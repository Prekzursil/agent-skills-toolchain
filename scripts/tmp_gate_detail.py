#!/usr/bin/env python
"""Fetch per-gate failure detail for a SHA's check-runs + annotations (read-only)."""
import json
import os
import sys
import urllib.request

REPO = "Prekzursil/agent-skills-toolchain"
TOKEN = os.environ["GITHUB_TOKEN"]
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}


def get(url):
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


sha = sys.argv[1]
cr = get(f"https://api.github.com/repos/{REPO}/commits/{sha}/check-runs")
print(f"total runs: {cr['total_count']}")
for run in cr["check_runs"]:
    if run["conclusion"] == "failure":
        print(f"\n### {run['name']}")
        summary = (run.get("output") or {}).get("summary") or "(no summary)"
        print("  summary:", summary[:300])
        try:
            ann = get(f"https://api.github.com/repos/{REPO}/check-runs/{run['id']}/annotations")
            for a in ann[:6]:
                msg = (a.get("message") or "")[:220].replace("\n", " | ")
                print(f"  - {a.get('path')}:{a.get('start_line')} [{a.get('title')}] {msg}")
            if len(ann) > 6:
                print(f"  ... +{len(ann)-6} more annotations")
        except Exception as e:
            print("  annotations fetch failed:", e)
