#!/usr/bin/env python3
"""Walk research JSON for external citation URLs, quotes, and snapshot hashes."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESEARCH = REPO / "command-center" / "research"

SKIP_HOST = (
    "json-schema.org",
    "json.schemastore.org",
)
URL_KEYS = ("url", "permalink", "resolved_url", "href", "source_url")
QUOTE_KEYS = ("quote", "passage", "locator", "excerpt")
HASH_KEYS = ("sha256", "snapshot_sha256", "digest", "content_sha256")
PATH_KEYS = ("capture_path", "snapshot", "snapshot_path", "path")


def _skip_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return True
    host = (urlparse(url).hostname or "").lower()
    if any(h in host for h in SKIP_HOST):
        return True
    if host in {"example.com", "www.example.com"}:
        return True
    return False


def _as_str(val) -> str | None:
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def harvest_research(root: Path | None = None) -> list[dict]:
    base = root or RESEARCH
    found: list[dict] = []
    if not base.is_dir():
        return found
    for path in sorted(base.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        rel = path.relative_to(REPO).as_posix()
        _walk(doc, rel, found, parent_claim=None, parent_id=None)
    # stable unique by url+quote+file
    uniq = []
    seen = set()
    for row in found:
        key = (row["url"], row.get("quote") or "", row["source_path"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq


def _walk(obj, source_path: str, acc: list, parent_claim, parent_id) -> None:
    if isinstance(obj, list):
        for item in obj:
            _walk(item, source_path, acc, parent_claim, parent_id)
        return
    if not isinstance(obj, dict):
        return
    claim_txt = (
        obj.get("text")
        or obj.get("claim")
        or obj.get("canonical_mechanism")
        or obj.get("mechanism")
        or parent_claim
    )
    cid = obj.get("id") or obj.get("claim_id") or parent_id
    nested = obj.get("source_lineage") or obj.get("lineage")
    url = None
    for k in URL_KEYS:
        val = _as_str(obj.get(k))
        if val and val.startswith("http"):
            url = val
            break
    if url is None and isinstance(nested, dict):
        for k in URL_KEYS + ("resolved_url",):
            val = _as_str(nested.get(k))
            if val and val.startswith("http"):
                url = val
                break
    quote = None
    for k in QUOTE_KEYS:
        quote = _as_str(obj.get(k))
        if quote:
            break
    if quote is None and isinstance(claim_txt, str):
        quote = claim_txt[:240]
    digest = None
    for k in HASH_KEYS:
        digest = _as_str(obj.get(k))
        if digest and len(digest) >= 64:
            digest = digest[:64]
            break
        digest = None
    if digest is None and isinstance(nested, dict):
        for k in HASH_KEYS:
            digest = _as_str(nested.get(k))
            if digest and len(digest) >= 64:
                digest = digest[:64]
                break
            digest = None
    capture = None
    for k in PATH_KEYS:
        capture = _as_str(obj.get(k))
        if capture and ("command-center/" in capture or capture.endswith((".body", ".txt", ".html", ".py", ".json"))):
            break
        capture = None
    status = obj.get("http_status") or obj.get("status")
    if url and not _skip_url(url):
        citationish = any(
            k in obj
            for k in (
                "quote",
                "sha256",
                "snapshot_sha256",
                "capture_path",
                "permalink",
                "source_lineage",
                "lineage",
                "http_status",
            )
        ) or isinstance(nested, dict)
        if citationish or obj.get("kind") in {"structured-source", "prose-docs", "structured-api"}:
            acc.append(
                {
                    "id": str(cid or f"{Path(source_path).stem}:{len(acc)+1}"),
                    "url": url,
                    "quote": quote or "",
                    "snapshot_sha256": digest,
                    "capture_path": capture,
                    "source_path": source_path,
                    "claim_id": str(cid) if cid else None,
                    "claim_text": claim_txt if isinstance(claim_txt, str) else None,
                    "recorded_http_status": status if isinstance(status, int) else None,
                    "kind": obj.get("kind") or obj.get("rail_kind"),
                }
            )
    for v in obj.values():
        if isinstance(v, (dict, list)):
            _walk(v, source_path, acc, claim_txt if isinstance(claim_txt, str) else parent_claim, cid or parent_id)


def local_capture_digest(repo: Path, capture_path: str | None) -> tuple[str | None, int | None]:
    if not capture_path:
        return None, None
    path = repo / capture_path
    if not path.is_file():
        return None, None
    raw = path.read_bytes()
    return sha256_bytes_local(raw), len(raw)


def sha256_bytes_local(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()
