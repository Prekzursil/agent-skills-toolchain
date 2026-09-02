#!/usr/bin/env python3
"""Probe 2: cold-cache re-run, budget NOT-CHECKED, schema, independent re-derive."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import largest_increase, module_median_table  # noqa: E402
from profiler import run_import, stage_commit  # noqa: E402
from scenario import (  # noqa: E402
    AFTER_ID,
    AFTER_SRC,
    BEFORE_SRC,
    CATALOG_SENTINEL,
    OUT_REL,
    REPO,
    find_latency_budget,
)
from schemautil import iter_errors, payload  # noqa: E402

RAW = HERE / "probe2-cold-cache.raw.json"


def load_artifact() -> dict:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        raise FileNotFoundError("artifact missing")
    return json.loads(art.read_text(encoding="utf-8"))


def main() -> int:
    try:
        doc = load_artifact()
    except (OSError, json.JSONDecodeError, FileNotFoundError) as exc:
        print("FAILED:CNF-0053-probe2 artifact", type(exc).__name__)
        return 1
    text = (REPO / OUT_REL).read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0053-probe2 catalog sentinel absent")
        return 1

    try:
        errs = iter_errors(doc)
    except Exception as exc:
        print("FAILED:CNF-0053-probe2 schema-resolve", type(exc).__name__, str(exc)[:240])
        return 1
    if errs:
        e0 = errs[0]
        loc = "/".join(str(p) for p in e0.absolute_path) or "<root>"
        print("FAILED:CNF-0053-probe2 schema", loc, e0.message)
        return 1

    # Independent re-derive: measure cold + one warm pair BEFORE reading answers.
    work = HERE / "_stage_probe2"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    before_root = stage_commit(BEFORE_SRC, work / "before", with_payload=False)
    after_root = stage_commit(AFTER_SRC, work / "after", with_payload=True)
    warm_b = run_import(before_root, cold=False)
    warm_a = run_import(after_root, cold=False)
    cold = run_import(after_root, cold=True)
    before_table = module_median_table([warm_b])
    after_table = module_median_table([warm_a])
    derived_largest = largest_increase(before_table, after_table)
    derived_delta = warm_a["wall_ms"] - warm_b["wall_ms"]
    derived_budget = find_latency_budget(REPO)

    derived = {
        "largest_module": derived_largest["module"],
        "delta_ms": round(derived_delta, 4),
        "cold_wall_ms": cold["wall_ms"],
        "cold_method": (cold.get("fadvise") or {}).get("method"),
        "advised": (cold.get("fadvise") or {}).get("advised"),
        "budget_status": derived_budget["status"],
        "budget_declared": derived_budget["declared"],
        "payload_ok": True,
    }
    RAW.write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")

    if derived_largest["module"] != "tool_startup.extra":
        print("FAILED:CNF-0053-probe2 re-derived largest", derived_largest)
        return 1
    if derived_budget["status"] != "NOT-CHECKED" or derived_budget["declared"]:
        print("FAILED:CNF-0053-probe2 budget was invented or declared", derived_budget)
        return 1
    if derived_delta <= 0:
        print("FAILED:CNF-0053-probe2 re-derived delta not positive", derived_delta)
        return 1
    fadv = cold.get("fadvise") or {}
    if fadv.get("advised", 0) < 1:
        print("FAILED:CNF-0053-probe2 fadvise advised no files", fadv)
        return 1

    # Only now compare to the artifact conclusion.
    body = payload(doc)
    answers = body.get("answers") or {}
    if answers.get("exceeds_declared_latency_budget") != "NOT-CHECKED":
        print("FAILED:CNF-0053-probe2 artifact invented a budget answer")
        return 1
    if answers.get("largest_increase_module") != "tool_startup.extra":
        print("FAILED:CNF-0053-probe2 artifact largest mismatch")
        return 1
    cold_art = body.get("cold_cache_measurement") or {}
    if cold_art.get("included") is not True:
        print("FAILED:CNF-0053-probe2 artifact omitted cold cache")
        return 1
    if int(cold_art.get("payload_bytes") or 0) < 1:
        print("FAILED:CNF-0053-probe2 artifact cold payload_bytes missing")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0053-probe2 self-declared", doc.get("state"))
        return 1
    if body.get("kind") != "benchmark-report":
        print("FAILED:CNF-0053-probe2 report.kind", body.get("kind"))
        return 1

    # Garbage must still be rejected by the schema (contract discriminates).
    rejected = 0
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}):
        g_errs = iter_errors(garbage)
        if g_errs:
            rejected += 1
        else:
            print("FAILED:CNF-0053-probe2 schema accepted garbage")
            return 1
    if rejected != 2:
        print("FAILED:CNF-0053-probe2 garbage control")
        return 1

    print(
        f"cold_ms={cold['wall_ms']} advised={fadv.get('advised')} "
        f"rederived_largest={derived_largest['module']} "
        f"budget={derived_budget['status']} schema=PASS"
    )
    print("SUCCESS:CNF-0053-probe2 cold-cache budget NOT-CHECKED schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
