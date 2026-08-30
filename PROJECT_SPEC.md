# LLM-Assisted Cloud Incident Response — Implementation Spec

## Project Overview

Build an AI agent system that automatically detects, diagnoses, and (with human approval) remediates cloud infrastructure incidents on AWS. The system watches a demo application for failures, uses an LLM (via Amazon Bedrock) to reason about root cause using observability data, and either recommends or executes a fix.

**Core loop:** Detect → Collect Data → Diagnose (LLM) → Recommend/Remediate → Report → Log for Evaluation

This is a research/academic project (IEEE paper + presentation), so the implementation must also produce **structured, loggable output** at every stage for later evaluation (accuracy, hallucination rate, MTTR).

---

## Scope: 3 Fault Classes

Build the full pipeline for all three of these. Do not expand scope beyond these three without updating this spec.

1. **Resource exhaustion** — CPU/memory spike on a compute resource
2. **Misconfiguration** — publicly exposed S3 bucket or overly permissive IAM policy
3. **Service failure cascade** — one service failing causes downstream errors in a dependent service

---

## Tech Stack

- **Cloud**: AWS (assume account + credits already available)
- **LLM**: Amazon Bedrock (Claude model) — use `bedrock-runtime InvokeModel` via boto3
- **RAG**: Amazon Bedrock Knowledge Bases (backed by OpenSearch Serverless, auto-provisioned)
- **Compute**: AWS Lambda (Python 3.12 runtime) for all backend logic
- **Detection**: CloudWatch Alarms, EventBridge Rules, AWS Config, Amazon GuardDuty
- **Tracing**: AWS X-Ray (for the cascade fault class)
- **Storage**: S3 (raw incident data lake + runbook docs), DynamoDB (structured incident records)
- **Approval/reporting**: SNS → Slack (via incoming webhook, simplest path — skip AWS Chatbot complexity)
- **IaC**: AWS SAM (Serverless Application Model) — use this to define all Lambda functions, EventBridge rules, IAM roles, and DynamoDB tables in one `template.yaml`. Do NOT click-ops resources in the console; everything must be reproducible from code.
- **Language**: Python for all Lambda functions and scripts
- **Demo app**: A minimal 2-3 service app deployed on ECS Fargate or Lambda (built as part of this project, not the AWS PetShop workshop app — keep it simple and fully owned)

---

## Repository Structure

```
/infra
  template.yaml              # SAM template: all AWS resources
  /demo-app                  # the toy microservice app to break
    service-a/
    service-b/
    service-c/
/src
  /detectors                 # fault-specific detection config (CFN/SAM fragments + any custom logic)
  /collector
    collector_lambda.py      # gathers CloudWatch/Config/X-Ray/GuardDuty data on trigger
  /diagnosis
    diagnosis_lambda.py      # calls Bedrock, returns structured diagnosis JSON
    prompts.py                # prompt templates, one per fault class
  /remediation
    remediation_lambda.py    # executes approved fix per fault class
    actions.py                 # one function per remediation action
  /reporting
    notify_lambda.py         # sends diagnosis + remediation status to Slack via SNS
  /approval
    approval_handler.py      # receives Slack button click / API call, triggers remediation
/knowledge_base
  runbook_resource_exhaustion.md
  runbook_misconfiguration.md
  runbook_service_cascade.md
/fault_injection
  inject_resource_exhaustion.py
  inject_misconfiguration.py
  inject_service_cascade.py
/evaluation
  run_evaluation.py          # runs fault injection N times, logs results
  metrics.py                  # computes MTTR, RCA accuracy, hallucination rate
  results/                    # output CSVs/JSON for the paper
/docs
  architecture.md
  data_schema.md
README.md
```

---

## Data Contracts (define these first — everything else depends on them)

