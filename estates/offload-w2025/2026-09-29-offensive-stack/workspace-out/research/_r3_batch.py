"""Round-3 onion engine batch: Onionland + DarkSearch(dir) + DarkSearch Engine API.
Usage: python _r3_batch.py q1 "q2 with spaces" ...
Writes raw pages to _r3/ and prints per-engine result counts + first lines."""
import sys, os, json, time, urllib.parse, re, html as H
import requests as rq

PROXIES = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
ENGINES = {
    "onionland": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q=",
    "dsdir": "http://darkzqtmbdeauwq5mzcmgeeuhet42fhfjj4p5wbak3ofx2yqgecoeqyd.onion/search?q=",
    "dsapi": "http://engin5cbd7izh2dlmugwrvvegtltxefgiefs6fo7esurguckwblpjsad.onion/api/search?q=",
}
os.makedirs("_r3", exist_ok=True)

def get(url):
    r = rq.get(url, headers=UA, proxies=PROXIES, timeout=90)
    return r.status_code, r.text

def parse_onionland(page):
    res = []
    for blk in re.findall(r'<div class="result-block">(.*?)</div>\s*</div>\s*</div>', page, re.S):
        tm = re.search(r'<div class="title">\s*<a[^>]*href="(/ads/click[^"]*)"[^>]*>(.*?)</a>', blk, re.S)
        title = re.sub(r"<[^>]+>", "", H.unescape(tm.group(2))).strip() if tm else ""
        lm = re.search(r'<div class="link">.*?(http://[^\s<]+)', blk, re.S)
        url = lm.group(1)[:160] if lm else ""
        res.append((title[:110], url))
    seen, out = set(), []
    for t, u in res:
        if not u or u in seen: continue
        seen.add(u); out.append((t, u))
    return out

def parse_dsdir(page):
    res = []
    for blk in re.findall(r'<div class="single-res[^"]*"[^>]*>(.*?)(?=<div class="single-res|</section>)', page, re.S):
        tm = re.search(r'<div class="title">(.*?)</div>', blk, re.S)
        title = re.sub(r"<[^>]+>", "", H.unescape(tm.group(1))).strip() if tm else ""
        um = re.search(r'<div class="url">(.*?)</div>', blk, re.S)
        url = re.sub(r"<[^>]+>", "", H.unescape(um.group(1))).strip() if um else ""
        if not url:
            om = re.search(r'(http://[a-z2-7]{56}\.onion)', blk)
            url = om.group(1) if om else ""
        res.append((title[:110], url[:160]))
    seen, out = set(), []
    for t, u in res:
        if not u or u in seen: continue
        seen.add(u); out.append((t, u))
    return out

def main():
    summary = {}
    for q in sys.argv[1:]:
        slug = re.sub(r"[^a-z0-9]+", "_", q.lower())[:40]
        row = {}
        for eng, base in ENGINES.items():
            try:
                st, page = get(base + urllib.parse.quote(q))
                open(f"_r3/{eng}_{slug}.html", "w", encoding="utf-8", errors="replace").write(page)
                if eng == "onionland":
                    res = parse_onionland(page)
                elif eng == "dsdir":
                    res = parse_dsdir(page)
                else:  # dsapi JSON
                    try:
                        js = json.loads(page)
                        items = js.get("results") or js.get("data") or []
                        if isinstance(items, dict): items = items.get("results", [])
                        res = [(str(i.get("title", ""))[:100], str(i.get("url") or i.get("link") or "")[:160]) for i in items]
                        if not res: row[eng] = {"status": st, "raw": page[:200]}
                    except Exception:
                        res = []
                        row[eng] = {"status": st, "raw": page[:200]}
                row[eng] = {"status": st, "n": len(res), "results": res[:12]}
            except Exception as e:
                row[eng] = {"error": repr(e)[:160]}
            time.sleep(1.5)
        summary[q] = row
        print(f"== {q} ==")
        for eng, d in row.items():
            if "error" in d: print(f"  {eng}: ERROR {d['error']}")
            elif "raw" in d: print(f"  {eng}: status {d['status']} RAW {d['raw'][:120]}")
            else: print(f"  {eng}: {d['status']} n={d['n']}")
    json.dump(summary, open("_r3/batch_summary.json", "w", encoding="utf-8"), indent=1)

main()
