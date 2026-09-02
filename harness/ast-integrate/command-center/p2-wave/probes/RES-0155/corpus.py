#!/usr/bin/env python3
"""Frozen shared corpus for RES-0155.

Every lens reads the same fetched snapshot set (RES-0137 community-tool
docs). Lens is the only varying factor. Hashes are re-checked on load.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP_ROOT = REPO / "command-center/p2-wave/probes/RES-0137"
INDEX_SRC = SNAP_ROOT / "sources_index.json"

# Document-dropout noise floor. Canonical run uses every ok snapshot.
DROP_N = 2
SEED_A = 17
SEED_B = 23


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def eol_twin_matches(raw: bytes, recorded: str) -> bool:
    """True when raw is byte-identical to the recorded capture modulo CRLF/LF.

    Git normalises text fixtures to LF on checkout (harness .gitattributes), so a
    snapshot fetched with CRLF hashes differently from its recorded lineage even
    though no character changed. Only a reconstruction that hashes to the
    recorded digest is accepted, so real content drift still fails.
    """
    if sha256_bytes(raw) == recorded:
        return True
    lf = raw.replace(b"\r\n", b"\n")
    if sha256_bytes(lf) == recorded:
        return True
    return sha256_bytes(lf.replace(b"\n", b"\r\n")) == recorded


def load_index() -> list[dict[str, Any]]:
    rows = json.loads(INDEX_SRC.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("ok"):
            continue
        rel = str(row.get("path") or "")
        path = SNAP_ROOT / rel
        if not path.is_file():
            raise SystemExit(f"corpus missing {rel}")
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        if not eol_twin_matches(raw, str(row.get("sha256") or "")):
            raise SystemExit(f"corpus hash drift {row.get('id')}")
        text = raw.decode("utf-8", "replace")
        out.append(
            {
                "id": str(row["id"]),
                "path": f"command-center/p2-wave/probes/RES-0137/{rel}",
                "resolved_url": str(row.get("resolved_url") or ""),
                "requested_url": str(row.get("requested_url") or ""),
                "fetched_at": str(row.get("fetched_at") or ""),
                "http_status": int(row.get("status") or 200),
                "sha256": digest,
                "bytes": len(raw),
                "text": text,
            }
        )
    out.sort(key=lambda r: r["id"])
    if len(out) < 10:
        raise SystemExit(f"corpus too small n={len(out)}")
    return out


def corpus_fingerprint(docs: list[dict[str, Any]] | None = None) -> str:
    rows = docs if docs is not None else load_index()
    blob = "\n".join(f"{r['id']}:{r['sha256']}" for r in rows).encode("utf-8")
    return sha256_bytes(blob)


def active_docs(docs: list[dict[str, Any]], seed: int | None) -> list[dict[str, Any]]:
    if seed is None or DROP_N <= 0 or len(docs) <= DROP_N:
        return list(docs)
    import random

    rng = random.Random(seed)
    ids = [d["id"] for d in docs]
    dropped = set(rng.sample(ids, DROP_N))
    return [d for d in docs if d["id"] not in dropped]


def blob_of(docs: list[dict[str, Any]]) -> str:
    return "\n".join(d["text"] for d in docs)


def by_id(docs: list[dict[str, Any]], sid: str) -> dict[str, Any]:
    for row in docs:
        if row["id"] == sid:
            return row
    raise KeyError(sid)
