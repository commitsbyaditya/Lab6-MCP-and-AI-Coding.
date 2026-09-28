"""Tests for expt2_weather_dashboard/weather_server.py.

* Offline tests use the saved wttr.in fixture (tests/fixtures/wttr_tokyo.json)
  and monkeypatch `fetch_wttr` (or `httpx.get` for the geocoding and
  `fetch_wttr` tests), so they never touch the network.
* One end-to-end test spawns the server over stdio and lists its tools.
* One LIVE test (marked `live`) hits the real wttr.in and is skipped
  automatically if the network is unavailable.  Deselect with `-m "not live"`.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

LAB6 = Path(__file__).resolve().parent.parent
SERVER_PATH = LAB6 / "expt2_weather_dashboard" / "weather_server.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "wttr_tokyo.json"

DATE_LINE = re.compile(r"^\d{4}-\d{2}-\d{2}:", re.MULTILINE)


def _load_server_module():
    spec = importlib.util.spec_from_file_location("weather_server_under_test", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = _load_server_module()


@pytest.fixture
def tokyo_data():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def offline(monkeypatch, tokyo_data):
    """Make fetch_wttr return the fixture for any location (records calls)."""
    calls = []

    def fake_fetch(location):
        calls.append(location)
        return tokyo_data

    monkeypatch.setattr(ws, "fetch_wttr", fake_fetch)
    return calls


def _area_name(data):
    return data["nearest_area"][0]["areaName"][0]["value"]


# --------------------------------------------------------------------------- #
# Offline: formatting helpers
# --------------------------------------------------------------------------- #
def test_fixture_is_valid_j1(tokyo_data):
    assert tokyo_data["current_condition"]
    assert len(tokyo_data["weather"]) >= 3


def test_format_current_contains_key_fields(tokyo_data):
    text = ws.format_current(tokyo_data, "Tokyo")
    cur = tokyo_data["current_condition"][0]
    assert "Temperature:" in text
    assert "Humidity:" in text
    assert "Condition:" in text
    assert f"Temperature: {cur['temp_C']}°C (feels like {cur['FeelsLikeC']}°C)" in text
    assert f"Humidity: {cur['humidity']}%" in text
    assert cur["weatherDesc"][0]["value"].strip() in text
    # The resolved Tokyo-area name from the fixture and the original query both appear.
    assert _area_name(tokyo_data) in text
    assert "Tokyo" in text


@pytest.mark.parametrize("days, expected", [(10, 3), (3, 3), (2, 2), (1, 1), (0, 1), (-5, 1)])
def test_format_forecast_clamps_days(tokyo_data, days, expected):
    text = ws.format_forecast(tokyo_data, "Tokyo", days)
    assert len(DATE_LINE.findall(text)) == expected, text


def test_format_forecast_uses_fixture_dates(tokyo_data):
    text = ws.format_forecast(tokyo_data, "Tokyo", 3)
    for day in tokyo_data["weather"][:3]:
        assert day["date"] in text


# --------------------------------------------------------------------------- #
# Offline: tools (fetch_wttr monkeypatched)
# --------------------------------------------------------------------------- #
def test_get_current_weather_offline(offline, tokyo_data):
    text = ws.get_current_weather("Tokyo")
    assert not text.startswith("ERROR")
    assert "Temperature:" in text and _area_name(tokyo_data) in text
    assert offline == ["Tokyo"]


@pytest.mark.parametrize("days, expected", [(10, 3), (0, 1), (2, 2)])
def test_get_forecast_tool_clamps_days(offline, days, expected):
    text = ws.get_forecast("Tokyo", days=days)
    assert not text.startswith("ERROR")
    assert len(DATE_LINE.findall(text)) == expected, text


def test_get_current_weather_returns_error_string(monkeypatch):
    def boom(location):
        raise ws.WeatherError("Unknown location: 'Atlantis'.")

    monkeypatch.setattr(ws, "fetch_wttr", boom)
    text = ws.get_current_weather("Atlantis")
    assert text.startswith("ERROR:")
    assert "Atlantis" in text


def test_get_forecast_returns_error_string(monkeypatch):
    def boom(location):
        raise ws.WeatherError("network down")

    monkeypatch.setattr(ws, "fetch_wttr", boom)
    assert ws.get_forecast("Tokyo", 2).startswith("ERROR:")


def test_compare_weather_two_cities(offline, tokyo_data):
    text = ws.compare_weather(["Tokyo", "Osaka"])
    assert not text.startswith("ERROR")
    assert offline == ["Tokyo", "Osaka"]
    assert "Tokyo" in text and "Osaka" in text
    temp = tokyo_data["current_condition"][0]["temp_C"]
    assert text.count(f"{temp}°C") >= 2  # one row per city


def test_compare_weather_partial_failure(monkeypatch, tokyo_data):
    def fetch(location):
        if location == "Atlantis":
            raise ws.WeatherError("Unknown location: 'Atlantis'.")
        return tokyo_data

    monkeypatch.setattr(ws, "fetch_wttr", fetch)
    text = ws.compare_weather(["Tokyo", "Atlantis"])
    assert "Tokyo" in text
    assert "ERROR: Atlantis" in text


def test_compare_weather_needs_two_locations(offline):
    assert ws.compare_weather(["Tokyo"]).startswith("ERROR:")
    assert offline == []


def test_fetch_wttr_rejects_empty_location():
    with pytest.raises(ws.WeatherError):
        ws.fetch_wttr("   ")


# --------------------------------------------------------------------------- #
# Offline: geocoding + fetch_wttr (httpx.get monkeypatched)
# --------------------------------------------------------------------------- #
GEO_RESULTS = {"results": [
    {"name": "London", "admin1": "England", "country": "United Kingdom",
     "country_code": "GB", "latitude": 51.50853, "longitude": -0.12574},
    {"name": "London", "admin1": "Ontario", "country": "Canada",
     "country_code": "CA", "latitude": 42.98339, "longitude": -81.23304},
]}


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)
        self.request = None

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ws.httpx.HTTPStatusError("boom", request=None, response=None)


@pytest.fixture
def fake_http(monkeypatch, tokyo_data):
    """Serve GEO_RESULTS for the geocoder and the fixture for wttr.in."""
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        if url == ws.GEOCODE_URL:
            return _FakeResp(GEO_RESULTS)
        return _FakeResp(json.loads(json.dumps(tokyo_data)))

    monkeypatch.setattr(ws.httpx, "get", fake_get)
    return urls


def test_geocode_prefers_top_ranked_match(fake_http):
    place = ws.geocode("London")
    assert place["name"] == "London, England, United Kingdom"
    assert (place["lat"], place["lon"]) == (51.50853, -0.12574)


def test_geocode_uses_qualifier_after_comma(fake_http):
    assert ws.geocode("London, Ontario")["name"] == "London, Ontario, Canada"
    assert ws.geocode("London, Narnia") is None


@pytest.mark.parametrize("raw", ["35.68,139.69", "-33.9, 151.2", "JFK", "~Eiffel Tower"])
def test_geocode_passes_through_wttr_native_inputs(fake_http, raw):
    assert ws.geocode(raw) is None
    assert fake_http == []  # no network call at all


def test_fetch_wttr_queries_coordinates_and_names_place(fake_http):
    data = ws.fetch_wttr("London")
    assert fake_http[-1] == "https://wttr.in/51.5085%2C-0.1257?format=j1"
    assert data["resolved_place"] == "London, England, United Kingdom"
    assert "London, England, United Kingdom (resolved from 'London')" in ws.format_current(data, "London")


def test_fetch_wttr_falls_back_to_raw_name_if_geocoder_fails(monkeypatch, tokyo_data):
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        if url == ws.GEOCODE_URL:
            raise ws.httpx.ConnectError("geocoder down")
        return _FakeResp(tokyo_data)

    monkeypatch.setattr(ws.httpx, "get", fake_get)
    data = ws.fetch_wttr("Tokyo")
    assert urls[-1] == "https://wttr.in/Tokyo?format=j1"
    assert "resolved_place" not in data


# --------------------------------------------------------------------------- #
# End-to-end over stdio
# --------------------------------------------------------------------------- #
async def test_stdio_server_lists_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"get_current_weather", "get_forecast", "compare_weather"} <= names
            fc = next(t for t in tools.tools if t.name == "get_forecast")
            assert "days" in fc.inputSchema.get("properties", {})


# --------------------------------------------------------------------------- #
# LIVE: real wttr.in
# --------------------------------------------------------------------------- #
@pytest.mark.live
def test_live_wttr_tokyo():
    try:
        data = ws.fetch_wttr("Tokyo")
    except ws.WeatherError as exc:
        pytest.skip(f"wttr.in unreachable: {exc}")
    text = ws.format_current(data, "Tokyo")
    assert "Location: Tokyo, Japan" in text, text  # not an outlying island
    assert "Temperature:" in text
    assert "Humidity:" in text
    assert re.search(r"Temperature: -?\d+°C", text), text
