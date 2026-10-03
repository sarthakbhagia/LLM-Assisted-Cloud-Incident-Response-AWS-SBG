#!/bin/bash
# Full deployment script for LLM-Assisted Cloud Incident Response
# Usage: ./scripts/deploy.sh [dev|staging|prod]

set -euo pipefail

ENVIRONMENT="${1:-dev}"
REGION="ap-south-1"
STACK_NAME="llm-incident-response"
DEMO_STACK_NAME="llm-incident-response-demo-${ENVIRONMENT}"

echo "=== Deploying LLM-Assisted Cloud Incident Response ==="
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Main Stack: ${STACK_NAME}"
echo "Demo Stack: ${DEMO_STACK_NAME}"
echo ""

# Step 1: Validate SAM template
echo "=== Step 1: Validating SAM template ==="
sam validate --template-file infra/template.yaml --lint
echo "Template validation passed"
echo ""

# Step 2: Build SAM application
echo "=== Step 2: Building SAM application ==="
sam build --template-file infra/template.yaml
echo "Build completed"
echo ""

# Step 3: Deploy main stack
echo "=== Step 3: Deploying main stack (${STACK_NAME}) ==="
sam deploy \
    --template-file infra/template.yaml \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}" \
    --no-fail-on-empty-changeset
echo "Main stack deployed"
echo ""

# Step 4: Deploy demo control stack
echo "=== Step 4: Deploying demo control stack (${DEMO_STACK_NAME}) ==="
sam deploy \
    --template-file infra/demo-control-template.yaml \
    --stack-name "${DEMO_STACK_NAME}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}" MainStackName="${STACK_NAME}" \
    --no-fail-on-empty-changeset
echo "Demo control stack deployed"
echo ""

# Step 5: Sync runbooks to S3
echo "=== Step 5: Syncing runbooks to S3 ==="
./scripts/sync_runbooks.sh "${ENVIRONMENT}"
echo ""

# Step 6: Get stack outputs for frontend configuration
echo "=== Step 6: Getting stack outputs for frontend ==="
DASHBOARD_API_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" \
    --output text)

DEMO_API_URL=$(aws cloudformation describe-stacks \
    --stack-name "${DEMO_STACK_NAME}" \
    --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='DemoControlApiUrl'].OutputValue" \
    --output text)

echo "DashboardApiUrl: ${DASHBOARD_API_URL}"
echo "DemoControlApiUrl: ${DEMO_API_URL}"
echo ""

# Step 7: Update frontend .env (optional - for local development)
echo "=== Step 7: Frontend configuration ==="
cat << EOF

To configure frontend for deployed environment, create frontend/.env with:

VITE_API_BASE_URL=${DASHBOARD_API_URL}
VITE_DEMO_API_BASE_URL=${DEMO_API_URL}
VITE_AWS_REGION=ap-south-1
VITE_ENVIRONMENT=${ENVIRONMENT}

Then run:
  cd frontend && npm run build && npm run dev

Or deploy to S3 + CloudFront:
  cd frontend && npm run build
  aws s3 sync dist/ s3://<your-frontend-bucket>/ --delete
  aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"

NOTE: VITE_API_BASE_URL must end at /Prod with NO trailing /api.
The frontend prepends /api/ to all routes internally (e.g. /api/incidents/{id}/evidence).
If you set VITE_API_BASE_URL to .../Prod/api the evidence, analytics and runbook
requests will hit .../Prod/api/api/... which does not exist, causing silent empty tabs.

EOF

echo "=== Deployment complete ==="