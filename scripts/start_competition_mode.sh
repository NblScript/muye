#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
VISUAL_SCRIPT="${ROOT_DIR}/scripts/start_px4_visual_demo.sh"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="8501"
START_BROWSER="true"
BROWSER_CMD="${BROWSER_CMD:-}"
VISUAL_ARGS=()
VISUAL_PID=""

usage() {
  cat <<'EOF'
Usage: ./scripts/start_competition_mode.sh [options]

Competition-mode launcher for live demos. It wraps the visual PX4 demo stack and
tries to open the dashboard in a browser for fast现场展示.

Pass-through options:
  --px4-dir <path>          PX4-Autopilot directory
  --sample-image <path>     Seed image copied into data/images after startup
  --system-address <addr>   MAVSDK system address
  --world <name>            Gazebo world name
  --frontend-port <port>    Frontend port, default 8501
  --api-port <port>         Frontend API port, default 18000
  --qgc-path <path>         Explicit QGroundControl executable/AppImage path
  --skip-px4                Reuse an already-running PX4 SITL
  --skip-qgc                Do not launch QGroundControl
  --keep-px4                Keep PX4 SITL running after exit

Competition-mode options:
  --skip-browser            Do not auto-open the dashboard in a browser
  --browser-cmd <path>      Explicit browser executable, e.g. /usr/bin/firefox
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-browser)
      START_BROWSER="false"
      shift
      ;;
    --browser-cmd)
      [[ $# -ge 2 ]] || { echo "Missing value for --browser-cmd" >&2; exit 1; }
      BROWSER_CMD="$2"
      shift 2
      ;;
    --frontend-port)
      [[ $# -ge 2 ]] || { echo "Missing value for --frontend-port" >&2; exit 1; }
      FRONTEND_PORT="$2"
      VISUAL_ARGS+=("$1" "$2")
      shift 2
      ;;
    --api-port)
      [[ $# -ge 2 ]] || { echo "Missing value for --api-port" >&2; exit 1; }
      VISUAL_ARGS+=("$1" "$2")
      shift 2
      ;;
    --px4-dir|--sample-image|--system-address|--world|--qgc-path)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      VISUAL_ARGS+=("$1" "$2")
      shift 2
      ;;
    --skip-px4|--skip-qgc|--keep-px4)
      VISUAL_ARGS+=("$1")
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

if [[ ! -x "$VISUAL_SCRIPT" ]]; then
  echo "Missing visual demo launcher: $VISUAL_SCRIPT" >&2
  exit 1
fi

cleanup() {
  local exit_code=$?
  if [[ -n "$VISUAL_PID" ]] && kill -0 "$VISUAL_PID" >/dev/null 2>&1; then
    kill "$VISUAL_PID" >/dev/null 2>&1 || true
    wait "$VISUAL_PID" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-90}"

  for ((i = 1; i <= attempts; i++)); do
    if [[ -n "$VISUAL_PID" ]] && ! kill -0 "$VISUAL_PID" >/dev/null 2>&1; then
      echo "Visual demo process exited unexpectedly while waiting for $name." >&2
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

detect_browser() {
  if [[ -n "$BROWSER_CMD" ]]; then
    echo "$BROWSER_CMD"
    return 0
  fi

  local candidate=""
  candidate="$(command -v xdg-open 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v sensible-browser 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v firefox 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v google-chrome 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  candidate="$(command -v chromium-browser 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

open_dashboard() {
  local url="$1"
  if [[ "$START_BROWSER" != "true" ]]; then
    echo "Skipping browser launch by request."
    return 0
  fi
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "Skipping browser launch: no DISPLAY/WAYLAND session detected."
    return 0
  fi

  local browser_bin=""
  browser_bin="$(detect_browser || true)"
  if [[ -z "$browser_bin" ]]; then
    echo "No browser command detected. Open manually: $url"
    return 0
  fi

  echo "Opening dashboard: $url"
  if [[ "$browser_bin" == *"xdg-open" || "$browser_bin" == *"sensible-browser" ]]; then
    "$browser_bin" "$url" >/dev/null 2>&1 &
  else
    "$browser_bin" "$url" >/dev/null 2>&1 &
  fi
}

echo "Starting competition mode..."
"$VISUAL_SCRIPT" "${VISUAL_ARGS[@]}" &
VISUAL_PID=$!

DASHBOARD_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
wait_for_url "$DASHBOARD_URL" "Competition dashboard"
open_dashboard "$DASHBOARD_URL"

echo
echo "Competition mode checklist:"
echo "1. Gazebo/PX4 should already be visible in the PX4 terminal session."
echo "2. Dashboard URL: ${DASHBOARD_URL}"
echo "3. If QGroundControl is installed, it should launch automatically unless --skip-qgc was used."
echo "4. Recommended presentation layout: left = Gazebo/QGC, right = Muye dashboard."
echo "5. Press Ctrl+C in this terminal to stop the whole demo stack."

set +e
wait "$VISUAL_PID"
status=$?
set -e

exit "$status"
