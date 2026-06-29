import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.forexfactory.api import ApiSettings, app, get_settings
from src.forexfactory.events import EventQuery, filter_events, load_events, query_events, summarize_events


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "date": "2026-06-23",
            "time": "01:00:00",
            "datetime_local": "2026-06-23T01:00:00+04:30",
            "datetime_utc": "2026-06-22T20:30:00+00:00",
            "currency": "AUD",
            "impact": "Low",
            "event": "Flash Manufacturing PMI",
            "actual": "51.2",
            "forecast": "",
            "previous": "50.7",
            "detail": "",
            "source": "forexfactory-html",
            "source_url": "https://example.test/week1",
            "detail_url": "https://example.test/week1",
        },
        {
            "date": "2026-06-24",
            "time": "15:30:00",
            "datetime_local": "2026-06-24T15:30:00+04:30",
            "datetime_utc": "2026-06-24T11:00:00+00:00",
            "currency": "USD",
            "impact": "High",
            "event": "Core PCE Price Index m/m",
            "actual": "0.2%",
            "forecast": "0.3%",
            "previous": "0.1%",
            "detail": "",
            "source": "forexfactory-html",
            "source_url": "https://example.test/week1",
            "detail_url": "https://example.test/week1",
        },
        {
            "date": "2026-06-25",
            "time": "10:00:00",
            "datetime_local": "2026-06-25T10:00:00+04:30",
            "datetime_utc": "2026-06-25T05:30:00+00:00",
            "currency": "EUR",
            "impact": "Medium",
            "event": "German Ifo Business Climate",
            "actual": "88.4",
            "forecast": "89.0",
            "previous": "89.2",
            "detail": "",
            "source": "forexfactory-html",
            "source_url": "https://example.test/week2",
            "detail_url": "https://example.test/week2",
        },
    ])


@pytest.fixture
def sample_csv(tmp_path, sample_df):
    csv_path = tmp_path / "events.csv"
    sample_df.to_csv(csv_path, index=False)
    return csv_path


def test_filter_events_by_date_currency_and_impact(sample_df):
    query = EventQuery(start="2026-06-24", end="2026-06-25", currencies=("USD",), impacts=("high",))
    filtered = filter_events(sample_df, query)

    assert len(filtered) == 1
    assert filtered.iloc[0]["event"] == "Core PCE Price Index m/m"


def test_query_events_pagination(sample_df):
    events, total = query_events(sample_df, EventQuery(limit=1, offset=1))

    assert total == 3
    assert len(events) == 1
    assert events[0]["currency"] == "USD"


def test_summarize_events(sample_df):
    summary = summarize_events(sample_df, EventQuery())

    assert summary["total"] == 3
    assert summary["min_date"] == "2026-06-23"
    assert summary["max_date"] == "2026-06-25"
    assert summary["currencies"]["USD"] == 1


def test_load_events_from_csv(sample_csv):
    df = load_events(sample_csv)

    assert len(df) == 3
    assert df.iloc[0]["currency"] == "AUD"


def test_api_health_and_events(sample_csv, monkeypatch):
    monkeypatch.setattr("src.forexfactory.api.refresh_cache", lambda *args, **kwargs: None)
    app.dependency_overrides[get_settings] = lambda: ApiSettings(csv_path=str(sample_csv), tzname="Asia/Tehran")
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["cached_events"] == 3

    response = client.get(
        "/events",
        params={"start": "2026-06-23", "end": "2026-06-25", "currency": "EUR", "impact": "medium"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["event"] == "German Ifo Business Climate"

    summary = client.get("/events/summary", params={"start": "2026-06-23", "end": "2026-06-24"})
    assert summary.status_code == 200
    assert summary.json()["total"] == 2

    missing_dates = client.get("/events")
    assert missing_dates.status_code == 422

    app.dependency_overrides.clear()
