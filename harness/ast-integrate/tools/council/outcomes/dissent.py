#!/usr/bin/env python3
"""Dissent and minority-report preservation pipeline (IMP-0312).

Every dissent a council produces must be *captured*, *attributed* to a participant and a
turn, carried verbatim into the *synthesis* artifact, and remain reachable by id after any
*parent aggregation*. Two signals are measured at every stage and recorded rather than
asserted:

* **conservation** -- the set of dissent ids entering a stage equals the set leaving it
  (:func:`conservation` -> :class:`LedgerRow` with ``lost_ids`` / ``extra_ids``);
* **presence** -- each dissent's distinctive claim survives verbatim in the stage output, or
  is resolvable through ``artifact["dissent_index"][id]`` (:func:`presence_check` ->
  :class:`PresenceRow` with per-dissent :class:`PresenceFailure` reasons).

A dissent without a ``participant_id`` is refused with :class:`AttributionError` -- never
silently dropped and never attributed by guesswork. A unanimous council yields an empty
minority report (nothing is fabricated).

Two mutants exist so the checks can be shown to discriminate: :func:`drop_dissent` removes
one dissent from an artifact (conservation must fire), :func:`summarise_away` keeps the id
slot but replaces the claim with a generic gloss everywhere (presence must fire while counts
still match).

Input shapes accepted by :meth:`DissentPipeline.run`: a list of turn dicts (``turn_id``,
``participant_id``, ``option_id``, ``claim``, ``is_dissent`` / ``kind="dissent"`` ...), a
list of :class:`Dissent`, raw IMP-0264 kernel events (``{"event": "turn", "payload": {...}}``,
see :func:`from_kernel_events`), or a council mapping carrying ``turns``.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

SPEC_ANCHORS: tuple[str, ...] = (
    "_USER-PROMPTS.md:11340 dissent preserved in synthesis",
    "catalog tests_required spec 11342 planted-drop control",
    "FAILURE-MODES FC-11340 dropped-dissent class",
)

STAGE_CAPTURE = "capture"
STAGE_ATTRIBUTE = "attribute"
STAGE_SYNTHESIS = "synthesis"
STAGE_PARENT = "parent_aggregation"

DISSENT_KINDS: frozenset[str] = frozenset({"dissent", "minority", "minority-report", "objection"})
GENERIC_GLOSS = "minority disagreed"


class AttributionError(ValueError):
    """A dissent could not be attributed to a participant; refusing to drop or guess."""


class ConservationError(ValueError):
    """A pipeline stage lost or invented a dissent (raised only in ``strict`` runs)."""


# --------------------------------------------------------------------------- data
@dataclass
class Dissent:
    """One attributed dissent. ``id`` is stable: ``dsnt:<council_id>:<turn_id>``."""

    id: str
    claim: str
    participant_id: str
    turn_id: str
    option_id: str = ""
    role: str = ""
    round_index: int = 0
    rationale: str = ""
    evidence_cites: list[str] = field(default_factory=list)
    council_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Dissent":
        cites = row.get("evidence_cites") or []
        return cls(
            id=str(row.get("id") or ""),
            claim=str(row.get("claim") or ""),
            participant_id=str(row.get("participant_id") or ""),
            turn_id=str(row.get("turn_id") or ""),
            option_id=str(row.get("option_id") or ""),
            role=str(row.get("role") or ""),
            round_index=int(row.get("round_index") or 0),
            rationale=str(row.get("rationale") or ""),
            evidence_cites=[str(c) for c in cites] if isinstance(cites, (list, tuple)) else [],
            council_id=str(row.get("council_id") or ""),
        )


@dataclass
class LedgerRow:
    """Conservation record for one stage: ids in versus ids out."""

    stage: str
    in_count: int
    out_count: int
    conserved: bool
    lost_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PresenceFailure:
    """One dissent whose claim did not survive a stage."""

    dissent_id: str
    reason: str  # "dropped" (id gone) | "summarised-away" (id kept, claim gone)
    claim: str
    found: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PresenceRow:
    """Text-presence record for one stage."""

    stage: str
    ok: bool
    checked: int = 0
    failures: list[PresenceFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "checked": self.checked,
            "failures": [f.to_dict() for f in self.failures],
        }


@dataclass
class PipelineResult:
    """Everything one run produced, including the per-stage ledgers."""

    captured: list[Dissent]
    attributed: list[Dissent]
    ledger: list[LedgerRow]
    presence: list[PresenceRow]
    artifact: dict[str, Any]
    parent: dict[str, Any] | None = None
    council_id: str = ""

    @property
    def conserved(self) -> bool:
        return all(row.conserved for row in self.ledger) and all(p.ok for p in self.presence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "council_id": self.council_id,
            "captured": [d.to_dict() for d in self.captured],
            "attributed": [d.to_dict() for d in self.attributed],
            "ledger": [r.to_dict() for r in self.ledger],
            "presence": [p.to_dict() for p in self.presence],
            "artifact": self.artifact,
            "parent": self.parent,
            "conserved": self.conserved,
        }


# --------------------------------------------------------------------------- input adapters
def _turn_from_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten one kernel ``turn`` event: envelope fields fill gaps in the payload."""
    payload = event.get("payload")
    turn: dict[str, Any] = dict(payload) if isinstance(payload, Mapping) else {}
    for key in ("turn_id", "participant_id", "round_index", "role"):
        if key in event and not turn.get(key):
            turn[key] = event[key]
    return turn


