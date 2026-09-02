#!/usr/bin/env python3
"""Claim-record validator: JSON Schema plus registry-level edge and ranking rules."""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
CONTRACT = REPO / "command-center/phase4/contracts/ARC-0085.json"

SEVERITY_W = {"P0": 8, "P1": 4, "P2": 2, "P3": 1, "none": 0}
CLASS_W = {
    "architecture": 2,
    "operator-decision": 2,
    "implementation": 1,
    "test": 1,
    "docs": 1,
    "none": 0,
}


def load_schema(path: Path | None = None) -> dict:
    p = path or CONTRACT
    return json.loads(p.read_text(encoding="utf-8"))


def schema_errors(record: dict, schema: dict | None = None) -> list[str]:
    sch = schema if schema is not None else load_schema()
    v = jsonschema.Draft202012Validator(sch)
    return [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in v.iter_errors(record)
    ]


def mechanism_key(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "")
    s = s.casefold()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def independence_key(entry: dict) -> tuple:
    probe = entry.get("probe") or {}
    if all(probe.get(k) for k in ("tool", "engine", "shell", "field")):
        return (
            str(probe["tool"]),
            str(probe["engine"]),
            str(probe["shell"]),
            str(probe["field"]),
        )
    return ("path-line", str(entry.get("path") or ""), int(entry.get("line") or 0))


def independent_evidence_score(record: dict) -> int:
    keys = {independence_key(e) for e in (record.get("source_lineage") or [])}
    return len(keys)


def decision_impact_score(record: dict) -> int:
    impact = record.get("implementation_impact") or {}
    return SEVERITY_W.get(str(impact.get("severity") or "none"), 0) * CLASS_W.get(
        str(impact.get("class") or "none"), 0
    )


def rank_score(record: dict) -> int:
    return independent_evidence_score(record) * decision_impact_score(record)


def _merge_status(statuses: list[str]) -> str:
    uniq = set(statuses)
    if "REFUTED" in uniq and "CONFIRMED" in uniq:
        return "PARTIAL"
    if "REFUTED" in uniq:
        return "REFUTED"
    if "CONFIRMED" in uniq and uniq <= {"CONFIRMED"}:
        return "CONFIRMED"
    if "UNVERIFIED" in uniq:
        return "UNVERIFIED"
    if "NOT-CHECKED" in uniq:
        return "NOT-CHECKED"
    if "BLOCKED" in uniq:
        return "BLOCKED"
    return statuses[0]


def _band_rank(band: str) -> int:
    order = ["remote", "unlikely", "roughly-even", "likely", "almost-certain"]
    try:
        return order.index(band)
    except ValueError:
        return 0


