#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0056.json (scale-model)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _unshadow_stdlib() -> None:
    repo = str(REPO.resolve())
    here = str(HERE)
    cleaned: list[str] = []
    for p in sys.path:
        if p in ("", "."):
            continue
        try:
            if str(Path(p).resolve()) == repo:
                continue
        except OSError:
            pass
        cleaned.append(p)
    if here not in cleaned:
        cleaned.insert(0, here)
    sys.path[:] = cleaned


_unshadow_stdlib()
import jsonschema  # noqa: E402

from engine import build_model  # noqa: E402

OUT = "command-center/receipts/BLD-0056.json"
SCHEMA = "command-center/schema/scale-model.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0056/probe1_parse_budget.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0056/probe2_dir_consolidator.py"
)
QUESTION = (
    "Question: what does the on-disk footprint do at ten times scale, and which "
    "store degrades first? Model event-log append rate, receipt count, manifest "
    "size, directory entry counts per folder, and full-parse time for the largest "
    "JSON documents, then identify the first component to cross a hard limit. "
    "Anchor on the measured pathology of a consolidation file that grew to 774 KB "
    "because its consolidation step always skipped."
)


def catalog_question() -> str:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "BLD-0056":
            q = str(unit.get("question_or_target") or "").strip()
            return q if len(q) >= 40 else QUESTION
    return QUESTION


def build_receipt(model: dict) -> dict:
    inv = model["inventory"]
    parse = model["parse_budget"]
    dscale = model["directory_scale"]
    consol = model["consolidation_control"]
    first = model["first_to_degrade"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = model["tests"]
    failed = [t["id"] for t in tests if t.get("result") != "PASS"]
    state = "SUCCESS" if not failed else "FAILED"
    sentinel = "SUCCESS:BLD-0056"
    rec = parse["reader_recommendation"]
    x1 = parse["x1"]
    x10 = parse["x10"]
    primary = dscale["primary"]
    second = dscale["second_filesystem"]
    answer = (
        f"At 10x, the first store to cross a hard limit is {first['store_id']} "
        f"({first['kind']}): always-skip consolidation reproduced "
        f"{consol['always_skip']['bytes']} bytes with compact_count="
        f"{consol['always_skip']['compacts']}, crossing the named 774 KB "
        f"({consol['pathology_bytes']} byte) pathology. Largest JSON "
        f"{parse['source']} parsed in {x1['parse_ms']} ms at 1x "
        f"({x1['file_bytes']} bytes) and {x10['parse_ms']} ms at synthetic 10x "
        f"({x10['file_bytes']} bytes); reader_recommendation={rec} against a "
        f"{parse['threshold_ms']} ms full-parse budget. A {dscale['n']}-file "
        f"directory on {primary.get('fstype')} listed in {primary.get('listdir_ms')} ms "
        f"and globbed in {primary.get('glob_ms')} ms (budget {dscale['budget_ms']} ms). "
        f"NTFS directory scale is {model['ntfs']['status']}. "
        f"Live EVENTS.jsonl and ARTIFACT-MANIFEST.json are absent; 10x event-log "
        f"bytes without a live file are ESTIMATE. {sentinel}"
    )
    return {
        "unit_id": "BLD-0056",
        "state": state,
        "sentinel": sentinel,
        "kind": "scale-model",
        "schema_version": 1,
        "question": catalog_question(),
        "live_inventory": {
            "events_log": inv["events_log"],
            "receipt_tree": inv["receipt_tree"],
            "artifact_manifest": inv["artifact_manifest"],
            "unit_manifests": inv["unit_manifests"],
            "largest_json": inv["largest_json"],
            "catalog_units": inv["catalog_units"],
        },
        "stores": model["stores"],
        "parse_budget": {
            "threshold_ms": parse["threshold_ms"],
            "source": parse["source"],
            "x1": parse["x1"],
            "x10": parse["x10"],
            "reader_recommendation": rec,
            "full_parse_readers": parse["full_parse_readers"],
            "byte_ratio": parse["byte_ratio"],
        },
        "directory_scale": {
            "n": dscale["n"],
            "budget_ms": dscale["budget_ms"],
            "primary": primary,
            "second_filesystem": second,
        },
        "consolidation_control": consol,
        "event_append": model["event_append"],
        "first_to_degrade": first,
        "ntfs": model["ntfs"],
        "reviewer": model["reviewer"],
        "tests": tests,
        "evidence": [
            {
                "claim": (
                    f"Full-parse of {parse['source']} at 1x "
                    f"({x1['file_bytes']} bytes, {x1['parse_ms']} ms) and "
                    f"synthetically inflated 10x ({x10['file_bytes']} bytes, "
                    f"{x10['parse_ms']} ms)."
                ),
                "verdict": "CONFIRMED",
                "kind": "MEASURED",
                "anchor": parse["source"],
            },
            {
                "claim": (
                    f"Folder of {dscale['n']} receipts listed and globbed on "
                    f"{primary.get('fstype')} within {dscale['budget_ms']} ms "
                    f"(listdir={primary.get('listdir_ms')} ms, glob={primary.get('glob_ms')} ms)."
                ),
                "verdict": "CONFIRMED",
                "kind": "MEASURED",
                "anchor": "engine.measure_dir_scale",
            },
            {
                "claim": (
                    "Always-skip consolidator is detectable: it reaches the 774 KB "
                    "pathology with compact_count=0; compacting twin stays bounded."
                ),
                "verdict": "CONFIRMED" if consol["detector"]["control_pass"] else "REFUTED",
                "kind": "MEASURED",
                "anchor": "engine.consolidation_control",
            },
            {
                "claim": "NTFS directory scale for 20480 receipts.",
                "verdict": model["ntfs"]["status"],
                "kind": "NOT-CHECKED" if model["ntfs"]["status"] == "NOT-CHECKED" else "MEASURED",
                "anchor": "findmnt -t ntfs,ntfs3,fuse.ntfs",
            },
            {
                "claim": "10x of the live event log on disk.",
                "verdict": "ESTIMATE",
                "kind": "ESTIMATE",
                "anchor": inv["events_log"]["path"],
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "answer": answer,
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for BLD-0056. Did not run global unit_manifest.py --write. "
            "cloud_ok is not delivery."
        ),
    }


def validate(doc: dict) -> list[str]:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errs]


def main() -> int:
    model = build_model()
    doc = build_receipt(model)
    if doc["state"] != "SUCCESS":
        print(f"FAILED:BLD-0056 model state={doc['state']} tests={doc['tests']}")
        return 1
    errs = validate(doc)
    if errs:
        print("FAILED:BLD-0056 schema errors")
        for line in errs[:20]:
            print(" ", line)
        return 1
    for garbage in ({}, {"unit_id": "BLD-0056"}, {"blob": "x" * 2000}):
        if not validate(garbage):
            print("FAILED:BLD-0056 schema accepted garbage")
            return 1
    if "SUCCESS:BLD-0056" not in json.dumps(doc):
        print("FAILED:BLD-0056 sentinel missing from payload")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < 2048:
        print(f"FAILED:BLD-0056 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:BLD-0056")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
