#!/usr/bin/env python3
"""Probe 2: comment-only reservation fails; deferral log audited independently.

Negative control: a reservation that exists only as a config comment must
not keep interactive wait in budget and must not emit interactive-headroom
deferrals while a slot is free.

Independent signal (b): re-read the scheduler arrival record at the moment
the interactive request is admitted. Does not trust probe 1's pass flag.
AST-checks that batch_ceiling consults interactive_reserved.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from b07_scheduler import (  # noqa: E402
    COMMENT_ONLY_CONFIG_TEXT,
    HOLD_S,
    REASON_HEADROOM,
    WAIT_BUDGET_S,
    LaneScheduler,
    active_config,
    comment_only_config,
    parse_lane_config,
    run_arm,
    run_trial,
)

OUT = HERE / "probe2-comment-and-deferral-audit.raw.json"
ART = REPO / "command-center" / "receipts" / "TST-0140.json"
SENTINEL = "SUCCESS:TST-0140"
LANES = "command-center/lib/b07_scheduler/lanes.py"
N = 6


def fail(payload: dict, msg: str) -> int:
    payload["pass"] = False
    payload["error"] = msg
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"FAILED:TST-0140-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact missing"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    return None


def ast_reservation_is_load_bearing(src: str) -> tuple[bool, str]:
    tree = ast.parse(src)
    ceiling_ok = False
    admit_uses_ceiling = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "batch_ceiling":
            attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            has_sub = any(
                isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub)
                for n in ast.walk(node)
            )
            if (
                "interactive_reserved" in attrs
                and "reservation_enabled" in attrs
                and has_sub
            ):
                ceiling_ok = True
        if isinstance(node, ast.FunctionDef) and node.name == "_try_admit_unlocked":
            called: list[str] = []
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                    called.append(n.func.attr)
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    called.append(n.func.id)
            if "batch_ceiling" in called:
                admit_uses_ceiling = True
    if not ceiling_ok:
        return (
            False,
            "batch_ceiling does not subtract interactive_reserved under reservation_enabled",
        )
    if not admit_uses_ceiling:
        return False, "_try_admit_unlocked does not consult batch_ceiling"
    return True, "batch_ceiling subtracts interactive_reserved; admit path uses it"


def independent_arrival_audit() -> dict:
    cfg = active_config()
    trial = run_trial(config=cfg, sweep=True, hold_s=HOLD_S, trial_id=9001)
    arrival = trial["arrival"]
    extra = arrival["extra_batch"]
    inter = arrival["interactive"]
    ok = (
        extra.get("action") == "DEFER"
        and extra.get("reason") == REASON_HEADROOM
        and int(extra.get("occupied", 99)) < int(extra.get("capacity", 0))
        and inter.get("action") == "ADMIT"
        and arrival.get("headroom_deferral") is True
        and trial["interactive_action"] == "ADMIT"
        and float(trial["interactive_wait_s"]) <= WAIT_BUDGET_S
    )
    return {
        "ok": ok,
        "extra_batch_action": extra.get("action"),
        "extra_batch_reason": extra.get("reason"),
        "occupied": extra.get("occupied"),
        "capacity": extra.get("capacity"),
        "interactive_action": inter.get("action"),
        "interactive_wait_s": trial["interactive_wait_s"],
        "dt_mono": arrival.get("dt_mono"),
        "headroom_deferral": arrival.get("headroom_deferral"),
    }


def main() -> int:
    payload: dict = {
        "probe": "probe2-comment-and-deferral-audit",
        "unit_id": "TST-0140",
        "pass": False,
        "reviewer_id": "TST-0140-probe2-deferral-audit",
        "independent": True,
    }
    err = check_receipt()
    if err:
        return fail(payload, err)

    src = (REPO / LANES).read_text(encoding="utf-8")
    ast_ok, ast_why = ast_reservation_is_load_bearing(src)
    payload["ast_ok"] = ast_ok
    payload["ast_why"] = ast_why
    if not ast_ok:
        return fail(payload, ast_why)

    parsed = parse_lane_config(COMMENT_ONLY_CONFIG_TEXT)
    comments = comment_only_config()
    if parsed != comments:
        return fail(payload, "comment_only_config drifted from parse of fixture text")
    if comments.interactive_reserved != 0 or comments.reservation_enabled:
        return fail(payload, f"comment-only parsed as a live reservation: {comments}")
    if comments.is_measurable_reservation():
        return fail(payload, "comment-only config reports a measurable reservation")
    if "# interactive_reserved = 1" not in COMMENT_ONLY_CONFIG_TEXT:
        return fail(payload, "comment-only fixture lost the commented reservation")

    comment_arm = run_arm(comments, sweep=True, n=N, hold_s=HOLD_S)
    payload["comment_only"] = {
        "parsed": comments.to_dict(),
        "p50": comment_arm["latency"]["p50"],
        "within_budget": comment_arm["within_budget"],
        "headroom_deferral_count": comment_arm["headroom_deferral_count"],
        "samples": comment_arm["latency"]["samples"],
    }
    if comment_arm["within_budget"]:
        return fail(payload, "comment-only reservation kept interactive in budget")
    if comment_arm["headroom_deferral_count"] != 0:
        return fail(payload, "comment-only emitted interactive-headroom deferrals")
    if float(comment_arm["latency"]["p50"]) < HOLD_S * 0.6:
        return fail(
            payload,
            f"comment-only p50 {comment_arm['latency']['p50']} not a held-batch wait",
        )

    audit = independent_arrival_audit()
    payload["deferral_audit"] = audit
    if not audit["ok"]:
        return fail(payload, f"independent deferral audit failed: {audit}")

    sched = LaneScheduler(config=active_config())
    admitted = 0
    for i in range(8):
        d = sched.try_admit("batch", f"fill-{i}")
        if d.action == "ADMIT":
            admitted += 1
    extra = sched.try_admit("batch", "one-too-many")
    inter = sched.try_admit("interactive", "interactive-now")
    payload["live_fill"] = {
        "admitted_batch": admitted,
        "batch_ceiling": sched.batch_ceiling(),
        "extra_batch": extra.to_dict(),
        "interactive": inter.to_dict(),
    }
    if admitted != sched.batch_ceiling():
        return fail(payload, f"batch fill {admitted} != ceiling {sched.batch_ceiling()}")
    if extra.action != "DEFER" or extra.reason != REASON_HEADROOM:
        return fail(payload, f"extra batch not headroom-deferred: {extra.to_dict()}")
    if extra.occupied >= extra.capacity:
        return fail(payload, "headroom deferral claimed while at capacity")
    if inter.action != "ADMIT":
        return fail(
            payload, f"interactive not admitted into reserved slot: {inter.to_dict()}"
        )

    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"comment_p50={comment_arm['latency']['p50']:.6f} "
        f"audit_ok={audit['ok']} ast_ok={ast_ok} "
        f"extra={extra.reason} interactive={inter.action}"
    )
    print(
        "SUCCESS:TST-0140-probe2 comment-only fails; deferral log shows "
        "batch held at interactive arrival"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
