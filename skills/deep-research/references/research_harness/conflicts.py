"""Contradiction detection: the ``contradicted`` verdict + "Disputed" callout.

Lens 12 find 9. The claim audit (``claims.py``) knows supported / partial /
unsupported / unchecked - nothing says "two graded sources assert *different*
values for the same claim". Deep-research systems that silently pick one number
ship a confident falsehood half the time; the honest move is to mark the claim
``contradicted``, show BOTH values with their provenance, and say which one the
grading prefers (tier first, then recency) so a reader can weigh it.

Deterministic and offline: values are extracted from the cited evidence spans
with regexes (numbers with a trailing unit token, percents, currencies, ISO /
long-form dates), normalised (``1,200`` -> ``1200``, ``12.50%`` -> ``12.5 %``,
``January 15, 2026`` -> ``2026-01-15``), and compared *per kind*: two
citations conflict when they both quote a value of the same kind (same unit,
or both dates, or both bare numbers) and share none. Grades stay a plain
``{citation_index: Grade}`` mapping so this module never imports the renderer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .claims import CONTRADICTED, Claim
from .grading import Grade

__all__ = [
    "CONTRADICTED",
    "Dispute",
    "DisputedValue",
    "detect_conflict",
    "extract_values",
    "resolve_claims",
]

_TIER_RANK = {"A": 2, "B": 1, "C": 0}

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ORDINAL = r"(?:st|nd|rd|th)?"
_ISO_DATE_RE = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_MDY_RE = re.compile(
    rf"\b(?P<mon>{_MONTH_ALT})\.?\s+(?P<d>\d{{1,2}}){_ORDINAL},?\s+(?P<y>\d{{4}})\b",
    re.IGNORECASE,
)
_DMY_RE = re.compile(
    rf"\b(?P<d>\d{{1,2}}){_ORDINAL}\s+(?P<mon>{_MONTH_ALT})\.?,?\s+(?P<y>\d{{4}})\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(
    r"(?P<cur>[$€£¥])?(?<![\w.])(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?"
    r"(?P<pct>\s?%)?(?:\s+(?P<unit>[A-Za-z][\w/.-]*))?"
)
# Words that follow a number without being its unit ("3 in the year").
_STOPWORDS = frozenset(
    """
    a an the and or but nor of to in on at by for from with as is are was were be
    been being it its this that these those then than there here when where which
    who whom while after before since during into onto within without over under
    up down more less about around only just also again not no yes per each every
    some any all both either neither so such very too if because although though
    however whereas
    """.split()
)
# After a currency prefix only a magnitude word is a unit ("$500 million").
_MAGNITUDES = frozenset(
    {"thousand", "million", "billion", "trillion", "k", "m", "bn", "b"}
)
_DATE_KIND = "date"


def _norm_number(num: str, dec: str | None) -> str:
    num = num.replace(",", "")
    if dec:
        dec = dec.rstrip("0")
        if len(dec) > 1:
            return num + dec
    return num


def _date_value(year: str, month: int, day: int) -> str | None:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{int(year):04d}-{month:02d}-{day:02d}"


def _find_dates(text: str) -> tuple[list[tuple[int, str]], str]:
    """Return ``[(position, ISO date)]`` and the text with those spans blanked."""
    found: list[tuple[int, str]] = []
    chars = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(start, end):
            chars[i] = " "

    for match in _ISO_DATE_RE.finditer(text):
        value = _date_value(match["y"], int(match["m"]), int(match["d"]))
        if value:
            found.append((match.start(), value))
            blank(match.start(), match.end())
    for pattern in (_MDY_RE, _DMY_RE):
        for match in pattern.finditer(text):
            if any(chars[i] != text[i] for i in range(match.start(), match.end())):
                continue  # overlaps a date already taken
            value = _date_value(
                match["y"], _MONTHS[match["mon"].lower()], int(match["d"])
            )
            if value:
                found.append((match.start(), value))
                blank(match.start(), match.end())
    return found, "".join(chars)


def extract_values(text: str) -> tuple[str, ...]:
    """Normalised comparable values in ``text``, first-seen order, de-duplicated.

    ``"reached 500 Wh/kg in 2026"`` -> ``("500 wh/kg", "2026")``;
    ``"$500 million raised"`` -> ``("500 $ million",)``;
    ``"on January 15, 2026"`` -> ``("2026-01-15",)``. Dates are taken first so
    their digits are never re-read as bare numbers.
    """
    found, remaining = _find_dates(text)
    for match in _NUMBER_RE.finditer(remaining):
        parts = [_norm_number(match["num"], match["dec"])]
        unit = (match["unit"] or "").rstrip(".,;:").lower()
        if match["cur"]:
            parts.append(match["cur"])
            if unit in _MAGNITUDES:
                parts.append(unit)
        elif match["pct"]:
            parts.append("%")
        elif unit and unit not in _STOPWORDS:
            parts.append(unit)
        found.append((match.start(), " ".join(parts)))
    found.sort(key=lambda item: item[0])
    return tuple(dict.fromkeys(value for _, value in found))


def _kind(value: str) -> str:
    """Comparison bucket: the unit part, ``date`` for dates, ``""`` for bare numbers."""
    if _ISO_DATE_RE.fullmatch(value):
        return _DATE_KIND
    _, _, unit = value.partition(" ")
    return unit


@dataclass(frozen=True, slots=True)
class DisputedValue:
    """One side of a dispute: a value, who cited it, and how that source graded."""

    value: str
    citation_index: int
    tier: str
    provenance: str


@dataclass(frozen=True, slots=True)
class Dispute:
    """A claim whose citations quote incompatible values."""

    claim_text: str
    values: tuple[DisputedValue, ...]
    preferred_index: int

    @property
    def callout(self) -> str:
        """Markdown callout: both values with provenance, plus the preferred one."""
        sides = "; ".join(
            f"{v.value} [{v.citation_index}] `{v.provenance}`"
            if v.provenance
            else f"{v.value} [{v.citation_index}]"
            for v in self.values
        )
        return (
            f"**Disputed:** {self.claim_text} - sources disagree: {sides} "
            f"(preferred: [{self.preferred_index}], by tier then recency)."
        )


def _preference(grade: Grade | None, citation_index: int) -> tuple[int, int, int]:
    if grade is None:
        return (-1, 0, -citation_index)
    return (_TIER_RANK.get(grade.tier, -1), 1 if grade.recent else 0, -citation_index)


def detect_conflict(claim: Claim, grades: Mapping[int, Grade]) -> Dispute | None:
    """``Dispute`` when two of the claim's citations quote incompatible values.

    Values are bucketed by kind; a kind quoted by two citations with no shared
    value is a conflict. A claim with one cited value-bearing span, or spans
    without values, never conflicts (nothing to disagree with).
    """
    per_citation: dict[int, dict[str, list[str]]] = {}
    for span in claim.evidence:
        kinds = per_citation.setdefault(span.citation_index, {})
        for value in extract_values(span.cited_text):
            bucket = kinds.setdefault(_kind(value), [])
            if value not in bucket:
                bucket.append(value)
    with_values = {idx: kinds for idx, kinds in per_citation.items() if kinds}
    if len(with_values) < 2:
        return None

    conflicting_kinds: set[str] = set()
    indexes = list(with_values)
    for i, left in enumerate(indexes):
        for right in indexes[i + 1 :]:
            for kind in with_values[left].keys() & with_values[right].keys():
                if not set(with_values[left][kind]) & set(with_values[right][kind]):
                    conflicting_kinds.add(kind)
    if not conflicting_kinds:
        return None

    values: list[DisputedValue] = []
    for idx in indexes:
        grade = grades.get(idx)
        for kind, bucket in with_values[idx].items():
            if kind not in conflicting_kinds:
                continue
            for value in bucket:
                values.append(
                    DisputedValue(
                        value=value,
                        citation_index=idx,
                        tier=grade.tier if grade else "?",
                        provenance=grade.provenance if grade else "",
                    )
                )
    disputed_indexes = {v.citation_index for v in values}
    preferred = max(disputed_indexes, key=lambda idx: _preference(grades.get(idx), idx))
    return Dispute(
        claim_text=claim.text, values=tuple(values), preferred_index=preferred
    )


def resolve_claims(
    claims: Sequence[Claim], grades: Mapping[int, Grade]
) -> tuple[tuple[Claim, ...], tuple[Dispute, ...]]:
    """Mark conflicting claims ``contradicted``; return the claims and the disputes.

    Non-conflicting claims pass through untouched (their verifier verdict stands).
    """
    resolved: list[Claim] = []
    disputes: list[Dispute] = []
    for claim in claims:
        dispute = detect_conflict(claim, grades)
        if dispute is None:
            resolved.append(claim)
            continue
        resolved.append(replace(claim, support=CONTRADICTED))
        disputes.append(dispute)
    return tuple(resolved), tuple(disputes)
