# CHANGES.md

Summary of fixes applied to the LLM-Assisted Cloud Incident Response project.

## P0 - Evaluation Integrity

### P0-1: Move mock results to mock/ subfolder and add synthetic flag ✅
- **Files**: `evaluation/run_evaluation.py`, `evaluation/metrics.py`, `tests/test_evaluation.py`
- **Changes**:
  - Moved existing evaluation results from `evaluation/results/` to `evaluation/results/mock/`
  - Added `"synthetic": true` to mock summary.json
  - Modified `run_evaluation()` to always write mock runs to `mock/` subfolder
  - Updated tests to expect output in `mock/` subfolder

### P0-2: Implement live path in run_evaluation() ✅
- **Files**: `evaluation/run_evaluation.py`
- **Changes**:
  - Added `_wait_for_incident_created()` to poll DynamoDB until a NEW incident is created for each injection (fault_class matches AND detected_at >= injected_at)
  - Added `_wait_for_incident_completion()` to poll DynamoDB until incident reaches terminal state (verification.status set or timeout)
  - Added `_build_record_from_dynamodb()` to build evaluation records from real DynamoDB items
  - Ground truth now comes from injection timestamp/fault_class, not from incident's own fault_class
  - Records injection timestamp and true fault class for each injection

### P0-3: Exclude synthetic incidents from RCA/diagnosis-recovery-gap metrics ✅
- **Files**: `evaluation/metrics.py`, `evaluation/run_evaluation.py`
- **Changes**:
  - Modified `compute_aggregate_metrics()` to track synthetic incidents separately
  - Primary metrics (rca_accuracy_pct, diagnosis_recovery_gap_pct) now exclude synthetic incidents
  - Added synthetic metrics bucket: `synthetic_incidents`, `synthetic_rca_accuracy_pct`, `synthetic_diagnosis_recovery_gap_pct`
  - Reports `used_rag` from what was actually loaded (via diagnosis.used_rag field)

## P0 - Verification Independent Check

### P0-4: Fix verification - replace sleep with env vars and polling ✅
- **Files**: `backend/verification/verification_lambda.py`, `backend/remediation/remediation_lambda.py`
- **Changes**:
  - Replaced hardcoded `time.sleep(120)` with configurable env vars:
    - `VERIFICATION_WAIT_SECONDS` (default 120, demo 15)
    - `VERIFICATION_POLL_SECONDS` (default 10)
    - `VERIFICATION_MAX_WAIT_SECONDS` (default 300)
  - Added `_poll_for_resolution()` that polls until resolved or max wait exceeded
  - Passes `remediation_completed_at` in verification payload
  - Ignores alarm state/datapoints older than remediation completion timestamp

### P0-5: Remove _reset_cloudwatch_alarm from normal remediation path ✅
- **Files**: `backend/remediation/actions.py`, `infra/template.yaml`
- **Changes**:
  - `_reset_cloudwatch_alarm()` now only executes when `DEMO_MODE=true`
  - Returns boolean indicating whether alarm was reset
  - All action functions return `alarm_reset` flag
  - Added `DEMO_MODE` parameter to template with conditional IAM policy for `cloudwatch:SetAlarmState` using `Fn::If`

### P0-6: Add active probe to verification ✅
- **Files**: `backend/verification/verification_lambda.py`, `infra/template.yaml`
- **Changes**:
  - Added `_active_probe_service_a()` that invokes Service A endpoint N times (configurable via `VERIFICATION_PROBE_COUNT`, default 5)
  - Computes success rate and p95 latency from probe responses
  - For resource_exhaustion: active probe is primary check; metric/alarm fallback only if probe fails
  - For service_cascade: active probe + Service C metric; alarm_state_fallback alone yields "inconclusive"
  - Added `evidence_type` field: `active_probe | metric | alarm_state_fallback | s3_direct | config | probe_unavailable | manual_review`
  - `alarm_state_fallback` alone never yields "resolved" (yields "inconclusive" or "resolved_unverified" in DEMO_MODE)
  - Probe success requires success_rate >= 0.8
  - Compare p95 to `PROBE_LATENCY_THRESHOLD_MS` (env, default 3000), not the 50000ms alarm threshold
  - If probe cannot run, set evidence_type "probe_unavailable" and do not return "resolved" from fallback path
  - Added `SERVICE_A_URL` env var to VerificationFunction (commented out to avoid circular dependency, with fallback to function URL discovery)