### `IncidentRecord` (DynamoDB table: `incidents`)
```json
{
  "incident_id": "uuid",
  "fault_class": "resource_exhaustion | misconfiguration | service_cascade",
  "detected_at": "ISO8601 timestamp",
  "raw_data_s3_key": "incidents/{incident_id}/raw_data.json",
  "diagnosis": {
    "root_cause": "string",
    "confidence": "float 0-1",
    "affected_resources": ["string"],
    "suggested_action": "string (maps to a remediation action key)",
    "reasoning_trace": "string — the LLM's full reasoning, for hallucination auditing",
    "used_rag": "boolean"
  },
  "remediation": {
    "status": "pending_approval | approved | executed | rejected | failed",
    "action_taken": "string",
    "executed_at": "ISO8601 timestamp | null"
  },
  "ground_truth": {
    "true_fault_class": "string — only populated during fault-injection evaluation runs",
    "injected_at": "ISO8601 timestamp"
  }
}
```

### Diagnosis Lambda output contract (LLM must return exactly this JSON — enforce with a strict system prompt and JSON schema validation, retry once on malformed output)
```json
{
  "root_cause": "string",
  "confidence": 0.0,
  "affected_resources": ["string"],
  "suggested_action": "scale_up | restart_service | lock_s3_bucket | tighten_iam_policy | restart_downstream_service | manual_review_required",
  "explanation": "string, plain-English, for the Slack report",
  "reasoning_trace": "string, step-by-step, for evaluation logging"
}
```

---

## Build Order (follow exactly — each phase depends on the last)

### Phase 0: Infra bootstrap
1. Initialize SAM project (`sam init`)
2. Define in `template.yaml`: S3 bucket (incident data lake), DynamoDB table (`incidents`, partition key `incident_id`), IAM roles (one for collector/diagnosis Lambdas with read-only observability + Bedrock invoke permissions; one separate, tightly-scoped role for remediation Lambda)
3. Deploy empty skeleton, confirm `sam deploy` works end to end

### Phase 1: Demo app
4. Build 3 minimal services (e.g., `service-a` calls `service-b` calls `service-c`), each a small Flask/FastAPI app in Lambda or Fargate, instrumented with X-Ray SDK
5. Deploy demo app via SAM, confirm services talk to each other successfully
6. Enable CloudWatch Logs, Container/Lambda Insights, X-Ray tracing on all three

### Phase 2: Detection
7. Add CloudWatch Alarm on CPU/memory for the resource-exhaustion fault class, targeting one of the demo services
8. Enable AWS Config with a rule for public S3 buckets and permissive IAM policies; add EventBridge rule on Config non-compliance events
9. Enable GuardDuty; add EventBridge rule for relevant finding types
10. Add a composite/custom CloudWatch alarm across services for the cascade fault class (e.g., error rate spike on service-a correlated with service-c latency)
11. Point all EventBridge rules at the same `collector_lambda` target, passing fault_class as part of the event payload

### Phase 3: Data collection
12. Implement `collector_lambda.py`:
    - Receives EventBridge event, extracts fault_class + resource identifiers
    - Queries CloudWatch Logs Insights (last 15 min of relevant logs)
    - Queries CloudWatch metrics for the affected resource
    - If fault_class is misconfiguration: fetches the Config/GuardDuty finding detail
    - If fault_class is service_cascade: fetches X-Ray trace summary for the affected service graph
    - Writes bundled JSON to S3 at `incidents/{incident_id}/raw_data.json`
    - Writes initial `IncidentRecord` to DynamoDB with status `detected`
    - Invokes `diagnosis_lambda` (async invoke or via EventBridge)

### Phase 4: Knowledge base + diagnosis
13. Write the 3 runbook markdown files (keep each under 1 page — plain, procedural, how a human would diagnose/fix each fault type)
14. Upload runbooks to S3, create a Bedrock Knowledge Base pointed at that S3 prefix, sync it
15. Implement `prompts.py` — one prompt template per fault_class, each instructing the model to: read the incident data, use retrieved runbook context, and return ONLY the JSON contract above, nothing else
16. Implement `diagnosis_lambda.py`:
    - Reads raw_data.json from S3
    - Retrieves relevant runbook chunks from the Knowledge Base (Bedrock `Retrieve` API)
    - Constructs the prompt (data + retrieved context)
    - Calls `bedrock-runtime InvokeModel`
    - Parses and validates the JSON response against the contract; retry once with an error-correction prompt if invalid
    - Updates the `IncidentRecord` in DynamoDB with the diagnosis
    - Invokes `notify_lambda`

