#!/usr/bin/env python3
"""Helper: firecrawl/exa search. Usage: python _search.py fc|exa "query" [limit]"""
import sys, os, json, urllib.request

def post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())

mode, q = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
if mode == "fc":
    d = post("https://api.firecrawl.dev/v1/search",
             {"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
             {"query": q, "limit": limit})
    for it in d.get("data", d.get("web", [])):
        print(f"- {it.get('title','')[:110]} | {it.get('url','')} | {(it.get('description') or '')[:160]}")
elif mode == "exa":
    d = post("https://api.exa.ai/search",
             {"x-api-key": os.environ["EXA_API_KEY"]},
             {"query": q, "numResults": limit, "contents": {"text": {"maxCharacters": 400}}})
    for it in d.get("results", []):
        txt = (it.get("text") or "").replace("\n", " ")[:200]
        print(f"- {it.get('title','')[:110]} | {it.get('url','')} | {txt}")
