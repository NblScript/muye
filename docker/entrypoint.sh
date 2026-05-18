#!/bin/bash
# Docker 入口：同时启动主处理流程和 Frontend API
set -e

ROOT_DIR="/app"

cleanup() {
    echo "停止所有服务..."
    kill "$MAIN_PID" "$API_PID" 2>/dev/null || true
    wait "$MAIN_PID" "$API_PID" 2>/dev/null || true
    exit 0
}

trap cleanup EXIT INT TERM

# 启动主处理流程（内嵌 YOLO API + PX4 工作流）
PYTHONPATH="$ROOT_DIR" python -m app.main \
    --with-yolo-api \
    --drone-backend px4 \
    --no-capture-on-startup \
    &
MAIN_PID=$!

# 等待内嵌服务就绪
echo "等待内嵌 YOLO API 就绪..."
for i in $(seq 1 60); do
    if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health')" 2>/dev/null; then
        echo "内嵌服务已就绪"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "内嵌服务启动超时" >&2
        exit 1
    fi
    sleep 1
done

# 启动 Frontend API
API_PORT="${MUYE_API_PORT:-8000}"
echo "启动 Frontend API (0.0.0.0:${API_PORT})..."
PYTHONPATH="$ROOT_DIR" python -m uvicorn app.main:api_app \
    --host 0.0.0.0 \
    --port "$API_PORT" \
    --log-level info \
    &
API_PID=$!

# 等待任一进程退出
wait -n "$MAIN_PID" "$API_PID" 2>/dev/null || true
echo "某个服务已退出，停止所有服务..."
