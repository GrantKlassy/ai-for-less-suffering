"""Parse LLM output through Pydantic. Retry once on validation failure, then raise."""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from afls.reasoning.client import AnthropicClient, Model
from afls.reasoning.prompts import system_blocks_for_query


class ReasoningError(RuntimeError):
    """The LLM could not produce schema-valid output even after one retry."""


def _extract_json(text: str) -> str:
    """Strip ```json fences if present; otherwise return the text unchanged."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        trimmed = [line for line in lines if not line.startswith("```")]
        return "\n".join(trimmed).strip()
    return stripped


def complete_and_parse[T: BaseModel](
    client: AnthropicClient,
    *,
    model_cls: type[T],
    user_message: str,
    extra_context: str = "",
    model: Model = Model.OPUS,
    max_tokens: int = 8192,
) -> T:
    """Send a query, parse the response as `model_cls`, retry once on failure."""
    schema_json = json.dumps(model_cls.model_json_schema(), indent=2)
    system_blocks = system_blocks_for_query(schema_json, extra_context)

    first_raw = client.complete(
        model=model,
        system_blocks=system_blocks,
        user_message=user_message,
        max_tokens=max_tokens,
    )
    try:
        return model_cls.model_validate_json(_extract_json(first_raw))
    except (ValidationError, json.JSONDecodeError) as first_error:
        retry_message = (
            f"{user_message}\n\n"
            f"Your previous response failed validation:\n{first_error}\n\n"
            "Return ONLY JSON matching the schema in the system prompt. "
            "No prose, no code fences, no explanation."
        )
        second_raw = client.complete(
            model=model,
            system_blocks=system_blocks,
            user_message=retry_message,
            max_tokens=max_tokens,
        )
        try:
            return model_cls.model_validate_json(_extract_json(second_raw))
        except (ValidationError, json.JSONDecodeError) as second_error:
            raise ReasoningError(
                f"LLM failed to produce valid {model_cls.__name__} after one retry. "
                f"Second error: {second_error}\n\nLast raw response:\n{second_raw}"
            ) from second_error
