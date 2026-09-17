# LLM-Assisted Cloud Incident Response — Implementation Spec

## Project Overview

Build an AI agent system that automatically detects, diagnoses, and (with human approval) remediates cloud infrastructure incidents on AWS. The system watches a demo application for failures, uses an LLM (via Amazon Bedrock) to reason about root cause using observability data, and either recommends or executes a fix.

**Core loop:** Detect → Collect Data → Diagnose (LLM) → Recommend/Remediate → Report → Log for Evaluation

This is a research/academic project (IEEE paper + presentation), so the implementation must also produce **structured, loggable output** at every stage for later evaluation (accuracy, hallucination rate, MTTR).

## Research Novelty (this is the paper's actual contribution — don't treat it as an afterthought)

Building a detect→diagnose→remediate agent is not novel by itself; several published systems already do this. This project's contribution is:

1. **Closed-loop remediation verification** — after a remediation action executes, the system automatically re-checks the same signal that triggered detection (metric, Config rule, trace) to confirm the incident actually resolved, rather than assuming a "successful" API call means the problem is fixed. This measures the gap between "the LLM correctly diagnosed the issue" and "the fix actually worked" — most existing systems stop at diagnosis and never verify.
2. **AWS-specific reasoning failure taxonomy** — every diagnosis is logged with enough structure to manually (or semi-automatically) categorize *how* the LLM's reasoning went wrong when it did (e.g., confused a metric name with a resource ARN, hallucinated an IAM permission not present in the fetched policy, mistook correlation in an X-Ray trace for causation). This produces a small taxonomy specific to AWS observability data, which does not yet exist in published work.

Both of these require no new AWS services beyond what's already in this spec — they are additional logging/verification steps layered onto the same pipeline. Do not skip these when implementing Phase 6 and Phase 7 — they are the difference between "a working demo" and "a publishable contribution."

---

## Scope: 3 Fault Classes

Build the full pipeline for all three of these. Do not expand scope beyond these three without updating this spec.

1. **Resource exhaustion** — CPU/memory spike on a compute resource
2. **Misconfiguration** — publicly exposed S3 bucket or overly permissive IAM policy
3. **Service failure cascade** — one service failing causes downstream errors in a dependent service

---

## Tech Stack

- **Cloud**: AWS (assume account + credits already available)
- **LLM**: Amazon Bedrock (Claude Sonnet, via Global cross-Region inference profile — e.g. `global.anthropic.claude-sonnet-4-6` — for ap-south-1) — use `bedrock-runtime InvokeModel` via boto3
- **RAG**: Direct context injection, NOT Bedrock Knowledge Bases / OpenSearch Serverless. The runbook corpus is only 3 short markdown files (under 1 page each) — there is no need for a vector store. Load all 3 runbook files directly and inject the relevant one(s) into the prompt as plain text context, selected by `fault_class`. This avoids OpenSearch Serverless entirely, which has a real, documented cost floor of ~$175-700/month even when idle — pure waste for a corpus this small. Document this as a deliberate methodology choice in the paper (see "RAG vs. no-RAG" evaluation in Phase 7), not a shortcut.
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
  runbook_loader.py           # loads the correct runbook(s) as plain text for prompt injection (no vector store)
/fault_injection
  inject_resource_exhaustion.py
  inject_misconfiguration.py
  inject_service_cascade.py
/evaluation
  run_evaluation.py          # runs fault injection N times, logs results
  metrics.py                  # computes MTTR, RCA accuracy, hallucination rate
  results/                    # output CSVs/JSON for the paper
