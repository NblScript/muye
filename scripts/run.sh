#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
FRONTEND_DIR="${ROOT_DIR}/frontend"
IMAGES_DIR="${ROOT_DIR}/data/images"
CONFIG_FILE="${ROOT_DIR}/config/drone_config.json"
API_KEYS_FILE="${ROOT_DIR}/config/api_keys.env"
PRODUCTION_ENV_FILE="${ROOT_DIR}/.env.production"
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
Usage: ./scripts/run.sh [options]

牧野生产模式主入口：24 小时自动巡检循环。
启动后自动采集图片 → YOLO 检测 → AI 决策 → 自动喷洒 → 自动复检 → 多轮循环至杀灭率达标。
每 24 小时重复一次，无需人工干预。

与 demo.sh 的区别：
  - 自动起飞（无需前端确认）
  - 启动即采集（不等待手动注入）
  - PX4 MAVSDK 真实执行模式（可连接 SITL 或真机）
  - 支持无前端无头运行
  - 使用真实 API（需配置 .env.production）

Options:
  --api-host <host>           API 监听地址（默认 127.0.0.1）
  --api-port <port>           API 端口（默认 18000）
  --frontend-port <port>      前端端口（默认 5173）
  --no-frontend               不启动前端（无头运行）
  --skip-precheck             跳过环境检查
  --allow-default-env         缺少 .env.production 时仍允许启动
  -h, --help                  显示帮助信息
EOF
}

# 默认配置
API_HOST="${MUYE_API_HOST:-127.0.0.1}"
API_PORT="${MUYE_API_PORT:-18000}"
FRONTEND_PORT=5173
NO_FRONTEND="false"
SKIP_PRECHECK="false"
ALLOW_DEFAULT_ENV="false"
USING_DEFAULT_ENV="false"

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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-host)
            [[ $# -ge 2 ]] || { echo "Missing value for --api-host" >&2; exit 1; }
            API_HOST="$2"
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
        --no-frontend) NO_FRONTEND="true"; shift ;;
        --skip-precheck) SKIP_PRECHECK="true"; shift ;;
        --allow-default-env) ALLOW_DEFAULT_ENV="true"; shift ;;
        -h|--help)       usage; exit 0 ;;
        *)               echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

# 加载环境变量
load_env_file "$API_KEYS_FILE" false
if [[ -f "$PRODUCTION_ENV_FILE" ]]; then
    load_env_file "$PRODUCTION_ENV_FILE" true
    print_info "已加载生产环境: .env.production"
else
    if [[ "$ALLOW_DEFAULT_ENV" == "true" ]]; then
        USING_DEFAULT_ENV="true"
        print_warn "缺少 .env.production，已按 --allow-default-env 使用默认配置"
    else
        print_error "缺少 .env.production"
        echo "  生产模式请先配置: cp .env.production.example .env.production"
        echo "  如需本地联调默认配置，请显式传入: ./scripts/run.sh --allow-default-env"
        exit 1
    fi
fi

# 显式允许无生产配置时，固定使用安全的本地联调行为。
if [[ "$USING_DEFAULT_ENV" == "true" ]]; then
    export QWEN_USE_MOCK="${QWEN_USE_MOCK:-true}"
    export QWEATHER_USE_MOCK="${QWEATHER_USE_MOCK:-true}"
    export RAG_ENABLED="${RAG_ENABLED:-false}"
    export MUYE_TAKEOFF_MODE="${MUYE_TAKEOFF_MODE:-manual}"
    export PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-animated_demo}"
    export PX4_AUTO_START_ON_SPRAY="${PX4_AUTO_START_ON_SPRAY:-false}"
fi

