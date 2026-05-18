# QUALITY_SCORE.md — 牧野质量评分标准

## 测试覆盖率

### 当前状态

- 后端测试：66+ 测试用例，覆盖所有核心模块
- 测试文件：`tests/` 目录，21 个测试文件

### 标准

| 指标 | 目标 | 当前 |
|------|------|------|
| 核心模块覆盖 | 100% | 通过 |
| API 端点覆盖 | 100% | 通过 |
| 边界情况覆盖 | 关键路径 | 部分 |
| 前端测试 | 核心组件 | 待提升（TD-001） |

### 测试规范

- **命名**：`test_<模块名>.py`，方法名 `test_<场景>_<预期结果>()`
- **隔离**：每个测试独立，不依赖执行顺序
- **Mock**：仅 Mock 外部服务（Qwen API、和风天气、PX4 SITL）
- **断言**：使用明确的断言，包含失败消息

## 代码质量

### 检查清单

- [ ] 无空 `except` 块
- [ ] 无未使用的 import
- [ ] 函数长度不超过 50 行
- [ ] 类长度不超过 300 行
- [ ] 所有公共 API 有 docstring
- [ ] 无硬编码的密钥或端点
- [ ] 错误处理遵循 [DESIGN.md](DESIGN.md) 规范

### Linting

```bash
# Python
ruff check app/ modules/ tests/

# TypeScript
cd frontend && npm run lint
```

## 文档新鲜度

### 规则

1. **代码变更必须同步更新文档**：修改 API 端点 → 更新 `docs/references/api.md`
2. **数据库 schema 变更必须更新**：修改模型 → 更新 `docs/generated/db-schema.md`
3. **架构变更必须更新**：新增模块 → 更新 `ARCHITECTURE.md` 和 `AGENTS.md`

### 验证

- CI 中检查文档最后修改时间
- 超过 30 天未更新的文档标记为"可能过时"
- AGENTS.md 中的链接必须指向存在的文件

## 性能基准

| 指标 | 目标 |
|------|------|
| API 响应时间（健康检查） | < 100ms |
| API 响应时间（工作流状态） | < 500ms |
| YOLO 推理时间（单张图片） | < 5s |
| AI 决策时间（含 RAG） | < 15s |
| 前端首屏加载 | < 3s |
| WebSocket 消息延迟 | < 200ms |
