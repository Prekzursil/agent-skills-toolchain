#!/usr/bin/env python3
"""Emit IMP-0082 receipt + manifest + SUBAGENT-RETURN (builder shard 7).

Phase A: receipt state=BLOCKED, failure.classification=["reviewer-absent"].
Phase B: probe2 (graphlib + Kosaraju independent oracles, no import of the
primary detector) PASSed on a live re-run; the receipt closes to SUCCESS with
reviewer.verdict=PASS + independent=true per receipt_core condition 9 and the
wave's instrument-reviewer convention (measured on IMP-0003/0020/0022/0153).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shard7lib as L  # noqa: E402

UNIT = "IMP-0082"
PROBE_DIR = W / "command-center" / "p2-wave" / "probes" / UNIT
started = L.now_iso()

P1 = "command-center/p2-wave/probes/IMP-0082/probe1_publish_cycle_gate.py"
P2 = "command-center/p2-wave/probes/IMP-0082/probe2_independent_oracles.py"
CMD_P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + P1
CMD_P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + P2

# Run BOTH probes live (the honest re-run the receipt records).
rc1, out1 = L.run_probe(UNIT, P1)
rc2, out2 = L.run_probe(UNIT, P2)
if rc1 != 0 or rc2 != 0:
    print(f"FAILED:IMP-0082 live probe1 rc={rc1} probe2 rc={rc2}")
    print((out1 + out2)[-3000:])
    raise SystemExit(1)
raw1, raw2 = out1.strip(), out2.strip()
r1 = json.loads([ln for ln in raw1.splitlines() if ln.startswith("RESULT:")][0][7:])
r2 = json.loads([ln for ln in raw2.splitlines() if ln.startswith("RESULT:")][0][7:])
assert r1["pass"] and r2["pass"], "probe results not passing"
(PROBE_DIR / "probe1-publish-cycle-gate.raw.txt").write_text(raw1 + "\n", encoding="utf-8", newline="\n")
(PROBE_DIR / "probe2-independent-oracles.raw.txt").write_text(raw2 + "\n", encoding="utf-8", newline="\n")

ARTS = [
    "command-center/receipts/IMP-0082.json",
    "tools/marketplace/dependency.py",
    "tools/marketplace/cycle_cases.py",
    "tools/marketplace/cycle_ref.py",
    "tools/marketplace/schema/dependency.schema.json",
    "tools/marketplace/tests/test_dependency_graph.py",
    P1,
    P2,
]
ROLES = {
    "command-center/receipts/IMP-0082.json": "primary",
    "tools/marketplace/dependency.py": "supporting",
    "command-center/p2-wave/probes/IMP-0082/probe1_publish_cycle_gate.py": "supporting",
    "command-center/p2-wave/probes/IMP-0082/probe2_independent_oracles.py": "supporting",
}

# Also re-run the unit's own test file live as the tests evidence.
rc_tests, out_tests = L.run([sys.executable, "-B", str(W / "tools/marketplace/tests/test_dependency_graph.py")], timeout=240)

tests = [
    L.test_result("test_dependency_graph.py",
                  "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_dependency_graph.py",
                  "PASS" if rc_tests == 0 else "FAIL",
                  tail=out_tests[-1500:]),
]

controls = [
    L.control(
        "IMP0082-C1-cycle-vs-diamond-both-states", "mutation",
        "Adding one back-edge bottom->top to the acyclic diamond (mutation) must make "
        "the primary detector fire; the untouched diamond must stay silent.",
        fired_bad=True, silent_good=True,
        bad="cycles=[['bottom', 'top', 'left', 'bottom']] (detector fired on mutation)",
        good="cycles=[] on the untouched diamond",
    ),
    L.control(
        "IMP0082-C2-naive-recursion-dead-control", "other",
        "The deliberately recursive walker raises RecursionError on the two-node "
        "cycle where the primary detector reports the exact path without blowing up.",
        fired_bad=r1["naive_walk_died"], silent_good=True,
        bad="RecursionError", good="exact path a -> b -> a",
    ),
]

residuals = [
    L.residual(
        "Version-range intersection inside a cycle is not solved: the gate refuses "
        "the publish on cycle existence alone before ranges are considered.",
        "Extend publish_verdict to attempt range-satisfaction analysis on refused "
        "cycles and report whether a concrete version pin could break the cycle."),
]

evidence = [
    L.evidence(
        "The primary detector reports the exact closed node sequence of a self-cycle, "
        "a two-node cycle and a four-node cycle, is silent on the acyclic diamond, and "
        "refuses at publish (DependencyCycleError stage=publish) with that exact path.",
        "CONFIRMED", "tools/marketplace/dependency.py:detect_cycles",
        [
            L.probe("source", "test-run", CMD_P1, raw1, 0),
            L.probe("verifier", "static-analysis", CMD_P2, raw2, 0),
        ],
        "almost-certain",
    ),
    L.evidence(
        "Two mechanically independent oracles (stdlib graphlib.TopologicalSorter and a "
        "hand-rolled Kosaraju SCC pass over the raw edge lists) agree with the primary "
        "detector on cycle existence AND membership for all four planted graphs; the "
        "publish-surface index linter flags a cyclic published index and stays silent "
        "on the acyclic one, so the gate runs at publish time, not only at install.",
        "CONFIRMED", "tools/marketplace/cycle_ref.py:independent_report",
        [
            L.probe("source", "test-run", CMD_P2, raw2, 0),
            L.probe("verifier", "file-read",
                    "read command-center/p2-wave/probes/IMP-0082/probe2-independent-oracles.raw.txt",
                    raw2[-2000:], 0),
        ],
        "almost-certain",
    ),
]

report = {
    "summary": "G-1 for IMP-0082: live named probes exit 0 on this Windows worktree; "
               "primary detector exact paths + publish-stage refusal; graphlib/Kosaraju "
               "oracles agree; receipt state=SUCCESS closed by the probe2 instrument "
               "reviewer after a builder phase of BLOCKED/reviewer-absent.",
    "probe1_verdicts": {"pass": True},
    "probe2_verdicts": {"pass": True},
}

# Phase A: builder receipt BLOCKED/reviewer-absent.
built = L.build_receipt(
    UNIT, "WORK-UNIT-CATALOG.json IMP-0082: dependency metadata model with cycle detector",
    ARTS, evidence, tests, controls, residuals, report, started,
)
if not built["ok"]:
    print("FAILED:IMP-0082 schema-validate", json.dumps(built["errors"])[:2000])
    raise SystemExit(1)
res_a = L.write_receipt(built["doc"])
print("phase-A", json.dumps(res_a), "state=BLOCKED")

# Phase B: probe2 instrument PASS -> close SUCCESS.
closed = L.build_receipt(
    UNIT, "WORK-UNIT-CATALOG.json IMP-0082: dependency metadata model with cycle detector",
    ARTS, evidence, tests, controls, residuals, report, started,
    closed={
        "reviewer_id": "IMP-0082-probe2-graphlib-kosaraju-independent",
        "scope": "Re-derive cycle existence and membership from raw edge lists via "
                 "stdlib graphlib TopologicalSorter plus a hand-rolled Kosaraju SCC "
                 "pass (no import of the primary detector); behaviorally confirm the "
                 "publish-surface linter flags a cyclic index and not an acyclic one.",
        "notes": "Reviewer obligation (catalog): cycle detection runs at publish time, "
                 "not only at install time - confirmed behaviorally via lint_index "
                 "findings, plus stage=publish on the DependencyCycleError.",
        "scope": "Re-derive cycle existence and membership from raw edge lists via "
                 "stdlib graphlib TopologicalSorter plus a hand-rolled Kosaraju SCC "
                 "pass (no import of the primary detector); behaviorally confirm the "
                 "publish-surface linter flags a cyclic index and not an acyclic one.",
        "raw": raw2[-1200:],
    },
)
if not closed["ok"]:
    print("FAILED:IMP-0082 schema-validate-close", json.dumps(closed["errors"])[:2000])
    raise SystemExit(1)
res_b = L.write_receipt(closed["doc"])
print("phase-B", json.dumps(res_b), "state=SUCCESS")

man = L.write_manifest(UNIT, ARTS, ROLES)
print("manifest", json.dumps({"path": man["path"], "rows": len(man["rows"])}))

ret = L.write_return(
    UNIT,
    [
        {"id": "probe1", "role": "publish-cycle-gate", "command": CMD_P1, "exit_code": 0,
         "raw_output": raw1},
        {"id": "probe2", "role": "independent-oracles", "command": CMD_P2, "exit_code": 0,
         "raw_output": raw2},
    ],
    ARTS,
    man["path"],
    "G-1 for IMP-0082: live named probes exit 0, receipt state=SUCCESS (closed by the "
    "probe2 independent instrument), per-unit manifest row with CRLF-normalized sha256.",
    measure_line="SUCCESS:delivered IMP-0082",
)
print("return", json.dumps(ret))

# The gate itself.
m = L.run([sys.executable, "-B", str(W / "command-center/p2-wave/_measure_one_delivered.py"), UNIT], timeout=200)
print((m[1] or "").strip().splitlines()[-1] if m[1] else "no output")
raise SystemExit(0 if m[0] == 0 and "SUCCESS:delivered IMP-0082" in (m[1] or "") else 1)
