#!/usr/bin/env python3
"""ADV-0020 citation reachability + archival fallback helpers.

Probe 1 uses live HTTP (status, final URL, quote containment).
Probe 2 uses the Wayback CDX API + snapshot body (mechanically different).
"""
from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESEARCH = REPO / "command-center" / "research"
UNIT = "ADV-0020"

URL_KEYS = (
    "permalink",
    "url",
    "requested_url",
    "html_url",
    "citation_url",
    "resolved_url",
    "final_url",
)
QUOTE_KEYS = (
    "snippet",
    "clause_quote",
    "quote",
    "quoted_text",
    "must_contain",
    "title",
)
SKIP_PREFIXES = (
    "fixture://",
    "file://",
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
)
UA = (
    "Mozilla/5.0 (compatible; ast-integrate-ADV-0020/1.0; "
    "+citation-linkrot-archival-audit)"
)
CTX = ssl.create_default_context()
LIVE_TIMEOUT = 8
ARCHIVE_TIMEOUT = 20
BODY_CAP = 750_000
WORKERS = 12
CDX = "https://archive.org/wayback/available"

CONTROLS = (
    {
        "id": "CTRL-LIVE-CONTAINING",
        "role": "known-live-and-containing",
        "url": "https://example.com/",
        "quoted_text": "Example Domain",
        "source_path": "command-center/p2-wave/probes/ADV-0020/lib_adv0020.py",
        "fetched_at_hint": None,
        "planted": True,
    },
    {
        "id": "CTRL-DEAD",
        "role": "known-dead",
        "url": "https://github.com/adv-0020-known-dead-never-created-9f3c2e1a/repo",
        "quoted_text": "ADV0020-PLANTED-QUOTE-MUST-BE-ABSENT",
        "source_path": "command-center/p2-wave/probes/ADV-0020/lib_adv0020.py",
        "fetched_at_hint": None,
        "planted": True,
    },
    {
        "id": "CTRL-LIVE-MISMATCH",
        "role": "known-live-quote-absent",
        "url": "https://example.com/",
        "quoted_text": "ADV0020-SILENT-ROT-QUOTE-NEVER-ON-EXAMPLE",
        "source_path": "command-center/p2-wave/probes/ADV-0020/lib_adv0020.py",
        "fetched_at_hint": None,
        "planted": True,
    },
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_http_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v.startswith(("http://", "https://")):
        return False
    low = v.lower()
    if any(low.startswith(p) for p in SKIP_PREFIXES):
        return False
    return True


def _quote_from_dict(obj: dict) -> str | None:
    for key in QUOTE_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            text = val.strip()
            if key == "title" and len(text) < 8:
                continue
            return text
    return None


def _same_object_quote(obj: dict) -> str | None:
    """Only quotes that live on the same object as the URL (no inherited titles)."""
    for key in ("snippet", "clause_quote", "quote", "quoted_text", "must_contain"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    title = obj.get("title")
    if isinstance(title, str) and len(title.strip()) >= 8:
        if any(is_http_url(obj.get(k) or "") for k in URL_KEYS):
            return title.strip()
    return None


def _walk(obj: Any, source: str, stack: list[dict], out: list[dict]) -> None:
    if isinstance(obj, dict):
        urls = []
        for key in URL_KEYS:
            val = obj.get(key)
            if is_http_url(val):
                urls.append(val.strip())
        quote = _same_object_quote(obj)
        fetched = obj.get("fetched_at") or obj.get("fetch_timestamp")
        if not isinstance(fetched, str):
            fetched = None
        for url in urls:
            out.append(
                {
                    "url": url,
                    "quoted_text": quote,
                    "source_path": source,
                    "fetched_at_hint": fetched,
                    "planted": False,
                    "role": "corpus",
                }
            )
        stack.append(obj)
        for val in obj.values():
            _walk(val, source, stack, out)
        stack.pop()
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, source, stack, out)


def extract_citations() -> list[dict]:
    raw: list[dict] = []
    if RESEARCH.is_dir():
        for path in sorted(RESEARCH.glob("*.json")):
            rel = path.relative_to(REPO).as_posix()
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            _walk(doc, rel, [], raw)
    # Dedup by (url, quoted_text). Keep first source.
    seen: set[tuple[str, str]] = set()
    citations: list[dict] = []
    n = 0
    for item in raw:
        quote = item["quoted_text"] or ""
        key = (item["url"], quote)
        if key in seen:
            continue
        seen.add(key)
        n += 1
        citations.append(
            {
                "id": f"C-{n:03d}",
                "url": item["url"],
                "quoted_text": item["quoted_text"],
                "source_path": item["source_path"],
                "fetched_at_hint": item["fetched_at_hint"],
                "planted": False,
                "role": "corpus",
            }
        )
    for ctrl in CONTROLS:
        citations.append(dict(ctrl))
    return citations


def _maybe_gunzip(raw: bytes) -> bytes:
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        try:
            return gzip.decompress(raw)
        except OSError:
            return raw
    return raw


def _decode_body(raw: bytes) -> str:
    raw = _maybe_gunzip(raw)
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _search_haystacks(body: str) -> str:
    unescaped = html.unescape(body)
    stripped = re.sub(r"<[^>]+>", " ", unescaped)
    collapsed = re.sub(r"\s+", " ", stripped)
    return "\n".join((body, unescaped, stripped, collapsed))


def quote_in_body(quoted: str | None, body: str) -> bool | None:
    if not quoted or not quoted.strip():
        return None
    needle = quoted.strip()
    hay = _search_haystacks(body)
    if needle in hay:
        return True
    if needle.lower() in hay.lower():
        return True
    # Long quotes: try a stable 80-char window from the start.
    compact = re.sub(r"\s+", " ", needle).strip()
    if len(compact) > 80:
        window = compact[:80]
        hay_c = re.sub(r"\s+", " ", hay)
        if window.lower() in hay_c.lower():
            return True
    return False


def http_resolve(url: str, timeout: float = LIVE_TIMEOUT) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "en",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    started = time.time()
    fetched_at = now_iso()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            status = int(resp.status)
            final = str(resp.geturl())
            raw = resp.read(BODY_CAP + 1)
            truncated = len(raw) > BODY_CAP
            raw = _maybe_gunzip(raw[:BODY_CAP])
            ctype = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(BODY_CAP) if exc.fp else b""
        except Exception:
            raw = b""
        raw = _maybe_gunzip(raw[:BODY_CAP])
        elapsed = round(time.time() - started, 3)
        body = _decode_body(raw)
        return {
            "requested_url": url,
            "final_url": url,
            "http_status": int(exc.code),
            "error": f"HTTPError:{exc.code}",
            "elapsed_s": elapsed,
            "fetched_at": fetched_at,
            "bytes": len(raw),
            "truncated": False,
            "content_type": (exc.headers.get("Content-Type") if exc.headers else "") or "",
            "body_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            "body_text": body,
        }
    except Exception as exc:
        return {
            "requested_url": url,
            "final_url": None,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "elapsed_s": round(time.time() - started, 3),
            "fetched_at": fetched_at,
            "bytes": 0,
            "truncated": False,
            "content_type": "",
            "body_sha256": None,
            "body_text": "",
        }
    elapsed = round(time.time() - started, 3)
    body = _decode_body(raw)
    return {
        "requested_url": url,
        "final_url": final,
        "http_status": status,
        "error": None,
        "elapsed_s": elapsed,
        "fetched_at": fetched_at,
        "bytes": len(raw),
        "truncated": truncated,
        "content_type": ctype,
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_text": body,
    }


def classify_live(citation: dict, resolved: dict) -> dict:
    quoted = citation.get("quoted_text")
    contained = quote_in_body(quoted, resolved.get("body_text") or "")
    status = int(resolved.get("http_status") or 0)
    live_ok = status == 200
    if contained is True and live_ok:
        kind = "live-containing"
    elif live_ok and contained is False:
        kind = "live-mismatch"
    elif live_ok and contained is None:
        kind = "live-unquoted"
    else:
        kind = "dead-or-error"
    needs_archive = kind in {"live-mismatch", "dead-or-error"}
    return {
        "id": citation["id"],
        "role": citation.get("role") or "corpus",
        "planted": bool(citation.get("planted")),
        "source_path": citation.get("source_path"),
        "url": citation["url"],
        "quoted_text": quoted,
        "quote_recorded": bool(quoted),
        "http_status": status,
        "final_url": resolved.get("final_url"),
        "error": resolved.get("error"),
        "elapsed_s": resolved.get("elapsed_s"),
        "fetched_at": resolved.get("fetched_at"),
        "bytes": resolved.get("bytes"),
        "truncated": resolved.get("truncated"),
        "content_type": resolved.get("content_type"),
        "body_sha256": resolved.get("body_sha256"),
        "quote_in_live_body": contained,
        "kind": kind,
        "needs_archive": needs_archive,
        "fetched_at_hint": citation.get("fetched_at_hint"),
    }


def live_probe(citations: list[dict] | None = None) -> dict:
    citations = citations if citations is not None else extract_citations()
    by_url: dict[str, dict] = {}
    unique = []
    for c in citations:
        if c["url"] not in by_url:
            by_url[c["url"]] = c
            unique.append(c["url"])

    resolved: dict[str, dict] = {}

    def _one(url: str) -> tuple[str, dict]:
        return url, http_resolve(url)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(_one, u) for u in unique]
        for fut in as_completed(futs):
            url, row = fut.result()
            # Drop body_text from the shared map after classify; keep per-row.
            resolved[url] = row

    rows = []
    for c in citations:
        row = classify_live(c, resolved[c["url"]])
        rows.append(row)

    corpus = [r for r in rows if not r["planted"]]
    controls = [r for r in rows if r["planted"]]
    n_200 = sum(1 for r in corpus if r["http_status"] == 200)
    n_containing = sum(1 for r in corpus if r["kind"] == "live-containing")
    n_mismatch = sum(1 for r in corpus if r["kind"] == "live-mismatch")
    n_dead = sum(1 for r in corpus if r["kind"] == "dead-or-error")
    n_unquoted = sum(1 for r in corpus if r["kind"] == "live-unquoted")
    n = len(corpus)
    summary = {
        "probe": "probe1-http-resolve",
        "unit_id": UNIT,
        "n_citations": len(rows),
        "n_corpus": n,
        "n_controls": len(controls),
        "n_unique_urls": len(unique),
        "n_http_200": n_200,
        "n_live_containing": n_containing,
        "n_live_mismatch": n_mismatch,
        "n_live_unquoted": n_unquoted,
        "n_dead_or_error": n_dead,
        "resolve_rate": (n_200 / n) if n else None,
        "containing_rate_among_quoted": (
            (
                sum(1 for r in corpus if r["quote_recorded"] and r["quote_in_live_body"])
                / max(1, sum(1 for r in corpus if r["quote_recorded"]))
            )
            if n
            else None
        ),
        "all_healthy_including_controls": all(
            r["kind"] in {"live-containing", "live-unquoted"} for r in rows
        ),
        "rows": rows,
    }
    return summary


