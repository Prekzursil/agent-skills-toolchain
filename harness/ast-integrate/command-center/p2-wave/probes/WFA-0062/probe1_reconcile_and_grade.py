#!/usr/bin/env python3
"""Probe 1: every conflict_map row reconciled; SOFT is not listed as HARD.

Re-runs fuse_same_stage per reconciled pair and checks the artifact's
enumerated HARD list against the solver. Does not trust author prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conflict_map import reconcile_all  # noqa: E402
from engine import fuse_same_stage, is_hard_pair  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0062-mechanism-conflicts.json"
SENTINEL = "SUCCESS:WFA-0062"
VERDICTS = {"CONFIRMED", "REFUTED", "RESTATED"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0062-probe1 {msg}")
    return 1


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def main() -> int:
    recon = reconcile_all()
    if recon["n"] != 20:
        return fail(f"conflict_map n={recon['n']} want=20")
    missing_verdict = [r["id"] for r in recon["rows"] if r.get("verdict") not in VERDICTS]
    if missing_verdict:
        return fail(f"unreconciled rows {missing_verdict}")
    for r in recon["rows"]:
        if r.get("grade") == "UNVERIFIED":
            return fail(f"row {r['id']} UNVERIFIED")
        left, right = r["mechanism_left"], r["mechanism_right"]
        fused = fuse_same_stage([left, right])
        hard = is_hard_pair(left, right)
        if hard and r["grade"] != "HARD":
            return fail(f"row {r['id']} solver HARD but grade={r['grade']}")
        if (not hard) and r["grade"] != "SOFT":
            return fail(f"row {r['id']} solver SAT but grade={r['grade']}")
        if hard and r["verdict"] not in {"CONFIRMED", "RESTATED"}:
            return fail(f"row {r['id']} HARD but verdict={r['verdict']}")
        if (not hard) and r["verdict"] != "REFUTED":
            return fail(f"row {r['id']} SOFT but verdict={r['verdict']}")
        if not r.get("incompatibility_argument"):
            return fail(f"row {r['id']} missing incompatibility_argument")
        if not r.get("worked_example"):
            return fail(f"row {r['id']} missing worked_example")
        if fused["sat"] != r["fusion_sat"]:
            return fail(f"row {r['id']} fusion_sat mismatch")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state={doc.get('state')}")
    hard_edges = [
        pair_key(e["source"], e["target"])
        for e in (doc.get("edges") or [])
        if e.get("kind") == "conflicts-with"
    ]
    for s in doc.get("soft_pairs") or []:
        key = pair_key(s["left"], s["right"])
        if key in hard_edges:
            return fail(f"SOFT pair listed as HARD {key}")
        if is_hard_pair(s["left"], s["right"]):
            return fail(f"soft_pairs entry is actually HARD {key}")
    enumerated = doc.get("enumerated_conflicts") or []
    if not enumerated:
        return fail("no enumerated HARD conflicts")
    for c in enumerated:
        if not is_hard_pair(c["left"], c["right"]):
            return fail(f"enumerated conflict is SAT {c['left']} {c['right']}")
        if c.get("grade") != "HARD":
            return fail("enumerated conflict not graded HARD")
        if not c.get("incompatibility_argument") or not c.get("worked_example"):
            return fail("enumerated conflict missing argument or example")
    rows_art = (doc.get("conflict_map_reconciliation") or {}).get("rows") or []
    if len(rows_art) != 20:
        return fail(f"artifact conflict_map n={len(rows_art)}")
    counts = {"CONFIRMED": 0, "REFUTED": 0, "RESTATED": 0}
    for r in rows_art:
        v = r.get("verdict")
        if v not in counts:
            return fail(f"artifact row verdict {v}")
        counts[v] += 1
    if 0 in counts.values():
        return fail(f"verdict coverage incomplete {counts}")
    print(
        json.dumps(
            {
                "probe": "probe1-reconcile-and-grade",
                "unit_id": "WFA-0062",
                "conflict_map_n": 20,
                "verdict_counts": counts,
                "hard_edges": len(hard_edges),
                "soft_pairs": len(doc.get("soft_pairs") or []),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0062-probe1 conflict_map reconciled; SOFT not listed as HARD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
