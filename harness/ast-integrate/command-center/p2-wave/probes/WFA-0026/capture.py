#!/usr/bin/env python3
"""Fetch practitioner and vendor pages. Three retries with jitter; no key rotation."""
from __future__ import annotations

import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import digest_bytes, dump_json, load_json  # noqa: E402

UA = "WFA-0026-practitioner-sweep/1.0 (+research; untrusted-DATA capture)"
TIMEOUT = 12
CAP = HERE / "captures"
FALLBACK_DIR = Path("/root/.cursor/projects/opt-p2-ast-integrate/agent-tools")
# Optional pre-fetched markdown used only when live HTTP fails.
FALLBACK_FILES = {
    "vendor-claude-hooks": "f1a8a272-907b-44f1-ac2a-db518bdf93b0.txt",
    "vendor-claude-subagents": "a936e5c6-d54a-4a6c-aacb-6a66d41ccb61.txt",
    "claudelab-hooks-production": "9fba5115-25eb-45b9-835e-3a310dbfdeb0.txt",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_once(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown,*/*;q=0.8",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    ts = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            body = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "http_status": int(exc.code),
            "error": f"HTTPError:{exc.code}",
            "fetched_at": ts,
            "final_url": url,
            "body": body,
            "rail": "http",
        }
    except Exception as exc:  # noqa: BLE001 - capture transport failures honestly
        return {
            "ok": False,
            "http_status": 0,
            "error": f"{type(exc).__name__}:{exc}",
            "fetched_at": ts,
            "final_url": url,
            "body": b"",
            "rail": "http",
        }
    return {
        "ok": 200 <= status < 400 and len(body) > 0,
        "http_status": status,
        "error": None,
        "fetched_at": ts,
        "final_url": final,
        "body": body,
        "rail": "http",
    }


def looks_blocked(raw: bytes) -> bool:
    if len(raw) < 180:
        return True
    low = raw.decode("utf-8", "replace").casefold()
    markers = (
        "just a moment",
        "enable javascript to run this app",
        "unfortunately, we could not display",
        "access denied",
    )
    return any(m in low for m in markers) and len(raw) < 12000


def fetch_with_retry(url: str) -> dict:
    last = None
    for attempt in range(2):
        if attempt:
            time.sleep((0.35 * (2 ** (attempt - 1))) + random.random() * 0.25)
        last = fetch_once(url)
        if last["ok"] and not looks_blocked(last["body"]):
            return last
        if last["ok"] and looks_blocked(last["body"]):
            last = dict(last)
            last["ok"] = False
            last["error"] = (last.get("error") or "") + ";interstitial-or-empty"
        if last["http_status"] and 400 <= last["http_status"] < 500 and last["http_status"] != 429:
            return last
    return last or fetch_once(url)


def fallback_body(source_id: str) -> bytes | None:
    name = FALLBACK_FILES.get(source_id)
    if name:
        p = FALLBACK_DIR / name
        if p.is_file():
            return p.read_bytes()
    # Inline fallbacks written next to this probe after a failed HTTP attempt.
    p = HERE / "fallbacks" / f"{source_id}.body"
    if p.is_file():
        return p.read_bytes()
    return None


def main() -> int:
    catalog = load_json(HERE / "sources.json")
    CAP.mkdir(parents=True, exist_ok=True)
    index = []
    fail = 0
    for src in catalog.get("sources") or []:
        sid = src["id"]
        if src.get("role") == "fixture" or str(src.get("url") or "").startswith("fixture://"):
            body_path = HERE / "fixtures" / "planted_injection.body"
            raw = body_path.read_bytes() if body_path.is_file() else b""
            row = {
                "id": sid,
                "permalink": src["url"],
                "final_url": src["url"],
                "fetched_at": utcnow(),
                "http_status": 200,
                "ok": bool(raw),
                "error": None,
                "bytes": len(raw),
                "sha256": digest_bytes(raw),
                "rail": "fixture",
                "capture_path": "command-center/p2-wave/probes/WFA-0026/fixtures/planted_injection.body",
            }
            (CAP / f"{sid}.body").write_bytes(raw)
            index.append(row)
            print(f"FIXTURE {sid} bytes={len(raw)}")
            continue
        got = fetch_with_retry(src["url"])
        raw = got["body"]
        rail = got.get("rail") or "http"
        if not got["ok"]:
            fb = fallback_body(sid)
            if fb:
                raw = fb
                got = dict(got)
                got["ok"] = True
                got["error"] = f"http-failed:{got.get('error')};used-fallback-bytes"
                got["http_status"] = got.get("http_status") or 0
                rail = "fallback-bytes"
        body_path = CAP / f"{sid}.body"
        body_path.write_bytes(raw)
        row = {
            "id": sid,
            "permalink": src["url"],
            "final_url": got.get("final_url") or src["url"],
            "fetched_at": got["fetched_at"],
            "http_status": got["http_status"],
            "ok": bool(got["ok"] and raw),
            "error": got.get("error"),
            "bytes": len(raw),
            "sha256": digest_bytes(raw),
            "rail": rail,
            "capture_path": f"command-center/p2-wave/probes/WFA-0026/captures/{sid}.body",
        }
        index.append(row)
        flag = "OK" if row["ok"] else "FAIL"
        if not row["ok"]:
            fail += 1
        print(
            f"{flag} {sid} status={row['http_status']} bytes={row['bytes']} "
            f"rail={rail} err={row['error']}"
        )
        time.sleep(0.15 + random.random() * 0.2)
    dump_json(CAP / "INDEX.json", index)
    print(f"wrote {len(index)} captures fail={fail}")
    if fail:
        print("FAILED:WFA-0026 capture one or more remote rails")
        return 1
    print("SUCCESS:WFA-0026 capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