def _wayback_ts(iso: str | None) -> str | None:
    if not iso:
        return None
    digits = re.sub(r"[^0-9]", "", iso)
    if len(digits) >= 14:
        return digits[:14]
    if len(digits) >= 8:
        return digits.ljust(14, "0")
    return None


def cdx_lookup(url: str, closest_iso: str | None = None) -> dict:
    """Query Wayback replay by URL+timestamp (availability/CDX APIs 429 on this host)."""
    closest = _wayback_ts(closest_iso)
    ts_day = (closest or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))[:8]
    snap_url = f"https://web.archive.org/web/{ts_day}/{url}"
    endpoint = snap_url
    fetched_at = now_iso()
    started = time.time()
    last_exc = None
    raw = b""
    status = 0
    final = snap_url
    for attempt in range(3):
        try:
            req = urllib.request.Request(snap_url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=ARCHIVE_TIMEOUT, context=CTX) as resp:
                raw = _maybe_gunzip(resp.read(BODY_CAP + 1)[:BODY_CAP])
                status = int(resp.status)
                final = str(resp.geturl())
            last_exc = None
            break
        except urllib.error.HTTPError as exc:
            raw = b""
            try:
                raw = _maybe_gunzip((exc.read(BODY_CAP) if exc.fp else b"")[:BODY_CAP])
            except Exception:
                raw = b""
            status = int(exc.code)
            if status in {429, 503} and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                last_exc = exc
                continue
            # 404 = not archived; that is a real archive miss, not an instrument failure.
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(0.5 * (attempt + 1))
    elapsed = round(time.time() - started, 3)
    if status == 0 and last_exc is not None:
        return {
            "url": url,
            "cdx_status": 0,
            "error": f"{type(last_exc).__name__}:{last_exc}",
            "snapshots": [],
            "chosen": None,
            "body_text": "",
            "fetched_at": fetched_at,
            "elapsed_s": elapsed,
            "endpoint": endpoint,
            "archive_api": "wayback-replay",
        }
    ts_match = re.search(r"/web/(\d{8,14})(?:id_)?/", final or "")
    ts = ts_match.group(1) if ts_match else ts_day
    snapshots = []
    chosen = None
    if status == 200:
        chosen = {
            "timestamp": ts,
            "original": url,
            "statuscode": str(status),
            "digest": "",
            "availability_url": final,
        }
        snapshots = [chosen]
    return {
        "url": url,
        "cdx_status": status,
        "error": None if status in {200, 404} else (f"HTTPError:{status}" if status else None),
        "snapshots": snapshots,
        "n_snapshots": len(snapshots),
        "chosen": chosen,
        "body_text": _decode_body(raw),
        "snapshot_http_status": status,
        "snapshot_url": final,
        "snapshot_bytes": len(raw),
        "fetched_at": fetched_at,
        "elapsed_s": elapsed,
        "endpoint": endpoint,
        "closest_requested": closest,
        "archive_api": "wayback-replay",
    }


