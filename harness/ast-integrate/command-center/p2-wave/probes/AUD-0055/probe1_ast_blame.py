#!/usr/bin/env python3
"""Named probe 1: AST census of skip/xfail/skipif plus git-blame age.

Does not execute tests. Mechanically independent of probe 2 (unmark-and-run).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.artifact_path()
SENTINEL = E.SENTINEL
CONTROL_IDS = {
    "stale-xfail-bug-fixed",
    "live-xfail-bug-present",
    "masquerade-temporary-skip",
    "skipif-true-unconditional",
}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0055-probe1 {msg}")
    return 1


def main() -> int:
    markers = E.collect_python_markers()
    js = E.collect_js_candidates()
    real = [m for m in markers if m.get("kind") in {"skip", "skipif", "xfail"}]
    fixtures = [m for m in real if m.get("in_aud0055_fixtures")]
    live = [m for m in real if not m.get("in_aud0055_fixtures")]
    found_ids = {m.get("control_id") for m in fixtures if m.get("control_id")}
    found_ids.discard("clean-no-marker")
    missing = sorted(CONTROL_IDS - found_ids)
    clean_rel = (
        "command-center/p2-wave/probes/AUD-0055/fixtures/test_clean_control.py"
    )
    clean_src = (E.REPO / clean_rel).read_text(encoding="utf-8")
    clean_marks = [
        m
        for m in E.extract_markers_from_source(clean_src, clean_rel)
        if m.get("kind") in {"skip", "skipif", "xfail"}
    ]
    blame_statuses = sorted(
        {((m.get("blame") or {}).get("status") or "MISSING") for m in real}
    )
    payload = {
        "probe": "probe1-ast-and-blame",
        "unit_id": "AUD-0055",
        "python_skip_xfail_markers": len(real),
        "live_tree_outside_aud0055_fixtures": len(live),
        "control_fixture_markers": len(fixtures),
        "js_lexical_skip_candidates": len(js),
        "control_ids_found": sorted(x for x in found_ids if x),
        "clean_control_silent": clean_marks == [],
        "git_blame_statuses": blame_statuses,
        "sample_markers": [
            {
                "path": m["path"],
                "function": m.get("function"),
                "kind": m.get("kind"),
                "reason": m.get("reason"),
                "lineno": m.get("lineno"),
                "control_id": m.get("control_id"),
                "blame": m.get("blame"),
            }
            for m in fixtures
        ],
        "pass": True,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if missing:
        return fail(f"control markers missing: {missing}")
    if clean_marks:
        return fail(f"clean control over-fired: {clean_marks}")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "AUD-0055":
        return fail(f"unit_id {doc.get('unit_id')}")
    headline = doc.get("headline") or {}
    if headline.get("control_fixture_markers") != len(fixtures):
        return fail("headline control_fixture_markers mismatch")
    if headline.get("live_tree_outside_aud0055_fixtures") != len(live):
        return fail("headline live_tree mismatch")
    print(
        "SUCCESS:AUD-0055-probe1 ast-blame "
        f"fixtures={len(fixtures)} live={len(live)} js={len(js)} "
        f"blame={','.join(blame_statuses)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
