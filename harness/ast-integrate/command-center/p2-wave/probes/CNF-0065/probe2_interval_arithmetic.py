#!/usr/bin/env python3
"""Probe 2: independently recompute Tukey hinges; check required classifications."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0065-external-benchmark-repro.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0065-probe2 {msg}")
    return 1


def reviewer_median(values: list[float]) -> float:
    ys = sorted(float(v) for v in values)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def reviewer_hinges(values: list[float]) -> tuple[float, float, float]:
    ys = sorted(float(v) for v in values)
    n = len(ys)
    med = reviewer_median(ys)
    if n < 2:
        return med, med, med
    if n % 2:
        lower, upper = ys[: n // 2], ys[n // 2 + 1 :]
    else:
        lower, upper = ys[: n // 2], ys[n // 2 :]
    return reviewer_median(lower), med, reviewer_median(upper)


def main() -> int:
    if not OUT.is_file():
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema errors {errs[0].message}")

    floor = doc.get("noise_floor") or {}
    raw = list(floor.get("raw_ms") or [])
    if len(raw) < 11:
        return fail("noise floor under-sampled")
    q1, med, q3 = reviewer_hinges(raw)
    iqr = q3 - q1
    print(f"recomputed q1={q1} median={med} q3={q3} iqr={iqr}")
    if abs(med - float(floor["median_ms"])) > 1e-9:
        return fail("median mismatch")
    if abs(iqr - float(floor["iqr_ms"])) > 1e-9:
        return fail("iqr mismatch")
    if floor.get("cnf0027_present") is True:
        return fail("CNF-0027 is not on this worktree; present=true is a lie")

    claims = doc.get("claims") or []
    cond = [c for c in claims if c.get("verdict") == "CONDITIONALLY-REPRODUCIBLE"]
    if not cond:
        return fail("no CONDITIONALLY-REPRODUCIBLE claim")
    for c in cond:
        inferred = c.get("inferred_conditions") or []
        if not inferred:
            return fail(f"{c['id']} missing inferred conditions")
        notes = c.get("measurement_notes") or {}
        if notes.get("default_matches_cited") is True:
            return fail(f"{c['id']} default encoder already matches; not undisclosed")
        if notes.get("compact_matches_cited") is not True:
            return fail(f"{c['id']} compact encoder does not match cited")
    live_default = H.json_wire_size(compact=False)
    live_compact = H.json_wire_size(compact=True)
    print(f"live json default={live_default} compact={live_compact}")
    if live_compact != 44 or live_default == 44:
        return fail("json undisclosed-conditions control failed on re-measure")

    missing = [
        c
        for c in claims
        if c.get("verdict") == "NOT-REPRODUCIBLE"
        and not (c.get("missing_prerequisite") or "").strip()
    ]
    if missing:
        return fail(f"NOT-REPRODUCIBLE without prerequisite: {[c['id'] for c in missing]}")
    if not any(c.get("verdict") == "NOT-REPRODUCIBLE" for c in claims):
        return fail("NOT-REPRODUCIBLE omitted")

    mutant = json.loads(json.dumps(doc))
    target = next(c for c in mutant["claims"] if c["verdict"] == "NOT-REPRODUCIBLE")
    target["missing_prerequisite"] = ""
    mutant_errs = list(jsonschema.Draft7Validator(schema).iter_errors(mutant))
    if not mutant_errs:
        return fail("schema accepted NOT-REPRODUCIBLE with empty prerequisite")

    print("interval_ok=True conditional_named=True not_reproducible_named=True mutant_red=True")
    print("SUCCESS:CNF-0065-probe2 interval arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
