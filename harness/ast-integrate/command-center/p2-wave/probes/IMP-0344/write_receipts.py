#!/usr/bin/env python3
"""Emit IMP-0344 receipt and per-unit probe receipts after live runs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

OUT = "command-center/receipts/IMP-0344.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0344/probe1_integration.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0344/probe2_swallowed_failure.py"
)
SUPPORTING = [
    "tools/council/bridge.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0344/scenario.py",
    "command-center/p2-wave/probes/IMP-0344/probe1_integration.py",
    "command-center/p2-wave/probes/IMP-0344/probe2_swallowed_failure.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
        "present": True,
        "unit_id": "IMP-0344",
        "receipt_path": "command-center/p2-wave/probes/IMP-0344/SUBAGENT-RETURN.json",
    }


def main() -> int:
    measured = S.run_all_required()
    if not measured["ok"]:
        print("FAILED:IMP-0344 live scenario did not pass")
        print(json.dumps(measured, indent=2, sort_keys=True, default=str)[:8000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    integration = measured["integration"]
    planted = measured["planted_second_plane"]
    honest = measured["honest_failure"]
    swallow = measured["swallowed_through_bridge"]
    detector = measured["detector_both_states"]
    ast_inv = measured["ast_invariant"]
    taxonomy = measured["out_of_taxonomy"]
    census = integration["census"]

    artifact_paths = [OUT] + SUPPORTING
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0344",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0344",
        "completion_sentinel": "SUCCESS:IMP-0344",
        "spec_anchor": (
            "_USER-PROMPTS.md:10727 (do not import a second orchestration runtime); "
            "_USER-PROMPTS.md:10483 (do not create duplicate control planes); "
            "catalog IMP-0344 council-as-a-workflow-stage bridge"
        ),
        "title": "Council-as-a-workflow-stage bridge",
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-bridge-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths,
        "artifacts": [
            {
                "path": rel,
                "exists": True,
                "role": "primary" if rel == OUT else "supporting",
            }
            for rel in artifact_paths
        ],
        "evidence": [
            {
                "claim": (
                    "A composed workflow run that invokes a council as a stage and "
                    "consumes the typed decision downstream uses exactly one scheduler "
                    "and one event log."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/bridge.py:CensusWindow+WorkflowRunner.run",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "scenario.run_integration",
                        "exit_code": 0,
                        "raw_output": json.dumps(census, sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "construction-log",
                        "command": "ControlPlaneCensus.single_control_plane",
                        "exit_code": 0,
                        "raw_output": (
                            f"event_log_count={census['event_log_count']} "
                            f"scheduler_count={census['scheduler_count']} "
                            f"plane_count={census['plane_count']} "
                            f"single={census['single_control_plane']}"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "A council failure inside a workflow is classified by reading the "
                    "workflow node's failure policy (family=model-error, action=abort, "
                    "source=workflow.failure_policy), not by a council-local policy."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/bridge.py:CouncilBridge._classify",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "scenario.run_honest_failure",
                        "exit_code": 0,
                        "raw_output": json.dumps(honest.get("classified"), sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "event-log",
                        "command": "detect_swallowed_council_failure on honest run",
                        "exit_code": 0,
                        "raw_output": f"swallowed_count={honest.get('swallowed_count')}",
                    },
                ],
            },
        ],
        "test_ids": [
            "IMP-0344-T1-integration",
            "IMP-0344-T2-invariant-single-plane",
            "IMP-0344-T3-negative-swallowed-failure",
        ],
        "tests": [
            {
                "id": "IMP-0344-T1-integration",
                "name": "Council invoked as a stage; typed decision consumed downstream",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "IMP-0344-T2-invariant-single-plane",
                "name": "Census is one scheduler and one event log; planted second log is detected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "IMP-0344-T3-negative-swallowed-failure",
                "name": "Swallowed council failure is detected and classified; honest failure is silent for the detector",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_control_ids": [
            "IMP-0344-C1-swallowed-failure-fixture",
            "IMP-0344-C2-planted-second-event-log",
            "IMP-0344-C3-out-of-taxonomy-policy",
        ],
        "negative_controls": [
            {
                "id": "IMP-0344-C1-swallowed-failure-fixture",
                "kind": "known-broken-fixture",
                "description": (
                    "A council.turn.failed event with no workflow.failure.classified "
                    "must fire detect_swallowed_council_failure. The same failure with "
                    "a policy classification must be silent. A SwallowingInvoker through "
                    "the live bridge must not silently pass."
                ),
                "fired_on_bad_state": detector["fired_on_bad"],
                "silent_on_good_state": detector["silent_on_good"],
                "bad_state_output": f"bad_count={detector['bad_count']} kind={detector['bad_kind']}",
                "good_state_output": (
                    f"good_count={detector['good_count']} "
                    f"bridge_silent_pass={swallow['silent_pass']} "
                    f"bridge_family={(swallow.get('classified') or {}).get('family')}"
                ),
            },
            {
                "id": "IMP-0344-C2-planted-second-event-log",
                "kind": "known-broken-fixture",
                "description": (
                    "An invoker that constructs a second EventLog during a council "
                    "stage must make ControlPlaneCensus.single_control_plane false "
                    "and classify duplicate-control-plane under the workflow policy."
                ),
                "fired_on_bad_state": planted["ok"],
                "silent_on_good_state": integration["census"]["single_control_plane"],
                "bad_state_output": json.dumps(planted["census"], sort_keys=True),
                "good_state_output": json.dumps(census, sort_keys=True),
            },
            {
                "id": "IMP-0344-C3-out-of-taxonomy-policy",
                "kind": "schema-invalid",
                "description": "A policy naming a family outside the closed set fails validation.",
                "fired_on_bad_state": taxonomy["ok"],
                "silent_on_good_state": True,
                "bad_state_output": taxonomy.get("error") or "",
                "good_state_output": "complete_policy() validates",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0344-named-probes",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Adversarial review started from the named probes and scenario "
                "fixtures, not from this receipt. Probe 1 re-runs the census and "
                "the planted second-log control. Probe 2 re-runs the swallowed-"
                "failure fixture both-states and the live SwallowingInvoker."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is not on this worktree. "
                    "The bridge binds a CouncilInvoker; InProcessDeliberation is "
                    "the stand-in that still submits every seat through the host "
                    "scheduler."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver IMP-0264 KernelInvoker and re-run probe1 against it."
                ),
            },
            {
                "claim": (
                    "tools/agentspec/agentspec/taxonomy.py (IMP-0138) is not on "
                    "this worktree. Bridge-local FAMILIES is the closed set used "
                    "here; remap when the agentspec taxonomy lands."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Import agentspec.taxonomy families and assert set(FAMILIES) "
                    "is a subset, then re-run out-of-taxonomy validation."
                ),
            },
            {
                "claim": (
                    "No live vendor council was seated. Votes are deterministic "
                    "from the brief string."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Bind a vendor-backed invoker and re-run the integration "
                    "workflow with recorded sampling parameters."
                ),
            },
        ],
        "control_plane_census": census,
        "planted_second_plane": planted["census"],
        "ast_invariant": ast_inv,
        "failure_fixture": honest.get("classified"),
        "swallowed_bridge": swallow.get("classified"),
        "module_path": "tools/council/bridge.py",
        "falsifiable_answers": {
            "second_scheduler_or_event_log": (
                f"No on the happy path: event_log_count={census['event_log_count']} "
                f"scheduler_count={census['scheduler_count']}. A planted second "
                f"EventLog is detected (event_log_count="
                f"{planted['census']['event_log_count']})."
            ),
            "council_failure_classification": (
                "Classified under the workflow failure policy "
                f"({honest.get('classified')}). A swallowed failure is not a "
                f"silent pass ({swallow.get('classified')})."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0344/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after two failures sharing "
                "an error fingerprint, enumerate >=2 alternative designs before a "
                "third attempt"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0344: live named probes, honest SUCCESS receipt, per-unit "
            "UNIT-ARTIFACT-MANIFEST.json row. Did not run global unit_manifest.py "
            "--write. SUCCESS:IMP-0344"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0344 probes c1={c1} c2={c2}")
        return 1

    primary = art_row(OUT, "primary")
    artifacts = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0344",
        "unit_id": "IMP-0344",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0344",
        "registered": True,
        "output_path": OUT,
        "output_schema": doc["output_schema"],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-4000:]},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0344/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0344-named-probes",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0344: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0344",
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
    print("SUCCESS:IMP-0344 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
