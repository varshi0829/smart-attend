#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY_FILE="$ROOT_DIR/key.pem"
CERT_FILE="$ROOT_DIR/cert.pem"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="$ROOT_DIR/.pids"

STUDENT_PORT="${STUDENT_FRONTEND_PORT:-8001}"
INSTRUCTOR_PORT="${INSTRUCTOR_FRONTEND_PORT:-8002}"

mkdir -p "$LOG_DIR" "$PID_DIR"

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "Error: $label not found: $path" >&2
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command not found: $cmd" >&2
    exit 1
  fi
}

is_pid_alive() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

start_http_server() {
  local name="$1"
  local dir="$2"
  local port="$3"
  local pid_file="$PID_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && is_pid_alive "$old_pid"; then
      echo "Warning: $name already running with PID $old_pid; skipping"
      return
    fi
    rm -f "$pid_file"
  fi

  : > "$log_file"
  (
    cd "$ROOT_DIR"
    nohup http-server "$dir" \
      -a 0.0.0.0 \
      -p "$port" \
      --ssl \
      --cert "$CERT_FILE" \
      --key "$KEY_FILE" \
      > "$log_file" 2>&1 &
    echo $! > "$pid_file"
  )

  local pid
  pid="$(cat "$pid_file")"
  echo "Started $name on https://0.0.0.0:$port (PID $pid)"
  echo "  log: $log_file"
}

require_file "$KEY_FILE" "SSL key"
require_file "$CERT_FILE" "SSL certificate"

start_http_server "frontend-student" "./frontend-student" "$STUDENT_PORT"
start_http_server "frontend-instructor" "./frontend-instructor" "$INSTRUCTOR_PORT"

echo "Frontends started."
