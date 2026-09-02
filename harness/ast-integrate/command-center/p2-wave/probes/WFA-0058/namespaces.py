"""Id-namespace collision check against candidate / blueprint / option tokens."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from vocab import ID_PATTERN, vocab_ids

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NS_PATH = REPO / "command-center/wfa/mechanism-namespaces.json"

CANDIDATE_RE = re.compile(r"^wf-", re.I)
BLUEPRINT_RE = re.compile(r"^BP-[0-9]+$", re.I)
OPTION_RE = re.compile(r"^M-[0-9]+$", re.I)


def load_namespaces() -> dict[str, set[str]]:
    if not NS_PATH.is_file():
        return {"candidate": set(), "blueprint": set(), "option": set()}
    doc = json.loads(NS_PATH.read_text(encoding="utf-8"))
    return {
        "candidate": set(doc.get("candidate_ids") or []),
        "blueprint": set(doc.get("blueprint_ids") or []),
        "option": set(doc.get("option_ids") or []),
    }


def classify_shape(mid: str) -> str | None:
    if CANDIDATE_RE.match(mid):
        return "candidate"
    if BLUEPRINT_RE.match(mid):
        return "blueprint"
    if OPTION_RE.match(mid):
        return "option"
    return None


def audit(ids: tuple[str, ...] | None = None) -> dict[str, Any]:
    mids = ids if ids is not None else vocab_ids()
    ns = load_namespaces()
    collisions: list[dict[str, str]] = []
    shape_hits: list[dict[str, str]] = []
    pattern_ok = True
    for mid in mids:
        if not re.match(ID_PATTERN, mid):
            pattern_ok = False
            shape_hits.append({"id": mid, "reason": "not-MX-NNNN"})
        shape = classify_shape(mid)
        if shape:
            shape_hits.append({"id": mid, "reason": f"shape-{shape}"})
        for kind, tokens in ns.items():
            if mid in tokens:
                collisions.append({"id": mid, "namespace": kind})
    planted_option = "M-16"
    planted_would_collide = planted_option in ns["option"] or bool(
        OPTION_RE.match(planted_option)
    )
    return {
        "ids": list(mids),
        "pattern_ok": pattern_ok and not shape_hits,
        "collisions": collisions,
        "shape_hits": shape_hits,
        "namespaces_loaded": {k: sorted(v) for k, v in ns.items()},
        "planted_M-16_rejected_as_vocab_id": planted_option not in mids,
        "planted_M-16_is_option_shape": planted_would_collide,
        "clean": pattern_ok and not collisions and not shape_hits,
    }
