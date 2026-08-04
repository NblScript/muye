# 演示流程规格

> 牧野系统竞赛演示的完整流程定义。

## 状态
- [x] 已批准

## 最后更新
2026-05-18

---

## 概述

演示流程从图片输入开始，经过检测、决策、执行，最终在大屏上展示完整结果。

## 流程阶段

### 阶段 1：环境准备

**脚本**：`./scripts/prepare.sh`

**动作**：
1. 检查 Python 依赖
2. 检查 Node.js 依赖
3. 复制 IP102 真实害虫图片到 `data/samples/`
4. 构建 RAG 知识库（`scripts/build_rag_knowledge.py`）

**输出**：环境就绪，演示图片可用

**固定样例评测集**：`python scripts/eval_fixed_set.py --output data/eval/latest_report.md`

- 样例清单：`data/eval/manifest.json`
- 覆盖：蚜虫、褐飞虱、稻纵卷叶螟变量喷洒，以及空检测、缺少坐标、非法围栏降级
- 校验：图片 SHA-256、完整 8×10 热力网格、航线、喷洒速率表和规划模式
- 输出：带逐场景哈希与 PASS/FAIL 的 Markdown 报告；标注边界与 IP102 来源见 `data/eval/README.md`

### 阶段 2：系统启动

**脚本**：`./scripts/demo.sh`

**动作**：
1. 启动主 API（端口 18000）
2. 启动 YOLO API（端口 8010）
3. 启动前端（端口 5173）
4. 注入演示图片

**参数**：
- `--mode virtual|px4`（默认 virtual）
- `--takeoff manual|auto`（默认 manual）
- `--api-port 18000`
- `--frontend-port 5173`
- `--interval 5`（图片注入间隔秒数）

**预设场景**：`./scripts/demo_scenario.sh <场景名>` 可预设环境变量和样例图片：

| 场景 | 说明 |
|------|------|
| `aphid_normal` | 小麦蚜虫，正常天气 |
| `planthopper_humid` | 水稻稻飞虱，高温高湿 |
| `wind_high` | 风速过高，AI 建议暂缓 |
| `rag_down` | RAG 不可用，降级处理 |
| `px4_down` | PX4 不可用，动画演示 |

**现场诊断**：`./scripts/demo_doctor.sh` 可在演示中随时运行，聚合 `/health`、`/slo`、`/workflow/state`、最近事件流和系统错误日志，输出 `PASS / WARN / FAIL`。

### 阶段 3：图片上传与检测

**触发**：用户通过前端上传图片，或 demo.sh 自动注入

**流程**：
1. 图片上传到 `data/images/`
2. YOLO API 执行推理
3. 返回害虫列表（类型 + 置信度 + 边界框）
4. 生成标注图片

**事件**：`detection_completed`

### 阶段 4：气象采集

**流程**：
1. 调用和风天气 API 获取实时气象数据
2. 缓存天气快照

**降级**：API 不可用时使用缓存数据

**事件**：`weather_collected`

### 阶段 5：AI 决策

**流程**：
1. 构建决策上下文（害虫 + 天气 + 农田信息）
2. RAG 检索相关农药知识
3. 调用 Qwen API 生成结构化决策
4. jsonschema 校验输出

**输出**：
- 推荐农药名称
- 用量
- 决策理由
- RAG 检索上下文

**降级**：RAG 失败时使用无上下文决策

**事件**：`decision_completed`

### 阶段 6：起飞确认（manual 模式）

**流程**：
1. 发布 `pending_confirmation` 事件
2. 前端显示"确认起飞"按钮
3. 等待用户点击确认
4. `POST /drone/confirm-takeoff` 触发继续

**auto 模式**：跳过此阶段，自动继续

### 阶段 7：无人机执行

**流程**：
1. 根据决策生成航线参数
2. 计算飞行路径（含喷洒参数）
3. PX4 SITL 执行飞行任务
4. 实时更新飞行状态

**输出**：
- 飞行轨迹
- 喷洒记录
- 任务完成状态

**事件**：`mission_started`, `mission_progress`, `mission_completed`

### 阶段 8：大屏展示

**展示内容**：
- 害虫检测结果（标注图片 + 害虫列表）
- 气象数据卡片
- AI 决策详情（农药、用量、理由）
- 无人机飞行轨迹（SVG 地图）
- 任务状态面板（电池、进度、遥测数据）
- 工作流管线步骤指示器
- Settings 页系统预检与当前生效配置（起飞模式、无人机后端、PX4 模式、AI/RAG/Router/多智能体、YOLO 模型）

## 时间线（典型演示）

