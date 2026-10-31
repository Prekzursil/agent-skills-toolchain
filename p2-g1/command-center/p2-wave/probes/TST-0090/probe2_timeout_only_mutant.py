#!/usr/bin/env python3
"""TST-0090 probe2: timeout alone is NOT reclaim safety (independent).

Mechanically different from probe1's green path: replays the identical
zombie-dispatcher scenario against the TimeoutOnlyMutant (expiry allows
takeover, no fencing) and shows the thawed original's late write is
ACCEPTED after the reclaimer's - the hole the fencing token closes.
Then a behavioral double-axis proof on the green store: wrong token
rejected for the current holder; wrong holder rejected presenting the
current token. Asserts the receipt's fault + evidence blocks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0090"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from fencing_lease import FencingLeaseStore, TimeoutOnlyMutant  # noqa: E402

UNIT = "TST-0090"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0090" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    t = [0.0]
    m = TimeoutOnlyMutant(ttl_s=1.0, clock=lambda: t[0])
    m.acquire("orig")
    t[0] = 1.5
    m.reclaim("reclaimer")
    m.commit("reclaimer", "SUCCESS from reclaimer")
    zombie = m.commit("orig", "SUCCESS from thawed original")
    chk(zombie == "COMMITTED", "mutant-accepts-zombie-write", zombie)
    chk(len(m.committed) == 2, "mutant-double-commit", json.dumps(m.committed))
    g = FencingLeaseStore(ttl_s=1.0, clock=lambda: t[0])
    g.acquire("orig")
    t[0] = 3.0
    g.reclaim("reclaimer")
    chk(g.commit("orig", 1, "late zombie") == "REJECTED", "green-store-rejects-same-zombie")
    ax_tok = g.commit("reclaimer", 1, "current holder stale token")
    chk(ax_tok == "REJECTED" and g.rejected[-1]["stale_token"] == 1, "axis-wrong-token-rejected", ax_tok)
    ax_holder = g.commit("orig", 2, "current token wrong holder")
    chk(ax_holder == "REJECTED" and g.rejected[-1]["holder"] == "orig", "axis-wrong-holder-rejected", ax_holder)
    eng = (HERE / "fencing_lease.py").read_text(encoding="utf-8")
    chk("stale-fencing-token" in eng, "stale-rejection-recorded-in-engine")
    inj = doc.get("injected_fault") or {}
    chk(inj.get("kind") == "zombie-dispatcher", "receipt-fault-kind")
    ev = doc.get("evidence_run") or {}
    chk(ev.get("stale_token_recorded") is True, "receipt-stale-token-recorded")
    chk(str(ev.get("thawed_status")) == "REJECTED", "receipt-thawed-rejected")
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"mutant_zombie_write": zombie, "mutant_commit_count": len(m.committed),
                      "green_store_same_scenario": "REJECTED",
                      "axis_wrong_token": ax_tok, "axis_wrong_holder": ax_holder}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 timeout-only takeover ACCEPTS the thawed original's zombie write after the reclaimer (2 commits, no fencing) while the fencing store rejects the identical scenario and both stale axes (token, holder); timeout alone is not reclaim safety")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
