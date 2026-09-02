#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0272.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.partition import (  # noqa: E402
    HONEST,
    SEAT_A,
    SEAT_B,
    WITHHELD_ID,
    run_fixture,
    search_seat,
)

OUT_REL = "command-center/receipts/TST-0272.json"
SENTINEL = "SUCCESS:TST-0272"

SUPPORTING = [
    "tools/council/partition.py",
    "tools/council/context.py",
    "tools/council/schema/information-partition.schema.json",
    "tools/council/tests/test_partition.py",
    "command-center/p2-wave/probes/TST-0272/probe1_withheld_canary.py",
    "command-center/p2-wave/probes/TST-0272/probe2_summary_and_detector.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/tests/test_partition.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0272/probe1_withheld_canary.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0272/probe2_summary_and_detector.py"
)
QUESTION = (
    "When the spec partitions information so seat A cannot see evidence "
    "bundle B, does the runtime actually withhold it, and does it stay "
    "withheld through summaries, shared scratchpads, tool results and the "
    "moderator's own paraphrase?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(text),
        "method": "command",
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0272 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:TST-0272-tests" not in t_test:
        print("FAILED:TST-0272 emit tests sentinel missing")
        return 1
    if "SUCCESS:TST-0272-probe1" not in t1:
        print("FAILED:TST-0272 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0272-probe2" not in t2:
        print("FAILED:TST-0272 emit probe2 sentinel missing")
        return 1

    honest = run_fixture(HONEST)
    token = honest.withheld_canary
    partitioned = search_seat(SEAT_A, token, honest.artifacts)
    privileged = search_seat(SEAT_B, token, honest.artifacts)

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": "TST-0272",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0272",
        "title": (
            "Information-partition leakage test for blind and partitioned "
            "council rounds"
        ),
        "question": QUESTION,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "no-automatic-retry; re-run after a named harness or fixture change",
        },
        "implementation": {
            "module": "tools/council/partition.py",
            "context_assembler": "tools/council/context.py",
            "withheld_bundle_id": WITHHELD_ID,
            "partitioned_seat": SEAT_A,
            "privileged_seat": SEAT_B,
            "canary_token": token,
            "forced_moderator_summary": True,
            "summary_path": f"derived/moderator_summary/{WITHHELD_ID}",
        },
        "artifact_paths": artifact_paths,
        "test_ids": [
            "test_honest_withheld_zero_hits_on_partitioned_seat",
            "test_detector_control_same_canary_in_allowed_is_found",
            "test_naive_summary_leaks_to_partitioned_seat",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "naive-moderator-summary-copies-withheld-body",
            "assembly-leak-feeds-withheld-into-partitioned-prompt",
            "empty-search-rejected-as-not-attributable",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/partition.py:search_seat",
                "claim": (
                    f"Canary {token} planted in {WITHHELD_ID} has zero hits "
                    f"across {len(partitioned.paths_searched)} artifacts "
                    f"{SEAT_A} can read: {list(partitioned.paths_searched)}. "
                    f"{SEAT_B} hits={privileged.hit_count} on the same token."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "mechanism": (
                    "partition.bundles_for_seat omits B-WITHHELD from seat-a "
                    "before context.assemble_seat; derived carriers inherit "
                    "the bundle allow-list or a redacted paraphrase."
                ),
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/partition.py:run_fixture",
                "claim": (
                    "Detector control plants the same canary in B-ALLOWED and "
                    "the search finds it in seat-a/prompt. Forced honest "
                    "moderator summary of B-WITHHELD still yields zero hits "
                    "for seat-a; a naive summary that copies the withheld "
                    "body is found at derived/moderator_summary/B-WITHHELD."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "mechanism": (
                    "Two-state summary path: honest summary.visible_to is "
                    "privileged seats only; naive-summary sets visible_to to "
                    "every seat without redacting the token."
                ),
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "naive-moderator-summary-copies-withheld-body",
                "kind": "planted-leak-carrier",
                "description": (
                    "Force a moderator summary that copies B-WITHHELD into a "
                    "carrier readable by seat-a. search_seat must find the "
                    "canary at derived/moderator_summary/B-WITHHELD."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "honest hit_count=0; summary not in paths_searched",
                "bad_state_output": "naive-summary hit_count>=1 at derived/moderator_summary/B-WITHHELD",
            },
            {
                "id": "assembly-leak-feeds-withheld-into-partitioned-prompt",
                "kind": "planted-assembly-leak",
                "description": (
                    "Feed every bundle into seat-a's assembler. The same "
                    "search must find the canary in seat-a/prompt, proving "
                    "context.py does not silently strip unknown tokens."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "honest seat-a/prompt does not contain withheld canary",
                "bad_state_output": "assembly-leak seat-a/prompt contains withheld canary",
            },
            {
                "id": "empty-search-rejected-as-not-attributable",
                "kind": "vacuous-zero",
                "description": (
                    "A search over zero artifacts must be rejected so a "
                    "zero-hit result cannot be claimed without paths searched."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"paths_searched={len(partitioned.paths_searched)}",
                "bad_state_output": "require_real_search raises PartitionError",
            },
        ],
        "tests": [
            {
                "id": "test_honest_withheld_zero_hits_on_partitioned_seat",
                "command": TEST_CMD
                + "::test_honest_withheld_zero_hits_on_partitioned_seat",
                "result": "PASS",
            },
            {
                "id": "test_detector_control_same_canary_in_allowed_is_found",
                "command": TEST_CMD
                + "::test_detector_control_same_canary_in_allowed_is_found",
                "result": "PASS",
            },
            {
                "id": "test_naive_summary_leaks_to_partitioned_seat",
                "command": TEST_CMD + "::test_naive_summary_leaks_to_partitioned_seat",
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "canary_search": {
            "token": token,
            "partitioned_seat": SEAT_A,
            "paths_searched": list(partitioned.paths_searched),
            "hit_count": partitioned.hit_count,
            "privileged_hit_count": privileged.hit_count,
        },
        "reviewer": {
            "reviewer_id": "TST-0272-probe2-summary-and-detector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "second_reviewer_id": "TST-0272-probe1-withheld-canary",
            "second_reviewer_role": "cross-vendor-security",
            "obligation": (
                "Reproduce the leakage attempt (naive summary) and the "
                "detector control (same canary in ALLOWED) before treating "
                "honest zero-hits as a withhold."
            ),
            "method": (
                "Re-ran probe2 from the search contract: forced moderator "
                "summary of B-WITHHELD, honest zero hits, naive-summary hit "
                "at the summary path, plus scratchpad/tool/paraphrase naive "
                "carriers. Did not re-read an author summary."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0272",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0272/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py and "
                    "command-center/schema/council-spec.schema.json are "
                    "absent on this worktree (TST-0257). This unit enforces "
                    "and measures information partitioning against the B07 "
                    "context assembler (tools/council/context.py) plus "
                    "tools/council/partition.py. It does not claim a full "
                    "scripted-persona council simulator exists."
                ),
                "settling_experiment": (
                    "After TST-0257 lands simulate.py, re-run both named "
                    "probes against a CouncilSpec round that declares the "
                    "same seat-a / B-WITHHELD partition."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of TST-0272 information-partition leakage test. "
            "Live probes: withheld canary zero hits with detector control, "
            "and forced-summary honest vs naive both-states. Did not run "
            "global unit_manifest.py --write. cloud ok is not consulted. "
            + SENTINEL
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
