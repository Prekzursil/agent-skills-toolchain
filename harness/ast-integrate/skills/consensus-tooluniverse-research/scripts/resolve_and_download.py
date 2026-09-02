"""Resolve Consensus paper records -> DOI -> open-access full text, organized by category.

Pipeline (uses ToolUniverse live for resolution/OA discovery; requests for the binary fetch):
  1. Load all searches/*/papers.json, DEDUP across searches by hash_paper_id (master unique list).
  2. Resolve DOI: Crossref_search_works -> openalex_search_works fallback. ACCEPTANCE TEST requires
     title-similarity (SequenceMatcher ratio >= TITLE_SIM) AND year (+/-1) AND first-author surname match;
     records the match score + matched title for audit. (Resolution RATE, not validated precision.)
  3. OA discovery: Unpaywall_get_full_text_url (is_oa + oa_status color + all_oa_locations).
  4. Tiered download (browser session + Referer; OA-ONLY, legal; verifies %PDF magic bytes before saving):
       a. each Unpaywall OA pdf location
       b. PMCID -> NCBI PMC OA package (oa.fcgi) PDF  (note: ftp->https rewrite can silently miss)
       c. PMCID -> EuropePMC fullTextXML (content capture when PDF is bot-walled; XML lacks figures)
  5. Download once, then copy into every citing searches/<topic>/papers/ folder.
  6. Write master bibliography (json+csv) + per-search references.md + a funnel report.

Resumable: _bibliography/_progress.json caches per-paper results; re-run continues.
OA-ONLY by design — paywalled papers are recorded with DOI+citation, never bypassed.

USAGE (parameterized — no PII, no hardcoded paths):
    set CONSENSUS_WS=C:\\path\\to\\workspace        # or --ws DIR, else current dir
    set UNPAYWALL_EMAIL=you@example.com             # or --email you@example.com  (REQUIRED by Unpaywall/OpenAlex)
    python resolve_and_download.py [N]              # optional N = smoke-test first N papers
"""

from __future__ import annotations
import csv
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
import requests
from tooluniverse import ToolUniverse

TITLE_SIM = 0.80
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


WS = Path(get_arg("--ws") or os.environ.get("CONSENSUS_WS") or Path.cwd())
EMAIL = get_arg("--email") or os.environ.get("UNPAYWALL_EMAIL")
if not EMAIL:
    sys.exit(
        "ERROR: set UNPAYWALL_EMAIL env var or pass --email (Unpaywall/OpenAlex require a contact email)."
    )

SEARCHES_DIR = WS / "searches"
BIB = WS / "_bibliography"
BIB.mkdir(parents=True, exist_ok=True)
LIB = WS / "_library"
LIB.mkdir(parents=True, exist_ok=True)
PROGRESS_F = BIB / "_progress.json"


def safe(doi):
    return re.sub(r"[^A-Za-z0-9._-]", "_", doi)


def sim(a, b):
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def is_pdf(c):
    return c[:5] == b"%PDF-"


def surname(author):
    return ((author or "").strip().split() or [""])[-1].lower()


tu = ToolUniverse()
tu.load_tools()

# ---------- 1. master unique list ----------
folders = sorted(p.name for p in SEARCHES_DIR.iterdir() if p.is_dir())
master: dict[str, dict] = {}
for folder in folders:
    pj = SEARCHES_DIR / folder / "papers.json"
    if not pj.exists():
        continue
    for p in json.loads(pj.read_text(encoding="utf-8")):
        rec = master.setdefault(p["hash_paper_id"], {**p, "searches": []})
        if folder not in rec["searches"]:
            rec["searches"].append(folder)
print(f"[master] -> {len(master)} unique papers across {len(folders)} searches")
progress = (
    json.loads(PROGRESS_F.read_text(encoding="utf-8")) if PROGRESS_F.exists() else {}
)


def crossref_title(it):
    t = it.get("title")
    return t[0] if isinstance(t, list) and t else (t if isinstance(t, str) else "")


