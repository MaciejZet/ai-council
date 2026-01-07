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
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.WEATHER_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "timezone": "Europe/Warsaw",
                    "forecast_days": min(days, 7)
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
            forecast = []
            for i in range(len(daily.get("time", []))):
                forecast.append({
                    "date": daily["time"][i],
                    "temp_max": daily["temperature_2m_max"][i],
                    "temp_min": daily["temperature_2m_min"][i],
                    "precipitation": daily["precipitation_sum"][i],
                    "description": self.WEATHER_CODES.get(daily["weather_code"][i], "")
                })
            
            return {"current": current_weather, "forecast": forecast}
