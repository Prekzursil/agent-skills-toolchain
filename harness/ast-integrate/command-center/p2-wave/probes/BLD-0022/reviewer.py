"""Quote-only rescorer. Does not read agent summaries or inference text.

Independence is the input restriction required by BLD-0022: re-read owner
quotations only, then re-score. A missing quote cannot be OWNER-EXPLICIT.
"""
from __future__ import annotations

import re

_NEG = re.compile(
    r"\b(not|never|don't|do not|reject|rejected|unselected)\b",
    re.IGNORECASE,
)
_CHOSE = re.compile(
    r"\b(select|selected|choose|chose|chosen|pick|picked|accept|accepted|is)\b",
    re.IGNORECASE,
)


def score_quote(option_id: str, owner_quote: str | None) -> str:
    """Return OWNER-EXPLICIT or NOT-OWNER-EXPLICIT from the quote string alone."""
    if not isinstance(owner_quote, str) or len(owner_quote.strip()) < 8:
        return "NOT-OWNER-EXPLICIT"
    text = owner_quote.strip()
    token = option_id
    # Control rows may use a decision token rather than an option id.
    needles = [token]
    if option_id.upper() in {"PR-ONLY", "CTRL-PR-ONLY-FIXTURE", "RELEASE-MODE"}:
        needles.append("PR-ONLY")
    hit = None
    for n in needles:
        if n.lower() in text.lower():
            hit = n
            break
    if hit is None:
        return "NOT-OWNER-EXPLICIT"
    if _NEG.search(text):
        return "NOT-OWNER-EXPLICIT"
    if option_id.upper() in {"PR-ONLY", "CTRL-PR-ONLY-FIXTURE", "RELEASE-MODE"}:
        if re.search(r"release\s+mode", text, re.IGNORECASE) or re.search(
            r"\bis\s+PR-ONLY\b", text, re.IGNORECASE
        ):
            return "OWNER-EXPLICIT"
        return "NOT-OWNER-EXPLICIT"
    if _CHOSE.search(text):
        return "OWNER-EXPLICIT"
    return "NOT-OWNER-EXPLICIT"


def agrees_with_primary(primary: str, quote_only: str) -> bool:
    if primary == "OWNER-EXPLICIT":
        return quote_only == "OWNER-EXPLICIT"
    return quote_only == "NOT-OWNER-EXPLICIT"


def rescore_rows(rows: list[dict], n: int = 5) -> dict:
    picked = list(rows)[:n]
    if len(picked) < n:
        raise ValueError(f"need {n} rows to rescore, got {len(picked)}")
    details = []
    agreements = 0
    for row in picked:
        qscore = score_quote(str(row.get("id") or ""), row.get("owner_quote"))
        primary = str(row.get("classification") or "")
        ok = agrees_with_primary(primary, qscore)
        if ok:
            agreements += 1
        details.append(
            {
                "id": row.get("id"),
                "primary": primary,
                "quote_only": qscore,
                "agree": ok,
                "quote_present": bool(row.get("owner_quote")),
            }
        )
    disagreements = n - agreements
    return {
        "reviewer_id": "BLD-0022-quote-only-rescorer",
        "verdict": "PASS" if disagreements == 0 else "FAIL",
        "independent": True,
        "input_was_quotes_only": True,
        "rescored_count": n,
        "agreements": agreements,
        "disagreements": disagreements,
        "rows": details,
        "scope_not_agreement": True,
        "notes": (
            "Input to this scorer is owner_quote only. Agent summaries and "
            "inference fields are not read."
        ),
    }
