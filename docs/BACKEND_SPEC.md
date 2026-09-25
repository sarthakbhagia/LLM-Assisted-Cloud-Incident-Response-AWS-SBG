# LLM-Assisted Cloud Incident Response — Detailed Backend Specification

**Status: All Phases (0-8) Deployed and Operational** — Backend Pytest: 73/73 tests passed (100%), SAM validation: zero errors, all Lambdas deployed in ap-south-1 (account 889081505756) as of September 25, 2026.

This document provides a detailed architectural and technical breakdown of the backend implementation for the LLM-Assisted Cloud Incident Response system. It serves as an extension of the primary `PROJECT_SPEC.md`.

## 1. High-Level Architecture
The backend is completely serverless, utilizing AWS SAM for Infrastructure as Code (IaC) and Python 3.12 for all compute logic. 

The core flow is: **Detect -> Collect -> Diagnose -> Notify -> Approve -> Remediate -> Verify**.

Each stage is handled by an independent AWS Lambda function, orchestrated either synchronously (direct invocation) or asynchronously (EventBridge / API Gateway).

### Core Services
- **Storage**: Amazon S3 (Data Lake for raw evidence and runbooks), Amazon DynamoDB (State machine and structured records).
- **Compute**: AWS Lambda functions deployed via SAM.
- **AI/LLM**: Amazon Bedrock (Claude 3.5 Sonnet).
- **Event Orchestration**: Amazon EventBridge, AWS Config, Amazon CloudWatch Alarms.
- **Remediation & Security**: AWS IAM, Auto Scaling, Amazon S3 Public Access Block, Amazon ECS.

---

## 2. Component Details

### 2.1 Demo Application (Phase 1)
To generate incidents, the environment hosts three dummy microservices deployed as Lambda functions:
- **Service A** (`/start`): Calls Service B. Monitored for Errors and Duration (Resource Exhaustion).
- **Service B** (`/service-b`): Middle-tier. Calls Service C.
- **Service C** (`/service-c`): Downstream dependency. Monitored for high latency (Service Cascade).
All services are instrumented with AWS X-Ray.

### 2.2 Detection Layer (Phase 2)
The detection layer is powered by native AWS observability tools, routing events to EventBridge:
1. **CloudWatch Alarms**: 
   - `incident-service-a-resource-exhaustion`: Triggers on high Lambda duration.
   - `incident-service-a-errors` & `incident-service-c-latency`: Combine into a `CompositeAlarm` for detecting service cascade failures.
2. **AWS Config Rules**: 
   - `incident-public-s3`: Detects public S3 buckets.
   - `incident-iam-policy`: Detects overly permissive IAM policies.
3. **Amazon GuardDuty**: Routes specific security findings.

**Event Routing**: EventBridge rules capture these state changes (`ALARM`, `NON_COMPLIANT`, etc.) and route them to the **Collector** Lambda function using an InputTransformer to standardize the payload with a `fault_class` and `source`.

### 2.3 Collector Layer (Phase 3)
- **Function**: `src/collector/app.py`
- **Role**: `incident-collector-diagnosis-role`
- **Responsibilities**:
  - Receives the normalized event from EventBridge.
  - Queries AWS observability tools (CloudWatch Logs, Metrics, X-Ray traces, AWS Config history, GuardDuty findings) based on the `fault_class`.
  - Packages the raw evidence into a structured JSON payload.
  - Saves the payload to the S3 Incident Data Lake (`incidents/{incident_id}/raw_data.json`).
  - Initializes the `IncidentRecord` in DynamoDB with a status of `detected`.
  - Asynchronously invokes the **Diagnosis** Lambda function.

### 2.4 Diagnosis Layer (Phase 4)
- **Function**: `src/diagnosis/app.py`
- **Role**: `incident-collector-diagnosis-role`
- **Responsibilities**:
  - Receives the `incident_id` from the Collector.
  - Fetches the raw evidence bundle from S3.
  - Loads the appropriate markdown runbook from S3 / local storage (RAG injection context).
  - Constructs a highly structured prompt combining the raw evidence, runbook context, and strict system instructions.
  - Invokes Amazon Bedrock (`Claude 3.5 Sonnet`) to determine root cause, confidence, and suggested remediation action.
  - Validates the LLM output against a strict JSON schema. If validation fails, it issues a 1-try error correction prompt.
  - Updates the DynamoDB `IncidentRecord` with the diagnosis and reasoning trace.
  - Invokes the **Notify** Lambda function.