## P1 - Make Faults Real

### P1-7: Add genuine fault modes to services ✅
- **Files**: `backend/service_a/app.py`, `backend/service_b/app.py`, `backend/service_c/app.py`
- **Changes**:
  - **Service C**: Module-level fault state (`_FAULT_STATE`) with injected latency, error rate, error type, enabled flag
    - Authenticated `/service-c/fault` endpoint (POST/GET) to configure fault state
    - Bearer token auth via `FAULT_INJECTION_TOKEN` env var
  - **Service B**: Same fault injection pattern as Service C
  - **Service A**: Same fault injection pattern + throttling scenario support via reserved concurrency
  - Cold start via restart actually clears fault state (module-level variable reset on new Lambda init)
  - Throttling: reserved concurrency of 1 under load makes scale_up actually fix it

### P1-8: Create sacrificial DemoMisconfigBucket ✅
- **Files**: `infra/template.yaml`, `fault_injection/inject_misconfiguration.py`, `backend/demo_control/demo_control_lambda.py`
- **Changes**:
  - Added `DemoMisconfigBucket` to template with public access block initially DISABLED
  - No public bucket policy or ACL ever applied
  - Fault injector targets this bucket (not data lake bucket)
  - Remediation re-enables public access block; verification checks it
  - Data lake bucket NEVER touched by fault injection
  - Updated `inject_misconfiguration.py` and `demo_control_lambda.py` to use DemoMisconfigBucket

### P1-9: Optionally add Config rule for s3-bucket-level-public-access-prohibited ✅
- **Files**: `infra/template.yaml`
- **Changes**:
  - Added `CreateConfigRule` parameter (default false)
  - When true: creates AWS Config rule + EventBridge rule for Config compliance changes
  - EventBridge rule triggers collector on NON_COMPLIANT for DemoMisconfigBucket
  - Condition prevents creation if account already has Config recorder

### P1-10: Mark synthetic evidence in diagnosis ✅
- **Files**: `backend/diagnosis/diagnosis_lambda.py`, `backend/diagnosis/prompts.py`
- **Changes**:
  - Added synthetic evidence note to diagnosis prompt when `evidence.demo_synthetic=true`
  - Stores `evidence_synthetic` flag on IncidentRecord
  - UI and metrics can now show synthetic evidence banner

## P2 - Correctness and Config

### P2-11: Add cloudwatch:DescribeAlarms and guardduty:ListDetectors to CollectorDiagnosisRole ✅
- **Files**: `infra/template.yaml`
- **Changes**:
  - Added `cloudwatch:DescribeAlarms` to observability-read policy
  - Added `guardduty:ListDetectors` to observability-read policy

### P2-12: Fix runbook_loader to read from S3 ✅
- **Files**: `backend/diagnosis/runbook_loader.py`, `backend/diagnosis/diagnosis_lambda.py`
- **Changes**:
  - Priority: S3 (`s3://$DATA_LAKE_BUCKET/runbooks/<fault_class>.md`) → local filesystem → packaged fallback → default
  - Returns tuple `(content, source)` where source is `s3 | local | packaged | none`
  - Stores `runbook_source` on diagnosis output
  - If no runbook loaded, sets `used_rag=false` and logs source

### P2-13: Remove hardcoded account ID/region from scripts ✅
- **Files**: `scripts/sync_runbooks.sh`, `scripts/deploy.sh`
- **Changes**:
  - `sync_runbooks.sh`: Uses `aws sts get-caller-identity` for account ID; `AWS_REGION`/`AWS_DEFAULT_REGION` for region
  - `deploy.sh`: Uses `AWS_REGION`/`AWS_DEFAULT_REGION` for region; passes region to frontend config
  - No more hardcoded `889081505756` or `ap-south-1`
  - `deploy.sh`: Reads existing ServiceBUrl/ServiceCUrl from stack before deploying (preserves values from samconfig); passes DemoMode and FaultInjectionToken

