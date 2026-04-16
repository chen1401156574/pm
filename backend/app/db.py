from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.kanban_schema import BoardState, deserialize_board_state, serialize_board_state

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "pm.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path | None = None) -> Path:
    resolved_path = (db_path or DEFAULT_DB_PATH).resolve()
    with _connect(resolved_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS board_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (board_id, version),
                FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards (user_id);
            CREATE INDEX IF NOT EXISTS idx_board_states_board_id ON board_states (board_id);
            """
        )
        connection.commit()
    return resolved_path


def create_user(connection: sqlite3.Connection, username: str, password_hash: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO users(username, password_hash)
        VALUES (?, ?)
        """,
        (username, password_hash),
    )
    connection.commit()
    return int(cursor.lastrowid)


def create_board(connection: sqlite3.Connection, user_id: int, name: str = "default") -> int:
    cursor = connection.execute(
        """
        INSERT INTO boards(user_id, name)
        VALUES (?, ?)
        """,
        (user_id, name),
    )
    connection.commit()
    return int(cursor.lastrowid)


def save_board_state(connection: sqlite3.Connection, board_id: int, state: BoardState) -> int:
    serialized_state = serialize_board_state(state)
    # BUG-1: use a single atomic INSERT with a subquery to eliminate the
    # SELECT-then-INSERT race condition that could cause a UNIQUE(board_id, version)
    # conflict under concurrent requests.
    cursor = connection.execute(
        """
        INSERT INTO board_states(board_id, version, state_json)
        VALUES (
            ?,
            (SELECT COALESCE(MAX(version), 0) + 1 FROM board_states WHERE board_id = ?),
            ?
        )
        """,
        (board_id, board_id, serialized_state),
    )
    connection.execute(
        """
        UPDATE boards
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (board_id,),
    )
    connection.commit()
    # Read back the version that was actually written via its rowid (= id column)
    version_cursor = connection.execute(
        "SELECT version FROM board_states WHERE id = ?",
        (cursor.lastrowid,),
    )
    return int(version_cursor.fetchone()[0])


def get_latest_board_state(connection: sqlite3.Connection, board_id: int) -> dict[str, Any] | None:
    cursor = connection.execute(
        """
        SELECT version, state_json
        FROM board_states
        WHERE board_id = ?
        ORDER BY version DESC
        LIMIT 1
        """,
        (board_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "version": int(row["version"]),
        "state": deserialize_board_state(str(row["state_json"])),
    }
