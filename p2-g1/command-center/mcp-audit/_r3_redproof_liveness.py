#!/usr/bin/env python3
"""Round-3 both-states proof for the liveness fixes.

Three parts, each of which must show the defect in the KNOWN-BROKEN state before its
absence in the current state is allowed to mean anything.

  A  the literal round-2 committed rows (pinned SHA, not HEAD) must trip
     ``assert_liveness_consistency`` -- and the current rows must not.
  B  four synthetic mutations, one per clause of the invariant, must each fire.
  C  the round-2 ``dod3`` predicate is re-implemented verbatim and run against the
     round-2 rows: it returns PASS while seven rows carry no cost at all.  The round-3
     predicate on the SAME rows must go red.  That is the discriminating comparison --
     "the new check passes now" says nothing on its own.

Every part fails CLOSED: if a BEFORE state stops exhibiting its defect, the detector is
broken and the run goes red rather than printing a reassuring SUCCESS.

Run::  python _r3_redproof_liveness.py   ->  exit 0 only if every part behaves.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import rank_disposition as rd  # noqa: E402
from _r2_dod_check import dod3 as dod3_round3  # noqa: E402

# The round-2 commit, pinned.  Reading HEAD would erase the defect the moment the round-3
# fix lands -- the exact self-defeating shape `_r2_reproduce.py` v1 shipped.
ROUND2_REV = "630bb8af"
DISP = "command-center/mcp-audit/disposition.json"
COST_FIELDS = ("tool_count", "name_bytes", "schema_bytes", "rss_bytes")


def blob_rows(rev: str) -> list[dict[str, Any]]:
    out = subprocess.run(
        ["git", "show", f"{rev}:{DISP}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)["rows"]


def worktree_rows() -> list[dict[str, Any]]:
    return json.loads((REPO / DISP).read_text(encoding="utf-8"))["rows"]


def fires(rows: list[dict[str, Any]]) -> str | None:
    try:
        rd.assert_liveness_consistency(copy.deepcopy(rows))
    except SystemExit as exc:
        return str(exc)
    return None


def dod3_round2(rows: list[dict[str, Any]]) -> list[str]:
    """The round-2 predicate, verbatim, kept so the comparison is real and not recalled."""
    bad = []
    for r in rows:
        if not r.get("handshake_verified"):
            continue
        for field in COST_FIELDS:
            if r.get(field) is None:
                bad.append(f"{r['name']}: {field} unmeasured")
    return bad


def part_a() -> list[str]:
    print(f"== PART A: assert_liveness_consistency, BEFORE = {ROUND2_REV} ==")
    fail: list[str] = []
    before = blob_rows(ROUND2_REV)
    contradictory = [
        r["name"] for r in before if r.get("last_error") and r.get("call_verified")
    ]
    basisless = [r["name"] for r in before if not r.get("liveness_basis")]
    print(f"  BEFORE verified-and-errored rows ({len(contradictory)}): {contradictory}")
    print(f"  BEFORE rows with no liveness_basis: {len(basisless)}/{len(before)}")
    if not contradictory or not basisless:
        print("  FAILED the BEFORE state no longer shows the defect -- detector broken")
        fail.append("before-clean")
    msg = fires(before)
    print(f"  BEFORE invariant fires: {msg is not None}")
    if msg is None:
        fail.append("before-not-caught")

    after = worktree_rows()
    after_contradictory = [
        r["name"] for r in after if r.get("last_error") and r.get("call_verified")
    ]
    msg2 = fires(after)
    print(f"  AFTER  verified-and-errored rows: {len(after_contradictory)}")
    print(f"  AFTER  invariant silent: {msg2 is None}")
    if msg2 is not None:
        print(f"  FAILED current rows trip the invariant: {msg2[:200]}")
        fail.append("after-red")
    return fail


def _row(**kw: Any) -> dict[str, Any]:
    base = {
        "name": "probe",
        "call_verified": True,
        "last_error": None,
        "pid": 111,
        "rss_bytes": 222,
        "tool_count": 3,
        "liveness_basis": rd.MEASURED_BASIS,
    }
    base.update(kw)
    return base


MUTATIONS: dict[str, list[dict[str, Any]]] = {
    # 1. the literal round-2 shape: proved working, and carrying an error.
    "verified-and-errored": [_row(last_error="transport='http': no stdio command")],
    # 2. a null with no stated reason at all.
    "no-liveness-basis": [
        _row(pid=None, rss_bytes=None, tool_count=None, liveness_basis="")
    ],
    # 3. a basis that claims a measurement the row does not have.
    "claims-measured-but-null": [_row(rss_bytes=None)],
    # 4. not-measured with no reason -- the disclosure equivalent of silence.
    "reasonless-not-measured": [
        _row(pid=None, rss_bytes=None, tool_count=None, liveness_basis="not-measured:")
    ],
    # 5. the inverse: a full snapshot mislabelled as unmeasured.  Without this the
    #    invariant would accept "not-measured:" as a free pass on any row.
    "measured-but-labelled-not": [
        _row(liveness_basis="not-measured: claims there is nothing to sample")
    ],
}


def part_b() -> list[str]:
    print("\n== PART B: one mutation per clause ==")
    survivors: list[str] = []
    if fires([_row()]) is not None:
        print("  FAILED baseline is already red")
        return ["baseline"]
    print("  baseline (a well-formed measured row) -> silent  OK")
    for label, rows in MUTATIONS.items():
        if fires(rows) is None:
            print(f"  mutation {label:26} -> SURVIVED")
            survivors.append(label)
        else:
            print(f"  mutation {label:26} -> invariant fired  OK")
    return survivors


def part_c() -> list[str]:
    print("\n== PART C: does the widened DoD3 see what the round-2 DoD3 could not? ==")
    fail: list[str] = []
    before = blob_rows(ROUND2_REV)
    nulls = [r["name"] for r in before if any(r.get(f) is None for f in COST_FIELDS)]
    old = dod3_round2(before)
    new = dod3_round3(before)
    print(
        f"  round-2 rows with a null cost field: {len(nulls)}/{len(before)} {nulls[:3]}..."
    )
    print(f"  round-2 predicate on those rows -> {len(old)} problems (PASS = blind)")
    print(f"  round-3 predicate on those rows -> {len(new)} problems")
    if not nulls:
        fail.append("no-nulls-to-find")
    if old:
        print("  FAILED the round-2 predicate was not blind here -- comparison invalid")
        fail.append("old-not-blind")
    if not new:
        print("  FAILED the round-3 predicate is blind too")
        fail.append("new-blind")
    current = dod3_round3(worktree_rows())
    print(f"  round-3 predicate on the CURRENT rows -> {len(current)} problems")
    if current:
        print(f"  FAILED current rows still hide a cost gap: {current[:3]}")
        fail.append("current-red")
    return fail


def main() -> int:
    fail = part_a() + part_b() + part_c()
    if fail:
        print(f"\nFAILED:r3-redproof {fail}")
        return 1
    print(
        f"\nSUCCESS:r3-redproof A ok, B {len(MUTATIONS)}/{len(MUTATIONS)} mutations "
        "caught, C the widened predicate sees the gap the old one skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
