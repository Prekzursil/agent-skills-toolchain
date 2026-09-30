"""Onionland-only battery. Usage: python _r3_onionland.py q1 q2 ..."""
import sys, json, time, urllib.parse, re, html as H
import requests as rq

PROXIES = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE = "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q="

def parse(page):
    res = []
    for blk in re.findall(r'<div class="result-block">(.*?)</div>\s*</div>\s*</div>', page, re.S):
        tm = re.search(r'<div class="title">\s*<a[^>]*(?:href="[^"]*")[^>]*>(.*?)</a>', blk, re.S)
        title = re.sub(r"<[^>]+>", "", H.unescape(tm.group(1))).strip() if tm else ""
        lm = re.search(r'<div class="link">.*?(http://[^\s<]+)', blk, re.S)
        url = lm.group(1)[:160] if lm else ""
        dm = re.search(r'<div class="desc">(.*?)</div>', blk, re.S)
        desc = re.sub(r"<[^>]+>", "", H.unescape(dm.group(1))).strip()[:180] if dm else ""
        res.append({"title": title[:110], "url": url, "desc": desc})
    out, seen = [], set()
    for r in res:
        if not r["url"] or r["url"] in seen or "/ads/click" in r["url"]: continue
        seen.add(r["url"]); out.append(r)
    return out

summary = {}
for q in sys.argv[1:]:
    slug = re.sub(r"[^a-z0-9]+", "_", q.lower())[:40]
    try:
        r = rq.get(BASE + urllib.parse.quote(q), headers=UA, proxies=PROXIES, timeout=90)
        open(f"_r3/onionland_{slug}.html", "w", encoding="utf-8", errors="replace").write(r.text)
        res = parse(r.text)
        summary[q] = {"status": r.status_code, "n": len(res), "results": res[:15]}
        print(f"== {q}: {r.status_code} n={len(res)}")
    except Exception as e:
        summary[q] = {"error": repr(e)[:160]}
        print(f"== {q}: ERROR {e!r}")
    time.sleep(2)
json.dump(summary, open("_r3/onionland_battery.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
