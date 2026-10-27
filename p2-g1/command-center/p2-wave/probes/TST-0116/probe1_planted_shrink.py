#!/usr/bin/env python3
# TST-0116 probe1: planted invariant violation found + shrunk (live, fail-closed).
# Rebuild 2026-10-26 (shard19-w3 resume): the prior builder died mid-flight
# before this probe dir landed. Re-derives the receipt claim live on the
# tools/proptest substrate: a workflow-DAG acyclicity property is violated by
# a planted 2-cycle (recorded seed 1160116, 12-node generated DAG), the
# violation is shrunk to the minimal 2-node cyclic core under the recorded
# node-edge-drop-v1 policy, the same seed replays identically, the good-state
# twin (plant_cycle=False) is silent, and the live substrate controls
# (runner.run_planted_shrink, report.planted_report) behave.
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0116"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
SEED = 1160116
N_NODES = 12
fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def gen_dag(seed, plant_cycle):
    # Deterministic 12-node workflow DAG; optionally plant a 2-cycle.
    rng = random.Random(seed)
    nodes = ["n%d" % i for i in range(N_NODES)]
    edges = [(nodes[i], nodes[i + 1]) for i in range(N_NODES - 1)]
    for _ in range(4):
        i = rng.randrange(N_NODES)
        j = rng.randrange(N_NODES)
        if j > i and (nodes[i], nodes[j]) not in edges:
            edges.append((nodes[i], nodes[j]))
    a = rng.randrange(N_NODES)
    b = rng.randrange(N_NODES)
    if b == a:
        b = (a + 1) % N_NODES
    if plant_cycle:
        edges.append((nodes[a], nodes[b]))
        edges.append((nodes[b], nodes[a]))
    return nodes, edges


def shrink(nodes, edges, cyclic_fn):
    # node-edge-drop-v1: drop nodes in index order while still cyclic, then edges.
    keep_n = list(nodes)
    keep_e = list(edges)
    for n in nodes:
        trial_n = [x for x in keep_n if x != n]
        trial_e = [(x, y) for (x, y) in keep_e if x != n and y != n]
        if cyclic_fn(trial_n, trial_e):
            keep_n, keep_e = trial_n, trial_e
    for e in list(keep_e):
        trial_e = [x for x in keep_e if x != e]
        if cyclic_fn(keep_n, trial_e):
            keep_e = trial_e
    return keep_n, keep_e


def main():
    try:
        sys.path.insert(0, str(REPO))
        sys.path.insert(0, str(REPO / "tools"))
        from proptest import report as rp
        from proptest import runner as rn
        from proptest import shrink as sh
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 proptest-import:" + type(exc).__name__)
        return 1
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 128, "under-min-bytes", str(OUT.stat().st_size))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk(("SUCCESS:" + UNIT) in text, "sentinel-absent")

    cyclic_fn = rn._cyclic
    nodes, edges = gen_dag(SEED, True)
    good_nodes, good_edges = gen_dag(SEED, False)

    # 1) violation found on the planted DAG; 2) good twin silent (NC1 both-states).
    chk(cyclic_fn(nodes, edges), "planted-violation-not-found")
    chk(not cyclic_fn(good_nodes, good_edges), "good-twin-not-silent")

    # 3-6) shrink to the minimal cyclic core.
    sn, se = shrink(nodes, edges, cyclic_fn)
    chk(cyclic_fn(sn, se), "shrunk-core-acyclic")
    chk(len(sn) < len(nodes), "shrink-not-smaller")
    chk(len(sn) == 2, "shrunk-size", str(len(sn)))
    minimal = (len(se) == 2 and set(se) == {(sn[0], sn[1]), (sn[1], sn[0])})
    chk(minimal, "shrunk-not-minimal-2cycle", str(se))

    # 7-8) replay identical and run-to-run determinism.
    rn_nodes, rn_edges = gen_dag(SEED, True)
    sn2, se2 = shrink(rn_nodes, rn_edges, cyclic_fn)
    chk((sn2, se2) == (sn, se), "replay-not-identical")
    first = json.dumps({"nodes": sn, "edges": [list(e) for e in se]}, sort_keys=True)
    second = json.dumps({"nodes": sn2, "edges": [list(e) for e in se2]}, sort_keys=True)
    chk(first == second, "not-deterministic")
    print("seed=%d original_nodes=%d shrunk_nodes=%d replay_identical=%s"
          % (SEED, len(nodes), len(sn), (sn2, se2) == (sn, se)))

    # 9) live substrate control: the package planted-shrink run passes.
    run = rn.run_planted_shrink(seed=SEED % 100000)
    chk(run.get("pass") is True, "substrate-run-failed", json.dumps(run)[:200])
    chk(run.get("replay_identical") is True, "substrate-replay-not-identical")

    # 10) live counterexample report: verdict FAIL + shrunk present per schema.
    pr = rp.planted_report()
    for field in (rp.REPORT_SCHEMA.get("required") or []):
        chk(field in pr.get("report") or field in pr, "report-schema-missing:" + field)
    rep_verdict = (pr.get("report") or {}).get("verdict")
    chk(rep_verdict == "FAIL", "report-verdict", str(rep_verdict))
    chk(bool((pr.get("report") or {}).get("shrunk")), "report-shrunk-absent")

    # 11) recorded shrink policy identity.
    chk(sh.SHRINK_POLICY.get("name") == "node-edge-drop-v1" and sh.SHRINK_POLICY.get("deterministic") is True,
        "shrink-policy-drift", json.dumps(sh.SHRINK_POLICY))

    # Receipt internal: the recorded shrink evidence names this unit seed family.
    seed_rec = doc.get("seed") or {}
    chk(int(seed_rec.get("value", 0)) == SEED and seed_rec.get("recorded") is True, "receipt-seed-mismatch")

    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 planted 2-cycle found at seed %d on a %d-node generated DAG, shrunk to the minimal cyclic core (2 nodes) under node-edge-drop-v1, replay identical, good twin silent, live substrate controls (runner+report) behave" % (SEED, len(nodes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
