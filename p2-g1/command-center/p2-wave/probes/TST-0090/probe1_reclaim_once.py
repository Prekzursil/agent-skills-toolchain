#!/usr/bin/env python3
"""TST-0090 probe1: reclaim exactly once with fencing (live, fail-closed).

Simulated clock; the four both-states rows from the receipt: unexpired
lease blocks reclaim; expired lease permits exactly ONE reclaim (token
1 -> 2, the second reclaimer is denied); the thawed original's write is
REJECTED with its stale token recorded; the reclaimer commits. Asserts
the receipt's evidence_run re-derives (orig_token=1, reclaim_token=2,
thawed REJECTED stale-fencing-token)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0090"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from fencing_lease import FencingLeaseStore  # noqa: E402

UNIT = "TST-0090"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 2048, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0090" in text, "sentinel-absent")

    t = [0.0]

    def clock() -> float:
        return t[0]

    s = FencingLeaseStore(ttl_s=1.0, clock=clock)
    tok = s.acquire("orig")
    chk(tok == 1, "orig-token-1", str(tok))
    blocked = ""
    try:
        s.reclaim("early-reclaimer")
    except Exception as exc:
        blocked = type(exc).__name__
    chk(blocked == "LeaseDenied", "unexpired-blocks-reclaim", blocked)
    t[0] = 1.5
    tok2 = s.reclaim("reclaimer")
    chk(tok2 == 2, "expired-reclaim-token-2", str(tok2))
    second = ""
    try:
        s.reclaim("second-reclaimer")
    except Exception as exc:
        second = type(exc).__name__
    chk(second == "LeaseDenied", "second-reclaimer-denied", second)
    late = s.commit("orig", 1, "SUCCESS from thawed original")
    chk(late == "REJECTED", "zombie-write-rejected", late)
    chk(len(s.rejected) == 1 and s.rejected[0]["stale_token"] == 1 and s.rejected[0]["reason"] == "stale-fencing-token",
        "stale-token-recorded", json.dumps(s.rejected))
    commit_rc = s.commit("reclaimer", 2, "SUCCESS from reclaimer")
    chk(commit_rc == "COMMITTED", "reclaimer-commits", commit_rc)
    # two concurrent reclaimers: exactly one wins
    t[0] = 5.0
    s2 = FencingLeaseStore(ttl_s=1.0, clock=clock)
    s2.acquire("orig")
    t[0] = 6.5
    winners = []
    for name in ("reclaimer-a", "reclaimer-b"):
        try:
            winners.append((name, s2.reclaim(name)))
        except Exception:
            pass
    chk(len(winners) == 1, "exactly-one-reclaimer-wins", json.dumps(winners))
    er = doc.get("evidence_run") or {}
    chk(int(er.get("orig_token", -1)) == 1 and int(er.get("reclaim_token", -1)) == 2, "receipt-evidence-run-tokens")
    chk(str(er.get("thawed_status")) == "REJECTED" and str(er.get("thawed_reason")) == "stale-fencing-token", "receipt-thawed-rejection")
    chk(str(er.get("reclaimer_status")) == "COMMITTED", "receipt-reclaimer-committed")
    tests = doc.get("tests") or []
    chk(len(tests) >= 3, "tests-rows")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({"acquired_token": tok, "unexpired_block": blocked, "reclaim_token": tok2,
                      "second_reclaimer": second, "zombie_write": late,
                      "stale_record": s.rejected, "reclaimer_commit": commit_rc,
                      "concurrent_winner": winners}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 fencing re-derives: unexpired blocked; expired reclaimed exactly once (token 1->2); thawed original REJECTED with stale token recorded; reclaimer COMMITTED; two concurrent reclaimers yield exactly one winner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
