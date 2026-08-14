#!/usr/bin/env python3
"""RED-PROOF for the per-backend signal: every new guard, observed going RED.

WHY THIS FILE.  The build lane added a fourth-signal axis (per BACKEND, not just per
server) and three new fail-closed guards behind it.  A guard never seen red is
indistinguishable from ``return`` -- this program has measured that eight-plus times -- so
each one is run here against a KNOWN-BROKEN input and required to FIRE, and against the
good input and required to stay SILENT.

PART A  ``assert_backend_consistency`` -- 6 mutations.
        The headline is A1: a row that carries a dead backend and does NOT disclose it.
        That is the round-1 defect (a legend and a field drifting apart) reappearing one
        level down, and prose cannot prevent it -- only a machine check can.

PART B  ``backend_view``'s two internal guards, which are NOT reachable through Part A
        because they abort before a row is ever built:
          B1  an unclassified tail must fail closed, not silently under-report the
              backend that owns those tools.
          B2  the C3 double-sum must fire when its two routes disagree.  Mutating
              ``classify`` alone cannot prove this -- BOTH sums would use the mutant and
              agree -- so the mutation drives ``bucket`` and ``classify`` APART, which is
              the real defect shape the double-sum exists to catch.

        B2 is the control that would have caught the inert-control failure this repo
        measured on ``manifest["events"][ev]``: four probes agreeing with each other and
        all four wrong, because they shared one broken route.

Read-only, pure, committed inputs only.  Spawns nothing.
"""

from __future__ import annotations

import copy
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backend_map  # noqa: E402
import rank_disposition as rd  # noqa: E402
import s4_evidence  # noqa: E402


def _row(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "cloud-hub",
        "tool_count": 424,
        "evidence": f"real handshake -- SCOPE: {rd.DEAD_BACKEND_MARK}: rclone",
        "backend_liveness": {
            "legend": rd.BACKEND_LEGEND,
            "attribution": "backend_map over the committed surface",
            "probed": [{"backend": "rclone", "verdict": "dead"}],
            "dead_backends": ["rclone"],
            "unprobed": ["aws"],
            "tools_over_dead_backend": 40,
            "dead_surface_pct": 9.4,
        },
    }
    base.update(over)
    return base


def _bl(row: dict[str, Any], **over: Any) -> dict[str, Any]:
    row = copy.deepcopy(row)
    row["backend_liveness"].update(over)
    return row


GOOD = [
    _row(),
    # a row with no backend records at all -- null must be representable and silent
    _row(name="angr", tool_count=14, evidence="real handshake", backend_liveness=None),
]

MUTATIONS: dict[str, list[dict[str, Any]]] = {
    # A1 -- THE HEADLINE.  Dead backend, undisclosed: reads as a working server.
    "dead backend not disclosed in evidence": [
        _row(evidence="real initialize+tools/list returned 424 tools in 230ms")
    ],
    "empty probed[] (a null in disguise)": [_bl(_row(), probed=[])],
    "dead-surface exceeds the advertised surface": [
        _bl(_row(), tools_over_dead_backend=999)
    ],
    "count without a percentage": [_bl(_row(), dead_surface_pct=None)],
    "percentage without a count": [_bl(_row(), tools_over_dead_backend=None)],
    "dead tools attributed to no dead backend": [_bl(_row(), dead_backends=[])],
}


def part_a(ev: s4_evidence.Evidence) -> list[str]:
    print("== PART A: assert_backend_consistency ==")
    survivors: list[str] = []
    try:
        rd.assert_backend_consistency(copy.deepcopy(GOOD), ev)
        print("  baseline (shipped semantics) -> silent  OK")
    except SystemExit as exc:
        print(f"  FAILED baseline is already red: {exc}")
        return ["baseline"]

    for label, rows in MUTATIONS.items():
        try:
            rd.assert_backend_consistency(copy.deepcopy(rows), ev)
        except SystemExit:
            print(f"  mutation {label:44} -> invariant fired  OK")
            continue
        print(f"  mutation {label:44} -> SURVIVED")
        survivors.append(label)

    # The null-means-nothing-probed reading, checked in the direction that matters: a row
    # that DOES have backend records but ships a null block must not pass as "fine".
    try:
        rd.assert_backend_consistency(
            [_row(name="cloud-hub", backend_liveness=None)], ev
        )
        print("  mutation null block hiding real backend records   -> SURVIVED")
        survivors.append("null block hiding real records")
    except SystemExit:
        print(
            f"  mutation {'null block hiding real backend records':44} -> invariant fired  OK"
        )
    return survivors


