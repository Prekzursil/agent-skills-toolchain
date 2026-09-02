#!/usr/bin/env python3
"""Named probe 1: re-draw the stratified sample from the recorded seed.

Signal: the plant list, clean list, ARM-2 ids, and canonical item hashes
must be byte-identical to the artifact. A different seed must diverge.
Schema must reject garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibration import SEED, draw_sample  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0129-refuter-calibration.json"
SCHEMA = REPO / "command-center/schema/calibration-report.schema.json"
UNIT = "ADV-0129"
GARBAGE = ({}, {"unit_id": "ADV-0129", "passing_tests": 12}, {"state": "SUCCESS"})


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:ADV-0129" not in blob:
        return fail("sentinel absent")
    if doc.get("report_kind") != "calibration-report":
        return fail("report_kind")
    arms = {a.get("id") for a in (doc.get("arms") or [])}
    if "arm1-recall" not in arms or "arm2-polarity" not in arms:
        return fail("both arms required", sorted(arms))

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)
    errors = list(validator.iter_errors(doc))
    if errors:
        return fail("artifact fails schema", errors[0].message)

    recorded = doc.get("sample") or {}
    seed = recorded.get("seed")
    if seed != SEED:
        return fail(f"seed mismatch recorded={seed} substrate={SEED}")
    live = draw_sample(seed)
    if live["fingerprint"] != recorded.get("fingerprint"):
        return fail(
            "sample fingerprint mismatch",
            {"live": live["fingerprint"], "recorded": recorded.get("fingerprint")},
        )
    if live["payload"] != recorded.get("payload"):
        return fail("sample payload not byte-identical")
    if live["known_detected_item_id"] != recorded.get("known_detected_item_id"):
        return fail("known-detected item id mismatch")
    kd = recorded.get("known_detected_item_id")
    stream_ids = [row["id"] for row in live["payload"]["stream"]]
    if kd not in stream_ids:
        return fail("known-detected item not in stream")
    plants = [row for row in live["payload"]["stream"] if row["kind"] == "plant"]
    if len(plants) < 24:
        return fail(f"ARM-1 plants {len(plants)} < 24")
    sevs = {p["severity"] for p in plants}
    if sevs != {"P0", "P1", "P2"}:
        return fail("not stratified P0/P1/P2", sorted(sevs))
    if len(live["payload"]["arm2"]) < 24:
        return fail("ARM-2 < 24")

    other = draw_sample(seed + 1)
    if other["fingerprint"] == live["fingerprint"]:
        return fail("different seed produced identical sample")

    out = {
        "probe": "probe1-redraw-sample",
        "unit_id": UNIT,
        "pass": True,
        "seed": seed,
        "fingerprint": live["fingerprint"],
        "n_plants": len(plants),
        "n_cleans": sum(1 for r in live["payload"]["stream"] if r["kind"] == "clean"),
        "n_arm2": len(live["payload"]["arm2"]),
        "known_detected_item_id": kd,
        "stratified": sorted(sevs),
        "different_seed_diverges": True,
        "schema_rejects_garbage": True,
    }
    (HERE / "probe1-redraw-sample.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ADV-0129-probe1 redraw sample byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
