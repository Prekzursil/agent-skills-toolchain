#!/usr/bin/env python3
"""Settle SYN-0011 divergences by re-reading raw sources. Never by vote.

`vote_pick` lives in scenario.py for the negative control; this module
does not call it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import scenario as S

VOTE_RE = re.compile(S.VOTE_RE_PATTERN)


def reason_is_clean(reason: str) -> bool:
    return not bool(VOTE_RE.search(reason or ""))


def catalog_unit(repo: Path, uid: str) -> dict:
    data = json.loads((repo / S.CATALOG_REL).read_text(encoding="utf-8"))
    units = data.get("work_units")
    if not isinstance(units, list):
        raise RuntimeError("WORK-UNIT-CATALOG.json missing work_units")
    for u in units:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(f"catalog unit {uid} missing")


def _unit_span(lines: list[str], uid: str) -> tuple[int, int]:
    needle_a = f'"id": "{uid}",'
    needle_b = f'"id": "{uid}"'
    id_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in {needle_a, needle_b}:
            id_idx = i
            break
    if id_idx is None:
        raise KeyError(f"no id line for {uid}")
    start = id_idx
    while start > 0 and lines[start].strip() != "{":
        start -= 1
    end = id_idx + 1
    while end < len(lines) and lines[end].strip() not in {"}", "},"}:
        end += 1
    return start, end


def catalog_field_anchor(repo: Path, uid: str, field: str) -> dict:
    path = repo / S.CATALOG_REL
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _unit_span(lines, uid)
    prefix = f'"{field}":'
    field_idx = None
    for i in range(start, end + 1):
        if lines[i].strip().startswith(prefix):
            field_idx = i
            break
    if field_idx is None:
        return {"path": S.CATALOG_REL, "line": 0, "snippet": "", "resolves": False}
    snippet = lines[field_idx].strip()
    return {
        "path": S.CATALOG_REL,
        "line": field_idx + 1,
        "snippet": snippet[:240],
        "resolves": True,
    }


def file_token_anchor(repo: Path, rel: str, token: str) -> dict:
    path = repo / rel
    if not path.is_file():
        return {"path": rel, "line": 0, "snippet": "", "resolves": False, "hit": False}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if token in line:
            return {
                "path": rel,
                "line": i,
                "snippet": line.strip()[:240],
                "resolves": True,
                "hit": True,
            }
    return {"path": rel, "line": 0, "snippet": "", "resolves": False, "hit": False}


def _supported(stmt: dict, repo: Path, div: dict) -> tuple[bool, dict]:
    kind = div["kind"]
    if kind == "file-token":
        anc = file_token_anchor(repo, div["raw_path"], stmt["token"])
        return bool(anc.get("hit")), anc
    if kind == "multi-file-token":
        anc = file_token_anchor(repo, stmt["raw_path"], stmt["token"])
        return bool(anc.get("hit")), anc
    if kind == "catalog-field":
        actual = catalog_unit(repo, div["unit_id"]).get(div["field"])
        anc = catalog_field_anchor(repo, div["unit_id"], div["field"])
        return actual == stmt.get("equals") and bool(anc.get("resolves")), anc
    if kind == "catalog-field-pair":
        actual = catalog_unit(repo, stmt["unit_id"]).get(stmt["field"])
        anc = catalog_field_anchor(repo, stmt["unit_id"], stmt["field"])
        if "equals" in stmt:
            ok = actual == stmt["equals"]
        elif "startswith" in stmt:
            ok = isinstance(actual, str) and actual.startswith(stmt["startswith"])
        else:
            ok = False
        return bool(ok and anc.get("resolves")), anc
    raise ValueError(f"unknown kind {kind}")


def _reason(div: dict, unsupported: list[dict], anchors: list[dict]) -> str:
    kind = div["kind"]
    if kind == "file-token":
        hit = next(a for a in anchors if a.get("hit"))
        miss = [s["id"] for s in unsupported]
        return (
            f"Re-read {hit['path']}:{hit['line']}. The line is "
            f"{hit['snippet']!r}. That string matches the supported "
            f"statement and does not contain the unsupported token(s) "
            f"claimed by {miss}."
        )
    if kind == "catalog-field":
        hit = next(a for a in anchors if a.get("resolves"))
        return (
            f"Parsed {hit['path']} unit {div['unit_id']} field "
            f"{div['field']} and cited {hit['path']}:{hit['line']} "
            f"{hit['snippet']!r}. The parsed value matches only the "
            f"supported statement."
        )
    if kind == "multi-file-token":
        bits = [
            f"{stmt['id']} holds because {anc['path']}:{anc['line']} "
            f"contains {stmt['token']!r}"
            for stmt, anc in zip(div["statements"], anchors)
        ]
        return (
            "Both statements re-read as true in different files. "
            + " ".join(bits)
            + ". They are not exclusive."
        )
    if kind == "catalog-field-pair":
        bits = [
            f"{stmt['id']} holds of {stmt['unit_id']}.{stmt['field']} "
            f"at {anc['path']}:{anc['line']}"
            for stmt, anc in zip(div["statements"], anchors)
        ]
        return (
            "Each statement is true of its own unit's catalog field. "
            + " ".join(bits)
            + ". Treating either as a global shape is a scope error."
        )
    raise ValueError(kind)


def settle(div: dict, repo: Path | None = None) -> dict:
    root = repo or S.REPO
    flags: list[bool] = []
    anchors: list[dict] = []
    for stmt in div["statements"]:
        ok, anc = _supported(stmt, root, div)
        flags.append(ok)
        anchors.append(anc)
    supported = [s for s, ok in zip(div["statements"], flags) if ok]
    unsupported = [s for s, ok in zip(div["statements"], flags) if not ok]
    if not supported:
        raise RuntimeError(f"{div['id']} raw source did not support any statement")

    if len(supported) == 1 and unsupported:
        winner = supported[0]
        disposition = "WRONG"
        win_idx = div["statements"].index(winner)
        raw_anchor = dict(anchors[win_idx])
        max_n = max(len(s["candidate_ids"]) for s in div["statements"])
        minority_win = len(winner["candidate_ids"]) < max_n
        winner_id: str | None = winner["id"]
    else:
        paths = [
            stmt.get("raw_path") or div.get("raw_path") or anc.get("path")
            for stmt, anc in zip(div["statements"], anchors)
        ]
        if len({p for p in paths if p}) > 1:
            disposition = "BOTH-TRUE-DIFFERENT-SCOPE"
        else:
            disposition = "CORRECTLY-SCOPED-DIFFERENTLY"
        winner_id = None
        minority_win = False
        raw_anchor = dict(next(a for a in anchors if a.get("line")))

    raw_anchor["resolves"] = True
    raw_anchor.pop("hit", None)
    reason = _reason(div, unsupported, anchors)
    if not reason_is_clean(reason):
        raise RuntimeError(f"{div['id']} reason failed lexical vote-gate: {reason}")
    if not raw_anchor.get("line"):
        raise RuntimeError(f"{div['id']} anchor did not resolve")

    return {
        "id": div["id"],
        "topic": div["topic"],
        "competing_statements": [
            {
                "id": s["id"],
                "candidate_ids": list(s["candidate_ids"]),
                "verbatim": s["verbatim"],
            }
            for s in div["statements"]
        ],
        "raw_anchor": {
            "path": raw_anchor["path"],
            "line": int(raw_anchor["line"]),
            "snippet": raw_anchor["snippet"],
            "resolves": True,
        },
        "winner_statement_id": winner_id,
        "losing_disposition": disposition,
        "reason": reason,
        "minority_win": bool(minority_win),
    }


def settle_all(repo: Path | None = None) -> list[dict]:
    return [settle(d, repo) for d in S.divergences()]


def vote_citations(rows: list[dict]) -> int:
    return sum(0 if reason_is_clean(r.get("reason") or "") else 1 for r in rows)
