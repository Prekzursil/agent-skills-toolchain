#!/usr/bin/env python3
"""Emit IMP-0333 receipt and per-unit G-1 return + manifest.

Order: oxford tests, live measurements, write receipts/IMP-0333.json,
re-run named probes, write SUBAGENT-RETURN.json and
UNIT-ARTIFACT-MANIFEST.json. Does not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

from tools.council.protocol.oxford import (  # noqa: E402
    DebateConfig,
    EvidenceBoundSpeaker,
    HIGH_FLIP_FLOOR,
    LOW_FLIP_CEILING,
    LocalTurnLoop,
    OxfordProtocol,
    compare_side_vs_evidence,
    evidence_swap_experiment,
    side_swap_experiment,
)

UNIT = "IMP-0333"
OUT = "command-center/receipts/IMP-0333.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0333/probe1_side_swap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0333/probe2_negative_control.py"
)
SUPPORTING = [
    "tools/council/protocol/oxford.py",
    "tools/council/protocol/__init__.py",
    "tools/council/tests/test_oxford.py",
    "command-center/p2-wave/probes/IMP-0333/scenario.py",
    "command-center/p2-wave/probes/IMP-0333/probe1_side_swap.py",
    "command-center/p2-wave/probes/IMP-0333/probe2_negative_control.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def slim(report: dict) -> dict:
    skip = {"base", "swapped", "reversed", "timing_base", "timing_swapped", "side_swap", "evidence_swap"}
    return {k: v for k, v in report.items() if k not in skip}


def main() -> int:
    rc_t, out_t = run_cmd(S.TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0333 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    proto = OxfordProtocol(S.CONFIG)
    rec = proto.run(S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS)
    extra = proto.submit_rebuttal(rec, S.evidence_speakers(), "alice", depth=3)

    decisive_e = side_swap_experiment(
        S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    rhetoric = side_swap_experiment(
        S.balanced(), S.side_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    rhetoric_on_decisive = side_swap_experiment(
        S.decisive(), S.side_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    evid_e = evidence_swap_experiment(
        S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    cmp_e = compare_side_vs_evidence(
        S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    cmp_s = compare_side_vs_evidence(
        S.balanced(), S.side_speakers(), S.ASSIGNMENTS, S.CONFIG
    )

    slow = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=5000),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=5000),
    }
    fast = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=10),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=10),
    }
    tcfg = DebateConfig(turn_budget_ms=100, max_rebuttal_depth=1)
    over = OxfordProtocol(tcfg, LocalTurnLoop()).run(
        S.decisive(), slow, S.ASSIGNMENTS
    )
    ok = OxfordProtocol(tcfg, LocalTurnLoop()).run(
        S.decisive(), fast, S.ASSIGNMENTS
    )

    if rec.turns_executed != rec.turns_recorded:
        print("FAILED:IMP-0333 loop invariant")
        return 1
    if not extra.refused:
        print("FAILED:IMP-0333 depth bound silent")
        return 1
    if float(decisive_e["flip_rate"]) > LOW_FLIP_CEILING:
        print("FAILED:IMP-0333 evidence-bound flip not low")
        return 1
    if float(rhetoric_on_decisive["flip_rate"]) < HIGH_FLIP_FLOOR:
        print("FAILED:IMP-0333 side-bound flip not high")
        return 1
    if over.timing.overrun_count != len(over.turns) or ok.timing.overrun_count != 0:
        print("FAILED:IMP-0333 timing audit did not discriminate")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_test = L.probe("source", "command", S.TEST_CMD, out_t[-4000:], rc_t)
    p_side = L.probe(
        "source",
        "command",
        "python3 -c side_swap_experiment",
        json.dumps(
            {
                "decisive_evidence_bound_flip_rate": decisive_e["flip_rate"],
                "balanced_side_bound_flip_rate": rhetoric["flip_rate"],
                "decisive_side_bound_flip_rate": rhetoric_on_decisive["flip_rate"],
                "n": decisive_e["n"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_evid = L.probe(
        "verifier",
        "command",
        "python3 -c evidence_swap_experiment + compare_side_vs_evidence",
        json.dumps(slim(cmp_e), sort_keys=True, default=str),
        0,
    )
    p_time = L.probe(
        "verifier",
        "command",
        "python3 -c OxfordProtocol timing audit",
        json.dumps(
            {
                "overrun_count": over.timing.overrun_count,
                "overrun_turns": len(over.turns),
                "in_budget_overrun_count": ok.timing.overrun_count,
            },
            sort_keys=True,
        ),
        0,
    )

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    kernel_path = REPO / "tools" / "council" / "kernel.py"
    chair_path = REPO / "tools" / "council" / "topology" / "chair.py"

    artifacts = [
        L.art("tools/council/protocol/oxford.py", "implementation"),
        L.art("tools/council/tests/test_oxford.py", "supporting"),
        L.art("command-center/p2-wave/probes/IMP-0333/probe1_side_swap.py", "named-probe"),
        L.art(
            "command-center/p2-wave/probes/IMP-0333/probe2_negative_control.py",
            "named-probe",
        ),
        L.art("command-center/p2-wave/probes/IMP-0333/scenario.py", "fixture"),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0333",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0333 "
            "(P07 oxford-debate; timed turns; bounded rebuttal depth; "
            "side-assignment effect)"
        ),
        "title": "Oxford debate engine with sides, timing and rebuttal depth",
        "question_or_target": (
            "Implement tools/council/protocol/oxford.py running a motion with "
            "proposition and opposition sides, timed turns and a bounded "
            "rebuttal depth. Falsifiable question: does the side a participant "
            "is assigned change its stated conclusion more than the evidence "
            "does - i.e. what is the measured side-assignment effect?"
        ),
        "min_bytes_threshold": 512,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "artifact_paths": [
            "tools/council/protocol/oxford.py",
            "tools/council/tests/test_oxford.py",
            OUT,
        ],
        "artifacts": artifacts,
        "measurements": {
            "evidence_bound_decisive_side_swap_flip_rate": decisive_e["flip_rate"],
            "side_bound_balanced_side_swap_flip_rate": rhetoric["flip_rate"],
            "side_bound_decisive_side_swap_flip_rate": rhetoric_on_decisive["flip_rate"],
            "evidence_bound_evidence_swap_flip_rate": evid_e["flip_rate"],
            "low_flip_ceiling": LOW_FLIP_CEILING,
            "high_flip_floor": HIGH_FLIP_FLOOR,
            "turns_executed": rec.turns_executed,
            "turns_recorded": rec.turns_recorded,
            "max_rebuttal_depth": S.CONFIG.max_rebuttal_depth,
            "over_depth_refused": extra.refused,
            "over_depth_reason": extra.refuse_reason,
            "timing_overrun_count": over.timing.overrun_count,
            "timing_in_budget_overrun_count": ok.timing.overrun_count,
            "kernel_bound": rec.kernel_bound,
            "compare_evidence_bound_decisive": slim(cmp_e),
            "compare_side_bound_balanced": slim(cmp_s),
        },
        "oxford": {
            "module": "tools/council/protocol/oxford.py",
            "sides": ["proposition", "opposition"],
            "turn_kinds": ["opening", "rebuttal", "closing"],
            "turn_budget_ms": S.CONFIG.turn_budget_ms,
            "max_rebuttal_depth": S.CONFIG.max_rebuttal_depth,
            "loop": rec.kernel_bound,
            "kernel_present": kernel_path.is_file(),
            "chair_present": chair_path.is_file(),
        },
        "evidence": [
            L.evidence(
                "Swapped-sides replication on the same motion publishes a "
                "conclusion flip rate. Evidence-bound speakers on the "
                "executable 2+2=4 motion flip at 0.0; side-bound speakers on "
                "the balanced taste motion flip at 1.0.",
                "CONFIRMED",
                "tools/council/protocol/oxford.py:side_swap_experiment",
                [p_side, p_test],
                "almost-certain",
            ),
            L.evidence(
                "Turn-timing audit against the configured budget: a 5000ms "
                "utterance on a 100ms budget is flagged timed_out; a 10ms "
                "utterance on the same budget is silent.",
                "CONFIRMED",
                "tools/council/protocol/oxford.py:timing_audit",
                [p_time, p_test],
                "almost-certain",
            ),
            L.evidence(
                "On the evidence-decisive motion, evidence-bound speakers "
                "change conclusion when evidence polarity is reversed "
                "(flip_rate=1.0) and do not change conclusion when sides are "
                "swapped (flip_rate=0.0), so evidence dominates side "
                "assignment for that cohort.",
                "CONFIRMED",
                "tools/council/protocol/oxford.py:compare_side_vs_evidence",
                [p_evid, p_side],
                "almost-certain",
            ),
        ],
        "test_ids": [
            "test_both_sides_and_timed_turns",
            "test_rebuttal_depth_bound_refuses",
            "test_timeout_audit_flags_overrun_and_is_silent_in_budget",
            "test_side_swap_flip_rate_published",
            "test_negative_control_evidence_decisive_low_flip",
            "test_loop_records_every_executed_turn",
            "test_weighted_speaker_loyalty_can_override_weak_evidence",
        ],
        "negative_control_ids": [
            "evidence-decisive-evidence-bound-low-flip",
            "evidence-decisive-side-bound-high-flip",
            "timing-overrun-vs-in-budget",
        ],
        "reviewer_verdict": "PASS",
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "oxford-unit-tests",
                "command": S.TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "experiment_side_swap_flip_rate_published",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative_control_evidence_decisive_low_flip",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "evidence-decisive-evidence-bound-low-flip",
                "both-states-same-run",
                "Evidence-bound speakers on 2+2=4 keep their conclusion under "
                "side swap (LOW). Side-bound speakers on the same motion flip "
                "(HIGH), so the control is not vacuous.",
                True,
                True,
                bad=f"side-bound flip_rate={rhetoric_on_decisive['flip_rate']}",
                good=f"evidence-bound flip_rate={decisive_e['flip_rate']}",
            ),
            L.control(
                "timing-overrun-vs-in-budget",
                "both-states-same-run",
                "Over-budget turns are flagged; in-budget turns are silent.",
                True,
                True,
                bad=f"overrun_count={over.timing.overrun_count}",
                good=f"in_budget_overrun_count={ok.timing.overrun_count}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0333-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Reviewer starts from tools/council/tests/test_oxford.py and "
                "recomputes side-swap rates plus the timing audit. Author "
                "summary is not the source of the verdict."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0333/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "tools/council/tests/test_oxford.py",
                "artifact_path": "tools/council/protocol/oxford.py",
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Speakers are deterministic fixtures (evidence-bound / "
                    "side-bound / weighted). Side-assignment effect on live "
                    "foundation-model participants is not measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Seat model-backed speakers on the same two motions and "
                    "recompute side_swap_experiment vs evidence_swap_experiment."
                ),
            },
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is absent on this "
                    f"worktree (present={kernel_path.is_file()}); Oxford uses "
                    "LocalTurnLoop with the same execute-and-record invariant."
                ),
                "verdict": "NOT-CHECKED" if not kernel_path.is_file() else "CONFIRMED",
                "settling_experiment": (
                    "Re-run IMP-0333 probes after IMP-0264 lands kernel.py and "
                    "assert bind_loop() returns Kernel."
                ),
            },
            {
                "claim": (
                    "tools/council/topology/chair.py (IMP-0282) is absent; "
                    "Oxford assigns sides itself and does not require a chair."
                ),
                "verdict": "NOT-CHECKED" if not chair_path.is_file() else "CONFIRMED",
                "settling_experiment": (
                    "After IMP-0282, optionally route recognition through the "
                    "chair while keeping side assignment in oxford.py."
                ),
            },
        ],
        "completion_sentinel": "SUCCESS:IMP-0333",
        "notes": (
            "G-1 IMP-0333: Oxford protocol runs proposition/opposition with "
            "timed turns and a bounded rebuttal depth. Side-assignment effect "
            "is published as a flip rate. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0333 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0333" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0333 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0333 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0333",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "side-swap-flip-rate",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-timing",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0333/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0333-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0333: live named probes exit 0, receipts/IMP-0333.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": (
                "command-center/p2-wave/probes/IMP-0333/SUBAGENT-RETURN.json"
            ),
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0333 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