def part_b(ev: s4_evidence.Evidence) -> list[str]:
    print("\n== PART B: backend_view internal guards (unreachable from Part A) ==")
    survivors: list[str] = []
    names = backend_map.proxy_tool_names()
    cap = {"tool_names": names, "tool_count": len(names)}

    try:
        view = rd.backend_view("cloud-hub", cap, len(names), ev)
        print(
            f"  baseline -> silent, {view['tools_over_dead_backend']}/{len(names)} "
            f"({view['dead_surface_pct']}%) over {len(view['dead_backends'])} dead backends  OK"
        )
    except SystemExit as exc:
        print(f"  FAILED baseline is already red: {exc}")
        return ["baseline"]

    real_classify, real_bucket = backend_map.classify, backend_map.bucket

    # The mutants must mirror the REAL signatures, including the optional ``table`` seam
    # backend_map grew for its C4 control.  ``bucket`` resolves ``classify`` through the
    # module namespace, so a patched 1-arg lambda is called with 2 args from inside the
    # real ``bucket`` and dies with a TypeError -- which the gate reported as this
    # red-proof failing rather than as the mutation being caught.  Accepting and ignoring
    # ``table`` keeps each mutation semantically identical to what it was before.

    # ---- B1: an unclassified tail must abort, never under-report.
    try:
        backend_map.classify = (
            lambda t, table=None: None if t == names[0] else real_classify(t, table)
        )
        backend_map.bucket = lambda ts, table=None: (
            real_bucket([t for t in ts if t != names[0]], table)[0],
            [names[0]],
        )
        rd.backend_view("cloud-hub", cap, len(names), ev)
        print("  B1 unclassified tail                          -> SURVIVED")
        survivors.append("B1 unclassified tail")
    except SystemExit:
        print(f"  B1 {'unclassified tail':44} -> guard fired  OK")
    finally:
        backend_map.classify, backend_map.bucket = real_classify, real_bucket

    # ---- B2: drive the two sums APART.  bucket() drops a dead-backend tool while
    # classify() still claims it, so the routes disagree exactly as they would under a
    # real bug in one of them.  Mutating classify alone would leave both sums agreeing --
    # which is what an inert control looks like.
    dead_tool = next((t for t in names if real_classify(t) == "rclone"), None)
    if dead_tool is None:
        survivors.append("B2 could not find a dead-backend tool to drop")
    else:
        try:
            backend_map.bucket = lambda ts, table=None: real_bucket(
                [t for t in ts if t != dead_tool], table
            )
            rd.backend_view("cloud-hub", cap, len(names), ev)
            print("  B2 double-sum disagreement                    -> SURVIVED")
            survivors.append("B2 double-sum disagreement")
        except SystemExit as exc:
            ok = "disagreement" in str(exc)
            print(
                f"  B2 {'double-sum disagreement':44} -> "
                f"{'guard fired' if ok else 'fired, WRONG guard'}  {'OK' if ok else 'BAD'}"
            )
            if not ok:
                survivors.append("B2 fired the wrong guard")
        finally:
            backend_map.bucket = real_bucket

    # The mutations must not leave the module broken for anything downstream.
    if (
        backend_map.classify is not real_classify
        or backend_map.bucket is not real_bucket
    ):
        survivors.append("monkeypatch not restored")
    return survivors


def main() -> int:
    ev = s4_evidence.load()
    survivors = part_a(ev) + part_b(ev)
    if survivors:
        print(f"FAILED:b1-redproof surviving mutation(s): {survivors}")
        return 1
    print(
        f"SUCCESS:b1-redproof A {len(MUTATIONS) + 1}/{len(MUTATIONS) + 1} mutations caught, "
        "B both backend_view guards fired on a routes-disagree mutation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
