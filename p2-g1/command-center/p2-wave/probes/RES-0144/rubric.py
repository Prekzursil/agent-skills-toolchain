"""Pre-published two-axis source-quality rubric (authority x independence).

Hashed before any source is scored. Changing a level definition after seeing
the 40-source sheets is a protocol violation, not a calibration update.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

AUTHORITY_LEVELS = ("PRIMARY", "MAINTAINER", "PRACTITIONER", "RETELLER")
INDEPENDENCE_LEVELS = ("ORIGINATING", "PARALLEL", "DERIVED", "SYNDICATED")
LOW_INDEPENDENCE = frozenset({"SYNDICATED"})

RUBRIC: dict[str, Any] = {
    "id": "RES-0144-two-axis-source-quality-v1",
    "title": "Authority x independence source-quality rubric",
    "protocol": (
        "Publish this document and its sha256 BEFORE scoring the 40-source set. "
        "Authority and independence are scored on separate axes. A primary "
        "source that is a syndicated reprint is still PRIMARY on authority and "
        "SYNDICATED (low) on independence. The axes must not be collapsed into "
        "a single 'quality' number."
    ),
    "axes": {
        "authority": {
            "id": "A",
            "question": "Is this the thing itself, a maintainer, a practitioner, or a re-teller?",
            "levels": {
                "PRIMARY": (
                    "The artifact is the thing itself: RFC/PEP/schema/license text, "
                    "or the implementing source file."
                ),
                "MAINTAINER": (
                    "Official documentation, README, changelog, or contributing "
                    "guide published by the project that owns the thing."
                ),
                "PRACTITIONER": (
                    "First-hand observation: measurement, reproduction, incident, "
                    "or operator notes that add a local experiment."
                ),
                "RETELLER": (
                    "News, tutorial, newsletter, or Q&A that restates another "
                    "source without adding observation."
                ),
            },
            "rule": "Assign the highest level whose definition matches. Fail closed to RETELLER.",
        },
        "independence": {
            "id": "I",
            "question": "Does this add observation, or restate another source?",
            "levels": {
                "ORIGINATING": "Adds observation not present in other members of the scored set.",
                "PARALLEL": (
                    "Independent observation of the same phenomenon as another "
                    "originating source (shared topic, distinct body)."
                ),
                "DERIVED": "Cites, paraphrases, or transforms another source without new observation.",
                "SYNDICATED": (
                    "Verbatim or near-verbatim copy of another source in the set. "
                    "This is the low-independence bucket."
                ),
            },
            "low_independence": ["SYNDICATED"],
            "rule": (
                "Assign the lowest independence that matches. Five identical "
                "bodies at five URLs are five SYNDICATED rows, not five votes."
            ),
        },
    },
    "forbidden_scorer_keys": [
        "gold_authority",
        "gold_independence",
        "expected",
        "label",
        "call_sheet_grade",
    ],
    "raters": {
        "A": {
            "id": "rater-A-publisher-class",
            "vendor_role": "openai-mechanical-publisher-class",
            "features": "URL host/path class and exact-body sha256 clustering only",
        },
        "B": {
            "id": "rater-B-content-ngram",
            "vendor_role": "anthropic-mechanical-content-ngram",
            "features": "body markers and pairwise word 5-gram Jaccard; URL is sealed",
        },
    },
    "agreement": (
        "Cohen's kappa on each axis over the 40-source set. Both rating sheets "
        "are committed. Perfect kappa on both axes is suspicious given planted "
        "borderline rows."
    ),
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def published_sha256(obj: Any | None = None) -> str:
    return hashlib.sha256(canonical_bytes(obj if obj is not None else RUBRIC)).hexdigest()


def dump_published(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(RUBRIC)
    path.write_bytes(raw + b"\n")
    return hashlib.sha256(raw).hexdigest()
