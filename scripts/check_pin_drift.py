#!/usr/bin/env python3
"""Pin-drift gate v2 (2026-09-19 pin-all policy): flags registry npx AND uvx
entries that are unpinned or float @latest. Exit 1 with findings (advisory if
PIN_DRIFT=warn). Disabled rows are exempt (policy polices active servers)."""

import json
import os
import re
import sys
from pathlib import Path

NPX_LATEST = re.compile(r"^[\w@/.-]+@latest$")
NPX_BARE = re.compile(r"^[\w@/.-]+$")
UVX_BARE = re.compile(r"^[\w.-]+$")

reg = json.loads((Path.home() / ".agents" / "agents.json").read_text(encoding="utf-8"))
bad = []
for name, e in reg.get("mcp", {}).get("servers", {}).items():
    if not e.get("enabled", True):
        continue  # parked rows exempt
    args = [str(a) for a in (e.get("args") or [])]
    joined = str(e.get("command", "")) + " " + " ".join(args)

    if "uvx" in joined:
        # package position: --from's value if present, else the first
        # non-flag arg. Other bare positionals are console-script names or
        # mode words (stdio/sse) — never packages. Constraint chars (== @ < >)
        # count as pinned.
        def _pinned(tok: str) -> bool:
            return any(c in tok for c in ("==", "@", "<", ">")) or ("/" in tok or "\\" in tok)

        pkg = None
        if "--from" in args:
            idx = args.index("--from")
            if idx + 1 < len(args):
                pkg = args[idx + 1]
        else:
            for a in args:
                if a.startswith("-") or a in ("uvx", "run"):
                    continue
                pkg = a
                break
        if pkg is not None and UVX_BARE.match(pkg) and not _pinned(pkg):
            bad.append(f"{name}: uvx {pkg}")

    if "npx" in joined:
        for i, a in enumerate(args):
            if a == "-y" and i + 1 < len(args):
                a = args[i + 1]
            if NPX_LATEST.match(a):
                bad.append(f"{name}: {a}")
            elif (NPX_BARE.match(a) and not a.startswith("-") and "@" not in a[1:]
                  and i > 0 and args[i - 1] in ("-y", "npx")):
                bad.append(f"{name}: {a}")

if bad:
    print("PIN-DRIFT: " + "; ".join(bad))
    sys.exit(0 if os.environ.get("PIN_DRIFT") == "warn" else 1)
print("PIN-DRIFT: clean (all npx+uvx pins absolute)")
sys.exit(0)
