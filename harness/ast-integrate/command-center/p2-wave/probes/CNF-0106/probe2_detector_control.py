#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL — known-broken fixture fires; comment is not evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0106-probe2 {msg}")
    return 1


def main() -> int:
    m = H.measure()
    bw = m["blocked_warm"]
    lie = H.step(bw, "test_claims_offline_but_fetches")
    herm = H.step(bw, "test_genuinely_hermetic")
    print(f"lying_comment={C.LYING_COMMENT!r}")
    print(f"known_broken_blocked_ok={lie['ok']} dests={lie['attempted_destinations']}")
    print(f"hermetic_blocked_ok={herm['ok']}")
    if lie["ok"]:
        return fail("detector silent on known-broken fixture")
    if not lie["attempted_destinations"]:
        return fail("detector fired without a destination (incomplete evidence)")
    if not herm["ok"]:
        return fail("detector false-positive on genuinely hermetic test")
    claim = C.LYING_COMMENT.lower()
    if "never downloads" not in claim and "never touches the network" not in claim:
        return fail("lying comment fixture missing the offline claim")
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    cne = rep.get("comment_is_not_evidence") or {}
    if cne.get("blocked_run_is_the_evidence") is not True:
        return fail("artifact did not record blocked_run_is_the_evidence")
    if cne.get("blocked_run_caught_the_fetch") is not True:
        return fail("artifact did not record blocked_run_caught_the_fetch")
    dc = rep.get("detector_control") or {}
    if dc.get("fired_on_known_broken") is not True:
        return fail("artifact detector_control.fired_on_known_broken is not true")
    if dc.get("silent_on_genuinely_hermetic") is not True:
        return fail("artifact detector_control.silent_on_genuinely_hermetic is not true")
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")
    notes = str(rev.get("notes") or "") + str(rev.get("job") or "")
    if "DETECTOR CONTROL" not in notes:
        return fail("reviewer job is not detector-control re-run")
    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print("SUCCESS:CNF-0106-probe2 detector-control fired on known-broken fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
