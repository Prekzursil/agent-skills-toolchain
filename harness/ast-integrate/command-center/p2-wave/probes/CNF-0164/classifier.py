#!/usr/bin/env python3
"""Quote-fidelity classifier for CNF-0164.

Classes (after CRLF/CR -> LF normalisation):
  exact                 quote is a contiguous substring of the source
  whitespace-different  not exact, but equal after collapsing all whitespace
  paraphrase            not the above; a same-length token window differs by
                        exactly one token (the catalog's one-word-altered case)
  absent                source was loaded and no window matches
  NOT-CHECKED           source could not be loaded (external URL without a
                        citation-time archive, missing path, empty source)

Absent is never returned unless a known-present probe quote is exact in the
same source (detector self-check). If that self-check fails, the class is
NOT-CHECKED with reason detector-untrusted.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

WORD_RE = re.compile(r"[A-Za-z0-9_]+")
WS_RE = re.compile(r"\s+")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARCHIVE_INDEX = HERE / "archives" / "index.json"


def eol_norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ws_collapse(text: str) -> str:
    return WS_RE.sub(" ", eol_norm(text)).strip()


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(eol_norm(text))]


def is_url(path: str) -> bool:
    p = path.strip().lower()
    return p.startswith("http://") or p.startswith("https://")


def load_archive_index() -> dict[str, Any]:
    if not ARCHIVE_INDEX.is_file():
        return {"archives": []}
    try:
        doc = json.loads(ARCHIVE_INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"archives": []}
    return doc if isinstance(doc, dict) else {"archives": []}


def archive_for_url(url: str) -> Path | None:
    idx = load_archive_index()
    for row in idx.get("archives") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("url") or "").strip() == url.strip():
            rel = str(row.get("path") or "").strip()
            if not rel:
                continue
            cand = (REPO / rel) if not Path(rel).is_absolute() else Path(rel)
            if cand.is_file():
                return cand
    return None


def known_present_slice(source: str) -> str | None:
    """A copy-pastable slice that must classify exact if the matcher works."""
    for line in eol_norm(source).split("\n"):
        stripped = line.strip()
        if len(stripped) >= 24:
            return stripped
    body = eol_norm(source).strip()
    if len(body) >= 24:
        return body[:80]
    return None


def token_hamming_one(quote: str, source: str) -> bool:
    qtoks = tokens(quote)
    stoks = tokens(source)
    n = len(qtoks)
    if n < 3 or len(stoks) < n:
        return False
    for i in range(len(stoks) - n + 1):
        window = stoks[i : i + n]
        dist = sum(a != b for a, b in zip(qtoks, window))
        if dist == 1:
            return True
    return False


def classify_loaded(quote: str, source: str) -> str:
    q = eol_norm(quote)
    s = eol_norm(source)
    if q and q in s:
        return "exact"
    qws, sws = ws_collapse(quote), ws_collapse(source)
    if qws and qws in sws:
        return "whitespace-different"
    if token_hamming_one(quote, source):
        return "paraphrase"
    return "absent"


def classify_against_text(quote: str, source: str) -> dict[str, Any]:
    """Classify with detector self-check before any absent verdict."""
    if not source:
        return {
            "class": "NOT-CHECKED",
            "reason": "source-empty",
            "detector_self_check": False,
        }
    present = known_present_slice(source)
    self_ok = bool(present) and classify_loaded(present, source) == "exact"
    klass = classify_loaded(quote, source)
    if klass == "absent" and not self_ok:
        return {
            "class": "NOT-CHECKED",
            "reason": "detector-untrusted",
            "detector_self_check": False,
            "known_present_probe": present,
        }
    return {
        "class": klass,
        "reason": "matched" if klass != "absent" else "no-window",
        "detector_self_check": self_ok,
        "known_present_probe": present,
    }


def load_source(source_path: str) -> dict[str, Any]:
    """Resolve a cited source. Never fetches the live network."""
    path = (source_path or "").strip()
    if not path:
        return {
            "ok": False,
            "text": "",
            "resolution": "empty-path",
            "reason": "source path is empty",
        }
    if is_url(path):
        archived = archive_for_url(path)
        if archived is None:
            return {
                "ok": False,
                "text": "",
                "resolution": "external-no-archive",
                "reason": (
                    "external URL has no citation-time archive in "
                    "probes/CNF-0164/archives/"
                ),
            }
        try:
            text = archived.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return {
                "ok": False,
                "text": "",
                "resolution": "archive-unreadable",
                "reason": f"{type(exc).__name__}",
            }
        return {
            "ok": True,
            "text": text,
            "resolution": "citation-time-archive",
            "reason": str(archived.relative_to(REPO).as_posix()),
        }
    cand = REPO / path
    if not cand.is_file():
        return {
            "ok": False,
            "text": "",
            "resolution": "path-missing",
            "reason": f"worktree file missing: {path}",
        }
    try:
        text = cand.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "ok": False,
            "text": "",
            "resolution": "path-unreadable",
            "reason": f"{type(exc).__name__}",
        }
    return {
        "ok": True,
        "text": text,
        "resolution": "worktree",
        "reason": "git repository absent; CNF-0163 artifact absent; worktree bytes after EOL norm",
    }


def classify_quote(quote: str, source_path: str) -> dict[str, Any]:
    loaded = load_source(source_path)
    if not loaded["ok"]:
        return {
            "class": "NOT-CHECKED",
            "reason": loaded["reason"],
            "resolution": loaded["resolution"],
            "detector_self_check": None,
        }
    out = classify_against_text(quote, loaded["text"])
    out["resolution"] = loaded["resolution"]
    return out


def reviewer_classify_loaded(quote: str, source: str) -> str:
    """Second implementation: per-line indent strip + collapse, then token hamming.

    Independent of classify_loaded's first exact-substring branch order only in
    the whitespace path (line-lstrip vs global collapse). Exact still uses
    substring after EOL norm so the two must agree on copy-pasted quotes.
    """
    q = eol_norm(quote)
    s = eol_norm(source)
    if q and q in s:
        return "exact"

    def indent_strip(text: str) -> str:
        return "\n".join(line.lstrip(" \t") for line in eol_norm(text).split("\n"))

    qi, si = indent_strip(quote), indent_strip(source)
    if qi.strip() and qi.strip() in si:
        return "whitespace-different"
    if ws_collapse(quote) and ws_collapse(quote) in ws_collapse(source):
        return "whitespace-different"
    if token_hamming_one(quote, source):
        return "paraphrase"
    return "absent"


def reviewer_classify_quote(quote: str, source_path: str) -> dict[str, Any]:
    loaded = load_source(source_path)
    if not loaded["ok"]:
        return {
            "class": "NOT-CHECKED",
            "reason": loaded["reason"],
            "resolution": loaded["resolution"],
        }
    present = known_present_slice(loaded["text"])
    self_ok = bool(present) and reviewer_classify_loaded(present, loaded["text"]) == "exact"
    klass = reviewer_classify_loaded(quote, loaded["text"])
    if klass == "absent" and not self_ok:
        return {
            "class": "NOT-CHECKED",
            "reason": "detector-untrusted",
            "resolution": loaded["resolution"],
        }
    return {
        "class": klass,
        "reason": "reviewer-matched" if klass != "absent" else "reviewer-no-window",
        "resolution": loaded["resolution"],
    }
