#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_SAMPLE_IMAGE="${ROOT_DIR}/IP000000042.jpg"
DEMO_SCRIPT="${ROOT_DIR}/scripts/start_demo.sh"
PX4_SCRIPT="${ROOT_DIR}/scripts/start_all_in_one.sh"

USE_PX4="false"
USE_SAMPLE="true"
SAMPLE_IMAGE=""
PASSTHROUGH_ARGS=()

usage() {
  cat <<'EOF'
Usage: ./scripts/start_showtime.sh [options]

One command launcher for competition现场演示.

Default behavior:
  - Starts the stable React + backend demo stack
  - Auto-seeds the built-in sample image when available

Options:
  --with-px4                Switch to the PX4/Gazebo competition stack
  --no-sample               Do not auto-seed the built-in demo image
  --sample-image <path>     Use a custom image instead of the built-in sample
  --frontend-port <port>    Frontend port
  --api-port <port>         Frontend API port
  --skip-browser            PX4 mode only: do not auto-open browser
  --skip-qgc                PX4 mode only: do not launch QGroundControl
  --skip-px4                PX4 mode only: reuse an already-running PX4 SITL
  --keep-px4                PX4 mode only: keep PX4 running after exit
  --browser-cmd <path>      PX4 mode only: explicit browser executable
  --px4-dir <path>          PX4 mode only: PX4-Autopilot directory
  --qgc-path <path>         PX4 mode only: explicit QGroundControl executable
  --system-address <addr>   PX4 mode only: MAVSDK system address
  --world <name>            PX4 mode only: Gazebo world name
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-px4)
      USE_PX4="true"
      shift
      ;;
    --no-sample)
      USE_SAMPLE="false"
      shift
      ;;
    --sample-image)
      [[ $# -ge 2 ]] || { echo "Missing value for --sample-image" >&2; exit 1; }
      SAMPLE_IMAGE="$2"
      USE_SAMPLE="true"
      shift 2
      ;;
    --frontend-port|--api-port|--skip-browser|--skip-qgc|--skip-px4|--keep-px4|--browser-cmd|--px4-dir|--qgc-path|--system-address|--world)
      if [[ "$1" =~ ^(--frontend-port|--api-port|--browser-cmd|--px4-dir|--qgc-path|--system-address|--world)$ ]]; then
        [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
        PASSTHROUGH_ARGS+=("$1" "$2")
        shift 2
      else
        PASSTHROUGH_ARGS+=("$1")
        shift
      fi
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

if [[ "$USE_PX4" == "true" ]]; then
  if [[ ! -x "$PX4_SCRIPT" ]]; then
    echo "Missing PX4 launcher: $PX4_SCRIPT" >&2
    exit 1
  fi
else
  if [[ ! -x "$DEMO_SCRIPT" ]]; then
    echo "Missing demo launcher: $DEMO_SCRIPT" >&2
    exit 1
  fi
fi

if [[ -n "$SAMPLE_IMAGE" ]]; then
  if [[ "$SAMPLE_IMAGE" != /* ]]; then
    SAMPLE_IMAGE="${ROOT_DIR}/${SAMPLE_IMAGE}"
  fi
  if [[ ! -f "$SAMPLE_IMAGE" ]]; then
    echo "Sample image not found: $SAMPLE_IMAGE" >&2
    exit 1
  fi
elif [[ "$USE_SAMPLE" == "true" && -f "$DEFAULT_SAMPLE_IMAGE" ]]; then
  SAMPLE_IMAGE="$DEFAULT_SAMPLE_IMAGE"
fi

echo "Launching Muye showtime mode..."
if [[ "$USE_PX4" == "true" ]]; then
  echo "Mode: PX4/Gazebo competition stack"
else
  echo "Mode: stable backend + React demo stack"
fi

if [[ -n "$SAMPLE_IMAGE" ]]; then
  echo "Sample image: $SAMPLE_IMAGE"
else
  echo "Sample image: none"
fi

if [[ "$USE_PX4" == "true" ]]; then
  if [[ -n "$SAMPLE_IMAGE" ]]; then
    exec "$PX4_SCRIPT" --sample-image "$SAMPLE_IMAGE" "${PASSTHROUGH_ARGS[@]}"
  fi
  exec "$PX4_SCRIPT" "${PASSTHROUGH_ARGS[@]}"
fi

if [[ -n "$SAMPLE_IMAGE" ]]; then
  exec "$DEMO_SCRIPT" --sample-image "$SAMPLE_IMAGE" "${PASSTHROUGH_ARGS[@]}"
fi

exec "$DEMO_SCRIPT" "${PASSTHROUGH_ARGS[@]}"
