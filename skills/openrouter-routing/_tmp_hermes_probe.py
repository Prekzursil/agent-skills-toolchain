"""Probe live OpenRouter /models for Hermes/Nous slugs. Read-only, no key printed."""
import json
import os
import urllib.request

req = urllib.request.Request("https://openrouter.ai/api/v1/models")
key = os.environ.get("OPENROUTER_API_KEY")
if key:
    req.add_header("Authorization", "Bearer " + key)
with urllib.request.urlopen(req, timeout=60) as r:
    data = json.load(r)["data"]

print("TOTAL_MODELS=", len(data))
hits = [m for m in data if "hermes" in m["id"].lower() or "nous" in m["id"].lower()]
print("HERMES/NOUS HITS:", len(hits))
for m in sorted(hits, key=lambda x: x.get("created", 0), reverse=True):
    p = m.get("pricing", {})
    print(f"{m['id']} | prompt={p.get('prompt')} completion={p.get('completion')} "
          f"| ctx={m.get('context_length')} | created={m.get('created')} "
          f"| params={','.join(m.get('supported_parameters', [])[:8])}")

# Also check dolphin / abliterated / uncensored slugs for Q3 hosted comparison
extra = [m for m in data if any(k in m["id"].lower() for k in ("dolphin", "abliterat", "uncensor", "venice"))]
print("\nDOLPHIN/UNCENSORED HITS:", len(extra))
for m in extra:
    p = m.get("pricing", {})
    print(f"{m['id']} | prompt={p.get('prompt')} completion={p.get('completion')} | ctx={m.get('context_length')}")
