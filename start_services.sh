#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY_FILE="$ROOT_DIR/key.pem"
CERT_FILE="$ROOT_DIR/cert.pem"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="$ROOT_DIR/.pids"
SSL_MODE="${SMARTATTEND_SSL_MODE:-auto}"
SSL_CN="${SMARTATTEND_SSL_CN:-localhost}"
LAN_IP="${SMARTATTEND_LAN_IP:-}"

# Service definitions: name:dir:port
SERVICES=(
  "face-service:face-service:5001"
  "qr-service:qr-service:5002"
  "attendance-service:attendance-service:5003"
)

mkdir -p "$LOG_DIR" "$PID_DIR"

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "Error: $label not found: $path" >&2
    exit 1
  fi
}

require_dir() {
  local path="$1"
  local label="$2"
  if [[ ! -d "$path" ]]; then
    echo "Error: $label not found: $path" >&2
    exit 1
  fi
}

get_pid_cmdline() {
  local pid="$1"
  local cmdline=""
  if [[ -r "/proc/$pid/cmdline" ]]; then
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  fi
  if [[ -z "$cmdline" ]]; then
    cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  fi
  echo "$cmdline"
}

is_port_bindable() {
  local port="$1"
  python3 - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
}

has_expected_uvicorn_runtime() {
  local pid="$1"
  local port="$2"
  local cmdline
  cmdline="$(get_pid_cmdline "$pid")"
  [[ "$cmdline" == *uvicorn* ]] || return 1
  [[ "$cmdline" == *"app.main:app"* ]] || return 1
  [[ "$cmdline" == *"--port $port"* ]] || return 1
  [[ "$cmdline" == *"--ssl-keyfile"* ]] || return 1
  [[ "$cmdline" == *"--ssl-certfile"* ]] || return 1
}

list_port_pids() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk '!seen[$0]++'
    return
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "( sport = :$port )" 2>/dev/null | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | awk '!seen[$0]++'
    return
  fi
}

is_smartattend_service_pid() {
  local pid="$1"
  local abs_service_dir="$2"
  if ! is_pid_alive "$pid"; then
    return 1
  fi

  local cwd
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  if [[ "$cwd" != "$abs_service_dir" ]]; then
    return 1
  fi

  local cmdline
  cmdline="$(get_pid_cmdline "$pid")"
  [[ "$cmdline" == *uvicorn* && "$cmdline" == *"app.main:app"* ]]
}

is_smartattend_expected_service_pid() {
  local pid="$1"
  local abs_service_dir="$2"
  local port="$3"
  if ! is_smartattend_service_pid "$pid" "$abs_service_dir"; then
    return 1
  fi
  has_expected_uvicorn_runtime "$pid" "$port"
}

cleanup_stale_pid_file() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]] || ! is_pid_alive "$pid"; then
    rm -f "$pid_file"
  fi
}

is_smartattend_project_pid() {
  local pid="$1"
  if ! is_pid_alive "$pid"; then
    return 1
  fi

  local cmdline
  cmdline="$(get_pid_cmdline "$pid")"
  [[ "$cmdline" == *uvicorn* && "$cmdline" == *"app.main:app"* && "$cmdline" == *"$ROOT_DIR"* ]]
}

print_port_diagnostic() {
  local port="$1"
  echo "Port $port listener details:"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
    return
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "( sport = :$port )" || true
    return
  fi

  if command -v fuser >/dev/null 2>&1; then
    fuser -v -n tcp "$port" || true
    return
  fi

  echo "No diagnostic tool available (install one of: lsof, ss, fuser)."
}

stop_smartattend_pid_safely() {
  local pid="$1"
  local name="$2"
  local port="$3"
  local attempt

  echo "Stopping stale $name process (PID $pid) on port $port..."
  kill -TERM "$pid" 2>/dev/null || true
  for ((attempt = 1; attempt <= 20; attempt++)); do
    if ! is_pid_alive "$pid"; then
      echo "Stopped stale PID $pid."
      return 0
    fi
    sleep 0.5
  done

  echo "Error: stale $name process PID $pid did not stop after SIGTERM." >&2
  echo "Please stop it manually, then re-run the launcher." >&2
  return 1
}

