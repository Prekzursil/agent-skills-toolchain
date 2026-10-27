#!/usr/bin/env python
"""Mechanical near-duplicate detector over the bp-6 blueprints, by MECHANISM not wording.

Why this is code and not a judgement call
-----------------------------------------
"Are two of these the same workflow?" decomposes into set membership and counting over
structural features, and a mechanical comparison handed to model judgement measured 86%
accurate with 100% of the errors pointing one way. So the comparison is an algorithm.

The fingerprint deliberately EXCLUDES prose (name, description, titles, narratives). Two
blueprints written in different words about the same mechanism must still collide, and two
written in similar words about different mechanisms must not.

Both-states control (rule 3b): the run synthesises a KNOWN DUPLICATE - a deep copy of one
blueprint with only its id, name, description and tags changed - and requires the detector to
flag it. A detector that stays silent on a copy measures nothing, so a silent control is a
FAILURE of this script, not a pass for the corpus.

Usage (repo root)::

    python platform/lib/workflows/_bp6_distinctness.py [--threshold 0.85] [--json OUT]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for _entry in (str(REPO_ROOT / "platform" / "lib"), str(HERE)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Imported by module name rather than as a package: this directory is shared with sibling
# units and deliberately carries no __init__.py, so adding one to enable a package import
# would change pytest's module-naming semantics for every sibling test file in here.
from _bp6_validate_report import BP6_FILES, WORKFLOW_DIR  # noqa: E402

#: Above this Jaccard similarity on the mechanism fingerprint a pair is a near-duplicate
#: candidate that must be merged or justified. Calibrated by the control below: an exact copy
#: scores 1.0, so any threshold under 1.0 catches it; 0.85 was chosen because the widest
#: genuine pair in this corpus measures well below it (printed on every run, so the margin is
#: visible rather than asserted).
DEFAULT_THRESHOLD = 0.85


def _stages(doc: Any) -> list[dict[str, Any]]:
    """Every stage in the document, depth-first, including nested bodies and repair arms."""
    out: list[dict[str, Any]] = []

    def walk(stages: Any) -> None:
        if not isinstance(stages, list):
            return
        for st in stages:
            if not isinstance(st, dict):
                continue
            out.append(st)
            walk(st.get("body"))
            for key in ("diagnose", "repair", "verify"):
                sub = st.get(key)
                if isinstance(sub, dict):
                    out.append(sub)
                    walk(sub.get("body"))

    walk(doc.get("stages"))
    return out


def _expr_tokens(expr: Any) -> set[str]:
    """Identifier-ish tokens of an expression, structured or string form."""
    tokens: set[str] = set()
    if isinstance(expr, str):
        cur = ""
        for ch in expr:
            if ch.isalnum() or ch in "_.-":
                cur += ch
            else:
                if cur:
                    tokens.add(cur)
                cur = ""
        if cur:
            tokens.add(cur)
        return {t for t in tokens if not t.isdigit() and t not in {"AND", "OR", "NOT"}}
    if isinstance(expr, dict):
        for v in expr.values():
            if isinstance(v, (str, dict)):
                tokens |= _expr_tokens(v)
            elif isinstance(v, list):
                for item in v:
                    tokens |= _expr_tokens(item)
    return tokens


def fingerprint(doc: dict[str, Any]) -> set[str]:
    """The mechanism fingerprint: structure and control flow, never prose."""
    fp: set[str] = set()
    stages = _stages(doc)

    kind_counts: dict[str, int] = {}
    for st in stages:
        kind_counts[str(st.get("kind"))] = kind_counts.get(str(st.get("kind")), 0) + 1
    for kind, count in kind_counts.items():
        fp.add(f"kind:{kind}:{count}")

    for st in stages:
        over = st.get("over")
        if isinstance(over, dict):
            fp.add(f"fanout-source:{over.get('source')}")
            fp.add(f"fanout-concurrency-band:{_band(st.get('max_concurrency'))}")
            fp.add(f"fanout-on-item-failure:{st.get('on_item_failure')}")
        bar = st.get("barrier")
        if isinstance(bar, dict):
            fp.add(f"barrier:{bar.get('mode')}:{bar.get('on_partial')}")
        conv = st.get("convergence")
        if isinstance(conv, dict):
            fp.add(f"convergence-on-no-convergence:{conv.get('on_no_convergence')}")
            for m in conv.get("metrics") or []:
                if isinstance(m, dict):
                    fp.add(f"convergence-metric:{m.get('name')}")
        if st.get("kind") == "human_checkpoint":
            fp.add(
                f"checkpoint-timeout:{st.get('on_timeout')}:{st.get('approval_mode')}"
            )
        if st.get("kind") == "repair_loop":
            fp.add(f"repair-attempts-band:{_band(st.get('max_attempts'))}")
        if st.get("kind") == "subworkflow":
            wf = st.get("workflow")
            if isinstance(wf, dict) and wf.get("workflow_id"):
                fp.add(f"calls-subworkflow:{wf['workflow_id']}")

    for gname, g in (doc.get("gates") or {}).items():
        if not isinstance(g, dict):
            continue
        fp.add(f"gate-predicate:{g.get('predicate')}:{g.get('on_fail')}")
        for tok in _expr_tokens(g.get("expression")):
            fp.add(f"gate-metric:{tok}")

    for rule in doc.get("stopping_rules") or []:
        if isinstance(rule, dict):
            fp.add(f"stop-on-stop:{rule.get('on_stop')}")
            for tok in _expr_tokens(rule.get("expression")):
                fp.add(f"stop-metric:{tok}")

    retry = doc.get("retry_policy") or {}
    fp.add(f"retry:{retry.get('strategy')}")
    fail = doc.get("failure_policy") or {}
    fp.add(f"failure:{fail.get('on_failure')}")
    for cls in fail.get("classify_as") or []:
        fp.add(f"failure-class:{cls}")

    rep = doc.get("replay") or {}
    fp.add(
        f"replay:{rep.get('deterministic')}:{rep.get('verify')}:{rep.get('on_divergence')}"
    )
    cache = doc.get("cache") or {}
    fp.add(f"cache:{cache.get('enabled')}:{cache.get('scope')}")

    declared = (doc.get("x_extensions") or {}).get("mechanism_fingerprint") or {}
    for key in ("primary", "distinguishing_stage", "distinguishing_gate"):
        if declared.get(key):
            fp.add(f"declared-{key}:{declared[key]}")

    for spec in (doc.get("outputs") or {}).values():
        if isinstance(spec, dict) and spec.get("schema_ref"):
            fp.add(f"output-schema:{spec['schema_ref']}")

    return fp


def _band(value: Any) -> str:
    """Bucket a small integer so 5-vs-6 concurrency is not treated as a mechanism difference."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "none"
    if n <= 1:
        return "serial"
    if n <= 4:
        return "small"
    if n <= 16:
        return "medium"
    return "large"


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def output_paths(doc: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for spec in (doc.get("outputs") or {}).values():
        if isinstance(spec, dict) and spec.get("path"):
            paths.add(str(spec["path"]))
    for st in _stages(doc):
        for spec in st.get("produces") or []:
            if isinstance(spec, dict) and spec.get("path"):
                paths.add(str(spec["path"]))
        dec = st.get("decision_artifact")
        if isinstance(dec, dict) and dec.get("path"):
            paths.add(str(dec["path"]))
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bp6-distinctness")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    docs: dict[str, dict[str, Any]] = {}
    for name in BP6_FILES:
        path = WORKFLOW_DIR / name
        if not path.is_file():
            print(f"FAILED:bp6-distinctness missing {name}")
            return 1
        docs[name] = json.loads(path.read_text(encoding="utf-8"))

    if not docs:
        print("FAILED:bp6-distinctness no inputs found")
        return 1

    fps = {name: fingerprint(doc) for name, doc in docs.items()}
    pairs = []
    for a, b in combinations(sorted(fps), 2):
        pairs.append((jaccard(fps[a], fps[b]), a, b))
    pairs.sort(reverse=True)

    # --- both-states control: a synthetic duplicate MUST be flagged -------------------
    victim = sorted(docs)[0]
    clone = copy.deepcopy(docs[victim])
    clone["id"] = "synthetic-duplicate-control"
    clone["name"] = "A deliberately renamed copy used as a detector control"
    clone["description"] = (
        "Different words. Identical mechanism. The detector must flag it."
    )
    clone["tags"] = ["control"]
    control_score = jaccard(fingerprint(clone), fps[victim])
    control_fires = control_score >= args.threshold

    # declared primaries must be unique, and no two blueprints may claim one artifact path
    primaries: dict[str, list[str]] = {}
    for name, doc in docs.items():
        p = ((doc.get("x_extensions") or {}).get("mechanism_fingerprint") or {}).get(
            "primary"
        )
        primaries.setdefault(str(p), []).append(name)
    duplicate_primaries = {k: v for k, v in primaries.items() if len(v) > 1}

    path_owner: dict[str, list[str]] = {}
    for name, doc in docs.items():
        for p in output_paths(doc):
            path_owner.setdefault(p, []).append(name)
    colliding_paths = {k: sorted(v) for k, v in path_owner.items() if len(v) > 1}

    flagged = [(s, a, b) for s, a, b in pairs if s >= args.threshold]

    report = {
        "artifact": "platform/workflows/BLUEPRINTS-BP6-DISTINCTNESS.json",
        "unit": "blueprints/bp-6",
        "blueprints": len(docs),
        "threshold": args.threshold,
        "fingerprint_sizes": {n: len(f) for n, f in sorted(fps.items())},
        "max_pairwise_similarity": pairs[0][0] if pairs else 0.0,
        "top_pairs": [
            {"similarity": round(s, 4), "a": a, "b": b} for s, a, b in pairs[:8]
        ],
        "flagged_near_duplicates": [
            {"similarity": round(s, 4), "a": a, "b": b} for s, a, b in flagged
        ],
        "duplicate_declared_primaries": duplicate_primaries,
        "colliding_artifact_paths": colliding_paths,
        "control": {
            "kind": "synthetic exact-mechanism duplicate of " + victim,
            "similarity_to_victim": round(control_score, 4),
            "detector_fires_on_known_duplicate": control_fires,
        },
    }
    ok = (
        control_fires
        and not flagged
        and not duplicate_primaries
        and not colliding_paths
    )
    report["ok"] = ok

    print(f"blueprints           : {len(docs)}")
    print(f"threshold            : {args.threshold}")
    print(f"max pairwise sim     : {report['max_pairwise_similarity']:.4f}")
    for row in report["top_pairs"][:5]:
        print(f"   {row['similarity']:.4f}  {row['a']}  ~  {row['b']}")
    print(
        f"CONTROL (known dup)  : sim={control_score:.4f} fires={control_fires}"
        f"  <- must be True, or the detector measures nothing"
    )
    print(f"flagged near-dupes   : {len(flagged)}")
    print(f"duplicate primaries  : {duplicate_primaries or 'none'}")
    print(f"colliding paths      : {colliding_paths or 'none'}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")

    print("SUCCESS:bp6-distinctness" if ok else "FAILED:bp6-distinctness")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
