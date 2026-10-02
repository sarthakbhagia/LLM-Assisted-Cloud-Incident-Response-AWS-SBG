#!/usr/bin/env bash
# start_local.sh - Start the full local development environment
# 
# This script starts both the backend (local_backend.py) and frontend (Vite)
# against the real AWS dev account.
#
# Usage: ./scripts/start_local.sh
# Or: source scripts/start_local.sh  (to keep environment variables in shell)

set -euo pipefail

# ─── Colors for output ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─── Configuration ───────────────────────────────────────────────────────────
PROJECT_ROOT="/Users/sarthak/LLM-Assisted-Cloud-Incident-Response-AWS-SBG"
BACKEND_LOG="${PROJECT_ROOT}/backend.log"
FRONTEND_LOG="${PROJECT_ROOT}/frontend.log"

# AWS Configuration (dev account)
export AWS_ACCOUNT_ID=889081505756
export AWS_REGION=ap-south-1
export AWS_DEFAULT_REGION=ap-south-1
export INCIDENTS_TABLE=incidents-dev
export DATA_LAKE_BUCKET=llm-incident-datalake-889081505756-dev
export ENVIRONMENT=dev
export ALLOWED_ORIGIN=http://localhost:3000

# ─── Helper functions ────────────────────────────────────────────────────────
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_aws_credentials() {
    log_info "Checking AWS credentials..."
    if ! aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1; then
        log_error "AWS credentials not configured or expired."
        echo "Run: aws configure"
        return 1
    fi
    log_success "AWS credentials valid"
}

check_python_deps() {
    log_info "Checking Python dependencies..."
    python3 -c "import boto3, flask, flask_cors" 2>/dev/null || {
        log_error "Missing Python dependencies. Run: pip3 install boto3 flask flask-cors --break-system-packages"
        return 1
    }
    log_success "Python dependencies available"
}

check_frontend_deps() {
    log_info "Checking frontend dependencies..."
    if [[ ! -d "${PROJECT_ROOT}/frontend/node_modules" ]]; then
        log_warn "Frontend dependencies not installed. Running npm install..."
        (cd "${PROJECT_ROOT}/frontend" && npm install)
    fi
    log_success "Frontend dependencies available"
}

start_backend() {
    log_info "Starting backend (local_backend.py) on ports 3001/3002..."
    cd "${PROJECT_ROOT}"
    nohup python3 local_backend.py > "${BACKEND_LOG}" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "${PROJECT_ROOT}/.backend.pid"
    
    # Wait for backend to be ready
    for i in {1..30}; do
        if curl -sf http://localhost:3001/api/health >/dev/null 2>&1; then
            log_success "Backend ready at http://localhost:3001"
            return 0
        fi
        sleep 1
    done
    log_error "Backend failed to start. Check ${BACKEND_LOG}"
    return 1
}

start_frontend() {
    log_info "Starting frontend (Vite) on port 3000..."
    cd "${PROJECT_ROOT}/frontend"
    nohup npm run dev > "${FRONTEND_LOG}" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "${PROJECT_ROOT}/.frontend.pid"
    
    # Wait for frontend to be ready
    for i in {1..30}; do
        if curl -sf http://localhost:3000/ >/dev/null 2>&1; then
            log_success "Frontend ready at http://localhost:3000"
            return 0
        fi
        sleep 1
    done
    log_error "Frontend failed to start. Check ${FRONTEND_LOG}"
    return 1
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
    echo "=================================================="
    echo "  LLM-Assisted Cloud Incident Response - Local Dev"
    echo "=================================================="
    echo ""
    
    check_aws_credentials || exit 1
    check_python_deps || exit 1
    check_frontend_deps || exit 1
    
    start_backend || exit 1
    start_frontend || exit 1
    
    echo ""
    echo "=================================================="
    echo "  All services running!"
    echo "=================================================="
    echo ""
    echo "  Frontend:  http://localhost:3000"
    echo "  Backend:   http://localhost:3001"
    echo "  Demo API:  http://localhost:3002"
    echo ""
    echo "  Backend PID:  ${BACKEND_PID} (log: ${BACKEND_LOG})"
    echo "  Frontend PID: ${FRONTEND_PID} (log: ${FRONTEND_LOG})"
    echo ""
    echo "  To stop: kill \$(cat ${PROJECT_ROOT}/.backend.pid) \$(cat ${PROJECT_ROOT}/.frontend.pid)"
    echo "  Or run:  ./scripts/stop_local.sh"
    echo ""
}

# Run main if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi