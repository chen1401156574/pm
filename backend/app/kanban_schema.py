from __future__ import annotations

import json
from typing import Any
from typing_extensions import TypedDict


class KanbanValidationError(ValueError):
    pass


class Card(TypedDict):
    id: str
    title: str
    details: str
    order: int


class Column(TypedDict):
    id: str
    title: str
    card_ids: list[str]
    order: int


class BoardState(TypedDict):
    columns: list[Column]
    cards: list[Card]


def _require_type(value: Any, expected_type: type, path: str) -> None:
    if not isinstance(value, expected_type):
        raise KanbanValidationError(f"{path} must be {expected_type.__name__}")


def validate_board_state(payload: Any) -> BoardState:
    _require_type(payload, dict, "board_state")
    if "columns" not in payload or "cards" not in payload:
        raise KanbanValidationError("board_state must include columns and cards")

    columns_raw = payload["columns"]
    cards_raw = payload["cards"]
    _require_type(columns_raw, list, "board_state.columns")
    _require_type(cards_raw, list, "board_state.cards")
    if len(columns_raw) == 0:
        raise KanbanValidationError("board_state.columns must not be empty")

    columns: list[Column] = []
    cards: list[Card] = []
    column_ids: set[str] = set()
    card_ids: set[str] = set()

    for index, column in enumerate(columns_raw):
        path = f"board_state.columns[{index}]"
        _require_type(column, dict, path)
        column_id = column.get("id")
        title = column.get("title")
        order = column.get("order")
        column_card_ids = column.get("card_ids")
        _require_type(column_id, str, f"{path}.id")
        _require_type(title, str, f"{path}.title")
        _require_type(order, int, f"{path}.order")
        _require_type(column_card_ids, list, f"{path}.card_ids")
        if column_id in column_ids:
            raise KanbanValidationError(f"duplicate column id: {column_id}")
        column_ids.add(column_id)

        normalized_card_ids: list[str] = []
        for card_index, card_id in enumerate(column_card_ids):
            _require_type(card_id, str, f"{path}.card_ids[{card_index}]")
            normalized_card_ids.append(card_id)

        columns.append(
            {
                "id": column_id,
                "title": title.strip(),
                "card_ids": normalized_card_ids,
                "order": order,
            }
        )

    for index, card in enumerate(cards_raw):
        path = f"board_state.cards[{index}]"
        _require_type(card, dict, path)
        card_id = card.get("id")
        title = card.get("title")
        details = card.get("details")
        order = card.get("order")
        _require_type(card_id, str, f"{path}.id")
        _require_type(title, str, f"{path}.title")
        _require_type(details, str, f"{path}.details")
        _require_type(order, int, f"{path}.order")
        if card_id in card_ids:
            raise KanbanValidationError(f"duplicate card id: {card_id}")
        card_ids.add(card_id)
        cards.append(
            {
                "id": card_id,
                "title": title.strip(),
                "details": details,
                "order": order,
            }
        )

    for column in columns:
        for card_id in column["card_ids"]:
            if card_id not in card_ids:
                raise KanbanValidationError(
                    f"column {column['id']} references unknown card id: {card_id}"
                )

    return {
        "columns": columns,
        "cards": cards,
    }


def serialize_board_state(payload: Any) -> str:
    validated = validate_board_state(payload)
    return json.dumps(validated, ensure_ascii=True, separators=(",", ":"))


def deserialize_board_state(payload: str) -> BoardState:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise KanbanValidationError("invalid JSON payload") from error
    return validate_board_state(data)
