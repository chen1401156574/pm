# Backend

FastAPI service for the PM MVP Kanban app.

## Architecture

```
app/main.py          – FastAPI app factory, routes, CORS, static-file serving
app/db.py            – SQLite data layer (users → boards → board_states)
app/kanban_schema.py – BoardState TypedDict + strict runtime validation
```

**Environment variables**

| Variable | Default | Description |
|---|---|---|
| `PM_DB_PATH` | `backend/data/pm.db` | Path to the SQLite database file |
| `PM_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed CORS origins |

**API routes**

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/kanban` | Fetch the current user's board (auto-migrates legacy 3-column state) |
| POST | `/api/kanban` | Save the current user's board (full replacement, versioned) |
| GET | `/` | Serve `frontend_dist/index.html` (or Hello World fallback) |
| GET | `/{path}` | Serve static assets from `frontend_dist/` |

## Local development

```bash
# Install dependencies (including dev extras for testing)
uv pip install --system -e ".[dev]"

# Start with hot reload
uvicorn app.main:app --reload
```

## Tests

```bash
# Run all tests with coverage report (requires >= 80 % line coverage)
pytest

# Run a single test file
pytest tests/test_main.py

# Run a specific test by name
pytest tests/test_main.py -k "test_health"
```
