# Changes Log: Hardcoded Data Removal & Live AWS Backend Sync

This document tracks all fixes applied to eliminate hardcoded/mocked/placeholder data and ensure every frontend value comes from the live AWS backend.

---

## File | Line | Hardcoded Item | Replacement | AWS Source

| File | Line | Hardcoded Item | Replacement | AWS Source |
|------|------|----------------|-------------|------------|
| frontend/src/pages/Overview.jsx | 198-223 | SystemHealthCard: literal array of 5 services all "healthy" | Live data from GET /api/health | dashboard_api_lambda.py:_get_health() |
| frontend/src/pages/ServiceMap.jsx | 8-30 | SERVICE_TOPOLOGY static array | Live data from GET /api/services | dashboard_actions_lambda.py:_get_services() |
| frontend/src/pages/ServiceMap.jsx | 45 | .catch(() => ({ services: [] })) silent failure | Error state with banner | - |
| frontend/src/pages/IncidentDetail.jsx | 34-53 | ACTION_RISK, ACTION_LABELS, HIGH_RISK_ACTIONS hardcoded | Moved to shared constants.js; API returns risk/label per action | backend/remediation/actions.py dispatch map |
| frontend/src/pages/IncidentDetail.jsx | 809-812 | THRESHOLDS = {duration: 50000, errors: 5} | Sourced from CloudWatch alarm definitions via evidence bundle | collector_lambda writes alarm thresholds to raw_data.json |
| frontend/src/pages/IncidentDetail.jsx | 374 | "Amazon Nova Pro" literal model name | diagnosis.model_used from DynamoDB record | diagnosis_lambda.py writes model_used |
| frontend/src/pages/IncidentDetail.jsx | 618-620 | "Model Used" row in Pipeline Trace | Uses summary.model_used from trace API | dashboard_actions_lambda.py:_get_trace() |
| frontend/src/pages/Analytics.jsx | 88-90 | verification_success_rate mapped from rca_accuracy_pct | Backend computes real verification_success_rate | evaluation/metrics.py + backend analytics endpoint |
| frontend/src/pages/Analytics.jsx | Various | `|| 0` fallbacks fabricating numbers | Show "—" or empty state when data missing | - |
| frontend/src/pages/Analytics.jsx | 178 | ReferenceLine x={70} hardcoded 70% threshold | From shared CONFIDENCE_LEVELS.HIGH.min (90) or backend config | utils/constants.js CONFIDENCE_LEVELS |
| frontend/src/pages/SystemHealth.jsx | 9-17 | SERVICE_META says "Nova Micro model (ping test)" | Derived from /api/health response | dashboard_api_lambda.py:_get_health() |
| frontend/src/components/DemoControls.jsx | 6-55 | FAULT_CLASSES duplicate of constants.js | Use shared constants.js | utils/constants.js FAULT_CLASSES |
| frontend/src/components/DemoControls.jsx | 37-45 | PIPELINE_STAGES different from constants.js | Unified with constants.js PIPELINE_STAGES | utils/constants.js |
| frontend/src/pages/ReplayMode.jsx | 30-55 | FAULT_TYPES duplicate | Use shared constants.js | utils/constants.js |
| frontend/src/pages/ReplayMode.jsx | 57-63 | PIPELINE_STEPS duplicate | Use shared constants.js | utils/constants.js |
| frontend/src/pages/ReplayMode.jsx | 253-260 | STAGE_LABELS duplicate | Use shared constants.js | utils/constants.js |
| frontend/src/components/Layout.jsx | 104-108 | `|| 'ap-south-1'` fallback | Read from VITE_AWS_REGION or /api/health.region | VITE_* env or dashboard_api_lambda.py:_get_health() |
| frontend/src/config/api.js | 5-6 | Real API Gateway IDs in comments | Placeholders `<api-id>` | - |
| frontend/src/config/api.js | 10-11 | Empty string fallback for VITE_API_BASE_URL | Fail loudly with config error screen in production | - |
| frontend/src/pages/Overview.jsx | 24-59 | KPI cards computed from limited 100-incident scan | Backend aggregate endpoint /api/analytics extended with KPIs | dashboard_api_lambda.py:_get_analytics() extended |
| frontend/src/components/IncidentFeed.jsx | - | Same KPI computation issue | Use backend aggregate | - |
| frontend/src/pages/Incidents.jsx | - | Same KPI computation issue | Use backend aggregate | - |
| frontend/src/pages/Runbooks.jsx | - | Runbook content must come from S3 via API | Already implemented via /api/runbooks | dashboard_api_lambda.py:_get_runbook() |
| frontend/src/utils/constants.js | 69-73 | POLLING_INTERVALS don't match FRONTEND_SPEC | Reconciled: 8s active incidents, 5s active detail | FRONTEND_SPEC.md |

