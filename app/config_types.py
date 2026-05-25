"""Configuration dataclass for MuyeApplication.

Centralizes all environment variable management into a single configuration object,
improving testability and reducing parameter explosion in __init__.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _parse_env_bool(value: str | None, default: bool) -> bool:
    """Parse a boolean environment variable."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class MuyeConfig:
    """牧野应用配置，集中管理所有环境变量。

    将 MuyeApplication.__init__ 中分散的 os.getenv 调用统一到单一配置对象中，
    提高可测试性和可维护性。
    """

    # 网络配置
    client_ip: str = "127.0.0.1"

    # 数据库配置
    sqlite_path: Path = field(default_factory=lambda: Path.home() / ".muye" / "data" / "muye.db")

    # YOLO 检测配置
    yolo_api_url: str = "http://127.0.0.1:8010/detect"
    yolo_api_key: str = ""
    yolo_confidence_threshold: float = 0.25

    # 和风天气配置
    qweather_geo_url: str = "https://geoapi.qweather.com/v2/city/lookup"
    qweather_weather_url: str = "https://devapi.qweather.com/v7/weather/now"
    qweather_api_key: str = ""
    qweather_use_mock: bool = False
    qweather_mock_temperature: str = "26"
    qweather_mock_humidity: str = "58"
    qweather_mock_summary: str = "多云"
    qweather_mock_wind_direction: str = "东南风"
    qweather_mock_wind_scale: str = "2"
    qweather_mock_wind_speed: str = "3.3"

    # 决策上下文配置
    enable_sqlite_decision_context: bool = False

    # Qwen AI 决策配置
    qwen_api_url: str = ""
    qwen_api_key: str = ""
    qwen_model: str = "qwen-max"
    qwen_use_mock: bool = False

    # 无人机配置
    drone_backend: str | None = None

    # PX4 配置
    px4_system_address: str | None = None
    px4_connect_timeout_seconds: float = 30.0
    px4_mission_timeout_seconds: float = 180.0
    px4_auto_arm: bool = True
    px4_auto_start_mission: bool = True
    px4_auto_start_on_spray: bool = True
    px4_return_to_launch_after_mission: bool = True
    px4_require_global_position: bool = True
    px4_arm_timeout_seconds: float = 30.0
    px4_arm_retries: int = 3
    px4_arm_retry_delay_seconds: float = 1.0
    px4_allow_force_arm: bool = False
    px4_prefer_demo_field: bool = True
    px4_acceptance_radius_m: float = 2.0

    # RAG 配置
    rag_enabled: bool = True
    qwen_embedding_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_embedding_model: str = "text-embedding-v3"
    qwen_embedding_dimensions: int = 1024
    qwen_embedding_timeout_seconds: float = 60.0

    # 多智能体会诊配置
    multi_agent_enabled: bool = False
    multi_agent_timeout_seconds: float = 60.0

    # 路由层配置
    router_enabled: bool = False
    router_familiarity_threshold: float = 0.6

    # DeepSeek 会诊模型配置
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # 小米会诊模型配置
    xiaomi_api_url: str = ""
    xiaomi_api_key: str = ""
    xiaomi_model: str = ""

    @classmethod
    def from_env(cls, drone_config: dict[str, Any] | None = None) -> "MuyeConfig":
        """从环境变量构建配置。

        Args:
            drone_config: 可选的无人机配置字典，用于提供默认值。
                          如果不提供，将从环境变量或硬编码默认值获取。

        Returns:
            MuyeConfig 实例
        """
        drone_config = drone_config or {}
        network_config = drone_config.get("network", {})
        execution_config = drone_config.get("execution", {})
        px4_config = drone_config.get("px4", {})

        # 获取数据库路径
        data_dir = Path.home() / ".muye" / "data"
        default_sqlite_path = data_dir / "muye.db"

        return cls(
            # 网络配置
            client_ip=os.getenv(
                "SERVICE_CLIENT_IP",
                network_config.get("client_ip", "127.0.0.1"),
            ),
            # 数据库配置
            sqlite_path=Path(os.getenv("MUYE_SQLITE_PATH", str(default_sqlite_path))),
            # YOLO 检测配置
            yolo_api_url=os.getenv("YOLO_API_URL", "http://127.0.0.1:8010/detect"),
            yolo_api_key=os.getenv("YOLO_API_KEY", ""),
            yolo_confidence_threshold=float(
                os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.25")
            ),
            # 和风天气配置
            qweather_geo_url=os.getenv(
                "QWEATHER_GEO_URL",
                "https://geoapi.qweather.com/v2/city/lookup",
            ),
            qweather_weather_url=os.getenv(
                "QWEATHER_WEATHER_URL",
                "https://devapi.qweather.com/v7/weather/now",
            ),
            qweather_api_key=os.getenv("QWEATHER_API_KEY", ""),
            qweather_use_mock=_parse_env_bool(os.getenv("QWEATHER_USE_MOCK"), False),
            qweather_mock_temperature=os.getenv("QWEATHER_MOCK_TEMPERATURE", "26"),
            qweather_mock_humidity=os.getenv("QWEATHER_MOCK_HUMIDITY", "58"),
            qweather_mock_summary=os.getenv("QWEATHER_MOCK_SUMMARY", "多云"),
            qweather_mock_wind_direction=os.getenv("QWEATHER_MOCK_WIND_DIRECTION", "东南风"),
            qweather_mock_wind_scale=os.getenv("QWEATHER_MOCK_WIND_SCALE", "2"),
            qweather_mock_wind_speed=os.getenv("QWEATHER_MOCK_WIND_SPEED", "3.3"),
            # 决策上下文配置
            enable_sqlite_decision_context=_parse_env_bool(
                os.getenv("MUYE_ENABLE_SQLITE_DECISION_CONTEXT"), False
            ),
            # Qwen AI 决策配置
            qwen_api_url=os.getenv("QWEN_API_URL", ""),
            qwen_api_key=os.getenv("QWEN_API_KEY", ""),
            qwen_model=os.getenv("QWEN_MODEL", "qwen-max"),
            qwen_use_mock=_parse_env_bool(os.getenv("QWEN_USE_MOCK"), False),
            # 无人机配置
            drone_backend="px4",
            # PX4 配置
            px4_system_address=os.getenv("PX4_SYSTEM_ADDRESS") or px4_config.get("system_address"),
            px4_connect_timeout_seconds=float(
                os.getenv("PX4_CONNECT_TIMEOUT_SECONDS", str(px4_config.get("connect_timeout_seconds", 30)))
            ),
            px4_mission_timeout_seconds=float(
                os.getenv("PX4_MISSION_TIMEOUT_SECONDS", str(px4_config.get("mission_timeout_seconds", 180)))
            ),
            px4_auto_arm=_parse_env_bool(
                os.getenv("PX4_AUTO_ARM"),
                bool(px4_config.get("auto_arm", True)),
            ),
            px4_auto_start_mission=_parse_env_bool(
                os.getenv("PX4_AUTO_START_MISSION"),
                bool(px4_config.get("auto_start_mission", True)),
            ),
            px4_auto_start_on_spray=_parse_env_bool(
                os.getenv("PX4_AUTO_START_ON_SPRAY"),
                bool(px4_config.get("auto_start_on_spray", True)),
            ),
            px4_return_to_launch_after_mission=_parse_env_bool(
                os.getenv("PX4_RETURN_TO_LAUNCH_AFTER_MISSION"),
                bool(px4_config.get("return_to_launch_after_mission", True)),
            ),
            px4_require_global_position=_parse_env_bool(
                os.getenv("PX4_REQUIRE_GLOBAL_POSITION"),
                bool(px4_config.get("require_global_position", True)),
            ),
            px4_arm_timeout_seconds=float(
                os.getenv("PX4_ARM_TIMEOUT_SECONDS", str(px4_config.get("arm_timeout_seconds", 30)))
            ),
            px4_arm_retries=int(
                os.getenv("PX4_ARM_RETRIES", str(px4_config.get("arm_retries", 3)))
            ),
            px4_arm_retry_delay_seconds=float(
                os.getenv(
                    "PX4_ARM_RETRY_DELAY_SECONDS",
                    str(px4_config.get("arm_retry_delay_seconds", 1.0)),
                )
            ),
            px4_allow_force_arm=_parse_env_bool(
                os.getenv("PX4_ALLOW_FORCE_ARM"),
                bool(px4_config.get("allow_force_arm", False)),
            ),
            px4_prefer_demo_field=_parse_env_bool(
                os.getenv("PX4_USE_SITL_DEMO_FIELD"),
                bool(px4_config.get("prefer_demo_field", True)),
            ),
            px4_acceptance_radius_m=float(
                os.getenv("PX4_ACCEPTANCE_RADIUS_M", str(px4_config.get("acceptance_radius_m", 2.0)))
            ),
            # RAG 配置
            rag_enabled=_parse_env_bool(os.getenv("RAG_ENABLED"), True),
            qwen_embedding_api_url=os.getenv(
                "QWEN_EMBEDDING_API_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            qwen_embedding_model=os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v3"),
            qwen_embedding_dimensions=int(os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024")),
            qwen_embedding_timeout_seconds=float(os.getenv("QWEN_EMBEDDING_TIMEOUT_SECONDS", "60")),
            # 多智能体会诊配置
            multi_agent_enabled=_parse_env_bool(os.getenv("MUYE_MULTI_AGENT_ENABLED"), False),
            multi_agent_timeout_seconds=float(os.getenv("MUYE_MULTI_AGENT_TIMEOUT_SECONDS", "60")),
            # 路由层配置
            router_enabled=_parse_env_bool(os.getenv("MUYE_ROUTER_ENABLED"), False),
            router_familiarity_threshold=float(os.getenv("MUYE_ROUTER_FAMILIARITY_THRESHOLD", "0.6")),
            # DeepSeek 会诊模型
            deepseek_api_url=os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            # 小米会诊模型
            xiaomi_api_url=os.getenv("XIAOMI_API_URL", ""),
            xiaomi_api_key=os.getenv("XIAOMI_API_KEY", ""),
            xiaomi_model=os.getenv("XIAOMI_MODEL", ""),
        )
