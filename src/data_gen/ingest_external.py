"""Descarga datos externos reales: clima histórico (Open-Meteo) y feriados (Nager.Date).

Ambas APIs son gratuitas y no requieren API key.

    python -m src.data_gen.ingest_external --out data/raw --start 2025-01-01 --end 2025-12-31

Escribe:
    <out>/weather/city=<ciudad>/weather.json
    <out>/holidays/country=<XX>/<año>.json

Luego pasar --weather-dir data/raw/weather --holidays-dir data/raw/holidays a generate.py
para que la demanda simulada responda al clima y feriados reales.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from src.data_gen import config as cfg

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
NAGER = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"


def weather_url(lat: float, lon: float, start: dt.date, end: dt.date) -> str:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "temperature_2m_mean,temperature_2m_max,precipitation_sum",
        "timezone": "auto",
    }
    return f"{OPEN_METEO}?{urllib.parse.urlencode(params)}"


def fetch_json(url: str, retries: int = 3) -> object:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("data/raw"))
    p.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2025, 1, 1))
    p.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2025, 12, 31))
    a = p.parse_args()

    for country, (_, _, cities) in cfg.COUNTRIES.items():
        for city, lat, lon in cities:
            data = fetch_json(weather_url(lat, lon, a.start, a.end))
            f = a.out / "weather" / f"city={city}" / "weather.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"city": city, "country": country, **data}))
            print(f"clima ok: {city}")
        for year in range(a.start.year, a.end.year + 1):
            data = fetch_json(NAGER.format(year=year, country=country))
            f = a.out / "holidays" / f"country={country}" / f"{year}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data))
            print(f"feriados ok: {country} {year}")


if __name__ == "__main__":
    main()
