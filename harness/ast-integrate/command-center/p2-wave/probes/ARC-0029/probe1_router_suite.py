#!/usr/bin/env python3
"""Probe 1: live recall, flooding, fallback, and explanation versus TEST-PLAN.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import run_suite  # noqa: E402

ART = REPO / "command-center/phase3/A4/TEST-PLAN.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0029-probe1 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0029":
        print("FAILED:ARC-0029-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:ARC-0029" not in text:
        print("FAILED:ARC-0029-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ARC-0029-probe1 self-declared", doc.get("state"))
        return 1
    if not doc.get("corpus", {}).get("author_wrote_labels"):
        print("FAILED:ARC-0029-probe1 author-wrote disclosure missing")
        return 1
    held = doc.get("corpus", {}).get("held_out") or {}
    if not held.get("labelled_after_index_freeze") or not held.get("task_ids"):
        print("FAILED:ARC-0029-probe1 held-out slice missing")
        return 1

    report = run_suite()
    if not report["pass"]:
        print("FAILED:ARC-0029-probe1 suite " + ",".join(report["failures"]))
        return 1

    rec = report["recall"]
    rec_h = report["recall_held_out"]
    flood = report["flooding"]
    fb = report["fallback"]
    expl = report["explanation"]
    measured = doc.get("measured") or {}

    if rec["hits"] != measured.get("recall_all", {}).get("hits"):
        print("FAILED:ARC-0029-probe1 recall hits drift", rec["hits"], measured.get("recall_all"))
        return 1
    if rec_h["hits"] != measured.get("recall_held_out", {}).get("hits"):
        print("FAILED:ARC-0029-probe1 held-out drift")
        return 1
    if flood["bounded_tokens"] != measured.get("flooding", {}).get("bounded_tokens"):
        print("FAILED:ARC-0029-probe1 flooding drift")
        return 1
    if not fb["pass"] or not flood["pass"] or not expl["pass"]:
        print("FAILED:ARC-0029-probe1 control flags")
        return 1
    if rec["hits"] != rec["total_gold"]:
        print("FAILED:ARC-0029-probe1 recall not full")
        return 1

    print(
        json.dumps(
            {
                "recall_hits": rec["hits"],
                "recall_total": rec["total_gold"],
                "held_out_hits": rec_h["hits"],
                "held_out_total": rec_h["total_gold"],
                "author_wrote_labels": True,
                "fallback_pass": fb["pass"],
                "flooding_pass": flood["pass"],
                "flooding_bounded_tokens": flood["bounded_tokens"],
                "flooding_ceiling": flood["ceiling"],
                "unbounded_tokens": flood["unbounded_tokens"],
                "explanation_pass": expl["pass"],
                "negative_query_fraction": report["negative_query_fraction"],
            },
            sort_keys=True,
        )
    )
    print(
        f"recall={rec['hits']}/{rec['total_gold']} held={rec_h['hits']}/{rec_h['total_gold']} "
        f"flood={flood['bounded_tokens']}/{flood['ceiling']} unbounded={flood['unbounded_tokens']} "
        f"fallback={fb['pass']} explain={expl['pass']}"
    )
    print("SUCCESS:ARC-0029-probe1 router suite reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
