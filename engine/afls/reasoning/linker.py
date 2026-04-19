"""Linker query: new DescriptiveClaims in, `claim_id -> [camp_id, ...]` out.

Runs after `ingest` so claims don't sit floating (held by no camp, invisible to
`find_descriptive_convergences`). No operator review step --- the Haiku pass
is authoritative and the CLI mutates each target camp's `held_descriptive` in
place. Mistakes are fixed by `afls edit camp_xyz` after.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from afls.reasoning.client import AnthropicClient, Model
from afls.reasoning.validator import complete_and_parse
from afls.schema import Camp, DescriptiveClaim
from afls.storage import list_nodes, load_node, save_node


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LinkerDraft(_StrictModel):
    """LLM-proposed camp linkages for a batch of new claims.

    `linkages` maps each new DescriptiveClaim id to the list of Camp ids that
    should hold it. An empty list means the claim doesn't fit any current camp
    (it stays floating).
    """

    linkages: dict[str, list[str]] = Field(default_factory=dict)


def _format_camp_for_linker(
    camp: Camp, claims_by_id: dict[str, DescriptiveClaim]
) -> str:
    lines = [f"- id: {camp.id}", f"  name: {camp.name}", f"  summary: {camp.summary}"]
    if camp.held_descriptive:
        lines.append("  held_descriptive (what kind of claims this camp holds today):")
        for ref in camp.held_descriptive:
            claim = claims_by_id.get(ref)
            if claim is None:
                continue
            text = claim.text[:100]
            suffix = "..." if len(claim.text) > 100 else ""
            lines.append(f"    - {ref}: {text}{suffix}")
    return "\n".join(lines)


def _format_new_claim(claim: DescriptiveClaim) -> str:
    return (
        f"- id: {claim.id}\n"
        f"  text: {claim.text}\n"
        f"  confidence: {claim.confidence}"
    )


def build_linker_context(
    camps: list[Camp],
    all_claims: list[DescriptiveClaim],
    new_claims: list[DescriptiveClaim],
) -> str:
    """System-block context: every camp's frame + each new claim."""
    claims_by_id = {c.id: c for c in all_claims}
    sections = ["# Camps (candidate holders)"]
    for camp in camps:
        sections.append(_format_camp_for_linker(camp, claims_by_id))
    sections.append("\n# New DescriptiveClaims to link")
    for claim in new_claims:
        sections.append(_format_new_claim(claim))
    return "\n".join(sections)


_USER_PROMPT = """For each new DescriptiveClaim, return the camp ids whose frame \
would include it. Rules:

- A claim can be held by multiple camps (common: descriptive facts that multiple \
camps cite for different normative reasons).
- An empty list is a valid answer --- if no current camp's frame fits, the claim \
stays floating. Do not force a linkage.
- Only use camp ids from the list in the system context. Do NOT invent new camps.
- Only return linkages for the new claim ids in the system context. Do NOT \
return linkages for claims that already exist in the graph.
- Match on what the claim is ABOUT, not on whether the camp would agree with it. \
A camp's `held_descriptive` is the set of claims within the camp's frame, not the \
set of claims the camp endorses.

Return ONLY JSON matching the schema in the system prompt. Format:

{"linkages": {"desc_example_1": ["camp_a", "camp_b"], "desc_example_2": []}}"""


def validate_linker_draft(
    draft: LinkerDraft,
    *,
    valid_camp_ids: set[str],
    valid_claim_ids: set[str],
) -> None:
    """Reject drafts that name unknown camp ids or claim ids the LLM invented.

    Raises `ValueError` on mismatch. The ingest CLI treats this as fatal ---
    the LLM must be re-prompted (or the operator must fix the graph) before
    mutation proceeds.
    """
    unknown_claims = set(draft.linkages.keys()) - valid_claim_ids
    if unknown_claims:
        raise ValueError(
            f"linker draft references unknown claim ids: {sorted(unknown_claims)}"
        )
    for claim_id, camp_ids in draft.linkages.items():
        unknown_camps = set(camp_ids) - valid_camp_ids
        if unknown_camps:
            raise ValueError(
                f"linker draft for {claim_id!r} references unknown camp ids: "
                f"{sorted(unknown_camps)}"
            )


def run_linker_query(
    client: AnthropicClient,
    data_dir: Path,
    *,
    new_claims: list[DescriptiveClaim],
    model: Model = Model.HAIKU,
) -> LinkerDraft:
    """Load camps, ask Haiku to map each new claim to holding camps, return draft.

    Rejects any draft that names camp ids not in the loaded set or claim ids not
    in `new_claims`. Haiku is fast and cheap --- this runs after every ingest.
    """
    if not new_claims:
        return LinkerDraft(linkages={})

    camps = list_nodes(Camp, data_dir)
    all_claims = list_nodes(DescriptiveClaim, data_dir)
    context = build_linker_context(camps, all_claims, new_claims)

    draft = complete_and_parse(
        client,
        model_cls=LinkerDraft,
        user_message=_USER_PROMPT,
        extra_context=context,
        model=model,
    )

    validate_linker_draft(
        draft,
        valid_camp_ids={c.id for c in camps},
        valid_claim_ids={c.id for c in new_claims},
    )
    return draft


def apply_linker_draft(draft: LinkerDraft, data_dir: Path) -> dict[str, int]:
    """Mutate camps on disk to hold each linked claim. Idempotent.

    Returns `{"linked": N, "floating": M, "camps_touched": K}`. A claim with
    an empty camp-id list counts toward `floating` --- it intentionally stays
    un-held. Re-applying the same draft is a no-op: each camp's
    `held_descriptive` is a set-collapsed sorted list, so duplicates cannot
    accumulate.
    """
    linked = 0
    floating = 0
    camps_touched: set[str] = set()
    for claim_id, camp_ids in draft.linkages.items():
        if not camp_ids:
            floating += 1
            continue
        linked += 1
        for camp_id in camp_ids:
            camp = load_node(Camp, camp_id, data_dir)
            if claim_id in camp.held_descriptive:
                continue
            camp.held_descriptive = sorted({*camp.held_descriptive, claim_id})
            save_node(camp, data_dir)
            camps_touched.add(camp_id)
    return {
        "linked": linked,
        "floating": floating,
        "camps_touched": len(camps_touched),
    }
