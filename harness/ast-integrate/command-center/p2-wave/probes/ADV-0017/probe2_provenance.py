#!/usr/bin/env python3
"""Probe 2: provenance (git %cI vs live mtime) plus content-read of live-larger files.

Mechanically different from probe 1 (no whole-tree line-set classification).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_common as A  # noqa: E402
import controls as C  # noqa: E402
import fixtures as F  # noqa: E402
import lib_provenance as P  # noqa: E402
import recover_historical as H  # noqa: E402

from audit_common import FIXTURE_LIVE, FIXTURE_REPO  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0017-probe2 {msg}")
    return 1


def main() -> int:
    if not FIXTURE_REPO.is_dir() or not FIXTURE_LIVE.is_dir():
        return _fail("fixture trees missing (emit writes them; probes are read-only)")
    before = C.snapshot(FIXTURE_REPO, FIXTURE_LIVE)
    repo_files = A.iter_rel_files(FIXTURE_REPO)
    live_files = A.iter_rel_files(FIXTURE_LIVE)
    rels = sorted(set(repo_files) | set(live_files))
    rows = P.provenance_rows(FIXTURE_REPO, FIXTURE_LIVE, rels)
    live_larger_reads = [
        r["live_larger_content"]
        for r in rows
        if isinstance(r.get("live_larger_content"), dict)
    ]
    git_attempted = all("git" in r and "exit_code" in r["git"] for r in rows)
    git_any_iso = any((r.get("git") or {}).get("iso") for r in rows)
    nowrite = C.finish_no_write(FIXTURE_REPO, FIXTURE_LIVE, before)
    pin = H.historical_pin()
    payload = {
        "probe": "probe2-provenance-git-mtime-live-larger-read",
        "unit_id": "ADV-0017",
        "instrument": "git log -1 --format=%cI vs live mtime plus content-read of live-larger files",
        "disclosed_synthetic_fixtures": True,
        "not_windows_live_estate": True,
        "git_repo": False,
        "git_attempted": git_attempted,
        "git_any_committer_iso": git_any_iso,
        "host_live_present": A.host_live_present(),
        "historical_pin": pin,
        "live_larger_read_n": len(live_larger_reads),
        "live_larger_reads": live_larger_reads,
        "no_write": {"result": nowrite["result"], "pass": nowrite["pass"]},
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not nowrite["pass"]:
        return _fail("no-write control failed")
    if not git_attempted:
        return _fail("git log was not attempted per file")
    if git_any_iso:
        return _fail("unexpected git committer iso on a non-git worktree")
    if len(live_larger_reads) < 1:
        return _fail("no live-larger file was content-read")
    pinned = {r["path"]: r for r in live_larger_reads}
    for rel in A.CATALOG_PIN_LIVE_LARGER:
        row = pinned.get(rel)
        if not row or row["live_only_line_n"] < 1:
            return _fail(f"live-larger content-read missed {rel}")
    both_live = next(
        (r for r in live_larger_reads if r["path"] == F.BOTH_UNIQUE_LIVE_AHEAD),
        None,
    )
    if both_live is None or both_live["live_only_line_n"] < 1:
        return _fail("both-unique live-ahead was not content-read as live-larger")
    print(
        "live_larger_read_n="
        + str(len(live_larger_reads))
        + " git_any_iso="
        + str(git_any_iso)
        + " historical_remeasured="
        + str(pin["cited_as_live_remeasure"])
    )
    print("SUCCESS:ADV-0017-probe2 provenance and live-larger content-read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