### Phase 5: Reporting + approval
17. Implement `notify_lambda.py`: formats the diagnosis into a readable Slack message (root cause, confidence, suggested action, explanation) and posts via Slack incoming webhook; include an approval link/command in the message
18. Implement `approval_handler.py` as an API Gateway + Lambda endpoint: receives an approve/reject call (triggered by a Slack slash command or a simple button-style link), updates DynamoDB status, and if approved, invokes `remediation_lambda`

### Phase 6: Remediation
19. Implement `actions.py` with one function per action key from the contract:
    - `scale_up`: call Application Auto Scaling or update Lambda concurrency/EC2 instance type
    - `restart_service`: restart the relevant ECS task or Lambda
    - `lock_s3_bucket`: call `s3:PutPublicAccessBlock` on the flagged bucket
    - `tighten_iam_policy`: attach a corrected policy (have a pre-defined safe policy ready, don't have the LLM generate IAM policy JSON directly)
    - `restart_downstream_service`: restart the failing dependency
    - `manual_review_required`: no-op, just flags for a human
20. Implement `remediation_lambda.py`: reads the approved incident, calls the matching action function, updates DynamoDB status to `executed` or `failed`

### Phase 7: Fault injection + evaluation harness
21. Implement the 3 injection scripts — each deliberately triggers its fault class against the demo app (e.g., a CPU-burn script for exhaustion, a script that flips an S3 bucket to public, a script that kills service-c to cascade failures into service-a/b)
22. Implement `run_evaluation.py`: runs each injection script N times (aim for 15-20 runs per class), waits for the pipeline to complete, pulls the resulting `IncidentRecord` from DynamoDB, and logs ground truth vs actual diagnosis
23. Implement `metrics.py`:
    - **MTTR**: `remediation.executed_at - detected_at`
    - **RCA accuracy**: does `diagnosis.root_cause` semantically match `ground_truth.true_fault_class`? (use simple keyword/LLM-judge scoring, document your method in the paper)
    - **Hallucination rate**: does `reasoning_trace` reference any resource/metric not present in `raw_data.json`? (can script a basic check, or manually audit a sample — document either way)
    - Add a flag to rerun a subset of evaluation with `used_rag=false` (bypass Knowledge Base retrieval) to compare RAG vs no-RAG accuracy/hallucination
24. Output all results to `/evaluation/results/` as CSV + summary JSON, ready to turn into paper graphs

---

## Guardrails / Non-negotiables

- Remediation Lambda IAM role must be scoped to ONLY the specific actions listed in `actions.py` — no wildcard permissions
- No remediation executes without a status change to `approved` in DynamoDB first
- LLM output must be JSON-schema validated before being used anywhere downstream — never execute an action based on unparsed/free-text LLM output
- Every incident, whether real or injected, gets logged to DynamoDB — this is your evaluation dataset, don't skip logging even during manual testing
- Keep prompts and runbooks in version control as plain files (`prompts.py`, `/knowledge_base/*.md`) so changes are diffable for the paper's methodology section

---

## Suggested build order for a vibecoding session

If feeding this to an AI IDE one phase at a time, do it in this order and confirm each phase deploys/runs before moving to the next:

1. Phase 0 (infra skeleton) → confirm `sam deploy` succeeds
2. Phase 1 (demo app) → confirm services communicate
3. Phase 2 + 3 (detection + collection) → manually trigger a fault, confirm data lands in S3/DynamoDB
4. Phase 4 (diagnosis) → confirm a valid JSON diagnosis is produced for a real triggered fault
5. Phase 5 (reporting/approval) → confirm Slack message + approval flow works
6. Phase 6 (remediation) → confirm an approved incident actually executes the fix
7. Phase 7 (evaluation) → run the full harness, generate results for the paper

Each phase should be a separate PR/commit so the team's workstreams can build in parallel once Phase 0-3 are stable and merged.
