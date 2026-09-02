#!/usr/bin/env python3
"""Probe 2: independent long-path matrix + leak-table vs measured cells.

Catalog evidence (b) and reviewer_requirement: re-run visibility on a second
view (Git Bash/MSYS codec and pwsh7/CPython) and report divergence. This probe
does not trust probe 1's printed numbers; it re-runs run_experiment().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    LONG_MIN,
    NOT_DELIVERING,
    OPERATIONS,
    OUT_REL,
    SENTINEL,
    SHELLS,
    UNIT,
)
from matrix import DOCUMENTED_LEAKS, compact_grid, run_experiment  # noqa: E402
from schema_local import payload  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    exp = run_experiment()
    long = exp["long_path"]
    planted = exp["planted_leaks"]
    det = planted["detector_control"]
    print(
        json.dumps(
            {
                "long_nchars": long["path_nchars"],
                "long_all_three_visible": long["all_three_visible"],
                "long_grid": compact_grid(exp["matrix"]["long"]),
                "leak_table_matches_matrix": exp["leak_table_matches_matrix"],
                "detector_control": det,
                "matched_leaks": [
                    r["id"] for r in exp["leak_table"] if r.get("matches_matrix")
                ],
            },
            sort_keys=True,
        )
    )
    if long["path_nchars"] < LONG_MIN:
        return fail(f"long path {long['path_nchars']} < {LONG_MIN}")
    if not long.get("exceeds_win32_max_path"):
        return fail("long path does not exceed Win32 MAX_PATH")
    if not long["all_three_visible"]:
        return fail(f"long POSIX path not visible from all three: {long['visible']}")
    if not long.get("all_ops_ok"):
        return fail("long-path 3x5 matrix has a failing cell")
    for shell in SHELLS:
        for op in OPERATIONS:
            hit = [
                r
                for r in exp["matrix"]["long"]
                if r["shell"] == shell and r["op"] == op
            ]
            if len(hit) != 1 or hit[0]["ok"] is not True:
                return fail(f"long cell {shell}.{op} missing or not ok")

    if not det.get("discriminates"):
        return fail(f"detector_control did not discriminate: {det}")
    if not det.get("posix_long_visible_from_git_bash"):
        return fail("Git Bash view failed the POSIX long-path control")
    if not det.get("extended_fails"):
        return fail("\\\\?\\ extended prefix did not fail in Git Bash view")
    if not det.get("unprefixed_over_max_fails"):
        return fail("unprefixed MAX_PATH path did not fail in Git Bash view")
    if "git-bash-msys-extended-prefix" not in det.get("extended_leak_ids", []):
        return fail(f"extended leak id missing: {det}")
    if "git-bash-max-path-unprefixed" not in det.get("unprefixed_leak_ids", []):
        return fail(f"unprefixed leak id missing: {det}")
    if not exp["leak_table_matches_matrix"]:
        return fail(f"leak table mismatch {exp['leak_mismatches']}")
    want_ids = {row["id"] for row in DOCUMENTED_LEAKS}
    got_ids = {row["id"] for row in exp["leak_table"] if row.get("matches_matrix")}
    if want_ids != got_ids:
        return fail(f"leak ids {got_ids} want={want_ids}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    body = payload(doc)
    if body.get("leak_table_matches_matrix") is not True:
        return fail("artifact leak_table_matches_matrix is not true")
    if body.get("parity_on_posix") is not True:
        return fail("artifact parity_on_posix is not true")
    art_long = body.get("long_path") or {}
    if int(art_long.get("path_nchars") or 0) < LONG_MIN:
        return fail("artifact long path too short")
    art_leaks = {row.get("id") for row in (body.get("leak_table") or [])}
    if not want_ids.issubset(art_leaks):
        return fail(f"artifact leak_table missing ids {want_ids - art_leaks}")
    # Independent reviewer: Git Bash and pwsh7 cells exist in the artifact matrix.
    art_shells = {r.get("shell") for r in (body.get("matrix") or {}).get("long") or []}
    if art_shells != set(SHELLS):
        return fail(f"artifact long matrix shells={art_shells}")

    print(
        f"long_nchars={long['path_nchars']} posix_parity=True "
        f"leaks_matched={sorted(got_ids)} detector_discriminates=True"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 long-path 3x5 visible; leak table matches "
        "planted Git Bash MSYS failures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
