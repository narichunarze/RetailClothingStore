"""Efectos de calendario y clima sobre la demanda (temporadas, fechas comerciales, temperatura)."""

from __future__ import annotations

import datetime as dt
import math


def nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """n-ésimo `weekday` (lunes=0) del mes."""
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def commercial_events(year: int, country: str) -> dict[dt.date, float]:
    """Fechas comerciales con su multiplicador de demanda (aplicado en una ventana de días)."""
    events: dict[dt.date, float] = {}

    def window(center: dt.date, before: int, after: int, peak: float) -> None:
        for k in range(-before, after + 1):
            d = center + dt.timedelta(days=k)
            # decae linealmente al alejarse del día central
            f = 1 + (peak - 1) * (1 - abs(k) / (max(before, after) + 1))
            events[d] = max(events.get(d, 1.0), f)

    mothers_day = dt.date(year, 5, 10) if country == "MX" else nth_weekday(year, 5, 6, 2)
    window(mothers_day, 6, 0, 1.8)
    black_friday = nth_weekday(year, 11, 4, 4)
    window(black_friday, 0, 3, 2.6)  # Black Friday + fin de semana + Cyber Monday
    for k in range(10, 25):  # campaña navideña 10–24 dic, pico el 23
        d = dt.date(year, 12, k)
        events[d] = 1.3 + 1.2 * (k - 10) / 14
    return events


def season_of(date: dt.date, hemisphere: str) -> str:
    """'summer' | 'winter' | 'mid' según mes y hemisferio."""
    m = date.month
    if hemisphere == "EQ":
        return "mid"
    north_summer = m in (5, 6, 7, 8)
    north_winter = m in (11, 12, 1, 2)
    if hemisphere == "N":
        return "summer" if north_summer else "winter" if north_winter else "mid"
    return "winter" if north_summer else "summer" if north_winter else "mid"


def season_factor(category_season: str, date: dt.date, hemisphere: str) -> float:
    if category_season == "all":
        return 1.0
    s = season_of(date, hemisphere)
    if s == "mid":
        return 0.8
    return 1.6 if s == category_season else 0.35


def synthetic_temperature(date: dt.date, lat: float) -> float:
    """Temperatura media diaria aproximada (°C) si no hay datos reales de Open-Meteo."""
    doy = date.timetuple().tm_yday
    amplitude = min(abs(lat) / 3.5, 9.0)
    phase = 0 if lat < 0 else math.pi  # sur: máximo en enero; norte: máximo en julio
    base = 27 - abs(lat) * 0.35
    return base + amplitude * math.cos(2 * math.pi * (doy - 15) / 365 + phase)


def temperature_factor(category_season: str, temp_c: float) -> float:
    """Más calor → más polos/shorts; más frío → más casacas/chompas."""
    if category_season == "summer":
        return max(0.5, min(1.6, 1 + (temp_c - 20) * 0.04))
    if category_season == "winter":
        return max(0.5, min(1.8, 1 + (16 - temp_c) * 0.06))
    return 1.0


def markdown_pct(category_season: str, date: dt.date, hemisphere: str) -> float:
    """Descuento de liquidación: últimas semanas de la temporada de la categoría."""
    if category_season == "all" or hemisphere == "EQ":
        return 0.0
    m, d = date.month, date.day
    # fin de verano sur = feb–mar; fin de invierno sur = ago–sep (al revés en el norte)
    south_end = {"summer": (2, 3), "winter": (8, 9)}[category_season]
    north_end = {"summer": (8, 9), "winter": (2, 3)}[category_season]
    end_months = south_end if hemisphere == "S" else north_end
    if m == end_months[0] and d >= 15:
        return 0.3
    if m == end_months[1]:
        return 0.5
    return 0.0
