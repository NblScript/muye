#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
SAMPLES_DIR="${ROOT_DIR}/data/samples"
IMAGES_DIR="${ROOT_DIR}/data/images"
CONFIG_FILE="${ROOT_DIR}/config/drone_config.json"
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

牧野单轮作业入口：自动检查环境、启动前后端、投喂一张巡检图片。
检测和 AI 决策完成后，前端人工确认起飞；确认后拉起 PX4 固定航线动画演示。
前端用于展示流程与状态，PX4 动画在 Gazebo 场景中播放。

Options:
  --image <path>              指定本轮投喂图片（默认使用 data/samples 中第一张）
  --api-port <port>           API 端口（默认 18000）
  --frontend-port <port>      前端端口（默认 5173）
  --skip-precheck             跳过环境检查
  --skip-inject               跳过图片注入
  -h, --help                  显示帮助信息
EOF
}

# 默认配置
TAKEOFF_MODE="manual"
API_PORT="${MUYE_API_PORT:-18000}"
FRONTEND_PORT=5173
SKIP_PRECHECK="false"
SKIP_INJECT="false"
SELECTED_IMAGE=""

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
        --image)
            [[ $# -ge 2 ]] || { echo "Missing value for --image" >&2; exit 1; }
            SELECTED_IMAGE="$2"
            shift 2
            ;;
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
        --skip-inject)   SKIP_INJECT="true"; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

if [[ -n "$SELECTED_IMAGE" && "$SELECTED_IMAGE" != /* ]]; then
    SELECTED_IMAGE="${ROOT_DIR}/${SELECTED_IMAGE}"
fi

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
        if curl -s "$url" >/dev/null 2>&1; then
            print_success "$name 已就绪"
            return 0
        fi
        sleep 1
    done
    print_error "$name 启动超时: $url"
    return 1
}

wait_for_latest_status() {
    local expected="$1"
    local attempts="${2:-60}"
    for ((i = 1; i <= attempts; i++)); do
        local payload
        payload="$(curl -s "http://127.0.0.1:${API_PORT}/workflow/state" 2>/dev/null || true)"
        if printf '%s' "$payload" | "$PYTHON_BIN" -c "
import json, sys
expected = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
latest = payload.get('latest_task') or {}
drone = latest.get('drone') or {}
status = str(drone.get('status') or latest.get('status') or '').strip()
raise SystemExit(0 if status == expected else 1)
" "$expected"; then
            return 0
        fi
        sleep 1
    done
    return 1
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

wait_for_terminal_status() {
    local attempts="${1:-180}"
    for ((i = 1; i <= attempts; i++)); do
        local payload
        payload="$(curl -s "http://127.0.0.1:${API_PORT}/workflow/state" 2>/dev/null || true)"
        local status
        status="$(printf '%s' "$payload" | "$PYTHON_BIN" -c "
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print('')
    raise SystemExit(0)
latest = payload.get('latest_task') or {}
drone = latest.get('drone') or {}
print(str(latest.get('status') or drone.get('status') or '').strip())
")"
        case "$status" in
            completed|error|failed|cancelled)
                printf '%s\n' "$status"
                return 0
                ;;
        esac
        sleep 1
    done
    return 1
}

echo "=========================================="
echo "  牧野智慧农业作业系统"
echo "=========================================="
echo ""
echo "  工作流程:   PX4 固定航线演示"
echo "  起飞确认:   前端人工确认"
echo "  图片投喂:   单张"
echo "  API 端口:   $API_PORT"
echo "  前端端口:   $FRONTEND_PORT"
echo "  PX4 演示:   确认起飞后启动"
if [[ -n "$SELECTED_IMAGE" ]]; then
    echo "  指定图片:   $SELECTED_IMAGE"
fi
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

    # 检查巡检图片
    if [[ -n "$SELECTED_IMAGE" ]]; then
        if [[ -f "$SELECTED_IMAGE" ]]; then
            print_success "巡检图片: $SELECTED_IMAGE"
        else
            print_error "指定图片不存在: $SELECTED_IMAGE"
            exit 1
        fi
    elif find "$SAMPLES_DIR" -maxdepth 1 \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) -print -quit 2>/dev/null | grep -q .; then
        IMG_COUNT=$(find "$SAMPLES_DIR" -maxdepth 1 \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) | wc -l)
        print_success "巡检图片: $IMG_COUNT 张"
    else
        print_warn "巡检图片不存在，正在准备..."
        bash "${ROOT_DIR}/scripts/prepare.sh" --images-only
    fi
else
    print_info "跳过环境检查"
fi

# ── 2. 更新配置 ──
print_stage "2/4" "更新运行配置"

print_success "演示配置已通过环境变量注入，不修改 drone_config.json"

# ── 3. 启动服务 ──
print_stage "3/4" "启动服务"

mkdir -p "$IMAGES_DIR"

# 清理旧事件
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -c "
from modules.infra.common import ensure_runtime_dirs
from modules.infra.event_bus import FileEventBus
from app import deps
import app.services.workflow_service as workflow_service
ensure_runtime_dirs()
deps.clear_takeoff_confirmation_state()
workflow_service.clear_demo_runtime_state()
FileEventBus().clear()
" 2>/dev/null || true

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
MAIN_ARGS=(--with-yolo-api --drone-backend px4 --no-capture-on-startup)
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
wait_for_url "http://127.0.0.1:${API_PORT}/health" "前端 API" 60
wait_for_url "http://127.0.0.1:8010/health" "YOLO API" 30
wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" "前端" 30
if wait_for_main_pipeline_ready "$SYSTEM_LOG_OFFSET" 60; then
    print_success "主处理链已就绪"
else
    print_warn "未检测到主处理链就绪日志，继续尝试演示"
fi

print_info "本轮将等待前端手动确认后启动 PX4 固定航线动画"

# ── 4. 注入巡检图片 ──
if [[ "$SKIP_INJECT" != "true" ]]; then
    print_stage "4/4" "投喂单张巡检图片"
    echo ""

    # 清理旧图片，只保留本轮投喂的一张
    find "$IMAGES_DIR" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) -delete 2>/dev/null || true
    print_info "已清理旧巡检图片"

    if [[ -n "$SELECTED_IMAGE" ]]; then
        DEMO_IMAGE="$SELECTED_IMAGE"
    else
        DEMO_IMAGE="$(find "$SAMPLES_DIR" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) -print | sort | head -n 1)"
    fi

    if [[ -z "${DEMO_IMAGE:-}" || ! -f "$DEMO_IMAGE" ]]; then
        print_warn "没有找到巡检图片，跳过投喂"
    else
        filename=$(basename "$DEMO_IMAGE")
        timestamp=$(date +%Y%m%d-%H%M%S)
        target="${IMAGES_DIR}/${timestamp}-${filename}"
        cp "$DEMO_IMAGE" "$target"
        print_success "已投喂 1 张图片: $filename"
        print_info "等待识别和 AI 决策..."

        if wait_for_latest_status "pending_confirmation" 120; then
            print_success "已进入等待起飞确认阶段"
            print_info "请在前端点击“确认起飞”，随后 Gazebo 中会开始 PX4 固定航线动画"
        else
            print_warn "未在预期时间内进入起飞确认阶段，请检查系统日志"
        fi
    fi
else
    print_info "跳过图片投喂"
fi

# ── 运行状态 ──
echo ""
echo "=========================================="
echo "  作业系统运行中"
echo "=========================================="
echo ""
echo "  前端大屏: http://localhost:${FRONTEND_PORT}"
echo "  API 服务: http://localhost:${API_PORT}/health"
echo "  下一步:    在前端点击确认起飞，然后观察 Gazebo 中的无人机动画"
echo "  PX4 演示:  使用固定航线动画模式"
echo ""
echo "  按 Ctrl+C 停止"
echo ""

# 等待任意子进程退出
wait -n "${PIDS[@]}" 2>/dev/null || true
