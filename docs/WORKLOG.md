# Worklog

## Current Session Summary

本轮围绕“统一旧前端与新前端功能，并删除旧前端”展开，已经完成主线迁移；随后又补做了一轮结构与演示链路收口。

- React 前端已补齐原 Streamlit 面板的核心能力：
  - 图片上传
  - 原图 / 识别图对照
  - 害虫识别摘要
  - 天气信息
  - 千问建议与安全提示
  - 任务历史检索
  - 运行模式展示
  - 实时工作流与事件日志
- 旧 `app.py` 已删除，仓库当前只保留 `frontend/` 作为前端实现。
- 已继续优化演示链路一致性：
  - Vite 默认代理目标统一到 `127.0.0.1:18000`
  - `start_demo.sh` / `start_px4_visual_demo.sh` 已支持 `--api-port`
  - `start_competition_mode.sh` / `start_all_in_one.sh` 已透传 `--api-port`
  - README 与前端结构说明已按当前真实结构重写

## Backend/API Changes

- `app/main.py -> api_app` 已补齐 React 前端所需接口：
  - `GET /dashboard/context`
  - `GET /workflow/history`
  - `POST /demo/upload-image`
  - `POST /demo/reset-events`
  - `GET /tasks/{request_id}/original-image`
  - `GET /tasks/{request_id}/annotated-image`
- `GET /workflow/state` 已扩展，最新任务会额外返回：
  - `image_path`
  - `detections`
  - `weather`
  - `error`

## Frontend Changes

- `frontend/src/pages/Dashboard.tsx`
  - 改为统一数据入口，集中拉取工作流、历史和运行模式
  - 增加顶部操作条与摘要指标
  - 增加图片对照、识别摘要、天气/决策详情、任务历史面板
- `frontend/src/components/map/FieldMap.tsx`
  - 改为纯展示组件，由父层注入地图状态
  - 新增当前任务航线/覆盖区叠加与任务摘要浮层
- `frontend/src/components/workflow/WorkflowPanel.tsx`
  - 改为消费父层传入的共享工作流状态，不再独立轮询
- `frontend/src/hooks/useSimMapState.ts`
  - 抽出地图 WebSocket / polling 双通道状态管理

## Runtime / Script Changes

- `scripts/start_demo.sh`
  - 已改为同时启动：
    - `app/main.py` 主流程
    - `uvicorn app.main:api_app`
    - `Vite` React 前端
- `scripts/start_px4_visual_demo.sh`
  - 已改为同时启动：
    - `app/main.py` 主流程
    - `uvicorn app.main:api_app`
    - `Vite` React 前端
- `scripts/start_competition_mode.sh`
  - 文案已同步为前端通用表述
- `scripts/start_all_in_one.sh`
  - 文案已同步为 React 前端表述

## Dependency / Docs

- `requirements.txt`
  - 移除 `streamlit` / `streamlit-autorefresh`
  - 新增 `Pillow`
- 已同步更新：
  - `README.md`
  - `PROJECT_MEMORY.md`
  - `CHANGELOG.md`
- 已补充前端性能优化文档：
  - `README.md` 新增“前端构建与缓存策略”
  - 记录 `manualChunks` 拆分为 `vendor-react`、`vendor-ui`、`vendor-map`、`vendor-misc`
  - 记录内容 hash 只解决“按内容失效”，真正长效缓存仍依赖部署层为 `dist/assets/*` 配置长期缓存头
- 已补生产部署示例：
  - 新增 `deploy/nginx.conf`
  - 为 `dist/assets/*` 配置一年长缓存
  - 为 `index.html` 配置 `no-cache`
  - 为 `/api/` 配置反向代理，并支持 SPA history 路由回退
  - 默认按比赛现场优先口径提供 HTTP 版本，降低证书依赖
  - 新增 `deploy/muye_backend.service`
  - 用 `systemd` 托管 `uvicorn app.main:api_app`
  - 明确当前后端走单进程部署，避免内存态实时数据在多 worker 下不一致
  - 为 `/api/` 代理补上 WebSocket、长超时和上传体积限制
  - 为 `systemd` 服务补上 `EnvironmentFile`、`.venv/bin/uvicorn` 和 `data/` 目录权限提示
- 已补后端生产级修复：
  - 上传接口增加真实图片解码校验和 `10MB` 限制
  - `/health` 增加 SQLite、`data/` 可写性和 embedded YOLO 存活检查
  - `workflow/history.total` 改为 SQLite + event bus 合并后的真实总数
  - `workflow/history` 改为合并后再应用 `limit`
  - `/demo/reset-events` 改为必须 `confirm=true`，并同步清空 SQLite 任务运行态数据

## Verification

- 已通过 `frontend` 构建验证：
  - `npm run build`
  - 当前构建产物已确认输出带 hash 的 vendor 文件，例如：
    - `vendor-map-ulfx7UOW.js`
    - `vendor-ui-Cdj0xTTn.js`
- 已通过 Python 语法检查：
  - `python -m py_compile app/main.py`
- 已通过 `tests/test_main.py`：
  - `25 passed in 1.18s`
- 已通过全量测试：
  - `66 passed in 5.23s`
- 已补结构文档收口：
  - `README.md` 项目结构、目录导读、启动说明
  - `frontend/PROJECT_STRUCTURE.md`
  - `PROJECT_MEMORY.md`
- 曾尝试做 FastAPI 最小接口探测，但当前命令会话没有正常收敛，因此没有把那次探测结果记为最终验证结论。

## Next Handoff Point

下一轮如果继续推进，优先做这两件事：

1. 补充新 API 的后端测试，尤其是：
   - 上传图片
   - 历史检索
   - 原图 / 识别图接口
2. 在真实演示环境走一遍：
   - `./scripts/start_demo.sh`
   - 或 `./scripts/start_px4_visual_demo.sh --sample-image IP000000042.jpg`
