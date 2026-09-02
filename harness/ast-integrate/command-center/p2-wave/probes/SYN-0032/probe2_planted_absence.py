#!/usr/bin/env python3
"""Probe 2: planted synthesis omission -> RECEIPTS-ONLY; TOC mentions do not count."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from coverage import compute_coverage  # noqa: E402
from graph import EXPECTED_BUCKET_IDS, load_phase_graph  # noqa: E402


def receipt_body(stem: str) -> str:
    return json.dumps({"unit_id": stem, "state": "SUCCESS"}, indent=1)


def by_id(table: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in table}


def main() -> int:
    graph = load_phase_graph(REPO)
    prefix_map = graph["prefix_map"]
    phases = list(graph["phases"])
    body_bucket_line = " ".join(EXPECTED_BUCKET_IDS)
    body_phase_line = " ".join(f"phase {ph}" for ph in phases)
    toc = (
        "# Table of Contents\n"
        "- B07 confirmation lane (toc-only control)\n"
        "- B03 research lane\n"
        "- Phase 16 closed loop\n"
        "\n"
    )
    body_full = (
        "# Body\n"
        f"Lanes in use: {body_bucket_line}.\n"
        f"Phases in use: {body_phase_line}.\n"
        "IMP-0001 and TST-0001 appear as used identifiers.\n"
    )
    body_stripped = body_full.replace("B07 ", "").replace(" B07", "")

    with tempfile.TemporaryDirectory(prefix="syn0032-p2-") as tmp:
        receipts = Path(tmp) / "receipts"
        receipts.mkdir()
        for pref in prefix_map:
            stem = f"{pref}-0001"
            (receipts / f"{stem}.json").write_text(
                receipt_body(stem), encoding="utf-8"
            )

        full = compute_coverage(
            REPO,
            receipts_dir=receipts,
            synthesis_docs=[("fixture/full.md", toc + body_full)],
        )
        full_b = by_id(full["bucket_table"])
        print(
            "full_B07",
            full_b["B07"]["verdict"],
            "mentions",
            full_b["B07"]["synthesis_mention_count"],
        )
        if full_b["B07"]["verdict"] != "REPRESENTED":
            print("FAILED:SYN-0032-probe2 expected B07 REPRESENTED on full body")
            return 1
        missing = [
            r["id"] for r in full["bucket_table"] if r["verdict"] != "REPRESENTED"
        ]
        if missing:
            print(f"FAILED:SYN-0032-probe2 full body left buckets unrepresented {missing}")
            return 1

        planted = compute_coverage(
            REPO,
            receipts_dir=receipts,
            synthesis_docs=[("fixture/stripped.md", toc + body_stripped)],
        )
        planted_b = by_id(planted["bucket_table"])
        print(
            "planted_B07",
            planted_b["B07"]["verdict"],
            "mentions",
            planted_b["B07"]["synthesis_mention_count"],
            "receipts",
            planted_b["B07"]["receipt_count"],
        )
        if planted_b["B07"]["verdict"] != "RECEIPTS-ONLY":
            print("FAILED:SYN-0032-probe2 stripped B07 was not RECEIPTS-ONLY")
            return 1
        if planted_b["B07"]["synthesis_mention_count"] != 0:
            print("FAILED:SYN-0032-probe2 TOC B07 was counted as a use")
            return 1
        if planted_b["B01"]["verdict"] != "REPRESENTED":
            print("FAILED:SYN-0032-probe2 sibling B01 lost representation")
            return 1

        json_doc = json.dumps(
            {
                "toc": ["B07 appears only here", "phase 16"],
                "body": "B01 is used. phase 4 is used.",
            }
        )
        json_cov = compute_coverage(
            REPO,
            receipts_dir=receipts,
            synthesis_docs=[("fixture/toc.json", json_doc)],
        )
        json_b = by_id(json_cov["bucket_table"])
        if json_b["B07"]["synthesis_mention_count"] != 0:
            print("FAILED:SYN-0032-probe2 JSON toc key counted as use")
            return 1
        if json_b["B01"]["synthesis_mention_count"] < 1:
            print("FAILED:SYN-0032-probe2 JSON body B01 not counted")
            return 1

    print("SUCCESS:SYN-0032-probe2 planted absence and TOC ignore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
