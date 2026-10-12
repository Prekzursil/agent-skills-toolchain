import requests, json, time

BASE = "https://hn.algolia.com/api/v1/search_by_date"
QUERIES = ["agentic pentest", "autonomous pentest", "pentest agent", "red team agent", "offensive security agent",
           "AI pentesting", "LLM red team", "hacking agent", "MCP security", "agentic security",
           "autonomous hacking", "pentest AI open source"]
seen = {}
for q in QUERIES:
    try:
        r = requests.get(BASE, params={"query": q, "tags": "story", "hitsPerPage": 30, "numericFilters": "created_at_i>1767225600"}, timeout=30)
        d = r.json()
        for h in d.get("hits", []):
            url = h.get("url") or ""
            seen[h["objectID"]] = {"title": h.get("title"), "url": url, "pts": h.get("points") or 0,
                                    "created": (h.get("created_at") or "")[:10], "q": q,
                                    "comments": h.get("num_comments") or 0}
        print(f"[{len(d.get('hits', [])):2d}] {q}")
    except Exception as e:
        print(f"ERR {q}: {e}")
    time.sleep(1)

rows = sorted(seen.values(), key=lambda x: -x["pts"])
print(f"\nHN UNIQUE STORIES (2026): {len(rows)}")
for r in rows[:45]:
    print(f"{r['pts']:4d}pt {r['created']} c{r['comments']:3d} | {r['title'][:95]} | {r['url'][:80]}")
with open("out/research/hn_stories.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1)
