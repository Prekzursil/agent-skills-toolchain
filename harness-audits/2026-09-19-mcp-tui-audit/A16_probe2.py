import json, os, re

H = os.path.expanduser("~")
run = "C:/Users/Prekzursil/source/agent-skills-toolchain/harness-audits/2026-09-19-mcp-tui-audit"

old = {x["name"] for x in json.load(open(run + "/registry-inventory.json", encoding="utf-8"))}
reg = json.load(open(H + "/.agents/agents.json", encoding="utf-8"))["mcp"]["servers"]
new = set(reg)
print("registry_total_now:", len(reg), "| inventory_0541:", len(old))
print("added_since_0541:", sorted(new - old))
print("removed_since_0541:", sorted(old - new))

cfg = H + "/.McpHub/config.json"
if os.path.exists(cfg):
    txt = open(cfg, encoding="utf-8", errors="replace").read()
    n = 0
    for line in txt.splitlines():
        if re.search(r'pdf[-_]?reader|playwright|postgres|pubmed', line, re.I) and n < 12:
            print("HUBCFG:", line.strip()[:160])
            n += 1
    if n == 0:
        print("HUBCFG: no matches in", cfg)
else:
    print("hub config ABSENT:", cfg)

g = H + "/AppData/Roaming/npm/node_modules/@playwright/mcp/package.json"
try:
    print("global-npm @playwright/mcp version:", json.load(open(g, encoding="utf-8")).get("version"))
except Exception as e:
    print("global-npm read err:", str(e)[:60])

for h in ("a5b920f00216d246", "9833c18b2d85bc59"):
    p = f"D:/npm-cache/_npx/{h}/node_modules/@playwright/mcp/package.json"
    try:
        print("D-cache", h, "-> v" + json.load(open(p, encoding="utf-8")).get("version", "?"))
    except Exception:
        print("D-cache", h, "-> MISSING")

base = "D:/npm-cache/_npx"
for pk in ("pubmed-mcp", "@sylphx/pdf-reader-mcp"):
    hit = None
    if os.path.isdir(base):
        for d in os.scandir(base):
            pj = os.path.join(d.path, "node_modules", pk, "package.json")
            if os.path.exists(pj):
                hit = (d.name[:10], json.load(open(pj, encoding="utf-8")).get("version"))
                break
    print("D-cache", pk, "->", hit or "NOT-CACHED")
print("DONE")
