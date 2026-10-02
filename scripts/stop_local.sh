#!/usr/bin/env bash
# stop_local.sh - Stop the local development environment

PROJECT_ROOT="/Users/sarthak/LLM-Assisted-Cloud-Incident-Response-AWS-SBG"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${YELLOW}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }

stop_process() {
    local pid_file="$1"
    local name="$2"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $name (PID: $pid)..."
            kill "$pid"
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
            log_success "$name stopped"
        else
            log_info "$name not running (stale PID file)"
        fi
        rm -f "$pid_file"
    else
        log_info "No PID file for $name"
    fi
}

# Also kill any remaining processes on the ports
kill_port() {
    local port="$1"
    local pids=$(lsof -ti:"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        log_info "Killing processes on port $port: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
}

main() {
    echo "Stopping local development environment..."
    
    stop_process "${PROJECT_ROOT}/.backend.pid" "Backend"
    stop_process "${PROJECT_ROOT}/.frontend.pid" "Frontend"
    
    # Clean up any remaining processes on the ports
    kill_port 3000
    kill_port 3001
    kill_port 3002
    
    log_success "All services stopped"
}

main