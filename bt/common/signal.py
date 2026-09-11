"""The one result contract every system emits (design/SYSTEM-DESIGN.md §4).

A signal without evidence is rejected: every finding must point back to the
rows or documents that produced it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SYSTEMS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")


@dataclass(frozen=True)
class Signal:
    signal_id: str
    entity_id: str          # the borrower the finding is about
    system: str             # S1..S7
    type: str               # e.g. UNDISCLOSED_SECURED_PARTY
    severity: float         # how bad if true, 0..1
    confidence: float       # how sure the system is, 0..1
    evidence: tuple[str, ...]
    explanation: str
    observed_month: int     # month index in the synthetic timeline (0..23)
    related_entities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.system not in SYSTEMS:
            raise ValueError(f"unknown system {self.system!r}")
        if not self.evidence:
            raise ValueError(f"{self.signal_id}: a signal without evidence is rejected")
        for name in ("severity", "confidence"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{self.signal_id}: {name}={v} outside 0..1")

    def row(self) -> dict:
        d = asdict(self)
        d["evidence"] = list(self.evidence)
        d["related_entities"] = list(self.related_entities)
        return d
