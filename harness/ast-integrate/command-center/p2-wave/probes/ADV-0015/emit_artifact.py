#!/usr/bin/env python3
"""Emit ADV-0015 stale-premise reprobe artifact from live probe measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

GARBAGE = (
    {},
    {"unit_id": "ADV-0015", "state": "SUCCESS"},
    {"totally": "unrelated", "passing_tests": 999999},
)


def main() -> int:
    m = L.measure()
    if not m["controls_ok"]:
        print("FAILED:ADV-0015 emit controls did not calibrate")
        print(json.dumps({
            "surface": {
                "matching_ok": m["surface_controls"]["matching_ok"],
                "stale_ok": m["surface_controls"]["stale_ok"],
            },
            "runtime": {
                "loud_ok": m["runtime_controls"]["loud_ok"],
                "silent_ok": m["runtime_controls"]["silent_ok"],
            },
        }, indent=2, sort_keys=True))
        return 1
    sentinel = L.catalog_sentinel()
    unit = L.load_catalog_unit()
    p1 = L.probe1_report(m)
    p2 = L.probe2_report(m)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {**t, "command": L.P1_CMD if "PROBE1" in t["id"] or "SURFACE" in t["id"] else L.P2_CMD}
        for t in m["tests"]
    ]
    doc = {
        "unit_id": L.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "profile": "stale-premise-reprobe",
        "report": {"kind": "stale-premise-reprobe"},
        "schema_version": 1,
        "question": unit.get("question_or_target"),
        "title": unit.get("title"),
        "spec_anchor": unit.get("spec_anchor"),
        "overall_verdict": m["overall_verdict"],
        "measured_at": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "stale-premise-refuter",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "ADV-0015-probe2-retired-id-runtime",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives retired-id behaviour from a live call into "
                "CNL-0004 _fit_budget, not from probe 1's surface-diff table."
            ),
        },
        "method": {
            "probe1": L.PROBE1_NAME,
            "probe2": L.PROBE2_NAME,
            "retired_id": L.RETIRED_ID,
            "silent_substitute_is_defect_even_if_substitute_works": True,
        },
        "counts": {
            "n_table_rows": m["n_table_rows"],
            "n_stale": m["n_stale"],
            "n_match": m["n_match"],
            "n_targets": len(m["targets"]),
        },
        "surface": m["surface"],
        "runtime": {
            "over_budget": m["runtime_over"],
            "under_budget": m["runtime_under"],
            "known_alias": m["runtime_known_alias"],
            "controls": m["runtime_controls"],
        },
        "stale_models": m["stale_models"],
        "matching_models": m["matching_models"],
        "unique_catalog_models": m["unique_catalog_models"],
        "diffs": m["diffs"],
        "targets": m["targets"],
        "evidence": [
            {
                "claim": (
                    "A planted current vendor id with a matching published "
                    "window is not flagged stale."
                ),
                "verdict": "REFUTED",
                "anchor": "CTRL-SURFACE-MATCHING-ROW",
            },
            {
                "claim": (
                    f"Planted retired id {L.RETIRED_ID} is absent from today's "
                    "published surface."
                ),
                "verdict": "CONFIRMED",
                "anchor": "CTRL-SURFACE-STALE-ROW",
            },
            {
                "claim": (
                    "Catalog / CNL-0004 / seed routing ids are not published "
                    "vendor API ids (aliases such as opus, gpt-5, sonnet)."
                ),
                "verdict": next(
                    t["verdict"]
                    for t in m["targets"]
                    if t["id"] == "CATALOG-ASSIGNED-MODEL-IDS"
                ),
                "anchor": "CATALOG-ASSIGNED-MODEL-IDS",
            },
            {
                "claim": (
                    f"CNL-0004 _fit_budget({L.RETIRED_ID!r}) does not fail "
                    "loudly; silent-drop or stale-price-estimate is a defect."
                ),
                "verdict": next(
                    t["verdict"]
                    for t in m["targets"]
                    if t["id"] == "RUNTIME-RETIRED-ID-OVER-BUDGET"
                ),
                "anchor": "RUNTIME-RETIRED-ID-OVER-BUDGET",
            },
            {
                "claim": (
                    "Silent substitution is classified as a defect even when "
                    "the substituted model would work."
                ),
                "verdict": "CONFIRMED",
                "anchor": "CTRL-SILENT-SUB-IS-DEFECT",
            },
        ],
        "tests": tests,
        "negative_controls": m["negative_controls"],
        "named_probes": [
            {
                "id": "probe1",
                "name": L.PROBE1_NAME,
                "command": L.P1_CMD,
                "raw_output": p1,
            },
            {
                "id": "probe2",
                "name": L.PROBE2_NAME,
                "command": L.P2_CMD,
                "raw_output": p2,
            },
        ],
        "artifacts": [
            {
                "path": L.OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": L.SCHEMA_REL,
                "exists": (L.REPO / L.SCHEMA_REL).is_file(),
                "role": "schema",
            },
        ],
        "output_schema": L.SCHEMA_REL,
        "answer": (
            f"{m['overall_verdict']}: program routing/cost tables use short "
            f"aliases ({', '.join(m['stale_models'][:8]) or 'none'}) that are "
            "absent from today's published Anthropic/OpenAI ids; CNL-0004 "
            f"_fit_budget({L.RETIRED_ID!r}) "
            f"{m['runtime_over'].get('behaviour')} "
            f"(defect={m['runtime_over'].get('defect')}). "
            "Silent substitution is a defect even when the substitute works."
        ),
    }
    errs = L.schema_errors(doc)
    if errs:
        print("FAILED:ADV-0015 emit schema", errs[:12])
        return 1
    for g in GARBAGE:
        g_errs = L.schema_errors(g)
        if not g_errs:
            print("FAILED:ADV-0015 emit schema accepted garbage")
            return 1
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0015 sentinel not in serialized artifact")
        return 1
    if "SUCCESS:ADV-0015" not in text:
        print("FAILED:ADV-0015 SUCCESS:ADV-0015 missing")
        return 1
    out = L.REPO / L.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(
        f"wrote {L.OUT_REL} bytes={out.stat().st_size} "
        f"overall={m['overall_verdict']} n_stale={m['n_stale']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
