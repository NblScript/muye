#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPETITION_SCRIPT="${ROOT_DIR}/scripts/start_competition_mode.sh"
DEFAULT_SAMPLE_IMAGE="${ROOT_DIR}/IP000000042.jpg"
DEFAULT_QGC_PATH="${HOME}/Applications/QGroundControl-x86_64.AppImage"

SAMPLE_IMAGE=""
USE_DEFAULT_SAMPLE="false"
QGC_PATH=""
PASSTHROUGH_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/start_all_in_one.sh [options]

One-click competition launcher. It brings up:
  - Muye backend
  - React frontend
  - Browser dashboard page
  - PX4 SITL + Gazebo
  - QGroundControl drone page when available

Options:
  --with-sample             Auto-seed the built-in demo image after startup
  --sample-image <path>     Seed a custom image after startup
  --qgc-path <path>         Explicit QGroundControl executable/AppImage path
  --skip-px4                Reuse an already-running PX4 SITL
  --skip-qgc                Do not launch QGroundControl
  --skip-browser            Do not auto-open the dashboard page
  --keep-px4                Keep PX4 SITL running after exit
  --px4-dir <path>          PX4-Autopilot directory
  --frontend-port <port>    Frontend port, default 8501
  --api-port <port>         Frontend API port, default 18000
  --system-address <addr>   MAVSDK system address
  --world <name>            Gazebo world name
  --browser-cmd <path>      Explicit browser executable
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-sample)
      USE_DEFAULT_SAMPLE="true"
      shift
      ;;
    --sample-image)
      [[ $# -ge 2 ]] || { echo "Missing value for --sample-image" >&2; exit 1; }
      SAMPLE_IMAGE="$2"
      shift 2
      ;;
    --qgc-path)
      [[ $# -ge 2 ]] || { echo "Missing value for --qgc-path" >&2; exit 1; }
      QGC_PATH="$2"
      shift 2
      ;;
    --skip-px4|--skip-qgc|--skip-browser|--keep-px4)
      PASSTHROUGH_ARGS+=("$1")
      shift
      ;;
    --px4-dir|--frontend-port|--api-port|--system-address|--world|--browser-cmd)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      PASSTHROUGH_ARGS+=("$1" "$2")
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

if [[ ! -x "$COMPETITION_SCRIPT" ]]; then
  echo "Missing launcher: $COMPETITION_SCRIPT" >&2
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
elif [[ "$USE_DEFAULT_SAMPLE" == "true" ]]; then
  if [[ ! -f "$DEFAULT_SAMPLE_IMAGE" ]]; then
    echo "Default sample image not found: $DEFAULT_SAMPLE_IMAGE" >&2
    exit 1
  fi
  SAMPLE_IMAGE="$DEFAULT_SAMPLE_IMAGE"
fi

if [[ -z "$QGC_PATH" && -x "$DEFAULT_QGC_PATH" ]]; then
  QGC_PATH="$DEFAULT_QGC_PATH"
fi

if [[ -n "$QGC_PATH" ]]; then
  PASSTHROUGH_ARGS+=("--qgc-path" "$QGC_PATH")
fi

if [[ -n "$SAMPLE_IMAGE" ]]; then
  PASSTHROUGH_ARGS+=("--sample-image" "$SAMPLE_IMAGE")
fi

echo "Launching one-click competition stack..."
if [[ -n "$QGC_PATH" ]]; then
  echo "QGroundControl: $QGC_PATH"
fi
if [[ -n "$SAMPLE_IMAGE" ]]; then
  echo "Seed image: $SAMPLE_IMAGE"
fi

exec "$COMPETITION_SCRIPT" "${PASSTHROUGH_ARGS[@]}"
