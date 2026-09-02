#!/usr/bin/env python3
"""Probe 1: both-states + IRREDUCIBLE + live engine matches the ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_corpus  # noqa: E402
from schema_check import report_view  # noqa: E402
from tiebreak import fingerprint, scan_live  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0155.json"


def main() -> int:
    run = run_corpus(REPO)
    printable = {
        "both_states": run["both_states"],
        "irreducible": run["profile"]["irreducible"],
        "anthropic_losses": run["profile"]["anthropic"]["losses"],
        "openai_losses": run["profile"]["openai"]["losses"],
        "live_disagreeing_pairs": run["live"]["live_disagreeing_pairs"],
        "cnf_0154_present": run["live"]["cnf_0154_present"],
        "agreeing_pair_excluded": run["agreeing_pair_excluded"],
        "controls": run["controls"],
        "fingerprint": [list(x) for x in fingerprint(run["adjudications"])],
        "probe": "probe1-both-states",
        "unit_id": "CNF-0155",
    }
    print(json.dumps(printable, sort_keys=True))
    if not run["both_states"]:
        print("FAILED:CNF-0155-probe1 both-states missing")
        return 1
    if run["profile"]["irreducible"] < 1:
        print("FAILED:CNF-0155-probe1 no IRREDUCIBLE")
        return 1
    if not run["agreeing_pair_excluded"]:
        print("FAILED:CNF-0155-probe1 agreeing pair leaked")
        return 1
    if not all(run["controls"].values()):
        print(f"FAILED:CNF-0155-probe1 controls {run['controls']}")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0155-probe1 ledger missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0155-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0155" not in text:
        print("FAILED:CNF-0155-probe1 sentinel absent")
        return 1
    view = report_view(doc)
    art_fp = [tuple(x) for x in (view["fingerprint"] or [])]
    live_fp = fingerprint(run["adjudications"])
    if art_fp != live_fp:
        print("FAILED:CNF-0155-probe1 fingerprint mismatch")
        print(f" artifact={art_fp}")
        print(f" live={live_fp}")
        return 1
    live_scan = scan_live(REPO)
    art_live = view["live_corpus"]
    if bool(art_live.get("cnf_0154_present")) != bool(live_scan["cnf_0154_present"]):
        print("FAILED:CNF-0155-probe1 live CNF-0154 flag dishonest")
        return 1
    art_pairs = art_live.get("live_disagreeing_pairs")
    if art_pairs is None or int(art_pairs) != int(live_scan["live_disagreeing_pairs"]):
        print(
            f"FAILED:CNF-0155-probe1 live pair count dishonest "
            f"artifact={art_pairs} live={live_scan['live_disagreeing_pairs']}"
        )
        return 1
    outcomes = [r.get("outcome") for r in view["adjudications"]]
    if "IRREDUCIBLE" not in outcomes:
        print("FAILED:CNF-0155-probe1 artifact missing IRREDUCIBLE")
        return 1
    losers = {
        r.get("losing_vendor")
        for r in view["adjudications"]
        if r.get("outcome") == "SETTLED"
    }
    if "anthropic" not in losers or "openai" not in losers:
        print(f"FAILED:CNF-0155-probe1 artifact losers={losers}")
        return 1
    print("SUCCESS:CNF-0155-probe1 both-states irreducible live-match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
