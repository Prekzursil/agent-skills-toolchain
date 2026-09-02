#!/usr/bin/env python3
"""Probe 1: two extractors agree, or disagreement is resolved from the document.

Also quotes the first and last live work-unit ids from the catalog text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

OUT = REPO / X.OUT_REL
SCHEMA = REPO / X.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0031-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact absent")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    unit = X.catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    if sentinel not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != X.UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    errs = X.schema_errors(doc, REPO)
    if errs:
        return fail("schema " + errs[0])

    live = X.measure_live(REPO)
    domain = X.domain_from_artifact(doc)
    if domain.get("kind") != "floor-recount":
        return fail(f"report.kind {domain.get('kind')}")
    if not domain["floors"]:
        return fail("floors absent from report")
    art_floors = {row["id"]: row for row in domain["floors"]}
    live_floors = live["by_id"]
    if set(art_floors) != set(live_floors):
        return fail(
            f"floor-id mismatch art={sorted(art_floors)} live={sorted(live_floors)}"
        )

    for fid, live_row in live_floors.items():
        art = art_floors[fid]
        if art.get("this_count") != live_row["this_count"]:
            return fail(
                f"{fid} this_count art={art.get('this_count')} "
                f"live={live_row['this_count']}"
            )
        if art.get("json_count") != live_row["json_count"]:
            return fail(f"{fid} json_count drift")
        if art.get("regex_count") != live_row["regex_count"]:
            return fail(f"{fid} regex_count drift")
        if art.get("extractor_verdict") != live_row["extractor_verdict"]:
            return fail(f"{fid} extractor_verdict drift")
        if art.get("extractor_verdict") not in {"AGREE", "DISAGREE"}:
            return fail(f"{fid} extractor_verdict {art.get('extractor_verdict')}")
        if art.get("vs_prior") not in {"AGREE", "DISAGREE"}:
            return fail(f"{fid} vs_prior {art.get('vs_prior')}")
        if live_row["extractor_verdict"] == "DISAGREE":
            if "resolved" not in str(art.get("resolution") or "").lower():
                return fail(f"{fid} DISAGREE without resolution from the document")
        if live_row["vs_prior"] == "DISAGREE":
            if "disagree" not in str(art.get("resolution") or "").lower():
                return fail(f"{fid} vs_prior DISAGREE without resolution text")
        if art.get("first_three_ids") != live_row["first_three_ids"]:
            return fail(f"{fid} first_three_ids drift")
        if art.get("last_three_ids") != live_row["last_three_ids"]:
            return fail(f"{fid} last_three_ids drift")
        print(
            f"{fid} this={live_row['this_count']} json={live_row['json_count']} "
            f"regex={live_row['regex_count']} verdict={live_row['extractor_verdict']} "
            f"vs_prior={live_row['vs_prior']} floor_met={live_row['floor_met']}"
        )

    if X.brace_scanner_calls_json_loads():
        return fail("brace_array_ids source contains json.loads")

    wu = live_floors["work_units"]
    catalog_text = (REPO / X.CATALOG_REL).read_text(encoding="utf-8")
    if wu["this_count"] < 2:
        return fail("work_units this_count too small for known-present control")
    first_id = wu["first_three_ids"][0]
    last_id = wu["last_three_ids"][-1]
    if f'"{first_id}"' not in catalog_text:
        return fail(f"first id {first_id} not quoted from catalog")
    if f'"{last_id}"' not in catalog_text:
        return fail(f"last id {last_id} not quoted from catalog")
    quotes = domain["known_present_quotes"]
    quoted_ids = {q.get("id") for q in quotes if q.get("quoted")}
    if first_id not in quoted_ids or last_id not in quoted_ids:
        return fail(f"artifact quotes missing first/last {first_id} {last_id}")
    print(f"known-present first={first_id} last={last_id} quoted_from_catalog=True")

    good = HERE / "fixtures/corpus-good"
    for name, keys, expect in (
        ("07-OPTION-UNIVERSE.json", ["options", "cards"], 5),
        ("08-WORKFLOW-ARCHAEOLOGY.json", ["candidates", "workflows"], 5),
        ("09-WORKFLOW-BLUEPRINT-LIBRARY.json", ["blueprints"], 5),
        ("12-COUNCIL-PROTOCOLS-AND-PRESETS.json", ["protocols"], 4),
        ("12-COUNCIL-PROTOCOLS-AND-PRESETS.json", ["presets"], 4),
    ):
        path = good / name
        a = X.json_array_ids(path, keys)
        b = X.brace_array_ids(path.read_text(encoding="utf-8"), keys)
        if a != b:
            return fail(f"fixture {name} keys={keys} extractors disagree {a} vs {b}")
        if len(a) != expect:
            return fail(f"fixture {name} keys={keys} n={len(a)} want={expect}")
        print(f"fixture-agree {name} {keys[0]} n={len(a)}")

    plant_json = (
        HERE / "fixtures/planted-disagreement/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    )
    plant_md = (
        HERE / "fixtures/planted-disagreement/12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
    )
    measured = X.recount_sources(plant_json, plant_md, ["protocols"], "Protocol")
    if measured["json_ids"] != ["PROT-001", "PROT-002", "PROT-003"]:
        return fail(f"planted json protocols {measured['json_ids']}")
    if measured["md_ids"] != ["PROT-001", "PROT-002"]:
        return fail(f"planted md protocols {measured['md_ids']}")
    if "PROT-003" not in measured["json_md_symmetric_difference"]:
        return fail(
            f"planted JSON↔MD delta {measured['json_md_symmetric_difference']}"
        )
    print(
        "planted-disagreement json=3 md=2 resolved_from_json="
        + ",".join(measured["json_ids"])
    )

    hits = live["locator"]["hits"]
    absent_map = {
        "workflow_candidates": "08",
        "blueprints": "09",
        "council_protocols": "12",
        "presets": "12",
        "platform_options": "07",
    }
    for fid, corpus in absent_map.items():
        art = art_floors[fid]
        present = hits[corpus]["json_present"] or hits[corpus]["md_present"]
        if (
            not present
            and art["this_count"] == art["prior_count"]
            and art["this_count"] > 0
        ):
            return fail(f"{fid} restated Prompt One count with corpus absent")

    print("SUCCESS:SYN-0031-probe1 two-extractors and known-present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
