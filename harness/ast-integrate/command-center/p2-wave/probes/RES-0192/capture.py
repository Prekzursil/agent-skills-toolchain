#!/usr/bin/env python3
"""Fetch source bytes into snapshots/ and write snapshots/index.json."""
from __future__ import annotations

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

from catalog import SOURCES, UNIT  # noqa: E402

SNAP = HERE / "snapshots"
UA = {
    "User-Agent": "ast-integrate-RES-0192/1.0 (research harvest; not a crawler farm)",
    "Accept": "application/json, text/html, application/xhtml+xml, */*",
    "Accept-Encoding": "identity",
}


def fetch(url: str) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            body = resp.read()
            return {
                "permalink": url,
                "final_url": resp.geturl(),
                "http_status": int(getattr(resp, "status", None) or resp.getcode()),
                "fetched_at": fetched_at,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "content_type": resp.headers.get("Content-Type"),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return {
            "permalink": url,
            "final_url": url,
            "http_status": int(exc.code),
            "fetched_at": fetched_at,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "content_type": None,
            "body": body,
            "error": f"HTTPError:{exc.code}",
        }


def capture() -> dict:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    for src in SOURCES:
        rec = fetch(src["url"])
        body = rec.pop("body")
        body_path = SNAP / f"{src['id']}.body"
        body_path.write_bytes(body)
        rec.update(
            {
                "id": src["id"],
                "kind": src["kind"],
                "doi": src.get("doi"),
                "year": src["year"],
                "databases": list(src["databases"]),
                "grey": src["grey"],
                "dissenting": src["dissenting"],
                "questions": list(src["questions"]),
                "title": src["title"],
                "pairs_with": src.get("pairs_with"),
                "snapshot": f"command-center/p2-wave/probes/RES-0192/snapshots/{src['id']}.body",
            }
        )
        status = rec.get("http_status")
        ok = status == 200 and rec["bytes"] > 200
        rec["ok"] = ok
        rows.append(rec)
        print(
            f"captured {src['id']} status={status} ok={ok} "
            f"sha256={rec['sha256'][:12]} bytes={rec['bytes']}"
        )
        if not ok:
            failures.append(src["id"])
    index = {
        "unit_id": UNIT,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rails": rows,
        "failures": failures,
    }
    (SNAP / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if failures:
        print(f"FAILED:RES-0192-capture missing {failures}")
        return index
    print("SUCCESS:RES-0192-capture")
    return index


def load_index() -> dict:
    path = SNAP / "index.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}; run capture.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    rails = data.get("rails") or data.get("rails") or []
    data["rails"] = rails
    data["rails"] = rails
    fails = data.get("failures") or data.get("failures") or []
    data["failures"] = fails
    data["failures"] = fails
    captured = data.get("captured_at") or data.get("captured_at")
    data["captured_at"] = captured
    data["captured_at"] = captured
    for row in rails:
        row.setdefault("http_status", row.get("http_status"))
        row.setdefault("http_status", row.get("http_status"))
        row.setdefault("fetched_at", row.get("fetched_at"))
        row.setdefault("fetched_at", row.get("fetched_at"))
        row.setdefault("final_url", row.get("final_url") or row.get("permalink"))
        row.setdefault("final_url", row.get("final_url") or row.get("permalink"))
    return data


def body_bytes(source_id: str) -> bytes:
    path = SNAP / f"{source_id}.body"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes()


def body_text(source_id: str) -> str:
    raw = body_bytes(source_id)
    return raw.decode("utf-8", errors="replace")


load_index = load_index
body_bytes = body_bytes
body_text = body_text


def main() -> int:
    index = capture()
    if index.get("failures") or index.get("failures"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
