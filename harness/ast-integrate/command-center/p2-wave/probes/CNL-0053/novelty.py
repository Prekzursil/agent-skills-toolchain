#!/usr/bin/env python3
"""Novelty vs quality scoring against a pinned prior-art corpus (CNL-0053).

Novelty is 1 - max similarity to a NAMED corpus pin. Quality is a disjoint
function of falsifier / evidence_kind / contradicts_known. Quality is never
1 - novelty. Corpus membership does not confer quality.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "fixtures" / "prior_art_corpus.json"
CANDIDATES_PATH = HERE / "fixtures" / "candidates.json"

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "and",
        "or",
        "for",
        "on",
        "in",
        "by",
        "with",
        "from",
        "that",
        "this",
        "is",
        "are",
        "be",
        "as",
        "at",
        "it",
        "its",
        "vs",
        "via",
        "use",
        "using",
        "used",
        "must",
        "stay",
        "all",
    }
)
SYNONYM = {
    "corrupted": "corruption",
    "corrupt": "corruption",
    "hash": "checksum",
    "hashed": "checksum",
    "digest": "checksum",
    "integrity": "corruption",
    "payload": "data",
    "checking": "detect",
    "detecting": "detect",
}

LOW_NOVELTY_MAX = 0.45
HIGH_NOVELTY_MIN = 0.55
HIGH_QUALITY_MIN = 0.70
LOW_QUALITY_MAX = 0.40
FIRE_NOVELTY_MIN = 0.55
FIRE_QUALITY_MAX = 0.40
SURFACE_MATCH_MIN = 0.55
MECH_RE = re.compile(r"^[a-z][a-z0-9_]{3,}$")
TOKEN_RE = re.compile(r"[a-z0-9]+")


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load_corpus(path: Path | None = None) -> dict:
    p = path or CORPUS_PATH
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("items"):
        raise ValueError(f"corpus missing items: {p}")
    doc = dict(doc)
    doc["pin_sha256"] = sha256_file(p)
    doc["pin_path"] = p.as_posix()
    return doc


def load_candidates(path: Path | None = None) -> dict:
    p = path or CANDIDATES_PATH
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"candidates unparseable: {p}")
    return doc


def tokens(text: str) -> frozenset[str]:
    raw = TOKEN_RE.findall((text or "").lower())
    out: set[str] = set()
    for t in raw:
        if t in STOP or len(t) < 3:
            continue
        out.add(SYNONYM.get(t, t))
    return frozenset(out)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def quality_score(idea: dict) -> float:
    """Independent of corpus membership and of novelty."""
    if idea.get("contradicts_known") is True:
        return 0.0
    score = 0.0
    mech = str(idea.get("mechanism") or "")
    if MECH_RE.fullmatch(mech):
        score += 0.30
    if str(idea.get("falsifier") or "").strip():
        score += 0.35
    if str(idea.get("evidence_kind") or "") in {
        "experiment",
        "measurement",
        "named-failure-class",
    }:
        score += 0.25
    if idea.get("contradicts_known") is False:
        score += 0.10
    return min(1.0, score)


def max_surface_jaccard(idea: dict, corpus: dict) -> tuple[float, str | None]:
    idea_tok = tokens(str(idea.get("text") or ""))
    best = 0.0
    best_id = None
    for row in corpus.get("items") or []:
        sim = jaccard(idea_tok, tokens(str(row.get("text") or "")))
        if sim > best:
            best = sim
            best_id = str(row.get("id") or "")
    return best, best_id


def mechanism_match(idea: dict, corpus: dict) -> str | None:
    mech = str(idea.get("mechanism") or "")
    if not mech:
        return None
    for row in corpus.get("items") or []:
        if str(row.get("mechanism") or "") == mech:
            return str(row.get("id") or "")
    return None


def novelty_score(idea: dict, corpus: dict) -> dict:
    """Novelty relative to the named corpus only.

    Mechanism-id identity collapses novelty to 0 (same idea already admitted).
    Surface Jaccard is the backstop when the id is withheld.
    """
    surface_sim, surface_id = max_surface_jaccard(idea, corpus)
    mech_id = mechanism_match(idea, corpus)
    if mech_id:
        novelty = 0.0
        match_kind = "mechanism-id"
        match_id = mech_id
    else:
        novelty = 1.0 - surface_sim
        match_kind = "surface-jaccard"
        match_id = surface_id
    return {
        "novelty": round(novelty, 6),
        "surface_jaccard": round(surface_sim, 6),
        "match_kind": match_kind,
        "match_id": match_id,
        "corpus_id": corpus.get("corpus_id"),
        "corpus_pin_sha256": corpus.get("pin_sha256"),
    }


def junk_novelty_check(scored: dict) -> str:
    """FIRES on high-novelty low-quality junk. SILENT otherwise.

    This is the check the both-states control exercises. It rejects using
    novelty as a quality proxy: a novelty-only gate would ACCEPT this junk.
    """
    nov = float(scored["novelty"])
    qual = float(scored["quality"])
    if nov >= FIRE_NOVELTY_MIN and qual < FIRE_QUALITY_MAX:
        return "FIRE"
    return "SILENT"


def score_idea(idea: dict, corpus: dict) -> dict:
    nov = novelty_score(idea, corpus)
    qual = quality_score(idea)
    out = dict(nov)
    out["quality"] = round(qual, 6)
    out["idea_id"] = idea.get("id")
    out["check"] = junk_novelty_check(out)
    out["low_novelty"] = out["novelty"] <= LOW_NOVELTY_MAX
    out["high_novelty"] = out["novelty"] >= HIGH_NOVELTY_MIN
    out["high_quality"] = out["quality"] >= HIGH_QUALITY_MIN
    out["low_quality"] = out["quality"] <= LOW_QUALITY_MAX
    return out


def band(scored: dict) -> str:
    n = "low-N" if scored["low_novelty"] else ("high-N" if scored["high_novelty"] else "mid-N")
    q = "high-Q" if scored["high_quality"] else ("low-Q" if scored["low_quality"] else "mid-Q")
    return f"{n}/{q}"