### 2.5 Reporting & Approval Layer (Phase 5)
- **Functions**: `src/reporting/app.py` (Notify), `src/approval/app.py` (Approve/Reject API)
- **Role**: `incident-reporting-approval-role`
- **Responsibilities**:
  - **Notify**: Formats a human-readable summary of the diagnosis and suggested action. Generates HMAC-signed Approval and Rejection links. Posts the message to a Slack Webhook (secured in SSM). Updates state to `pending_approval`.
  - **Approval API**: An API Gateway endpoint that receives GET/POST requests from Slack actions. Validates the HMAC signature. Updates the DynamoDB state to `approved` or `rejected`. If approved, invokes the **Remediation** Lambda.

### 2.6 Remediation Layer (Phase 6)
- **Function**: `src/remediation/app.py` (and `actions.py`)
- **Role**: `incident-remediation-role` (Strictly scoped permissions, no wildcards)
- **Responsibilities**:
  - Verifies the incident is in the `approved` state.
  - Executes the predefined Python function corresponding to the `suggested_action` (e.g., `scale_up`, `lock_s3_bucket`, `tighten_iam_policy`).
  - Updates DynamoDB state to `executed` or `failed`.
  - Invokes the **Verification** Lambda function to close the loop.

### 2.7 Verification Layer (Phase 6.5)
- **Function**: `src/verification/app.py`
- **Responsibilities**:
  - Implements a programmatic delay (wait time for the fix to propagate).
  - Re-queries the exact original signal that triggered the incident (e.g., re-checks the specific CloudWatch metric or AWS Config rule status).
  - Evaluates if the fix actually resolved the underlying signal.
  - Updates the `verification.status` in DynamoDB to `resolved`, `not_resolved`, or `inconclusive`. This enables measuring the "diagnosis-recovery gap".

---

## 3. Data Architecture

### 3.1 DynamoDB Schema (`incidents` Table)
The state of the system is managed entirely through DynamoDB.
- **Partition Key**: `incident_id` (String / UUID)
- **Core Attributes**:
  - `fault_class` (String): Resource exhaustion, misconfiguration, or service cascade.
  - `raw_data_s3_key` (String): Pointer to evidence in S3.
  - `diagnosis` (Map): Contains `root_cause`, `confidence`, `suggested_action`, `reasoning_trace`, `used_rag`, and `failure_mode`.
  - `remediation` (Map): Contains `status` (`detected`, `pending_approval`, `approved`, `executed`, `rejected`, `failed`), `action_taken`, and `executed_at`.
  - `verification` (Map): Contains `status` (`resolved`, `not_resolved`), `checked_at`, and `signal_rechecked`.

### 3.2 S3 Data Lake
Stores immutable artifacts for reproducibility and evaluation:
- `incidents/{incident_id}/raw_data.json`: The raw JSON bundle from the collector.
- `runbooks/{fault_class}.md`: The markdown operational runbooks injected into the prompt context.

---

## 4. Security & Permissions Boundary
A critical architectural decision is the isolation of IAM roles:
1. **Collector/Diagnosis Role**: Granted extensive read-only access to CloudWatch, X-Ray, Config, and GuardDuty, plus Bedrock invoke permissions and limited S3/DynamoDB write access. It **cannot** modify infrastructure.
2. **Reporting/Approval Role**: Granted read access to DynamoDB/S3 and SSM Parameter Store for secure webhooks/secrets.
3. **Remediation Role**: Extremely locked down. Only allowed to perform exact remediation actions (e.g., `s3:PutPublicAccessBlock`, `application-autoscaling:RegisterScalableTarget`). It is invoked solely by the Approval handler.

---

## 5. Frontend Support Requirements

These are additional backend changes required **after** all `PROJECT_SPEC.md` phases are complete, specifically to support the frontend described in `FRONTEND_SPEC.md`. They are not in `PROJECT_SPEC.md` but are all straightforward additions that do not change the core pipeline.

**Status: All items implemented** — The `DashboardActionsFunction` Lambda provides all required endpoints including per-stage timestamps, approver identity, before/after metric snapshots, live service health, and confidence vs correctness data.

### 5.1 Per-Stage Pipeline Timestamps (enables accurate Lifecycle Timeline) — IMPLEMENTED

**Problem**: The frontend Lifecycle Timeline only has `detected_at`, `remediation.executed_at`, and `verification.checked_at` from DynamoDB. The Diagnose, Notify, and Approve stages show no real timestamps.

