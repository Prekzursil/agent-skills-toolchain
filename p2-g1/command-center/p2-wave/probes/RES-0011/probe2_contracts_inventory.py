#!/usr/bin/env python3
# RES-0011 probe2: frontmatter contracts + live estate inventory (2026-10-25).
# Re-derives the live ~/.claude/agents + ~/.claude/commands inventory (this
# estate HAS the trees; the receipt estate block recorded the /root host where
# they were absent) and cross-checks observed keys against the documented
# contract tables. Model-resolution order is re-asserted from the receipt.
# Reading the live tree is READ-ONLY.
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def fail(msg):
    print("FAILED:RES-0011-probe2 " + str(msg))
    return 1


def frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    keys = set()
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", line)
        if km:
            keys.add(km.group(1))
    return keys


def main():
    rec = json.loads((REPO / "command-center/research/RES-0011.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    fc = rec.get("frontmatter_contracts") or {}
    agent_keys = set((fc.get("agent") or {}).get("keys") or [])
    cmd_keys = set((fc.get("command") or {}).get("keys") or [])
    if not agent_keys or not cmd_keys:
        return fail("receipt-contract-tables-empty")
    home = Path.home()
    live_agents = home / ".claude" / "agents"
    live_commands = home / ".claude" / "commands"
    md_files = sorted(p for p in live_agents.glob("*.md")) if live_agents.is_dir() else []
    print("live agents tree: " + str(live_agents) + " md_files=" + str(len(md_files)))
    observed = {}
    for p in md_files:
        for k in frontmatter(p.read_text(encoding="utf-8", errors="replace")):
            observed[k] = observed.get(k, 0) + 1
    print("live observed agent keys: " + json.dumps(observed, sort_keys=True))
    documented_union = agent_keys | set((rec.get("inventory") or {}).get("agents", {}).get("keys_not_in_docs_table") or [])
    undocumented = sorted(k for k in observed if k not in documented_union)
    if undocumented:
        return fail("undocumented-live-keys:" + json.dumps(undocumented))
    inv = rec.get("inventory") or {}
    rec_files = (inv.get("agents") or {}).get("files")
    print("receipt recorded agents files=" + str(rec_files)
          + " live now=" + str(len(md_files))
          + " (post-closure drift is expected and reported, not failed)")
    # commands tree exists and parses
    cmd_files = sorted(live_commands.glob("*.md")) if live_commands.is_dir() else []
    # estate-local skill-wrapper commands carry a "command:" key that is NOT part
    # of the client slash-command contract; it is an ESTATE EXTENSION and is
    # REPORTED here as recorded residual, never silently passed.
    ESTATE_KEYS = {"command", "allowed_tools"}
    cmd_undoc = []
    estate_ext = {}
    for p in cmd_files:
        for k in frontmatter(p.read_text(encoding="utf-8", errors="replace")):
            if k in cmd_keys:
                continue
            if k in ESTATE_KEYS:
                estate_ext[k] = estate_ext.get(k, 0) + 1
            else:
                cmd_undoc.append((p.name, k))
    if cmd_undoc:
        return fail("undocumented-command-keys:" + json.dumps(cmd_undoc[:5]))
    print("live commands tree: " + str(len(cmd_files)) + " md files; documented keys OK; "
          "estate-extension keys (recorded residual, not contract): " + json.dumps(estate_ext))
    # model resolution order
    mr = rec.get("model_resolution") or {}
    if mr.get("order") != ["CLAUDE_CODE_SUBAGENT_MODEL", "per-invocation model parameter",
                           "definition model frontmatter", "parent conversation model"]:
        return fail("receipt-model-order-drift")
    if mr.get("default") != "inherit" or "inherit" not in (mr.get("aliases") or []):
        return fail("receipt-model-aliases-drift")
    print("model resolution: " + " -> ".join(mr["order"]) + " (default=inherit)")
    if not (rec.get("negative_controls") or []):
        return fail("receipt-negative-controls-absent")
    print("SUCCESS:RES-0011-probe2 contracts-and-inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
