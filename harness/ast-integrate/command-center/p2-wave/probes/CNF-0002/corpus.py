#!/usr/bin/env python3
"""Live corpus + catalog census for CNF-0002.

Empty directories and a missing EVENTS.jsonl are measured as 0 of 0, never as
a pass. Planted fixtures under this probe directory are not the real corpus.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from predicate import (
    CATALOG_AUTHOR_KEYS,
    catalog_item_names_author,
    confirmer_id_of,
    evaluate_confirmation,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
POLICY_MARKERS = frozenset(
    {
        "policy_kind",
        "catalog_author_census",
        "c_rejects_a_lets_through",
        "empty_set_read_as_pass",
    }
)
CONSULTED = (
    "command-center/events/EVENTS.jsonl",
    "command-center/receipts/",
    "command-center/confirmation/",
    "command-center/WORK-UNIT-CATALOG.json",
    "git log --format=%an -- <output_path>",
)


def domain_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain measurements live under report on a schema-valid receipt."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        "catalog_author_census" in report
        or "planted" in report
        or "rule_a" in report
    ):
        return report
    return doc


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def looks_like_confirmation_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if any(k in doc for k in POLICY_MARKERS):
        return False
    claim = doc.get("claim_id") or doc.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        return False
    verdict = str(doc.get("verdict") or "").upper()
    if verdict not in VERDICTS:
        return False
    return confirmer_id_of(doc) is not None or any(
        doc.get(k) not in (None, "", [], {})
        for k in ("confirmer", "confirmer_id", "confirmed_by", "confirmer_agent")
    )


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    text = text.strip()
    if not text:
        return []
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return []
    if looks_like_confirmation_receipt(doc):
        doc = dict(doc)
        doc["_corpus_path"] = repo_rel(path)
        return [doc]
    if isinstance(doc, list):
        out = []
        for item in doc:
            if looks_like_confirmation_receipt(item):
                row = dict(item)
                row["_corpus_path"] = repo_rel(path)
                out.append(row)
        return out
    return []


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if looks_like_confirmation_receipt(doc):
            row = dict(doc)
            row["_corpus_path"] = repo_rel(path)
            out.append(row)
    return out


def iter_confirmation_receipts() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    events = REPO / "command-center" / "events" / "EVENTS.jsonl"
    if events.is_file():
        for row in _load_jsonl(events):
            key = json.dumps(row, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                found.append(row)
    for folder in (
        REPO / "command-center" / "receipts",
        REPO / "command-center" / "confirmation",
    ):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.json")):
            if path.name.startswith("CNF-0002"):
                continue
            for row in _load_json_file(path):
                key = json.dumps(row, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    found.append(row)
    return found


def git_available() -> bool:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0 and "true" in (p.stdout or "").lower()


def git_authors_for(rel: str) -> list[str]:
    if not rel:
        return []
    try:
        p = subprocess.run(
            ["git", "log", "--format=%an", "--", rel],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if p.returncode != 0:
        return []
    names = []
    for line in (p.stdout or "").splitlines():
        s = line.strip()
        if s and s not in names:
            names.append(s)
    return names


def catalog_author_census(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_catalog()
    items = [x for x in (cat.get("items") or []) if isinstance(x, dict)]
    units = [x for x in (cat.get("work_units") or []) if isinstance(x, dict)]
    items_named = sum(1 for x in items if catalog_item_names_author(x))
    units_named = sum(1 for x in units if catalog_item_names_author(x))
    assigned = sum(
        1
        for x in units
        if isinstance(x.get("assigned_model_vendor_role"), dict)
        and (
            x["assigned_model_vendor_role"].get("vendor")
            or x["assigned_model_vendor_role"].get("model")
        )
    )
    return {
        "backlog_items": len(items),
        "backlog_items_that_can_name_an_author": items_named,
        "backlog_stated": f"{items_named} of {len(items)}",
        "work_units": len(units),
        "work_units_that_can_name_an_author": units_named,
        "work_units_stated": f"{units_named} of {len(units)}",
        "work_units_with_assigned_vendor_model_role": assigned,
        "author_fields_searched": sorted(CATALOG_AUTHOR_KEYS),
        "assigned_model_vendor_role_is_not_authorship": True,
        "note": (
            "0 catalog items name an implementation author. Every work_unit "
            "carries assigned_model_vendor_role, which is a planned assignment, "
            "not authoring provenance of an artifact."
        ),
    }


def _index_units(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    for u in catalog.get("items") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out.setdefault(u["id"], u)
    return out


def _ancestors_of(uid: str, index: dict[str, dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    stack = list(index.get(uid, {}).get("dependencies") or [])
    while stack:
        dep = stack.pop()
        if not isinstance(dep, str) or dep in seen:
            continue
        seen.add(dep)
        node = index.get(dep) or {}
        for nxt in node.get("dependencies") or []:
            if isinstance(nxt, str) and nxt not in seen:
                stack.append(nxt)
    seen.discard(uid)
    return sorted(seen)


def _impl_from_unit(unit: dict[str, Any] | None, git_ok: bool) -> dict[str, Any] | None:
    if not isinstance(unit, dict):
        return None
    impl: dict[str, Any] = {
        "claim_id": unit.get("id"),
        "output_path": unit.get("output_path"),
    }
    if git_ok and isinstance(unit.get("output_path"), str):
        authors = git_authors_for(unit["output_path"])
        if authors:
            impl["git_authors"] = authors
    # Catalog assignment is not copied into authoring provenance.
    if not impl.get("git_authors") and not impl.get("author_id"):
        return impl
    return impl


def measure_real_corpus(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = catalog if catalog is not None else load_catalog()
    git_ok = git_available()
    receipts = iter_confirmation_receipts()
    index = _index_units(cat)
    a_rej = 0
    c_rej = 0
    a_lets = 0
    c_minus_a = 0
    unevaluable = 0
    for rec in receipts:
        claim = str(rec.get("claim_id") or rec.get("claim") or "")
        unit = index.get(claim)
        impl = _impl_from_unit(unit, git_ok)
        ancs = []
        if unit is not None:
            for dep in _ancestors_of(claim, index):
                node = _impl_from_unit(index.get(dep), git_ok)
                if node:
                    ancs.append(node)
        v = evaluate_confirmation(rec, impl, ancs)
        if v.unevaluable:
            unevaluable += 1
        if v.rule_a_reject:
            a_rej += 1
        if v.rule_c_reject:
            c_rej += 1
        if v.authorship_only_accept:
            a_lets += 1
        if v.c_rejects_a_lets_through:
            c_minus_a += 1
    n = len(receipts)
    empty_policy = (
        "report 0 of 0 explicitly; an empty corpus is not a pass "
        "(failure class empty-set-read-as-pass)"
    )
    return {
        "size": n,
        "empty": n == 0,
        "empty_set_policy": empty_policy,
        "paths_consulted": list(CONSULTED),
        "events_jsonl_present": (REPO / "command-center/events/EVENTS.jsonl").is_file(),
        "receipts_dir_present": (REPO / "command-center/receipts").is_dir(),
        "confirmation_dir_present": (REPO / "command-center/confirmation").is_dir(),
        "git_available": git_ok,
        "planted_fixtures_excluded": True,
        "unevaluable": unevaluable,
        "rule_a": {
            "rejected": a_rej,
            "of": n,
            "stated": f"{a_rej} of {n}",
        },
        "rule_c": {
            "rejected": c_rej,
            "of": n,
            "stated": f"{c_rej} of {n}",
        },
        "c_rejects_a_lets_through": {
            "count": c_minus_a,
            "of": n,
            "a_lets_through": a_lets,
            "fraction_of_corpus": (None if n == 0 else c_minus_a / n),
            "fraction_of_a_lets_through": (None if a_lets == 0 else c_minus_a / a_lets),
            "stated": f"{c_minus_a} of {n}",
        },
        "empty_set_read_as_pass": False,
    }