def from_kernel_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Adapt IMP-0264 kernel events to pipeline turns.

    Only ``event == "turn"`` records (or records carrying a ``payload``) are turns; other
    kernel events (round boundaries, stop rules) are ignored. No participant output is
    written behind the kernel: the payload is taken as emitted.
    """
    turns: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if event.get("event") == "turn" or isinstance(event.get("payload"), Mapping):
            turns.append(_turn_from_event(event))
    return turns


def _turn_from_dissent(dissent: Dissent) -> dict[str, Any]:
    turn = dissent.to_dict()
    turn["is_dissent"] = True
    turn["kind"] = "dissent"
    return turn


def _normalise_turns(council: Any) -> list[dict[str, Any]]:
    """Coerce any accepted input shape into a list of turn dicts (order preserved)."""
    if isinstance(council, Mapping):
        for key in ("turns", "dissents", "events"):
            if isinstance(council.get(key), (list, tuple)):
                return _normalise_turns(council[key])
        raise TypeError("council mapping carries no turns/dissents/events list")
    if isinstance(council, (str, bytes)) or not isinstance(council, Iterable):
        raise TypeError(f"council must be a list of turns, got {type(council).__name__}")
    turns: list[dict[str, Any]] = []
    for item in council:
        if isinstance(item, Dissent):
            turns.append(_turn_from_dissent(item))
        elif isinstance(item, Mapping):
            if item.get("event") == "turn" and isinstance(item.get("payload"), Mapping):
                turns.append(_turn_from_event(item))
            else:
                turns.append(dict(item))
    return turns


def _majority_parts(majority: Any) -> tuple[str, str]:
    """Return ``(option_id, claim)`` from a majority mapping or bare string."""
    if isinstance(majority, Mapping):
        return str(majority.get("option_id") or ""), str(majority.get("claim") or "")
    if isinstance(majority, str):
        return "", majority
    return "", ""


def is_dissent_turn(turn: Mapping[str, Any], majority_option: str = "") -> bool:
    """A turn is a dissent when flagged, kinded as one, or voting against the majority option."""
    if turn.get("is_dissent") or turn.get("dissent") is True:
        return True
    if str(turn.get("kind") or "").strip().lower() in DISSENT_KINDS:
        return True
    option = str(turn.get("option_id") or "")
    return bool(majority_option) and bool(option) and option != majority_option


def _dissent_from_turn(turn: Mapping[str, Any], index: int, council_id: str) -> Dissent:
    turn_id = str(turn.get("turn_id") or turn.get("id") or f"turn-{index}")
    participant = str(turn.get("participant_id") or turn.get("author") or turn.get("speaker") or "")
    claim = str(turn.get("claim") or turn.get("rationale") or turn.get("text") or "")
    cites = turn.get("evidence_cites") or []
    return Dissent(
        id=f"dsnt:{council_id}:{turn_id}",
        claim=claim,
        participant_id=participant,
        turn_id=turn_id,
        option_id=str(turn.get("option_id") or ""),
        role=str(turn.get("role") or ""),
        round_index=int(turn.get("round_index") or 0),
        rationale=str(turn.get("rationale") or ""),
        evidence_cites=[str(c) for c in cites] if isinstance(cites, (list, tuple)) else [],
        council_id=council_id,
    )


# --------------------------------------------------------------------------- stages
def capture(turns: Sequence[Mapping[str, Any]], majority: Any, council_id: str) -> tuple[list[str], list[Dissent]]:
    """Stage 1: identify dissent turns. Returns ``(detected_ids, captured)``.

    ``detected_ids`` are the ids the detector saw; ``captured`` are the objects built from
    them. They are compared by :func:`conservation` so a capture that silently skips a turn
    (empty claim, odd shape) shows up as ``lost_ids`` instead of vanishing.
    """
    majority_option, _ = _majority_parts(majority)
    detected: list[str] = []
    captured: list[Dissent] = []
    for index, turn in enumerate(turns):
        if not is_dissent_turn(turn, majority_option):
            continue
        dissent = _dissent_from_turn(turn, index, council_id)
        detected.append(dissent.id)
        captured.append(dissent)
    return detected, captured


def attribute(captured: Sequence[Dissent]) -> list[Dissent]:
    """Stage 2: every dissent must name its participant and turn, or the run is refused."""
    attributed: list[Dissent] = []
    for dissent in captured:
        if not dissent.participant_id.strip():
            raise AttributionError(
                f"dissent turn {dissent.turn_id!r} (round {dissent.round_index}, role "
                f"{dissent.role!r}) has no participant_id; refusing to drop or guess attribution"
            )
        if not dissent.turn_id.strip():
            raise AttributionError(
                f"dissent by {dissent.participant_id!r} has no turn_id; cannot attribute"
            )
        attributed.append(dissent)
    return attributed


def _minority_line(dissent: Dissent) -> str:
    return f"[{dissent.id}] {dissent.participant_id} ({dissent.role or 'participant'}): {dissent.claim}"


def synthesise(
    attributed: Sequence[Dissent],
    majority: Any,
    council_id: str,
    turns: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Stage 3: build the final council artifact with the minority report carried verbatim."""
    majority_option, majority_claim = _majority_parts(majority)
    supporters = sorted(
        str(t.get("participant_id") or "")
        for t in turns
        if str(t.get("option_id") or "") == majority_option and not is_dissent_turn(t, majority_option)
    )
    dissent_rows = [d.to_dict() for d in attributed]
    ids = [d.id for d in attributed]
    summary = (
        f"{council_id}: majority option {majority_option or '(none)'}: {majority_claim or '(no claim)'}"
        f" | {len(attributed)} dissent(s) recorded verbatim in minority_report"
    )
    return {
        "council_id": council_id,
        "majority": dict(majority) if isinstance(majority, Mapping) else {"option_id": majority_option, "claim": majority_claim},
        "decision": {
            "option_id": majority_option,
            "claim": majority_claim,
            "supporters": [pid for pid in supporters if pid],
        },
        "minority_report": {
            "count": len(attributed),
            "dissent_ids": ids,
            "dissents": dissent_rows,
        },
        "dissent_index": {d.id: d.claim for d in attributed},
        "synthesis": {
            "summary": summary,
            "minority_lines": [_minority_line(d) for d in attributed],
        },
        "participants": sorted({str(t.get("participant_id") or "") for t in turns} - {""}),
        "pipeline_stages": [STAGE_CAPTURE, STAGE_ATTRIBUTE, STAGE_SYNTHESIS],
    }


