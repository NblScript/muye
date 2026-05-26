#!/usr/bin/env bash
# check.sh — 竞赛前一键总验证
# 后端关键测试 + 前端测试/构建 + 文档校验
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
NPM_BIN="${ROOT_DIR}/frontend/node_modules/.bin"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass=0
fail=0

run_step() {
  local name="$1"
  shift
  echo -e "${YELLOW}▶ $name${NC}"
  if "$@" 2>&1; then
    echo -e "${GREEN}  ✓ $name 通过${NC}"
    ((pass++))
  else
    echo -e "${RED}  ✗ $name 失败${NC}"
    ((fail++))
  fi
}

echo "========================================"
echo " 牧野系统 — 竞赛总验证"
echo "========================================"

# 1. 后端关键测试（排除需要 PX4 硬件的）
run_step "后端测试" \
  env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m pytest \
    "${ROOT_DIR}/tests/" \
    -v -x \
    -k "not px4_simulator" \
    --timeout=60 \
    --ignore="${ROOT_DIR}/tests/test_script_imports.py" \
    -q

# 2. 前端测试
run_step "前端测试" \
  bash -c 'cd "${0}/frontend" && npx vitest run' "${ROOT_DIR}"

# 3. 前端构建
run_step "前端构建" \
  bash -c 'cd "${0}/frontend" && npx vite build' "${ROOT_DIR}"

# 4. 文档一致性
run_step "文档校验" \
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/verify_docs.py"

echo ""
echo "========================================"
echo -e " 结果：${GREEN}${pass} 通过${NC} / ${RED}${fail} 失败${NC}"
echo "========================================"

if [[ $fail -gt 0 ]]; then
  exit 1
fi
