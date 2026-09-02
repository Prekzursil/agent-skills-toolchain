#!/usr/bin/env python3
"""Probe 2: overlap is symmetric and reflexive; Windows case pair; case-sensitive mutant is red."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "leases"))

import overlap  # noqa: E402

WIN_A = "src/Foo.py"
WIN_B = "src/foo.py"


def windows_case_must_overlap(fn) -> None:
    got = fn(WIN_A, WIN_B, os_family="windows")
    if got is not True:
        raise AssertionError(f"windows case-only pair must overlap, got {got!r}")


def case_sensitive_mutant(a: str, b: str, *, os_family: str = "posix", ignore_case=None) -> bool:
    """Mutation: force case-sensitive comparison even on Windows."""
    return overlap.paths_overlap(a, b, os_family=os_family, ignore_case=False)


def main() -> int:
    pairs = overlap.load_corpus()
    ref_fail = []
    sym_fail = []
    for p in pairs:
        osf = p["os_family"]
        for path in list(p["a"]) + list(p["b"]):
            if overlap.paths_overlap(path, path, os_family=osf) is not True:
                ref_fail.append({"id": p["id"], "path": path})
        ab = overlap.pathsets_overlap(p["a"], p["b"], os_family=osf)
        ba = overlap.pathsets_overlap(p["b"], p["a"], os_family=osf)
        if ab is not ba:
            sym_fail.append({"id": p["id"], "ab": ab, "ba": ba})

    original_ok = False
    mutant_red = False
    mutant_error = ""
    try:
        windows_case_must_overlap(overlap.paths_overlap)
        original_ok = True
    except AssertionError as exc:
        mutant_error = f"original:{exc}"
    try:
        windows_case_must_overlap(case_sensitive_mutant)
    except AssertionError as exc:
        mutant_red = True
        mutant_error = str(exc)

    nonempty_sets = overlap.pathsets_overlap(["src/a.py", "src/b.py"], ["src/b.py"]) is True
    disjoint_sets = overlap.pathsets_overlap(["src/a.py", "src/c.py"], ["src/b.py"]) is False
    empty_sets = overlap.pathsets_overlap([], ["src/a.py"]) is False

    payload = {
        "reflexive_failures": ref_fail,
        "symmetric_failures": sym_fail,
        "windows_case_original_green": original_ok,
        "case_sensitive_mutant_red": mutant_red,
        "mutant_error": mutant_error,
        "nonempty_set_overlap": nonempty_sets,
        "disjoint_set_no_overlap": disjoint_sets,
        "empty_set_no_overlap": empty_sets,
        "pairs_checked": len(pairs),
    }
    print(json.dumps(payload, indent=2))
    if ref_fail:
        print(f"FAILED:IMP-0411-probe2 reflexive {len(ref_fail)}")
        return 1
    if sym_fail:
        print(f"FAILED:IMP-0411-probe2 symmetric {len(sym_fail)}")
        return 1
    if not original_ok:
        print("FAILED:IMP-0411-probe2 windows case-only pair did not overlap")
        return 1
    if not mutant_red:
        print("FAILED:IMP-0411-probe2 case-sensitive mutant did not turn the test red")
        return 1
    if not (nonempty_sets and disjoint_sets and empty_sets):
        print("FAILED:IMP-0411-probe2 path-set membership")
        return 1
    print(
        "reflexive=ok symmetric=ok windows_case=green "
        "case_sensitive_mutant=red"
    )
    print("SUCCESS:IMP-0411-probe2 properties and case-sensitive mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
