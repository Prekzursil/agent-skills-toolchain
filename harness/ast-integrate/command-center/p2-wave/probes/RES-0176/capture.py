#!/usr/bin/env python3
"""Live-fetch RES-0176 rails. Writes snapshots/<name> and harvest_meta.json."""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sources import SOURCES, UA  # noqa: E402

SNAP = HERE / "snapshots"
META = HERE / "harvest_meta.json"
CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def http_get(url: str, accept: str) -> tuple[int, bytes, str, str, str | None]:
    headers = {
        "User-Agent": UA,
        "Accept": accept or "*/*",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
            raw = resp.read()
            status = int(resp.status)
            final = str(resp.geturl())
            ctype = resp.headers.get("Content-Type") or ""
            return status, raw, final, ctype, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:
            body = b""
        return int(exc.code), body, url, "", f"HTTPError:{exc.code}"
    except Exception as exc:
        return 0, b"", url, "", f"{type(exc).__name__}:{exc}"


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    errors: list[str] = []
    for src in SOURCES:
        name = src["name"]
        url = src["url"]
        status, raw, final, ctype, err = http_get(url, src.get("accept") or "*/*")
        if status != 200 or err or not raw:
            # one retry
            time.sleep(0.4)
            status, raw, final, ctype, err = http_get(url, src.get("accept") or "*/*")
        ok = status == 200 and bool(raw) and err is None
        rec = {
            "name": name,
            "url": url,
            "final_url": final,
            "ok": ok,
            "status": status,
            "error": err,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw) if raw else None,
            "fetched_at": utc_now(),
            "content_type": ctype,
            "family": src["family"],
            "rail": src["rail"],
        }
        entries.append(rec)
        if ok:
            (SNAP / name).write_bytes(raw)
            print(f"OK {status} {name} bytes={len(raw)} sha256={rec['sha256']}")
        else:
            errors.append(f"{name} status={status} err={err}")
            print(f"FAIL {name} status={status} err={err}")
    META.write_text(
        json.dumps(
            {
                "unit_id": "RES-0176",
                "fetched_at": utc_now(),
                "entries": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if errors:
        print("FAILED:RES-0176 capture", errors)
        return 1
    print(f"SUCCESS:RES-0176 capture n={len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
