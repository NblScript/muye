<div align="center">

# 牧野智农 · Muye

### 从昆虫识别到变量喷洒的智能农业作业闭环

基于 YOLO、气象数据、多模型 AI 会诊与无人机任务规划，构建可运行、可追溯、可扩展的植保指挥系统。

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=111)
![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?style=flat-square&logo=typescript&logoColor=white)
![PX4](https://img.shields.io/badge/PX4-SITL-1B1F23?style=flat-square)
![Tests](https://img.shields.io/badge/tests-330_backend_%7C_28_frontend-success?style=flat-square)

[快速开始](#快速开始) · [系统架构](#系统架构) · [真实数据边界](#真实数据边界) · [项目文档](#项目文档)

</div>

## 项目是什么

牧野面向大田植保场景，将巡检图像接入、害虫识别、天气融合、AI 用药决策、安全合规检查、无人机变量喷洒和药效复检串成一条完整工作流。

项目首页不是行政区地图，而是一块与业务数据绑定的虚拟田地：展示 YOLO 昆虫相对热值、喷洒航线、无人机状态、气象条件、AI 决策与闭环评估。演示数据和真实检测数据具有明确来源标记，不在前端随机生成虫情。

## 核心能力

| 能力 | 当前实现 |
|---|---|
| 昆虫检测 | 本地 Ultralytics YOLO API，支持模型热切换、批量检测和结果校验 |
| 热力地图 | 检测框按图像尺寸归一化，生成田块相对热值网格与变量喷洒计划 |
| AI 决策 | Qwen 快速专家路径，或 Qwen / DeepSeek / Xiaomi 多智能体并行会诊与加权投票 |
| 知识增强 | LangChain + ChromaDB，融合农药目录、农业知识和历史决策案例 |
| 安全合规 | 用药规则检查、阻断原因、替代方案和自动/人工起飞策略 |
| 无人机执行 | PX4 SITL + MAVSDK；保留 DJI OSDK 后端接口与仿真适配 |
| 闭环评估 | 喷洒后复检、杀灭率评估与未达标任务重试 |
| 指挥大屏 | React + Three.js 虚拟田地、稳定热力层、航线、任务流程和历史追溯 |
| 数据存储 | SQLite 结构化任务数据 + JSONL 事件流 + Chroma 向量库 |
| 工程质量 | 领域模块化、API 数据校验、速率限制、SLO、前后端自动化测试 |

## 系统架构

```mermaid
flowchart LR
    A[巡检图片] --> B[YOLO 昆虫检测]
    B --> C[坐标归一化与热力网格]
    C --> D[天气与地块上下文]
    D --> E[DecisionRouter]
    E --> F[快速专家 / 多模型会诊]
    F --> G[农药安全合规]
    G --> H[变量喷洒任务规划]
    H --> I[PX4 / DJI 后端]
    I --> J[药效复检与闭环评估]

    B -. 实时状态 .-> K[React 指挥大屏]
    F -. 决策与证据 .-> K
    H -. 热力、航线、遥测 .-> K
    J -. 评估结果 .-> K
```

主要目录：

```text
muye/
├── app/                 # FastAPI 应用、路由与工作流编排
├── modules/
│   ├── detection/       # YOLO 服务、图像处理与数据采集
│   ├── decision/        # AI 决策、路由、多智能体、RAG 与合规检查
│   ├── drone/           # 密度网格、任务规划、PX4 与 DJI 后端
│   └── infra/           # SQLite、天气、事件总线与公共基础设施
├── frontend/            # React + TypeScript + Three.js 指挥大屏
├── models/              # API Schema 与农业数据模型
├── config/              # YOLO、无人机和模型配置
├── data/                # 示例图片、种子数据和运行时数据
├── scripts/             # 环境准备、演示、生产运行和质量检查
└── docs/                # 架构、产品、API、数据模型和农业知识文档
```

## 快速开始

### 1. 获取代码并安装依赖

```bash
git clone git@github.com:NblScript/muye.git
cd muye

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd frontend
npm ci
cd ..
```

### 2. 检查本地环境

```bash
./scripts/prepare.sh --check-only
```

### 3. 启动确定性演示

```bash
cp .env.demo.example .env.demo
./scripts/demo.sh
```

启动后访问：

- 指挥大屏：<http://localhost:5173/?demo=1>
- 后端 API：<http://127.0.0.1:18000>
- 健康检查：<http://127.0.0.1:18000/health>

演示模式使用固定的阶段数据、模拟天气和模拟 AI 决策，适合界面体验与流程讲解；它不会被标记为真实 YOLO 虫情。

## 接入真实服务

1. 将训练好的模型放到 `models/best.pt`，或在环境变量中指定其他模型路径。
2. 从 `.env.example` 创建 `.env.production`，配置 Qwen、和风天气、可选的 DeepSeek/Xiaomi 和 PX4 参数。
3. 启动 PX4 SITL，或配置支持的无人机后端。
4. 运行生产入口：

```bash
cp .env.example .env.production
./scripts/run.sh
```

常用服务端口：

| 服务 | 默认地址 |
|---|---|
| React 前端 | `127.0.0.1:5173` |
| FastAPI | `127.0.0.1:18000` |
| 本地 YOLO API | `127.0.0.1:8010` |
| PX4 MAVSDK | `udpin://0.0.0.0:14540` |

API 密钥只应写入本地环境文件，不要提交到仓库。生产运行参数和安全边界参见 [安全说明](SECURITY.md) 与 [演示流程规范](docs/product-specs/demo-pipeline.md)。

## 真实数据边界

为了避免“好看但不真实”，项目对热力数据做了以下约束：

- Ultralytics `xyxy` 检测框按像素处理，并携带原图宽高；归一化框使用明确的 `image_normalized` 坐标空间。
- 缺少图像尺寸的像素框不会进入真实密度网格，也不会被强行放到田块边缘。
- `density_grid[].density` 是本次任务内按检测置信度累计并归一化的**相对热值**，不是每亩虫口数或经济防治阈值。
- 当前 `image_frame_to_geofence_bbox` 投影假定图像覆盖田块且图像顶部对应北侧；没有正射影像或相机位姿时，不宣称虫点具有测绘级 GPS 精度。
- 演示种子通过 `density_metadata.is_simulated` 明确标记，前端同步显示数据来源。

详细契约参见 [数据模型](docs/references/data-model.md) 和 [前端热力规则](FRONTEND.md#昆虫热力图规则)。

## 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/live` | 进程存活检查 |
| `GET` | `/health` | 依赖与运行状态检查 |
| `GET` | `/workflow/state` | 当前聚合工作流 |
| `WS` | `/ws/enhanced-state` | 实时任务、遥测与热力状态 |
| `POST` | `/demo/upload-image` | 上传巡检图片并进入处理链 |
| `POST` | `/drone/confirm-takeoff` | 确认人工起飞 |
| `GET` | `/drone/density-map` | 查询任务密度网格与来源元数据 |

完整端点、请求体和响应示例见 [API 参考](docs/references/api.md)。

## 质量验证

```bash
# 竞赛关键路径
./scripts/check.sh

# 后端全量回归 + 前端测试/构建 + 文档校验
MUYE_FULL_CHECK=1 ./scripts/check.sh

# 前端静态检查
cd frontend && npm run lint
```

当前基线：后端 `330 passed / 1 skipped`，前端 `28 passed`，生产构建与文档一致性检查通过。

## 项目文档

| 文档 | 内容 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统边界、模块依赖和关键数据流 |
| [FRONTEND.md](FRONTEND.md) | 指挥大屏架构、实时状态和热力规则 |
| [docs/references/api.md](docs/references/api.md) | API 与 WebSocket 接口参考 |
| [docs/references/data-model.md](docs/references/data-model.md) | 检测框、密度网格和存储模型 |
| [docs/demo-script.md](docs/demo-script.md) | 演示操作说明 |
| [RELIABILITY.md](RELIABILITY.md) | 健康检查、SLO 和故障处理 |
| [SECURITY.md](SECURITY.md) | 密钥、网络与飞行安全约束 |
| [PLANS.md](PLANS.md) | 已完成能力与后续路线 |

## 当前阶段

牧野目前是一个可运行的智慧植保系统原型，适合竞赛展示、教学、算法联调和无人机任务流程验证。真实农田生产使用仍需要完成现场标定、正射影像或相机位姿接入、农艺阈值校准、药剂法规复核以及真实飞行安全认证。

项目会持续围绕真实虫情数据、精准变量喷洒、无人机硬件接入和可观测性演进。
