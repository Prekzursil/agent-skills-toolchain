#!/usr/bin/env python3
"""Structural checks for RES-0074 (imported by named probes)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0074.json"
INDEX = HERE / "capture-index.json"
SENTINEL = (
    "SUCCESS:RES-0074 in the receipt AND a per-format table naming read "
    "and write implementations, with one-way formats marked"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
INDEP = ("tool", "engine", "shell", "field")


def load_art(path: Path | None = None) -> dict:
    p = path or ART
    return json.loads(p.read_text(encoding="utf-8"))


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def capture_map() -> dict[str, dict]:
    idx = load_index()
    return {c["id"]: c for c in idx.get("captures") or [] if isinstance(c, dict)}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def both_rw(row: dict) -> set[str]:
    readers = {str(x) for x in (row.get("read_implementations") or []) if str(x).strip()}
    writers = {str(x) for x in (row.get("write_implementations") or []) if str(x).strip()}
    return readers & writers


def is_real_interchange(row: dict) -> bool:
    if row.get("one_way") is True:
        return False
    return len(both_rw(row)) >= 2


def independence_key(rail: dict) -> tuple[str, str, str, str]:
    return tuple(str(rail.get(k) or "") for k in INDEP)  # type: ignore[return-value]


def rails_independent(a: dict, b: dict) -> bool:
    ka, kb = independence_key(a), independence_key(b)
    if ka == kb:
        return False
    diffs = sum(1 for x, y in zip(ka, kb) if x != y)
    return diffs >= 2


def grade_table(doc: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return False, f"state:{st}"
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        return False, "sentinel-absent"
    table = doc.get("per_format_table")
    if not isinstance(table, list) or len(table) < 6:
        return False, "table-too-small"
    one_way = 0
    real = []
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            return False, f"row-{i}-not-object"
        fid = str(row.get("format_id") or "")
        if not fid:
            return False, f"row-{i}-no-format_id"
        r = row.get("read_implementations")
        w = row.get("write_implementations")
        if not isinstance(r, list) or not isinstance(w, list) or not r or not w:
            return False, f"{fid}:missing-rw-names"
        if "one_way" not in row:
            return False, f"{fid}:one_way-unmarked"
        if row.get("one_way") is True:
            one_way += 1
            if is_real_interchange(row):
                return False, f"{fid}:one_way-but-classified-real"
        else:
            if not is_real_interchange(row):
                return False, f"{fid}:not-one-way-but-lacks-two-rw-impls"
            real.append(fid)
    if one_way < 1:
        return False, "one-way-control-absent"
    if "BPMN-2.0" not in real:
        return False, "bpmn-not-classified-real"
    extras = [x for x in real if x != "BPMN-2.0"]
    if extras:
        return False, f"overclaim-real:{extras}"
    return True, f"ok rows={len(table)} one_way={one_way} real={real}"


def grade_rails(doc: dict, *, require_files: bool = True) -> tuple[bool, str]:
    caps = capture_map()
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-absent"
    for claim in claims:
        if not isinstance(claim, dict):
            return False, "claim-not-object"
        cid = str(claim.get("claim_id") or "?")
        verdict = str(claim.get("verdict") or "")
        if verdict in {"REFUTED", "NOT-CHECKED"}:
            continue
        rails = claim.get("rails") or claim.get("source_lineage")
        if not isinstance(rails, list) or len(rails) < 2:
            return False, f"{cid}:need-two-rails"
        kinds = {str(r.get("rail_kind") or r.get("kind") or "") for r in rails}
        if "api" not in kinds or "prose" not in kinds:
            return False, f"{cid}:need-api-and-prose"
        if not rails_independent(rails[0], rails[1]):
            return False, f"{cid}:rails-not-independent"
        for r in rails[:2]:
            st = int(r.get("http_status") or 0)
            if st != 200:
                return False, f"{cid}:http-{st}"
            sha = str(r.get("sha256") or "")
            cap_id = str(r.get("capture_id") or "")
            if cap_id not in caps:
                return False, f"{cid}:capture-missing:{cap_id}"
            rec = caps[cap_id]
            if rec.get("sha256") != sha:
                return False, f"{cid}:index-sha-mismatch:{cap_id}"
            if require_files:
                rel = str(rec.get("body_path") or "")
                path = REPO / rel
                if not path.is_file():
                    return False, f"{cid}:body-absent:{rel}"
                live = file_sha256(path)
                if live != sha:
                    return False, f"{cid}:body-sha-mismatch:{cap_id}"
        if str(claim.get("evidence_grade") or "") == "E3":
            return False, f"{cid}:e3-cited-as-fact"
    return True, f"ok claims={len(claims)}"


def both_states_table(doc: dict) -> tuple[bool, str]:
    ok, why = grade_table(doc)
    if not ok:
        return False, f"good-state-failed:{why}"
    mutant = copy.deepcopy(doc)
    for row in mutant["per_format_table"]:
        if row.get("one_way") is True:
            row["one_way"] = False
    mok, mwhy = grade_table(mutant)
    if mok:
        return False, "mutant-cleared-one-way-still-accepted"
    mutant2 = copy.deepcopy(doc)
    for row in mutant2["per_format_table"]:
        if row.get("format_id") == "GHA-YAML":
            row["one_way"] = False
    m2ok, _ = grade_table(mutant2)
    if m2ok:
        return False, "mutant-gha-as-real-accepted"
    return True, f"good={why}; mutant_fired={mwhy}"


def both_states_rails(doc: dict) -> tuple[bool, str]:
    ok, why = grade_rails(doc)
    if not ok:
        return False, f"good-state-failed:{why}"
    mutant = copy.deepcopy(doc)
    stripped = False
    for claim in mutant["claims"]:
        if str(claim.get("verdict") or "") == "CONFIRMED":
            rails = claim.get("rails")
            if isinstance(rails, list) and len(rails) >= 2:
                claim["rails"] = rails[:1]
                stripped = True
                break
    if not stripped:
        return False, "no-confirmed-rail-to-strip"
    mok, mwhy = grade_rails(mutant, require_files=False)
    if mok:
        return False, "mutant-one-rail-still-accepted"
    return True, f"good={why}; mutant_fired={mwhy}"
