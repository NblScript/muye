#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PX4_DIR="${HOME}/PX4-Autopilot"
SAMPLE_IMAGE="${ROOT_DIR}/IP000000042.jpg"
SYSTEM_ADDRESS="udpin://0.0.0.0:14540"
WORLD_NAME="muye_demo_field"
TIMEOUT_SECONDS="240"
START_PX4="true"
KEEP_PX4="false"

APP_PID=""
PX4_PID=""
APP_LOG=""
PX4_LOG=""
SEEDED_IMAGE=""
PX4_LOG_GUARD_PID=""
PX4_LOG_MAX_BYTES="${MUYE_PX4_LOG_MAX_BYTES:-104857600}"
PX4_LOG_KEEP_BYTES="${MUYE_PX4_LOG_KEEP_BYTES:-52428800}"

usage() {
  cat <<'EOF'
Usage: ./scripts/run_px4_demo.sh [options]

Run a full PX4 SITL -> Muye -> sample image -> mission completion demo.

Options:
  --px4-dir <path>          PX4-Autopilot directory. Default: ~/PX4-Autopilot
  --sample-image <path>     Image to inject into data/images. Default: IP000000042.jpg
  --system-address <addr>   MAVSDK system address. Default: udpin://0.0.0.0:14540
  --world <name>            Gazebo world name. Default: muye_demo_field
  --timeout <seconds>       End-to-end wait timeout. Default: 240
  --skip-px4                Assume PX4 SITL is already running.
  --keep-px4                Do not stop PX4 SITL when the demo finishes.
  -h, --help                Show this help message.
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
    --timeout)
      [[ $# -ge 2 ]] || { echo "Missing value for --timeout" >&2; exit 1; }
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --skip-px4)
      START_PX4="false"
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

if ! "$PYTHON_BIN" -c "import ultralytics" >/dev/null 2>&1; then
  echo "Missing Python dependency: ultralytics" >&2
  echo "Install it with: ${PYTHON_BIN} -m pip install -r ${ROOT_DIR}/requirements.txt" >&2
  exit 1
fi

if [[ "$SAMPLE_IMAGE" != /* ]]; then
  SAMPLE_IMAGE="${ROOT_DIR}/${SAMPLE_IMAGE}"
fi

if [[ ! -f "$SAMPLE_IMAGE" ]]; then
  echo "Sample image not found: $SAMPLE_IMAGE" >&2
  exit 1
fi

if [[ "$START_PX4" == "true" && ! -d "$PX4_DIR" ]]; then
  echo "PX4 directory not found: $PX4_DIR" >&2
  exit 1
fi

cleanup() {
  local exit_code=$?
  if [[ -n "$PX4_LOG_GUARD_PID" ]] && kill -0 "$PX4_LOG_GUARD_PID" >/dev/null 2>&1; then
    kill "$PX4_LOG_GUARD_PID" >/dev/null 2>&1 || true
    wait "$PX4_LOG_GUARD_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" >/dev/null 2>&1; then
    kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_PX4" != "true" && -n "$PX4_PID" ]] && kill -0 "$PX4_PID" >/dev/null 2>&1; then
    kill "$PX4_PID" >/dev/null 2>&1 || true
    wait "$PX4_PID" >/dev/null 2>&1 || true
  fi
  if [[ $exit_code -ne 0 ]]; then
    [[ -n "$APP_LOG" ]] && echo "Muye log: $APP_LOG" >&2
    [[ -n "$PX4_LOG" ]] && echo "PX4 log: $PX4_LOG" >&2
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for ((i = 1; i <= attempts; i++)); do
    if [[ -n "$APP_PID" ]] && ! kill -0 "$APP_PID" >/dev/null 2>&1; then
      echo "Muye backend exited unexpectedly while waiting for $name." >&2
      return 1
    fi
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

wait_for_log_pattern() {
  local log_file="$1"
  local pattern="$2"
  local name="$3"
  local attempts="${4:-60}"

  for ((i = 1; i <= attempts; i++)); do
    if [[ -n "$APP_PID" ]] && ! kill -0 "$APP_PID" >/dev/null 2>&1; then
      echo "Muye backend exited unexpectedly while waiting for $name." >&2
      return 1
    fi
    if [[ -f "$log_file" ]] && rg -q "$pattern" "$log_file"; then
      echo "$name is ready."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for $name." >&2
  return 1
}

wait_for_demo_completion() {
  local db_path="$1"
  local image_path="$2"
  local timeout_seconds="$3"

  "$PYTHON_BIN" - "$db_path" "$image_path" "$timeout_seconds" <<'PY'
import json
import sqlite3
import sys
import time

db_path, image_path, timeout_seconds = sys.argv[1], sys.argv[2], float(sys.argv[3])
deadline = time.time() + timeout_seconds
last_status = None

while time.time() < deadline:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        task = conn.execute(
            """
            SELECT request_id, status
            FROM tasks
            WHERE image_path = ?
            ORDER BY COALESCE(end_time, start_time) DESC, request_id DESC
            LIMIT 1
            """,
            (image_path,),
        ).fetchone()
        if task is None:
            time.sleep(1)
            continue

        drone = conn.execute(
            """
            SELECT task_id, status, message, progress, current_waypoint_index
            FROM drone_mission_updates
            WHERE request_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (task["request_id"],),
        ).fetchone()

        if drone is not None and drone["status"] != last_status:
            last_status = drone["status"]
            print(
                json.dumps(
                    {
                        "request_id": task["request_id"],
                        "task_status": task["status"],
                        "drone_status": drone["status"],
                        "message": drone["message"],
                        "progress": drone["progress"],
                        "task_id": drone["task_id"],
                        "current_waypoint_index": drone["current_waypoint_index"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        if drone is not None and drone["status"] == "completed":
            print(
                json.dumps(
                    {
                        "request_id": task["request_id"],
                        "result": "completed",
                        "task_id": drone["task_id"],
                        "progress": drone["progress"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            raise SystemExit(0)

        if task["status"] == "error":
            print(
                json.dumps(
                    {
                        "request_id": task["request_id"],
                        "result": "error",
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            raise SystemExit(1)
    finally:
        conn.close()

    time.sleep(1)

print(
    json.dumps(
        {
            "result": "timeout",
            "image_path": image_path,
        },
        ensure_ascii=False,
    ),
    flush=True,
)
raise SystemExit(1)
PY
}

mkdir -p "${ROOT_DIR}/data/logs"
APP_LOG="${ROOT_DIR}/data/logs/muye-px4-demo-$(date +%Y%m%d-%H%M%S).log"
PX4_LOG="${ROOT_DIR}/data/logs/px4-sitl-$(date +%Y%m%d-%H%M%S).log"

echo "Preparing runtime state..."
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" - <<'PY'
from modules.common import ensure_runtime_dirs
from modules.event_bus import FileEventBus

ensure_runtime_dirs()
FileEventBus().clear()
PY

if [[ "$START_PX4" == "true" ]]; then
  echo "Starting PX4 SITL..."
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

echo "Starting Muye PX4 backend..."
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

wait_for_url "http://127.0.0.1:8010/health" "YOLO API"
wait_for_log_pattern "$APP_LOG" "主处理链已启动" "Muye backend"

timestamp="$(date +%Y%m%d-%H%M%S)"
SEEDED_IMAGE="${ROOT_DIR}/data/images/${timestamp}-$(basename "$SAMPLE_IMAGE")"
cp "$SAMPLE_IMAGE" "$SEEDED_IMAGE"
echo "Seeded sample image: $SEEDED_IMAGE"

echo "Waiting for PX4 mission completion..."
wait_for_demo_completion "${ROOT_DIR}/data/muye.db" "$SEEDED_IMAGE" "$TIMEOUT_SECONDS"

echo "PX4 demo completed successfully."
echo "Muye log: $APP_LOG"
if [[ "$START_PX4" == "true" ]]; then
  echo "PX4 log: $PX4_LOG"
  echo "Gazebo world: $WORLD_NAME"
fi
