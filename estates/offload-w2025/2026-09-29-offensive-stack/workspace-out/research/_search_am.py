#!/usr/bin/env python3
"""agent-memory lane search helper.
Usage: python _search_am.py exa|fc|ddg "query" [limit]
"""
import json
import os
import sys
import urllib.request


def post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


mode, q = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

try:
    if mode == "fc":
        d = post("https://api.firecrawl.dev/v1/search",
                 {"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
                 {"query": q, "limit": limit})
        for it in d.get("data", d.get("web", [])):
            print(f"- {it.get('title','')[:110]} | {it.get('url','')} | {(it.get('description') or it.get('markdown') or '')[:180]}")
    elif mode == "exa":
        d = post("https://api.exa.ai/search",
                 {"x-api-key": os.environ["EXA_API_KEY"]},
                 {"query": q, "numResults": limit, "contents": {"text": {"maxCharacters": 400}}})
        for it in d.get("results", []):
            txt = (it.get("text") or "").replace("\n", " ")[:220]
            print(f"- {it.get('title','')[:110]} | {it.get('url','')} | {txt}")
    elif mode == "ddg":
        from ddgs import DDGS
        with DDGS() as d:
            for r in d.text(q, max_results=limit):
                print(f"- {(r.get('title') or '')[:110]} | {r.get('href') or r.get('url') or ''} | {(r.get('body') or '')[:180]}")
    else:
        print(f"unknown mode {mode}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
