#!/bin/bash
# Docker 入口：同时启动主处理流程和 Frontend API
set -e

ROOT_DIR="/app"
MAIN_PID=""
API_PID=""
YOLO_PID=""

cleanup() {
    echo "停止所有服务..."
    for pid in "$MAIN_PID" "$API_PID" "$YOLO_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

SMOKE_MODE="${MUYE_CONTAINER_SMOKE:-false}"
if [[ "${SMOKE_MODE,,}" =~ ^(1|true|yes|on)$ ]]; then
    echo "启动显式模拟 YOLO API（仅容器冒烟测试）..."
    PYTHONPATH="$ROOT_DIR" python -m uvicorn app.smoke_yolo_api:app \
        --host 0.0.0.0 \
        --port 8010 \
        --log-level info \
        &
    YOLO_PID=$!

    # 冒烟模式把显式模拟服务当作外部 YOLO，不加载任何模型权重。
    PYTHONPATH="$ROOT_DIR" python -m app.main \
        --drone-backend "${DRONE_BACKEND:-px4}" \
        --no-capture-on-startup \
        &
    MAIN_PID=$!
else
    # 默认/生产路径仍启动真实内嵌 YOLO；模型缺失时主进程必须失败。
    PYTHONPATH="$ROOT_DIR" python -m app.main \
        --with-yolo-api \
        --drone-backend "${DRONE_BACKEND:-px4}" \
        --no-capture-on-startup \
        &
    MAIN_PID=$!
fi

# 等待 YOLO 服务就绪
echo "等待 YOLO API 就绪..."
for i in $(seq 1 60); do
    if ! kill -0 "$MAIN_PID" 2>/dev/null; then
        echo "主处理流程在 YOLO 就绪前退出" >&2
        wait "$MAIN_PID" 2>/dev/null || true
        exit 1
    fi
    if [ -n "$YOLO_PID" ] && ! kill -0 "$YOLO_PID" 2>/dev/null; then
        echo "模拟 YOLO API 在就绪前退出" >&2
        wait "$YOLO_PID" 2>/dev/null || true
        exit 1
    fi
    if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health')" 2>/dev/null; then
        echo "YOLO API 已就绪"
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
if [ -n "$YOLO_PID" ]; then
    wait -n "$MAIN_PID" "$API_PID" "$YOLO_PID" 2>/dev/null || true
else
    wait -n "$MAIN_PID" "$API_PID" 2>/dev/null || true
fi
echo "某个服务已退出，停止所有服务..."
