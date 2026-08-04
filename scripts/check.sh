#!/usr/bin/env bash
# check.sh — 竞赛前一键总验证
# 默认跑竞赛关键路径；需要全量后端回归时设置 MUYE_FULL_CHECK=1。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
CHECK_TIMEOUT_SECONDS="${MUYE_CHECK_TIMEOUT_SECONDS:-180}"
FULL_CHECK="${MUYE_FULL_CHECK:-0}"

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
  if timeout "${CHECK_TIMEOUT_SECONDS}" "$@" 2>&1; then
    echo -e "${GREEN}  ✓ $name 通过${NC}"
    ((pass += 1))
  else
    echo -e "${RED}  ✗ $name 失败${NC}"
    ((fail += 1))
  fi
}

echo "========================================"
echo " 牧野系统 — 竞赛总验证"
echo "========================================"

echo "模式：$([[ "${FULL_CHECK}" == "1" ]] && echo "全量后端回归" || echo "竞赛关键路径")"
echo "单步骤超时：${CHECK_TIMEOUT_SECONDS}s"
echo ""

# 1. 后端关键路径：覆盖合规、RAG、主流程、无人机执行门控、报告和接口稳定性。
run_step "后端关键路径测试" \
  env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m pytest \
    "${ROOT_DIR}/tests/test_pesticide_compliance.py" \
    "${ROOT_DIR}/tests/test_rag_retriever.py" \
    "${ROOT_DIR}/tests/test_ai_decision.py::test_ai_decision_attaches_compliance_result_to_bundle_and_event" \
    "${ROOT_DIR}/tests/test_main.py::test_main_pipeline_blocks_drone_execution_when_compliance_blocks" \
    "${ROOT_DIR}/tests/test_main.py::test_main_pipeline_forces_manual_takeoff_when_compliance_warns" \
    "${ROOT_DIR}/tests/test_main.py::test_main_px4_backend_auto_starts_px4_before_spray" \
    "${ROOT_DIR}/tests/test_data_collector.py" \
    "${ROOT_DIR}/tests/test_rate_limit.py" \
    -q

# 2. 可选全量后端回归：CI 或赛前深度检查再开启，默认不拖慢现场验证。
if [[ "${FULL_CHECK}" == "1" ]]; then
  run_step "后端全量回归" \
    env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m pytest \
      "${ROOT_DIR}/tests/" \
      -x \
      -k "not px4_simulator" \
      --ignore="${ROOT_DIR}/tests/test_script_imports.py" \
      -q
fi

# 3. 固定样例回归：锁定图片、完整热力网格、航线和喷洒速率表。
run_step "固定热力图回归" \
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/eval_fixed_set.py"

# 4. 前端测试
run_step "前端测试" \
  bash -c 'cd "${0}/frontend" && npx vitest run' "${ROOT_DIR}"

# 5. 前端构建
run_step "前端构建" \
  bash -c 'cd "${0}/frontend" && npx vite build' "${ROOT_DIR}"

# 6. 文档一致性
run_step "文档校验" \
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/verify_docs.py"

echo ""
echo "========================================"
echo -e " 结果：${GREEN}${pass} 通过${NC} / ${RED}${fail} 失败${NC}"
echo "========================================"

if [[ $fail -gt 0 ]]; then
  exit 1
fi
