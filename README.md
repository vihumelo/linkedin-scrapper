# LinkedIn Scrapper

A FastAPI service for LinkedIn job search, company search, and structured job details. It parses
LinkedIn search HTML and authenticated Voyager JSON, and caches complete job details in SQLite.

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

Set `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` in `.env` to enable authenticated search and job
details. Keep these credentials private; never commit `.env`.

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
  --data-urlencode "keywords=biomedical science" \
  --data-urlencode "geo_id=90009574" \
  --data-urlencode "f_TPR=r86400" \
  --data-urlencode "start=0"
```

Search by a LinkedIn company ID without a keyword:

```bash
curl -G "http://127.0.0.1:8000/api/jobs/search" \
  --data-urlencode "company_id=1185"
```

Optional parameters: `geo_id` (default `90009574`, Greater São Paulo Area), `f_TPR` (default
`r2592000`, past 30 days), and `start` (default `0`). The supported `f_TPR` values are `r86400`
(past 24 hours), `r604800` (past week), and `r2592000` (past 30 days). The response contains
`query`, `pagination`, and `jobs`, including the applied `f_tpr` value in `query`.
At least one of `keywords` or `company_id` is required; both may be combined. For company-only
searches, the LinkedIn request uses `keywords=jobs` internally with the company filter. The API
response keeps `query.keywords` as `null` and reports the supplied `company_id`.

The search HTML parser recognizes English and Brazilian Portuguese interface labels. Other LinkedIn
interface languages are not explicitly supported and may affect empty-state, pagination, or job-card
status detection.

### Search companies

`GET /api/companies/search` finds LinkedIn companies by name through the authenticated Voyager API.
Use a returned `id` as `company_id` in `/api/jobs/search`.

```bash
curl -G "http://127.0.0.1:8000/api/companies/search" \
  --data-urlencode "name=banco do brasil" \
  --data-urlencode "start=0"
```

`name` is required and must not be blank; `start` defaults to `0`. The response contains `query`,
`pagination`, and `companies`, in LinkedIn's result order. Each company has `id`, `name`,
`industry_location`, `followers`, and `url`. `industry_location` and `followers` are LinkedIn's display
texts, returned as provided: the first may contain the industry, the location, or both separated by
`•`, and both depend on the LinkedIn interface language. `pagination.total` is LinkedIn's reported
total for the search, and `has_next` and `next_start` are `null` when LinkedIn does not report it.
A search without matches returns `200` with an empty `companies` list.

The search uses a LinkedIn GraphQL query ID configured by `LINKEDIN_COMPANY_SEARCH_QUERY_ID`.
LinkedIn changes these IDs without notice. In our tests, LinkedIn answered an invalid query ID with
HTTP 500, which this API reports as `503`. If company searches keep returning `503` while job
details work, copy the current `queryId` of the `voyagerSearchDashClusters` request from the
browser's network tab on a LinkedIn company search and update the variable.

### Job details

`GET /api/job/{job_id}` checks the cache before requesting LinkedIn's authenticated Voyager API.
IDs must use ASCII digits, and the LinkedIn cookies must be configured.

```bash
curl "http://127.0.0.1:8000/api/job/4486249045"
curl "http://127.0.0.1:8000/api/job/4486249045?refresh=true"
```

The second request bypasses the cache and refreshes it after a successful fetch. Cached records do
not expire. A job is cached only when `id`, `title`, `company`, `url`, and `description_text` are
present. Cache failures fall back to LinkedIn. The response includes `is_cached` to indicate whether
the returned details came from SQLite. Job details also include `job_state`, `closed_at`,
`expires_at`, and `application_url`; these fields are `null` when LinkedIn does not provide them.
Timestamps are ISO 8601 strings in UTC. The application URL is taken from the external company URL
or LinkedIn Easy Apply URL when available.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `LINKEDIN_LI_AT`, `LINKEDIN_JSESSIONID` | empty | Cookies for authenticated search and details |
| `LINKEDIN_USER_AGENT` | Chrome user agent | LinkedIn request header |
| `LINKEDIN_COMPANY_SEARCH_QUERY_ID` | current known ID | GraphQL query ID for company search |
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

Online tests are marked with `integration`, call LinkedIn, and are skipped by default.
`--integration` runs only them; `--no-cov` disables the coverage threshold, which applies to
the offline suite. They require `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID`:

```bash
pytest --integration --no-cov
```
