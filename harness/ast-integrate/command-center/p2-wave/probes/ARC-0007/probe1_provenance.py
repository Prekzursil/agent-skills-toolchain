#!/usr/bin/env python3
"""Named probe 1 (ARC-0007): two independent provenance signals on a 10-file sample.

Mechanically: git log -1 --format=%cI (repo) vs filesystem mtime + line-diff (live).
A different data field than probe 2 (unique-line union / refuse-overwrite).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import procedure as P  # noqa: E402

ART = REPO / "command-center/phase3/A1/MIGRATION.json"
LEDGER = HERE / "fixtures/repo-committer-ledger.json"
REPO_ROOT = HERE / "fixtures/repo"
LIVE_ROOT = HERE / "fixtures/live"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0007-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    sample = doc.get("sample") or []
    if len(sample) != 10:
        print(f"FAILED:ARC-0007-probe1 sample_size={len(sample)} want=10")
        return 1
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    live_larger = 0
    git_attempts = 0
    independent = 0
    rows = []
    for row in sample:
        rel = row["path"]
        rec = P.measure_file(rel, REPO_ROOT, LIVE_ROOT, ledger, None)
        git_attempts += 1
        sig1 = rec.repo_committer_iso or rec.ledger_committer_iso
        sig2 = rec.live_mtime_iso
        if not sig1 or not sig2:
            print(f"FAILED:ARC-0007-probe1 missing signal on {rel} s1={sig1} s2={sig2}")
            return 1
        if rec.ledger_committer_iso != rec.live_mtime_iso:
            independent += 1
        if rec.live_larger:
            live_larger += 1
        rows.append(
            {
                "path": rel,
                "git_log_exit": rec.git_log_exit,
                "git_log_raw": rec.git_log_raw,
                "ledger_iso": rec.ledger_committer_iso,
                "live_mtime_iso": rec.live_mtime_iso,
                "live_unique_lines": rec.live_unique_line_count,
                "repo_unique_lines": rec.repo_unique_line_count,
                "live_larger": rec.live_larger,
            }
        )
    pinned = set(P.LIVE_LARGER_NAMES)
    have = {r["path"] for r in rows if r["live_larger"]}
    if live_larger < 1 or not (pinned & have):
        print(f"FAILED:ARC-0007-probe1 live_larger={live_larger} overlap={pinned & have}")
        return 1
    if independent < 10:
        print(f"FAILED:ARC-0007-probe1 signals not independent independent={independent}")
        return 1
    out = {
        "probe": "probe1-provenance",
        "unit_id": "ARC-0007",
        "sample": 10,
        "git_log_attempts": git_attempts,
        "independent_signal_pairs": independent,
        "live_larger_in_sample": live_larger,
        "live_larger_paths": sorted(have),
        "pass": True,
    }
    (HERE / "probe1-provenance.raw.json").write_text(
        json.dumps({**out, "rows": rows}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ARC-0007-probe1 provenance two-signal sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
