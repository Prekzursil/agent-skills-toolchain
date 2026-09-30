import json, re

with open("out/research/gh_sweep_results.json", encoding="utf-8") as f:
    data = json.load(f)

seen = {}
for q, items in data.items():
    for it in items:
        fn = it["full_name"]
        if fn not in seen:
            seen[fn] = {"stars": it["stargazers_count"], "created": it["created_at"][:10],
                        "pushed": it["pushed_at"][:10], "desc": (it.get("description") or ""),
                        "lang": it.get("language") or ""}

CJK = re.compile(r"渗透|红队|漏洞|攻击|靶场|入侵|破解|逆向|提权|挖洞|安全测试|포침투|ハッキング")
AGENTIC = re.compile(r"agent|agentic|mcp|autonomous|llm|\bgpt\b|claude|codex|大语言模型|大模型|智能体", re.I)

rows = []
for fn, e in seen.items():
    blob = fn + " " + e["desc"]
    if CJK.search(blob) and AGENTIC.search(blob):
        rows.append((e["stars"], e["created"], fn, e["desc"][:120], e["lang"]))
rows.sort(key=lambda r: -r[0])
print(f"CJK+AGENTIC matches: {len(rows)}")
for stars, created, fn, desc, lang in rows[:40]:
    print(f"{stars:5d} {created} {fn} [{lang}] {desc}")
