#!/usr/bin/env python3
"""Probe 2: every cited artifact path is Test-Path'd before a digest is accepted.

Missing path: REJECT PATH_ABSENT; digest is not read.
Present paths: Test-Path events all precede any digest_read event.
Digest-only (no raw citations): REJECT DIGEST_IS_CLAIM; digest is never a receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from certify import certify  # noqa: E402
from confirm_hook import (  # noqa: E402
    REASON_DIGEST_IS_CLAIM,
    REASON_PATH_ABSENT,
    VERDICT_ACCEPT,
    VERDICT_REJECT,
    admit,
    load_json,
)

FIX = HERE / "fixtures"


def _first_index(trace: list[str], prefix: str) -> int:
    for i, ev in enumerate(trace):
        if ev.startswith(prefix):
            return i
    return -1


def _all_test_path_before_digest(trace: list[str]) -> bool:
    digest_idx = [i for i, ev in enumerate(trace) if ev.startswith("digest_read:")]
    if not digest_idx:
        # No digest read is valid for the accept path when no digest was supplied.
        return any(ev.startswith("test_path:") for ev in trace)
    first_digest = digest_idx[0]
    test_idx = [i for i, ev in enumerate(trace) if ev.startswith("test_path:")]
    if not test_idx:
        return False
    return max(test_idx) < first_digest and min(test_idx) < first_digest


def main() -> int:
    workflow = load_json(FIX / "workflow.json")
    missing = load_json(FIX / "confirmation_missing_path.json")
    citing = load_json(FIX / "confirmation_citing.json")
    digest_only = load_json(FIX / "confirmation_digest_only.json")
    # Attach a digest to the good confirmation so the admit path may read it
    # *after* Test-Path. The digest still cannot become the receipt.
    citing_with_digest = json.loads(json.dumps(citing))
    citing_with_digest["digest"] = "corroboration-only"

    absent = admit(missing, workflow, FIX)
    present = admit(citing_with_digest, workflow, FIX)
    digest = admit(digest_only, workflow, FIX)
    cert_absent = certify(workflow, missing, FIX)
    cert_present = certify(workflow, citing_with_digest, FIX)

    ghost = "raw/ghost-case-does-not-exist.json"
    absent_ok = (
        absent.verdict == VERDICT_REJECT
        and absent.reason == REASON_PATH_ABSENT
        and ghost in absent.paths_missing
        and not absent.digest_read
        and not absent.digest_accepted
        and not cert_absent.get("certified")
        and any(ev == f"test_path:{ghost}" for ev in absent.trace)
        and all(not ev.startswith("digest_read:") for ev in absent.trace)
        and _first_index(absent.trace, "stage:test_path") >= 0
        and _first_index(absent.trace, "stage:digest_read_allowed") < 0
    )
    present_ok = (
        present.verdict == VERDICT_ACCEPT
        and present.digest_read is True
        and present.digest_accepted is False
        and cert_present.get("certified") is True
        and cert_present.get("digest_accepted") is False
        and _all_test_path_before_digest(present.trace)
        and any(ev.startswith("test_path:raw/per_case_rows.json") for ev in present.trace)
        and any(ev == "digest_read:confirmation.digest" for ev in present.trace)
        and _first_index(present.trace, "stage:test_path")
        < _first_index(present.trace, "stage:digest_read_allowed")
    )
    digest_ok = (
        digest.verdict == VERDICT_REJECT
        and digest.reason == REASON_DIGEST_IS_CLAIM
        and not digest.digest_accepted
        and not digest.raw_citations
    )

    passed = absent_ok and present_ok and digest_ok
    print(
        json.dumps(
            {
                "probe": "probe2-existence-before-digest",
                "unit_id": "IMP-0202",
                "missing_path": {
                    "verdict": absent.verdict,
                    "reason": absent.reason,
                    "paths_missing": absent.paths_missing,
                    "digest_read": absent.digest_read,
                    "digest_accepted": absent.digest_accepted,
                    "trace": absent.trace,
                },
                "present_path": {
                    "verdict": present.verdict,
                    "reason": present.reason,
                    "digest_read": present.digest_read,
                    "digest_accepted": present.digest_accepted,
                    "trace": present.trace,
                    "certified": cert_present.get("certified"),
                },
                "digest_only": {
                    "verdict": digest.verdict,
                    "reason": digest.reason,
                    "digest_accepted": digest.digest_accepted,
                },
                "absent_ok": absent_ok,
                "present_ok": present_ok,
                "digest_ok": digest_ok,
                "pass": passed,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"absent_ok={absent_ok} present_ok={present_ok} digest_ok={digest_ok} "
        f"digest_read_after_test_path={_all_test_path_before_digest(present.trace)}"
    )
    if not passed:
        print("FAILED:IMP-0202-probe2 Test-Path-before-digest did not hold")
        return 1
    print("SUCCESS:IMP-0202-probe2 every cited path Test-Path'd before digest accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
