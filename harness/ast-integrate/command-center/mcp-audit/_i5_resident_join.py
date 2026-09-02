#!/usr/bin/env python3
"""INTEGRATE: prove the round-4 measurement actually REACHES the deliverable.

WHAT WAS BROKEN.  Round 4 measured the RESIDENT cost of the 7 HTTP-transport rows the
stdio sweep cannot spawn -- 154 tools, 2,487 B -- and wrote it to
``unsampled-surface.json``.  Nothing joined it back into ``disposition.json``, so
``docs/mcp-audit/DISPOSITION-TABLE.md``, the only artifact a human reads, went on printing
``--`` in all seven ``tools`` cells, and the DoD ledger went on reporting
``cost-measured=16/23``.  Round 4 named the fix as its own first residual and did not run
it.  A measurement that reaches no consumer is indistinguishable from one never taken.

WHAT THIS FILE PROVES, by execution rather than by assurance:

  P1  The completeness invariant FIRES on the artifact as it shipped BEFORE the join, and
      is SILENT on the artifact as it ships after.  Without the first half, green here
      would be compatible with an invariant that cannot fail at all -- the shape this
      lane has caught in itself four times.  ``PRE`` is pinned to a real commit, so this
      is two committed blobs compared, not a mutation of one.

  P2  The JOIN-INTEGRITY limb is live, not merely the presence limb.  P1 alone would pass
      with a producer that invented the numbers, because invented numbers are still
      non-null.  So one joined value is perturbed by exactly 1 and the invariant must
      notice it disagrees with ``unsampled-surface.json``.

  P3  The EMPTY-JOIN limb is live.  It cannot be isolated in the real artifact -- with
      zero rows joined, the 7 HTTP rows have no resident cost and the presence limb fires
      first -- so it is exercised against a synthetic all-stdio row set where presence and
      integrity both pass and an inert join is the ONLY thing left to detect.  A guard
      that only ever fires alongside another guard has not been shown to work.

  P4  The rendered table actually CHANGED.  The invariant is about ``disposition.json``;
      the deliverable is a markdown file, and a reader is served by neither if the
      renderer drops the join on the floor.  So the two committed tables are compared
      directly: PRE must contain seven ``--`` cost cells, POST must contain none, and
      POST must carry the provenance mark.

Read-only.  Spawns only ``git show``.  Prints no credential value.

Terminal state per AGENTS.md 4: ``SUCCESS:i5-resident-join`` / ``FAILED:i5-resident-join``.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rank_disposition as rd  # noqa: E402
from render_table import CLIENT_MARK, INSTR_STDIO  # noqa: E402

# The last commit BEFORE the join.  Pinned deliberately: the point is to compare two real
# committed artifacts, so that "it used to be broken" is a blob anyone can fetch rather
# than a sentence in a report.
PRE = "f6a1f91b"
DISP = "command-center/mcp-audit/disposition.json"
TABLE = "docs/mcp-audit/DISPOSITION-TABLE.md"
REPO = HERE.parent.parent
# The exact phrase assert_resident_completeness emits for a missing resident cost.  Kept
# next to the pin so the two things this file matches on are visible together.
NO_RESIDENT = "mounted but no resident cost"


def blob(rev: str, path: str) -> bytes | None:
    """The STORED bytes at ``rev``.

    ``git show`` returns the blob unconverted; ``git archive`` would apply EOL conversion
    and hand back CRLF on Windows, which is why it is not used here.
    """
    out = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
    )
    return out.stdout if out.returncode == 0 else None


def rows_at(rev: str) -> list[dict[str, Any]] | None:
    raw = blob(rev, DISP)
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8"))["rows"]


def fires(
    rows: list[dict[str, Any]], unsampled: dict[str, dict[str, Any]]
) -> str | None:
    """The invariant's complaint, or None if it stayed silent."""
    try:
        rd.assert_resident_completeness(rows, unsampled)
    except SystemExit as exc:  # the invariant's own fail-closed path
        return str(exc)
    return None


