#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" "${ROOT_DIR}/scripts/demo_doctor.py" "$@"
