#!/usr/bin/env python3
"""Qualifier B: stopping-condition recompute, independent of qualify_a.

Stopping condition (catalog WFA-0123): after alias collapse, duplicate collapse
and trivial-fork exclusion, count candidates that are classified AND carry a
resolved provenance record AND a fetched licence class. Floor = 160.

This file must not import qualify_a. Licence free-text is inadmissible.
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

FLOOR = 160

DECIDED = {
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
NOT_YET = {
    "UNKNOWN-NEEDS-PROBE",
    "UNKNOWN-NEEDS-PROBE",
    "UNCLASSIFIED",
    "UNSET",
    "",
}

LICENCE_PREFIXES = (
    (b"mit license", "MIT"),
    (b"apache license", "Apache-2.0"),
    (b"gnu general public license", "GPL"),
    (b"spdx-license-identifier: mit", "MIT"),
    (b"spdx-license-identifier: apache-2.0", "Apache-2.0"),
)


def _up(value: Any) -> str:
    return str(value or "").strip().upper().replace("_", "-")


def classified_p(rec: dict) -> bool:
    c = _up(rec.get("classification") or rec.get("disposition"))
    return bool(c) and c in DECIDED and c not in NOT_YET


def _file(repo: Path, value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw or "://" in raw:
        return None
    raw = raw.split("#", 1)[0]
    if ":" in raw and not raw.startswith("/"):
        # drop :line only when the prefix is a real path
        head, tail = raw.rsplit(":", 1)
        if tail.isdigit():
            raw = head
    p = Path(raw)
    if not p.is_absolute():
        p = repo / raw
    return p


def resolved_provenance_p(rec: dict, repo: Path) -> bool:
    for key in ("provenance", "provenance_path", "anchor", "path"):
        p = _file(repo, rec.get(key))
        if p is not None and p.is_file() and p.stat().st_size > 0:
            return True
    return False


def fetched_licence_p(rec: dict, repo: Path) -> str | None:
    files: list[Path] = []
    for key in ("license_file", "licence_file"):
        p = _file(repo, rec.get(key))
        if p is not None:
            files.append(p)
    for key in ("provenance", "path"):
        src = _file(repo, rec.get(key))
        if src is not None:
            d = src.parent
            files.extend(
                [
                    d / "LICENSE",
                    d / "LICENSE.md",
                    d / "LICENCE",
                    d / "COPYING",
                ]
            )
            break
    tried: set[str] = set()
    for path in files:
        s = str(path)
        if s in tried:
            continue
        tried.add(s)
        if not path.is_file():
            continue
        try:
            blob = path.read_bytes()[:800].lower()
        except OSError:
            continue
        if not blob:
            continue
        for prefix, label in LICENCE_PREFIXES:
            if prefix in blob:
                return label
        if blob.startswith(b"copyright") or b"licensed" in blob:
            return "LICENSE-FILE-PRESENT"
    return None


def _text(rec: dict) -> str:
    mech = rec.get("mechanisms")
    if isinstance(mech, list):
        mech = " ".join(map(str, mech))
    return " ".join(
        str(x)
        for x in (
            rec.get("does") or rec.get("description") or "",
            mech or "",
        )
    ).lower()


def _alias_of(rec: dict, ids: set[str], names: dict[str, str]) -> str | None:
    for key in ("alias_of", "alias_target"):
        v = rec.get(key)
        if v and str(v) in ids and str(v) != str(rec.get("id")):
            return str(v)
    body = str(rec.get("body") or rec.get("does") or "").strip()
    first = body.splitlines()[0].strip() if body else ""
    low = first.lower()
    for prefix in ("use skill ", "invoke skill ", "run skill "):
        if low.startswith(prefix):
            name = first[len(prefix) :].strip().rstrip(".")
            if name in ids:
                return name
            if name in names:
                return names[name]
    return None


def _stem(name: str) -> str:
    n = str(name or "").strip().lower()
    for suf in ("-copy", "-fork", "-clone", "-renamed", "-v2", "_copy"):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return "".join(ch for ch in n if ch.isalnum())


def collapse(records: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    ids = {str(r.get("id")) for r in records}
    names = {str(r.get("name")): str(r.get("id")) for r in records if r.get("name")}
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    drop: set[str] = set()

    for rec in records:
        rid = str(rec.get("id"))
        target = _alias_of(rec, ids, names)
        if target:
            drop.add(rid)
            excluded["alias"].append(rid)

    live = [r for r in records if str(r.get("id")) not in drop]
    texts = {str(r.get("id")): _text(r) for r in live}
    live_ids = [str(r.get("id")) for r in live]
    for i, a in enumerate(live_ids):
        if a in drop:
            continue
        for b in live_ids[i + 1 :]:
            if b in drop:
                continue
            ratio = difflib.SequenceMatcher(None, texts[a], texts[b]).ratio()
            if ratio >= 0.90:
                drop.add(b)
                excluded["duplicate"].append(b)

    live = [r for r in records if str(r.get("id")) not in drop]
    seen_stem: dict[str, str] = {}
    for rec in live:
        rid = str(rec.get("id"))
        st = _stem(str(rec.get("name") or rid))
        prev = seen_stem.get(st)
        if prev:
            drop.add(rid)
            excluded["trivial_fork"].append(rid)
        else:
            seen_stem[st] = rid

    return [r for r in records if str(r.get("id")) not in drop], excluded


def evaluate(records: list[dict], repo: Path) -> dict[str, Any]:
    raw = len(records)
    survivors, excluded = collapse(records)
    qualified = []
    rejected = []
    for rec in survivors:
        flags = {
            "id": str(rec.get("id")),
            "classified": classified_p(rec),
            "resolved_provenance": resolved_provenance_p(rec, repo),
            "fetched_licence": fetched_licence_p(rec, repo) is not None,
            "licence_class": fetched_licence_p(rec, repo),
        }
        if (
            flags["classified"]
            and flags["resolved_provenance"]
            and flags["fetched_licence"]
        ):
            qualified.append(flags)
        else:
            rejected.append(flags)
    n = len(qualified)
    return {
        "method": "qualify-b-difflib-header-prefix",
        "raw_count": raw,
        "after_collapse": len(survivors),
        "qualified_count": n,
        "floor": FLOOR,
        "floor_clears": n >= FLOOR,
        "shortfall": max(0, FLOOR - n),
        "excluded": excluded,
        "failed_three_way_and": rejected,
        "qualified": qualified,
        "stopping_condition": (
            "After alias collapse, duplicate collapse and trivial-fork "
            "exclusion, count rows that are classified AND have resolved "
            "provenance AND a fetched licence class. Floor 160. A raw "
            "record count (historically 284) is not this metric."
        ),
    }
