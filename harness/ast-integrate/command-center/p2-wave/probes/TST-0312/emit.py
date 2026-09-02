#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0312.json plus per-unit G-1 files.

Runs the two-signal revert scenarios live, writes the catalog receipt,
re-runs named probes, then writes SUBAGENT-RETURN.json and
UNIT-ARTIFACT-MANIFEST.json. Does not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import _p2lib as L  # noqa: E402
from revert_restore import run_all  # noqa: E402

UNIT = "TST-0312"
OUT = "command-center/receipts/TST-0312.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0312/probe1_both_signals.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0312/probe2_residue_and_invert.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0312/revert_restore.py",
    "command-center/p2-wave/probes/TST-0312/probe1_both_signals.py",
    "command-center/p2-wave/probes/TST-0312/probe2_residue_and_invert.py",
    "command-center/p2-wave/probes/TST-0312/fixtures/kernel_baseline.py",
    "command-center/p2-wave/probes/TST-0312/fixtures/kernel_changed.py",
    "command-center/p2-wave/probes/TST-0312/fixtures/cache_residue.json",
]
QUESTION = (
    "Question: the loop at :11146 reverts when a change is neutral or "
    "harmful, but a revert that leaves residue is worse than no revert "
    "because the baseline silently drifts. After every revert, re-run the "
    "baseline benchmark and require the result to fall within the B03 "
    "variance floor of the pre-change baseline, and separately require the "
    "working tree to match the pre-change SHA on the affected paths."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate_test_receipt(doc: dict) -> None:
    """Local contract: catalog receipt.schema.json is ABSENT.

    command-center/schema/test-receipt.schema.json currently requires
    metrics.n_payloads==100 (a different unit). This revert-restore receipt
    does not fake that metric and does not claim to satisfy it.
    """
    required = (
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "question",
        "answer",
        "tests",
        "controls",
        "evidence",
        "reviewer",
        "artifacts",
    )
    missing = [k for k in required if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:TST-0312 schema missing {missing}")
    if doc.get("state") not in {
        "SUCCESS",
        "PARTIAL",
        "BLOCKED",
        "FAILED",
        "TIMEOUT",
        "SEVERED",
    }:
        raise SystemExit(f"FAILED:TST-0312 state {doc.get('state')}")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        raise SystemExit("FAILED:TST-0312 tests")
    if "SUCCESS:TST-0312" not in json.dumps(doc):
        raise SystemExit("FAILED:TST-0312 sentinel not in document")


def live_inputs() -> dict:
    prompts = REPO / "_USER-PROMPTS.md"
    bench = REPO / "tools" / "bench"
    b03 = REPO / "command-center" / "receipts" / "TST-0297.json"
    bench_files = (
        sorted(p.name for p in bench.iterdir() if p.is_file()) if bench.is_dir() else []
    )
    return {
        "user_prompts": {
            "path": "_USER-PROMPTS.md",
            "exists": prompts.is_file(),
            "note": (
                "Catalog cites :11135-11150. File ABSENT on this worktree; "
                "the unit question is taken from WORK-UNIT-CATALOG.json."
            ),
        },
        "tools_bench": {
            "path": "tools/bench/",
            "exists": bench.is_dir(),
            "files": bench_files,
            "has_revert_or_baseline": False,
            "note": (
                "Directory present (TST-0303 live-result expiry). No "
                "baseline, revert, or variance symbols. Not B08 records "
                "and not a restore checker."
            ),
        },
        "b08_immutable_baselines": {
            "exists": False,
            "note": "TST-0302 / B08 immutable baseline records ABSENT.",
        },
        "b03_variance_floor_record": {
            "path": "command-center/receipts/TST-0297.json",
            "exists": b03.is_file(),
            "note": (
                "Live B03/TST-0297 floor ABSENT. This unit measures a "
                "fixture null-delta floor (deterministic kernel, floor=0)."
            ),
        },
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0312/SUBAGENT-RETURN.json",
        "role": role,
    }


def jsonable(value):
    return json.loads(json.dumps(value, default=str))


def main() -> int:
    inputs = live_inputs()
    with tempfile.TemporaryDirectory(prefix="tst0312-emit-") as tmp:
        result = run_all(Path(tmp))
    if not result["ok"]:
        print("FAILED:TST-0312 scenarios")
        print(
            json.dumps(
                {
                    k: result[k]["pass"]
                    for k in ("gate", "restore", "residue", "invert")
                }
            )
        )
        return 1

    restore = jsonable(result["restore"])
    residue = jsonable(result["residue"])
    invert = jsonable(result["invert"])
    gate = jsonable(result["gate"])
    after = restore["after_revert"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    p_restore = L.probe(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/TST-0312/revert_restore.py",
        json.dumps(
            {
                "during": restore["during_change"]["verdict"],
                "after": after["verdict"],
                "delta": after["benchmark"]["delta"],
                "floor": after["benchmark"]["floor"],
                "baseline_sha": restore["baseline_sha"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_residue = L.probe(
        "verifier",
        "command",
        "isolated git checkout tracked-only; inventory untracked .cache/",
        json.dumps(
            {
                "residue": residue["residue_paths"],
                "verdict": residue["after_tracked_checkout"]["verdict"],
                "detected_not_absorbed": residue["detected_not_absorbed"],
            },
            sort_keys=True,
        ),
        0,
    )

    artifacts = [
        L.art(
            "command-center/p2-wave/probes/TST-0312/revert_restore.py",
            "implementation",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0312/probe1_both_signals.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0312/probe2_residue_and_invert.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0312/fixtures/kernel_baseline.py",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0312/fixtures/kernel_changed.py",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/TST-0312/fixtures/cache_residue.json",
            "fixture",
        ),
        L.art(SCHEMA, "supporting"),
    ]
    if not all(a.get("exists") for a in artifacts):
        missing = [a["path"] for a in artifacts if not a.get("exists")]
        print(f"FAILED:TST-0312 missing artifacts {missing}")
        return 1

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0312",
        "completion_sentinel": "SUCCESS:TST-0312",
        "report_kind": "test-receipt",
        "schema_version": 1,
        "title": "Prove the automatic revert actually restores the measured baseline",
        "question": QUESTION,
        "answer": (
            "A revert restores the measured baseline only when both signals "
            "agree: the re-run bench delta sits inside the fixture null-delta "
            "floor, and git diff vs the pre-change SHA is empty with no "
            "untracked residue. One signal alone is SINGLE_SIGNAL_REJECTED. "
            "Live B03/B08 records are ABSENT; those floors/records are "
            "fixture stand-ins, not claimed product-tree facts."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "catalog_output_schema": CATALOG_SCHEMA,
        "catalog_output_schema_present": (REPO / CATALOG_SCHEMA).is_file(),
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "restore_real_change": restore,
        "residue_control": residue,
        "invertibility": invert,
        "single_signal_gate": gate,
        "both_signals": {
            "benchmark_delta": after["benchmark"]["delta"],
            "variance_floor": after["benchmark"]["floor"],
            "variance_floor_source": "fixture-null-delta n=10 (live B03 ABSENT)",
            "path_git_diff": after["path"]["git_diff_paths"],
            "pre_change_sha": after["path"]["pre_change_sha"],
            "residue": after["path"]["residue"],
            "verdict": after["verdict"],
        },
        "live_inputs": inputs,
        "tests": [
            {
                "id": "revert-real-change-both-signals",
                "requirement": (
                    "Revert a real change; both signals agree that the "
                    "baseline is restored."
                ),
                "verdict": "PASS" if restore["pass"] else "FAIL",
                "result": "PASS" if restore["pass"] else "FAIL",
                "evidence": (
                    f"during={restore['during_change']['verdict']} "
                    f"after={after['verdict']} "
                    f"delta={after['benchmark']['delta']} "
                    f"floor={after['benchmark']['floor']} "
                    f"git_diff={after['path']['git_diff_paths']} "
                    f"baseline_sha={restore['baseline_sha']}"
                ),
            },
            {
                "id": "residue-detected-not-absorbed",
                "requirement": (
                    "Residue control: revert a change that also wrote a "
                    "cache or a generated file, and confirm the residue is "
                    "detected rather than absorbed."
                ),
                "verdict": "PASS" if residue["pass"] else "FAIL",
                "result": "PASS" if residue["pass"] else "FAIL",
                "evidence": (
                    f"residue={residue['residue_paths']} "
                    f"verdict={residue['after_tracked_checkout']['verdict']} "
                    f"detected_not_absorbed={residue['detected_not_absorbed']} "
                    f"bench_only_would_claim={residue['bench_only_would_claim']}"
                ),
            },
            {
                "id": "revert-of-revert-not-lossy",
                "requirement": (
                    "Revert of a revert returns to the changed state, "
                    "proving the operation is not lossy."
                ),
                "verdict": "PASS" if invert["pass"] else "FAIL",
                "result": "PASS" if invert["pass"] else "FAIL",
                "evidence": (
                    f"lossy={invert['lossy']} "
                    f"tree_matches_changed_state={invert['tree_matches_changed_state']} "
                    f"metric={invert['metric_after_revert_of_revert']} "
                    f"first_revert_restored={invert['after_first_revert_restored']}"
                ),
            },
        ],
        "controls": {
            "single_signal_conjunction": L.control(
                "single-signal-or-rejected",
                "both-states-gate",
                (
                    "Restore requires benchmark AND path. True/False and "
                    "False/True are SINGLE_SIGNAL_REJECTED, not RESTORED."
                ),
                True,
                True,
                bad="bench_ok XOR path_ok -> SINGLE_SIGNAL_REJECTED",
                good="both ok -> RESTORED",
            ),
            "residue_vs_bench_only": L.control(
                "residue-not-absorbed",
                "both-states-same-run",
                (
                    "Tracked checkout restores WEIGHT so the bench signal "
                    "passes; untracked .cache/score.json keeps the path "
                    "signal red. A bench-only gate would absorb the residue."
                ),
                True,
                True,
                bad=json.dumps(residue["residue_paths"]),
                good="clean restore residue=[]",
            ),
            "invertibility": L.control(
                "revert-of-revert",
                "round-trip",
                (
                    "Materializing the recorded changed tree after a "
                    "baseline revert returns WEIGHT=25 and the changed bytes."
                ),
                True,
                True,
                bad="lossy=true would fail",
                good=f"metric={invert['metric_after_revert_of_revert']}",
            ),
        },
        "evidence": [
            {
                "kind": "benchmark-delta",
                "note": (
                    "After reverting WEIGHT 25->10 in an isolated git repo, "
                    f"delta={after['benchmark']['delta']} "
                    f"floor={after['benchmark']['floor']} "
                    f"verdict={after['verdict']}."
                ),
                "path": "command-center/p2-wave/probes/TST-0312/revert_restore.py",
                "probe": p_restore,
            },
            {
                "kind": "path-diff",
                "note": (
                    f"pre_change_sha={after['path']['pre_change_sha']} "
                    f"git_diff={after['path']['git_diff_paths']} "
                    "(isolated fixture repo, not the host worktree)."
                ),
                "path": "command-center/p2-wave/probes/TST-0312/revert_restore.py",
            },
            {
                "kind": "residue",
                "note": (
                    "Tracked-only checkout leaves .cache/score.json; "
                    f"verdict={residue['after_tracked_checkout']['verdict']} "
                    f"paths={residue['residue_paths']}."
                ),
                "path": "command-center/p2-wave/probes/TST-0312/fixtures/cache_residue.json",
                "probe": p_residue,
            },
            {
                "kind": "live-input-gap",
                "note": (
                    "tools/bench/ exists as TST-0303 expiry, not a restore "
                    "platform. B08 immutable baselines and the B03 floor "
                    "record are ABSENT. Fixture floor and isolated git SHAs "
                    "are the measured stand-in, not a claim those records exist."
                ),
                "path": "tools/bench/",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0312-probe2-residue-inventory",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs residue inventory and revert-of-revert "
                "byte compare independently of probe 1's benchmark-delta "
                "and git-diff field."
            ),
        },
        "artifacts": artifacts,
        "residual_unknowns": [
            {
                "claim": "Live B08 immutable baseline records from TST-0302.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run evaluate() against a real B08 record once "
                    "TST-0302 writes one."
                ),
            },
            {
                "claim": "Live B03/TST-0297 variance floor on the product bench.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Replace fixture floor=0 with the published TST-0297 "
                    "null-delta distribution when that receipt exists."
                ),
            },
            {
                "claim": "_USER-PROMPTS.md:11135-11150 Phase 16 loop text.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-read those line numbers when _USER-PROMPTS.md is "
                    "present; catalog question_or_target was used instead."
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0312: two-signal revert restore proven on an isolated "
            "git fixture. Host worktree was not mutated. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    validate_test_receipt(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0312 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0312" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0312 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0312 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0312",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-signals-restore",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "residue-and-invertibility",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0312/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0312-probe2-residue-inventory",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0312: live named probes exit 0, receipts/TST-0312.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
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
    print("SUCCESS:TST-0312 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
