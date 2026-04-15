import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.openrouter_client import OpenRouterClientError

@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_pm.db"
    os.environ["PM_DB_PATH"] = str(db_path)
    yield db_path
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            # On Windows, SQLite file handles may be released slightly later.
            pass
    if "PM_DB_PATH" in os.environ:
        del os.environ["PM_DB_PATH"]

@pytest.fixture
def client(test_db_path) -> TestClient:
    app = create_app()
    with TestClient(app) as client:
        yield client

def test_index_returns_html(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hello World from FastAPI" in response.text

def test_health_endpoint(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_kanban_initial_empty(client) -> None:
    response = client.get("/api/kanban")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 0
    assert "state" in data
    assert len(data["state"]["columns"]) == 5
    assert [column["id"] for column in data["state"]["columns"]] == [
        "col-backlog",
        "col-discovery",
        "col-progress",
        "col-review",
        "col-done",
    ]
    assert data["state"]["cards"] == []

def test_update_and_get_kanban(client) -> None:
    new_state = {
        "columns": [
            {"id": "col-1", "title": "Todo", "card_ids": ["card-1"], "order": 0}
        ],
        "cards": [
            {"id": "card-1", "title": "Test Task", "details": "Details here", "order": 0}
        ]
    }
    # Update
    update_response = client.post("/api/kanban", json=new_state)
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 1
    assert update_response.json()["status"] == "success"

    # Get again
    get_response = client.get("/api/kanban")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["version"] == 1
    assert data["state"]["columns"][0]["id"] == "col-1"
    assert data["state"]["cards"][0]["id"] == "card-1"

def test_update_kanban_invalid_data(client) -> None:
    # Missing columns
    invalid_state = {
        "cards": []
    }
    response = client.post("/api/kanban", json=invalid_state)
    assert response.status_code == 422 # FastAPI built-in validation for TypedDict/Pydantic

    # Valid structure but fails application-level validation (e.g., empty columns)
    # Actually, our validate_board_state is called in save_board_state
    invalid_state_2 = {
        "columns": [],
        "cards": []
    }
    response = client.post("/api/kanban", json=invalid_state_2)
    assert response.status_code == 400
    assert "board_state.columns must not be empty" in response.json()["detail"]

def test_legacy_three_columns_are_auto_migrated_to_five_columns(client) -> None:
    legacy_state = {
        "columns": [
            {"id": "col-todo", "title": "To Do", "card_ids": ["card-1"], "order": 0},
            {"id": "col-doing", "title": "In Progress", "card_ids": [], "order": 1},
            {"id": "col-done", "title": "Done", "card_ids": [], "order": 2},
        ],
        "cards": [
            {"id": "card-1", "title": "Legacy card", "details": "from old board", "order": 0},
        ],
    }
    update_response = client.post("/api/kanban", json=legacy_state)
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 1

    migrated_response = client.get("/api/kanban")
    assert migrated_response.status_code == 200
    migrated = migrated_response.json()
    assert migrated["version"] == 2
    assert [column["id"] for column in migrated["state"]["columns"]] == [
        "col-backlog",
        "col-discovery",
        "col-progress",
        "col-review",
        "col-done",
    ]
    assert migrated["state"]["columns"][0]["card_ids"] == ["card-1"]
    assert migrated["state"]["cards"][0]["id"] == "card-1"

def test_serves_exported_frontend_files(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend_dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<h1>Kanban Studio</h1>", encoding="utf-8")
    (frontend_dist / "asset.js").write_text("console.log('ok')", encoding="utf-8")

    # Use a separate app instance for this test to avoid conflicting with the test_db fixture
    with TestClient(create_app(frontend_dist)) as test_client:
        home_response = test_client.get("/")
        assert home_response.status_code == 200
        assert "Kanban Studio" in home_response.text

        asset_response = test_client.get("/asset.js")
        assert asset_response.status_code == 200
        assert "console.log('ok')" in asset_response.text


def test_ai_self_check_returns_reply(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.request_openrouter_completion", lambda messages: "4")

    response = client.post("/api/ai/self-check", json={"prompt": "2+2"})
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "4"
    assert data["model"] == "openai/gpt-oss-120b"


def test_ai_self_check_maps_client_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_openrouter_error(messages):
        raise OpenRouterClientError(message="OpenRouter request timed out", status_code=504)

    monkeypatch.setattr("app.main.request_openrouter_completion", _raise_openrouter_error)

    response = client.post("/api/ai/self-check", json={"prompt": "2+2"})
    assert response.status_code == 504
    assert response.json()["detail"] == "OpenRouter request timed out"


def test_ai_chat_applies_valid_board_update(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _mock_openrouter(messages):
        return (
            '{"reply":"已更新","board_update":{"columns":[{"id":"col-backlog","title":"Backlog","card_ids":["card-1"],"order":0},'
            '{"id":"col-discovery","title":"Discovery","card_ids":[],"order":1},'
            '{"id":"col-progress","title":"In Progress","card_ids":[],"order":2},'
            '{"id":"col-review","title":"Review","card_ids":[],"order":3},'
            '{"id":"col-done","title":"Done","card_ids":[],"order":4}],'
            '"cards":[{"id":"card-1","title":"AI Task","details":"from ai","order":0}]}}'
        )

    monkeypatch.setattr("app.main.request_openrouter_completion", _mock_openrouter)
    response = client.post("/api/ai/chat", json={"question": "加一张卡片"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "已更新"
    assert payload["board_update"] is not None
    assert payload["board_update"]["cards"][0]["id"] == "card-1"

    latest = client.get("/api/kanban").json()
    assert latest["state"]["cards"][0]["title"] == "AI Task"


def test_ai_chat_rejects_invalid_board_update_without_db_pollution(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # Seed initial board state.
    seed_state = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "card_ids": ["card-1"], "order": 0},
            {"id": "col-discovery", "title": "Discovery", "card_ids": [], "order": 1},
            {"id": "col-progress", "title": "In Progress", "card_ids": [], "order": 2},
            {"id": "col-review", "title": "Review", "card_ids": [], "order": 3},
            {"id": "col-done", "title": "Done", "card_ids": [], "order": 4},
        ],
        "cards": [
            {"id": "card-1", "title": "Baseline", "details": "seed", "order": 0},
        ],
    }
    update_response = client.post("/api/kanban", json=seed_state)
    assert update_response.status_code == 200
    before = client.get("/api/kanban").json()
    before_version = before["version"]

    monkeypatch.setattr(
        "app.main.request_openrouter_completion",
        lambda messages: '{"reply":"bad","board_update":{"columns":[],"cards":[]}}',
    )
    response = client.post("/api/ai/chat", json={"question": "破坏数据"})
    assert response.status_code == 502
    assert "Invalid AI response" in response.json()["detail"]

    after = client.get("/api/kanban").json()
    assert after["version"] == before_version
    assert after["state"] == before["state"]


def test_ai_chat_includes_history_and_trims_context(client, monkeypatch: pytest.MonkeyPatch) -> None:
    captured_histories: list[list[dict[str, str]]] = []

    def _mock_openrouter(messages):
        assert len(messages) == 2
        context = messages[1]["content"]
        assert '"board_state"' in context
        marker = '"history":'
        history_start = context.index(marker) + len(marker)
        history_end = context.rfind("]")
        history_json = context[history_start : history_end + 1]
        captured_histories.append(json.loads(history_json))
        return '{"reply":"ok","board_update":null}'

    monkeypatch.setattr("app.main.request_openrouter_completion", _mock_openrouter)

    for idx in range(8):
        response = client.post("/api/ai/chat", json={"question": f"q-{idx}"})
        assert response.status_code == 200
        assert response.json()["board_update"] is None

    assert captured_histories[0] == []
    # History is trimmed to MAX_AI_HISTORY_MESSAGES (=12), so it should not grow unbounded.
    assert len(captured_histories[-1]) <= 12
    assert captured_histories[-1][-1]["role"] == "assistant"


def test_non_ai_kanban_api_still_works_after_ai_chat(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.main.request_openrouter_completion",
        lambda messages: '{"reply":"no update","board_update":null}',
    )
    ai_response = client.post("/api/ai/chat", json={"question": "只聊天"})
    assert ai_response.status_code == 200

    update_state = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "card_ids": ["card-2"], "order": 0},
            {"id": "col-discovery", "title": "Discovery", "card_ids": [], "order": 1},
            {"id": "col-progress", "title": "In Progress", "card_ids": [], "order": 2},
            {"id": "col-review", "title": "Review", "card_ids": [], "order": 3},
            {"id": "col-done", "title": "Done", "card_ids": [], "order": 4},
        ],
        "cards": [
            {"id": "card-2", "title": "Still works", "details": "normal api", "order": 0},
        ],
    }
    update_response = client.post("/api/kanban", json=update_state)
    assert update_response.status_code == 200

    latest = client.get("/api/kanban").json()
    assert latest["state"]["cards"][0]["id"] == "card-2"
