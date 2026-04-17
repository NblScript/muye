#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
NPM_BIN="$(command -v npm || true)"
PX4_DIR="${HOME}/PX4-Autopilot"
SAMPLE_IMAGE=""
SYSTEM_ADDRESS="udpin://0.0.0.0:14540"
WORLD_NAME="muye_demo_field"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8501"
API_HOST="127.0.0.1"
API_PORT="${MUYE_API_PORT:-18000}"
START_PX4="true"
START_QGC="true"
KEEP_PX4="false"
QGC_PATH="${QGC_PATH:-}"

APP_PID=""
API_PID=""
FRONTEND_PID=""
PX4_PID=""
QGC_PID=""
APP_LOG=""
API_LOG=""
FRONTEND_LOG=""
PX4_LOG=""
QGC_LOG=""
PX4_LOG_GUARD_PID=""
PX4_LOG_MAX_BYTES="${MUYE_PX4_LOG_MAX_BYTES:-104857600}"
PX4_LOG_KEEP_BYTES="${MUYE_PX4_LOG_KEEP_BYTES:-52428800}"

usage() {
  cat <<'EOF'
Usage: ./scripts/start_px4_visual_demo.sh [options]

Starts a visual PX4 demo stack for competition demos:
  - PX4 SITL + Gazebo world
  - Muye backend in PX4 mode
  - Vite React dashboard
  - QGroundControl when available

Options:
  --px4-dir <path>          PX4-Autopilot directory. Default: ~/PX4-Autopilot
  --sample-image <path>     Optional image copied into data/images after startup
  --system-address <addr>   MAVSDK system address. Default: udpin://0.0.0.0:14540
  --world <name>            Gazebo world name. Default: muye_demo_field
  --frontend-port <port>    Frontend port. Default: 8501
  --api-port <port>         Frontend API port. Default: 18000
  --qgc-path <path>         Explicit QGroundControl executable/AppImage path
  --skip-px4                Assume PX4 SITL is already running
  --skip-qgc                Do not attempt to launch QGroundControl
  --keep-px4                Do not stop PX4 SITL when this script exits
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --px4-dir)
      [[ $# -ge 2 ]] || { echo "Missing value for --px4-dir" >&2; exit 1; }
      PX4_DIR="$2"
      shift 2
      ;;
    --sample-image)
      [[ $# -ge 2 ]] || { echo "Missing value for --sample-image" >&2; exit 1; }
      SAMPLE_IMAGE="$2"
      shift 2
      ;;
    --system-address)
      [[ $# -ge 2 ]] || { echo "Missing value for --system-address" >&2; exit 1; }
      SYSTEM_ADDRESS="$2"
      shift 2
      ;;
    --world)
      [[ $# -ge 2 ]] || { echo "Missing value for --world" >&2; exit 1; }
      WORLD_NAME="$2"
      shift 2
      ;;
    --frontend-port)
      [[ $# -ge 2 ]] || { echo "Missing value for --frontend-port" >&2; exit 1; }
      FRONTEND_PORT="$2"
      shift 2
      ;;
    --api-port)
      [[ $# -ge 2 ]] || { echo "Missing value for --api-port" >&2; exit 1; }
      API_PORT="$2"
      shift 2
      ;;
    --qgc-path)
      [[ $# -ge 2 ]] || { echo "Missing value for --qgc-path" >&2; exit 1; }
      QGC_PATH="$2"
      shift 2
      ;;
    --skip-px4)
      START_PX4="false"
      shift
      ;;
    --skip-qgc)
      START_QGC="false"
      shift
      ;;
    --keep-px4)
      KEEP_PX4="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -z "$NPM_BIN" ]]; then
  echo "Missing npm in PATH." >&2
  exit 1
fi

if [[ ! -f "${FRONTEND_DIR}/package.json" ]]; then
  echo "Missing frontend package.json: ${FRONTEND_DIR}/package.json" >&2
  exit 1
fi

if [[ "$START_PX4" == "true" && ! -d "$PX4_DIR" ]]; then
  echo "PX4 directory not found: $PX4_DIR" >&2
  exit 1
fi

if [[ -n "$SAMPLE_IMAGE" ]]; then
  if [[ "$SAMPLE_IMAGE" != /* ]]; then
    SAMPLE_IMAGE="${ROOT_DIR}/${SAMPLE_IMAGE}"
  fi
  if [[ ! -f "$SAMPLE_IMAGE" ]]; then
    echo "Sample image not found: $SAMPLE_IMAGE" >&2
    exit 1
  fi
fi

cleanup() {
  local exit_code=$?
  if [[ -n "$PX4_LOG_GUARD_PID" ]] && kill -0 "$PX4_LOG_GUARD_PID" >/dev/null 2>&1; then
    kill "$PX4_LOG_GUARD_PID" >/dev/null 2>&1 || true
    wait "$PX4_LOG_GUARD_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" >/dev/null 2>&1; then
    kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
    wait "$API_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$QGC_PID" ]] && kill -0 "$QGC_PID" >/dev/null 2>&1; then
    kill "$QGC_PID" >/dev/null 2>&1 || true
    wait "$QGC_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_PX4" != "true" && -n "$PX4_PID" ]] && kill -0 "$PX4_PID" >/dev/null 2>&1; then
    kill "$PX4_PID" >/dev/null 2>&1 || true
    wait "$PX4_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

cleanup_stale_mavsdk() {
  local mavsdk_pids=""
  mavsdk_pids="$(pgrep -f '/mavsdk/bin/mavsdk_server' || true)"
  if [[ -z "$mavsdk_pids" ]]; then
    return 0
  fi

  echo "Stopping stale mavsdk_server processes: $mavsdk_pids"
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<<"$mavsdk_pids"
  sleep 1
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for ((i = 1; i <= attempts; i++)); do
    if "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

url = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(url, timeout=2) as response:
    if 200 <= response.status < 500:
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
      echo "$name is ready: $url"
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for $name: $url" >&2
  return 1
}

wait_for_px4_startup() {
  local log_file="$1"
  local attempts="${2:-120}"

  for ((i = 1; i <= attempts; i++)); do
    if [[ -n "$PX4_PID" ]] && ! kill -0 "$PX4_PID" >/dev/null 2>&1; then
      echo "PX4 SITL exited unexpectedly." >&2
      return 1
    fi
    if [[ -f "$log_file" ]] && rg -q "Startup script returned successfully|Ready for takeoff|INFO  \\[px4\\] Startup script returned successfully" "$log_file"; then
      echo "PX4 SITL startup confirmed."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for PX4 SITL startup." >&2
  return 1
}

start_log_size_guard() {
  local log_file="$1"
  local watched_pid="$2"
  local label="$3"
  local max_bytes="${4:-104857600}"
  local keep_bytes="${5:-52428800}"

  if (( keep_bytes >= max_bytes )); then
    keep_bytes=$(( max_bytes / 2 ))
  fi

  (
    while kill -0 "$watched_pid" >/dev/null 2>&1; do
      if [[ -f "$log_file" ]]; then
        current_size="$(wc -c <"$log_file" 2>/dev/null || echo 0)"
        if (( current_size > max_bytes )); then
          tmp_file="${log_file}.tmp"
          tail -c "$keep_bytes" "$log_file" >"$tmp_file" 2>/dev/null || true
          mv "$tmp_file" "$log_file" 2>/dev/null || true
          printf '[log-guard] Truncated %s log to last %s bytes\n' "$label" "$keep_bytes" >>"$log_file"
        fi
      fi
      sleep 5
    done
  ) &
  PX4_LOG_GUARD_PID=$!
}

detect_qgc() {
  if [[ -n "$QGC_PATH" ]]; then
    echo "$QGC_PATH"
    return 0
  fi

  local candidate=""
  candidate="$(command -v QGroundControl.AppImage 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v QGroundControl 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v qgroundcontrol 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

mkdir -p "${ROOT_DIR}/data/logs"
APP_LOG="${ROOT_DIR}/data/logs/muye-px4-backend-$(date +%Y%m%d-%H%M%S).log"
FRONTEND_LOG="${ROOT_DIR}/data/logs/muye-px4-frontend-$(date +%Y%m%d-%H%M%S).log"
API_LOG="${ROOT_DIR}/data/logs/muye-frontend-api-$(date +%Y%m%d-%H%M%S).log"
PX4_LOG="${ROOT_DIR}/data/logs/px4-visual-sitl-$(date +%Y%m%d-%H%M%S).log"
QGC_LOG="${ROOT_DIR}/data/logs/qgc-$(date +%Y%m%d-%H%M%S).log"

echo "Preparing runtime state..."
cleanup_stale_mavsdk
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" - <<'PY'
from modules.common import ensure_runtime_dirs
from modules.event_bus import FileEventBus

ensure_runtime_dirs()
FileEventBus().clear()
PY

if [[ "$START_PX4" == "true" ]]; then
  echo "Starting PX4 SITL + Gazebo..."
  (
    cd "$PX4_DIR"
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
      PX4_GZ_WORLD="$WORLD_NAME" \
      make px4_sitl gz_x500
  ) >"$PX4_LOG" 2>&1 &
  PX4_PID=$!
  start_log_size_guard "$PX4_LOG" "$PX4_PID" "PX4 SITL" "$PX4_LOG_MAX_BYTES" "$PX4_LOG_KEEP_BYTES"
  wait_for_px4_startup "$PX4_LOG"
else
  echo "Skipping PX4 startup. Expecting an existing SITL instance."
fi

echo "Starting Muye backend in PX4 mode..."
(
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" \
  DRONE_BACKEND=px4 \
  PX4_USE_SITL_DEMO_FIELD=true \
  PX4_SYSTEM_ADDRESS="$SYSTEM_ADDRESS" \
  QWEN_USE_MOCK=true \
  QWEATHER_USE_MOCK=true \
  "$PYTHON_BIN" main.py --with-yolo-api --drone-backend px4 --no-capture-on-startup
) >"$APP_LOG" 2>&1 &
APP_PID=$!

echo "Starting Muye frontend API..."
(
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn main:api_app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --log-level warning
) >"$API_LOG" 2>&1 &
API_PID=$!

wait_for_url "http://${API_HOST}:${API_PORT}/health" "Frontend API"
wait_for_url "http://127.0.0.1:8010/health" "YOLO API"

echo "Starting Vite React frontend..."
(
  cd "$FRONTEND_DIR"
  MUYE_API_TARGET="http://${API_HOST}:${API_PORT}" \
    "$NPM_BIN" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

wait_for_url "http://${FRONTEND_HOST}:${FRONTEND_PORT}" "Vite frontend"

if [[ -n "$SAMPLE_IMAGE" ]]; then
  timestamp="$(date +%Y%m%d-%H%M%S)"
  target_path="${ROOT_DIR}/data/images/${timestamp}-$(basename "$SAMPLE_IMAGE")"
  cp "$SAMPLE_IMAGE" "$target_path"
  echo "Seeded sample image: $target_path"
fi

if [[ "$START_QGC" == "true" ]]; then
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "Skipping QGroundControl launch: no DISPLAY/WAYLAND session detected."
  else
    QGC_BIN="$(detect_qgc || true)"
    if [[ -n "$QGC_BIN" ]]; then
      echo "Starting QGroundControl: $QGC_BIN"
      (
        cd "$ROOT_DIR"
        "$QGC_BIN"
      ) >"$QGC_LOG" 2>&1 &
      QGC_PID=$!
    else
      echo "QGroundControl not found. Install it or pass --qgc-path /path/to/QGroundControl.AppImage"
    fi
  fi
fi

echo
echo "PX4 visual demo is running."
echo "Frontend:   http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "API:        http://${API_HOST}:${API_PORT}/health"
echo "YOLO API:   http://127.0.0.1:8010/health"
echo "PX4 world:  ${WORLD_NAME}"
echo "PX4 log:    ${PX4_LOG}"
echo "Backend log:${APP_LOG}"
echo "API log:    ${API_LOG}"
echo "UI log:     ${FRONTEND_LOG}"
if [[ -n "$QGC_PID" ]]; then
  echo "QGC log:    ${QGC_LOG}"
fi
echo "Press Ctrl+C to stop."

set +e
wait -n "$APP_PID" "$FRONTEND_PID" ${PX4_PID:+"$PX4_PID"}
status=$?
set -e

echo "A visual demo service exited unexpectedly." >&2
exit "$status"
