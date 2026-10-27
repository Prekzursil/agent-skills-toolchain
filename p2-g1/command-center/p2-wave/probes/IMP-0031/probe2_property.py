#!/usr/bin/env python3
"""IMP-0031 probe2: independent property probe + adversarial reviewer triple.

Reviewer obligation (receipt reviewer block): an adversarial triple where ours
reorders JSON keys, adds a leading comment and a timeout key, while theirs adds
gamma — the structural merge must keep comment + timeout + gamma without a
conflict. Then the seeded unique-ours-line property over 200 triples, plus the
two-way-overwrite negative control which must FAIL the same property.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.ours_invariant import make_triple, run_property, unique_ours_lines  # noqa: E402
from plugin.three_way_merge import merge_bytes, two_way_overwrite  # noqa: E402


def reviewer_triple() -> bool:
    base = '{\n  "alpha": "one",\n  "beta": "two"\n}\n'
    ours = ('// user added a comment and reordered\n'
            '{\n  "beta": "two",\n  "alpha": "one",\n  "timeout": 30\n}\n')
    theirs = '{\n  "alpha": "one",\n  "beta": "two",\n  "gamma": "three"\n}\n'
    res = merge_bytes(base.encode(), ours.encode(), theirs.encode(), "reviewer.json")
    body = "\n".join(
        ln for ln in (res.text or "").splitlines() if not ln.lstrip().startswith("//")
    )
    doc = json.loads(body)
    ok = (
        res.status == "merged"
        and res.strategy == "json"
        and doc == {"alpha": "one", "beta": "two", "gamma": "three", "timeout": 30}
        and (res.report or {}).get("comments_preserved", 0) >= 1
        and res.text is not None
        and res.text.startswith("//")
    )
    print(json.dumps({"reviewer_triple": {
        "status": res.status, "strategy": res.strategy,
        "comment_kept": bool(res.text and res.text.startswith("//")),
        "keys": sorted(doc), "conflicts": len(res.conflicts)}}))
    return ok


def overwrite_control() -> int:
    rng = random.Random(31)
    fired = 0
    for _ in range(200):
        base, ours, theirs = make_triple(rng)
        uniq = unique_ours_lines(base, ours, theirs)
        if not uniq:
            continue
        res = two_way_overwrite(
            "".join(base).encode(), "".join(ours).encode(), "".join(theirs).encode(), "notes.md"
        )
        text = res.text or ""
        if any(ln not in text for ln in uniq):
            fired += 1
    return fired


def main() -> int:
    if not reviewer_triple():
        print("FAILED:IMP-0031-probe2 reviewer triple violated")
        return 1
    rep = run_property(merge_bytes, n=200, seed=31)
    fired = overwrite_control()
    ok = bool(rep["ok"] and rep["failures"] == 0 and rep["with_unique_ours_lines"] > 0 and fired > 0)
    out = {
        "property_ok": rep["ok"],
        "failures": rep["failures"],
        "with_unique": rep["with_unique_ours_lines"],
        "samples": rep["samples"],
        "overwrite_failures": fired,
        "pass": ok,
    }
    print(json.dumps({"property": {k: rep[k] for k in ("samples", "seed", "failures", "ok")},
                      "overwrite_failures": fired, "pass": ok}, sort_keys=True))
    print(f"property_ok={ok} overwrite_failures={fired}")
    if not ok:
        print("FAILED:IMP-0031-probe2 property or control failed")
        return 1
    print("SUCCESS:IMP-0031-probe2 property holds; overwrite control fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
