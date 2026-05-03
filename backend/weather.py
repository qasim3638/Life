"""Open-Meteo helper — free, no API key, no registration.
Used by Companion chat to inject real-world weather context.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Subset of WMO weather codes → short human descriptions
WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm",
}


def describe(code: int) -> str:
    return WEATHER_CODES.get(code, "mixed conditions")


async def geocode(query: str) -> dict | None:
    """Resolve a city name to {name, country, latitude, longitude}.
    Falls back to progressively shorter queries if the full string returns no hit."""
    q = (query or "").strip()
    # Try the full query, then each attempt with the last word stripped (e.g. "Gravesend UK" → "Gravesend")
    attempts = [q]
    parts = q.split()
    if len(parts) > 1:
        attempts.append(" ".join(parts[:-1]))
    if len(parts) > 2:
        attempts.append(" ".join(parts[:-2]))
    for attempt in attempts:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(GEOCODE_URL, params={"name": attempt, "count": 1, "language": "en"})
                r.raise_for_status()
                data = r.json()
                results = data.get("results") or []
                if not results:
                    continue
                hit = results[0]
                return {
                    "name": hit.get("name"),
                    "country": hit.get("country"),
                    "admin1": hit.get("admin1"),
                    "latitude": hit.get("latitude"),
                    "longitude": hit.get("longitude"),
                }
        except Exception as e:
            logger.warning(f"Geocode failed for '{attempt}': {e}")
    return None


async def forecast(lat: float, lon: float, days: int = 3) -> dict | None:
    """Return current conditions + next N days daily forecast."""
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(FORECAST_URL, params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset",
                "forecast_days": max(1, min(7, days)),
                "timezone": "auto",
            })
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"Forecast failed for ({lat}, {lon}): {e}")
        return None


def summarise(location_name: str, data: dict) -> str:
    """Turn the raw Open-Meteo response into a compact prompt-ready string."""
    if not data:
        return ""
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    lines = [f"Weather for {location_name}:"]
    if current:
        temp = current.get("temperature_2m")
        wcode = current.get("weather_code")
        wind = current.get("wind_speed_10m")
        hum = current.get("relative_humidity_2m")
        bits = []
        if temp is not None:
            bits.append(f"{temp}°C")
        if wcode is not None:
            bits.append(describe(wcode))
        if wind is not None:
            bits.append(f"wind {wind} km/h")
        if hum is not None:
            bits.append(f"humidity {hum}%")
        lines.append("  now: " + ", ".join(bits))
    times = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    pprob = daily.get("precipitation_probability_max") or []
    codes = daily.get("weather_code") or []
    for i, day in enumerate(times[:3]):
        label = "today" if i == 0 else ("tomorrow" if i == 1 else day)
        parts = [label + ":"]
        if i < len(tmin) and i < len(tmax):
            parts.append(f"{tmin[i]}–{tmax[i]}°C")
        if i < len(codes):
            parts.append(describe(codes[i]))
        if i < len(pprob) and pprob[i] is not None:
            parts.append(f"rain {pprob[i]}%")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


WEATHER_KEYWORDS = (
    "weather", "forecast", "rain", "raining", "sunny", "cloudy", "snow",
    "snowing", "storm", "wind", "windy", "temperature", "degrees",
    "hot today", "cold today", "humidity", "umbrella", "sunrise", "sunset",
    "climate today", "climate tomorrow",
)


def is_weather_question(text: str) -> bool:
    low = (text or "").lower()
    return any(kw in low for kw in WEATHER_KEYWORDS)
