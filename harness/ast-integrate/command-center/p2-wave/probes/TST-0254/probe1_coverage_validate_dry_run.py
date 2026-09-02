#!/usr/bin/env python3
"""Probe 1: every tagged workflow fence in the docs tree schema-validates and dry-runs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate import evaluate_extractor_control, evaluate_live  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0254-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    report = evaluate_live()
    control = evaluate_extractor_control()
    summary = {
        "extracted": report["extracted"],
        "independent_open_count": report["independent_open_count"],
        "count_match": report["count_match"],
        "all_schema_ok": report["all_schema_ok"],
        "all_dry_run_ok": report["all_dry_run_ok"],
        "schema_pass_n": report["schema_pass_n"],
        "dry_run_pass_n": report["dry_run_pass_n"],
        "vacuous": report["vacuous"],
        "present_named": report["present_named"],
        "missing_named": report["missing_named"],
        "extractor_control_ok": control["ok"],
        "locations": [r["location"] for r in report["rows"]],
        "spawn_counts": [r.get("spawn_count") for r in report["rows"]],
        "ok": True,
    }
    print(json.dumps(summary, sort_keys=True))
    if report["vacuous"]:
        return fail("vacuous empty tagged-workflow corpus refused")
    if report["missing_named"]:
        return fail("named catalog docs missing", report["missing_named"])
    if not report["count_match"]:
        return fail(
            "extractor count != independent fence-open count",
            {
                "extracted": report["extracted"],
                "independent": report["independent_open_count"],
            },
        )
    if not control["ok"]:
        return fail("extractor control did not isolate tagged vs untagged", control)
    if not report["all_schema_ok"]:
        bad = [r for r in report["rows"] if not r["schema_ok"]]
        return fail("schema validation failed for a tagged example", bad)
    if not report["all_dry_run_ok"]:
        bad = [r for r in report["rows"] if not r["dry_run_ok"]]
        return fail("dry-run failed for a tagged example", bad)
    if any(r.get("spawn_count") not in (0, None) and r.get("spawn_count") != 0 for r in report["rows"]):
        return fail("dry-run recorded a spawn", report["rows"])
    for row in report["rows"]:
        if row.get("spawn_count") != 0 or row.get("write_count") != 0 or row.get("network_count") != 0:
            return fail("dry-run was not side-effect free", row)
        if row.get("stages_planned", 0) < 1:
            return fail("dry-run produced an empty plan", row)
    print(
        f"examples={report['extracted']} schema_ok={report['schema_pass_n']} "
        f"dry_run_ok={report['dry_run_pass_n']} extractor_control={control['ok']}"
    )
    print("SUCCESS:TST-0254-probe1 coverage schema-valid and dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
