#!/usr/bin/env python3
"""Live both-states + negative-control scenarios for TST-0228."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import gate as G


def _trace(gate: G.BaseGate) -> dict[str, Any]:
    revokes = [e.as_dict() for e in gate.events if e.kind == "revoke"]
    denies = [e.as_dict() for e in gate.events if e.kind == "deny"]
    allows = [e.as_dict() for e in gate.events if e.kind == "allow"]
    return {
        "gate": gate.name,
        "run_id": gate.run_id,
        "restart_count": gate.restart_count,
        "start_grants": list(gate.start_grants),
        "live_grants": sorted(gate.live_grants),
        "events": gate.event_log(),
        "calls": [c.as_dict() for c in gate.calls],
        "revokes": revokes,
        "denies": denies,
        "allows": allows,
        "marker_bytes": None
        if gate.marker_bytes() is None
        else gate.marker_bytes().decode("utf-8"),
        "marker_sha256": None
        if gate.marker_bytes() is None
        else G.sha256_hex(gate.marker_bytes() or b""),
        "dest": str(gate.dest),
    }


def run_revocation_script(
    gate_cls: type[G.BaseGate],
    dest: Path,
    *,
    revoke: bool,
    intervening_read: bool = False,
    raise_on_deny: bool = False,
    sleep_s: float = 0.002,
) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    gate = gate_cls(
        granted=("Read", "Grep", "Bash", "Write"),
        dest=dest,
        raise_on_deny=raise_on_deny,
    )
    before = gate.invoke("Write")
    mid_read = None
    revoke_event = None
    after = None
    observed_exc: dict[str, Any] | None = None
    if revoke:
        if sleep_s:
            time.sleep(sleep_s)
        revoke_event = gate.revoke("Write").as_dict()
        if sleep_s:
            time.sleep(sleep_s)
        if intervening_read:
            mid_read = gate.invoke("Read")
        try:
            after = gate.invoke("Write")
        except G.CapabilityRevoked as exc:
            after = exc.result
            observed_exc = {
                "type": type(exc).__name__,
                "code": exc.code,
                "message": str(exc),
                "result": exc.result.as_dict(),
            }
    else:
        if intervening_read:
            mid_read = gate.invoke("Read")
        after = gate.invoke("Write")
    post_read = gate.invoke("Read")
    row = _trace(gate)
    row.update(
        {
            "before": before.as_dict(),
            "revoke_event": revoke_event,
            "intervening_read": None if mid_read is None else mid_read.as_dict(),
            "after": None if after is None else after.as_dict(),
            "post_read": post_read.as_dict(),
            "observed_exception": observed_exc,
            "script": {
                "revoke": revoke,
                "intervening_read": intervening_read,
                "raise_on_deny": raise_on_deny,
            },
        }
    )
    return row


def predicate(row: dict[str, Any]) -> dict[str, Any]:
    """TST-0228 pass predicate against one revocation-script trace."""
    fails: list[str] = []
    before = row.get("before") or {}
    after = row.get("after") or {}
    revoke_event = row.get("revoke_event")
    post_read = row.get("post_read") or {}

    if not before.get("ok") or before.get("code") != G.CODE_OK:
        fails.append(f"pre-revoke Write did not succeed: {before.get('code')}")
    if not before.get("wrote"):
        fails.append("pre-revoke Write produced no side effect")
    if revoke_event is None:
        fails.append("no revocation event")
        return {"pass": False, "fails": fails, "within_one_call": False}

    if after.get("ok"):
        fails.append("post-revoke Write succeeded")
    if after.get("code") != G.CODE_REVOKED:
        fails.append(f"post-revoke code={after.get('code')} want {G.CODE_REVOKED}")
    if after.get("wrote"):
        fails.append("post-revoke Write still produced a side effect")

    t_rev = int(revoke_event.get("t_ns") or 0)
    t_den = int(after.get("t_ns") or 0)
    if not (t_den > t_rev > 0):
        fails.append(f"timestamp order revoke={t_rev} deny={t_den}")

    seq_before = int(before.get("seq") or 0)
    seq_after = int(after.get("seq") or 0)
    intervening = row.get("intervening_read")
    expected_seq = seq_before + (2 if intervening else 1)
    if seq_after != expected_seq:
        fails.append(
            f"post-revoke Write seq={seq_after} expected {expected_seq} "
            f"(before={seq_before} intervening={bool(intervening)})"
        )

    successes_after_revoke = [
        c
        for c in row.get("calls") or []
        if c.get("tool") == "Write"
        and c.get("ok")
        and int(c.get("seq") or 0) > seq_before
        and int(c.get("t_ns") or 0) > t_rev
    ]
    if successes_after_revoke:
        fails.append(
            f"Write succeeded {len(successes_after_revoke)} time(s) after revoke"
        )

    within_one_call = (
        not after.get("ok")
        and after.get("code") == G.CODE_REVOKED
        and not successes_after_revoke
        and seq_after == expected_seq
        and t_den > t_rev
    )
    if not within_one_call:
        fails.append("denial was not within one call of revocation")

    if not post_read.get("ok"):
        fails.append("Read after Write-revoke was denied (over-revoke)")

    err = after.get("observed_error") or {}
    if err.get("code") != G.CODE_REVOKED:
        fails.append("unit observed_error missing CAPABILITY_REVOKED")
    if revoke_event.get("event_id") and err.get("revocation_event_id") != revoke_event.get(
        "event_id"
    ):
        fails.append("observed_error does not name the revocation event id")

    if int(row.get("restart_count") or 0) != 0:
        fails.append("unit restarted between revoke and deny")

    return {
        "pass": not fails,
        "fails": fails,
        "within_one_call": within_one_call,
        "t_revoke_ns": t_rev,
        "t_deny_ns": t_den,
        "seq_before": seq_before,
        "seq_after": seq_after,
        "delta_ns": t_den - t_rev,
        "revocation_event_id": revoke_event.get("event_id"),
        "deny_event_id": after.get("event_id"),
    }


def both_states_ok(control: dict[str, Any], revoked: dict[str, Any]) -> bool:
    after_ok = (control.get("after") or {}).get("ok") is True
    after_wrote = (control.get("after") or {}).get("wrote") is True
    pred = predicate(revoked)
    return after_ok and after_wrote and pred["pass"]


def evaluate() -> dict[str, Any]:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tst0228-") as td:
        root = Path(td)
        live = run_revocation_script(G.PerCallGate, root / "live-revoke", revoke=True)
        control = run_revocation_script(
            G.PerCallGate, root / "live-control", revoke=False
        )
        mixed = run_revocation_script(
            G.PerCallGate,
            root / "live-mixed",
            revoke=True,
            intervening_read=True,
        )
        raised = run_revocation_script(
            G.PerCallGate,
            root / "live-raise",
            revoke=True,
            raise_on_deny=True,
        )
        start_only = run_revocation_script(
            G.StartTimeOnlyGate, root / "neg-start-only", revoke=True
        )
        one_more = run_revocation_script(
            G.OneMoreCallGate, root / "neg-one-more", revoke=True
        )

    live_pred = predicate(live)
    mixed_pred = predicate(mixed)
    raised_pred = predicate(raised)
    start_pred = predicate(start_only)
    one_more_pred = predicate(one_more)

    control_after = control.get("after") or {}
    both = both_states_ok(control, live)
    negative_start_only = (not start_pred["pass"]) and (control_after.get("ok") is True)
    negative_one_more = not one_more_pred["pass"]
    exception_observed = raised.get("observed_exception") or {}

    fails: list[str] = []
    if not live_pred["pass"]:
        fails.extend("live: " + f for f in live_pred["fails"])
    if not mixed_pred["pass"]:
        fails.extend("mixed: " + f for f in mixed_pred["fails"])
    if not raised_pred["pass"]:
        fails.extend("raised: " + f for f in raised_pred["fails"])
    if not both:
        fails.append("both-states control failed")
    if control_after.get("code") != G.CODE_OK:
        fails.append("control post-call was not OK")
    if not control_after.get("wrote"):
        fails.append("control post-call wrote nothing")
    if start_pred["pass"]:
        fails.append("start-time-only evaluation unexpectedly passed TST-0228")
    if one_more_pred["pass"]:
        fails.append("one-more-call mutant unexpectedly passed TST-0228")
    if exception_observed.get("code") != G.CODE_REVOKED:
        fails.append("raise_on_deny did not surface CapabilityRevoked")
    if exception_observed.get("type") != "CapabilityRevoked":
        fails.append("raise_on_deny exception type is not CapabilityRevoked")

    return {
        "pass": not fails,
        "fails": fails,
        "both_states": both,
        "negative_control": negative_start_only,
        "mutation_control": negative_one_more,
        "live": live,
        "control": control,
        "mixed": mixed,
        "raised": raised,
        "start_time_only": start_only,
        "one_more_call": one_more,
        "live_predicate": live_pred,
        "mixed_predicate": mixed_pred,
        "raised_predicate": raised_pred,
        "start_time_only_predicate": start_pred,
        "one_more_call_predicate": one_more_pred,
        "workspace_mjs": "tools/lib/workspace.mjs",
        "net_allowlist_mjs": "tools/lib/net-allowlist.mjs",
    }
