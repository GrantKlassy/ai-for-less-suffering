"""Provenance schema + reliability-prior tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from afls.schema import (
    LOW_TRUST_KINDS,
    RELIABILITY_PRIOR,
    Provenance,
    Source,
    SourceKind,
    new_id,
)


def _stamp() -> Provenance:
    return Provenance(
        method="httpx",
        tool="afls-ingest/0.1.0",
        git_sha="deadbeef",
        at=datetime(2026, 4, 18, 10, 15, 0, tzinfo=UTC),
        raw_content_hash="e3b0c442" + "0" * 56,
    )


def test_provenance_basic() -> None:
    prov = _stamp()
    assert prov.method == "httpx"
    assert prov.raw_content_hash is not None
    assert prov.raw_content_hash.startswith("e3b0c442")


def test_provenance_rejects_unknown_method() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            method="wget",
            tool="afls-ingest/0.1.0",
            git_sha="deadbeef",
            at=datetime.now(UTC),
        )


def test_provenance_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            method="httpx",
            tool="afls-ingest/0.1.0",
            git_sha="deadbeef",
            at=datetime.now(UTC),
            smuggled="nope",  # type: ignore[call-arg]
        )


def test_provenance_requires_tool_and_sha() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            method="httpx",
            tool="",
            git_sha="deadbeef",
            at=datetime.now(UTC),
        )
    with pytest.raises(ValidationError):
        Provenance(
            method="httpx",
            tool="afls-ingest/0.1.0",
            git_sha="",
            at=datetime.now(UTC),
        )


def test_provenance_hash_optional() -> None:
    prov = Provenance(
        method="manual_paste",
        tool="afls-ingest/0.1.0",
        git_sha="deadbeef",
        at=datetime.now(UTC),
    )
    assert prov.raw_content_hash is None


def test_source_defaults_no_provenance() -> None:
    source = Source(
        id=new_id("src"),
        source_kind=SourceKind.PAPER,
        title="Old source without provenance",
        reliability=0.8,
    )
    assert source.provenance is None


def test_source_with_provenance_roundtrips() -> None:
    source = Source(
        id=new_id("src"),
        source_kind=SourceKind.PAPER,
        title="test paper",
        reliability=0.82,
        provenance=_stamp(),
    )
    payload = source.model_dump(mode="json")
    rebuilt = Source.model_validate(payload)
    assert rebuilt.model_dump(mode="json") == payload
    assert rebuilt.provenance is not None
    assert rebuilt.provenance.method == "httpx"


def test_reliability_prior_covers_every_kind() -> None:
    for kind in SourceKind:
        assert kind in RELIABILITY_PRIOR, f"{kind} missing from RELIABILITY_PRIOR"
        assert 0.0 <= RELIABILITY_PRIOR[kind] <= 1.0


def test_reliability_prior_orders_kinds_sensibly() -> None:
    assert RELIABILITY_PRIOR[SourceKind.PRIMARY_DOC] > RELIABILITY_PRIOR[SourceKind.PRESS]
    assert RELIABILITY_PRIOR[SourceKind.FILING] > RELIABILITY_PRIOR[SourceKind.BLOG]
    assert RELIABILITY_PRIOR[SourceKind.DATASET] > RELIABILITY_PRIOR[SourceKind.BLOG]
    assert RELIABILITY_PRIOR[SourceKind.PAPER] > RELIABILITY_PRIOR[SourceKind.PRESS]


def test_low_trust_kinds_contains_expected() -> None:
    assert SourceKind.PRESS in LOW_TRUST_KINDS
    assert SourceKind.BLOG in LOW_TRUST_KINDS
    assert SourceKind.PRIMARY_DOC not in LOW_TRUST_KINDS
    assert SourceKind.FILING not in LOW_TRUST_KINDS
    assert SourceKind.DATASET not in LOW_TRUST_KINDS
