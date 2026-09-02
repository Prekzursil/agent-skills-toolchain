"""Re-check transcript-sourced claims against raw transcript bytes."""
from __future__ import annotations

import json
from pathlib import Path

from role import (
    classify_role,
    context_changes_meaning,
    read_lf,
    substring_classify,
    surrounding_turn,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLAIMS = HERE / "fixtures" / "claims.json"

MENTION_CONTROL_ID = "C-MENTION-CONTROL"
DEFECT_TRAP_ID = "C-DEFECT-TRAP"
USE_IDS = frozenset({"C-USE-FP", "C-USE-INDEP"})
NEGATION_ID = "C-NEGATION"
ABSENT_ID = "C-ABSENT"


def load_claims() -> list[dict]:
    data = json.loads(CLAIMS.read_text(encoding="utf-8"))
    return list(data["claims"])


def _line_span(text: str, line_no: int, span: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    if line_no < 1 or line_no > len(lines):
        return None
    start = sum(len(x) for x in lines[: line_no - 1])
    idx = lines[line_no - 1].find(span)
    if idx < 0:
        return None
    return start + idx, start + idx + len(span)


def verdict_for(verbatim: bool, role: str, changed: bool) -> str:
    if not verbatim:
        return "QUOTE-NOT-FOUND"
    if role == "MENTION":
        return "MENTION-ONLY"
    if changed:
        return "CONTEXT-CHANGES-MEANING"
    if role == "USE":
        return "SUPPORTED"
    return "UNRESOLVED"


def audit_one(claim: dict) -> dict:
    rel = str(claim["transcript_path"]).replace("\\", "/")
    path = REPO / rel
    span = str(claim["quoted_span"])
    line_no = int(claim["line"])
    cid = str(claim["id"])
    text = read_lf(path)
    raw = text.encode("utf-8")
    loc = _line_span(text, line_no, span)
    verbatim = loc is not None
    if verbatim:
        start, end = loc
        role = classify_role(text, start, end)
        turn = surrounding_turn(text, start)
        changed = context_changes_meaning(turn, start, end, text)
        byte_offset = len(text[:start].encode("utf-8"))
    else:
        start = end = -1
        role = "ABSENT"
        turn = surrounding_turn(text, 0)
        changed = False
        byte_offset = -1
    broken = substring_classify(text, span)
    mutant = (
        classify_role(text, start, end, ignore_wrappers=True)
        if verbatim
        else "ABSENT"
    )
    row = {
        "id": cid,
        "claim": str(claim["claim"]),
        "source": {
            "locator": rel,
            "quoted_span": span,
            "line": line_no,
            "byte_offset": byte_offset,
        },
        "verbatim_found": verbatim,
        "role": role,
        "context_changes_meaning": changed,
        "surrounding_turn": turn,
        "verdict": verdict_for(verbatim, role, changed),
        "substring_matcher_role": broken,
        "wrapper_ignored_mutant_role": mutant,
        "char_start": start,
        "char_end": end,
        "byte_length": len(raw),
    }
    return row


def audit_all() -> list[dict]:
    return [audit_one(c) for c in load_claims()]


def mention_control_pass(rows: list[dict]) -> dict:
    row = next(r for r in rows if r["id"] == MENTION_CONTROL_ID)
    classified = row["role"]
    ok = classified == "MENTION" and row["verbatim_found"] is True
    return {
        "claim_id": MENTION_CONTROL_ID,
        "classified_as": classified,
        "substring_matcher_classified_as": row["substring_matcher_role"],
        "pass": ok,
        "notes": (
            "Mention-only control: the span appears only inside a quoted "
            "example. Role must be MENTION, not USE/assertion. Substring "
            "presence is not an assertion."
        ),
    }


def artifact_payload(doc: dict) -> dict:
    """Merge report (schema home) under top-level so probes accept both shapes."""
    merged: dict = {}
    report = doc.get("report")
    if isinstance(report, dict):
        merged.update(report)
    merged.update({k: v for k, v in doc.items() if k != "report"})
    return merged
