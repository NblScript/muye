#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
NPM_BIN="$(command -v npm || true)"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8501"
API_HOST="127.0.0.1"
API_PORT="${MUYE_API_PORT:-18000}"
SAMPLE_IMAGE=""

usage() {
  cat <<'EOF'
Usage: ./scripts/start_demo.sh [--sample-image <path>] [--frontend-port <port>] [--api-port <port>]

Starts the Muye backend demo stack and Vite React frontend together.

Options:
  --sample-image <path>   Copy a sample image into data/images after startup.
                          Relative paths are resolved from the project root.
  --frontend-port <port>  Frontend port, default is 8501.
  --api-port <port>       Frontend API port, default is 18000.
  -h, --help              Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample-image)
      [[ $# -ge 2 ]] || { echo "Missing value for --sample-image" >&2; exit 1; }
      SAMPLE_IMAGE="$2"
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

if [[ -n "$SAMPLE_IMAGE" ]]; then
  if [[ "$SAMPLE_IMAGE" != /* ]]; then
    SAMPLE_IMAGE="${ROOT_DIR}/${SAMPLE_IMAGE}"
  fi
  if [[ ! -f "$SAMPLE_IMAGE" ]]; then
    echo "Sample image not found: $SAMPLE_IMAGE" >&2
    exit 1
  fi
fi

BACKEND_PID=""
API_PID=""
FRONTEND_PID=""

cleanup() {
  local exit_code=$?
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
    wait "$API_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for ((i = 1; i <= attempts; i++)); do
    if "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=2) as response:
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

echo "Preparing runtime state..."
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" - <<'PY'
from modules.common import ensure_runtime_dirs
from modules.event_bus import FileEventBus

ensure_runtime_dirs()
FileEventBus().clear()
PY

echo "Starting Muye backend demo stack..."
(
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" main.py --with-demo-stack
) &
BACKEND_PID=$!

echo "Starting Muye frontend API..."
(
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn main:api_app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --log-level warning
) &
API_PID=$!

wait_for_url "http://${API_HOST}:${API_PORT}/health" "Frontend API"
wait_for_url "http://127.0.0.1:8010/health" "YOLO API"
wait_for_url "http://127.0.0.1:9010/health" "Virtual Drone API"

echo "Starting Vite React frontend..."
(
  cd "$FRONTEND_DIR"
  MUYE_API_TARGET="http://${API_HOST}:${API_PORT}" \
    "$NPM_BIN" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

wait_for_url "http://${FRONTEND_HOST}:${FRONTEND_PORT}" "Vite frontend"

if [[ -n "$SAMPLE_IMAGE" ]]; then
  timestamp="$(date +%Y%m%d-%H%M%S)"
  target_path="${ROOT_DIR}/data/images/${timestamp}-$(basename "$SAMPLE_IMAGE")"
  cp "$SAMPLE_IMAGE" "$target_path"
  echo "Seeded sample image: $target_path"
fi

echo
echo "Muye demo is running."
echo "Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "API:      http://${API_HOST}:${API_PORT}/health"
echo "YOLO API:  http://127.0.0.1:8010/health"
echo "Drone API: http://127.0.0.1:9010/health"
echo "Press Ctrl+C to stop."

set +e
wait -n "$BACKEND_PID" "$API_PID" "$FRONTEND_PID"
status=$?
set -e

echo "A demo service exited unexpectedly." >&2
exit "$status"
