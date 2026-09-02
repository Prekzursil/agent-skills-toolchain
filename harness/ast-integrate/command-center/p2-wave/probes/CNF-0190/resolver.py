#!/usr/bin/env python3
"""Mechanical option-id namespace resolver for CNF-0190.

Namespace assignment comes from token and path rules only. There is no LLM
classifier. A hit whose window carries no discriminating token is UNRESOLVED
and is routed to authors — never guessed. LLM classification of a mechanical
comparison measured 86% accurate on this estate with 100% of errors pointing
at data loss.

Token regex (printed for the evidence record):
    \\b([A-Z]{1,8})-(\\d{1,4})\\b
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

TOKEN_RE = re.compile(r"\b([A-Z]{1,8})-(\d{1,4})\b")
DEFINING_HEADING_RE = re.compile(r"^#{1,3}\s+(M|MECH)-(\d{1,4})\b", re.IGNORECASE)

CLASS_RESOLVED = "RESOLVED"
CLASS_UNRESOLVED = "UNRESOLVED"
CLASS_MENTION = "MENTION"

NS_OPTION = "option-universe"
NS_MECH = "architecture-mechanisms"
NS_WAVE3 = "wave3-deliverable"
NS_WAVE1 = "wave1-mission"

MENTION_MARKERS = (
    "collision",
    "namespaces share",
    "four m-nn",
    "re-prefixed",
    "re-prefix",
    "bare ambiguous",
    "present tense",
    "quoting the collision",
    "queued as p2-09",
    "inherit a closed problem",
    "inherit a fixed problem",
)

RESEARCH_HARNESS_MARKERS = (
    "research harness",
    "deep-research",
    "deep research",
)

MISSION_MARKERS = (
    "mission grade",
    "mission-grade",
    "mission grades",
    "wave-1 register",
    "wave1 register",
)

OPTION_MARKERS = (
    "option universe",
    "option card",
    "family m",
    "family-m",
)

WINDOW_CHARS = 180


def canonical_token(prefix: str, number: str) -> str:
    return f"{prefix.upper()}-{int(number)}"


def line_number(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def line_span(text: str, index: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    return start, end


def window_at(text: str, start: int, end: int) -> str:
    lo = max(0, start - WINDOW_CHARS)
    hi = min(len(text), end + WINDOW_CHARS)
    return text[lo:hi]


def posix_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def file_role(rel: str) -> str:
    low = rel.replace("\\", "/").lower()
    name = Path(low).name
    if "07-option" in low:
        return "option-universe-defining"
    if "13-architecture" in low:
        return "architecture-defining"
    if "17-decision-log" in low or "17-decision" in low:
        return "decision-log"
    if "option-id-resolution" in low:
        return "resolution-index"
    if name == "register.md" and ("wave1" in low or "wave-1" in low or "/wave1/" in low):
        return "wave1-register"
    if "deep-research" in low or "deep_research" in low:
        return "wave3-skill"
    if "mention" in low:
        return "mention-doc"
    if "unambiguous" in low:
        return "consumer"
    if "ambiguous" in low:
        return "ambiguous-consumer"
    if "consumers/" in low or "consumers/" in low:
        return "consumer"
    return "other"


def is_defining_line(line: str) -> bool:
    return bool(DEFINING_HEADING_RE.match(line.strip()))


def is_mention_window(window: str, role: str) -> bool:
    if role in {"mention-doc", "decision-log"}:
        blob = window.lower()
        if any(m in blob for m in MENTION_MARKERS):
            return True
        if role == "decision-log":
            return True
    blob = window.lower()
    return any(m in blob for m in MENTION_MARKERS)


def classify_hit(
    *,
    prefix: str,
    number: str,
    rel: str,
    line: str,
    window: str,
    role: str,
) -> dict:
    token = canonical_token(prefix, number)
    prefix_u = prefix.upper()
    defining = is_defining_line(line)
    blob = window.lower()

    # Rule 1: disjoint MECH- prefix. Never a bare M-NN. No adjudication.
    if prefix_u == "MECH":
        return {
            "classification": CLASS_RESOLVED,
            "namespace": NS_MECH,
            "resolved_meaning": "architecture-candidate mechanism card",
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "prefix-MECH",
        }

    # Rule 2: use-vs-mention. Quoting the collision is not a binding.
    if (not defining) and is_mention_window(window, role):
        return {
            "classification": CLASS_MENTION,
            "namespace": None,
            "resolved_meaning": None,
            "confidence": "use-vs-mention",
            "adjudicated": False,
            "rule": "mention-markers",
        }

    # Rule 3: Research Harness (M-16) / deep-research skill trees.
    if token == "M-16" and (
        role == "wave3-skill" or any(m in blob for m in RESEARCH_HARNESS_MARKERS)
    ):
        return {
            "classification": CLASS_RESOLVED,
            "namespace": NS_WAVE3,
            "resolved_meaning": "wave-3 Research Harness deliverable",
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "research-harness-M-16",
        }

    # Rule 4: wave-1 single-digit mission grades.
    if token in {"M-1", "M-3"} and (
        role == "wave1-register" or any(m in blob for m in MISSION_MARKERS)
    ):
        return {
            "classification": CLASS_RESOLVED,
            "namespace": NS_WAVE1,
            "resolved_meaning": "wave-1 mission grade",
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "wave1-mission-grade",
        }

    # Rule 5: option-universe defining file or option-card markers.
    if prefix_u == "M" and (
        role in {"option-universe-defining", "resolution-index"}
        or defining
        or any(m in blob for m in OPTION_MARKERS)
    ):
        return {
            "classification": CLASS_RESOLVED,
            "namespace": NS_OPTION,
            "resolved_meaning": "option-universe family-M card",
            "confidence": "token-rule",
            "adjudicated": False,
            "rule": "option-universe-M",
        }

    # Rule 6: no discriminating token. Do not guess.
    return {
        "classification": CLASS_UNRESOLVED,
        "namespace": None,
        "resolved_meaning": None,
        "confidence": "none",
        "adjudicated": False,
        "rule": "no-discriminating-token",
        "author_route": True,
    }


def extract_hits(text: str, rel: str) -> list[dict]:
    role = file_role(rel)
    hits: list[dict] = []
    for match in TOKEN_RE.finditer(text):
        prefix, number = match.group(1), match.group(2)
        start, end = match.span()
        ls, le = line_span(text, start)
        line = text[ls:le]
        window = window_at(text, start, end)
        verdict = classify_hit(
            prefix=prefix,
            number=number,
            rel=rel,
            line=line,
            window=window,
            role=role,
        )
        hits.append(
            {
                "id": canonical_token(prefix, number),
                "raw": match.group(0),
                "artifact": rel,
                "line": line_number(text, start),
                "snippet": line.strip()[:240],
                "window": " ".join(window.split())[:360],
                "role": role,
                "defining_site": is_defining_line(line),
                **verdict,
            }
        )
    return hits


def scan_file(path: Path, root: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = posix_rel(path, root)
    return extract_hits(text, rel)


def scan_tree(root: Path, *, skip_parts: Iterable[str] = ()) -> list[dict]:
    skip = {s.replace("\\", "/").lower() for s in skip_parts}
    hits: list[dict] = []
    if not root.is_dir():
        return hits
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt"}:
            continue
        rel = posix_rel(path, root)
        low = rel.lower()
        if any(s in low for s in skip):
            continue
        hits.extend(extract_hits(path.read_text(encoding="utf-8"), rel))
    return hits


def count_mech_tokens(text: str) -> dict:
    """Re-count MECH tokens. Used on 17-DECISION-LOG.md after any update."""
    token_hits = [
        m.group(0)
        for m in TOKEN_RE.finditer(text)
        if m.group(1).upper() == "MECH"
    ]
    bare_word = re.findall(r"\bMECH\b", text)
    return {
        "mech_nn_tokens": len(token_hits),
        "bare_MECH_word": len(bare_word),
        "total": len(token_hits) + len(bare_word),
        "samples": token_hits[:8],
    }


def present_tense_collision(text: str) -> bool:
    low = text.lower()
    present = (
        "is still" in low
        or "still live" in low
        or "is live" in low
        or "queued as p2-09" in low
    )
    return "collision" in low and present and "was re-prefixed" not in low


def path_stem_namespace(rel: str, token: str) -> str | None:
    """Second mechanical signal: path stem only, no surrounding prose.

    Used by probe 2 so the confirmation is not a single-signal verification.
    Abstains (None) when the path does not name a namespace.
    """
    low = rel.replace("\\", "/").lower()
    prefix = token.split("-", 1)[0]
    if prefix == "MECH":
        return NS_MECH
    if "deep-research" in low and token == "M-16":
        return NS_WAVE3
    if "wave1" in low and "register" in low and token in {"M-1", "M-3"}:
        return NS_WAVE1
    if "07-option" in low and prefix == "M":
        return NS_OPTION
    if "13-architecture" in low and prefix == "MECH":
        return NS_MECH
    return None


def uniqueness_by_id(hits: list[dict]) -> dict[str, dict]:
    """For each id, the set of resolved namespaces among non-MENTION hits."""
    out: dict[str, dict] = {}
    for hit in hits:
        if hit["classification"] == CLASS_MENTION:
            continue
        rec = out.setdefault(
            hit["id"],
            {
                "id": hit["id"],
                "namespaces": [],
                "unresolved_refs": 0,
                "resolved_refs": 0,
                "artifacts": [],
            },
        )
        rec["artifacts"].append(
            {"artifact": hit["artifact"], "line": hit["line"], "classification": hit["classification"]}
        )
        if hit["classification"] == CLASS_UNRESOLVED:
            rec["unresolved_refs"] += 1
        elif hit["classification"] == CLASS_RESOLVED:
            rec["resolved_refs"] += 1
            ns = hit.get("namespace")
            if ns and ns not in rec["namespaces"]:
                rec["namespaces"].append(ns)
    for rec in out.values():
        unique = (
            rec["unresolved_refs"] == 0
            and len(rec["namespaces"]) == 1
            and rec["resolved_refs"] > 0
        )
        rec["exactly_one_meaning"] = unique
        rec["meaning_count"] = len(rec["namespaces"]) + (1 if rec["unresolved_refs"] else 0)
    return out
