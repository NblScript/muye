#!/usr/bin/env bash
# demo_scenario.sh — 一键演示场景库
# 用法: ./scripts/demo_scenario.sh <场景名>
# 场景: aphid_normal | planthopper_humid | wind_high | rag_down | px4_down
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO="${1:-}"
API_URL="${API_URL:-http://localhost:18000}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

usage() {
  echo "用法: $0 <场景名>"
  echo ""
  echo "可用场景:"
  echo "  aphid_normal      小麦蚜虫，正常天气，顺利施药"
  echo "  planthopper_humid 水稻稻飞虱，高湿天气，提示风险"
  echo "  wind_high         风速过高，AI 建议暂缓喷洒"
  echo "  rag_down          RAG 不可用，降级但流程不中断"
  echo "  px4_down          PX4 不可用，动画演示模式"
  exit 1
}

if [[ -z "$SCENARIO" ]]; then
  usage
fi

echo -e "${CYAN}========================================"
echo " 演示场景: $SCENARIO"
echo -e "========================================${NC}"

case "$SCENARIO" in
  aphid_normal)
    IMAGE="${ROOT_DIR}/data/samples/aphids_01.jpg"
    export QWEN_USE_MOCK="true"
    export QWEATHER_USE_MOCK="true"
    export QWEATHER_MOCK_TEMPERATURE="26"
    export QWEATHER_MOCK_HUMIDITY="58"
    export QWEATHER_MOCK_WIND_SPEED="3.3"
    export RAG_ENABLED="true"
    export MUYE_TAKEOFF_MODE="manual"
    echo -e "${GREEN}场景: 小麦蚜虫，正常天气，RAG 启用${NC}"
    ;;
  planthopper_humid)
    IMAGE="${ROOT_DIR}/data/samples/brown_planthopper_01.jpg"
    export QWEN_USE_MOCK="true"
    export QWEATHER_USE_MOCK="true"
    export QWEATHER_MOCK_TEMPERATURE="31"
    export QWEATHER_MOCK_HUMIDITY="89"
    export QWEATHER_MOCK_WIND_SPEED="1.2"
    export RAG_ENABLED="true"
    export MUYE_TAKEOFF_MODE="manual"
    echo -e "${YELLOW}场景: 水稻稻飞虱，高温高湿天气，RAG 启用${NC}"
    ;;
  wind_high)
    IMAGE="${ROOT_DIR}/data/samples/aphids_01.jpg"
    export QWEN_USE_MOCK="true"
    export QWEATHER_USE_MOCK="true"
    export QWEATHER_MOCK_TEMPERATURE="22"
    export QWEATHER_MOCK_HUMIDITY="45"
    export QWEATHER_MOCK_WIND_SPEED="7.8"
    export RAG_ENABLED="true"
    export MUYE_TAKEOFF_MODE="manual"
    echo -e "${RED}场景: 风速过高(7.8m/s)，AI 应建议暂缓施药${NC}"
    ;;
  rag_down)
    IMAGE="${ROOT_DIR}/data/samples/corn_borer_01.jpg"
    export QWEN_USE_MOCK="true"
    export QWEATHER_USE_MOCK="true"
    export RAG_ENABLED="false"
    export MUYE_TAKEOFF_MODE="manual"
    echo -e "${YELLOW}场景: RAG 关闭，系统降级决策但流程不中断${NC}"
    ;;
  px4_down)
    IMAGE="${ROOT_DIR}/data/samples/aphids_01.jpg"
    export QWEN_USE_MOCK="true"
    export QWEATHER_USE_MOCK="true"
    export RAG_ENABLED="true"
    export PX4_EXECUTION_MODE="animated_demo"
    export PX4_AUTO_START_ON_SPRAY="false"
    export MUYE_TAKEOFF_MODE="auto"
    echo -e "${YELLOW}场景: PX4 不启动，使用动画演示模式${NC}"
    ;;
  *)
    echo -e "${RED}未知场景: $SCENARIO${NC}"
    usage
    ;;
esac

if [[ ! -f "$IMAGE" ]]; then
  echo -e "${RED}样例图片不存在: $IMAGE${NC}"
  echo "请先运行 ./scripts/prepare.sh"
  exit 1
fi

echo ""
echo -e "环境变量已设置。现在可以："
echo ""
echo -e "  1. 启动系统:  ${CYAN}./scripts/demo.sh --takeoff manual${NC}"
echo -e "  2. 上传图片:  ${CYAN}curl -F 'file=@${IMAGE}' ${API_URL}/demo/upload-image${NC}"
echo -e "  3. 或直接在浏览器上传图片"
echo ""
echo -e "提示: 场景参数已 export 到当前 shell，demo.sh 会自动使用。"
