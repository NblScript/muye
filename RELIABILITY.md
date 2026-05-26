# RELIABILITY.md — 牧野可靠性要求

## SLO 定义

### 演示场景 SLO

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| 系统可用性（演示期间） | 99.9% | 演示全程无崩溃 |
| API 成功率 | 99% | 非 5xx 响应比例 |
| 管线完成率 | 95% | 从图片上传到任务完成的比例 |
| WebSocket 连接稳定性 | 99% | 连接断开比例 |

### 单次演示容错

- 允许单次 API 重试（最多 2 次）
- 允许 WebSocket 短暂断开（自动重连）
- 不允许管线中断（检测→决策→执行必须完整）

## 降级策略

### RAG 降级

```
RAG 检索可用 → 使用知识增强的决策
RAG 检索失败 → 发出 WARNING 事件 → 使用无上下文的 Qwen 决策
```

- **触发条件**：ChromaDB 不可用、Embedding 超时、检索结果为空
- **行为**：日志记录 + EventBus 发出 `rag_degraded` 事件
- **影响**：决策质量可能下降，但管线不中断

### 天气降级

```
天气 API 可用 → 使用实时气象数据
天气 API 不可用 → 使用缓存数据或默认值
```

- **触发条件**：和风天气 API 超时或返回错误
- **行为**：使用 `data/` 中的缓存天气数据
- **影响**：决策可能不够精确，但管线不中断

### PX4 降级

```
PX4 SITL 可用 → 真实仿真飞行
PX4 SITL 不可用 → 使用动画演示模式
```

- **触发条件**：PX4 进程未启动或连接失败
- **行为**：切换到 `animated_demo` 模式
- **影响**：视觉效果略有差异，但演示流程完整

### DJI OSDK 降级

```
DJI OSDK 真机连接可用 → 真实 DJI 无人机执行
DJI OSDK 真机不可用 → 使用 osdk_sim 仿真模式
PX4 也可用 → 回退到 PX4 后端
```

- **触发条件**：`execution.backend` 设为 `dji_osdk` 但无硬件
- **行为**：`osdk_sim` 模式用 GPS 坐标插值模拟飞行，接口与真机一致
- **影响**：无物理飞行，但任务流程完整可演示

## 故障恢复

### 自动恢复

| 故障 | 恢复方式 |
|------|----------|
| WebSocket 断开 | 自动重连（指数退避） |
| API 请求超时 | 自动重试（最多 2 次） |
| EventBus 文件损坏 | 重新创建事件文件 |
| SQLite 锁冲突 | 重试写入（WAL 模式） |

### 手动恢复

| 故障 | 恢复方式 |
|------|----------|
| 系统崩溃 | `./scripts/demo.sh` 重新启动 |
| 数据库损坏 | 从 `data/seeds/` 重新导入 |
| ChromaDB 损坏 | `python scripts/build_rag_knowledge.py` 重建 |
| PX4 仿真挂起 | 重启 PX4 SITL 进程 |

## 监控

### SLO 指标

系统内置进程内 SLO 指标采集（`app/slo.py`），无需外部依赖。通过滑动窗口（60 秒）追踪 4 项 SLO：

| SLO | 目标 | 采集点 |
|-----|------|--------|
| API 成功率 | 99% | 每次请求后记录状态码 |
| 管线完成率 | 95% | pipeline_start/complete/error 事件 |
| WebSocket 稳定性 | 99% | ws_connect/ws_disconnect 事件 |
| 系统可用性 | 99.9% | 基于请求成功率 |

```bash
# SLO 指标快照
curl http://localhost:18000/slo
```

### API 限流

滑动窗口 per-IP 限流中间件（`app/middleware.py`），默认每分钟 120 次请求。超限返回 429。

配置项：`config/app_config.json` → `api_rate_limit_per_minute`

### 健康检查

```bash
# API 健康检查
curl http://localhost:18000/health

# YOLO 服务健康检查
curl http://localhost:8010/health
```

### 日志监控

```bash
# 查看系统日志
tail -f data/logs/system.log

# 查看 PX4 日志
tail -f data/logs/px4.log

# 查看事件流
tail -f data/logs/demo_events.jsonl | jq .
```

## 演示前检查清单

- [ ] 运行 `./scripts/precheck.sh` 检查环境
- [ ] 运行 `./scripts/prepare.sh` 准备数据
- [ ] 确认 API 端口（18000, 8010）未被占用
- [ ] 确认 PX4 SITL 可启动（如使用 px4 模式）
- [ ] 确认网络连接（如需实时天气）
- [ ] 确认演示图片已准备（`data/samples/`）
- [ ] 运行 `./scripts/demo.sh --takeoff manual` 启动系统
- [ ] 访问 http://localhost:5173 确认前端正常
