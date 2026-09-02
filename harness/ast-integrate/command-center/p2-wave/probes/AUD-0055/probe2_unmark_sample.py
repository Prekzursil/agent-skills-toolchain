#!/usr/bin/env python3
"""Named probe 2: strip skip/xfail on a stratified sample and run the body.

The catalog control requires executing a fixed-bug xfail (XPASS marked,
PASS unmarked) rather than reasoning about the reason string.
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


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0055-probe2 {msg}")
    return 1


def main() -> int:
    markers = E.collect_python_markers()
    real = [m for m in markers if m.get("kind") in {"skip", "skipif", "xfail"}]
    unmark = E.run_unmark_campaign(real)
    stale = unmark.get("control_stale_xfail") or {}
    live = unmark.get("control_live_xfail") or {}
    payload = {
        "probe": "probe2-unmark-and-run",
        "unit_id": "AUD-0055",
        "sample_size": unmark["sample_size"],
        "executed_count": unmark["executed_count"],
        "stale_xfail_count": unmark["stale_xfail_count"],
        "still_justified_count": unmark["still_justified_count"],
        "masquerade_count": unmark["masquerade_count"],
        "control_ok": unmark["control_ok"],
        "scratch_is_git_worktree": False,
        "stale_marked": stale.get("marked_outcome"),
        "stale_unmarked": stale.get("unmarked_outcome"),
        "stale_unmarked_executed": stale.get("unmarked_executed"),
        "live_marked": live.get("marked_outcome"),
        "live_unmarked": live.get("unmarked_outcome"),
        "live_unmarked_executed": live.get("unmarked_executed"),
        "results": [
            {
                "function": r.get("function"),
                "kind": r.get("kind"),
                "control_id": r.get("control_id"),
                "marked_outcome": r.get("marked_outcome"),
                "unmarked_outcome": r.get("unmarked_outcome"),
                "unmarked_executed": r.get("unmarked_executed"),
                "reason_still_holds": r.get("reason_still_holds"),
                "masquerade": (r.get("masquerade") or {}).get(
                    "permanent_masquerading_as_temporary"
                ),
            }
            for r in unmark.get("results") or []
        ],
        "pass": True,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not unmark["control_ok"]:
        return fail("stale-xfail/live-xfail control did not discriminate")
    if unmark["executed_count"] < 1:
        return fail("sample was reasoned about, not executed")
    if stale.get("marked_outcome") != "XPASS":
        return fail(f"stale marked {stale.get('marked_outcome')} want XPASS")
    if stale.get("unmarked_outcome") != "PASS":
        return fail(f"stale unmarked {stale.get('unmarked_outcome')} want PASS")
    if not stale.get("unmarked_executed"):
        return fail("stale unmarked was not executed")
    if live.get("marked_outcome") != "XFAIL":
        return fail(f"live marked {live.get('marked_outcome')} want XFAIL")
    if live.get("unmarked_outcome") != "FAIL":
        return fail(f"live unmarked {live.get('unmarked_outcome')} want FAIL")
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
    art_unmark = doc.get("unmark") or {}
    art_stale = art_unmark.get("control_stale_xfail") or {}
    if art_stale.get("marked_outcome") != "XPASS":
        return fail("artifact stale control not XPASS")
    if art_stale.get("unmarked_outcome") != "PASS":
        return fail("artifact stale control unmarked not PASS")
    if art_stale.get("unmarked_executed") is not True:
        return fail("artifact stale control not executed")
    print(
        "SUCCESS:AUD-0055-probe2 unmark-and-run "
        f"executed={unmark['executed_count']} "
        f"stale=XPASS/PASS live=XFAIL/FAIL masquerade={unmark['masquerade_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
