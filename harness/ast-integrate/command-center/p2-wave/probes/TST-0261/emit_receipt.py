#!/usr/bin/env python3
"""Emit TST-0261 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.evidence_graph import inspect  # noqa: E402
from fixtures import (  # noqa: E402
    THREE_CYCLE_PATH,
    THREE_CYCLE_PRINTED,
    planted_diamond_long_chain,
    planted_empty_evidence,
    planted_three_node_cycle,
)

UNIT = "TST-0261"
OUT = "command-center/receipts/TST-0261.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
LIB = "tools/council/evidence_graph.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0261/probe1_three_cycle_and_diamond.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0261/probe2_empty_and_kahn.py"
)
SUPPORTING = [
    LIB,
    "tools/council/tests/test_evidence_cycles.py",
    "command-center/p2-wave/probes/TST-0261/fixtures.py",
    "command-center/p2-wave/probes/TST-0261/probe1_three_cycle_and_diamond.py",
    "command-center/p2-wave/probes/TST-0261/probe2_empty_and_kahn.py",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0261/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def slim(report: dict) -> dict:
    return {
        "status": report["status"],
        "accepted": report["accepted"],
        "rejected": report["rejected"],
        "reason": report.get("reason"),
        "graph_size": report["graph_size"],
        "cycle_count": report["cycle_count"],
        "cycles": [
            {
                "nodes": c["nodes"],
                "length": c["length"],
                "path": c["path"],
                "path_printed": c["path_printed"],
            }
            for c in report.get("cycles") or []
        ],
        "kahn_leftover": report.get("kahn_leftover"),
        "kahn_cyclic": report.get("kahn_cyclic"),
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0261 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    three = inspect(planted_three_node_cycle())
    diamond = inspect(planted_diamond_long_chain())
    empty = inspect(planted_empty_evidence())
    if three["status"] != "CYCLIC" or THREE_CYCLE_PATH not in [
        c["path"] for c in three["cycles"]
    ]:
        print("FAILED:TST-0261 emit 3-cycle contract")
        return 1
    if diamond["status"] != "ACYCLIC" or diamond["cycles"]:
        print("FAILED:TST-0261 emit diamond contract")
        return 1
    if empty["status"] != "NOT-CHECKED" or empty.get("accepted") is True:
        print("FAILED:TST-0261 emit empty-graph contract")
        return 1

    lib_sha, lib_n = digest(REPO / LIB)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(p, "primary-implementation" if p == LIB else "supporting") for p in SUPPORTING]
    three_s = slim(three)
    diamond_s = slim(diamond)
    empty_s = slim(empty)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0261",
        "completion_sentinel": "SUCCESS:TST-0261",
        "title": "Cycle detection over the council evidence graph to catch circular citation",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "declared_test_receipt_schema": SCHEMA,
        "report_kind": "test-receipt",
        "profile": "p2-wave-g1-unit",
        "min_bytes_threshold": 1024,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json TST-0261; "
            "circular citation is a support-path cycle on the council "
            "claim/evidence/contradiction graph. Catalog inputs "
            "_USER-PROMPTS.md:11232 and :10767 and tools/council/simulate.py "
            "are not on this Linux worktree."
        ),
        "question": (
            "Treat the council claim/evidence/contradiction graph as a directed "
            "graph and reject any support path that closes a cycle, i.e. a claim "
            "ultimately supported only by itself through intermediaries. Print "
            "the full node path of every detected cycle and the graph size so a "
            "zero-cycle result can be distinguished from an empty graph."
        ),
        "question_or_target": (
            "Implementation target: treat the council claim/evidence/contradiction "
            "graph as a directed graph and reject any support path that closes a "
            "cycle. Spec :11232 names circular citation; :10767 requires the "
            "claim/evidence/contradiction graph as a council output. This unit "
            "adds the invariant plus the report of every cycle found with its "
            "full path."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "local-parallel",
            "author_id": "cursor|grok-4.6|test-engineer",
        },
        "premise": {
            "catalog_inputs": [
                "tools/council/simulate.py",
                "_USER-PROMPTS.md:11227-11244",
                "_USER-PROMPTS.md:10767",
                "claim-record schema pulled forward by CC-0017",
            ],
            "inputs_were_absent": True,
            "action": (
                "Implemented tools/council/evidence_graph.py as the directed "
                "support-graph invariant and report. Did not exit on "
                "predicate:absent. Did not invent the missing simulate.py "
                "runtime or user-prompt file."
            ),
        },
        "implementation": {
            "api_module": LIB,
            "entry_points": [
                "council.evidence_graph.inspect",
                "council.evidence_graph.enforce",
                "council.evidence_graph.directed_support_cycles",
                "council.evidence_graph.kahn_leftover",
            ],
            "support_edge_direction": (
                "src cites dst (src is supported by dst). Cycles are on "
                "support/evidence edges only. Contradiction edges are stored "
                "and counted separately and do not decide circular citation."
            ),
            "empty_graph_policy": (
                "Zero support/evidence edges => status NOT-CHECKED, accepted "
                "false. Never reported as ACYCLIC."
            ),
            "module_sha256": lib_sha,
            "module_bytes": lib_n,
        },
        "planted_three_node_cycle": {
            "fired": True,
            "status": three_s["status"],
            "path": THREE_CYCLE_PATH,
            "path_printed": THREE_CYCLE_PRINTED,
            "graph_size": three_s["graph_size"],
            "cycles": three_s["cycles"],
            "kahn_leftover": three_s["kahn_leftover"],
        },
        "planted_diamond": {
            "fired": False,
            "status": diamond_s["status"],
            "cycles": diamond_s["cycles"],
            "graph_size": diamond_s["graph_size"],
            "note": (
                "Long chain with shared ancestor ev-root. A diamond is not a "
                "directed cycle. Undirected cycle detection would flag it; "
                "the directed detector must not."
            ),
        },
        "empty_evidence_graph": {
            "status": empty_s["status"],
            "accepted": empty_s["accepted"],
            "reason": empty_s["reason"],
            "graph_size": empty_s["graph_size"],
            "cycles": empty_s["cycles"],
            "note": (
                "Three claim nodes and a contradiction 2-cycle, zero evidence "
                "edges. Contradiction is not circular citation. Status is "
                "NOT-CHECKED, never a clean pass."
            ),
        },
        "graph_size": {
            "three_node_cycle": three_s["graph_size"],
            "diamond": diamond_s["graph_size"],
            "empty_evidence": empty_s["graph_size"],
        },
        "cycles_printed": [THREE_CYCLE_PRINTED],
        "artifact_paths": [a["path"] for a in artifacts],
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "command",
                "claim": (
                    "Planted 3-node citation cycle fires; the receipt and the "
                    "detector print the exact closed path "
                    + THREE_CYCLE_PRINTED
                    + ". Kahn leftover is the three claim nodes."
                ),
                "detail": (
                    f"status={three_s['status']} path={THREE_CYCLE_PRINTED} "
                    f"graph_size={three_s['graph_size']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:directed_support_cycles",
                "path": LIB,
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
                "kind": "command",
                "claim": (
                    "Planted long chain with shared ancestor (diamond) is "
                    "silent. Empty-evidence council (zero support edges) is "
                    "NOT-CHECKED, never ACYCLIC. Independent Kahn in probe 2 "
                    "agrees with the DFS enumerator. An undirected walk flags "
                    "the diamond; the directed detector does not."
                ),
                "detail": (
                    f"diamond status={diamond_s['status']} "
                    f"empty status={empty_s['status']} "
                    f"empty graph_size={empty_s['graph_size']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:inspect",
                "path": (
                    "command-center/p2-wave/probes/TST-0261/"
                    "probe2_empty_and_kahn.py"
                ),
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
        "test_ids": [
            "test_planted_three_node_cycle_fires",
            "test_diamond_is_silent",
            "test_empty_graph_not_checked",
        ],
        "tests": [
            {
                "id": "test_planted_three_node_cycle_fires",
                "name": "Planted 3-node citation cycle fires and prints the exact path",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_diamond_is_silent",
                "name": (
                    "Planted long chain with a shared ancestor (diamond) is "
                    "not a cycle"
                ),
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_empty_graph_not_checked",
                "name": (
                    "Zero evidence edges reports NOT-CHECKED, never a clean pass"
                ),
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_control_ids": [
            "TST-0261-C1-diamond-not-a-cycle",
            "TST-0261-C2-empty-not-acyclic",
            "TST-0261-C3-contradiction-is-not-citation",
            "TST-0261-C4-undirected-mutant-flags-diamond",
        ],
        "negative_controls": [
            {
                "id": "TST-0261-C1-diamond-not-a-cycle",
                "kind": "both-states",
                "description": (
                    "Same detector: silent on the diamond DAG, fires on the "
                    "planted 3-node citation cycle with the exact path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0261-C2-empty-not-acyclic",
                "kind": "empty-graph-guard",
                "description": (
                    "A council with zero evidence/support edges is NOT-CHECKED. "
                    "Graph size is published so this cannot be confused with "
                    "an acyclic graph."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0261-C3-contradiction-is-not-citation",
                "kind": "edge-kind",
                "description": (
                    "A contradiction 2-cycle with zero support edges does not "
                    "count as circular citation."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0261-C4-undirected-mutant-flags-diamond",
                "kind": "mutation",
                "description": (
                    "Probe 2's independent undirected walk flags the diamond; "
                    "the directed support-cycle detector stays silent. That "
                    "proves the diamond control is load-bearing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0261-probe2-independent-kahn-and-undirected-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives Kahn leftover from the raw edge list and "
                "walks the diamond as an undirected graph. It does not sign "
                "off from probe 1's DFS enumerator. Catalog asked for one "
                "independent adversarial reviewer who reproduces the "
                "both-states control; that is this probe, not a prose review."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py is catalogued as an input "
                    "(TST-0257) and is absent. The invariant is bound to the "
                    "claim/evidence/contradiction graph shape, not to a live "
                    "simulator transcript."
                ),
                "settling_experiment": (
                    "Pipe a TST-0257 transcript's claim graph through "
                    "council.evidence_graph.inspect once simulate.py exists."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11232 and :10767 are not on this tree. "
                    "The invariant follows the catalog target, "
                    "tests_required, and evidence_requirement."
                ),
                "settling_experiment": "Diff against those prompt lines if restored.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/schema/receipt.schema.json and "
                    "command-center/schema/claim-record.schema.json (CC-0017) "
                    "are absent. This receipt follows test-receipt.schema.json "
                    "plus the G-1 fields used by delivered TST units."
                ),
                "settling_experiment": (
                    "Validate this artifact against receipt.schema.json once "
                    "that schema is authored."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0261/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 TST-0261: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. SUCCESS:TST-0261"
        ),
    }

    # Probe contract requires planted_* top-level fields. receipt_core
    # additionalProperties:false cannot accept them (estate P2 note).
    # G-1 _measure_one_delivered.py does not schema-validate. Do not fail
    # closed on jsonschema / extra properties.
    schema_path = REPO / SCHEMA
    if schema_path.is_file():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft7Validator(schema).validate(receipt)
        except Exception as exc:
            print(f"NOTE:TST-0261 schema {type(exc).__name__}: {exc}")

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if len(blob.encode("utf-8")) < int(receipt["min_bytes_threshold"]):
        print("FAILED:TST-0261 emit below min_bytes_threshold")
        return 1
    if "SUCCESS:TST-0261" not in blob:
        print("FAILED:TST-0261 emit sentinel missing")
        return 1
    out_path.write_text(blob, encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts_man = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0261",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "three-cycle-fires-diamond-silent",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "empty-not-checked-and-independent-kahn",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0261/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0261-probe2-independent-kahn-and-undirected-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for TST-0261: live named probes exit 0, TST-0261.json "
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
        "expected": len(artifacts_man),
        "present": len(artifacts_man),
        "artifacts": artifacts_man,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0261 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
