"""
CS3235 Lab 6 - Experiment 2: "Data Dashboard" Connector
=======================================================

An MCP server that connects an LLM to a *real-time* external API:
wttr.in (https://wttr.in/<location>?format=j1), a free, keyless weather service.

Tools exposed to the LLM
------------------------
* get_current_weather(location)       - live conditions for one place
* get_forecast(location, days=3)      - 1..3 day outlook
* compare_weather(locations)          - side-by-side table for 2-5 places

Design notes
------------
* The network call (`fetch_wttr`) is separated from the pure formatting helpers
  (`format_current`, `format_forecast`, `format_comparison_row`) so the
  formatters can be unit-tested offline against a saved JSON fixture.
* Tools never raise: any WeatherError is converted into an "ERROR: ..." string
  so the LLM can read it and explain the problem to the user.
* wttr.in's own place-name lookup is unreliable ("Tokyo" -> the island
  Shikinejima, "Rome" -> Lome in Togo), so `fetch_wttr` first geocodes the
  name with the free, keyless Open-Meteo geocoding API (results ranked by
  population) and asks wttr.in for those coordinates. If geocoding fails, it
  falls back to passing the raw name to wttr.in.
* stdout is reserved for the MCP stdio protocol, so all logging goes to stderr.
  Only WARNING and above is logged unless LOG_LEVEL is set (e.g. LOG_LEVEL=INFO).

Run:  python weather_server.py      (normally launched by an MCP client)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Logging (stderr only - stdout carries JSON-RPC messages for stdio transport)
# --------------------------------------------------------------------------- #
# Quiet by default so server logs (inherited stderr) don't clutter the client
# UI. Set LOG_LEVEL=INFO (or DEBUG) to see every request.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING").upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    LOG_LEVEL = "WARNING"
logging.basicConfig(
    stream=sys.stderr,
    level=LOG_LEVEL,
    format="%(asctime)s [weather-dashboard] %(levelname)s: %(message)s",
)
log = logging.getLogger("weather-dashboard")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
WTTR_URL = "https://wttr.in/{location}?format=j1"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_S = 20.0
RETRIES = 2                      # extra attempts after the first one
HEADERS = {"User-Agent": "curl/8"}  # wttr.in serves JSON reliably to curl-like UAs

mcp = FastMCP("weather-dashboard", log_level=LOG_LEVEL)


class WeatherError(Exception):
    """Raised when weather data cannot be fetched or the location is unknown."""


# --------------------------------------------------------------------------- #
# Small defensive accessors for the (deeply nested, all-string) j1 JSON
# --------------------------------------------------------------------------- #
def _first(seq: Any) -> dict:
    """Return seq[0] if seq is a non-empty list of dicts, else {}."""
    if isinstance(seq, list) and seq and isinstance(seq[0], dict):
        return seq[0]
    return {}


def _val(obj: dict, key: str, default: str = "?") -> str:
    """Read a j1 field that may be a plain string or [{'value': '...'}]."""
    raw = obj.get(key) if isinstance(obj, dict) else None
    if raw is None:
        return default
    if isinstance(raw, list):
        raw = _first(raw).get("value")
        if raw is None:
            return default
    text = str(raw).strip()
    return text if text else default


def _resolved_name(data: dict) -> str:
    """Name of the place the data is for.

    Uses the geocoded name that `fetch_wttr` stores under "resolved_place"
    when available; otherwise builds 'Area, Region, Country' from wttr.in's
    nearest_area[0], skipping duplicates.
    """
    place = data.get("resolved_place") if isinstance(data, dict) else None
    if isinstance(place, str) and place.strip():
        return place.strip()
    area = _first(data.get("nearest_area"))
    parts: list[str] = []
    for key in ("areaName", "region", "country"):
        v = _val(area, key, "")
        if v and v not in parts:
            parts.append(v)
    return ", ".join(parts) if parts else "Unknown"


# --------------------------------------------------------------------------- #
# Network layer
# --------------------------------------------------------------------------- #
# Inputs wttr.in understands directly and that must not be geocoded:
# "lat,lon" coordinates, 3-letter airport codes (JFK), "~place" and "@domain".
_PASSTHROUGH_RE = re.compile(r"^(-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?|[A-Z]{3}|[~@].+)$")


def geocode(location: str) -> dict | None:
    """Resolve a place name to {"name", "lat", "lon"} with Open-Meteo.

    "Tokyo" -> Tokyo, Japan (35.69, 139.69). A qualifier after a comma
    ("Paris, France", "London, Ontario") picks the first match whose country,
    country code or region contains it. Returns None when the input should be
    passed to wttr.in unchanged, nothing matches, or the geocoder is down.
    """
    location = location.strip()
    if _PASSTHROUGH_RE.match(location):
        return None
    name, _, qualifier = (p.strip() for p in location.partition(","))
    try:
        resp = httpx.get(GEOCODE_URL, headers=HEADERS, timeout=TIMEOUT_S,
                         params={"name": name, "count": 10, "language": "en", "format": "json"})
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Geocoding %r failed (%s); falling back to wttr.in lookup", location, exc)
        return None

    if qualifier:
        q = qualifier.lower()
        results = [r for r in results
                   if any(q in str(r.get(k) or "").lower() or str(r.get(k) or "").lower() == q
                          for k in ("country", "country_code", "admin1", "admin2"))]
    if not results:
        return None
    best = results[0]  # Open-Meteo ranks matches by population
    parts: list[str] = []
    for key in ("name", "admin1", "country"):
        v = str(best.get(key) or "").strip()
        if v and v not in parts:
            parts.append(v)
    return {"name": ", ".join(parts), "lat": best["latitude"], "lon": best["longitude"]}


def fetch_wttr(location: str) -> dict:
    """Fetch the wttr.in j1 JSON for `location`.

    The name is geocoded first (see `geocode`) and wttr.in is queried by
    coordinates; the geocoded name is stored in data["resolved_place"].
    Retries up to RETRIES times on network / 5xx failures.
    Raises WeatherError on persistent failure or unknown location.
    """
    location = (location or "").strip()
    if not location:
        raise WeatherError("Location must be a non-empty string.")

    place = geocode(location)
    query = f"{place['lat']:.4f},{place['lon']:.4f}" if place else location
    url = WTTR_URL.format(location=quote(query))
    last_err: str = "unknown error"

    for attempt in range(1, RETRIES + 2):
        try:
            log.info("GET %s (attempt %d)", url, attempt)
            resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_S,
                             follow_redirects=True)
            body = resp.text.strip()

            # wttr.in reports unknown places as plain text (often with HTTP 404/500).
            if "location not found" in body.lower() or "unknown location" in body.lower():
                raise WeatherError(f"Unknown location: '{location}'.")
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {body[:120]}"
                raise httpx.HTTPStatusError(last_err, request=resp.request, response=resp)

            data = resp.json()
            if not isinstance(data, dict) or not data.get("current_condition"):
                raise WeatherError(f"No weather data returned for '{location}'.")
            if place:
                data["resolved_place"] = place["name"]
            return data

        except WeatherError:
            raise  # definitive answer - do not retry
        except (httpx.HTTPError, ValueError) as exc:  # ValueError covers bad JSON
            last_err = str(exc) or exc.__class__.__name__
            log.warning("Attempt %d failed: %s", attempt, last_err)
            if attempt <= RETRIES:
                time.sleep(1.0 * attempt)  # simple linear back-off

    raise WeatherError(f"Could not reach wttr.in for '{location}': {last_err}")


# --------------------------------------------------------------------------- #
# Pure formatting helpers (offline-testable)
# --------------------------------------------------------------------------- #
def format_current(data: dict, location: str) -> str:
    """Render current conditions from a j1 payload as structured text."""
    cur = _first(data.get("current_condition"))
    today = _first(data.get("weather"))
    astro = _first(today.get("astronomy"))

    # Prefer the local observation timestamp. Otherwise use observation_time,
    # which wttr.in gives in UTC. We leave out weather[0].date on purpose,
    # because that is the *local* date and may be a different day.
    local_obs = _val(cur, "localObsDateTime", "")
    if local_obs:
        observed = f"{local_obs} (local)"
    else:
        observed = f"{_val(cur, 'observation_time')} UTC"

    lines = [
        f"📍 Location: {_resolved_name(data)} (resolved from '{location}')",
        f"🕒 Observed: {observed}",
        f"Condition: {_val(cur, 'weatherDesc')}",
        f"Temperature: {_val(cur, 'temp_C')}°C (feels like {_val(cur, 'FeelsLikeC')}°C)",
        f"Humidity: {_val(cur, 'humidity')}%",
        f"Wind: {_val(cur, 'windspeedKmph')} km/h {_val(cur, 'winddir16Point', '')}".rstrip(),
        f"Precipitation: {_val(cur, 'precipMM')} mm",
        f"Pressure: {_val(cur, 'pressure')} hPa",
        f"Visibility: {_val(cur, 'visibility')} km",
        f"UV index: {_val(cur, 'uvIndex')}",
        (f"Today: min {_val(today, 'mintempC')}°C / max {_val(today, 'maxtempC')}°C, "
         f"sunrise {_val(astro, 'sunrise')}, sunset {_val(astro, 'sunset')}"),
        "Source: wttr.in (live)",
    ]
    return "\n".join(lines)


def _day_condition(day: dict) -> str:
    """Dominant condition of a day = the midday (hourly[4], 12:00) description."""
    hourly = day.get("hourly") or []
    if isinstance(hourly, list) and len(hourly) > 4 and isinstance(hourly[4], dict):
        return _val(hourly[4], "weatherDesc")
    return _val(_first(hourly), "weatherDesc")


def _day_rain_chance(day: dict) -> str:
    """Highest 3-hourly chance of rain for a day, as a string percentage."""
    chances = []
    for h in day.get("hourly") or []:
        try:
            chances.append(int(h.get("chanceofrain", "")))
        except (TypeError, ValueError, AttributeError):
            continue
    return f"{max(chances)}%" if chances else "?"


def format_forecast(data: dict, location: str, days: int) -> str:
    """Render a 1..3 day forecast, one line per day."""
    days = max(1, min(3, int(days)))
    weather = data.get("weather") or []
    header = f"📅 {min(days, len(weather))}-day forecast for {_resolved_name(data)} (resolved from '{location}')"
    lines = [header]
    for day in weather[:days]:
        if not isinstance(day, dict):
            continue
        lines.append(
            f"{_val(day, 'date')}: min {_val(day, 'mintempC')}°C / max {_val(day, 'maxtempC')}°C, "
            f"{_day_condition(day)}, chance of rain {_day_rain_chance(day)}"
        )
    if len(lines) == 1:
        lines.append("No forecast data available.")
    lines.append("Source: wttr.in (live)")
    return "\n".join(lines)


def format_comparison_row(data: dict, location: str) -> list[str]:
    """One table row: [query, resolved, temp, feels, condition, humidity, wind, min/max]."""
    cur = _first(data.get("current_condition"))
    today = _first(data.get("weather"))
    return [
        location,
        _resolved_name(data),
        f"{_val(cur, 'temp_C')}°C",
        f"{_val(cur, 'FeelsLikeC')}°C",
        _val(cur, "weatherDesc"),
        f"{_val(cur, 'humidity')}%",
        f"{_val(cur, 'windspeedKmph')} km/h",
        f"{_val(today, 'mintempC')}/{_val(today, 'maxtempC')}°C",
    ]


def _markdown_table(header: list[str], rows: list[list[str]]) -> str:
    """Tiny markdown table renderer (renders nicely in Streamlit / chat UIs)."""
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# MCP tools (docstrings are what the LLM sees - keep them precise)
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_current_weather(location: str) -> str:
    """Get LIVE current weather for a single location.

    Args:
        location: City name, optionally with country (e.g. "Tokyo",
            "Paris, France", "Bengaluru"). Airport codes (e.g. "JFK") and
            "lat,lon" coordinates also work.

    Returns structured text: resolved location, observation time, condition,
    temperature/feels-like (°C), humidity, wind, precipitation, pressure,
    visibility, UV index, and today's min/max with sunrise/sunset.
    Returns a string starting with "ERROR:" if the lookup fails.
    """
    try:
        return format_current(fetch_wttr(location), location)
    except WeatherError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:  # never let the tool crash the session
        log.exception("Unexpected failure in get_current_weather")
        return f"ERROR: unexpected problem getting weather for '{location}': {exc}"


@mcp.tool()
def get_forecast(location: str, days: int = 3) -> str:
    """Get a daily weather FORECAST (today plus up to 2 more days) for a location.

    Args:
        location: City name, optionally with country (e.g. "Bengaluru", "London, UK").
        days: Number of days, 1-3 (values outside this range are clamped). Default 3.

    Returns one line per day: date, min/max temperature (°C), midday condition,
    and the maximum chance of rain for that day.
    Returns a string starting with "ERROR:" if the lookup fails.
    """
    try:
        days = max(1, min(3, int(days)))
    except (TypeError, ValueError):
        days = 3
    try:
        return format_forecast(fetch_wttr(location), location, days)
    except WeatherError as exc:
        return f"ERROR: {exc}"
    except Exception as exc:
        log.exception("Unexpected failure in get_forecast")
        return f"ERROR: unexpected problem getting forecast for '{location}': {exc}"


@mcp.tool()
def compare_weather(locations: list[str]) -> str:
    """Compare CURRENT weather across 2 to 5 locations in one table.

    Args:
        locations: List of 2-5 city names, e.g. ["Tokyo", "London", "New York"].

    Returns a markdown table with temperature, feels-like, condition, humidity,
    wind speed and today's min/max for each location. Locations that fail are
    listed below the table with an ERROR note; the others are still shown.
    Use this instead of calling get_current_weather repeatedly when the user
    wants a comparison.
    """
    cleaned = [str(l).strip() for l in (locations or []) if str(l).strip()]
    # De-duplicate while keeping order.
    cleaned = list(dict.fromkeys(cleaned))
    if len(cleaned) < 2:
        return "ERROR: compare_weather needs at least 2 distinct locations."
    if len(cleaned) > 5:
        return "ERROR: compare_weather supports at most 5 locations at a time."

    rows: list[list[str]] = []
    errors: list[str] = []
    for loc in cleaned:
        try:
            rows.append(format_comparison_row(fetch_wttr(loc), loc))
        except WeatherError as exc:
            errors.append(f"ERROR: {loc}: {exc}")
        except Exception as exc:
            log.exception("Unexpected failure comparing %s", loc)
            errors.append(f"ERROR: {loc}: unexpected problem: {exc}")

    if not rows:
        return "ERROR: none of the locations could be fetched.\n" + "\n".join(errors)

    header = ["Query", "Resolved", "Temp", "Feels", "Condition", "Humidity", "Wind", "Min/Max"]
    parts = ["🌍 Weather comparison (live)", _markdown_table(header, rows)]
    if errors:
        parts.append("\n".join(errors))
    parts.append("Source: wttr.in (live)")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    log.info("Starting weather-dashboard MCP server (stdio)")
    mcp.run()
