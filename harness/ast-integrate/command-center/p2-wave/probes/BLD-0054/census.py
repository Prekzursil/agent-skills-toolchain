#!/usr/bin/env python3
"""Catalog + disk census for BLD-0054.

Coverage of the four named units is computed from catalog rows and whether
their output_path exists on disk. Catalog intent without a receipt is not
treated as a live test.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

NAMED_FOUR = ("CNL-0099", "CNL-0100", "ADV-0071", "ADV-0100")

ABUSE_KEYWORDS = {
    "collusion": ("collusion", "same-tuple", "same tuple", "coordinated participants"),
    "sybil": ("sybil", "duplicate identit", "duplicate identit", "same model twice"),
    "chair_capture": (
        "moderator capture",
        "chair capture",
        "moderator/chair",
        "chair-sycophancy",
        "sycophancy",
    ),
    "strategic_abstention": ("strategic abstention", "no-show paradox", "abstention"),
    "vote_trading": ("vote trading", "vote-trading", "complementary ballot"),
    "idea_count_gaming": (
        "idea-count",
        "idea count",
        "wording variants",
        "trivial variants",
        "uniqueness gate",
        "novelty",
    ),
    "citation_laundering": (
        "citation laundering",
        "circular citation",
        "citation cycle",
    ),
    "hallucinated_expertise": (
        "hallucinated expertise",
        "asserting expertise",
        "expertise it does not have",
        "competence probe",
    ),
    "hidden_conflict_of_interest": (
        "conflict of interest",
        "hidden conflict",
        "self-review",
        "self review",
        "reviewing its own",
    ),
    "artifact_injection": (
        "inject",
        "prompt injection",
        "participant artifact",
        "later stage",
        "instruction payload",
    ),
}

PRODUCTION_RUNTIME_CANDIDATES = (
    "tools/council",
    "tools/council/antifail",
    "platform/lib/councilspec",
    "tools/council/simulate.py",
    "tools/council/antifail/unanimity.py",
    "tools/council/antifail/injection.py",
)


def _blob(unit: dict) -> str:
    tests = unit.get("tests_required") or unit.get("tests_required") or []
    parts = [
        str(unit.get("id") or ""),
        str(unit.get("title") or ""),
        str(unit.get("question_or_target") or unit.get("target") or ""),
        " ".join(str(x) for x in tests),
        str(unit.get("evidence_requirement") or ""),
    ]
    return " ".join(parts).lower()


def abuses_from_text(text: str) -> list[str]:
    hits = []
    for abuse, kws in ABUSE_KEYWORDS.items():
        if any(kw.lower() in text for kw in kws):
            hits.append(abuse)
    return hits


def load_units() -> dict[str, dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id"):
            out[str(u["id"])] = u
    return out


def artifact_status(rel: str) -> dict:
    path = REPO / rel.replace("\\", "/")
    exists = path.is_file() and path.stat().st_size > 0
    return {
        "path": rel.replace("\\", "/"),
        "present": exists,
        "bytes": path.stat().st_size if exists else 0,
    }


def named_four_census(units: dict[str, dict] | None = None) -> dict:
    units = units or load_units()
    rows = []
    covered: set[str] = set()
    for uid in NAMED_FOUR:
        unit = units.get(uid) or {}
        out_rel = str(unit.get("output_path") or "")
        art = artifact_status(out_rel) if out_rel else {
            "path": "",
            "present": False,
            "bytes": 0,
        }
        mapped = abuses_from_text(_blob(unit))
        if mapped:
            covered.update(mapped)
        rows.append(
            {
                "unit_id": uid,
                "present_in_catalog": uid in units,
                "title": unit.get("title"),
                "question": unit.get("question_or_target"),
                "output_path": out_rel,
                "artifact": art,
                "mapped_abuses": mapped,
                "covers_as": "catalog-intent-only"
                if uid in units and not art["present"]
                else ("live-artifact" if art["present"] else "absent"),
            }
        )
    return {
        "named_units": list(NAMED_FOUR),
        "rows": rows,
        "catalog_mapped_abuses": sorted(covered),
        "artifacts_present": sum(1 for r in rows if r["artifact"]["present"]),
        "artifacts_expected": len(NAMED_FOUR),
    }


NAMED_ABUSE_CONTROL_FILES = (
    "tools/council/antifail/unanimity.py",
    "tools/council/antifail/injection.py",
    "tools/council/antifail/collusion.py",
    "tools/council/antifail/sybil.py",
    "tools/council/antifail/novelty.py",
    "tools/council/simulate.py",
)


def production_runtime_census() -> dict:
    hits = []
    for rel in PRODUCTION_RUNTIME_CANDIDATES:
        p = REPO / rel
        hits.append(
            {
                "path": rel,
                "present": p.exists(),
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
            }
        )
    root = REPO / "tools" / "council"
    py_files: list[str] = []
    if root.is_dir():
        py_files = sorted(
            p.relative_to(REPO).as_posix()
            for p in root.rglob("*.py")
            if p.is_file()
        )
    control_files = []
    for rel in NAMED_ABUSE_CONTROL_FILES:
        p = REPO / rel
        control_files.append({"path": rel, "present": p.is_file()})
    live_named = sum(1 for c in control_files if c["present"])
    if live_named:
        verdict = "NAMED-ABUSE-CONTROLS-PRESENT"
    elif py_files:
        verdict = "PARTIAL-TREE-MISSING-NAMED-ABUSE-CONTROLS"
    else:
        verdict = "ABSENT-ON-THIS-WORKTREE"
    return {
        "candidates": hits,
        "python_modules": py_files,
        "named_abuse_control_files": control_files,
        "named_abuse_control_files_present": live_named,
        "any_present": bool(py_files or any(h["present"] for h in hits)),
        "verdict": verdict,
    }


def estate_catalog_hits(units: dict[str, dict] | None = None) -> dict[str, list[str]]:
    """Keyword hits elsewhere in the catalog. Intent only; not receipts."""
    units = units or load_units()
    hits: dict[str, list[str]] = {k: [] for k in ABUSE_KEYWORDS}
    for uid, unit in units.items():
        if uid in NAMED_FOUR or uid == "BLD-0054":
            continue
        blob = _blob(unit)
        for abuse in abuses_from_text(blob):
            if uid not in hits[abuse]:
                hits[abuse].append(uid)
    for k in hits:
        hits[k] = sorted(hits[k])[:12]
    return hits


def uncovered_by_named_four(spec_abuses: tuple[str, ...], census: dict) -> list[str]:
    covered = set(census.get("catalog_mapped_abuses") or [])
    return [a for a in spec_abuses if a not in covered]


def run_census(spec_abuses: tuple[str, ...]) -> dict:
    units = load_units()
    named = named_four_census(units)
    return {
        "named_four": named,
        "production_runtime": production_runtime_census(),
        "estate_catalog_hits_intent_only": estate_catalog_hits(units),
        "uncovered_by_named_four": uncovered_by_named_four(spec_abuses, named),
        "receipts_note": (
            "Coverage of CNL-0099/CNL-0100/ADV-0071/ADV-0100 is computed from "
            "catalog rows plus whether output_path exists on disk. A planned "
            "unit with no receipt does not cover an abuse."
        ),
    }