def dissents_from_artifact(artifact: Any) -> list[Dissent]:
    """Read the dissents an artifact (or :class:`PipelineResult`) actually carries."""
    if isinstance(artifact, PipelineResult):
        artifact = artifact.artifact
    if not isinstance(artifact, Mapping):
        return []
    report = artifact.get("minority_report")
    if not isinstance(report, Mapping):
        return []
    rows = report.get("dissents")
    if not isinstance(rows, (list, tuple)):
        return []
    return [Dissent.from_dict(row) for row in rows if isinstance(row, Mapping)]


def aggregate_parent(
    own: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]],
    council_id: str,
) -> dict[str, Any]:
    """Stage 4: a parent view over this council and its children; every child id stays reachable."""
    merged: list[Dissent] = []
    seen: set[str] = set()
    by_council: dict[str, list[str]] = {}
    for source in [own, *children]:
        cid = str(source.get("council_id") or "") if isinstance(source, Mapping) else ""
        for dissent in dissents_from_artifact(source):
            by_council.setdefault(cid or dissent.council_id or "?", []).append(dissent.id)
            if dissent.id in seen:
                continue
            seen.add(dissent.id)
            merged.append(dissent)
    ids = sorted(d.id for d in merged)
    return {
        "council_id": council_id,
        "kind": "parent-aggregation",
        "children": [str(c.get("council_id") or "") for c in children if isinstance(c, Mapping)],
        "majority": deepcopy(own.get("majority")) if isinstance(own, Mapping) else None,
        "minority_report": {
            "count": len(merged),
            "dissent_ids": ids,
            "dissents": [d.to_dict() for d in sorted(merged, key=lambda d: d.id)],
            "by_council": {cid: sorted(v) for cid, v in sorted(by_council.items())},
        },
        "dissent_index": {d.id: d.claim for d in merged},
        "synthesis": {
            "summary": (
                f"{council_id}: parent aggregation over {1 + len(children)} council(s); "
                f"{len(merged)} dissent(s) reachable by id."
            ),
            "minority_lines": [_minority_line(d) for d in sorted(merged, key=lambda d: d.id)],
        },
        "pipeline_stages": [STAGE_CAPTURE, STAGE_ATTRIBUTE, STAGE_SYNTHESIS, STAGE_PARENT],
    }


