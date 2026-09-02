#!/usr/bin/env python3
"""Named probe 1: live pytest --durations, twice, ranking stability.

The in-runner report is the evidence. A missing durations table is not 0.0s.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import profile as P  # noqa: E402

ART = REPO / P.OUT
SCHEMA = REPO / P.SCHEMA


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0056-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "AUD-0056":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if P.COMPLETION not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:AUD-0056-probe1 schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1

    parser = P.parser_control()
    if not parser["pass"]:
        print(json.dumps(parser, indent=2)[:2000])
        return fail("parser control does not discriminate")
    rank_ctl = P.ranking_detector_control()
    if not rank_ctl["pass"]:
        print(json.dumps(rank_ctl, indent=2)[:2000])
        return fail("ranking detector control does not discriminate")

    modules, collect_raw, collect_code = P.collect_modules()
    if not modules:
        print(collect_raw[-2000:])
        return fail(f"no modules collected collect_exit={collect_code}")

    run_a = P.run_durations_suite()
    run_b = P.run_durations_suite()
    if not run_a["pytest_invoked"] or not run_b["pytest_invoked"]:
        return fail("pytest not invoked")
    if not run_a["durations_header_present"] or run_a["row_count"] < 1:
        print(run_a["raw_output"][-2000:])
        return fail("run_a missing --durations table")
    if not run_b["durations_header_present"] or run_b["row_count"] < 1:
        print(run_b["raw_output"][-2000:])
        return fail("run_b missing --durations table")

    union = sorted(set(run_a["by_module"]) | set(run_b["by_module"]) | set(modules))
    vals_a = [float((run_a["by_module"].get(m) or {}).get("call_s") or 0.0) for m in union]
    vals_b = [float((run_b["by_module"].get(m) or {}).get("call_s") or 0.0) for m in union]
    live_rank = P.ranking_stability(union, vals_a, vals_b)
    art_rank = doc.get("ranking") or {}
    art_slowest = str(art_rank.get("slowest_module_durations") or "")
    live_slowest = str(live_rank.get("slowest_run_a") or "")
    if not live_slowest:
        return fail("live slowest missing")
    if art_slowest != live_slowest:
        return fail(f"slowest drifted artifact={art_slowest} live={live_slowest}")

    claimed_stable = bool(art_rank.get("durations_stable"))
    if claimed_stable and not live_rank["stable"]:
        return fail("artifact claimed durations ranking stable; live rerun is not")
    if doc.get("baseline_usable") and not live_rank["stable"]:
        return fail("artifact claimed baseline_usable; live durations ranking unstable")

    named = [p for p in (doc.get("named_probes") or []) if p.get("id") == "probe1"]
    if not named:
        return fail("artifact missing probe1 verbatim")
    raw = str(named[0].get("raw_output") or "")
    if "duration" not in raw.lower() and "slowest" not in raw.lower():
        return fail("probe1 raw_output has no durations report")

    report = {
        "probe": "probe1-durations",
        "unit_id": "AUD-0056",
        "pass": True,
        "collect_n": len(modules),
        "run_a_rows": run_a["row_count"],
        "run_b_rows": run_b["row_count"],
        "run_a_wall_s": run_a["wall_s"],
        "run_b_wall_s": run_b["wall_s"],
        "live_ranking": live_rank,
        "artifact_slowest": art_slowest,
        "parser_control": True,
        "ranking_control": True,
    }
    print(P.format_durations_verbatim(run_a, "RUN-A"))
    print(P.format_durations_verbatim(run_b, "RUN-B"))
    print(json.dumps(report, indent=2, sort_keys=True))
    print("SUCCESS:AUD-0056-probe1 live --durations ranking recorded twice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
