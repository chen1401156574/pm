import pytest

from app.kanban_schema import KanbanValidationError, deserialize_board_state, serialize_board_state


def _valid_board_state() -> dict:
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
                "title": "Draft design",
                "details": "Create first visual draft",
                "order": 0,
            }
        ],
    }


def test_schema_round_trip_serialization() -> None:
    payload = _valid_board_state()
    serialized = serialize_board_state(payload)
    restored = deserialize_board_state(serialized)
    assert restored == payload


def test_schema_rejects_invalid_json_payload() -> None:
    with pytest.raises(KanbanValidationError, match="invalid JSON payload"):
        deserialize_board_state("{bad json}")


def test_schema_rejects_empty_board() -> None:
    payload = {"columns": [], "cards": []}
    with pytest.raises(KanbanValidationError, match="must not be empty"):
        serialize_board_state(payload)


def test_schema_rejects_unknown_card_reference() -> None:
    payload = _valid_board_state()
    payload["columns"][0]["card_ids"] = ["missing-card"]
    with pytest.raises(KanbanValidationError, match="unknown card id"):
        serialize_board_state(payload)
