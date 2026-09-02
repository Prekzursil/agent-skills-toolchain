"""Mark inventory, nominative-use classifier, and name-collision rules for ADV-0052.

Catalog rule: 'works with X' is nominative; 'X Toolchain' is not.
"""
from __future__ import annotations

import re
from typing import Any

# Product / house marks this review treats as third-party identity.
# Nice classes are the software/SaaS pair (9, 42). USPTO serial numbers are
# not asserted: TMsearch returned a JS SPA shell with no structured hits.
MARKS: tuple[dict[str, Any], ...] = (
    {
        "id": "agent-skills",
        "phrase": "agent skills",
        "owner": "Anthropic, PBC",
        "nice_classes": [9, 42],
        "kind": "product-mark",
        "source_url": "https://www.anthropic.com/news/skills",
    },
    {
        "id": "claude",
        "phrase": "claude",
        "owner": "Anthropic, PBC",
        "nice_classes": [9, 42],
        "kind": "house-and-product-mark",
        "source_url": "https://www.anthropic.com/legal/consumer-terms",
    },
    {
        "id": "claude-code",
        "phrase": "claude code",
        "owner": "Anthropic, PBC",
        "nice_classes": [9, 42],
        "kind": "product-mark",
        "source_url": "https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview",
    },
    {
        "id": "anthropic",
        "phrase": "anthropic",
        "owner": "Anthropic, PBC",
        "nice_classes": [9, 42],
        "kind": "house-mark",
        "source_url": "https://www.anthropic.com/legal/consumer-terms",
    },
    {
        "id": "openai",
        "phrase": "openai",
        "owner": "OpenAI, L.L.C.",
        "nice_classes": [9, 42],
        "kind": "house-mark",
        "source_url": "https://registry.npmjs.org/openai",
    },
    {
        "id": "chatgpt",
        "phrase": "chatgpt",
        "owner": "OpenAI, L.L.C.",
        "nice_classes": [9, 42],
        "kind": "product-mark",
        "source_url": "https://registry.npmjs.org/openai",
    },
)

NOMINATIVE_CUES = (
    r"\bworks with\b",
    r"\bcompatible with\b",
    r"\bfor use with\b",
    r"\bintegrates with\b",
    r"\busing\b",
    r"\bvia\b",
    r"\bagainst\b",
)

# Catalog example: 'X Toolchain' is not nominative.
NON_NOMINATIVE_SHAPES = (
    r"{mark}(?:\s+|[-_])toolchain\b",
    r"{mark}(?:\s+|[-_])official\b",
    r"{mark}(?:\s+|[-_])certified\b",
    r"\bofficial(?:\s+|[-_]){mark}\b",
)

CONTROL_INFRINGING = "Claude-Code-Toolchain"
CONTROL_CLEAN = "zorch-quilt-niner-adv0052"
CONTROL_NOMINATIVE_PROSE = "works with Claude"
CONTROL_NON_NOMINATIVE_PROSE = "Claude Code Toolchain"


def normalize(text: str) -> str:
    t = (text or "").replace("@", " ").replace("/", " ").replace("_", "-")
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = t.replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _mark_pat(phrase: str) -> str:
    return r"\b" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"\b"


def marks_in(text: str) -> list[dict[str, Any]]:
    norm = normalize(text)
    hits = []
    for mark in MARKS:
        if re.search(_mark_pat(mark["phrase"]), norm):
            hits.append(mark)
    return hits


def is_nominative_prose(text: str) -> bool:
    raw = text or ""
    return any(re.search(p, raw, flags=re.I) for p in NOMINATIVE_CUES)


def non_nominative_shapes(text: str) -> list[dict[str, str]]:
    norm = normalize(text)
    found = []
    for mark in MARKS:
        mp = _mark_pat(mark["phrase"])
        for shape in NON_NOMINATIVE_SHAPES:
            pat = shape.format(mark=mp)
            if re.search(pat, norm):
                found.append(
                    {
                        "mark_id": mark["id"],
                        "phrase": mark["phrase"],
                        "owner": mark["owner"],
                        "shape": shape,
                        "nice_classes": mark["nice_classes"],
                    }
                )
    return found


