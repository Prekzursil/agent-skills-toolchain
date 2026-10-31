"""Discovery adapter for documentation / papers / transcripts."""
from __future__ import annotations

import re
from typing import Any, Iterable

USE_RE = re.compile(r"\b(we use|using|implements|implemented|calls|invokes)\b", re.I)
MENTION_RE = re.compile(r"\b(consider|might use|similar to|inspired by|see also)\b", re.I)


def norm_id(value: str) -> str:
    return str(value).strip().lower().replace(" ", "-")


def naive_keyword_hits(text: str) -> list[dict[str, Any]]:
    hits = []
    for m in re.finditer(r"\b[A-Z]{2,5}-\d{4}\b", text):
        hits.append({"id": m.group(0), "kind": "keyword"})
    for m in re.finditer(r"\b(workflow|adapter|protocol)\b", text, re.I):
        hits.append({"id": m.group(0).lower(), "kind": "keyword"})
    return hits


def mine_text(
    text: str,
    *,
    source_path: str,
    implemented: Iterable[str],
    distinguish_use_mention: bool = True,
) -> list[dict[str, Any]]:
    implemented_n = {norm_id(x) for x in implemented}
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        mention = bool(MENTION_RE.search(line))
        use = bool(USE_RE.search(line))
        if distinguish_use_mention and mention and not use:
            continue
        ids = re.findall(r"\b[A-Z]{2,5}-\d{4}\b", line)
        tokens = re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", line.lower())
        for tok in ids + tokens:
            nid = norm_id(tok)
            if nid in implemented_n or ids:
                rows.append(
                    {
                        "id": nid,
                        "source_path": source_path,
                        "line": i,
                        "use": use or not distinguish_use_mention,
                        "mention_only": mention and not use,
                    }
                )
    return rows


def harvestable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("use") and not r.get("mention_only")]
