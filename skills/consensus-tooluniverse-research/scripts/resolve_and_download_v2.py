"""v2 keyed recovery pass — re-fetch the OA-but-bot-walled (and entitled paywalled) papers via
LEGITIMATE keyed sources. Reads keys from ~/.tooluniverse/.env (or env). Sci-Hub/LibGen NOT used.

Tiers per paper (first %PDF wins):
  1. CORE        — api.core.ac.uk/v3 (Bearer CORE_API_KEY): hosts downloadable OA copies publishers bot-wall
  2. Elsevier    — api.elsevier.com/content/article/doi (X-ELS-APIKey): full text the key is ENTITLED to (OA + subscribed)
  3. Zenodo      — zenodo.org/api/records (access_token): self-archived / preprint OA copies
  4. DOAJ        — doaj.org/api OA-journal fulltext links
  5. Unpaywall   — retry the recorded OA location (transient bot-wall)

Targets (from _bibliography/_progress.json):
  - downloaded == "blocked"  (confirmed OA, just bot-walled)  — all tiers
  - paywalled (doi & not is_oa) — Elsevier tier only (entitled access via the publisher's own API)
Resumable + non-destructive: only upgrades "blocked"/paywalled rows; never bypasses a paywall.
"""
from __future__ import annotations
import argparse, csv, json, os, re, time
from pathlib import Path
import requests

_AP = argparse.ArgumentParser(description="v2 keyed recovery pass (legitimate keyed OA sources)")
_AP.add_argument("--ws", default=os.environ.get("CONSENSUS_WS") or ".",
                 help="Consensus workspace dir (default: $CONSENSUS_WS, else current dir)")
