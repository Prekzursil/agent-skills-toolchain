#!/usr/bin/env python3
"""Pack AUD-0046 detector-control sweep receipt.

Emits BLOCKED until an independent cross-vendor Codex review PASS that re-ran
ONLY probe 2 (catalog `reviewer_requirement`) is on disk; then SUCCESS. Never
stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0046"
OUT = "command-center/audit/AUD-0046-gate-detector-control-sweep.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0046/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when an independent cross-vendor Codex review PASS that
    re-ran ONLY probe 2 is on disk (catalog reviewer_requirement)."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-gate-baseline-census.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (PROBE / "probe2-gate-plant-revert-sweep.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-gate-baseline-census.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-gate-plant-revert-sweep.raw.txt").read_text(
        encoding="utf-8"
    )
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T21:20:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    gates_present_total = p1["gates_present_total"]
    gates_swept = p1["gates_swept_this_pass"]
    gates_not_yet_swept = p1["gates_not_yet_swept"]
    baseline_all_ok = bool(p1.get("baseline_all_ok"))
    p2_all_ok = bool(p2.get("all_ok"))
    gates_both_states_and_revert_ok = p2.get("gates_both_states_and_revert_ok")

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe1-gate-baseline-census.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe2-gate-plant-revert-sweep.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe1-gate-baseline-census.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe2-gate-plant-revert-sweep.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe1_gate_baseline_census.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/probe2_gate_plant_revert_sweep.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0046/fixtures/gate_cases.json",
            "control",
        ),
        L.art("command-center/audit/AUD-0041-ci-step-inventory.json", "supporting"),
        L.art("command-center/audit/AUD-0045-fail-open-gate-census.json", "supporting"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0046/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For each gate, does a deliberately planted defect of the exact class the "
        "gate claims to detect make it turn RED - and does the gate stay GREEN on "
        "the unmodified tree?"
    )
    headline = (
        f"{gates_present_total} gates present in the AUD-0041/AUD-0045 inventory; "
        f"{gates_swept} swept end-to-end this pass with a mutation matched to the "
        f"exact defect class each gate's own docstring names -- "
        f"{gates_both_states_and_revert_ok}/{gates_swept} confirmed baseline=0, "
        "mutated=non-zero, AND reverted=0 in the same scratch worktree instance; "
        f"{gates_not_yet_swept} gates carried forward as not-yet-swept residuals."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0046"
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0046-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0046-D-COVERAGE",
                "severity": "P2",
                "status": "open" if gates_not_yet_swept else "resolved",
                "summary": (
                    f"{gates_swept}/{gates_present_total} present gates swept with a "
                    f"matched plant+revert mutation this pass; {gates_not_yet_swept} "
                    "carried forward (fixtures/gate_cases.json -> not_yet_swept)."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe (probe2_gate_plant_revert_sweep.py, the plant -> "
                "RED -> revert -> GREEN sweep). Unavailable in-session; BLOCKED "
                "instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            f"FAILED:AUD-0046 gate-baseline+plant-revert-sweep probes measured "
            f"gates_present={gates_present_total} gates_swept={gates_swept} "
            f"both_states_and_revert_ok={gates_both_states_and_revert_ok}/{gates_swept}; "
            "blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "green-not-live",
                "detector-failure",
            ],
            "reason": (
                "Named probes completed: baseline exit-0 census measured for "
                f"{gates_swept} gates and a matched plant->RED->revert->GREEN cycle "
                "recorded for the same set inside one disposable scratch worktree, "
                "but catalog reviewer_requirement is unmet (cross-vendor Codex must "
                "re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"gates_present_total={gates_present_total} gates_swept={gates_swept} "
                f"baseline_all_ok={baseline_all_ok} p2_all_ok={p2_all_ok} "
                f"both_states_and_revert_ok={gates_both_states_and_revert_ok}/{gates_swept} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0046/probe2_gate_plant_revert_sweep.py "
                "and confirm the plant->RED->revert->GREEN cycle for all 8 swept gates "
                "before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0046/probe2_gate_plant_revert_sweep.py",
                    f"both_states_and_revert_ok={gates_both_states_and_revert_ok}/{gates_swept}",
                    0 if p2_all_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0046-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0046-D-COVERAGE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{gates_swept}/{gates_present_total} present gates swept with a "
                    f"matched plant+revert mutation this pass; {gates_not_yet_swept} "
                    "carried forward (fixtures/gate_cases.json -> not_yet_swept)."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0046",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 baseline census: {gates_swept} gates ("
                    f"of {gates_present_total} present in the AUD-0041/AUD-0045 "
                    "inventory) run unmodified inside a disposable scratch worktree; "
                    f"baseline_all_ok={baseline_all_ok} (every gate exits 0 on the "
                    "unmutated tree)."
                ),
                "CONFIRMED" if baseline_all_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0046/probe1-gate-baseline-census.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0046/probe1_gate_baseline_census.py",
                        raw1,
                        0 if baseline_all_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-gate-baseline-census.json",
                        json.dumps(
                            {
                                "gates_swept_this_pass": gates_swept,
                                "baseline_all_ok": baseline_all_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 plant-revert sweep: for each of {gates_swept} gates, "
                    "one mutation matched to the exact defect class its own docstring "
                    "names was planted inside the SAME scratch worktree instance the "
                    "baseline ran in, the gate turned RED (non-zero exit), the "
                    "mutation was reverted (git checkout/reset or move-back), and the "
                    "gate returned to 0 -- proving the RED was caused by the "
                    "mutation, not scratch-tree contamination. "
                    f"{gates_both_states_and_revert_ok}/{gates_swept} confirmed all "
                    "three states."
                ),
                "CONFIRMED" if p2_all_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0046/probe2-gate-plant-revert-sweep.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0046/probe2_gate_plant_revert_sweep.py",
                        raw2,
                        0 if p2_all_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-gate-plant-revert-sweep.json",
                        json.dumps(
                            {
                                "gates_both_states_and_revert_ok": gates_both_states_and_revert_ok,
                                "gates_swept": gates_swept,
                                "all_ok": p2_all_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0046-plant-red-revert-green",
                "name": (
                    "the sweep IS the both-states test; additionally require that "
                    "the mutation is reverted and the gate returns to 0, proving "
                    "the RED was caused by the mutation and not by scratch-tree "
                    "contamination"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0046/probe2_gate_plant_revert_sweep.py",
                "result": "PASS" if p2_all_ok else "FAIL",
                "assertions": gates_swept * 3,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0046-baseline-census",
                "name": "gate exit code on the unmodified scratch worktree must be 0",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0046/probe1_gate_baseline_census.py",
                "result": "PASS" if baseline_all_ok else "FAIL",
                "assertions": gates_swept,
                "output_tail": raw1[-600:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0046-C1",
                "mutation",
                (
                    "One planted mutation per gate, matched to the exact defect "
                    "class the gate's own docstring says it detects, must turn the "
                    "gate RED (non-zero exit) inside the scratch worktree."
                ),
                True,
                True,
                bad=f"mutated_exit != 0 for {gates_both_states_and_revert_ok}/{gates_swept} gates",
                good=f"baseline_all_ok={baseline_all_ok}",
            ),
            L.control(
                "AUD0046-C2",
                "mutation",
                (
                    "After reverting the planted mutation in the same scratch "
                    "worktree instance, the gate must return to exit 0 -- proving "
                    "the RED came from the mutation, not from scratch-tree "
                    "contamination."
                ),
                True,
                True,
                bad="reverted_exit != 0",
                good=f"gates_both_states_and_revert_ok={gates_both_states_and_revert_ok}/{gates_swept}",
            ),
            L.control(
                "AUD0046-C3",
                "other",
                "The sweep must never write to the live tree; every mutation and its revert happen inside a disposable `git worktree add --detach` checkout, removed at the end of the run.",
                True,
                True,
                bad="live_tree_mutated=true",
                good=f"live_tree_mutated={p2.get('live_tree_mutated')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-detector-control schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0046/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the tree; "
                "restore from the AUD-0092 backup, record the mutation, and escalate"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"Whether the {gates_not_yet_swept} present gates NOT yet swept "
                    "this pass (fixtures/gate_cases.json -> not_yet_swept: "
                    "claim_gate.py, the three per-lane ci_gate.py entry points, "
                    "rail_count_gate.py, vendor_satisfiability.py, "
                    "interpreter_floor_gate.py, hook_predeploy_gate.py, "
                    "ssot_drift_gate.py, unitgate.py, hooks/harness-bench/gate.py, "
                    "and the three pytest test files) turn RED on a mutation "
                    "matched to their own claimed defect class."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend fixtures/gate_cases.json with one matched mutation per "
                    "remaining gate (reading each gate's own docstring for the "
                    "exact defect class first, per this unit's method) and re-run "
                    "both probes; each addition is independently falsifiable the "
                    "same way the 8 already swept are."
                ),
            },
            {
                "claim": (
                    "Whether the same 8 gates also turn RED for OTHER defect "
                    "classes within their scope, not just the one mutation each "
                    "was tested against this pass (a gate can be correctly "
                    "sensitive to one defect shape and blind to a sibling one)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "For each of the 8 swept gates, enumerate every FAIL branch in "
                    "its source (grep for `return 1` / `FAILED:` sites) and add one "
                    "matched mutation per branch to fixtures/gate_cases.json."
                ),
            },
        ],
        "report": {
            "kind": "audit-detector-control",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0046-C1", "AUD0046-C2", "AUD0046-C3"],
            "observations": [
                {
                    "name": "gates_present_total",
                    "measured": gates_present_total,
                    "method": "AUD-0041 CI step inventory + AUD-0045 fail-open gate census (24 present of 26 considered)",
                    "anchor": "command-center/audit/AUD-0045-fail-open-gate-census.json",
                },
                {
                    "name": "gates_swept_this_pass",
                    "measured": gates_swept,
                    "method": "fixtures/gate_cases.json -> gates (one matched mutation per gate)",
                    "anchor": "command-center/p2-wave/probes/AUD-0046/fixtures/gate_cases.json",
                },
                {
                    "name": "baseline_all_ok",
                    "measured": baseline_all_ok,
                    "method": "run each swept gate unmodified inside a fresh scratch worktree; require exit 0",
                    "anchor": "command-center/p2-wave/probes/AUD-0046/probe1-gate-baseline-census.raw.txt",
                },
                {
                    "name": "gates_both_states_and_revert_ok",
                    "measured": gates_both_states_and_revert_ok,
                    "method": "plant matched mutation -> require non-zero -> revert -> require 0, same worktree instance",
                    "anchor": "command-center/p2-wave/probes/AUD-0046/probe2-gate-plant-revert-sweep.raw.txt",
                },
                {
                    "name": "gates_not_yet_swept",
                    "measured": gates_not_yet_swept,
                    "method": "gates_present_total minus gates_swept_this_pass",
                    "anchor": "command-center/p2-wave/probes/AUD-0046/fixtures/gate_cases.json",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-detector-control",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "gates_present_total": gates_present_total,
                "gates_swept_this_pass": gates_swept,
                "gates_not_yet_swept": gates_not_yet_swept,
                "baseline_all_ok": baseline_all_ok,
            },
            "probe2_summary": {
                "gates_swept": gates_swept,
                "gates_both_states_and_revert_ok": gates_both_states_and_revert_ok,
                "all_ok": p2_all_ok,
                "worktree_mode": p2.get("worktree_mode"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-gate-baseline-census.json",
        PROBE / "probe2-gate-plant-revert-sweep.json",
        PROBE / "probe1-gate-baseline-census.raw.txt",
        PROBE / "probe2-gate-plant-revert-sweep.raw.txt",
        PROBE / "fixtures" / "gate_cases.json",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0046 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
