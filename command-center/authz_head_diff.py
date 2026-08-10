#!/usr/bin/env python
"""Collision detector for the shared catalog: git HEAD blob vs the working tree.

TWO agents write ``command-center/WORK-UNIT-CATALOG.json`` in this wave. ``authz_diff_audit.py``
compares MY pre-edit snapshot to MY output, which structurally cannot see a peer write that
landed between the two, so it is not sufficient. This compares against the committed blob and
partitions every difference into MINE and PEER.

Measured 2026-08-10: 134 units differ from HEAD in ``assigned_model_vendor_role`` only - the
D5 vendor/role canonicalization lane. All 134 were already present in my pre-edit snapshot
(HEAD->snapshot = 134, snapshot->worktree = 0), so my full-file rewrite preserved them
byte-identically. The hazard is NOT closed by that: a peer that rewrites the whole file from
a snapshot taken before my write would silently revert my 35 edits. This script is the check
that would catch it.

PASS requires: my 34 unit edits present with their expected values, ``tool_policy`` added,
no unit added or removed, and every remaining difference confined to fields this unit does
not own.

Reads the blob with ``git cat-file -p HEAD:<path>`` - never ``git archive`` (it applies EOL
conversion and returns CRLF on this box) and never the raw working-tree bytes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
REL = "command-center/WORK-UNIT-CATALOG.json"

#: unit id -> (field, expected value after my edit)
APPROVAL_FLIPS = [
    f"TST-0{n}"
    for n in (
        257,
        258,
        259,
        260,
        262,
        263,
        264,
        267,
        268,
        271,
        272,
        273,
        274,
        275,
        276,
        277,
        278,
        279,
        285,
        286,
        289,
        290,
        291,
    )
]
SUBSTRATE_FIXES = ["TST-0293", "TST-0294"]
WILDCARD_EXPANSIONS = [
    "WFA-0021",
    "WFA-0023",
    "WFA-0025",
    "WFA-0026",
    "WFA-0027",
    "WFA-0028",
    "WFA-0031",
    "WFA-0033",
    "WFA-0065",
]
#: the only three fields this unit is allowed to have touched
MY_FIELDS = {"owner_approval_required", "execution_substrate", "tool_permissions"}


def blob() -> dict[str, Any]:
    out = subprocess.run(
        ["git", "cat-file", "-p", f"HEAD:{REL}"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return json.loads(out.stdout.decode("utf-8"))


def main() -> int:
    head = blob()
    work = json.loads((REPO / REL).read_bytes().replace(b"\r\n", b"\n").decode("utf-8"))
    failures: list[str] = []

    added, removed = sorted(set(work) - set(head)), sorted(set(head) - set(work))
    changed_roots = [
        k
        for k in sorted(set(head) & set(work))
        if k != "work_units" and head[k] != work[k]
    ]
    print("root keys added vs HEAD  :", added)
    print("root keys removed vs HEAD:", removed)
    print("other root keys changed  :", changed_roots)
    if added != ["tool_policy"]:
        failures.append(f"unexpected root additions {added}")
    if removed or changed_roots:
        failures.append(f"root keys removed/changed: {removed} {changed_roots}")

    h = {str(u["id"]): u for u in head["work_units"]}
    w = {str(u["id"]): u for u in work["work_units"]}
    print(
        "unit count HEAD/work     :", len(head["work_units"]), len(work["work_units"])
    )
    if set(h) ^ set(w):
        failures.append(
            f"unit id set changed: +{sorted(set(w) - set(h))[:5]} -{sorted(set(h) - set(w))[:5]}"
        )

    touched: dict[str, set[str]] = {}
    for uid in sorted(set(h) & set(w)):
        for field in sorted(set(h[uid]) | set(w[uid])):
            if h[uid].get(field, "<absent>") != w[uid].get(field, "<absent>"):
                touched.setdefault(uid, set()).add(field)

    # --- my edits must all be PRESENT (a peer rewrite would silently drop them) -------
    for uid in APPROVAL_FLIPS:
        if w.get(uid, {}).get("owner_approval_required") is not True:
            failures.append(f"{uid} owner_approval_required is not True (reverted?)")
    for uid in SUBSTRATE_FIXES:
        if str(w.get(uid, {}).get("execution_substrate")) != "local-parallel":
            failures.append(
                f"{uid} execution_substrate is not local-parallel (reverted?)"
            )
    for uid in WILDCARD_EXPANSIONS:
        tools = [str(t) for t in w.get(uid, {}).get("tool_permissions", [])]
        if any("*" in t.split("(", 1)[0] for t in tools):
            failures.append(f"{uid} still holds an identity wildcard (reverted?)")

    mine = set(APPROVAL_FLIPS) | set(SUBSTRATE_FIXES) | set(WILDCARD_EXPANSIONS)
    peer = {uid: fs for uid, fs in touched.items() if uid not in mine}
    peer_fields = {f for fs in peer.values() for f in fs}
    mine_extra_fields = {
        f for uid, fs in touched.items() if uid in mine for f in fs
    } - MY_FIELDS
    print(
        f"units differing vs HEAD  : {len(touched)}  "
        f"(mine={len(touched.keys() & mine)} peer={len(peer)})"
    )
    print("peer-touched fields      :", sorted(peer_fields))
    if peer_fields & MY_FIELDS:
        failures.append(
            f"a peer edited a field this unit owns: {sorted(peer_fields & MY_FIELDS)}"
        )
    if mine_extra_fields:
        failures.append(
            f"my units carry unexpected field edits {sorted(mine_extra_fields)}"
        )

    for line in failures:
        print("  !", line)
    print(
        f"SUCCESS:authz-head-diff mine={len(touched.keys() & mine)} peer={len(peer)} "
        f"peer_fields={sorted(peer_fields)}"
        if not failures
        else f"FAILED:authz-head-diff {len(failures)} problem(s)"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
