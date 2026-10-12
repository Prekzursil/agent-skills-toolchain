import json, re

with open("out/research/gh_sweep_results.json", encoding="utf-8") as f:
    data = json.load(f)

seen = {}
for q, items in data.items():
    for it in items:
        fn = it["full_name"]
        e = seen.setdefault(fn, {"stars": it["stargazers_count"], "created": it["created_at"][:10],
                                  "pushed": it["pushed_at"][:10], "desc": (it.get("description") or ""),
                                  "lang": it.get("language") or "", "queries": []})
        e["queries"].append(q.split("+created")[0])

STRONG = re.compile(r"pentest|penetration|red.?team|offensive|exploit|hacking|hack(ing)?\b|ctf|fuzz|adversar|attack|vulnerab|recon|bug.?bount|malware|weaponi|privilege escal|lateral|c2|implant|phishing|prompt inject|jailbreak|hacktricks|metasploit|bloodhound|nuclei|cve|0day|zero.?day|rootkit|keylog|brute.?forc|subdomain|port.?scan|osint", re.I)
AGENTIC = re.compile(r"agent|agentic|mcp|autonomous|llm|\bgpt\b|claude|copilot|gemini|openai|anthropic|ai[- ]|copilot", re.I)

rows = []
for fn, e in seen.items():
    blob = fn + " " + e["desc"]
    s = bool(STRONG.search(blob)); a = bool(AGENTIC.search(blob))
    if s and a:
        rows.append((e["stars"], e["created"], fn, e["desc"][:130], e["lang"], e["pushed"]))

rows.sort(key=lambda r: (-r[0], r[1]))
print(f"STRONG+AGENTIC matches: {len(rows)}\n")
for stars, created, fn, desc, lang, pushed in rows:
    print(f"{stars:5d} {created} {fn} [{lang}] {desc}")
