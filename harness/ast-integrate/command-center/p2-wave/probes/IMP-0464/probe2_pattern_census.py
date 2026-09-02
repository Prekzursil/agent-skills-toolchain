#!/usr/bin/env python3
"""Named probe 2: per-pattern match census and dead-pattern naming.

A pattern matching zero files across every build is named dead-or-broken.
Live patterns in the exclusion set must each fire at least once. Credential
values must not appear in the census output.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from package_gate.content_gate import (  # noqa: E402
    SYNTHETIC_CREDENTIAL,
    dead_or_broken_patterns,
    evaluate,
    load_exclusion_set,
    merge_counts,
    plant_credential,
    plant_git,
    plant_log,
    plant_oversize,
    plant_pycache,
    plant_transcript,
    write_clean_tree,
)

LIVE_PATTERNS = (
    "git-dir",
    "oversize-file",
    "credential-env",
    "credential-json",
    "pycache",
    "log-file",
    "transcript",
)
DEAD_ID = "never-match-canary"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0464-probe2 {msg}")
    return 1


def main() -> int:
    exclusion = load_exclusion_set().with_extra(
        [
            {
                "id": DEAD_ID,
                "kind": "basename",
                "value": "this-pattern-never-exists-imp0464",
                "failure_class": "dead-pattern-control",
            }
        ]
    )
    with tempfile.TemporaryDirectory(prefix="imp0464-p2-") as raw:
        base = Path(raw)
        rows = []
        builds = (
            ("clean", lambda _r: None),
            ("git", plant_git),
            ("big", plant_oversize),
            ("cred-env", plant_credential),
            ("cred-json", lambda r: plant_credential(r, "credentials.json")),
            ("cache", plant_pycache),
            ("log", plant_log),
            ("transcript", plant_transcript),
        )
        for name, planter in builds:
            root = base / name
            write_clean_tree(root)
            planter(root)
            result = evaluate(root, exclusion)
            rows.append(
                {
                    "build": name,
                    "ok": result.ok,
                    "counts": result.pattern_match_counts,
                    "reasons": result.reasons,
                    "file_count": sum(1 for f in result.files if not f.is_dir),
                    "total_bytes": result.total_bytes,
                }
            )
        merged = merge_counts(r["counts"] for r in rows)
        dead = dead_or_broken_patterns(merged)
        if DEAD_ID not in dead:
            return fail(f"injected dead pattern was not named: {dead}")
        for pid in LIVE_PATTERNS:
            if merged.get(pid, 0) < 1:
                return fail(f"live pattern {pid} matched 0 across every build")
            if pid in dead:
                return fail(f"live pattern {pid} incorrectly named dead")
        dumped = json.dumps({"rows": rows, "merged": merged, "dead": dead})
        if SYNTHETIC_CREDENTIAL in dumped:
            return fail("credential value leaked into census")

        clean_row = next(r for r in rows if r["build"] == "clean")
        if not clean_row["ok"]:
            return fail("clean census build refused")
        git_row = next(r for r in rows if r["build"] == "git")
        if git_row["ok"]:
            return fail("git census build packed")

        payload = {
            "probe": "probe2-pattern-census",
            "unit_id": "IMP-0464",
            "pattern_match_counts": merged,
            "dead_or_broken_patterns": dead,
            "live_patterns_fired": {pid: merged[pid] for pid in LIVE_PATTERNS},
            "builds": [
                {
                    "build": r["build"],
                    "ok": r["ok"],
                    "file_count": r["file_count"],
                    "total_bytes": r["total_bytes"],
                    "reasons": r["reasons"],
                }
                for r in rows
            ],
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"dead_named={dead} live_fired={list(LIVE_PATTERNS)} "
            f"clean_ok={clean_row['ok']}"
        )
        print("SUCCESS:IMP-0464-probe2 per-pattern census names dead-or-broken patterns")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
