"""
Weather Plugin
===============
Pogoda przez Open-Meteo API (darmowe, bez API key)
"""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from src.plugins import BasePlugin, PluginResult


class WeatherPlugin(BasePlugin):
    """Prognoza pogody przez Open-Meteo"""
    
    name = "Weather"
    description = "Aktualna pogoda i prognoza (Open-Meteo, darmowe)"
    icon = "☁️"
    category = "data"
    requires_api_key = False
    
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    
    WEATHER_CODES = {
        0: "☀️ Bezchmurnie",
        1: "🌤️ Prawie bezchmurnie",
        2: "⛅ Częściowe zachmurzenie",
        3: "☁️ Zachmurzenie całkowite",
        45: "🌫️ Mgła",
        48: "🌫️ Szadź",
        51: "🌧️ Mżawka lekka",
        53: "🌧️ Mżawka",
        55: "🌧️ Mżawka gęsta",
        61: "🌧️ Deszcz lekki",
        63: "🌧️ Deszcz",
        65: "🌧️ Deszcz intensywny",
        71: "🌨️ Śnieg lekki",
        73: "🌨️ Śnieg",
        75: "🌨️ Śnieg intensywny",
        80: "🌧️ Przelotny deszcz",
        81: "🌧️ Przelotny deszcz",
        82: "🌧️ Ulewny deszcz",
        95: "⛈️ Burza",
        96: "⛈️ Burza z gradem",
        99: "⛈️ Burza z gradem"
    }
    
    async def execute(
        self,
        city: str,
        forecast_days: int = 3
    ) -> PluginResult:
        """
        Pobiera pogodę dla miasta
        
        Args:
            city: Nazwa miasta
            forecast_days: Liczba dni prognozy (1-7)
        """
        try:
            # Geokodowanie
            geo = await self._geocode(city)
            if not geo:
                return PluginResult(
                    success=False,
                    error=f"Nie znaleziono miasta: {city}",
                    source="weather"
                )
            
            lat, lon, name, country = geo
            
            # Pobierz pogodę
            weather = await self._get_weather(lat, lon, forecast_days)
            
            return PluginResult(
                success=True,
                data={
                    "location": f"{name}, {country}",
                    "coordinates": {"lat": lat, "lon": lon},
                    "current": weather.get("current"),
                    "forecast": weather.get("forecast", [])
                },
                source="weather"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Weather error: {str(e)}",
                source="weather"
            )
    
    async def _geocode(self, city: str):
        """Geokodowanie miasta"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.GEOCODE_URL,
                params={"name": city, "count": 1, "language": "pl"}
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                return None
            
            r = data["results"][0]
            return (r["latitude"], r["longitude"], r["name"], r.get("country", ""))
    
    async def _get_weather(self, lat: float, lon: float, days: int) -> Dict[str, Any]:
        """Pobiera dane pogodowe"""
        try:
            requested_days = int(days)
        except (TypeError, ValueError):
            requested_days = 3
        safe_days = max(1, min(requested_days, 7))

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.WEATHER_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "timezone": "Europe/Warsaw",
                    "forecast_days": safe_days
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Aktualna pogoda
            current = data.get("current", {})
            current_weather = {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "weather_code": current.get("weather_code"),
                "description": self.WEATHER_CODES.get(current.get("weather_code", 0), "Nieznane")
            }
            
            # Prognoza
            daily = data.get("daily", {})
            times = daily.get("time", []) or []
            temp_max_list = daily.get("temperature_2m_max", []) or []
            temp_min_list = daily.get("temperature_2m_min", []) or []
            precipitation_list = daily.get("precipitation_sum", []) or []
            weather_codes = daily.get("weather_code", []) or []

            def pick(values, idx):
                return values[idx] if idx < len(values) else None

            forecast = []
            for i, forecast_date in enumerate(times):
                code = pick(weather_codes, i)
                forecast.append({
                    "date": forecast_date,
                    "temp_max": pick(temp_max_list, i),
                    "temp_min": pick(temp_min_list, i),
                    "precipitation": pick(precipitation_list, i),
                    "description": self.WEATHER_CODES.get(code, "")
                })
            
            return {"current": current_weather, "forecast": forecast}
