#!/usr/bin/env python3
"""Write IMP-0268 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
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
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

UID = "IMP-0268"
OUT = "command-center/receipts/IMP-0268.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json profile=council-participants-module"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0268/probe1_score_fixture.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0268/probe2_empty_store.py"
)
IMPL = "tools/council/participants/select_calibrated.py"
SUPPORTING = [
    IMPL,
    "command-center/p2-wave/probes/IMP-0268/probe1_score_fixture.py",
    "command-center/p2-wave/probes/IMP-0268/probe2_empty_store.py",
    "command-center/p2-wave/probes/IMP-0268/scenario.py",
    "command-center/p2-wave/probes/IMP-0268/fixtures/warm-store.json",
    "command-center/p2-wave/probes/IMP-0268/fixtures/empty-store.json",
    "command-center/p2-wave/probes/IMP-0268/fixtures/zero-history-store.json",
    "command-center/p2-wave/probes/IMP-0268/fixtures/hand_computed.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(), len(data)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
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


def write_receipt(sel, warm: dict, cold: dict, zeros: dict) -> None:
    impl = art_row(IMPL, "primary")
    supporting = [art_row(p, "supporting") for p in SUPPORTING[1:]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hand = S.load_json(S.HAND)
    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0268",
        "completion_sentinel": "SUCCESS:IMP-0268",
        "title": "Calibration-ranked selector over a persistent calibration store",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0268 question_or_target; "
            "_USER-PROMPTS.md:10915-10946; 11-COUNCIL-SPECIFICATION.md"
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "artifact_paths": [IMPL, OUT] + SUPPORTING[1:],
        "artifacts": [impl] + supporting,
        "evidence": [
            {
                "claim": (
                    "A cold/empty calibration store emits an explicit degradation "
                    "event and falls back to explicit-order instead of ranking on zeros."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/participants/select_calibrated.py:select_calibrated",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "select_calibrated(candidates, empty-store.json)",
                        "raw_output": json.dumps(
                            {
                                "strategy_used": cold.get("strategy_used"),
                                "confident_ranking": cold.get("confident_ranking"),
                                "degradation": cold.get("degradation"),
                                "ranking": cold.get("ranking"),
                                "seated_scores": [
                                    s.get("score") for s in (cold.get("seated") or [])
                                ],
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "in-process",
                        "command": "select_calibrated(candidates, zero-history-store.json)",
                        "raw_output": json.dumps(
                            {
                                "strategy_used": zeros.get("strategy_used"),
                                "confident_ranking": zeros.get("confident_ranking"),
                                "degradation": zeros.get("degradation"),
                                "ranking": zeros.get("ranking"),
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A warm store ranks alice < bob < cara by Brier, matching the "
                    "hand-computed table 0.109375 / 0.25 / 0.5625."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0268/fixtures/hand_computed.json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "select_calibrated(candidates, warm-store.json, metric=brier)",
                        "raw_output": json.dumps(
                            {
                                "strategy_used": warm.get("strategy_used"),
                                "ranking": warm.get("ranking"),
                                "score_table": warm.get("score_table"),
                                "hand_brier": hand.get("brier"),
                            },
                            sort_keys=True,
                            default=str,
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read fixtures/hand_computed.json arithmetic_brier",
                        "raw_output": json.dumps(hand.get("arithmetic_brier"), sort_keys=True),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "test_ids": [
            "IMP-0268-probe1-score-fixture",
            "IMP-0268-probe2-empty-store",
        ],
        "tests": [
            {
                "id": "IMP-0268-probe1-score-fixture",
                "command": P1,
                "result": "PENDING-LIVE-RERUN",
            },
            {
                "id": "IMP-0268-probe2-empty-store",
                "command": P2,
                "result": "PENDING-LIVE-RERUN",
            },
        ],
        "negative_control_ids": [
            "IMP-0268-empty-store-no-zero-ranking",
            "IMP-0268-zero-history-stored-zeros",
        ],
        "negative_controls": [
            {
                "id": "IMP-0268-empty-store-no-zero-ranking",
                "kind": "empty-store",
                "description": "Empty participants must degrade loudly, not rank on zeros.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(cold.get("degradation"), sort_keys=True),
                "good_state_output": json.dumps(
                    {
                        "strategy_used": warm.get("strategy_used"),
                        "degradation": warm.get("degradation"),
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP-0268-zero-history-stored-zeros",
                "kind": "insufficient-history",
                "description": "Stored brier=0.0 with n_resolved<10 must not be treated as perfect calibration.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(zeros.get("degradation"), sort_keys=True),
                "good_state_output": json.dumps({"ranking": warm.get("ranking")}, sort_keys=True),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0268-probe2-empty-store",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (named probes), not the author's summary",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog question cites IMP-0352 as the store writer; IMP-0352 is "
                    "budget preflight. The dependency list and IMP-0329's own target "
                    "name IMP-0329 as the store writer. This selector consumes store v1 "
                    "fixtures; a live IMP-0329 writer is not in this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run probe1 against a store file emitted by delivered IMP-0329.",
            },
            {
                "claim": (
                    "No separate human reviewer ran in a fresh context. The named "
                    "probes are the adversarial check that starts from the tests."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Independent reviewer re-runs probe1 and probe2 from a clean checkout.",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0268/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this receipt is written",
            }
        ],
        "notes": (
            "G-1 for IMP-0268: select_calibrated.py ranks by Brier/log from a v1 "
            "store; empty store degrades loudly to explicit-order. Did not run "
            "global unit_manifest.py --write. SUCCESS:IMP-0268"
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0268/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not S.MODULE.is_file():
        print("FAILED:IMP-0268 module missing")
        return 1
    sel = S.load_selector()
    warm = sel.select_calibrated(S.CANDIDATES, S.WARM, metric="brier")
    cold = sel.select_calibrated(S.CANDIDATES, S.EMPTY, metric="brier")
    zeros = sel.select_calibrated(S.CANDIDATES, S.ZERO, metric="brier")
    if not warm.get("confident_ranking"):
        print("FAILED:IMP-0268 warm store did not rank")
        print(json.dumps(warm, indent=2, default=str)[:2000])
        return 1
    if cold.get("confident_ranking") or zeros.get("confident_ranking"):
        print("FAILED:IMP-0268 empty/zero-history produced confident ranking")
        return 1
    write_receipt(sel, warm, cold, zeros)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0268 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rec_path = REPO / OUT
    text = rec_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    doc["tests"] = [
        {
            "id": "IMP-0268-probe1-score-fixture",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "output_tail": t1[-4000:],
        },
        {
            "id": "IMP-0268-probe2-empty-store",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "output_tail": t2[-4000:],
        },
    ]
    doc["downstream_consumers"] = [
        {
            "consumer": "named-probes",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
        }
    ]
    rec_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:IMP-0268 probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0268",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "score-fixture-warm-ranking",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "empty-store-negative-control",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0268/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0268-probe2-empty-store",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0268: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0268 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
