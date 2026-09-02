#!/usr/bin/env python3
"""Probe 2: control mutant is KILLED — the harness can produce a red.

Without a killed mutant, a silent-in-both-states campaign would report
survivors that prove nothing. This probe also refuses overclaim: the
catalog's DEFAULT_MIN_BYTES 1024->512 story is not re-measured here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness  # noqa: E402

ART = REPO / "command-center/research/RES-0096.json"
SENTINEL = (
    "SUCCESS:RES-0096 in the receipt AND at least one recorded surviving-or-killed "
    "mutant pair from this repo's actual suite"
)


def main() -> int:
    base = harness.run_baseline()
    row = harness.run_operator(
        "M-KILL-DONE-VERIFIED",
        baseline_failed=list(base.get("failed_tests") or []),
    )
    print(
        f"baseline ok={base['suite_ok']} passed={base['passed']}/{base['n']} "
        f"failed={base['failed_tests']}"
    )
    print(
        f"mutant {row['id']} verdict={row['verdict']} extra={row['extra_failures']}"
    )
    if not row["expect_met"] or row["verdict"] != "KILLED":
        print("FAILED:RES-0096-probe2 expected KILLED relative to baseline")
        return 1
    extra = row.get("extra_failures") or []
    if "test_close_sets_a_terminal_disposition_with_evidence" not in extra:
        print("FAILED:RES-0096-probe2 kill did not land on the disposition assertion")
        print(extra)
        return 1
    if not ART.is_file():
        print("FAILED:RES-0096-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0096-probe2 completion sentinel absent")
        return 1
    pairs = doc.get("mutant_pairs") or []
    killed = [p for p in pairs if p.get("verdict") == "KILLED"]
    if not killed:
        print("FAILED:RES-0096-probe2 artifact missing killed mutant")
        return 1
    blob = json.dumps(killed)
    if "DONE-VERIFIED" not in blob and "DONE-CLAIMED" not in blob:
        print("FAILED:RES-0096-probe2 killed mutant not recorded verbatim")
        return 1
    # Overclaim control: a research record that pretends the historical
    # DEFAULT_MIN_BYTES mutation was re-run on this tree is REFUSED.
    if "DEFAULT_MIN_BYTES = 1024" in text and "re-ran" in text.lower():
        print("FAILED:RES-0096-probe2 overclaim: DEFAULT_MIN_BYTES is absent on this tree")
        return 1
    print("SUCCESS:RES-0096-probe2 killed control mutant; harness is live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
