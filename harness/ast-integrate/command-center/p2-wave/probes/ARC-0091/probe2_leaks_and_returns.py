#!/usr/bin/env python3
"""Probe 2: leak-declaration completeness + no-silent-return control.

Both-states: a good two-vendor instance is accepted; empty leaks, missing
marker, inline transport, and background=true are rejected. AST of
_dispatch_impl shows every return calls emit_terminal. A silent {} return
is caught by dispatch().
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0091.json"
UNIT_ID = "ARC-0016"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0091-probe2 {msg}")
    return 1


def main() -> int:
    if "SUCCESS:ARC-0091" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    unit = A.catalog_unit(UNIT_ID)
    scratch = HERE / "scratch" / "probe2"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    good = A.two_vendor_run(unit, workdir=scratch)
    gerr = A.validate_instance(good)
    print(f"good_accepted={not gerr} nerr={len(gerr)}")
    if gerr:
        return fail("good-instance-rejected:" + " | ".join(gerr[:6]))

    empty_root = copy.deepcopy(good)
    empty_root["abstraction_leaks"] = []
    e1 = A.validate_instance(empty_root)
    print(f"empty_root_leaks rejected={bool(e1)} n={len(e1)}")
    if not e1:
        return fail("empty-root-leaks-accepted")

    empty_disp = copy.deepcopy(good)
    empty_disp["dispatches"][0]["abstraction_leaks"] = []
    e2 = A.validate_instance(empty_disp)
    print(f"empty_dispatch_leaks rejected={bool(e2)} n={len(e2)}")
    if not e2:
        return fail("empty-dispatch-leaks-accepted")

    all_honored = copy.deepcopy(good)
    for leak in all_honored["abstraction_leaks"]:
        leak["honored"] = True
    for d in all_honored["dispatches"]:
        for leak in d["abstraction_leaks"]:
            leak["honored"] = True
    e3 = A.validate_instance(all_honored)
    print(f"all_honored_leaks rejected={bool(e3)} n={len(e3)}")
    if not e3:
        return fail("vacuous-all-honored-leaks-accepted")

    no_marker = copy.deepcopy(good)
    no_marker["dispatches"][1]["terminal_marker"] = ""
    e4 = A.validate_instance(no_marker)
    print(f"empty_marker rejected={bool(e4)} n={len(e4)}")
    if not e4:
        return fail("empty-marker-accepted")

    inline = copy.deepcopy(good)
    inline["prompt_transport_rule"] = "inline"
    e5 = A.validate_instance(inline)
    print(f"inline_transport rejected={bool(e5)} n={len(e5)}")
    if not e5:
        return fail("inline-transport-accepted")

    bg = copy.deepcopy(good)
    bg["dispatches"][0]["background"] = True
    e6 = A.validate_instance(bg)
    print(f"background_true rejected={bool(e6)} n={len(e6)}")
    if not e6:
        return fail("background-true-accepted")

    points = A.impl_return_points()
    print(f"return_points n={len(points)} all_emit={all(p['emits_terminal'] for p in points)}")
    if len(points) < 6:
        return fail(f"too-few-return-points:{len(points)}")
    silent = [p for p in points if not p["emits_terminal"]]
    if silent:
        return fail(f"silent-return-lines:{[p['lineno'] for p in silent]}")

    real_impl = A._dispatch_impl

    def mute(*_a, **_k):
        return {}

    A._dispatch_impl = mute  # type: ignore[assignment]
    try:
        caught = A.dispatch(unit, "anthropic", workdir=scratch / "silent")
    finally:
        A._dispatch_impl = real_impl
    print(f"silent_caught kind={caught.get('terminal_kind')} reason={caught.get('reason')}")
    if caught.get("terminal_kind") != "FAILED" or "silent-return" not in str(caught.get("reason")):
        return fail("silent-return-not-caught")

    empty_out = A.dispatch(unit, "openai", force_empty_output=True, workdir=scratch / "empty")
    print(f"empty_output kind={empty_out.get('terminal_kind')} reason={empty_out.get('reason')}")
    if empty_out.get("terminal_kind") != "SEVERED":
        return fail(f"empty-output-not-severed:{empty_out.get('terminal_kind')}")

    bad_json = A.dispatch(unit, "anthropic", force_bad_json=True, workdir=scratch / "badjson")
    print(f"bad_json kind={bad_json.get('terminal_kind')} reason={bad_json.get('reason')}")
    if bad_json.get("terminal_kind") != "SEVERED":
        return fail(f"bad-json-not-severed:{bad_json.get('terminal_kind')}")

    loud = A.dispatch(
        unit,
        "anthropic",
        require_tool="mcp__codex__codex",
        workdir=scratch / "downgrade",
    )
    print(f"downgrade kind={loud.get('terminal_kind')} reason={loud.get('reason')}")
    if loud.get("terminal_kind") != "FAILED" or "silent-downgrade-refused" not in str(
        loud.get("reason")
    ):
        return fail("guaranteed-mismatch-not-loud")

    # Catalog anchors: contract question names the six required surfaces.
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    row = next(u for u in catalog["work_units"] if u.get("id") == "ARC-0091")
    q = str(row.get("question_or_target") or "")
    for needle in (
        "capability negotiation record",
        "abstraction-leak",
        "by file, never inline",
        "32,767",
        "blocking-dispatch",
        "terminal-state result marker",
    ):
        if needle not in q:
            return fail(f"catalog-question-missing:{needle}")
        print(f"anchor ok={needle}")

    print("SUCCESS:ARC-0091-probe2 leaks+no-silent-return both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
