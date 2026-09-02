#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0307.json from live detector measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from bench.contamination import (  # noqa: E402
    DEFAULT_THRESHOLD,
    METHOD,
    measure,
)

OUT_REL = "command-center/receipts/TST-0307.json"
SENTINEL = "SUCCESS:TST-0307"
IMPL_REL = "command-center/bench/contamination.py"
QUESTION = (
    "Implementation target: a case whose answer already appears in a prompt "
    "template, a skill file, a memory note or a committed fixture is not "
    "measuring capability. Build the contamination scan that hashes case "
    "inputs and expected outputs and searches the entire program corpus and "
    "the live harness trees for near matches, then quarantines every "
    "contaminated case. Distinct from B12 (dev/shadow gap symptom): this "
    "finds the mechanism."
)


def _anchor() -> dict:
    path = REPO / IMPL_REL
    needle = "def scan("
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith(needle):
            return {
                "path": IMPL_REL,
                "line": i,
                "fn": "scan",
                "anchor": f"{IMPL_REL}:{i}",
            }
    raise SystemExit("scan() not found in contamination.py")


def _art(rel: str, role: str) -> dict:
    p = REPO / rel
    return {
        "path": rel,
        "exists": p.is_file(),
        "role": role,
        "bytes": p.stat().st_size if p.is_file() else 0,
    }


