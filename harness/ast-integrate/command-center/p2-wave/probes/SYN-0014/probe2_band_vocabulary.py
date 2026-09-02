#!/usr/bin/env python3
"""Probe 2: declared five-band vocabulary; unknown hedges reported not ignored.

Also re-reads the live artifact and requires both counts to carry
denominators and sampled_read_size >= 30.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

from bands import DECLARED_BANDS  # noqa: E402
from corpus import unknown_hedge_claims  # noqa: E402
from scan import classify_claim  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0014.json"
EXPECTED = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)


def main() -> int:
    if tuple(DECLARED_BANDS) != EXPECTED:
        print(f"FAILED:SYN-0014-probe2 declared_bands={DECLARED_BANDS}")
        return 1
    if len(set(DECLARED_BANDS)) != 5:
        print("FAILED:SYN-0014-probe2 band vocabulary is not five distinct tokens")
        return 1
    print(f"declared_bands={list(DECLARED_BANDS)}")

    for claim in unknown_hedge_claims():
        row = classify_claim(claim, REPO)
        print(
            f"hedge {row['id']} band={row.get('band')} "
            f"unknown_hedges={row.get('unknown_hedges')}"
        )
        if row.get("band"):
            print(
                f"FAILED:SYN-0014-probe2 unknown hedge mapped to band="
                f"{row.get('band')} id={row['id']}"
            )
            return 1
        if not row.get("unknown_hedges"):
            print(f"FAILED:SYN-0014-probe2 unknown hedge ignored id={row['id']}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0014-probe2 live artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    a = doc.get("band_without_any_anchor") or report.get("band_without_any_anchor") or {}
    b = (
        doc.get("band_not_supported_by_its_anchor")
        or report.get("band_not_supported_by_its_anchor")
        or {}
    )
    sample_n = int(doc.get("sampled_read_size") or report.get("sampled_read_size") or 0)
    declared = doc.get("declared_bands") or report.get("declared_bands") or []
    print(
        f"live no_anchor={a.get('count')}/{a.get('denominator')} "
        f"unsupported={b.get('count')}/{b.get('denominator')} "
        f"sampled_read_size={sample_n}"
    )
    if a.get("denominator") is None or int(a.get("denominator") or -1) < 0:
        print("FAILED:SYN-0014-probe2 band_without_any_anchor missing denominator")
        return 1
    if b.get("denominator") is None or int(b.get("denominator") or -1) < 1:
        print("FAILED:SYN-0014-probe2 band_not_supported_by_its_anchor missing denominator")
        return 1
    if sample_n < 30:
        print(f"FAILED:SYN-0014-probe2 sampled_read_size={sample_n} < 30")
        return 1
    if int(b.get("sample_size") or 0) != sample_n:
        print("FAILED:SYN-0014-probe2 sample_size does not match sampled_read_size")
        return 1
    if list(declared) != list(DECLARED_BANDS):
        print("FAILED:SYN-0014-probe2 live declared_bands drift")
        return 1
    print("SUCCESS:SYN-0014-probe2 band vocabulary and hedge residue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
