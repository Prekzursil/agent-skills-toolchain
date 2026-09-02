"""Live fixtures for IMP-0344 named probes.

These start from the tests: they import the bridge module and compose a
workflow. They do not read the author's receipt narrative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.bridge import (  # noqa: E402
    Event,
    EventLog,
    CouncilDecision,
    CouncilFailed,
    CouncilStageInput,
    StageSpec,
    WorkflowRunner,
    complete_policy,
    detect_swallowed_council_failure,
    invoke_constructs_control_plane,
)

HERE = Path(__file__).resolve().parent
BRIDGE_SRC = REPO / "tools" / "council" / "bridge.py"


class HonestFailingInvoker:
    def run(self, payload: CouncilStageInput, plane: Any) -> CouncilDecision:
        plane.event_log.append(
            "council.turn.failed",
            stage_id=payload.stage_id,
            family="model-error",
            message="vendor 500",
        )
        raise CouncilFailed("model-error", "vendor 500")


class SwallowingInvoker:
    """Returns a success decision after writing a council failure event."""

    def run(self, payload: CouncilStageInput, plane: Any) -> CouncilDecision:
        plane.event_log.append(
            "council.turn.failed",
            stage_id=payload.stage_id,
            family="model-error",
            message="internal exception swallowed",
        )
        return CouncilDecision(
            outcome="decided",
            verdict="approve",
            dissenting=(),
            plane_id=plane.id,
            source_stage=payload.stage_id,
        )


class RivalLogInvoker:
    """Constructs a second EventLog — the duplicate-control-plane plant."""

    def run(self, payload: CouncilStageInput, plane: Any) -> CouncilDecision:
        rival = EventLog(plane_id="rival-plane")
        rival.append("council.turn.completed", seat="ghost", vote="approve")
        return CouncilDecision(
            outcome="decided",
            verdict="approve",
            dissenting=(),
            plane_id=plane.id,
            source_stage=payload.stage_id,
        )


def _council_input(ctx: dict[str, Any]) -> CouncilStageInput:
    brief = str(ctx.get("brief") or "")
    return CouncilStageInput(
        question=brief,
        evidence=(brief,),
        roster=("alice", "bob", "cara"),
        protocol="blind_first",
    )


def _prepare(ctx: dict[str, Any]) -> str:
    return str(ctx.get("question") or "approve the change")


def _act(ctx: dict[str, Any]) -> str:
    decision = ctx.get("decision")
    if not isinstance(decision, CouncilDecision):
        raise TypeError(f"downstream expected CouncilDecision, got {type(decision)!r}")
    if decision.outcome == "failed":
        ctx["acted_on"] = f"classified:{decision.verdict}"
        return ctx["acted_on"]
    ctx["acted_on"] = decision.verdict
    return decision.verdict


def integration_workflow(invoker=None) -> WorkflowRunner:
    policy = complete_policy()
    return WorkflowRunner(
        [
            StageSpec(
                id="prepare",
                kind="compute",
                output_key="brief",
                on_failure=policy,
                compute=_prepare,
            ),
            StageSpec(
                id="deliberate",
                kind="council",
                output_key="decision",
                on_failure=policy,
                council_input=_council_input,
            ),
            StageSpec(
                id="act",
                kind="compute",
                output_key="acted_on",
                on_failure=policy,
                compute=_act,
            ),
        ],
        invoker=invoker,
    )


def run_integration() -> dict[str, Any]:
    result = integration_workflow().run({"question": "approve the change"})
    decision = result.context.get("decision")
    consumed = result.context.get("acted_on")
    ok = (
        result.status == "SUCCESS"
        and result.census.single_control_plane is True
        and isinstance(decision, CouncilDecision)
        and decision.outcome == "decided"
        and decision.verdict == "approve"
        and consumed == "approve"
        and decision.classified_failure is None
        and result.duplicate_control_plane is False
    )
    return {
        "ok": ok,
        "status": result.status,
        "census": result.census.to_dict(),
        "acted_on": consumed,
        "decision": decision.to_dict() if isinstance(decision, CouncilDecision) else None,
        "event_kinds": [e.kind for e in result.plane.event_log.events],
        "classifications": [c.to_dict() for c in result.classifications],
    }


def run_planted_second_plane() -> dict[str, Any]:
    result = integration_workflow(invoker=RivalLogInvoker()).run(
        {"question": "approve the change"}
    )
    detected = (
        result.duplicate_control_plane is True
        and result.census.event_log_count == 2
        and result.census.single_control_plane is False
        and any(c.family == "duplicate-control-plane" for c in result.classifications)
        and result.status == "FAILED"
    )
    return {
        "ok": detected,
        "status": result.status,
        "census": result.census.to_dict(),
        "classifications": [c.to_dict() for c in result.classifications],
        "duplicate_control_plane": result.duplicate_control_plane,
    }


def run_honest_failure() -> dict[str, Any]:
    policy = complete_policy({"model-error": "abort"})
    runner = WorkflowRunner(
        [
            StageSpec(
                id="deliberate",
                kind="council",
                output_key="decision",
                on_failure=policy,
                council_input=_council_input,
            ),
            StageSpec(
                id="act",
                kind="compute",
                output_key="acted_on",
                on_failure=policy,
                compute=_act,
            ),
        ],
        invoker=HonestFailingInvoker(),
    )
    result = runner.run({"brief": "approve the change"})
    decision = result.context.get("decision")
    classified = (
        isinstance(decision, CouncilDecision)
        and decision.classified_failure is not None
        and decision.classified_failure.family == "model-error"
        and decision.classified_failure.action == "abort"
        and decision.classified_failure.source == "workflow.failure_policy"
    )
    swallowed = detect_swallowed_council_failure(result.plane.event_log.events)
    ok = (
        classified
        and result.status == "FAILED"
        and len(swallowed) == 0
        and "act" not in [e.payload.get("stage_id") for e in result.plane.event_log.events if e.kind == "workflow.stage.completed"]
    )
    return {
        "ok": ok,
        "status": result.status,
        "classified": None if not classified else decision.classified_failure.to_dict(),
        "swallowed_count": len(swallowed),
        "downstream_ran": result.context.get("acted_on") is not None,
        "census": result.census.to_dict(),
    }


def run_swallowed_through_bridge() -> dict[str, Any]:
    result = integration_workflow(invoker=SwallowingInvoker()).run(
        {"question": "approve the change"}
    )
    decision = result.context.get("decision")
    classified = (
        isinstance(decision, CouncilDecision)
        and decision.classified_failure is not None
        and decision.classified_failure.family == "swallowed-failure"
        and decision.classified_failure.source == "workflow.failure_policy"
    )
    silent_pass = result.status == "SUCCESS" and (
        not isinstance(decision, CouncilDecision) or decision.outcome == "decided"
    )
    ok = classified and result.status == "FAILED" and not silent_pass
    return {
        "ok": ok,
        "status": result.status,
        "silent_pass": silent_pass,
        "classified": None
        if not isinstance(decision, CouncilDecision) or decision.classified_failure is None
        else decision.classified_failure.to_dict(),
        "acted_on": result.context.get("acted_on"),
    }


def planted_swallowed_log() -> tuple[Event, ...]:
    """Hand-built bad log: council failed, workflow never classified."""
    log = EventLog(plane_id="fixture-plane", log_id="fixture-log")
    log.bind_scheduler("fixture-sched")
    log.append("council.stage.entered", stage_id="deliberate")
    log.append(
        "council.turn.failed",
        stage_id="deliberate",
        family="model-error",
        message="swallowed",
    )
    log.append("council.stage.exited", stage_id="deliberate", verdict="approve")
    return log.events


def classified_failure_log() -> tuple[Event, ...]:
    log = EventLog(plane_id="fixture-plane", log_id="fixture-log-ok")
    log.bind_scheduler("fixture-sched")
    failed = log.append(
        "council.turn.failed",
        stage_id="deliberate",
        family="model-error",
        message="vendor 500",
    )
    log.append(
        "workflow.failure.classified",
        family="model-error",
        action="abort",
        stage_id="deliberate",
        source="workflow.failure_policy",
        ref_seq=failed.seq,
        message="vendor 500",
    )
    return log.events


def run_detector_both_states() -> dict[str, Any]:
    bad = detect_swallowed_council_failure(planted_swallowed_log())
    good = detect_swallowed_council_failure(classified_failure_log())
    fired_on_bad = len(bad) == 1 and bad[0].kind == "council.turn.failed"
    silent_on_good = len(good) == 0
    return {
        "ok": fired_on_bad and silent_on_good,
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "bad_count": len(bad),
        "good_count": len(good),
        "bad_kind": None if not bad else bad[0].kind,
    }


def run_ast_invariant() -> dict[str, Any]:
    hits = invoke_constructs_control_plane(BRIDGE_SRC.read_text(encoding="utf-8"))
    return {"ok": hits == [], "hits": hits}


def run_out_of_taxonomy_policy() -> dict[str, Any]:
    from tools.council.bridge import PolicyValidationError, validate_failure_policy

    try:
        validate_failure_policy({**complete_policy(), "not-a-family": "abort"})
        failed_closed = False
        error = ""
    except PolicyValidationError as exc:
        failed_closed = "not-a-family" in str(exc)
        error = str(exc)
    return {"ok": failed_closed, "error": error}


def run_all_required() -> dict[str, Any]:
    integration = run_integration()
    planted = run_planted_second_plane()
    honest = run_honest_failure()
    swallow_bridge = run_swallowed_through_bridge()
    detector = run_detector_both_states()
    ast_inv = run_ast_invariant()
    taxonomy = run_out_of_taxonomy_policy()
    ok = all(
        block["ok"]
        for block in (
            integration,
            planted,
            honest,
            swallow_bridge,
            detector,
            ast_inv,
            taxonomy,
        )
    )
    return {
        "ok": ok,
        "integration": integration,
        "planted_second_plane": planted,
        "honest_failure": honest,
        "swallowed_through_bridge": swallow_bridge,
        "detector_both_states": detector,
        "ast_invariant": ast_inv,
        "out_of_taxonomy": taxonomy,
    }


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, default=str)
