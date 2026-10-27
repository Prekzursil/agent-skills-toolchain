#!/usr/bin/env python3
"""RES-0180 probe2_live_sample.

tests row: live-20-source-sample. Recomputes the 20-source live sample from
the artifact's pairs: every pair stamped on both rounds, wake counts and the
false-wake rate re-derived and matched against the recorded summary; the
recorded live window is parsed and the honest residual (no standing 7-day
daemon was left running) is asserted so it cannot silently rot into a success
claim. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
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

    m = doc.get("measurements") or {}
    pairs = m.get("pairs") or []
    ck("twenty-pairs", len(pairs) == 20 and m.get("sample_size") == 20,
       f"n={len(pairs)} sample_size={m.get('sample_size')}")
    ck("chosen-ids-unique-twenty",
       len(set(m.get("chosen_ids") or [])) == 20,
       f"n={len(set(m.get('chosen_ids') or []))}")

    poller_wakes = sum(1 for p in pairs if p.get("poller_wake") is True)
    poller_false = sum(1 for p in pairs
                       if p.get("poller_wake") is True and p.get("false_wake_if_poller") is True)
    watcher_wakes = sum(1 for p in pairs if p.get("watcher_wake") is True)
    ck("recomputed-wakes-match-recorded",
       poller_wakes == int(m.get("poller_wakes", -1))
       and poller_false == int(m.get("poller_false_wakes", -1))
       and watcher_wakes == int(m.get("watcher_wakes", -1)),
       f"recomputed poller={poller_wakes} false={poller_false} watcher={watcher_wakes} "
       f"recorded={m.get('poller_wakes')}/{m.get('poller_false_wakes')}/{m.get('watcher_wakes')}")
    rec_rate = float(m.get("poller_false_wake_rate", -1))
    exp_rate = (poller_false / poller_wakes) if poller_wakes else 0.0
    ck("false-wake-rate-consistent", abs(rec_rate - exp_rate) < 1e-6,
       f"recorded={rec_rate} recomputed={exp_rate}")
    ck("pairs-carry-round-stamps-and-hashes",
       all(p.get("r1_sha256") and p.get("r1_observed_at") and p.get("paired") is True for p in pairs),
       f"paired={sum(1 for p in pairs if p.get('paired'))}")

    # honest residual: the standing 7d daemon was NOT left running; keep it visible
    ck("standing-7d-residual-honestly-recorded",
       m.get("standing_7d_daemon") is False,
       f"standing_7d_daemon={m.get('standing_7d_daemon')} (recorded false, not assumed)")

    s = datetime.fromisoformat(str(doc.get("live_started_at")).replace("Z", "+00:00"))
    e = datetime.fromisoformat(str(doc.get("live_ended_at")).replace("Z", "+00:00"))
    ck("live-window-parses-and-positive", (e - s).total_seconds() > 0,
       f"{doc.get('live_started_at')} -> {doc.get('live_ended_at')} ({(e - s).total_seconds():.0f}s)")

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0180",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-live-sample", "unit_id": "RES-0180", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0180-probe2 20-source sample recomputed, residual visible" if not red
          else f"FAILED:RES-0180-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
