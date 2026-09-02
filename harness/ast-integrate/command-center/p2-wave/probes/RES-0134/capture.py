#!/usr/bin/env python3
"""Snapshot cited primary sources into captures/ with sha256 lineage."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
STAGING = Path("/tmp/res0134-cap")

SOURCES = [
    {
        "id": "rb-archives",
        "url": "https://reproducible-builds.org/docs/archives/",
        "staging": "archives.bin",
        "role": "prose",
        "quote": "file ordering",
        "supports": ["archive-member-order", "mtimes"],
    },
    {
        "id": "rb-timestamps",
        "url": "https://reproducible-builds.org/docs/timestamps/",
        "staging": "timestamps.bin",
        "role": "prose",
        "quote": "SOURCE_DATE_EPOCH",
        "supports": ["mtimes"],
    },
    {
        "id": "rb-sde-spec",
        "url": "https://reproducible-builds.org/specs/source-date-epoch/",
        "staging": "sde-spec.bin",
        "role": "spec",
        "quote": "SOURCE_DATE_EPOCH",
        "supports": ["mtimes"],
    },
    {
        "id": "rb-stable-inputs",
        "url": "https://reproducible-builds.org/docs/stable-inputs/",
        "staging": "stable-inputs.bin",
        "role": "prose",
        "quote": "sort",
        "supports": ["archive-member-order"],
    },
    {
        "id": "pkware-appnote",
        "url": "https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT",
        "staging": "appnote.bin",
        "role": "spec",
        "quote": "MUST be forward slashes",
        "supports": ["path-separators"],
    },
    {
        "id": "cpython-zipfile-v3123",
        "url": "https://raw.githubusercontent.com/python/cpython/v3.12.3/Lib/zipfile/__init__.py",
        "staging": "cpython-zipfile.bin",
        "role": "code",
        "quote": "self.create_system = 0",
        "supports": ["zip-create-system"],
    },
    {
        "id": "cpython-zipfile-local",
        "url": "file:///usr/lib/python3.12/zipfile/__init__.py",
        "staging": "cpython-local-zipfile.py",
        "role": "code",
        "quote": "self.create_system = 0",
        "supports": ["zip-create-system"],
    },
    {
        "id": "python-zipfile-docs",
        "url": "https://docs.python.org/3/library/zipfile.html",
        "staging": "zipfile-docs.bin",
        "role": "prose",
        "quote": "ZipInfo",
        "supports": ["mtimes"],
    },
    {
        "id": "unicode-tr15",
        "url": "https://www.unicode.org/reports/tr15/",
        "staging": "tr15.bin",
        "role": "spec",
        "quote": "Normalization Form C",
        "supports": ["unicode-path-casing"],
    },
    {
        "id": "ms-wsl-case-md",
        "url": "https://raw.githubusercontent.com/MicrosoftDocs/WSL/live/WSL/case-sensitivity.md",
        "staging": "ms-wsl-case.md",
        "role": "prose",
        "quote": "case-insensitive",
        "supports": ["unicode-path-casing"],
    },
]


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def fetch(url: str, timeout: int = 40) -> tuple[bytes, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "RES-0134-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", 200) or 200
        return resp.read(), int(status)


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for src in SOURCES:
        dest = CAP / f"{src['id']}.bin"
        blob = None
        status = None
        origin = None
        staged = STAGING / src["staging"]
        if staged.is_file():
            blob = staged.read_bytes()
            status = 200
            origin = f"staging:{staged}"
        elif src["url"].startswith("file://"):
            blob = Path(src["url"][7:]).read_bytes()
            status = 200
            origin = src["url"]
        else:
            blob, status = fetch(src["url"])
            origin = src["url"]
        dest.write_bytes(blob)
        text = blob.decode("utf-8", "replace")
        quote_ok = src["quote"].encode("utf-8") in blob or src["quote"] in text
        cap_rel = dest.relative_to(REPO).as_posix()
        rows.append(
            {
                "id": src["id"],
                "requested_url": src["url"],
                "resolved_url": src["url"],
                "fetched_at": now,
                "http_status": status,
                "sha256": sha256_bytes(blob),
                "bytes": len(blob),
                "capture_path": cap_rel,
                "role": src["role"],
                "quote": src["quote"],
                "quote_found": bool(quote_ok),
                "supports": src["supports"],
                "origin": origin,
            }
        )
        print(f"{src['id']} status={status} bytes={len(blob)} quote_found={quote_ok}")
    index = {"unit_id": "RES-0134", "captured_at": now, "sources": rows}
    (CAP / "_index.json").write_text(
        json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("SUCCESS:RES-0134-capture", len(rows), "sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
