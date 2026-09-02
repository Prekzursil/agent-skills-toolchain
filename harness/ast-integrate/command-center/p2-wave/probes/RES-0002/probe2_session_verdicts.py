#!/usr/bin/env python3
"""Probe 2: one-session WebSearch/Read/WebFetch verdicts plus 200/404 control.

Does not re-run the AST/regex locator. Re-runs the loopback HTTP pair and
feeds the same session_id events to live (if any) and reconstructed hooks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import OUTPUT_REL, REPO, SENTINEL, UNIT_ID  # noqa: E402
from measure import expected_reconstructed, measure  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    art = REPO / OUTPUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = measure()
    http_pair = live["http_pair"]
    if http_pair.get("ok_status") != 200 or http_pair.get("missing_status") != 404:
        return fail("loopback HTTP pair was not 200/404")
    if not http_pair.get("ok_body_matches_fixture"):
        return fail("HTTP 200 body did not match fixture bytes")
    if not http_pair.get("missing_body_matches_fixture"):
        return fail("HTTP 404 body did not match fixture bytes")

    want = expected_reconstructed()
    for name, expect in want.items():
        got = live["sessions"][name]["verdicts"]
        for key in ("WebSearch", "Read", "WebFetch", "WebFetch_404"):
            if got.get(key) != expect[key]:
                return fail(f"{name} {key} got={got.get(key)} want={expect[key]}")
        if live["sessions"][name]["both_states"] != expect["both_states"]:
            return fail(f"{name} both_states drifted")
        if live["sessions"][name]["scope"] != expect["scope"]:
            return fail(f"{name} scope drifted")

    rec_tools = doc.get("verdicts_per_tool_type") or {}
    live_tools = live["verdicts_per_tool_type"]
    for tool in ("WebSearch", "Read", "WebFetch", "WebFetch_404"):
        for field in (
            "live",
            "reconstructed_status_as_exit",
            "reconstructed_eq_200",
            "correct_control",
        ):
            got = (live_tools.get(tool) or {}).get(field)
            stored = (rec_tools.get(tool) or {}).get(field)
            if got != stored:
                return fail(f"artifact drift {tool}.{field} stored={stored} live={got}")

    live_v = live["sessions"]["live"]["verdicts"]
    if live["estate"]["hook_script_count"] == 0:
        for tool in ("WebSearch", "Read", "WebFetch", "WebFetch_404"):
            if live_v.get(tool) != "NOT-FIRED":
                return fail(f"absent hook produced {tool}={live_v.get(tool)}")

    # status-as-exit: FAILED in both HTTP states (measures nothing as detector)
    rec = live["sessions"]["inverted_status_as_exit"]
    if rec["both_states"] != "FAILED-IN-BOTH":
        return fail("status-as-exit both-states was not FAILED-IN-BOTH")
    if rec["scope"] != "WebFetch-specific":
        return fail("status-as-exit was not WebFetch-specific")

    payload = {
        "pass": True,
        "probe": "probe2-session-verdicts",
        "unit_id": UNIT_ID,
        "live_verdicts": live_v,
        "reconstructed_status_as_exit": rec["verdicts"],
        "reconstructed_scope": rec["scope"],
        "both_states": rec["both_states"],
        "http_ok": http_pair["ok_status"],
        "http_missing": http_pair["missing_status"],
        "one_session": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe2 "
        f"live={live_v} reconstructed={rec['verdicts']} "
        f"scope={rec['scope']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
