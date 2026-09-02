#!/usr/bin/env python3
"""Probe 1: unexercised-default mutant SURVIVES the live close-test replay.

Also proves the mutant is not equivalent: omitting --days changes until-date
from NOW+7 to NOW+99 while the suite stays at the baseline failure set.
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
        "M-SURVIVE-DEFER-DAYS",
        baseline_failed=list(base.get("failed_tests") or []),
    )
    print(
        f"baseline ok={base['suite_ok']} passed={base['passed']}/{base['n']} "
        f"failed={base['failed_tests']}"
    )
    print(
        f"mutant {row['id']} verdict={row['verdict']} extra={row['extra_failures']} "
        f"semantic={row.get('semantic_omit_days')}"
    )
    if not row["expect_met"] or row["verdict"] != "SURVIVED":
        print("FAILED:RES-0096-probe1 expected SURVIVED relative to baseline")
        return 1
    if row["extra_failures"]:
        print("FAILED:RES-0096-probe1 extra failures on survivor", row["extra_failures"])
        return 1
    sem = row.get("semantic_omit_days") or ""
    want = row.get("expected_until_if_default_99") or ""
    if want not in sem:
        print("FAILED:RES-0096-probe1 equivalent-mutant not refuted; until missing", want)
        print(sem)
        return 1
    if "2026-08-16" in sem and want not in sem:
        print("FAILED:RES-0096-probe1 mutant behaved like default=7")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0096-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0096-probe1 completion sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0096-probe1 self-declared", doc.get("state"))
        return 1
    pairs = doc.get("mutant_pairs") or []
    survived = [p for p in pairs if p.get("verdict") == "SURVIVED"]
    killed = [p for p in pairs if p.get("verdict") == "KILLED"]
    if not survived or not killed:
        print("FAILED:RES-0096-probe1 missing surviving-or-killed pair")
        return 1
    if "DEFAULT_DEFER_DAYS" not in json.dumps(survived):
        print("FAILED:RES-0096-probe1 survivor pair does not name DEFAULT_DEFER_DAYS")
        return 1
    # Catalog lore must not be dressed up as a live re-measurement on this tree.
    if "reproduced DEFAULT_MIN_BYTES" in text.lower() or "1024-to-512 live" in text.lower():
        print("FAILED:RES-0096-probe1 overclaim of DEFAULT_MIN_BYTES on this tree")
        return 1
    print("SUCCESS:RES-0096-probe1 surviving unexercised-default mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
