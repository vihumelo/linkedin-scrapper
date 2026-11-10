# AGENT.md

## 1. Architecture

This project is a **REST API built with Python and FastAPI**, following a modular architecture with clear separation of responsibilities.

Reference structure:

```text
project/
├── app/
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── api/
│   │   └── routes/
│   ├── clients/
│   ├── services/
│   ├── parsers/
│   └── schemas/
├── tests/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── AGENT.md
```

**Responsibilities:**
- `api/routes/`: HTTP endpoints and parameter validation.
- `clients/`: communication with external services.
- `services/`: business rules and orchestration.
- `parsers/`: data extraction and transformation.
- `schemas/`: Pydantic input and output models.
- `core/`: settings and shared components.
- `tests/`: automated tests using pytest.

Keep business logic out of route handlers.

## 2. Code standards

- Use **Python 3.12+**.
- Add **type hints** to all functions, methods, parameters, and return values.
- Write **docstrings in US English** for public modules, classes, and functions.
- Keep variable, function, class, and file names in English, following PEP 8.
- Prefer small, cohesive functions with a single responsibility.
- Use Pydantic v2 for contracts and data validation.
- Use `async/await` for asynchronous I/O operations.
- Use `logging` instead of `print`.
- Handle errors explicitly; do not silently suppress exceptions.
- Add pytest tests for relevant features and fixes.

## 3. FastAPI

- Use `APIRouter` to organize endpoints.
- Use dependency injection with `Depends` where appropriate.
- Declare a `response_model` on routes.
- Return appropriate HTTP status codes.
- Standardize error responses as JSON.
- Provide automatic documentation at `/docs` and `/openapi.json`.
- Keep the API bound to `127.0.0.1` by default.

## 4. Environment settings

Centralize settings in `app/core/config.py` using `pydantic-settings`.

Create `.env.example` with the following variables:

```dotenv
# LinkedIn
LINKEDIN_LI_AT=
LINKEDIN_JSESSIONID=
LINKEDIN_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36

# HTTP
HTTP_TIMEOUT_SECONDS=30

# Cache
CACHE_BACKEND=sqlite
CACHE_SQLITE_PATH=./data/jobs_cache.db
```

Rules:
- Create `.env` from `.env.example`, preserving existing settings.
- Never invent credentials or add real values to the code.
- Never commit `.env` or log tokens and cookies.
- Commit only `.env.example`, with no secrets.
- Validate required settings at startup or before using the corresponding integration.

## 5. Quality and maintenance

- Prioritize simplicity, readability, and maintainability.
- Avoid premature abstractions and unnecessary dependencies.
- Keep modules loosely coupled and testable.
- Do not mix HTTP communication, parsing, and business rules.
- Use `ruff` for linting and formatting.
- Ensure changes do not break public contracts or existing tests.
