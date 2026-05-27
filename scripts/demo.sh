#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
API_KEYS_FILE="${ROOT_DIR}/config/api_keys.env"
DEMO_ENV_FILE="${ROOT_DIR}/.env.demo"
SYSTEM_LOG_PATH="${ROOT_DIR}/data/logs/system.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1" >&2; }
print_stage() { echo -e "${CYAN}[$1]${NC} $2"; }

usage() {
    cat <<'EOF'
Usage: ./scripts/demo.sh [options]

牧野真实链路演示剧本：自动检查环境、启动前后端、注入多智能体固定演示任务。
本剧本用于稳定呈现完整业务链路，不依赖巡检图片、YOLO 推理或实时识别服务。
前端用于展示流程与状态，PX4 动画在 Gazebo 场景中播放。

Options:
  --api-port <port>           API 端口（默认 18000）
  --frontend-port <port>      前端端口（默认 5173）
  --skip-precheck             跳过环境检查
  -h, --help                  显示帮助信息
EOF
}

# 默认配置
TAKEOFF_MODE="manual"
API_PORT="${MUYE_API_PORT:-18000}"
FRONTEND_PORT=5173
SKIP_PRECHECK="false"

load_env_file() {
    local file="$1"
    local override="${2:-false}"
    if [[ -f "$file" ]]; then
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
            [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"
            if [[ "$override" == "true" || -z "${!key+x}" ]]; then
                value="${value%\"}"
                value="${value#\"}"
                value="${value%\'}"
                value="${value#\'}"
                export "$key=$value"
            fi
        done < "$file"
    fi
}

load_demo_environment() {
    load_env_file "$API_KEYS_FILE" false
    if [[ -f "$DEMO_ENV_FILE" ]]; then
        load_env_file "$DEMO_ENV_FILE" true
        print_info "已加载演示环境: .env.demo"
    fi
}

is_placeholder_secret() {
    local value="${1:-}"
    [[ -z "$value" || "$value" == *"your-"* || "$value" == *"replace-with"* || "$value" == *"在此填入"* ]]
}

configure_demo_fallbacks() {
    export QWEATHER_USE_MOCK="true"
    export QWEATHER_MOCK_HUMIDITY="70"
    print_info "演示天气固定使用本地数据，湿度 70%"

    if [[ "${QWEN_USE_MOCK:-false}" != "true" ]] && is_placeholder_secret "${QWEN_API_KEY:-}"; then
        export QWEN_USE_MOCK="true"
        export RAG_ENABLED="${RAG_ENABLED:-false}"
        print_warn "未检测到有效 QWEN_API_KEY，本次启动自动使用本地 AI 决策"
    fi

    export DRONE_BACKEND="px4"
    export MUYE_TAKEOFF_MODE="${MUYE_TAKEOFF_MODE:-$TAKEOFF_MODE}"
    export PX4_AUTO_START_ON_SPRAY="${PX4_AUTO_START_ON_SPRAY:-true}"
    export PX4_RETURN_TO_LAUNCH_AFTER_MISSION="false"
    export PX4_REQUIRE_GLOBAL_POSITION="${PX4_REQUIRE_GLOBAL_POSITION:-false}"
    export PX4_ALLOW_FORCE_ARM="${PX4_ALLOW_FORCE_ARM:-true}"
    export PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-animated_demo}"
    export PX4_USE_EXISTING_MISSION="${PX4_USE_EXISTING_MISSION:-false}"
    export PX4_REQUIRE_EXISTING_MISSION="${PX4_REQUIRE_EXISTING_MISSION:-false}"
    export PX4_EXISTING_MISSION_TOTAL_WAYPOINTS="${PX4_EXISTING_MISSION_TOTAL_WAYPOINTS:-0}"
    export PX4_MISSION_TAKEOFF_ALTITUDE_M="${PX4_MISSION_TAKEOFF_ALTITUDE_M:-2.0}"
    export PX4_MISSION_TAKEOFF_BEFORE_START="${PX4_MISSION_TAKEOFF_BEFORE_START:-false}"
    export PX4_MISSION_TAKEOFF_TIMEOUT_SECONDS="${PX4_MISSION_TAKEOFF_TIMEOUT_SECONDS:-20.0}"
    export PX4_MISSION_TAKEOFF_ALTITUDE_TOLERANCE_M="${PX4_MISSION_TAKEOFF_ALTITUDE_TOLERANCE_M:-0.35}"
    export PX4_MISSION_EMERGENCY_MAX_ALTITUDE_M="${PX4_MISSION_EMERGENCY_MAX_ALTITUDE_M:-3.0}"
    print_info "PX4 航线模式：人工确认后启动固定航线动画演示"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-port)
            [[ $# -ge 2 ]] || { echo "Missing value for --api-port" >&2; exit 1; }
            API_PORT="$2"
            shift 2
            ;;
        --frontend-port)
            [[ $# -ge 2 ]] || { echo "Missing value for --frontend-port" >&2; exit 1; }
            FRONTEND_PORT="$2"
            shift 2
            ;;
        --skip-precheck) SKIP_PRECHECK="true"; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

load_demo_environment
configure_demo_fallbacks

# 清理函数
PIDS=()
cleanup() {
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT INT TERM

wait_for_url() {
    local url="$1"
    local name="$2"
    local attempts="${3:-60}"
    for ((i = 1; i <= attempts; i++)); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            print_success "$name 已就绪"
            return 0
        fi
        sleep 1
    done
    print_error "$name 启动超时: $url"
    return 1
}

clear_runtime_state() {
    if PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -c "
from modules.infra.common import ensure_runtime_dirs
from modules.infra.event_bus import FileEventBus
from app import deps
import app.services.workflow_service as workflow_service
ensure_runtime_dirs()
deps.clear_takeoff_confirmation_state()
workflow_service.clear_demo_runtime_state()
FileEventBus().clear()
"; then
        print_success "旧运行状态已清理"
    else
        print_warn "旧运行状态清理失败，可能存在 SQLite 外键约束；不影响本轮演示继续启动"
        PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -c "
from modules.infra.common import ensure_runtime_dirs
from modules.infra.event_bus import FileEventBus
from app import deps
ensure_runtime_dirs()
deps.clear_takeoff_confirmation_state()
FileEventBus().clear()
" 2>/dev/null || true
    fi
}

wait_for_main_pipeline_ready() {
    local offset="${1:-0}"
    local attempts="${2:-60}"
    for ((i = 1; i <= attempts; i++)); do
        if [[ -f "$SYSTEM_LOG_PATH" ]] && tail -c "+$((offset + 1))" "$SYSTEM_LOG_PATH" 2>/dev/null | grep -q "主处理链已启动"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

wait_for_seeded_demo_state() {
    local attempts="${1:-30}"
    for ((i = 1; i <= attempts; i++)); do
        local payload
        payload="$(curl -s "http://127.0.0.1:${API_PORT}/workflow/state" 2>/dev/null || true)"
        if printf '%s' "$payload" | "$PYTHON_BIN" -c "
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

latest = payload.get('latest_task') or {}
rag_context = latest.get('rag_context') or {}
consultation_detail = rag_context.get(\"consultation_detail\") or {}
active_count = int(consultation_detail.get(\"active_count\") or 0)
pesticide = ((latest.get('decision') or {}).get('用药') or {}).get('农药名称')
status = str(latest.get('status') or '').strip()
request_id = str(latest.get('request_id') or '').strip()
ok = (
    request_id == 'demo-fixed-consultation'
    and pesticide == '吡虫啉'
    and status in {'spraying', 'completed', 'pending_confirmation'}
    and active_count >= 3
)
raise SystemExit(0 if ok else 1)
"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

echo "=========================================="
echo "  牧野智慧农业作业系统"
echo "=========================================="
echo ""
echo "  工作流程:   真实链路演示"
echo "  图片投喂:   关闭（固定会诊任务不依赖巡检图片）"
echo "  起飞确认:   前端人工确认"
echo "  API 端口:   $API_PORT"
echo "  前端端口:   $FRONTEND_PORT"
echo "  PX4 演示:   确认起飞后启动"
echo "  演示任务:   多智能体固定演示任务"
echo ""

# ── 1. 环境检查 ──
if [[ "$SKIP_PRECHECK" != "true" ]]; then
    print_stage "1/4" "环境检查"
    if [[ ! -x "$PYTHON_BIN" ]]; then
        print_error "Python 虚拟环境不存在"
        echo "  运行: ./scripts/prepare.sh"
        exit 1
    fi
    print_success "Python: $("$PYTHON_BIN" --version 2>&1)"
    print_info "固定会诊任务不依赖巡检图片，跳过图片检查"
else
    print_info "跳过环境检查"
fi

# ── 2. 更新配置 ──
print_stage "2/4" "更新运行配置"

print_success "演示配置已通过环境变量注入，不修改 drone_config.json"

# ── 3. 启动服务 ──
print_stage "3/4" "启动服务"

# 清理旧事件
clear_runtime_state

SYSTEM_LOG_OFFSET=0
if [[ -f "$SYSTEM_LOG_PATH" ]]; then
    SYSTEM_LOG_OFFSET=$(wc -c < "$SYSTEM_LOG_PATH")
fi

# 启动前端 API
(
    cd "$ROOT_DIR"
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn app.main:api_app \
        --host 127.0.0.1 --port "$API_PORT" --log-level warning
) &
PIDS+=($!)
print_info "前端 API 启动中 (端口 $API_PORT)..."

# 启动后台主流程
MAIN_ARGS=(--drone-backend px4 --no-capture-on-startup)
(
    cd "$ROOT_DIR"
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m app.main "${MAIN_ARGS[@]}"
) &
PIDS+=($!)
print_info "后台主流程启动中..."

# 启动前端
(
    cd "$FRONTEND_DIR"
    MUYE_API_TARGET="http://127.0.0.1:${API_PORT}" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
) &
PIDS+=($!)
print_info "前端启动中 (端口 $FRONTEND_PORT)..."

# 等待服务就绪
wait_for_url "http://127.0.0.1:${API_PORT}/live" "前端 API 进程" 60
wait_for_url "http://127.0.0.1:${API_PORT}/health" "前端 API 依赖" 60
print_info "真实链路演示剧本不等待实时识别服务"
wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" "前端" 30
if wait_for_main_pipeline_ready "$SYSTEM_LOG_OFFSET" 60; then
    print_success "主处理链已就绪"
else
    print_warn "未检测到主处理链就绪日志，继续尝试演示"
fi

print_info "本轮将等待前端手动确认后启动 PX4 固定航线动画"

# ── 4. 准备演示任务 ──
print_stage "4/4" "注入多智能体固定演示任务"
echo ""

if (
    cd "$ROOT_DIR"
    ./scripts/seed_demo_state.sh --keep-existing
); then
    print_success "多智能体固定演示任务已注入"
    if wait_for_seeded_demo_state 30; then
        print_success "前端 API 已读取到 3 位专家会诊结果"
        print_info "刷新前端即可查看多智能体专家会诊、AI 决策和决策依据"
    else
        print_error "固定会诊任务已写入，但前端 API 未读取到完整会诊结果"
        exit 1
    fi
else
    print_error "多智能体固定演示任务注入失败"
    exit 1
fi

# ── 运行状态 ──
echo ""
echo "=========================================="
echo "  作业系统运行中"
echo "=========================================="
echo ""
echo "  前端大屏: http://localhost:${FRONTEND_PORT}"
echo "  API 服务: http://localhost:${API_PORT}/health"
echo "  现场诊断: ./scripts/demo_doctor.sh --base-url http://127.0.0.1:${API_PORT}"
echo "  下一步:    在前端点击确认起飞，然后观察 Gazebo 中的无人机动画"
echo "  PX4 演示:  使用固定航线动画模式"
echo ""
echo "  按 Ctrl+C 停止"
echo ""

# 等待任意子进程退出
wait -n "${PIDS[@]}" 2>/dev/null || true
