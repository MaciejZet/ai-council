"""Regression tests for weather plugin edge cases."""

import pytest

from src.plugins.weather import WeatherPlugin


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _WeatherAsyncClient:
    weather_payload = {
        "current": {
            "temperature_2m": 18.1,
            "relative_humidity_2m": 60,
            "weather_code": 1,
            "wind_speed_10m": 12.3,
        },
        "daily": {
            "time": ["2026-04-20"],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [12.0],
            "precipitation_sum": [0.2],
            "weather_code": [1],
        },
    }
    last_weather_params = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params=None):
        if "geocoding-api.open-meteo.com" in url:
            return _FakeResponse(
                {
                    "results": [
                        {
                            "latitude": 52.23,
                            "longitude": 21.01,
                            "name": "Warszawa",
                            "country": "Polska",
                        }
                    ]
                }
            )
        if "api.open-meteo.com" in url:
            _WeatherAsyncClient.last_weather_params = params or {}
            return _FakeResponse(_WeatherAsyncClient.weather_payload)
        raise AssertionError(f"Unexpected URL: {url}")


@pytest.mark.asyncio
async def test_weather_plugin_clamps_forecast_days_minimum(monkeypatch):
    import src.plugins.weather as weather_mod

    _WeatherAsyncClient.weather_payload = {
        "current": {
            "temperature_2m": 18.1,
            "relative_humidity_2m": 60,
            "weather_code": 1,
            "wind_speed_10m": 12.3,
        },
        "daily": {
            "time": ["2026-04-20"],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [12.0],
            "precipitation_sum": [0.2],
            "weather_code": [1],
        },
    }
    _WeatherAsyncClient.last_weather_params = None
    monkeypatch.setattr(weather_mod.httpx, "AsyncClient", _WeatherAsyncClient)

    plugin = WeatherPlugin()
    result = await plugin.execute("Warszawa", forecast_days=0)

    assert result.success is True
    assert _WeatherAsyncClient.last_weather_params is not None
    assert _WeatherAsyncClient.last_weather_params["forecast_days"] == 1


@pytest.mark.asyncio
async def test_weather_plugin_handles_partial_daily_payload(monkeypatch):
    import src.plugins.weather as weather_mod

    _WeatherAsyncClient.weather_payload = {
        "current": {
            "temperature_2m": 17.5,
            "relative_humidity_2m": 63,
            "weather_code": 2,
            "wind_speed_10m": 9.1,
        },
        "daily": {
            "time": ["2026-04-20", "2026-04-21"],
            "temperature_2m_max": [21.0],
            # missing: temperature_2m_min, precipitation_sum, weather_code
        },
    }
    monkeypatch.setattr(weather_mod.httpx, "AsyncClient", _WeatherAsyncClient)

    plugin = WeatherPlugin()
    result = await plugin.execute("Warszawa", forecast_days=2)

    assert result.success is True
    assert len(result.data["forecast"]) == 2
    assert result.data["forecast"][0]["temp_min"] is None
    assert result.data["forecast"][1]["temp_max"] is None
