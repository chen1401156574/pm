# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A single-board Kanban app ("PM MVP") with a **Next.js 16 frontend** and a **FastAPI backend**. The app is deployed as a single Docker container: the backend serves the pre-built Next.js static export from `backend/frontend_dist/`.

Default credentials (hardcoded MVP): `user` / `password`.

---

## Commands

### Backend (run from `backend/`)

```bash
# Install deps (including dev extras)
uv pip install --system -e ".[dev]"

# Start dev server (hot reload)
uvicorn app.main:app --reload

# Run all tests (requires 80% coverage)
pytest

# Run a single test file
pytest tests/test_main.py

# Run a single test by name
pytest tests/test_main.py -k "test_health"
```

### Frontend (run from `frontend/`)

```bash
npm install

# Dev server (proxies /api to :8000 when running locally on :3000)
npm run dev

# Unit tests (Vitest)
npm run test:unit

# Unit tests in watch mode
npm run test:unit:watch

# E2E tests (Playwright) — requires backend + frontend both running
npm run test:e2e

# Lint
npm run lint
```

### Docker (run from repo root)

```bash
# Build and start (platform scripts wrap this)
docker compose up --build -d

# Stop
docker compose down
```

Platform helper scripts are in `scripts/` (`start-windows.ps1`, `start-mac.sh`, `start-linux.sh`, etc.).

---

## Architecture

### Data flow

```
Browser  ──fetch──►  Next.js page.tsx
                          │
                    kanbanApi.ts  (toBoardData / toApiBoardState convert snake_case ↔ camelCase)
                          │
                     GET/POST /api/kanban
                          │
                    FastAPI main.py
                          │
                    db.py (SQLite via sqlite3)
```

### Backend

- `app/main.py` — FastAPI app factory (`create_app`). Handles lifespan (DB init + default user seeding), CORS (`PM_CORS_ORIGINS` env var), and two API routes: `GET /api/kanban` and `POST /api/kanban`. Also serves the Next.js static export for all other paths.
- `app/db.py` — Raw `sqlite3` wrapper. Schema: `users → boards → board_states` (append-only versioned snapshots). `get_latest_board_state` returns the highest-version row.
- `app/kanban_schema.py` — `TypedDict` types (`BoardState`, `Column`, `Card`) plus strict `validate_board_state` used on both read and write. Raises `KanbanValidationError` on bad input.

**Key env vars:**
- `PM_DB_PATH` — override SQLite file location (default: `backend/data/pm.db`)
- `PM_CORS_ORIGINS` — comma-separated allowed origins (default: `http://localhost:3000,http://127.0.0.1:3000`)

**Legacy migration:** `migrate_legacy_three_column_state` in `main.py` transparently upgrades old 3-column boards (col-todo / col-doing / col-done) to the current 5-column layout on first read.

### Frontend

- `src/lib/kanban.ts` — Pure business logic: `BoardData` / `Column` / `Card` types, `moveCard` (drag-and-drop reordering), `createId`, and `initialData` (seed data shown before backend responds).
- `src/lib/kanbanApi.ts` — Fetch layer. `resolveApiBaseUrl` auto-detects dev mode (localhost:3000 → port 8000). `toBoardData` and `toApiBoardState` translate between the API's snake_case schema and the frontend's camelCase `BoardData`.
- `src/app/page.tsx` — Auth gate (client-side only, `sessionStorage`). Manages load/save state and passes everything into `KanbanBoard`.
- `src/components/KanbanBoard.tsx` — DnD context (`@dnd-kit/core`), local board state, column rename, add/delete card handlers. Calls `onBoardChange` on every mutation, which triggers a backend save.
- `src/components/KanbanColumn.tsx` / `KanbanCard.tsx` / `KanbanCardPreview.tsx` / `NewCardForm.tsx` — Presentational column/card components. `data-testid="column-{id}"` and `data-testid="card-{id}"` attributes are used by Playwright.

**API base URL:** Controlled by `NEXT_PUBLIC_API_BASE_URL`. When unset and running on localhost:3000, the frontend automatically targets `:8000`. In production (same origin), it uses a relative path.

### Testing strategy

- **Backend unit tests** (`pytest`): `httpx.TestClient` against the FastAPI app with a temp SQLite DB.
- **Frontend unit tests** (`vitest` + `@testing-library/react`): test `kanban.ts` logic and `kanbanApi.ts` transformations directly; `page.tsx` and `KanbanBoard.tsx` are tested with mocked fetch.
- **E2E tests** (`playwright`, `frontend/tests/kanban.spec.ts`): full login → board interaction → logout flow against a live stack.