ensure_port_available_for_service() {
  local name="$1"
  local abs_service_dir="$2"
  local port="$3"
  local pid_file="$4"
  local had_conflict="false"
  local had_unrelated="false"
  local had_other_smartattend="false"

  if is_port_bindable "$port"; then
    return 0
  fi

  echo "Port $port is currently in use before starting $name."

  # First, try stale PID-file cleanup for this service even if listener PID introspection is limited.
  if [[ -f "$pid_file" ]]; then
    local pid_from_file
    pid_from_file="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid_from_file" ]] && is_smartattend_service_pid "$pid_from_file" "$abs_service_dir"; then
      if ! stop_smartattend_pid_safely "$pid_from_file" "$name" "$port"; then
        return 1
      fi
      rm -f "$pid_file"
      if is_port_bindable "$port"; then
        return 0
      fi
    fi
  fi

  mapfile -t port_pids < <(list_port_pids "$port" || true)
  for pid in "${port_pids[@]}"; do
    [[ -z "$pid" ]] && continue
    had_conflict="true"

    if is_smartattend_service_pid "$pid" "$abs_service_dir"; then
      if ! has_expected_uvicorn_runtime "$pid" "$port"; then
        echo "Detected stale $name process with unexpected runtime flags (PID $pid)."
        echo "  command: $(get_pid_cmdline "$pid")"
      fi
      if ! stop_smartattend_pid_safely "$pid" "$name" "$port"; then
        return 1
      fi
      if [[ -f "$pid_file" ]] && [[ "$(cat "$pid_file" 2>/dev/null || true)" == "$pid" ]]; then
        rm -f "$pid_file"
      fi
      continue
    fi

    if is_smartattend_project_pid "$pid"; then
      had_other_smartattend="true"
      echo "Conflict: port $port is used by another SmartAttend uvicorn process (PID $pid), not $name." >&2
      echo "  command: $(get_pid_cmdline "$pid")" >&2
      continue
    fi

    had_unrelated="true"
    echo "Conflict: port $port is used by an unrelated process (PID $pid)." >&2
    echo "  command: $(get_pid_cmdline "$pid")" >&2
  done

  if ! is_port_bindable "$port"; then
    echo "Error: $name cannot start because port $port is still occupied." >&2
    if [[ "${#port_pids[@]}" -eq 0 ]]; then
      echo "Reason: port ownership could not be inspected in this environment; process appears unrelated or inaccessible." >&2
    elif [[ "$had_unrelated" == "true" ]]; then
      echo "Reason: unrelated process is listening on port $port. It was not terminated automatically." >&2
    elif [[ "$had_other_smartattend" == "true" ]]; then
      echo "Reason: another SmartAttend process owns port $port. Automatic stop is limited to stale same-service instances." >&2
    elif [[ "$had_conflict" == "true" ]]; then
      echo "Reason: stale $name process could not be fully stopped." >&2
    fi
    print_port_diagnostic "$port" >&2
    return 1
  fi

  return 0
}

is_pid_alive() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

is_port_listening() {
  local port="$1"
  if ! is_port_bindable "$port"; then
    return 0
  fi
  mapfile -t port_pids < <(list_port_pids "$port" || true)
  if [[ "${#port_pids[@]}" -gt 0 ]]; then
    return 0
  fi
  if command -v ss >/dev/null 2>&1 || command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  return 2
}

https_probe_ok() {
  local name="$1"
  local port="$2"
  if ! command -v curl >/dev/null 2>&1; then
    return 2
  fi

  # Primary readiness signal: expected /health response shape.
  if service_health_signature_ok "$name" "$port"; then
    return 0
  fi

  # Fallback FastAPI probe.
  curl -kfsS --max-time 2 "https://127.0.0.1:$port/openapi.json" >/dev/null 2>&1
}

service_health_signature_ok() {
  local name="$1"
  local port="$2"
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi

  local body
  body="$(curl -kfsS --max-time 2 "https://127.0.0.1:$port/health" 2>/dev/null || true)"
  if [[ -z "$body" ]]; then
    return 1
  fi

  case "$name" in
    face-service)
      [[ "$body" == *"\"status\":\"ok\""* && "$body" == *"\"model\""* ]]
      ;;
    qr-service)
      [[ "$body" == *"\"status\":\"ok\""* && "$body" == *"\"qr_expiry_seconds\""* ]]
      ;;
    attendance-service)
      [[ "$body" == *"\"status\":\"ok\""* && "$body" == *"\"face_service_url\""* && "$body" == *"\"qr_service_url\""* ]]
      ;;
    *)
      [[ "$body" == *"\"status\":\"ok\""* ]]
      ;;
  esac
}