| 时间 | 阶段 | 时长 |
|------|------|------|
| 0:00 | 环境准备（提前完成） | - |
| 0:00 | 系统启动 | 30s |
| 0:30 | 图片上传 | 5s |
| 0:35 | 害虫检测 | 3-5s |
| 0:40 | 气象采集 | 2s |
| 0:42 | AI 决策 | 5-10s |
| 0:52 | 讲解决策过程 | 2-3min |
| 3:52 | 确认起飞 | 5s |
| 3:57 | 无人机执行 | 2-5min |
| 8:57 | 展示结果 | 1-2min |
| **总计** | | **~10min** |

## 故障处理

| 故障 | 处理方式 |
|------|----------|
| YOLO 推理失败 | 重试 1 次；演示模式可使用明确标记的模拟种子，生产模式不得伪装为真实检测 |
| 天气 API 超时 | 使用缓存数据 |
| Qwen API 失败 | 重试 1 次，失败则显示错误 |
| RAG 检索失败 | 降级到无上下文决策 |
| PX4 连接失败 | 生产任务明确失败并停止执行；演示必须显式选择 `animated_demo` |
| WebSocket 断开 | 自动重连 + HTTP 轮询降级 |

## 生产模式

除演示入口 `demo.sh` 外，系统还提供生产入口 `run.sh`，用于 24 小时自动巡检作业。

### 启动方式

```bash
cp .env.production.example .env.production
./scripts/prepare.sh --production  # 环境准备 + 生产检查
./scripts/run.sh                   # 启动 24h 自动巡检
```

### 与演示模式的差异

| 配置项 | demo.sh（演示） | run.sh（生产） |
|--------|----------------|---------------|
| 起飞模式 | `manual`（前端确认） | `auto`（自动起飞） |
| 图片采集 | `--no-capture-on-startup`（手动注入） | 启动即采集，每 24h 循环 |
| PX4 模式 | `animated_demo` | `real`（MAVSDK，可连接 SITL 或真机） |
| 任务闭环 | 单次喷洒 | 自动重试至杀灭率 ≥ 90% |
| 前端 | 必须启动 | 可选（`--no-frontend` 无头运行） |
| AI/天气 | mock 模式 | 真实 API（需配置 `.env.production`） |
| RAG 索引 | 不自动索引 | 完成任务自动索引到 RAG |

### run.sh 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--api-port <port>` | `18000` | API 端口 |
| `--frontend-port <port>` | `5173` | 前端端口 |
| `--no-frontend` | - | 不启动前端（无头运行） |
| `--skip-precheck` | - | 跳过环境检查 |
| `--allow-default-env` | - | 仅用于本地联调；缺少生产配置时显式启用 mock 与动画模式 |

### 生产配置

生产模式需在 `.env.production` 中配置真实 API Key：

```bash
MUYE_TAKEOFF_MODE=auto
MUYE_EVALUATION_AUTO_RETRY=true
MUYE_EVALUATION_KILL_RATE_THRESHOLD=0.9
PX4_EXECUTION_MODE=real
# QWEN_API_KEY=<your-key>
# QWEATHER_API_KEY=<your-key>

# 无人机后端选择
# DRONE_BACKEND=px4    # MAVSDK 执行链路，可连接 PX4 SITL 或真机（默认）
# DRONE_BACKEND=dji_osdk  # DJI OSDK 后端；当前仅完成仿真适配

# DJI OSDK 配置（仅 DRONE_BACKEND=dji_osdk 时需要）
# DJI_OSDK_EXECUTION_MODE=osdk_real
# DJI_OSDK_SERIAL_PORT=/dev/ttyACM0
```

`PX4_EXECUTION_MODE` 只接受 `animated_demo` 或 `real`。生产入口默认使用 `real`，未知值会直接报错，不会静默降级为动画。

### DJI OSDK 当前边界

系统已经保留面向 Matrice M300 / M350 / 30T 等机型的 DJI OSDK 后端接口，但当前 `osdk_real` 尚未实现串口/OSDK 握手、遥测和任务下发。设置 `DJI_OSDK_EXECUTION_MODE=osdk_real` 只会记录警告并继续使用仿真实现，不代表真机已连接。

当前联调应使用 `DRONE_BACKEND=dji_osdk` 和 `DJI_OSDK_EXECUTION_MODE=osdk_sim`。真正接入硬件前需要完成：

1. 串口或 UDP 通信与 OSDK 握手。
2. 真机遥测读取、任务上传、状态回调和异常中止。
3. 机型适配、权限配置、地理围栏和人工接管验证。
4. 硬件在环测试与现场飞行安全验收。
