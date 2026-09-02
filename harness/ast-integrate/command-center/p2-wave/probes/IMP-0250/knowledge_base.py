#!/usr/bin/env python3
"""knowledge-base-construction: inverted index over normalized cells.

Tokens come from already-normalized fields so a planted US cannot split a
title into two index keys.
"""
from __future__ import annotations

from typing import Any

import extract_normalize as en


def build(rows: list[list[bytes]]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        for cell in row:
            token = cell.decode("utf-8", "replace")
            if not token:
                continue
            bucket = index.setdefault(token, [])
            if i not in bucket:
                bucket.append(i)
    return index


def lookup(index: dict[str, list[int]], token: str) -> list[int]:
    return list(index.get(token, []))


def smoke() -> dict[str, Any]:
    rows = en.parse_table(en.planted_fixture())
    index = build(rows)
    # Normalized title is one token; the US must not mint "widget" / "deluxe" keys.
    has_joined = "widgetdeluxe" in index
    split_keys = ("widget" in index) or ("deluxe" in index)
    naive_index = build(en.parse_table_naive(en.planted_fixture()))
    naive_split = ("widget" in naive_index) and ("deluxe" in naive_index)
    ok = has_joined and not split_keys and naive_split
    return {
        "ok": ok,
        "joined_present": has_joined,
        "fixed_split_keys": split_keys,
        "naive_split_keys": naive_split,
        "hits": lookup(index, "widgetdeluxe"),
    }
