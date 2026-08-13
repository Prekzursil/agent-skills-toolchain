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


def blob(rev: str, path: str) -> dict:
    out = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def dod1(rows: list[dict[str, Any]]) -> list[str]:
    """Scope + absolute source file on every row, and the file must exist."""
    bad = []
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


def dod3(rows: list[dict[str, Any]]) -> list[str]:
    """Every row verified by a handshake must carry a measured cost, not a null."""
    bad = []
    for r in rows:
        if not r.get("handshake_verified"):
            continue
        for field in ("tool_count", "name_bytes", "schema_bytes", "rss_bytes"):
            if r.get(field) is None:
                bad.append(f"{r['name']}: {field} unmeasured")
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


def break_for(item: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A copy of the rows with exactly the defect `item` is supposed to catch."""
    bad = copy.deepcopy(rows)
    if item == "DoD1":
        bad[0]["source_file"] = ""
    elif item == "DoD2":
        bad[0]["call_verified"] = not bad[0]["call_verified"]
    elif item == "DoD3":
        for r in bad:
            if r.get("handshake_verified"):
                r["rss_bytes"] = None
                break
    elif item == "DoD4":
        bad[0]["disposition"] = "REMOVE"
    return bad


CHECKS: dict[str, tuple[str, Callable[[list[dict[str, Any]]], list[str]]]] = {
    "DoD1": ("inventory: scope + source file per row", dod1),
    "DoD2": ("liveness vs capability by a real call", dod2),
    "DoD3": ("per-server context cost measured", dod3),
    "DoD4": ("reversible recommendations with evidence", dod4),
}


def main(argv: list[str]) -> int:
    rev = argv[0] if argv else "HEAD"
    disp = blob(rev, DISP)
    rows = disp["rows"]
    if len(rows) < 20:
        print(f"FAILED:dod-check only {len(rows)} rows (fail closed)")
        return 1

    print(f"== DoD ledger, executed against {rev}:{DISP} ({len(rows)} rows) ==")
    failed: list[str] = []
    for item, (label, fn) in CHECKS.items():
        problems = fn(rows)
        control_fired = bool(fn(break_for(item, rows)))
        state = "PASS" if not problems and control_fired else "FAIL"
        print(f"  {item} {state}  {label}")
        print(f"       negative control fires: {control_fired}")
        if problems:
            print(f"       problems: {problems[:4]}")
        if state == "FAIL":
            failed.append(item)

    verified = sum(1 for r in rows if r.get("call_verified"))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["disposition"]] = counts.get(r["disposition"], 0) + 1
    print(f"  summary: call_verified={verified}/{len(rows)}  dispositions={counts}")
    if failed:
        print(f"FAILED:dod-check {failed}")
        return 1
    print("SUCCESS:dod-check 4/4 DoD items PASS, 4/4 negative controls fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
