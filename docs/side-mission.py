#!/usr/bin/env python3
"""
Fetch June 19-21 historical weather for Mayne Island (2015-2025).
Uses Environment Canada GeoMet (North Pender Island station) first,
Open-Meteo as fallback. Writes results to CSV.
"""

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

# Config
OUTPUT_PATH = Path(__file__).resolve().parent / "mayne_weather_june19-21.csv"
YEARS = range(2015, 2026)  # 2015..2025
JUNE_DAYS = (19, 20, 21)
EC_STATION_ID = "1015638"
EC_BASE = "https://api.weather.gc.ca/collections/climate-daily/items"
OPENMETEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
MAYNE_LAT, MAYNE_LON = 48.85, -123.30
RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_TIMEOUT = 15


def fetch_ec(year: int, month: int, day: int) -> dict | None:
    """Fetch one day from Environment Canada GeoMet. Returns feature props or None."""
    params = f"CLIMATE_IDENTIFIER={EC_STATION_ID}&LOCAL_YEAR={year}&LOCAL_MONTH={month}&LOCAL_DAY={day}&f=json&limit=1"
    url = f"{EC_BASE}?{params}"
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            if attempt < RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
        features = data.get("features", [])
        if features:
            return features[0].get("properties")
        return None


def fetch_openmeteo(year: int, month: int, day: int) -> dict | None:
    """Fetch one day from Open-Meteo archive for Mayne Island. Returns normalized row dict."""
    date_str = f"{year}-{month:02d}-{day:02d}"
    params = (
        f"latitude={MAYNE_LAT}&longitude={MAYNE_LON}"
        f"&start_date={date_str}&end_date={date_str}"
        f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,snowfall_sum"
        f"&timezone=America/Vancouver"
    )
    url = f"{OPENMETEO_ARCHIVE}?{params}"
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            if attempt < RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
        daily = data.get("daily", {})
        times = daily.get("time", [])
        if not times:
            return None
        return {
            "source": "Open-Meteo",
            "station_name": "Mayne Island (reanalysis)",
            "climate_identifier": "",
            "date": date_str,
            "year": year,
            "month": month,
            "day": day,
            "min_temp": daily.get("temperature_2m_min", [None])[0],
            "mean_temp": daily.get("temperature_2m_mean", [None])[0],
            "max_temp": daily.get("temperature_2m_max", [None])[0],
            "total_precip_mm": daily.get("precipitation_sum", [None])[0],
            "total_rain_mm": daily.get("rain_sum", [None])[0],
            "total_snow_cm": daily.get("snowfall_sum", [None])[0],
        }


def props_to_row(props: dict, source: str = "Environment Canada") -> dict:
    """Convert EC feature properties to normalized row dict."""
    return {
        "source": source,
        "station_name": props.get("STATION_NAME", ""),
        "climate_identifier": props.get("CLIMATE_IDENTIFIER", ""),
        "date": f"{props.get('LOCAL_YEAR')}-{props.get('LOCAL_MONTH', 0):02d}-{props.get('LOCAL_DAY', 0):02d}",
        "year": props.get("LOCAL_YEAR"),
        "month": props.get("LOCAL_MONTH"),
        "day": props.get("LOCAL_DAY"),
        "min_temp": props.get("MIN_TEMPERATURE"),
        "mean_temp": props.get("MEAN_TEMPERATURE"),
        "max_temp": props.get("MAX_TEMPERATURE"),
        "total_precip_mm": props.get("TOTAL_PRECIPITATION"),
        "total_rain_mm": props.get("TOTAL_RAIN"),
        "total_snow_cm": props.get("TOTAL_SNOW"),
    }


def main() -> None:
    rows: list[dict] = []
    missing: list[str] = []
    used_fallback: list[str] = []

    for year in YEARS:
        for day in JUNE_DAYS:
            date_key = f"{year}-06-{day:02d}"
            props = fetch_ec(year, 6, day)
            if props:
                rows.append(props_to_row(props))
            else:
                fallback = fetch_openmeteo(year, 6, day)
                if fallback:
                    rows.append(fallback)
                    used_fallback.append(date_key)
                else:
                    missing.append(date_key)
            time.sleep(0.2)

    fieldnames = [
        "source", "station_name", "climate_identifier", "date", "year", "month", "day",
        "min_temp", "mean_temp", "max_temp", "total_precip_mm", "total_rain_mm", "total_snow_cm",
    ]
    rows.sort(key=lambda r: (r["year"], r["month"], r["day"]))

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Rows written: {len(rows)}")
    if missing:
        print(f"Missing dates: {missing}")
    if used_fallback:
        print(f"Fallback used for: {used_fallback}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
