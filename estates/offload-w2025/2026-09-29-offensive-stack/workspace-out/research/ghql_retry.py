import subprocess, json, time

with open("out/research/awesome_links.json", encoding="utf-8") as f:
    links = json.load(f)["flat"]
with open("out/research/awesome_resolved.json", encoding="utf-8") as f:
    results = json.load(f)

def clean(l):
    if l.endswith(".git"): l = l[:-4]
    return l

def gql(chunk):
    parts = []
    for j, repo in enumerate(chunk):
        o, n = repo.split("/", 1)
        parts.append(f'r{j}: repository(owner:"{o}", name:"{n}") {{ nameWithOwner createdAt pushedAt stargazerCount description isArchived primaryLanguage {{ name }} }}')
    q = "{" + " ".join(parts) + "}"
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None, r.stderr[:200]
    d = json.loads(r.stdout)
    if d.get("errors") and not d.get("data"):
        return None, str(d["errors"])[:200]
    return (d.get("data") or {}), None

def resolve(chunk, depth=0):
    if len(chunk) == 1 or depth > 6:
        # single: try once, drop on failure
        data, err = gql(chunk)
        if data:
            for key, node in data.items():
                if node:
                    results[node["nameWithOwner"]] = {
                        "created": node["createdAt"][:10], "pushed": node["pushedAt"][:10],
                        "stars": node["stargazerCount"], "desc": (node.get("description") or "")[:140],
                        "lang": (node.get("primaryLanguage") or {}).get("name", ""), "archived": node.get("isArchived", False)}
        return
    data, err = gql(chunk)
    if data is not None:
        for key, node in data.items():
            if node:
                results[node["nameWithOwner"]] = {
                    "created": node["createdAt"][:10], "pushed": node["pushedAt"][:10],
                    "stars": node["stargazerCount"], "desc": (node.get("description") or "")[:140],
                    "lang": (node.get("primaryLanguage") or {}).get("name", ""), "archived": node.get("isArchived", False)}
        # repos that returned null are dead; find them by absence? GraphQL returns null node -> skipped
        time.sleep(1.2)
    else:
        mid = len(chunk) // 2
        resolve(chunk[:mid], depth + 1)
        resolve(chunk[mid:], depth + 1)

todo = [clean(l) for l in links if "/" in l and not any(x in l for x in ("user-attachments",))]
todo = [l for l in todo if l.count("/") == 1 and not l.endswith((".git",".png",".jpg",".io",".com")) and l.split("/")[0] not in ("apps","orgs","users","topics","features","site","about","settings","marketplace","solutions","enterprises","services")]
todo = sorted(set(todo))
print(f"resolving {len(todo)} links (have {len(results)} already)")
B = 80
for i in range(0, len(todo), B):
    chunk = todo[i:i+B]
    have = set(results)
    if all(c in have for c in chunk):
        continue
    resolve(chunk)
    if (i // B) % 4 == 0:
        print(f"  progress {min(i+B, len(todo))}/{len(todo)} total={len(results)}", flush=True)

with open("out/research/awesome_resolved.json", "w", encoding="utf-8") as f:
    json.dump(results, f)
born26 = {k: v for k, v in results.items() if v.get("created", "0") >= "2026-01-01" and not v.get("archived")}
print(f"\nresolved OK: {len(results)}; created 2026+: {len(born26)}")
for k, v in sorted(born26.items(), key=lambda x: -x[1]["stars"]):
    print(f"{v['stars']:6d} {v['created']} {k} [{v['lang']}] {v['desc'][:100]}")
