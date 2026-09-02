#!/usr/bin/env python3
"""Probe 2: child failure honours parent policy (both-states: abort vs continue).

Continue: sibling embed-b is STARTED after embed-a FAILED (event log).
Abort: sibling embed-b is SKIPPED (event log), never started.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = Path(__file__).resolve().parents[4] / "command-center/receipts/IMP-0189.json"


def _events(result, kind: str, node_id: str):
    return [e for e in result.events if e.kind == kind and e.node_id == node_id]


def _seq(result, kind: str, node_id: str) -> int | None:
    hits = _events(result, kind, node_id)
    return hits[0].seq if hits else None


def main() -> int:
    cont = S.run_policy("continue")
    abort = S.run_policy("abort")

    fail_seq_c = _seq(cont, "failed", "embed-a")
    start_b_c = _seq(cont, "started", "embed-b")
    succ_b_c = _seq(cont, "succeeded", "embed-b")
    skip_b_c = _seq(cont, "skipped", "embed-b")

    fail_seq_a = _seq(abort, "failed", "embed-a")
    start_b_a = _seq(abort, "started", "embed-b")
    skip_b_a = _seq(abort, "skipped", "embed-b")

    payload = {
        "probe": "probe2-failure-policy",
        "continue": {
            "failed_embed_a_seq": fail_seq_c,
            "started_embed_b_seq": start_b_c,
            "succeeded_embed_b_seq": succ_b_c,
            "skipped_embed_b_seq": skip_b_c,
            "ok": cont.ok,
            "policy_applied": cont.policy_applied,
        },
        "abort": {
            "failed_embed_a_seq": fail_seq_a,
            "started_embed_b_seq": start_b_a,
            "skipped_embed_b_seq": skip_b_a,
            "ok": abort.ok,
            "policy_applied": abort.policy_applied,
            "aborted": abort.aborted,
        },
    }
    print(json.dumps(payload, sort_keys=True))

    if fail_seq_c is None:
        print("FAILED:IMP-0189-probe2 continue: embed-a failure not in event log")
        return 1
    if start_b_c is None or start_b_c <= fail_seq_c:
        print(
            "FAILED:IMP-0189-probe2 continue: sibling embed-b did not start after "
            "child failure (must be observed in the event log)"
        )
        return 1
    if succ_b_c is None:
        print("FAILED:IMP-0189-probe2 continue: sibling embed-b did not succeed")
        return 1
    if skip_b_c is not None:
        print("FAILED:IMP-0189-probe2 continue: sibling was skipped")
        return 1
    if not cont.ok or cont.policy_applied != "continue":
        print("FAILED:IMP-0189-probe2 continue policy not applied")
        return 1

    if fail_seq_a is None:
        print("FAILED:IMP-0189-probe2 abort: embed-a failure not in event log")
        return 1
    if start_b_a is not None:
        print("FAILED:IMP-0189-probe2 abort: sibling embed-b started (should skip)")
        return 1
    if skip_b_a is None or skip_b_a <= fail_seq_a:
        print("FAILED:IMP-0189-probe2 abort: sibling skip not observed after failure")
        return 1
    if abort.ok or abort.policy_applied != "abort" or not abort.aborted:
        print("FAILED:IMP-0189-probe2 abort policy not applied")
        return 1

    print(
        f"continue_sibling_started_after_fail=True seq_fail={fail_seq_c} "
        f"seq_start_b={start_b_c} abort_sibling_skipped=True seq_skip_b={skip_b_a}"
    )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print(f"FAILED:IMP-0189-probe2 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:IMP-0189" not in text:
            print("FAILED:IMP-0189-probe2 sentinel absent")
            return 1
        both = doc.get("failure_policy_both_states") or {}
        if both and not (
            both.get("continue_sibling_ran") is True
            and both.get("abort_sibling_skipped") is True
        ):
            print("FAILED:IMP-0189-probe2 receipt both-states drift")
            return 1

    print("SUCCESS:IMP-0189-probe2 child failure honours parent policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
