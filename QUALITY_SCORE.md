# QUALITY_SCORE.md — 模块质量评分

> 每个模块的质量评分，帮助 AI Agent 快速识别风险区域。

## 评分标准

| 等级 | 测试覆盖 | 文档 | 复杂度 | 风险 |
|------|---------|------|--------|------|
| A | >80% | 完整 | 低 | 低 |
| B | 50-80% | 基本 | 中 | 中 |
| C | <50% | 缺失 | 高 | 高 |
| D | 无测试 | 无 | 极高 | 极高 |

## 模块评分

### app/（应用层）

| 模块 | 等级 | 测试 | 说明 |
|------|------|------|------|
| app/main.py | B | 间接 | 通过 E2E 测试覆盖，缺少单元测试 |
| app/routes/ | B | 间接 | 通过集成测试覆盖 |
| app/services/ | B | 间接 | workflow_service 有集成测试 |
| app/deps.py | A | 有 | 简单依赖注入 |
| app/config.py | A | 有 | 配置解析 |

### modules/decision/（决策域）

| 模块 | 等级 | 测试 | 说明 |
|------|------|------|------|
| ai_decision.py | B | 有 | jsonschema 校验 + API mock |
| decision_context.py | B | 有 | test_decision_context.py |
| rag/embeddings.py | B | 有 | test_rag_embeddings.py |
| rag/vectorstore.py | B | 有 | ChromaDB 交互 |
| rag/retriever.py | B | 有 | test_rag_retriever.py |
| rag/knowledge_loader.py | B | 有 | test_knowledge_loader.py |

### modules/drone/（无人机域）

| 模块 | 等级 | 测试 | 说明 |
|------|------|------|------|
| controller.py | B | 有 | 无人机状态管理测试 |
| mission_planner.py | B | 有 | 航线计算测试 |
| px4_simulator.py | C | 间接 | 需要 SITL 环境 |
| virtual_api.py | A | 有 | test_virtual_drone_api.py 完整 |

### modules/detection/（检测域）

| 模块 | 等级 | 测试 | 说明 |
|------|------|------|------|
| image_processor.py | B | 有 | 图像处理测试 |
| local_yolo_api.py | B | 有 | YOLO API 测试 |
| data_collector.py | C | 间接 | 通过集成测试覆盖 |

### modules/infra/（基础设施域）

| 模块 | 等级 | 测试 | 说明 |
|------|------|------|------|
| common.py | A | 有 | 工具函数测试 |
| event_bus.py | A | 有 | 事件总线完整测试 |
| sqlite_store.py | A | 有 | SQLite CRUD 完整测试 |
| weather.py | B | 有 | 天气 API mock 测试 |

## 整体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 测试覆盖 | B+ | 145 个测试，核心链路全覆盖 |
| 文档完整 | B | 架构/设计/API 文档齐全，模块内文档待补充 |
| 代码规范 | B | 类型注解 + jsonschema，部分模块缺少 docstring |
| 可维护性 | A- | 领域分组清晰，依赖方向正确 |
| 部署简易 | A | SQLite 零运维，单命令启动 |

## 待改进项（按优先级）

1. **px4_simulator.py** — 需要 SITL 集成测试
2. **data_collector.py** — 缺少独立单元测试
3. **app/main.py** — 缺少启动流程的单元测试
4. **sqlite_store.py** — 1786 行/47 方法，建议按功能拆分 mixin
