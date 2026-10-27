#!/usr/bin/env python3
"""WFA-0052 probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's headline claims from its own raw rows on a separate
code path (never re-running the original builder logic), runs the live
both-states mutation control, and byte-compares the per-unit manifest
registration against the live artifact (LF-normalized sha256, matching
_measure_one_delivered.py). Fixtures from the prior Linux build are absent on
this worktree; where inputs are absent the re-derivation is from recorded raw
rows only and says so. Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/wfa/WFA-0052-adapter-github-actions.json"
MANIFEST = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0052" / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0052"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lr(doc):
    return doc.get("extensions", {}).get("legacy_root", doc)


def lf_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rederive(doc, chk, lr):
    ctl = (lr.get("evidence_a") or {}).get("control") or {}
    nodes = ctl.get("nodes") or []
    edges = [(e.get("from"), e.get("to")) for e in ctl.get("edges") or []]
    chk(ctl.get("ast_edge_count") == ctl.get("text_edge_count") == len(edges),
        "edge-count-extractors-mismatch")
    chk(ctl.get("extractors_agree") is True and ctl.get("pass") is True,
        "extractors-disagree")
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for s, t in edges:
        out[s].append(t)
        indeg[t] += 1
    ready = sorted(n for n in nodes if indeg[n] == 0)
    topo = []
    while ready:
        n = ready.pop(0)
        topo.append(n)
        for t in sorted(out[n]):
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
                ready.sort()
    chk(topo == ctl.get("topo_kahn"), "kahn-topo-recompute-mismatch",
        "recomputed=%s recorded=%s" % (topo, ctl.get("topo_kahn")))
    chk(len(topo) == len(nodes), "needs-graph-has-cycle")
    chk(ctl.get("kahn_valid") is True and ctl.get("dfs_valid") is True,
        "recorded-validity-flags-false")
    chk((lr.get("evidence_a") or {}).get("estate_all_pass") is True, "estate-not-all-pass")
    eb = (lr.get("evidence_b") or {}).get("result") or {}
    chk(eb.get("pass") is True and eb.get("job_count_match") is True,
        "rendered-graph-compare-failed")
    chk(bool(lr.get("ir_fields_filled")), "ir-fields-unfilled")

def mutate(doc, lr):
    lr["evidence_a"]["control"]["edges"].append({"from": "d", "to": "a"})


def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:WFA-0052-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    L = lr(doc)

    rederive(doc, chk, L)

    # live both-states mutation control: the re-derivation must stay silent on
    # the intact artifact and fire on a mutated headline number.
    good_fails = []
    rederive(doc, lambda ok, label, detail="": None if ok else good_fails.append(label), L)
    chk(not good_fails, "live-control-silent-on-good-failed", ";".join(good_fails[:3]))
    mutant = copy.deepcopy(doc)
    mutate(mutant, L)
    mutant_fails = []
    rederive(mutant, lambda ok, label, detail="": None if ok else mutant_fails.append(label), L)
    chk(bool(mutant_fails), "live-control-did-not-fire-on-bad")

    # claimed control booleans in the artifact must match this live run
    for nc in doc.get("negative_controls") or []:
        if str(nc.get("id", "")).endswith("LIVE-MUTANT"):
            chk(nc.get("fired_on_bad_state") is True, "claimed-live-control-false-fire")
            chk(nc.get("silent_on_good_state") is True, "claimed-live-control-false-silent")

    # manifest byte-compare (LF-normalized, matching _measure_one_delivered.py)
    chk(MANIFEST.is_file(), "manifest-absent")
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live = lf_sha(OUT)
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
        chk(bool(rows), "manifest-row-absent")
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\", "/") == "command-center/wfa/WFA-0052-adapter-github-actions.json"
                 and str(a.get("sha256") or "") == live
                 and a.get("present") is True]
        chk(bool(match), "manifest-sha-mismatch-live",
            "live=" + live[:16] + " rows=" + repr([str(a.get("sha256"))[:16] for a in rows]))

    if fails:
        for f in fails[:12]:
            print("FAILED:WFA-0052-probe2 " + f)
        return 1
    print("SUCCESS:WFA-0052-probe2 re-derivation + live mutant control + manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
