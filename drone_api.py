from __future__ import annotations

import argparse

import uvicorn

from modules.virtual_drone_api import create_virtual_drone_app, load_virtual_drone_settings


def parse_args() -> argparse.Namespace:
    settings = load_virtual_drone_settings()
    parser = argparse.ArgumentParser(description="启动牧野虚拟无人机 API")
    parser.add_argument("--host", default=settings.host, help="虚拟无人机 API 监听地址")
    parser.add_argument("--port", type=int, default=settings.port, help="虚拟无人机 API 监听端口")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_virtual_drone_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
