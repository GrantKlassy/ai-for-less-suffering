"""Ingest query: article text in, drafted Source + Claims + Evidence out.

Mirrors the shape of `afls.queries.steelman` but runs once per URL rather than
per-target-intervention. The LLM is constrained by a strict Pydantic schema; its
output is a *draft* --- the CLI then maps it to concrete nodes with generated
IDs, stamps provenance, and saves YAML. The operator reviews/edits the YAML
after.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from afls.reasoning.client import AnthropicClient, Model
from afls.reasoning.validator import complete_and_parse
from afls.schema import (
    RELIABILITY_PRIOR,
    DescriptiveClaim,
    MethodTag,
    SourceKind,
    Support,
)
from afls.storage import list_nodes

_SLUG_PATTERN = r"^[a-z0-9_]+$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IngestDraftSource(_StrictModel):
    """LLM-proposed Source metadata. `id_slug` becomes the filename stem."""

    id_slug: str = Field(
        min_length=2, max_length=40, pattern=_SLUG_PATTERN,
        description="Short lowercase identifier, 2-5 words with underscores. Becomes the "
        "source file stem: src_<id_slug>.yaml.",
    )
    source_kind: SourceKind
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    published_at: str = Field(default="")
    reliability: float = Field(ge=0.0, le=1.0)
    notes: str = Field(default="")


class IngestDraftClaim(_StrictModel):
    """A DescriptiveClaim the LLM extracted from the article."""

    id_slug: str = Field(
        min_length=2, max_length=50, pattern=_SLUG_PATTERN,
        description="Short lowercase identifier. Becomes desc_<id_slug>.yaml.",
    )
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class IngestDraftEvidence(_StrictModel):
    """A Source->Claim edge. `claim_idx` is the 0-based index into the claims list."""

    claim_idx: int = Field(ge=0)
    locator: str = Field(default="")
    quote: str = Field(default="")
    method_tag: MethodTag
    supports: Support = Support.SUPPORT
    weight: float = Field(ge=0.0, le=1.0)


class IngestLLMOutput(_StrictModel):
    """Complete draft the LLM must return for the ingest query."""

    source: IngestDraftSource
    claims: list[IngestDraftClaim] = Field(min_length=1, max_length=5)
    evidence: list[IngestDraftEvidence] = Field(min_length=1)


_USER_PROMPT = """Draft a Source, one to five DescriptiveClaims, and one or more \
Evidence edges from the article provided in the system context.

For the Source:
- pick source_kind from the enum (paper, dataset, filing, press, primary_doc, blog, \
dashboard). Match the nature of the artifact, not its subject matter: a news article \
about a dataset is still `press`.
- id_slug is 2-5 words, lowercase, separated by underscores. Becomes the filename.
- reliability should be within ~0.15 of the prior for its kind (see prior table in \
context) unless you can justify a sharper score in `notes`.
- title is the article's headline. authors are the byline if present.
- published_at is the publication date if available (YYYY, YYYY-MM, or YYYY-MM-DD).

For each DescriptiveClaim:
- state a factual assertion about the world. Not a value claim (that's normative, not \
in scope here).
- confidence reflects how strongly the ARTICLE backs the claim, not how strongly you \
personally believe it.
- if the claim already exists in the graph (see dedup list in context), OMIT it --- do \
not restate existing claims.
- id_slug is a short lowercase underscore-separated identifier. Becomes \
desc_<id_slug>.yaml.

For each Evidence edge:
- claim_idx is the 0-based index of the DescriptiveClaim it supports within the \
`claims` list you are returning (NOT the dedup list). Every Evidence must reference a \
claim you are creating.
- quote is a short (~1 sentence) excerpt from the article. Omit if ToS/paywall would \
make copying problematic.
- locator points into the article: section title, figure/table number, paragraph cue.
- method_tag describes HOW the article backs this claim: direct_measurement, \
expert_estimate, triangulation, journalistic_report, primary_testimony, \
modeled_projection, leaked_document.
- weight is the local contribution of THIS evidence to the claim (0-1). High if the \
article is a primary source backing the claim directly; lower if it is reporting on \
something else.

No hedging. No manifesto voice. Do not invent claims the article does not make. If the \
article is thin and yields fewer than 1-5 novel claims, return the smaller honest set. \
Return ONLY JSON matching the schema in the system prompt."""


def _format_prior_table() -> str:
    lines = ["## Reliability priors by source_kind"]
    for kind, value in sorted(RELIABILITY_PRIOR.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {kind.value}: {value:.2f}")
    return "\n".join(lines)


def _format_dedup_claims(existing: list[DescriptiveClaim]) -> str:
    if not existing:
        return "## Existing descriptive claims (none yet)"
    lines = [
        "## Existing descriptive claims "
        "(DO NOT duplicate; omit from output if article restates)"
    ]
    for claim in sorted(existing, key=lambda c: c.id):
        lines.append(f"- `{claim.id}` (confidence {claim.confidence:.2f}): {claim.text}")
    return "\n".join(lines)


def build_ingest_context(
    url: str, article_text: str, existing: list[DescriptiveClaim]
) -> str:
    """Build the system-block extra_context for an ingest call."""
    sections = [
        _format_prior_table(),
        "",
        _format_dedup_claims(existing),
        "",
        "## Article URL",
        url,
        "",
        "## Article text (may be truncated at a UTF-8 boundary)",
        article_text,
    ]
    return "\n".join(sections)


def run_ingest_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    url: str,
    article_text: str,
    model: Model = Model.OPUS,
) -> IngestLLMOutput:
    """Load existing claims for dedup, call Claude, return the validated draft."""
    existing = list_nodes(DescriptiveClaim, data_dir)
    context = build_ingest_context(url, article_text, existing)
    return complete_and_parse(
        client,
        model_cls=IngestLLMOutput,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )
