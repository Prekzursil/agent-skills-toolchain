"""Ahmia.fi scripted search: extracts per-page anti-bot token, then queries /search/.
Usage: python ahmia_search.py "query" [outfile]
Prints title<TAB>onion-url lines from the result page."""
import re, sys, urllib.request, urllib.parse, html, time

BASE = "https://ahmia.fi"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def search(q):
    home = get(BASE + "/")
    m = re.search(r'name="([0-9a-f]{4,10})"\s+value="([0-9a-f]{4,10})"', home)
    if not m:
        print("NO_TOKEN_FOUND", file=sys.stderr)
        return ""
    name, val = m.group(1), m.group(2)
    url = BASE + "/search/?" + urllib.parse.urlencode({"q": q, name: val})
    return get(url)

def parse(page):
    out = []
    # results are <li class="result"><h4><a href="...onion...">title</a>...
    for m in re.finditer(r'<h4[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        url, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        out.append((html.unescape(title).strip(), html.unescape(url)))
    if not out:
        for m in re.finditer(r'href="(https?://[a-z2-7]{56}\.onion[^"]*)"', page):
            out.append(("", m.group(1)))
    return out

if __name__ == "__main__":
    q = sys.argv[1]
    page = search(q)
    open(sys.argv[2], "w", encoding="utf-8").write(page) if len(sys.argv) > 2 else None
    res = parse(page)
    print(f"RESULTS={len(res)}")
    seen = set()
    for t, u in res:
        if u in seen: continue
        seen.add(u)
        print(f"{t}\t{u}")
    if not res:
        snip = re.sub(r"\s+", " ", page)[:300]
        print("RAW_SNIPPET:", snip)
