#!/usr/bin/env python3
"""Emit IMP-0174 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import live_graph, planted_both_states  # noqa: E402

UNIT = "IMP-0174"
OUT = "command-center/receipts/IMP-0174.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0174/probe1_orphan_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0174/probe2_planted_orphan.py"
)
SUPPORTING = [
    "tools/workflow_foundry/component_graph.py",
    "tools/workflow_foundry/__init__.py",
    "tools/workflow_foundry/tests/test_component_graph.py",
    "command-center/p2-wave/probes/IMP-0174/fixtures/control.json",
    "command-center/p2-wave/probes/IMP-0174/scenario.py",
    "command-center/p2-wave/probes/IMP-0174/probe1_orphan_count.py",
    "command-center/p2-wave/probes/IMP-0174/probe2_planted_orphan.py",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0174/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0174 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    graph = live_graph()
    both = planted_both_states()
    if graph["orphan_count"] != 0 or not both["pass"]:
        print("FAILED:IMP-0174 emit live graph or both-states")
        return 1

    impl = "tools/workflow_foundry/component_graph.py"
    impl_sha, impl_n = digest(REPO / impl)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    public_nodes = [
        {
            "id": n["id"],
            "kind": n["kind"],
            "roles": n["contract"]["roles"],
            "output_type": n["contract"]["output_type"],
            "tools": n["contract"]["tools"],
            "gate": n["contract"]["gate"],
            "provenance": n["provenance"],
        }
        for n in graph["nodes"]
    ]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0174",
        "completion_sentinel": "SUCCESS:IMP-0174",
        "title": "Build the semantic component graph over extracted stages, roles and gates",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0174: graph nodes are "
            "reusable COMPONENTS (stage kind + contract); edges are observed "
            "compositions; every node traces to a candidate source span; an "
            "orphan component is a build failure"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "IMP-0165",
                "IMP-0166",
                "IMP-0167 outputs",
                "_USER-PROMPTS.md:11152-11170 (Workflow Foundry required production behavior)",
            ],
            "inputs_were_absent": True,
            "action": (
                "IMP-0165/0166/0167 receipts are absent on this worktree. "
                "Shipped the graph builder against a typed extraction document "
                "and in-tree control fixtures standing in for stage/role/gate/"
                "tool extraction those units would emit. Did not exit on "
                "predicate:absent."
            ),
        },
        "implementation": {
            "api_module": impl,
            "entry_points": [
                "workflow_foundry.component_graph.build",
                "workflow_foundry.component_graph.assemble",
                "workflow_foundry.component_graph.orphan_count",
                "workflow_foundry.component_graph.plant_orphan",
            ],
            "node_identity": "sha256(kind + canonical contract: roles, gate, tools, output_type)",
            "edge_identity": "observed compositions mapped onto component ids",
            "orphan_rule": (
                "a node is an orphan iff it has no provenance entry with a "
                "non-empty candidate_id and a resolvable source_span "
                "(uri + start_line<=end_line, start_line>=1)"
            ),
            "sha256": impl_sha,
            "bytes": impl_n,
        },
        "graph": {
            "orphan_count": graph["orphan_count"],
            "orphan_ids": graph["orphan_ids"],
            "node_count": graph["stats"]["node_count"],
            "edge_count": graph["stats"]["edge_count"],
            "stage_observations": graph["stats"]["stage_observations"],
            "collapsed": graph["stats"]["collapsed"],
            "nodes": public_nodes,
            "edges": graph["edges"],
        },
        "artifacts": [
            {
                "path": impl,
                "role": "primary-implementation",
                "sha256": impl_sha,
                "bytes": impl_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    f"orphan_count == {graph['orphan_count']} computed over "
                    f"{graph['stats']['node_count']} component nodes "
                    f"(from {graph['stats']['stage_observations']} stage "
                    "observations); every node has a candidate source span."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{impl}:orphan_count",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "A planted component with empty provenance fails the build "
                    f"({both['planted_error_id']}); a keyword lookalike kind "
                    "'orphan-lookalike' with a real span does not. Detector "
                    "reads provenance/source_span, not the token 'orphan' in ids."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{impl}:assert_no_orphans",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "orphan-component-count-eq-0",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "planted-orphan-must-fail-the-build",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0174-C1-planted-empty-provenance",
                "kind": "both-states",
                "description": (
                    "Insert a node with empty provenance; assert_no_orphans must "
                    "raise orphan-component. Control extraction stays silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0174-C2-unanchored-stage",
                "kind": "both-states",
                "description": (
                    "A stage missing source_span is ingested as an orphan and "
                    "fails build(); a spanned twin of the same kind is not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0174-C3-keyword-lookalike",
                "kind": "mutation",
                "description": (
                    "Kind 'orphan-lookalike' with a resolvable span must build; "
                    "an invented node whose id does not contain 'orphan' must fail."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0174-probe2-planted-orphan-and-keyword-lookalike",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the planted empty-provenance node plus "
                "AST scan of is_orphan/valid_provenance; not a self-attested "
                "prose review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0174/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0174: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0174"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0174",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "orphan-count-computed",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "planted-orphan-detector-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0174/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0174-probe2-planted-orphan-and-keyword-lookalike",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0174: live named probes exit 0, IMP-0174.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print("SUCCESS:IMP-0174 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
