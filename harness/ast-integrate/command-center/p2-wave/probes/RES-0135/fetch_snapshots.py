#!/usr/bin/env python3
"""Fetch official licence texts and compatibility commentaries into snapshots/.

Records resolved URL, HTTP status, fetch timestamp, sha256 of CRLF-normalised bytes.
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

SOURCES = [
    ("apache-2.0.txt", "https://www.apache.org/licenses/LICENSE-2.0.txt"),
    ("gpl-3.0.txt", "https://www.gnu.org/licenses/gpl-3.0.txt"),
    ("agpl-3.0.txt", "https://www.gnu.org/licenses/agpl-3.0.txt"),
    ("mpl-2.0.txt", "https://www.mozilla.org/media/MPL/2.0/index.txt"),
    ("cc-by-4.0.txt", "https://creativecommons.org/licenses/by/4.0/legalcode.txt"),
    ("cc-by-sa-4.0.txt", "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"),
    ("cc0-1.0.txt", "https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt"),
    (
        "mit.txt",
        "https://raw.githubusercontent.com/spdx/license-list-data/main/text/MIT.txt",
    ),
    (
        "bsd-3-clause.txt",
        "https://raw.githubusercontent.com/spdx/license-list-data/main/text/BSD-3-Clause.txt",
    ),
    (
        "fsf-license-list.html",
        "https://www.gnu.org/licenses/license-list.html",
    ),
    (
        "apache-gpl-compatibility.html",
        "https://www.apache.org/licenses/GPL-compatibility.html",
    ),
    (
        "cc-compatible-licenses.html",
        "https://creativecommons.org/share-your-work/licensing-considerations/compatible-licenses/",
    ),
    (
        "cc-by-sa-gplv3-one-way.html",
        "https://creativecommons.org/2015/10/08/cc-by-sa-4-0-now-one-way-compatible-with-gplv3/",
    ),
    (
        "n8n-sustainable-use-LICENSE.md",
        "https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md",
    ),
    (
        "uscode-17-106.html",
        "https://www.law.cornell.edu/uscode/text/17/106",
    ),
]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str) -> tuple[int, str, bytes]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RES-0135-licence-matrix/1.0 (research snapshot)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            body = resp.read()
            final = str(resp.geturl())
            status = int(getattr(resp, "status", 200) or 200)
            return status, final, body
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), url, body


def main() -> int:
    SNAP.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, url in SOURCES:
        t0 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status, final, body = fetch(url)
        path = SNAP / name
        path.write_bytes(body)
        rec = {
            "id": name,
            "requested_url": url,
            "resolved_url": final,
            "http_status": status,
            "fetch_timestamp": t0,
            "sha256": digest(body),
            "bytes": len(body.replace(b"\r\n", b"\n")),
            "snapshot": f"command-center/p2-wave/probes/RES-0135/snapshots/{name}",
        }
        rows.append(rec)
        print(f"{status} {name} sha256={rec['sha256'][:12]} bytes={rec['bytes']}")
        time.sleep(0.4)
    cap = {
        "unit_id": "RES-0135",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rails": rows,
    }
    (SNAP / "CAPTURE.json").write_text(
        json.dumps(cap, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bad = [r for r in rows if r["http_status"] != 200 or r["bytes"] < 200]
    if bad:
        print("FAILED:RES-0135 fetch", json.dumps(bad, indent=2))
        return 1
    print("SUCCESS:RES-0135 snapshots fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
