#!/usr/bin/env python3
"""RES-0180 probe1_both_states.

tests row: both-states-control. Recomputes the wake-matrix from the artifact's
recorded controls: a GENUINE change must wake BOTH signals (poller + watcher)
while a COSMETIC change (ad markup, feed channel updated stamp, unrelated
release tag) must wake the poller ONLY - a watcher that wakes on cosmetics is
the false-wake defect this unit exists to measure. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/sources-frontier/RES-0180-watchlist-standing-recheck.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    controls = doc.get("controls") or []
    by = {c.get("id"): c for c in controls}
    ck("six-control-plants", len(controls) == 6, str(sorted(by)))
    ck("all-controls-pass", all(c.get("verdict") == "PASS" for c in controls),
       str([c.get("verdict") for c in controls]))

    genuine = [k for k in by if k.endswith("-genuine")]
    cosmetic = [k for k in by if k.endswith("-cosmetic")]
    ck("three-genuine-plants-wake-both",
       len(genuine) == 3 and all(by[k].get("poller_wake") is True and by[k].get("watcher_wake") is True
                                 for k in genuine),
       str([(k, by[k].get("poller_wake"), by[k].get("watcher_wake")) for k in genuine]))
    ck("three-cosmetic-plants-wake-poller-only",
       len(cosmetic) == 3 and all(by[k].get("poller_wake") is True and by[k].get("watcher_wake") is False
                                  for k in cosmetic),
       str([(k, by[k].get("poller_wake"), by[k].get("watcher_wake")) for k in cosmetic]))
    ck("both-states-discriminate",
       all(by[k].get("watcher_wake") is True for k in genuine)
       and not any(by[k].get("watcher_wake") is True for k in cosmetic),
       "watcher wakes on genuine only - the discriminator holds")

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0180",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-both-states", "unit_id": "RES-0180", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0180-probe1 wake matrix recomputed, watcher genuine-only" if not red
          else f"FAILED:RES-0180-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