adopt_running_service_pid() {
  local name="$1"
  local abs_service_dir="$2"
  local port="$3"
  local pid_file="$4"
  mapfile -t port_pids < <(list_port_pids "$port" || true)

  # PID inspection unavailable: rely on health signature only.
  if [[ "${#port_pids[@]}" -eq 0 ]]; then
    echo "Warning: $name already healthy on port $port (PID inspection unavailable)."
    return 0
  fi

  local preferred_pid=""
  local fallback_pid=""
  for pid in "${port_pids[@]}"; do
    [[ -z "$pid" ]] && continue
    if is_smartattend_expected_service_pid "$pid" "$abs_service_dir" "$port"; then
      preferred_pid="$pid"
      break
    fi
    if [[ -z "$fallback_pid" ]] && is_smartattend_service_pid "$pid" "$abs_service_dir"; then
      fallback_pid="$pid"
    fi
  done

  if [[ -n "$preferred_pid" ]]; then
    echo "$preferred_pid" > "$pid_file"
    echo "Warning: $name already healthy on port $port (adopted PID $preferred_pid)."
    return 0
  fi

  if [[ -n "$fallback_pid" ]]; then
    echo "$fallback_pid" > "$pid_file"
    echo "Warning: $name already healthy on port $port (adopted same-service PID $fallback_pid)."
    return 0
  fi

  echo "Error: port $port is healthy but owned by a non-$name process; refusing PID adoption." >&2
  print_port_diagnostic "$port" >&2
  return 1
}

adopt_running_service_if_safe() {
  local name="$1"
  local abs_service_dir="$2"
  local port="$3"
  local pid_file="$4"

  if is_port_bindable "$port"; then
    return 1
  fi

  if ! service_health_signature_ok "$name" "$port"; then
    return 1
  fi

  if ! adopt_running_service_pid "$name" "$abs_service_dir" "$port" "$pid_file"; then
    return 2
  fi
  return 0
}

show_recent_logs() {
  local log_file="$1"
  if [[ -f "$log_file" ]]; then
    echo "Last 40 log lines from $log_file:"
    tail -n 40 "$log_file"
  else
    echo "Log file not found: $log_file"
  fi
}

classify_startup_failure() {
  local name="$1"
  local port="$2"
  local log_file="$3"

  if [[ -f "$log_file" ]] && grep -q "could not bind on any address" "$log_file"; then
    echo "Diagnosis: $name failed due to port bind error on $port (application reached uvicorn startup)." >&2
    if grep -q "Application startup complete." "$log_file"; then
      echo "Application startup succeeded, but socket bind on $port failed." >&2
    fi
    print_port_diagnostic "$port" >&2
    echo "Manual checks:" >&2
    echo "  lsof -nP -iTCP:$port -sTCP:LISTEN" >&2
    echo "  ss -ltnp 'sport = :$port'" >&2
    return 0
  fi

  echo "Diagnosis: $name failed during application startup/init. See logs above." >&2
}

wait_for_service_ready() {
  local name="$1"
  local pid="$2"
  local port="$3"
  local log_file="$4"
  local max_attempts=30
  local attempt

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    # If the expected service is already responding correctly, mark ready immediately.
    if service_health_signature_ok "$name" "$port"; then
      return 0
    fi

    if ! is_pid_alive "$pid"; then
      echo "Error: $name exited immediately (PID $pid is not running)." >&2
      classify_startup_failure "$name" "$port" "$log_file" >&2 || true
      show_recent_logs "$log_file" >&2
      return 1
    fi

    local port_state=1
    is_port_listening "$port" || port_state=$?
    if [[ "$port_state" -eq 0 ]]; then
      if https_probe_ok "$name" "$port"; then
        return 0
      fi
      local probe_state=$?
      if [[ "$probe_state" -eq 2 ]]; then
        # curl not available; port listening is enough to verify startup.
        return 0
      fi
      # Process is alive and listening, endpoint may not be ready yet.
    elif [[ "$port_state" -eq 2 ]]; then
      # Could not inspect port due to missing tools; fall back to PID+HTTPS probe.
      if https_probe_ok "$name" "$port"; then
        return 0
      fi
      local probe_state=$?
      if [[ "$probe_state" -eq 2 ]]; then
        # Neither port nor HTTP probe tools are available; PID is the only signal.
        return 0
      fi
    fi

    sleep 0.5
  done

  echo "Error: $name did not become ready on port $port within 15 seconds." >&2
  classify_startup_failure "$name" "$port" "$log_file" >&2 || true
  show_recent_logs "$log_file" >&2
  return 1
}

print_ssl_recovery_command() {
  local san
  san="$(build_ssl_san)"
  echo "Recovery command:"
  echo "  openssl req -x509 -newkey rsa:4096 -nodes -days 365 \\"
  echo "    -keyout \"$KEY_FILE\" -out \"$CERT_FILE\" \\"
  echo "    -subj \"/CN=$SSL_CN\" \\"
  echo "    -addext \"subjectAltName=$san\""
}

discover_lan_ip() {
  if [[ -n "$LAN_IP" ]]; then
    echo "$LAN_IP"
    return
  fi
  hostname -I 2>/dev/null | awk '{print $1}'
}

build_ssl_san() {
  local discovered_ip
  discovered_ip="$(discover_lan_ip)"
  local san="DNS:localhost,IP:127.0.0.1"
  if [[ -n "$discovered_ip" ]]; then
    san="$san,IP:$discovered_ip"
  fi
  echo "$san"
}