# --------------------------------------------------------------------------- the two signals
def _ids_of(items: Iterable[Any]) -> list[str]:
    ids: list[str] = []
    for item in items:
        if isinstance(item, Dissent):
            ids.append(item.id)
        elif isinstance(item, Mapping):
            ids.append(str(item.get("id") or item.get("dissent_id") or ""))
        else:
            ids.append(str(item))
    return ids


def conservation(incoming: Iterable[Any], outgoing: Iterable[Any], stage: str = STAGE_SYNTHESIS) -> LedgerRow:
    """Signal 1: in-count versus out-count with the exact ids lost or invented."""
    in_ids = _ids_of(incoming)
    out_ids = _ids_of(outgoing)
    in_set, out_set = set(in_ids), set(out_ids)
    duplicates = sorted({i for i in out_ids if out_ids.count(i) > 1} | {i for i in in_ids if in_ids.count(i) > 1})
    lost = sorted(in_set - out_set)
    extra = sorted(out_set - in_set)
    conserved = not lost and not extra and len(in_ids) == len(out_ids)
    return LedgerRow(
        stage=stage,
        in_count=len(in_ids),
        out_count=len(out_ids),
        conserved=conserved,
        lost_ids=lost,
        extra_ids=extra,
        duplicate_ids=duplicates,
    )


