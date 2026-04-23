# ARCHITECTURE.md — 牧野系统架构总览

## 系统定位

牧野（muye）是一个端到端的智慧农业害虫防治演示与原型系统，涵盖：
害虫检测 → 气象采集 → AI 决策 → 无人机执行 → 大屏展示

## 架构分层

```
┌──────────────────────────────────────────────┐
│              frontend/ (React + Vite)         │
│         指挥大屏 · 地图 · 任务面板            │
├──────────────────────────────────────────────┤
│              app/ (FastAPI 应用层)             │
│   routes/ → services/ → deps.py → config.py  │
├──────────────────────────────────────────────┤
│            modules/ (核心业务逻辑)             │
│  decision/  drone/  detection/  infra/        │
├──────────────────────────────────────────────┤
│            models/ (数据模型)                  │
│           Pydantic schema 定义                │
├──────────────────────────────────────────────┤
│    data/ (SQLite)  config/ (.env/.yaml)       │
│           持久化层 + 配置层                    │
└──────────────────────────────────────────────┘
```

## 领域模型

### 1. detection（检测域）
- **入口**：`app/yolo_api.py` — 独立 FastAPI 服务
- **核心**：`modules/detection/` — YOLO 推理 + 图像处理 + 数据采集
- **数据流**：上传图片 → YOLO 推理 → 标注图片 + 害虫列表

### 2. decision（决策域）
- **入口**：通过 `app/services/workflow_service.py` 调用
- **核心**：`modules/decision/` — AI 决策 + RAG 知识增强
- **数据流**：害虫列表 + 天气数据 → RAG 检索 → Qwen API → 用药/农事建议 JSON
- **RAG 链路**：用户查询 → QwenEmbeddings → ChromaDB 检索 → 上下文注入

### 3. drone（无人机域）
- **入口**：`app/drone_api.py` — 独立 FastAPI 服务
- **核心**：`modules/drone/` — 控制器 + 任务规划 + PX4 仿真
- **数据流**：决策结果 → 任务规划 → 航线生成 → PX4 SITL 执行 / 虚拟模拟

### 4. infra（基础设施域）
- **核心**：`modules/infra/` — 事件总线 + SQLite 存储 + 天气集成 + 公共工具
- **事件总线**：`EventBus` 是跨域通信的唯一通道，解耦检测→决策→执行
- **天气**：`weather.py` 封装和风天气 API

## 数据流总图

```
用户上传图片
    │
    ▼
YOLO 检测 (detection)
    │ 害虫列表
    ▼
天气采集 (infra/weather)
    │ 害虫 + 天气
    ▼
RAG 检索 (decision/rag) ──→ 农药知识库 (ChromaDB)
    │ 增强上下文
    ▼
Qwen 决策 (decision/ai_decision)
    │ 用药建议 + 农事建议
    ▼
任务规划 (drone/mission_planner)
    │ 航线参数
    ▼
无人机执行 (drone/controller → PX4/SITL)
    │
    ▼
大屏展示 (frontend)
```

## 外部依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| 和风天气 | 实时气象数据 | QWEATHER_API_KEY |
| 千问 API | AI 结构化决策 | DASHSCOPE_API_KEY |
| DashScope | RAG 文本向量化 | DASHSCOPE_API_KEY |
| PX4 SITL | 无人机仿真 | 自动启动 |
| YOLO 模型 | 害虫图像识别 | 本地 ONNX 权重 |

## 部署拓扑

```
端口 8000: app/main.py (主 API + 静态文件)
端口 8001: app/drone_api.py (无人机 API)
端口 8002: app/yolo_api.py (YOLO API)
端口 5173: frontend/ (Vite 开发服务器)
```

## 设计决策记录

| 决策 | 理由 | 替代方案 |
|------|------|----------|
| SQLite 为主存储 | 零运维，单文件可移植 | PostgreSQL（过度工程） |
| 事件总线解耦 | 领域间松耦合 | 直接函数调用（紧耦合） |
| RAG 降级策略 | 检索失败不中断主流程 | 严格依赖（单点故障） |
| 领域子包分组 | 按业务边界组织代码 | 按技术层分组（controller/service） |
| jsonschema 校验 | 强制 LLM 输出结构 | 纯 prompt 约束（不可靠） |