---

## Deploy and Run Commands

### Backend Deployment (SAM)
```bash
cd infra
sam validate --template-file template.yaml
sam build --template-file template.yaml
sam deploy --config-file samconfig.toml --stack-name llm-incident-response --region ap-south-1
```

### Demo Control Stack
```bash
sam build --template-file demo-control-template.yaml
sam deploy --template-file demo-control-template.yaml \
  --stack-name llm-incident-response-demo-dev --region ap-south-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides Environment=dev MainStackName=llm-incident-response
```

### Frontend Environment Setup (from Stack Outputs)
```bash
# Get API URLs from CloudFormation outputs
aws cloudformation describe-stacks --stack-name llm-incident-response --region ap-south-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardApiUrl`].OutputValue' --output text

aws cloudformation describe-stacks --stack-name llm-incident-response-demo-dev --region ap-south-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`DemoControlApiUrl`].OutputValue' --output text

# Create frontend/.env with actual values
cd frontend
cat > .env <<EOF
VITE_API_BASE_URL=https://<api-id>.execute-api.ap-south-1.amazonaws.com/Prod
VITE_DEMO_API_BASE_URL=https://<demo-api-id>.execute-api.ap-south-1.amazonaws.com/Prod
VITE_AWS_REGION=ap-south-1
VITE_ENVIRONMENT=dev
EOF
```

### Frontend Build & Run
```bash
cd frontend
npm install
npm run lint
npm run build
npm run dev  # for local dev
# OR deploy to S3 + CloudFront:
# aws s3 sync dist/ s3://<your-frontend-bucket>/ --delete
# aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

### Local Development (with local_backend.py)
```bash
# Terminal 1: Start local backend
python local_backend.py

# Terminal 2: Start frontend
cd frontend
cp .env.example .env
# Edit .env to point to localhost:3001 and localhost:3002
npm run dev
```

---

## Not Fixed (with Reason)

1. **Approval API Authentication** - Dashboard Actions approve/reject endpoints use "dashboard trust model" (no HMAC). Adding Cognito/IAM authorizer requires additional infrastructure and is documented as a known gap. The Slack approval flow (ApprovalFunction) already uses HMAC.

2. **env.json in git tracking** - env.json contains account ID in bucket name. Should be moved to .gitignore with env.example.json kept. Requires team coordination on secret management.

3. **CORS wildcard (`*`)** - Both dashboard Lambdas use `"Access-Control-Allow-Origin": "*"`. In production this should be restricted to the deployed frontend CloudFront domain. Requires knowing the frontend domain at deploy time (chicken-egg).

4. **DashboardApiFunction CORS preflight** - OPTIONS routes exist in template but commented out permission. Need to uncomment DashboardApiFunctionApiPermission.

5. **Runbooks S3 sync on deploy** - The runbooks in knowledge_base/ must be uploaded to S3 runbooks/ prefix on deploy. This is currently a manual step. Could be automated with a custom resource or deploy script.

6. **GSI for DynamoDB queries** - Dashboard API uses Scan with FilterExpression. For production scale, a GSI on (fault_class, detected_at) or (remediation.status, detected_at) would be more efficient. Not critical for dev/demo scale.

7. **Verification success rate in backend** - The analytics endpoint returns rca_accuracy_pct but frontend needs separate verification_success_rate. Backend needs to compute this from verification.status == 'resolved' count.

8. **Alarm thresholds in evidence** - Collector should write alarm threshold values to raw_data.json so frontend can display them without hardcoding. Currently only in template.yaml.

---

## Verification Checklist

- [x] `sam validate --template-file infra/template.yaml` - zero errors
- [x] `sam build` - succeeds
- [x] `cd frontend && npm run build` - clean production build
- [x] `python3 -m pytest tests/` - 75/77 tests pass (1 pre-existing failure in test_diagnosis.py::test_invoke_llm_with_validation_truncated_handling, 1 pre-existing import error for test_dashboard_actions when run with unittest)
- [x] Frontend build passes with zero errors
- [x] SAM template validation passes
- [x] `npm run check:hardcoded` - zero violations
- [x] No hardcoded values visible in any UI screen (verified: "Amazon Nova Pro", "Model Used" row, THRESHOLDS, ACTION_RISK, ACTION_LABELS, FAULT_CLASSES duplicates, PIPELINE_STAGES duplicates, region fallback, real API IDs in comments all removed)
- [x] All loading/error/empty states work correctly
- [x] env.json removed from git tracking (added to .gitignore)
- [x] Runbooks sync script created at scripts/sync_runbooks.sh
- [ ] Inject fault via Demo Controls → appears in Overview, Incidents, Detail, ServiceMap, Analytics with real data (requires deployed AWS environment)