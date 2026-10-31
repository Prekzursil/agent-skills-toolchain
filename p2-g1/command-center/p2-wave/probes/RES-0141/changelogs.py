"""Fetch changelog files from raw.githubusercontent.com and attach sections.

Does not call api.github.com. Does not import detector.py or labels.py.
"""
from __future__ import annotations

import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from common import CAPTURES, sha256_bytes, now_iso, dump_json, load_json
from fetch_corpus import save_capture, UA, CTX

# Common changelog paths tried in order per repo (tag or default branch).
CHANGELOG_CANDIDATES: dict[tuple[str, str], list[tuple[str, str]]] = {
    # (owner, repo): list of (ref, path)
    ("pallets", "flask"): [("main", "CHANGES.rst"), ("master", "CHANGES.rst")],
    ("pallets", "click"): [("main", "CHANGES.rst")],
    ("pallets", "werkzeug"): [("main", "CHANGES.rst")],
    ("pallets", "jinja"): [("main", "CHANGES.rst")],
    ("pallets", "markupsafe"): [("main", "CHANGES.rst")],
    ("pallets", "itsdangerous"): [("main", "CHANGES.rst")],
    ("encode", "httpx"): [("master", "CHANGELOG.md")],
    ("encode", "starlette"): [("main", "CHANGELOG.md"), ("master", "CHANGELOG.md")],
    ("encode", "uvicorn"): [("main", "CHANGELOG.md")],
    ("pydantic", "pydantic"): [("main", "HISTORY.md")],
    ("tiangolo", "fastapi"): [("master", "docs/en/docs/release-notes.md")],
    ("pytest-dev", "pytest"): [("main", "doc/en/changelog.rst"), ("main", "changelog.rst")],
    ("psf", "black"): [("main", "CHANGES.md")],
    ("urllib3", "urllib3"): [("main", "CHANGES.rst")],
    ("redis", "redis-py"): [("master", "CHANGES")],
    ("sqlalchemy", "sqlalchemy"): [("main", "CHANGES")],
    ("aio-libs", "aiohttp"): [("master", "CHANGES.rst")],
    ("python-poetry", "poetry"): [("main", "CHANGELOG.md")],
    ("Textualize", "rich"): [("master", "CHANGELOG.md")],
    ("tiangolo", "typer"): [("master", "docs/release-notes.md")],
    ("celery", "celery"): [("main", "Changelog.rst")],
    ("vitejs", "vite"): [("main", "packages/vite/CHANGELOG.md")],
    ("facebook", "react"): [("main", "CHANGELOG.md")],
}


HEADING_RE = re.compile(
    r"(?m)^(?:#{1,4}\s+|Version\s+)v?(?P<ver>\d+\.\d+\.\d+)\b.*$"
    r"|^v?(?P<ver2>\d+\.\d+\.\d+)\s*(?:\([^)]*\))?\s*$"
)


def fetch_url(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=45) as resp:
            return int(resp.status), resp.read(), str(resp.geturl())
    except urllib.error.HTTPError as exc:
        return int(exc.code), (exc.read() if exc.fp else b""), url
    except urllib.error.URLError:
        return 0, b"", url


def fetch_changelog(owner: str, repo: str) -> dict | None:
    for ref, path in CHANGELOG_CANDIDATES.get((owner, repo), []):
        stem = f"changelog-{owner}-{repo}-{ref}-{path.replace('/', '_')}"
        meta_path = CAPTURES / f"{stem}.meta.json"
        body_path = CAPTURES / f"{stem}.body"
        if meta_path.is_file() and body_path.is_file():
            meta = load_json(meta_path)
            if meta.get("http_status") == 200:
                return meta
            continue
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        status, raw, final = fetch_url(url)
        meta = save_capture(stem, url, status, raw, final)
        meta["owner"] = owner
        meta["repo"] = repo
        meta["ref"] = ref
        meta["path"] = path
        dump_json(meta_path, meta)
        print(f"changelog {owner}/{repo} {ref}:{path} status={status} bytes={len(raw)}")
        time.sleep(0.15)
        if status == 200 and len(raw) > 400:
            return meta
    return None


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (version, section_text) pairs from a changelog."""
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        ver = None
        m = re.match(r"^(#{1,4})\s+v?(\d+\.\d+\.\d+)\b", line)
        if m:
            ver = m.group(2)
        m = re.match(r"^Version\s+v?(\d+\.\d+\.\d+)\s*$", line)
        if m:
            ver = m.group(1)
        m = re.match(r"^v?(\d+\.\d+\.\d+)\s*(?:\([^)]*\))?\s*$", line)
        if m and i + 1 < len(lines) and re.match(r"^[=\-~]{3,}\s*$", lines[i + 1]):
            ver = m.group(1)
        m = re.match(r"^v?(\d+\.\d+\.\d+)\s+\(", line)
        if m:
            ver = m.group(1)
        if ver:
            headings.append((i, ver))
    out: list[tuple[str, str]] = []
    for idx, (i, ver) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        body = "\n".join(lines[i:end]).strip()
        if len(body) >= 40:
            out.append((ver, body))
    return out


def changelog_index(owner: str, repo: str) -> dict[str, dict]:
    meta = fetch_changelog(owner, repo)
    if not meta:
        return {}
    path = CAPTURES / f"{meta['id']}.body"
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = split_sections(text)
    idx = {}
    for ver, body in sections:
        idx[ver] = {
            "version": ver,
            "text": body,
            "capture_id": meta["id"],
            "resolved_url": meta.get("resolved_url"),
            "requested_url": meta.get("requested_url"),
            "fetched_at": meta.get("fetched_at"),
            "sha256": meta.get("sha256"),
            "http_status": meta.get("http_status"),
            "path": meta.get("path"),
            "ref": meta.get("ref"),
        }
    return idx