**Required change**: Add the following fields to the `IncidentRecord` DynamoDB schema and write them at the appropriate stage:
- `collected_at` — written by Collector Lambda just before it invokes Diagnosis.
- `diagnosed_at` — written by Diagnosis Lambda after it updates DynamoDB with the diagnosis.
- `notified_at` — written by Notify Lambda after it posts the Slack message.
- `approved_at` — written by Approval Handler when status changes to `approved` or `rejected`.

All four are ISO8601 strings, nullable until the stage completes.

**Implementation**: `DashboardActionsFunction` provides these via the `/trace` and `/trace/artifact` endpoints; incident records now include per-stage timestamps.

---

### 5.2 Approver Identity and Rejection Reason (enables Approval Audit Trail) — IMPLEMENTED

**Problem**: The Approval Handler currently writes `approved` or `rejected` to `remediation.status` but does not record who approved or why it was rejected.

**Required changes**:
- Add `remediation.approved_by` (string, nullable) — the identifier of the approver. This can be a query parameter passed in the approval link or a value from a JWT claim if auth is added.
- Add `remediation.rejected_reason` (string, nullable) — the rejection reason text submitted via the frontend Reject form. The approval endpoint must accept a `reason` field in the POST body and write it to DynamoDB.

**Implementation**: Approval endpoint now captures `approved_by` from request context and `rejected_reason` from POST body; stored in DynamoDB and returned via `/incidents/{id}`.

---

### 5.3 Before/After Metric Snapshots for Verification Panel (enables numerical comparison display) — IMPLEMENTED

**Problem**: The Verification Lambda writes only a human-readable `notes` string (e.g., "Max Duration = 1400ms vs threshold 50000ms"). The frontend cannot render a structured before/after comparison from a plain string.

**Required change**: After the verification wait period, before writing the result, the Verification Lambda should fetch the final metric value and compare it against the value stored in the collector's evidence. Write two additional fields to `verification`:
- `verification.pre_remediation_value` — the relevant metric value at incident detection time, extracted from `raw_data.json`.
- `verification.post_remediation_value` — the metric value re-fetched after the wait period.
- `verification.threshold` — the alarm threshold value used for the comparison.

These are numbers, not strings, allowing the frontend to render a structured "Before: 8200ms / Threshold: 50000ms / After: 1400ms" display.

**Implementation**: `DashboardActionsFunction` `/trace/artifact` endpoint returns structured before/after metric data from S3 raw evidence and verification re-checks.

---

### 5.4 Live Service Health Endpoint (enables live Service Map page) — IMPLEMENTED

**Problem**: There is no backend endpoint that returns the current real-time health of Service A, Service B, and Service C outside of an incident context. The `GET /api/services` endpoint required by the frontend does not exist.

**Required change**: Add a `GET /api/services` route to the Dashboard API Lambda (Phase 8) that:
- Queries CloudWatch for the last 5 minutes of Duration and Errors metrics for all three service Lambda functions.
- Queries the DynamoDB `incidents` table for any active (non-terminal) incidents and maps them to affected services.
- Returns a `ServiceNode[]` + `ServiceEdge[]` response describing the topology and per-node health.

This allows the Service Map page to show live latency and error rate on nodes and highlight affected services.

**Implementation**: `DashboardActionsFunction` provides `GET /services` endpoint returning `ServiceNode[]` and `ServiceEdge[]` with live CloudWatch metrics and incident overlays.

---

### 5.5 Confidence vs Correctness per Incident (enables calibration scatter chart in Analytics) — IMPLEMENTED

**Problem**: The Phase 7 `metrics.py` computes aggregate accuracy across all evaluation runs, but the Analytics scatter chart requires a per-incident data point: `(diagnosis.confidence, is_correct)`.

**Required change**: During evaluation runs, after each incident's pipeline completes, `run_evaluation.py` should write a `diagnosis.is_correct` boolean to the `IncidentRecord` based on whether `diagnosis.root_cause` semantically matched `ground_truth.true_fault_class` using the keyword/rule-based scoring from `metrics.py`. This field is only populated for fault-injection evaluation runs (where `ground_truth.true_fault_class` is known), never for real incidents.

**Implementation**: Evaluation harness populates `diagnosis.is_correct` in DynamoDB for injected incidents; `DashboardActionsFunction` `/results` endpoint returns per-incident confidence/correctness pairs for the scatter chart.
