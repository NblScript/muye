# 牧野智能农业害虫防治系统

`muye` 是一个基于 Python 的智能农业害虫防治项目，集成了无人机图像采集、YOLO 害虫识别、和风天气数据整合、千问 AI 决策和精准喷洒控制。项目采用异步任务流、模块化设计，并对外部 API 响应进行严格校验。

## 项目结构

```text
muye/
├── .env.example
├── app.py
├── config/
│   ├── api_keys.env
│   ├── drone_config.json
│   └── yolo_config.yaml
├── data/
│   ├── images/
│   └── logs/
├── models/
│   └── README.md
├── modules/
│   ├── __init__.py
│   ├── ai_decision.py
│   ├── common.py
│   ├── data_collector.py
│   ├── drone_controller.py
│   ├── event_bus.py
│   ├── image_processor.py
│   ├── local_yolo_api.py
│   ├── virtual_drone_api.py
│   └── weather_integration.py
├── drone_api.py
├── tests/
│   ├── test_ai_decision.py
│   ├── test_event_bus.py
│   ├── test_image_processor.py
│   ├── test_local_yolo_api.py
│   ├── test_main.py
│   ├── test_virtual_drone_api.py
│   └── test_weather_integration.py
├── main.py
├── requirements.txt
├── yolo_api.py
└── README.md
```

## 功能说明

1. `data_collector.py`
   - 每 24 小时自动触发无人机采图。
   - 使用 `watchdog` 实时监听 `data/images/` 新图片。
   - 图片命名格式为 `YYYYMMDD-HHMMSS.jpg`。

2. `image_processor.py`
   - 异步调用 YOLO API。
   - 校验害虫类型、置信度、位置信息。
   - 过滤低于置信度阈值的检测结果。
   - 已默认接到本地 YOLO `best.pt` API。

3. `local_yolo_api.py` + `yolo_api.py`
   - 将本地 `models/best.pt` 封装为 HTTP API。
   - 暴露 `/health` 和 `/detect` 两个接口。
   - 支持 Bearer Token 鉴权、IP 白名单、速率限制和批量推理。

4. `weather_integration.py`
   - 先调用和风天气城市查询接口获取 `Location ID`。
   - 再调用和风天气实况天气接口获取天气数据。
   - 将返回字段统一映射为项目内部格式：温度、湿度、风向、风力、天气概况。

5. `ai_decision.py`
   - 将害虫检测和天气信息整合成结构化文本。
   - 调用千问 API 输出 JSON 决策。
   - 使用 `jsonschema` 强制校验返回结构。

6. `drone_controller.py`
   - 校验气象限制、地理围栏和飞行控制参数。
   - 支持虚拟无人机 API 执行与状态轮询。

7. `main.py`
   - 使用 `asyncio` 组织采集、识别、决策、执行全流程。
   - 通过异步队列避免并发场景下的资源竞争。
   - 支持一键同时启动本地 YOLO API、虚拟无人机 API 和主系统。

8. `event_bus.py`
   - 采用 `JSONL` 文件作为简单事件总线。
   - 后端关键节点会写入带时间戳、阶段和状态的事件。
   - Streamlit 面板通过轮询同一份事件文件实现跨进程展示。

9. `app.py`
   - 基于 Streamlit 的演示面板。
   - 支持上传图片、原图/识别图对比、天气/决策卡片、无人机进度和实时日志。

10. `virtual_drone_api.py` + `drone_api.py`
   - 提供虚拟无人机任务创建与任务状态查询接口。
   - 自动模拟排队、起飞、前往作业区、喷洒、返航和完成状态。

## 安装依赖

```bash
cd /home/qingking/muye
pip install -r requirements.txt
```

如果你已经安装了项目内虚拟环境，也可以直接使用：

```bash
cd /home/qingking/muye
. .venv/bin/activate
```

## 环境变量配置

项目提供两个环境配置参考文件：

- [`.env.example`](/home/qingking/muye/.env.example)：模板文件
- [`api_keys.env`](/home/qingking/muye/config/api_keys.env)：当前项目运行时读取的配置文件

和风天气开发者 Key 获取方式：

1. 访问 `https://console.qweather.com`
2. 注册并登录和风天气开发者平台
3. 创建项目并申请 API Key
4. 将 Key 写入 `QWEATHER_API_KEY`

推荐配置示例：

