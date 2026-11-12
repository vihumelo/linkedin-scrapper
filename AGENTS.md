
# AGENTS.md

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
├── AGENTS.md
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
- Keep application code compatible with Pyright's strict type checking. Use precise types instead of `Any` or casts where practical, and do not silence type errors without a documented reason.
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
- Treat credentials, access tokens, cookies, personal information, and other sensitive values as secrets while writing code. Do not hard-code or expose them in source code, logs, exceptions, API responses, URLs, test fixtures, or documentation; load secrets from settings and redact sensitive values before producing diagnostic output.
- For environment files, commit `.env.example` only; never commit `.env` or put real secrets in the example.
- Validate required settings at startup or before using the corresponding integration.

## 5. Quality and maintenance

- Treat this section as the primary guidance when creating or modifying project features.
- Before making a change, inspect the relevant modules and trace how the behavior flows through routes, services, clients, parsers, and schemas. Read nearby tests and configuration when they affect the change.
- Follow the existing architecture and conventions. Keep modules loosely coupled and testable, and do not mix HTTP communication, parsing, and business rules.
- Prefer the smallest clear change that solves the requested problem. Avoid premature abstractions, unrelated refactors, and unnecessary dependencies.
- Preserve existing API contracts and expected behavior unless the requested feature requires changing them. Update affected schemas, documentation, and tests when behavior or contracts change.
- Add or update pytest tests for relevant features and fixes. The project configures pytest with strict markers and configuration, branch coverage, and a minimum coverage threshold of 85%; keep that threshold passing.
- Tests must validate observable behavior, not implementation details. Do not write meaningless tests solely to increase coverage.
- Never weaken linting, typing, coverage thresholds, or CI checks to make failing code pass without explicit approval.
- Before finishing a change, install the development dependencies with `python -m pip install -e ".[dev]"` if needed and run the same quality checks used by CI:

  ```text
  ruff check .
  ruff format --check .
  pyright
  pytest
  deptry .
  ```

- Fix failures caused by the change. Run `deptry .` when adding, removing, or changing dependencies.
- Keep code readable and maintainable. Do not silently ignore errors, weaken validation, or add workarounds that hide failures. Explain any known limitation that prevents a check from passing.

## 6. Review and commit workflow

- Never create commits unless explicitly requested by the user.
- Before creating any commit, review the complete diff, including staged and unstaged changes, as a code review. Identify and report problems, then fix them before proceeding. Do not commit while known issues from the review remain unresolved.
- After the code review and fixes, run the complete CI checks listed in Section 5. Create commits only after all checks pass; if a check cannot pass, explain why and do not present the change as CI-verified.
- Use Conventional Commits. Keep each commit focused on one file or a cohesive group of files that implements one logical change. Split unrelated changes into separate commits; never combine all pending work into one global commit.
- After committing, inspect the commit summaries and repository status to confirm the intended files are included and no unintended changes were committed. Report the commit messages and any remaining working-tree changes.
