#!/usr/bin/env python3
"""What is measurable as written: scan cited spec files + catalog quotes.

Two independent signals:
  1. Path.is_file on every cited spec path and common remaps.
  2. Catalog JSON walk: formulas/thresholds quoting the eight targets, vs
     identity/taxonomy/corpus/admissibility definitions (absent).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
HERE = Path(__file__).resolve().parent

CITED = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]

REMAPS = [
    REPO / "_USER-PROMPTS.md",
    REPO / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "11-COUNCIL-SPECIFICATION.md",
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "_USER-PROMPTS.md",
    REPO / "command-center" / "sources" / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "_USER-PROMPTS.md",
    Path.home() / ".claude" / "harness-restore-20260806" / "11-COUNCIL-SPECIFICATION.schema.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
]

TARGETS = (
    "unique-idea",
    "category",
    "novelty",
    "diversity",
    "coverage",
    "objection",
    "counterexample",
    "evidence",
)

# A target is measurable-as-written only if the spec writes identity + operator + threshold.
FORMULA_HINTS = {
    "unique-idea": [
        r"unique_ideas\s*>=\s*100",
        r"100 unique ideas",
        r"unique-idea",
    ],
    "category": [r"\bcategor(y|ies)\b"],
    "novelty": [r"\bnovelty\b"],
    "diversity": [r"\bdiversity\b"],
    "coverage": [r"\bcoverage\b"],
    "objection": [
        r"no_new_objection_rounds",
        r"\bobjection\b",
    ],
    "counterexample": [
        r"unresolved_load_bearing_counterexample",
        r"\bcounterexample\b",
    ],
    "evidence": [
        r"evidence_saturation",
        r"\bevidence\b",
    ],
}

IDENTITY_HINTS = {
    "unique-idea": [
        r"canonical mechanism",
        r"jaccard",
        r"deduplicat",
        r"when two ideas are the same",
    ],
    "category": [r"taxonomy T", r"declared taxonomy", r"category ids"],
    "novelty": [r"prior-art", r"prior art corpus"],
    "diversity": [r"shannon", r"pairwise jaccard", r"entropy"],
    "coverage": [r"per-category", r"per category", r"empty categor"],
    "objection": [r"admissible", r"unfalsifiable"],
    "counterexample": [r"expected_rc", r"observed_rc", r"executable"],
    "evidence": [r"sha256", r"resolvable", r"saturation iff"],
}


def _exists(path: Path) -> dict:
    try:
        present = path.is_file()
        size = path.stat().st_size if present else 0
    except OSError:
        present, size = False, 0
    return {
        "path": str(path),
        "present": present,
        "bytes": size,
    }


def spec_files() -> dict:
    cited = []
    for raw in CITED:
        cited.append(_exists(Path(raw)))
    remaps = [_exists(p) for p in REMAPS]
    present = [r for r in cited + remaps if r["present"]]
    return {
        "cited": cited,
        "remaps": remaps,
        "any_present": bool(present),
        "present_paths": [r["path"] for r in present],
        "signal": "Path.is_file",
    }


def _find_unit(units: list, uid: str) -> tuple[dict | None, int]:
    for i, u in enumerate(units):
        if isinstance(u, dict) and u.get("id") == uid:
            return u, i
    return None, -1


def catalog_quotes() -> dict:
    text = CATALOG.read_text(encoding="utf-8")
    data = json.loads(text)
    units = data.get("work_units") or []
    unit, idx = _find_unit(units, "CNL-0009")
    q = str((unit or {}).get("question_or_target") or "")
    # Line number of the question field: first occurrence of the eight-target clause.
    needle = "eight declared targets"
    line = 1 + text[: text.find(needle)].count("\n") if needle in text else 0
    named = [t for t in TARGETS if t in q]
    # Stopping-expression quotes elsewhere in the catalog (thresholds without identity).
    thresholds = {
        "unique-idea": bool(re.search(r"unique_ideas\s*>=\s*100", text)),
        "category": False,
        "novelty": False,
        "diversity": False,
        "coverage": False,
        "objection": bool(re.search(r"no_new_objection_rounds\s*>=\s*2", text)),
        "counterexample": bool(
            re.search(r"unresolved_load_bearing_counterexample\s*==\s*0", text)
        ),
        "evidence": bool(re.search(r"evidence_saturation\s*==\s*true", text)),
    }
    identity_in_catalog_unit_question = {}
    for t in TARGETS:
        identity_in_catalog_unit_question[t] = any(
            re.search(p, q, re.I) for p in IDENTITY_HINTS[t]
        )
    related = {}
    for uid in (
        "CNL-0051",
        "CNL-0053",
        "CNL-0054",
        "CNL-0060",
        "CNL-0068",
        "CNL-0078",
        "CNL-0079",
        "IMP-0300",
        "IMP-0301",
    ):
        u, _ = _find_unit(units, uid)
        related[uid] = {
            "present": u is not None,
            "title": (u or {}).get("title"),
            "question": (u or {}).get("question_or_target"),
        }
    return {
        "signal": "catalog JSON walk + regex (different mechanism from Path.is_file)",
        "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
        "cnl_0009_index": idx,
        "question_line": line,
        "question": q,
        "targets_named_in_question": named,
        "all_eight_named": named == list(TARGETS),
        "thresholds_quoted_elsewhere": thresholds,
        "identity_defined_in_cnl0009_question": identity_in_catalog_unit_question,
        "related_units": {
            k: {"present": v["present"], "title": v["title"]}
            for k, v in related.items()
        },
    }


def per_target_as_written(files: dict, quotes: dict) -> dict:
    rows = {}
    spec_on_disk = files["any_present"]
    for t in TARGETS:
        identity = quotes["identity_defined_in_cnl0009_question"][t]
        threshold = quotes["thresholds_quoted_elsewhere"][t]
        named = t in quotes["targets_named_in_question"]
        measurable = bool(spec_on_disk and identity and threshold)
        if not spec_on_disk:
            why = (
                "Cited spec files are absent on this worktree, so nothing is "
                "measurable as written in the spec. Catalog names and later "
                "stopping thresholds are not a substitute for an identity relation."
            )
        elif not identity:
            why = "Named, possibly with a threshold, but no identity/taxonomy/corpus/admissibility operator."
        else:
            why = "Would be measurable if operator and threshold both appear in the spec body."
        rows[t] = {
            "named_in_cnl0009_question": named,
            "threshold_quoted_in_catalog": threshold,
            "identity_operator_written": identity,
            "spec_files_on_disk": spec_on_disk,
            "measurable_as_written": measurable,
            "why": why,
        }
    unmeasurable = [t for t, r in rows.items() if not r["measurable_as_written"]]
    return {
        "rows": rows,
        "unmeasurable": unmeasurable,
        "measurable": [t for t in TARGETS if t not in unmeasurable],
        "all_eight_unmeasurable": unmeasurable == list(TARGETS),
    }


def scan() -> dict:
    files = spec_files()
    quotes = catalog_quotes()
    verdict = per_target_as_written(files, quotes)
    return {
        "spec_files": files,
        "catalog_quotes": quotes,
        "verdict": verdict,
    }


if __name__ == "__main__":
    doc = scan()
    v = doc["verdict"]
    print(f"spec_any_present={doc['spec_files']['any_present']}")
    print(f"eight_named={doc['catalog_quotes']['all_eight_named']}")
    print(f"unmeasurable={v['unmeasurable']}")
    print(f"all_eight_unmeasurable={v['all_eight_unmeasurable']}")
