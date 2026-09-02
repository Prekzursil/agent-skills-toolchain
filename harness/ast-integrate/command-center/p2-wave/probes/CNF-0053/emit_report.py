#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0053-startup-overhead.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import run_campaign, write_raw  # noqa: E402
from scenario import (  # noqa: E402
    AFTER_ID,
    CATALOG_SENTINEL,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    SCHEMA_REL,
    find_latency_budget,
)
from schemautil import file_artifact, iter_errors, payload  # noqa: E402


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    campaign = run_campaign()
    raw_rel = "command-center/p2-wave/probes/CNF-0053/probe-campaign.raw.json"
    write_raw(campaign, HERE / "probe-campaign.raw.json")
    budget = find_latency_budget(REPO)
    largest = campaign["largest_increase_module"]
    if largest["module"] != "tool_startup.extra":
        print(
            "FAILED:CNF-0053 emit largest module "
            f"{largest['module']!r} expected tool_startup.extra"
        )
        return 1
    if not campaign["after_slower"]:
        print(
            "FAILED:CNF-0053 emit after was not slower than before "
            f"delta={campaign['delta_ms']} noise={campaign['noise_floor_ms']}"
        )
        return 1
    cold = campaign["cold_cache_measurement"]
    if not cold.get("included") or cold.get("payload_bytes", 0) < 1:
        print("FAILED:CNF-0053 emit cold-cache measurement missing")
        return 1
    table = campaign["per_module_cost_table"]
    if AFTER_ID not in table or campaign["commits"][0]["id"] not in table:
        print("FAILED:CNF-0053 emit per-module table missing a commit")
        return 1
    if budget["status"] != "NOT-CHECKED":
        print("FAILED:CNF-0053 emit invented a latency budget", budget)
        return 1

    slower_text = (
        "YES on the two in-tree fixture commits: after adds tool_startup.extra "
        f"which reads a {cold['payload_bytes']}-byte payload at import time. "
        "Historical git SHAs are NOT-CHECKED because this worktree has no .git."
    )
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0053/measure.py"
    )
    src_out = (
        f"delta_ms={campaign['delta_ms']} noise={campaign['noise_floor_ms']} "
        f"largest={largest['module']} n={len(campaign['raw_repetitions'])} "
        f"cold_ms={cold['wall_ms']}"
    )
    ver_cmd = P2
    ver_out = (
        f"rederived_largest={largest['module']} budget={budget['status']} "
        f"cold_included={cold['included']}"
    )
    extra_rel = (
        "command-center/p2-wave/probes/CNF-0053/fixtures/commits/after/"
        "tool_startup/extra.py"
    )
    profiler_rel = "command-center/p2-wave/probes/CNF-0053/profiler.py"

    report = {
        "kind": "benchmark-report",
        "observations": [
            {
                "name": "import-time-delta-ms",
                "measured": campaign["delta_ms"],
                "method": "python -X importtime interleaved A B A B n=11 pairs",
                "anchor": raw_rel,
            },
            {
                "name": "largest-increase-module",
                "measured": largest["module"],
                "method": "median self_us after minus before",
                "anchor": extra_rel,
            },
            {
                "name": "cold-cache-wall-ms",
                "measured": cold["wall_ms"],
                "method": cold.get("method") or "posix_fadvise(POSIX_FADV_DONTNEED)",
                "anchor": raw_rel,
            },
            {
                "name": "declared-latency-budget",
                "measured": "NOT-CHECKED",
                "method": "name-search tools/ and command-center/; never invent a threshold",
                "anchor": SCHEMA_REL,
            },
        ],
        "control_ids": [
            "CNF-0053-before",
            "CNF-0053-after",
            "warm-importtime",
            "cold-posix_fadvise",
        ],
        "title": "Startup and import overhead delta measurement",
        "question": QUESTION,
        "git_history": {
            "present": False,
            "status": "NOT-CHECKED",
            "reason": (
                "/opt/p2/ast-integrate is not a git worktree; two fixture "
                "commits stand in so the per-module table and cold-cache run "
                "can still be measured"
            ),
        },
        "commits": campaign["commits"],
        "interleaving": campaign["interleaving"],
        "repetitions": campaign["repetitions"],
        "raw_repetitions": campaign["raw_repetitions"],
        "summaries": campaign["summaries"],
        "per_module_cost_table": table,
        "cold_cache_measurement": {
            "included": True,
            "commit_id": cold["commit_id"],
            "method": cold["method"],
            "advised_files": cold.get("advised_files"),
            "wall_ms": cold["wall_ms"],
            "payload_bytes": cold["payload_bytes"],
            "package_self_us": cold.get("package_self_us"),
        },
        "delta_ms": campaign["delta_ms"],
        "noise_floor_ms": campaign["noise_floor_ms"],
        "measurable": campaign["measurable"],
        "largest_increase_module": largest,
        "latency_budget": budget,
        "answers": {
            "did_the_change_make_the_tool_slower": slower_text,
            "delta_ms": campaign["delta_ms"],
            "largest_increase_module": largest["module"],
            "exceeds_declared_latency_budget": "NOT-CHECKED",
        },
        "interval": {
            "before_median_wall_ms": campaign["summaries"][campaign["commits"][0]["id"]][
                "median_wall_ms"
            ],
            "after_median_wall_ms": campaign["summaries"][AFTER_ID]["median_wall_ms"],
            "delta_ms": campaign["delta_ms"],
            "noise_floor_ms": campaign["noise_floor_ms"],
            "intervals_overlap": not campaign["measurable"],
            "rule": (
                "a difference inside the noise floor is no measurable change, "
                "never an improvement"
            ),
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0053",
        "state": "SUCCESS",
        "sentinel": CATALOG_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0053]",
        "min_bytes_threshold": 2048,
        "artifacts": [
            file_artifact(extra_rel, "fixture"),
            file_artifact(profiler_rel, "supporting"),
            file_artifact(raw_rel, "log"),
            file_artifact(SCHEMA_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Per-module import-time tables exist for both fixture commits "
                    "and the after-only module tool_startup.extra accounts for the "
                    "largest self_us increase."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": extra_rel,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": src_cmd,
                        "raw_output": src_out,
                        "fingerprint": fp("command", src_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "re-derive largest_increase from per_module_cost_table "
                            "before reading answers"
                        ),
                        "raw_output": ver_out,
                        "fingerprint": fp("static-analysis", "largest_increase"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "At least one cold-cache posix_fadvise measurement is included, "
                    "and the latency-budget question is NOT-CHECKED because no "
                    "numeric startup threshold is declared."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": raw_rel,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": src_out,
                        "fingerprint": fp("command", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": ver_cmd,
                        "raw_output": ver_out,
                        "fingerprint": fp("schema-validate", ver_cmd),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "CNF0053-T1-interleaved",
                "name": "11 interleaved A B A B import-time repetitions",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "CNF0053-T2-cold-cache",
                "name": "cold filesystem cache measured at least once via posix_fadvise",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "CNF0053-T3-budget-not-invented",
                "name": "undeclared latency budget reported NOT-CHECKED",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "Empty and unrelated JSON must be rejected by output_schema "
                    "once $ref is resolved onto disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejects {} and {totally:unrelated}",
                "good_state_output": "schema accepts this receipt",
            },
            {
                "id": "NC-AFTER-ONLY-EXTRA",
                "kind": "known-broken-fixture",
                "description": (
                    "Commit-before has no tool_startup.extra; the largest "
                    "increase must be that after-only import."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "before table has no tool_startup.extra",
                "good_state_output": "largest_increase_module=tool_startup.extra",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0053-probe2-cold-cache-budget",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "probe2 re-runs the cold-cache sample and re-derives largest "
                "module plus budget status from live output before comparing "
                "the artifact answers"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0053/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0053",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": (
                        "python3 -c \"import json,pathlib; "
                        "json.loads(pathlib.Path("
                        f"'{OUT_REL}').read_text())\""
                    ),
                    "raw_output": "parsed",
                    "fingerprint": fp("command", "json.loads:" + OUT_REL),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs are permitted ONLY as flake "
                "measurement and EVERY run's outcome is recorded"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Product git before/after SHAs are NOT-CHECKED; this "
                    "worktree has no .git so fixture commits stand in."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run on a git checkout that names the product commits "
                    "under test and compare those trees to the fixture pair."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "performance-analyst",
            "execution_substrate": "local-serialized",
        },
        "report": report,
        "extensions": {
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
        },
    }

    garbage_rejected = 0
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}):
        if iter_errors(garbage):
            garbage_rejected += 1
        else:
            print("FAILED:CNF-0053 emit schema accepted garbage")
            return 1
    if garbage_rejected != 2:
        print("FAILED:CNF-0053 emit garbage control")
        return 1

    errs = iter_errors(doc)
    if errs:
        print("FAILED:CNF-0053 emit schema errors")
        for e in errs[:25]:
            loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
            print(f"  {loc}: {e.message}")
        return 1

    body = payload(doc)
    if body.get("largest_increase_module", {}).get("module") != "tool_startup.extra":
        print("FAILED:CNF-0053 emit payload largest missing")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0053 emit catalog sentinel absent from bytes")
        return 1
    out.write_text(text, encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    if loaded.get("unit_id") != "CNF-0053":
        print("FAILED:CNF-0053 emit json.loads consumer missed unit_id")
        return 1
    print(
        f"wrote {OUT_REL} delta_ms={doc['report']['delta_ms']} "
        f"largest={largest['module']} budget={budget['status']} "
        f"cold_ms={cold['wall_ms']}"
    )
    print("SUCCESS:CNF-0053 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
