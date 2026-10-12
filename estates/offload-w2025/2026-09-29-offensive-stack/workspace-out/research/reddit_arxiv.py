import requests, json, time

UA = {"User-Agent": "research-lane-wildcard/1.0 (estate research)"}
out = {}

# Reddit r/netsec + r/OffensiveSecurity + r/netsec + r/cybersecurity new search
for sub in ["netsec", "OffensiveSecurity", "bugbounty"]:
    try:
        r = requests.get(f"https://old.reddit.com/r/{sub}/search.json",
                         params={"q": "agent", "sort": "new", "restrict_sr": 1, "limit": 40, "t": "year"}, headers=UA, timeout=30)
        if r.status_code != 200:
            print(f"[{sub}] HTTP {r.status_code}")
            continue
        posts = r.json().get("data", {}).get("children", [])
        kept = []
        for p in posts:
            d = p["data"]
            kept.append({"t": d.get("title"), "u": d.get("url"), "score": d.get("score"), "created": time.strftime("%Y-%m-%d", time.gmtime(d.get("created_utc", 0))), "selftext": (d.get("selftext") or "")[:150]})
        out[sub] = kept
        print(f"r/{sub}: {len(kept)} posts")
    except Exception as e:
        print(f"r/{sub} ERR: {e}")
    time.sleep(3)

# arXiv sweep
try:
    r = requests.get("http://export.arxiv.org/api/query",
                     params={"search_query": 'all:"agentic" AND all:"penetration testing"', "start": 0, "max_results": 25, "sortBy": "submittedDate", "sortOrder": "descending"}, headers=UA, timeout=40)
    import re
    entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.S)
    print(f"\narXiv entries: {len(entries)}")
    for e in entries[:20]:
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        pub = re.search(r"<published>(.*?)</published>", e)
        link = re.search(r'href="([^"]+abs[^"]+)"', e)
        if pub and pub.group(1)[:4] == "2026":
            print(f"  {pub.group(1)[:10]} | {t.group(1)[:100].strip()} | {link.group(1) if link else ''}")
except Exception as e:
    print(f"arXiv ERR: {e}")

with open("out/research/reddit_arxiv.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("\n-- reddit titles (netsec, newest, containing agent|AI|LLM) --")
for sub, posts in out.items():
    for p in posts:
        blob = (p["t"] + " " + p["selftext"]).lower()
        if any(k in blob for k in ["agent", "llm", "ai ", "mcp", "autonomous"]) and any(k in blob for k in ["pentest", "red team", "redteam", "offensive", "exploit", "hack", "ctf", "recon", "bug bount"]):
            print(f"  r/{sub} {p['created']} s{p['score']:3d} | {p['t'][:100]} | {p['u'][:80]}")
