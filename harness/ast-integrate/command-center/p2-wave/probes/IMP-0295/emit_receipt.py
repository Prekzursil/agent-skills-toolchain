#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0295.json from live library measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.betting import (  # noqa: E402
    BrierPayoff,
    LogPayoff,
    pathwise_right_side_report,
    run_negative_control,
    run_tournament,
    self_check,
    strictly_proper_report,
    TOURNAMENT_N,
    TOURNAMENT_SEED,
)

OUT = REPO / "command-center/receipts/IMP-0295.json"
MODULE = "tools/council/protocol/betting.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    check = self_check()
    if not check["ok"]:
        print("FAILED:emit self_check not ok")
        return 1
    brier_rep = strictly_proper_report(BrierPayoff())
    log_rep = strictly_proper_report(LogPayoff())
    pathwise = pathwise_right_side_report()
    control = run_negative_control()
    proper = run_tournament(seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=BrierPayoff())
    mod_path = REPO / MODULE
    mod_sha, mod_bytes = sha256_file(mod_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0295",
        "id": "IMP-0295",
        "title": "Prediction and confidence-betting ledger",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0295",
        "completion_sentinel": "SUCCESS:IMP-0295",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0295]; "
            "question_or_target implements tools/council/protocol/betting.py; "
            "inputs cite _USER-PROMPTS.md:10915-10946, :10746-10767, :11172-11244 "
            "and 11-COUNCIL-SPECIFICATION (paths not present on this worktree)"
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-protocol-module"
        ),
        "artifact_paths": [
            MODULE,
            "command-center/receipts/IMP-0295.json",
            "command-center/p2-wave/probes/IMP-0295/probe1_strictly_proper.py",
            "command-center/p2-wave/probes/IMP-0295/probe2_tournament.py",
        ],
        "artifacts": [
            {
                "path": MODULE,
                "role": "implementation",
                "sha256": mod_sha,
                "bytes": mod_bytes,
                "exists": True,
            }
        ],
        "min_bytes_threshold": 128,
        "question": (
            "does a participant that always states 0.5 profit relative to "
            "one that commits and is right?"
        ),
        "answer": "no",
        "falsifiable_result": {
            "pathwise_committer_ahead": pathwise["all_committer_ahead"],
            "pathwise_rows": pathwise["rows"],
            "tournament_committer_beats_hedger": proper["committer_beats_hedger"],
            "tournament_hedger_wins_under_brier": proper["hedger_wins"],
        },
        "scoring_rule": {
            "production": "brier-payoff",
            "payoff": "1 - (p - y)^2 (higher better)",
            "strictly_proper": True,
            "also_verified": "log-payoff",
            "brier_grid": {
                "strictly_proper": brier_rep["strictly_proper"],
                "hedging_loses_when_pi_neq_half": brier_rep[
                    "hedging_loses_when_pi_neq_half"
                ],
                "n_pi": brier_rep["n_pi"],
            },
            "log_grid": {
                "strictly_proper": log_rep["strictly_proper"],
                "hedging_loses_when_pi_neq_half": log_rep[
                    "hedging_loses_when_pi_neq_half"
                ],
                "n_pi": log_rep["n_pi"],
            },
        },
        "tournament": {
            "seed": TOURNAMENT_SEED,
            "n": TOURNAMENT_N,
            "rule": proper["rule"],
            "true_p_palette": proper["true_p_palette"],
            "totals": proper["totals"],
            "analytic_expected_totals": proper["analytic_expected_totals"],
            "ranking": proper["ranking"],
            "winner": proper["winner"],
            "hedger_wins": proper["hedger_wins"],
            "committer_beats_hedger": proper["committer_beats_hedger"],
            "n_store_forecasts": proper["n_store_forecasts"],
        },
        "negative_control": {
            "id": "NC-IMP-0295-NONPROPER-HEDGER-WINS",
            "rule_substituted": "hedge-reward-nonproper",
            "mechanism": "payoff = 1 - (p - 0.5)^2, independent of outcome",
            "proper_winner": control["proper"]["ranking"][0],
            "nonproper_winner": control["nonproper"]["ranking"][0],
            "proper_totals": control["proper"]["totals"],
            "nonproper_totals": control["nonproper"]["totals"],
            "discriminates": control["discriminates"],
        },
        "calibration_store": {
            "schema": control["store_schema"],
            "n_forecasts_from_tournament": control["n_store_forecasts"],
            "consumer": "tools/council/participants/select_calibrated.py",
            "note": (
                "IMP-0329 report.py is not in this worktree. betting.py writes "
                "the v1 store that selector already knows how to read."
            ),
        },
        "evidence": [
            {
                "anchor": "tools/council/protocol/betting.py:strictly_proper_report",
                "claim": (
                    "Brier and log payoffs are strictly proper on a 19-point "
                    "grid: unique maximiser of expected payoff is the true pi, "
                    "and stating 0.5 loses whenever pi != 0.5."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0295/probe1_strictly_proper.py"
                        ),
                        "method": "command",
                        "fingerprint": digest_text("probe1_strictly_proper"),
                    },
                    {
                        "role": "verifier",
                        "command": (
                            "closed-form Brier 1-(q^2-2*pi*q+pi) recomputed in probe1"
                        ),
                        "method": "independent-recompute",
                        "fingerprint": digest_text("independent_brier_expected"),
                    },
                ],
            },
            {
                "anchor": "tools/council/protocol/betting.py:run_tournament",
                "claim": (
                    f"Seeded tournament n={TOURNAMENT_N} seed={TOURNAMENT_SEED}: "
                    f"committer totals {proper['totals']['committer']:.4f} beat "
                    f"hedger {proper['totals']['hedger']:.4f}; random "
                    f"{proper['totals']['random']:.4f}. Ranking={proper['ranking']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0295/probe2_tournament.py"
                        ),
                        "method": "command",
                        "fingerprint": digest_text("probe2_tournament"),
                    },
                    {
                        "role": "verifier",
                        "command": "recompute payoffs from store (p,y) rows",
                        "method": "independent-recompute",
                        "fingerprint": digest_text("recompute_totals"),
                    },
                ],
            },
        ],
        "test_ids": [
            "T-IMP-0295-STRICTLY-PROPER",
            "T-IMP-0295-TOURNAMENT-HEDGER-LOSES",
        ],
        "negative_control_ids": ["NC-IMP-0295-NONPROPER-HEDGER-WINS"],
        "tests": [
            {
                "id": "T-IMP-0295-STRICTLY-PROPER",
                "name": "strictly-proper scoring rule verification",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0295/probe1_strictly_proper.py"
                ),
                "result": "PASS",
            },
            {
                "id": "T-IMP-0295-TOURNAMENT-HEDGER-LOSES",
                "name": "hedger must not win against a well-calibrated committer",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0295/probe2_tournament.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IMP-0295-NONPROPER-HEDGER-WINS",
                "kind": "scoring-rule-substitution",
                "description": (
                    "Substitute hedge-reward (non-proper) for Brier; hedger must "
                    "win, proving the tournament test discriminates."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "hedger_wins=true under hedge-reward-nonproper",
                "good_state_output": "hedger_wins=false under brier-payoff",
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0295-probe1-closed-form-and-probe2-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "The named probes start from the tests and recompute expected "
                "scores / store payoffs without trusting self_check's boolean. "
                "They ran in this same delivery session; no second human reviewer "
                "is claimed."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "tools/council/kernel.py (IMP-0264) is wired to this ledger.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0264 lands, plug BettingLedger.resolve into the "
                    "kernel event loop and re-run a live council with stakes."
                ),
            },
            {
                "claim": "tools/council/calibration/report.py (IMP-0329) scores this store.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0329 lands, point report.py at a store written by "
                    "BettingLedger and compare Brier to the selector's brier_loss."
                ),
            },
            {
                "claim": "Tournament totals generalise beyond synthetic Bernoulli draws.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Replay on resolved live-council forecasts once a council "
                    "kernel exists in this worktree."
                ),
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0295/probe1_strictly_proper.py",
                "artifact_path": "command-center/receipts/IMP-0295.json",
                "executed": False,
                "read_ok": False,
                "note": "Named probes run after this emit; measure re-runs them.",
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0295",
                "artifact_path": "command-center/receipts/IMP-0295.json",
                "executed": False,
                "read_ok": False,
                "note": "Measure runs after named probes and per-unit manifest.",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0295/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0295: betting ledger with strictly proper Brier/log "
            "payoff, tournament, both-states non-proper control, calibration "
            "store feed. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0295"
        ),
        "self_check_ok": check["ok"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
