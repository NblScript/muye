# SECURITY.md — 牧野安全规范

## API 密钥管理

### 存储规则

| 规则 | 说明 |
|------|------|
| 开发密钥文件 | `config/api_keys.env`（不入 Git） |
| 演示环境 | `.env.demo`，从 `.env.demo.example` 创建 |
| 生产环境 | `.env.production`，从 `.env.production.example` 创建 |
| Git 忽略 | `.gitignore` 已忽略真实密钥文件，只提交模板 |
| 硬编码禁止 | 代码中不得出现任何密钥明文 |

### 当前密钥

| 密钥 | 用途 | 配置项 |
|------|------|--------|
| 和风天气 API Key | 气象数据 | `QWEATHER_API_KEY` |
| Qwen API Key | Qwen 决策 + RAG 向量化 | `QWEN_API_KEY` |
| DeepSeek API Key | 多智能体会诊 | `DEEPSEEK_API_KEY` |
| Xiaomi API Key | 多智能体会诊 | `XIAOMI_API_KEY` |
| YOLO API 端点 | 检测服务 | `YOLO_API_URL` |

### 密钥轮换

1. 更新实际使用的本地环境文件中的对应值
2. 重启相关服务
3. 验证功能正常

## 输入验证

### API 输入

- **文件上传**：限制文件类型（`.jpg`, `.png`, `.bmp`）、大小（主 API < 10MB / YOLO API < 20MB）
- **查询参数**：类型校验 + 范围限制
- **请求体**：Pydantic 模型自动校验

### LLM 输出

- **jsonschema 校验**：所有 Qwen API 返回必须通过 schema 校验
- **字段白名单**：只接受预期的字段名
- **值范围检查**：数值字段必须在合理范围内

### 文件路径

- **路径遍历防护**：所有文件操作使用 `os.path.join()` + 路径规范化
- **目录限制**：文件操作限制在 `data/` 目录内

## 网络安全

### 端口暴露

| 端口 | 服务 | 暴露范围 |
|------|------|----------|
| 18000 | 主 API | 本地（开发）/ Nginx 反向代理（生产） |
| 8010 | YOLO API | 仅本地 |
| 5173 | 前端 | 本地（开发）/ Nginx 反向代理（生产） |

隔离容器冒烟栈另使用回环地址端口 `5174` / `18080` / `18010`。其 YOLO 端点是显式模拟服务，必须由 `MUYE_CONTAINER_SMOKE=true` 启用，不得改用于生产、精度评测或对外服务。真实模型验收栈使用回环地址 `5175` / `18081`，不暴露 YOLO 端口，且使用独立数据卷自动清理。

### 生产部署

- **Nginx 反向代理**：Docker Compose 使用 `docker/nginx.conf`，前端与 API 同源
- **默认网络边界**：脚本与 Compose 模式下 API、前端和 YOLO 默认绑定回环地址
- **鉴权边界**：当前主 API 没有完整用户认证，只适合受控本地网络；暴露到公网前必须增加认证、TLS 和访问审计
- **无人机安全**：生产默认禁止 force-arm；真实执行必须经过硬件、地理围栏和现场安全验收
- **速率限制**：已实现，滑动窗口 per-IP 限流（默认 120 次/分钟），见 `app/middleware.py`

## 依赖安全

### Python 依赖

```bash
# 检查已知漏洞
pip-audit -r requirements.txt

# 固定版本
pip freeze > requirements-lock.txt
```

### 前端依赖

```bash
cd frontend && npm audit --omit=dev --audit-level=high
```

CI 会阻断生产依赖中的 high/critical 公告。当前三个静态页面使用浏览器 History API 导航，不引入完整 SSR/RSC 路由运行时；测试与构建工具链公告另行评估，不能用 `--force` 破坏性升级掩盖。

### 更新策略

- 定期检查依赖安全公告
- 重大漏洞立即修复
- 非紧急更新在竞赛间歇期进行

## 数据安全

### 敏感数据

| 数据 | 存储 | 保护措施 |
|------|------|----------|
| API 密钥 | `.env.production` / `config/api_keys.env` | Git 忽略、禁止写入日志 |
| 用户上传图片 | `data/images/` | 本地持久化，部署方负责保留周期与脱敏 |
| 事件日志 | `data/logs/events.jsonl` | 本地轮转，禁止写入密钥和不必要的个人信息 |
| SQLite 数据库 | `data/muye.db` | 本地存储，无远程访问 |

### 竞赛场景注意

- 演示前通过系统清理入口处理 `data/logs/events.jsonl`，避免直接删除正在使用的日志文件
- 确认 `config/api_keys.env` 中的密钥有效
- 不在演示中暴露真实的 API 密钥
