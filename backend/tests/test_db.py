import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import create_board, create_user, get_latest_board_state, initialize_database, save_board_state
from app.main import create_app


def _sample_state() -> dict:
    return {
        "columns": [
            {
                "id": "col-backlog",
                "title": "Backlog",
                "card_ids": ["card-1"],
                "order": 0,
            }
        ],
        "cards": [
            {
                "id": "card-1",
                "title": "Collect requirements",
                "details": "Talk to key stakeholders",
                "order": 0,
            }
        ],
    }


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_initialize_database_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "pm.db"
    initialize_database(db_path)
    assert db_path.exists()

    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    table_names = {row["name"] for row in rows}
    assert {"users", "boards", "board_states"}.issubset(table_names)


def test_data_layer_can_persist_and_read_latest_board_state(tmp_path: Path) -> None:
    db_path = initialize_database(tmp_path / "pm.db")
    with _connect(db_path) as connection:
        user_id = create_user(connection, username="user-a", password_hash="hash")
        board_id = create_board(connection, user_id=user_id, name="default")

        version_1 = save_board_state(connection, board_id=board_id, state=_sample_state())
        assert version_1 == 1
        latest = get_latest_board_state(connection, board_id=board_id)

    assert latest is not None
    assert latest["version"] == 1
    assert latest["state"]["columns"][0]["id"] == "col-backlog"


def test_create_board_fails_when_user_missing(tmp_path: Path) -> None:
    db_path = initialize_database(tmp_path / "pm.db")
    with _connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            create_board(connection, user_id=999, name="default")


def test_app_startup_initializes_database_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "startup" / "pm.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))

    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    assert db_path.exists()
