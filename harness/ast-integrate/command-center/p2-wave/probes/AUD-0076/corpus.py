"""Locate the Prompt-One transcript or build the on-tree owner corpus."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from common import CATALOG, PLANTED_TEXT, REPO, TRANSCRIPT_CANDIDATES


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_existing(rel_or_abs: str) -> Path | None:
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = REPO / rel_or_abs
    if p.is_file() and p.stat().st_size > 0:
        return p
    return None


def locate_transcript() -> dict[str, Any]:
    tried = []
    for cand in TRANSCRIPT_CANDIDATES:
        tried.append(cand)
        found = resolve_existing(cand)
        if found is not None:
            raw = found.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            try:
                rel = found.resolve().relative_to(REPO.resolve()).as_posix()
            except ValueError:
                rel = str(found)
            return {
                "found": True,
                "path": rel,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                "source": "transcript-file",
                "tried": tried,
                "text": text,
            }
    return {
        "found": False,
        "path": None,
        "bytes": 0,
        "sha256": None,
        "source": "catalog-owner-corpus",
        "tried": tried,
        "text": "",
    }


def _quote_block(label: str, body: str) -> str:
    return f"## {label}\n{body.strip()}\n"


def build_catalog_owner_corpus(catalog: dict) -> str:
    """Recoverable owner-utterance surface when _USER-PROMPTS.md is absent.

    Concatenates answered and open owner_questions plus DROPPED-BY-OWNER and
    SUPERSEDED catalog items that quote the owner. This is not the 375-message
    file; callers must disclose that.
    """
    parts = [
        "# AUD-0076 recoverable owner corpus (catalog quotes; not the 1.49 MB transcript)\n"
    ]
    for q in catalog.get("owner_questions") or []:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or "")
        st = str(q.get("state") or "")
        text = str(q.get("text") or "")
        answer = str(q.get("answer") or "")
        detail = str(q.get("answer_detail") or "")
        prov = str(q.get("answer_provenance") or "")
        body = (
            f"id={qid} state={st}\nquestion: {text}\n"
            f"answer: {answer}\ndetail: {detail}\nprovenance: {prov}\n"
        )
        parts.append(_quote_block(f"owner_question {qid}", body))
    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        disp = str(item.get("disposition") or "")
        if disp not in {"DROPPED-BY-OWNER", "SUPERSEDED"}:
            continue
        iid = str(item.get("id") or "")
        ev = str(item.get("disposition_evidence") or item.get("evidence") or "")
        title = str(item.get("title") or "")
        body = f"id={iid} disposition={disp}\ntitle: {title}\nevidence: {ev}\n"
        parts.append(_quote_block(f"catalog_item {iid}", body))
    return "\n".join(parts)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def owner_surface() -> dict[str, Any]:
    loc = locate_transcript()
    catalog = load_catalog()
    surrogate = build_catalog_owner_corpus(catalog)
    if loc["found"]:
        surface = loc["text"]
        source = "transcript-file"
        path = loc["path"]
    else:
        surface = surrogate
        source = "catalog-owner-corpus"
        path = CATALOG.relative_to(REPO).as_posix()
    return {
        "locator": {k: v for k, v in loc.items() if k != "text"},
        "catalog": catalog,
        "surface_text": surface,
        "surrogate_text": surrogate,
        "source": source,
        "path": path,
        "surface_sha256": sha256_text(surface),
        "surface_bytes": len(surface.encode("utf-8")),
    }


def scratch_with_plant(surface_text: str) -> str:
    return surface_text.rstrip() + "\n\n## PLANTED-CONTROL\n" + PLANTED_TEXT + "\n"
