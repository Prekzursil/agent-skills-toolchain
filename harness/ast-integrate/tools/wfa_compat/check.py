#!/usr/bin/env python3
"""CI invariant: every compat declaration must be reciprocal (WFA-0004).

Library API: ``run_invariant`` (ok iff zero one-sided declarations and zero
dangling refs) and ``drop_one_reciprocal`` (the both-states mutation).
CLI: ``check.py --library lib.json [--expect-red]`` — exit 0 when the
invariant verdict matches the expectation, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from wfa_compat.counts import count_graph  # noqa: E402
from wfa_compat.library import adj_from_library  # noqa: E402
from wfa_compat.transpose import matrix_equals_transpose  # noqa: E402


def run_invariant(adj: dict[str, set[str]]) -> dict[str, Any]:
    counts = count_graph(adj)
    transpose = matrix_equals_transpose(adj)
    ok = counts["asymmetric"] == 0 and counts["dangling"] == 0 and transpose["M_equals_MT"]
    return {
        "ok": bool(ok),
        "onesided": counts["asymmetric"],
        "dangling": counts["dangling"],
        "counts": counts,
        "transpose": transpose,
    }


def drop_one_reciprocal(adj: dict[str, set[str]]) -> dict[str, set[str]]:
    """Remove ONE direction of the first reciprocal pair (deterministic)."""
    out = {k: set(v) for k, v in adj.items()}
    for src in sorted(out):
        for dst in sorted(out[src]):
            if src < dst and src in out.get(dst, set()):
                out[dst].discard(src)
                return out
    raise ValueError("library has no reciprocal pair to drop")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True)
    parser.add_argument("--expect-red", action="store_true")
    args = parser.parse_args()
    doc = json.loads(Path(args.library).read_text(encoding="utf-8"))
    verdict = run_invariant(adj_from_library(doc))
    print(
        json.dumps(
            {
                "library": args.library,
                "ok": verdict["ok"],
                "onesided": verdict["onesided"],
                "dangling": verdict["dangling"],
                "expect_red": bool(args.expect_red),
            },
            sort_keys=True,
        )
    )
    if args.expect_red:
        if verdict["ok"]:
            print("FAILED:wfa-compat-invariant expected red but library is green")
            return 1
        print("OK:wfa-compat-invariant red as expected (one-sided declarations present)")
        return 0
    if not verdict["ok"]:
        print(f"FAILED:wfa-compat-invariant onesided={verdict['onesided']}")
        return 1
    print("OK:wfa-compat-invariant green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