def main() -> int:
    print("== i5: does the round-4 measurement reach the deliverable? ==")
    problems: list[str] = []
    unsampled = rd.load_unsampled(HERE)
    print(
        f"  source: unsampled-surface.json carries {len(unsampled)} client-listed rows"
    )

    pre = rows_at(PRE)
    post = json.loads((HERE / "disposition.json").read_text(encoding="utf-8"))["rows"]
    if pre is None:
        print(f"FAILED:i5-resident-join {DISP} is unreadable at {PRE} (fail closed)")
        return 1

    # ---- P1 both states, two committed blobs -------------------------------------
    pre_msg = fires(pre, unsampled)
    post_msg = fires(post, unsampled)
    if not pre_msg:
        problems.append(
            f"P1 the invariant is SILENT on the pre-join blob at {PRE} -- it cannot fail, "
            "so its silence on the current one measures nothing"
        )
    if post_msg:
        problems.append(f"P1 the invariant FIRES on the current artifact: {post_msg}")
    # Count the string the invariant ACTUALLY emits.  The first version of this line
    # counted "mounted with no RESIDENT cost" -- dod3's wording, not this invariant's --
    # and printed "fires (0 mounted rows)" beside a verdict that it fired.  A run that
    # reports two things which cannot both be true is a detector failure, not a finding,
    # so the mismatch is now itself a problem rather than a cosmetic zero.
    pre_n = _complaints(pre_msg)
    if pre_msg and not pre_n:
        problems.append(
            f"P1 the invariant fired on {PRE} but the complaint counter read 0 -- the "
            "counter is not parsing the message the invariant emits"
        )
    if pre_n > len(pre):
        problems.append(
            f"P1 counted {pre_n} complaints over {len(pre)} rows -- more complaints than "
            "rows means the parser is splitting something other than per-row lines"
        )
    print(
        f"  {'ok ' if pre_msg and pre_n and not post_msg else 'BAD'} P1 fires on {PRE} "
        f"({pre_n} mounted rows with no resident cost), silent now"
    )

    # ---- P2 join integrity, not merely presence ----------------------------------
    drifted = copy.deepcopy(post)
    target = next(
        (r for r in drifted if r.get("resident_instrument") == rd.INSTR_CLIENT), None
    )
    if target is None:
        problems.append(
            "P2 no client-listed row to perturb -- the join produced nothing"
        )
    else:
        target["resident_bytes"] = (target["resident_bytes"] or 0) + 1
        if not fires(drifted, unsampled):
            problems.append(
                "P2 a joined value 1 byte off its source did NOT fire -- the invariant "
                "checks presence only, so invented numbers would pass"
            )
        print(
            f"  {'ok ' if fires(drifted, unsampled) else 'BAD'} P2 a 1-byte drift from "
            f"unsampled-surface.json fires ({target['name']})"
        )

    # ---- P3 the empty-join limb, isolated ----------------------------------------
    only_stdio = [
        copy.deepcopy(r) for r in post if r.get("resident_instrument") == INSTR_STDIO
    ]
    if not only_stdio:
        problems.append("P3 no stdio rows to build the synthetic set from")
    else:
        msg = fires(only_stdio, unsampled)
        if not msg or "0 rows joined" not in msg:
            problems.append(
                f"P3 an all-stdio row set (presence ok, integrity ok) did not trip the "
                f"empty-join limb: {msg}"
            )
        print(
            f"  {'ok ' if msg and '0 rows joined' in msg else 'BAD'} P3 an inert join "
            f"fires on its own, with every other limb satisfied ({len(only_stdio)} rows)"
        )

    # ---- P4 the DELIVERABLE changed ----------------------------------------------
    pre_tbl = blob(PRE, TABLE)
    post_tbl = (REPO / TABLE).read_bytes()
    if pre_tbl is None:
        problems.append(f"P4 {TABLE} is unreadable at {PRE}")
    else:
        pre_dashes = _cost_dashes(pre_tbl.decode("utf-8"))
        post_dashes = _cost_dashes(post_tbl.decode("utf-8"))
        if pre_dashes == 0:
            problems.append(
                "P4 the pre-join table had NO unmeasured cost cells -- then this round "
                "closed nothing and the detector is reading the wrong column"
            )
        if post_dashes:
            problems.append(
                f"P4 {post_dashes} row(s) still print `--` for resident cost after the join"
            )
        marks = _marked_rows(post_tbl.decode("utf-8"))
        expected_marks = sum(
            1 for r in post if r.get("resident_instrument") == rd.INSTR_CLIENT
        )
        if not marks:
            problems.append(
                "P4 no row carries the provenance mark -- every joined number now reads "
                "as a stdio measurement"
            )
        elif marks != expected_marks:
            # The first version counted `"* |" in line`, which every row satisfies because
            # the disposition cell is bolded (`**KEEP**` ends in `* |`).  It reported 23
            # marks for 7 client-listed rows and read as a pass.  Count the FIELD.
            problems.append(
                f"P4 {marks} row(s) marked in the tools column but {expected_marks} are "
                "client-listed -- the mark and the data disagree"
            )
        print(
            f"  {'ok ' if pre_dashes and not post_dashes else 'BAD'} P4 table cost cells: "
            f"{pre_dashes} unmeasured at {PRE} -> {post_dashes} now, "
            f"{marks} row(s) marked `{CLIENT_MARK}`"
        )

    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        print(f"FAILED:i5-resident-join {len(problems)} problem(s)")
        return 1
    # Quote the TABLE's own counter here, not the invariant's.  The first version printed
    # `pre_n` -- a disposition.json row count -- in a sentence about the rendered table,
    # so the summary line disagreed with the P4 line directly above it.
    print(
        f"SUCCESS:i5-resident-join the join is reachable end to end: invariant both-states "
        f"on two committed blobs ({pre_n} rows short at {PRE}), integrity + empty-join "
        f"limbs fire in isolation, and the rendered table went {pre_dashes} rows "
        f"unmeasured -> {post_dashes}"
    )
    return 0


