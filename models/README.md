# YOLO 模型放置目录

请将你已经训练完成的 YOLO 权重文件放到以下固定位置：

```text
muye/models/best.pt
```

说明：

- API 服务默认从 `config/api_keys.env` 的 `YOLO_LOCAL_MODEL_PATH` 读取模型路径。
- 如果你想放到其他位置，可以修改 `YOLO_LOCAL_MODEL_PATH` 或 `config/yolo_config.yaml` 中的 `local_api.model_path`。
- 启动本地 API 前，请确认该文件已经存在。
