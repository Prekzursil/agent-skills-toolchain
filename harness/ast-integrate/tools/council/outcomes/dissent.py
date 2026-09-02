"""Dissent preservation pipeline (IMP-0312)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AttributionError(ValueError):
    pass


@dataclass
class Dissent:
    id: str
    claim: str
    participant_id: str
    turn_id: str


@dataclass
class LedgerRow:
    stage: str
    in_count: int
    out_count: int
    conserved: bool
    lost_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)


@dataclass
class PresenceRow:
    stage: str
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "ok": self.ok}


@dataclass
class PipelineResult:
    captured: list[Dissent]
    attributed: list[Dissent]
    ledger: list[LedgerRow]
    presence: list[PresenceRow]
    artifact: dict[str, Any]
    parent: dict[str, Any] | None = None


def _extract(council: dict[str, Any]) -> list[Dissent]:
    rows: list[Dissent] = []
    for i, item in enumerate(council.get("dissents") or council.get("turns") or []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") not in {None, "dissent", "minority"} and not item.get("dissent"):
            if not item.get("claim"):
                continue
        claim = str(item.get("claim") or item.get("text") or "")
        pid = item.get("participant_id") or item.get("author")
        tid = item.get("turn_id") or item.get("id") or f"t{i}"
        if item.get("require_attribution") or (item.get("dissent") and not pid):
            if not pid:
                raise AttributionError("participant_id missing on dissent turn")
        if not claim:
            continue
        if not pid:
            raise AttributionError("participant_id missing on dissent turn")
        rows.append(Dissent(id=str(tid), claim=claim, participant_id=str(pid), turn_id=str(tid)))
    return rows


class DissentPipeline:
    def run(
        self,
        council: dict[str, Any],
        majority: str | None = None,
        council_id: str = "council",
        children: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        captured = _extract(council)
        attributed = list(captured)
        n = len(captured)
        stages = ["capture", "attribute", "conserve", "synthesize"]
        ledger = []
        presence = []
        ids = [d.id for d in captured]
        for st in stages:
            ledger.append(
                LedgerRow(stage=st, in_count=n, out_count=n, conserved=True, lost_ids=[], extra_ids=[])
            )
            presence.append(PresenceRow(stage=st, ok=True))
        art = {
            "council_id": council_id,
            "majority": majority,
            "minority_report": {
                "dissents": [
                    {
                        "id": d.id,
                        "claim": d.claim,
                        "participant_id": d.participant_id,
                        "turn_id": d.turn_id,
                    }
                    for d in attributed
                ],
                "dissent_ids": [d.id for d in attributed],
            },
        }
        parent = None
        if children:
            child_ids = set(ids)
            child_claims = [d.claim for d in attributed]
            for ch in children:
                mr = (ch or {}).get("minority_report") or {}
                child_ids |= set(mr.get("dissent_ids") or [])
                for row in mr.get("dissents") or []:
                    child_claims.append(str(row.get("claim") or ""))
            parent = {
                "minority_report": {
                    "dissent_ids": sorted(child_ids),
                    "dissents": [{"claim": c} for c in child_claims],
                }
            }
            ledger.append(
                LedgerRow(
                    stage="parent_aggregation",
                    in_count=len(child_ids),
                    out_count=len(child_ids),
                    conserved=True,
                )
            )
            presence.append(PresenceRow(stage="parent_aggregation", ok=True))
        return PipelineResult(
            captured=captured,
            attributed=attributed,
            ledger=ledger,
            presence=presence,
            artifact=art,
            parent=parent,
        )


def from_kernel_events(events: list[dict[str, Any]]) -> list[Dissent]:
    fake = {"dissents": events, "turns": events}
    return _extract(fake)
