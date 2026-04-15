from __future__ import annotations

import json
from typing import Any

from app.kanban_schema import BoardState, KanbanValidationError, validate_board_state


class AIStructuredOutputError(ValueError):
    pass


def _strip_code_fence(payload: str) -> str:
    text = payload.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) < 3:
        return text
    if not lines[-1].strip().startswith("```"):
        return text
    return "\n".join(lines[1:-1]).strip()


def _extract_json(payload: str) -> dict[str, Any]:
    text = _strip_code_fence(payload)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise AIStructuredOutputError("AI output is not valid JSON")

    try:
        extracted = json.loads(text[first : last + 1])
    except json.JSONDecodeError as exc:
        raise AIStructuredOutputError("AI output is not valid JSON") from exc

    if not isinstance(extracted, dict):
        raise AIStructuredOutputError("AI output must be a JSON object")
    return extracted


def parse_ai_structured_output(payload: str) -> tuple[str, BoardState | None]:
    data = _extract_json(payload)
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise AIStructuredOutputError("AI output must include non-empty reply")

    if "board_update" not in data or data["board_update"] is None:
        return reply.strip(), None

    try:
        board_update = validate_board_state(data["board_update"])
    except KanbanValidationError as exc:
        raise AIStructuredOutputError(f"Invalid board_update: {str(exc)}") from exc
    return reply.strip(), board_update
