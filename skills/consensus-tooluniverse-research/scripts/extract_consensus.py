"""Consensus.app shared-search extractor (browser-free, deterministic-given-fixed-schema).

Fetches each shared Consensus search URL, parses the Next.js __NEXT_DATA__ SSR payload, and writes
per-search: <NN>_<slug>_search.md (source `analysis` markdown for every interaction), papers.json
(deduped paper list), _raw_thread.json (provenance), meta.json (funnel + paper counts).

No auth needed (shared threads are public). Pair with clean_markdown.py for readable output + the
Consensus-Meter question/funnel manifest.

USAGE (parameterized — nothing hardcoded):
    set CONSENSUS_WS=C:\\path\\to\\workspace            # or pass --ws DIR, else current dir
    python extract_consensus.py URL1 URL2 ...           # Consensus shared-search URLs
    python extract_consensus.py --urls searches.txt     # one URL per line (relative to the workspace)
Folder names are derived as <NN>_<slug-from-url>.
"""
from __future__ import annotations
import json, os, re, sys
import requests
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
URL_RE = re.compile(r"^https://consensus\.app/search/([\w-]+)/([\w-]+)/?$")


def workspace() -> Path:
    if "--ws" in sys.argv:
        return Path(sys.argv[sys.argv.index("--ws") + 1])
    return Path(os.environ.get("CONSENSUS_WS") or Path.cwd())


def collect_urls(ws: Path) -> list[str]:
    if "--urls" in sys.argv:
        f = ws / sys.argv[sys.argv.index("--urls") + 1]
        return [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
    return [a for a in sys.argv[1:] if a.startswith("http")]


def fetch_next_data(url: str) -> dict:
    if not URL_RE.match(url):
        raise ValueError(f"refusing non-Consensus-search URL: {url!r}")
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    resp.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text, re.S)
    if not m:
        raise RuntimeError("no __NEXT_DATA__ in " + url)
    return json.loads(m.group(1))


def collect_papers(obj, acc: dict):
    if isinstance(obj, dict):
        if "hash_paper_id" in obj and obj.get("title"):
            acc.setdefault(obj["hash_paper_id"], {
                "title": obj.get("title"), "year": obj.get("year"),
                "first_author": obj.get("first_author"), "has_full_text": obj.get("has_full_text"),
                "hash_paper_id": obj.get("hash_paper_id"),
            })
        for v in obj.values():
            collect_papers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_papers(v, acc)


def main() -> int:
    ws = workspace()
    urls = collect_urls(ws)
    if not urls:
        print("ERROR: no Consensus URLs. Pass URLs as args or --urls <file>.", file=sys.stderr)
        return 2
    (ws / "searches").mkdir(parents=True, exist_ok=True)
    summary = []
    for i, url in enumerate(urls, 1):
        m = URL_RE.match(url)
        if not m:
            summary.append((url, "SKIP (not a Consensus search URL)")); continue
        slug, tid = m.group(1), m.group(2)
        folder = f"{i:02d}_{slug}"
        out = ws / "searches" / folder
        out.mkdir(parents=True, exist_ok=True)
        try:
            thread = fetch_next_data(url)["props"]["pageProps"]["thread"]
        except Exception as e:
            summary.append((folder, f"ERROR: {e}")); continue
        (out / "_raw_thread.json").write_text(json.dumps(thread, indent=2, ensure_ascii=False), encoding="utf-8")
        inter = thread.get("interactions", [])
        papers: dict = {}
        full_text_ids: set = set()
        md = [f"# Consensus search: {slug.replace('-', ' ').title()}\n",
              f"- **URL:** {url}\n- **thread_id:** {tid}\n- **interactions:** {len(inter)}\n\n---\n"]
        for j, it in enumerate(inter):
            at = it.get("agent_trace") or {}
            stats = at.get("summary_stats", {})
            collect_papers(at, papers)
            collect_papers(it.get("results", []), papers)
            full_text_ids |= set(it.get("full_text_paper_ids", []) or [])
            md.append(f"\n## Interaction {j+1} — mode: {it.get('search_mode','')}\n\n"
                      f"**Query:** {it.get('user_message','')}\n\n"
                      f"**Funnel (Consensus internal, not PRISMA):** retrieved {stats.get('num_retrieved','?')} "
                      f"→ eligible {stats.get('num_eligible','?')} → included {stats.get('num_included','?')}\n\n"
                      f"{it.get('analysis','') or ''}\n")
        (out / f"{folder}_search.md").write_text("".join(md), encoding="utf-8")
        plist = sorted(papers.values(), key=lambda p: (p.get("year") or 0), reverse=True)
        for p in plist:
            p["full_text_on_consensus"] = p["hash_paper_id"] in full_text_ids
        (out / "papers.json").write_text(json.dumps(plist, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "meta.json").write_text(json.dumps({
            "url": url, "thread_id": tid, "interactions": len(inter), "n_papers": len(plist),
            "n_full_text_on_consensus": sum(p["full_text_on_consensus"] for p in plist),
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        summary.append((folder, f"{len(inter)} interaction(s), {len(plist)} papers"))
    print("=== EXTRACTION SUMMARY ===")
    for f, s in summary:
        print(f"  {f}: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
