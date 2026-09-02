#!/usr/bin/env python3
"""Extract discrete mechanism statements from the nine tournament architectures.

Live DESIGN.json is the primary source. Missing dossiers are not rebuilt.
Catalog question_or_target (and a few live sibling artifacts) fill those
slots and are labeled catalog-brief / sibling-artifact so the comparison
never pretends a label is a design.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PIN_DIR = HERE / "fixtures"

ARCH_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("A1", "ARC-0003", "command-center/phase3/A1/DESIGN.json"),
    ("A2", "ARC-0010", "command-center/phase3/A2/DESIGN.json"),
    ("A3", "ARC-0017", "command-center/phase3/A3/DESIGN.json"),
    ("A4", "ARC-0024", "command-center/phase3/A4/DESIGN.json"),
    ("A5", "ARC-0031", "command-center/phase3/A5/DESIGN.json"),
    ("A6", "ARC-0038", "command-center/phase3/A6/DESIGN.json"),
    ("A7", "ARC-0045", "command-center/phase3/A7/DESIGN.json"),
    ("A8", "ARC-0052", "command-center/phase3/A8/DESIGN.json"),
    ("A9", "ARC-0059", "command-center/phase3/A9/DESIGN.json"),
)

SIBLING: dict[str, tuple[str, ...]] = {
    "A3": ("command-center/phase3/A3/COST.json",),
    "A8": ("command-center/phase3/A8/FAILURE-MODES.json",),
    "A9": ("command-center/phase3/A9/MIGRATION.json",),
}

OPTION_UNIVERSE_CANDIDATES: tuple[str, ...] = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.json",
    "command-center/07-OPTION-UNIVERSE.json",
    "command-center/sources/07-OPTION-UNIVERSE.json",
)

IDENTITY_TOKEN = re.compile(
    r"^(?:a[1-9]|q9|arc[-_]?\d{3,4}|arc9999)$", re.IGNORECASE
)
PATHISH = re.compile(r"[/\\]|command-center|control-plane|phase3")
SPLITTER = re.compile(r"(?<=[.;:])\s+|\n+")


def pick(doc: dict, *keys: str) -> Any:
    for key in keys:
        if key in doc and doc[key] not in (None, ""):
            return doc[key]
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pin_path(arch_id: str) -> Path:
    return PIN_DIR / f"{arch_id}.DESIGN.json"


def pin_live_designs(ids: tuple[str, ...] = ("A1", "A2")) -> dict[str, dict]:
    """Snapshot live DESIGN.json bytes so planted-mutant is not racing other units."""
    import time

    PIN_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for arch_id, _uid, rel in ARCH_SLOTS:
        if arch_id not in ids:
            continue
        live = REPO / rel
        if not live.is_file():
            continue
        prev = None
        raw = b""
        for _ in range(8):
            raw = live.read_bytes()
            if prev is not None and raw == prev and raw:
                break
            prev = raw
            time.sleep(0.03)
        dest = pin_path(arch_id)
        if len(raw) < 2048 and dest.is_file() and dest.stat().st_size >= 2048:
            out[arch_id] = {
                "live": rel,
                "pin": dest.relative_to(REPO).as_posix(),
                "bytes": dest.stat().st_size,
                "kept_previous_pin": True,
            }
            continue
        dest.write_bytes(raw)
        out[arch_id] = {
            "live": rel,
            "pin": dest.relative_to(REPO).as_posix(),
            "bytes": len(raw),
        }
    return out


def load_catalog_units() -> dict[str, dict]:
    data = load_json(REPO / "command-center/WORK-UNIT-CATALOG.json")
    rows = data.get("work_units") if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                out[row["id"]] = row
    return out


def option_universe_status() -> dict[str, Any]:
    found = []
    for rel in OPTION_UNIVERSE_CANDIDATES:
        p = Path(rel)
        if not p.is_absolute():
            p = REPO / rel
        found.append({"path": rel, "present": p.is_file()})
    return {
        "catalog_input": OPTION_UNIVERSE_CANDIDATES[0],
        "present_on_this_host": any(x["present"] for x in found),
        "candidates": found,
        "used_as_mechanism_source": False,
        "note": (
            "07-OPTION-UNIVERSE.json is a catalog input, not a ninth "
            "architecture. It is absent on this host; no Windows restore "
            "tree was read."
        ),
    }


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _add(bucket: list[dict], statement: str, source: str, kind: str) -> None:
    text = " ".join(statement.split())
    if len(text) < 16:
        return
    key = text.lower()
    if any(x["text"].lower() == key for x in bucket):
        return
    bucket.append({"text": text, "source": source, "kind": kind})


def split_clauses(text: str, source: str, kind: str) -> list[dict]:
    bucket: list[dict] = []
    for part in SPLITTER.split(text.strip()):
        _add(bucket, part, source, kind)
    if not bucket and text.strip():
        _add(bucket, text, source, kind)
    return bucket


def statements_from_design(doc: dict, rel: str) -> list[dict]:
    bucket: list[dict] = []
    klass = _text(pick(doc, "architecture_class", "architecture_class"))
    if klass:
        _add(bucket, f"architecture class is {klass}", rel, "class")
    for key in ("answer", "answer", "question", "title"):
        raw = _text(doc.get(key))
        if raw:
            for row in split_clauses(raw, f"{rel}#{key}", key):
                bucket.append(row)

    prec = doc.get("precedence")
    if isinstance(prec, dict):
        for k, v in prec.items():
            t = _text(v)
            if t:
                _add(
                    bucket,
                    f"precedence.{k}: {t}",
                    f"{rel}#precedence.{k}",
                    "precedence",
                )

    exp = pick(doc, "expressibility", "expressibility") or {}
    if isinstance(exp, dict):
        fields = {
            "structural_rule": (
                "structural_rule",
                "structural_rule",
            ),
            "first_non_expressible_construct": (
                "first_non_expressible_construct",
                "first_non_expressible_construct",
            ),
            "catalogue_claim": ("catalogue_claim", "catalogue_claim"),
            "stop_reason": ("stop_reason", "stop_reason"),
        }
        for canon, keys in fields.items():
            t = _text(pick(exp, *keys))
            if t:
                _add(
                    bucket,
                    f"expressibility.{canon}: {t}",
                    f"{rel}#expressibility.{canon}",
                    "expressibility",
                )

    hand = pick(doc, "hand_edit_rule", "hand_edit_rule") or {}
    if isinstance(hand, dict):
        for k, v in hand.items():
            t = _text(v)
            if t and k != "executable":
                _add(
                    bucket,
                    f"hand_edit.{k}: {t}",
                    f"{rel}#hand_edit_rule.{k}",
                    "hand-edit",
                )

    det = pick(doc, "determinism_contract", "determinism_contract") or {}
    if isinstance(det, dict):
        for k in ("statement", "generator_id", "generator_version"):
            t = _text(det.get(k))
            if t:
                _add(
                    bucket,
                    f"determinism.{k}: {t}",
                    f"{rel}#determinism_contract.{k}",
                    "determinism",
                )
        rules = det.get("rules")
        if isinstance(rules, list):
            for i, rule in enumerate(rules):
                t = _text(rule)
                if t:
                    _add(
                        bucket,
                        f"determinism.rule: {t}",
                        f"{rel}#determinism_contract.rules[{i}]",
                        "determinism",
                    )

    files = pick(doc, "file_set", "file_set") or []
    if isinstance(files, list):
        for i, row in enumerate(files):
            if not isinstance(row, dict):
                continue
            role = _text(row.get("role"))
            notes = _text(row.get("notes") or row.get("notes"))
            if role and notes:
                _add(
                    bucket,
                    f"file role {role}: {notes}",
                    f"{rel}#file_set[{i}]",
                    "file-role",
                )
            elif notes:
                _add(bucket, notes, f"{rel}#file_set[{i}]", "file-role")
    return bucket


def statements_from_sibling(arch_id: str, doc: dict, rel: str) -> list[dict]:
    bucket: list[dict] = []
    klass = _text(pick(doc, "architecture_class", "architecture_class"))
    if klass:
        _add(bucket, f"architecture class is {klass}", rel, "sibling-class")
    if arch_id == "A9":
        first = pick(doc, "first_subsystem", "first_subsystem") or {}
        if isinstance(first, dict):
            for k in ("id", "borrowed_from", "why_first", "why_first", "mechanism"):
                t = _text(first.get(k))
                if t:
                    _add(
                        bucket,
                        f"A9 first subsystem {k}: {t}",
                        f"{rel}#first_subsystem.{k}",
                        "sibling-hybrid",
                    )
        rationale = _text(
            pick(
                doc,
                "adoption_rationale",
                "adoption_rationale",
                "binding_constraint",
            )
        )
        if rationale:
            for row in split_clauses(rationale, f"{rel}#adoption", "sibling-hybrid"):
                bucket.append(row)
        for i, stage in enumerate(doc.get("stages") or []):
            if not isinstance(stage, dict):
                continue
            t = _text(stage.get("mechanism"))
            if t:
                _add(
                    bucket,
                    t,
                    f"{rel}#stages[{i}].mechanism",
                    "sibling-hybrid",
                )
        prov = doc.get("provenance_of_mechanisms") or doc.get("provenance_of_mechanisms") or []
        for i, row in enumerate(prov):
            if not isinstance(row, dict):
                continue
            t = _text(row.get("mechanism"))
            src = _text(row.get("borrowed_from"))
            if t:
                _add(
                    bucket,
                    f"A9 borrows from {src}: {t}" if src else t,
                    f"{rel}#provenance_of_mechanisms[{i}]",
                    "sibling-hybrid",
                )
    if arch_id == "A8":
        modes = (
            doc.get("author_failure_modes")
            or doc.get("author_failure_modes")
            or []
        )
        for i, fm in enumerate(modes):
            if not isinstance(fm, dict):
                continue
            title = _text(fm.get("title"))
            if title:
                _add(
                    bucket,
                    f"A8 product mechanism named by failure mode: {title}",
                    f"{rel}#author_failure_modes[{i}]",
                    "sibling-ux",
                )
    return bucket


def statements_from_catalog(unit: dict, unit_id: str) -> list[dict]:
    bucket: list[dict] = []
    title = _text(unit.get("title"))
    if title:
        _add(
            bucket,
            title,
            f"WORK-UNIT-CATALOG.json#{unit_id}.title",
            "catalog-title",
        )
    q = _text(unit.get("question_or_target") or unit.get("question_or_target") or "")
    if q:
        for row in split_clauses(
            q,
            f"WORK-UNIT-CATALOG.json#{unit_id}.question_or_target",
            "catalog-brief",
        ):
            bucket.append(row)
    ev = _text(unit.get("evidence_requirement") or unit.get("evidence_requirement") or "")
    if ev:
        for row in split_clauses(
            ev,
            f"WORK-UNIT-CATALOG.json#{unit_id}.evidence_requirement",
            "catalog-evidence",
        ):
            bucket.append(row)
    return bucket


def source_rank(kinds: list[str]) -> str:
    design_kinds = {
        "class",
        "answer",
        "answer",
        "question",
        "precedence",
        "expressibility",
        "hand-edit",
        "determinism",
        "file-role",
    }
    if any(k in design_kinds for k in kinds):
        return "design-dossier"
    if any(k.startswith("sibling") for k in kinds):
        return "sibling-artifact"
    return "catalog-brief"


def extract_architecture(
    arch_id: str, design_unit_id: str, design_rel: str, catalog: dict[str, dict]
) -> dict:
    live_path = REPO / design_rel
    live_present = live_path.is_file()
    pin = pin_path(arch_id)
    pin_present = pin.is_file()
    design_doc = None
    design_source = "absent"
    if pin_present:
        loaded = load_json(pin)
        if isinstance(loaded, dict):
            design_doc = loaded
            design_source = "unit-pin"
    elif live_present:
        loaded = load_json(live_path)
        if isinstance(loaded, dict):
            design_doc = loaded
            design_source = "live"
    design_present = isinstance(design_doc, dict)
    statements: list[dict] = []
    if design_present:
        statements.extend(statements_from_design(design_doc, design_rel))
    sibling_used: list[dict] = []
    if not design_present:
        for rel in SIBLING.get(arch_id, ()):
            p = REPO / rel
            row = {"path": rel, "present": p.is_file()}
            sibling_used.append(row)
            if p.is_file():
                doc = load_json(p)
                if isinstance(doc, dict):
                    statements.extend(statements_from_sibling(arch_id, doc, rel))
        unit = catalog.get(design_unit_id) or {}
        statements.extend(statements_from_catalog(unit, design_unit_id))
    kinds = [s["kind"] for s in statements]
    klass = ""
    if isinstance(design_doc, dict):
        klass = _text(pick(design_doc, "architecture_class", "architecture_class"))
    if not klass:
        unit = catalog.get(design_unit_id) or {}
        title = _text(unit.get("title"))
        m = re.search(r"\(([^)]+)\)", title)
        klass = m.group(1).strip() if m else ""
    return {
        "architecture_id": arch_id,
        "design_unit_id": design_unit_id,
        "design_path": design_rel,
        "design_present": design_present,
        "design_source": design_source,
        "live_present": live_present,
        "architecture_class": klass,
        "source_rank": source_rank(kinds),
        "statement_count": len(statements),
        "statements": statements,
        "siblings": sibling_used,
        "raw_design": design_doc,
    }


def extract_from_design_doc(doc: dict, arch_id: str, rel: str) -> dict:
    statements = statements_from_design(doc, rel)
    klass = _text(pick(doc, "architecture_class", "architecture_class"))
    return {
        "architecture_id": arch_id,
        "design_unit_id": _text(doc.get("unit_id")) or "PLANTED",
        "design_path": rel,
        "design_present": True,
        "architecture_class": klass,
        "source_rank": "design-dossier",
        "statement_count": len(statements),
        "statements": statements,
        "siblings": [],
        "planted": True,
    }


def extract_all() -> dict[str, dict]:
    catalog = load_catalog_units()
    out: dict[str, dict] = {}
    for arch_id, unit_id, rel in ARCH_SLOTS:
        out[arch_id] = extract_architecture(arch_id, unit_id, rel, catalog)
    return out


def concatenated_text(arch: dict) -> str:
    return "\n".join(s["text"] for s in arch.get("statements") or [])


def is_identity_token(tok: str) -> bool:
    if IDENTITY_TOKEN.match(tok):
        return True
    if PATHISH.search(tok) and "/" in tok:
        return True
    return False
