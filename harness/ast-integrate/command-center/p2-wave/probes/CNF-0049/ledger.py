"""Byte-prefix and prefix-hash checks for an append-only JSONL ledger.

The prefix check is exact bytes, not parsed JSON: a rewritten timestamp inside
a retained line must change the prefix hash even when the line count is
unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def normalize(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def encode_event(payload: dict[str, Any]) -> str:
    """Match tools/command-center/close.py:append_event serialization."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"


def split_lines(raw: bytes) -> list[bytes]:
    text = normalize(raw)
    if not text:
        return []
    parts = text.split(b"\n")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return [p + b"\n" for p in parts]


def line_count(raw: bytes) -> int:
    return len(split_lines(raw))


def is_byte_prefix(pre: bytes, post: bytes) -> bool:
    pre_n = normalize(pre)
    post_n = normalize(post)
    return post_n.startswith(pre_n)


def prefix_hash(raw: bytes, n_bytes: int | None = None) -> str:
    body = normalize(raw)
    if n_bytes is None:
        n_bytes = len(body)
    return sha256_bytes(body[:n_bytes])


def snap(raw: bytes, prefix_n: int | None = None) -> dict[str, Any]:
    body = normalize(raw)
    n = len(body) if prefix_n is None else prefix_n
    return {
        "bytes": len(body),
        "line_count": line_count(body),
        "content_sha256": sha256_bytes(body),
        "prefix_hash": prefix_hash(body, n),
    }


def truncate_one_line(raw: bytes) -> bytes:
    lines = split_lines(raw)
    if len(lines) < 2:
        raise ValueError("need at least two lines to truncate one")
    return b"".join(lines[:-1])


def rewrite_timestamp_in_retained_line(raw: bytes, line_index: int = 0) -> bytes:
    """In-place edit of one retained JSONL line's ts field. Line count unchanged."""
    lines = split_lines(raw)
    if line_index < 0 or line_index >= len(lines):
        raise IndexError(line_index)
    obj = json.loads(lines[line_index].decode("utf-8"))
    if not isinstance(obj, dict) or "ts" not in obj:
        raise ValueError("retained line has no ts field")
    obj["ts"] = "1999-01-01T00:00:00+00:00"
    lines[line_index] = encode_event(obj).encode("utf-8")
    return b"".join(lines)


def retained_prefix_diff(pre: bytes, post: bytes) -> list[str]:
    """Human-readable diff of the bytes that should have been preserved."""
    pre_n = normalize(pre)
    post_n = normalize(post)
    if post_n.startswith(pre_n):
        return []
    kept = post_n[: len(pre_n)]
    if kept == pre_n:
        return []
    out: list[str] = []
    if len(post_n) < len(pre_n):
        out.append(f"post shorter than pre: post={len(post_n)} pre={len(pre_n)}")
    for i, (a, b) in enumerate(zip(pre_n, kept)):
        if a != b:
            out.append(f"first differing byte offset={i} pre={a} post={b}")
            break
    pre_lines = split_lines(pre_n)
    post_lines = split_lines(kept)
    for i, (pl, ql) in enumerate(zip(pre_lines, post_lines)):
        if pl != ql:
            out.append(f"line[{i}] pre={pl.decode('utf-8', 'replace').rstrip()}")
            out.append(f"line[{i}] post={ql.decode('utf-8', 'replace').rstrip()}")
            break
    return out
