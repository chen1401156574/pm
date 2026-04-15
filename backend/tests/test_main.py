import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_pm.db"
    os.environ["PM_DB_PATH"] = str(db_path)
    yield db_path
    if db_path.exists():
        db_path.unlink()
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
    test_client = TestClient(create_app(frontend_dist))

    home_response = test_client.get("/")
    assert home_response.status_code == 200
    assert "Kanban Studio" in home_response.text

    asset_response = test_client.get("/asset.js")
    assert asset_response.status_code == 200
    assert "console.log('ok')" in asset_response.text
