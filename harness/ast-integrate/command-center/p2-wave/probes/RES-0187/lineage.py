"""Live hashes of captures and local files. Never trusts a remembered digest."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from contract import CATALOG_SNIPPET, HERE, HEDGE_RULE, REPO, UNIT

CAP = HERE / "captures"

CAPTURES = {
    "wep-wikipedia": {
        "requested_url": "https://en.wikipedia.org/wiki/Words_of_estimative_probability",
        "resolved_url": "https://en.wikipedia.org/wiki/Words_of_estimative_probability",
        "http_status": 200,
        "snippet": '<td id="mwLg">Almost certain</td>',
    },
    "kent-wep-wayback": {
        "requested_url": (
            "https://web.archive.org/web/20070613122040/https://www.cia.gov/library/"
            "center-for-the-study-of-intelligence/csi-publications/books-and-monographs/"
            "sherman-kent-and-the-board-of-national-estimates-collected-essays/6words.html"
        ),
        "resolved_url": (
            "https://web.archive.org/web/20070613122040/https://www.cia.gov/library/"
            "center-for-the-study-of-intelligence/csi-publications/books-and-monographs/"
            "sherman-kent-and-the-board-of-national-estimates-collected-essays/6words.html"
        ),
        "http_status": 200,
        "snippet": "<td>Almost certain</td>",
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> tuple[str, int, bytes]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw), raw


def iso_mtime(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_capture(capture_id: str) -> dict:
    spec = CAPTURES[capture_id]
    path = CAP / f"{capture_id}.raw"
    if not path.is_file():
        raise FileNotFoundError(capture_id)
    sha, nbytes, raw = digest_file(path)
    text = raw.decode("utf-8", errors="replace")
    snippet = spec["snippet"]
    if snippet not in text:
        raise AssertionError(f"snippet absent from {capture_id}: {snippet!r}")
    return {
        "id": capture_id,
        "path": path.relative_to(REPO).as_posix(),
        "sha256": sha,
        "bytes": nbytes,
        "text": text,
        "fetched_at": iso_mtime(path),
        "url": spec["resolved_url"],
        "requested_url": spec["requested_url"],
        "http_status": spec["http_status"],
        "snippet": snippet,
    }


def file_signal(rel: str, snippet: str, sid: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    sha, nbytes, raw = digest_file(path)
    text = raw.decode("utf-8", errors="replace")
    if snippet not in text:
        raise AssertionError(f"snippet absent from {rel}: {snippet[:80]!r}")
    return {
        "id": sid,
        "url": "file://" + str(path.resolve()),
        "resolved_url": "file://" + str(path.resolve()),
        "fetched_at": now_iso(),
        "sha256": sha,
        "bytes": nbytes,
        "capture_id": Path(rel).name,
        "path": rel,
        "snippet": snippet,
        "http_status": 200,
    }


def capture_signal(capture_id: str, sid: str) -> dict:
    cap = load_capture(capture_id)
    return {
        "id": sid,
        "url": cap["url"],
        "resolved_url": cap["url"],
        "fetched_at": cap["fetched_at"],
        "sha256": cap["sha256"],
        "bytes": cap["bytes"],
        "capture_id": capture_id,
        "path": cap["path"],
        "snippet": cap["snippet"],
        "http_status": cap["http_status"],
    }


def catalog_unit_signal(sid: str) -> dict:
    rel = "command-center/WORK-UNIT-CATALOG.json"
    sig = file_signal(rel, CATALOG_SNIPPET, sid)
    # Confirm the hedge rule is in the same unit block.
    text = (REPO / rel).read_text(encoding="utf-8")
    if f'"id": "{UNIT}"' not in text:
        raise AssertionError("catalog missing RES-0187")
    if HEDGE_RULE not in text:
        raise AssertionError("catalog missing hedge rule")
    return sig


def write_source_lineage() -> dict:
    rows = []
    for cid in CAPTURES:
        cap = load_capture(cid)
        rows.append(
            {
                "id": cid,
                "requested_url": cap["requested_url"],
                "resolved_url": cap["url"],
                "fetched_at": cap["fetched_at"],
                "http_status": cap["http_status"],
                "sha256": cap["sha256"],
                "bytes": cap["bytes"],
                "path": cap["path"],
            }
        )
    doc = {"unit_id": UNIT, "sources": rows}
    (HERE / "source-lineage.json").write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc
