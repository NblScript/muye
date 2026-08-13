#!/bin/bash
# Build, run, verify and clean up the real-YOLO container acceptance stack.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.real-smoke.yml"
PROJECT_NAME="${MUYE_REAL_SMOKE_PROJECT_NAME:-muye-real-smoke}"
WAIT_TIMEOUT="${MUYE_REAL_SMOKE_WAIT_TIMEOUT:-300}"
API_PORT="${MUYE_REAL_SMOKE_API_PORT:-18081}"
FRONTEND_PORT="${MUYE_REAL_SMOKE_FRONTEND_PORT:-5175}"
PIPELINE_TIMEOUT="${MUYE_REAL_SMOKE_PIPELINE_TIMEOUT:-120}"
MODEL_PATH="$ROOT_DIR/models/best.pt"
SAMPLE_PATH="${MUYE_REAL_SMOKE_SAMPLE:-$ROOT_DIR/data/samples/aphids_01.jpg}"
KEEP_STACK="${MUYE_REAL_SMOKE_KEEP:-0}"

case "$PROJECT_NAME" in
    ""|*[!a-zA-Z0-9_-]*)
        echo "MUYE_REAL_SMOKE_PROJECT_NAME 只能包含字母、数字、下划线和连字符" >&2
        exit 2
        ;;
esac

PREFLIGHT_FAILED=0
for command_name in docker python3; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "缺少必需命令: $command_name" >&2
        PREFLIGHT_FAILED=1
    fi
done
if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 不可用" >&2
    PREFLIGHT_FAILED=1
fi
if [ ! -s "$MODEL_PATH" ]; then
    echo "真实 YOLO 模型不存在或为空: $MODEL_PATH" >&2
    echo "请将训练权重放到 models/best.pt 后重试。" >&2
    PREFLIGHT_FAILED=1
fi
if [ ! -s "$SAMPLE_PATH" ]; then
    echo "真实推理样本不存在或为空: $SAMPLE_PATH" >&2
    PREFLIGHT_FAILED=1
fi
if [ "$PREFLIGHT_FAILED" -ne 0 ]; then
    exit 2
fi

COMPOSE=(docker compose --project-name "$PROJECT_NAME" --file "$COMPOSE_FILE")

cleanup() {
    status=$?
    set +e
    if [ "$status" -ne 0 ]; then
        echo "真实模型冒烟失败，输出容器日志..." >&2
        "${COMPOSE[@]}" logs --no-color --tail 300 >&2
    fi
    if [ "$KEEP_STACK" = "1" ]; then
        echo "MUYE_REAL_SMOKE_KEEP=1，保留项目 $PROJECT_NAME 供排查"
    else
        "${COMPOSE[@]}" down --volumes --remove-orphans
    fi
    return "$status"
}
trap cleanup EXIT

echo "真实模型: $MODEL_PATH ($(wc -c < "$MODEL_PATH") bytes)"
echo "推理样本: $SAMPLE_PATH"

cd "$ROOT_DIR"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up --build --wait --wait-timeout "$WAIT_TIMEOUT"

python3 scripts/container_smoke.py \
    --mode real \
    --backend-url "http://127.0.0.1:${API_PORT}" \
    --frontend-url "http://127.0.0.1:${FRONTEND_PORT}" \
    --sample "$SAMPLE_PATH" \
    --pipeline-timeout "$PIPELINE_TIMEOUT"
