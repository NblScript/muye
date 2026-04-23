# Muye 项目目录重构

## 目标
将项目目录从分散的结构重组为按领域划分的清晰结构，参考 OpenAI Harness Engineering 实践。

## 任务

### 1. modules/ 内部按领域分组
创建以下子目录并移动文件：

```
modules/
├── decision/              # 决策域
│   ├── __init__.py
│   ├── ai_decision.py     # 从 modules/ai_decision.py 移动
│   ├── decision_context.py # 从 modules/decision_context.py 移动
│   └── rag/               # 从 modules/rag/ 移动
├── drone/                 # 无人机域
│   ├── __init__.py
│   ├── controller.py      # 从 modules/drone_controller.py 重命名移动
│   ├── mission_planner.py  # 从 modules/mission_planner.py 移动
│   ├── px4_simulator.py    # 从 modules/px4_simulator.py 移动
│   └── virtual_api.py     # 从 modules/virtual_drone_api.py 重命名移动
├── detection/             # 检测域
│   ├── __init__.py
│   ├── image_processor.py # 从 modules/image_processor.py 移动
│   ├── local_yolo_api.py # 从 modules/local_yolo_api.py 移动
│   └── data_collector.py  # 从 modules/data_collector.py 移动
└── infra/                 # 基础设施
    ├── __init__.py
    ├── common.py          # 从 modules/common.py 移动
    ├── event_bus.py       # 从 modules/event_bus.py 移动
    ├── sqlite_store.py    # 从 modules/sqlite_store.py 移动
    └── weather.py         # 从 modules/weather_integration.py 重命名移动
```

### 2. 合并 routes/ + services/ + core/ → app/
创建 app/ 目录：

```
app/
├── __init__.py
├── main.py               # 从根目录 main.py 移动并适配
├── routes/               # 从 routes/ 移动
│   ├── __init__.py
│   ├── health.py
│   ├── workflow.py
│   ├── dashboard.py
│   ├── demo.py
│   ├── tasks.py
│   └── sim.py
├── services/             # 从 services/ 移动
│   ├── __init__.py
│   ├── workflow_service.py
│   └── map_simulator.py
└── deps.py               # 从 core/deps.py 移动
```

### 3. 入口文件移动
- 根目录 `drone_api.py` → `app/drone_api.py`
- 根目录 `yolo_api.py` → `app/yolo_api.py`
- 更新其中的 import 路径

### 4. 更新所有 import 路径
关键映射：
- `from modules.ai_decision` → `from modules.decision.ai_decision`
- `from modules.decision_context` → `from modules.decision.decision_context`
- `from modules.rag` → `from modules.decision.rag`
- `from modules.drone_controller` → `from modules.drone.controller`
- `from modules.mission_planner` → `from modules.drone.mission_planner`
- `from modules.px4_simulator` → `from modules.drone.px4_simulator`
- `from modules.virtual_drone_api` → `from modules.drone.virtual_api`
- `from modules.image_processor` → `from modules.detection.image_processor`
- `from modules.local_yolo_api` → `from modules.detection.local_yolo_api`
- `from modules.data_collector` → `from modules.detection.data_collector`
- `from modules.common` → `from modules.infra.common`
- `from modules.event_bus` → `from modules.infra.event_bus`
- `from modules.sqlite_store` → `from modules.infra.sqlite_store`
- `from modules.weather_integration` → `from modules.infra.weather`
- `from core.deps` → `from app.deps`
- `from core.config` → `from app.config` (如果有的话)
- `from routes.*` → `from app.routes.*`
- `from services.*` → `from app.services.*`

### 5. 删除空目录
删除重构后空的目录：
- `core/` (已合并到 app/)
- `routes/` (已移动到 app/routes/)
- `services/` (已移动到 app/services/)
- 旧的 `modules/` 散落文件

### 6. 根目录入口脚本
在根目录创建启动脚本：
```
scripts/run_api.sh        # 运行 python -m app.main
scripts/run_drone_api.sh  # 运行 python -m app.drone_api
scripts/run_yolo_api.sh   # 运行 python -m app.yolo_api
```

## 验证
重构完成后运行测试：
```bash
.venv/bin/python -m pytest -q tests/
```

确保所有测试通过。

## 注意
- 不要修改 tests/ 目录结构，只更新其 import 路径
- 不要修改 config/、data/、frontend/、models/、scripts/ 目录
- 保留 requirements.txt、.env.example 等根目录文件
