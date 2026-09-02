#!/usr/bin/env python3
"""IMP-0085 resolver tests. Exit 0 when the matrix is deterministic and unknown packages stay out."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import compat as C  # noqa: E402


def main() -> int:
    pkgs = C.load_candidates()
    first = C.resolution_matrix(pkgs, client_name="claude")
    second = C.resolution_matrix(pkgs, client_name="claude")
    if first != second:
        print("FAILED:test_compat_resolution matrix nondeterministic")
        return 1
    unknown = {"demo.unknown-compat@9.9.9", "demo.empty-compat-object@0.0.1"}
    for accepted in first.values():
        if unknown.intersection(accepted):
            print("FAILED:test_compat_resolution unknown leaked")
            return 1
    empty = C.filter_candidates(
        pkgs, platform="linux", client_version="0.9.0", client_name="claude"
    )
    if empty.accepted != ():
        print("FAILED:test_compat_resolution expected empty", empty.accepted)
        return 1
    if empty.unmet_requirement != "requires client >= 1.0.0, you have 0.9.0":
        print("FAILED:test_compat_resolution unmet", empty.unmet_requirement)
        return 1
    print("SUCCESS:test_compat_resolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