def _complaints(msg: str | None) -> int:
    """Per-row complaints in the invariant's message.

    Counts LINES, not one chosen phrase.  The first version matched only
    ``NO_RESIDENT``; on the pre-join blob the rows carry no ``resident_basis`` at all, so
    a DIFFERENT limb fires with different wording and the counter read 0 beside a verdict
    that it fired.  Which limb objected is not the question this probe asks -- how many
    rows the artifact was short is.
    """
    if not msg:
        return 0
    return sum(
        1
        for ln in msg.splitlines()
        if ln.strip() and not ln.startswith("FAILED:") and ":" in ln
    )


def _data_cols(ln: str) -> list[str] | None:
    """Columns of a data row, or None if this line is not one.

    Columns are 1-indexed past the leading pipe: 6 = S4, 7 = tools, 8 = name B,
    9 = schema B (schema is EXPECTED to stay `--` on the client-listed rows).
    """
    if not ln.startswith("| **"):  # data rows only; skips header, rule and prose
        return None
    return [c.strip() for c in ln.split("|")]


def _marked_rows(text: str) -> int:
    """Rows whose TOOLS cell carries the provenance mark.

    Reads the cell, not the line.  A substring test over the whole row matches the bolded
    disposition cell (`**KEEP**` ends in `* |`) and so reports every row as marked -- a
    detector that cannot tell a marked table from an unmarked one, which is exactly the
    use-vs-mention shape this repo keeps paying for.
    """
    n = 0
    for ln in text.splitlines():
        cols = _data_cols(ln)
        if cols and len(cols) > 7 and cols[7].endswith(CLIENT_MARK):
            n += 1
    return n


def _cost_dashes(text: str) -> int:
    """Rows whose RESIDENT cost cells (`tools`, `name B`) read `--`.

    Counts the FIELD, not the document: `--` appears in the header rule and in the S4
    column too, so a naive substring count over the whole table would report a number
    that has nothing to do with cost.  Columns are 1-indexed past the leading pipe:
    6 = S4, 7 = tools, 8 = name B, 9 = schema B (schema is EXPECTED to stay `--`).
    """
    n = 0
    for ln in text.splitlines():
        cols = _data_cols(ln)
        if cols and len(cols) > 8 and (cols[7] == "--" or cols[8] == "--"):
            n += 1
    return n


if __name__ == "__main__":
    raise SystemExit(main())
