#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
SMOKE_DIR="${ROOT_DIR}/data/runtime/smoke"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python virtualenv not found: $PYTHON_BIN" >&2
    echo "Run: ./scripts/prepare.sh" >&2
    exit 1
fi

mkdir -p "$SMOKE_DIR"

export QWEN_USE_MOCK="true"
export QWEATHER_USE_MOCK="true"
export QWEATHER_MOCK_HUMIDITY="${QWEATHER_MOCK_HUMIDITY:-70}"
export RAG_ENABLED="false"
export DRONE_BACKEND="px4"
export MUYE_TAKEOFF_MODE="auto"
export PX4_AUTO_START_ON_SPRAY="false"
export PX4_REQUIRE_GLOBAL_POSITION="false"
export PX4_ALLOW_FORCE_ARM="true"
export MUYE_SQLITE_PATH="${SMOKE_DIR}/muye-smoke.db"
export YOLO_ALLOWED_IPS=""

PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" "${ROOT_DIR}/scripts/demo_smoke.py"
