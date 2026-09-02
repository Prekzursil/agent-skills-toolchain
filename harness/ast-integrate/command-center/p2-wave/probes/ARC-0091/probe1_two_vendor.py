#!/usr/bin/env python3
"""Probe 1: one real catalog unit through two vendors; schema discriminates.

Evidence: both adapters emit a terminal-state marker and a negotiation record.
The combined evidence document validates against ARC-0091.json. Garbage is
rejected. Prompt is by file. Dispatch is blocking.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0091.json"
UNIT_ID = "ARC-0016"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
]


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0091-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("contract missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0091" not in text:
        return fail("sentinel-absent")
    schema = json.loads(text)
    if str(schema.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{schema.get('state')}")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return fail(f"check_schema:{type(exc).__name__}:{exc}")
    v = Draft202012Validator(schema)
    for i, g in enumerate(GARBAGE):
        errs = list(v.iter_errors(g))
        print(f"garbage[{i}] rejected={bool(errs)} n={len(errs)}")
        if not errs:
            return fail(f"schema-vacuous garbage[{i}]")

    unit = A.catalog_unit(UNIT_ID)
    scratch = HERE / "scratch" / "probe1"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    evidence = A.two_vendor_run(unit, workdir=scratch)
    print(f"unit={UNIT_ID} vendors={[d.get('vendor') for d in evidence['dispatches']]}")
    neg = evidence.get("negotiation") or {}
    print(
        f"negotiation computed={neg.get('intersection_computed')} "
        f"silent_downgrade={neg.get('silent_downgrade_attempted')} "
        f"tier={neg.get('unit_minimum_tier')}"
    )
    if neg.get("intersection_computed") is not True:
        return fail("intersection-not-computed")
    if neg.get("silent_downgrade_attempted") is not False:
        return fail("silent-downgrade-flag")
    tools_row = next(r for r in neg["capabilities"] if r["axis"] == "tools")
    inter = set(tools_row["intersection"])
    a_tools = set(tools_row["per_vendor"]["anthropic"])
    b_tools = set(tools_row["per_vendor"]["openai"])
    if inter != (a_tools & b_tools):
        return fail("tools-intersection-not-computed")
    ctx = next(r for r in neg["capabilities"] if r["axis"] == "context_window")
    if ctx["intersection"] != min(ctx["per_vendor"]["anthropic"], ctx["per_vendor"]["openai"]):
        return fail("context-intersection-not-computed")

    markers = []
    for d in evidence["dispatches"]:
        kind = d.get("terminal_kind")
        marker = d.get("terminal_marker")
        print(f"dispatch vendor={d.get('vendor')} kind={kind} marker={marker}")
        if kind != "SUCCESS":
            return fail(f"vendor-{d.get('vendor')}-not-success:{kind}:{d.get('reason')}")
        if not isinstance(marker, str) or not marker.startswith("SUCCESS:"):
            return fail(f"marker-missing:{d.get('vendor')}")
        if d.get("prompt_transport") != "file" or not d.get("prompt_file_written"):
            return fail(f"prompt-not-by-file:{d.get('vendor')}")
        if d.get("dispatch_mode") != "blocking_foreground" or d.get("background") is not False:
            return fail(f"not-blocking:{d.get('vendor')}")
        argv = d.get("argv") or []
        if "--prompt-file" not in argv:
            return fail(f"argv-missing-prompt-file:{d.get('vendor')}")
        if "--background" in argv:
            return fail(f"argv-has-background:{d.get('vendor')}")
        prompt_path = Path(d["prompt_path"])
        body = prompt_path.read_text(encoding="utf-8")
        if body in " ".join(argv):
            return fail(f"prompt-inline-on-argv:{d.get('vendor')}")
        if d.get("command_contains_prompt_body") is not False:
            return fail(f"command_contains_prompt_body:{d.get('vendor')}")
        markers.append(marker)

    errs = A.validate_instance(evidence)
    print(f"instance_errors={errs[:4]} n={len(errs)}")
    if errs:
        return fail("evidence-schema-invalid:" + " | ".join(errs[:6]))

    bg = A.dispatch(unit, "anthropic", background=True)
    print(f"background_refused kind={bg.get('terminal_kind')} reason={bg.get('reason')}")
    if bg.get("terminal_kind") != "FAILED" or "background" not in str(bg.get("reason")):
        return fail("background-not-refused")
    inline = A.dispatch(unit, "openai", prompt_inline="x" * 34472)
    print(f"inline_refused kind={inline.get('terminal_kind')} reason={inline.get('reason')}")
    if inline.get("terminal_kind") != "FAILED" or "inline" not in str(inline.get("reason")):
        return fail("inline-not-refused")
    if inline.get("prompt_inline_chars") != 0:
        return fail("inline-chars-leaked-into-record")

    print(
        f"both_markers={markers} leaks={len(evidence['abstraction_leaks'])} "
        f"runtime_live_api={evidence['runtime']['live_vendor_api']}"
    )
    print("SUCCESS:ARC-0091-probe1 two-vendor terminal+negotiation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
