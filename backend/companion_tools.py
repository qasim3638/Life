"""Companion live tools: prayer times, world clock, unit conversion.
Each tool has an intent detector + a text builder for the Claude prompt.
"""
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones
import httpx

logger = logging.getLogger(__name__)

# =========================================================================
# 1. PRAYER TIMES (AlAdhan — free, no API key)
# =========================================================================

ALADHAN_URL = "https://api.aladhan.com/v1/timings/{date}"

_PRAYER_RE = re.compile(r"\b(prayer|namaz|namaaz|salah|salat|fajr|dhuhr|zuhr|asr|maghrib|isha|iqamah|iftar|suhoor|sehri|sehar)\b", re.IGNORECASE)


def wants_prayer_times(msg: str) -> bool:
    return bool(_PRAYER_RE.search(msg or ""))


async def prayer_times(lat: float, lon: float, method: int = 2) -> dict | None:
    """Today's prayer times for (lat, lon). method=2 is ISNA (widely used)."""
    today = datetime.now().strftime("%d-%m-%Y")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(
                ALADHAN_URL.format(date=today),
                params={"latitude": lat, "longitude": lon, "method": method},
            )
            r.raise_for_status()
            return r.json().get("data", {}).get("timings")
    except Exception as e:
        logger.warning(f"Prayer times failed: {e}")
        return None


def summarise_prayer(times: dict, city: str) -> str:
    if not times:
        return ""
    keys = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
    lines = [f"Prayer times today for {city} (ISNA):"]
    for k in keys:
        if k in times:
            lines.append(f"  {k}: {times[k]}")
    return "\n".join(lines)


# =========================================================================
# 2. WORLD CLOCK (stdlib zoneinfo — no API)
# =========================================================================

# Light alias map for cities → IANA timezones. Falls back to substring match.
CITY_TO_TZ = {
    "karachi": "Asia/Karachi", "lahore": "Asia/Karachi", "islamabad": "Asia/Karachi",
    "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
    "dubai": "Asia/Dubai", "abu dhabi": "Asia/Dubai",
    "doha": "Asia/Qatar", "riyadh": "Asia/Riyadh", "jeddah": "Asia/Riyadh",
    "cairo": "Africa/Cairo", "istanbul": "Europe/Istanbul", "mecca": "Asia/Riyadh",
    "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid", "rome": "Europe/Rome", "moscow": "Europe/Moscow",
    "new york": "America/New_York", "nyc": "America/New_York", "toronto": "America/Toronto",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "chicago": "America/Chicago", "vancouver": "America/Vancouver",
    "tokyo": "Asia/Tokyo", "seoul": "Asia/Seoul", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong", "singapore": "Asia/Singapore", "bangkok": "Asia/Bangkok",
    "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne", "auckland": "Pacific/Auckland",
    "johannesburg": "Africa/Johannesburg", "cape town": "Africa/Johannesburg",
}

_TIME_RE = re.compile(
    r"(?:what(?:'s| is)?\s+the\s+time|what\s+time\s+is\s+it|current\s+time|time\s+in|time\s+now\s+in)\s+(?:in\s+)?([a-zA-Z ]+?)(?:\?|$|[,.])",
    re.IGNORECASE,
)


def wants_world_time(msg: str) -> str | None:
    """Return city query if detected, else None."""
    m = _TIME_RE.search(msg or "")
    if not m:
        return None
    q = m.group(1).strip().lower()
    # Trim trailing noise words
    for noise in (" right now", " today", " now"):
        if q.endswith(noise):
            q = q[: -len(noise)]
    return q.strip() or None


def world_time(city_query: str) -> str | None:
    q = (city_query or "").lower().strip()
    tz_name = CITY_TO_TZ.get(q)
    if not tz_name:
        # Try substring match against CITY_TO_TZ
        for k, v in CITY_TO_TZ.items():
            if q in k or k in q:
                tz_name = v
                break
    if not tz_name:
        # Try matching against IANA directly (e.g. "Asia/Tokyo")
        for name in available_timezones():
            if q.replace(" ", "_") in name.lower() or name.lower().endswith("/" + q.replace(" ", "_")):
                tz_name = name
                break
    if not tz_name:
        return None
    try:
        now = datetime.now(ZoneInfo(tz_name))
        pretty = now.strftime("%-I:%M %p on %A, %B %-d").lstrip("0")
        return f"Local time in {city_query.title()} ({tz_name}): {pretty}"
    except Exception as e:
        logger.warning(f"world_time failed: {e}")
        return None


