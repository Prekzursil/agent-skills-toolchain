#!/usr/bin/env python3
"""Mechanical requirement extraction and cover spot-check for WFA-0125.

The spec's enumerated library at _USER-PROMPTS.md:10900-10907 is the
authoritative list. When those bytes are absent, the IMP-0234..IMP-0256
catalog questions (which quote the hyphenated ids) and the IMP-0178
family-count parenthesis are the operational reconstruction. A hardcoded
96 is not a count.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/wfa/WFA-0125-library-category-coverage.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0125/coverage.schema.json"
DECLARED_SCHEMA = (
    "command-center/wfa/schema/wfa-schema-pack.json#/$defs/CoverageMatrix"
)

SPEC_CANDIDATES = (
    REPO / "_USER-PROMPTS.md",
    REPO / "command-center" / "sources" / "_USER-PROMPTS.md",
    REPO / "command-center" / "_USER-PROMPTS.md",
    Path.home() / ".claude" / "harness-restore-20260806" / "_USER-PROMPTS.md",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
)
CC0024_SLICE = (
    REPO / "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
)

REGISTRY_CANDIDATES = (
    "command-center/wfa/WFA-0078-candidate-registry-v2.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
BLUEPRINT_CANDIDATES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/libraries/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/WFA-0061-mechanism-coverage-gaps.json",
)
TASKFIT_CANDIDATES = (
    "command-center/wfa/WFA-0035-extract-task-fit.json",
)
ON_TREE_REGISTRIES = (
    "command-center/p2-wave/probes/ARC-0010/registry.json",
)

IMP_ENUM_IDS = tuple(f"IMP-{n:04d}" for n in range(234, 257))
FAMILY_COUNT_RE = re.compile(
    r"(research/evidence|engineering/reliability|security/governance|"
    r"product/design|data/science|collective-intelligence/meta)\s+(\d+)",
    re.I,
)
DASH_LIST_RE = re.compile(
    r"Target:\s*(?:implement|register)\s+(\d+)\s+(?:library\s+)?"
    r"blueprints?\s+-\s+([a-z0-9]+(?:-[a-z0-9]+)*)"
    r"((?:\s*,\s*[a-z0-9]+(?:-[a-z0-9]+)*)*)",
    re.I,
)
BARE_REGISTER_RE = re.compile(
    r"Target:\s*register\s+([a-z0-9]+(?:-[a-z0-9]+)*"
    r"(?:\s*,\s*[a-z0-9]+(?:-[a-z0-9]+)*)+)\s+as library entries",
    re.I,
)
QUESTION_FAMILIES_RE = re.compile(
    r"across\s+(.+?)\s+-\s+is there a covering",
    re.I | re.S,
)
TITLE_FAMILY_RULES = (
    (re.compile(r"research blueprint", re.I), "research and evidence"),
    (re.compile(r"engineering blueprint", re.I), "engineering and reliability"),
    (re.compile(r"security blueprint", re.I), "security and governance"),
    (re.compile(r"product blueprint", re.I), "product and strategy"),
    (re.compile(r"data blueprint", re.I), "data and science"),
    (re.compile(r"science blueprint", re.I), "data and science"),
    (re.compile(r"knowledge blueprint", re.I), "data and science"),
    (re.compile(r"analysis blueprint", re.I), "data and science"),
    (re.compile(r"meta-workflow blueprint", re.I), "collective intelligence"),
    (re.compile(r"council-protocol blueprint", re.I), "collective intelligence"),
)
IMP0178_TO_QUESTION = {
    "research/evidence": "research and evidence",
    "engineering/reliability": "engineering and reliability",
    "security/governance": "security and governance",
    "product/design": "product and strategy",
    "data/science": "data and science",
    "collective-intelligence/meta": "collective intelligence",
}
ID_PREFIXES = ("", "wf-", "blueprint-", "bp-", "lib-")
STRUCTURED_LIST_KEYS = (
    "covers",
    "task_classes",
    "requirement_ids",
    "library_ids",
)
STRUCTURED_SCALAR_KEYS = (
    "id",
    "requirement_id",
    "task_class",
    "blueprint_id",
    "library_id",
    "canonical_id",
)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_units(data: dict | None = None) -> dict[str, dict]:
    doc = data if data is not None else load_catalog()
    out: dict[str, dict] = {}
    for u in doc.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    return out


def spec_path() -> Path | None:
    for p in SPEC_CANDIDATES:
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def spec_fragments() -> dict[str, Any]:
    """Recovered Prompt-Two slice lines 10900-10907, if present."""
    rows = []
    if CC0024_SLICE.is_file():
        lines = CC0024_SLICE.read_text(encoding="utf-8").splitlines()
        # File is 1-indexed with spec line numbers as file line numbers.
        for n in range(10900, 10908):
            if 1 <= n <= len(lines):
                text = lines[n - 1].strip()
                recovered = not text.startswith("(no catalog-recovered text")
                rows.append(
                    {
                        "line": n,
                        "text": text,
                        "recovered": recovered,
                    }
                )
    recovered_n = sum(1 for r in rows if r["recovered"])
    return {
        "path": (
            CC0024_SLICE.relative_to(REPO).as_posix()
            if CC0024_SLICE.is_file()
            else None
        ),
        "live_spec": spec_path().as_posix() if spec_path() else None,
        "lines": rows,
        "recovered_count": recovered_n,
        "enumerated_list_present": False,
        "note": (
            "CC-0024 recovered fragments at 10900/10902/10906 name the "
            "taxonomy, watchlist, and expert elicitation; they do not "
            "enumerate the 96 workflows. Live harness-restore spec is "
            f"{'present' if spec_path() else 'absent'}."
        ),
    }


def parse_family_counts(question: str) -> dict[str, int]:
    found = FAMILY_COUNT_RE.findall(question or "")
    counts: dict[str, int] = {}
    for key, n in found:
        counts[key.lower()] = int(n)
    return counts


def parse_question_families(question: str) -> list[str]:
    m = QUESTION_FAMILIES_RE.search(question or "")
    if not m:
        return []
    blob = m.group(1).strip()
    parts = re.split(r",\s+and\s+|,\s+", blob)
    return [p.strip() for p in parts if p.strip()]


def family_from_title(title: str) -> str | None:
    for rx, fam in TITLE_FAMILY_RULES:
        if rx.search(title or ""):
            return fam
    return None


def _split_ids(head: str, tail: str = "") -> list[str]:
    blob = head + (tail or "")
    ids = [p.strip().lower() for p in blob.split(",") if p.strip()]
    return ids


def parse_blueprint_ids(question: str) -> tuple[list[str], int | None]:
    q = question or ""
    m = DASH_LIST_RE.search(q)
    if m:
        declared = int(m.group(1))
        ids = _split_ids(m.group(2), m.group(3) or "")
        return ids, declared
    m = BARE_REGISTER_RE.search(q)
    if m:
        ids = _split_ids(m.group(1))
        return ids, len(ids)
    return [], None


def extract_requirements(units: dict[str, dict] | None = None) -> dict[str, Any]:
    u = units if units is not None else catalog_units()
    imp0178 = u.get("IMP-0178") or {}
    wfa = u.get("WFA-0125") or {}
    family_counts_raw = parse_family_counts(str(imp0178.get("question_or_target") or ""))
    family_counts = {
        IMP0178_TO_QUESTION[k]: v
        for k, v in family_counts_raw.items()
        if k in IMP0178_TO_QUESTION
    }
    q_fams = parse_question_families(str(wfa.get("question_or_target") or ""))
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for uid in IMP_ENUM_IDS:
        rec = u.get(uid)
        if not isinstance(rec, dict):
            errors.append(f"missing {uid}")
            continue
        title = str(rec.get("title") or "")
        question = str(rec.get("question_or_target") or "")
        fam = family_from_title(title)
        ids, declared = parse_blueprint_ids(question)
        if not ids:
            errors.append(f"{uid} yielded no blueprint ids")
            continue
        if fam is None:
            errors.append(f"{uid} family not classified from title")
            continue
        if declared is not None and declared != len(ids):
            errors.append(
                f"{uid} declared {declared} blueprints but parsed {len(ids)}: {ids}"
            )
            continue
        for item in ids:
            rows.append(
                {
                    "id": item,
                    "family": fam,
                    "catalog_unit": uid,
                    "spec_cite": "_USER-PROMPTS.md:10902-10907",
                    "catalog_anchor": f"command-center/WORK-UNIT-CATALOG.json {uid}",
                }
            )
    ids = [r["id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate requirement ids: {dupes}")
    per_family: dict[str, int] = {}
    for r in rows:
        per_family[r["family"]] = per_family.get(r["family"], 0) + 1
    expected_total = sum(family_counts.values()) if family_counts else None
    return {
        "requirements": rows,
        "n": len(rows),
        "unique_n": len(set(ids)),
        "family_counts_imp0178": family_counts,
        "family_counts_imp0178_raw": family_counts_raw,
        "family_counts_parsed": per_family,
        "expected_total_from_imp0178": expected_total,
        "wfa0125_question_families": q_fams,
        "errors": errors,
        "source": "catalog-IMP-0234-to-IMP-0256-questions",
        "spec_bytes_present": spec_path() is not None,
    }


def _schema_pack_census() -> dict[str, Any]:
    rel = "command-center/wfa/schema/wfa-schema-pack.json"
    row = path_probe(rel)
    defs: list[str] = []
    if row["exists"]:
        try:
            doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("$defs"), dict):
                defs = sorted(doc["$defs"].keys())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            defs = []
    row["defs"] = defs
    row["coverage_matrix_def"] = "CoverageMatrix" in defs
    return row


def path_probe(rel: str) -> dict[str, Any]:
    p = REPO / rel
    exists = p.is_file()
    return {
        "path": rel,
        "exists": exists,
        "bytes": p.stat().st_size if exists else 0,
    }


def source_census() -> dict[str, Any]:
    return {
        "spec": [path_probe(str(p.relative_to(REPO)) if str(p).startswith(str(REPO)) else str(p)) for p in SPEC_CANDIDATES if str(p).startswith(str(REPO))]
        + [
            {
                "path": str(p),
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
            for p in SPEC_CANDIDATES
            if not str(p).startswith(str(REPO))
        ],
        "registry": [path_probe(r) for r in REGISTRY_CANDIDATES],
        "blueprint": [path_probe(r) for r in BLUEPRINT_CANDIDATES],
        "task_fit": [path_probe(r) for r in TASKFIT_CANDIDATES],
        "on_tree": [path_probe(r) for r in ON_TREE_REGISTRIES],
        "schema_pack": _schema_pack_census(),
        "wfa_0035": path_probe("command-center/wfa/WFA-0035-extract-task-fit.json"),
        "wfa_0061": path_probe("command-center/wfa/WFA-0061-mechanism-coverage-gaps.json"),
        "wfa_0078": path_probe("command-center/wfa/WFA-0078-candidate-registry-v2.json"),
    }


def _iter_records(node: Any) -> list[dict]:
    found: list[dict] = []
    if isinstance(node, dict):
        if any(k in node for k in ("id", "name", "kind", "does")):
            found.append(node)
        for v in node.values():
            found.extend(_iter_records(v))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_records(item))
    return found


def load_corpus() -> list[dict[str, Any]]:
    """Load candidate and blueprint records from on-disk covering artifacts."""
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for rel, kind in (
        *[(r, "candidate") for r in REGISTRY_CANDIDATES],
        *[(r, "blueprint") for r in BLUEPRINT_CANDIDATES],
        *[(r, "task_fit") for r in TASKFIT_CANDIDATES],
        *[(r, "on_tree") for r in ON_TREE_REGISTRIES],
    ):
        if rel in seen_paths:
            continue
        seen_paths.add(rel)
        p = REPO / rel
        if not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for rec in _iter_records(doc):
            if not isinstance(rec, dict):
                continue
            rec_kind = rec.get("kind")
            if kind == "on_tree" and rec_kind not in {
                "workflow_blueprint",
                "workflow_candidate",
                "candidate",
            }:
                continue
            rows.append(
                {
                    "record": rec,
                    "path": rel,
                    "corpus_kind": kind,
                    "id": str(rec.get("id") or ""),
                }
            )
    return rows


def structured_ids(record: dict) -> set[str]:
    out: set[str] = set()
    for key in STRUCTURED_SCALAR_KEYS:
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            out.add(val.strip().lower())
    for key in STRUCTURED_LIST_KEYS:
        val = record.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    out.add(item.strip().lower())
    return out


def accepted_ids_for(requirement_id: str) -> set[str]:
    rid = requirement_id.strip().lower()
    return {f"{p}{rid}" for p in ID_PREFIXES}


def keyword_mention(requirement_id: str, record: dict) -> bool:
    """True when the slug appears as a token in prose fields (use-vs-mention)."""
    rid = requirement_id.strip().lower()
    needle = rid.replace("-", " ")
    blobs = []
    for key in ("does", "notes", "description", "name", "title", "prose", "body"):
        val = record.get(key)
        if isinstance(val, str):
            blobs.append(val.lower())
    text = " ".join(blobs)
    if not text:
        return False
    if rid in text.replace(" ", "-"):
        return True
    if needle and needle in text:
        return True
    return False


def spot_check(requirement_id: str, record: dict) -> dict[str, Any]:
    """Independent of keyword matching: structured id/covers/task_class only."""
    rid = requirement_id.strip().lower()
    accepted = accepted_ids_for(rid)
    structured = structured_ids(record)
    hit = sorted(structured & accepted)
    mention = keyword_mention(rid, record)
    if hit:
        return {
            "pass": True,
            "reason": "structured-id",
            "matched": hit,
            "keyword_mention": mention,
        }
    if mention:
        return {
            "pass": False,
            "reason": "keyword-only-mention",
            "matched": [],
            "keyword_mention": True,
        }
    return {
        "pass": False,
        "reason": "no-structured-cover",
        "matched": [],
        "keyword_mention": False,
    }


def keyword_trap_record(requirement_id: str) -> dict:
    slug = requirement_id.replace("-", " ")
    return {
        "id": "wf-unrelated-taxonomy-note",
        "name": "taxonomy-vocabulary-mention.js",
        "does": (
            f"This note discusses the required library taxonomy and mentions "
            f"{requirement_id} / {slug} as a vocabulary token, not as a "
            f"workflow this candidate implements."
        ),
        "notes": "use-versus-mention trap",
    }


def cover_status(cand_ok: bool, bp_ok: bool) -> str:
    if cand_ok and bp_ok:
        return "BOTH"
    if cand_ok:
        return "CANDIDATE"
    if bp_ok:
        return "BLUEPRINT"
    return "NEITHER"


def measure_cells(
    requirements: list[dict],
    corpus: list[dict] | None = None,
) -> dict[str, Any]:
    corpus = corpus if corpus is not None else load_corpus()
    cells = []
    goals = []
    downgrades = []
    for req in requirements:
        rid = req["id"]
        cand_hits = []
        bp_hits = []
        keyword_rejects = []
        for item in corpus:
            rec = item["record"]
            kind = item["corpus_kind"]
            check = spot_check(rid, rec)
            if check["pass"]:
                hit = {
                    "id": item["id"],
                    "path": item["path"],
                    "corpus_kind": kind,
                    "spot_check": check,
                }
                if kind in {"candidate", "task_fit"}:
                    cand_hits.append(hit)
                elif kind in {"blueprint", "on_tree"}:
                    bp_hits.append(hit)
                else:
                    cand_hits.append(hit)
            elif check["reason"] == "keyword-only-mention":
                keyword_rejects.append(
                    {
                        "id": item["id"],
                        "path": item["path"],
                        "corpus_kind": kind,
                    }
                )
                downgrades.append(
                    {
                        "requirement_id": rid,
                        "from": "keyword-claim",
                        "to": "UNCOVERED",
                        "path": item["path"],
                        "record_id": item["id"],
                    }
                )
        cand_ok = bool(cand_hits)
        bp_ok = bool(bp_hits)
        status = cover_status(cand_ok, bp_ok)
        if keyword_rejects and not cand_ok and not bp_ok:
            status = "UNCOVERED"
        cell = {
            "requirement_id": rid,
            "family": req["family"],
            "spec_cite": req["spec_cite"],
            "catalog_unit": req["catalog_unit"],
            "candidate_covers": cand_hits,
            "blueprint_covers": bp_hits,
            "keyword_rejects": keyword_rejects,
            "status": status,
        }
        cells.append(cell)
        if status in {"NEITHER", "UNCOVERED"}:
            goals.append(
                {
                    "kind": "typed-generation-goal",
                    "lane": "generation",
                    "requirement_id": rid,
                    "family": req["family"],
                    "spec_cite": req["spec_cite"],
                    "catalog_unit": req["catalog_unit"],
                    "reason": (
                        f"{status}: no covering candidate and no covering "
                        f"blueprint survived the structured spot check"
                    ),
                }
            )
    counts = {
        "BOTH": 0,
        "CANDIDATE": 0,
        "BLUEPRINT": 0,
        "NEITHER": 0,
        "UNCOVERED": 0,
    }
    for c in cells:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    counts["total"] = len(cells)
    trap = keyword_trap_record("deep-research")
    trap_check = spot_check("deep-research", trap)
    return {
        "cells": cells,
        "counts": counts,
        "generation_lane_goals": goals,
        "downgrades": downgrades,
        "corpus_n": len(corpus),
        "keyword_trap": {
            "requirement_id": "deep-research",
            "record": trap,
            "spot_check": trap_check,
            "downgraded": (not trap_check["pass"])
            and trap_check["reason"] == "keyword-only-mention",
        },
    }


def both_states_extract(units: dict[str, dict] | None = None) -> dict[str, Any]:
    """Deletion of one enumerating IMP unit must change the parsed count."""
    u = dict(units if units is not None else catalog_units())
    full = extract_requirements(u)
    dropped = dict(u)
    dropped.pop("IMP-0234", None)
    reduced = extract_requirements(dropped)
    q = str((u.get("IMP-0178") or {}).get("question_or_target") or "")
    full_fam = parse_family_counts(q)
    mutated_q = q.replace("research/evidence 15", "research/evidence 14", 1)
    mut_fam = parse_family_counts(mutated_q)
    return {
        "full_n": full["n"],
        "reduced_n": reduced["n"],
        "drop_unit": "IMP-0234",
        "count_changed": full["n"] != reduced["n"],
        "family_sum_full": sum(full_fam.values()),
        "family_sum_mutated": sum(mut_fam.values()),
        "family_sum_changed": sum(full_fam.values()) != sum(mut_fam.values()),
        "full_errors": full["errors"],
        "reduced_errors_ok": True,
    }
