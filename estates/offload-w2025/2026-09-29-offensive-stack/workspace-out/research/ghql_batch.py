import subprocess, json, time

with open("out/research/awesome_links.json", encoding="utf-8") as f:
    links = json.load(f)["flat"]
with open("out/research/gh_sweep_results.json", encoding="utf-8") as f:
    sweep = set()
    for q, items in json.load(f).items():
        for it in items:
            sweep.add(it["full_name"])

todo = [l for l in links if l not in sweep]
print(f"links: {len(links)}, already in sweep: {len(links)-len(todo)}, to resolve: {len(todo)}")

results = {}
B = 80
for i in range(0, len(todo), B):
    chunk = todo[i:i+B]
    parts = []
    for j, repo in enumerate(chunk):
        o, n = repo.split("/", 1)
        parts.append(f'r{j}: repository(owner:"{o}", name:"{n}") {{ nameWithOwner createdAt pushedAt stargazerCount description isArchived primaryLanguage {{ name }} }}')
    q = "{" + " ".join(parts) + "}"
    try:
        r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"chunk {i//B} ERR: {r.stderr[:150]}")
            continue
        d = json.loads(r.stdout)
        for key, node in (d.get("data") or {}).items():
            if node:
                results[node["nameWithOwner"]] = {
                    "created": node["createdAt"][:10], "pushed": node["pushedAt"][:10],
                    "stars": node["stargazerCount"], "desc": (node.get("description") or "")[:140],
                    "lang": (node.get("primaryLanguage") or {}).get("name", ""), "archived": node.get("isArchived", False)}
    except Exception as e:
        print(f"chunk {i//B} EXC: {e}")
    if (i // B) % 5 == 0:
        print(f"  resolved {min(i+B, len(todo))}/{len(todo)}", flush=True)
    time.sleep(1.5)

with open("out/research/awesome_resolved.json", "w", encoding="utf-8") as f:
    json.dump(results, f)

born26 = {k: v for k, v in results.items() if v["created"] >= "2026-01-01"}
print(f"\nresolved OK: {len(results)}; created 2026+: {len(born26)}")
for k, v in sorted(born26.items(), key=lambda x: -x[1]["stars"]):
    print(f"{v['stars']:5d} {v['created']} {k} [{v['lang']}] {v['desc'][:105]}")
