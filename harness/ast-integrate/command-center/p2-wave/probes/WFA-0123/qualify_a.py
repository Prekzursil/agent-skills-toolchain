#!/usr/bin/env python3
"""Qualifier A: three-way AND after alias/duplicate/trivial-fork collapse.

Independence: Jaccard token collapse and SPDX-line licence parse. Qualifier B
must not import this module. Free-text `license` fields are not fetched licences.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FLOOR = 160

CLASSIFIED = frozenset(
    {
        "ADOPT-AS-IS",
        "ADOPT-AS-IS",
        "ADOPT-WITH-WRAPPER",
        "ADOPT-WITH-WRAPPER",
        "DISTILL",
        "RETIRE",
        "REPAIR",
        "EXTEND",
        "MERGE",
        "SPECIALIZE",
        "CLEAN-ROOM-REIMPLEMENT",
        "COMPOSE",
        "GENERALIZE",
        "REBUILD-FROM-SPEC",
        "REJECT",
        "TRANSLATE",
    }
)
UNDECIDED = frozenset(
    {
        "",
        "UNKNOWN-NEEDS-PROBE",
        "UNKNOWN-NEEDS-PROBE",
        "UNCLASSIFIED",
        "UNSET",
        "NONE",
    }
)
FORK_SUFFIX = re.compile(
    r"(?:[-_ ](?:copy|fork|clone|renamed|v2|dup))+$",
    re.IGNORECASE,
)
TOKEN = re.compile(r"[a-z0-9]+")
SKILL_INVOKE = re.compile(
    r"^\s*(?:use|invoke|run)?\s*skill[:\s]+([a-z0-9._-]+)\s*$",
    re.IGNORECASE,
)
SPDX_LINE = re.compile(
    r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)",
    re.IGNORECASE,
)


def _norm_class(value: Any) -> str:
    return str(value or "").strip().upper().replace("_", "-")


def is_classified(rec: dict) -> bool:
    c = _norm_class(rec.get("classification") or rec.get("disposition"))
    return c in CLASSIFIED and c not in UNDECIDED


def _as_path(value: Any, repo: Path) -> Path | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith("http://") or raw.startswith("https://"):
        return None
    raw = raw.split("#", 1)[0].split(":", 1)[0] if "://" not in raw else raw
    # file:line anchors — strip trailing :digits
    raw = re.sub(r":\d+$", "", raw)
    p = Path(raw)
    if not p.is_absolute():
        p = repo / raw
    return p


def provenance_resolved(rec: dict, repo: Path) -> bool:
    """Resolved = the provenance anchor exists on this worktree as a file."""
    for key in ("provenance", "provenance_path", "anchor", "path"):
        p = _as_path(rec.get(key), repo)
        if p is not None and p.is_file() and p.stat().st_size > 0:
            return True
    return False


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def fetched_licence_class(rec: dict, repo: Path) -> str | None:
    """Licence class from a fetched LICENSE/COPYING file, never free text."""
    candidates: list[Path] = []
    for key in ("license_file", "licence_file"):
        p = _as_path(rec.get(key), repo)
        if p is not None:
            candidates.append(p)
    prov = None
    for key in ("provenance", "provenance_path", "path"):
        prov = _as_path(rec.get(key), repo)
        if prov is not None:
            break
    if prov is not None:
        parent = prov.parent
        for name in ("LICENSE", "LICENSE.md", "COPYING", "LICENCE", "COPYING.md"):
            candidates.append(parent / name)
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        text = _read(path)
        m = SPDX_LINE.search(text)
        if m:
            return m.group(1).strip()
        head = text[:400].lower()
        if "apache license" in head and "2.0" in head:
            return "Apache-2.0"
        if "mit license" in head or "permission is hereby granted, free of charge" in head:
            return "MIT"
        if "gnu general public license" in head:
            return "GPL-3.0" if "version 3" in head else "GPL-2.0"
        return "LICENSE-FILE-UNPARSED"
    return None


def three_way(rec: dict, repo: Path) -> bool:
    return (
        is_classified(rec)
        and provenance_resolved(rec, repo)
        and fetched_licence_class(rec, repo) is not None
    )


def _tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def _blob(rec: dict) -> str:
    mech = rec.get("mechanisms")
    if isinstance(mech, list):
        mech = " ".join(str(x) for x in mech)
    return " ".join(
        str(x)
        for x in (
            rec.get("name") or "",
            rec.get("does") or rec.get("description") or "",
            mech or "",
        )
    )


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _alias_target(rec: dict, by_id: dict[str, dict]) -> str | None:
    explicit = rec.get("alias_of") or rec.get("alias_target")
    if explicit:
        tid = str(explicit)
        if tid in by_id and tid != rec.get("id"):
            return tid
    body = str(rec.get("body") or rec.get("does") or "")
    m = SKILL_INVOKE.match(body.strip().splitlines()[0] if body.strip() else "")
    if m:
        name = m.group(1)
        for other in by_id.values():
            if other.get("id") == rec.get("id"):
                continue
            if str(other.get("id")) == name or str(other.get("name")) == name:
                return str(other.get("id"))
    kind = str(rec.get("kind") or "").lower()
    if kind == "command":
        tokens = _tokens(body)
        for other in by_id.values():
            if other.get("id") == rec.get("id"):
                continue
            oid = str(other.get("id"))
            if oid in tokens and len(tokens) <= 8:
                return oid
    return None


def _name_core(name: str) -> str:
    n = FORK_SUFFIX.sub("", str(name or "").strip().lower())
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def collapse(records: list[dict], repo: Path) -> tuple[list[dict], dict[str, list[str]]]:
    by_id = {str(r.get("id")): r for r in records if r.get("id")}
    excluded: dict[str, list[str]] = {
        "alias": [],
        "duplicate": [],
        "trivial_fork": [],
    }
    drop: set[str] = set()

    for rec in records:
        rid = str(rec.get("id"))
        if rid in drop:
            continue
        target = _alias_target(rec, by_id)
        if target and target not in drop:
            drop.add(rid)
            excluded["alias"].append(rid)

    remaining = [r for r in records if str(r.get("id")) not in drop]
    blobs = {str(r.get("id")): _tokens(_blob(r)) for r in remaining}
    ids = [str(r.get("id")) for r in remaining]
    for i, a in enumerate(ids):
        if a in drop:
            continue
        for b in ids[i + 1 :]:
            if b in drop:
                continue
            score = jaccard(blobs[a], blobs[b])
            if score >= 0.92:
                # keep the three-way survivor if exactly one qualifies
                keep, lose = a, b
                qa = three_way(by_id[a], repo)
                qb = three_way(by_id[b], repo)
                if qb and not qa:
                    keep, lose = b, a
                drop.add(lose)
                excluded["duplicate"].append(lose)
                _ = keep

    remaining = [r for r in records if str(r.get("id")) not in drop]
    cores: dict[str, str] = {}
    for rec in remaining:
        rid = str(rec.get("id"))
        core = _name_core(str(rec.get("name") or rid))
        other = cores.get(core)
        if other:
            lose = rid
            keep = other
            if three_way(by_id[rid], repo) and not three_way(by_id[other], repo):
                lose, keep = other, rid
            drop.add(lose)
            excluded["trivial_fork"].append(lose)
            cores[core] = keep
        else:
            cores[core] = rid

    survivors = [r for r in records if str(r.get("id")) not in drop]
    return survivors, excluded


def evaluate(records: list[dict], repo: Path) -> dict[str, Any]:
    raw = len(records)
    survivors, excluded = collapse(records, repo)
    qualified = []
    failed_and = []
    for rec in survivors:
        rid = str(rec.get("id"))
        flags = {
            "classified": is_classified(rec),
            "resolved_provenance": provenance_resolved(rec, repo),
            "fetched_licence": fetched_licence_class(rec, repo) is not None,
            "licence_class": fetched_licence_class(rec, repo),
        }
        rec_out = {"id": rid, **flags}
        if flags["classified"] and flags["resolved_provenance"] and flags["fetched_licence"]:
            qualified.append(rec_out)
        else:
            failed_and.append(rec_out)
    qn = len(qualified)
    return {
        "method": "qualify-a-jaccard-spdx",
        "raw_count": raw,
        "after_collapse": len(survivors),
        "qualified_count": qn,
        "floor": FLOOR,
        "floor_clears": qn >= FLOOR,
        "shortfall": max(0, FLOOR - qn),
        "excluded": excluded,
        "failed_three_way_and": failed_and,
        "qualified": qualified,
        "gap": {
            "raw_minus_qualified": raw - qn,
            "collapsed": raw - len(survivors),
            "and_rejected": len(failed_and),
            "note": (
                "Raw record count is not the floor metric. The floor is the "
                "three-way AND after alias, duplicate, and trivial-fork collapse."
            ),
        },
    }