def fetch_snapshot(timestamp: str, original: str) -> dict:
    snap_url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    started = time.time()
    fetched_at = now_iso()
    try:
        req = urllib.request.Request(snap_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=ARCHIVE_TIMEOUT, context=CTX) as resp:
            raw = _maybe_gunzip(resp.read(BODY_CAP + 1)[:BODY_CAP])
            status = int(resp.status)
            final = str(resp.geturl())
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(BODY_CAP) if exc.fp else b""
        except Exception:
            raw = b""
        return {
            "snapshot_url": snap_url,
            "http_status": int(exc.code),
            "error": f"HTTPError:{exc.code}",
            "final_url": snap_url,
            "bytes": len(raw),
            "body_text": _decode_body(raw),
            "fetched_at": fetched_at,
            "elapsed_s": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {
            "snapshot_url": snap_url,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "final_url": None,
            "bytes": 0,
            "body_text": "",
            "fetched_at": fetched_at,
            "elapsed_s": round(time.time() - started, 3),
        }
    return {
        "snapshot_url": snap_url,
        "http_status": status,
        "error": None,
        "final_url": final,
        "bytes": len(raw),
        "body_text": _decode_body(raw),
        "fetched_at": fetched_at,
        "elapsed_s": round(time.time() - started, 3),
    }


def archive_recheck(live_rows: list[dict]) -> dict:
    candidates = [
        r
        for r in live_rows
        if r.get("needs_archive") or r.get("planted")
    ]
    # Always archive-check planted controls even if live-containing (calibration).
    seen_ids = {r["id"] for r in candidates}
    for r in live_rows:
        if r.get("planted") and r["id"] not in seen_ids:
            candidates.append(r)
            seen_ids.add(r["id"])

    uniq: dict[str, dict] = {}
    for row in candidates:
        if row["url"] not in uniq:
            uniq[row["url"]] = row

    def _prio(url: str) -> tuple[int, str]:
        src = uniq[url]
        if src.get("id") == "CTRL-LIVE-CONTAINING" or src.get("role") == "known-live-and-containing":
            return (0, url)
        if src.get("planted"):
            return (1, url)
        return (2, url)

    ordered = sorted(uniq.keys(), key=_prio)
    fetched: dict[str, dict] = {}
    for i, url in enumerate(ordered):
        if i:
            time.sleep(0.35)
        src = uniq[url]
        hint = src.get("fetched_at_hint") or src.get("fetched_at")
        cdx = cdx_lookup(url, hint)
        snap = None
        chosen = cdx.get("chosen")
        if chosen or cdx.get("body_text"):
            snap = {
                "snapshot_url": cdx.get("snapshot_url"),
                "http_status": cdx.get("snapshot_http_status") or cdx.get("cdx_status"),
                "error": cdx.get("error"),
                "bytes": cdx.get("snapshot_bytes"),
                "elapsed_s": cdx.get("elapsed_s"),
                "timestamp": (chosen or {}).get("timestamp"),
                "body_text": cdx.get("body_text") or "",
            }
        fetched[url] = {"cdx": cdx, "snap": snap, "chosen": chosen}

    out_rows = []
    for row in candidates:
        payload = fetched[row["url"]]
        cdx = payload["cdx"]
        snap = payload["snap"]
        chosen = payload["chosen"]
        quote = row.get("quoted_text")
        archive_quote = None
        snap_meta = None
        if snap:
            archive_quote = quote_in_body(quote, snap.get("body_text") or "")
            snap_meta = {
                "snapshot_url": snap.get("snapshot_url"),
                "http_status": snap.get("http_status"),
                "error": snap.get("error"),
                "bytes": snap.get("bytes"),
                "elapsed_s": snap.get("elapsed_s"),
                "timestamp": (chosen or {}).get("timestamp"),
            }
        out_rows.append(
            {
                "id": row["id"],
                "role": row.get("role"),
                "planted": bool(row.get("planted")),
                "url": row["url"],
                "quoted_text": quote,
                "live_kind": row.get("kind"),
                "live_http_status": row.get("http_status"),
                "quote_in_live_body": row.get("quote_in_live_body"),
                "needs_archive": bool(row.get("needs_archive")),
                "cdx_status": cdx.get("cdx_status"),
                "cdx_error": cdx.get("error"),
                "n_snapshots": len(cdx.get("snapshots") or []),
                "chosen_timestamp": (chosen or {}).get("timestamp"),
                "snapshot": snap_meta,
                "quote_in_archive_body": archive_quote,
                "archival_recovery": bool(archive_quote) if archive_quote is not None else False,
            }
        )
    out_rows.sort(key=lambda r: r["id"])

    deadish = [r for r in live_rows if r.get("needs_archive") and not r.get("planted")]
    checked_ids = {r["id"] for r in out_rows}
    missing = [r["id"] for r in deadish if r["id"] not in checked_ids]
    recovered = sum(1 for r in out_rows if r.get("archival_recovery") and r.get("needs_archive"))
    return {
        "probe": "probe2-archive-recheck",
        "unit_id": UNIT,
        "n_live_rows": len(live_rows),
        "n_archive_candidates": len(candidates),
        "n_corpus_needing_archive": len(deadish),
        "n_archive_checked": len(out_rows),
        "n_archival_recovery": recovered,
        "missing_checks": missing,
        "every_failure_checked": not missing,
        "rows": out_rows,
    }


def public_live_row(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "body_text"}


def dump_json(path: Path, doc: dict) -> None:
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
