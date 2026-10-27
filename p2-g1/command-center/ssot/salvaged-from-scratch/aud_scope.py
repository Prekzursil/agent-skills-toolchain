import json
import pathlib

BASE = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit")
d = json.loads((BASE / "disposition.json").read_text(encoding="utf-8"))
rows = d["rows"]

# The 23 MCP server namespaces visible in THIS auditor session's deferred-tool list.
# Transcribed by hand from the system prompt tool inventory -- a mechanically INDEPENDENT
# signal from anything the lane produced (it comes from the harness, not from disposition.json).
SESSION_NS = {
    "agent-mail", "angr", "basic-memory", "brightdata", "chrome-devtools",
    "claude-code-mcp", "cloud-hub", "codex", "context7", "deepwiki", "figma",
    "frida-mcp", "github", "huggingface", "paper-search", "playwright",
    "playwright-cdp", "playwright-extension", "qlty", "repomix",
    "scholarly-access", "search-hub", "searxng",
}
rownames = {r["name"] for r in rows}
print("auditor-session namespaces:", len(SESSION_NS))
print("disposition rows          :", len(rownames))
print("SET IDENTICAL             :", SESSION_NS == rownames)
print("only in session :", sorted(SESSION_NS - rownames))
print("only in rows    :", sorted(rownames - SESSION_NS))
print()
print("session_mounted values:", {r["name"]: r.get("session_mounted") for r in rows})
print()
print("counts block:", json.dumps(d.get("counts"), indent=1)[:600])
print()
print("s4_declined:", json.dumps(d.get("s4_declined"))[:400])
print()
for k in ("refuted_round_1", "refuted_round_2", "reversibility_invariant", "signals"):
    print(f"--- {k} ---")
    print(json.dumps(d.get(k), indent=1)[:900])
    print()
