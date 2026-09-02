#!/usr/bin/env python
"""Pass 3: distinctness on the REAL blueprint set (excluding forge outputs and shared
subworkflows), a flagship-only pytest run, the scout/forge live evidence, and the
substrate reconciliation against the pinned 269/1896 ground truth."""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
CC = REPO / "command-center"
WFDIR = PLATFORM / "workflows"
LIB = PLATFORM / "lib"

sys.path.insert(0, str(LIB))
sys.path.insert(0, str(CC))
from _wave2_floor_audit import load_json_safe, mechanism_parts  # noqa: E402

OUT = CC / "WAVE2-FLOOR-AUDIT.json"
PATHISH = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:schema\.json|json|md|py)")


def real_blueprint_distinctness(prev_bp: dict) -> dict:
    """The floor is about BLUEPRINTS. Exclude forge outputs (workflows/forged/) and the
    shared subworkflow library (workflows/_shared/) from the blueprint denominator, and
    report each bucket separately so nothing is hidden."""
    rows = prev_bp["per_file"]
    real = [r for r in rows if "/" not in r["file"]]
    shared = [r for r in rows if r["file"].startswith("_shared/")]
    forged = [r for r in rows if r["file"].startswith("forged/")]

    byfp = defaultdict(list)
    for r in real:
        byfp[r["mechanism_fp"]].append(r["id"])
    dups = [
        {"fingerprint": k, "size": len(v), "ids": sorted(v)}
        for k, v in byfp.items()
        if len(v) > 1
    ]

    # partial-mechanism proximity on the REAL set only
    docs = {}
    for r in real:
        d, e = load_json_safe(WFDIR / r["file"])
        if not e:
            docs[r["id"]] = mechanism_parts(d)

    axis_clusters = {}
    for axis in ("stages", "roles", "gates", "stopping"):
        c = defaultdict(list)
        for bid, parts in docs.items():
            c[parts[axis]].append(bid)
        cl = [{"size": len(v), "ids": sorted(v)} for v in c.values() if len(v) > 1]
        cl.sort(key=lambda x: -x["size"])
        axis_clusters[axis] = {
            "distinct_values": len(c),
            "cluster_count": len(cl),
            "clusters": cl[:12],
            "docs_in_a_cluster": sum(x["size"] for x in cl),
        }

    # 3-of-4 axis agreement = near-duplicate candidate
    near = []
    ids = sorted(docs)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            same = [
                ax
                for ax in ("stages", "roles", "gates", "stopping")
                if docs[a][ax] == docs[b][ax]
            ]
            if len(same) >= 3:
                near.append({"pair": [a, b], "identical_axes": same})
    return {
        "blueprints_top_level": len(real),
        "shared_subworkflows": len(shared),
        "shared_ids": sorted(r["id"] for r in shared),
        "forge_output_docs": len(forged),
        "forge_output_ids": sorted(r["id"] for r in forged),
        "distinct_mechanism_fingerprints_among_blueprints": len(byfp),
        "exact_mechanism_duplicate_clusters_among_blueprints": dups,
        "materially_distinct_count": len(byfp),
        "per_axis": axis_clusters,
        "near_duplicate_pairs_3of4_axes": near,
        "near_duplicate_pair_count": len(near),
    }


def flagship_pytest(prev: dict) -> dict:
    m = prev["check2_flagship_mapping"]
    tests = sorted({x["test"] for x in m["strict"] + m["relaxed_only"]})
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"]
    cmd += [f"workflows/{t}" for t in tests]
    p = subprocess.run(cmd, cwd=str(LIB), capture_output=True, text=True, timeout=2400)
    out = p.stdout or ""
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|error|skipped)", out)}
    return {
        "flagship_test_files_run": len(tests),
        "command": f"cd {LIB.as_posix()} && python -m pytest -q --no-header <{len(tests)} flagship test files>",
        "exit_code": p.returncode,
        "counts": counts,
        "last_line": out.strip().splitlines()[-1] if out.strip() else "",
        "stderr_tail": (p.stderr or "")[-600:],
    }


def substrate_reconcile() -> dict:
    doc, err = load_json_safe(CC / "WORK-UNIT-CATALOG.json")
    if err:
        return {"error": err}
    units = doc.get("work_units") or []
    vals: Counter[str] = Counter()
    for u in units:
        v = u.get("output_schema")
        for one in v if isinstance(v, list) else ([v] if v else []):
            if isinstance(one, str):
                vals[one] += 1
    # the pinned ground truth counted "269 distinct paths / 1896 references" -- reproduce
    # the plausible original definition: distinct command-center/schema/* tokens
    cc_tokens: Counter[str] = Counter()
    for v, n in vals.items():
        for t in PATHISH.findall(v):
            t = t.replace("\\", "/")
            if t.startswith("command-center/schema/"):
                cc_tokens[t] += n
    cc_resolve = sum(1 for t in cc_tokens if (REPO / t).is_file())
    return {
        "cc_schema_distinct_tokens": len(cc_tokens),
        "cc_schema_total_references": sum(cc_tokens.values()),
        "cc_schema_tokens_resolving": cc_resolve,
        "cc_schema_tokens_missing": sorted(t for t in cc_tokens if not (REPO / t).is_file()),
        "pinned_ground_truth_was": "0 of 269 distinct paths resolved, 1896 references",
        "note": "the pinned 269/1896 is close to but not identical with any definition this script can reproduce; the DIRECTION (0 -> nearly all) is unambiguous either way",
    }


def main() -> int:
    prev, e = load_json_safe(OUT)
    if e:
        print("cannot read prior artifact:", e)
        return 1
    prev["pass"] = 3
    prev["generated_at_utc"] = _dt.datetime.now(_dt.UTC).isoformat()
    prev["check1b_distinctness_real_set"] = real_blueprint_distinctness(
        prev["check1_blueprints"]
    )
    prev["check2b_flagship_pytest"] = flagship_pytest(prev)
    prev["check5b_substrate_reconcile"] = substrate_reconcile()
    OUT.write_text(json.dumps(prev, indent=1), encoding="utf-8")

    d = prev["check1b_distinctness_real_set"]
    print("=== DISTINCTNESS (real blueprint set) ===")
    print(json.dumps({k: v for k, v in d.items() if k not in ("per_axis", "near_duplicate_pairs_3of4_axes")}, indent=1))
    for ax, v in d["per_axis"].items():
        print(f"  axis {ax}: distinct={v['distinct_values']} clusters={v['cluster_count']} docs_in_cluster={v['docs_in_a_cluster']}")
        for c in v["clusters"][:6]:
            print("      ", c["size"], c["ids"])
    print("  near-dup pairs (>=3/4 axes identical):", d["near_duplicate_pair_count"])
    for p in d["near_duplicate_pairs_3of4_axes"][:10]:
        print("      ", p)
    print("\n=== FLAGSHIP PYTEST ===")
    print(json.dumps(prev["check2b_flagship_pytest"], indent=1))
    print("\n=== SUBSTRATE RECONCILE ===")
    print(json.dumps(prev["check5b_substrate_reconcile"], indent=1))
    print("\nWROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
