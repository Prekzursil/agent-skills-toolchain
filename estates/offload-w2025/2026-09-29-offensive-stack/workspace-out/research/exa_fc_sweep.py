import requests, json, os, time

EXA = os.environ.get("EXA_API_KEY"); FC = os.environ.get("FIRECRAWL_API_KEY")
EXA_Q = [
    "brand new agentic offensive security tool released 2026 github",
    "autonomous penetration testing agent framework 2026 open source",
    "MCP server red team operations tool 2026",
    "AI agent hacking framework launched 2026",
    "new AI pentesting tool nobody talks about 2026",
    "Claude Code offensive security skills 2026",
    "agentic CTF solver tool 2026",
    "红队 AI 智能体 渗透 工具 2026 开源",
    "自動ペンテスト AIエージェント 2026 ツール",
    "post-trained model that pen tests Argus Red",
]
out = {}
for q in EXA_Q:
    try:
        r = requests.post("https://api.exa.ai/search", json={"query": q, "numResults": 10},
                          headers={"x-api-key": EXA, "Content-Type": "application/json"}, timeout=40)
        d = r.json()
        rs = d.get("results", [])
        out[q] = [{"t": x.get("title"), "u": x.get("url"), "s": (x.get("text") or "")[:220]} for x in rs]
        print(f"EXA [{len(rs):2d}] {q}")
    except Exception as e:
        print(f"EXA ERR {q}: {e}")
    time.sleep(1)

FC_Q = [
    "new agentic offensive security tools september 2026",
    "autonomous pentest agent open source 2026",
    "AI red teaming framework new release 2026",
    "agentic security tool launched 2026 github trending",
    "Nightcrawler AI pentesting agent smartphone",
]
for q in FC_Q:
    try:
        r = requests.post("https://api.firecrawl.dev/v1/search", json={"query": q, "limit": 10},
                          headers={"Authorization": f"Bearer {FC}", "Content-Type": "application/json"}, timeout=60)
        d = r.json()
        rs = (d.get("data") or {}).get("results" if isinstance(d.get("data"), dict) else 0, d.get("data") or [])
        out["FC: " + q] = [{"t": x.get("title"), "u": x.get("url"), "s": (x.get("description") or "")[:200]} for x in rs]
        print(f"FC  [{len(rs):2d}] {q}")
    except Exception as e:
        print(f"FC ERR {q}: {e}")
    time.sleep(1)

with open("out/research/exa_fc_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)

# print URLs not on github.com already-known hosts
seen_u = set()
for q, rs in out.items():
    for x in rs:
        u = x["u"]
        if u and u not in seen_u:
            seen_u.add(u)
            print(f"{q[:28]:28s} | {x['t'][:80] if x['t'] else ''} | {u[:100]}")
