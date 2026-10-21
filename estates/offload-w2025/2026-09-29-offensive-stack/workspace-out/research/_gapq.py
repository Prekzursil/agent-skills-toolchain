"""Gap-chase query helper: exa + firecrawl search wrappers (real keys from registry)."""
import json, os, subprocess, sys, urllib.request

def _key_user(name):
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::GetEnvironmentVariable('{name}','User')"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        return out if out else None
    except Exception:
        return None

def exa(q, n=8):
    key = os.environ.get("EXA_API_KEY", "")
    body = json.dumps({"query": q, "numResults": n,
                       "contents": {"text": {"maxCharacters": 400}}}).encode()
    req = urllib.request.Request("https://api.exa.ai/search", data=body,
        headers={"x-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read())
        out = []
        for res in d.get("results", []):
            out.append({"title": res.get("title"), "url": res.get("url"),
                        "date": res.get("publishedDate"), "snip": (res.get("text") or "")[:300]})
        return out
    except Exception as e:
        return [{"error": str(e)}]

def fc(q, n=6):
    key = _key_user("FIRECRAWL_API_KEY") or os.environ.get("FIRECRAWL_API_KEY", "")
    body = json.dumps({"query": q, "limit": n}).encode()
    req = urllib.request.Request("https://api.firecrawl.dev/v1/search", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        out = []
        data = d.get("data") or []
        if isinstance(data, dict):
            data = data.get("web", [])
        for res in data:
            if not isinstance(res, dict):
                continue
            out.append({"title": res.get("title"), "url": res.get("url"),
                        "snip": (res.get("description") or res.get("markdown") or "")[:300]})
        return out
    except Exception as e:
        return [{"error": str(e)}]

def gh(q, n=10, sort="stars"):
    s = subprocess.run(["gh", "api", "-X", "GET", "search/repositories",
                        "-f", f"q={q}", "-f", f"per_page={n}", "-f", f"sort={sort}"],
                       capture_output=True, text=True, timeout=60)
    if s.returncode != 0:
        return [{"error": s.stderr.strip()[:300]}]
    d = json.loads(s.stdout)
    out = []
    for it in d.get("items", []):
        out.append({"repo": it["full_name"], "stars": it["stargazers_count"],
                    "lang": it.get("language"), "pushed": it["pushed_at"][:10],
                    "desc": (it.get("description") or "")[:200], "archived": it.get("archived")})
    return out

if __name__ == "__main__":
    backend, q = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    fn = {"exa": exa, "fc": fc, "gh": gh}[backend]
    for item in fn(q, n):
        print(json.dumps(item, ensure_ascii=False))
