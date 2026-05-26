# 技术债务追踪器

> 追踪项目中的技术债务项。每项必须有 ID、优先级、状态和负责人。

## 活跃项

### TD-001: 前端测试覆盖率提升

- **优先级**：中
- **状态**：已完成
- **完成日期**：2026-05-26
- **描述**：前端组件缺少单元测试，核心组件（Dashboard, FieldMap, WorkflowPanel）需要测试覆盖
- **验收标准**：
  - [x] Dashboard.tsx 有基本渲染测试
  - [x] FieldMap.tsx 有交互测试
  - [x] WorkflowPanel.tsx 有状态切换测试
  - [x] Hooks 有独立测试

### TD-002: API 速率限制

- **优先级**：低
- **状态**：已完成
- **完成日期**：2026-05-26
- **描述**：API 端点无速率限制，可能导致资源耗尽
- **验收标准**：
  - [x] 关键端点（/demo/upload-image, /workflow/state）有速率限制
  - [x] 超限时返回 429 状态码
  - [x] 可通过配置调整限制参数

### TD-003: DJI OSDK 无人机对接

- **优先级**：中
- **状态**：已完成（Phase 1 + Phase 2）
- **完成日期**：2026-05-26
- **描述**：对接 DJI 行业级无人机（Matrice/M300/M350），通过 OSDK 直连机载计算机
- **验收标准**：
  - [x] DroneBackend ABC 抽象基类
  - [x] 后端注册表 + resolve_backend
  - [x] PX4Backend 薄包装
  - [x] DJIOSDKBackend（osdk_sim 仿真 + osdk_real 接口）
  - [x] controller.py 改用后端抽象层
  - [x] DJI API 端点（status/telemetry/connect/disconnect）
  - [x] 28 个后端测试全部通过

### TD-004: SLO 监控

- **优先级**：中
- **状态**：已完成
- **完成日期**：2026-05-26
- **描述**：进程内 SLO 指标采集，无需外部依赖
- **验收标准**：
  - [x] 4 项 SLO 追踪（API 成功率、管线完成率、WebSocket 稳定性、系统可用性）
  - [x] 滑动窗口 60 秒
  - [x] /slo 端点暴露指标快照
  - [x] 7 个 SLO 测试全部通过

## 已完成项

### TD-000: 目录结构重组

- **优先级**：高
- **状态**：已完成
- **完成日期**：2026-04-23
- **描述**：将 modules/ 重组为领域子包（decision/, drone/, detection/, infra/）
- **结果**：已按计划完成，所有导入路径已更新

---

## 添加新项

使用以下模板：

```markdown
### TD-XXX: <标题>

- **优先级**：高/中/低
- **状态**：待处理/进行中
- **创建日期**：YYYY-MM-DD
- **描述**：<问题描述>
- **验收标准**：
  - [ ] <标准1>
  - [ ] <标准2>
```