WS = Path(_AP.parse_known_args()[0].ws).resolve()
ENV_FILE = Path.home() / ".tooluniverse" / ".env"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Accept": "application/pdf,*/*"}

def load_env(p: Path):
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())
load_env(ENV_FILE)

SEARCHES_DIR = WS / "searches"
BIB = WS / "_bibliography"
LIB = WS / "_library"; LIB.mkdir(exist_ok=True)
PROGRESS_F = BIB / "_progress.json"

def is_pdf(c): return c[:5] == b"%PDF-"
def safe(doi): return re.sub(r"[^A-Za-z0-9._-]", "_", doi)

CORE_KEY = os.environ.get("CORE_API_KEY")
ELS_KEY = os.environ.get("ELSEVIER_API_KEY")
ZEN_TOK = os.environ.get("ZENODO_TOKEN")

def core_pdf(doi):
    if not CORE_KEY: return None, None
    try:
        r = requests.get("https://api.core.ac.uk/v3/search/works",
                         params={"q": f'doi:"{doi}"', "limit": 3},
                         headers={"Authorization": f"Bearer {CORE_KEY}"}, timeout=45)
        if r.status_code != 200: return None, None
        for w in r.json().get("results", []):
            url = w.get("downloadUrl")
            if url:
                p = requests.get(url, headers=UA, timeout=90)
                if is_pdf(p.content) and len(p.content) > 2000:
                    return p.content, "core"
    except Exception:
        pass
    return None, None

def elsevier_pdf(doi):
    if not ELS_KEY: return None, None
    try:
        r = requests.get(f"https://api.elsevier.com/content/article/doi/{doi}",
                         headers={"X-ELS-APIKey": ELS_KEY, "Accept": "application/pdf"}, timeout=60)
        if r.status_code == 200 and is_pdf(r.content) and len(r.content) > 2000:
            return r.content, "elsevier"
    except Exception:
        pass
    return None, None

def zenodo_pdf(doi):
    try:
        params = {"q": f'doi:"{doi}"', "size": 3}
        if ZEN_TOK: params["access_token"] = ZEN_TOK
        r = requests.get("https://zenodo.org/api/records", params=params, timeout=45)
        if r.status_code != 200: return None, None
        for h in r.json().get("hits", {}).get("hits", []):
            for f in h.get("files", []):
                if (f.get("key", "").lower().endswith(".pdf")):
                    url = f.get("links", {}).get("self")
                    if url:
                        if ZEN_TOK: url += ("&" if "?" in url else "?") + f"access_token={ZEN_TOK}"
                        p = requests.get(url, headers=UA, timeout=90)
                        if is_pdf(p.content):
                            return p.content, "zenodo"
    except Exception:
        pass
    return None, None

def doaj_pdf(doi):
    try:
        r = requests.get(f"https://doaj.org/api/articles/search/doi:{doi}", timeout=45)
        if r.status_code != 200: return None, None
        for res in r.json().get("results", []):
            for link in res.get("bibjson", {}).get("link", []):
                u = link.get("url")
                if link.get("type") == "fulltext" and u:
                    p = requests.get(u, headers={**UA, "Referer": u}, timeout=60)
                    if is_pdf(p.content):
                        return p.content, "doaj"
    except Exception:
        pass
    return None, None

def unpaywall_retry(oa_url):
    if not oa_url: return None, None
    try:
        s = requests.Session()
        p = s.get(oa_url, headers={**UA, "Referer": oa_url}, timeout=60)
        if is_pdf(p.content) and len(p.content) > 2000:
            return p.content, "unpaywall-retry"
    except Exception:
        pass
    return None, None

# hash -> searches (from papers.json) for distribution
master_searches: dict[str, list] = {}
folders = sorted(p.name for p in SEARCHES_DIR.iterdir() if p.is_dir())
for folder in folders:
    pj = SEARCHES_DIR / folder / "papers.json"
    if pj.exists():
        for p in json.loads(pj.read_text(encoding="utf-8")):
            master_searches.setdefault(p["hash_paper_id"], [])
            if folder not in master_searches[p["hash_paper_id"]]:
                master_searches[p["hash_paper_id"]].append(folder)

progress = json.loads(PROGRESS_F.read_text(encoding="utf-8"))
targets = []
for hid, r in progress.items():
    if r.get("downloaded") == "blocked":
        targets.append((hid, r, "blocked"))
    elif r.get("doi") and r.get("is_oa") is False:
        targets.append((hid, r, "paywalled"))
print(f"[v2] keys: CORE={bool(CORE_KEY)} ELS={bool(ELS_KEY)} ZEN={bool(ZEN_TOK)} | targets: "
      f"{sum(1 for _,_,k in targets if k=='blocked')} blocked + {sum(1 for _,_,k in targets if k=='paywalled')} paywalled")

recovered = 0
for i, (hid, r, kind) in enumerate(targets, 1):
    doi = r.get("doi")
    if not doi:
        continue
    blob = src = None
    if kind == "blocked":
        for fn in (core_pdf, elsevier_pdf, zenodo_pdf, doaj_pdf):
            blob, src = fn(doi)
            if blob: break
        if not blob:
            blob, src = unpaywall_retry(r.get("oa_url"))
    else:  # paywalled: only the publisher's own entitled API
        blob, src = elsevier_pdf(doi)
    if blob:
        fname = f"{safe(doi)}.pdf"
        (LIB / fname).write_bytes(blob)
        r["downloaded"], r["file"], r["recovered_via"] = "pdf", fname, src
        recovered += 1
        for folder in master_searches.get(hid, []):
            dest = SEARCHES_DIR / folder / "papers" / fname
            if not dest.exists():
                dest.write_bytes(blob)
        PROGRESS_F.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.2)
    if i % 25 == 0:
        print(f"  [{i}/{len(targets)}] recovered so far: {recovered}", flush=True)

# rewrite bibliography + funnel
allrows = list(progress.values())
(BIB/"master_bibliography.json").write_text(json.dumps(allrows, indent=2, ensure_ascii=False), encoding="utf-8")
with (BIB/"master_bibliography.csv").open("w", newline="", encoding="utf-8") as f:
    cols = ["title","first_author","year","doi","doi_src","match_score","is_oa","oa_status","downloaded","file","recovered_via","oa_url"]
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for r in allrows: w.writerow({k: r.get(k) for k in cols})
report = {
    "unique_papers": len(allrows),
    "downloaded_pdf": sum(1 for r in allrows if r.get("downloaded") == "pdf"),
    "v2_recovered_this_run": recovered,
    "still_blocked": sum(1 for r in allrows if r.get("downloaded") == "blocked"),
    "no_oa_paywalled": sum(1 for r in allrows if r.get("doi") and r.get("is_oa") is False and r.get("downloaded") != "pdf"),
}
(BIB/"_funnel_report_v2.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\n=== v2 FUNNEL ===")
print(json.dumps(report, indent=2))
print(f"DONE — recovered {recovered} more PDFs via legitimate keyed sources")
