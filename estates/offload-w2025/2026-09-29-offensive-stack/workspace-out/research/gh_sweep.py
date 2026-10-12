import subprocess, json, time, sys

QUERIES = [
    # topic sweeps
    "topic:offensive-security+created:>2026-01-01",
    "topic:red-team+created:>2026-01-01",
    "topic:red-teaming+created:>2026-01-01",
    # agentic pentest concepts
    "agentic+pentest+created:>2026-01-01",
    "autonomous+pentest+created:>2026-01-01",
    "agentic+pentration+created:>2026-01-01",
    "pentest+agent+created:>2026-01-01",
    "red+team+agent+created:>2026-01-01",
    "offensive+security+agent+created:>2026-01-01",
    "llm+hacking+agent+created:>2026-01-01",
    "mcp+pentest+created:>2026-01-01",
    "mcp+red+team+created:>2026-01-01",
    "exploit+generation+llm+created:>2026-01-01",
    "llm+fuzzing+created:>2026-01-01",
    "attack+path+agent+created:>2026-01-01",
    "agentic+ctf+created:>2026-01-01",
    "adversary+emulation+llm+created:>2026-01-01",
    "autonomous+hacking+created:>2026-01-01",
    "ai+hacking+agent+created:>2026-04-01",
    "pentest+mcp+server+created:>2026-04-01",
]

out = {}
for q in QUERIES:
    page = 1
    items_all = []
    while page <= 3:  # up to 300 per query
        try:
            r = subprocess.run(
                ["gh", "api", f"search/repositories?q={q}&sort=updated&order=desc&per_page=100&page={page}"],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                sys.stderr.write(f"ERR {q} p{page}: {r.stderr[:200]}\n")
                break
            data = json.loads(r.stdout)
            items = data.get("items", [])
            items_all += items
            if len(items) < 100 or len(items_all) >= data.get("total_count", 0):
                break
            page += 1
            time.sleep(2)
        except Exception as e:
            sys.stderr.write(f"EXC {q}: {e}\n")
            break
    out[q] = items_all
    total = len(items_all)
    print(f"[{total:4d}] {q}", flush=True)
    time.sleep(2.5)

with open("out/research/gh_sweep_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f)

# dedup summary
seen = {}
for q, items in out.items():
    for it in items:
        fn = it["full_name"]
        if fn not in seen:
            seen[fn] = {"q": q, "stars": it["stargazers_count"], "created": it["created_at"],
                        "pushed": it["pushed_at"], "desc": (it.get("description") or "")[:150],
                        "lang": it.get("language"), "url": it["html_url"]}
print(f"\nTOTAL UNIQUE: {len(seen)}")
for fn, d in sorted(seen.items(), key=lambda x: -x[1]["stars"]):
    print(f"{d['stars']:5d} | {d['created'][:10]} | {fn} | {d['desc'][:110]}")
