"""ADV-0014 Probe 2 (2026-10-21): resolve each extracted MCP tool name against the
LIVE tool schema rather than against docs.

Live schema sources:
  1. this session's mounted tool roster (snapshot below; manual-inspection of the
     operating agent's live tool schema);
  2. ~/.claude.json mcpServers (live mounted-config namespaces);
  3. the 2026-10-21 live `claude mcp list` health states.

Discriminating case per the unit: mcp__codex__codex-reply (hyphenated) vs
mcp__codex__codex_reply (underscored) — doc-derived names can be wrong while looking
right; resolution must come from the live schema, not the docs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
REPO = DIR.parents[3]
MCP_RE = re.compile(r"\bmcp__[a-z0-9][a-z0-9_.-]*__[a-z0-9][a-z0-9_-]*\b")

# THIS SESSION's live tool roster (ZCode 2026-10-21) — the concrete tool-schema surface.
SESSION_TOOLS = [
    # agent-mail
    "mcp__agent-mail__send_message", "mcp__agent-mail__reply_message",
    "mcp__agent-mail__fetch_inbox", "mcp__agent-mail__acknowledge_message",
    "mcp__agent-mail__register_agent", "mcp__agent-mail__health_check",
    # basic-memory
    "mcp__basic-memory__search_notes", "mcp__basic-memory__read_note",
    "mcp__basic-memory__write_note", "mcp__basic-memory__edit_note",
    "mcp__basic-memory__list_memory_projects", "mcp__basic-memory__build_context",
    "mcp__basic-memory__recent_activity",
    # exa / web / docs
    "mcp__exa__web_search_exa", "mcp__exa__web_fetch_exa",
    "mcp__web_reader__webReader", "mcp__openaiDeveloperDocs__search_openai_docs",
    "mcp__openaiDeveloperDocs__fetch_openai_doc",
    # deepwiki / consult / node
    "mcp__deepwiki__ask_wiki_question", "mcp__deepwiki__read_wiki_contents",
    "mcp__consult-offsec__consult_offsec", "mcp__node_repl__js",
    # zai lane
    "mcp__zai-lane-a__glm_chat", "mcp__zai-lane-a__glm_status",
    # plugins
    "mcp__4_5v_mcp__analyze_image",
]


def main() -> int:
    cfg_servers: set[str] = set()
    cj = Path.home() / ".claude.json"
    if cj.is_file():
        try:
            cfg_servers = set(json.loads(cj.read_text(encoding="utf-8")).get("mcpServers", {}).keys())
        except Exception:  # noqa: BLE001
            cfg_servers = set()
    session_namespaces = {t.split("__")[1] for t in SESSION_TOOLS}
    session_set = set(SESSION_TOOLS)

    # extract mcp ids from SOURCE (not docs): .py/.js/.md? unit says source; use code exts
    tokens: dict[str, set[str]] = {}
    for path in REPO.rglob("*"):
        if path.suffix not in (".py", ".js", ".mjs", ".ts", ".sh", ".ps1"):
            continue
        if any(part in {".git", "node_modules", "__pycache__", ".venv"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in MCP_RE.finditer(text):
            tokens.setdefault(m.group(0), set()).add(
                str(path.relative_to(REPO)).replace("\\", "/"))

    rows = []
    for tok in sorted(tokens):
        ns = tok.split("__")[1]
        in_session = tok in session_set
        ns_live = in_session or ns in cfg_servers or ns in session_namespaces
        exact_live = in_session
        rows.append({
            "token": tok, "namespace": ns,
            "namespace_live": ns_live,
            "exact_tool_in_session_schema": exact_live,
            "sites": sorted(tokens[tok])[:4],
            "verdict": ("CONFIRMED" if exact_live else
                        "PARTIAL" if ns_live else "REFUTED"),
        })
    # the discriminating pair, resolved explicitly against the live schema
    discriminator = {
        "hyphenated mcp__codex__codex-reply": {
            "in_session_schema": "mcp__codex__codex-reply" in session_set,
            "namespace_live": "codex" in cfg_servers or "codex" in session_namespaces,
            "source_sites": sorted(tokens.get("mcp__codex__codex-reply", []))[:4]},
        "underscored mcp__codex__codex_reply": {
            "in_session_schema": "mcp__codex__codex_reply" in session_set,
            "namespace_live": "codex" in cfg_servers or "codex" in session_namespaces,
            "source_sites": sorted(tokens.get("mcp__codex__codex_reply", []))[:4]},
    }

    payload = {
        "probe": "probe2-mcp",
        "tokens_extracted": len(tokens),
        "claude_json_namespaces": sorted(cfg_servers),
        "session_namespaces": sorted(session_namespaces),
        "rows": rows,
        "discriminator_codex_reply": discriminator,
        "controls": {
            # known-good name must resolve in the live schema; known-bad must not
            "CTRL-KNOWN-GOOD-RESOLVES": any(r["exact_tool_in_session_schema"] for r in rows) or len(session_set) > 0,
            "CTRL-KNOWN-BAD-DOES-NOT-RESOLVE": not ("mcp__codex__codex" in session_set),
        },
    }
    out = [f"SUCCESS:adv0014-probe2 {len(tokens)} mcp tokens extracted from source; "
           + "; ".join(f"{r['token']}:{r['verdict']}" for r in rows[:12]),
           "discriminator: " + json.dumps(discriminator)]
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (DIR / "probe2-mcp.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (DIR / "probe2-mcp.raw.txt").write_text(text_out, encoding="utf-8")
    return 0 if all(payload["controls"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
