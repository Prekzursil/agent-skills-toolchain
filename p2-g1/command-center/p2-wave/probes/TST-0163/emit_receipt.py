#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0163.json from live spec-hash measurements."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

UNIT = "TST-0163"
OUT = "command-center/receipts/TST-0163.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/concurrency_report"
SENTINEL = "SUCCESS:TST-0163"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0163/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0163/probe2_independent_hash.py"
)
IMPLEMENTATION = [
    "command-center/p2-wave/probes/TST-0163/hash_spec.py",
    "command-center/p2-wave/probes/TST-0163/launcher.py",
    "command-center/p2-wave/probes/TST-0163/scenario.py",
    "command-center/p2-wave/probes/TST-0163/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0163/probe2_independent_hash.py",
]
QUESTION = (
    "If the fan-out launcher or unit spec is edited after launch, does fan-in "
    "detect that units ran under different contracts? PASS requires a spec hash "
    "recorded at dispatch and compared at fan-in, with a typed CONTRACT-DRIFT "
    "result naming the two hashes."
)


def digest_rel(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = S.run_all()
    if not live["pass"]:
        print(json.dumps(live, sort_keys=True, default=str)[:8000])
        print("FAILED:TST-0163 live scenarios did not pass; receipt not written")
        return 1

    unedited = live["test_unedited_reports_no_drift"]
    drift = live["test_midrun_cap_edit_is_contract_drift"]
    naive = live["test_naive_last_write_wins_leaves_contradictory_caps"]
    named = drift.get("named_hashes") or {}
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [digest_rel(rel) for rel in IMPLEMENTATION]
    arts[1]["role"] = "implementation"

    answer = (
        "YES: dispatch records sha256 of the unit spec; fan-in recomputes the "
        "current spec hash in a separate process. An unedited cohort is silent "
        f"(result=OK, n_drifted=0, cap={S.CAP_BEFORE}). A mid-run tool_call_cap "
        f"edit {S.CAP_BEFORE}->{S.CAP_AFTER} yields typed CONTRACT-DRIFT naming "
        f"dispatch={named.get('dispatch')} and fanin={named.get('fanin')}. "
        "Last-write-wins fan-in stays OK while both caps remain live, so the "
        "detector is not a constant-pass."
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Launcher edited mid-run is detected by a spec hash at fan-in",
        "report_kind": "concurrency_report",
        "output_schema": SCHEMA,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "failure_class": "mid-run spec edit leaves contradictory tool-call caps live",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0163; "
            "_USER-PROMPTS.md:11011 / 10965-10983 (absent on this worktree)"
        ),
        "both_states": {
            "unedited_silent": unedited["pass"] and unedited.get("result") == "OK",
            "edited_drift": drift["pass"] and drift.get("result") == "CONTRACT-DRIFT",
            "unedited_n_drifted": unedited.get("n_drifted"),
            "edited_n_drifted": drift.get("n_drifted"),
            "unedited_caps": unedited.get("caps_observed"),
            "edited_caps": drift.get("caps_observed"),
        },
        "regression_seed": {
            "kind": "mid-run-tool-call-cap-edit",
            "cap_before": S.CAP_BEFORE,
            "cap_after": S.CAP_AFTER,
            "n": S.N,
            "split": S.SPLIT,
            "dispatch_hash": named.get("dispatch"),
            "fanin_hash": named.get("fanin"),
            "typed_result": "CONTRACT-DRIFT",
            "contradictory_caps_live_without_detector": True,
            "naive_compare_mode": "last-write-wins",
        },
        "contract_drift": {
            "kind": "CONTRACT-DRIFT",
            "named_hashes": named,
            "n_drifted": drift.get("n_drifted"),
            "drifted_units": drift.get("drifted_units"),
            "fanin_process": drift.get("fanin_process"),
            "pids_distinct": drift.get("pids_distinct"),
            "launcher_pid": drift.get("launcher_pid"),
            "fanin_hasher_pid": drift.get("fanin_hasher_pid"),
        },
        "tests": [
            {
                "id": "test_unedited_reports_no_drift",
                "name": "both-states control: an unedited run reports no drift",
                "command": P1,
                "result": "PASS" if unedited["pass"] else "FAIL",
                "observable": (
                    f"result={unedited.get('result')} n_drifted={unedited.get('n_drifted')} "
                    f"caps={unedited.get('caps_observed')} "
                    f"pids_distinct={unedited.get('pids_distinct')}"
                ),
            },
            {
                "id": "test_midrun_cap_edit_is_contract_drift",
                "name": (
                    "regression seed: the measured mid-run edit that left "
                    "contradictory tool-call caps live"
                ),
                "command": P1,
                "result": "PASS" if drift["pass"] else "FAIL",
                "observable": (
                    f"result={drift.get('result')} "
                    f"dispatch={named.get('dispatch')} fanin={named.get('fanin')} "
                    f"caps={drift.get('caps_observed')}"
                ),
            },
            {
                "id": "test_naive_last_write_wins_leaves_contradictory_caps",
                "name": (
                    "negative control: last-write-wins fan-in stays OK while "
                    "both tool_call_cap values remain live"
                ),
                "command": P2,
                "result": "PASS" if naive["pass"] else "FAIL",
                "observable": (
                    f"mutant_misses={naive.get('mutant_misses')} "
                    f"silent_on_good={naive.get('silent_on_good')}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0163-C1-UNEDITED",
                "kind": "both-states",
                "description": (
                    "Unedited cohort: all six units share one spec hash and cap=8; "
                    "fan-in is OK. The mid-run cap edit fires CONTRACT-DRIFT."
                ),
                "fired_on_bad_state": drift["pass"],
                "silent_on_good_state": unedited["pass"],
                "good_state_output": (
                    f"result={unedited.get('result')} n_drifted={unedited.get('n_drifted')}"
                ),
                "bad_state_output": f"result={drift.get('result')} named={named}",
            },
            {
                "id": "TST-0163-C2-LAST-WRITE-WINS",
                "kind": "mutation",
                "description": (
                    "Compare only the last dispatch hash (the measured defect). "
                    "Must stay OK while caps {8,32} are live on the same cohort."
                ),
                "fired_on_bad_state": naive.get("mutant_misses") is True,
                "silent_on_good_state": naive.get("silent_on_good") is True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Signal (a): each dispatch records sha256 of the spec file "
                    "bytes. After a mid-run tool_call_cap edit the first three "
                    f"units keep dispatch_hash={named.get('dispatch')} (cap={S.CAP_BEFORE})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0163/launcher.py:dispatch",
                "measured": {
                    "dispatch_hash": named.get("dispatch"),
                    "record_hashes": drift.get("record_hashes"),
                    "record_caps": drift.get("record_caps"),
                },
            },
            {
                "claim": (
                    "Signal (b): fan-in recomputes the current spec hash in a "
                    "separate process (hash_spec.py) and emits typed "
                    "CONTRACT-DRIFT naming both hashes when they differ."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0163/launcher.py:fan_in",
                "measured": {
                    "fanin_hash": named.get("fanin"),
                    "fanin_process": drift.get("fanin_process"),
                    "pids_distinct": drift.get("pids_distinct"),
                    "launcher_pid": drift.get("launcher_pid"),
                    "fanin_hasher_pid": drift.get("fanin_hasher_pid"),
                    "kind": "CONTRACT-DRIFT",
                },
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "both-states-unedited-vs-edit"},
            {"id": "probe2", "command": P2, "role": "independent-hash-reviewer"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0163-probe2-independent-hash",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-hashes saved dispatch-spec bytes and the post-edit "
                "spec via hash_spec.py in a child process, and re-runs the "
                "last-write-wins mutant. It does not author compare_mode."
            ),
        },
        "artifacts": arts,
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts with full-jitter backoff; a flake rate above "
                "1-in-20 reruns is filed as a DEFECT against the test, never "
                "absorbed as a retry"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/lib/handled-ledger.mjs and rules/common/fan-out-contract.md "
                    "are not on this worktree. The SUT under probes/TST-0163/ is the "
                    "measured launcher; production fan-out call sites are not patched."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Wire independent_digest into the live fan-out launcher when "
                    "those inputs are restored."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0163/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is on disk",
            }
        ],
        "platform": {
            "system": platform.system(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "min_bytes_threshold": 128,
        "defects": [],
        "cloud_ok": False,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
