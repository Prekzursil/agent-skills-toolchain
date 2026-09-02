#!/usr/bin/env python3
"""Probe 2: both-states REACH-6 + platform parity.

FIRE on genuine content change, SILENT on pure EOL. Windows-CRLF worktree vs
Linux-LF blob agree AFTER cat-file hashing and disagree BEFORE (worktree hasher).
Independent of probe 1's archive census.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CC-0005.json"
RAW = HERE / "probe2-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0005-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CC-0005" not in text:
        return fail("sentinel-absent")
    live = S.measure()
    RAW.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fails = [
        f
        for f in S.failures(live)
        if f
        in {
            "gate not silent on EOL-only worktree",
            "gate did not fire on genuine content change",
            "blob hasher not green after fix",
            "worktree hasher did not fail on CRLF before the fix",
            "Windows/Linux blob hasher verdicts differ",
            "worktree hasher did not diverge across platforms before the fix",
            "silent path did not hash via git-cat-file",
        }
    ]
    if fails:
        return fail("; ".join(fails))
    if not live["silent_on_eol_only"] or not live["fires_on_content_change"]:
        return fail("both-states missing")
    gate = doc.get("gate_exits") or {}
    if gate.get("windows_before") != live["windows_worktree_hasher_exit_before"]:
        return fail("receipt windows_before stale")
    if gate.get("windows_after") != live["windows_blob_hasher_exit_after"]:
        return fail("receipt windows_after stale")
    print(
        "silent_on_eol={silent_on_eol_only} fire_on_content={fires_on_content_change} "
        "hash_via={reach6_hash_via_silent} win_before={windows_worktree_hasher_exit_before} "
        "win_after={windows_blob_hasher_exit_after} linux_before={linux_worktree_hasher_exit_before} "
        "linux_after={linux_blob_hasher_exit_after} parity_after={platform_parity_after}".format(
            **live
        )
    )
    print("SUCCESS:CC-0005-probe2 both-states and platform parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
