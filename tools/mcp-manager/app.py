#!/usr/bin/env python
"""mcp-manager — cross-plane MCP + skill manager (CLI surface).

Read-only inventory + analysis today; safe toggle adapters available for a future
Textual GUI. Never mutates real config without an explicit subcommand + confirmation.

Usage:
  uv run app.py status        # unified MCP inventory across planes (+ duplicates)
  uv run app.py duplicates    # just the cross-plane duplicate servers
  uv run app.py consolidate   # Spec-3 user-skill consolidation analysis (no deletions)
  uv run app.py json          # full machine-readable inventory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.inventory import build_inventory  # noqa: E402
from core import consolidation  # noqa: E402

HOME = Path.home()
PROJ = str(HOME).replace("\\", "/")
SKILL_ROOTS = [HOME / ".claude" / "skills", HOME / ".agents" / "skills"]


def cmd_status() -> None:
    rep = build_inventory(HOME, project_path=PROJ)
    print(
        f"MCP servers across planes: {rep['server_count']}  "
        + f"(cross-plane duplicates: {len(rep['duplicated_servers'])})\n"
    )
    print(f"{'SERVER':28} {'PLANES':40} STATE")
    print("-" * 90)
    for s in rep["servers"]:
        state = (
            "enabled:" + ",".join(sorted(set(s["enabled_in"])))
            if s["enabled_in"]
            else ""
        )
        if s["disabled_in"]:
            state += "  disabled:" + ",".join(sorted(set(s["disabled_in"])))
        dup = " *DUP*" if s["duplicated"] else ""
        print(
            f"{s['name'][:27]:28} {','.join(sorted(set(s['planes'])))[:39]:40} {state}{dup}"
        )


def cmd_duplicates() -> None:
    rep = build_inventory(HOME, project_path=PROJ)
    print("Cross-plane duplicate servers (defined in >1 plane):")
    for n in rep["duplicated_servers"]:
        print(f"  {n}")
    print(f"\nTotal: {len(rep['duplicated_servers'])} of {rep['server_count']}")


def cmd_consolidate() -> None:
    analysis = consolidation.analyze_skills(SKILL_ROOTS)
    print(consolidation.render_report(analysis))


def cmd_json() -> None:
    json.dump(build_inventory(HOME, project_path=PROJ), sys.stdout, indent=2)


def main(argv: list[str]) -> int:
    cmds = {
        "status": cmd_status,
        "duplicates": cmd_duplicates,
        "consolidate": cmd_consolidate,
        "json": cmd_json,
    }
    cmd = argv[1] if len(argv) > 1 else "status"
    fn = cmds.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