ensure_ssl_certs() {
  local key_exists="false"
  local cert_exists="false"

  [[ -f "$KEY_FILE" ]] && key_exists="true"
  [[ -f "$CERT_FILE" ]] && cert_exists="true"

  if [[ "$key_exists" == "true" && "$cert_exists" == "true" ]]; then
    return
  fi

  if [[ "$SSL_MODE" == "fail" ]]; then
    echo "Error: SSL certificate files are missing." >&2
    echo "Expected files:" >&2
    echo "  $KEY_FILE" >&2
    echo "  $CERT_FILE" >&2
    print_ssl_recovery_command >&2
    exit 1
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is not installed, cannot auto-generate certificates." >&2
    print_ssl_recovery_command >&2
    echo "Install it with: sudo apt-get update && sudo apt-get install -y openssl" >&2
    exit 1
  fi

  echo "SSL files missing. Generating local self-signed certificates in $ROOT_DIR..."
  local san
  san="$(build_ssl_san)"
  local discovered_ip
  discovered_ip="$(discover_lan_ip)"
  if [[ -n "$discovered_ip" ]]; then
    echo "Using SAN entries: DNS:localhost, IP:127.0.0.1, IP:$discovered_ip"
  else
    echo "Using SAN entries: DNS:localhost, IP:127.0.0.1"
    echo "Tip: set SMARTATTEND_LAN_IP=<your-lan-ip> to include LAN IP SAN explicitly."
  fi
  rm -f "$KEY_FILE" "$CERT_FILE"
  openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=$SSL_CN" \
    -addext "subjectAltName=$san"
  chmod 600 "$KEY_FILE"
  chmod 644 "$CERT_FILE"
  echo "Generated:"
  echo "  $KEY_FILE"
  echo "  $CERT_FILE"
}

ensure_ssl_certs
require_file "$KEY_FILE" "SSL key"
require_file "$CERT_FILE" "SSL certificate"

start_service() {
  local name="$1"
  local service_dir="$2"
  local port="$3"

  local abs_service_dir="$ROOT_DIR/$service_dir"
  local activate_path="$abs_service_dir/venv/bin/activate"
  local log_file="$LOG_DIR/${name}.log"
  local pid_file="$PID_DIR/${name}.pid"

  require_dir "$abs_service_dir" "Service directory for $name"
  require_file "$activate_path" "Virtual environment activate script for $name"
  require_file "$abs_service_dir/app/main.py" "FastAPI entrypoint for $name"

  cleanup_stale_pid_file "$pid_file"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    if [[ -n "${old_pid}" ]] && is_smartattend_service_pid "$old_pid" "$abs_service_dir"; then
      if is_smartattend_expected_service_pid "$old_pid" "$abs_service_dir" "$port" && ! is_port_bindable "$port"; then
        echo "Warning: $name already running with PID $old_pid; skipping"
        return
      fi
      echo "Warning: $name PID $old_pid is stale or does not match expected SSL runtime; restarting."
      echo "  command: $(get_pid_cmdline "$old_pid")"
      if ! stop_smartattend_pid_safely "$old_pid" "$name" "$port"; then
        rm -f "$pid_file"
        exit 1
      fi
    elif [[ -n "${old_pid}" ]] && is_pid_alive "$old_pid"; then
      echo "Warning: removing stale PID file for $name (PID $old_pid is live but unrelated)."
    fi
    rm -f "$pid_file"
  fi

  # If a healthy same-service instance is already serving on this port, adopt/skip.
  if adopt_running_service_if_safe "$name" "$abs_service_dir" "$port" "$pid_file"; then
    return
  else
    local adopt_state=$?
    if [[ "$adopt_state" -eq 2 ]]; then
      exit 1
    fi
  fi

  if ! ensure_port_available_for_service "$name" "$abs_service_dir" "$port" "$pid_file"; then
    exit 1
  fi

  : > "$log_file"
  (
    cd "$abs_service_dir"
    # Activate the service-specific virtual environment before launching uvicorn.
    source "$activate_path"
    nohup uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "$port" \
      --ssl-keyfile "$KEY_FILE" \
      --ssl-certfile "$CERT_FILE" \
      > "$log_file" 2>&1 &
    echo $! > "$pid_file"
  )

  local pid
  pid="$(cat "$pid_file")"
  if ! wait_for_service_ready "$name" "$pid" "$port" "$log_file"; then
    rm -f "$pid_file"
    exit 1
  fi

  echo "Started $name on https://0.0.0.0:$port (PID $pid) [verified]"
  echo "  log: $log_file"
}

for svc in "${SERVICES[@]}"; do
  IFS=':' read -r name dir port <<< "$svc"
  start_service "$name" "$dir" "$port"
done

echo "All requested services started."
