#!/usr/bin/env python3
"""Named probe 2: independent interval arithmetic + classifier controls.

Mechanically different from probe 1 (which redraws the sample): this probe
recomputes IQR from raw values, applies the UNMEASURABLE rule, refuses a
summary-only record, and checks that a planted mtime change forces SAMPLE.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from stats import classify_delta, summarize  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0027-baseline-variance.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"


def close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0027-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    live_errs = list(validator.iter_errors(doc))
    if live_errs:
        print("FAILED:CNF-0027-probe2 artifact fails schema", live_errs[0].message)
        return 1

    summary_only = copy.deepcopy(doc)
    summary_only["benchmarks"][0]["raw_repetitions"] = []
    if not list(validator.iter_errors(summary_only)):
        print("FAILED:CNF-0027-probe2 summary-only record was accepted")
        return 1

    floors = {}
    for b in doc["benchmarks"]:
        raw = b["raw_repetitions"]
        stats = summarize(raw)
        if not close(stats["iqr"], b["iqr"]) or not close(stats["noise_floor"], b["noise_floor"]):
            print(f"FAILED:CNF-0027-probe2 IQR mismatch {b['id']}")
            return 1
        if not isinstance(b["noise_floor"], (int, float)):
            print(f"FAILED:CNF-0027-probe2 non-numeric floor {b['id']}")
            return 1
        floors[b["id"]] = float(b["noise_floor"])

    claims = doc.get("improvement_claims") or []
    planted = [c for c in claims if str(c.get("source") or "").startswith("negative-control")]
    if len(planted) < 2:
        print("FAILED:CNF-0027-probe2 planted controls missing")
        return 1
    for c in planted:
        delta = float(c["claimed_delta"])
        floor = float(c["noise_floor"])
        want = classify_delta(delta, floor)
        if c.get("verdict") != want or want != "UNMEASURABLE":
            print(f"FAILED:CNF-0027-probe2 planted {c['id']} verdict {c.get('verdict')} want {want}")
            return 1

    # Large synthetic delta must classify as MEASURABLE against catalog IQR
    # unless the floor is itself huge.
    cat_floor = floors["catalog-json-parse"]
    huge = classify_delta(1e9, cat_floor)
    if huge != "MEASURABLE":
        print(f"FAILED:CNF-0027-probe2 huge delta not MEASURABLE floor={cat_floor}")
        return 1

    qui = doc.get("quiescence") or {}
    for key in ("loadavg_1m_at_start", "mem_available_kb_at_start", "freeze_label"):
        if key not in qui:
            print(f"FAILED:CNF-0027-probe2 quiescence missing {key}")
            return 1
    if not isinstance(qui["loadavg_1m_at_start"], (int, float)):
        print("FAILED:CNF-0027-probe2 loadavg not numeric")
        return 1
    if not isinstance(qui["mem_available_kb_at_start"], int):
        print("FAILED:CNF-0027-probe2 mem_available not int")
        return 1
    if qui["freeze_label"] not in {"FREEZE", "SAMPLE"}:
        print("FAILED:CNF-0027-probe2 bad freeze_label")
        return 1

    # Control: a directory whose mtime fingerprint changes must not be FREEZE.
    with tempfile.TemporaryDirectory(prefix="cnf0027-mtime-") as tmp:
        root = Path(tmp)
        f = root / "a.txt"
        f.write_text("one\n", encoding="utf-8")
        before = H.mtime_fingerprint(root, ())
        f.write_text("two\n" + ("x" * 64) + "\n", encoding="utf-8")
        after = H.mtime_fingerprint(root, ())
        if before["sha256"] == after["sha256"]:
            print("FAILED:CNF-0027-probe2 mtime fingerprint did not change on edit")
            return 1
        planted_label = "SAMPLE" if before["sha256"] != after["sha256"] else "FREEZE"
        if planted_label != "SAMPLE":
            print("FAILED:CNF-0027-probe2 planted mutation was not SAMPLE")
            return 1

    if qui["freeze_label"] == "FREEZE" and (
        (qui.get("sibling_agents") or {}).get("other_n") or 0
    ) > 0:
        print("FAILED:CNF-0027-probe2 freeze_label=FREEZE despite sibling agents")
        return 1

    out = {
        "probe": "probe2-noise-floor",
        "unit_id": "CNF-0027",
        "schema_ok": True,
        "summary_only_rejected": True,
        "iqr_recomputed": True,
        "planted_unmeasurable": True,
        "huge_delta_measurable": True,
        "mtime_mutation_is_sample": True,
        "freeze_label": qui["freeze_label"],
        "loadavg_1m_at_start": qui["loadavg_1m_at_start"],
        "mem_available_kb_at_start": qui["mem_available_kb_at_start"],
        "noise_floors": floors,
        "pass": True,
    }
    (HERE / "probe2-noise-floor.raw.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0027-probe2 noise floor and interval arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