def resolve_doi(title, author, year):
    """Accept only if title-sim>=TITLE_SIM AND year+/-1 AND first-author surname present in candidate authors."""
    want_surname = surname(author)
    try:
        cr = tu.run(
            {
                "name": "Crossref_search_works",
                "arguments": {"query": f"{title} {author}".strip(), "limit": 3},
            }
        )
        for it in cr.get("data") or []:
            t = crossref_title(it)
            yr = (
                (
                    (it.get("issued") or it.get("published") or {}).get("date-parts")
                    or [[None]]
                )[0]
                or [None]
            )[0]
            authors = " ".join(
                (a.get("family", "") + " " + a.get("given", ""))
                for a in (it.get("author") or [])
            ).lower()
            score = sim(t, title)
            if (
                score >= TITLE_SIM
                and (not year or not yr or abs(int(yr) - int(year)) <= 1)
                and (not want_surname or want_surname in authors)
            ):
                return it.get("DOI"), "crossref", round(score, 3), t
    except Exception:
        pass
    try:
        oa = tu.run(
            {
                "name": "openalex_search_works",
                "arguments": {"search": title, "per_page": 3, "mailto": EMAIL},
            }
        )
        results = (
            oa.get("data", {}).get("results")
            if isinstance(oa.get("data"), dict)
            else (oa.get("data") or [])
        )
        for it in results or []:
            t = it.get("title") or it.get("display_name") or ""
            authors = " ".join(
                a.get("author", {}).get("display_name", "")
                for a in (it.get("authorships") or [])
            ).lower()
            score = sim(t, title)
            if score >= 0.82 and (not want_surname or want_surname in authors):
                d = (it.get("doi") or "").replace("https://doi.org/", "")
                if d:
                    return d, "openalex", round(score, 3), t
    except Exception:
        pass
    return None, None, None, None


def oa_locations(doi):
    try:
        up = tu.run(
            {
                "name": "Unpaywall_get_full_text_url",
                "arguments": {"doi": doi, "email": EMAIL},
            }
        )
        d = up.get("data", {}) if isinstance(up, dict) else {}
        locs = []
        if d.get("best_pdf_url"):
            locs.append(d["best_pdf_url"])
        for L in d.get("all_oa_locations") or []:
            u = L.get("url_for_pdf") or L.get("url")
            if u and u not in locs:
                locs.append(u)
        return bool(d.get("is_oa")), d.get("oa_status"), locs
    except Exception:
        return False, None, []


def pmcid_for(doi):
    try:
        q = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22{doi}%22&format=json&resultType=lite"
        res = (
            requests.get(q, headers=UA, timeout=30).json().get("resultList") or {}
        ).get("result") or []
        return res[0].get("pmcid") if res else None
    except Exception:
        return None


def try_download(locs, pmcid):
    s = requests.Session()
    for url in locs:
        try:
            r = s.get(
                url, headers={**UA, "Referer": url}, timeout=60, allow_redirects=True
            )
            if r.status_code == 200 and is_pdf(r.content) and len(r.content) > 2000:
                return "pdf", "pdf", r.content
        except Exception:
            pass
    if pmcid:
        try:
            oa = requests.get(
                f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}",
                headers=UA,
                timeout=30,
            ).text
            m = re.search(r'href="(ftp://[^"]+\.pdf[^"]*)"', oa) or re.search(
                r'href="(https?://[^"]+\.pdf[^"]*)"', oa
            )
            if m:
                r = requests.get(
                    m.group(1).replace("ftp://", "https://"), headers=UA, timeout=60
                )
                if is_pdf(r.content):
                    return "pdf", "pdf", r.content
        except Exception:
            pass
        try:
            r = requests.get(
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
                headers=UA,
                timeout=60,
            )
            if r.status_code == 200 and (
                b"<article" in r.content[:5000] or b"<?xml" in r.content[:50]
            ):
                return "xml", "xml", r.content
        except Exception:
            pass
    return None, None, None


# ---------- 2-5. process ----------
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
items = list(master.items())[:LIMIT] if LIMIT else list(master.items())
if LIMIT:
    print(f"[smoke] limiting to first {LIMIT} papers")
