#!/bin/bash
# Build, run, verify and clean up the isolated container smoke stack.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.smoke.yml"
PROJECT_NAME="${MUYE_SMOKE_PROJECT_NAME:-muye-smoke}"
WAIT_TIMEOUT="${MUYE_SMOKE_WAIT_TIMEOUT:-180}"
API_PORT="${MUYE_SMOKE_API_PORT:-18080}"
YOLO_PORT="${MUYE_SMOKE_YOLO_PORT:-18010}"
FRONTEND_PORT="${MUYE_SMOKE_FRONTEND_PORT:-5174}"
KEEP_STACK="${MUYE_SMOKE_KEEP:-0}"

case "$PROJECT_NAME" in
    ""|*[!a-zA-Z0-9_-]*)
        echo "MUYE_SMOKE_PROJECT_NAME 只能包含字母、数字、下划线和连字符" >&2
        exit 2
        ;;
esac

for command_name in docker python3; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "缺少必需命令: $command_name" >&2
        exit 2
    fi
done
if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 不可用" >&2
    exit 2
fi

COMPOSE=(docker compose --project-name "$PROJECT_NAME" --file "$COMPOSE_FILE")

cleanup() {
    status=$?
    set +e
    if [ "$status" -ne 0 ]; then
        echo "冒烟测试失败，输出容器日志..." >&2
        "${COMPOSE[@]}" logs --no-color --tail 300 >&2
    fi
    if [ "$KEEP_STACK" = "1" ]; then
        echo "MUYE_SMOKE_KEEP=1，保留项目 $PROJECT_NAME 供排查"
    else
        "${COMPOSE[@]}" down --volumes --remove-orphans
    fi
    return "$status"
}
trap cleanup EXIT

cd "$ROOT_DIR"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up --build --wait --wait-timeout "$WAIT_TIMEOUT"

python3 scripts/container_smoke.py \
    --backend-url "http://127.0.0.1:${API_PORT}" \
    --frontend-url "http://127.0.0.1:${FRONTEND_PORT}" \
    --yolo-url "http://127.0.0.1:${YOLO_PORT}"
