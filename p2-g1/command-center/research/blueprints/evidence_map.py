"""Evidence-map blueprint: every harvested claim is scored for coverage holes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


@dataclass
class MappedClaim:
    id: str
    text: str
    evidence_ids: list[str]
    hole: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceMap:
    claims: list[MappedClaim]
    known_evidence_ids: list[str]
    holes: list[str] = field(default_factory=list)
    coverage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims": [c.to_dict() for c in self.claims],
            "known_evidence_ids": list(self.known_evidence_ids),
            "holes": list(self.holes),
            "coverage": self.coverage,
            "hole_count": len(self.holes),
            "claim_count": len(self.claims),
        }


def map_evidence(
    claims: Iterable[Mapping[str, Any]],
    evidence: Iterable[Mapping[str, Any]] | None = None,
) -> EvidenceMap:
    known = [str(e.get("id") or "") for e in (evidence or []) if e.get("id")]
    known_set = {k for k in known if k}
    mapped: list[MappedClaim] = []
    holes: list[str] = []
    for claim in claims:
        cid = str(claim.get("id") or "")
        ids = [str(x) for x in (claim.get("evidence_ids") or []) if x]
        live_ids = [i for i in ids if (not known_set or i in known_set)]
        hole = len(live_ids) == 0
        mapped.append(
            MappedClaim(
                id=cid,
                text=str(claim.get("text") or ""),
                evidence_ids=ids,
                hole=hole,
            )
        )
        if hole:
            holes.append(cid)
    total = len(mapped)
    covered = total - len(holes)
    coverage = 1.0 if total == 0 else covered / total
    return EvidenceMap(
        claims=mapped,
        known_evidence_ids=known,
        holes=holes,
        coverage=coverage,
    )
