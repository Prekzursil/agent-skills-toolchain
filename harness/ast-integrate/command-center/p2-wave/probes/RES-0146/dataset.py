#!/usr/bin/env python3
"""Load frozen captures into scoring rows. Labels come from INDEX provenance."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import CAPTURE_DIR, N_DOCS, N_PER_CLASS, load_index  # noqa: E402
from textutil import body_text  # noqa: E402


def load_docs() -> list[dict]:
    index = load_index()
    docs = []
    for row in index["documents"]:
        path = CAPTURE_DIR / row["file"]
        raw = path.read_bytes()
        if row.get("sha256"):
            import hashlib

            live = hashlib.sha256(raw).hexdigest()
            if live != row["sha256"]:
                raise AssertionError(f"capture-sha-mismatch {row['id']}")
        text = row.get("text") or body_text(raw)
        docs.append(
            {
                "id": row["id"],
                "label": row["label"],
                "text": text,
                "permalink": row["permalink"],
                "fetch_timestamp": row["fetch_timestamp"],
                "http_status": row["http_status"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "path": row["path"],
                "provenance_kind": row["provenance_kind"],
                "provenance_basis": row["provenance_basis"],
                "source_class": row.get("source_class") or row["label"],
            }
        )
    return docs


def assert_corpus_shape(docs: list[dict]) -> None:
    if len(docs) != N_DOCS:
        raise AssertionError(f"n={len(docs)} want={N_DOCS}")
    n_mill = sum(1 for d in docs if d["label"] == "mill")
    n_prac = sum(1 for d in docs if d["label"] == "practitioner")
    if n_mill != N_PER_CLASS or n_prac != N_PER_CLASS:
        raise AssertionError(f"class-split mill={n_mill} practitioner={n_prac}")
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise AssertionError("duplicate-doc-ids")
    for d in docs:
        if len(d["text"].strip()) < 40:
            raise AssertionError(f"thin-body {d['id']}")
        if d["http_status"] != 200:
            raise AssertionError(f"bad-status {d['id']} {d['http_status']}")
        if len(d["sha256"]) != 64:
            raise AssertionError(f"bad-sha {d['id']}")
        if not d["permalink"]:
            raise AssertionError(f"missing-permalink {d['id']}")
        if not d["provenance_basis"]:
            raise AssertionError(f"missing-provenance {d['id']}")
