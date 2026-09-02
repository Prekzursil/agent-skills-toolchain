#!/usr/bin/env python3
"""Fetch RES-0161 engine docs/schemas and hash local spec files."""
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
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"

import sources as S  # noqa: E402

UA = "ast-integrate-RES-0161-research/1.0 (two-rail evidence; no credentials)"
CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_url(url: str, attempts: int = 3) -> tuple[int, bytes, str]:
    last_exc: Exception | None = None
    for i in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=45) as resp:
                body = resp.read()
                return int(resp.status), body, resp.geturl()
        except urllib.error.HTTPError as exc:
            body = exc.read() or b""
            if exc.code in {429, 500, 502, 503, 504} and i + 1 < attempts:
                time.sleep(1.5 * (i + 1))
                last_exc = exc
                continue
            return int(exc.code), body, url
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if i + 1 < attempts:
                time.sleep(1.5 * (i + 1))
                continue
            raise
    raise RuntimeError(f"fetch failed {url}: {last_exc}")


def _load_remote_rows() -> list[dict]:
    """Frozen remote rows from the existing INDEX.json (local-only refresh keeps them)."""
    path = CAPTURES / "INDEX.json"
    if not path.is_file():
        raise RuntimeError("--local-only needs an existing captures/INDEX.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    local_ids = {src["id"] for src in S.LOCAL_SOURCES}
    return [row for row in doc.get("captures") or [] if row.get("id") not in local_ids]


def main() -> int:
    # --local-only re-snapshots only LOCAL_SOURCES (repo files copied to captures/*.bin).
    # The local-catalog snapshot is a >5 MB copy of WORK-UNIT-CATALOG.json that the
    # tree capture drops (MaxFileBytes); this rebuilds it from the live file with no
    # network, leaving the frozen remote captures and their index rows untouched.
    local_only = "--local-only" in sys.argv[1:]
    CAPTURES.mkdir(parents=True, exist_ok=True)
    index: list[dict] = _load_remote_rows() if local_only else []
    failures: list[str] = []
    for src in [] if local_only else S.SOURCES:
        sid = src["id"]
        url = src["url"]
        try:
            status, body, final = fetch_url(url)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{sid}: {type(exc).__name__}: {exc}")
            index.append(
                {
                    "id": sid,
                    "engine": src["engine"],
                    "kind": src["kind"],
                    "url": url,
                    "ok": False,
                    "http_status": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                    "fetched_at": utc_now(),
                }
            )
            continue
        dest = CAPTURES / f"{sid}.bin"
        dest.write_bytes(body)
        rec = {
            "id": sid,
            "engine": src["engine"],
            "kind": src["kind"],
            "url": url,
            "final_url": final,
            "ok": status == 200 and len(body) > 0,
            "http_status": status,
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "fetched_at": utc_now(),
            "path": str(dest.relative_to(REPO)).replace("\\", "/"),
        }
        index.append(rec)
        print(f"{'OK' if rec['ok'] else 'BAD'} {status:3d} {len(body):8d} {sid}")
        if not rec["ok"]:
            failures.append(f"{sid} http={status} bytes={len(body)}")

    for src in S.LOCAL_SOURCES:
        path = REPO / src["relpath"]
        if not path.is_file():
            failures.append(f"local missing {src['relpath']}")
            index.append(
                {
                    "id": src["id"],
                    "engine": src["engine"],
                    "kind": src["kind"],
                    "url": src["relpath"],
                    "ok": False,
                    "http_status": 0,
                    "error": "missing",
                    "fetched_at": utc_now(),
                    "path": src["relpath"],
                }
            )
            continue
        body = path.read_bytes()
        dest = CAPTURES / f"{src['id']}.bin"
        dest.write_bytes(body)
        index.append(
            {
                "id": src["id"],
                "engine": src["engine"],
                "kind": src["kind"],
                "url": src["relpath"],
                "ok": True,
                "http_status": 200,
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "fetched_at": utc_now(),
                "path": str(dest.relative_to(REPO)).replace("\\", "/"),
                "source_path": src["relpath"],
            }
        )
        print(f"OK  200 {len(body):8d} {src['id']} (local)")

    (CAPTURES / "INDEX.json").write_text(
        json.dumps({"fetched_at": utc_now(), "captures": index}, indent=1, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print("FAILED:RES-0161-capture " + "; ".join(failures[:12]))
        return 1
    print(f"SUCCESS:RES-0161-capture n={len(index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
