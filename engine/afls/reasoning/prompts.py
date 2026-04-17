"""System prompt construction. Operator context (BRAIN/MANIFESTO/CLAUDE) is cache-marked."""

from __future__ import annotations

from pathlib import Path

from anthropic.types import TextBlockParam

from afls.config import repo_root

DISCIPLINE_HEADER = """You are the reasoning engine for afls --- a typed graph tool for thinking \
about AI deployment toward the reduction of suffering.

Non-negotiable discipline:
- Separate descriptive (what is) from normative (what should be) at every turn. Never conflate.
- No hedging, no manifesto voice, no EA-discourse jargon the operator did not ask for.
- Coalition logic over purity logic: surface convergences between camps that hold different \
normative axioms, do not flatten the difference.
- Output valid JSON matching the schema provided in the system context. No prose, no fences, \
no preamble, no apology, no closing remarks --- just JSON.
"""

_DIRECTIVES_FILES: tuple[tuple[str, str], ...] = (
    ("BRAIN", "BRAIN.md"),
    ("MANIFESTO", "MANIFESTO.md"),
    ("CLAUDE", "CLAUDE.md"),
)


def _directives_dir() -> Path:
    return repo_root() / "directives-ai"


def operator_context_blocks() -> list[TextBlockParam]:
    """Load BRAIN, MANIFESTO, and CLAUDE.md as cache-marked system blocks."""
    directives = _directives_dir()
    blocks: list[TextBlockParam] = []
    for label, filename in _DIRECTIVES_FILES:
        text = (directives / filename).read_text()
        blocks.append(
            {
                "type": "text",
                "text": f"# {label}.md (operator context)\n\n{text}",
                "cache_control": {"type": "ephemeral"},
            }
        )
    return blocks


def system_blocks_for_query(
    schema_json: str,
    extra_context: str = "",
) -> list[TextBlockParam]:
    """Assemble system blocks: header, operator context, output schema, optional extra."""
    blocks: list[TextBlockParam] = [{"type": "text", "text": DISCIPLINE_HEADER}]
    blocks.extend(operator_context_blocks())
    blocks.append(
        {
            "type": "text",
            "text": (
                "# Output schema\n\nRespond with JSON that matches this JSON Schema "
                "exactly. No extra fields, no prose:\n\n"
                f"{schema_json}"
            ),
            "cache_control": {"type": "ephemeral"},
        }
    )
    if extra_context:
        blocks.append({"type": "text", "text": extra_context})
    return blocks
