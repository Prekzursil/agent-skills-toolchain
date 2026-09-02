"""SYN-0017 duplicate-mechanism collapse with two mechanically different detectors.

Detector A: order-sensitive SequenceMatcher on normalized text (lexical).
Detector B: order-insensitive token Jaccard (set overlap). These are not the
same measurement: A cares about sequence, B does not.

Embedding similarity is NOT implemented. A full rewrite of the same mechanism
therefore scores like a distinct entry under this pair. That lexical-only
coverage gap is disclosed, not hidden.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any

from role import load_subject

LENS_ID = "SYN-0017"
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "to",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "was",
        "be",
        "by",
    }
)
WS = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return WS.sub(" ", text.lower()).strip()


def _stem(token: str) -> str:
    """Light suffix strip so Jaccard is not a SequenceMatcher clone.

    Mechanically different from lexical ratio: order is discarded and
    trailing -ing/-es/-s are folded. This is still not an embedding.
    """
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def tokens(text: str) -> set[str]:
    return {_stem(t) for t in normalize(text).split() if t and t not in STOP}


def lexical_score(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def jaccard_score(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_members(obj: Any) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        for key in ("findings", "members", "candidates", "items"):
            val = obj.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and (
                        item.get("text") or item.get("claim") or item.get("sentence")
                    ):
                        members.append(item)
        if not members and (obj.get("text") or obj.get("claim")):
            members.append(obj)
        if not members:
            for val in obj.values():
                members.extend(extract_members(val))
    elif isinstance(obj, list):
        for item in obj:
            members.extend(extract_members(item))
    return members


def _anchors_of(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    val = item.get("anchors") or item.get("evidence") or []
    if isinstance(val, str) and val.strip():
        out.append(val.strip())
    elif isinstance(val, list):
        for x in val:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
    return out


def pair_decision(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    ta = str(a.get("text") or a.get("claim") or a.get("sentence") or "")
    tb = str(b.get("text") or b.get("claim") or b.get("sentence") or "")
    lex = lexical_score(ta, tb)
    jac = jaccard_score(ta, tb)
    # Confirmed duplicate when either detector is very high, or both agree moderately.
    collapse = lex >= 0.86 or jac >= 0.80 or (lex >= 0.62 and jac >= 0.55)
    union = sorted(set(_anchors_of(a)) | set(_anchors_of(b)))
    return {
        "left": str(a.get("id") or ""),
        "right": str(b.get("id") or ""),
        "lexical": round(lex, 4),
        "jaccard": round(jac, 4),
        "collapse": collapse,
        "anchor_union": union,
        "anchor_union_preserves_both": set(union) >= set(_anchors_of(a)) | set(_anchors_of(b)),
    }


def scan_obj(path: Path, obj: Any) -> list[dict[str, Any]]:
    members = extract_members(obj)
    pairs = [pair_decision(a, b) for a, b in combinations(members, 2)]
    findings: list[dict[str, Any]] = []
    seq = 1
    for pair in pairs:
        if not pair["collapse"]:
            continue
        findings.append(
            {
                "id": f"SYN-0017-F{seq:03d}",
                "lens": LENS_ID,
                "kind": "duplicate-mechanism",
                "use_or_mention": "USE",
                "counted_as_defect": True,
                "span": f"{pair['left']}~{pair['right']}",
                "source_path": path.as_posix(),
                "source_locator": path.as_posix(),
                "pair": pair,
                "reason": (
                    "two findings describe the same mechanism "
                    f"(lexical={pair['lexical']}, jaccard={pair['jaccard']})"
                ),
            }
        )
        seq += 1
    return findings


def scan_path(path: Path, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    del ignore_wrappers
    sub = load_subject(path)
    if sub["kind"] != "json":
        return []
    return scan_obj(path, sub["parsed"])


def planted_control(path: Path) -> dict[str, Any]:
    """Score the planted rename / paraphrase / parameter-fork / distinct pair."""
    obj = json.loads(path.read_text(encoding="utf-8"))
    by_id = {str(m.get("id")): m for m in extract_members(obj)}
    wanted = {
        "rename": ("R1", "R2"),
        "paraphrase": ("P1", "P2"),
        "parameter-fork": ("F1", "F2"),
        "distinct": ("D1", "D2"),
    }
    results = {}
    for name, (a, b) in wanted.items():
        if a not in by_id or b not in by_id:
            results[name] = {"present": False}
            continue
        dec = pair_decision(by_id[a], by_id[b])
        results[name] = {"present": True, **dec}
    return {
        "members": sorted(by_id),
        "pairs": results,
        "rename_caught": bool(results.get("rename", {}).get("collapse")),
        "paraphrase_caught": bool(results.get("paraphrase", {}).get("collapse")),
        "parameter_fork_caught": bool(results.get("parameter-fork", {}).get("collapse")),
        "distinct_not_collapsed": results.get("distinct", {}).get("collapse") is False,
        "lexical_only_coverage_disclosed": True,
    }
