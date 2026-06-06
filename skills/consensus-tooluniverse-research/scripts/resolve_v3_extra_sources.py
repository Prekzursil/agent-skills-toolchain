"""v3 incremental recovery — add Semantic Scholar (keyless), Springer-OA, and NCBI-keyed PMC tiers
on top of v2. Targets entries that still have no PDF: downloaded=="blocked" (OA but bot-walled) and
paywalled (doi & is_oa False). LEGITIMATE sources only; %PDF-verified; OA-only (+ Springer OA / SS openAccessPdf).

Note: the provided SEMANTIC_SCHOLAR_API_KEY returns 403 (invalid/inactive) — SS is used KEYLESS (200 OK, lower rate).
"""
from __future__ import annotations
import argparse, csv, json, os, re, time
from pathlib import Path
import requests

_AP = argparse.ArgumentParser(description="v3 incremental recovery (Semantic Scholar keyless + Springer-OA + NCBI PMC)")
_AP.add_argument("--ws", default=os.environ.get("CONSENSUS_WS") or ".",
                 help="Consensus workspace dir (default: $CONSENSUS_WS, else current dir)")
WS = Path(_AP.parse_known_args()[0].ws).resolve()

_ENV_FILE = Path.home() / ".tooluniverse" / ".env"
if _ENV_FILE.exists():  # absent .env is skipped gracefully (no crash) — keys then come from the real environment
    for _ln in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _ln = _ln.strip()
        if _ln and not _ln.startswith("#") and "=" in _ln:
            _k, _v = _ln.split("=", 1)
            if _v.strip():
                os.environ.setdefault(_k.strip(), _v.strip())

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Accept": "application/pdf,*/*"}
SEARCHES_DIR = WS / "searches"; BIB = WS / "_bibliography"; LIB = WS / "_library"; LIB.mkdir(exist_ok=True)
PROGRESS_F = BIB / "_progress.json"
SPRINGER = os.environ.get("SPRINGER_API_KEY")
NCBI = os.environ.get("NCBI_API_KEY")

def is_pdf(c): return c[:5] == b"%PDF-"
def safe(doi): return re.sub(r"[^A-Za-z0-9._-]", "_", doi)

def ss_keyless(doi):
    # SS aggregates OA across hosts; keyless returns 200 (the provided key 403s). Retry once on 429.
    for attempt in (1, 2):
        try:
            r = requests.get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                             params={"fields": "openAccessPdf"}, timeout=30)
            if r.status_code == 429:
                time.sleep(3); continue
            if r.status_code == 200:
                oa = (r.json() or {}).get("openAccessPdf") or {}
                url = oa.get("url")
                if url:
                    p = requests.get(url, headers={**UA, "Referer": url}, timeout=90)
                    if is_pdf(p.content) and len(p.content) > 2000:
                        return p.content, "semanticscholar"
            return None, None
        except Exception:
            return None, None
    return None, None

def springer_pdf(doi):
    if not SPRINGER: return None, None
    try:
        sp = requests.get("https://api.springernature.com/openaccess/json",
                          params={"q": f"doi:{doi}", "api_key": SPRINGER}, timeout=30)
        if sp.status_code != 200 or not sp.json().get("records"):
            return None, None  # not an OA Springer/Nature article
        p = requests.get(f"https://link.springer.com/content/pdf/{doi}.pdf",
                         headers={**UA, "Referer": f"https://link.springer.com/article/{doi}"}, timeout=90)
        if is_pdf(p.content) and len(p.content) > 2000:
            return p.content, "springer-oa"
    except Exception:
        pass
    return None, None

def pmc_ncbi(doi):
    try:
        q = f'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22{doi}%22&format=json&resultType=lite'
        res = (requests.get(q, headers=UA, timeout=30).json().get("resultList") or {}).get("result") or []
        pmcid = res[0].get("pmcid") if res else None
        if not pmcid:
            return None, None
        oaurl = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
        if NCBI: oaurl += f"&api_key={NCBI}"
        oa = requests.get(oaurl, headers=UA, timeout=30).text
        m = re.search(r'href="(ftp://[^"]+\.pdf[^"]*)"', oa) or re.search(r'href="(https?://[^"]+\.pdf[^"]*)"', oa)
        if m:
            p = requests.get(m.group(1).replace("ftp://", "https://"), headers=UA, timeout=90)
            if is_pdf(p.content):
                return p.content, "pmc-oa"
    except Exception:
        pass
    return None, None

# hash -> searches for distribution
master_searches = {}
folders = sorted(p.name for p in SEARCHES_DIR.iterdir() if p.is_dir())
for folder in folders:
    pj = SEARCHES_DIR / folder / "papers.json"
    if pj.exists():
        for p in json.loads(pj.read_text(encoding="utf-8")):
            master_searches.setdefault(p["hash_paper_id"], [])
            if folder not in master_searches[p["hash_paper_id"]]:
                master_searches[p["hash_paper_id"]].append(folder)

progress = json.loads(PROGRESS_F.read_text(encoding="utf-8"))
targets = [(h, r) for h, r in progress.items()
           if r.get("doi") and (r.get("downloaded") == "blocked" or r.get("is_oa") is False) and r.get("downloaded") != "pdf"]
print(f"[v3] SS=keyless SPRINGER={bool(SPRINGER)} NCBI={bool(NCBI)} | targets: {len(targets)}")

recovered = 0
for i, (hid, r) in enumerate(targets, 1):
    doi = r["doi"]
    blob = src = None
    for fn in (ss_keyless, springer_pdf, pmc_ncbi):
        blob, src = fn(doi)
        if blob: break
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
    time.sleep(1.1)  # SS keyless shared-pool politeness
    if i % 25 == 0:
        print(f"  [{i}/{len(targets)}] recovered: {recovered}", flush=True)

allrows = list(progress.values())
(BIB/"master_bibliography.json").write_text(json.dumps(allrows, indent=2, ensure_ascii=False), encoding="utf-8")
with (BIB/"master_bibliography.csv").open("w", newline="", encoding="utf-8") as f:
    cols = ["title","first_author","year","doi","doi_src","match_score","is_oa","oa_status","downloaded","file","recovered_via","oa_url"]
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for r in allrows: w.writerow({k: r.get(k) for k in cols})
report = {"unique_papers": len(allrows),
          "downloaded_pdf": sum(1 for r in allrows if r.get("downloaded") == "pdf"),
          "v3_recovered_this_run": recovered,
          "still_blocked": sum(1 for r in allrows if r.get("downloaded") == "blocked"),
          "no_oa_paywalled_no_pdf": sum(1 for r in allrows if r.get("doi") and r.get("is_oa") is False and r.get("downloaded") != "pdf")}
(BIB/"_funnel_report_v3.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\n=== v3 FUNNEL ===")
print(json.dumps(report, indent=2))
print(f"DONE — v3 recovered {recovered} more PDFs")
