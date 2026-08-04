# QUALITY_SCORE.md — 牧野质量评分标准

## 测试覆盖率

### 当前状态

- 后端基线：372 passed / 1 skipped（54 个 `test_*.py` 文件）
- 前端基线：33 个 Vitest passed（10 个测试文件）+ 6 个 Playwright 布局场景
- 前端生产依赖：`npm audit --omit=dev --audit-level=high` 为 0 vulnerabilities，并由 CI 持续检查
- 统一入口：`MUYE_FULL_CHECK=1 ./scripts/check.sh`
- 固定数据回归：6 个场景，锁定图片、8×10 热力网格、航线、喷洒速率和安全降级结果
- 持续集成：`.github/workflows/ci.yml` 并行执行后端/数据/文档、前端单元/真浏览器布局验收和隔离容器端到端冒烟

### 标准

| 指标 | 目标 | 当前 |
|------|------|------|
| 核心模块覆盖 | 100% | 通过 |
| API 端点覆盖 | 100% | 通过 |
| 边界情况覆盖 | 关键路径 | 持续补充 |
| 前端测试 | 核心组件 + 多视口 | 已覆盖首页数据映射、热力稳定性、航线、导航和 3 种桌面可用区域 |

### 测试规范

- **命名**：`test_<模块名>.py`，方法名 `test_<场景>_<预期结果>()`
- **隔离**：每个测试独立，不依赖执行顺序
- **Mock**：仅 Mock 外部服务和硬件边界，固定输入必须产生确定性输出
- **断言**：使用明确的断言，包含失败消息
- **固定基线**：`data/eval/manifest.json` 的图片和计算结果均校验 SHA-256；算法有意变化后必须人工审阅再更新，不允许测试自动覆盖

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
# 后端全量、前端测试/构建、文档校验
MUYE_FULL_CHECK=1 ./scripts/check.sh

# 前端静态检查
cd frontend && npm run lint

# 真实 Chromium 多视口验收（先执行 npm run build）
cd frontend && npm run test:e2e
```

## 文档新鲜度

### 规则

1. **代码变更必须同步更新文档**：修改 API 端点 → 更新 `docs/references/api.md`
2. **数据库 schema 变更必须更新**：修改迁移或表结构 → 更新 `docs/generated/db-schema.md`
3. **架构变更必须更新**：新增模块 → 更新 `ARCHITECTURE.md` 和 `AGENTS.md`
4. **热力语义变更必须更新**：修改坐标、归一化或喷洒分档 → 更新昆虫热力产品规格和数据模型参考

### 验证

- `scripts/verify_docs.py` 校验索引、链接、API 路由和废弃引用
- AGENTS.md 中的链接必须指向存在的文件
- 变更日志中的“当前”描述不得与已删除实现或旧端口冲突
- GitHub CI 使用 Python 3.11、Node.js 22，与 Docker 构建环境保持一致；权限限制为只读仓库内容
- 容器冒烟只允许在 `MUYE_CONTAINER_SMOKE=true` 下启动固定检测器，使用独立数据卷并在结束后清理
- 真实模型容器验收不得设置 `MUYE_CONTAINER_SMOKE`，必须验证模型存在、真实检测结果、`image_pixel` 坐标及原图尺寸，并使用独立数据卷
- Playwright 在 1366×768、1920×1080 和 1536×864（1920 在 125% 缩放的等效可用区域）下运行，CI 使用单 worker 并保留截图/trace

## 性能基准

| 指标 | 目标 |
|------|------|
| API 响应时间（健康检查） | < 100ms |
| API 响应时间（工作流状态） | < 500ms |
| YOLO 推理时间（单张图片） | < 5s |
| AI 决策时间（含 RAG） | < 15s |
| 前端首屏加载 | < 3s |
| WebSocket 消息延迟 | < 200ms |
