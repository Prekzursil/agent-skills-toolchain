#!/usr/bin/env python3
"""Probe 2: append-only assertion via a different shell and a different field.

Probe 1 counts JSON objects with json.loads. This probe:
  * hashes the source file (sha256) before and after fold
  * reads byte and line cardinality with `wc -c` / `wc -l` (different shell)
  * refuses in-place rewrite
  * drains the in-flight census (different data field: drain rows, not event counts)

If wc -l and Python splitlines disagree, report BLOCKED with both numbers.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import drain as D  # noqa: E402
import fold as F  # noqa: E402
import harvest as H  # noqa: E402

ART = REPO / "command-center/phase3/A5/MIGRATION.json"
SOURCE = HERE / "fixtures" / "source-events.jsonl"
LEDGER = HERE / "fixtures" / "ledger.jsonl"
DROPS = HERE / "fixtures" / "drops.jsonl"
LIVE = REPO / "command-center" / "events" / "EVENTS.jsonl"


def wc(flag: str, path: Path) -> int:
    p = subprocess.run(
        ["wc", flag, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(p.stdout.split()[0])


def physical_line_list(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text == "":
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def python_physical_lines(path: Path) -> int:
    return len(physical_line_list(path))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0035-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if not SOURCE.is_file():
        H.harvest(SOURCE)
    rel = SOURCE.relative_to(REPO).as_posix()
    live_before = F.sha256_bytes(LIVE.read_bytes()) if LIVE.is_file() else None
    if live_before is not None:
        live_lines = physical_line_list(LIVE)
        src_lines = physical_line_list(SOURCE)
        if live_lines and src_lines[: len(live_lines)] != live_lines:
            print("FAILED:ARC-0035-probe2 fixture prefix is not live EVENTS.jsonl")
            return 1
    before_sha, before_py_bytes = F.file_digest(SOURCE)
    wc_lines = wc("-l", SOURCE)
    wc_bytes = wc("-c", SOURCE)
    py_lines = python_physical_lines(SOURCE)
    if wc_lines != py_lines:
        print("FAILED:ARC-0035-probe2 BLOCKED line-count disagreement")
        print(f" wc_l={wc_lines} python_splitlines={py_lines}")
        return 1
    result = F.fold_file(SOURCE, LEDGER, DROPS, rel)
    after_sha, after_py_bytes = F.file_digest(SOURCE)
    if not result.get("ok"):
        print("FAILED:ARC-0035-probe2 fold failed", result.get("reason"))
        return 1
    if before_sha != after_sha or before_py_bytes != after_py_bytes:
        print("FAILED:ARC-0035-probe2 source mutated by fold")
        print(f" before={before_sha} after={after_sha}")
        return 1
    if not result.get("source_unmodified"):
        print("FAILED:ARC-0035-probe2 source_unmodified false")
        return 1

    inplace = F.fold_file(SOURCE, SOURCE, DROPS, rel)
    if not inplace.get("refused"):
        print("FAILED:ARC-0035-probe2 in-place rewrite was not refused")
        return 1
    if F.sha256_bytes(SOURCE.read_bytes()) != before_sha:
        print("FAILED:ARC-0035-probe2 in-place attempt mutated source")
        return 1
    if live_before is not None:
        live_after = F.sha256_bytes(LIVE.read_bytes())
        if live_after != live_before:
            print("FAILED:ARC-0035-probe2 live EVENTS.jsonl was rewritten")
            return 1

    D.write_census()
    drained = D.drain()
    if not drained.get("ok") or not drained.get("census_unmodified"):
        print("FAILED:ARC-0035-probe2 drain mutated census or failed")
        return 1
    if drained["in_flight"] != drained["drained"]:
        print(
            "FAILED:ARC-0035-probe2 drain count "
            f"{drained['in_flight']} vs {drained['drained']}"
        )
        return 1
    if drained["abandoned_without_record"] != 0:
        print("FAILED:ARC-0035-probe2 abandoned without record")
        return 1
    neg = D.refuse_abandon_without_record(D.load_census())
    if not neg.get("pass") or not neg.get("refused"):
        print("FAILED:ARC-0035-probe2 abandon-without-record not refused")
        return 1

    recorded = (doc.get("tests") or {}).get("append_only_assertion") or {}
    if not recorded.get("source_unmodified") or not recorded.get("in_place_rewrite_refused"):
        print("FAILED:ARC-0035-probe2 artifact missing append-only proof")
        return 1
    census = (doc.get("drain_procedure") or {}).get("census") or {}
    if census.get("in_flight") != drained["in_flight"]:
        print(
            "FAILED:ARC-0035-probe2 drain census disagree "
            f"live={drained['in_flight']} artifact={census.get('in_flight')}"
        )
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-append-only-wc-and-drain",
                "source_unmodified": True,
                "in_place_rewrite_refused": True,
                "ledger_path_distinct": True,
                "sha256": before_sha,
                "wc_l": wc_lines,
                "python_splitlines": py_lines,
                "wc_c": wc_bytes,
                "python_bytes": before_py_bytes,
                "drain_in_flight": drained["in_flight"],
                "drain_drained": drained["drained"],
                "signal": "wc-c-sha256-plus-drain-census",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0035-probe2 append-only and drain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
