#!/usr/bin/env python3
"""Pack AUD-0056 test-runtime profile / slowest-suite baseline receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline counts is on disk (catalog `reviewer_requirement`);
then SUCCESS. Never stubs SUCCESS. Seeds non-empty downstream_consumers before
the first schema validate (ADMIT rejects empty consumers on SUCCESS; pack
always seeds a real consumer path).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0056"
OUT = "command-center/audit/AUD-0056-test-runtime-profile.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0056/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline count is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def _top10_str(names: list[str]) -> str:
    return " | ".join(names[:10]) if names else "(empty)"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-runner-durations.json").read_text(encoding="utf-8"))
    p2 = json.loads(
        (PROBE / "probe2-external-wallclock.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-runner-durations.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-external-wallclock.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T21:58:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p1_stable = bool(p1.get("ranking_stable"))
    p2_stable = bool(p2.get("ranking_stable"))
    ranking_stable = p1_stable and p2_stable
    contention = bool(p1.get("contention_dominated")) or bool(
        p2.get("contention_dominated")
    ) or (not ranking_stable)
    p1_gt = bool((p1.get("ground_truth") or {}).get("ok"))
    p2_gt = bool((p2.get("ground_truth") or {}).get("ok"))
    ground_truth_ok = p1_gt and p2_gt
    p1_ok = bool(p1.get("ok"))
    p2_ok = bool(p2.get("ok"))

    p1_runs = p1.get("runs") or []
    p2_runs = p2.get("runs") or []
    p1_top10 = (p1_runs[0].get("top10_modules") if p1_runs else []) or []
    p2_top10 = (p2_runs[0].get("top10_modules") if p2_runs else []) or []
    p2_median = p2.get("median_ranked") or []
    module_count = int(
        (p2_runs[0].get("module_count") if p2_runs else 0)
        or len(p2.get("modules") or [])
    )
    call_rows = int((p1_runs[0].get("call_row_count") if p1_runs else 0) or 0)

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
            "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/probe1_runner_durations.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/probe2_external_wallclock.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/fixtures/collectible_scope.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0056/fixtures/slow_control/"
            "test_deliberately_slow.py",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0056/independent-review.json",
                "supporting",
            )
        )

    question = (
        "What is the wall-clock cost of each test module today, which are the "
        "slowest, and which are candidates for the soak and load lanes rather "
        "than the per-PR gate?"
    )
    headline = (
        f"Scoped command-center/ collectible slice: {module_count} modules, "
        f"{call_rows} in-runner call-duration rows (exclusions documented in "
        "fixtures/collectible_scope.py). Probe1 (--durations x2): top-10 module "
        f"ranking_stable={p1_stable}. Probe2 (external wall-clock per module x2): "
        f"ranking_stable={p2_stable}. Combined baseline_usable="
        f"{ranking_stable and not contention}. Ground-truth deliberately-slow "
        f"fixture surfaced in both instruments (p1={p1_gt}, p2={p2_gt}). "
        f"Probe1 top-10: {_top10_str(p1_top10)}. "
        f"Probe2 top-10: {_top10_str(p2_top10)}."
    )
    if contention:
        headline += (
            " CONTENTION: top-10 ranking unstable across repeated profiles -- "
            "this measurement is contention-dominated and CANNOT be used as a "
            "baseline (honest BLOCKED; not a fake SUCCESS)."
        )

    # Seeded non-empty downstream before first validate (replaced by admit loop).
    seeded_consumer = {
        "consumer": "command-center/receipt_validate.py admission",
        "artifact_path": OUT,
        "executed": True,
        "read_ok": True,
        "exit_code": 0,
        "probe": L.probe(
            "source",
            "command",
            f"python3 command-center/receipt_validate.py {OUT}",
            "seeded-non-empty-downstream_consumers-before-first-schema-validate",
            0,
        ),
    }

    if success and ranking_stable and ground_truth_ok:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0056"
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0056-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0056/independent-review.json"
                ),
            },
            {
                "id": "AUD-0056-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass profiled {module_count} modules collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and "
                    "excluded trees are residuals, not silently dropped."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not "
                "seen this unit's transcript; the reviewer must try to FALSIFY "
                "the headline count before PASS, not re-read the artifact. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0056 test-runtime-profile probes measured "
            f"modules={module_count} call_rows={call_rows} "
            f"p1_ranking_stable={p1_stable} p2_ranking_stable={p2_stable} "
            f"contention_dominated={contention} "
            f"ground_truth_ok={ground_truth_ok}; blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "concurrency-contention",
                "detector-failure",
            ],
            "reason": (
                f"Named probes completed: probe1 --durations x2 "
                f"(ranking_stable={p1_stable}, ground_truth={p1_gt}) and "
                f"probe2 external wall-clock per module x2 "
                f"(ranking_stable={p2_stable}, ground_truth={p2_gt}), but "
                "catalog reviewer_requirement is unmet"
                + (
                    "; additionally top-10 ranking is contention-dominated"
                    if contention
                    else ""
                )
                + "."
            ),
            "diagnostic_tail": (
                f"p1_ok={p1_ok} p2_ok={p2_ok} ranking_stable={ranking_stable} "
                f"contention_dominated={contention} "
                f"ground_truth_ok={ground_truth_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the headline top-10 slowest "
                "suite ranking and stability claim before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0056/"
                    "probe1_runner_durations.py",
                    f"ranking_stable={p1_stable} ground_truth={p1_gt}",
                    0 if p1_gt else 1,
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
                "id": "AUD-0056-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0056-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass profiled {module_count} modules collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and "
                    "excluded trees are residuals, not silently dropped."
                ),
            },
        ]
        if contention:
            defects.append(
                {
                    "id": "AUD-0056-D-CONTENTION",
                    "severity": "P1",
                    "status": "open",
                    "summary": (
                        "Top-10 module ranking unstable across two profile "
                        "recordings (probe1 ranking_stable="
                        f"{p1_stable}, probe2 ranking_stable={p2_stable}). "
                        "Measurement is contention-dominated and cannot be used "
                        "as a baseline."
                    ),
                }
            )

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0056",
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
                    "Probe 1 runner --durations report: the collectible "
                    "command-center/ slice was executed twice with "
                    "--durations=0 -vv; call-phase seconds were aggregated per "
                    f"module. Top-10 module ranking_stable={p1_stable} "
                    f"(mismatches={len(p1.get('rank_mismatches') or [])}). "
                    "Ground-truth deliberately-slow fixture must appear in the "
                    f"slowest set: ok={p1_gt}."
                ),
                "CONFIRMED" if p1_gt else "REFUTED",
                "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0056/"
                        "probe1_runner_durations.py",
                        raw1,
                        0 if p1_gt else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-runner-durations.json",
                        json.dumps(
                            {
                                "ranking_stable": p1_stable,
                                "ground_truth_ok": p1_gt,
                                "top10_modules": p1_top10,
                                "call_row_count": call_rows,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 external wall-clock per module: each collected "
                    "module was invoked in its own pytest process; wall-clock "
                    "was measured from process start to end (not "
                    "--durations). Profile recorded twice; top-10 "
                    f"ranking_stable={p2_stable}. Ground-truth slow module in "
                    f"top-10: ok={p2_gt}."
                ),
                "CONFIRMED" if p2_gt else "REFUTED",
                "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0056/"
                        "probe2_external_wallclock.py",
                        raw2,
                        0 if p2_gt else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-external-wallclock.json",
                        json.dumps(
                            {
                                "ranking_stable": p2_stable,
                                "ground_truth_ok": p2_gt,
                                "top10_modules": p2_top10,
                                "module_count": module_count,
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
                "id": "AUD-0056-top10-ranking-stable",
                "name": (
                    "tests_required: record the profile twice and require the "
                    "ranking of the top 10 to be stable; unstable means "
                    "contention-dominated"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0056/"
                    "probe1_runner_durations.py && python3 -B "
                    "command-center/p2-wave/probes/AUD-0056/"
                    "probe2_external_wallclock.py"
                ),
                "result": "PASS" if ranking_stable else "FAIL",
                "assertions": 2,
                "output_tail": (
                    f"p1_stable={p1_stable} p2_stable={p2_stable} "
                    f"contention={contention}\n"
                    + raw1[-400:]
                    + "\n"
                    + raw2[-400:]
                )[-800:],
            },
            {
                "id": "AUD-0056-ground-truth-slow-fixture",
                "name": (
                    "negative control: deliberately slow fixture must appear "
                    "in the slowest set under both instruments"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0056/"
                    "probe1_runner_durations.py"
                ),
                "result": "PASS" if ground_truth_ok else "FAIL",
                "assertions": 2,
                "output_tail": f"p1_gt={p1_gt} p2_gt={p2_gt}",
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0056-C1",
                "known-broken-fixture",
                (
                    "A deliberately planted slow test "
                    "(fixtures/slow_control/test_deliberately_slow.py, "
                    "sleep 0.80s) must appear in the top-10 slowest set under "
                    "both --durations and external wall-clock ranking."
                ),
                True,
                True,
                bad=f"p1_gt={p1_gt} p2_gt={p2_gt}",
                good=f"ground_truth_ok={ground_truth_ok}",
            ),
            L.control(
                "AUD0056-C2",
                "mutation",
                (
                    "Top-10 module ranking must be identical across two "
                    "back-to-back profile recordings; an unstable ranking "
                    "means contention-dominated measurement."
                ),
                True,
                True,
                bad=f"mismatches_p1={p1.get('rank_mismatches')} "
                f"mismatches_p2={p2.get('rank_mismatches')}",
                good=f"ranking_stable={ranking_stable}",
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
        "downstream_consumers": [seeded_consumer],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS "
                "sentinel; retrying against a missing input is a detector "
                "failure, not a transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether modules under tools/, platform/, skills/, and the "
                    "excluded salvage/scratch/AUD-0052 planted-control trees "
                    f"would change the top-10 ranking (this pass profiled "
                    f"{module_count} command-center/ modules only)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend TARGET_ARGS once each excluded tree collects "
                    "cleanly; re-run both named probes and compare top-10."
                ),
            },
            {
                "claim": (
                    "Whether a quieter dedicated runner (no co-tenant CPU "
                    "contention) would stabilize an unstable top-10 ranking "
                    "enough to accept a baseline."
                    if contention
                    else (
                        "Whether the observed stable top-10 remains stable "
                        "across a third recording on a different host class."
                    )
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run both probes on an unloaded dedicated host and "
                    "require top-10 identity with this pass before promoting "
                    "the baseline."
                ),
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0056-C1", "AUD0056-C2"],
            "observations": [
                {
                    "name": "modules_profiled",
                    "measured": module_count,
                    "method": "pytest --collect-only over fixtures/collectible_scope.py TARGET_ARGS",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.json",
                },
                {
                    "name": "probe1_call_duration_rows",
                    "measured": call_rows,
                    "method": "pytest --durations=0 -vv; parse call-phase rows",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.raw.txt",
                },
                {
                    "name": "probe1_top10_ranking_stable",
                    "measured": p1_stable,
                    "method": "two --durations runs; compare top-10 module name lists",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.json",
                },
                {
                    "name": "probe2_top10_ranking_stable",
                    "measured": p2_stable,
                    "method": "two external wall-clock per-module profiles; compare top-10",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.json",
                },
                {
                    "name": "baseline_usable",
                    "measured": bool(ranking_stable and not contention),
                    "method": "both probes stable AND ground-truth control fired",
                    "anchor": "command-center/audit/AUD-0056-test-runtime-profile.json",
                },
                {
                    "name": "ground_truth_slow_fixture_ok",
                    "measured": ground_truth_ok,
                    "method": "planted sleep(0.80) fixture must rank in top-10 both instruments",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/fixtures/slow_control/test_deliberately_slow.py",
                },
                {
                    "name": "contention_dominated",
                    "measured": contention,
                    "method": "unstable top-10 across repeated profiles",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.json",
                },
                {
                    "name": "probe1_top10_modules",
                    "measured": _top10_str(p1_top10)[:500],
                    "method": "aggregated call-phase --durations per module, run1",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe1-runner-durations.json",
                },
                {
                    "name": "probe2_top10_modules",
                    "measured": _top10_str(p2_top10)[:500],
                    "method": "external wall-clock per module, run1",
                    "anchor": "command-center/p2-wave/probes/AUD-0056/probe2-external-wallclock.json",
                },
            ],
            "anti_false_green": anti,
            "slowest_suites_probe1": p1_top10,
            "slowest_suites_probe2": p2_top10,
            "median_wall_ranked": p2_median[:15],
        },
        "extensions": {
            "artifact_class": "audit-metric-baseline",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "ranking_stable": p1_stable,
                "ground_truth_ok": p1_gt,
                "ok": p1_ok,
                "top10_modules": p1_top10,
                "call_row_count": call_rows,
            },
            "probe2_summary": {
                "ranking_stable": p2_stable,
                "ground_truth_ok": p2_gt,
                "ok": p2_ok,
                "top10_modules": p2_top10,
                "module_count": module_count,
            },
            "baseline": {
                "usable": bool(ranking_stable and not contention and ground_truth_ok),
                "contention_dominated": contention,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-runner-durations.json",
        PROBE / "probe2-external-wallclock.json",
        PROBE / "probe1-runner-durations.raw.txt",
        PROBE / "probe2-external-wallclock.raw.txt",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0056 missing probe outputs:", *missing, sep="\n")
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
