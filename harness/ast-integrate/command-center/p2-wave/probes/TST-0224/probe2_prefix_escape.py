#!/usr/bin/env python3
"""Probe 2: StartsWith prefix-escape regression plus the other denials.

tools/libextra must be admitted by a naive String StartsWith against
tools/lib, and denied by tools/lib/workspace.mjs. Independent filesystem
stat after the attempted write must show no landing file. The same live
run also denies tools/lib/../x, a symlink pointing outside, and a
case-variant path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_all  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0224.json"
DENY_IDS = (
    "prefix-sibling-libextra",
    "dotdot-escape",
    "symlink-outside",
    "case-variant",
)


def main() -> int:
    summary = run_all()
    by_id = {c["id"]: c for c in summary["cases"]}
    libextra = by_id["prefix-sibling-libextra"]
    denials = {i: by_id[i] for i in DENY_IDS}
    payload = {
        "canary_unchanged": summary["canary_unchanged"],
        "naive_allows_libextra": summary["naive_allows_libextra"],
        "pass": bool(
            summary["naive_allows_libextra"]
            and summary["seed_sut_denies_libextra"]
            and summary["all_denies_hold"]
            and summary["canary_unchanged"]
        ),
        "probe": "probe2-prefix-escape",
        "seed_fs_exists": libextra["fs_after"]["exists"],
        "seed_sut_allowed": libextra["sut"]["allowed"],
        "unit_id": "TST-0224",
        "verdicts": {
            i: {
                "fs_exists": denials[i]["fs_after"]["exists"],
                "naive": denials[i]["naive_startswith_allows"],
                "sut_allowed": denials[i]["sut"]["allowed"],
            }
            for i in DENY_IDS
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if not libextra["naive_startswith_allows"]:
        print("FAILED:TST-0224-probe2 naive StartsWith did not admit tools/libextra")
        return 1
    if libextra["sut"]["allowed"] or libextra["fs_after"]["exists"]:
        print("FAILED:TST-0224-probe2 real containment admitted or wrote libextra")
        return 1
    for case_id, row in denials.items():
        if row["sut"]["allowed"] or row["fs_after"]["exists"] or not row["pass"]:
            print(f"FAILED:TST-0224-probe2 denial {case_id} did not hold")
            return 1
    if not summary["canary_unchanged"]:
        print("FAILED:TST-0224-probe2 outside canary mutated")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        live = (doc.get("live_measurements") or {}).get("prefix_escape") or {}
        if live.get("naive_allows_libextra") is False:
            print("FAILED:TST-0224-probe2 artifact lost the StartsWith seed")
            return 1
        if live.get("seed_sut_denies_libextra") is False:
            print("FAILED:TST-0224-probe2 artifact claims libextra was allowed")
            return 1
    print(
        "SUCCESS:TST-0224-probe2 naive StartsWith admits libextra; "
        "realpath containment denies libextra, ../x, symlink, case-variant"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
