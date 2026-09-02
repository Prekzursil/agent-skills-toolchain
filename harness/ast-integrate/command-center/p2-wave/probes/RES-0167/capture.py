#!/usr/bin/env python3
"""Fetch public retry-policy rails and snapshot local sources with sha256."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
CAP = CAP
UA = "RES-0167-repair-loop-research/1.0 (local measurement; +https://github.com)"
CTX = ssl.create_default_context()

WEB_SOURCES: list[dict[str, Any]] = [
    {
        "id": "sre-handling-overload",
        "url": "https://sre.google/sre-book/handling-overload/",
        "fallbacks": [
            "https://sre.google/sre-book/addressing-cascading-failures/",
        ],
        "needles": ["retry", "overload"],
        "rail": "R2-prose",
    },
    {
        "id": "aws-backoff-jitter",
        "url": "https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/",
        "fallbacks": [],
        "needles": ["jitter", "backoff"],
        "rail": "R2-prose",
    },
    {
        "id": "temporal-retry-policy",
        "url": "https://docs.temporal.io/encyclopedia/retry-policies",
        "fallbacks": [
            "https://docs.temporal.io/develop/go/failure-detection",
            "https://docs.temporal.io/references/sdk-metrics",
        ],
        "needles": ["retry", "attempt"],
        "rail": "R2-prose",
    },
]

LOCAL_SOURCES: list[dict[str, str]] = [
    {
        "id": "supervisor-log",
        "path": "/opt/p2/supervisor.log",
        "url": "file:///opt/p2/supervisor.log",
        "rail": "R1-estate-log",
    },
    {
        "id": "dispatch-cursor",
        "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "url": "file:///opt/p2/ast-integrate/command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "rail": "R1-source",
    },
    {
        "id": "adv-0059-validate",
        "path": "command-center/p2-wave/probes/ADV-0059/_validate_out.json",
        "url": "file:///opt/p2/ast-integrate/command-center/p2-wave/probes/ADV-0059/_validate_out.json",
        "rail": "R1-recorded-retry",
    },
    {
        "id": "aud-0084-refute",
        "path": "command-center/p2-wave/probes/AUD-0084/_refute_out.json",
        "url": "file:///opt/p2/ast-integrate/command-center/p2-wave/probes/AUD-0084/_refute_out.json",
        "rail": "R1-recorded-retry",
    },
    {
        "id": "cc-0024-slice",
        "path": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
        "url": "file:///opt/p2/ast-integrate/command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
        "rail": "R1-spec-slice",
    },
    {
        "id": "catalog-res-0167",
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "url": "file:///opt/p2/ast-integrate/command-center/WORK-UNIT-CATALOG.json",
        "rail": "R1-catalog",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def http_get(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
            return int(resp.status), resp.read(), str(resp.geturl())
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read() or b"", url
    except urllib.error.URLError:
        return 0, b"", url


def fetch_web() -> list[dict[str, Any]]:
    CAP.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for src in WEB_SOURCES:
        fetched_at = utc_now()
        status, raw, final = 0, b"", src["url"]
        used = src["url"]
        for url in [src["url"], *(src.get("fallbacks") or [])]:
            used = url
            status, raw, final = http_get(url)
            if status == 200 and raw:
                break
        body_path = CAP / f"{src['id']}.body"
        meta_path = CAP / f"{src['id']}.meta.json"
        body_path.write_bytes(raw)
        text = raw.decode("utf-8", errors="replace")
        needles = {n: (n.lower() in text.lower()) for n in src["needles"]}
        rec = {
            "id": src["id"],
            "requested_url": src["url"],
            "resolved_url": final or used,
            "url_used": used,
            "fetch_timestamp": fetched_at,
            "http_status": status,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "snapshot": f"command-center/p2-wave/probes/RES-0167/captures/{src['id']}.body",
            "needles": needles,
            "rail": src["rail"],
            "ok": status == 200 and raw and all(needles.values()),
        }
        meta_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        out.append(rec)
    return out


def snapshot_local() -> list[dict[str, Any]]:
    CAP.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for src in LOCAL_SOURCES:
        rel = src["path"]
        path = Path(rel) if rel.startswith("/") else REPO / rel
        fetched_at = utc_now()
        raw = path.read_bytes() if path.is_file() else b""
        dest = CAP / f"{src['id']}.body"
        dest.write_bytes(raw)
        rec = {
            "id": src["id"],
            "requested_url": src["url"],
            "resolved_url": src["url"],
            "fetch_timestamp": fetched_at,
            "http_status": None,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw.replace(b"\r\n", b"\n")) if raw else sha256_bytes(raw),
            "snapshot": f"command-center/p2-wave/probes/RES-0167/captures/{src['id']}.body",
            "present": path.is_file() and len(raw) > 0,
            "source_path": rel,
            "rail": src["rail"],
            "ok": path.is_file() and len(raw) > 0,
        }
        (CAP / f"{src['id']}.meta.json").write_text(
            json.dumps(rec, indent=2) + "\n", encoding="utf-8"
        )
        out.append(rec)
    return out


def capture_all() -> dict[str, Any]:
    web = fetch_web()
    local = snapshot_local()
    index = {
        "captured_at": utc_now(),
        "web": web,
        "local": local,
        "web_ok": sum(1 for r in web if r.get("ok")),
        "local_ok": sum(1 for r in local if r.get("ok")),
    }
    (CAP / "INDEX.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    return index


def load_index() -> dict[str, Any]:
    path = CAP / "INDEX.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return capture_all()


def main() -> int:
    idx = capture_all()
    print(
        f"web_ok={idx['web_ok']}/{len(idx['web'])} "
        f"local_ok={idx['local_ok']}/{len(idx['local'])}"
    )
    for row in idx["web"] + idx["local"]:
        print(
            f"{row['id']} status={row.get('http_status')} "
            f"bytes={row['bytes']} ok={row.get('ok')} sha256={row['sha256'][:12]}"
        )
    return 0 if idx["local_ok"] >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())

capture_all = capture_all
capture_all = capture_all

capture_all = capture_all
