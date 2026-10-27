#!/usr/bin/env python3
"""HTML/text normalisation for RES-0140 source items."""
from __future__ import annotations

import html as htmlmod
import re

_SCRIPT = re.compile(r"(?is)<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>")
_COMMENT = re.compile(r"(?is)<!--.*?-->")
_NAV = re.compile(
    r"(?is)<(nav|footer|header|aside|form)[^>]*>.*?</\1>"
)
_ARTICLE = re.compile(r"(?is)<article\b[^>]*>(.*?)</article>")
_MAIN = re.compile(r"(?is)<main\b[^>]*>(.*?)</main>")
_TAG = re.compile(r"(?is)<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")


def _strip_to_text(chunk: str) -> str:
    chunk = re.sub(r"(?is)<br\s*/?>", "\n", chunk)
    chunk = re.sub(r"(?is)</(p|div|h[1-6]|li|tr|section)>", "\n", chunk)
    chunk = _TAG.sub(" ", chunk)
    chunk = htmlmod.unescape(chunk)
    return _clean_plain(chunk)


def html_to_text(raw: str) -> str:
    if "<" not in raw[:2000] and "</" not in raw:
        return _clean_plain(raw)
    body = _SCRIPT.sub(" ", raw)
    body = _COMMENT.sub(" ", body)
    body = _NAV.sub(" ", body)
    candidates = [_strip_to_text(body)]
    for m in _ARTICLE.finditer(body):
        candidates.append(_strip_to_text(m.group(1)))
    for m in _MAIN.finditer(body):
        candidates.append(_strip_to_text(m.group(1)))
    # Prefer the longest extract so a short author-bio <article> cannot win.
    return max(candidates, key=lambda s: len(s))


def _clean_plain(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    lines = [_WS.sub(" ", ln).strip() for ln in text.split("\n")]
    out = "\n".join(lines)
    out = _BLANK.sub("\n\n", out)
    return out.strip()


def bytes_to_text(raw: bytes, content_type: str = "") -> str:
    text = raw.replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
    ctype = (content_type or "").lower()
    looks_html = (
        "html" in ctype
        or text.lstrip()[:32].lower().startswith("<!doctype html")
        or text.lstrip()[:15].lower().startswith("<html")
        or "<article" in text[:12000].lower()
        or "</html>" in text[-4000:].lower()
    )
    if looks_html:
        return html_to_text(text)
    return _clean_plain(text)
