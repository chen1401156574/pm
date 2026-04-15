from __future__ import annotations

import pytest

from app.ai_structured_output import AIStructuredOutputError, parse_ai_structured_output


def test_parse_ai_structured_output_with_reply_only() -> None:
    payload = '{"reply":"Done","board_update":null}'
    reply, board_update = parse_ai_structured_output(payload)
    assert reply == "Done"
    assert board_update is None


def test_parse_ai_structured_output_with_board_update() -> None:
    payload = (
        '{"reply":"Updated","board_update":{"columns":[{"id":"col-1","title":"Todo","card_ids":["card-1"],"order":0}],'
        '"cards":[{"id":"card-1","title":"Task","details":"d","order":0}]}}'
    )
    reply, board_update = parse_ai_structured_output(payload)
    assert reply == "Updated"
    assert board_update is not None
    assert board_update["cards"][0]["id"] == "card-1"


def test_parse_ai_structured_output_rejects_invalid_board_update() -> None:
    payload = '{"reply":"Updated","board_update":{"columns":[],"cards":[]}}'
    with pytest.raises(AIStructuredOutputError):
        parse_ai_structured_output(payload)
