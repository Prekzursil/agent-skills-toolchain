#!/usr/bin/env python3
"""Probe 2: thawed original write is rejected by the fencing token (timeout-only mutant is not)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fencing_lease import (  # noqa: E402
    COMMITTED,
    REJECTED,
    REASON_STALE,
    ast_commit_is_token_gated,
    scenario_zombie_write,
)


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0090-probe2 {msg}")
    return 1


def main() -> int:
    src = (HERE / "fencing_lease.py").read_text(encoding="utf-8")
    ast_info = ast_commit_is_token_gated(src)
    with tempfile.TemporaryDirectory(prefix="tst0090-p2-") as tmp:
        root = Path(tmp)
        good = scenario_zombie_write(root / "fencing", mode="fencing")
        mutant = scenario_zombie_write(root / "timeout-only", mode="timeout-only")

    thawed = good["thawed_original"]
    mutant_thawed = mutant["thawed_original"]
    reclaimer_ok = good["reclaimer_committed"]["status"] == COMMITTED
    zombie_rejected = (
        thawed["status"] == REJECTED
        and thawed["reason"] == REASON_STALE
        and int(thawed.get("stale_token") or -1) == int(good["orig_token"])
        and good["stale_token_recorded"] is True
    )
    mutant_accepts = mutant_thawed["status"] == COMMITTED
    winner_is_reclaimer = good["winner_payload"] == "SUCCESS from reclaimer"
    both_states = zombie_rejected and mutant_accepts

    payload = {
        "pass": False,
        "probe": "probe2-stale-token",
        "unit_id": "TST-0090",
        "ast": ast_info,
        "fencing": {
            "orig_token": good["orig_token"],
            "reclaim_token": good["reclaimed"].get("token"),
            "reclaimer_status": good["reclaimer_committed"]["status"],
            "thawed_status": thawed["status"],
            "thawed_reason": thawed["reason"],
            "stale_token": thawed.get("stale_token"),
            "stale_token_recorded": good["stale_token_recorded"],
            "winner_payload": good["winner_payload"],
        },
        "timeout_only_mutant": {
            "orig_token": mutant["orig_token"],
            "reclaim_token": mutant["reclaimed"].get("token"),
            "thawed_status": mutant_thawed["status"],
            "thawed_reason": mutant_thawed["reason"],
            "accepts_zombie_write": mutant_accepts,
        },
        "both_states": {
            "fencing_rejects_zombie": zombie_rejected,
            "timeout_only_accepts_zombie": mutant_accepts,
        },
    }
    ok = (
        reclaimer_ok
        and zombie_rejected
        and mutant_accepts
        and both_states
        and winner_is_reclaimer
        and ast_info["pass"] is True
        and int(good["reclaimed"].get("token") or 0) == int(good["orig_token"]) + 1
        and int(mutant["reclaimed"].get("token") or -1) == int(mutant["orig_token"])
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return _fail(
            f"zombie_rejected={zombie_rejected} mutant_accepts={mutant_accepts} "
            f"ast={ast_info.get('pass')}"
        )
    print(
        "SUCCESS:TST-0090-probe2 thawed original write rejected by fencing token; "
        "timeout-only mutant still commits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
