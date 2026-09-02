"""One end-to-end journey through every Phase 9 surface, in the order a real wave hits them.

The per-module tests prove each mechanism in isolation. This one proves they COMPOSE: a Claude
session claims a unit, leases a file, writes partial work and dies; a second session discovers the
corpse, recovers it without destroying anything, and a Codex session takes the handoff, is refused
the capability it does not have, degrades loudly on the one it cannot enforce, finishes, and has its
receipt judged by the SHARED reducer.

Composition is where coordination layers usually break, because each unit passes its own test with a
store nobody else touched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from coordination.adapters import load_adapter_registry
from coordination.capability import NegotiationVerdict
from coordination.claims import (
    ClaimOutcome,
    ClaimState,
    acquire_claim,
    complete_claim,
    record_artifacts,
)
from coordination.dispatch import (
    DispatchPlan,
    DispatchVerdict,
    audit_plan,
    verify_dispatch,
)
from coordination.errors import CapabilityUnavailable, HandoffRefused
from coordination.handoff import accept_handoff, offer_handoff, open_offers
from coordination.leases import LeaseOutcome, acquire_lease, detect_conflicts
from coordination.recovery import execute_recovery, plan_recovery
from coordination.reducer import (
    PredicateOptions,
    Verdict,
    assert_single_reducer,
    reduce_claim,
)
from coordination.session import (
    DEFAULT_HEARTBEAT_TTL,
    Liveness,
    close_session,
    discover,
    heartbeat,
    register_session,
)
from coordination.simclock import SimClock
from coordination.store import Store

UNIT: dict[str, Any] = {
    "id": "COORD-0900",
    "phase": "9",
    "question_or_target": "does the coordination layer survive a mid-unit crash?",
    "inputs": ["platform/coordination/"],
    "dependencies": [],
    "assigned_model_vendor_role": {
        "vendor": "anthropic",
        "model": "opus",
        "role": "builder",
    },
    "output_path": "coordination-result.json",
    "output_schema": "result.schema.json",
    "evidence_requirement": "two mechanically independent probes",
    "tests_required": ["test_integration.py"],
    "reviewer_requirement": "cross-vendor independent reviewer",
    "completion_sentinel": "SUCCESS:COORD-0900",
}

#: What the unit needs. ``interactive.owner_approval`` is deliberately absent from the main list and
#: used separately, so the refusal path is exercised without poisoning the happy path.
REQUIRED = (
    "fs.read",
    "fs.write",
    "proc.exec",
    "artifact.output_file",
    "sandbox.enforced",
)


def test_full_cross_vendor_lifecycle(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    registry = load_adapter_registry()
    claude = registry.get("claude-code")
    codex = registry.get("codex-cli")
    gemini = registry.get("gemini-cli")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # ---- 0. the control plane is single before anything else happens ----------------------
    assert assert_single_reducer().ok is True

    # ---- 1. capability negotiation, before any work is claimed ---------------------------
    claude_deal = claude.negotiate(REQUIRED)
    assert claude_deal.verdict is NegotiationVerdict.DEGRADED, (
        "no enforced sandbox on Windows"
    )
    assert [f.capability for f in claude_deal.degraded] == ["sandbox.enforced"]
    assert claude_deal.may_proceed is True
    assert gemini.negotiate(REQUIRED).verdict is NegotiationVerdict.REFUSED

    # An unmeasured adapter is REFUSED rather than trusted, and asking it anyway raises loudly.
    with pytest.raises(CapabilityUnavailable, match="never measured"):
        gemini.require("fs.write", unit_id=UNIT["id"])

    # ---- 2. session discovery --------------------------------------------------------------
    _record_a, lock_a = register_session(
        store,
        vendor="anthropic",
        adapter_id=claude.adapter_id,
        tool="claude-code",
        session_id="claude-A",
        capabilities=claude.profile.offers,
        cwd=workspace,
    )
    assert lock_a is not None and lock_a.acquired
    _record_b, lock_b = register_session(
        store,
        vendor="anthropic",
        adapter_id=claude.adapter_id,
        tool="claude-code",
        session_id="claude-B",
    )
    assert lock_b is not None and lock_b.acquired
    assert {v.session_id for v in discover(store, vendor="claude")} == {
        "claude-A",
        "claude-B",
    }
    assert discover(store, vendor="openai") == ()

    # ---- 3. work claim + duplicate suppression --------------------------------------------
    first = acquire_claim(
        store,
        unit_id=UNIT["id"],
        unit=UNIT,
        session_id="claude-A",
        adapter_id=claude.adapter_id,
        vendor="anthropic",
    )
    assert first.outcome is ClaimOutcome.GRANTED
    duplicate = acquire_claim(
        store, unit_id=UNIT["id"], unit=UNIT, session_id="claude-B"
    )
    assert duplicate.outcome is ClaimOutcome.DUPLICATE_SUPPRESSED
    same_work_new_id = acquire_claim(
        store,
        unit_id="COORD-0900-COPY",
        unit={**UNIT, "id": "COORD-0900-COPY"},
        session_id="claude-B",
    )
    assert same_work_new_id.outcome is ClaimOutcome.DUPLICATE_SUPPRESSED

    # ---- 4. file lease + conflict detection ------------------------------------------------
    lease = acquire_lease(
        store,
        session_id="claude-A",
        paths=["src"],
        root=workspace,
        purpose="edit the module",
    )
    assert lease.outcome is LeaseOutcome.GRANTED
    blocked = acquire_lease(
        store, session_id="claude-B", paths=["src/mod.py"], root=workspace
    )
    assert blocked.outcome is LeaseOutcome.CONFLICT, (
        "a directory lease covers its files"
    )
    sibling = acquire_lease(
        store, session_id="claude-B", paths=["src-generated/mod.py"], root=workspace
    )
    assert sibling.outcome is LeaseOutcome.GRANTED, "src-generated is NOT inside src"
    assert detect_conflicts(store) == ()

    # ---- 5. the dispatch plan is audited BEFORE anything is dispatched ---------------------
    runner = workspace / "run-codex.sh"
    runner.write_text(
        'codex exec --ignore-user-config - < "$1"\nrc=$?\nexit "$rc"\n',
        encoding="utf-8",
    )
    plan = DispatchPlan(
        unit_id=UNIT["id"],
        adapter_id="codex-cli",
        argv=("codex", "exec", "--ignore-user-config", "-o", "last-message.json"),
        timeout_ms=1_800_000,
        background=True,
        barrier="monitor-until-terminal-marker",
        result_channel="output-file",
        output_path=str(workspace / "last-message.json"),
        prompt_delivery="runner-script",
        runner_script_text=runner.read_text(encoding="utf-8"),
        schema_path=str(workspace / "result.schema.json"),
        expected_duration_s=900.0,
    )
    assert audit_plan(plan).ok is True, audit_plan(plan).to_dict()

    # ---- 6. partial work, then the session crashes -----------------------------------------
    partial = workspace / "partial.json"
    partial.write_text(
        json.dumps({"rows": [1, 2, 3], "state": "half"}), encoding="utf-8"
    )
    record_artifacts(store, UNIT["id"], [partial])
    heartbeat(store, "claude-A")
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()

    lock_a.release()  # the OS releases the liveness lock when a process dies
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    heartbeat(store, "claude-B")  # claude-B is alive and keeps beating
    views = {v.session_id: v.liveness for v in discover(store)}
    assert views["claude-A"] is Liveness.DEAD, "both signals agree"
    assert views["claude-B"] is Liveness.LIVE, "a live sibling must not be swept up"

    # ---- 7. crash recovery: plan, then execute, destroying nothing --------------------------
    recovery_plan = plan_recovery(
        store, required_capabilities=["fs.read", "fs.write", "artifact.output_file"]
    )
    assert recovery_plan.dead == ("claude-A",)
    assert recovery_plan.forced_actions == ()
    outcome = execute_recovery(store, recovery_plan)
    assert outcome.abandoned_claims == (UNIT["id"],)
    assert outcome.artifacts_missing == ()
    assert partial.exists()
    assert hashlib.sha256(partial.read_bytes()).hexdigest() == digest

    # ---- 8. the lease freed, so the blocked session can now proceed ------------------------
    assert acquire_lease(
        store, session_id="claude-B", paths=["src/mod.py"], root=workspace
    ).granted

    # ---- 9. handoff: refused for a capability the receiver lacks --------------------------
    offer = open_offers(store, unit_id=UNIT["id"])[0]
    assert partial.as_posix() in [Path(a).as_posix() for a in offer.artifacts]
    strict = offer_handoff(
        store,
        unit_id=UNIT["id"],
        reason="needs an owner decision",
        required_capabilities=["interactive.owner_approval"],
    )
    register_session(
        store,
        vendor="codex",
        adapter_id=codex.adapter_id,
        tool="codex-cli",
        session_id="codex-C",
        hold_lock=False,
    )
    with pytest.raises(HandoffRefused) as refusal:
        accept_handoff(
            store,
            offer_id=strict.offer_id,
            session_id="codex-C",
            adapter=codex,
            unit=UNIT,
        )
    assert refusal.value.missing == ("interactive.owner_approval",)

    # ---- 10. handoff: accepted, cross-vendor, DEGRADED and said so ------------------------
    result = accept_handoff(
        store, offer_id=offer.offer_id, session_id="codex-C", adapter=codex, unit=UNIT
    )
    assert result.claim.session_id == "codex-C"
    assert result.vendor_comparison == "CROSS-VENDOR"
    assert result.negotiation.verdict is NegotiationVerdict.AGREED
    assert result.missing_artifacts == ()
    degraded = codex.negotiate(REQUIRED)
    assert degraded.verdict is NegotiationVerdict.DEGRADED
    assert [f.capability for f in degraded.degraded] == ["sandbox.enforced"]

    # ---- 11. the dispatch AND-gate on the real produced artifact --------------------------
    schema = workspace / "result.schema.json"
    schema.write_text(
        json.dumps({"type": "object", "required": ["unit_id", "verdict"]}),
        encoding="utf-8",
    )
    produced = workspace / "last-message.json"
    produced.write_text(
        json.dumps({"unit_id": UNIT["id"], "verdict": "CONFIRMED", "rows": [1, 2, 3]}),
        encoding="utf-8",
    )
    check = verify_dispatch(
        unit_id=UNIT["id"], exit_code=0, output_path=produced, schema_path=schema
    )
    assert check.verdict is DispatchVerdict.SUCCESS and check.ok is True

    # exit 0 with the artifact removed is SEVERED, not success - the whole point of the gate
    produced.unlink()
    assert (
        verify_dispatch(
            unit_id=UNIT["id"], exit_code=0, output_path=produced, schema_path=schema
        ).verdict
        is DispatchVerdict.SEVERED
    )
    produced.write_text(
        json.dumps({"unit_id": UNIT["id"], "verdict": "CONFIRMED"}), encoding="utf-8"
    )

    # ---- 12. the SHARED reducer has the last word ------------------------------------------
    receipt = workspace / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "unit_id": UNIT["id"],
                "state": "SUCCESS",
                "sentinel": f"SUCCESS:{UNIT['id']} coordination lifecycle complete",
                "artifacts": [
                    {"path": str(produced), "role": "primary", "exists": True}
                ],
                "evidence": [],
            }
        ),
        encoding="utf-8",
    )
    complete_claim(store, UNIT["id"], receipt_path=receipt, artifacts=[produced])
    verdict = reduce_claim(store, UNIT["id"], PredicateOptions(repo_root=workspace))
    assert verdict.reducer_id == "platform/lib/completion_predicate.py@v1"
    assert verdict.verdict is not Verdict.COMPLETE, (
        "a hand-built receipt with no tests, controls or reviewer must NOT reach COMPLETE - "
        "the reducer is not a rubber stamp for the coordination layer"
    )
    assert verdict.not_checked, "unmeasured conditions stay NOT-CHECKED"

    # ---- 13. the unit is now closed to re-claiming, and the session closes gracefully -----
    assert (
        acquire_claim(
            store, unit_id=UNIT["id"], unit=UNIT, session_id="claude-B"
        ).outcome
        is ClaimOutcome.ALREADY_COMPLETE
    )
    closed = close_session(store, "codex-C")
    assert closed.closed_at is not None
    final_plan = plan_recovery(store)
    assert [a.kind.value for a in final_plan.actions] == ["NOOP-COMPLETED"], (
        "a clean close holding a COMPLETED claim leaves nothing to recover - only the audit row. "
        "Anything else here would mean recovery re-opens finished work."
    )
    assert final_plan.forced_actions == ()
    lock_b.release()

    # ---- 14. the journal is a complete, ordered audit trail --------------------------------
    events = [e["event"] for e in store.journal_entries()]
    for expected in (
        "session.register",
        "claim.granted",
        "claim.denied",
        "lease.granted",
        "lease.conflict",
        "recovery.executed",
        "handoff.offered",
        "handoff.refused",
        "handoff.accepted",
        "claim.transition",
        "session.close",
    ):
        assert expected in events, expected
    ats = [e["at"] for e in store.journal_entries()]
    assert ats == sorted(ats), "the journal must be append-only and monotonic"
    assert (
        store.read(store.path_for("claims", UNIT["id"]))["state"]
        == ClaimState.COMPLETED.value
    )
