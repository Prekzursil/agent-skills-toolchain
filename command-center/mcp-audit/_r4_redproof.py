#!/usr/bin/env python3
"""Round-4 red-proof: each fix must be silent now and LOUD on the shipped-broken state.

PART A  the false CRLF sentences.  A doc fix is only real if a checker can tell the
        difference between ASSERTING a thing and QUOTING it as refuted -- otherwise the
        blockquote that preserves the refuted wording (which this program requires) would
        itself keep the check red forever, and the tempting "fix" is to delete the
        evidence.  So the predicate counts the FIELD, not the document: an assertion is a
        match on a line that is NOT a blockquote.  Two clauses, opposite directions:
          A1 no unquoted assertion survives   (the defect is gone)
          A2 the refuted wording is still there, quoted  (it was not silently deleted)

PART B  the DoD1 set-membership gap.  The round-3 gate is not recalled, it is EXTRACTED
        from its own commit and executed, so "the old predicate was blind" is a
        measurement.

Run::  python _r4_redproof.py   ->  exit 0 only if every mutation fires and both states
behave.  Fails closed if a BEFORE state stops exhibiting its defect, because a detector
that has quietly stopped detecting must not print SUCCESS.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
GATE = "command-center/mcp-audit/_r2_dod_check.py"
DISP = "command-center/mcp-audit/disposition.json"

# The two shapes the shipped docs used to assert CRLF as fact.
ASSERT_PATTERNS = [
    re.compile(r"(?i)\b(?:carry|carries|store|stores)\s+CRLF\b"),
    re.compile(r"(?i)^\|\s*blob\s*\|\s*CRLF lines\s*\|"),
]
# The revision that SHIPPED each false sentence.  My first attempt pinned the round-3 doc
# at 0d3c9e93 -- the rev the verifier used for its LINE-count measurement -- and the
# detector reported asserted=0, i.e. silent on a state where the defect provably exists.
# Measured, not guessed: `grep -c "blobs carry CRLF"` over the three round-3 commits gives
# bfec0543=0, 0d3c9e93=0, 673cd180=1.  A BEFORE state that does not exhibit the defect
# would have made this whole red-proof meaningless, which is why main() fails closed on it.
DOCS_BEFORE = [
    ("673cd180", "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md"),
    ("2caafe53", "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md"),
]


def text(rev: str, path: str) -> str:
    if rev == "WORKTREE":
        return (REPO / path).read_text(encoding="utf-8")
    return subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def scan(body: str) -> tuple[list[str], list[str]]:
    """(assertions made in the document's own voice, occurrences inside blockquotes)."""
    asserted, quoted = [], []
    for line in body.splitlines():
        if not any(p.search(line) for p in ASSERT_PATTERNS):
            continue
        (quoted if line.lstrip().startswith(">") else asserted).append(line.strip())
    return asserted, quoted


def part_a() -> bool:
    print("== PART A: the false CRLF sentences, before and after ==")
    ok = True
    for rev, path in DOCS_BEFORE:
        a, q = scan(text(rev, path))
        fired = len(a) > 0
        print(
            f"  BEFORE {rev} {pathlib.PurePosixPath(path).name:32} "
            f"asserted={len(a)} quoted={len(q)} detector fires: {fired}"
        )
        if a:
            print(f"         e.g. {a[0][:88]}")
        ok = ok and fired
    if not ok:
        print("  !! a BEFORE state no longer exhibits the defect -- detector suspect")

    for path in (p for _, p in DOCS_BEFORE):
        a, q = scan(text("WORKTREE", path))
        a1, a2 = len(a) == 0, len(q) > 0
        print(
            f"  AFTER          {pathlib.PurePosixPath(path).name:32} "
            f"asserted={len(a)} (want 0, ok={a1})  quoted={len(q)} (want >0, ok={a2})"
        )
        if a:
            print(f"         still asserted: {a[0][:88]}")
        ok = ok and a1 and a2

    # Mutations, so the AFTER silence is not just an inert predicate.
    body = text("WORKTREE", DOCS_BEFORE[0][1])
    lines = body.splitlines()
    idx = next(
        i
        for i, ln in enumerate(lines)
        if ln.lstrip().startswith(">") and any(p.search(ln) for p in ASSERT_PATTERNS)
    )
    m1 = lines[:idx] + [lines[idx].lstrip("> ")] + lines[idx + 1 :]
    m2 = lines[:idx] + lines[idx + 1 :]
    f1 = len(scan("\n".join(m1))[0]) > 0
    f2 = len(scan("\n".join(m2))[1]) == 0
    print(f"  mutation unquote-the-refuted-line -> A1 fires: {f1}")
    print(f"  mutation delete-the-refuted-line  -> A2 fires: {f2}")
    return ok and f1 and f2


def load_gate(rev: str) -> dict:
    # __file__ must be present: the gate derives REPO from it, and without it the exec
    # dies with a bare NameError that looks like a missing blob.
    ns: dict = {
        "__name__": "_gate_" + rev,
        "__file__": str(REPO / GATE),
    }
    exec(compile(text(rev, GATE), f"{rev}:{GATE}", "exec"), ns)
    return ns


def part_b() -> bool:
    print("\n== PART B: can the OLD DoD1 see a server disappear? ==")
    rows = json.loads(text("WORKTREE", DISP))["rows"]
    old = load_gate("673cd180")
    new = load_gate("WORKTREE")

    dropped = copy.deepcopy(rows)
    victim = dropped.pop(3)["name"]
    print(
        f"  mutation: drop the row for {victim!r} ({len(rows)} -> {len(dropped)} rows)"
    )
    old_sees = bool(old["dod1"](dropped))
    new_sees = bool(new["dod1"](dropped))
    print(
        f"  round-3 dod1 on the shrunken table -> {len(old['dod1'](dropped))} problems "
        f"(PASS = blind: {not old_sees})"
    )
    print(
        f"  round-4 dod1 on the shrunken table -> {len(new['dod1'](dropped))} problems "
        f"(fires: {new_sees})"
    )
    clean = not new["dod1"](rows)
    print(f"  round-4 dod1 on the CURRENT table  -> silent: {clean}")

    # The old gate's numeric floor: 20, so three rows could vanish under it.
    old_floor_blind = len(rows) - 3 >= 20
    print(
        f"  round-3 main() floor was 20 of {len(rows)} rows -> up to 3 could vanish "
        f"silently: {old_floor_blind}"
    )
    return (not old_sees) and new_sees and clean


def main() -> int:
    a = part_a()
    b = part_b()
    if not (a and b):
        print(f"FAILED:r4-redproof partA={a} partB={b}")
        return 1
    print(
        "SUCCESS:r4-redproof A both-states + 2 mutations, "
        "B the widened DoD1 sees the absence the old one could not"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
