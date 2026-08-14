# PLANS.md — 牧野高层级路线图

> 本文件只保留路线图骨架与长期愿景。
> 执行计划的详细状态见 [docs/exec-plans/index.md](docs/exec-plans/index.md)，
> 工程质量项见 [技术债务追踪器](docs/exec-plans/tech-debt-tracker.md)。

## 已完成（里程碑）

- [x] 核心管线搭建（检测→决策→执行→展示）
- [x] 领域模块重构（按业务边界分包）
- [x] LangChain RAG 知识增强
- [x] 手动/自动起飞模式
- [x] 前端从 Streamlit 迁移到 React
- [x] SQLite v1.1.1 迁移
- [x] 演示脚本统一（prepare.sh + demo.sh）
- [x] 昆虫热力图产品化（巡检/快照数据层、筛选 API、历史分析、变量喷洒追溯、固定回归、CI 与容器冒烟）
- [x] 多智能体会诊、农药安全合规推理链、闭环效果评估与任务生命周期
- [x] DJI OSDK 后端抽象与仿真（实机通信待硬件）
- [x] CI 三链路全绿（后端回归、前端多视口验收、容器端到端冒烟）

## 当前焦点

- 昆虫热力产品化收尾与真实模型容器验收 → [执行计划](docs/exec-plans/2026-08-04-insect-heatmap-productization.md) · [Phase 0 真实模型验收](docs/exec-plans/2026-08-13-real-model-acceptance-phase0.md)
- 演示可靠性维护与工程质量 → [技术债务追踪器](docs/exec-plans/tech-debt-tracker.md)

## 长期愿景

- 多农田支持（当前固定单个活动田地，不接行政区地图）
- 实时视频流检测（当前为静态图片上传）
- DJI OSDK Matrice 实机通信与硬件验收（等待凭证与硬件）
- 基于绝对虫口密度的经济阈值判断（需采样面积、相机位姿或正射影像标定）
