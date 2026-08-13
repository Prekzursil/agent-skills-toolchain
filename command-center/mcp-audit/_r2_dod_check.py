#!/usr/bin/env python3
"""Check all four lane DoD items against the COMMITTED BLOB, not the working tree.

A DoD ledger written as prose is a claim.  This executes it, and it reads
``git show <rev>:<path>`` so the verdict is about the bytes that actually shipped -- a
working-tree check would pass on an uncommitted edit that no reviewer will ever see.

  DoD1  every mounted server inventoried with its scope and source file
  DoD2  liveness distinguished from capability by a REAL call
  DoD3  per-server context cost measured
  DoD4  recommendations reversible (disable, not remove) with evidence per row

Each item also carries a NEGATIVE control: the same predicate is re-run against a
deliberately broken copy of the row set and must fail there.  Without that, a predicate
with a typo'd field name would report PASS for all 23 rows by finding nothing to object
to -- the control-that-cannot-distinguish failure this lane has already committed twice.

Run::  python _r2_dod_check.py [rev]   ->  exit 0 only if all four PASS and all four
negative controls fire.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
from typing import Any, Callable

REPO = pathlib.Path(__file__).resolve().parents[2]
DISP = "command-center/mcp-audit/disposition.json"
REVERSIBLE = {"KEEP", "DISABLE", "INVESTIGATE"}

# ROUND 4, closing a gap a verifier found LATENT: dod1() checked fields per row but never
# SET MEMBERSHIP, and main() failed closed only below 20 rows -- so silently dropping up
# to 3 mounted servers would still print "DoD1 PASS  inventory: scope + source file per
# row".  Every surviving row would be well-formed; the missing ones simply would not be
# asked about.  That is DoD1's actual promise ("EVERY mounted server inventoried"), so the
# gate has to be able to notice an absence, not just malformed presence.
#
# PINNED 2026-08-13 from two mechanically independent sources that agree exactly:
#   (a) the 23 `mcp__<name>__*` namespaces the harness exposed to this session, and
#   (b) the 23 rows of the committed capability-matrix.json.
# LIMITATION, stated because a gate that hides one is worse than no gate: a committed blob
# cannot know what is mounted TODAY, so this is a FLOOR.  A newly mounted server does not
# red the gate (it should be added, but its absence is an inventory gap this artifact
# cannot self-detect); a server disappearing DOES.  Retiring one legitimately therefore
# requires editing this constant in the same commit -- which is the point: a deliberate,
# reviewable line in a diff instead of a silent shrink.
EXPECTED_MOUNTED = frozenset(
    {
        "agent-mail",
        "angr",
        "basic-memory",
        "brightdata",
        "chrome-devtools",
        "claude-code-mcp",
        "cloud-hub",
        "codex",
        "context7",
        "deepwiki",
        "figma",
        "frida-mcp",
        "github",
        "huggingface",
        "paper-search",
        "playwright",
        "playwright-cdp",
        "playwright-extension",
        "qlty",
        "repomix",
        "scholarly-access",
        "search-hub",
        "searxng",
    }
)


def blob(rev: str, path: str) -> dict:
    if rev == "WORKTREE":
        # Pre-flight only.  The default stays HEAD because a working-tree check passes on
        # an uncommitted edit no reviewer will ever see; the marker below says so out loud
        # so a WORKTREE run can never be quoted as a shipped verdict.
        return json.loads((REPO / path).read_text(encoding="utf-8"))
    out = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def dod1(rows: list[dict[str, Any]]) -> list[str]:
    """Scope + absolute source file on every row, and no mounted server may vanish."""
    bad = []
    for name in sorted(EXPECTED_MOUNTED - {r.get("name") for r in rows}):
        bad.append(f"{name}: mounted server absent from the row set")
    for r in rows:
        for field in ("definition_scope", "source_file", "config_basis", "transport"):
            if not r.get(field):
                bad.append(f"{r['name']}: empty {field}")
        src = r.get("source_file") or ""
        if src and not pathlib.Path(src).is_absolute():
            bad.append(f"{r['name']}: source_file not absolute")
        elif src and not pathlib.Path(src).exists():
            bad.append(f"{r['name']}: source_file missing on disk")
    return bad


def dod2(rows: list[dict[str, Any]]) -> list[str]:
    """S4 must be the union of its two methods, and unverified rows must state why."""
    bad = []
    for r in rows:
        union = bool(r.get("handshake_verified")) or bool(r.get("s4_executed"))
        if bool(r.get("call_verified")) != union:
            bad.append(f"{r['name']}: call_verified contradicts its own evidence")
        if not union and "no real call" not in (r.get("evidence") or ""):
            bad.append(f"{r['name']}: unverified without a recorded reason")
    return bad


COST_FIELDS = ("tool_count", "name_bytes", "schema_bytes", "rss_bytes")
NOT_MEASURED = "not-measured:"


def dod3(rows: list[dict[str, Any]]) -> list[str]:
    """EVERY row carries a measured cost, or a stated reason why it does not.

    ROUND 3 WIDENED THIS, BECAUSE THE ROUND-2 VERSION COULD NOT SEE THE GAP IT WAS
    NAMED AFTER.  It opened with ``if not r.get("handshake_verified"): continue``, so the
    seven rows that carry no cost at all were skipped and DoD3 printed PASS for
    "per-server context cost measured" while 7 of 23 rows were silently null -- and its
    negative control (blank a measured row's ``rss_bytes``) could only ever exercise the
    measured branch, so it proved the predicate ran, not that a silent gap would be
    caught.  A control that passes under both hypotheses is not a control.

    The predicate is now: a gap is acceptable ONLY beside a ``liveness_basis`` that
    starts with ``not-measured:`` and gives a reason.  Silence is the failure.
    """
    bad = []
    for r in rows:
        gaps = [f for f in COST_FIELDS if r.get(f) is None]
        if not gaps:
            continue
        basis = r.get("liveness_basis") or ""
        reason = (
            basis[len(NOT_MEASURED) :].strip() if basis.startswith(NOT_MEASURED) else ""
        )
        if len(reason) < 12:
            bad.append(f"{r['name']}: {gaps} unmeasured with no stated reason")
    return bad


def dod4(rows: list[dict[str, Any]]) -> list[str]:
    """No irreversible disposition, and every row carries a real evidence sentence."""
    bad = []
    for r in rows:
        if r.get("disposition") not in REVERSIBLE:
            bad.append(f"{r['name']}: irreversible {r.get('disposition')!r}")
        if len(r.get("evidence") or "") < 20:
            bad.append(f"{r['name']}: evidence too thin")
    return bad


def break_for(control: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A copy of the rows carrying exactly the defect `control` is supposed to catch."""
    bad = copy.deepcopy(rows)
    if control == "drop-a-mounted-row":
        # The shape the round-2/3 gate could not express: a well-formed table that is
        # simply MISSING a server.  Drop one that is in the pinned set, not just rows[0].
        for i, r in enumerate(bad):
            if r.get("name") in EXPECTED_MOUNTED:
                return bad[:i] + bad[i + 1 :]
        return bad
    if control == "blank-source-file":
        bad[0]["source_file"] = ""
    elif control == "flip-call-verified":
        bad[0]["call_verified"] = not bad[0]["call_verified"]
    elif control == "drop-rss-on-measured-row":
        for r in bad:
            if r.get("liveness_basis", "").startswith(NOT_MEASURED):
                continue
            r["rss_bytes"] = None
            break
    elif control == "strip-reason-from-unmeasured-row":
        # The shape the round-2 predicate could not express: a row with no cost AND no
        # stated reason -- i.e. exactly what 7 rows looked like before round 3.
        for r in bad:
            if any(r.get(f) is None for f in COST_FIELDS):
                r["liveness_basis"] = ""
                break
    elif control == "irreversible-disposition":
        bad[0]["disposition"] = "REMOVE"
    return bad


CHECKS: dict[
    str, tuple[str, Callable[[list[dict[str, Any]]], list[str]], list[str]]
] = {
    "DoD1": (
        "inventory: scope + source file per row, and no server missing",
        dod1,
        # BOTH branches: a malformed row, and an ABSENT one.  Round 3 controlled only the
        # first, so a shrinking table passed.
        ["blank-source-file", "drop-a-mounted-row"],
    ),
    "DoD2": (
        "liveness vs capability by a real call",
        dod2,
        ["flip-call-verified"],
    ),
    "DoD3": (
        "per-server context cost measured, or a stated reason",
        dod3,
        # BOTH branches, because the predicate has two and round 2 only controlled one.
        ["drop-rss-on-measured-row", "strip-reason-from-unmeasured-row"],
    ),
    "DoD4": (
        "reversible recommendations with evidence",
        dod4,
        ["irreversible-disposition"],
    ),
}


def main(argv: list[str]) -> int:
    rev = argv[0] if argv else "HEAD"
    disp = blob(rev, DISP)
    rows = disp["rows"]
    # Tied to the pinned set rather than a hand-picked 20, so the floor cannot drift below
    # the inventory it is supposed to protect.
    if len(rows) < len(EXPECTED_MOUNTED):
        print(
            f"FAILED:dod-check only {len(rows)} rows, "
            f"fewer than the {len(EXPECTED_MOUNTED)} pinned mounted servers (fail closed)"
        )
        return 1

    print(f"== DoD ledger, executed against {rev}:{DISP} ({len(rows)} rows) ==")
    failed: list[str] = []
    n_controls = 0
    for item, (label, fn, controls) in CHECKS.items():
        problems = fn(rows)
        fired = {c: bool(fn(break_for(c, rows))) for c in controls}
        n_controls += len(controls)
        state = "PASS" if not problems and all(fired.values()) else "FAIL"
        print(f"  {item} {state}  {label}")
        for control, ok in fired.items():
            print(f"       negative control {control:34} fires: {ok}")
        if problems:
            print(f"       problems: {problems[:4]}")
        if state == "FAIL":
            failed.append(item)

    verified = sum(1 for r in rows if r.get("call_verified"))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["disposition"]] = counts.get(r["disposition"], 0) + 1
    # A row with NO basis at all is not "measured" -- on a pre-round-3 blob every row
    # lacks the field, and a naive `not startswith(...)` reported cost-measured=23/23
    # directly beneath a DoD3 FAIL.  A summary that contradicts the verdict above it is a
    # detector failure, so absence counts as unmeasured.
    measured = sum(
        1
        for r in rows
        if (r.get("liveness_basis") or "").strip()
        and not r["liveness_basis"].startswith(NOT_MEASURED)
    )
    print(
        f"  summary: call_verified={verified}/{len(rows)}  "
        f"cost-measured={measured}/{len(rows)}  dispositions={counts}"
    )
    if failed:
        print(f"FAILED:dod-check {failed}")
        return 1
    scope = " [WORKTREE pre-flight, NOT a shipped verdict]" if rev == "WORKTREE" else ""
    print(
        f"SUCCESS:dod-check 4/4 DoD items PASS, {n_controls}/{n_controls} "
        f"negative controls fired{scope}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
