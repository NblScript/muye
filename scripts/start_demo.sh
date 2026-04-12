#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
STREAMLIT_BIN="${VENV_DIR}/bin/streamlit"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8501"
SAMPLE_IMAGE=""

usage() {
  cat <<'EOF'
Usage: ./scripts/start_demo.sh [--sample-image <path>] [--frontend-port <port>]

Starts the Muye backend demo stack and Streamlit frontend together.

Options:
  --sample-image <path>   Copy a sample image into data/images after startup.
                          Relative paths are resolved from the project root.
  --frontend-port <port>  Streamlit port, default is 8501.
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

if [[ ! -x "$STREAMLIT_BIN" ]]; then
  echo "Missing streamlit executable: $STREAMLIT_BIN" >&2
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
FRONTEND_PID=""

cleanup() {
  local exit_code=$?
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
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

wait_for_url "http://127.0.0.1:8010/health" "YOLO API"
wait_for_url "http://127.0.0.1:9010/health" "Virtual Drone API"

echo "Starting Streamlit frontend..."
(
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" "$STREAMLIT_BIN" run app.py \
    --server.headless true \
    --server.address "$FRONTEND_HOST" \
    --server.port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

wait_for_url "http://${FRONTEND_HOST}:${FRONTEND_PORT}" "Streamlit frontend"

if [[ -n "$SAMPLE_IMAGE" ]]; then
  timestamp="$(date +%Y%m%d-%H%M%S)"
  target_path="${ROOT_DIR}/data/images/${timestamp}-$(basename "$SAMPLE_IMAGE")"
  cp "$SAMPLE_IMAGE" "$target_path"
  echo "Seeded sample image: $target_path"
fi

echo
echo "Muye demo is running."
echo "Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "YOLO API:  http://127.0.0.1:8010/health"
echo "Drone API: http://127.0.0.1:9010/health"
echo "Press Ctrl+C to stop."

set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
status=$?
set -e

echo "A demo service exited unexpectedly." >&2
exit "$status"
