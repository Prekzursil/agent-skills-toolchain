"""Round-1: verify the prior build round's probe RE-RUNS against the dead agents'
ORIGINAL probe outputs. This closes grounding residual R3 ("I did not re-derive the
dead agents' numbers").

Emits sha256 for each pair, an exact-byte verdict, and for JSON pairs a semantic
key-by-key diff so a formatting-only delta is not reported as a substantive one.

Read-only apart from stdout.
"""
import hashlib
import json
import os
import sys

PO = r"C:/Users/Prekzursil/source/ast-integrate/command-center/casualty/probe-output"

PAIRS = [
    ("adv0021_probe1_out.ORIGINAL.json", "adv0021_probe1_out.RERUN.json", "json"),
    ("adv0021_results_b.ORIGINAL.json", "adv0021_results_b.RERUN.json", "json"),
    ("adv0022_probe1_out.ORIGINAL.txt", "adv0022_probe1_out.RERUN.txt", "text"),
    ("adv0022_probe2_out.ORIGINAL.txt", "adv0022_probe2_out.RERUN.txt", "text"),
]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def walk(o, prefix=""):
    """flatten a JSON tree to leaf paths -> scalar"""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(walk(v, f"{prefix}.{k}"))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(walk(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = o
    return out


report = {"generated_at_epoch": None, "pairs": []}
import time
report["generated_at_epoch"] = int(time.time())

for a, b, kind in PAIRS:
    pa, pb = os.path.join(PO, a), os.path.join(PO, b)
    row = {"original": a, "rerun": b, "kind": kind}
    if not (os.path.exists(pa) and os.path.exists(pb)):
        row["verdict"] = "MISSING"
        row["exists"] = {a: os.path.exists(pa), b: os.path.exists(pb)}
        report["pairs"].append(row)
        continue
    row["bytes"] = {a: os.path.getsize(pa), b: os.path.getsize(pb)}
    row["sha256"] = {a: sha(pa), b: sha(pb)}
    row["md5"] = {a: md5(pa), b: md5(pb)}
    row["byte_identical"] = row["sha256"][a] == row["sha256"][b]
    if kind == "json":
        try:
            da, db = json.load(open(pa, encoding="utf-8")), json.load(open(pb, encoding="utf-8"))
            fa, fb = walk(da), walk(db)
            keys = set(fa) | set(fb)
            diffs = [k for k in sorted(keys) if fa.get(k, "<ABSENT>") != fb.get(k, "<ABSENT>")]
            row["semantic_leaf_count"] = len(keys)
            row["semantic_diff_count"] = len(diffs)
            row["semantic_diff_sample"] = [
                {"key": k, "original": str(fa.get(k, "<ABSENT>"))[:200],
                 "rerun": str(fb.get(k, "<ABSENT>"))[:200]} for k in diffs[:12]
            ]
        except Exception as e:  # noqa: BLE001
            row["semantic_error"] = repr(e)
    else:
        la = open(pa, encoding="utf-8", errors="replace").read().splitlines()
        lb = open(pb, encoding="utf-8", errors="replace").read().splitlines()
        sa, sb = set(la), set(lb)
        row["lines"] = {a: len(la), b: len(lb)}
        row["only_in_original"] = sorted(sa - sb)[:25]
        row["only_in_rerun"] = sorted(sb - sa)[:25]
        row["line_diff_count"] = len(sa ^ sb)
    row["verdict"] = ("BYTE-IDENTICAL" if row["byte_identical"]
                      else ("SEMANTIC-IDENTICAL" if row.get("semantic_diff_count") == 0
                            else "DIFFERS"))
    report["pairs"].append(row)

out = os.path.join(os.path.dirname(PO), "RERUN-EQUIVALENCE.json")
json.dump(report, open(out, "w", encoding="utf-8"), indent=2)
print(json.dumps(report, indent=2)[:12000])
print("\nWROTE", out, os.path.getsize(out), "B")
