#!/usr/bin/env python3
"""Probe 2: first writer's post-expiry write outcome (signal b).

PASS requires the expiring writer to fail its next write after ownership
transfers. The advisory-only mutant (no write-time recheck) must continue,
which is the negative control firing on the bad state.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import expiry_mid_write  # noqa: E402

ART = REPO / "command-center/receipts/TST-0161.json"
SENTINEL = "SUCCESS:TST-0161"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0161-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0161-p2-") as tmp:
        root = Path(tmp)
        enforced = expiry_mid_write(root / "enforced", write_time_recheck=True)
        advisory = expiry_mid_write(root / "advisory", write_time_recheck=False)
        reviewer = expiry_mid_write(root / "reviewer", write_time_recheck=True)

    print(json.dumps(enforced, sort_keys=True, default=str))
    print(json.dumps(advisory, sort_keys=True, default=str))

    if not enforced.get("ok"):
        return fail("enforced expiry-mid-write scenario failed")
    commit_a = enforced.get("commit_a") or {}
    if commit_a.get("ok") is not False:
        return fail("expiring writer continued after ownership transfer")
    if commit_a.get("kind") not in {"STALE_FENCE", "LEASE_EXPIRED"}:
        return fail(f"expiring writer denial is untyped: {commit_a}")
    if not enforced.get("fence_bumped"):
        return fail("transferee fence did not increase")
    if not enforced.get("published_is_transferee"):
        return fail("published bytes are not the transferee's")
    if enforced.get("published_is_original"):
        return fail("original writer's staged payload was published after expiry")

    if not advisory.get("ok"):
        return fail("advisory mutant did not exhibit the silent-continue defect")
    if advisory.get("original_continued") is not True:
        return fail("negative control: advisory writer did not continue")
    if not advisory.get("published_is_original"):
        return fail("negative control: advisory publish was not the original payload")

    if not reviewer.get("ok") or reviewer.get("original_failed") is not True:
        return fail("independent reviewer re-run of expiry transfer failed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live receipt absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    report = doc.get("report") or {}
    live_commit = (report.get("expiry_enforced") or {}).get("commit_a") or {}
    if live_commit.get("ok") is not False:
        return fail("receipt expiry_enforced.commit_a.ok is not false")
    nc = report.get("negative_control") or doc.get("negative_controls") or []
    if isinstance(nc, list):
        nc0 = nc[0] if nc else {}
    else:
        nc0 = nc
    if nc0.get("fired_on_bad_state") is not True or nc0.get("silent_on_good_state") is not True:
        return fail("receipt negative control does not discriminate")

    print(
        json.dumps(
            {
                "probe": "probe2-expiry-write",
                "unit_id": "TST-0161",
                "pass": True,
                "original_commit_kind": commit_a.get("kind"),
                "original_failed": True,
                "advisory_continued": True,
                "reviewer_original_failed": reviewer.get("original_failed"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0161-probe2 expiring writer denied; advisory mutant continues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
