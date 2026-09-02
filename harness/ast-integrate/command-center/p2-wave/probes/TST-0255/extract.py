"""Extract file:line anchors and http(s) URLs from documentation text."""
from __future__ import annotations

import re
from pathlib import Path

ANCHOR_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\."
    r"(?:md|py|json|txt|yml|yaml|toml|rst|sh|ps1|js|ts))"
    r":(\d+)([A-Za-z])?"
)
URL_RE = re.compile(r"https?://[^\s)\]>'\"`]+")
TRAIL_URL = frozenset(".,;:)]}>'\"")

CATALOG_DOCS = (
    "command-center/RUNBOOK.md",
    "command-center/RELEASE-CHECKLIST.md",
)
CATALOG_PROMPTS = (
    "_USER-PROMPTS.md",
)
LIVE_GLOBS = (
    "command-center/*.md",
    "command-center/design/**/*.md",
    "command-center/p2-wave/*.md",
)


def strip_url(raw: str) -> str:
    url = raw.rstrip()
    while url and url[-1] in TRAIL_URL:
        url = url[:-1]
    return url


def extract_text(text: str, source: str) -> dict:
    anchors = []
    seen_a = set()
    for match in ANCHOR_RE.finditer(text):
        path, line_s, suffix = match.group(1), match.group(2), match.group(3) or ""
        start = match.start(1)
        if start >= 3 and text[start - 3 : start] == "://":
            continue
        line = int(line_s)
        key = (path, line, suffix)
        if key in seen_a:
            continue
        seen_a.add(key)
        anchors.append(
            {
                "path": path,
                "line": line,
                "suffix": suffix or None,
                "raw": match.group(0),
                "source": source,
                "source_offset": start,
            }
        )
    urls = []
    seen_u = set()
    for match in URL_RE.finditer(text):
        url = strip_url(match.group(0))
        if not url or url in seen_u:
            continue
        seen_u.add(url)
        urls.append({"url": url, "source": source, "source_offset": match.start()})
    return {"anchors": anchors, "urls": urls}


def iter_live_docs(repo: Path) -> list[str]:
    found: list[str] = []
    seen = set()
    for pattern in LIVE_GLOBS:
        for path in sorted(repo.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if "/probes/" in rel:
                continue
            if rel in seen:
                continue
            seen.add(rel)
            found.append(rel)
    return found


def catalog_inputs(repo: Path) -> list[dict]:
    rows = []
    for rel in list(CATALOG_DOCS) + list(CATALOG_PROMPTS):
        p = repo / rel
        rows.append(
            {
                "path": rel,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
                "role": "catalog-input",
            }
        )
    return rows


def scan_docs(repo: Path) -> dict:
    inputs = catalog_inputs(repo)
    live = iter_live_docs(repo)
    files = []
    anchors = []
    urls = []
    for rel in live:
        path = repo / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        extracted = extract_text(text, rel)
        files.append({"path": rel, "exists": True, "bytes": len(text.encode("utf-8"))})
        anchors.extend(extracted["anchors"])
        urls.extend(extracted["urls"])
    missing_catalog = [r for r in inputs if not r["exists"] and r["path"] in CATALOG_DOCS]
    return {
        "catalog_inputs": inputs,
        "catalog_docs_present": all(r["exists"] for r in inputs if r["path"] in CATALOG_DOCS),
        "missing_catalog_docs": [r["path"] for r in missing_catalog],
        "scanned_files": files,
        "scanned_file_count": len(files),
        "anchors": anchors,
        "urls": urls,
        "anchor_count": len(anchors),
        "url_count": len(urls),
    }
