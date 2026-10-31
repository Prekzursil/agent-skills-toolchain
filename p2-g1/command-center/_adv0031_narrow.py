"""ADV-0031 step 2 - narrow the 1,852 call sites to FIRST-PARTY sites where an
externally-supplied parameter actually reaches the sink.

Two filters:
  (a) first-party path (drop vendored / mirrored third-party trees)
  (b) the sink line interpolates a variable (a constant command line cannot be injected)
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INV = REPO / "command-center" / "_adv0031_inventory_out.json"

# Vendored / mirrored third-party trees. These ship inside the repo but are not authored here,
# so a finding in them is an upstream bug, not this program's injection surface.
THIRD_PARTY_PREFIXES = (
    "tools/editor/",            # metaswarm + ralph-orchestrator vendored checkouts
    "tools/mcp/",               # vendored MCP servers
    "tools/omniaudit-mcp/",
    "node_modules/",
    "harness-sota-",
    "apktool_mcp_server_workspace/",
    "release/",
)
# Mirrors of the same authored file (live-tree copies). Keep ONE canonical copy.
MIRROR_PREFIXES = (".agents/skills/", ".claude/")

VAR_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*|\$[@*1-9#]|\$\(|%[A-Za-z_]+%")


def first_party(p: str) -> bool:
    return not p.startswith(THIRD_PARTY_PREFIXES)


def canonical(p: str) -> bool:
    return not p.startswith(MIRROR_PREFIXES)


def main() -> None:
    inv = json.loads(INV.read_text(encoding="utf-8"))
    rows = []
    for key in ("string_command_sites", "here_string_sites", "argv_dynamic_sites"):
        rows += inv[key]

    kept = []
    for r in rows:
        f = r["file"]
        if not first_party(f) or not canonical(f):
            continue
        has_var = bool(VAR_RE.search(r.get("src", "")))
        r = dict(r, interpolates_variable=has_var)
        kept.append(r)

    interp = [r for r in kept if r["interpolates_variable"]]
    by_shape = collections.Counter(r["shape"] for r in interp)
    by_file = collections.Counter(r["file"] for r in interp)

    out = {
        "input_total_sites": len(rows),
        "first_party_canonical": len(kept),
        "first_party_canonical_interpolating_a_variable": len(interp),
        "by_shape": dict(by_shape),
        "top_files": by_file.most_common(30),
        "sites": interp,
    }
    dst = REPO / "command-center" / "_adv0031_narrow_out.json"
    dst.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "sites"}, indent=2))
    print("wrote", dst)


if __name__ == "__main__":
    main()
