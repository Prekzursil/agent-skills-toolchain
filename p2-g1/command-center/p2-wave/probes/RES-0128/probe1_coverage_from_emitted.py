#!/usr/bin/env python3
"""Probe 1: coverage is computed from emitted citation fields.

Control: a class cited by exactly one fixture unit must show unit_count==1.
Negative: planned-but-uncited classes (papers, multilingual) stay at 0.
Spec width: exactly 16 class rows and 12 mode rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from canon import RESEARCH_MODES, SOURCE_CLASSES  # noqa: E402
from coverage import (  # noqa: E402
    control_singleton,
    coverage_from_docs,
    load_emitted_records,
)

CORPUS = HERE / "fixtures" / "corpus"
PLANS = HERE / "fixtures" / "catalog-plans.json"
OUT = HERE / "probe1-coverage-from-emitted.raw.json"


def _load_corpus() -> list[tuple[str, object]]:
    loaded = load_emitted_records(sorted(CORPUS.glob("RES-FX-*.json")))
    docs = []
    for uid, _path, doc, status in loaded:
        if status != "parsed":
            print(f"FAILED:RES-0128-probe1 fixture {uid} {status}")
            raise SystemExit(1)
        docs.append((uid, doc))
    return docs


def main() -> int:
    docs = _load_corpus()
    cov = coverage_from_docs(docs, expected_units=[u for u, _ in docs])

    class_ids = [r["id"] for r in cov["classes"]]
    mode_ids = [r["id"] for r in cov["modes"]]
    by_class = {r["id"]: r for r in cov["classes"]}
    by_mode = {r["id"]: r for r in cov["modes"]}

    ctrl = control_singleton(cov, "public-tor")
    payload = {
        "probe": "probe1-coverage-from-emitted",
        "unit_id": "RES-0128",
        "class_row_count": len(class_ids),
        "mode_row_count": len(mode_ids),
        "public_tor": ctrl,
        "official_docs_count": by_class["official-docs"]["unit_count"],
        "papers_count": by_class["papers"]["unit_count"],
        "multilingual_class_count": by_class["multilingual"]["unit_count"],
        "archival_count": by_class["archival"]["unit_count"],
        "source_code_count": by_class["source-code"]["unit_count"],
        "blogs_count": by_class["blogs"]["unit_count"],
        "deep_research_count": by_mode["deep-research"]["unit_count"],
        "multilingual_mode_count": by_mode["multilingual"]["unit_count"],
        "records_parsed": cov["records_parsed"],
        "pass": False,
    }

    if class_ids != list(SOURCE_CLASSES) or len(class_ids) != 16:
        payload["error"] = f"class table != 16 spec ids: {class_ids}"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 class-table-width")
        return 1
    if mode_ids != list(RESEARCH_MODES) or len(mode_ids) != 12:
        payload["error"] = f"mode table != 12 spec ids: {mode_ids}"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 mode-table-width")
        return 1
    if not ctrl["pass"] or ctrl["unit_ids"] != ["RES-FX-0001"]:
        payload["error"] = f"singleton control failed: {ctrl}"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 singleton-control")
        return 1
    # Two independent units cited official-docs.
    if by_class["official-docs"]["unit_count"] != 2:
        payload["error"] = "official-docs should be cited by exactly two fixture units"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 official-docs-count")
        return 1
    # Plan-only record must not create papers / multilingual / archival coverage.
    if by_class["papers"]["unit_count"] != 0:
        payload["error"] = "papers was planned but never cited; count must be 0"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 planned-papers-counted")
        return 1
    if by_class["multilingual"]["unit_count"] != 0:
        payload["error"] = "multilingual class planned but never cited; count must be 0"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 planned-multilingual-counted")
        return 1
    if by_class["archival"]["unit_count"] != 0:
        payload["error"] = "archival planned only; count must be 0"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 planned-archival-counted")
        return 1
    if by_mode["multilingual"]["unit_count"] != 0:
        payload["error"] = "multilingual mode planned only; count must be 0"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 planned-mode-counted")
        return 1
    if by_class["source-code"]["unit_count"] != 1:
        payload["error"] = "source-code should be cited by exactly one fixture unit"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 source-code-count")
        return 1
    if by_class["blogs"]["unit_count"] != 1:
        payload["error"] = "blogs should be cited by exactly one fixture unit"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 blogs-count")
        return 1

    # Catalog plans file must not be readable as emitted coverage.
    plans = json.loads(PLANS.read_text(encoding="utf-8"))
    plan_cov = coverage_from_docs([("RES-0006", plans)])
    plan_any = sum(r["unit_count"] for r in plan_cov["classes"] + plan_cov["modes"])
    payload["catalog_plan_cited_total"] = plan_any
    if plan_any != 0:
        payload["error"] = "catalog-shaped JSON was counted as citations"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 catalog-plan-counted")
        return 1

    # Per-unit ignore list must have seen the plan fields on FX-0004.
    fx4 = next(r for r in cov["per_unit"] if r["unit_id"] == "RES-FX-0004")
    if not fx4["planned_fields_ignored"]:
        payload["error"] = "FX-0004 plan fields were not observed-and-ignored"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 plan-fields-unseen")
        return 1
    if fx4["classes"] or fx4["modes"]:
        payload["error"] = "FX-0004 plan-only record produced citations"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:RES-0128-probe1 plan-only-cited")
        return 1

    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:RES-0128-probe1 emitted-only coverage; "
        "public-tor count==1; planned papers/multilingual stay 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