def presence_check(expected: Iterable[Dissent], artifact: Any, stage: str = STAGE_SYNTHESIS) -> PresenceRow:
    """Signal 2: each claim survives verbatim in ``artifact`` or resolves through its index.

    A dissent whose id is still listed but whose claim text is gone is ``summarised-away``;
    one whose id is gone as well is ``dropped``.
    """
    if isinstance(artifact, PipelineResult):
        artifact = artifact.artifact
    payload = artifact if isinstance(artifact, Mapping) else {}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    index = payload.get("dissent_index") if isinstance(payload.get("dissent_index"), Mapping) else {}
    listed = set(_ids_of(dissents_from_artifact(payload)))
    report = payload.get("minority_report")
    if isinstance(report, Mapping) and isinstance(report.get("dissent_ids"), (list, tuple)):
        listed |= {str(i) for i in report["dissent_ids"]}
    failures: list[PresenceFailure] = []
    checked = 0
    for dissent in expected:
        checked += 1
        indexed = index.get(dissent.id)
        if dissent.claim:
            if dissent.claim in blob:
                continue
            if indexed == dissent.claim:
                continue
        elif dissent.id in index or dissent.id in listed:
            continue  # nothing textual to lose; the id resolves
        reason = "summarised-away" if (dissent.id in listed or dissent.id in index) else "dropped"
        failures.append(
            PresenceFailure(
                dissent_id=dissent.id,
                reason=reason,
                claim=dissent.claim,
                found=str(indexed) if indexed is not None else None,
            )
        )
    return PresenceRow(stage=stage, ok=not failures, checked=checked, failures=failures)


# --------------------------------------------------------------------------- mutants
def _find_entry(artifact: Mapping[str, Any], dissent_id: str) -> dict[str, Any]:
    report = artifact.get("minority_report") if isinstance(artifact, Mapping) else None
    rows = report.get("dissents") if isinstance(report, Mapping) else None
    for row in rows or []:
        if isinstance(row, Mapping) and str(row.get("id")) == dissent_id:
            return dict(row)
    raise KeyError(f"dissent {dissent_id!r} is not in the artifact")


def drop_dissent(artifact: Mapping[str, Any], dissent_id: str) -> dict[str, Any]:
    """Planted-drop mutant: remove one dissent (entry, id, index, synthesis line) entirely."""
    _find_entry(artifact, dissent_id)
    mutant = deepcopy(dict(artifact))
    report = mutant["minority_report"]
    report["dissents"] = [r for r in report.get("dissents", []) if str(r.get("id")) != dissent_id]
    report["dissent_ids"] = [i for i in report.get("dissent_ids", []) if str(i) != dissent_id]
    report["count"] = len(report["dissents"])
    if isinstance(mutant.get("dissent_index"), dict):
        mutant["dissent_index"].pop(dissent_id, None)
    synthesis = mutant.get("synthesis")
    if isinstance(synthesis, dict) and isinstance(synthesis.get("minority_lines"), list):
        synthesis["minority_lines"] = [
            line for line in synthesis["minority_lines"] if not str(line).startswith(f"[{dissent_id}]")
        ]
    return mutant


def _replace_text(node: Any, old: str, new: str) -> Any:
    if isinstance(node, str):
        return node.replace(old, new)
    if isinstance(node, list):
        return [_replace_text(item, old, new) for item in node]
    if isinstance(node, dict):
        return {key: _replace_text(value, old, new) for key, value in node.items()}
    return node


