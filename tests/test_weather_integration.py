from __future__ import annotations

import httpx
import pytest

from modules.weather_integration import WeatherClient, WeatherIntegrationError


@pytest.mark.asyncio
async def test_weather_client_uses_mock_payload_when_enabled() -> None:
    client = WeatherClient(
        geo_api_url="https://api.qweather.com/geo/v2/city/lookup",
        weather_api_url="https://api.qweather.com/v7/weather/now",
        api_key="weather-key",
        use_mock=True,
        mock_weather={
            "temperature": "25",
            "humidity": "60",
            "summary": "晴",
            "wind_direction": "东北风",
            "wind_scale_text": "2",
            "wind_speed": "3.3",
        },
    )
    try:
        result = await client.fetch_current_weather(
            location_query="郑州",
            request_id="req-weather-mock-1",
        )
    finally:
        await client.close()

    assert result == {
        "temperature": 25,
        "humidity": 60.0,
        "summary": "晴",
        "wind_direction": "东北风",
        "wind_scale": 2,
        "wind_scale_text": "2",
        "wind_speed": 3.3,
    }


@pytest.mark.asyncio
async def test_weather_client_fetches_qweather_in_two_steps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v2/city/lookup"):
            assert request.url.params["location"] == "郑州"
            assert request.url.params["key"] == "weather-key"
            return httpx.Response(
                200,
                json={
                    "code": "200",
                    "location": [{"id": "101180101", "name": "郑州"}],
                },
            )

        if request.url.path.endswith("/v7/weather/now"):
            assert request.url.params["location"] == "101180101"
            assert request.url.params["key"] == "weather-key"
            return httpx.Response(
                200,
                json={
                    "code": "200",
                    "now": {
                        "temp": "26",
                        "text": "多云",
                        "windDir": "东南风",
                        "windScale": "3",
                        "humidity": "61",
                    },
                },
            )

        raise AssertionError(f"unexpected request path: {request.url.path}")

    client = WeatherClient(
        geo_api_url="https://geoapi.qweather.com/v2/city/lookup",
        weather_api_url="https://devapi.qweather.com/v7/weather/now",
        api_key="weather-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.fetch_current_weather(
            location_query="郑州",
            request_id="req-weather-1",
        )
    finally:
        await client.close()

    assert result == {
        "temperature": 26,
        "humidity": 61.0,
        "summary": "多云",
        "wind_direction": "东南风",
        "wind_scale": 3,
        "wind_scale_text": "3",
        "wind_speed": 5.4,
    }


@pytest.mark.asyncio
async def test_weather_client_rejects_missing_qweather_location() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "200", "location": []})

    client = WeatherClient(
        geo_api_url="https://geoapi.qweather.com/v2/city/lookup",
        weather_api_url="https://devapi.qweather.com/v7/weather/now",
        api_key="weather-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(WeatherIntegrationError):
            await client.fetch_current_weather(
                location_query="不存在的城市",
                request_id="req-weather-2",
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_weather_client_rejects_invalid_qweather_humidity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v2/city/lookup"):
            return httpx.Response(
                200,
                json={
                    "code": "200",
                    "location": [{"id": "101180101", "name": "郑州"}],
                },
            )
        return httpx.Response(
            200,
            json={
                "code": "200",
                "now": {
                    "temp": "24",
                    "text": "晴",
                    "windDir": "北风",
                    "windScale": "2",
                    "humidity": "140",
                },
            },
        )

    client = WeatherClient(
        geo_api_url="https://geoapi.qweather.com/v2/city/lookup",
        weather_api_url="https://devapi.qweather.com/v7/weather/now",
        api_key="weather-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(WeatherIntegrationError):
            await client.fetch_current_weather(
                location_query="郑州",
                request_id="req-weather-3",
            )
    finally:
        await client.close()
