#!/usr/bin/env bash
# demo.sh — 牧野竞赛演示剧本（录像用）
# 自动推进：巡检(30s) → 害虫识别(5s) → AI决策(手动确认) → 打药执行
#
# 用法:
#   ./scripts/demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
API_KEYS_FILE="${ROOT_DIR}/config/api_keys.env"
DEMO_ENV_FILE="${ROOT_DIR}/.env.demo"
SEED_SCRIPT="${ROOT_DIR}/scripts/seed_demo_stages.py"

# ── 颜色 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info()    { echo -e "${BLUE}ℹ${NC} $1"; }
print_warn()    { echo -e "${YELLOW}⚠${NC} $1"; }

# ── 配置 ──
API_PORT="${MUYE_API_PORT:-18000}"
FRONTEND_PORT=5173

# ── 加载环境 ──
load_env_file() {
    local file="$1" override="${2:-false}"
    if [[ -f "$file" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
            [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
            local key="${BASH_REMATCH[1]}" value="${BASH_REMATCH[2]}"
            if [[ "$override" == "true" || -z "${!key+x}" ]]; then
                value="${value%\"}"; value="${value#\"}"
                value="${value%\'}"; value="${value#\'}"
                export "$key=$value"
            fi
        done < "$file"
    fi
}

load_env_file "$API_KEYS_FILE" false
[[ -f "$DEMO_ENV_FILE" ]] && load_env_file "$DEMO_ENV_FILE" true

# ── 演示环境变量 ──
export DRONE_BACKEND="px4"
export PX4_EXECUTION_MODE="animated_demo"
export PX4_AUTO_START_ON_SPRAY="false"
export MUYE_TAKEOFF_MODE="manual"
export QWEATHER_USE_MOCK="true"
export QWEATHER_MOCK_HUMIDITY="61"
export QWEN_USE_MOCK="true"
export RAG_ENABLED="false"
export MUYE_MULTI_AGENT_ENABLED="false"
export MUYE_ROUTER_ENABLED="false"
export PX4_REQUIRE_GLOBAL_POSITION="false"
export PX4_ALLOW_FORCE_ARM="true"

# ── 清理 ──
PIDS=()
cleanup() {
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

# ── 工具函数 ──
wait_for_url() {
    local url="$1" name="$2" attempts="${3:-60}"
    for ((i = 1; i <= attempts; i++)); do
        if curl -fsS "$url" >/dev/null 2>&1; then sleep 1; return 0; fi
        sleep 1
    done
    echo -e "${YELLOW}⚠${NC} $name 启动超时" >&2
    return 1
}

seed_stage() {
    local stage="$1" label="$2"
    print_info "${label}..."
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" "$SEED_SCRIPT" --stage "$stage"
    sleep 1
}

countdown() {
    local sec="$1"
    for ((i = sec; i > 0; i--)); do
        printf "\r  ${CYAN}⏳${NC} %ds " "$i"
        sleep 1
    done
    printf "\r\033[K"
}

# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════


# ── 环境检查 ──
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python 虚拟环境不存在: $VENV_DIR，请先运行 ./scripts/prepare.sh" >&2
    exit 1
fi
if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
    print_info "安装前端依赖..."
    (cd "$FRONTEND_DIR" && npm install --silent)
fi

# ── 清空旧数据 ──
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" "$SEED_SCRIPT" --stage clear 2>/dev/null || true
print_success "旧数据已清空"

# ── 启动服务 ──
echo ""
echo -e "${CYAN}━━━ 启动服务 ━━━${NC}"

(cd "$ROOT_DIR" && PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn app.main:api_app \
    --host 127.0.0.1 --port "$API_PORT" --log-level warning) &
PIDS+=($!)

(cd "$FRONTEND_DIR" && MUYE_API_TARGET="http://127.0.0.1:${API_PORT}" \
    npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --no-open) &
PIDS+=($!)

wait_for_url "http://127.0.0.1:${API_PORT}/live" "API" 60
wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" "前端" 60

print_success "所有服务已就绪"
echo -e "  前端大屏: ${GREEN}http://localhost:${FRONTEND_PORT}?demo=1${NC}"
echo ""

# ═══════════════════════════════════════════════════
# 阶段 1: 无人机巡检 (30s)
# ═══════════════════════════════════════════════════
echo -e "${CYAN}╔══ 阶段 1: 无人机起飞巡检 ══╗${NC}"
echo -e "  ${WHITE}演讲开场，15 秒后启动无人机巡检动画${NC}"
countdown 15
seed_stage "patrol" "播种巡检数据"
echo -e "  ${WHITE}前端显示：无人机巡检动画、飞行路径${NC}"
countdown 30

# ═══════════════════════════════════════════════════
# 阶段 2: 害虫识别 (5s)
# ═══════════════════════════════════════════════════
echo ""
echo -e "${CYAN}╔══ 阶段 2: 害虫检测 ══╗${NC}"
seed_stage "detect" "播种检测数据"
echo -e "  ${WHITE}前端显示：YOLO检测结果、害虫标注图${NC}"
countdown 5

# ═══════════════════════════════════════════════════
# 阶段 3: AI多智能体会诊
# ═══════════════════════════════════════════════════
echo ""
echo -e "${CYAN}╔══ 阶段 3: AI多智能体会诊 ══╗${NC}"
seed_stage "decide" "播种决策数据"
echo -e "  ${WHITE}前端显示：三专家会诊、合规推理、用药方案${NC}"
echo ""

# ═══════════════════════════════════════════════════
# 阶段 4: 确认起飞 → 打药
# ═══════════════════════════════════════════════════
echo -e "${YELLOW}  ═══════════════════════════════════════${NC}"
echo -e "${YELLOW}  ▶  请在前端点击「确认起飞」，系统自动执行喷洒${NC}"
echo -e "${YELLOW}  ═══════════════════════════════════════${NC}"

echo -e "  ${GREEN}前端大屏: http://localhost:${FRONTEND_PORT}?demo=1 — 按 Ctrl+C 停止${NC}"
echo ""

wait -n "${PIDS[@]}" 2>/dev/null || true