def summarise_away(artifact: Mapping[str, Any], dissent_id: str, gloss: str = GENERIC_GLOSS) -> dict[str, Any]:
    """Summarised-away mutant: keep the id slot, replace the distinctive claim everywhere."""
    entry = _find_entry(artifact, dissent_id)
    mutant = deepcopy(dict(artifact))
    claim = str(entry.get("claim") or "")
    if claim:
        mutant = _replace_text(mutant, claim, gloss)
    rationale = str(entry.get("rationale") or "")
    if rationale and rationale != claim:
        mutant = _replace_text(mutant, rationale, gloss)
    for row in mutant["minority_report"].get("dissents", []):
        if str(row.get("id")) == dissent_id:
            row["claim"] = gloss
    if isinstance(mutant.get("dissent_index"), dict) and dissent_id in mutant["dissent_index"]:
        mutant["dissent_index"][dissent_id] = gloss
    return mutant


# --------------------------------------------------------------------------- pipeline
class DissentPipeline:
    """capture -> attribute -> synthesis [-> parent_aggregation], with a ledger per stage."""

    def run(
        self,
        council: Any,
        majority: Any = None,
        council_id: str = "council",
        children: Sequence[Any] | None = None,
        strict: bool = False,
    ) -> PipelineResult:
        """Run every stage and record conservation and presence after each one.

        ``children`` are sibling/child artifacts (or results) to aggregate under a parent
        view; passing ``children=[]`` still produces a parent over this council alone.
        With ``strict=True`` a non-conserved stage raises :class:`ConservationError` instead
        of merely being recorded.
        """
        turns = _normalise_turns(council)
        ledger: list[LedgerRow] = []
        presence: list[PresenceRow] = []

        detected_ids, captured = capture(turns, majority, council_id)
        ledger.append(conservation(detected_ids, captured, STAGE_CAPTURE))
        presence.append(
            presence_check(captured, {"captured": [d.to_dict() for d in captured]}, STAGE_CAPTURE)
        )

        attributed = attribute(captured)
        ledger.append(conservation(captured, attributed, STAGE_ATTRIBUTE))
        presence.append(
            presence_check(attributed, {"attributed": [d.to_dict() for d in attributed]}, STAGE_ATTRIBUTE)
        )

        artifact = synthesise(attributed, majority, council_id, turns)
        ledger.append(conservation(attributed, dissents_from_artifact(artifact), STAGE_SYNTHESIS))
        presence.append(presence_check(attributed, artifact, STAGE_SYNTHESIS))

        parent: dict[str, Any] | None = None
        if children is not None:
            child_artifacts = [c.artifact if isinstance(c, PipelineResult) else c for c in children]
            expected = list(attributed)
            for child in child_artifacts:
                expected.extend(dissents_from_artifact(child))
            parent = aggregate_parent(artifact, child_artifacts, council_id)
            ledger.append(conservation(expected, dissents_from_artifact(parent), STAGE_PARENT))
            presence.append(presence_check(expected, parent, STAGE_PARENT))

        result = PipelineResult(
            captured=captured,
            attributed=attributed,
            ledger=ledger,
            presence=presence,
            artifact=artifact,
            parent=parent,
            council_id=council_id,
        )
        if strict and not result.conserved:
            broken = [r.to_dict() for r in ledger if not r.conserved] + [p.to_dict() for p in presence if not p.ok]
            raise ConservationError(f"dissent lost in {council_id}: {json.dumps(broken, sort_keys=True)}")
        return result


__all__ = [
    "AttributionError",
    "ConservationError",
    "DISSENT_KINDS",
    "Dissent",
    "DissentPipeline",
    "GENERIC_GLOSS",
    "LedgerRow",
    "PipelineResult",
    "PresenceFailure",
    "PresenceRow",
    "SPEC_ANCHORS",
    "STAGE_ATTRIBUTE",
    "STAGE_CAPTURE",
    "STAGE_PARENT",
    "STAGE_SYNTHESIS",
    "aggregate_parent",
    "attribute",
    "capture",
    "conservation",
    "dissents_from_artifact",
    "drop_dissent",
    "from_kernel_events",
    "is_dissent_turn",
    "presence_check",
    "summarise_away",
    "synthesise",
]
