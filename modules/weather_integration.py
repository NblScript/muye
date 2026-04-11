from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from modules.common import log_event


class WeatherIntegrationError(RuntimeError):
    """天气服务错误。"""


class WeatherClient:
    def __init__(
        self,
        geo_api_url: str,
        weather_api_url: str,
        api_key: str,
        timeout_seconds: float = 15,
        logger: logging.Logger | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.geo_api_url = geo_api_url
        self.weather_api_url = weather_api_url
        self.api_key = api_key
        self.logger = logger or logging.getLogger("muye.weather")
        self._client = httpx.AsyncClient(timeout=timeout_seconds, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_current_weather(
        self,
        location_query: str,
        request_id: str,
        client_ip: str = "127.0.0.1",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            if not self.api_key:
                raise WeatherIntegrationError("缺少 QWEATHER_API_KEY 配置")
            if not self.geo_api_url or not self.weather_api_url:
                raise WeatherIntegrationError("缺少和风天气接口地址配置")

            location_id = await self._lookup_location_id(location_query)
            payload = await self._fetch_weather_payload(location_id)
            normalized = self._normalize_weather_payload(payload)
            log_event(
                self.logger,
                logging.INFO,
                "天气数据获取完成",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                weather=normalized,
                location_query=location_query,
                location_id=location_id,
            )
            return normalized
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "天气数据获取失败",
                request_id=request_id,
                client_ip=client_ip,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
                location_query=location_query,
            )
            raise WeatherIntegrationError(str(exc)) from exc

    async def _lookup_location_id(self, location_query: str) -> str:
        response = await self._client.get(
            self.geo_api_url,
            params={
                "location": location_query,
                "key": self.api_key,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("code")) != "200":
            raise WeatherIntegrationError(
                f"和风天气地点查询失败，返回 code={payload.get('code')}"
            )

        locations = payload.get("location") or []
        if not locations:
            raise WeatherIntegrationError(f"和风天气未找到地点: {location_query}")

        location_id = locations[0].get("id")
        if not location_id:
            raise WeatherIntegrationError("和风天气地点查询缺少 location.id")
        return str(location_id)

    async def _fetch_weather_payload(self, location_id: str) -> dict[str, Any]:
        response = await self._client.get(
            self.weather_api_url,
            params={
                "location": location_id,
                "key": self.api_key,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def _normalize_weather_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if str(payload.get("code")) != "200":
            raise WeatherIntegrationError(
                f"和风天气实况查询失败，返回 code={payload.get('code')}"
            )

        now = payload.get("now")
        if not isinstance(now, dict):
            raise WeatherIntegrationError("和风天气响应缺少 now 字段")

        required_fields = {"temp", "text", "windDir", "windScale", "humidity"}
        if not required_fields.issubset(now):
            raise WeatherIntegrationError("和风天气响应缺少 temp/text/windDir/windScale/humidity 字段")

        wind_scale_text = str(now["windScale"])
        wind_scale = self._parse_wind_scale(wind_scale_text)
        data = {
            "temperature": int(float(now["temp"])),
            "humidity": float(now["humidity"]),
            "summary": str(now["text"]),
            "wind_direction": str(now["windDir"]),
            "wind_scale": wind_scale,
            "wind_scale_text": wind_scale_text,
            # 无人机控制仍以风速阈值做校验，这里用风力等级推算风速上限。
            "wind_speed": self._wind_scale_to_speed_mps(wind_scale),
        }

        if data["humidity"] < 0 or data["humidity"] > 100:
            raise WeatherIntegrationError("天气响应中的湿度超出合理范围")
        return data

    def _parse_wind_scale(self, raw_value: str) -> int:
        normalized = raw_value.strip()
        if "-" in normalized:
            parts = [item.strip() for item in normalized.split("-") if item.strip()]
            try:
                return int(float(parts[-1]))
            except (IndexError, ValueError) as exc:
                raise WeatherIntegrationError(f"无法解析和风天气风力等级: {raw_value}") from exc

        try:
            return int(float(normalized))
        except ValueError as exc:
            raise WeatherIntegrationError(f"无法解析和风天气风力等级: {raw_value}") from exc

    def _wind_scale_to_speed_mps(self, wind_scale: int) -> float:
        beaufort_upper_bound = {
            0: 0.2,
            1: 1.5,
            2: 3.3,
            3: 5.4,
            4: 7.9,
            5: 10.7,
            6: 13.8,
            7: 17.1,
            8: 20.7,
            9: 24.4,
            10: 28.4,
            11: 32.6,
            12: 36.9,
        }
        clamped = max(0, min(wind_scale, 12))
        return beaufort_upper_bound[clamped]
