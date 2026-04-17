"""Reasoning-layer tests. Anthropic SDK is mocked; no network calls happen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

import pytest
from anthropic.types import TextBlock
from pydantic import BaseModel

from afls.reasoning import (
    DISCIPLINE_HEADER,
    AnthropicClient,
    Model,
    ReasoningError,
    complete_and_parse,
    operator_context_blocks,
    system_blocks_for_query,
)


class Toy(BaseModel):
    name: str
    value: int


@dataclass
class _FakeResponse:
    content: list[TextBlock]


class _FakeMessages:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("no responses queued for fake messages.create")
        block = TextBlock(type="text", text=self._responses.pop(0), citations=None)
        return _FakeResponse(content=[block])


class _FakeSDK:
    def __init__(self, responses: list[str]) -> None:
        self.messages = _FakeMessages(responses)


def _client(responses: list[str]) -> tuple[AnthropicClient, _FakeSDK]:
    sdk = _FakeSDK(responses)
    return AnthropicClient(sdk_client=cast(Any, sdk)), sdk


def test_client_requires_key_or_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicClient()


def test_client_uses_injected_sdk() -> None:
    client, sdk = _client(['{"name": "x", "value": 1}'])
    out = client.complete(model=Model.OPUS, system_blocks=[], user_message="hi")
    assert out == '{"name": "x", "value": 1}'
    assert sdk.messages.calls[0]["model"] == "claude-opus-4-7"


def test_complete_and_parse_success() -> None:
    client, sdk = _client([json.dumps({"name": "x", "value": 1})])
    result = complete_and_parse(client, model_cls=Toy, user_message="test")
    assert result.name == "x"
    assert result.value == 1
    assert len(sdk.messages.calls) == 1


def test_complete_and_parse_retries_on_validation_error() -> None:
    client, sdk = _client(
        [
            '{"name": "x", "value": "not a number"}',
            json.dumps({"name": "x", "value": 7}),
        ]
    )
    result = complete_and_parse(client, model_cls=Toy, user_message="test")
    assert result.value == 7
    assert len(sdk.messages.calls) == 2
    retry_msg = sdk.messages.calls[1]["messages"][0]["content"]
    assert "failed validation" in retry_msg
    assert "ONLY JSON" in retry_msg


def test_complete_and_parse_retries_on_json_decode_error() -> None:
    client, sdk = _client(
        [
            "this is not JSON at all",
            json.dumps({"name": "x", "value": 1}),
        ]
    )
    result = complete_and_parse(client, model_cls=Toy, user_message="test")
    assert result.value == 1
    assert len(sdk.messages.calls) == 2


def test_complete_and_parse_raises_after_second_failure() -> None:
    client, sdk = _client(
        [
            '{"invalid": true}',
            "still not valid json",
        ]
    )
    with pytest.raises(ReasoningError) as exc_info:
        complete_and_parse(client, model_cls=Toy, user_message="test")
    assert "after one retry" in str(exc_info.value)
    assert len(sdk.messages.calls) == 2


def test_complete_and_parse_strips_code_fences() -> None:
    fenced = '```json\n{"name": "x", "value": 1}\n```'
    client, _ = _client([fenced])
    result = complete_and_parse(client, model_cls=Toy, user_message="test")
    assert result.value == 1


def test_complete_and_parse_uses_haiku_when_asked() -> None:
    client, sdk = _client([json.dumps({"name": "x", "value": 1})])
    complete_and_parse(client, model_cls=Toy, user_message="t", model=Model.HAIKU)
    assert sdk.messages.calls[0]["model"] == "claude-haiku-4-5-20251001"


def test_operator_context_blocks_loads_directives() -> None:
    blocks = operator_context_blocks()
    labels = [block["text"].split("\n")[0] for block in blocks]
    assert any("BRAIN" in label for label in labels)
    assert any("MANIFESTO" in label for label in labels)
    assert any("CLAUDE" in label for label in labels)
    for block in blocks:
        assert block["type"] == "text"
        assert block["cache_control"] == {"type": "ephemeral"}


def test_system_blocks_for_query_structure() -> None:
    blocks = system_blocks_for_query('{"type": "object"}')
    assert blocks[0]["text"] == DISCIPLINE_HEADER
    schema_block = next(b for b in blocks if "Output schema" in b["text"])
    assert '{"type": "object"}' in schema_block["text"]
    assert schema_block["cache_control"] == {"type": "ephemeral"}


def test_system_blocks_for_query_includes_extra_context() -> None:
    blocks = system_blocks_for_query("{}", extra_context="WIDGET_CONTEXT")
    assert blocks[-1]["text"] == "WIDGET_CONTEXT"


def test_complete_and_parse_calls_include_schema_block() -> None:
    client, sdk = _client([json.dumps({"name": "x", "value": 1})])
    complete_and_parse(client, model_cls=Toy, user_message="t")
    system = sdk.messages.calls[0]["system"]
    schema_block = next(b for b in system if "Output schema" in b["text"])
    assert "name" in schema_block["text"]
    assert "value" in schema_block["text"]
