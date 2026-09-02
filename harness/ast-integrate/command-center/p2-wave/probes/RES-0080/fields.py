"""Live inventory of council transcript fields this unit may name.

A detector is implementable only when every field it reads is present on at
least one of: kernel Event.as_dict (runtime log), unanimity Vote/Brief/
CouncilSnapshot (IMP-0318 snapshot), chair journal records, or
council-audit.schema.json participant_action_logs.

Classical Asch conformity needs private_judgment + trial_type + ground_truth.
Those names are queried here so the control can prove they are absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

_NOT_PORTABLE_CLASSICAL = (
    "private_judgment",
    "private_vote",
    "trial_type",
    "critical_trial",
    "ground_truth",
    "morale",
    "illusion_of_invulnerability",
)


def _tools_on_path() -> None:
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)


def _kernel_event_fields() -> dict[str, str]:
    _tools_on_path()
    from council.kernel import Event

    sample = Event(
        seq=1,
        kind="TURN",
        round_index=0,
        turn_index=1,
        participant_id="p",
        status="ok",
        output="x",
        obligations=("position",),
        obligations_met=("position",),
        obligations_missing=(),
        elapsed_ms=1,
    )
    src = "tools/council/kernel.py:Event.as_dict"
    return {f"events.{k}": src for k in sample.as_dict()}


def _unanimity_fields() -> dict[str, str]:
    _tools_on_path()
    from council.antifail.unanimity import Brief, Participant, Vote

    src_vote = "tools/council/antifail/unanimity.py:Vote.to_dict"
    src_brief = "tools/council/antifail/unanimity.py:Brief.to_dict"
    src_part = "tools/council/antifail/unanimity.py:Participant.to_dict"
    src_snap = "tools/council/antifail/unanimity.py:CouncilSnapshot"
    out: dict[str, str] = {}
    for k in Vote("p", "c", 1, 0.5).to_dict():
        out[f"votes.{k}"] = src_vote
    for k in Brief("p", "t", (), False).to_dict():
        out[f"briefs.{k}"] = src_brief
    for k in Participant("p", "seat").to_dict():
        out[f"participants.{k}"] = src_part
    for k in (
        "council_id",
        "question",
        "claims",
        "rounds_elapsed",
        "disagreement_rounds",
        "family",
    ):
        out[k] = src_snap
    return out


def _chair_journal_fields() -> dict[str, str]:
    """Inventory live chair journal records (IMP-0282 ChairLedSession).

    FloorRequest / DeniedAct / as_dict() were retired; the live types are
    Submission, Recognition, CaptureVerdict, and ChairLedSession.artifact().
    """
    from dataclasses import asdict

    _tools_on_path()
    from council.topology.chair import (
        CaptureVerdict,
        Recognition,
        Submission,
    )

    mapping = (
        (
            "submissions",
            asdict(Submission("s1", "p", 0, "text")),
            "tools/council/topology/chair.py:Submission",
        ),
        (
            "recognitions",
            asdict(Recognition(0, "chair", "p")),
            "tools/council/topology/chair.py:Recognition",
        ),
        (
            "capture_verdict",
            CaptureVerdict(
                flagged=False,
                starved=(),
                actual_counts={},
                fair_counts={},
                chi_square=0.0,
                max_abs_diff=0,
                n_slots=0,
                reason="even-handed",
            ).as_dict(),
            "tools/council/topology/chair.py:CaptureVerdict.as_dict",
        ),
    )
    out: dict[str, str] = {}
    for prefix, blob, src in mapping:
        for k in blob:
            out[f"{prefix}.{k}"] = src
    artifact_src = "tools/council/topology/chair.py:ChairLedSession.artifact"
    for k in (
        "kind",
        "roster",
        "chair",
        "chair_history",
        "agenda",
        "submissions",
        "recognition_distribution",
        "events_recorded",
        "local_operations",
    ):
        out[f"chair_artifact.{k}"] = artifact_src
    return out


def _audit_schema_fields() -> dict[str, str]:
    path = REPO / "command-center" / "schema" / "council-audit.schema.json"
    src = "command-center/schema/council-audit.schema.json"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    doc = json.loads(path.read_text(encoding="utf-8"))
    logs = (
        doc.get("properties", {})
        .get("configurations", {})
        .get("items", {})
        .get("properties", {})
        .get("participant_action_logs", {})
        .get("items", {})
    )
    for k in logs.get("properties") or {}:
        out[f"participant_action_logs.{k}"] = src
    ev_props = (
        (logs.get("properties") or {})
        .get("events", {})
        .get("items", {})
        .get("properties")
        or {}
    )
    for k in ev_props:
        out[f"participant_action_logs.events.{k}"] = src
    return out


def inventory() -> dict[str, Any]:
    fields: dict[str, str] = {}
    fields.update(_kernel_event_fields())
    fields.update(_unanimity_fields())
    fields.update(_chair_journal_fields())
    fields.update(_audit_schema_fields())
    absent = [n for n in _NOT_PORTABLE_CLASSICAL if n not in fields]
    dotted_absent = [
        n for n in _NOT_PORTABLE_CLASSICAL if f"votes.{n}" not in fields and n not in fields
    ]
    return {
        "fields": dict(sorted(fields.items())),
        "names": sorted(fields),
        "count": len(fields),
        "classical_names_absent": sorted(set(absent) | set(dotted_absent)),
        "sources": sorted(set(fields.values())),
    }


def field_exists(name: str, inv: dict[str, Any] | None = None) -> bool:
    data = inv if inv is not None else inventory()
    names = set(data["names"])
    return name in names


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
