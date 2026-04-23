from __future__ import annotations

import argparse

import uvicorn

from modules.detection.local_yolo_api import create_app, load_local_yolo_settings


def parse_args() -> argparse.Namespace:
    settings = load_local_yolo_settings()
    parser = argparse.ArgumentParser(description="启动牧野本地 YOLO 推理 API")
    parser.add_argument("--host", default=settings.host, help="YOLO API 监听地址")
    parser.add_argument("--port", type=int, default=settings.port, help="YOLO API 监听端口")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
