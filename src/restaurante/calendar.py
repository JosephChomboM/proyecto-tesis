"""Dated Peruvian context shared by operations; no automatic holiday demand uplift."""

from datetime import date

import pandas as pd

from .research.calendar import HOLIDAY_SOURCES, national_holidays

CALENDAR_SOURCES = HOLIDAY_SOURCES | {
    2026: "https://elperuano.pe/noticia/286039-fin-de-semana-largo-el-2-de-enero-del-2026-sera-dia-no-laborable",
}
EVENT_KINDS = {"promotion": "Promoción", "reservation": "Reserva grande",
               "closure": "Cierre excepcional", "holiday": "Feriado local declarado",
               "other": "Otro evento"}
CONTEXT_FEATURES = ("is_holiday", "calendar_known", "promotion", "reservation", "other")


def holidays_for_year(year):
    if year in HOLIDAY_SOURCES:
        return {day.date(): name for day, name in national_holidays().items() if day.year == year}
    if year == 2026:
        # Fixed holidays follow the 2025 list; Holy Week moves to April 2/3 in 2026.
        holidays = {date(year, day.month, day.day): name for day, name in national_holidays().items()
                    if day.year == 2025 and name not in {"Jueves Santo", "Viernes Santo"}}
        return holidays | {date(2026, 4, 2): "Jueves Santo", date(2026, 4, 3): "Viernes Santo"}
    return {}


def daily_context(dates, events=None, as_of=None):
    """Reconstruct only event revisions registered by the forecast's issue date.

    Historical annotations can train today's model, but cannot leak back into an
    evaluation origin before they were registered. The latest revision wins.
    """
    dates = [pd.Timestamp(day).date() for day in dates]
    latest = {}
    if events is not None and not events.empty:
        required = {"id", "day", "kind", "name", "recorded_on"}
        if not required <= set(events):
            raise ValueError("Los eventos necesitan id, day, kind, name y recorded_on.")
        frame = events.copy()
        frame["day"] = pd.to_datetime(frame.day, errors="raise").dt.date
        frame["recorded_on"] = pd.to_datetime(frame.recorded_on, errors="raise").dt.date
        if frame[["day", "recorded_on"]].isna().any().any() or not frame.kind.isin([*EVENT_KINDS, "cancelled"]).all():
            raise ValueError("Hay fechas o tipos de evento inválidos.")
        if as_of is not None:
            frame = frame[frame.recorded_on <= pd.Timestamp(as_of).date()]
        for record in frame.sort_values("id").to_dict("records"):
            latest[record["day"]] = record
    holidays = {year: holidays_for_year(year) for year in {day.year for day in dates}}
    rows = []
    for day in dates:
        holiday = holidays[day.year].get(day, "")
        event = latest.get(day, {})
        kind = event.get("kind", "")
        if kind == "cancelled":
            kind, event = "", {}
        local_holiday = kind == "holiday"
        rows.append({"date": day, "is_holiday": bool(holiday or local_holiday),
                     "holiday_name": holiday or (event.get("name", "") if local_holiday else ""),
                     "calendar_known": day.year in CALENDAR_SOURCES,
                     "calendar_source": CALENDAR_SOURCES.get(day.year, "Sin calendario nacional verificado"),
                     "event_type": kind, "event_name": event.get("name", ""),
                     "event_recorded_on": event.get("recorded_on", ""),
                     "forced_closed": kind == "closure",
                     "promotion": kind == "promotion", "reservation": kind == "reservation",
                     "other": kind == "other"})
    return pd.DataFrame(rows)
