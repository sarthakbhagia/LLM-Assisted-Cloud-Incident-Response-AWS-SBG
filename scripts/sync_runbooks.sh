#!/bin/bash
# Sync runbook files from knowledge_base/ to S3 data lake
# Usage: ./scripts/sync_runbooks.sh [dev|staging|prod]

set -euo pipefail

ENVIRONMENT="${1:-dev}"
# Use AWS_REGION or AWS_DEFAULT_REGION with default
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-1}}"

# Get account ID from AWS STS
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo "ERROR: Failed to get AWS account ID. Make sure AWS credentials are configured."
    exit 1
}

BUCKET="llm-incident-datalake-${ACCOUNT_ID}-${ENVIRONMENT}"
SOURCE_DIR="knowledge_base"
DEST_PREFIX="runbooks"

echo "Syncing runbooks from ${SOURCE_DIR}/ to s3://${BUCKET}/${DEST_PREFIX}/"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Account ID: ${ACCOUNT_ID}"
echo "Bucket: ${BUCKET}"

# Check if source directory exists
if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "ERROR: Source directory ${SOURCE_DIR} not found"
    exit 1
fi

# Check if bucket exists
aws s3api head-bucket --bucket "${BUCKET}" --region "${REGION}" 2>/dev/null || {
    echo "ERROR: Bucket ${BUCKET} not found or not accessible"
    exit 1
}

# Sync runbook files
aws s3 sync "${SOURCE_DIR}/" "s3://${BUCKET}/${DEST_PREFIX}/" \
    --region "${REGION}" \
    --delete \
    --exclude "*" \
    --include "*.md" \
    --metadata-directive REPLACE \
    --cache-control "max-age=86400"

echo "Runbook sync completed successfully"
echo "Files synced to s3://${BUCKET}/${DEST_PREFIX}/:"
aws s3 ls "s3://${BUCKET}/${DEST_PREFIX}/" --region "${REGION}" --human-readable --summarize