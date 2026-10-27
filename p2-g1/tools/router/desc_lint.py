"""Lexical routing-description linter with negative-scope coverage (IMP-0388)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIVE_INDEX = REPO / "capability-index.json"
IMP_0386 = REPO / "command-center" / "receipts" / "IMP-0386.json"

STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "for",
        "to",
        "of",
        "in",
        "on",
        "or",
        "is",
        "as",
        "by",
        "with",
        "from",
        "when",
        "use",
        "user",
        "asks",
        "that",
        "this",
        "it",
        "into",
        "via",
        "plus",
        "not",
    }
)
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
NEG_FIELD_KEYS = ("negative_scope", "do_not_use_for", "do_not_use", "not_for")
DO_NOT_RE = re.compile(r"\bdo not use\b", re.IGNORECASE)


def cap_id(cap: dict[str, Any]) -> str:
    return str(cap.get("capability_id") or cap.get("id") or cap.get("name") or "")


def description_of(cap: dict[str, Any]) -> str:
    return str(cap.get("description") or "")


def tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP and len(t) > 1}


def token_overlap(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    if not union:
        return 0.0
    return len(inter) / float(len(union))


def has_negative_scope(cap: dict[str, Any]) -> bool:
    for key in NEG_FIELD_KEYS:
        val = cap.get(key)
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, list) and val:
            return True
    return bool(DO_NOT_RE.search(description_of(cap)))


def _caps_from_obj(obj: Any) -> list[dict[str, Any]] | None:
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return list(obj)
    if isinstance(obj, dict):
        for key in ("capabilities", "index", "items", "rows"):
            val = obj.get(key)
            if isinstance(val, list) and val and all(isinstance(x, dict) for x in val):
                return list(val)
    return None


def load_index(path: Path | str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[tuple[str, Path]] = []
    if LIVE_INDEX.is_file():
        candidates.append(("live", LIVE_INDEX))
    if IMP_0386.is_file():
        candidates.append(("imp-0386", IMP_0386))
    if path is not None:
        candidates.append(("given", Path(path)))
    loaded = {
        "kind": "missing",
        "path": None,
        "capability_count": 0,
        "live_present": LIVE_INDEX.is_file(),
        "imp_0386_present": IMP_0386.is_file(),
    }
    for kind, cand in candidates:
        if not cand.is_file() or cand.stat().st_size <= 0:
            continue
        try:
            obj = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        caps = _caps_from_obj(obj)
        if not caps:
            continue
        loaded = {
            "kind": kind,
            "path": cand.as_posix(),
            "capability_count": len(caps),
            "live_present": LIVE_INDEX.is_file(),
            "imp_0386_present": IMP_0386.is_file(),
        }
        return [dict(c) for c in caps], loaded
    return [], loaded


def apply_rename_paraphrase(
    caps: list[dict[str, Any]],
    *,
    source_id: str,
    sibling_id: str,
    new_id: str,
    paraphrase: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cap in caps:
        row = dict(cap)
        if cap_id(row) == source_id:
            if "capability_id" in row:
                row["capability_id"] = new_id
            elif "id" in row:
                row["id"] = new_id
            else:
                row["name"] = new_id
            row["description"] = paraphrase
        out.append(row)
    _ = sibling_id
    return out


def zero_negative_scope(caps: list[dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(cap_id(c) for c in caps if cap_id(c) and not has_negative_scope(c))
    return {"count": len(ids), "ids": ids}


def ranked_confusable_pairs(caps: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = [(cap_id(c), description_of(c), c) for c in caps if cap_id(c)]
    for i, (ida, desa, _) in enumerate(items):
        for idb, desb, _capb in items[i + 1 :]:
            score = token_overlap(desa, desb)
            a, b = (ida, idb) if ida <= idb else (idb, ida)
            da, db = (desa, desb) if ida <= idb else (desb, desa)
            rows.append(
                {
                    "id_a": a,
                    "id_b": b,
                    "token_overlap_score": score,
                    "description_a": da,
                    "description_b": db,
                }
            )
    rows.sort(key=lambda r: (-float(r["token_overlap_score"]), r["id_a"], r["id_b"]))
    return rows[: max(0, int(top_n))]


def pair_in_top(ranking: list[dict[str, Any]], id_a: str, id_b: str, k: int = 5) -> dict[str, Any] | None:
    want = frozenset({id_a, id_b})
    for row in ranking[:k]:
        if frozenset({row.get("id_a"), row.get("id_b")}) == want:
            return row
    return None


def four_axes(caps: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(caps)
    zeros = zero_negative_scope(caps)
    return {
        "coverage": n,
        "negative_scope_present": n - zeros["count"],
        "zero_negative_scope": zeros["count"],
        "unique_ids": len({cap_id(c) for c in caps if cap_id(c)}),
    }


def lint(caps: list[dict[str, Any]], top_n: int = 20) -> dict[str, Any]:
    ranking = ranked_confusable_pairs(caps, top_n=max(int(top_n), 20))
    zeros = zero_negative_scope(caps)
    most = ranking[0] if ranking else {"id_a": "", "id_b": "", "token_overlap_score": 0.0}
    return {
        "capability_count": len(caps),
        "zero_negative_scope": zeros,
        "confusability": {
            "top_20": ranking[:20],
            "most_confusable_pair": most,
        },
        "four_axes": four_axes(caps),
    }


__all__ = [
    "IMP_0386",
    "LIVE_INDEX",
    "apply_rename_paraphrase",
    "cap_id",
    "four_axes",
    "has_negative_scope",
    "lint",
    "load_index",
    "pair_in_top",
    "ranked_confusable_pairs",
    "token_overlap",
    "zero_negative_scope",
]
