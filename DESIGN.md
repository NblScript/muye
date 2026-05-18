# DESIGN.md — 牧野通用设计指南

## 命名约定

### Python（后端）

| 类型 | 规则 | 示例 |
|------|------|------|
| 模块文件 | snake_case | `ai_decision.py`, `event_bus.py` |
| 类名 | PascalCase | `DecisionEngine`, `FileEventBus` |
| 函数/方法 | snake_case | `get_weather()`, `process_image()` |
| 常量 | UPPER_SNAKE_CASE | `DATA_DIR`, `MAX_RETRY_COUNT` |
| 私有方法 | 前缀 `_` | `_validate_input()`, `_build_context()` |
| 测试文件 | `test_` 前缀 | `test_ai_decision.py` |
| 测试方法 | `test_` 前缀 | `test_decision_with_valid_input()` |

### TypeScript（前端）

| 类型 | 规则 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `FieldMap.tsx`, `WorkflowPanel.tsx` |
| Hook 文件 | `use` 前缀 | `useSimMapState.ts` |
| API 文件 | camelCase | `simMap.ts`, `workflow.ts` |
| 类型文件 | camelCase + `.types.ts` | `dashboard.types.ts` |
| CSS 文件 | kebab-case | `dashboard.css`, `px4-viewer.css` |
| 接口 | PascalCase，无 `I` 前缀 | `SimMapState`, `WorkflowEvent` |

## 错误处理

### 后端原则

1. **边界处校验**：所有外部输入（API 请求、文件上传、LLM 输出）必须在入口处校验。
2. **结构化错误**：使用 FastAPI 的 `HTTPException`，返回 JSON 格式错误。
3. **降级优于崩溃**：RAG 检索失败 → 发出警告事件 + 使用无上下文决策。天气 API 超时 → 使用缓存数据。
4. **日志伴随错误**：每个错误必须有对应的结构化日志（JSON 格式，含 `level`, `message`, `context`）。
5. **不吞异常**：禁止空 `except` 块。捕获异常后必须记录或重新抛出。

### 前端原则

1. **ErrorBoundary**：每个页面级组件包裹 `ErrorBoundary`。
2. **API 错误**：统一在 `api/client.ts` 中处理，显示 Toast 通知。
3. **加载状态**：所有异步操作必须有 loading 状态指示。

## 日志规范

```python
# 结构化日志格式
import logging
logger = logging.getLogger(__name__)

logger.info("决策完成", extra={
    "request_id": request_id,
    "pest_type": pest_type,
    "confidence": 0.95
})
```

- **级别**：`DEBUG`（开发）→ `INFO`（正常流程）→ `WARNING`（降级）→ `ERROR`（失败）→ `CRITICAL`（系统不可用）
- **存储**：`data/logs/` 目录，按服务分类
- **格式**：JSON 结构化，包含时间戳、级别、消息、上下文

## 配置管理

- **配置文件**：`config/` 目录（`.env`, `.json`, `.yaml`）
- **敏感信息**：`config/api_keys.env`（不入 Git），模板在 `.env.example`
- **加载方式**：`app/config.py` 统一加载，通过 `app/config_types.py` 定义类型
- **运行时配置**：`config/drone_config.json`（无人机参数）、`config/yolo_config.yaml`（检测参数）

## 代码组织

### 后端包结构

```
app/
├── routes/        # HTTP 路由层（薄层，只做参数解析和响应格式化）
├── services/      # 应用服务层（编排业务流程）
├── config.py      # 配置加载
├── config_types.py # 配置类型定义
├── deps.py        # 依赖注入（全局单例）
└── main.py        # FastAPI 应用入口

modules/
├── detection/     # 检测域（独立服务）
├── decision/      # 决策域（含 RAG 子系统）
├── drone/         # 无人机域
└── infra/         # 基础设施（事件总线、存储、天气、工具）
```

### 前端包结构

```
frontend/src/
├── api/           # HTTP 客户端和 API 调用
├── components/    # UI 组件（按功能分组）
├── hooks/         # 自定义 Hooks
├── pages/         # 页面级组件
├── layouts/       # 布局组件
├── types/         # TypeScript 类型定义
├── styles/        # 全局样式
└── utils/         # 工具函数
```

## 测试策略

- **单元测试**：覆盖核心业务逻辑（66+ 测试用例）
- **测试位置**：`tests/` 目录，文件名 `test_<模块名>.py`
- **Mock 策略**：仅 Mock 外部服务（Qwen API、和风天气、PX4 SITL），不 Mock 内部模块
- **测试数据**：使用 `data/samples/` 和 `data/seeds/` 中的种子数据
- **运行方式**：`pytest tests/ -v`

## 文档规范

- **代码注释**：仅在 WHY 非显而易见时添加（隐藏约束、变通方案）
- **Docstring**：公共 API 必须有简短 docstring（一行描述 + 参数说明）
- **README**：每个子目录可有 README.md 说明该目录用途
- **设计文档**：存放在 `docs/design-docs/`，必须在 `index.md` 中注册
