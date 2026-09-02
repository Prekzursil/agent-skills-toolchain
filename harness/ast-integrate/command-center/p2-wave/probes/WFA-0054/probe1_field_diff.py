#!/usr/bin/env python3
"""Probe 1: field-level native↔IR↔native diffs on each adapter's FULL claimed corpus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import evaluate_all  # noqa: E402


def main() -> int:
    report = evaluate_all()
    if report["adapter_count"] != 9:
        print(f"FAILED:WFA-0054-probe1 expected 9 adapters got {report['adapter_count']}")
        return 1
    if not report["full_corpus"]:
        print("FAILED:WFA-0054-probe1 corpus was sampled rather than run in full")
        return 1
    if report["undeclared_total"] != 0:
        print(
            "FAILED:WFA-0054-probe1 undeclared losses "
            + json.dumps(
                [
                    {
                        "adapter_id": row["adapter_id"],
                        "items": [
                            {
                                "corpus_id": item["corpus_id"],
                                "undeclared_losses": item["undeclared_losses"],
                            }
                            for item in row["items"]
                            if item["undeclared_losses"]
                        ],
                    }
                    for row in report["adapters"]
                    if row["undeclared_loss_count"]
                ]
            )
        )
        return 1
    for row in report["adapters"]:
        observed = sorted(
            {
                field
                for item in row["items"]
                for field in item["declared_lossy_observed"]
            }
        )
        print(
            f"adapter={row['adapter_id']} corpus={row['ran_corpus_size']}/"
            f"{row['claimed_corpus_size']} undeclared=0 "
            f"declared_lossy_observed={observed} "
            f"carried={row['declared_carried_fields']}"
        )
        for item in row["items"]:
            print(
                f"  item={item['corpus_id']} differing_carried="
                f"{[d['path'] for d in item['differing_carried_fields']] or '[]'}"
            )
    print(
        f"adapters=9 items={report['corpus_items_total']} "
        f"undeclared_total=0 full_corpus=True"
    )
    print("SUCCESS:WFA-0054-probe1 field-level diffs on full claimed corpora")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
