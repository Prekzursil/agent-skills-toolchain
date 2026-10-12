#!/usr/bin/env python3
"""Search runner for browser-offense lane. Modes: fc (firecrawl search), exa, scrape (firecrawl scrape), hn (algolia)."""
import json, os, re, sys, time
import urllib.request, urllib.error, urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_raw")
os.makedirs(RAW, exist_ok=True)

def slug(s):
    return re.sub(r"[^a-zA-Z0-9]+", "_", s)[:80]

def post(url, headers, body, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:500]
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(3 * (attempt + 1)); continue
            return {"_error": f"HTTP {e.code}", "_detail": detail}
        except Exception as e:
            if attempt < 2:
                time.sleep(3); continue
            return {"_error": str(e)}

def save(name, obj):
    p = os.path.join(RAW, name + ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return p

def fc_search(q, limit=10):
    key = os.environ.get("FIRECRAWL_API_KEY")
    r = post("https://api.firecrawl.dev/v1/search", {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, {"query": q, "limit": limit})
    save("fc_" + slug(q), r)
    out = []
    data = r.get("data") if isinstance(r, dict) else None
    if data:
        for it in data:
            out.append(f"- {str(it.get('title',''))[:90]} | {it.get('url','')} | {str(it.get('description',''))[:140]}")
    else:
        out.append(json.dumps(r)[:400])
    print("## firecrawl:", q)
    print("\n".join(out))

def exa_search(q, n=10):
    key = os.environ.get("EXA_API_KEY")
    r = post("https://api.exa.ai/search", {"x-api-key": key, "Content-Type": "application/json"}, {"query": q, "numResults": n})
    save("exa_" + slug(q), r)
    out = []
    res = r.get("results") if isinstance(r, dict) else None
    if res:
        for it in res:
            out.append(f"- {str(it.get('title',''))[:90]} | {it.get('url','')} | {str(it.get('text') or '')[:140]}")
    else:
        out.append(json.dumps(r)[:400])
    print("## exa:", q)
    print("\n".join(out))

def fc_scrape(url):
    key = os.environ.get("FIRECRAWL_API_KEY")
    r = post("https://api.firecrawl.dev/v1/scrape", {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, {"url": url, "formats": ["markdown"], "onlyMainContent": False})
    save("scrape_" + slug(url), r)
    if isinstance(r, dict) and r.get("data"):
        md = r["data"].get("markdown") or ""
        print("## scrape:", url, "| chars:", len(md))
        print(md[:6000])
    else:
        print(json.dumps(r)[:500])

def hn(q):
    url = "https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote(q) + "&tags=story&hitsPerPage=15"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.loads(r.read().decode())
    except Exception as e:
        print("HN error:", e); return
    save("hn_" + slug(q), d)
    print("## hn:", q)
    for h in d.get("hits", []):
        print(f"- {str(h.get('title',''))[:100]} | {h.get('url') or ''} | pts={h.get('points')} comments={h.get('num_comments')} | id={h.get('objectID')}")

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "fc": fc_search(sys.argv[2])
    elif mode == "exa": exa_search(sys.argv[2])
    elif mode == "scrape": fc_scrape(sys.argv[2])
    elif mode == "hn": hn(sys.argv[2])
    else: print("unknown mode")