```env
YOLO_API_URL="http://127.0.0.1:8010/detect"
YOLO_API_KEY="muye-local-yolo-token"
YOLO_LOCAL_MODEL_PATH="models/best.pt"
YOLO_LOCAL_HOST="127.0.0.1"
YOLO_LOCAL_PORT="8010"

QWEN_API_URL="https://your-qwen-compatible-endpoint/v1/chat/completions"
QWEN_API_KEY="replace-with-your-qwen-key"
QWEN_MODEL="qwen-max"

QWEATHER_API_KEY="在此填入你的和风天气API_KEY"
QWEATHER_GEO_URL="https://geoapi.qweather.com/v2/city/lookup"
QWEATHER_WEATHER_URL="https://devapi.qweather.com/v7/weather/now"

DRONE_API_URL="http://127.0.0.1:9010/missions"
DRONE_API_KEY="virtual-drone-token"
VIRTUAL_DRONE_HOST="127.0.0.1"
VIRTUAL_DRONE_PORT="9010"
VIRTUAL_DRONE_ALLOWED_IPS="127.0.0.1,::1"
SERVICE_CLIENT_IP="127.0.0.1"
```

说明：

- 请将训练好的权重文件放到 `models/best.pt`。
- `drone_config.json` 中的 `field.weather_location` 或 `field.location.city` 用于和风天气地点查询，建议填写城市名，例如 `上海`。
- 本地 YOLO API 默认读取 `YOLO_LOCAL_MODEL_PATH`，主流程默认调用 `YOLO_API_URL`。
- `YOLO_API_KEY` 同时用于主项目访问本地 YOLO API 的 Bearer Token。
- `drone_config.json` 中 `simulate_capture=true` 时，系统会自动生成一张最小 JPEG 作为采图结果，便于本地联调。
- `execution.simulate_only=true` 时，无人机喷洒任务只做本地模拟，不访问虚拟无人机 API。
- 使用 `--with-virtual-drone-api` 或 `--with-demo-stack` 时，主程序会自动接管无人机接口地址并关闭本地模拟模式。

## 运行方式

推荐一键启动本地 YOLO API、虚拟无人机 API 与主系统：

```bash
cd /home/qingking/muye
python main.py --with-demo-stack
```

执行一次完整链路后退出：

```bash
cd /home/qingking/muye
python main.py --with-demo-stack --once
```

如果你希望分开启动，也可以先启动本地 YOLO API：

```bash
cd /home/qingking/muye
python yolo_api.py
```

再启动虚拟无人机 API：

```bash
cd /home/qingking/muye
python drone_api.py
```

可选检查：

```bash
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:9010/health
```

再启动主系统：

```bash
cd /home/qingking/muye
python main.py
```

## 可视化演示面板

后端与前端通过同一个事件文件连接：

- 事件总线文件：`data/logs/demo_events.jsonl`
- 图片投喂目录：`data/images/`

推荐使用两个终端同时启动：

终端 1，启动后端主流程：

```bash
cd /home/qingking/muye
. .venv/bin/activate
python main.py --with-demo-stack
```

终端 2，启动 Streamlit 前端：

```bash
cd /home/qingking/muye
. .venv/bin/activate
streamlit run app.py
```

启动后：

1. 在 Streamlit 左侧栏上传图片
2. 前端会将图片写入 `data/images/`
3. 后端监听到新图片后，依次执行 YOLO、天气、千问和无人机流程
4. 事件总线持续写入 `data/logs/demo_events.jsonl`
5. Streamlit 自动轮询并刷新原图、识别框、天气卡片、AI 建议和无人机状态

## 日志与数据

- 无人机图片存放在 `data/images/`
- 系统日志存放在 `data/logs/system.log`
- 日志会记录 `request_id`、`client_ip`、`duration_ms` 等字段

## 测试

```bash
cd /home/qingking/muye
pytest
```

测试覆盖：

- YOLO 检测结果过滤与响应校验
- 事件总线的写入、清空与任务视图聚合
- 和风天气地点查询与天气实况两步流程
- 本地 YOLO API 的鉴权与标准输出格式
- 虚拟无人机任务状态推进
- 千问决策 JSON Schema 校验与结构化输入构建

## 部署建议

- 将 `config/api_keys.env` 中的示例值替换为真实密钥，避免提交到公共仓库。
- 若需要增强安全性，可在网关层补充 API 密钥认证、IP 白名单和速率限制。
- 如需监控，可在现有日志基础上接入 Prometheus/Grafana，并为 YOLO/Qwen/无人机接口增加指标采集。
