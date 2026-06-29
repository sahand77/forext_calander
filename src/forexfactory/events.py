from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from dateutil.tz import gettz

from .cache_validation import canonicalize_cache_frame
from .incremental import scrape_incremental
from .providers import ForexFactoryHtmlProvider

EVENT_FIELDS = [
    "date",
    "time",
    "datetime_local",
    "datetime_utc",
    "currency",
    "impact",
    "event",
    "actual",
    "forecast",
    "previous",
    "detail",
    "source",
    "source_url",
    "detail_url",
]

DEFAULT_CSV_PATH = os.environ.get("FOREXFACTORY_CSV_PATH", "forex_factory_cache.csv")
DEFAULT_TZ = os.environ.get("FOREXFACTORY_TZ", "Asia/Tehran")
_scrape_lock = threading.Lock()


@dataclass(frozen=True)
class EventQuery:
    start: str | None = None
    end: str | None = None
    currencies: tuple[str, ...] = ()
    impacts: tuple[str, ...] = ()
    search: str | None = None
    limit: int = 100
    offset: int = 0


def load_events(csv_path: str | Path, tzname: str = DEFAULT_TZ) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        return pd.DataFrame(columns=EVENT_FIELDS)
    df = pd.read_csv(path, dtype=str)
    return canonicalize_cache_frame(df, tzname=tzname)


def _parse_date_range(start: str, end: str, tzname: str) -> tuple[datetime, datetime]:
    tz = gettz(tzname)
    if tz is None:
        raise ValueError(f"Unknown timezone: {tzname}")
    from_date = datetime.fromisoformat(start).replace(tzinfo=tz)
    to_date = datetime.fromisoformat(end).replace(tzinfo=tz)
    if to_date < from_date:
        raise ValueError("end must be greater than or equal to start")
    return from_date, to_date


def refresh_cache(
    csv_path: str | Path,
    start: str,
    end: str,
    tzname: str = DEFAULT_TZ,
    impact_filter: list[str] | None = None,
    keep_currencies: list[str] | None = None,
) -> None:
    """Scrape ForexFactory for the requested range and merge results into the CSV cache."""
    from_date, to_date = _parse_date_range(start, end, tzname)
    with _scrape_lock:
        scrape_incremental(
            from_date,
            to_date,
            str(csv_path),
            tzname=tzname,
            scrape_details=True,
            impact_filter=impact_filter,
            keep_currencies=keep_currencies,
            provider=ForexFactoryHtmlProvider(),
        )


def _normalize_filter_values(values: Iterable[str]) -> set[str]:
    return {value.strip().upper() for value in values if value and value.strip()}


def _normalize_impact_values(values: Iterable[str]) -> set[str]:
    return {value.strip().lower() for value in values if value and value.strip()}


def filter_events(df: pd.DataFrame, query: EventQuery) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()

    if query.start:
        start_date = pd.Timestamp(query.start).date()
        filtered = filtered.loc[pd.to_datetime(filtered["date"], errors="coerce").dt.date >= start_date]
    if query.end:
        end_date = pd.Timestamp(query.end).date()
        filtered = filtered.loc[pd.to_datetime(filtered["date"], errors="coerce").dt.date <= end_date]

    currencies = _normalize_filter_values(query.currencies)
    if currencies:
        currency_series = filtered["currency"].fillna("").astype(str).str.strip().str.upper()
        filtered = filtered.loc[currency_series.isin(currencies)]

    impacts = _normalize_impact_values(query.impacts)
    if impacts:
        impact_series = filtered["impact"].fillna("").astype(str).str.strip().str.lower()
        filtered = filtered.loc[impact_series.isin(impacts)]

    if query.search:
        needle = query.search.strip().lower()
        event_series = filtered["event"].fillna("").astype(str).str.lower()
        filtered = filtered.loc[event_series.str.contains(needle, regex=False)]

    filtered = filtered.sort_values(
        by=["datetime_local", "currency", "event"],
        ascending=True,
        kind="mergesort",
    )
    return filtered.reset_index(drop=True)


def frame_to_events(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    rows = []
    for _, row in df.iterrows():
        event = {field: str(row.get(field, "") or "").strip() for field in EVENT_FIELDS}
        rows.append(event)
    return rows


def query_events(df: pd.DataFrame, query: EventQuery) -> tuple[list[dict], int]:
    filtered = filter_events(df, query)
    total = len(filtered)
    page = filtered.iloc[query.offset : query.offset + query.limit]
    return frame_to_events(page), total


def summarize_events(df: pd.DataFrame, query: EventQuery) -> dict:
    filtered = filter_events(df, query)
    if filtered.empty:
        return {
            "total": 0,
            "min_date": None,
            "max_date": None,
            "currencies": {},
            "impacts": {},
        }

    dates = pd.to_datetime(filtered["date"], errors="coerce").dropna()
    return {
        "total": int(len(filtered)),
        "min_date": dates.min().date().isoformat() if not dates.empty else None,
        "max_date": dates.max().date().isoformat() if not dates.empty else None,
        "currencies": filtered["currency"].fillna("").astype(str).str.strip().replace("", "<NA>").value_counts().to_dict(),
        "impacts": filtered["impact"].fillna("").astype(str).str.strip().replace("", "<NA>").value_counts().to_dict(),
    }
