# Quick Start Guide

This guide gets the full LLM-Assisted Cloud Incident Response system running in under 10 minutes, either against live AWS resources locally or against the already-deployed production stack.

---

## Prerequisites

| Tool | Version | Install |
| :--- | :--- | :--- |
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| AWS CLI | v2 | [Install guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| AWS SAM CLI | 1.100+ | [Install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Docker Desktop | any | Only needed for `sam local` (optional) |

Configure AWS credentials before starting:

```bash
aws configure
# Region: ap-south-1
# Account: 889081505756
```

Verify credentials:

```bash
aws sts get-caller-identity
```

---

## Option A: Local Development (no Docker required)

This is the recommended path for day-to-day development. The backend runs as a lightweight Flask proxy that calls your Lambda handlers directly and connects to the real `dev` DynamoDB table and S3 bucket.

### Step 1: Install backend dependencies

```bash
pip install flask flask-cors boto3
```

### Step 2: Start the backend

From the project root:

```bash
python local_backend.py
```

This starts two servers:

| Server | URL | Purpose |
| :--- | :--- | :--- |
| Main API | http://localhost:3001 | Dashboard API (incidents, runbooks, analytics, evidence) |
| Demo Control API | http://localhost:3002 | Fault injection and pipeline approval |

Both servers connect to the real AWS `dev` resources:
- DynamoDB table: `incidents-dev`
- S3 data lake: `llm-incident-datalake-889081505756-dev`
- AWS region: `ap-south-1`

Leave this terminal running.

### Step 3: Configure the frontend

Create `frontend/.env` pointing to the local backend:

```ini
VITE_API_BASE_URL=http://localhost:3001
VITE_DEMO_API_BASE_URL=http://localhost:3002
```

This file already exists if you ran the project before. If not, copy and edit:

```bash
cp frontend/.env.example frontend/.env
```

Then set the URLs as above.

### Step 4: Start the frontend

```bash
cd frontend
npm install   # first time only
npm run dev
```

Open http://localhost:3000 in your browser.

### Step 5: Inject a test incident (optional)

On the Overview page, click the demo mode button (top-right) to open the Demo Controls panel. Select a fault class and click "Inject Fault". The pipeline tracker shows real-time progress through Detect, Collect, Diagnose, Approve, Remediate, and Verify stages.

---

## Option B: SAM Local (requires Docker Desktop running)

SAM local spins up full Lambda containers, exactly matching the production runtime (Python 3.12, ARM64 emulated via QEMU).

### Step 1: Start Docker Desktop

Make sure Docker Desktop is running before continuing.

### Step 2: Start the main API

```bash
sam local start-api \
  --template infra/template.yaml \
  --env-vars env.json \
  --port 3001 \
  --region ap-south-1
```

### Step 3: Start the demo control API

In a second terminal:

```bash
sam local start-api \
  --template infra/demo-control-template.yaml \
  --env-vars env.demo.json \
  --port 3002 \
  --region ap-south-1
```

### Step 4: Start the frontend

Same as Option A, Step 3 and Step 4.

> The first request to each Lambda function takes 15-30 seconds while SAM pulls the container image. Subsequent requests are fast.

---

## Option C: Connect to the deployed AWS stack

Skip running any backend locally. The frontend connects directly to the deployed API Gateway endpoints.

Remove (or do not create) `frontend/.env`. The `api.js` fallback URLs point to the deployed production stack:

- Main API: `https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod`
- Demo API: `https://0l32vjl4n8.execute-api.ap-south-1.amazonaws.com/Prod`

Start only the frontend:

```bash
cd frontend
npm run dev
```

---

## Environment Variable Reference

### `env.json` - main stack (used by both `local_backend.py` and SAM local)

```json
{
  "DashboardApiFunction": {
    "DATA_LAKE_BUCKET": "llm-incident-datalake-889081505756-dev",
    "INCIDENTS_TABLE": "incidents-dev"
  },
  "ApprovalFunction": {
    "DATA_LAKE_BUCKET": "llm-incident-datalake-889081505756-dev",
    "INCIDENTS_TABLE": "incidents-dev"
  },
  "CollectorFunction": {
    "DATA_LAKE_BUCKET": "llm-incident-datalake-889081505756-dev",
    "INCIDENTS_TABLE": "incidents-dev",
    "INCIDENT_AWS_REGION": "ap-south-1"
  }
}
```

### `env.demo.json` - demo-control stack

```json
{
  "DemoControlFunction": {
    "ENVIRONMENT": "dev",
    "INCIDENTS_TABLE": "incidents-dev",
    "DATA_LAKE_BUCKET": "llm-incident-datalake-889081505756-dev",
    "APPROVAL_FUNCTION_NAME": "llm-incident-response-ApprovalFunction-dev"
  }
}
```

### `frontend/.env`

```ini
VITE_API_BASE_URL=http://localhost:3001
VITE_DEMO_API_BASE_URL=http://localhost:3002
```

---

## Deploying to AWS

### Deploy main stack

```bash
cd infra
sam build --template template.yaml
sam deploy --config-file samconfig.toml
```

The `samconfig.toml` already contains all parameters for the `dev` environment.

### Deploy demo-control stack

```bash
sam build --template demo-control-template.yaml
sam deploy \
  --template demo-control-template.yaml \
  --stack-name llm-incident-response-demo-dev \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region ap-south-1
```

### Deploy frontend to S3 + CloudFront

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://<your-frontend-bucket>/ --delete
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

---

## Project Structure

```
.
├── backend/
│   ├── dashboard_api/      # Phase 8: read-only visualization API
│   ├── demo_control/       # Demo Mode: fault injection and approval
│   ├── collector/          # Phase 3: collects evidence from AWS
│   ├── diagnosis/          # Phase 4: LLM diagnosis via Bedrock
│   ├── reporting/          # Phase 5: Slack notification
│   ├── approval/           # Phase 5: approve/reject API
│   ├── remediation/        # Phase 6: executes fix actions
│   └── verification/       # Phase 6.5: verifies remediation worked
├── frontend/               # React + Vite + Tailwind dashboard
│   ├── src/
│   │   ├── config/api.js   # API client with envelope unwrapping
│   │   ├── pages/          # Overview, Incidents, IncidentDetail, Analytics,
│   │   │                   # Runbooks, ServiceMap, ReplayMode
│   │   ├── components/     # Layout, IncidentFeed, DemoControls
│   │   └── utils/          # constants.js, helpers.js
│   └── .env                # Points frontend to local or deployed backend
├── infra/
│   ├── template.yaml               # Main SAM template
│   ├── demo-control-template.yaml  # Demo control SAM template
│   └── samconfig.toml              # Deploy config for dev environment
├── knowledge_base/         # Runbook markdown files
├── evaluation/             # Phase 7 evaluation scripts
├── fault_injection/        # Manual fault injection scripts
├── local_backend.py        # Flask proxy for local dev (no Docker needed)
├── env.json                # SAM local env vars - main stack
├── env.demo.json           # SAM local env vars - demo stack
├── BACKEND_SPEC.md         # Backend architecture + API response contracts
├── FRONTEND_SPEC.md        # Frontend architecture + implementation status
├── PROJECT_SPEC.md         # Full project specification
└── DESIGN_SPEC.md          # Design system tokens and component specs
```

---

## API Endpoints Quick Reference

All endpoints are wrapped in `{ data: ..., error: null }`. The frontend `ApiClient` unwraps this automatically - component code never sees the envelope.

| Method | Path | What it returns (after unwrap) |
| :--- | :--- | :--- |
| GET | `/api/incidents` | `{ items: IncidentRecord[], next_token, count }` |
| GET | `/api/incidents/:id` | The `IncidentRecord` object directly |
| GET | `/api/incidents/:id/evidence` | `{ incident_id, fault_class, s3_key, evidence: {...} }` |
| GET | `/api/analytics` | Phase 7 summary JSON, or `null` |
| GET | `/api/runbooks` | `{ runbooks: RunbookMeta[], count }` |
| GET | `/api/runbooks/:fault_class` | `{ fault_class, s3_key, content: "..." }` |
| POST | `/demo/inject` | `{ incident_id, status }` |
| POST | `/demo/approve/:id` | `{ success, message }` |
| POST | `/api/incidents/:id/approve` | `{ status: "approved", incident_id, remediation_invoked, detail }` |
| POST | `/api/incidents/:id/reject` | `{ status: "rejected", incident_id, detail }` |

> Approve/reject via the dashboard (`/api/incidents/:id/approve|reject`) is served by `local_backend.py`, which routes to the real Phase 5 approval handler and signs the HMAC token from the SSM secret (`/llm-incident-response/approval-token-secret`). The deployed API Gateway currently exposes only the Slack-link flow (`GET/POST /approval`) and `/demo/approve/{id}`.

> **Important field names:** The incidents list uses `items` (not `incidents`), and pagination uses `next_token` (not `cursor`). The detail endpoint returns the incident object directly (not nested under `.incident`). See `BACKEND_SPEC.md` Section 6 for the full contract.

---

## Common Issues

### "Failed to load incidents" on the Overview page

The frontend cannot reach the backend. Check:
1. `local_backend.py` is running and shows no import errors.
2. `frontend/.env` contains the correct `VITE_API_BASE_URL`.
3. AWS credentials are valid: `aws sts get-caller-identity`
4. The DynamoDB table `incidents-dev` exists in `ap-south-1`.

### Runbooks page shows "No runbooks found"

The `runbooks/` prefix in S3 is empty. Upload the runbook files:

```bash
aws s3 cp knowledge_base/resource_exhaustion.md \
  s3://llm-incident-datalake-889081505756-dev/runbooks/
aws s3 cp knowledge_base/misconfiguration.md \
  s3://llm-incident-datalake-889081505756-dev/runbooks/
aws s3 cp knowledge_base/service_cascade.md \
  s3://llm-incident-datalake-889081505756-dev/runbooks/
```

### Analytics page shows "No evaluation data"

Phase 7 has not run yet. The `evaluation/results/summary.json` key does not exist in S3. Run the evaluation pipeline:

```bash
python evaluation/run_evaluation.py
```

### Demo inject does not trigger the pipeline

The Demo Control Lambda triggers real CloudWatch alarm state changes, which flow through EventBridge to the Collector Lambda. This path requires the full AWS stack to be deployed. The local backend only serves the read API and the `demo/approve` shortcut locally. Fault injection itself must reach real AWS.

### Vite page is blank after `.env` change

Vite injects `VITE_*` vars at server start, not at runtime. Stop and restart `npm run dev` if a blank page persists after editing `.env`.

### SAM local: "container runtime not found"

Docker Desktop is not running. Either start Docker Desktop and retry Option B, or use `local_backend.py` (Option A), which does not require Docker at all.

### `local_backend.py` crashes on import

Run `pip install flask flask-cors boto3` and try again. The script attempts to auto-install these on first run, but a manual install is more reliable.
