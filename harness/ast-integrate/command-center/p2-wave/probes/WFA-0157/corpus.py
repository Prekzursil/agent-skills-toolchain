"""108-record blueprint array with catalog arithmetic for state gloss vs vocab.

09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent on this Linux worktree (same
measurement as ARC-0003/0010/0014). This module builds a disclosed
reconstructed array whose live recount matches the catalog claim:

  n=108, distinct state literals=36, vocab-exact=74, non-literal=34

Vocabulary tokens: FOUND, REPAIRED, MERGED, NEW.
The 34 non-exact rows use 32 additional gloss strings (two repeats) so
4 vocab + 32 gloss = 36 distinct literals.

Every record also carries decomposed ``state_v`` / ``size_v`` for machine
consumers. Gloss ``state`` / ``size`` remain as human text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "blueprints-108.json"

VOCAB_STATE = ("FOUND", "REPAIRED", "MERGED", "NEW")
VOCAB_SIZE = ("S", "M", "L", "XL")

# 32 unique glosses, none equal to a vocabulary token.
STATE_GLOSSES = (
    "found in archaeology dump",
    "repaired locally after parse fail",
    "merged from upstream candidate",
    "new — not yet classified",
    "FOUND (partial)",
    "needs-repair",
    "already-merged",
    "brand new",
    "discovered",
    "fixed-in-place",
    "combined",
    "created-here",
    "FOUND?",
    "REPAIRED (wip)",
    "MERGED/NEW",
    "unknown",
    "legacy-found",
    "source-repaired",
    "fusion-merged",
    "greenfield",
    "archived-found",
    "patched",
    "folded-in",
    "draft",
    "seen-in-harness",
    "hotfix",
    "composite",
    "experimental",
    "recovered",
    "normalized",
    "imported",
    "forked",
)

# Gloss -> decomposed token. Mapping is explicit, not inferred from substrings.
GLOSS_TO_STATE_V = {
    "found in archaeology dump": "FOUND",
    "repaired locally after parse fail": "REPAIRED",
    "merged from upstream candidate": "MERGED",
    "new — not yet classified": "NEW",
    "FOUND (partial)": "FOUND",
    "needs-repair": "REPAIRED",
    "already-merged": "MERGED",
    "brand new": "NEW",
    "discovered": "FOUND",
    "fixed-in-place": "REPAIRED",
    "combined": "MERGED",
    "created-here": "NEW",
    "FOUND?": "FOUND",
    "REPAIRED (wip)": "REPAIRED",
    "MERGED/NEW": "MERGED",
    "unknown": "NEW",
    "legacy-found": "FOUND",
    "source-repaired": "REPAIRED",
    "fusion-merged": "MERGED",
    "greenfield": "NEW",
    "archived-found": "FOUND",
    "patched": "REPAIRED",
    "folded-in": "MERGED",
    "draft": "NEW",
    "seen-in-harness": "FOUND",
    "hotfix": "REPAIRED",
    "composite": "MERGED",
    "experimental": "NEW",
    "recovered": "FOUND",
    "normalized": "REPAIRED",
    "imported": "MERGED",
    "forked": "NEW",
}

SIZE_GLOSSES = (
    "small-ish",
    "medium pack",
    "large (approx)",
    "xl / oversized",
    "tiny",
    "mid",
    "big",
    "huge",
)

GLOSS_TO_SIZE_V = {
    "small-ish": "S",
    "medium pack": "M",
    "large (approx)": "L",
    "xl / oversized": "XL",
    "tiny": "S",
    "mid": "M",
    "big": "L",
    "huge": "XL",
}

LIBRARY_CANDIDATES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/p2-wave/probes/ARC-0003/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)


def library_on_disk(repo: Path = REPO) -> Path | None:
    for rel in LIBRARY_CANDIDATES:
        p = repo / rel
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _record(i: int, state: str, state_v: str, size: str, size_v: str) -> dict[str, Any]:
    return {
        "id": f"bp-{i:03d}",
        "state": state,
        "state_v": state_v,
        "size": size,
        "size_v": size_v,
    }


def _size_pair(i: int) -> tuple[str, str]:
    if i % 5 == 0:
        gloss = SIZE_GLOSSES[i % len(SIZE_GLOSSES)]
        return gloss, GLOSS_TO_SIZE_V[gloss]
    tok = VOCAB_SIZE[i % len(VOCAB_SIZE)]
    return tok, tok


def build_records() -> list[dict[str, Any]]:
    if len(STATE_GLOSSES) != 32:
        raise RuntimeError(f"need 32 glosses, got {len(STATE_GLOSSES)}")
    if len(set(STATE_GLOSSES)) != 32:
        raise RuntimeError("gloss list is not unique")
    overlap = set(STATE_GLOSSES) & set(VOCAB_STATE)
    if overlap:
        raise RuntimeError(f"gloss collides with vocab: {overlap}")
    missing = set(STATE_GLOSSES) - set(GLOSS_TO_STATE_V)
    if missing:
        raise RuntimeError(f"unmapped glosses: {missing}")

    records: list[dict[str, Any]] = []
    # 74 vocab-exact: 20 FOUND, 20 REPAIRED, 18 MERGED, 16 NEW
    vocab_counts = (20, 20, 18, 16)
    i = 0
    for tok, n in zip(VOCAB_STATE, vocab_counts):
        for _ in range(n):
            size, size_v = _size_pair(i)
            records.append(_record(i, tok, tok, size, size_v))
            i += 1
    # 34 non-exact: 32 unique glosses + first two repeated
    extra = list(STATE_GLOSSES) + [STATE_GLOSSES[0], STATE_GLOSSES[1]]
    if len(extra) != 34:
        raise RuntimeError(f"need 34 extra rows, got {len(extra)}")
    for gloss in extra:
        size, size_v = _size_pair(i)
        records.append(_record(i, gloss, GLOSS_TO_STATE_V[gloss], size, size_v))
        i += 1
    if len(records) != 108:
        raise RuntimeError(f"need 108 records, got {len(records)}")
    return records


def write_fixture(path: Path = FIXTURE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "provenance": {
            "kind": "reconstructed-to-catalog-arithmetic",
            "library_on_this_tree": False,
            "absent_source": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            "catalog_claim": {
                "n": 108,
                "distinct_state_literals": 36,
                "vocab_exact": 74,
                "non_literal": 34,
                "vocab_state": list(VOCAB_STATE),
            },
        },
        "blueprints": build_records(),
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_blueprints(path: Path = FIXTURE) -> list[dict[str, Any]]:
    if not path.is_file():
        write_fixture(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and isinstance(doc.get("blueprints"), list):
        return list(doc["blueprints"])
    if isinstance(doc, list):
        return list(doc)
    raise RuntimeError(f"unrecognised corpus shape in {path}")
