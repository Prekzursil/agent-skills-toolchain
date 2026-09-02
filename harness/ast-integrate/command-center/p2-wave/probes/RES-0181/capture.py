#!/usr/bin/env python3
"""Build capture index and planted silent fixtures. Optional --fetch re-downloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "captures" / "raw"
INDEX = HERE / "captures" / "index.json"
UA = "ast-integrate-RES-0181-research/1.0 (+local-worktree; no-auth)"

from corpus import RAILS, UNIT_ID  # noqa: E402

PLANTED = {
    "silent-s01-search.json": (
        '{"total_count":0,"incomplete_results":false,"items":[],'
        '"search_type":"lexical"}\n'
    ),
    "silent-s01-wip.txt": (
        "commit deadbeef0001\n"
        "Author: none <none@example.invalid>\n"
        "Date: 1970-01-01\n"
        "\n"
        "wip\n"
        "\n"
        "commit cafe00010002\n"
        "fix typo in readme\n"
    ),
    "silent-s02-wip.txt": (
        "commit 111111111111\n"
        "wip\n"
        "\n"
        "commit 222222222222\n"
        "chore: whitespace\n"
    ),
    "silent-s03-wip.txt": (
        "commit aaaaaaaaaaaa\n"
        "n/a\n"
        "\n"
        "commit bbbbbbbbbbbb\n"
        "merge leftover\n"
    ),
    "silent-empty-docs.txt": (
        "# no published documentation for this planted silent mechanism\n"
    ),
}


def sha256_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET"
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            return int(resp.status), resp.read(), str(resp.geturl())
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url


def ensure_planted() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, text in PLANTED.items():
        path = RAW / name
        if not path.is_file() or path.stat().st_size == 0:
            path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="re-download non-planted rails (default: index existing files)",
    )
    args = parser.parse_args()
    ensure_planted()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    failures = []
    for spec in RAILS:
        cid = spec["id"]
        path = RAW / cid
        kind = spec["kind"]
        permalink = spec["permalink"]
        if args.fetch and kind != "planted-silent-fixture" and permalink.startswith("http"):
            status, body, final = fetch(permalink)
            path.write_bytes(body)
            http_status = status
            final_url = final
            if status != 200 or not body:
                failures.append(cid)
        else:
            if not path.is_file():
                failures.append(cid)
                rows.append(
                    {
                        "id": cid,
                        "kind": kind,
                        "permalink": permalink,
                        "http_status": None,
                        "present": False,
                    }
                )
                continue
            http_status = 200
            final_url = permalink
        raw = path.read_bytes()
        digest, n = sha256_bytes(raw)
        # Preserve prior timestamp when not fetching.
        prev_ts = ts
        if INDEX.is_file() and not args.fetch:
            try:
                old = json.loads(INDEX.read_text(encoding="utf-8"))
                for r in old.get("rails") or []:
                    if r.get("id") == cid and r.get("fetch_timestamp"):
                        prev_ts = r["fetch_timestamp"]
                        break
            except json.JSONDecodeError:
                pass
        rows.append(
            {
                "id": cid,
                "kind": kind,
                "permalink": permalink,
                "final_url": final_url,
                "http_status": http_status,
                "fetch_timestamp": prev_ts,
                "sha256": digest,
                "bytes": n,
                "present": True,
                "path": f"command-center/p2-wave/probes/RES-0181/captures/raw/{cid}",
            }
        )
        print(f"OK {cid} sha256={digest[:12]} bytes={n}")
    INDEX.write_text(
        json.dumps(
            {
                "unit_id": UNIT_ID,
                "user_agent": UA,
                "auth": "none",
                "fetched_at": ts,
                "rails": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        print(f"FAILED:capture {failures}")
        return 1
    print(f"SUCCESS:RES-0181-capture n={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
