#!/usr/bin/env python3
"""Deterministic HTML/text extraction. No labels, no URLs in the output text."""
from __future__ import annotations

import html
import re

SCRIPT_RE = re.compile(rb"(?is)<script\b[^>]*>.*?</script>")
STYLE_RE = re.compile(rb"(?is)<style\b[^>]*>.*?</style>")
NOSCRIPT_RE = re.compile(rb"(?is)<noscript\b[^>]*>.*?</noscript>")
COMMENT_RE = re.compile(rb"(?is)<!--.*?-->")
TAG_RE = re.compile(rb"(?is)<[^>]+>")
WS_RE = re.compile(r"[ \t\f\v]+")


def decode_body(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def html_to_text(raw: bytes) -> str:
    blob = SCRIPT_RE.sub(b" ", raw)
    blob = STYLE_RE.sub(b" ", blob)
    blob = NOSCRIPT_RE.sub(b" ", blob)
    blob = COMMENT_RE.sub(b" ", blob)
    blob = TAG_RE.sub(b" ", blob)
    text = decode_body(blob)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = WS_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def looks_like_html(raw: bytes) -> bool:
    head = raw[:4096].lower()
    return b"<html" in head or b"<!doctype html" in head or b"<head" in head


def body_text(raw: bytes) -> str:
    if looks_like_html(raw):
        return html_to_text(raw)
    return decode_body(raw).replace("\r\n", "\n").replace("\r", "\n")
