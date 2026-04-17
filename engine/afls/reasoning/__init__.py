"""Reasoning layer: Anthropic SDK wrapper + Pydantic validator + system prompts."""

from afls.reasoning.client import AnthropicClient, Model
from afls.reasoning.prompts import (
    DISCIPLINE_HEADER,
    operator_context_blocks,
    system_blocks_for_query,
)
from afls.reasoning.validator import ReasoningError, complete_and_parse

__all__ = [
    "DISCIPLINE_HEADER",
    "AnthropicClient",
    "Model",
    "ReasoningError",
    "complete_and_parse",
    "operator_context_blocks",
    "system_blocks_for_query",
]
