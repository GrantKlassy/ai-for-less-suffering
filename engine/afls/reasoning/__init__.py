"""Reasoning layer: Anthropic SDK wrapper + Pydantic validator + system prompts."""

from afls.reasoning.client import AnthropicClient, Model
from afls.reasoning.ingest import (
    IngestDraftClaim,
    IngestDraftEvidence,
    IngestDraftSource,
    IngestLLMOutput,
    build_ingest_context,
    run_ingest_query,
)
from afls.reasoning.prompts import (
    DISCIPLINE_HEADER,
    operator_context_blocks,
    system_blocks_for_query,
)
from afls.reasoning.validator import ReasoningError, complete_and_parse

__all__ = [
    "DISCIPLINE_HEADER",
    "AnthropicClient",
    "IngestDraftClaim",
    "IngestDraftEvidence",
    "IngestDraftSource",
    "IngestLLMOutput",
    "Model",
    "ReasoningError",
    "build_ingest_context",
    "complete_and_parse",
    "operator_context_blocks",
    "run_ingest_query",
    "system_blocks_for_query",
]
