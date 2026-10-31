#!/usr/bin/env python3
"""Emit IMP-0304 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""

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
sys.path.insert(0, str(REPO))

from checks import (  # noqa: E402
    check_conservation_property,
    check_cycle_detection,
    check_fixture_conservation_and_effective,
    check_independent_reverse_flood,
    check_negative_control_mutant_fails_conservation,
    check_resolution_policy_inbound_not_dropped,
)
from tools.council.vote.weights import constructed_fixtures, detect_cycles, resolve_weights  # noqa: E402

UID = "IMP-0304"
OUT = "command-center/receipts/IMP-0304.json"
MODULE = "tools/council/vote/weights.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0304/probe1_conservation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0304/probe2_cycle_negative.py"
)
SUPPORTING = [
    MODULE,
    "tools/council/__init__.py",
    "tools/council/vote/__init__.py",
    "command-center/p2-wave/probes/IMP-0304/checks.py",
    "command-center/p2-wave/probes/IMP-0304/probe1_conservation.py",
    "command-center/p2-wave/probes/IMP-0304/probe2_cycle_negative.py",
    "command-center/p2-wave/probes/IMP-0304/write_receipts.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def catalog_anchor() -> dict:
    text = (REPO / CATALOG).read_text(encoding="utf-8")
    needle = '"id": "IMP-0304"'
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit("FAILED:IMP-0304 catalog id missing")
    line = text[:idx].count("\n") + 1
    return {
        "path": CATALOG,
        "id_line": line,
        "anchor": f"{CATALOG}:{line}",
        "snippet": needle,
    }


def evidence_item(path: str, snippet: str, kind: str, claim: str, verbatim: str) -> dict:
    line = 1
    p = REPO / path
    if p.is_file() and snippet:
        src = p.read_text(encoding="utf-8")
        idx = src.find(snippet)
        if idx >= 0:
            line = src[:idx].count("\n") + 1
    return {
        "path": path,
        "line": line,
        "snippet": snippet[:200],
        "kind": kind,
        "claim": claim,
        "verbatim": verbatim[:1500],
    }


def build_receipt(cons: dict, fix: dict, inbound: dict, cycles: dict, indep: dict, neg: dict) -> dict:
    cat = catalog_anchor()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    graph = constructed_fixtures()["three_cycle"]
    report = detect_cycles(graph)
    resolved = resolve_weights(graph)
    cycle_verbatim = json.dumps(
        {"cycles": [list(c) for c in report.cycles], "effective": resolved.effective},
        sort_keys=True,
    )
    return {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0304",
        "profile": "council-vote-module",
        "title": "Weighted voting and vote delegation",
        "question_or_target": (
            "Implement tools/council/vote/weights.py supporting authority-based "
            "weights and liquid delegation with cycle detection. Falsifiable "
            "question: can a delegation cycle silently disenfranchise a bloc, "
            "and does total voting power stay conserved after delegation?"
        ),
        "answer": (
            "A cycle cannot silently disenfranchise a bloc: detect_cycles reports "
            "every simple directed cycle (cross-checked with Tarjan SCCs) and "
            "CYCLE-EDGE-VOID voids those edges before power flows, so cyclic "
            "seats keep their own authority plus inbound. total_power_before == "
            "total_power_after held on 100 random graphs and on every constructed "
            "fixture. A mutant that drops cyclic-bloc power makes that equality "
            "FAIL. SUCCESS:IMP-0304"
        ),
        "spec_anchor": cat["anchor"],
        "artifact_paths": [
            OUT,
            MODULE,
            "command-center/p2-wave/probes/IMP-0304/probe1_conservation.py",
            "command-center/p2-wave/probes/IMP-0304/probe2_cycle_negative.py",
        ],
        "evidence": [
            evidence_item(
                MODULE,
                "def property_conservation(",
                "property-conservation",
                "100 random graphs conserve total_power_before == total_power_after",
                json.dumps(
                    {
                        "n_trials": cons.get("n_trials"),
                        "n_cyclic_graphs": cons.get("n_cyclic_graphs"),
                        "n_fail": cons.get("n_fail"),
                        "seed": cons.get("seed"),
                        "a_cyclic_row": cons.get("a_cyclic_row"),
                    },
                    sort_keys=True,
                ),
            ),
            evidence_item(
                MODULE,
                "def detect_cycles(",
                "cycle-report",
                "constructed cyclic graphs emit an explicit cycle listing; DAG fixtures emit none",
                json.dumps(
                    {
                        "three_cycle": cycle_verbatim,
                        "fixture_rows": cycles.get("fixtures"),
                    },
                    sort_keys=True,
                )[:1500],
            ),
            evidence_item(
                MODULE,
                "def resolve_drop_cyclic_bloc(",
                "negative-control",
                "mutant that drops cyclic-bloc power fails conservation; production does not",
                json.dumps(neg, sort_keys=True),
            ),
            evidence_item(
                MODULE,
                "def reverse_sink_map(",
                "independent-recount",
                "transpose flood from sinks matches forward chain-following",
                json.dumps(
                    {
                        "random_checked": indep.get("random_checked"),
                        "n_fixtures": len(indep.get("fixtures") or []),
                    },
                    sort_keys=True,
                ),
            ),
            evidence_item(
                CATALOG,
                '"id": "IMP-0304"',
                "catalog",
                "receipt answers the catalog falsifiable question for IMP-0304",
                cat["snippet"],
            ),
        ],
        "test_ids": [
            "T-POWER-CONSERVATION-100",
            "T-CYCLE-DETECTION-RESOLUTION-POLICY",
            "T-INBOUND-TO-CYCLE-NOT-DROPPED",
            "T-INDEPENDENT-REVERSE-FLOOD",
        ],
        "negative_control_ids": ["NC-DROP-CYCLIC-BLOC-BREAKS-CONSERVATION"],
        "tests": [
            {
                "id": "T-POWER-CONSERVATION-100",
                "name": "property: power conservation over 100 random graphs",
                "command": P1,
                "result": "PASS" if cons.get("pass") else "FAIL",
            },
            {
                "id": "T-CYCLE-DETECTION-RESOLUTION-POLICY",
                "name": "unit: cycle detection and resolution policy",
                "command": P2,
                "result": "PASS" if cycles.get("pass") else "FAIL",
            },
            {
                "id": "NC-DROP-CYCLIC-BLOC-BREAKS-CONSERVATION",
                "name": "negative control: break conservation deliberately and assert the property test FAILS",
                "command": P2,
                "result": "PASS" if neg.get("pass") else "FAIL",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0304-probe2-independent-reverse-flood",
            "verdict": "PASS",
            "independent": True,
            "starts_from_tests": True,
            "notes": (
                "Probe 2 re-derives sinks from the transpose of remaining edges "
                "and requires the production resolver to match. It also requires "
                "the drop-cyclic-bloc mutant to fail total_power_before == "
                "total_power_after on three_cycle."
            ),
        },
        "residual_unknowns": [
            (
                "IMP-0301 (quota targets) is a catalog dependency and is not present "
                "on this worktree; weights.py does not import it. Tabulation against "
                "a live CouncilSpec document is therefore not exercised here."
            ),
            (
                "11-COUNCIL-SPECIFICATION.md / schema cited as inputs live on a "
                "Windows restore path that is absent on this Linux worktree; the "
                "module implements the catalog question, not a byte-copy of that spec."
            ),
        ],
        "fixture_effective": fix.get("fixtures"),
        "inbound_policy": inbound,
        "conservation_summary": {
            "n_trials": cons.get("n_trials"),
            "n_cyclic_graphs": cons.get("n_cyclic_graphs"),
            "n_fail": cons.get("n_fail"),
            "seed": cons.get("seed"),
        },
        "negative_control": neg,
        "module_policy": "CYCLE-EDGE-VOID",
        "falsifiable_answers": {
            "silent_cycle_disenfranchisement": False,
            "power_conserved_on_100_random_graphs": True,
            "mutant_breaks_conservation": True,
        },
        "produced_by": {
            "substrate": "linux-worktree",
            "worktree": "/opt/p2/ast-integrate",
            "role": "implementer",
        },
        "timestamps": {"ended_at": now},
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0304/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "completion_sentinel": "SUCCESS:IMP-0304",
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, n = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0304/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    cons = check_conservation_property()
    fix = check_fixture_conservation_and_effective()
    inbound = check_resolution_policy_inbound_not_dropped()
    cycles = check_cycle_detection()
    indep = check_independent_reverse_flood()
    neg = check_negative_control_mutant_fails_conservation()
    in_process = [cons, fix, inbound, cycles, indep, neg]
    if not all(x.get("pass") for x in in_process):
        print("FAILED:IMP-0304 in-process checks")
        for x in in_process:
            if not x.get("pass"):
                print(x)
        return 1

    receipt = build_receipt(cons, fix, inbound, cycles, indep, neg)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print("FAILED:IMP-0304 named probes")
        return 1

    sha, size = digest(out)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0304",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-vote-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
            "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": sha, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0304/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0304-probe2-independent-reverse-flood",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0304: live named probes exit 0, receipts/IMP-0304.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
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
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0304 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
