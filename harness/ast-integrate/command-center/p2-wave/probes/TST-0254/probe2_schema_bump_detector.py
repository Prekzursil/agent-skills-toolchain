#!/usr/bin/env python3
"""Probe 2: bump the schema in a scratch copy; live examples must be reported stale.

Both-states: current schema still accepts the live examples; the bumped schema
rejects every live example; an epoch-stamped copy is accepted only by the bump.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate import evaluate_live  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0254-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    report = evaluate_live()
    epoch = report.get("epoch_control") or {}
    summary = {
        "extracted": report["extracted"],
        "all_schema_ok": report["all_schema_ok"],
        "all_stale_on_bump": report["all_stale_on_bump"],
        "stale_on_bump_n": report["stale_on_bump_n"],
        "epoch_control": epoch,
        "locations": [r["location"] for r in report["rows"]],
        "bumped_errors_head": [r.get("bumped_errors") for r in report["rows"]],
        "ok": True,
    }
    print(json.dumps(summary, sort_keys=True))
    if report["vacuous"]:
        return fail("vacuous corpus; detector cannot fire")
    if not report["all_schema_ok"]:
        return fail(
            "current schema rejected a live example (cannot isolate bump)",
            [r for r in report["rows"] if not r["schema_ok"]],
        )
    if not report["all_stale_on_bump"]:
        silent = [r for r in report["rows"] if not r["stale_on_bumped_schema"]]
        return fail("bumped schema did not report live examples as stale", silent)
    if not epoch.get("current_rejects_epoch_field"):
        return fail("current schema accepted the epoch-stamped control (additionalProperties leak)")
    if not epoch.get("bumped_accepts_epoch_field"):
        return fail("bumped schema rejected the epoch-stamped control (detector rejects everything)")
    print(
        f"stale={report['stale_on_bump_n']}/{report['extracted']} "
        f"current_green={report['all_schema_ok']} "
        f"epoch_both_states={epoch}"
    )
    print("SUCCESS:TST-0254-probe2 schema-bump detector reported stale examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
