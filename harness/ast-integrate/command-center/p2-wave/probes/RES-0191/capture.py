#!/usr/bin/env python3
"""Fetch dual-rail sources for RES-0191 (structured API/schema + prose)."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = "RES-0191-ast-integrate-research/1.0 (honest-capture)"
CTX = ssl.create_default_context()

SOURCES = [
    {
        "id": "nextflow-cache-and-resume",
        "kind": "prose-source",
        "filename": "nextflow-cache-and-resume.md",
        "url": (
            "https://raw.githubusercontent.com/nextflow-io/nextflow/"
            "7b664ced/docs/cache-and-resume.md"
        ),
        "needles": ["resume", "successfully"],
    },
    {
        "id": "nextflow-task-status",
        "kind": "structured-api",
        "filename": "nextflow-TaskStatus.groovy",
        "url": (
            "https://raw.githubusercontent.com/nextflow-io/nextflow/"
            "v24.04.4/modules/nextflow/src/main/groovy/nextflow/processor/TaskStatus.groovy"
        ),
        "needles": ["COMPLETED", "RUNNING", "error condition"],
        "fallbacks": [
            (
                "https://raw.githubusercontent.com/nextflow-io/nextflow/"
                "v24.10.4/modules/nextflow/src/main/groovy/nextflow/processor/TaskStatus.groovy"
            ),
            (
                "https://raw.githubusercontent.com/nextflow-io/nextflow/"
                "master/modules/nextflow/src/main/groovy/nextflow/processor/TaskStatus.groovy"
            ),
        ],
    },
    {
        "id": "airflow-task-instance-state",
        "kind": "structured-api",
        "filename": "airflow-utils-state.py",
        "url": (
            "https://raw.githubusercontent.com/apache/airflow/"
            "2.10.4/airflow/utils/state.py"
        ),
        "needles": ["SUCCESS", "FAILED", "RUNNING", "UP_FOR_RETRY"],
    },
    {
        "id": "airflow-task-lifecycle-docs",
        "kind": "prose-source",
        "filename": "airflow-concepts-tasks.html",
        "url": (
            "https://airflow.apache.org/docs/apache-airflow/2.10.4/"
            "core-concepts/tasks.html"
        ),
        "needles": ["failed", "retry", "success"],
    },
    {
        "id": "temporal-event-type-proto",
        "kind": "structured-api",
        "filename": "temporal-event-type.proto",
        "url": (
            "https://raw.githubusercontent.com/temporalio/api/"
            "v1.43.0/temporal/api/enums/v1/event_type.proto"
        ),
        "needles": ["ACTIVITY_TASK_COMPLETED", "ACTIVITY_TASK_FAILED"],
        "fallbacks": [
            (
                "https://raw.githubusercontent.com/temporalio/api/"
                "master/temporal/api/enums/v1/event_type.proto"
            ),
        ],
    },
    {
        "id": "temporal-event-history-docs",
        "kind": "prose-source",
        "filename": "temporal-event-history.md",
        "url": (
            "https://raw.githubusercontent.com/temporalio/documentation/"
            "main/docs/encyclopedia/event-history.md"
        ),
        "needles": ["Event History", "replay"],
        "fallbacks": [
            (
                "https://raw.githubusercontent.com/temporalio/documentation/"
                "main/docs/develop/python/core-application.md"
            ),
            "https://docs.temporal.io/encyclopedia/event-history",
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    ts = utc_now()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "http_status": int(resp.status),
                "content_type": resp.headers.get("Content-Type"),
                "fetched_at": ts,
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": int(exc.code),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "fetched_at": ts,
            "error": str(exc),
            "body": body,
        }
    except Exception as exc:  # noqa: BLE001 — capture rail must record the miss
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "http_status": None,
            "fetched_at": ts,
            "error": f"{type(exc).__name__}: {exc}",
            "body": b"",
        }


def needles_ok(body: bytes, needles: list[str]) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    return [n for n in needles if n not in text]


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    rows = []
    failed = []
    for spec in SOURCES:
        urls = [spec["url"]] + list(spec.get("fallbacks") or [])
        got = None
        used = spec["url"]
        for url in urls:
            got = fetch(url)
            used = url
            if got.get("ok") and got.get("http_status") == 200 and got.get("body"):
                missing = needles_ok(got["body"], spec["needles"])
                if not missing:
                    break
                got["needle_miss"] = missing
        body = got.get("body") or b""
        dest = CAP / spec["filename"]
        dest.write_bytes(body)
        missing = needles_ok(body, spec["needles"]) if body else list(spec["needles"])
        row = {
            "id": spec["id"],
            "kind": spec["kind"],
            "url": spec["url"],
            "permalink": used,
            "final_url": got.get("final_url"),
            "http_status": got.get("http_status"),
            "content_type": got.get("content_type"),
            "fetched_at": got.get("fetched_at"),
            "bytes": dest.stat().st_size,
            "sha256": sha256_bytes(dest.read_bytes()) if dest.is_file() else None,
            "path": (
                "command-center/p2-wave/probes/RES-0191/captures/" + spec["filename"]
            ),
            "needles": spec["needles"],
            "needles_missing": missing,
            "ok": bool(
                got.get("ok")
                and got.get("http_status") == 200
                and dest.stat().st_size > 0
                and not missing
            ),
        }
        if got.get("error"):
            row["error"] = got["error"]
        if not row["ok"]:
            failed.append(spec["id"])
        rows.append(row)
        print(
            f"http {row['http_status']} {spec['id']} ok={row['ok']} "
            f"bytes={row['bytes']} miss={missing}"
        )

    index = {
        "unit_id": "RES-0191",
        "captured_at": utc_now(),
        "captures": rows,
        "failed_ids": failed,
    }
    (CAP / "INDEX.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if failed:
        print(f"FAILED:RES-0191-capture missing={failed}")
        return 1
    print("SUCCESS:RES-0191-capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
