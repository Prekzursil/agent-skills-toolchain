#!/usr/bin/env python3
"""Fetch RES-0158 primary sources. Writes captures/<id>.body + INDEX.json."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sources import SOURCES, UA  # noqa: E402

CAP = HERE / "captures"
CTX = ssl.create_default_context()
TIMEOUT = 70


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def pdf_strings(raw: bytes) -> str:
    """Best-effort Latin text from a PDF without a PDF library."""
    chunks: list[str] = []
    for m in re.finditer(rb"\((?:\\.|[^\\)]){4,200}\)", raw):
        s = m.group(0)[1:-1]
        try:
            t = s.decode("latin-1")
        except UnicodeDecodeError:
            continue
        t = (
            t.replace("\\n", " ")
            .replace("\\r", " ")
            .replace("\\t", " ")
            .replace("\\(", "(")
            .replace("\\)", ")")
        )
        if sum(ch.isalpha() for ch in t) >= 8:
            chunks.append(t)
    for m in re.finditer(rb"[\x20-\x7e]{16,}", raw):
        t = m.group(0).decode("ascii")
        if sum(ch.isalpha() for ch in t) >= 12:
            chunks.append(t)
    return "\n".join(chunks)


def searchable(raw: bytes, ctype: str) -> str:
    if "pdf" in (ctype or "").lower() or raw[:5] == b"%PDF-":
        return pdf_strings(raw)
    return raw.decode("utf-8", errors="replace")


def http_get(url: str) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    ts = utc_now()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
            final = str(resp.geturl())
            ctype = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        status = int(exc.code)
        final = url
        ctype = exc.headers.get("Content-Type") if exc.headers else ""
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "fetched_at": ts,
            "final_url": url,
            "body": b"",
            "content_type": "",
        }
    return {
        "ok": 200 <= status < 400 and len(raw) > 400,
        "http_status": status,
        "error": None,
        "fetched_at": ts,
        "final_url": final,
        "body": raw,
        "content_type": ctype,
    }


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    fail = 0
    for src in SOURCES:
        got = None
        used = ""
        for url in src["urls"]:
            trial = http_get(url)
            print(
                f"  try {src['id']} status={trial['http_status']} "
                f"bytes={len(trial['body'])} url={url[:90]}"
            )
            if trial["ok"]:
                got = trial
                used = url
                break
            got = trial
            used = url
        assert got is not None
        body_name = f"{src['id']}.body"
        text_name = f"{src['id']}.text"
        (CAP / body_name).write_bytes(got["body"])
        text = searchable(got["body"], got.get("content_type") or "")
        (CAP / text_name).write_text(text, encoding="utf-8", errors="replace")
        sha = sha256_bytes(got["body"])
        row = {
            "id": src["id"],
            "rail": src["rail"],
            "kind": src["kind"],
            "covers": src["covers"],
            "permalink": src["urls"][0],
            "resolved_url": got["final_url"],
            "url_used": used,
            "fetched_at": got["fetched_at"],
            "http_status": got["http_status"],
            "ok": got["ok"],
            "error": got["error"],
            "bytes": len(got["body"]),
            "sha256": sha,
            "text_chars": len(text),
            "capture_path": (
                "command-center/p2-wave/probes/RES-0158/captures/" + body_name
            ),
            "text_path": (
                "command-center/p2-wave/probes/RES-0158/captures/" + text_name
            ),
        }
        index.append(row)
        flag = "OK" if got["ok"] else "FAIL"
        if not got["ok"]:
            fail += 1
        print(
            f"{flag} {src['id']} status={got['http_status']} "
            f"bytes={len(got['body'])} text={len(text)} sha={sha[:12]}"
        )
    (CAP / "INDEX.json").write_text(
        json.dumps(index, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(index)} captures fail={fail}")
    if fail:
        print("FAILED:RES-0158 capture one or more remote rails")
        return 1
    print("SUCCESS:RES-0158 capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
