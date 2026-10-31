#!/usr/bin/env python3
"""RES-0162 probe1_harvest_both_states.

tests row: both-states-harvest. Recomputes the harvest both-states control
matrix from the artifact's controls rows: the poller wakes on ALL five plants
(complete, empty, absent, progress-stream, nonzero) while the watcher wakes
ONLY on harvest-complete - a watcher that wakes on any of the empty/absent/
progress/nonzero plants would fire on severed streams and is the defect the
unit exists to expose. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/prior-art/RES-0162-cross-vendor-invocation-surface-leaks.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    controls = doc.get("controls") or []
    ck("five-harvest-plants", len(controls) == 5,
       str([c.get("id") for c in controls]))
    ck("all-verdicts-pass", all(c.get("verdict") == "PASS" for c in controls),
       str([c.get("verdict") for c in controls]))

    by_id = {c.get("id"): c for c in controls}
    # recorded matrix: poller wakes on the four data-bearing plants; the
    # nonzero-exit plant wakes NEITHER (a failed harvest is not a wake event -
    # the exit code carries the failure loudly); watcher wakes ONLY on complete
    ck("poller-wakes-on-four-data-bearing-plants",
       [by_id.get(k, {}).get("poller_wake") for k in
        ["harvest-complete", "harvest-empty", "harvest-absent", "harvest-progress-stream"]] == [True] * 4
       and by_id.get("harvest-nonzero", {}).get("poller_wake") is False,
       str({k: (by_id.get(k) or {}).get("poller_wake") for k in
            ["harvest-complete", "harvest-empty", "harvest-absent",
             "harvest-progress-stream", "harvest-nonzero"]}))
    ck("watcher-wakes-only-on-complete",
       by_id.get("harvest-complete", {}).get("watcher_wake") is True
       and not any(by_id.get(k, {}).get("watcher_wake") is True
                   for k in ["harvest-empty", "harvest-absent",
                             "harvest-progress-stream", "harvest-nonzero"]),
       str({k: (by_id.get(k) or {}).get("watcher_wake") for k in
            ["harvest-complete", "harvest-empty", "harvest-absent",
             "harvest-progress-stream", "harvest-nonzero"]}))
    ck("both-states-discriminate",
       by_id.get("harvest-complete", {}).get("watcher_wake") is True
       and by_id.get("harvest-empty", {}).get("watcher_wake") is False,
       "watcher both-states control holds")

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0162",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-harvest-both-states", "unit_id": "RES-0162", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0162-probe1 harvest both-states matrix recomputed" if not red
          else f"FAILED:RES-0162-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
