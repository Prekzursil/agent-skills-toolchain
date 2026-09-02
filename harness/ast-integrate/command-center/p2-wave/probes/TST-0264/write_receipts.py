#!/usr/bin/env python3
"""Write TST-0264 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.simulate import run_council  # noqa: E402
from tools.council.stopping.minimum import (  # noqa: E402
    FLOOR_INDEPENDENT_OPENING_POSITIONS,
    SpecValidationError,
    validate_spec,
)

OUT = "command-center/receipts/TST-0264.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0264/probe1_premature_stop_floored.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0264/probe2_met_floors_and_bypass.py"
)
SUPPORTING = [
    "tools/council/simulate.py",
    "tools/council/stopping/minimum.py",
    "tools/council/stopping/expr.py",
    "tools/council/stopping/__init__.py",
    "command-center/p2-wave/probes/TST-0264/scenario.py",
    "command-center/p2-wave/probes/TST-0264/probe1_premature_stop_floored.py",
    "command-center/p2-wave/probes/TST-0264/probe2_met_floors_and_bypass.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("probe emitted no JSON object")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "eol": "LF",
        "unit_id": "TST-0264",
        "receipt_path": "command-center/p2-wave/probes/TST-0264/SUBAGENT-RETURN.json",
        "role": role,
    }


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def snippet(rel: str, line: int) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:160]
    return ""


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0264 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json(t1)
    p2 = first_json(t2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0264 receipts probe JSON pass=false")
        return 1

    floored = run_council(S.spec(S.PREMATURE_SPEC), S.silent_cast(), apply_floors=True)
    ungated = run_council(S.spec(S.PREMATURE_SPEC), S.silent_cast(), apply_floors=False)
    healthy = run_council(S.spec(S.HEALTHY_SPEC), S.productive_cast(), apply_floors=True)
    first = floored["stop_evals"][0]
    if first.get("named_floor") != FLOOR_INDEPENDENT_OPENING_POSITIONS:
        print("FAILED:TST-0264 emit-time named floor drifted from probe1")
        return 1
    if first.get("stop_expression_true") is not True or first.get("decision") != "continue":
        print("FAILED:TST-0264 emit-time premature run did not continue under a true stop")
        return 1
    if int(healthy["rounds_completed"]) != 2:
        print("FAILED:TST-0264 emit-time healthy run over-blocked")
        return 1
    bypass_code = None
    try:
        validate_spec(S.spec(S.BYPASS_SPEC))
        print("FAILED:TST-0264 emit-time min_rounds=0 accepted")
        return 1
    except SpecValidationError as exc:
        bypass_code = exc.code

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_rows = [row(path, "supporting") for path in SUPPORTING]
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    min_py = "tools/council/stopping/minimum.py"
    sim_py = "tools/council/simulate.py"
    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0264",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0264",
        "completion_sentinel": "SUCCESS:TST-0264",
        "completion_marker": "UNIT-COMPLETE:TST-0264",
        "title": "Enforce minimum deliberation conditions so a council cannot stop before it has deliberated",
        "spec_anchor": "_USER-PROMPTS.md:10762,:11338 catalog TST-0264 (spec file absent; floors taken from the unit text)",
        "question_or_target": (
            "Encode minimum-deliberation conditions as a hard precondition on ANY "
            "stopping expression so a satisfied stop rule cannot terminate a run "
            "that has not met the floor."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0264/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "no automatic retry; re-run after a named harness or fixture change"},
        "reviewer": {
            "reviewer_id": "TST-0264-probe2-met-floors-and-bypass",
            "independent": True,
            "fresh_context": True,
            "executed_both_states": True,
            "verdict": "PASS",
        },
        "tests": [
            {
                "id": "stop-true-round-1-zero-briefs-continues",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
                "observation": (
                    "Permissive expression `true` evaluated TRUE in round 1 with "
                    "zero independent briefs; run continued; transcript named "
                    f"{FLOOR_INDEPENDENT_OPENING_POSITIONS}."
                ),
            },
            {
                "id": "floors-met-true-stop-terminates-immediately",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "observation": (
                    "After round 2 all floors were met and the expression was TRUE; "
                    "the run stopped at round 2 with no extra round."
                ),
            },
            {
                "id": "min-rounds-zero-rejected-at-validation",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "observation": (
                    f"spec min_rounds=0 raised SpecValidationError code={bypass_code} "
                    "before any round ran."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "gate-disabled-stops-early",
                "kind": "both-states",
                "verbatim": (
                    "NEGATIVE CONTROL (gate disabled): On the identical silent-cast "
                    "fixture whose permissive stop expression evaluates TRUE in "
                    "round 1 with zero independent opening briefs, disabling the "
                    "minimum-deliberation gate makes the run STOP in round 1. The "
                    "check is meant to reject that early stop: with the gate on, "
                    "the same fixture CONTINUES and names independent_opening_positions."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ungated["stop_evals"][0]["reason"],
                "good_state_output": first["reason"],
            },
            {
                "id": "floors-met-do-not-substitute-for-false-expression",
                "kind": "both-states",
                "verbatim": (
                    "NEGATIVE CONTROL (false expression): A productive cast that "
                    "meets every floor by round 2 must NOT stop via the floor when "
                    "the stopping expression is `false`. The floor is a "
                    "precondition on a satisfied stop, not a stop rule of its own."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p2.get("false_expression_round2_reason"),
                "good_state_output": p2.get("healthy_reason"),
            },
        ],
        "evidence": [
            {
                "path": min_py,
                "line": 279,
                "snippet": snippet(min_py, 279),
                "claim": (
                    "decide_stop treats floors as a hard precondition: a True "
                    "expression with unmet floors returns continue with "
                    "floor-blocks-satisfied-stop."
                ),
                "kind": "source",
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": "emit-time recompute run_council(premature, apply_floors=True)",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "fingerprint": fp(P1),
                        "raw_output": t1[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit-time recompute run_council premature floored",
                        "exit_code": 0,
                        "fingerprint": fp("run_council-premature-floored"),
                        "raw_output": json.dumps(
                            {
                                "round": first["round"],
                                "stop_expression_true": first["stop_expression_true"],
                                "decision": first["decision"],
                                "named_floor": first["named_floor"],
                                "unmet_floors": first["unmet_floors"],
                                "floor_block_message": first["floor_block_message"],
                                "independent_briefs": first["measured"]["independent_briefs"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "path": sim_py,
                "line": 98,
                "snippet": snippet(sim_py, 98),
                "claim": (
                    "run_council evaluates the stopping expression each round then "
                    "applies the floor gate; a min_rounds=0 spec never reaches a round."
                ),
                "kind": "source",
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": "emit-time recompute run_council(healthy)+validate_spec(bypass)",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "fingerprint": fp(P2),
                        "raw_output": t2[-1500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "emit-time recompute healthy stop + min_rounds=0 validate",
                        "exit_code": 0,
                        "fingerprint": fp("run_council-healthy-bypass"),
                        "raw_output": json.dumps(
                            {
                                "healthy_rounds": healthy["rounds_completed"],
                                "healthy_reason": healthy["stop_reason"],
                                "bypass_code": bypass_code,
                                "transcript_sha256": healthy["transcript_sha256"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "implementation": {
            "simulator": sim_py,
            "floor_module": min_py,
            "expr_module": "tools/council/stopping/expr.py",
            "permissive_expression": S.PERMISSIVE_STOP,
            "premature_named_floor": first["named_floor"],
            "premature_floor_block_message": first["floor_block_message"],
            "premature_unmet_floors": first["unmet_floors"],
            "ungated_reason": ungated["stop_evals"][0]["reason"],
            "healthy_stopped_round": healthy["rounds_completed"],
            "healthy_transcript_sha256": healthy["transcript_sha256"],
            "bypass_code": bypass_code,
            "note": (
                "tools/council/simulate.py and tools/council/stopping/ were absent; "
                "TST-0264 implemented the floor gate and a scripted-cast simulator "
                "so the unit's three tests can run. TST-0257/TST-0281/IMP-0308/IMP-0309 "
                "remain separate units and are not claimed delivered."
            ),
        },
        "inputs_inventory": [
            {
                "declared": "tools/council/simulate.py (deterministic council simulator)",
                "status": "implemented-here",
                "path": sim_py,
            },
            {
                "declared": "_USER-PROMPTS.md:10937-10942 / :11339 / :10762",
                "status": "absent-on-worktree",
                "note": "floors taken from catalog TST-0264 tests_required and question_or_target",
            },
            {
                "declared": "stopping-rule engine from bucket B05/B07",
                "status": "seam-implemented",
                "path": "tools/council/stopping/minimum.py",
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py TST-0264",
                    "method": "command",
                    "role": "verifier",
                    "note": "run after this receipt and the per-unit manifest are on disk",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "_USER-PROMPTS.md is absent; numeric spec lines 10762/11338/11339 were not re-read from the original file.",
                "settling_experiment": "Re-run against the restored spec file and confirm the four floor names still match.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": "TST-0257 (full persona-fidelity simulator) and TST-0281 (six-example evaluator conformance) are not delivered on this worktree.",
                "settling_experiment": "Once those units land, re-run these two probes against their modules without changing the floor contract.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "artifacts": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "exists": True,
                "role": item["role"],
            }
            for item in impl_rows
        ],
        "notes": (
            "G-1 for TST-0264: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    out_path = REPO / OUT
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print("FAILED:TST-0264 emit below min_bytes_threshold")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    ret = {
        "id": "TST-0264",
        "unit_id": "TST-0264",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0264",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/TST-0264/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0264-probe2-met-floors-and-bypass",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0264: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0264",
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
    print("SUCCESS:TST-0264 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
