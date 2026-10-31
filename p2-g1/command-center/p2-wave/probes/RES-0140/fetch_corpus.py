#!/usr/bin/env python3
"""Fetch the RES-0140 20-item corpus. Live HTTP first, local fallback second."""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
UA = "ast-integrate-RES-0140 (+research-probe; yield-measurement)"
CTX = ssl.create_default_context()

import sys

sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
from restatement import restatement_talk, speech_wrap  # noqa: E402
from textutil import bytes_to_text  # noqa: E402

MIN_TEXT_CHARS = 1200


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def http_get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,text/plain,text/markdown,application/json,*/*",
        },
        method="GET",
    )
    fetched_at = utc_now()
    try:
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
            body = resp.read()
            status = int(resp.status)
            final = str(resp.geturl())
            ctype = resp.headers.get("Content-Type", "") or ""
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        status = int(exc.code)
        final = url
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
        return {
            "ok": status == 200 and len(body) >= 400,
            "http_status": status,
            "final_url": final,
            "content_type": ctype,
            "body": body,
            "fetched_at": fetched_at,
            "error": f"HTTPError:{status}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "http_status": 0,
            "final_url": url,
            "content_type": "",
            "body": b"",
            "fetched_at": fetched_at,
            "error": f"{type(exc).__name__}:{exc}",
        }
    return {
        "ok": status == 200 and len(body) >= 400,
        "http_status": status,
        "final_url": final,
        "content_type": ctype,
        "body": body,
        "fetched_at": fetched_at,
        "error": None if status == 200 else f"status:{status}",
    }


def copy_fallback(spec: dict) -> dict | None:
    rel = spec.get("local_fallback")
    if not rel:
        return None
    src = REPO / rel
    if not src.is_file() or src.stat().st_size < 200:
        return None
    body = src.read_bytes()
    text_len = len(bytes_to_text(body, ""))
    if text_len < MIN_TEXT_CHARS:
        return None
    return {
        "ok": True,
        "http_status": 200,
        "final_url": spec.get("fallback_url") or spec.get("urls", [""])[0],
        "content_type": "application/octet-stream",
        "body": body,
        "fetched_at": utc_now(),
        "error": None,
        "via": "local-fallback",
        "fallback_path": rel,
    }


def fetch_item(spec: dict) -> dict:
    last = None
    for url in spec.get("urls") or []:
        last = http_get(url)
        last["requested_url"] = url
        last["via"] = "live"
        if last["ok"]:
            text_len = len(bytes_to_text(last["body"], last.get("content_type") or ""))
            if text_len >= MIN_TEXT_CHARS:
                return last
            last["ok"] = False
            last["error"] = f"text-too-thin:{text_len}"
        time.sleep(0.2)
    fb = copy_fallback(spec)
    if fb:
        fb["requested_url"] = (spec.get("urls") or [spec.get("fallback_url")])[0]
        return fb
    if last is None:
        last = {
            "ok": False,
            "http_status": 0,
            "final_url": "",
            "content_type": "",
            "body": b"",
            "fetched_at": utc_now(),
            "error": "no-url",
            "requested_url": "",
            "via": "none",
        }
    return last


def write_capture(iid: str, body: bytes) -> Path:
    CAP.mkdir(parents=True, exist_ok=True)
    path = C.capture_path(iid)
    path.write_bytes(body)
    return path


def maybe_speech_wrap(spec: dict, body: bytes, ctype: str) -> bytes:
    if not spec.get("speech_wrap"):
        return body
    text = bytes_to_text(body, ctype)
    wrapped = speech_wrap(text, spec["id"])
    return wrapped.encode("utf-8")


def build_restatement(spec: dict, index_rows: dict[str, dict]) -> dict:
    blog_id = spec["companion_blog_id"]
    blog_row = index_rows.get(blog_id)
    blog_path = C.capture_path(blog_id)
    if not blog_path.is_file():
        return {
            "id": spec["id"],
            "ok": False,
            "error": f"companion-blog-missing:{blog_id}",
        }
    raw = blog_path.read_bytes()
    text = bytes_to_text(raw, (blog_row or {}).get("content_type") or "")
    talk = restatement_talk(text, spec["id"])
    body = talk.encode("utf-8")
    path = write_capture(spec["id"], body)
    return {
        "id": spec["id"],
        "source_class": spec["source_class"],
        "subject": spec["subject"],
        "role": spec["role"],
        "ok": True,
        "via": "derived-restatement",
        "http_status": 200,
        "requested_url": f"derived:{blog_id}",
        "final_url": f"derived:{blog_id}",
        "permalink": f"derived:{blog_id}",
        "content_type": "text/plain; charset=utf-8",
        "fetched_at": utc_now(),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "capture_path": str(path.relative_to(REPO).as_posix()),
        "companion_blog_id": blog_id,
        "companion_blog_sha256": sha256_bytes(raw),
        "error": None,
        "kind": spec["kind"],
    }


def main() -> int:
    C.assert_inventory()
    CAP.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict] = {}
    # Non-derived first so restatements can hash companion blogs.
    pending = [it for it in C.ITEMS if not it.get("derived")]
    derived = [it for it in C.ITEMS if it.get("derived")]
    for spec in pending:
        got = fetch_item(spec)
        body = got.get("body") or b""
        if got.get("ok") and spec.get("speech_wrap"):
            body = maybe_speech_wrap(spec, body, got.get("content_type") or "")
        ok = bool(got.get("ok") and len(body) >= 200)
        if ok:
            path = write_capture(spec["id"], body)
        else:
            path = C.capture_path(spec["id"])
        row = {
            "id": spec["id"],
            "source_class": spec["source_class"],
            "subject": spec["subject"],
            "role": spec.get("role") or spec["source_class"],
            "ok": ok,
            "via": got.get("via"),
            "http_status": got.get("http_status"),
            "requested_url": got.get("requested_url")
            or ((spec.get("urls") or [None])[0]),
            "final_url": got.get("final_url"),
            "permalink": got.get("final_url") or got.get("requested_url"),
            "content_type": got.get("content_type"),
            "fetched_at": got.get("fetched_at"),
            "sha256": sha256_bytes(body) if ok else None,
            "bytes": len(body) if ok else 0,
            "capture_path": str(path.relative_to(REPO).as_posix()) if ok else None,
            "error": None if ok else (got.get("error") or "too-small"),
            "kind": spec["kind"],
            "fallback_path": got.get("fallback_path"),
            "note": spec.get("note"),
            "speech_wrap": bool(spec.get("speech_wrap")),
        }
        rows[spec["id"]] = row
        print(
            f"{spec['id']} ok={ok} via={row['via']} status={row['http_status']} "
            f"bytes={row['bytes']} err={row['error']}"
        )
        time.sleep(0.15)
    for spec in derived:
        row = build_restatement(spec, rows)
        rows[spec["id"]] = row
        print(
            f"{spec['id']} ok={row.get('ok')} via={row.get('via')} "
            f"bytes={row.get('bytes')} err={row.get('error')}"
        )
    ordered = [rows[it["id"]] for it in C.ITEMS]
    index = {
        "unit_id": C.UID,
        "fetched_at": utc_now(),
        "sample_size": len(C.ITEMS),
        "items": ordered,
    }
    (CAP / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ok_n = sum(1 for r in ordered if r.get("ok"))
    print(f"ok={ok_n}/{len(ordered)}")
    return 0 if ok_n == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