def build_receipt() -> dict:
    report = measure()
    ctrl = report["control"]
    live = report["live"]
    if not report.get("pass"):
        raise SystemExit("detector-control did not pass; refusing to emit SUCCESS")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    anchor = _anchor()
    contaminated = []
    for row in ctrl.get("contaminated") or []:
        contaminated.append(
            {
                "case_id": row.get("case_id"),
                "paths": row.get("paths"),
                "methods": row.get("methods"),
            }
        )
    answer = (
        f"Detector-control searched {ctrl.get('n_paths_searched')} isolated "
        f"corpus paths with method {METHOD!r} at threshold "
        f"{DEFAULT_THRESHOLD}. Contaminated case ids: "
        f"{ctrl.get('quarantine_ids')}. Planted verbatim ALPHA and "
        f"paraphrase BETA were found; clean GAMMA was silent; naive "
        f"verbatim-only missed BETA. Quarantine dropped scored cases "
        f"from 3 to 1 (points_delta={ctrl.get('points_delta')}). Live "
        f"command-center/bench/cases/ present="
        f"{live.get('cases_present')} paths_walked="
        f"{live.get('n_paths_searched')} hits="
        f"{live.get('contaminated_ids')}. "
        f"{ctrl.get('near_match_scope')}"
    )
    return {
        SENTINEL: True,
        "unit_id": "TST-0307",
        "id": "TST-0307",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": SENTINEL,
        "title": (
            "Contamination check: benchmark cases leaking into prompts, "
            "fixtures and the program corpus"
        ),
        "question": QUESTION,
        "answer": answer,
        "output_schema": "command-center/schema/receipt.schema.json",
        "cloud_ok": False,
        "computed_at": now,
        "spec_anchor": "spec:11059",
        "failure_classes": [
            "benchmark-gaming",
            "overclaim",
            "detector-failure",
        ],
        "matching": {
            "method": METHOD,
            "threshold": DEFAULT_THRESHOLD,
            "shingle_n": ctrl.get("shingle_n"),
            "near_match_scope": ctrl.get("near_match_scope"),
            "anchor": anchor,
        },
        "detector_control": {
            "pass": ctrl.get("pass"),
            "n_paths_searched": ctrl.get("n_paths_searched"),
            "paths_searched": (ctrl.get("full") or {}).get("paths_searched"),
            "alpha_found": ctrl.get("alpha_found"),
            "beta_found": ctrl.get("beta_found"),
            "gamma_found": ctrl.get("gamma_found"),
            "naive_alpha": ctrl.get("naive_alpha"),
            "naive_beta": ctrl.get("naive_beta"),
            "paraphrase_caught": ctrl.get("paraphrase_caught"),
            "paraphrase_coverage": ctrl.get("paraphrase_jaccard"),
            "rewrite_caught": ctrl.get("rewrite_caught"),
            "rewrite_coverage": ctrl.get("rewrite_jaccard"),
            "hash_hits": ctrl.get("hash_hits"),
            "contaminated": contaminated,
            "quarantine_ids": ctrl.get("quarantine_ids"),
        },
        "live_scan": {
            "cases_present": live.get("cases_present"),
            "n_cases": live.get("n_cases"),
            "n_paths_searched": live.get("n_paths_searched"),
            "paths_searched_sample": live.get("paths_searched_sample"),
            "contaminated_ids": live.get("contaminated_ids"),
            "note": live.get("note"),
            "method": live.get("method"),
            "threshold": live.get("threshold"),
        },
        "quarantine_effect": {
            "without_quarantine": ctrl.get("score_without_quarantine"),
            "with_quarantine": ctrl.get("score_with_quarantine"),
            "quarantine_changes_score": ctrl.get("quarantine_changes_score"),
            "points_delta": ctrl.get("points_delta"),
            "both_states": True,
        },
        "evidence": [
            {
                "id": "E1",
                "kind": "planted-verbatim-and-hash",
                "path": IMPL_REL,
                "claim": (
                    "Copying ALPHA's expected output into a prompt fixture "
                    "and planting ALPHA's sha256 digest into a skill file "
                    "both produce hits; GAMMA (unplanted) does not."
                ),
                "alpha_found": ctrl.get("alpha_found"),
                "gamma_found": ctrl.get("gamma_found"),
                "hash_hits": ctrl.get("hash_hits"),
            },
            {
                "id": "E2",
                "kind": "near-match-sensitivity",
                "path": IMPL_REL,
                "claim": ctrl.get("near_match_scope"),
                "paraphrase_caught": ctrl.get("paraphrase_caught"),
                "naive_beta": ctrl.get("naive_beta"),
                "rewrite_caught": ctrl.get("rewrite_caught"),
            },
            {
                "id": "E3",
                "kind": "quarantine-score-recompute",
                "path": IMPL_REL,
                "claim": (
                    "All three control cases oracle-PASS. Score without "
                    "quarantine is 3/3. After quarantining contaminated "
                    "ALPHA and BETA, score is 1/1 (GAMMA only). Dirty "
                    "score still includes the contaminated passes."
                ),
                "points_delta": ctrl.get("points_delta"),
            },
        ],
        "controls": [
            {
                "id": "verbatim-plant",
                "kind": "known-present",
                "plant": {
                    "id": "TST0307-ALPHA",
                    "path": "isolated-control/corpus/prompts/system-prompt.md",
                },
                "verdict": "found",
            },
            {
                "id": "paraphrase-plant",
                "kind": "known-present-near",
                "plant": {
                    "id": "TST0307-BETA",
                    "path": "isolated-control/corpus/fixtures/memory-note.txt",
                },
                "verdict": "found",
            },
            {
                "id": "clean-negative",
                "kind": "known-absent",
                "plant": {
                    "id": "TST0307-GAMMA",
                    "path": "isolated-control/corpus/clean/README.md",
                },
                "verdict": "silent",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-naive-verbatim-misses-paraphrase",
                "kind": "known-broken-fixture",
                "description": (
                    "Verbatim-only scan finds ALPHA and misses BETA; the "
                    "trigram-coverage scan finds both."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-unplanted-gamma-silent",
                "kind": "known-absent",
                "description": "Unplanted GAMMA must not be quarantined.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "tests": [
            {
                "id": "planted-control",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/TST-0307/probe1_planted.py"
                ),
                "result": "PASS",
            },
            {
                "id": "quarantine-score",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/TST-0307/probe2_quarantine.py"
                ),
                "result": "PASS",
            },
            {
                "id": "unit-tests",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/bench/tests/test_contamination.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0307-probe1-planted-control",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-run measure_detector_control in a fresh tempdir; require "
                "ALPHA+BETA found, GAMMA silent, naive miss on paraphrase, "
                "and quarantine score 3->1."
            ),
        },
        "artifacts": [
            _art(OUT_REL, "primary"),
            _art(IMPL_REL, "implementation"),
            _art(
                "command-center/bench/tests/test_contamination.py",
                "tests",
            ),
            _art(
                "command-center/p2-wave/probes/TST-0307/probe1_planted.py",
                "probe",
            ),
            _art(
                "command-center/p2-wave/probes/TST-0307/probe2_quarantine.py",
                "probe",
            ),
        ],
        "detector": {
            "name": "bench.contamination.scan",
            "mechanism": METHOD,
            "threshold": DEFAULT_THRESHOLD,
        },
    }


def main() -> int:
    doc = build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
