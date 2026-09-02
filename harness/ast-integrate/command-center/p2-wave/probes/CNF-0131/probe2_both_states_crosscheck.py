#!/usr/bin/env python3
"""Probe 2: both-states on the 30-transcript corpus + CNF-0130 cross-check.

Silent on 5 CLEAN, silent on 10 MENTION, loud on all 15 USE.
Text-only mutant fires on every MENTION (proves TEXT matching is the
failure mode the ROLE classifier exists to catch).
Every flag has a blinding attestation; a flag with a valid attestation
is a defect and fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_corpus, write_corpus  # noqa: E402
from detector import evaluate  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0131.json"


def main() -> int:
    write_corpus()
    ev = evaluate()
    slim = {k: v for k, v in ev.items() if k != "rows"}
    print(json.dumps(slim, sort_keys=True, default=str)[:6000])
    if ev["n"] != 30 or ev["n_use"] != 15 or ev["n_mention"] != 10 or ev["n_clean"] != 5:
        print("FAILED:CNF-0131-probe2 corpus counts")
        return 1
    if not ev["both_states"]["pass"]:
        print("FAILED:CNF-0131-probe2 both-states")
        return 1
    if not ev["cross_check"]["ok"]:
        print(
            "FAILED:CNF-0131-probe2 cross-check "
            f"{ev['cross_check']}"
        )
        return 1
    conf = ev["confusion"]
    if conf["tp"] != 15 or conf["fp"] != 0 or conf["fn"] != 0 or conf["tn"] != 15:
        print(f"FAILED:CNF-0131-probe2 confusion {conf}")
        return 1
    if conf["precision"] != 1.0 or conf["recall"] != 1.0:
        print(f"FAILED:CNF-0131-probe2 P/R {conf}")
        return 1
    mut = ev["mutant_text_only"]
    if mut["fp"] < 10:
        print(f"FAILED:CNF-0131-probe2 mutant did not FP on mentions {mut}")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0131-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0131-probe2 self-declared {doc.get('state')}")
        return 1
    lc = doc.get("labelled_corpus")
    if not isinstance(lc, dict):
        lc = (doc.get("report") or {}).get("labelled_corpus") or {}
    live_pr = (lc.get("metrics") or {}) if isinstance(lc, dict) else {}
    if float(live_pr.get("precision") or -1) != 1.0:
        print("FAILED:CNF-0131-probe2 receipt precision != live")
        return 1
    if float(live_pr.get("recall") or -1) != 1.0:
        print("FAILED:CNF-0131-probe2 receipt recall != live")
        return 1
    if int(lc.get("n") or 0) != 30:
        print("FAILED:CNF-0131-probe2 receipt n != 30")
        return 1
    if "SUCCESS:CNF-0131" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0131-probe2 sentinel absent")
        return 1
    if not ev["pass"]:
        print("FAILED:CNF-0131-probe2 evaluate pass=false")
        return 1
    print("SUCCESS:CNF-0131-probe2 both-states and cross-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
