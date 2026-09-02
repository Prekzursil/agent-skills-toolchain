#!/usr/bin/env python3
"""Enrol proxy-mcp in the disabled-by-default MCP set.

The owner's standing preference is "expose them all, keep them disabled" -- a
server should be visible in the canonical inventory but must not spawn until a
session actually wants it. That matters more than usual for this one: a traffic
proxy is both heavyweight and privacy-sensitive, and this machine has a
documented freeze mode driven by per-session stdio MCP process duplication.

This script adds ``proxy-mcp`` to ``~/.claude/.mcp-disabled-defaults.json``, the
canonical list the ``mcp-defaults`` SessionStart hook reads. That hook then
propagates the entry into each project's ``disabledMcpServers`` array on its own.

It deliberately does NOT touch ``~/.claude.json``. A running Claude Code session
holds that file in memory and rewrites it every ~30s, so any external edit is
silently clobbered -- the hook is the supported write path, not this script.

Idempotent, backs up before writing, and verifies the result before replacing the
original.

Usage::

    python apply-disabled-default.py            # apply
    python apply-disabled-default.py --dry-run  # show the plan, write nothing
    python apply-disabled-default.py --undo     # re-enable (remove from the list)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys

SERVER = "proxy-mcp"
DEFAULTS = os.path.join(
    os.path.expanduser("~"), ".claude", ".mcp-disabled-defaults.json"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true", help="show the plan, write nothing"
    )
    ap.add_argument("--undo", action="store_true", help="remove the entry (re-enable)")
    args = ap.parse_args()

    if not os.path.exists(DEFAULTS):
        print(f"FAILED: {DEFAULTS} not found")
        return 1

    with open(DEFAULTS, encoding="utf-8") as fh:
        doc = json.load(fh)

    entries = list(doc.get("disabledMcpServers", []))
    present = SERVER in entries

    if args.undo:
        if not present:
            print(
                f"SUCCESS: {SERVER} already absent ({len(entries)} disabled) - no change"
            )
            return 0
        updated = [e for e in entries if e != SERVER]
    else:
        if present:
            print(
                f"SUCCESS: {SERVER} already disabled-by-default ({len(entries)} disabled)"
            )
            return 0
        updated = sorted([*entries, SERVER])

    verb = "remove" if args.undo else "add"
    print(f"plan: {verb} {SERVER!r}  ({len(entries)} -> {len(updated)} disabled)")
    if args.dry_run:
        print("SUCCESS: dry run, nothing written")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{DEFAULTS}.bak-{SERVER}-{stamp}"
    shutil.copy2(DEFAULTS, backup)
    if os.path.getsize(backup) == 0:
        print(f"FAILED: backup {backup} is empty - refusing to write")
        return 1

    doc["disabledMcpServers"] = updated
    tmp = DEFAULTS + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    with open(tmp, encoding="utf-8") as fh:
        check = json.load(fh)
    if (SERVER in check.get("disabledMcpServers", [])) == args.undo:
        os.remove(tmp)
        print("FAILED: verification failed - original left untouched")
        return 1

    os.replace(tmp, DEFAULTS)
    print(f"backup: {backup}")
    print(f"SUCCESS: {SERVER} {'re-enabled' if args.undo else 'disabled-by-default'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
