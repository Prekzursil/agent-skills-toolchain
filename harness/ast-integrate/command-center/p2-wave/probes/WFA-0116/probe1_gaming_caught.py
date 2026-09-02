#!/usr/bin/env python3
"""Probe 1: every planted gaming workflow is caught; the report names the signal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

UNIT = "WFA-0116"
SENTINEL = "SUCCESS:WFA-0116"
OUT = REPO / "command-center/wfa/WFA-0116-benchmark-gaming-detector.json"


def main() -> int:
    live = D.evaluate()
    gaming = [w for w in live["workflows"] if w["expected_gaming"]]
    if len(gaming) < 4:
        print("FAILED:WFA-0116-probe1 expected four planted gaming workflows")
        return 1
    missed = [w["workflow_id"] for w in gaming if not w["caught"] or not w["caught_by"]]
    if missed:
        print(f"FAILED:WFA-0116-probe1 uncaught {missed}")
        return 1
    a_hits = [
        w["workflow_id"]
        for w in gaming
        if w["signal_a"]["fired"]
    ]
    b_hits = [
        w["workflow_id"]
        for w in gaming
        if w["signal_b"]["fired"]
    ]
    if not a_hits or not b_hits:
        print(f"FAILED:WFA-0116-probe1 both signals must fire on the plant a={a_hits} b={b_hits}")
        return 1
    named = {w["workflow_id"]: list(w["caught_by"]) for w in gaming}

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        print("FAILED:WFA-0116-probe1 artifact missing")
        return 1
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:WFA-0116-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0116-probe1 self-declared", doc.get("state"))
        return 1
    art_tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    t1 = art_tests.get("planted-gaming-caught-named-signal") or {}
    if t1.get("result") != "PASS":
        print("FAILED:WFA-0116-probe1 artifact test1 not PASS")
        return 1
    art_which = t1.get("caught_by") or {}
    for wid, signals in named.items():
        rec = art_which.get(wid)
        if rec != signals:
            print(f"FAILED:WFA-0116-probe1 caught_by drift {wid} live={signals} art={rec}")
            return 1
    payload = {
        "probe": "probe1-gaming-caught",
        "unit_id": UNIT,
        "planted": len(gaming),
        "caught": len(gaming),
        "caught_by": named,
        "signal_a_workflows": a_hits,
        "signal_b_workflows": b_hits,
        "ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:WFA-0116-probe1 planted={len(gaming)} caught={len(gaming)} "
        f"named-signals a={len(a_hits)} b={len(b_hits)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
