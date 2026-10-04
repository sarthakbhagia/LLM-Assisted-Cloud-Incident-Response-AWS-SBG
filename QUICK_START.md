# Quick Start Guide

Get the full LLM-Assisted Cloud Incident Response system running in under 10 minutes.

---

## Prerequisites

| Tool | Version | Notes |
| :--- | :--- | :--- |
| Python | 3.12+ | Backend runtime |
| Node.js | 18+ | Frontend |
| AWS CLI | v2 | Credentials and stack queries |
| AWS SAM CLI | 1.100+ | Deploy and SAM local |
| Docker Desktop | any | Only needed for Option B |

Configure credentials:

```bash
aws configure
# Region: ap-south-1  |  Account: 889081505756
```

---

## Option A: Local (in-process, recommended)

All Lambda handlers run in-process inside a lightweight Flask proxy. No deployed Lambdas needed.

```bash
# 1. Install backend dependencies
pip install flask flask-cors boto3

# 2. Start the backend (from project root)
python local_backend.py
#   Main API   → http://localhost:3001
#   Demo API   → http://localhost:3002

# 3. Create frontend/.env
echo "VITE_API_BASE_URL=http://localhost:3001" > frontend/.env
echo "VITE_DEMO_API_BASE_URL=http://localhost:3002" >> frontend/.env

# 4. Start the frontend
cd frontend
npm install   # first time only
npm run dev   # http://localhost:3000
```

To inject a demo incident: open the dashboard, click the demo button (top-right), select a fault class, click "Inject Fault".

---

## Option A2: Local (real Lambda invocations)

Same Flask proxy as Option A, but pipeline stages call the deployed Lambda functions over the network. Useful for verifying the deployed code end-to-end.

Set these env vars before starting `local_backend.py`:

```powershell
$env:COLLECTOR_FUNCTION_NAME    = "llm-incident-response-CollectorFunction-Ua4o8GiKBAbg"
$env:DIAGNOSIS_FUNCTION_NAME    = "llm-incident-response-DiagnosisFunction-7LdQHslLb6wT"
$env:NOTIFY_FUNCTION_NAME       = "llm-incident-response-NotifyFunction-zPbl9Ffm5w43"
$env:REMEDIATION_FUNCTION_NAME  = "llm-incident-response-RemediationFunction-22DBlzqigUh0"
$env:VERIFICATION_FUNCTION_NAME = "llm-incident-response-VerificationFunction-iaxrM8IyCp0v"
$env:APPROVAL_FUNCTION_NAME     = "llm-incident-response-ApprovalFunction-ZcwuiQs5Gvm9"
python local_backend.py
```

Then follow Option A steps 3 and 4. Lambda logs appear in CloudWatch, not the local terminal.

> If you have redeployed the stacks, refresh function names with:
> ```powershell
> aws cloudformation describe-stacks --stack-name llm-incident-response --region ap-south-1 --query "Stacks[0].Outputs[*].[OutputKey,Value]" --output table
> ```

---

## Option B: SAM Local (Docker required)

Runs full Lambda containers matching the production runtime (Python 3.12, ARM64).

```bash
# Terminal 1 - main API
sam local start-api --template infra/template.yaml --env-vars env.json --port 3001 --region ap-south-1

# Terminal 2 - demo control API
sam local start-api --template infra/demo-control-template.yaml --env-vars env.demo.json --port 3002 --region ap-south-1
```

Then follow Option A steps 3 and 4. First request per function takes 15-30 s (container pull).

---

## Option C: Deployed stack only

No local backend needed. Remove (or skip creating) `frontend/.env` and start only the frontend:

```bash
cd frontend && npm run dev
```

The frontend falls back to the deployed API Gateway endpoints:
- Dashboard API: `https://5guo2bztz5.execute-api.ap-south-1.amazonaws.com/Prod`
- Demo Control API: `https://0l32vjl4n8.execute-api.ap-south-1.amazonaws.com/Prod`

---

## Deploying to AWS

```bash
cd infra

# Main stack
sam build --template-file template.yaml
sam deploy --config-env default

# Demo-control stack
sam build --template-file demo-control-template.yaml
sam deploy --template-file demo-control-template.yaml \
  --stack-name llm-incident-response-demo-control \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region ap-south-1 --no-confirm-changeset
```

---

## Project Structure

```
.
├── backend/
│   ├── collector/          # Phase 3: evidence collection
│   ├── diagnosis/          # Phase 4: LLM diagnosis via Bedrock
│   ├── reporting/          # Phase 5: Slack notification
│   ├── approval/           # Phase 5: approve/reject API
│   ├── remediation/        # Phase 6: fix actions
│   ├── verification/       # Phase 6.5: post-remediation checks
│   ├── dashboard_api/      # Phase 8: read-only API
│   ├── dashboard_actions/  # Phase 8: write/action API
│   └── demo_control/       # Demo: fault injection and approval
├── frontend/               # React + Vite dashboard
├── infra/                  # SAM templates + samconfig.toml
├── knowledge_base/         # Runbook markdown files
├── evaluation/             # Phase 7 evaluation scripts
├── fault_injection/        # Manual fault injection scripts
└── local_backend.py        # Flask proxy for local dev
```

---

## API Quick Reference

All responses are wrapped in `{ data: ..., error: null }`. The frontend unwraps automatically.

| Method | Path | Returns |
| :--- | :--- | :--- |
| GET | `/api/incidents` | `{ items, next_token, count }` |
| GET | `/api/incidents/:id` | `IncidentRecord` |
| GET | `/api/incidents/:id/evidence` | `{ incident_id, fault_class, evidence }` |
| GET | `/api/analytics` | Evaluation summary or `null` |
| GET | `/api/runbooks` | `{ runbooks, count }` |
| GET | `/api/runbooks/:fault_class` | `{ fault_class, content }` |
| GET | `/api/incidents/:id/trace` | Pipeline stage timestamps |
| POST | `/api/incidents/:id/approve` | `{ success, message }` |
| POST | `/api/incidents/:id/reject` | `{ success, message }` |

---

## Common Issues

**"Failed to load incidents"** - check that `local_backend.py` is running, `frontend/.env` has the correct URLs, and `aws sts get-caller-identity` returns successfully.

**"No runbooks found"** - upload the runbook files to S3:
```bash
aws s3 cp knowledge_base/ s3://llm-incident-datalake-889081505756-dev/runbooks/ --recursive
```

**"No evaluation data"** - run `python evaluation/run_evaluation.py` to generate `evaluation/results/summary.json`.

**Blank page after `.env` change** - restart `npm run dev`. Vite bakes env vars at server start.

**SAM local "container runtime not found"** - start Docker Desktop, or use Option A instead.
