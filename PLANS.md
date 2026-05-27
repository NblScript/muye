# PLANS.md — 牧野高层级路线图

## 已完成

- [x] 核心管线搭建（检测→决策→执行→展示）
- [x] 领域模块重构（按业务边界分包）
- [x] LangChain RAG 知识增强
- [x] 手动/自动起飞模式
- [x] 前端从 Streamlit 迁移到 React
- [x] SQLite v1.1.1 迁移
- [x] 演示脚本统一（prepare.sh + demo.sh）

## 进行中

| 优先级 | 项目 | 状态 |
|--------|------|------|
| 中 | DJI Cloud API 消费级无人机对接（Phase 3） | 待处理 |

## 已完成（近期）

- [x] 前端测试覆盖率提升（60 个测试，Vitest + React Testing Library）
- [x] API 速率限制（滑动窗口 per-IP 限流，默认 120 次/分钟）
- [x] SLO 监控（进程内指标采集，4 项 SLO 追踪）
- [x] DJI OSDK 行业级无人机对接 Phase 1 + Phase 2（后端抽象层 + 仿真模式）
- [x] 多智能体会诊（Qwen/DeepSeek/Xiaomi 三模型投票 + DecisionRouter）
- [x] 农药安全合规推理链（5 项检查 + 证据链 + 执行策略）
- [x] 闭环效果评估 + 任务生命周期（多轮喷洒至杀灭率达标）
- [x] 密度热力图 + 变量喷洒可视化

详见 [技术债务追踪器](docs/exec-plans/tech-debt-tracker.md)

## 长期愿景

- 多农田支持（当前仅单个演示农田）
- ~~真实无人机硬件对接~~ — Phase 1+2 已完成（DJI OSDK），Phase 3（Cloud API 消费级）待处理
- 实时视频流检测（当前为静态图片上传）
- ~~多模型支持~~ — 已实现（3 模型多智能体会诊 + YOLO 模型热切换）
