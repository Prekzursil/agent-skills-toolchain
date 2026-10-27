#!/usr/bin/env python3
"""Capture R1 (GitHub Contents/Blob JSON API) and R2 (prose docs) evidence rails.

Each capture records permalink, final URL, HTTP status, fetch timestamp, sha256
of the exact bytes stored. Does not print tokens.
"""
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
SNAP = HERE / "snapshots"
UA = "ast-integrate-RES-0063-research/1.0 (evidence-capture; +https://github.com)"

SOURCES = [
    {
        "id": "airflow-r1-taskinstance-api",
        "engine": "airflow",
        "rail": "R1",
        "kind": "structured-api",
        "url": "https://api.github.com/repos/apache/airflow/contents/airflow-core/src/airflow/models/taskinstance.py",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "airflow-r2-tasks-docs",
        "engine": "airflow",
        "rail": "R2",
        "kind": "prose",
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html",
        "accept": "text/html",
    },
    {
        "id": "prefect-r1-tasks-api",
        "engine": "prefect",
        "rail": "R1",
        "kind": "structured-api",
        "url": "https://api.github.com/repos/PrefectHQ/prefect/contents/src/prefect/tasks.py",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prefect-r2-tasks-docs",
        "engine": "prefect",
        "rail": "R2",
        "kind": "prose",
        "url": "https://docs.prefect.io/v3/concepts/tasks",
        "accept": "text/html",
    },
    {
        "id": "prefect-r2-caching-docs",
        "engine": "prefect",
        "rail": "R2",
        "kind": "prose",
        "url": "https://docs.prefect.io/v3/concepts/caching",
        "accept": "text/html",
    },
    {
        "id": "dagster-r1-assetkey-api",
        "engine": "dagster",
        "rail": "R1",
        "kind": "structured-api",
        "url": "https://api.github.com/repos/dagster-io/dagster/contents/python_modules/dagster/dagster/_core/definitions/asset_key.py",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "dagster-r2-defining-assets",
        "engine": "dagster",
        "rail": "R2",
        "kind": "prose",
        "url": "https://docs.dagster.io/guides/build/assets/defining-assets",
        "accept": "text/html",
    },
    {
        "id": "dagster-r2-run-retries",
        "engine": "dagster",
        "rail": "R2",
        "kind": "prose",
        "url": "https://docs.dagster.io/deployment/execution/run-retries",
        "accept": "text/html",
    },
    {
        "id": "flyte-r1-identifier-api",
        "engine": "flyte",
        "rail": "R1",
        "kind": "structured-api",
        "url": "https://api.github.com/repos/flyteorg/flytekit/contents/flytekit/models/core/identifier.py",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "flyte-r2-caching-docs",
        "engine": "flyte",
        "rail": "R2",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/flyteorg/flyte/master/docs/user_guide/development_lifecycle/caching.md",
        "accept": "text/plain",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, accept: str) -> tuple[int, str, bytes, dict]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            body = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), str(resp.geturl()), body, headers
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        return int(exc.code), url, body, headers


def maybe_follow_blob(meta: dict, headers_in: dict) -> dict | None:
    """If Contents API says the file is too large, fetch git blob JSON instead."""
    if meta.get("encoding") == "base64" and meta.get("content"):
        return None
    sha = meta.get("sha")
    url = meta.get("git_url") or (f"https://api.github.com/repos/{meta.get('url','')}".strip())
    if not sha and not meta.get("git_url"):
        msg = str(meta.get("message") or "")
        # Typical oversized contents response includes a git_url-less message.
        if "Git Blobs API" in msg or "too large" in msg.lower():
            return {"reason": "too-large-no-git-url", "message": msg[:300]}
        return None
    blob_url = meta.get("git_url")
    if not blob_url:
        return None
    status, final, body, headers = fetch(blob_url, "application/vnd.github+json")
    rec = {
        "url": blob_url,
        "final_url": final,
        "http_status": status,
        "headers": {k: headers.get(k) for k in ("content-type", "x-ratelimit-remaining", "etag") if k in headers},
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "fetched_at": utc_now(),
    }
    return {"blob_meta": rec, "body": body}


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    index = {
        "unit_id": "RES-0063",
        "captured_at": utc_now(),
        "user_agent": UA,
        "rails": [],
    }
    for src in SOURCES:
        time.sleep(0.4)
        status, final, body, headers = fetch(src["url"], src["accept"])
        rec = {
            "id": src["id"],
            "engine": src["engine"],
            "rail": src["rail"],
            "kind": src["kind"],
            "permalink": src["url"],
            "final_url": final,
            "http_status": status,
            "fetch_timestamp": utc_now(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "content_type": headers.get("content-type"),
            "github_html_url": None,
            "github_blob_sha": None,
            "github_download_url": None,
            "decoded_source_sha256": None,
            "body_path": f"snapshots/{src['id']}.bin",
        }
        (SNAP / f"{src['id']}.bin").write_bytes(body)
        extra = {}
        if src["kind"] == "structured-api" and status == 200:
            try:
                meta = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                meta = None
            if isinstance(meta, dict):
                rec["github_html_url"] = meta.get("html_url")
                rec["github_blob_sha"] = meta.get("sha")
                rec["github_download_url"] = meta.get("download_url")
                rec["permalink"] = meta.get("html_url") or src["url"]
                blob_follow = maybe_follow_blob(meta, headers)
                if blob_follow and blob_follow.get("body"):
                    bname = f"{src['id']}.git-blob.json"
                    (SNAP / bname).write_bytes(blob_follow["body"])
                    extra["git_blob"] = {k: v for k, v in blob_follow["blob_meta"].items()}
                    extra["git_blob"]["body_path"] = f"snapshots/{bname}"
                    try:
                        blob = json.loads(blob_follow["body"].decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        blob = None
                    if isinstance(blob, dict) and blob.get("content") and blob.get("encoding") == "base64":
                        import base64

                        decoded = base64.b64decode(blob["content"])
                        dname = f"{src['id']}.decoded.bin"
                        (SNAP / dname).write_bytes(decoded)
                        rec["decoded_source_sha256"] = hashlib.sha256(decoded).hexdigest()
                        extra["decoded_path"] = f"snapshots/{dname}"
                        extra["decoded_bytes"] = len(decoded)
                elif isinstance(meta, dict) and meta.get("encoding") == "base64" and meta.get("content"):
                    import base64

                    decoded = base64.b64decode(meta["content"])
                    dname = f"{src['id']}.decoded.bin"
                    (SNAP / dname).write_bytes(decoded)
                    rec["decoded_source_sha256"] = hashlib.sha256(decoded).hexdigest()
                    extra["decoded_path"] = f"snapshots/{dname}"
                    extra["decoded_bytes"] = len(decoded)
        rec["extra"] = extra
        index["rails"].append(rec)
        print(f"{src['id']} status={status} bytes={rec['bytes']} sha256={rec['sha256'][:16]}...")
    (SNAP / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failed = [r for r in index["rails"] if int(r["http_status"]) >= 400]
    if failed:
        print("FAILED:fetch some rails HTTP>=400")
        for r in failed:
            print(f"  {r['id']} {r['http_status']}")
        return 1
    print("SUCCESS:RES-0063-fetch rails captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
