#!/usr/bin/env python3
"""Probe 2: independent reviewer recount from fixture bytes.

Does not trust the detector's boolean. Rebuilds the yield curve from the
JSON search logs, applies the published fire rule, and blocks on any
disagreement in the numbers. Also checks the catalog artifact quotes the
spec expression and carries SUCCESS:CNL-0082.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import SPEC_EXPR  # noqa: E402
from load_fixtures import NAMES, load  # noqa: E402
from saturation import detect  # noqa: E402

ARTIFACT = (
    "command-center/design/council/"
    "CNL-0082-executable-stopping-example-evidence-saturation-true-or-ti.schema.json"
)

# Published fire rule (copied, not imported) — disagreement with detect() fails.
STREAK_K = 3
YIELD_FLOOR = 0
MIN_QUERIES = 6
MIN_INDEPENDENT = 1


def recount(fixture: dict) -> dict:
    mechs = {r["source_id"]: r["mechanism_id"] for r in fixture["corpus_sources"]}
    gt = len(set(mechs.values()))
    seen: set[str] = set()
    zero_families: list[str] = []
    fire_idx = None
    last_sat = False
    last_reason = "empty_log"
    curve = []
    source_ids: set[str] = set()
    queries = list(fixture["queries"])
    for i, q in enumerate(queries):
        family = q["query_family"]
        retrieved = list(q.get("retrieved_source_ids") or [])
        new = 0
        for sid in retrieved:
            source_ids.add(sid)
            m = mechs[sid]
            if m not in seen:
                seen.add(m)
                new += 1
        if new <= YIELD_FLOOR:
            zero_families.append(family)
        else:
            zero_families = []
        sat = False
        fatigue = False
        if (
            i + 1 >= MIN_QUERIES
            and len(seen) >= MIN_INDEPENDENT
            and len(zero_families) >= STREAK_K
        ):
            window = zero_families[-STREAK_K:]
            if len(set(window)) == STREAK_K:
                sat = True
            else:
                fatigue = True
        elif len(zero_families) >= STREAK_K and len(set(zero_families[-STREAK_K:])) < STREAK_K:
            fatigue = True
        if sat and fire_idx is None:
            fire_idx = i
        last_sat = sat
        if sat:
            last_reason = "saturated"
        elif fatigue:
            last_reason = "search_fatigue"
        elif new > YIELD_FLOOR:
            last_reason = "still_yielding"
        else:
            last_reason = last_reason if last_reason != "empty_log" else "still_yielding"
        curve.append(
            {
                "i": i,
                "new_independent": new,
                "cumulative_independent": len(seen),
                "query_family": family,
                "saturated_this_tick": sat,
            }
        )
    return {
        "evidence_saturation": last_sat,
        "reason": last_reason,
        "independent_mechanisms_found": len(seen),
        "ground_truth_independent_count": gt,
        "fire_after_query_index": fire_idx,
        "source_ids_seen": len(source_ids),
        "missed_independent_if_stop_here": max(0, gt - len(seen)),
        "yield_curve": curve,
    }


def main() -> int:
    art_path = REPO / ARTIFACT
    if not art_path.is_file():
        print("FAILED:CNL-0082-probe2 artifact missing", ARTIFACT)
        return 1
    text = art_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNL-0082" not in text:
        print("FAILED:CNL-0082-probe2 sentinel-absent")
        return 1
    if SPEC_EXPR not in text:
        print("FAILED:CNL-0082-probe2 spec expression not quoted")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0082-probe2 self-declared", doc.get("state"))
        return 1
    if doc.get("expression_verbatim") != SPEC_EXPR:
        print("FAILED:CNL-0082-probe2 expression_verbatim mismatch")
        return 1

    disagreements: list[str] = []
    table = []
    for name in NAMES:
        fx = load(name)
        author = detect(fx)
        review = recount(fx)
        keys = (
            "evidence_saturation",
            "reason",
            "independent_mechanisms_found",
            "ground_truth_independent_count",
            "fire_after_query_index",
            "source_ids_seen",
            "missed_independent_if_stop_here",
        )
        for k in keys:
            if author[k] != review[k]:
                disagreements.append(f"{name}:{k} author={author[k]!r} review={review[k]!r}")
        if len(author["yield_curve"]) != len(review["yield_curve"]):
            disagreements.append(f"{name}:curve-len")
        else:
            for a, b in zip(author["yield_curve"], review["yield_curve"]):
                if a["new_independent"] != b["new_independent"]:
                    disagreements.append(f"{name}:q{a['i']}:new")
                if a["cumulative_independent"] != b["cumulative_independent"]:
                    disagreements.append(f"{name}:q{a['i']}:cum")
        if author["evidence_saturation"] != fx["expected_saturation"]:
            disagreements.append(f"{name}:expected_saturation")
        table.append(
            {
                "fixture": name,
                "author_fire": author["evidence_saturation"],
                "review_fire": review["evidence_saturation"],
                "found": review["independent_mechanisms_found"],
                "gt": review["ground_truth_independent_count"],
                "fire_idx": review["fire_after_query_index"],
                "reason": review["reason"],
            }
        )

    if disagreements:
        print("FAILED:CNL-0082-probe2 recount disagreement", disagreements)
        return 1

    cited = doc.get("both_states") or {}
    sat_row = cited.get("saturated-12") or {}
    if sat_row.get("fire_after_query_index") != table[0]["fire_idx"]:
        print("FAILED:CNL-0082-probe2 artifact fire index != recount", sat_row, table[0])
        return 1
    if sat_row.get("independent_mechanisms_found") != 12:
        print("FAILED:CNL-0082-probe2 artifact saturated found", sat_row)
        return 1

    raw = {"disagreements": [], "table": table, "pass": True}
    (HERE / "probe2-reviewer-recount.raw.json").write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(table, sort_keys=True))
    print("negative_control: unsaturated-12 and fatigue-repeat-queries stay SILENT")
    print("SUCCESS:CNL-0082-probe2 independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
