#!/usr/bin/env python3
# RES-0004 content-addressed evidence snapshot store (rebuilt 2026-10-25).
# Store contract (schema res-0004-evidence-snapshot/v1):
#   INDEX.json entries carry url, final_url, http_status, fetch_timestamp,
#   sha256(body), bytes, archive_relpath (content-addressed blob), shape,
#   optional redirect_chain + js_markers/quote anchors.
# A re-check 30 days later re-hashes each blob in a FRESH process and
# classifies: SNAPSHOT-CORRUPT / SOURCE-CHANGED / CLAIM-WAS-WRONG / CLAIM-HOLDS.
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
INDEX_REL = "command-center/research/snapshot-store/INDEX.json"


def load_index():
    return json.loads((REPO / INDEX_REL).read_text(encoding="utf-8"))


def blob_path(entry):
    p = REPO / entry["archive_relpath"]
    if not p.is_file():
        raise FileNotFoundError(entry["archive_relpath"])
    return p


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def rehash_entry(entry):
    p = blob_path(entry)
    b = p.read_bytes()
    digest = sha_bytes(b)
    return {"id": entry["id"], "ok": digest == entry["sha256"] and len(b) == entry["bytes"],
            "sha256": digest, "bytes": len(b)}


def verify_store():
    idx = load_index()
    rows = [rehash_entry(e) for e in idx["entries"]]
    ok = sum(1 for r in rows if r["ok"])
    return {"entries": len(rows), "ok": ok,
            "corrupt": [r["id"] for r in rows if not r["ok"]],
            "all_ok": ok == len(rows) and len(rows) > 0}
