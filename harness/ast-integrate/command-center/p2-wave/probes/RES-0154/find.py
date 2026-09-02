#!/usr/bin/env python3
"""Volume finder. Does not import refute predicates."""
from __future__ import annotations

import json

from util import REPO


def finder_findings(rel: str) -> list[dict]:
    raw = (REPO / rel).read_text(encoding="utf-8")
    doc = json.loads(raw)
    out: list[dict] = []
    if isinstance(doc, dict):
        for key in doc.keys():
            out.append(
                {
                    "kind": "key-inventory",
                    "rel": rel,
                    "key": str(key),
                    "detail": "top-level key present",
                }
            )
    out.append(
        {
            "kind": "byte-count",
            "rel": rel,
            "bytes": len(raw.encode("utf-8")),
            "detail": "non-empty JSON document",
        }
    )
    return out
