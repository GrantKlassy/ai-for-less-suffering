"""Thin wrapper over the Anthropic SDK. Centralizes model IDs and call plumbing."""

from __future__ import annotations

import os
from enum import StrEnum

import anthropic
from anthropic.types import TextBlock, TextBlockParam


class Model(StrEnum):
    """Model IDs used by the engine.

    Opus is the reasoning model (query synthesis, bridge generation, blindspot detection).
    Haiku is the parsing/scaffolding model (routine JSON reshaping, cheap classification).
    """

    OPUS = "claude-opus-4-7"
    HAIKU = "claude-haiku-4-5-20251001"


class AnthropicClient:
    """Stateless wrapper. Accepts an injected `sdk_client` for tests."""

    def __init__(
        self,
        *,
        sdk_client: anthropic.Anthropic | None = None,
        api_key: str | None = None,
    ) -> None:
        if sdk_client is not None:
            self._client: anthropic.Anthropic = sdk_client
            return
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it or pass api_key=... explicitly."
            )
        self._client = anthropic.Anthropic(api_key=key)

    def complete(
        self,
        *,
        model: Model,
        system_blocks: list[TextBlockParam],
        user_message: str,
        max_tokens: int = 8192,
    ) -> str:
        """Send one messages.create call; return the first text block's content."""
        response = self._client.messages.create(
            model=model.value,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user_message}],
        )
        for block in response.content:
            if isinstance(block, TextBlock):
                return block.text
        raise RuntimeError(f"no text block in response: {response!r}")