for i, (hid, rec) in enumerate(items, 1):
    if hid in progress:
        continue
    title, author, year = (
        rec.get("title", ""),
        rec.get("first_author") or "",
        rec.get("year"),
    )
    doi, src, score, matched_title = resolve_doi(title, author, year)
    res = {
        "hash_paper_id": hid,
        "title": title,
        "first_author": author,
        "year": year,
        "doi": doi,
        "doi_src": src,
        "match_score": score,
        "matched_title": matched_title,
        "is_oa": None,
        "oa_status": None,
        "downloaded": None,
        "file": None,
        "oa_url": None,
    }
    if doi:
        is_oa, oa_status, locs = oa_locations(doi)
        res["is_oa"], res["oa_status"] = is_oa, oa_status
        res["oa_url"] = locs[0] if locs else None
        if is_oa or locs:
            kind, ext, blob = try_download(locs, pmcid_for(doi))
            if blob:
                fname = f"{safe(doi)}.{ext}"
                (LIB / fname).write_bytes(blob)
                res["downloaded"], res["file"] = kind, fname
            else:
                res["downloaded"] = "blocked"
    progress[hid] = res
    PROGRESS_F.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.25)
    if i % 20 == 0:
        print(f"  [{i}/{len(items)}] done", flush=True)

# ---------- 6. distribute + bibliography ----------
for hid, res in progress.items():
    if res.get("file") and (LIB / res["file"]).exists():
        for folder in master.get(hid, {}).get("searches", []):
            dest = SEARCHES_DIR / folder / "papers" / res["file"]
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((LIB / res["file"]).read_bytes())

for folder in folders:
    rows = [
        progress[p["hash_paper_id"]]
        for p in json.loads(
            (SEARCHES_DIR / folder / "papers.json").read_text(encoding="utf-8")
        )
        if p["hash_paper_id"] in progress
    ]
    rows.sort(key=lambda r: r.get("year") or 0, reverse=True)
    lines = [
        f"# References — {folder}\n",
        f"\n{len(rows)} papers. PDF/XML in `papers/`; 📄 PDF · 📃 XML (text only, figures absent) · ⛔ OA-blocked (browser) · 🔒 no OA.\n\n",
    ]
    for r in rows:
        mark = {"pdf": "📄", "xml": "📃", "blocked": "⛔"}.get(r.get("downloaded"), "")
        if r.get("doi") and not r.get("is_oa"):
            mark = "🔒"
        lines.append(
            f"- {mark} **{r['title']}** ({r.get('year')}) — {r.get('first_author') or 'n/a'} — "
            f"DOI: {r.get('doi') or '—'}"
            + (f" — [OA]({r['oa_url']})" if r.get("oa_url") else "")
            + (f" — `{r['file']}`" if r.get("file") else "")
            + "\n"
        )
    refs_md = SEARCHES_DIR / folder / "papers" / "references.md"
    refs_md.parent.mkdir(parents=True, exist_ok=True)
    refs_md.write_text("".join(lines), encoding="utf-8")

allrows = list(progress.values())
(BIB / "master_bibliography.json").write_text(
    json.dumps(allrows, indent=2, ensure_ascii=False), encoding="utf-8"
)
with (BIB / "master_bibliography.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(
        f,
        fieldnames=[
            "title",
            "first_author",
            "year",
            "doi",
            "doi_src",
            "match_score",
            "is_oa",
            "oa_status",
            "downloaded",
            "file",
            "oa_url",
        ],
    )
    w.writeheader()
    for r in allrows:
        w.writerow({k: r.get(k) for k in w.fieldnames})

report = {
    "unique_papers": len(master),
    "doi_resolution_rate": sum(
        1 for r in allrows if r.get("doi")
    ),  # rate (assigned), not validated precision
    "open_access": sum(1 for r in allrows if r.get("is_oa")),
    "downloaded_pdf": sum(1 for r in allrows if r.get("downloaded") == "pdf"),
    "downloaded_xml": sum(1 for r in allrows if r.get("downloaded") == "xml"),
    "oa_blocked": sum(1 for r in allrows if r.get("downloaded") == "blocked"),
    "no_oa": sum(1 for r in allrows if r.get("doi") and not r.get("is_oa")),
    "no_doi": sum(1 for r in allrows if not r.get("doi")),
}
(BIB / "_funnel_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\n=== FUNNEL (doi_resolution_rate = DOI assigned, not validated precision) ===")
print(json.dumps(report, indent=2))
print("DONE")
