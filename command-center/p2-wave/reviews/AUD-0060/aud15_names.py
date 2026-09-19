# Extract AUD-0015 ENABLED-DECLARED server names (list items carry name fields).
import json

ROOT = r"C:\Users\Prekzursil\source\agent-skills-toolchain"
a15 = json.load(
    open(
        ROOT + r"\command-center\audit\AUD-0015-mcp-scope-resolution.json",
        encoding="utf-8",
    )
)
servers = a15["report"]["servers"]
probe1_16 = [
    "agent-mail",
    "basic-memory",
    "cloud-hub",
    "codex",
    "deepwiki",
    "fiddler",
    "figma",
    "frida-mcp",
    "github",
    "huggingface",
    "paper-search",
    "playwright",
    "qlty",
    "repomix",
    "scholarly-access",
    "search-hub",
]
item0 = servers[0] if isinstance(servers, list) else None
print(
    "item_type:",
    type(servers).__name__,
    "| first_item_keys:",
    sorted(item0.keys()) if isinstance(item0, dict) else "?",
)
ed = []
for it in servers:
    if isinstance(it, dict) and it.get("effective_state") == "ENABLED-DECLARED":
        nm = it.get("name") or it.get("server") or it.get("id") or it.get("label")
        ed.append(nm)
print("ENABLED-DECLARED count:", len(ed))
print("names:", sorted(str(x) for x in ed))
print("set_equal_to_probe1_16:", sorted(str(x) for x in ed) == sorted(probe1_16))
# also show where AUD-0015 says its server universe came from
src = (
    a15.get("report", {}).get("question") or a15.get("report", {}).get("headline") or ""
)
print("aud0015_report_headline:", str(src)[:300])
