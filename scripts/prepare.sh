#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
SAMPLES_DIR="${ROOT_DIR}/data/samples"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1" >&2; }

usage() {
    cat <<'EOF'
Usage: ./scripts/prepare.sh [options]

环境准备脚本：检查依赖、准备展示图片、构建 RAG 知识库。
比赛前跑一次即可。

Options:
  --images-only    仅准备展示图片
  --check-only     仅检查环境
  --rag            构建 RAG 知识库
  --production     额外检查生产模式依赖
  -h, --help       显示帮助信息
EOF
}

IMAGES_ONLY="false"
CHECK_ONLY="false"
BUILD_RAG="false"
PRODUCTION="false"

read_env_value() {
    local file="$1"
    local key="$2"
    "$PYTHON_BIN" - "$file" "$key" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = ""
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, current = line.split("=", 1)
    if name.strip() != key:
        continue
    value = current.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    break
print(value)
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --images-only) IMAGES_ONLY="true"; shift ;;
        --check-only)  CHECK_ONLY="true"; shift ;;
        --rag)         BUILD_RAG="true"; shift ;;
        --production)  PRODUCTION="true"; shift ;;
        -h|--help)     usage; exit 0 ;;
        *)             echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

echo "=========================================="
echo "  牧野环境准备"
echo "=========================================="
echo ""

# ── 1. 检查 Python 虚拟环境 ──
if [[ ! -x "$PYTHON_BIN" ]]; then
    print_error "Python 虚拟环境不存在: $PYTHON_BIN"
    echo "  请先创建: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi
print_success "Python 解释器: $("$PYTHON_BIN" --version 2>&1)"

if [[ "$IMAGES_ONLY" == "true" ]]; then
    # 仅准备图片，跳过其他检查
    true
