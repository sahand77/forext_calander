from __future__ import annotations

import argparse
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from .events import (
    DEFAULT_CSV_PATH,
    DEFAULT_TZ,
    EventQuery,
    load_events,
    query_events,
    refresh_cache,
    summarize_events,
)
from .providers import ProviderError

app = FastAPI(
    title="ForexFactory Events API",
    description="Scrape ForexFactory for the requested date range, update the local cache, and return events.",
    version="1.0.0",
)


class Event(BaseModel):
    date: str = ""
    time: str = ""
    datetime_local: str = ""
    datetime_utc: str = ""
    currency: str = ""
    impact: str = ""
    event: str = ""
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    detail: str = ""
    source: str = ""
    source_url: str = ""
    detail_url: str = ""


class EventsResponse(BaseModel):
    start: str
    end: str
    total: int
    limit: int
    offset: int
    events: list[Event]


class SummaryResponse(BaseModel):
    start: str
    end: str
    total: int
    min_date: str | None
    max_date: str | None
    currencies: dict[str, int]
    impacts: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    csv_path: str
    timezone: str
    cached_events: int


class ApiSettings:
    def __init__(self, csv_path: str | None = None, tzname: str | None = None):
        self.csv_path = csv_path or DEFAULT_CSV_PATH
        self.tzname = tzname or DEFAULT_TZ


def get_settings() -> ApiSettings:
    return ApiSettings()


def _build_event_query(
    start: str,
    end: str,
    currency: list[str] | None,
    impact: list[str] | None,
    search: str | None,
    limit: int,
    offset: int,
) -> EventQuery:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be greater than or equal to 0")
    return EventQuery(
        start=start,
        end=end,
        currencies=tuple(currency or ()),
        impacts=tuple(impact or ()),
        search=search,
        limit=limit,
        offset=offset,
    )


def _scrape_and_load(
    settings: ApiSettings,
    start: str,
    end: str,
    currency: list[str] | None,
    impact: list[str] | None,
):
    impact_filter = [value.strip().lower() for value in impact or () if value.strip()]
    try:
        refresh_cache(
            settings.csv_path,
            start,
            end,
            tzname=settings.tzname,
            impact_filter=impact_filter or None,
            keep_currencies=currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return load_events(settings.csv_path, tzname=settings.tzname)


@app.get("/health", response_model=HealthResponse)
def health(settings: Annotated[ApiSettings, Depends(get_settings)]):
    df = load_events(settings.csv_path, tzname=settings.tzname)
    return HealthResponse(
        status="ok",
        csv_path=settings.csv_path,
        timezone=settings.tzname,
        cached_events=len(df),
    )


@app.get("/events", response_model=EventsResponse)
def list_events(
    settings: Annotated[ApiSettings, Depends(get_settings)],
    start: Annotated[str, Query(description="Inclusive start date (YYYY-MM-DD)")],
    end: Annotated[str, Query(description="Inclusive end date (YYYY-MM-DD)")],
    currency: Annotated[list[str] | None, Query(description="Filter by currency codes (repeatable)")] = None,
    impact: Annotated[list[str] | None, Query(description="Filter by impact levels (repeatable)")] = None,
    search: Annotated[str | None, Query(description="Case-insensitive substring match on event name")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = _build_event_query(start, end, currency, impact, search, limit, offset)
    df = _scrape_and_load(settings, start, end, currency, impact)
    events, total = query_events(df, query)
    return EventsResponse(
        start=start,
        end=end,
        total=total,
        limit=limit,
        offset=offset,
        events=[Event(**event) for event in events],
    )


@app.get("/events/summary", response_model=SummaryResponse)
def events_summary(
    settings: Annotated[ApiSettings, Depends(get_settings)],
    start: Annotated[str, Query(description="Inclusive start date (YYYY-MM-DD)")],
    end: Annotated[str, Query(description="Inclusive end date (YYYY-MM-DD)")],
    currency: Annotated[list[str] | None, Query(description="Filter by currency codes (repeatable)")] = None,
    impact: Annotated[list[str] | None, Query(description="Filter by impact levels (repeatable)")] = None,
    search: Annotated[str | None, Query(description="Case-insensitive substring match on event name")] = None,
):
    query = EventQuery(
        start=start,
        end=end,
        currencies=tuple(currency or ()),
        impacts=tuple(impact or ()),
        search=search,
    )
    df = _scrape_and_load(settings, start, end, currency, impact)
    summary = summarize_events(df, query)
    return SummaryResponse(start=start, end=end, **summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ForexFactory events API server")
    parser.add_argument("--host", default=os.environ.get("FOREXFACTORY_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FOREXFACTORY_API_PORT", "8000")))
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the events CSV cache")
    parser.add_argument("--tz", default=DEFAULT_TZ, help="Timezone used when canonicalizing legacy rows")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    return parser


def main(argv: list[str] | None = None):
    import uvicorn

    args = build_parser().parse_args(argv)
    os.environ["FOREXFACTORY_CSV_PATH"] = args.csv
    os.environ["FOREXFACTORY_TZ"] = args.tz
    uvicorn.run(
        "src.forexfactory.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
