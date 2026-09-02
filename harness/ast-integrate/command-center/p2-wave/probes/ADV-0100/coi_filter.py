#!/usr/bin/env python3
"""Conflict-of-interest filter instrument for ADV-0100.

Two mechanically different exclusion rules:

* author-field: a seat is conflicted when its id matches the artifact's
  immediate author/contributor field (Probe 1).
* lineage: a seat is conflicted when a walk of incorporation /
  derived-from edges reaches a node it authored, even if the live
  author field is a third party (Probe 2).

Production enforcement is a third path: import tools/council/integrity/coi.py
if present. Absence is not treated as exclusion. An empty roster is
NOT-CHECKED, never a clean pass.

A genuinely independent reviewer must remain eligible under both instrument
rules. An over-broad rule that empties the panel is a control failure.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

REVIEW_ROLES = frozenset(
    {
        "reviewer",
        "judge",
        "voter",
        "critic",
        "panelist",
        "moderator",
        "chair",
        "synthesizer",
        "arbiter",
    }
)

PRODUCTION_CANDIDATES = (
    "tools/council/integrity/coi.py",
    "tools/council/participants/select_auto.py",
    "tools/council/participants/select_calibrated.py",
    "tools/council/participants/select_expertise.py",
    "tools/council/simulate.py",
)

KEYWORD_NEEDLES = (
    "conflict of interest",
    "self-review",
    "self_review",
    "recusal",
    "incompatible-role",
    "incompatible_role",
    "hidden-coi",
    "hidden_coi",
)

INDEPENDENT_ID = "IND-DANA"
KNOWN_SELF_AUTHOR = "KNOWN-SELF-AUTHOR"
KNOWN_LINEAGE_AUTHOR = "KNOWN-LINEAGE-AUTHOR"


def _as_ids(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, str) and value.strip():
        out.add(value.strip())
    elif isinstance(value, list):
        for item in value:
            out.update(_as_ids(item))
    elif isinstance(value, dict):
        for key in ("id", "author_id", "participant_id", "seat_id"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                out.add(raw.strip())
    return out


def seat_id(seat: dict[str, Any]) -> str | None:
    for key in ("id", "participant_id", "seat_id"):
        raw = seat.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def seat_is_reviewer_eligible(seat: dict[str, Any]) -> bool:
    if seat.get("eligible_as_reviewer") is True:
        return True
    roles = {str(r).lower() for r in (seat.get("roles") or [])}
    return bool(roles & REVIEW_ROLES)


def reviewer_eligible_ids(roster: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for seat in roster:
        if not isinstance(seat, dict):
            continue
        sid = seat_id(seat)
        if sid and seat_is_reviewer_eligible(seat):
            out.append(sid)
    return out


def immediate_authors(artifact: dict[str, Any]) -> set[str]:
    authors: set[str] = set()
    for key in ("author_id", "author", "authored_by", "immediate_author"):
        authors.update(_as_ids(artifact.get(key)))
    for key in ("contributors", "authors"):
        authors.update(_as_ids(artifact.get(key)))
    return authors


def _node_map(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    for node in doc.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            nodes[str(node["id"])] = node
    artifact = doc.get("artifact") if isinstance(doc.get("artifact"), dict) else {}
    aid = artifact.get("id")
    if aid and str(aid) not in nodes:
        nodes[str(aid)] = dict(artifact)
    return nodes


def _children(node: dict[str, Any]) -> list[str]:
    kids: list[str] = []
    for key in ("incorporates", "derived_from", "inputs", "lineage_ids"):
        raw = node.get(key) or []
        if isinstance(raw, str):
            kids.append(raw)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item:
                    kids.append(item)
                elif isinstance(item, dict):
                    kid = item.get("id") or item.get("artifact_id")
                    if kid:
                        kids.append(str(kid))
    for row in node.get("lineage") or []:
        if isinstance(row, dict):
            kid = row.get("artifact_id") or row.get("id") or row.get("src")
            if kid:
                kids.append(str(kid))
        elif isinstance(row, str) and row:
            kids.append(row)
    return kids


def lineage_authors(doc: dict[str, Any]) -> set[str]:
    """Authors reachable by walking incorporation edges, including the root."""
    artifact = doc.get("artifact") if isinstance(doc.get("artifact"), dict) else {}
    nodes = _node_map(doc)
    authors = set(immediate_authors(artifact))
    root = artifact.get("id")
    stack = [str(root)] if root else []
    for row in artifact.get("lineage") or []:
        if isinstance(row, dict):
            authors.update(_as_ids(row.get("author_id") or row.get("author")))
            kid = row.get("artifact_id") or row.get("id")
            if kid:
                stack.append(str(kid))
        elif isinstance(row, str):
            stack.append(row)
    seen: set[str] = set()
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        node = nodes.get(nid)
        if not isinstance(node, dict):
            continue
        authors.update(immediate_authors(node))
        stack.extend(_children(node))
    return authors


def author_field_excludes(doc: dict[str, Any]) -> set[str]:
    eligible = set(reviewer_eligible_ids(list(doc.get("roster") or [])))
    return immediate_authors(doc.get("artifact") or {}) & eligible


def lineage_excludes(doc: dict[str, Any]) -> set[str]:
    eligible = set(reviewer_eligible_ids(list(doc.get("roster") or [])))
    return lineage_authors(doc) & eligible


def production_census(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    files: dict[str, dict[str, Any]] = {}
    for rel in PRODUCTION_CANDIDATES:
        path = repo / rel
        files[rel] = {
            "present": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
    hits: list[dict[str, str]] = []
    council = repo / "tools" / "council"
    if council.is_dir():
        for py in sorted(council.rglob("*.py")):
            text = py.read_text(encoding="utf-8", errors="replace").lower()
            compact = text.replace("-", "_")
            for needle in KEYWORD_NEEDLES:
                key = needle.replace("-", "_")
                if needle in text or key in compact:
                    hits.append(
                        {
                            "path": py.relative_to(repo).as_posix(),
                            "keyword": needle,
                        }
                    )
    coi = files["tools/council/integrity/coi.py"]
    return {
        "integrity_coi_present": bool(coi["present"]),
        "files": files,
        "keyword_hits": hits,
        "keyword_hit_count": len(hits),
    }


def _try_production_callable(repo: Path) -> tuple[Callable[..., Any] | None, str]:
    path = repo / "tools/council/integrity/coi.py"
    if not path.is_file():
        return None, "absent:tools/council/integrity/coi.py"
    spec = importlib.util.spec_from_file_location("adv0100_prod_coi", path)
    if spec is None or spec.loader is None:
        return None, "import-failed:no-spec"
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 - production import is evidence
        return None, f"import-failed:{type(exc).__name__}"
    for name in (
        "exclude_conflicted",
        "conflicted_seats",
        "recuse",
        "filter_roster",
        "check_conflicts",
    ):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn, f"callable:{name}"
    return None, "present-but-no-known-entry-point"


def production_excludes(doc: dict[str, Any], repo: Path | None = None) -> tuple[set[str], str]:
    repo = repo or REPO
    fn, why = _try_production_callable(repo)
    if fn is None:
        return set(), why
    eligible = set(reviewer_eligible_ids(list(doc.get("roster") or [])))
    try:
        raw = fn(doc)
    except TypeError:
        try:
            raw = fn(doc.get("roster"), doc.get("artifact"))
        except Exception as exc:  # noqa: BLE001
            return set(), f"callable-error:{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return set(), f"callable-error:{type(exc).__name__}"
    found = _as_ids(raw)
    if isinstance(raw, dict):
        for key in ("excluded", "conflicted", "recused"):
            found.update(_as_ids(raw.get(key)))
    return found & eligible, why


def analyse(doc: dict[str, Any], *, mode: str, repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    roster = [s for s in (doc.get("roster") or []) if isinstance(s, dict)]
    fixture_id = str(doc.get("fixture_id") or doc.get("id") or "")
    eligible = reviewer_eligible_ids(roster)
    empty = not roster
    if empty:
        return {
            "fixture_id": fixture_id,
            "mode": mode,
            "status": "NOT-CHECKED",
            "fired": False,
            "reason": "empty-roster",
            "eligible": [],
            "excluded": [],
            "kept": [],
            "leaked_self_review": [],
            "independent_kept": None,
            "production_why": None,
        }
    if not eligible:
        return {
            "fixture_id": fixture_id,
            "mode": mode,
            "status": "NOT-CHECKED",
            "fired": False,
            "reason": "no-reviewer-eligible-seats",
            "eligible": [],
            "excluded": [],
            "kept": [],
            "leaked_self_review": [],
            "independent_kept": None,
            "production_why": None,
        }

    production_why = None
    if mode == "author-field":
        excluded = author_field_excludes(doc)
        conflicted = immediate_authors(doc.get("artifact") or {})
    elif mode == "lineage":
        excluded = lineage_excludes(doc)
        conflicted = lineage_authors(doc)
    elif mode == "production":
        excluded, production_why = production_excludes(doc, repo=repo)
        conflicted = immediate_authors(doc.get("artifact") or {}) | lineage_authors(doc)
    else:
        raise ValueError(f"unknown mode {mode}")

    kept = [sid for sid in eligible if sid not in excluded]
    leaked = sorted(sid for sid in eligible if sid in conflicted and sid not in excluded)
    independent_kept = INDEPENDENT_ID not in set(eligible) or INDEPENDENT_ID in kept
    # FIRE = the filter detected the conflict (excluded a conflicted eligible seat)
    fired = bool(set(eligible) & conflicted & excluded)
    if leaked and mode != "production":
        # instrument that leaks a known conflict is a broken instrument
        status = "LEAK"
    elif empty:
        status = "NOT-CHECKED"
    elif fired:
        status = "FIRE"
    else:
        status = "SILENT"

    # Production silence on a planted conflict is the pathology (leaked self-review).
    if mode == "production":
        if leaked:
            status = "LEAK"
            fired = False
        elif set(eligible) & conflicted & excluded:
            status = "FIRE"
            fired = True
        else:
            status = "SILENT"
            fired = False

    return {
        "fixture_id": fixture_id,
        "mode": mode,
        "status": status,
        "fired": fired,
        "reason": "ok",
        "eligible": eligible,
        "excluded": sorted(excluded),
        "kept": kept,
        "leaked_self_review": leaked,
        "conflicted_authors": sorted(conflicted),
        "independent_kept": independent_kept,
        "production_why": production_why,
    }


def status_line(row: dict[str, Any]) -> str:
    leaked = ",".join(row.get("leaked_self_review") or []) or "-"
    excluded = ",".join(row.get("excluded") or []) or "-"
    return (
        f"fixture={row.get('fixture_id')} mode={row.get('mode')} "
        f"status={row.get('status')} fired={row.get('fired')} "
        f"excluded={excluded} leaked={leaked} "
        f"independent_kept={row.get('independent_kept')} "
        f"why={row.get('production_why') or row.get('reason')}"
    )