else
    # ── 2. 检查 Python 依赖 ──
    MISSING=$("$PYTHON_BIN" -c "
deps = ['fastapi', 'uvicorn', 'httpx', 'PIL', 'yaml', 'dotenv']
missing = []
for d in deps:
    try:
        __import__(d)
    except:
        missing.append(d)
print(','.join(missing))
" 2>/dev/null || echo "check_failed")

    if [[ "$MISSING" == "check_failed" ]]; then
        print_error "Python 依赖检查失败"
    elif [[ -z "$MISSING" ]]; then
        print_success "Python 核心依赖"
    else
        print_error "缺少 Python 依赖: $MISSING"
        echo "  请运行: .venv/bin/pip install -r requirements.txt"
        exit 1
    fi

    # ── 3. 检查 Node.js ──
    if command -v node >/dev/null 2>&1; then
        print_success "Node.js: $(node --version)"
    else
        print_error "Node.js 未安装"
        exit 1
    fi

    if command -v npm >/dev/null 2>&1; then
        print_success "npm: $(npm --version)"
    else
        print_error "npm 未安装"
        exit 1
    fi

    # ── 4. 检查前端依赖 ──
    if [[ -d "${ROOT_DIR}/frontend/node_modules" ]]; then
        print_success "前端 node_modules"
    else
        print_warn "前端依赖未安装"
        echo "  运行: cd frontend && npm install"
    fi

    # ── 5. 检查默认 YOLO 模型 ──
    # 生产模式稍后按 .env.production 中的自定义路径检查，避免误报。
    if [[ "$PRODUCTION" != "true" ]]; then
        if [[ -f "${ROOT_DIR}/models/best.pt" ]]; then
            MODEL_SIZE=$(du -sh "${ROOT_DIR}/models/best.pt" | cut -f1)
            print_success "YOLO 模型 ($MODEL_SIZE)"
        else
            print_warn "YOLO 模型不存在，将使用 mock 模式"
        fi
    fi

    # ── 5b. 生产模式额外检查 ──
    if [[ "$PRODUCTION" == "true" ]]; then
        echo ""
        print_info "生产模式额外检查..."

        PRODUCTION_ENV="${ROOT_DIR}/.env.production"
        if [[ -f "$PRODUCTION_ENV" ]]; then
            print_success ".env.production 已配置"
        else
            print_error "缺少 .env.production"
            echo "  请复制模板并填入真实配置: cp .env.production.example .env.production"
            exit 1
        fi

        # 引号包裹的空值也视为未配置。
        if [[ -n "$(read_env_value "$PRODUCTION_ENV" "QWEN_API_KEY")" ]]; then
            print_success "Qwen API Key 已配置"
        else
            print_warn "Qwen API Key 未配置，请在启动真实决策前补齐"
        fi

        if [[ -n "$(read_env_value "$PRODUCTION_ENV" "QWEATHER_API_KEY")" ]]; then
            print_success "和风天气 API Key 已配置"
        else
            print_warn "和风天气 API Key 未配置，请在启动真实天气前补齐"
        fi

        # 检查本机 PX4 SITL；连接真机时不要求本机存在 px4 命令。
        if command -v px4 >/dev/null 2>&1; then
            print_success "PX4 SITL: $(px4 --version 2>&1 | head -1)"
        else
            print_warn "PX4 SITL 命令未找到；连接真机时可忽略此项"
        fi

        # 检查配置指定的 YOLO 模型（生产模式必须）
        CONFIGURED_MODEL="$(read_env_value "$PRODUCTION_ENV" "YOLO_LOCAL_MODEL_PATH")"
        CONFIGURED_MODEL="${CONFIGURED_MODEL:-models/best.pt}"
        if [[ "$CONFIGURED_MODEL" = /* ]]; then
            MODEL_PATH="$CONFIGURED_MODEL"
        else
            MODEL_PATH="${ROOT_DIR}/${CONFIGURED_MODEL}"
        fi
        if [[ -f "$MODEL_PATH" ]]; then
            print_success "YOLO 模型已就绪: $CONFIGURED_MODEL"
        else
            print_error "生产模式需要 YOLO 模型: $CONFIGURED_MODEL"
            exit 1
        fi

        # 检查 run.sh 是否可执行
        if [[ -x "${ROOT_DIR}/scripts/run.sh" ]]; then
            print_success "run.sh 生产入口脚本"
        else
            print_error "scripts/run.sh 不存在或不可执行"
            exit 1
        fi
    fi
fi

# ── 6. 准备展示图片 ──
if [[ "$CHECK_ONLY" != "true" ]]; then
    echo ""
    print_info "准备展示图片..."

    mkdir -p "${ROOT_DIR}/data/images" "$SAMPLES_DIR"

    # IP102 数据集路径
    IP102_VAL_DIR="${IP102_VAL_DIR:-/mnt/c/muye/PestYOLO-main/PestYOLO-main/IP102_YOLOv8/val/images}"

    if find "$SAMPLES_DIR" -maxdepth 1 \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) -print -quit 2>/dev/null | grep -q .; then
        COUNT=$(find "$SAMPLES_DIR" -maxdepth 1 \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) | wc -l)
        print_success "已有 $COUNT 张展示图片"
    elif [[ -d "$IP102_VAL_DIR" ]]; then
        # IP102 文件名前缀使用 0 起始类别编号，官方 classes.txt 使用 1 起始编号。
        # 这里按“前缀 + 1”后的官方类别命名，避免历史上的错一类问题。
        DEMO_SELECTIONS=(
            "IP000000000.jpg rice_leaf_roller_01.jpg 水稻稻纵卷叶螟"
            "IP007000004.jpg brown_planthopper_01.jpg 水稻褐飞虱"
            "IP004000001.jpg yellow_rice_borer_01.jpg 水稻三化螟"
            "IP023000056.jpg army_worm_01.jpg 黏虫"
            "IP024000016.jpg aphids_01.jpg 蚜虫"
            "IP022000006.jpg corn_borer_01.jpg 玉米螟虫"
            "IP036000049.jpg beet_fly_01.jpg 甜菜潜叶蝇"
            "IP015000008.jpg mole_cricket_01.jpg 蝼蛄"
        )
        copied=0
        for entry in "${DEMO_SELECTIONS[@]}"; do
            src_name=$(echo "$entry" | awk '{print $1}')
            dst_name=$(echo "$entry" | awk '{print $2}')
            desc=$(echo "$entry" | awk '{print $3}')
            if [[ -f "$IP102_VAL_DIR/$src_name" ]]; then
                cp "$IP102_VAL_DIR/$src_name" "$SAMPLES_DIR/$dst_name"
                print_success "$desc"
                copied=$((copied + 1))
            fi
        done
        print_success "已复制 $copied 张真实害虫图片"
    else
        print_warn "IP102 数据集未找到: $IP102_VAL_DIR"
        echo "  请将害虫图片放入: $SAMPLES_DIR"
        echo "  或设置环境变量: export IP102_VAL_DIR=/path/to/val/images"
    fi
fi

# ── 7. 构建 RAG 知识库（可选）──
if [[ "$BUILD_RAG" == "true" ]]; then
    echo ""
    print_info "构建 RAG 知识库..."
    PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" "${ROOT_DIR}/scripts/build_rag_knowledge.py" --all
    print_success "RAG 知识库构建完成"
fi

echo ""
echo "=========================================="
echo "  环境准备完成"
echo "=========================================="
echo ""
echo "启动展示: ./scripts/demo.sh"
echo ""
