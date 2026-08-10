"""Ingest + normalize candidate workflows (Foundry pipeline step 1, spec :10845).

Two very different input populations feed the foundry and BOTH are real:

1. ``platform/registry/workflow-candidates-{1..5}.json`` - 163 catalogued candidates written by
   five independent archaeology units. They do NOT share a schema. Two files are bare JSON
   arrays, one wraps its rows in ``{"candidates": [...]}`` and carries a header, and the field
   names for the same concept differ per file (``provenance.anchor`` vs
   ``provenance.primary_anchor`` vs a top-level ``primary_anchor``; ``license`` is a string in
   three files and an object in two; ``mechanisms`` / ``reusable_mechanisms`` /
   ``prior_pass_fields.mechanisms``). Normalizing this is the whole job of step 1, and it is
   done by an exact algorithm - never by judgement.

2. ``platform/workflows/*.json`` - the executable DSL blueprints. These are the only candidates
   whose capabilities can be measured STRUCTURALLY rather than read off prose, so scout tags
   every capability finding with how it was derived and never launders one into the other.

Provenance verification (spec :10835 "record provenance ... verify provenance and license") is
a real filesystem probe, not a field copy. The probe is control-tested in
``test_foundry.py::test_provenance_probe_both_states``: it must resolve a known-present path and
refuse a known-absent one, or its "resolved" verdicts mean nothing.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from foundry.model import Candidate, REGISTRY_DIR, WORKFLOWS_DIR, classify_license

#: an anchor may carry a ``:LINE`` suffix (``.../SKILL.md:2``) or be a git rev
#: (``07f465f3:skills/x/SKILL.md``). Only the first form is a filesystem path.
_LINE_SUFFIX = re.compile(r":(\d+)$")
_GIT_REV_PREFIX = re.compile(r"^[0-9a-f]{7,40}:")
_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def _as_str_list(value: Any) -> list[str]:
    """Flatten whatever shape a list-ish field arrived in into ``list[str]``, order-stable."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in value.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out.append(f"{k}: {v}" if v not in (None, "") else str(k))
            else:
                out.append(str(k))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("name", "id", "title", "role", "stage", "token"):
                    if isinstance(item.get(key), str):
                        out.append(item[key])
                        break
                else:
                    out.append(json.dumps(item, sort_keys=True)[:200])
            else:
                out.append(str(item))
        return out
    return [str(value)]


def _first_str(row: dict[str, Any], *paths: str) -> str:
    """First non-empty string at any of the given ``a.b.c`` dotted paths."""
    for path in paths:
        cur: Any = row
        for part in path.split("."):
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(part)
        if isinstance(cur, str) and cur.strip():
            return cur
        if isinstance(cur, (int, float)) and cur is not None:
            return str(cur)
    return ""


def classify_anchor(anchor: str) -> str:
    """``abs-path`` | ``git-rev`` | ``repo-relative`` | ``token`` | ``absent``."""
    if not anchor:
        return "absent"
    a = anchor.strip()
    if _GIT_REV_PREFIX.match(a):
        return "git-rev"
    body = _LINE_SUFFIX.sub("", a)
    if _WINDOWS_ABS.match(body) or body.startswith("/"):
        return "abs-path"
    if "/" in body or "\\" in body:
        return "repo-relative"
    return "token"


def probe_anchor(anchor: str, repo_root: Path | None = None) -> tuple[bool | None, str]:
    """Resolve an anchor on disk.

    Returns ``(resolved, probe_description)``. ``resolved`` is ``None`` for anchor kinds this
    probe cannot decide (a git rev, a bare token) - NOT ``False``. Reporting "unresolvable by
    this probe" as "does not exist" is exactly the detector failure this program keeps paying
    for, so the tri-state is deliberate.
    """
    kind = classify_anchor(anchor)
    if kind in ("absent", "token"):
        return None, f"NOT-CHECKED: anchor kind {kind!r} is not a filesystem path"
    if kind == "git-rev":
        return (
            None,
            "NOT-CHECKED: git-rev anchor; needs `git cat-file -e`, not os.path.exists",
        )
    body = _LINE_SUFFIX.sub("", anchor.strip()).replace("\\", "/")
    if kind == "repo-relative":
        root = repo_root or Path(__file__).resolve().parents[3]
        target = root / body
    else:
        target = Path(body)
    exists = os.path.exists(target)
    return exists, f"os.path.exists({target.as_posix()!r}) -> {exists}"


