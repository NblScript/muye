# SECURITY.md — 牧野安全规范

## API 密钥管理

### 存储规则

| 规则 | 说明 |
|------|------|
| 密钥文件 | `config/api_keys.env`（不入 Git） |
| 模板文件 | `.env.example`（入 Git，含占位符） |
| Git 忽略 | `.gitignore` 已配置忽略 `config/api_keys.env` |
| 硬编码禁止 | 代码中不得出现任何密钥明文 |

### 当前密钥

| 密钥 | 用途 | 配置项 |
|------|------|--------|
| 和风天气 API Key | 气象数据 | `QWEATHER_API_KEY` |
| DashScope API Key | Qwen 决策 + RAG 向量化 | `DASHSCOPE_API_KEY` |
| YOLO API 端点 | 检测服务 | `YOLO_API_URL` |

### 密钥轮换

1. 更新 `config/api_keys.env` 中的对应值
2. 重启相关服务
3. 验证功能正常

## 输入验证

### API 输入

- **文件上传**：限制文件类型（`.jpg`, `.png`, `.bmp`）、大小（< 10MB）
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

### 生产部署

- **Nginx 反向代理**：`deploy/nginx.conf`
- **无 CORS 开放**：前端和 API 同源
- **无认证**：竞赛演示系统，无需用户认证
- **速率限制**：待实现（TD-002）

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
cd frontend && npm audit
```

### 更新策略

- 定期检查依赖安全公告
- 重大漏洞立即修复
- 非紧急更新在竞赛间歇期进行

## 数据安全

### 敏感数据

| 数据 | 存储 | 保护措施 |
|------|------|----------|
| API 密钥 | `config/api_keys.env` | Git 忽略 |
| 用户上传图片 | `data/images/` | 无持久化需求 |
| 事件日志 | `data/logs/demo_events.jsonl` | 无敏感信息 |
| SQLite 数据库 | `data/muye.db` | 本地存储，无远程访问 |

### 竞赛场景注意

- 演示前清空 `data/logs/demo_events.jsonl`（避免上次演示的残留数据）
- 确认 `config/api_keys.env` 中的密钥有效
- 不在演示中暴露真实的 API 密钥
