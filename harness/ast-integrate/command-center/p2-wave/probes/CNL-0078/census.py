#!/usr/bin/env python3
"""Live census: completeness_score has no producer on this worktree outside this unit.

Identifier mentions in stopping-expression parsers, schema examples, and
protocol JSON are not producers. A producer is a function/class that *computes*
completeness_score from a ledger (the coverage-leg formula). The undefined
component remains coverage_domain_identity: even a producer must bind the
idea-set those numerators union over, which no live module outside this unit
does.
"""
from __future__ import annotations

import re
from pathlib import Path

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    "_deps",
    "probes",
}
SKIP_FILE_PARTS = (
    "WORK-UNIT-CATALOG.json",
    "P2-CLOUD-LEFTOVER",
)

# A producer *defines* how completeness_score is computed, not how a snapshot
# key of that name is parsed/evaluated in a stopping expression.
PRODUCER_RE = re.compile(
    r"(?:^|\n)\s*(?:async\s+)?def\s+completeness_score\s*\("
    r"|(?:^|\n)\s*class\s+CompletenessScore\b"
)


def _classify(text: str) -> str:
    if PRODUCER_RE.search(text):
        return "producer"
    return "identifier_mention"


def census_completeness_score(repo: Path) -> dict:
    mentions: list[dict[str, str]] = []
    producers: list[dict[str, str]] = []
    roots = [
        repo / "tools",
        repo / "platform",
        repo / "skills",
        repo / "command-center" / "schema",
        repo / "command-center" / "design",
        repo / "command-center" / "receipts",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        files.extend(p for p in root.rglob("*") if p.is_file())
    for path in files:
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        if any(p in SKIP_DIR_NAMES for p in path.parts):
            continue
        rel = path.relative_to(repo).as_posix()
        if any(s in rel for s in SKIP_FILE_PARTS):
            continue
        if "CNL-0078" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "completeness_score" not in text:
            continue
        kind = _classify(text)
        row = {"path": rel, "kind": kind}
        mentions.append(row)
        if kind == "producer":
            producers.append(row)
    quota = (repo / "tools" / "council" / "quota" / "unique_ideas.py").is_file()
    expr_mod = (repo / "tools" / "council" / "stopping" / "expr.py").is_file()
    completeness_mod = (repo / "tools" / "council" / "completeness.py").is_file()
    schema = (repo / "command-center" / "schema" / "councilspec.v2.schema.json").is_file()
    return {
        "completeness_score_hits_outside_catalog_and_this_unit": producers,
        "identifier_mentions": [
            {"path": m["path"]} for m in mentions if m["kind"] == "identifier_mention"
        ],
        "identifier_mention_count": sum(
            1 for m in mentions if m["kind"] == "identifier_mention"
        ),
        "hit_count": len(producers),
        "tools_council_quota_unique_ideas_py": quota,
        "tools_council_stopping_expr_py": expr_mod,
        "tools_council_completeness_py": completeness_mod,
        "councilspec_v2_schema_present": schema,
        "undefined_component": "coverage_domain_identity",
        "undefined_component_reason": (
            "Catalog TST-0282 names three coverage legs (declared subquestions, "
            "required categories, evidence classes) but no live producer binds "
            "the idea-set those numerators union over. Identifier mentions in "
            "stopping-expression parsers and schema examples consume a snapshot "
            "key; they do not define coverage_domain_identity. Human-label "
            "calibration is a second undefined residual (not used as a gate here)."
        ),
    }
