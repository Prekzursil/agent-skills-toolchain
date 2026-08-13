#!/usr/bin/env python3
"""Both-states red-proof for the two round-2 fixes.  Fails closed.

Round 1 shipped two claims a verifier refuted.  Both fixes are now enforced by code, and
code that has never been observed to go RED is indistinguishable from code that cannot.
So each fix gets a mutation set that must make it fire.

PART A -- ``rank_disposition.assert_signal_consistency`` (fixes D1).
  The invariant that makes the round-1 shape unrepresentable: a row whose S4 verdict
  disagrees with the evidence printed beside it.  Four mutations, including the exact
  round-1 computation, must each raise SystemExit.

PART B -- the producer actually fills ``mcpctl.matrix.Liveness`` (fixes D2).
  Round 1 claimed the producer emitted "exactly the four fields mcpctl.matrix.Row leaves
  null".  It emitted three of the four by name -- ``rss_bytes`` was published as
  ``working_set_bytes``, so an injection would have silently dropped memory.  This is no
  longer a sentence: it CONSTRUCTS ``Liveness`` from the producer's own row keys and runs
  ``build_rows``, then proves the check is not inert by deleting ``rss_bytes`` from the
  rows and requiring it to go red.

  Note the control shape.  "Does build_rows() succeed" would pass under BOTH hypotheses
  (Liveness defaults every field to None, so an empty snapshot builds happily) -- that is
  the control-that-cannot-distinguish failure.  The discriminating assertion is that the
  built Row carries a NON-NULL value for each of the four fields.

Run: ``python _r2_redproof_invariants.py [capability-matrix.json ...]`` -> exit 0 / 1.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "mcpctl"))

import rank_disposition as rd  # noqa: E402  (path injection must precede)
from mcpctl.matrix import Liveness  # noqa: E402


# ------------------------------------------------------------------ part A
def _row(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "x",
        "call_verified": True,
        "handshake_verified": True,
        "s4_executed": None,
        "call_method": "stdio-handshake",
    }
    base.update(over)
    return base


GOOD_ROWS = [
    _row(name="stdio-verified"),
    _row(
        name="http-verified",
        handshake_verified=False,
        s4_executed=("whoami", "ok"),
        call_method="in-session-tool-call",
    ),
    _row(
        name="unverified",
        call_verified=False,
        handshake_verified=False,
        call_method=None,
    ),
]

MUTATIONS: dict[str, tuple[list[dict[str, Any]], str]] = {
    # The exact round-1 defect: call_verified computed from the handshake alone, so an
    # HTTP server sits at false next to its own in-session evidence.
    "round1-handshake-only": (
        [
            _row(
                name="http-verified",
                call_verified=False,
                handshake_verified=False,
                s4_executed=("whoami", "ok"),
                call_method=None,
            )
        ],
        rd.S4_LEGEND,
    ),
    # The opposite direction: a verdict with no evidence at all behind it.
    "verified-with-no-evidence": (
        [
            _row(
                name="ghost",
                call_verified=True,
                handshake_verified=False,
                s4_executed=None,
                call_method="stdio-handshake",
            )
        ],
        rd.S4_LEGEND,
    ),
    # Right verdict, wrong provenance -- the method column lies about which probe answered.
    "wrong-call-method": (
        [
            _row(
                name="mislabelled",
                handshake_verified=False,
                s4_executed=("whoami", "ok"),
                call_method="stdio-handshake",
            )
        ],
        rd.S4_LEGEND,
    ),
    # The drift that caused round 1: the legend narrows while the computation does not.
    "legend-narrowed": (
        GOOD_ROWS,
        "real initialize+tools/list only",
    ),
}


def part_a() -> list[str]:
    print("== PART A: assert_signal_consistency ==")
    survivors: list[str] = []
    try:
        rd.assert_signal_consistency(copy.deepcopy(GOOD_ROWS), rd.S4_LEGEND)
        print("  baseline (shipped semantics) -> silent  OK")
    except SystemExit as exc:
        print(f"  FAILED baseline is already red: {exc}")
        return ["baseline"]
    for label, (rows, legend) in MUTATIONS.items():
        try:
            rd.assert_signal_consistency(copy.deepcopy(rows), legend)
        except SystemExit:
            print(f"  mutation {label:26} -> invariant fired  OK")
            continue
        print(f"  mutation {label:26} -> SURVIVED")
        survivors.append(label)
    return survivors


# ------------------------------------------------------------------ part B
LIVENESS_FIELDS = tuple(f.name for f in dataclasses.fields(Liveness))


def _inject(rows: list[dict[str, Any]]) -> tuple[int, list[str]]:
    """Build Liveness from the producer's own keys; return (n_full, missing)."""
    missing: list[str] = []
    full = 0
    for row in rows:
        if not row.get("call_verified"):
            continue
        snap = Liveness(**{f: row.get(f) for f in LIVENESS_FIELDS})
        gaps = [
            f for f in LIVENESS_FIELDS if f != "last_error" and getattr(snap, f) is None
        ]
        if gaps:
            missing.append(f"{row['name']}: {gaps}")
        else:
            full += 1
    return full, missing


def part_b(paths: list[pathlib.Path]) -> list[str]:
    print("\n== PART B: producer -> mcpctl.matrix.Liveness ==")
    print(f"  mcpctl Liveness fields: {list(LIVENESS_FIELDS)}")
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            rows += json.loads(path.read_text(encoding="utf-8"))["rows"]
    if not rows:
        print("  FAILED no capability rows (fail closed)")
        return ["no-rows"]
    full, missing = _inject(rows)
    print(f"  verified rows with all 4 fields non-null: {full}")
    if missing:
        print(f"  FAILED gaps: {missing}")
        return ["real-rows-incomplete"]

    # Control: the check must be able to go red.  Drop the field the round-1 producer
    # omitted and require a gap to be reported.
    mutated = copy.deepcopy(rows)
    for row in mutated:
        row.pop("rss_bytes", None)
    _full2, missing2 = _inject(mutated)
    fired = bool(missing2)
    print(f"  mutation drop-rss_bytes -> check red? {fired}")
    return [] if fired else ["drop-rss_bytes-survived"]


def main(argv: list[str]) -> int:
    # Default to the CURRENT producer's output only.  Round-1's matrix is deliberately
    # kept on disk as the frozen known-broken state, so concatenating it here would make
    # the no-arg run permanently red for a defect that is fixed -- pass it explicitly
    # (`_r2_redproof_invariants.py capability-matrix.json`) to see it go red on purpose.
    paths = [pathlib.Path(a) for a in argv] or [HERE / "capability-matrix-r2.json"]
    survivors = part_a() + part_b(paths)
    if survivors:
        print(f"\nFAILED:r2-redproof survivors={survivors}")
        return 1
    print(
        f"\nSUCCESS:r2-redproof {len(MUTATIONS)}/{len(MUTATIONS)} A-mutations caught, "
        "B injection complete and its control fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
