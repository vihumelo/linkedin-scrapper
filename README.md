# LinkedIn Scrapper

A FastAPI service for LinkedIn job search and structured job details. It parses LinkedIn HTML and
caches complete job details in SQLite.

## Setup

Requires Python 3.12+.

```bash
git clone https://github.com/<your-account>/linkedin-scrapper.git
cd linkedin-scrapper
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` in `.env` to enable authenticated search. Keep these
credentials private; never commit `.env`.

Start the API:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Docs: <http://127.0.0.1:8000/docs>

## Endpoints

### Search jobs

`GET /api/jobs/search` always fetches fresh results from LinkedIn.

```bash
curl -G "http://127.0.0.1:8000/api/jobs/search" \
  --data-urlencode "keywords=biomedicina" \
  --data-urlencode "start=0"
```

Optional parameters: `geo_id` (default `106057199`) and `start` (default `0`). The response
contains `query`, `pagination`, and `jobs`.

### Job details

`GET /api/jobs/{job_id}` checks the cache before requesting LinkedIn. IDs must use ASCII digits.

```bash
curl "http://127.0.0.1:8000/api/jobs/4486249045"
curl "http://127.0.0.1:8000/api/jobs/4486249045?refresh=true"
```

The second request bypasses the cache and refreshes it after a successful fetch. Cached records do
not expire. A job is cached only when `id`, `title`, `company`, `url`, and `description_text` are
present. Cache failures fall back to LinkedIn.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `LINKEDIN_LI_AT`, `LINKEDIN_JSESSIONID` | empty | Cookies for authenticated search |
| `LINKEDIN_USER_AGENT` | Chrome user agent | LinkedIn request header |
| `HTTP_TIMEOUT_SECONDS` | `30` | Upstream timeout |
| `CACHE_BACKEND` | `sqlite` | Cache adapter |
| `CACHE_SQLITE_PATH` | `./data/jobs_cache.db` | Local cache database |

The database is created automatically and is excluded from Git.

## Tests

```bash
pytest -q
ruff check app tests
ruff format --check app tests
```

Online tests are opt-in and call LinkedIn:

```bash
RUN_LINKEDIN_INTEGRATION=1 pytest tests/integration/test_linkedin_search.py
RUN_LINKEDIN_JOB_DETAILS_INTEGRATION=1 pytest tests/integration/test_linkedin_job_details.py
```
