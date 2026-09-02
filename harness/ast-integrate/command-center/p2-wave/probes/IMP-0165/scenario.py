"""Shared IMP-0165 scenario: live extractor vs a nearest-neighbour mutant."""
from __future__ import annotations

import ast
import difflib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.role_extract import (  # noqa: E402
    CANONICAL_ROLES,
    SYNONYM_TABLE,
    UNKNOWN,
    extract_candidate_set,
    normalize_role,
    unknown_rate,
)
from candidates import CANDIDATES, labelled_stats  # noqa: E402

SRC = REPO / "tools/workflow_foundry/role_extract.py"

# Near-miss spellings a Levenshtein/difflib snap would pull onto critic.
NEAR_MISS = ("critc", "refutr", "red teem")
KNOWN_SYNONYMS = (
    ("critic", "critic"),
    ("red team", "critic"),
    ("refuter", "critic"),
    ("RED-TEAM", "critic"),
    ("devil's advocate", "critic"),
    ("author", "proposer"),
)
INVENTED = (
    "floor-wax-auditor",
    "banana-steward",
    "quantum-shepherd",
    "IMP-0165-invented-zxqv",
)
SUBSTRING_TRAPS = (
    "critical-path-owner",
    "red teammate",
    "referee-adjacent",
)
FORBIDDEN_MODULES = frozenset(
    {
        "difflib",
        "Levenshtein",
        "fuzzywuzzy",
        "rapidfuzz",
        "jellyfish",
        "textdistance",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        "get_close_matches",
        "SequenceMatcher",
        "levenshtein",
        "hamming",
        "jaro",
        "jaro_winkler",
        "closest",
        "nearest",
        "fuzzy",
    }
)


def snap_normalize(raw: str | None) -> str:
    """Forbidden mutant: snap an unknown key onto its nearest table neighbour."""
    if raw is None:
        return UNKNOWN
    key = (
        str(raw)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )
    key = "".join(ch if ch.isalnum() or ch == " " else " " for ch in key)
    key = " ".join(key.split())
    if not key:
        return UNKNOWN
    if key in CANONICAL_ROLES:
        return key
    if key in SYNONYM_TABLE:
        return SYNONYM_TABLE[key]
    pool = sorted(set(SYNONYM_TABLE) | set(CANONICAL_ROLES))
    hits = difflib.get_close_matches(key, pool, n=1, cutoff=0.6)
    if not hits:
        return UNKNOWN
    hit = hits[0]
    if hit in CANONICAL_ROLES:
        return hit
    return SYNONYM_TABLE.get(hit, UNKNOWN)


def production_source_is_exact() -> dict[str, Any]:
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: list[str] = []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module.split(".")[0])
        elif isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    bad_mod = sorted(set(imported) & FORBIDDEN_MODULES)
    bad_name = sorted(set(names) & FORBIDDEN_NAMES)
    return {
        "forbidden_modules": bad_mod,
        "forbidden_names": bad_name,
        "exact": not bad_mod and not bad_name,
        "source": str(SRC.relative_to(REPO).as_posix()),
    }


def both_states_synonym_vs_invented() -> dict[str, Any]:
    synonym_rows = []
    for surface, want in KNOWN_SYNONYMS:
        got = normalize_role(surface)
        synonym_rows.append(
            {
                "surface": surface,
                "expected": want,
                "got": got,
                "match": got == want,
            }
        )
    invented_rows = []
    for surface in INVENTED:
        got = normalize_role(surface)
        invented_rows.append(
            {
                "surface": surface,
                "expected": UNKNOWN,
                "got": got,
                "snapped": got != UNKNOWN,
                "match": got == UNKNOWN,
            }
        )
    trap_rows = []
    for surface in SUBSTRING_TRAPS:
        got = normalize_role(surface)
        trap_rows.append(
            {
                "surface": surface,
                "expected": UNKNOWN,
                "got": got,
                "match": got == UNKNOWN,
            }
        )
    ok = (
        all(r["match"] for r in synonym_rows)
        and all(r["match"] for r in invented_rows)
        and all(r["match"] for r in trap_rows)
    )
    return {
        "pass": ok,
        "synonym_rows": synonym_rows,
        "invented_rows": invented_rows,
        "substring_trap_rows": trap_rows,
    }


def no_silent_snap() -> dict[str, Any]:
    rows = []
    for surface in NEAR_MISS:
        live = normalize_role(surface)
        mutant = snap_normalize(surface)
        rows.append(
            {
                "surface": surface,
                "production": live,
                "nearest_neighbour_mutant": mutant,
                "production_unknown": live == UNKNOWN,
                "mutant_snapped": mutant != UNKNOWN,
            }
        )
    comparable = {
        "critic": normalize_role("critic"),
        "red team": normalize_role("red team"),
        "refuter": normalize_role("refuter"),
    }
    ast_scan = production_source_is_exact()
    ok = (
        all(r["production_unknown"] and r["mutant_snapped"] for r in rows)
        and set(comparable.values()) == {"critic"}
        and ast_scan["exact"]
    )
    return {
        "pass": ok,
        "near_miss_rows": rows,
        "comparable": comparable,
        "ast": ast_scan,
    }


def candidate_set_rate() -> dict[str, Any]:
    labels = labelled_stats()
    rows = extract_candidate_set(CANDIDATES)
    got = [r["canonical"] for r in rows]
    want = [exp for c in CANDIDATES for exp in c["expected"]]
    stats = unknown_rate(rows)
    recount_unknown = sum(1 for g in got if g == UNKNOWN)
    recount_rate = (recount_unknown / len(got)) if got else 0.0
    label_match = got == want
    computed = (
        stats["total"] == len(got)
        and stats["unknown"] == recount_unknown
        and stats["known"] == len(got) - recount_unknown
        and abs(float(stats["rate"]) - recount_rate) < 1e-12
        and abs(float(stats["rate"]) - float(labels["rate"])) < 1e-12
        and stats["total"] == labels["total"]
    )
    # Mutation: one extra invented row must raise the rate (not a hardcoded 0).
    mutated = list(rows) + [
        {
            "candidate_id": "mutation",
            "container": "participants",
            "index": 0,
            "participant_id": "mut",
            "surface": "brand-new-invented-role",
            "canonical": UNKNOWN,
        }
    ]
    mutated_stats = unknown_rate(mutated)
    rate_moves = float(mutated_stats["rate"]) > float(stats["rate"])
    # Both-states on the rate: all-known subset is 0; mixed set is labels.rate.
    known_only = [r for r in rows if r["canonical"] != UNKNOWN]
    zero = unknown_rate(known_only)
    both_states = (
        zero["unknown"] == 0
        and float(zero["rate"]) == 0.0
        and float(stats["rate"]) > 0.0
    )
    return {
        "pass": bool(label_match and computed and rate_moves and both_states),
        "label_match": label_match,
        "computed": computed,
        "rate_moves_on_extra_unknown": rate_moves,
        "both_states_rate": both_states,
        "stats": stats,
        "labels": labels,
        "recount_rate": recount_rate,
        "zero_subset_rate": zero["rate"],
        "mutated_rate": mutated_stats["rate"],
        "mismatches": [
            {"index": i, "got": g, "want": w}
            for i, (g, w) in enumerate(zip(got, want))
            if g != w
        ]
        + (
            [{"index": "len", "got": len(got), "want": len(want)}]
            if len(got) != len(want)
            else []
        ),
    }
