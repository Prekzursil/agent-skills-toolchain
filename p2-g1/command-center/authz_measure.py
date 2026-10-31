#!/usr/bin/env python
"""Cross-tabs needed to choose defensible SEM-008..SEM-011 thresholds.

Read-only. Prints, never writes the catalog.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

cat = json.loads(CAT.read_text(encoding="utf-8"))
units = cat["work_units"]

SCOPE = re.compile(r"^(?P<head>[^(]*?)\s*(?:\((?P<scope>.*)\))?\s*$", re.DOTALL)


def identity(token: str) -> str:
    m = SCOPE.match(str(token))
    return (m.group("head") or "").strip() if m else str(token)


def scope_of(token: str) -> str:
    m = SCOPE.match(str(token))
    return (m.group("scope") or "") if m else ""


print("units:", len(units))

# 1. wildcard position: identity vs scope-only
id_wc, scope_wc, both = set(), set(), set()
id_wc_tokens: collections.Counter = collections.Counter()
scope_wc_tokens: collections.Counter = collections.Counter()
for u in units:
    for t in u["tool_permissions"]:
        t = str(t)
        i, s = identity(t), scope_of(t)
        if "*" in i:
            id_wc.add(u["id"])
            id_wc_tokens[t] += 1
        if "*" in s:
            scope_wc.add(u["id"])
            scope_wc_tokens[t] += 1
any_wc = {u["id"] for u in units if any("*" in str(t) for t in u["tool_permissions"])}
print("\n--- wildcard census ---")
print("units with '*' ANYWHERE in a token     :", len(any_wc))
print("units with '*' in the token IDENTITY   :", len(id_wc))
print("units with '*' only in a ( ) SCOPE     :", len(scope_wc - id_wc))
print("identity-wildcard tokens:", dict(id_wc_tokens))
print("scope-wildcard tokens   :", dict(scope_wc_tokens))

# 2. Task / mcp / approval
task_units = [
    u for u in units if any(identity(t) == "Task" for t in u["tool_permissions"])
]
mcp_units = [
    u
    for u in units
    if any(identity(t).startswith("mcp__") for t in u["tool_permissions"])
]
approved = [u for u in units if u.get("owner_approval_required") is True]
print("\n--- headline census ---")
print("owner_approval_required true :", len(approved))
print("units holding Task           :", len(task_units))
print(
    "  of those UNAPPROVED        :",
    sum(1 for u in task_units if u.get("owner_approval_required") is not True),
)
print("units holding an mcp__ token :", len(mcp_units))
print(
    "  of those UNAPPROVED        :",
    sum(1 for u in mcp_units if u.get("owner_approval_required") is not True),
)
print(
    "identity-wildcard UNAPPROVED :",
    sum(
        1
        for u in units
        if u["id"] in id_wc and u.get("owner_approval_required") is not True
    ),
)

# 3. substrate cross-tab for candidate substrate-coherence tokens
CANDIDATES = [
    "Task",
    "AskUserQuestion",
    "Monitor",
    "PowerShell",
    "WebFetch",
    "WebSearch",
    "Edit",
    "Write",
]
print("\n--- substrate x candidate token (unit counts) ---")
subs = sorted({str(u["execution_substrate"]) for u in units})
hdr = "substrate".ljust(20) + "".join(c[:14].rjust(16) for c in CANDIDATES) + "     n"
print(hdr)
for s in subs:
    row = [u for u in units if str(u["execution_substrate"]) == s]
    cells = []
    for c in CANDIDATES:
        n = sum(1 for u in row if any(identity(t) == c for t in u["tool_permissions"]))
        cells.append(str(n).rjust(16))
    print(s.ljust(20) + "".join(cells) + str(len(row)).rjust(6))

# 4. which units are cloud-batch AND hold a session-local tool
print("\n--- cloud-batch units holding a session-local tool ---")
LOCAL_ONLY = {"Task", "AskUserQuestion", "Monitor", "PowerShell"}
for u in units:
    if str(u["execution_substrate"]) != "cloud-batch":
        continue
    hits = sorted(
        {identity(t) for t in u["tool_permissions"] if identity(t) in LOCAL_ONLY}
    )
    if hits:
        print(" ", u["id"], hits, "approved=" + str(u.get("owner_approval_required")))

# 5. every Task-holding unit
print("\n--- every Task-holding unit ---")
for u in task_units:
    print(
        " ",
        u["id"],
        str(u["execution_substrate"]).ljust(18),
        "approved=" + str(u.get("owner_approval_required")),
        "|",
        str(u["title"])[:80],
    )

# 6. every identity-wildcard unit
print("\n--- every identity-wildcard unit ---")
for u in units:
    if u["id"] in id_wc:
        wc = [str(t) for t in u["tool_permissions"] if "*" in identity(str(t))]
        print(
            " ",
            u["id"],
            str(u["execution_substrate"]).ljust(18),
            "approved=" + str(u.get("owner_approval_required")),
            wc,
        )

# 7. distinct identities (for the allowlist)
ids: collections.Counter = collections.Counter()
for u in units:
    for t in u["tool_permissions"]:
        ids[identity(str(t))] += 1
print("\n--- distinct token identities:", len(ids))
for k, v in sorted(ids.items()):
    print(f"  {v:>5}  {k}")

print("\n--- existing tool_policy on the catalog root? ---")
print("tool_policy" in cat, list(cat.keys()))
