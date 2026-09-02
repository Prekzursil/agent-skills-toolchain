#!/usr/bin/env python3
"""Load five prior P2-wave research/measurement documents as ordered source runs.

These files existed on this worktree before RES-0151. Each ## / ### heading is
one source; claims are extracted from the section body (not simulated).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

HISTORICAL_RUNS: tuple[tuple[str, str], ...] = (
    ("P2-GROUNDING", "command-center/p2-wave/P2-GROUNDING.md"),
    ("P2-BUILD-ROUND1", "command-center/p2-wave/P2-BUILD-ROUND1.md"),
    ("P2-BUILD-ROUND2", "command-center/p2-wave/P2-BUILD-ROUND2.md"),
    ("P2-BUILD-ROUND3", "command-center/p2-wave/P2-BUILD-ROUND3.md"),
    ("P2-INTEGRATE", "command-center/p2-wave/P2-INTEGRATE.md"),
)

HEADING_RE = re.compile(r"^(#{2,3}) (.+)$", re.M)
FENCE_RE = re.compile(r"```.*?```", re.S)
SENTENCE_RE = re.compile(r"[^.!?\n]{24,}[.!?]")
KEYWORD_RE = re.compile(
    r"\b(REFUTED|CONFIRMED|MEASURED|SUCCESS|FAILED|BLOCKED|NOT-CHECKED|"
    r"INVALID|VALID|DELIVERED|READY|SILENT|FIRES?)\b",
    re.I,
)


def _sha256_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _mtime_iso(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_md(text: str) -> str:
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sections(text: str) -> list[dict[str, str]]:
    matches = list(HEADING_RE.finditer(text))
    sections: list[dict[str, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        heading = match.group(2).strip()
        body = text[match.end() : end]
        sections.append({"heading": heading, "body": body, "raw": text[match.start() : end]})
    return sections


def extract_claim_texts(heading: str, body: str) -> list[str]:
    """Deterministic claim harvest from one already-written section."""
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = _strip_md(raw)
        if len(text) < 24:
            return
        if text in seen:
            return
        seen.add(text)
        found.append(text)

    add(heading)
    unfenced = FENCE_RE.sub(" ", body)
    for line in unfenced.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and set(cells[0]) <= set("-: "):
                continue
            add(" — ".join(c for c in cells if c))
            continue
        bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", stripped)
        if bullet:
            add(bullet.group(1))
            continue
        for bold in re.findall(r"\*\*([^*]{24,180})\*\*", stripped):
            add(bold)
        if KEYWORD_RE.search(stripped):
            add(stripped)

    for sent in SENTENCE_RE.findall(unfenced):
        if KEYWORD_RE.search(sent):
            add(sent)

    if not found:
        add(heading + " (section present; no longer extractable sentence)")
    return found[:12]


def load_run(run_id: str, rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    text = path.read_text(encoding="utf-8")
    file_sha = _sha256_text(text)
    fetched = _mtime_iso(path)
    url = path.resolve().as_uri()
    sources: list[dict[str, Any]] = []
    for i, section in enumerate(split_sections(text), 1):
        claims = [
            {"text": c, "kind": "extracted-from-prior-document"}
            for c in extract_claim_texts(section["heading"], section["body"])
        ]
        src_sha = _sha256_text(section["raw"])
        slug = re.sub(r"[^a-z0-9]+", "-", section["heading"].lower()).strip("-")[:80]
        sources.append(
            {
                "source_id": f"{run_id}#{i:02d}-{slug}",
                "index": i,
                "heading": section["heading"],
                "path": rel,
                "resolved_url": f"{url}#{slug}",
                "fetch_timestamp": fetched,
                "sha256": src_sha,
                "file_sha256": file_sha,
                "sherman_kent_band": "likely",
                "claims": claims,
            }
        )
    if len(sources) < 5:
        raise RuntimeError(f"{rel} yielded only {len(sources)} sources; need >=5")
    return {
        "run_id": run_id,
        "path": rel,
        "resolved_url": url,
        "fetch_timestamp": fetched,
        "file_sha256": file_sha,
        "bytes": len(text.replace("\r\n", "\n").encode("utf-8")),
        "n_sources": len(sources),
        "sources": sources,
        "corpus_class": "real-prior-document",
    }


def load_historical_runs() -> list[dict[str, Any]]:
    return [load_run(run_id, rel) for run_id, rel in HISTORICAL_RUNS]
