#!/usr/bin/env python3
"""Live-fetch RES-0059 rails. Writes captures/<id>.body and captures/<id>.meta.json."""
from __future__ import annotations

import base64
import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sources import NEEDLES, SOURCES, UA  # noqa: E402

CAP = HERE / "captures"
CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode_github(raw: bytes) -> str | None:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict) or doc.get("encoding") != "base64":
        return None
    blob = doc.get("content")
    if not isinstance(blob, str) or not blob.strip():
        return None
    try:
        return base64.b64decode(blob).decode("utf-8", errors="replace")
    except Exception:
        return None


def searchable(raw: bytes, decoded: str | None) -> str:
    if decoded:
        return decoded
    return raw.decode("utf-8", errors="replace")


def needle_hits(text: str) -> dict[str, str | None]:
    hits: dict[str, str | None] = {}
    lowered = text
    for key, needles in NEEDLES.items():
        found = None
        for n in needles:
            if n in lowered:
                found = n
                break
        hits[key] = found
    return hits


def http_get(url: str, src: dict) -> tuple[int, bytes, str, str, str | None]:
    headers = {
        "User-Agent": UA,
        "Accept": src.get("accept") or "*/*",
    }
    if src.get("rail") == "api":
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
            raw = resp.read()
            status = int(resp.status)
            final = str(resp.geturl())
            ctype = resp.headers.get("Content-Type") or ""
            return status, raw, final, ctype, None
    except urllib.error.HTTPError as exc:
        raw = exc.read() or b""
        ctype = exc.headers.get("Content-Type") if exc.headers else ""
        return int(exc.code), raw, url, ctype or "", None
    except urllib.error.URLError as exc:
        err = str(exc.reason if getattr(exc, "reason", None) else exc)
        return 0, b"", url, "", err


def fetch_one(src: dict) -> dict:
    urls = [src["url"]] + list(src.get("fallback_urls") or [])
    fetched_at = utc_now()
    status, raw, final, ctype, err = 0, b"", src["url"], "", None
    url_used = src["url"]
    for url in urls:
        url_used = url
        status, raw, final, ctype, err = http_get(url, src)
        if status == 200 and raw:
            break
    if err and status == 0:
        return {
            "id": src["id"],
            "family": src["family"],
            "rail": src["rail"],
            "request_url": url_used,
            "permalink": url_used,
            "final_url": url_used,
            "http_status": 0,
            "error": err,
            "fetched_at": fetched_at,
            "sha256": None,
            "bytes": 0,
            "ok": False,
        }
    permalink = final

    decoded = decode_github(raw) if src.get("decode_github_contents") else None
    if src.get("decode_github_contents") and 200 <= status < 300:
        try:
            meta = json.loads(raw.decode("utf-8"))
            if isinstance(meta, dict) and meta.get("html_url"):
                permalink = meta["html_url"]
            if decoded is None and isinstance(meta, dict):
                dl = meta.get("download_url")
                if isinstance(dl, str) and dl:
                    _st, raw2, _fn, _ct, _e = http_get(
                        dl, {"accept": "application/octet-stream", "rail": "prose"}
                    )
                    if _st == 200 and raw2:
                        decoded = raw2.decode("utf-8", errors="replace")
        except Exception:
            pass

    text = searchable(raw, decoded)
    hits = needle_hits(text) if status == 200 else {}
    rec = {
        "id": src["id"],
        "family": src["family"],
        "rail": src["rail"],
        "request_url": url,
        "permalink": permalink,
        "final_url": final,
        "http_status": status,
        "content_type": ctype,
        "fetched_at": fetched_at,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "github_decoded": bool(decoded),
        "decoded_sha256": sha256_bytes(decoded.encode("utf-8")) if decoded else None,
        "decoded_bytes": len(decoded.encode("utf-8")) if decoded else None,
        "needle_hits": hits,
        "ok": status == 200 and len(raw) > 0,
    }
    (CAP / f"{src['id']}.body").write_bytes(raw)
    if decoded is not None:
        (CAP / f"{src['id']}.decoded.txt").write_text(decoded, encoding="utf-8")
    (CAP / f"{src['id']}.meta.json").write_text(
        json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return rec


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    fail = 0
    for src in SOURCES:
        rec = fetch_one(src)
        index.append(rec)
        flag = "OK" if rec.get("ok") else "FAIL"
        if not rec.get("ok"):
            fail += 1
        print(
            f"{flag} {rec['id']} status={rec.get('http_status')} "
            f"bytes={rec.get('bytes')} sha256={str(rec.get('sha256'))[:12]} "
            f"hits={[k for k, v in (rec.get('needle_hits') or {}).items() if v]}"
        )
        if rec.get("error"):
            print(f"  error={rec['error']}")
    (CAP / "INDEX.json").write_text(
        json.dumps({"captured_at": utc_now(), "sources": index}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    ok_n = sum(1 for r in index if r.get("ok"))
    print(f"captured_ok={ok_n}/{len(index)} fail={fail}")
    # Do not hard-fail the capture runner on a subset of 404s; emit decides.
    return 0 if ok_n >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
