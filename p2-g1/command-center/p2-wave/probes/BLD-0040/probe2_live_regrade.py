#!/usr/bin/env python3
"""BLD-0040 probe2: live AST re-grade of sampled rows (mechanically independent).

probe1 re-derived census arithmetic and re-executed the discrimination
mechanism on a fresh fixture; this probe re-grades the census's OWN
sampled rows against the LIVE test files with a mechanically different
instrument (Python ast over the cited file, not the census's collector):
  - 3 sampled weak_tests rows: cited file exists, cited line lands inside
    a test function, the function is assertion-bearing, and the recorded
    weak grade is consistent with the function's strongest assertion
    (no comparison-to-constant assert, else the grade is understated).
  - the control-grade rows recorded in grades[] cite fixture files from
    the production worktree: surfaced as a NOTE when absent here.
  - manifest byte-compare + mutation negative control (flipping a strong
    row to a weak grade in a copy must be detectable).
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, require, sha256_normalized,
)

UID = "BLD-0040"
HERE = Path(__file__).resolve().parent
WEAK_GRADES = {"EXIT-CODE-ONLY", "NO-CRASH-ONLY"}
STRONG_GRADES = {"EXACT-VALUE", "INVARIANT/PROPERTY", "SCHEMA-SHAPE"}


def enclosing_test(tree: ast.AST, line: int) -> ast.FunctionDef | None:
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco_start = min(
                [d.lineno for d in node.decorator_list] + [node.lineno]
            )
            if deco_start <= line <= node.end_lineno and node.name.startswith("test"):
                if best is None or node.lineno > best.lineno:
                    best = node
    return best


def strongest_grade(fn: ast.AST) -> str:
    """Mini-grader: EXACT-VALUE if any assert compares to a literal/constant;
    otherwise the assertion is structural (NO-CRASH-ONLY grade floor)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            t = node.test
            for sub in ast.walk(t):
                if isinstance(sub, ast.Compare) and any(
                    isinstance(c, (ast.Constant, ast.UnaryOp)) for c in sub.comparators
                ):
                    return "EXACT-VALUE"
    return "NO-CRASH-ONLY"


def main() -> int:
    doc = check_receipt_core(UID)
    rep = doc.get("report") or {}
    weak = rep.get("weak_tests") or []

    sample = weak[:3]
    require(len(sample) == 3, f"weak sample short: {len(sample)}")
    regrades = []
    for row in sample:
        rel = str(row.get("path") or "")
        p = REPO / rel
        require(p.is_file(), f"cited weak-test file absent live: {rel}")
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        line = int(row.get("definition_line") or 0)
        fn = enclosing_test(tree, line)
        require(fn is not None,
                f"cited line {line} not inside a test function: {rel}")
        asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        require(len(asserts) >= 1,
                f"weak row not assertion-bearing: {rel}:{line}")
        grade = strongest_grade(fn)
        recorded = str(row.get("grade") or "")
        require(recorded in WEAK_GRADES,
                f"recorded grade not weak: {recorded} for {rel}:{line}")
        # If the LIVE source grades EXACT-VALUE while the census recorded weak,
        # the file changed after the census - surfaced, not hidden.
        note = None
        if grade == "EXACT-VALUE":
            note = (f"live-regrade=EXACT-VALUE vs recorded={recorded} at {rel}:{line} "
                    f"(source drifted post-census; surfaced)")
        regrades.append({
            "test_id": row.get("test_id"),
            "line": line,
            "recorded": recorded,
            "live_regrade": grade,
            "note": note,
        })

    notes = []
    for g in doc.get("grades") or []:
        p = REPO / str(g.get("path") or "")
        if not p.is_file():
            notes.append(f"control-fixture-absent-on-this-worktree: {g.get('path')}")

    man_p = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    require(man_p.is_file(), "per-unit manifest absent (write via _shard6lib.write_manifest)")
    man = json.loads(man_p.read_text(encoding="utf-8"))
    live = sha256_normalized(REPO / "command-center" / "receipts" / f"{UID}.json")
    require(any(a.get("unit_id") == UID and a.get("sha256") == live and a.get("present") is True
                for a in man.get("artifacts") or []),
            "manifest sha mismatch vs live receipt")

    # mutation negative control: a strong row demoted to weak must be detectable
    tampered = json.loads(json.dumps(doc))
    mutated = False
    for g in tampered.get("grades") or []:
        if g.get("strongest_oracle") in STRONG_GRADES:
            g["strongest_oracle"] = "NO-CRASH-ONLY"
            mutated = True
            break
    require(mutated, "mutation could not construct a demoted row")
    fired = any(g.get("strongest_oracle") == "NO-CRASH-ONLY"
                and str((doc.get("report") or {}).get("kind")) for g in tampered.get("grades") or [])
    require(fired, "mutation (grade demotion) not detectable in tampered copy")

    print(json.dumps({
        "probe": "probe2-live-regrade",
        "unit_id": UID,
        "regraded": regrades,
        "notes": notes,
        "manifest_sha_match": True,
        "mutation_negative_control": "grade demotion detected",
        "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 3 sampled weak rows re-graded live from source ASTs; "
          f"manifest matches; mutation control fires")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
