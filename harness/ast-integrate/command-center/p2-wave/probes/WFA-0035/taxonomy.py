#!/usr/bin/env python3
"""Typed task taxonomy from the spec's workflow-library categories.

_USER-PROMPTS.md:10900-10907 is absent on this Linux worktree. The catalog
units that cite those lines carry the same family floors (IMP-0178) and the
same 96 leaf class names (IMP-0234..IMP-0256). This module recounts both
independently and requires them to agree. A hardcoded 96 is a broken detector.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

FAMILY_BY_UNIT = {
    "IMP-0234": "research-evidence",
    "IMP-0235": "research-evidence",
    "IMP-0236": "research-evidence",
    "IMP-0237": "research-evidence",
    "IMP-0238": "engineering-reliability",
    "IMP-0239": "engineering-reliability",
    "IMP-0240": "engineering-reliability",
    "IMP-0241": "engineering-reliability",
    "IMP-0242": "engineering-reliability",
    "IMP-0243": "security-governance",
    "IMP-0244": "security-governance",
    "IMP-0245": "security-governance",
    "IMP-0246": "product-design",
    "IMP-0247": "product-design",
    "IMP-0248": "product-design",
    "IMP-0249": "product-design",
    "IMP-0250": "data-science",
    "IMP-0251": "data-science",
    "IMP-0252": "data-science",
    "IMP-0253": "data-science",
    "IMP-0254": "collective-intelligence-meta",
    "IMP-0255": "collective-intelligence-meta",
    "IMP-0256": "collective-intelligence-meta",
}

# IMP-0234..IMP-0253 are the 20 blueprint-library families D1-D20.
D_FAMILY_UNITS = [f"IMP-{n:04d}" for n in range(234, 254)]

SLICE_RE = re.compile(
    r"(?:implement|register)\s+(\d+)\s+(?:library\s+)?blueprints\s+-\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
COUNCIL9_RE = re.compile(
    r"register\s+([a-z0-9-]+(?:,\s*[a-z0-9-]+){8})\s+as library entries",
    re.IGNORECASE,
)
FLOOR_RE = re.compile(
    r"research/evidence\s+(\d+),\s*engineering/reliability\s+(\d+),\s*"
    r"security/governance\s+(\d+),\s*product/design\s+(\d+),\s*"
    r"data/science\s+(\d+),\s*collective-intelligence/meta\s+(\d+)",
    re.IGNORECASE,
)
NAME_TOKEN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STOP = frozenset(
    """
    a an the and or of to for in on by with from that this those these
    is are was were be been being it its as at not no nor but if then
    than into over after before must may can should would will target
    implement register acceptance four 4 three 3 five 5 nine 9 library
    blueprints blueprint entries entry as with plus rather than never
    only when whose own so a the
    """.split()
)


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_units_by_id(doc: dict[str, Any] | None = None) -> dict[str, dict]:
    doc = doc or load_catalog()
    out: dict[str, dict] = {}
    for u in doc.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    return out


def _split_names(blob: str) -> list[str]:
    blob = blob.strip()
    blob = re.split(r"\s+-\s+as\s+", blob, maxsplit=1)[0]
    blob = re.split(r"\.\s+Acceptance", blob, maxsplit=1)[0]
    blob = blob.replace(" and ", ", ")
    names: list[str] = []
    for part in blob.split(","):
        name = part.strip().strip(".").strip()
        if NAME_TOKEN.match(name):
            names.append(name)
    return names


def parse_floor_counts(units: dict[str, dict]) -> dict[str, int]:
    q = str(units["IMP-0178"].get("question_or_target") or "")
    m = FLOOR_RE.search(q)
    if not m:
        raise RuntimeError("IMP-0178 family-floor sentence not found")
    keys = [
        "research-evidence",
        "engineering-reliability",
        "security-governance",
        "product-design",
        "data-science",
        "collective-intelligence-meta",
    ]
    return {k: int(v) for k, v in zip(keys, m.groups())}


def parse_slices(units: dict[str, dict]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for uid in sorted(FAMILY_BY_UNIT):
        rec = units[uid]
        q = str(rec.get("question_or_target") or "")
        title = str(rec.get("title") or "")
        names: list[str] = []
        declared: int | None = None
        m = SLICE_RE.search(q)
        if m:
            declared = int(m.group(1))
            names = _split_names(m.group(2))
        if uid == "IMP-0256":
            m9 = COUNCIL9_RE.search(q)
            if not m9:
                raise RuntimeError("IMP-0256 nine council names not found")
            names = _split_names(m9.group(1))
            declared = 9
        if not names:
            raise RuntimeError(f"{uid}: no class names parsed")
        if declared is not None and declared != len(names):
            raise RuntimeError(
                f"{uid}: declared n={declared} parsed n={len(names)} {names}"
            )
        d_family = None
        if uid in D_FAMILY_UNITS:
            d_family = f"D{D_FAMILY_UNITS.index(uid) + 1:02d}"
        slices.append(
            {
                "unit_id": uid,
                "title": title,
                "question": q,
                "family": FAMILY_BY_UNIT[uid],
                "d_family": d_family,
                "class_ids": names,
            }
        )
    return slices


def _clauses_for_class(class_id: str, question: str) -> str:
    """Use Acceptance prose that actually discusses this class, not the name list."""
    acc = question
    if "Acceptance:" in question:
        acc = question.split("Acceptance:", 1)[1]
    variants = {
        class_id,
        class_id.replace("-", " "),
        class_id.replace("-", "/"),
    }
    # Drop one-token prefixes; they collide across classes (e.g. "workflow").
    parts = re.split(r"(?<=[.;:])\s+", acc)
    hits = []
    for part in parts:
        low = part.lower()
        if any(v.lower() in low for v in variants if len(v) >= 8):
            hits.append(part.strip())
    return " ".join(hits) if hits else ""


def class_definition(class_id: str, slice_row: dict[str, Any]) -> str:
    unique = _clauses_for_class(class_id, slice_row["question"])
    expanded = class_id.replace("-", " ")
    family = slice_row["family"]
    d_fam = slice_row["d_family"] or "not-in-D1-D20"
    # Do not name sibling classes here. A definition that lists siblings
    # makes those siblings' candidates look in-class under Jaccard.
    if unique:
        body = unique
    else:
        body = (
            f"Typed workflow-library task class '{expanded}' "
            f"in family {family}."
        )
    return (
        f"Task class {class_id} ({expanded}) in family {family} "
        f"blueprint-library-family {d_fam}. {body}"
    )


def cue_tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in toks if t not in STOP and len(t) >= 4}


def build_taxonomy(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    units = catalog_units_by_id(doc)
    floors = parse_floor_counts(units)
    slices = parse_slices(units)
    classes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sl in slices:
        for cid in sl["class_ids"]:
            if cid in seen:
                raise RuntimeError(f"duplicate class id {cid}")
            seen.add(cid)
            definition = class_definition(cid, sl)
            classes.append(
                {
                    "id": cid,
                    "family": sl["family"],
                    "d_family": sl["d_family"],
                    "source_unit": sl["unit_id"],
                    "definition": definition,
                    "cues": sorted(cue_tokens(definition) | set(cid.split("-"))),
                    "spec_cite": f"command-center/WORK-UNIT-CATALOG.json {sl['unit_id']}",
                }
            )
    family_counts: dict[str, int] = {}
    for c in classes:
        family_counts[c["family"]] = family_counts.get(c["family"], 0) + 1
    disagreements = {
        fam: {"floor": floors[fam], "parsed": family_counts.get(fam, 0)}
        for fam in floors
        if floors[fam] != family_counts.get(fam, 0)
    }
    n = len(classes)
    floor_sum = sum(floors.values())
    return {
        "taxonomy_id": "wfa-0035-library-task-taxonomy-v1",
        "taxonomy_version": 1,
        "source": "catalog-IMP-0178-floors + catalog-IMP-0234-0256-class-names",
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
        "blueprint_library_present": False,
        "n_classes": n,
        "floor_sum": floor_sum,
        "floors": floors,
        "family_counts": family_counts,
        "floor_agreement": not disagreements and n == floor_sum,
        "disagreements": disagreements,
        "n_d_families": sum(1 for sl in slices if sl["d_family"]),
        "classes": classes,
        "slices": [
            {
                "unit_id": sl["unit_id"],
                "family": sl["family"],
                "d_family": sl["d_family"],
                "class_ids": sl["class_ids"],
            }
            for sl in slices
        ],
    }


def classes_by_id(tax: dict[str, Any] | None = None) -> dict[str, dict]:
    tax = tax if tax is not None else build_taxonomy()
    return {c["id"]: c for c in tax["classes"]}


if __name__ == "__main__":
    tax = build_taxonomy()
    print(
        json.dumps(
            {
                "n_classes": tax["n_classes"],
                "floor_sum": tax["floor_sum"],
                "floor_agreement": tax["floor_agreement"],
                "family_counts": tax["family_counts"],
                "n_d_families": tax["n_d_families"],
            },
            indent=2,
        )
    )