def _license_text(row: dict[str, Any]) -> str:
    lic = row.get("license")
    parts: list[str] = []
    if isinstance(lic, str):
        parts.append(lic)
    elif isinstance(lic, dict):
        for key in ("spdx", "declared", "effective", "note", "source_anchor"):
            v = lic.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v)
    src = row.get("license_source")
    if isinstance(src, str):
        parts.append(src)
    for key in ("third_party_license_anchors", "vendoring_origin"):
        v = row.get(key)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, dict)):
            parts.append(json.dumps(v, sort_keys=True)[:400])
    return " | ".join(parts)


def _mechanisms(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("mechanisms", "reusable_mechanisms"):
        out.extend(_as_str_list(row.get(key)))
    prior = row.get("prior_pass_fields")
    if isinstance(prior, dict):
        out.extend(_as_str_list(prior.get("mechanisms")))
    scan = row.get("mechanism_scan_measured")
    if isinstance(scan, dict):
        out.extend(f"{k}={v}" for k, v in sorted(scan.items()))
    seen: set[str] = set()
    uniq: list[str] = []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def normalize_row(
    row: dict[str, Any], source_file: str, repo_root: Path | None = None
) -> Candidate:
    """One heterogeneous registry row -> one :class:`Candidate`. Pure, order-stable."""
    anchor = _first_str(
        row,
        "provenance.anchor",
        "provenance.primary_anchor",
        "primary_anchor",
        "provenance.path",
        "provenance.pinned_repo_ref",
    )
    resolved, probe = probe_anchor(anchor, repo_root)
    lic_text = _license_text(row)
    stages = _as_str_list(row.get("stages")) or _as_str_list(
        row.get("phase_names_measured")
    )
    return Candidate(
        id=str(row.get("id") or row.get("wfc_id") or row.get("prior_id") or "<no-id>"),
        name=str(row.get("name") or row.get("id") or "<unnamed>"),
        source_file=source_file,
        family=str(row.get("family") or row.get("kind") or ""),
        classification=str(
            row.get("classification") or row.get("prior_classification") or ""
        ),
        what_it_does=_first_str(
            row, "what_it_does", "prior_pass_fields.does", "coverage_note"
        ),
        task_fit=_first_str(
            row, "task_fit", "classification_rationale", "classification_basis"
        ),
        stages=stages,
        roles=_as_str_list(row.get("roles")),
        tools=_as_str_list(row.get("tools")),
        stop_rules=_as_str_list(row.get("stop_rules")),
        failure_behaviour=_first_str(row, "failure_behaviour", "failure_behavior"),
        benchmark_evidence=_first_str(row, "benchmark_evidence"),
        declared_mechanisms=_mechanisms(row),
        license_text=lic_text,
        license_tier=classify_license(lic_text),
        maintenance_state=json.dumps(
            row.get("maintenance_state") or row.get("maintenance") or {}, sort_keys=True
        )[:400],
        provenance_anchor=anchor,
        provenance_anchor_kind=classify_anchor(anchor),
        provenance_resolved=resolved,
        provenance_probe=probe,
    )


def iter_registry_rows(
    registry_dir: Path | None = None,
) -> Iterable[tuple[dict[str, Any], str]]:
    """Yield ``(row, source_file)`` for every real candidate row across all shapes.

    A header/manifest row (one carries a ``_manifest`` key instead of candidate fields) is NOT
    a candidate and is skipped - counting it would inflate the registry by one.
    """
    rdir = registry_dir or REGISTRY_DIR
    for path in sorted(rdir.glob("workflow-candidates-[0-9].json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc if isinstance(doc, list) else (doc.get("candidates") or [])
        for row in rows:
            if not isinstance(row, dict) or "_manifest" in row:
                continue
            yield row, path.name


def load_registry_candidates(
    registry_dir: Path | None = None, repo_root: Path | None = None
) -> list[Candidate]:
    return [
        normalize_row(row, src, repo_root)
        for row, src in iter_registry_rows(registry_dir)
    ]


def load_dsl_candidates(workflows_dir: Path | None = None) -> list[Candidate]:
    """Every ``platform/workflows/*.json`` that is actually a DSL document.

    The directory also holds ``*-STATUS.json`` sidecars from sibling lanes; the discriminator is
    the presence of a ``dsl_version`` key, not the filename.
    """
    wdir = workflows_dir or WORKFLOWS_DIR
    out: list[Candidate] = []
    if not wdir.is_dir():
        return out
    for path in sorted(wdir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(doc, dict) or "dsl_version" not in doc:
            continue
        lineage = doc.get("lineage") or {}
        lic_parts = [
            str(d.get("license", ""))
            for d in (lineage.get("derived_from") or [])
            if isinstance(d, dict)
        ]
        lic_text = (
            " | ".join(p for p in lic_parts if p) or "owner-authored private estate"
        )
        rel = path.relative_to(path.parents[2]).as_posix()
        out.append(
            Candidate(
                id=str(doc.get("id") or path.stem),
                name=str(doc.get("name") or path.stem),
                source_file=path.name,
                family="I-executable-dsl-blueprint",
                classification="ADOPT-AS-IS",
                what_it_does=str(doc.get("description", ""))[:2000],
                task_fit=", ".join(_as_str_list(doc.get("categories"))),
                # stage ids AND titles: the titles are where a blueprint says what it actually
                # does ("S2 FAN OUT one worktree per unit"), and a search over ids alone was
                # measured to be near-blind - 7 of 8 top hits scored lexical_fit 0.00.
                stages=[
                    f"{s.get('id')} {s.get('title', '')}".strip()
                    for s in doc.get("stages", [])
                    if isinstance(s, dict)
                ],
                roles=sorted(doc.get("roles", {}) or {}),
                tools=sorted((doc.get("tool_policy") or {}).get("allow", []) or []),
                stop_rules=[
                    str(r.get("expression"))
                    for r in doc.get("stopping_rules", []) or []
                    if isinstance(r, dict)
                ],
                failure_behaviour=json.dumps(
                    doc.get("failure_policy") or {}, sort_keys=True
                )[:400],
                benchmark_evidence="structural: measured directly off the DSL document",
                declared_mechanisms=_as_str_list(doc.get("tags")),
                license_text=lic_text,
                license_tier=classify_license(lic_text),
                maintenance_state=f"version={doc.get('version')}",
                provenance_anchor=rel,
                provenance_anchor_kind="repo-relative",
                provenance_resolved=True,
                provenance_probe=f"loaded and json-parsed from {rel}",
                dsl_doc=doc,
                dsl_path=rel,
            )
        )
    return out


def load_all(
    registry_dir: Path | None = None,
    workflows_dir: Path | None = None,
    repo_root: Path | None = None,
) -> list[Candidate]:
    """The full candidate population, registry rows first then executable blueprints."""
    return load_registry_candidates(registry_dir, repo_root) + load_dsl_candidates(
        workflows_dir
    )


def population_summary(cands: list[Candidate]) -> dict[str, Any]:
    from collections import Counter

    return {
        "total": len(cands),
        "registry_rows": sum(1 for c in cands if not c.is_executable_dsl),
        "executable_dsl_blueprints": sum(1 for c in cands if c.is_executable_dsl),
        "by_license_tier": dict(Counter(c.license_tier for c in cands).most_common()),
        "by_anchor_kind": dict(
            Counter(c.provenance_anchor_kind for c in cands).most_common()
        ),
        "provenance_resolved_true": sum(
            1 for c in cands if c.provenance_resolved is True
        ),
        "provenance_resolved_false": sum(
            1 for c in cands if c.provenance_resolved is False
        ),
        "provenance_not_checked": sum(
            1 for c in cands if c.provenance_resolved is None
        ),
        "duplicate_ids": sorted(
            k for k, v in Counter(c.id for c in cands).items() if v > 1
        ),
    }