### P2-14: Fix heuristic fallback in diagnosis_lambda.py ✅
- **Files**: `backend/diagnosis/diagnosis_lambda.py`
- **Changes**:
  - Misconfiguration heuristic now reads `config_rule` from `raw_data["detection_event"]` instead of `evidence.get("config_rule")`
  - Consistent with how collector stores the detection event

## Additional Improvements

### Diagnosis used_rag logic ✅
- **Files**: `backend/diagnosis/diagnosis_lambda.py`
- **Changes**:
  - Store `used_rag` as (request flag AND runbook_source != "none")
  - When runbook_source is "none", pass runbook_text=None so the prompt uses the no-runbook branch instead of placeholder text

### Verification gating ✅
- **Files**: `backend/verification/verification_lambda.py`, `backend/remediation/remediation_lambda.py`
- **Changes**:
  - Skip verification when result["success"] is False or action_key is "manual_review_required"
  - Write verification.status "not_run" with a note instead
  - Pass alarm_reset and evidence_synthetic flag in verification payload
  - If DEMO_MODE is true and alarm_reset is true and the only evidence is alarm state, return "resolved_unverified"
  - Never return "resolved" from alarm state alone

### Live evaluation enhancements ✅
- **Files**: `evaluation/run_evaluation.py`
- **Changes**:
  - After each injection, find the NEW incident: fault_class matches AND detected_at >= injected_at; wait for it to be created
  - Added `--auto-approve` flag which approves the incident the same way demo_control does and records approved_via "eval_harness"
  - Without `--auto-approve`, reports that the incident stalled at pending_approval instead of waiting silently
  - Wait timeout set above VerificationMaxWaitSeconds plus remediation time (300s = 5 minutes)

## Tests Added/Updated

All existing tests pass (115 passed, 1 skipped). Updated tests include:
- `tests/test_evaluation.py`: Updated for mock subfolder, synthetic metrics, DemoMisconfigBucket pattern
- `tests/test_diagnosis.py`: Updated for runbook_loader tuple return, S3 mocking for runbook_loader
- `tests/test_verification.py`: Verification flow with new parameters
- `tests/test_remediation.py`: Remediation with verification gating
- All other tests continue to pass

## SAM Template Validation

Both templates validate successfully:
- `infra/template.yaml` ✅
- `infra/demo-control-template.yaml` ✅

## Follow-ups Requiring AWS Console Access

The following items require manual setup in the AWS console:

1. **Enable Bedrock Model Access**
   - Go to Amazon Bedrock console → Model access
   - Enable: Nova Pro, Nova Micro, Llama 3 70B, Mistral Large (in ap-south-1)

2. **Create SSM Parameters**
   - `/llm-incident-response/slack-webhook-url` (SecureString) - Slack incoming webhook URL
   - `/llm-incident-response/approval-token-secret` (SecureString) - HMAC secret for approval links

3. **Configure Config Recorder (if using Config rule)**
   - If `CreateConfigRule=true`, ensure Config recorder exists in account
   - Config rule creation will fail if no recorder/channel exists

4. **Set FAULT_INJECTION_TOKEN**
   - Set `FAULT_INJECTION_TOKEN` env var on Service A, B, C Lambdas for fault injection auth
   - Or store in SSM and reference from template

5. **Deploy with DemoMode for demos**
   - `sam deploy --parameter-overrides DemoMode=true` to enable alarm reset and Config rule

6. **Set VERIFICATION_* env vars for faster demos**
   - `VERIFICATION_WAIT_SECONDS=15`
   - `VERIFICATION_MAX_WAIT_SECONDS=60`
   - `VERIFICATION_PROBE_COUNT=5`

7. **Set PROBE_LATENCY_THRESHOLD_MS for verification probe**
   - Default 3000ms, adjust based on Service A baseline latency

8. **Set FAULT_INJECTION_TOKEN for fault injection endpoints**
   - Required for authenticated access to `/start/fault`, `/service-b/fault`, `/service-c/fault`