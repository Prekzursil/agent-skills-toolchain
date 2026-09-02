"""Load free-text mechanism strings: live registry if present, else stand-in.

Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is preferred. When it is
absent (this Linux worktree), the stand-in is built from catalog-named
mechanism paraphrases plus held-out and gap strings — not a fabricated
284-row mapping of unseen live strings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from discriminate import HELDOUT, GAP_STRINGS
from vocab import MECHANISMS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SEARCH_PATHS = (
    Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    HERE / "fixtures/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)


def find_live() -> Path | None:
    for path in SEARCH_PATHS:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def _iter_mech_strings(value: Any) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, str):
        s = value.strip()
        if s:
            out.append(s)
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_iter_mech_strings(item))
        return out
    if isinstance(value, dict):
        for key in ("name", "id", "text", "mechanism", "label"):
            if key in value:
                out.extend(_iter_mech_strings(value[key]))
    return out


def extract_live(doc: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for cand in doc.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        cid = str(cand.get("id") or "")
        for text in _iter_mech_strings(cand.get("mechanisms")):
            key = " ".join(text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            rows.append({"text": text, "kind": "live", "source": cid or "candidate"})
    return rows


def standin_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for mech in MECHANISMS:
        for alias in mech["aliases"]:
            rows.append(
                {
                    "text": str(alias),
                    "kind": "alias",
                    "source": str(mech["id"]),
                }
            )
    for item in HELDOUT:
        rows.append(
            {
                "text": str(item["text"]),
                "kind": "held_out",
                "source": str(item["gold"]),
            }
        )
    for text in GAP_STRINGS:
        rows.append({"text": text, "kind": "gap", "source": "planted-gap"})
    return rows


def load_corpus() -> dict[str, Any]:
    live = find_live()
    if live is not None:
        doc = json.loads(live.read_text(encoding="utf-8"))
        rows = extract_live(doc)
        extra = [
            r
            for r in standin_rows()
            if r["kind"] in {"held_out", "gap"}
        ]
        # Keep held-out + gap controls even on a live load so probes stay armed.
        seen = {" ".join(r["text"].lower().split()) for r in rows}
        for row in extra:
            key = " ".join(row["text"].lower().split())
            if key not in seen:
                rows.append(row)
                seen.add(key)
        return {
            "origin": "live-file",
            "live_present": True,
            "path": str(live),
            "n_candidates": len(doc.get("candidates") or []),
            "n_distinct": len(rows),
            "rows": rows,
            "absent_reason": None,
        }
    rows = standin_rows()
    return {
        "origin": "catalog-derived-stand-in",
        "live_present": False,
        "path": "command-center/p2-wave/probes/WFA-0058/corpus.py",
        "n_candidates": 0,
        "n_distinct": len(rows),
        "rows": rows,
        "absent_reason": (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux "
            "worktree. Mapping covers catalog-named paraphrases, 20 "
            "held-out examples, and planted gaps — not a fabricated "
            "census of the 282 unseen live mechanism strings."
        ),
    }


def distinct_texts(corpus: dict[str, Any] | None = None) -> list[str]:
    data = corpus if corpus is not None else load_corpus()
    return [str(r["text"]) for r in data["rows"]]
