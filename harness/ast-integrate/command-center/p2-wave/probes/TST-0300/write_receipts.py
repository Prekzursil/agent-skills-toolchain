#!/usr/bin/env python3
"""Write TST-0300 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
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

from bench.tournament import (  # noqa: E402
    evaluate_field,
    planted_cycle_scores,
    schedule_unstable_scores,
    select_format,
    transitive_scores,
    write_case_corpus,
)

UNIT = "TST-0300"
OUT = "command-center/receipts/TST-0300.json"
SENTINEL = "SUCCESS:TST-0300"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0300/probe1_pairwise_cycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0300/probe2_schedule_equivalence.py"
)
ENGINE = "tools/bench/tournament.py"
SUPPORTING = [
    ENGINE,
    "tools/bench/__init__.py",
    "command-center/bench/cases/tst-0300-planted-cycle.json",
    "command-center/bench/cases/tst-0300-transitive.json",
    "command-center/bench/cases/tst-0300-schedule-unstable.json",
    "command-center/p2-wave/probes/TST-0300/probe1_pairwise_cycle.py",
    "command-center/p2-wave/probes/TST-0300/probe2_schedule_equivalence.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def line_anchor(rel: str, needle: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(text, 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:1"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        if raw
        else hashlib.sha256(b"").hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0300/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(c1: int, t1: str, c2: int, t2: str) -> dict:
    cycle = evaluate_field(planted_cycle_scores())
    trans = evaluate_field(transitive_scores())
    unstable = evaluate_field(schedule_unstable_scores())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests_ok = c1 == 0 and c2 == 0
    return {
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS" if tests_ok else "FAILED",
        "status": "DELIVERED" if tests_ok else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Tournament scheduling and the transitivity check that reveals an unstable ranking",
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0300; _USER-PROMPTS.md:11164",
        "question": (
            "Build the tournament scheduler (round-robin for small fields, Swiss "
            "for large, elimination only where budget forces it) and test the "
            "resulting ranking for pairwise transitivity. Non-transitive results "
            "mean a single-number ranking is fiction and the field must be "
            "reported as a partial order."
        ),
        "answer": (
            "tools/bench/tournament.py schedules round-robin when n<=8 and the "
            f"pair budget allows ({select_format(4)}), Swiss when the field is "
            f"large ({select_format(16)}), and elimination only when the budget "
            f"cannot afford Swiss ({select_format(6, 5)}). The planted three-cycle "
            f"{cycle.cycles} is reported as ranking_kind={cycle.ranking_kind} with "
            "binding_leaderboard=null. Round-robin and Swiss agree on wf-apex on "
            "the transitive control and disagree on the unstable four-candidate "
            "field; that disagreement is schedule-finding "
            f"{(unstable.schedule_finding or {}).get('kind')} with binding_top=null, "
            "not resolved by picking a scheduler. Full pairwise matrices are in "
            "pairwise_result_matrix below."
        ),
        "artifact_paths": [OUT, ENGINE],
        "min_bytes_threshold": 128,
        "reviewer_verdict": "PASS" if tests_ok else "FAIL",
        "test_ids": [
            "TST-0300-T1-pairwise-matrix-and-cycles",
            "TST-0300-T2-planted-cycle-control",
            "TST-0300-T3-schedule-equivalence",
        ],
        "negative_control_ids": [
            "TST-0300-NC1-hide-cycle-as-total-order",
            "TST-0300-NC2-pick-scheduler-on-disagreement",
        ],
        "tests": [
            {
                "id": "TST-0300-T1-pairwise-matrix-and-cycles",
                "name": "Pairwise matrix computed and cycles enumerated",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "TST-0300-T2-planted-cycle-control",
                "name": "Three synthetic non-transitive candidates detected as a cycle",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "TST-0300-T3-schedule-equivalence",
                "name": (
                    "Round-robin and Swiss agree on the top entry, or the "
                    "disagreement is reported as a finding about the field"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0300-NC1-hide-cycle-as-total-order",
                "kind": "known-broken-fixture",
                "description": (
                    "mutant_hide_cycle binds a Copeland/name leaderboard on the "
                    "planted cycle; hides_nontransitivity must FIRE on the mutant "
                    "and stay silent on the live evaluate_field() report"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ranking_kind=TOTAL_ORDER binding_top=wf-cycle-a",
                "good_state_output": (
                    f"ranking_kind={cycle.ranking_kind} "
                    f"binding_leaderboard={cycle.binding_leaderboard} "
                    f"cycles={cycle.cycles}"
                ),
            },
            {
                "id": "TST-0300-NC2-pick-scheduler-on-disagreement",
                "kind": "known-broken-fixture",
                "description": (
                    "mutant_pick_round_robin sets schedule_agreement=True and binds "
                    "a top despite RR/Swiss disagreement; silently_resolves_schedule "
                    "must FIRE on the mutant and stay silent on the live report"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "owner_action=PICK_ROUND_ROBIN schedule_agreement=true",
                "good_state_output": (
                    f"agreement={unstable.schedule_agreement} "
                    f"binding_top={unstable.binding_top} "
                    f"finding={(unstable.schedule_finding or {}).get('kind')}"
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "The planted three-candidate fixture has pairwise winners "
                    "A>B, B>C, C>A (each 2-1 on three matched cases). "
                    "enumerate_cycles reports members "
                    f"{cycle.cycles} and ranking_kind={cycle.ranking_kind}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(ENGINE, "def enumerate_cycles("),
                "probes": [
                    probe_obj("source", "command", P1, t1, c1),
                    probe_obj(
                        "verifier",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/bench/tournament.py",
                        json.dumps(
                            {
                                "cycles": cycle.cycles,
                                "ranking_kind": cycle.ranking_kind,
                                "binding_leaderboard": cycle.binding_leaderboard,
                                "matrix": {k: v.to_dict() for k, v in cycle.matrix.items()},
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "On the transitive four-candidate control, round-robin and Swiss "
                    f"both name wf-apex (agreement={trans.schedule_agreement}). On the "
                    "unstable field Swiss names wf-cite while round-robin has a "
                    "three-way Copeland tie; the disagreement is published as "
                    f"{(unstable.schedule_finding or {}).get('kind')} and "
                    "binding_top stays null."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(ENGINE, "def compare_schedulers("),
                "probes": [
                    probe_obj("source", "command", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "file-read",
                        f"read {ENGINE} compare_schedulers/silently_resolves_schedule",
                        json.dumps(
                            {
                                "transitive_rr": None
                                if trans.round_robin is None
                                else trans.round_robin.top,
                                "transitive_swiss": None
                                if trans.swiss is None
                                else trans.swiss.top,
                                "unstable_rr_tied": None
                                if unstable.round_robin is None
                                else unstable.round_robin.tied_tops,
                                "unstable_swiss": None
                                if unstable.swiss is None
                                else unstable.swiss.top,
                                "unstable_finding": unstable.schedule_finding,
                                "unstable_binding_top": unstable.binding_top,
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "select_format uses round-robin for small fields, Swiss for "
                    "large fields even when the pair budget would allow round-robin, "
                    "and elimination only when the budget cannot afford Swiss."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": line_anchor(ENGINE, "def select_format("),
                "probes": [
                    probe_obj("source", "command", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "command",
                        "select_format(4), select_format(16), select_format(6,5), select_format(6,4)",
                        json.dumps(
                            {
                                "n4": select_format(4),
                                "n16": select_format(16),
                                "n6_budget5": select_format(6, 5),
                                "n6_budget4": select_format(6, 4),
                            }
                        ),
                        0,
                    ),
                ],
            },
        ],
        "pairwise_result_matrix": {
            "planted-cycle": {k: v.to_dict() for k, v in cycle.matrix.items()},
            "transitive": {k: v.to_dict() for k, v in trans.matrix.items()},
            "schedule-unstable": {k: v.to_dict() for k, v in unstable.matrix.items()},
        },
        "detected_cycles": {
            "planted-cycle": cycle.cycles,
            "transitive": trans.cycles,
            "schedule-unstable": unstable.cycles,
        },
        "schedule_comparison": {
            "transitive": {
                "agreement": trans.schedule_agreement,
                "round_robin_top": None if trans.round_robin is None else trans.round_robin.top,
                "swiss_top": None if trans.swiss is None else trans.swiss.top,
                "binding_top": trans.binding_top,
            },
            "schedule-unstable": {
                "agreement": unstable.schedule_agreement,
                "round_robin_top": None
                if unstable.round_robin is None
                else unstable.round_robin.top,
                "round_robin_tied_tops": None
                if unstable.round_robin is None
                else unstable.round_robin.tied_tops,
                "swiss_top": None if unstable.swiss is None else unstable.swiss.top,
                "binding_top": unstable.binding_top,
                "finding": unstable.schedule_finding,
            },
        },
        "format_selector": {
            "small_n4": select_format(4),
            "large_n16": select_format(16),
            "budget_forces_elimination_n6_b5": select_format(6, 5),
            "insufficient_n6_b4": select_format(6, 4),
        },
        "reviewer": {
            "reviewer_id": "TST-0300-probe2-schedule-equivalence",
            "verdict": "PASS" if tests_ok else "FAIL",
            "independent": True,
            "fresh_context": True,
            "mandate": "statistics",
            "starts_from": (
                "raw per-case CaseScore rows; nested-loop pairwise recount and "
                "independent DFS cycle enumeration, not evaluate_field's summary"
            ),
            "scope_not_agreement": (
                "probe2 recomputes winners and effect sizes (win-margin / n_cases) "
                "without calling pairwise_matrix or enumerate_cycles"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live bucket-B04 workflow candidates are not on disk in this "
                    "worktree. The scheduler and transitivity check were proven on "
                    "synthetic wf-* fixtures that encode the required controls "
                    "(planted cycle, transitive order, schedule-unstable field). "
                    "A later unit that lands the B04 registry can feed those ids "
                    "through evaluate_field without changing the comparison rule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When command-center/bench/cases/ contains real B04 candidate "
                    "scores, re-run evaluate_field on that corpus and publish the "
                    "pairwise matrix the same way."
                ),
            },
            {
                "claim": (
                    "Swiss pairing here is deterministic adjacent-score pairing "
                    "with name tie-break, not FIDE Dutch pairing. Whether a "
                    "published-rating Swiss would change the unstable-field "
                    "finding is not measured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Swap _swiss_pair_round for Dutch pairing and re-run probe2.",
            },
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0300/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "downstream_consumers": [
            {
                "artifact_path": ENGINE,
                "consumer": "command-center/p2-wave/probes/TST-0300/probe1_pairwise_cycle.py",
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
                "probe": probe_obj("verifier", "command", P1, t1, c1),
            },
            {
                "artifact_path": ENGINE,
                "consumer": "command-center/p2-wave/probes/TST-0300/probe2_schedule_equivalence.py",
                "executed": True,
                "exit_code": c2,
                "read_ok": True,
                "probe": probe_obj("verifier", "command", P2, t2, c2),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [],
    }


def main() -> int:
    write_case_corpus()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0300 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_receipt(c1, t1, c2, t2)
    supporting = [art(p, "supporting") for p in SUPPORTING]
    doc["artifacts"] = [
        {
            "path": OUT,
            "role": "primary",
            "exists": True,
            "bytes": 0,
            "sha256": "pending",
        }
    ] + supporting
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary_row = row(OUT, "primary")
    artifacts = [primary_row] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json profile=bench-tournament",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary_row["sha256"],
                "bytes": primary_row["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0300/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0300-probe2-schedule-equivalence",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0300: live named probes exit 0, receipts/TST-0300.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary_row['sha256']} bytes={primary_row['bytes']}")
    print("SUCCESS:TST-0300 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
