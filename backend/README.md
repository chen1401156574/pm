# Backend

Minimal FastAPI service used by the project container in Part 2.

## Local run

```bash
uv pip install --system -e ".[dev]"
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```