# =========================================================================
# 3. UNIT CONVERSION (hand-written, safe + common units)
# =========================================================================

# Canonical base units:
#   mass → grams;  volume → millilitres;  length → metres;  temp handled specially
UNIT_ALIASES = {
    # mass
    "g": ("mass", 1), "gram": ("mass", 1), "grams": ("mass", 1),
    "kg": ("mass", 1000), "kilo": ("mass", 1000), "kilos": ("mass", 1000), "kilogram": ("mass", 1000), "kilograms": ("mass", 1000),
    "mg": ("mass", 0.001), "milligram": ("mass", 0.001), "milligrams": ("mass", 0.001),
    "oz": ("mass", 28.3495), "ounce": ("mass", 28.3495), "ounces": ("mass", 28.3495),
    "lb": ("mass", 453.592), "lbs": ("mass", 453.592), "pound": ("mass", 453.592), "pounds": ("mass", 453.592),
    "stone": ("mass", 6350.29), "st": ("mass", 6350.29),
    # volume
    "ml": ("volume", 1), "millilitre": ("volume", 1), "milliliter": ("volume", 1),
    "l": ("volume", 1000), "litre": ("volume", 1000), "liter": ("volume", 1000), "litres": ("volume", 1000), "liters": ("volume", 1000),
    "cup": ("volume", 240), "cups": ("volume", 240),
    "tbsp": ("volume", 15), "tablespoon": ("volume", 15), "tablespoons": ("volume", 15),
    "tsp": ("volume", 5), "teaspoon": ("volume", 5), "teaspoons": ("volume", 5),
    "floz": ("volume", 29.5735), "fl_oz": ("volume", 29.5735),
    # length
    "m": ("length", 1), "meter": ("length", 1), "metre": ("length", 1), "meters": ("length", 1), "metres": ("length", 1),
    "cm": ("length", 0.01), "centimeter": ("length", 0.01), "centimetre": ("length", 0.01),
    "mm": ("length", 0.001), "millimeter": ("length", 0.001),
    "km": ("length", 1000), "kilometer": ("length", 1000), "kilometre": ("length", 1000), "kilometers": ("length", 1000), "kilometres": ("length", 1000),
    "in": ("length", 0.0254), "inch": ("length", 0.0254), "inches": ("length", 0.0254),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048), "feet": ("length", 0.3048),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144), "yards": ("length", 0.9144),
    "mi": ("length", 1609.34), "mile": ("length", 1609.34), "miles": ("length", 1609.34),
}
TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}

_CONV_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([a-zA-Z °]+?)\s+(?:in|to|into|as)\s+([a-zA-Z °]+?)(?:\?|$|\.|,)",
    re.IGNORECASE,
)


def _norm(u: str) -> str:
    return u.strip().lower().replace("°", "").replace(".", "").replace("-", "_")


def convert_units(value: float, from_u: str, to_u: str) -> str | None:
    fu, tu = _norm(from_u), _norm(to_u)
    # Temperature
    if fu in TEMP_UNITS and tu in TEMP_UNITS:
        c = _to_celsius(value, fu)
        if c is None:
            return None
        out = _from_celsius(c, tu)
        if out is None:
            return None
        return f"{value:g}°{fu[0].upper()} = {out:.2f}°{tu[0].upper()}"
    # Length/mass/volume
    if fu in UNIT_ALIASES and tu in UNIT_ALIASES:
        fcat, ffac = UNIT_ALIASES[fu]
        tcat, tfac = UNIT_ALIASES[tu]
        if fcat != tcat:
            return f"Those are different kinds of unit ({fcat} vs {tcat}) — can't convert."
        base = value * ffac
        out = base / tfac
        return f"{value:g} {from_u.strip()} = {out:g} {to_u.strip()}"
    return None


def _to_celsius(v: float, unit: str) -> float | None:
    if unit.startswith("c"):
        return v
    if unit.startswith("f"):
        return (v - 32) * 5 / 9
    if unit.startswith("k"):
        return v - 273.15
    return None


def _from_celsius(c: float, unit: str) -> float | None:
    if unit.startswith("c"):
        return c
    if unit.startswith("f"):
        return c * 9 / 5 + 32
    if unit.startswith("k"):
        return c + 273.15
    return None


def detect_and_convert(msg: str) -> str | None:
    m = _CONV_RE.search(msg or "")
    if not m:
        return None
    try:
        v = float(m.group(1))
    except Exception:
        return None
    return convert_units(v, m.group(2), m.group(3))
