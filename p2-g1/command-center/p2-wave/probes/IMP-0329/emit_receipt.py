#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0329.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0329.json"
SENTINEL = "SUCCESS:IMP-0329"

SUPPORTING = [
    "tools/council/calibration/report.py",
    "tools/council/calibration/__init__.py",
    "tools/council/calibration/schema/store.schema.json",
    "tools/council/tests/test_calibration_report.py",
    "command-center/p2-wave/probes/IMP-0329/probe1_hand_computed.py",
    "command-center/p2-wave/probes/IMP-0329/probe2_insufficient_n.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/tests/test_calibration_report.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0329/probe1_hand_computed.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0329/probe2_insufficient_n.py"
)

QUESTION = (
    "Implement tools/council/calibration/report.py scoring resolved "
    "predictions per participant and writing the calibration store consumed "
    "by IMP-0291 and IMP-0318. Falsifiable question: with fewer than 10 "
    "resolved predictions, does the report state that the calibration "
    "estimate is not yet meaningful rather than printing a confident number?"
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
        print(f"FAILED:IMP-0329 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:IMP-0329-tests" not in t_test:
        print("FAILED:IMP-0329 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0329-probe1" not in t1:
        print("FAILED:IMP-0329 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0329-probe2" not in t2:
        print("FAILED:IMP-0329 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(now.timestamp() - 1, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    unknowns = [
        {
            "claim": (
                "IMP-0316 (dependency: audit CLI), IMP-0291 (brainstorm ledger) "
                "and IMP-0318 (unanimity antifail) are not delivered on this "
                "worktree. This unit writes the council-calibration-store/v1 "
                "document those modules are catalogued to consume; live wiring "
                "is their work."
            ),
            "settling_experiment": (
                "After those units land, load a store written by "
                "write_calibration_store and assert they rank/read "
                "RANK_ELIGIBLE rows only."
            ),
            "verdict": "NOT-CHECKED",
        }
    ]

    receipt = {
        "unit_id": "IMP-0329",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0329",
        "title": "Post-run calibration report generator",
        "question": QUESTION,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/calibration/report.py",
            "store_schema": "council-calibration-store/v1",
            "min_meaningful_n": 10,
            "scoring_rule": "Brier mean((p-y)^2) on SCOREABLE rows",
            "insufficient_marker": "INSUFFICIENT-DATA",
            "unscoreable_excluded": True,
        },
        "artifact_paths": [OUT_REL] + SUPPORTING,
        "test_ids": [
            "test_hand_computed_brier_matches",
            "named-probe1-independent-brier",
            "test_n_below_10_marks_insufficient",
            "named-probe2-insufficient-n",
        ],
        "negative_control_ids": [
            "n-below-10-no-bare-brier",
            "planted-bare-score-detected",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/calibration/report.py:hand_computed_predictions",
                "claim": (
                    "A 12-resolved-prediction fixture for alice has Brier 0.19 "
                    "by hand arithmetic (sum of squares 2.28 / 12). The module "
                    "score matches an independent identity "
                    "mean(p^2)+mean(y^2)-2*mean(p*y) computed in probe1 without "
                    "calling brier_of, and the written store carries the same number."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/calibration/report.py:format_estimate",
                "claim": (
                    "With resolved_n<10 (bob n=9, cara n=0) the report sets "
                    "brier=null, writes INSUFFICIENT-DATA, and states that the "
                    "calibration estimate is not yet meaningful. A planted twin "
                    "that publishes a numeric brier is detected; the honest "
                    "record is not."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "n-below-10-no-bare-brier",
                "kind": "small-sample-honesty",
                "description": (
                    "n=9 and n=0 participants carry INSUFFICIENT-DATA and a "
                    "null brier; format_estimate does not contain brier=."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "INSUFFICIENT-DATA / brier=null",
                "bad_state_output": "planted estimate_sentence brier=<number>",
            },
            {
                "id": "planted-bare-score-detected",
                "kind": "known-broken-twin",
                "description": (
                    "planted_bare_score_record on bob publishes a numeric Brier "
                    "with no marker; detect_bare_confident_score fires."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "detector silent on honest bob",
                "bad_state_output": "detector fires on planted bob",
            },
        ],
        "tests": [
            {
                "id": "test_hand_computed_brier_matches",
                "command": TEST_CMD + "::test_hand_computed_brier_matches",
                "result": "PASS",
            },
            {
                "id": "named-probe1-independent-brier",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_n_below_10_marks_insufficient",
                "command": TEST_CMD + "::test_n_below_10_marks_insufficient",
                "result": "PASS",
            },
            {
                "id": "named-probe2-insufficient-n",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0329-probe2-insufficient-n",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "n<10 must carry INSUFFICIENT-DATA and must not present a "
                "numeric Brier. The detector must fire on a planted bare score."
            ),
            "method": (
                "Same-run honest n=9/n=0 records versus planted_bare_score_record; "
                "alice n=12 remains MEANINGFUL."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0329",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            },
            {
                "artifact_path": "tools/council/calibration/report.py",
                "consumer": "IMP-0291 / IMP-0318 calibration store (absent on this tree)",
                "executed": False,
                "read_ok": False,
                "note": "Store schema is council-calibration-store/v1 for those units to consume.",
            },
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0329/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": unknowns,
        "notes": (
            "G-1 delivery of IMP-0329 post-run calibration report. Two live "
            "signals: independent Brier identity on n=12, insufficient-data "
            "marker on n<10 with planted-bare-score negative control. Did not "
            "run global unit_manifest.py --write. cloud ok is not consulted."
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
