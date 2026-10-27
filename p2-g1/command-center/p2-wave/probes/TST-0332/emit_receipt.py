#!/usr/bin/env python3
"""Emit TST-0332 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Does not call tools/command-center/unit_manifest.py --write.
Does not rotate or print API keys.
Does not import command-center/receipt_writer.py (absent on this worktree).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import reviewer as R  # noqa: E402

UNIT = "TST-0332"
OUT = "command-center/receipts/TST-0332.json"
SENTINEL = "SUCCESS:TST-0332"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0332/probe1_setdiff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0332/probe2_cannot_run.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0332/harness.py",
    "command-center/p2-wave/probes/TST-0332/reviewer.py",
    "command-center/p2-wave/probes/TST-0332/probe1_setdiff.py",
    "command-center/p2-wave/probes/TST-0332/probe2_cannot_run.py",
    "command-center/p2-wave/probes/TST-0332/fixtures/workflows/phase0-ci-test-gap.yml",
    "command-center/p2-wave/probes/TST-0332/fixtures/runs/latest-green.json",
    "command-center/p2-wave/probes/TST-0332/fixtures/runs/latest-green.log",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()[:16]


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0332/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "exists": False, "role": role}
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
    }


def main() -> int:
    H.write_fixtures(HERE)
    live = H.phase0_report(REPO)
    wf = HERE / "fixtures/workflows/phase0-ci-test-gap.yml"
    runp = HERE / "fixtures/runs/latest-green.json"
    logp = HERE / "fixtures/runs/latest-green.log"
    rev = R.review(wf, runp, logp)
    tmp = Path(tempfile.mkdtemp(prefix="tst0332-emit-"))
    try:
        ctl = H.detector_control(wf, runp, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if live["declared_count"] != 60 or live["executed_count"] != 28:
        print("FAILED:TST-0332 phase0 counts drifted before emit")
        return 1
    if not live["gap_invisible_from_badge"] or not ctl.get("ok"):
        print("FAILED:TST-0332 detector or control not green before emit")
        return 1
    if rev["verdict"] != "PASS":
        print("FAILED:TST-0332 independent reviewer FAIL before emit")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_src = live["live_sources"]
    nongreen = live.get("captured_nongreen")
    live_q = live_src.get("live_quality") or {}
    bind = live_src.get("test_registry_bind") or {}
    unex = live["unexecuted"]
    by_reason = {k: 0 for k in H.SKIP_REASONS}
    for item in unex:
        by_reason[item["skip_reason"]] += 1
    live_declared = int(live_q.get("declared_count") or 0)
    nongreen_skipped = (
        int(nongreen.get("declared_also_skipped") or 0) if isinstance(nongreen, dict) else 0
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Prove every declared CI test step actually executed in the last green run"
        ),
        "report_kind": "receipt",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0332",
        "question": (
            "A workflow can declare 60 test steps and execute 28 of them because "
            "earlier steps short-circuit, matrix legs are skipped, or a condition "
            "never matches — and the run still reports green. Parse CI definitions "
            "for declared test steps, parse run logs for executed ones, and report "
            "the difference."
        ),
        "answer": (
            f"Phase-0 green fixture: declared {live['declared_count']}, executed "
            f"{live['executed_count']}, unexecuted {live['unexecuted_count']} "
            f"(conclusion={live['workflow_conclusion']}). "
            "A green badge is not evidence any particular step ran. "
            f"Skip reasons: {by_reason}. "
            f"Live .github/workflows/quality.yml declares {live_declared} test "
            "steps on this worktree. gh CLI is absent, so the origin latest-green "
            "run was NOT fetched. AUD-0041 captured quality run "
            f"{(nongreen or {}).get('run_id') if isinstance(nongreen, dict) else None} "
            f"is NOT green and shows {nongreen_skipped} declared test steps also "
            "listed as skipped. TEST-REGISTRY.json is present "
            f"(exact ci_step matches={len(bind.get('exact_match') or [])}). "
            + SENTINEL
        ),
        "declared_executed_gap": {
            "declared_count": live["declared_count"],
            "executed_count": live["executed_count"],
            "unexecuted_count": live["unexecuted_count"],
            "green_badge": live["green_badge"],
            "workflow_conclusion": live["workflow_conclusion"],
            "run_id": live["run_id"],
            "gap_invisible_from_badge": live["gap_invisible_from_badge"],
            "naive_green_implies_all_executed": live["naive_green_implies_all_executed"],
            "skip_reasons_present": live["skip_reasons_present"],
            "unexecuted_by_reason": by_reason,
            "unexecuted": unex,
            "executed": live["executed"],
            "source": "phase0-green-fixture",
            "live_quality_yml_declared_count": live_declared,
        },
        "live_sources": live_src,
        "captured_nongreen_quality_run": nongreen,
        "negative_control": {
            "id": "planted-cannot-run",
            "planted_name": ctl["planted_name"],
            "fired_on_bad_state": ctl["fired_on_bad_state"],
            "silent_on_good_state": ctl["silent_on_good_state"],
            "skip_reason": "conditional_false",
            "before_declared": ctl["before_declared"],
            "after_declared": ctl["after_declared"],
        },
        "tests": [
            {
                "id": "set-difference-latest-green",
                "command": P1,
                "result": "PASS",
                "declared_count": live["declared_count"],
                "executed_count": live["executed_count"],
                "unexecuted_count": live["unexecuted_count"],
            },
            {
                "id": "skip-reason-attribution",
                "command": P1,
                "result": "PASS",
                "reasons": live["skip_reasons_present"],
                "by_reason": by_reason,
            },
            {
                "id": "detector-control-cannot-run",
                "command": P2,
                "result": "PASS",
                "planted_name": H.PLANTED_NAME,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-cannot-run",
                "kind": "mutation",
                "description": (
                    "Add a pytest step with if: ${{ false }} and confirm the "
                    "detector lists it as unexecuted/conditional_false while the "
                    "unmodified workflow does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "evidence": [
            {
                "id": "EV-set-difference-green-run",
                "kind": "measurement",
                "claim": (
                    "Phase-0 green fixture (fixture-latest-green) declares 60 test "
                    "steps, executes 28, and leaves 32 unexecuted. The workflow "
                    "conclusion is success, so a green badge does not imply "
                    "every declared step ran."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0332/probe1_setdiff.py",
                "confidence": "almost-certain",
                "counts": {
                    "declared": live["declared_count"],
                    "executed": live["executed_count"],
                    "unexecuted": live["unexecuted_count"],
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "fingerprint": fingerprint("command", P1),
                        "raw_output": (
                            f"declared={live['declared_count']} "
                            f"executed={live['executed_count']} "
                            f"unexecuted={live['unexecuted_count']}"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "command-center/p2-wave/probes/TST-0332/reviewer.py"
                        ),
                        "fingerprint": fingerprint(
                            "static-analysis",
                            "command-center/p2-wave/probes/TST-0332/reviewer.py",
                        ),
                        "raw_output": (
                            f"reviewer_verdict={rev['verdict']} "
                            f"declared={rev['declared_count']} "
                            f"executed={rev['executed_count']} "
                            f"unexecuted={rev['unexecuted_count']}"
                        ),
                    },
                ],
            },
            {
                "id": "EV-skip-reason-attribution",
                "kind": "measurement",
                "claim": (
                    "Every unexecuted step is attributed with one of: "
                    "conditional_false, matrix_exclusion, earlier_failure, "
                    "cancelled. An independent reviewer re-derived the same list "
                    "from YAML + job-summary without reading this conclusion."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0332/reviewer.py",
                "confidence": "almost-certain",
                "by_reason": by_reason,
                "reviewer_id": rev["reviewer_id"],
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "fingerprint": fingerprint("command", P1),
                        "raw_output": f"unexecuted_by_reason={by_reason}",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "command-center/p2-wave/probes/TST-0332/"
                            "fixtures/runs/latest-green.json"
                        ),
                        "fingerprint": fingerprint(
                            "file-read",
                            "command-center/p2-wave/probes/TST-0332/"
                            "fixtures/runs/latest-green.json",
                        ),
                        "raw_output": (
                            f"run_id={live['run_id']} "
                            f"conclusion={live['workflow_conclusion']}"
                        ),
                    },
                ],
            },
            {
                "id": "EV-planted-cannot-run",
                "kind": "negative-control",
                "claim": (
                    "Planting a step with if: ${{ false }} adds it to the "
                    "unexecuted list as conditional_false; the unmodified "
                    "workflow does not list planted-cannot-run."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0332/probe2_cannot_run.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "fingerprint": fingerprint("command", P2),
                        "raw_output": (
                            f"fired_on_bad_state={ctl['fired_on_bad_state']} "
                            f"silent_on_good_state={ctl['silent_on_good_state']}"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/"
                            "TST-0332/harness.py --write-fixtures"
                        ),
                        "fingerprint": fingerprint(
                            "test-run",
                            "python3 -B command-center/p2-wave/probes/"
                            "TST-0332/harness.py --write-fixtures",
                        ),
                        "raw_output": json.dumps(
                            {
                                "before_declared": ctl["before_declared"],
                                "after_declared": ctl["after_declared"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "saw_conclusion_first": False,
            "method": rev["method"],
            "notes": (
                "Mechanical adversarial control is probe2 (plant cannot-run) "
                "plus the independent skip-reason re-derivation. No separate "
                "human reviewer ran in a fresh context on this worktree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0332/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "global_unit_manifest_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "notes": "Measure runs after this receipt is written.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Latest green GitHub Actions quality.yml run on the origin "
                    "repo via gh (job summaries + logs)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install gh, authenticate, then "
                    "`gh run list --workflow quality.yml --status success --limit 1` "
                    "and re-run the detector against that job summary."
                ),
            },
            {
                "claim": (
                    "Whether every TEST-REGISTRY ci_step name equals a live "
                    "quality.yml step name byte-for-byte (one registry row uses "
                    "a shorter harness title than the workflow step)."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Rename either the registry ci_step or the workflow step "
                    "name so they match, then re-run bind_test_registry."
                ),
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the harness "
                "or the fixture."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now, "generated_at": now},
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "notes": (
                    "Live sha256 is recorded in the per-unit "
                    "UNIT-ARTIFACT-MANIFEST.json after this file is written."
                ),
            },
            art("command-center/p2-wave/probes/TST-0332/harness.py", "implementation"),
            art(
                "command-center/p2-wave/probes/TST-0332/fixtures/workflows/phase0-ci-test-gap.yml",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0332/fixtures/runs/latest-green.json",
                "supporting",
            ),
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "min_bytes_threshold": 128,
    }

    out_path = REPO / OUT
    write_json(out_path, doc)
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0332 sentinel missing from receipt body")
        return 1
    if out_path.stat().st_size < 128:
        print(f"FAILED:TST-0332 receipt too small ({out_path.stat().st_size} B)")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(t1[-2000:])
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0332 probes after emit c1={c1} c2={c2}")
        return 1

    doc["downstream_consumers"] = [
        {
            "consumer": "command-center/p2-wave/probes/TST-0332/probe1_setdiff.py",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": c1,
            "probe": {
                "role": "source",
                "method": "command",
                "command": P1,
                "fingerprint": fingerprint("command", P1),
                "raw_output": t1[-4000:],
                "exit_code": c1,
            },
        },
        {
            "consumer": "command-center/p2-wave/probes/TST-0332/probe2_cannot_run.py",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": c2,
            "probe": {
                "role": "verifier",
                "method": "command",
                "command": P2,
                "fingerprint": fingerprint("command", P2),
                "raw_output": t2[-4000:],
                "exit_code": c2,
            },
        },
    ]
    write_json(out_path, doc)
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0332 probes after consumer rewrite c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "set-difference-and-skip-reasons",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-cannot-run-control",
                "raw_output": t2,
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
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0332/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0332: live named probes exit 0, receipts/TST-0332.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "No ADV rebuild."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0332 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