def classify_name(name: str) -> dict[str, Any]:
    """Registry-independent identity classifier for a proposed package/display name."""
    hits = marks_in(name)
    shapes = non_nominative_shapes(name)
    flagged = bool(shapes) or (
        bool(hits) and not is_nominative_prose(name) and bool(re.search(r"toolchain", normalize(name)))
    )
    # A bare house-mark as the entire product name is also non-nominative.
    if hits and normalize(name) in {m["phrase"] for m in MARKS}:
        flagged = True
        shapes = shapes or [
            {
                "mark_id": hits[0]["id"],
                "phrase": hits[0]["phrase"],
                "owner": hits[0]["owner"],
                "shape": "name-equals-mark",
                "nice_classes": hits[0]["nice_classes"],
            }
        ]
    return {
        "name": name,
        "normalized": normalize(name),
        "marks": [
            {
                "id": m["id"],
                "phrase": m["phrase"],
                "owner": m["owner"],
                "nice_classes": m["nice_classes"],
            }
            for m in hits
        ],
        "non_nominative_shapes": shapes,
        "flagged": flagged,
        "reason": (
            "non-nominative product-form using a third-party mark"
            if flagged
            else "no third-party mark in a non-nominative product form"
        ),
    }


def classify_prose(text: str) -> dict[str, Any]:
    hits = marks_in(text)
    shapes = non_nominative_shapes(text)
    nominative = is_nominative_prose(text)
    flagged = bool(shapes) or (bool(hits) and not nominative)
    uses = []
    for mark in hits:
        use = "nominative" if nominative and not shapes else "non-nominative"
        if shapes and any(s["mark_id"] == mark["id"] for s in shapes):
            use = "non-nominative"
        elif nominative:
            use = "nominative"
        uses.append(
            {
                "mark_id": mark["id"],
                "phrase": mark["phrase"],
                "owner": mark["owner"],
                "use": use,
                "nice_classes": mark["nice_classes"],
            }
        )
    return {
        "text": text,
        "marks": uses,
        "non_nominative_shapes": shapes,
        "nominative_cue": nominative,
        "flagged": flagged,
        "reason": (
            "vendor mark used other than nominatively"
            if flagged
            else (
                "nominative use only"
                if nominative and hits
                else "no vendor mark"
            )
        ),
    }


def control_pair() -> dict[str, Any]:
    inf_name = classify_name(CONTROL_INFRINGING)
    clean_name = classify_name(CONTROL_CLEAN)
    inf_prose = classify_prose(CONTROL_NON_NOMINATIVE_PROSE)
    nom_prose = classify_prose(CONTROL_NOMINATIVE_PROSE)
    clean_prose = classify_prose("a local skill runner with no vendor house marks")
    calibrated = (
        inf_name["flagged"] is True
        and clean_name["flagged"] is False
        and inf_prose["flagged"] is True
        and nom_prose["flagged"] is False
        and clean_prose["flagged"] is False
    )
    return {
        "infringing_name": CONTROL_INFRINGING,
        "clean_name": CONTROL_CLEAN,
        "infringing_name_flagged": inf_name["flagged"],
        "clean_name_flagged": clean_name["flagged"],
        "non_nominative_prose_flagged": inf_prose["flagged"],
        "nominative_prose_flagged": nom_prose["flagged"],
        "clean_prose_flagged": clean_prose["flagged"],
        "calibrated": calibrated,
        "classifications": {
            "infringing_name": inf_name,
            "clean_name": clean_name,
            "non_nominative_prose": inf_prose,
            "nominative_prose": nom_prose,
            "clean_prose": clean_prose,
        },
    }