/dashboard
  /api
    dashboard_api_lambda.py    # GET /incidents, GET /incidents/{id}, GET /results — read-only, no write paths
  /web
    src/
      IncidentFeed.jsx          # live-polling list of incidents with state badges
      IncidentDetail.jsx        # raw data, reasoning_trace, diagnosis, verification side-by-side
      MetricsPanel.jsx          # MTTR / RCA accuracy / hallucination rate / diagnosis-recovery gap charts
      ReplayMode.jsx             # steps through a saved past incident at demo speed
    package.json
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
    "used_rag": "boolean — false when running the no-context-injection ablation for comparison",
    "failure_mode": "string | null — populated during manual/semi-automated evaluation review; e.g. 'metric_arn_confusion', 'hallucinated_permission', 'correlation_as_causation', 'none' if diagnosis was clean"
  },
  "remediation": {
    "status": "pending_approval | approved | executed | rejected | failed",
    "action_taken": "string",
    "executed_at": "ISO8601 timestamp | null"
  },
  "verification": {
    "status": "not_run | resolved | not_resolved | inconclusive",
    "checked_at": "ISO8601 timestamp | null",
    "signal_rechecked": "string — which metric/Config rule/trace was re-queried post-remediation",
    "notes": "string — brief explanation of what the recheck found"
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

### Phase 4: Runbook context + diagnosis
13. Write the 3 runbook markdown files (keep each under 1 page — plain, procedural, how a human would diagnose/fix each fault type). Store them in `/knowledge_base/` and also copy to S3 for reference/audit purposes.
14. Implement `runbook_loader.py`: a simple function that takes `fault_class` and returns the matching runbook's full text (plain file read, no embeddings, no vector search — the corpus is 3 files, this is a lookup, not retrieval)
15. Implement `prompts.py` — one prompt template per fault_class, each instructing the model to: read the incident data, use the injected runbook text as context, and return ONLY the JSON contract above, nothing else
16. Implement `diagnosis_lambda.py`:
    - Reads raw_data.json from S3
    - Loads the matching runbook text via `runbook_loader.py` (unless `used_rag=false` is set for the ablation run, in which case skip this step entirely and rely on the model's own knowledge)
    - Constructs the prompt (incident data + runbook text as context)
    - Calls `bedrock-runtime InvokeModel` with the Claude Sonnet inference profile
    - Parses and validates the JSON response against the contract; retry once with an error-correction prompt if invalid
    - Sets `diagnosis.used_rag` based on whether runbook context was included
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

### Phase 6.5: Closed-loop verification (core novelty — do not skip)
21. Implement a `verification_lambda.py` (or a final step inside `remediation_lambda.py` if simpler): after a remediation action executes, wait a short fixed interval (e.g., 2-5 minutes, long enough for the fix to take effect), then re-query the *same signal* that originally triggered detection for this incident:
    - Resource exhaustion → re-check the CloudWatch metric that crossed the alarm threshold
    - Misconfiguration → re-check the Config rule compliance status or re-run the GuardDuty-equivalent check on the resource
    - Service cascade → re-check the X-Ray trace / error rate on the affected services
22. Compare the rechecked signal against the original alarm threshold/condition. Write the result to `IncidentRecord.verification`: `resolved` (signal back to normal), `not_resolved` (signal still triggering), or `inconclusive` (ambiguous/insufficient data)
23. This step runs for both real and injected incidents — it's what lets you measure the diagnosis-recovery gap (cases where `diagnosis.confidence` was high but `verification.status` came back `not_resolved`)

### Phase 7: Fault injection + evaluation harness
24. Implement the 3 injection scripts — each deliberately triggers its fault class against the demo app (e.g., a CPU-burn script for exhaustion, a script that flips an S3 bucket to public, a script that kills service-c to cascade failures into service-a/b)
25. Implement `run_evaluation.py`: runs each injection script N times (aim for 15-20 runs per class), waits for the pipeline (including the Phase 6.5 verification step) to complete, pulls the resulting `IncidentRecord` from DynamoDB, and logs ground truth vs actual diagnosis vs verification outcome
26. Implement `metrics.py`:
    - **MTTR**: `remediation.executed_at - detected_at`
    - **RCA accuracy**: does `diagnosis.root_cause` semantically match `ground_truth.true_fault_class`? (use simple keyword/rule-based scoring as the primary metric to avoid LLM-judging-LLM bias; optionally compute a secondary LLM-judge score for comparison and document both methods clearly)
    - **Hallucination rate**: does `reasoning_trace` reference any resource/metric not present in `raw_data.json`? (script a basic check, or manually audit a sample — document either way)
    - **Diagnosis-recovery gap** (novelty metric): % of incidents where `diagnosis.confidence` was high (e.g. >0.7) but `verification.status == not_resolved` — this is your headline result for the "diagnosis isn't the same as recovery" contribution
    - **Failure mode distribution** (novelty metric): tally of `diagnosis.failure_mode` values across all runs — produces the taxonomy breakdown table for the paper (this requires a manual or semi-automated review pass over `reasoning_trace` for incidents where diagnosis was wrong or `verification.status == not_resolved`; define 4-6 failure mode categories after reviewing your first ~20 traces, don't predefine them before seeing real data)
    - Add a flag to rerun a subset of evaluation with `used_rag=false` (skip runbook context injection) to compare context-injection vs no-context accuracy/hallucination/verification outcomes
27. Output all results to `/evaluation/results/` as CSV + summary JSON, ready to turn into paper graphs (include a dedicated `failure_taxonomy.csv` and `diagnosis_recovery_gap.csv`)

### Phase 8: Presentation dashboard (read-only visualization layer)

**Why this phase exists:** every prior phase produces state changes visible only in DynamoDB/CloudWatch/S3. There is currently nothing to show a live audience. This phase adds a thin, strictly read-only visualization layer on top of the existing pipeline — it must not introduce any new write paths, remediation logic, or business logic. If it's not on screen, it doesn't belong in this phase.

28. Implement `dashboard_api_lambda.py` behind a new API Gateway route (reuse the existing HTTP API from Phase 5's `approval_handler` if simpler, just add routes, don't stand up a second API Gateway):
    - `GET /incidents` — returns recent `IncidentRecord` items from DynamoDB, newest first, paginated
    - `GET /incidents/{incident_id}` — returns the full record, plus fetches `raw_data.json` from S3 for that incident so the detail view can show original observability data alongside the diagnosis
    - `GET /results` — returns the latest summary JSON from `/evaluation/results/` (MTTR, RCA accuracy, hallucination rate, diagnosis-recovery gap, failure mode distribution)
    - IAM role for this Lambda: read-only on the `incidents` table and the incident-data S3 bucket. No remediation, no approval, no write permissions of any kind — this is a hard guardrail, not a suggestion (see Guardrails section below)
29. Build `/dashboard/web` as a minimal React app (Vite, no backend framework needed — it only talks to the API above):
    - `IncidentFeed.jsx`: polls `GET /incidents` every few seconds, renders each incident as a card that visually reflects its current pipeline stage (`detected` → `diagnosing` → `pending_approval` → `approved` → `executed` → `resolved` / `not_resolved`). This is the main "watch it happen live" view for a demo.
    - `IncidentDetail.jsx`: click into a card to see the raw collected data, the full `diagnosis` block (including `reasoning_trace`), the `remediation` block, and the `verification` block side by side — specifically laid out so a viewer can visually compare `diagnosis.confidence` against `verification.status` in one glance, since that comparison is the paper's headline result
    - `MetricsPanel.jsx`: renders the Phase 7 evaluation results (`results/*.json`/CSV) as charts — MTTR distribution, RCA accuracy, hallucination rate, and the two novelty metrics (diagnosis-recovery gap, failure-mode taxonomy breakdown)
    - `ReplayMode.jsx`: lets you pick a past incident_id from an evaluation run and step through its state transitions at a controlled pace (e.g., 1 stage every 3 seconds), so the demo doesn't depend on a live fault injection completing cleanly in front of an audience
30. Deploy the React build as a static site (S3 + CloudFront, or just `npm run build` + local `vite preview` for the actual presentation if you don't want to manage another CloudFront distribution) — add this to `template.yaml` only if you want it reproducible via SAM; a manually-hosted static build is acceptable here since it's a demo surface, not part of the evaluated pipeline
31. Confirm end-to-end: trigger a fault injection script from Phase 7, watch the incident card move through every state on the dashboard in real time, then open the detail view and confirm `reasoning_trace`, `diagnosis`, and `verification` all render correctly

**Optional stretch additions** (do these only if time allows after 28–31 are solid — do not let them delay the core dashboard):
- Confidence-calibration chart in `MetricsPanel.jsx`: plot `diagnosis.confidence` vs actual correctness across all injected runs
- Hallucination highlighting in `IncidentDetail.jsx`: highlight the specific sentence(s) in `reasoning_trace` that reference a resource/metric absent from `raw_data.json`
- A small `used_rag=true` vs `used_rag=false` toggle/filter on `MetricsPanel.jsx` to visually contrast the RAG-ablation results already computed in Phase 7

---

## Guardrails / Non-negotiables

- Remediation Lambda IAM role must be scoped to ONLY the specific actions listed in `actions.py` — no wildcard permissions
- No remediation executes without a status change to `approved` in DynamoDB first
- LLM output must be JSON-schema validated before being used anywhere downstream — never execute an action based on unparsed/free-text LLM output
- Every incident, whether real or injected, gets logged to DynamoDB — this is your evaluation dataset, don't skip logging even during manual testing
- Keep prompts and runbooks in version control as plain files (`prompts.py`, `/knowledge_base/*.md`) so changes are diffable for the paper's methodology section
- Do NOT skip the Phase 6.5 verification step or the failure-mode logging to save time — these are the paper's actual novel contribution, not optional polish. A working demo without these is a class project; with these, it's a publishable result.
- Do NOT provision Bedrock Knowledge Bases / OpenSearch Serverless anywhere in this project, including via the console's "quick create" option — it auto-provisions an OpenSearch Serverless collection with a real cost floor even when idle, and deleting the Knowledge Base does not delete the underlying collection
- The Phase 8 dashboard Lambda/IAM role must be strictly read-only (DynamoDB `GetItem`/`Query` and S3 `GetObject` only) — it must never be granted permissions that could approve, remediate, or otherwise mutate incident state. The dashboard visualizes the pipeline; it is never part of it.

---

## Suggested build order for a vibecoding session

If feeding this to an AI IDE one phase at a time, do it in this order and confirm each phase deploys/runs before moving to the next:

1. Phase 0 (infra skeleton) → confirm `sam deploy` succeeds
2. Phase 1 (demo app) → confirm services communicate
3. Phase 2 + 3 (detection + collection) → manually trigger a fault, confirm data lands in S3/DynamoDB
4. Phase 4 (diagnosis) → confirm a valid JSON diagnosis is produced for a real triggered fault, using injected runbook context (no Knowledge Base/OpenSearch)
5. Phase 5 (reporting/approval) → confirm Slack message + approval flow works
6. Phase 6 (remediation) → confirm an approved incident actually executes the fix
7. Phase 6.5 (verification) → confirm the system re-checks the original signal post-remediation and correctly logs resolved/not_resolved
8. Phase 7 (evaluation) → run the full harness including the RAG-ablation and failure-mode review pass, generate results for the paper
9. Phase 8 (presentation dashboard) → confirm the incident feed reflects live pipeline state end-to-end, and that the metrics panel correctly renders Phase 7's evaluation output; this phase can start as soon as Phase 3 is stable (the incident feed only needs `detected` records to exist) and doesn't need to wait for Phase 7, but the metrics/replay views do need Phase 7's results

Each phase should be a separate PR/commit so the team's workstreams can build in parallel once Phase 0-3 are stable and merged. Phase 8 can be built in parallel with Phases 4-7 by a separate team member once Phase 3 is merged, since it only depends on `IncidentRecord` existing in DynamoDB, not on any later phase's logic.