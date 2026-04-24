# 牧野（muye）— Codex 项目指令

## 项目定位
智慧农业害虫防治演示与原型系统：
害虫检测 → 气象采集 → AI决策 → 无人机执行 → 大屏展示

## 技术栈
- **后端**: Python 3.x + FastAPI + SQLAlchemy + LangChain + ChromaDB
- **前端**: React + Vite
- **AI**: YOLOv8 (检测) + Qwen (决策) + RAG (知识增强)
- **仿真**: PX4 SITL (无人机)

## 端口
| 服务 | 端口 | 启动命令 |
|------|------|----------|
| 主API | 8000 | `.venv/bin/uvicorn app.main:api_app --reload` |
| 无人机API | 8001 | `.venv/bin/uvicorn app.drone_api:app --port 8001` |
| YOLO API | 8002 | `.venv/bin/uvicorn app.yolo_api:app --port 8002` |
| 前端 | 5173 | `cd frontend && npm run dev` |

## 关键约定
1. **import**: `from modules.<domain>.<module>` 如 `from modules.decision.ai_decision`
2. **配置**: `app.config.get_config()` 统一获取配置
3. **事件总线**: `modules.infra.event_bus` 是跨域唯一通信通道
4. **存储**: `modules.infra.sqlite_store` 是唯一持久层

## 领域边界
| 领域 | 职责 | 关键模块 |
|------|------|----------|
| detection | 害虫检测 + 图像处理 | modules/detection/ |
| decision | AI决策 + RAG知识增强 | modules/decision/ |
| drone | 无人机控制 + 任务规划 | modules/drone/ |
| infra | 事件总线 + 存储 + 天气 | modules/infra/ |

## 开发流程
1. 先读 `docs/reference/ARCHITECTURE.md` 理解全局
2. 改代码前先跑测试: `.venv/bin/python -m pytest -q tests/`
3. 改完必须跑全量测试
4. 新功能必须写测试
5. 更新相关文档（如有API变更）

## 测试
```bash
.venv/bin/python -m pytest -q tests/          # 全量测试
.venv/bin/python -m pytest tests/test_drone.py -v  # 单模块
```

## 安全
- 无硬编码 API KEY（使用 get_config()）
- 上传文件有大小和格式校验
- 无人机指令有安全限制和紧急中断
- SQL 使用 ORM，禁止拼接
