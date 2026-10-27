#!/usr/bin/env python3
"""Deterministic mechanism extractor and Jaccard dedup for RES-0140."""
from __future__ import annotations

import re

RFC = re.compile(
    r"\b(MUST NOT|MUST|SHALL NOT|SHALL|SHOULD NOT|SHOULD|REQUIRED|MAY NOT|MAY)\b"
)
HEADING_MD = re.compile(r"^(#{1,3})\s+(.+)$", re.M)
BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", re.M)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")
NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
WS = re.compile(r"\s+")

# Frozen keyword set: a chunk is a mechanism candidate if it hits RFC 2119
# or at least two of these control-plane terms.
KEYWORDS = frozenset(
    {
        "agent",
        "agents",
        "allowlist",
        "api",
        "audit",
        "capability",
        "composab",
        "context",
        "contract",
        "disclosure",
        "endpoint",
        "filesystem",
        "frontmatter",
        "jsonrpc",
        "json-rpc",
        "mcp",
        "metadata",
        "openapi",
        "permission",
        "progressive",
        "protocol",
        "runtime",
        "sandbox",
        "sandboxed",
        "schema",
        "session",
        "skill",
        "skills",
        "stdio",
        "token",
        "tokens",
        "tool",
        "tools",
        "transcript",
        "verify",
        "verification",
        "webhook",
        "workflow",
        "workspace",
        "yaml",
    }
)

STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "and",
        "to",
        "for",
        "in",
        "on",
        "with",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "by",
        "or",
        "from",
        "that",
        "this",
        "it",
        "we",
        "you",
        "our",
        "their",
        "can",
        "will",
        "not",
        "into",
        "about",
        "than",
        "then",
        "also",
        "have",
        "has",
        "had",
        "but",
        "if",
        "at",
        "its",
        "they",
        "them",
        "your",
        "any",
        "all",
        "more",
        "using",
        "used",
        "use",
        "new",
        "one",
        "out",
        "up",
        "so",
        "just",
        "like",
        "over",
        "when",
        "what",
        "how",
        "which",
        "who",
        "there",
        "here",
        "been",
        "being",
        "do",
        "does",
        "did",
        "may",
        "must",
        "should",
        "shall",
        "each",
        "other",
        "such",
        "these",
        "those",
        "via",
        "per",
        "across",
        "between",
        "within",
        "without",
        "through",
        "after",
        "before",
        "while",
        "where",
        "because",
        "today",
        "now",
        "get",
        "got",
        "make",
        "made",
        "let",
        "lets",
        "want",
        "need",
        "needs",
        "way",
        "ways",
        "thing",
        "things",
        "really",
        "very",
        "even",
        "still",
        "back",
        "first",
        "second",
        "third",
    }
)

JACCARD_DUP = 0.72
CONTAIN_RATIO = 0.80
MIN_WORDS = 6
MAX_WORDS = 90


def keyword_hits(text: str) -> int:
    toks = set(re.findall(r"[a-z0-9-]+", text.lower()))
    n = 0
    for t in toks:
        if t in KEYWORDS:
            n += 1
        elif any(t.startswith(k) and len(k) >= 7 for k in KEYWORDS):
            n += 1
    return n


def split_sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(text)
    out = []
    for p in parts:
        s = WS.sub(" ", p).strip()
        if s:
            out.append(s)
    return out


def extract_raw(text: str) -> list[str]:
    chunks: list[str] = []
    for m in HEADING_MD.finditer(text):
        h = m.group(2).strip()
        if 2 <= len(h.split()) <= 16 and keyword_hits(h) >= 1:
            chunks.append(h)
    for m in BULLET.finditer(text):
        b = WS.sub(" ", m.group(1)).strip()
        if _keep(b) and (RFC.search(b) or keyword_hits(b) >= 1):
            chunks.append(b)
    for sent in split_sentences(text):
        if _keep(sent) and (RFC.search(sent) or keyword_hits(sent) >= 2):
            chunks.append(sent)
    return chunks


def _keep(s: str) -> bool:
    words = s.split()
    if not (MIN_WORDS <= len(words) <= MAX_WORDS):
        return False
    letters = sum(ch.isalpha() for ch in s)
    if letters < 20:
        return False
    low = s.lower()
    if low.startswith("cookie") or "subscribe" in low[:80]:
        return False
    return True


def norm_tokens(s: str) -> frozenset[str]:
    s = s.lower()
    s = NON_ALNUM.sub(" ", s)
    return frozenset(w for w in s.split() if w not in STOP and len(w) > 2)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def is_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    if jaccard(a, b) >= JACCARD_DUP:
        return True
    if a <= b or b <= a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        if shorter >= 4 and shorter / longer >= CONTAIN_RATIO:
            return True
    return False


def cluster(texts: list[str]) -> list[dict]:
    """Greedy clustering; representative is the longest string in the cluster."""
    items = []
    for t in texts:
        nt = norm_tokens(t)
        if len(nt) < 3:
            continue
        items.append({"text": t, "tokens": nt})
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if is_duplicate(items[i]["tokens"], items[j]["tokens"]):
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for members in groups.values():
        best = max(members, key=lambda k: len(items[k]["text"]))
        out.append(
            {
                "text": items[best]["text"],
                "tokens": items[best]["tokens"],
                "cluster_size": len(members),
            }
        )
    out.sort(key=lambda r: r["text"])
    return out


def extract_mechanisms(text: str) -> list[dict]:
    return cluster(extract_raw(text))


def unique_against(candidates: list[dict], others: list[dict]) -> list[dict]:
    uniq = []
    for c in candidates:
        if any(is_duplicate(c["tokens"], o["tokens"]) for o in others):
            continue
        uniq.append(c)
    return uniq