# 配置生产模式覆盖
export DRONE_BACKEND="${DRONE_BACKEND:-px4}"
export MUYE_TAKEOFF_MODE="${MUYE_TAKEOFF_MODE:-auto}"
export PX4_EXECUTION_MODE="${PX4_EXECUTION_MODE:-real}"
export PX4_AUTO_START_ON_SPRAY="${PX4_AUTO_START_ON_SPRAY:-true}"
export PX4_RETURN_TO_LAUNCH_AFTER_MISSION="${PX4_RETURN_TO_LAUNCH_AFTER_MISSION:-true}"
export PX4_REQUIRE_GLOBAL_POSITION="${PX4_REQUIRE_GLOBAL_POSITION:-true}"
export PX4_ALLOW_FORCE_ARM="${PX4_ALLOW_FORCE_ARM:-false}"
export PX4_AUTO_ARM="${PX4_AUTO_ARM:-true}"
export PX4_AUTO_START_MISSION="${PX4_AUTO_START_MISSION:-true}"
export PX4_USE_EXISTING_MISSION="${PX4_USE_EXISTING_MISSION:-false}"
export PX4_REQUIRE_EXISTING_MISSION="${PX4_REQUIRE_EXISTING_MISSION:-false}"
export PX4_EXISTING_MISSION_TOTAL_WAYPOINTS="${PX4_EXISTING_MISSION_TOTAL_WAYPOINTS:-0}"
export PX4_MISSION_TAKEOFF_ALTITUDE_M="${PX4_MISSION_TAKEOFF_ALTITUDE_M:-2.0}"
export PX4_MISSION_TAKEOFF_BEFORE_START="${PX4_MISSION_TAKEOFF_BEFORE_START:-false}"
export PX4_MISSION_TAKEOFF_TIMEOUT_SECONDS="${PX4_MISSION_TAKEOFF_TIMEOUT_SECONDS:-20.0}"
export PX4_MISSION_TAKEOFF_ALTITUDE_TOLERANCE_M="${PX4_MISSION_TAKEOFF_ALTITUDE_TOLERANCE_M:-0.35}"
export PX4_MISSION_EMERGENCY_MAX_ALTITUDE_M="${PX4_MISSION_EMERGENCY_MAX_ALTITUDE_M:-3.0}"

# 闭环评估配置
export MUYE_EVALUATION_AUTO_RETRY="${MUYE_EVALUATION_AUTO_RETRY:-true}"
export MUYE_EVALUATION_KILL_RATE_THRESHOLD="${MUYE_EVALUATION_KILL_RATE_THRESHOLD:-0.9}"
export MUYE_EVALUATION_MAX_RETRIES="${MUYE_EVALUATION_MAX_RETRIES:-3}"
export MUYE_EVALUATION_ENABLED="${MUYE_EVALUATION_ENABLED:-true}"

