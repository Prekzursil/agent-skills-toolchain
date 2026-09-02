#!/usr/bin/env python3
"""Probe 1: code read of early-return / default-off paths, independent of emit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = REPO / "command-center/audit/AUD-0045-fail-open-gate-census.json"
COMPLETION = (
    "SUCCESS:AUD-0045 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        print("FAILED:AUD-0045-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0045-probe1 self-declared", doc.get("state"))
        return 1
    if COMPLETION not in text or "SUCCESS:AUD-0045" not in text:
        print("FAILED:AUD-0045-probe1 sentinel absent")
        return 1
    if doc.get("report_kind") != "audit-finding":
        print("FAILED:AUD-0045-probe1 report_kind", doc.get("report_kind"))
        return 1

    live_static = C.static_scan()
    live_ci = C.ci_static_fail_open()
    rec_ci = doc.get("ci_static") or {}
    live_count = live_ci.get("fail_open_step_count")
    rec_count = rec_ci.get("fail_open_step_count")
    if live_count != rec_count:
        print(
            "FAILED:AUD-0045-probe1 ci fail_open_step_count drift",
            live_count,
            rec_count,
        )
        return 1

    live_paths = {s["path"] for s in live_static if s.get("exists")}
    rec_paths = {s["path"] for s in (doc.get("static_scan") or []) if s.get("exists")}
    if live_paths != rec_paths:
        print("FAILED:AUD-0045-probe1 static path set drift", live_paths ^ rec_paths)
        return 1

    routing = [
        s
        for s in (live_ci.get("fail_open_steps") or [])
        if "continue_on_error=true-on-named-probe" in (s.get("reasons") or [])
    ]
    if not routing:
        print("FAILED:AUD-0045-probe1 did not re-find continue_on_error named probe")
        return 1

    summary = {
        "probe": "probe1-static-paths",
        "static_files": len(live_paths),
        "ci_fail_open_step_count": live_count,
        "routing_continue_on_error": True,
        "default_off_flags": [
            f for s in live_static for f in (s.get("default_off_flags") or [])
        ],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"static_files={len(live_paths)} ci_fail_open_steps={live_count} "
        "routing_continue_on_error=True"
    )
    print("SUCCESS:AUD-0045-probe1 static early-return and CI fail-open paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
