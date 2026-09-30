import requests, json, os

FC = os.environ.get("FIRECRAWL_API_KEY")
QUERIES = [
    "new agentic offensive security tools 2026",
    "autonomous pentest agent open source 2026 github",
    "Agent OPFOR open source AI red teaming",
    "nightcrawler AI pentesting agent garagehq",
]
for q in QUERIES:
    try:
        r = requests.post("https://api.firecrawl.dev/v1/search", json={"query": q, "limit": 8},
                          headers={"Authorization": f"Bearer {FC}", "Content-Type": "application/json"}, timeout=60)
        print(f"--- {q} | HTTP {r.status_code}")
        d = r.json()
        data = d.get("data")
        if isinstance(data, list):
            for x in data[:8]:
                print(f"  {x.get('title','')[:70]} | {x.get('url','')[:90]}")
        else:
            print("  RAW:", json.dumps(d)[:400])
    except Exception as e:
        print(f"ERR {q}: {e}")

# one mandated scrape of a JS-heavy page: agentopfor.ai
try:
    r = requests.post("https://api.firecrawl.dev/v1/scrape", json={"url": "https://agentopfor.ai/", "formats": ["markdown"]},
                      headers={"Authorization": f"Bearer {FC}", "Content-Type": "application/json"}, timeout=90)
    d = r.json()
    md = ((d.get("data") or {}).get("markdown") or "")[:1800]
    print("\n=== SCRAPE agentopfor.ai ===")
    print(md)
except Exception as e:
    print(f"SCRAPE ERR: {e}")
