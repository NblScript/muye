#!/usr/bin/env bash
set -euo pipefail

PRECHECK_ROOT_DIR="${PRECHECK_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PRECHECK_PYTHON_BIN="${PRECHECK_ROOT_DIR}/.venv/bin/python"
PRECHECK_FRONTEND_DIR="${PRECHECK_ROOT_DIR}/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

precheck_print_success() {
  local label="${1:-}"
  echo -e "${GREEN}✓${NC} ${label}"
}

precheck_print_fail() {
  local label="${1:-}"
  local reason="${2:-}"
  if [[ -n "$reason" ]]; then
    echo -e "${RED}✗${NC} ${label}: ${reason}" >&2
  else
    echo -e "${RED}✗${NC} ${label}" >&2
  fi
}

precheck_print_warn() {
  local message="${1:-}"
  echo -e "${YELLOW}⚠${NC} ${message}" >&2
}

precheck_python_venv() {
  if [[ ! -x "$PRECHECK_PYTHON_BIN" ]]; then
    precheck_print_fail "Python 虚拟环境" "缺少可执行解释器 ${PRECHECK_PYTHON_BIN}"
    return 1
  fi

  precheck_print_success "Python 虚拟环境"
}

precheck_python_deps() {
  local missing_modules=""
  if ! missing_modules="$("$PRECHECK_PYTHON_BIN" - <<'PY'
modules = ("ultralytics", "fastapi", "uvicorn")
missing = []
for module in modules:
    try:
        __import__(module)
    except Exception:
        missing.append(module)
print(",".join(missing))
PY
  )"; then
    precheck_print_fail "Python 核心依赖" "依赖检查执行失败"
    return 1
  fi

  if [[ -n "$missing_modules" ]]; then
    precheck_print_fail "Python 核心依赖" "缺少 ${missing_modules}，请执行 ${PRECHECK_PYTHON_BIN} -m pip install -r ${PRECHECK_ROOT_DIR}/requirements.txt"
    return 1
  fi

  precheck_print_success "Python 核心依赖"
}

precheck_npm() {
  local npm_bin=""
  npm_bin="$(command -v npm 2>/dev/null || true)"
  if [[ -z "$npm_bin" ]]; then
    precheck_print_fail "npm" "PATH 中未找到 npm"
    return 1
  fi

  precheck_print_success "npm"
}

precheck_frontend_deps() {
  if [[ ! -d "${PRECHECK_FRONTEND_DIR}/node_modules" ]]; then
    precheck_print_fail "前端依赖" "缺少 ${PRECHECK_FRONTEND_DIR}/node_modules，请先执行 cd ${PRECHECK_FRONTEND_DIR} && npm install"
    return 1
  fi

  precheck_print_success "前端依赖"
}

precheck_px4_dir() {
  local px4_dir="${1:-${HOME}/PX4-Autopilot}"
  if [[ ! -d "$px4_dir" ]]; then
    precheck_print_fail "PX4 目录" "目录不存在 ${px4_dir}"
    return 1
  fi

  precheck_print_success "PX4 目录"
}

precheck_display() {
  if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    precheck_print_success "图形显示环境"
    return 0
  fi

  precheck_print_warn "未检测到 DISPLAY 或 WAYLAND_DISPLAY，GUI 程序可能无法启动"
  return 0
}

precheck_all() {
  local px4_dir="${1:-}"
  local status=0

  precheck_python_venv || status=1
  if [[ $status -eq 0 ]]; then
    precheck_python_deps || status=1
  fi
  precheck_npm || status=1
  precheck_frontend_deps || status=1
  if [[ -n "$px4_dir" ]]; then
    precheck_px4_dir "$px4_dir" || status=1
  fi
  precheck_display || true

  return "$status"
}
