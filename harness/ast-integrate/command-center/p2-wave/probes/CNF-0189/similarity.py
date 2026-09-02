#!/usr/bin/env python3
"""Lexical Jaccard vs concept-hash embedding cosine.

Lexical measure: token-set Jaccard (the prior pass). A full vocabulary
rewrite lands in the same low band as a genuinely distinct entry.

Embedding measure: L2-normalised hashed bag of canonical concept ids
plus residual surface tokens after synonym folding. This is not a neural
sentence embedding. It can see synonym-level deep paraphrase that Jaccard
cannot. It cannot see metaphor that never hits the concept lexicon.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")
PATH_RE = re.compile(r"(?:[a-z]:\\|command-center/|~/)[^\s]+", re.I)
STOP = frozenset(
    """
    a an the and or of to for in on at by with from into over after before
    when whichever comes first there is no any than then also only if be
    are was were been being this that these those it its they their them
    we our you your not but so as may must can cannot each one
    """.split()
)

PHRASES: list[tuple[str, str]] = [
    ("peer weighted", "EQUALWEIGHT"),
    ("peer-weighted", "EQUALWEIGHT"),
    ("equal weight", "EQUALWEIGHT"),
    ("equal-weight", "EQUALWEIGHT"),
    ("hidden multiplier", "SECRETWEIGHT"),
    ("secret weight", "SECRETWEIGHT"),
    ("clock expires", "TIMEOUT"),
    ("time elapses", "TIMEOUT"),
    ("allotted duration elapses", "TIMEOUT"),
    ("allotted time elapses", "TIMEOUT"),
    ("force an outcome", "OVERRIDE"),
    ("force a result", "OVERRIDE"),
    ("chair override", "OVERRIDE"),
    ("halt on error", "HALTONERROR"),
    ("halt-on-error", "HALTONERROR"),
    ("filesystem walk", "FSWALK"),
    ("static scan", "STATICSCAN"),
]

TOKEN_MAP: dict[str, str] = {
    "four": "CARD4",
    "quartet": "CARD4",
    "voices": "PARTICIPANT",
    "voice": "PARTICIPANT",
    "speakers": "PARTICIPANT",
    "speaker": "PARTICIPANT",
    "roles": "PARTICIPANT",
    "role": "PARTICIPANT",
    "ballot": "VOTETOKEN",
    "ballots": "VOTETOKEN",
    "ticket": "VOTETOKEN",
    "tickets": "VOTETOKEN",
    "vote": "VOTETOKEN",
    "votes": "VOTETOKEN",
    "voting": "VOTETOKEN",
    "equalweight": "EQUALWEIGHT",
    "equal": "EQUALWEIGHT",
    "peer": "EQUALWEIGHT",
    "assents": "ASSENT",
    "assent": "ASSENT",
    "agrees": "ASSENT",
    "agree": "ASSENT",
    "agreement": "ASSENT",
    "unanimous": "UNIVERSALASSENT",
    "unanimously": "UNIVERSALASSENT",
    "every": "UNIVERSAL",
    "all": "UNIVERSAL",
    "total": "UNIVERSAL",
    "carries": "PASS",
    "carry": "PASS",
    "passage": "PASS",
    "motion": "MOTION",
    "sitting": "SESSION",
    "session": "SESSION",
    "ends": "HALT",
    "end": "HALT",
    "terminates": "HALT",
    "terminate": "HALT",
    "halt": "HALT",
    "stop": "HALT",
    "stops": "HALT",
    "eight": "EIGHT",
    "8": "EIGHT",
    "rounds": "ROUND",
    "round": "ROUND",
    "cycles": "ROUND",
    "cycle": "ROUND",
    "timeout": "TIMEOUT",
    "clock": "TIMEOUT",
    "expires": "TIMEOUT",
    "elapses": "TIMEOUT",
    "dissent": "DISSENT",
    "disagreement": "DISSENT",
    "transcript": "RECORD",
    "minutes": "RECORD",
    "record": "RECORD",
    "recorded": "RECORD",
    "written": "RECORD",
    "chair": "CHAIR",
    "moderator": "CHAIR",
    "override": "OVERRIDE",
    "force": "OVERRIDE",
    "secretweight": "SECRETWEIGHT",
    "seat": "SEAT",
    "occupant": "SEAT",
    "occupants": "SEAT",
    "quorum": "QUORUM",
    "protocol": "PROTOCOL",
    "preset": "PRESET",
    "blueprint": "BLUEPRINT",
    "workflow": "WORKFLOW",
    "council": "COUNCIL",
    "deliberative": "DELIBERATIVE",
    "adversarial": "ADVERSARIAL",
    "judicial": "JUDICIAL",
    "veto": "VETO",
    "staticscan": "STATICSCAN",
    "fswalk": "FSWALK",
    "haltonerror": "HALTONERROR",
    "scan": "SCAN",
    "writer": "WRITER",
    "nonzero": "NONZERO",
    "filesystem": "FSWALK",
    "repository": "REPO",
    "repo": "REPO",
}

DIM = 256
CONCEPT_GAIN = 3.0
BIGRAM_GAIN = 1.5
RESIDUAL_GAIN = 0.35
CHAR_GAIN = 0.2


def scrub(text: str) -> str:
    t = PATH_RE.sub(" ", text or "")
    t = re.sub(r"_user-prompts\.md:\d+", " ", t, flags=re.I)
    t = re.sub(r"\b(?:cnf|cnl|wfa|arc|aud|imp)-\d{4}\b", " ", t, flags=re.I)
    return t


def _apply_phrases(text: str) -> str:
    t = (text or "").lower()
    for src, dst in sorted(PHRASES, key=lambda kv: -len(kv[0])):
        t = t.replace(src, f" {dst.lower()} ")
    return t


def tokens(text: str) -> list[str]:
    t = _apply_phrases(scrub(text))
    out: list[str] = []
    for tok in TOKEN_RE.findall(t):
        if tok in STOP or len(tok) < 2:
            continue
        out.append(tok)
    return out


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def jaccard(a: str, b: str) -> float:
    left, right = token_set(a), token_set(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def is_concept(tok: str) -> bool:
    return tok.isupper() and any(ch.isalpha() for ch in tok)


def canonicalize(text: str) -> list[str]:
    out: list[str] = []
    for tok in tokens(text):
        mapped = TOKEN_MAP.get(tok, tok)
        mapped = TOKEN_MAP.get(mapped, mapped)
        out.append(mapped)
    return out


def concept_set(text: str) -> set[str]:
    return {t for t in canonicalize(text) if is_concept(t)}


def _bucket(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h, 16) % DIM


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    can = canonicalize(text)
    for i, c in enumerate(can):
        gain = CONCEPT_GAIN if is_concept(c) else RESIDUAL_GAIN
        vec[_bucket("u:" + c)] += gain
        if i + 1 < len(can):
            vec[_bucket("b:" + c + "|" + can[i + 1])] += BIGRAM_GAIN
    s = " ".join(can)
    for i in range(max(0, len(s) - 2)):
        vec[_bucket("c:" + s[i : i + 3])] += CHAR_GAIN
    return _l2(vec)


def _l2(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec))
    if n == 0.0:
        return vec
    return [x / n for x in vec]


def cosine(u: Iterable[float], v: Iterable[float]) -> float:
    acc = 0.0
    for a, b in zip(u, v):
        acc += a * b
    if acc > 1.0:
        return 1.0
    if acc < 0.0:
        return 0.0
    return acc


def cosine_texts(a: str, b: str) -> float:
    return cosine(embed(a), embed(b))


def body_of(rec: dict) -> str:
    parts = [
        str(rec.get("title") or rec.get("name") or ""),
        str(rec.get("body") or rec.get("text") or rec.get("description") or ""),
    ]
    return "\n".join(p for p in parts if p)


# Names used by scan.py / probes.
jaccard = jaccard
embed = embed
cosine_texts = cosine_texts
body_of = body_of
concept_set = concept_set
jaccard = jaccard
embed = embed
cosine_texts = cosine_texts
body_of = body_of
concept_set = concept_set
