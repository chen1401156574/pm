from pathlib import Path
from contextlib import asynccontextmanager
import os
import logging
import json
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.db import initialize_database, _connect, get_latest_board_state, save_board_state, create_user, create_board
from app.kanban_schema import BoardState, KanbanValidationError
from app.openrouter_client import (
    OPENROUTER_MODEL,
    OpenRouterClientError,
    request_openrouter_completion,
)
from app.ai_structured_output import AIStructuredOutputError, parse_ai_structured_output

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HELLO_WORLD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PM MVP</title>
  </head>
  <body>
    <h1>Hello World from FastAPI</h1>
    <p>Use <code>/api/health</code> to verify API reachability.</p>
  </body>
</html>
"""

# Default user for MVP
DEFAULT_USERNAME = "user"
DEFAULT_PASSWORD_HASH = "password" # In a real app, use a real hash
FIVE_COLUMN_TEMPLATE = [
    {"id": "col-backlog", "title": "Backlog", "order": 0},
    {"id": "col-discovery", "title": "Discovery", "order": 1},
    {"id": "col-progress", "title": "In Progress", "order": 2},
    {"id": "col-review", "title": "Review", "order": 3},
    {"id": "col-done", "title": "Done", "order": 4},
]


class AISelfCheckRequest(BaseModel):
    prompt: str = "2+2"


class AIChatRequest(BaseModel):
    question: str


MAX_AI_HISTORY_MESSAGES = 12
AI_SYSTEM_PROMPT = (
    "You are an assistant for a Kanban board manager. "
    "Return only a JSON object with this exact shape: "
    '{"reply":"string","board_update":null|BoardState}. '
    "If no board change is needed, set board_update to null. "
    "Do not include markdown or extra keys."
)


def build_default_board_state() -> BoardState:
    return {
        "columns": [
            {**column, "card_ids": []}
            for column in FIVE_COLUMN_TEMPLATE
        ],
        "cards": [],
    }


def migrate_legacy_three_column_state(state: BoardState) -> BoardState | None:
    columns = state.get("columns", [])
    if len(columns) != 3:
        return None

    column_cards = {column["id"]: column["card_ids"] for column in columns}
    legacy_ids = {"col-todo", "col-doing", "col-done"}
    if set(column_cards.keys()) != legacy_ids:
        return None

    return {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "card_ids": list(column_cards["col-todo"]), "order": 0},
            {"id": "col-discovery", "title": "Discovery", "card_ids": [], "order": 1},
            {"id": "col-progress", "title": "In Progress", "card_ids": list(column_cards["col-doing"]), "order": 2},
            {"id": "col-review", "title": "Review", "card_ids": [], "order": 3},
            {"id": "col-done", "title": "Done", "card_ids": list(column_cards["col-done"]), "order": 4},
        ],
        "cards": state["cards"],
    }

def get_db_path() -> Path:
    db_path = os.getenv("PM_DB_PATH")
    return Path(db_path) if db_path else Path(__file__).resolve().parents[1] / "data" / "pm.db"

def get_db():
    db_path = get_db_path()
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

def get_current_user_id(db=Depends(get_db)) -> int:
    # For MVP, we just use the hardcoded "user"
    cursor = db.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    
    # If user doesn't exist, create it (this shouldn't happen if lifespan works correctly)
    user_id = create_user(db, DEFAULT_USERNAME, DEFAULT_PASSWORD_HASH)
    create_board(db, user_id)
    return user_id

def get_user_board_id(user_id: int, db=Depends(get_db)) -> int:
    cursor = db.execute("SELECT id FROM boards WHERE user_id = ? AND name = 'default'", (user_id,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    
    # If board doesn't exist, create it
    return create_board(db, user_id)

def create_app(frontend_dist_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db_path = get_db_path()
        initialize_database(db_path)
        
        # Ensure default user exists
        with _connect(db_path) as conn:
            cursor = conn.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_USERNAME,))
            if not cursor.fetchone():
                user_id = create_user(conn, DEFAULT_USERNAME, DEFAULT_PASSWORD_HASH)
                create_board(conn, user_id)
        
        yield

    app = FastAPI(title="PM MVP Backend", version="0.1.0", lifespan=lifespan)
    app.state.ai_histories = {}
    cors_origins = os.getenv(
        "PM_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dist = (
        frontend_dist_dir
        if frontend_dist_dir is not None
        else Path(__file__).resolve().parents[1] / "frontend_dist"
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = str(uuid.uuid4())
        logger.info(f"Request {request_id} started: {request.method} {request.url}")
        try:
            response = await call_next(request)
            logger.info(f"Request {request_id} finished with status {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Request {request_id} failed: {str(e)}")
            raise

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/kanban")
    def get_kanban(
        user_id: int = Depends(get_current_user_id),
        db=Depends(get_db)
    ) -> dict[str, Any]:
        board_id = get_user_board_id(user_id, db)
        state_data = get_latest_board_state(db, board_id)
        if state_data is None:
            return {"version": 0, "state": build_default_board_state()}

        migrated_state = migrate_legacy_three_column_state(state_data["state"])
        if migrated_state is not None:
            migrated_version = save_board_state(db, board_id, migrated_state)
            return {
                "version": migrated_version,
                "state": migrated_state,
            }

        return state_data

    @app.post("/api/kanban")
    def update_kanban(
        state: BoardState,
        user_id: int = Depends(get_current_user_id),
        db=Depends(get_db)
    ) -> dict[str, Any]:
        try:
            board_id = get_user_board_id(user_id, db)
            new_version = save_board_state(db, board_id, state)
            return {"version": new_version, "status": "success"}
        except KanbanValidationError as e:
            logger.warning(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error updating kanban: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

    @app.post("/api/ai/self-check")
    def ai_self_check(payload: AISelfCheckRequest) -> dict[str, str]:
        try:
            reply = request_openrouter_completion(
                messages=[{"role": "user", "content": payload.prompt}],
            )
            return {"reply": reply, "model": OPENROUTER_MODEL}
        except OpenRouterClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    @app.post("/api/ai/chat")
    def ai_chat(
        payload: AIChatRequest,
        user_id: int = Depends(get_current_user_id),
        db=Depends(get_db),
    ) -> dict[str, Any]:
        board_id = get_user_board_id(user_id, db)
        state_data = get_latest_board_state(db, board_id)
        board_state = state_data["state"] if state_data is not None else build_default_board_state()

        histories: dict[int, list[dict[str, str]]] = app.state.ai_histories
        conversation_history = histories.get(user_id, [])

        user_context = {
            "question": payload.question,
            "board_state": board_state,
            "history": conversation_history,
        }
        messages = [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_context, ensure_ascii=True)},
        ]

        try:
            raw_reply = request_openrouter_completion(messages=messages)
            reply, board_update = parse_ai_structured_output(raw_reply)
        except OpenRouterClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        except AIStructuredOutputError as exc:
            raise HTTPException(status_code=502, detail=f"Invalid AI response: {str(exc)}") from exc

        response: dict[str, Any] = {"reply": reply, "board_update": None}
        if board_update is not None:
            new_version = save_board_state(db, board_id, board_update)
            response["board_update"] = board_update
            response["version"] = new_version

        next_history = [
            *conversation_history,
            {"role": "user", "content": payload.question},
            {"role": "assistant", "content": reply},
        ]
        histories[user_id] = next_history[-MAX_AI_HISTORY_MESSAGES:]
        return response

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return HTMLResponse(content=HELLO_WORLD_HTML)

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        requested_file = frontend_dist / full_path
        if requested_file.is_file():
            return FileResponse(requested_file)

        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)

        raise HTTPException(status_code=404, detail="Not Found")

    return app


app = create_app()
