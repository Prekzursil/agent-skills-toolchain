"""Unicode-confusable folding plus normalised edit distance.

Folding is NFKC, then casefold, then a small homoglyph/separator table.
A pair is a collision when folded Levenshtein distance is <= 1 and the
original strings differ. Distance 0 after fold is an exact homoglyph or
separator/digit squat.
"""
from __future__ import annotations

import unicodedata
from typing import Iterable

# After NFKC+casefold. Keys are single characters.
HOMOGLYPH = {
    "0": "o",
    "1": "l",
    "i": "l",
    "|": "l",
    "5": "s",
    "8": "b",
    "_": "-",
    "–": "-",
    "—": "-",
    "а": "a",  # Cyrillic a
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
}


def fold_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name)).casefold()
    out: list[str] = []
    for ch in text:
        mapped = HOMOGLYPH.get(ch, ch)
        if mapped == "i":
            mapped = HOMOGLYPH.get(mapped, mapped)
        out.append(mapped)
    return "".join(out)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def folded_distance(left: str, right: str) -> int:
    return levenshtein(fold_name(left), fold_name(right))


def raw_distance(left: str, right: str) -> int:
    return levenshtein(str(left), str(right))


def generate_confusable(protected: str) -> str:
    """Digit/homoglyph squat: first ASCII 'o' -> '0', else first 'i'/'l' -> '1'."""
    chars = list(protected)
    for i, ch in enumerate(chars):
        if ch == "o":
            chars[i] = "0"
            return "".join(chars)
        if ch == "O":
            chars[i] = "0"
            return "".join(chars)
    for i, ch in enumerate(chars):
        if ch in ("i", "l", "I"):
            chars[i] = "1"
            return "".join(chars)
    return protected + "0"


def generate_homoglyph(protected: str) -> str:
    """Cyrillic 'е' for Latin 'e' when present, else Cyrillic 'а' for 'a'."""
    if "e" in protected:
        return protected.replace("e", "е", 1)
    if "a" in protected:
        return protected.replace("a", "а", 1)
    return "а" + protected


def ranked_collisions(
    existing: Iterable[str],
    protected: Iterable[str],
    *,
    max_distance: int = 1,
) -> list[dict]:
    """Every existing name against the protected set, excluding self-pairs."""
    rows: list[dict] = []
    prot = list(protected)
    seen: set[tuple[str, str]] = set()
    for name in existing:
        for target in prot:
            if name == target:
                continue
            key = (name, target)
            if key in seen:
                continue
            seen.add(key)
            dist = folded_distance(name, target)
            if dist <= max_distance:
                rows.append(
                    {
                        "name": name,
                        "confused_with": target,
                        "folded_distance": dist,
                        "raw_distance": raw_distance(name, target),
                        "folded_name": fold_name(name),
                        "folded_target": fold_name(target),
                    }
                )
    rows.sort(key=lambda r: (r["folded_distance"], r["raw_distance"], r["name"]))
    return rows


def mutant_flags_distinct(name: str, protected: Iterable[str]) -> list[dict]:
    """KNOWN-BROKEN scanner: reports the candidate as confusable with every protected name."""
    return [
        {
            "name": name,
            "confused_with": target,
            "folded_distance": 0,
            "mutant": True,
        }
        for target in protected
        if name != target
    ]
