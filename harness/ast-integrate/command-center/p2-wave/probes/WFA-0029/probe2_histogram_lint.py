#!/usr/bin/env python3
"""Probe 2: dry-run histogram + independent provider 429s + call-site lint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import dry_run  # noqa: E402
from lint_call_sites import evaluate as lint_evaluate_direct  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "wfa" / "WFA-0029-acquisition-scheduler.json"
SENTINEL = "SUCCESS:WFA-0029"
OUT = HERE / "probe2-histogram-lint.raw.json"


def main() -> int:
    failed: list[str] = []
    dry = dry_run()
    lint = lint_evaluate_direct(REPO)
    if not dry.get("pass"):
        failed.append("live:dry-run")
    if not lint.get("pass"):
        failed.append("live:lint")
    if dry["naive_burst"]["http_429"] <= 0:
        failed.append("naive-burst-vacuous")
    if dry["scheduled"]["github_provider"]["http_429"] != 0:
        failed.append("scheduled-path-429")
    if dry["detector"]["detector_failure"]:
        failed.append("detector-failure-provider-wins")
    if not lint.get("planted_fired"):
        failed.append("lint-planted-silent")
    if not lint.get("routed_ok"):
        failed.append("lint-routed-false-positive")

    if not ART.is_file():
        failed.append("artifact-absent")
        doc = {}
        live_fp = None
        art_fp = None
    else:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            failed.append("sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            failed.append(f"self-declared:{st}")
        art_fp = doc.get("fingerprint")
        if art_fp:
            if art_fp.get("github_max") != dry["scheduled"]["github_max_in_window"]:
                failed.append("artifact:github-max-mismatch")
            if art_fp.get("exa_max") != dry["scheduled"]["exa_max_in_window"]:
                failed.append("artifact:exa-max-mismatch")
            if art_fp.get("sched_github_429") != dry["scheduled"]["github_provider"]["http_429"]:
                failed.append("artifact:sched-429-mismatch")
            if art_fp.get("naive_429") != dry["naive_burst"]["http_429"]:
                failed.append("artifact:naive-429-mismatch")
            if art_fp.get("detector_failure") is not False:
                failed.append("artifact:detector-failure")
            if art_fp.get("lint_pass") is not True:
                failed.append("artifact:lint-fp")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        for tid in ("histogram-within-rate", "provider-429-independent", "call-site-lint"):
            row = tests.get(tid)
            if not row or row.get("pass") is not True:
                failed.append(f"artifact:{tid}")
        live_fp = {
            "github_max": dry["scheduled"]["github_max_in_window"],
            "exa_max": dry["scheduled"]["exa_max_in_window"],
            "sched_github_429": dry["scheduled"]["github_provider"]["http_429"],
            "naive_429": dry["naive_burst"]["http_429"],
            "detector_failure": dry["detector"]["detector_failure"],
            "lint_pass": lint["pass"],
        }

    payload = {
        "probe": "probe2-histogram-lint",
        "unit_id": "WFA-0029",
        "dry_pass": dry.get("pass"),
        "lint_pass": lint.get("pass"),
        "github_max": dry["scheduled"]["github_max_in_window"],
        "naive_429": dry["naive_burst"]["http_429"],
        "sched_429": dry["scheduled"]["github_provider"]["http_429"],
        "winner": dry["detector"]["winner"],
        "planted_fired": lint.get("planted_fired"),
        "live_fp": live_fp,
        "failed": failed,
        "pass": not failed,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:WFA-0029-probe2 histogram/lint")
        print(json.dumps(failed))
        print(json.dumps({
            "detector": dry.get("detector"),
            "naive_429": dry["naive_burst"]["http_429"],
            "lint_pass": lint.get("pass"),
            "planted": {k: {"bypass": v.get("bypass"), "route_calls": v.get("route_calls")} for k, v in (lint.get("planted") or {}).items()},
        }, indent=2, default=str)[:3000])
        return 1
    print(
        f"github_max={dry['scheduled']['github_max_in_window']} "
        f"exa_max={dry['scheduled']['exa_max_in_window']} "
        f"naive_429={dry['naive_burst']['http_429']} "
        f"sched_429={dry['scheduled']['github_provider']['http_429']} "
        f"winner={dry['detector']['winner']} "
        f"lint_planted={lint['planted_fired']} live_files={lint['live_files_scanned']}"
    )
    print("SUCCESS:WFA-0029-probe2 histogram provider-429 lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
