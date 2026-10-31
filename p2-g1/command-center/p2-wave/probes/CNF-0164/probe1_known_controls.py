#!/usr/bin/env python3
"""CNF-0164 probe1: planted quote-fidelity controls, re-run live.

Replays the receipt's recorded control expectations through the rebuilt
classifier against the planted fixture source, asserting:
  * detector self-check: a known-present quote classifies exact BEFORE any
    absent verdict is trusted (and the matched slice is printed);
  * CTRL-EXACT / CTRL-EXACT-CRLF classify exact (good state stays silent
    under the paraphrase trap);
  * CTRL-PARAPHRASE classifies paraphrase, not exact (known-broken fires);
  * CTRL-WHITESPACE classifies whitespace-different, not paraphrase;
  * CTRL-ABSENT classifies absent;
  * CTRL-EXTERNAL-NO-ARCHIVE classifies NOT-CHECKED;
  * every recorded receipt control row's class equals the fresh verdict.

Emits the recorded output-tail style lines and exits 0 only when every
control agrees. Re-materialized 2026-10-26 (shard8-w3 builder) after the
prior builder attempt died mid-flight; the receipt's tests[].command rows
reference this exact script name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parents[3]
sys.path.insert(0, str(PROBE_DIR))
from classifier import (  # noqa: E402
    CLASS_ABSENT, CLASS_EXACT, CLASS_NOT_CHECKED, CLASS_WS,
    classify, detector_self_check)

RECEIPT_REL = "command-center/receipts/CNF-0164.json"
CHECKS = []
FACTS = {}


def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)


def main() -> int:
    receipt = json.loads((REPO / RECEIPT_REL).read_text(encoding="utf-8"))
    fx = json.loads((PROBE_DIR / "fixtures" / "planted-quotes.json").read_text(encoding="utf-8"))
    src_path = PROBE_DIR / "fixtures" / "source.txt"
    src = src_path.read_bytes()

    # --- recorded rows from the receipt (expectations) ---
    recorded = {}
    for c in receipt["extensions"]["cases"]:
        recorded[c["id"]] = c
    for c in receipt["extensions"].get("absent_cases") or []:
        recorded.setdefault(c["id"], c)
    for c in receipt["extensions"].get("not_checked_cases") or []:
        recorded.setdefault(c["id"], c)

    # --- detector self-check FIRST (known-present before absent is trusted) ---
    exact_quote = next(c["quote"] for c in fx["controls"] if c["id"] == "CTRL-EXACT")
    found, slice_ = detector_self_check(exact_quote, src)
    FACTS["detector_self"] = {"known_present": found, "slice": slice_}
    ck("detector_self_known_present", found)
    print(f"DETECTOR-SELF known_present={str(found).lower()} slice={slice_!r}")

    results = {}
    all_ok = True
    for c in fx["controls"]:
        cid = c["id"]
        external = cid == "CTRL-EXTERNAL-NO-ARCHIVE"
        cls, reason = classify(c["quote"], src, external=external, archive_present=not external)
        got = cls
        expect = c["expect"]
        results[cid] = {"expect": expect, "got": got, "reason": reason}
        print(f"{cid} expect={expect} got={got} resolution={'external-no-archive' if external else 'worktree'}")
        ck(f"{cid}_matches_expect", got == expect)
        rec = recorded.get(cid)
        ck(f"{cid}_matches_recorded_receipt_class", bool(rec) and rec.get("class") == got)
        all_ok &= (got == expect)

    # --- both-states discipline, stated explicitly ---
    ck("paraphrase_trap_fires_not_exact",
       results["CTRL-PARAPHRASE"]["got"] != CLASS_EXACT)
    ck("good_state_still_exact",
       results["CTRL-EXACT"]["got"] == CLASS_EXACT)
    ck("whitespace_not_paraphrase",
       results["CTRL-WHITESPACE"]["got"] == CLASS_WS)
    ck("absent_case_classified_absent",
       results["CTRL-ABSENT"]["got"] == CLASS_ABSENT)
    ck("external_no_archive_not_checked",
       results["CTRL-EXTERNAL-NO-ARCHIVE"]["got"] == CLASS_NOT_CHECKED)

    raw = {"probe": "probe1_known_controls", "unit": "CNF-0164",
           "facts": FACTS, "results": results, "checks": CHECKS,
           "all_ok": all(c["ok"] for c in CHECKS)}
    (PROBE_DIR / "probe1_known_controls.raw.json").write_bytes(
        json.dumps(raw, indent=1, ensure_ascii=False).encode("utf-8"))
    print(json.dumps(raw))
    ok = raw["all_ok"]
    print("SUCCESS:CNF-0164-probe1 known-present known-broken whitespace detector-self"
          if ok else
          "FAILED:CNF-0164-probe1 control disagreement")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
