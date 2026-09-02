#!/usr/bin/env python3
"""Probe 1: three planted duplicate classes; per-class recall must be 1.0.

Planted kinds: exact-duplicate, paraphrase, one-parameter-fork.
A pure string-equality counter is recorded as a baseline (must be worse).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loader import load_counter, load_fixture, planted_members  # noqa: E402


def main() -> int:
    ui = load_counter()
    doc = load_fixture()
    texts, class_ids, _kinds = planted_members(doc)
    report = ui.evaluate_labeled(texts, class_ids)
    recalls = report["per_class_recall"]
    expected = {"exact-duplicate", "paraphrase", "one-parameter-fork"}
    missing = expected - set(recalls)
    if missing:
        print(json.dumps({"pass": False, "missing_classes": sorted(missing)}, indent=2))
        print("FAILED:IMP-0300-probe1 missing planted classes")
        return 1
    bad = {cid: row for cid, row in recalls.items() if row["recall"] != 1.0}
    if report["unique_count"] != 3:
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"FAILED:IMP-0300-probe1 unique_count={report['unique_count']} want=3")
        return 1
    if bad:
        print(json.dumps(report, indent=2, sort_keys=True))
        print("FAILED:IMP-0300-probe1 per-class recall not 1.0")
        return 1
    if not report["string_equality_worse"]:
        print(json.dumps(report, indent=2, sort_keys=True))
        print("FAILED:IMP-0300-probe1 string-equality counter was not worse")
        return 1
    payload = {
        "pass": True,
        "probe": "probe1-per-class-recall",
        "unit_id": "IMP-0300",
        "unique_count": report["unique_count"],
        "string_equality_count": report["string_equality_count"],
        "per_class_recall": {k: v["recall"] for k, v in recalls.items()},
        "string_equality_per_class_recall": {
            k: v["recall"] for k, v in report["string_equality_per_class_recall"].items()
        },
        "semantic_mean_recall": report["semantic_mean_recall"],
        "string_mean_recall": report["string_mean_recall"],
        "string_equality_worse": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "recall exact={:.3f} paraphrase={:.3f} fork={:.3f} unique={} string_eq={}".format(
            recalls["exact-duplicate"]["recall"],
            recalls["paraphrase"]["recall"],
            recalls["one-parameter-fork"]["recall"],
            report["unique_count"],
            report["string_equality_count"],
        )
    )
    print("SUCCESS:IMP-0300-probe1 per-class recall on three planted duplicate classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
