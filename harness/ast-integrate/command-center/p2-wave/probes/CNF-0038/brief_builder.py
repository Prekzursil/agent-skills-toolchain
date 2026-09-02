"""CNF-0005-style brief: claim + public API surface; strip conclusion/test/diff."""
from __future__ import annotations

import json
from pathlib import Path

import leak_detector as L
from paths import (
    AUTHOR_TEST,
    BRIEF_PATH,
    DIFF_PATCH,
    GENERATED,
    IMPLEMENTER_NOTES,
    PUBLIC_API,
    REPO,
    REQUIREMENT,
    UNIT,
)


def build_brief(dest: Path | None = None) -> dict:
    claim = REQUIREMENT.read_text(encoding="utf-8")
    surface = PUBLIC_API.read_text(encoding="utf-8")
    doc = {
        "unit_id": UNIT,
        "kind": "cnf-0005-style-blind-brief",
        "claim_statement": claim,
        "public_api_surface": surface,
        "raw_source": surface,
        "tests": None,
        "implementer_conclusion": None,
        "diff": None,
        "stripped": [
            "implementer_conclusion",
            "author_test",
            "diff",
            "confidence_band",
            "summary_table",
        ],
        "inputs_read": [
            REQUIREMENT.relative_to(REPO).as_posix(),
            PUBLIC_API.relative_to(REPO).as_posix(),
        ],
        "inputs_not_read": [
            AUTHOR_TEST.name,
            DIFF_PATCH.name,
            IMPLEMENTER_NOTES.name,
        ],
    }
    text = json.dumps(doc, indent=2, sort_keys=True)
    hits = L.scan(text)
    if hits:
        raise SystemExit(f"FAILED:CNF-0038 brief leaked {hits}")
    GENERATED.mkdir(parents=True, exist_ok=True)
    path = dest or BRIEF_PATH
    path.write_text(text + "\n", encoding="utf-8")
    return doc