# 清理函数
PIDS=()
cleanup() {
    echo ""
    print_info "正在停止所有服务..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    print_info "已停止"
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

echo "=========================================="
echo "  牧野智慧农业作业系统（生产模式）"
echo "=========================================="
echo ""
echo "  工作模式:   24h 自动巡检循环"
echo "  起飞模式:   $MUYE_TAKEOFF_MODE"
echo "  无人机后端: $DRONE_BACKEND"
echo "  PX4 模式:   $PX4_EXECUTION_MODE"
echo "  任务闭环:   自动重试至杀灭率 ≥ 90%"
echo "  API 地址:   ${API_HOST}:${API_PORT}"
if [[ "$NO_FRONTEND" != "true" ]]; then
    echo "  前端端口:   $FRONTEND_PORT"
else
    echo "  前端:       不启动（无头模式）"
fi
echo ""

# ── 1. 环境检查 ──
if [[ "$SKIP_PRECHECK" != "true" ]]; then
    print_stage "1/3" "环境检查"
    if [[ ! -x "$PYTHON_BIN" ]]; then
        print_error "Python 虚拟环境不存在"
        echo "  运行: ./scripts/prepare.sh"
        exit 1
    fi
    print_success "Python: $("$PYTHON_BIN" --version 2>&1)"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        print_error "无人机配置文件不存在: $CONFIG_FILE"
        exit 1
    fi
    print_success "配置文件: $CONFIG_FILE"

    # --with-yolo-api 会加载本地模型，因此模型缺失必须立即失败。
    YOLO_MODEL_PATH="${YOLO_LOCAL_MODEL_PATH:-models/best.pt}"
    if [[ "$YOLO_MODEL_PATH" = /* ]]; then
        RESOLVED_YOLO_MODEL_PATH="$YOLO_MODEL_PATH"
    else
        RESOLVED_YOLO_MODEL_PATH="${ROOT_DIR}/${YOLO_MODEL_PATH}"
    fi
    if [[ -f "$RESOLVED_YOLO_MODEL_PATH" ]]; then
        print_success "YOLO 模型: $YOLO_MODEL_PATH"
    else
        print_error "YOLO 模型不存在: $YOLO_MODEL_PATH"
        echo "  --with-yolo-api 需要可用的本地模型，请设置 YOLO_LOCAL_MODEL_PATH"
        exit 1
    fi

    # 检查 DJI OSDK 配置（当后端为 dji_osdk 时）
    if [[ "$DRONE_BACKEND" == "dji_osdk" ]]; then
        DJI_PORT=$("$PYTHON_BIN" -c "
import json
c = json.load(open('$CONFIG_FILE'))
print(c.get('dji_osdk', {}).get('serial_port', ''))
" 2>/dev/null || echo "")
        if [[ -n "$DJI_PORT" ]]; then
            print_success "DJI OSDK 串口: $DJI_PORT"
        else
            print_warn "DJI OSDK 串口未配置，请检查 config/drone_config.json → dji_osdk.serial_port"
        fi
    fi
else
    print_info "跳过环境检查"
fi

# ── 2. 启动服务 ──
print_stage "2/3" "启动服务"

mkdir -p "$IMAGES_DIR"

# 清理旧事件和状态
PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -c "
from modules.infra.common import ensure_runtime_dirs
from app import deps
import app.services.workflow_service as workflow_service
ensure_runtime_dirs()
deps.clear_takeoff_confirmation_state()
" 2>/dev/null || true

SYSTEM_LOG_OFFSET=0
if [[ -f "$SYSTEM_LOG_PATH" ]]; then
    SYSTEM_LOG_OFFSET=$(wc -c < "$SYSTEM_LOG_PATH")
fi

# 启动前端 API
(
    cd "$ROOT_DIR"
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn app.main:api_app \
        --host "$API_HOST" --port "$API_PORT" --log-level info
) &
PIDS+=($!)
print_info "前端 API 启动中 (端口 $API_PORT)..."

# 启动后台主流程（注意：不传 --no-capture-on-startup，启动即采集）
(
    cd "$ROOT_DIR"
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m app.main \
        --with-yolo-api --drone-backend "$DRONE_BACKEND"
) &
PIDS+=($!)
print_info "主管道启动中（含 24h 自动巡检）..."

# 启动前端（可选）
if [[ "$NO_FRONTEND" != "true" ]]; then
    (
        cd "$FRONTEND_DIR"
        MUYE_API_TARGET="http://127.0.0.1:${API_PORT}" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
    ) &
    PIDS+=($!)
    print_info "前端启动中 (端口 $FRONTEND_PORT)..."
fi

# 等待服务就绪
wait_for_url "http://${API_HOST}:${API_PORT}/live" "前端 API 进程" 60
wait_for_url "http://${API_HOST}:${API_PORT}/health" "前端 API 依赖" 60
wait_for_url "http://127.0.0.1:8010/health" "YOLO API" 30

if [[ "$NO_FRONTEND" != "true" ]]; then
    wait_for_url "http://127.0.0.1:${FRONTEND_PORT}" "前端" 30
fi

if wait_for_main_pipeline_ready "$SYSTEM_LOG_OFFSET" 60; then
    print_success "主处理链已就绪"
else
    print_warn "未检测到主处理链就绪日志，继续运行"
fi

# ── 3. 运行状态 ──
print_stage "3/3" "系统就绪"
echo ""
echo "=========================================="
echo "  生产模式运行中"
echo "=========================================="
echo ""
echo "  API 服务:    http://${API_HOST}:${API_PORT}/health"
echo "  巡检间隔:    每 24 小时自动采集"
echo "  起飞模式:    $MUYE_TAKEOFF_MODE"
echo "  任务闭环:    自动重试至杀灭率 ≥ 90%"
echo "  RAG 索引:    完成任务自动索引"
if [[ "$NO_FRONTEND" != "true" ]]; then
    echo "  前端大屏:    http://localhost:${FRONTEND_PORT}"
fi
echo ""
echo "  按 Ctrl+C 停止"
echo ""

# 等待任意子进程退出
wait -n "${PIDS[@]}" 2>/dev/null || true
