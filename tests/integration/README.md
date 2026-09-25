# Integration Tests

**Status: All Phases (0-8) Validated** — 73/73 backend unit tests passing (100%), full E2E test suite operational as of September 25, 2026.

These tests require a **deployed AWS environment** with valid credentials. They are NOT unit tests and will fail without real AWS resources.

## Prerequisites

1. **AWS credentials configured** (`aws configure` with access to the target account)
2. **Stack deployed** to the target environment (dev/staging/prod)
3. **Region** set to `ap-south-1` (Mumbai)
4. **Environment variables** (or `env.json`):
   - `INCIDENTS_TABLE` - DynamoDB table name (e.g., `incidents-dev`)
   - `DATA_LAKE_BUCKET` - S3 data lake bucket name
   - `SERVICE_A_URL` - API Gateway URL for Service A

## Tests

### `test_e2e_phases.py`
Comprehensive phase-by-phase validation of all deployed components (Phases 0-8):
- Infrastructure (S3, DynamoDB)
- Demo application (Services A/B/C)
- Detection (CloudWatch alarms, Config rules, GuardDuty)
- Data collection (Collector Lambda)
- Diagnosis (Diagnosis Lambda, runbooks)
- Reporting & Approval (Notify, Approval Lambdas)
- Remediation (Remediation Lambda, actions)
- Verification (Verification Lambda)
- Evaluation (scripts, fault injection)
- **Phase 8: Dashboard API (DashboardApiFunction, DashboardActionsFunction)**
- Service communication
- Bedrock access

Run:
```bash
cd tests/integration
python3 test_e2e_phases.py
```

### `test_full_incident_flow.py`
End-to-end flow test that:
1. Triggers a resource exhaustion incident
2. Waits for alarm → collector → diagnosis → pending approval
3. Manually approves the incident
4. Monitors remediation → verification

**Requires manual approval step** (automated in test).

Run:
```bash
cd tests/integration
python3 test_full_incident_flow.py
```

## Expected Runtime
- `test_e2e_phases.py`: ~2-3 minutes
- `test_full_incident_flow.py`: ~10-15 minutes (waits for alarms, Lambda execution, verification)

## Notes
- These tests make real AWS API calls and may incur costs
- `test_full_incident_flow.py` contains hardcoded resource names for the `dev` environment
- Update the hardcoded values for other environments
- Results are logged to console and saved as `test_report_<timestamp>.json`

## Current Deployment Status (ap-south-1, dev)
- **Main Stack**: `llm-incident-response` (all core Lambdas, DynamoDB, S3, EventBridge, Config, CloudWatch)
- **Demo Control Stack**: `llm-incident-response-demo-dev` (fault injection, approval endpoints)
- **Account**: 889081505756
- **Backend Tests**: 73/73 passing (100%)
- **Frontend Build**: Clean production bundle verified
- **SAM Template**: Valid with zero errors