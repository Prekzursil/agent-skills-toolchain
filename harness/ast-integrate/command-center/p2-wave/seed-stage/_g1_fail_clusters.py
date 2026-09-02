#!/usr/bin/env python3
"""Cluster G-1 fails from g1-local-full.jsonl by normalized FAILED reason line."""
import json, re, collections, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "ovh-monitor")
rows = [json.loads(l) for l in open(os.path.join(ROOT, "g1-local-full.jsonl"), encoding="utf-8")]
fails = [r for r in rows if not r.get("ok")]

c = collections.Counter()
samples = collections.defaultdict(list)
for r in fails:
    tail = str(r.get("tail") or "")
    key = None
    for line in re.findall(r"FAILED:[^\n]*", tail):
        if line.startswith("FAILED:delivered"):
            continue
        key = line
        break
    if key is None:
        if "TIMEOUT" in tail:
            key = "TIMEOUT"
        elif "ModuleNotFoundError" in tail:
            mm = re.search(r"ModuleNotFoundError: No module named '([^']+)'", tail)
            key = "ModuleNotFoundError: " + (mm.group(1) if mm else "?")
        elif "Traceback" in tail:
            mm = re.search(r"(\w+Error[^\n]*)", tail)
            key = "EXC: " + (mm.group(1)[:80] if mm else "traceback")
        else:
            key = "(no FAILED line) " + tail[-80:].replace("\n", " ")
    key = re.sub(r"[A-Z]{2,4}-\d{4}", "<ID>", key)
    key = re.sub(r"[0-9a-f]{16,}", "<HEX>", key)
    key = re.sub(r"\d+", "N", key)[:140]
    c[key] += 1
    samples[key].append(r["id"])

out = []
for t, n in c.most_common():
    out.append({"n": n, "key": t, "ids": samples[t]})
with open(os.path.join(ROOT, "g1-fail-clusters_2026-08-27.json"), "w", encoding="utf-8") as f:
    json.dump({"n_fails": len(fails), "clusters": out}, f, indent=1)
print("n_fails", len(fails), "n_clusters", len(out))
for t, n in c.most_common(50):
    print(n, "|", samples[t][0], "|", t)