def collapse(records: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Collapse same-mechanism records. Returns (canonical_records, alias_to_canonical)."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for rec in records:
        key = mechanism_key(str(rec.get("canonical_mechanism") or ""))
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(rec)

    alias_map: dict[str, str] = {}
    out: list[dict] = []
    for key in order:
        members = groups[key]
        def _cid(m: dict) -> str:
            return str(m.get("claim_id") or m.get("id") or m.get("canonical_id") or "")

        ids = [_cid(m) for m in members]
        ids = [i for i in ids if i] or ["anon-0"]
        canonical_id = sorted(ids)[0]
        for cid in ids:
            alias_map[cid] = canonical_id
        survivor = copy.deepcopy(next((m for m in members if _cid(m) == canonical_id), members[0]))
        survivor["claim_id"] = canonical_id
        lineage = []
        seen_lin = set()
        supports: list[str] = []
        contradicts: list[str] = []
        for m in members:
            for e in m.get("source_lineage") or []:
                sig = (
                    e.get("author"),
                    e.get("path"),
                    e.get("line"),
                    independence_key(e),
                )
                if sig in seen_lin:
                    continue
                seen_lin.add(sig)
                lineage.append(copy.deepcopy(e))
            supports.extend(m.get("supports") or [])
            contradicts.extend(m.get("contradicts") or [])
        survivor["source_lineage"] = lineage
        survivor["duplicate_of"] = []
        survivor["supports"] = sorted(set(supports) - set(ids))
        survivor["contradicts"] = sorted(set(contradicts) - set(ids))
        survivor["verification_status"] = _merge_status(
            [str(m.get("verification_status")) for m in members]
        )
        bands = [str(m.get("confidence_band")) for m in members]
        survivor["confidence_band"] = min(bands, key=_band_rank)
        out.append(survivor)
        for m in members:
            cid = str(m["claim_id"])
            if cid == canonical_id:
                continue
            alias = copy.deepcopy(m)
            alias["duplicate_of"] = [canonical_id]
            alias["canonical_mechanism"] = survivor["canonical_mechanism"]
            out.append(alias)
    return out, alias_map


def rewrite_edges(records: list[dict], alias_map: dict[str, str]) -> list[dict]:
    def remap(ids: list[str], self_id: str) -> list[str]:
        mapped = []
        for i in ids:
            t = alias_map.get(i, i)
            if t != self_id and t not in mapped:
                mapped.append(t)
        return mapped

    rewritten = []
    for rec in records:
        row = copy.deepcopy(rec)
        cid = str(row["claim_id"])
        if row.get("duplicate_of"):
            rewritten.append(row)
            continue
        row["supports"] = remap(row.get("supports") or [], cid)
        row["contradicts"] = remap(row.get("contradicts") or [], cid)
        rewritten.append(row)
    return rewritten


def _canonical_records(records: list[dict]) -> list[dict]:
    return [r for r in records if not (r.get("duplicate_of") or [])]


def edge_errors(records: list[dict]) -> list[str]:
    errs: list[str] = []
    by_id = {str(r["claim_id"]): r for r in records}
    canon = {str(r["claim_id"]): r for r in _canonical_records(records)}

    def exist(cid: str, src: str, kind: str) -> None:
        if cid not in by_id:
            errs.append(f"{src} {kind} -> missing id {cid}")

    parent: dict[str, str] = {}
    for rec in records:
        src = str(rec["claim_id"])
        dups = rec.get("duplicate_of") or []
        if src in dups:
            errs.append(f"{src} duplicate_of self")
        for t in dups:
            exist(t, src, "duplicate_of")
            parent[src] = str(t)
        for t in rec.get("supports") or []:
            exist(t, src, "supports")
            if t == src:
                errs.append(f"{src} supports self")
        for t in rec.get("contradicts") or []:
            exist(t, src, "contradicts")
            if t == src:
                errs.append(f"{src} contradicts self")
            if t in (rec.get("duplicate_of") or []):
                errs.append(f"{src} both duplicate_of and contradicts {t}")
            other = by_id.get(str(t))
            if other is None:
                continue
            if (
                rec.get("verification_status") == "CONFIRMED"
                and other.get("verification_status") == "CONFIRMED"
            ):
                errs.append(
                    f"unresolved-confirmed-contradiction {src} vs {t}"
                )

    # duplicate_of cycle
    seen_global = set()
    for start in parent:
        if start in seen_global:
            continue
        stack = []
        cur: str | None = start
        while cur is not None:
            if cur in stack:
                errs.append(f"duplicate_of cycle involving {cur}")
                break
            stack.append(cur)
            seen_global.add(cur)
            cur = parent.get(cur)

    # every non-canonical must point at a canonical
    for rec in records:
        dups = rec.get("duplicate_of") or []
        if not dups:
            continue
        tgt = str(dups[0])
        if tgt not in canon:
            errs.append(f"{rec['claim_id']} duplicate_of {tgt} is not canonical")
    return errs


def rank_canonical(records: list[dict]) -> list[dict]:
    rows = []
    for rec in _canonical_records(records):
        row = copy.deepcopy(rec)
        row["_independent_evidence_score"] = independent_evidence_score(rec)
        row["_decision_impact_score"] = decision_impact_score(rec)
        row["_rank_score"] = rank_score(rec)
        rows.append(row)
    rows.sort(key=lambda r: (-r["_rank_score"], r["claim_id"]))
    return rows


def validate_records(
    records: list[dict], schema: dict | None = None
) -> dict[str, Any]:
    sch = schema if schema is not None else load_schema()
    field_errs: dict[str, list[str]] = {}
    for rec in records:
        cid = str(rec.get("claim_id") or "<missing-id>")
        errs = schema_errors(rec, sch)
        if errs:
            field_errs[cid] = errs
    collapsed, alias_map = collapse(records)
    collapsed = rewrite_edges(collapsed, alias_map)
    e_errs = edge_errors(collapsed)
    ranked = rank_canonical(collapsed)
    return {
        "schema_errors": field_errs,
        "edge_errors": e_errs,
        "collapsed": collapsed,
        "alias_map": alias_map,
        "canonical_count": len(_canonical_records(collapsed)),
        "ranked": ranked,
        "ok": not field_errs and not e_errs,
    }
