"""Three duplicate-detection methods for the WFA-0097 envelope.

Lexical: stopword-filtered token Jaccard over name + does + mechanisms.
Embedding-class: Jaccard after frozen synonym expansion. WFA-0008's neural
embedding artifact is absent on this tree; this stand-in is the embedding-class
method that can actually run. It is labelled as such in every envelope row.
Structural: equality of the five IR sets (stages, roles, gates, tools,
stop_rules). Empty-IR pairs do not count as a hit.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    """
    a an the of to and or for with on in by using over from at as is are be
    this that it its was were been being not no so if then than into onto
    across via per plus same both each other more less
    """.split()
)
IR_KEYS = ("stages", "roles", "gates", "tools", "stop_rules")
LEXICAL_THRESHOLD = 0.50
EMBEDDING_THRESHOLD = 0.50

_PAIRS = (
    ("scan", "inspect"),
    ("candidate", "record"),
    ("workflows", "pipelines"),
    ("workflow", "pipeline"),
    ("lexical", "word"),
    ("near", "close"),
    ("duplicates", "copies"),
    ("duplicate", "copy"),
    ("token", "term"),
    ("jaccard", "overlap"),
    ("name", "title"),
    ("does", "purpose"),
    ("mechanisms", "devices"),
    ("mechanism", "device"),
)
SYN: dict[str, set[str]] = {}
for _a, _b in _PAIRS:
    SYN.setdefault(_a, set()).add(_b)
    SYN.setdefault(_b, set()).add(_a)

METHOD_IDS = (
    "lexical-jaccard",
    "embedding-expanded-token-jaccard",
    "structural-ir-sets",
)


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1}


def morph_forms(word: str) -> set[str]:
    forms = {word}
    if word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
    else:
        forms.add(word + "s")
    return forms


def expand(toks: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for t in toks:
        forms = morph_forms(t)
        out |= forms
        for f in list(forms):
            out |= morph_forms(f)
            for syn in SYN.get(f, ()):
                out |= morph_forms(syn)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def record_text(rec: dict[str, Any]) -> str:
    mechs = rec.get("mechanisms") or []
    if isinstance(mechs, list):
        mech_s = " ".join(str(m) for m in mechs)
    else:
        mech_s = str(mechs)
    return " ".join(
        str(rec.get(k) or "") for k in ("name", "does")
    ) + " " + mech_s


def lexical_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    return jaccard(tokens(record_text(a)), tokens(record_text(b)))


def embedding_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    return jaccard(
        expand(tokens(record_text(a))),
        expand(tokens(record_text(b))),
    )


def ir_sets(rec: dict[str, Any]) -> dict[str, frozenset[str]]:
    ir = rec.get("ir") if isinstance(rec.get("ir"), dict) else rec
    out: dict[str, frozenset[str]] = {}
    for key in IR_KEYS:
        vals = ir.get(key) or []
        if isinstance(vals, list):
            out[key] = frozenset(str(x) for x in vals)
        else:
            out[key] = frozenset()
    return out


def ir_nonempty(sets: dict[str, frozenset[str]]) -> bool:
    return any(sets[k] for k in IR_KEYS)


def structural_hit(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if str(a.get("id") or "") == str(b.get("id") or "") and a.get("id"):
        return False
    sa, sb = ir_sets(a), ir_sets(b)
    if not ir_nonempty(sa) or not ir_nonempty(sb):
        return False
    return all(sa[k] == sb[k] for k in IR_KEYS)


def lexical_hit(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, float]:
    score = lexical_score(a, b)
    return score >= LEXICAL_THRESHOLD, score


def embedding_hit(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, float]:
    score = embedding_score(a, b)
    return score >= EMBEDDING_THRESHOLD, score


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    lex_hit, lex = lexical_hit(a, b)
    emb_hit, emb = embedding_hit(a, b)
    st_hit = structural_hit(a, b)
    combined = bool(lex_hit or emb_hit or st_hit)
    return {
        "lexical-jaccard": {"hit": lex_hit, "score": round(lex, 6)},
        "embedding-expanded-token-jaccard": {
            "hit": emb_hit,
            "score": round(emb, 6),
            "stand_in_for": "WFA-0008-neural-embedding",
            "stand_in_reason": "WFA-0008 artifact ABSENT on this tree",
        },
        "structural-ir-sets": {
            "hit": st_hit,
            "score": 1.0 if st_hit else 0.0,
        },
        "combined_hit": combined,
    }
