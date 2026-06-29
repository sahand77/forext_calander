# ForexFactory Calendar Scraper

Scrape ForexFactory economic calendar events and serve them over HTTP. Each API request fetches the requested date range from ForexFactory, updates a local CSV cache, and returns the result.

Does not bypass Cloudflare, CAPTCHA, or other security checks.

## Setup (without Docker)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.forexfactory.api --host 127.0.0.1 --port 8000
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs

## Setup (with Docker)

```powershell
docker compose up --build
```

Cache is stored in `./data/forex_factory_cache.csv` (created on first scrape).

Without Compose:

```powershell
docker build -t forexfactory-scraper .
docker run --rm -p 8000:8000 -v "${PWD}/data:/data" forexfactory-scraper
```

## API

| Endpoint | Scrapes? | Description |
|----------|----------|-------------|
| `GET /health` | No | Service status and cache row count |
| `GET /events` | Yes | Scrape date range, return events |
| `GET /events/summary` | Yes | Scrape date range, return counts |

### Parameters

**Required** (`/events`, `/events/summary`):

| Param | Example | Description |
|-------|---------|-------------|
| `start` | `2026-06-23` | Inclusive start date (`YYYY-MM-DD`) |
| `end` | `2026-06-29` | Inclusive end date (`YYYY-MM-DD`) |

**Optional**:

| Param | Example | Description |
|-------|---------|-------------|
| `currency` | `USD`, `EUR` | Repeat for multiple currencies |
| `impact` | `high`, `medium` | Repeat for multiple impact levels |
| `search` | `GDP` | Case-insensitive event name filter |
| `limit` | `50` | Page size for `/events` (default `100`, max `1000`) |
| `offset` | `0` | Pagination offset for `/events` |

### Examples

Health check:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health"
```

All options on `/events`:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/events?start=2026-06-23&end=2026-06-29&currency=USD&currency=EUR&impact=high&impact=medium&search=GDP&limit=50&offset=0"
```

Summary with filters:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/events/summary?start=2026-06-23&end=2026-06-29&currency=USD&impact=high&search=GDP"
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FOREXFACTORY_CSV_PATH` | `forex_factory_cache.csv` | Cache file path |
| `FOREXFACTORY_TZ` | `Asia/Tehran` | Timezone for event times |
| `FOREXFACTORY_API_HOST` | `127.0.0.1` | API bind host |
| `FOREXFACTORY_API_PORT` | `8000` | API bind port |

## CLI scraper (optional)

For batch updates without the API:

```powershell
python -m src.forexfactory.main `
  --start 2026-06-23 `
  --end 2026-06-29 `
  --csv forex_factory_cache.csv `
  --tz Asia/Tehran `
  --details
```

Validate cache:

```powershell
python scripts/validate_cache.py --csv forex_factory_cache.csv --start 2026-06-23 --end 2026-06-29
```

## Development

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```
