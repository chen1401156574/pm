# Backend Agent Notes

## Scope

This directory contains the FastAPI service for the PM MVP.
Part 2 intentionally keeps the backend minimal:

- Static HTML response at `/` for hello-world verification.
- JSON health endpoint at `/api/health`.

## Structure

- `app/main.py`
  - FastAPI app instance and routes.
- `tests/test_main.py`
  - Basic endpoint tests using `fastapi.testclient`.
- `pyproject.toml`
  - Runtime dependencies and test dependencies.

## Run

From `backend/`:

```bash
uv pip install --system -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

From `backend/`:

```bash
pytest
```
