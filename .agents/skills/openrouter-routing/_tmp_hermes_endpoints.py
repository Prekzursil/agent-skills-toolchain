"""Full supported_parameters + endpoints for Hermes 4 slugs. Read-only, no key printed."""
import json
import urllib.request

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
        return json.load(r)

data = get("https://openrouter.ai/api/v1/models")["data"]
for m in data:
    if m["id"] in ("nousresearch/hermes-4-70b", "nousresearch/hermes-4-405b",
                   "cognitivecomputations/dolphin-mistral-24b-venice-edition"):
        print(m["id"])
        print("  params:", ",".join(m.get("supported_parameters", [])))
        print("  ctx:", m.get("context_length"), "| pricing:", m.get("pricing", {}).get("prompt"),
              "/", m.get("pricing", {}).get("completion"))

for slug in ("nousresearch/hermes-4-70b", "nousresearch/hermes-4-405b"):
    try:
        ep = get(f"https://openrouter.ai/api/v1/models/{slug}/endpoints")["data"]
        provs = [(e.get("provider_name"), e.get("pricing", {}).get("prompt"),
                  e.get("pricing", {}).get("completion"),
                  "tools" in (e.get("supported_parameters") or [])) for e in ep.get("endpoints", [])]
        print(slug, "endpoints:", provs)
    except Exception as e:
        print(slug, "endpoints error:", e)
