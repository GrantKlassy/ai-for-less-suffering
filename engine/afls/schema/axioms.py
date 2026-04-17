"""Axiom families tag normative claims with their normative-tradition of origin.

Listed flat so coalition logic can reason over them: identical policy outputs from
different axiom families count as agreement (MANIFESTO).
"""

from __future__ import annotations

from enum import StrEnum


class AxiomFamily(StrEnum):
    KANTIAN = "kantian"
    CAPABILITIES = "capabilities"
    THEOLOGICAL = "theological"
    CONSEQUENTIALIST = "consequentialist"
    E_ACC = "e_acc"
    EA_80K = "ea_80k"
    POKER_EV = "poker_ev"
    OTHER = "other"
