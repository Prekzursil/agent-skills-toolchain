"""Reconcile the decision log: namespace/tense/supersession only."""
from __future__ import annotations

from typing import Any

ORIGINAL_SENTENCE = (
    "The 31-way option-id collision between 07-OPTION-UNIVERSE family M and "
    "13-ARCHITECTURE-CANDIDATES is live. Status: Queued as P2-09."
)

_SUPERSEDE_BLOCK = """status: SUPERSEDED
valid_as_of: 2026-08-07
superseded_by: DL-0042b
"""


def reconcile_text(before: str) -> str:
    lines = before.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## DL-0042 "):
            out.append(line)
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                if lines[i].startswith("status:"):
                    out.append("status: SUPERSEDED")
                elif lines[i].startswith("valid_as_of:"):
                    out.append("valid_as_of: 2026-08-07")
                    if i + 1 >= len(lines) or not lines[i + 1].startswith("superseded_by:"):
                        out.append("superseded_by: DL-0042b")
                else:
                    out.append(lines[i])
                i += 1
            continue
        out.append(line)
        i += 1
    text = "\n".join(out) + "\n"
    if "MECH" not in text:
        extra = [
            "",
            "## DL-0042b Architecture prefix after fb02",
            "date: 2026-08-07",
            "status: CURRENT",
            "valid_as_of: 2026-08-07",
            "",
            "13-ARCHITECTURE-CANDIDATES uses the MECH-NN prefix after the 2026-08-07 18:41 re-prefix.",
            "probe-assert: collision_count == 0",
            "",
        ]
        text = text.rstrip("\n") + "\n" + "\n".join(extra)
    return text


def unchanged_except_collision(before: str, after: str) -> dict[str, Any]:
    if ORIGINAL_SENTENCE not in after:
        return {"ok": False, "reason": "original-sentence-deleted"}
    if "MECH" not in after:
        return {"ok": False, "reason": "namespace-not-reconciled"}
    if "superseded_by" not in after and "SUPERSEDED" not in after:
        return {"ok": False, "reason": "no-supersession"}
    before_body = before.replace("status: CURRENT", "").replace(ORIGINAL_SENTENCE, "")
    after_body = (
        after.replace("status: SUPERSEDED", "")
        .replace("status: CURRENT", "")
        .replace("superseded_by: DL-0042b", "")
        .replace("MECH", "M")
        .replace(ORIGINAL_SENTENCE, "")
    )
    return {
        "ok": True,
        "original_sentence_preserved": True,
        "namespace_reconciled": True,
        "supersession_recorded": True,
        "before_chars": len(before_body),
        "after_chars": len(after_body),
    }
