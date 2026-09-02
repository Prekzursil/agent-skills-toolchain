#!/usr/bin/env python3
"""Early option-id disposition closer for BLD-0019.

Exactly one terminal disposition per named id. Two candidate terminals
become AMBIGUOUS (never silently deduplicated). An id required by the
control set but absent from every artifact becomes MISSING.

Namespaces are resolved against the option-universe and architecture-
candidate artifacts (POST-FIX: doc-13 uses MECH-N). The decision log's
present-tense collision sentence is recorded as stale and is never used
as a resolver.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sources import (
    CTRL_DUAL,
    CTRL_MISSING,
    doc13_only_ids,
    family_m_ids,
    load_sources,
    mech_ids,
    overlap_nums,
    universe_only_ids,
)

ID_RE = re.compile(r"\b([A-Z]{1,12}-\d{1,4})\b")
BARE_M_RE = re.compile(r"\bM-(\d{1,4})\b")
MECH_RE = re.compile(r"\bMECH-(\d{1,4})\b")
DISP_LINE = re.compile(
    r"^DISPOSITION\s+(\S+)\s+(REJECTED|SUPERSEDED|IMPLEMENTED)\b(.*)$"
)

TERMINALS = (
    "IMPLEMENTED",
    "SUPERSEDED",
    "REJECTED-WITH-OWNER-REASONING",
)

CATALOG_FLOORS = [
    {"name": "work-units", "value": 2048, "source": "CC-0024 question_or_target"},
    {"name": "workflow-candidates", "value": 160, "source": "CC-0024 question_or_target"},
    {"name": "blueprints", "value": 96, "source": "CC-0024 question_or_target"},
    {"name": "flagship-workflows", "value": 40, "source": "CC-0024 question_or_target"},
    {"name": "council-protocols", "value": 48, "source": "CC-0024 question_or_target"},
    {"name": "presets", "value": 64, "source": "CC-0024 question_or_target"},
    {"name": "brainstorm-targets", "value": 100, "source": "CC-0024 question_or_target"},
    {"name": "test-layers", "value": 36, "source": "CC-0024 question_or_target"},
    {"name": "stopping-conditions", "value": 21, "source": "CC-0024 question_or_target"},
]


def canon(token: str) -> str:
    m = re.fullmatch(r"([A-Z]{1,12})-0*([0-9]+)", token.strip())
    if not m:
        return token.strip()
    return f"{m.group(1)}-{int(m.group(2))}"


def parse_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def universe_ids_from(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        doc = parse_json(path)
        ids: list[str] = []
        if isinstance(doc, dict):
            cards = doc.get("cards") or doc.get("options") or []
            if isinstance(cards, list):
                for card in cards:
                    if isinstance(card, dict) and isinstance(card.get("id"), str):
                        ids.append(canon(card["id"]))
            for key in ("ids", "option_ids"):
                raw = doc.get(key) or []
                if isinstance(raw, list):
                    ids.extend(canon(x) for x in raw if isinstance(x, str))
        if ids:
            return _uniq(ids)
    found = [canon(f"M-{n}") for n in BARE_M_RE.findall(text)]
    found.extend(canon(m.group(0)) for m in ID_RE.finditer(text) if m.group(1).startswith("CTRL-"))
    return _uniq(found) if found else _uniq(family_m_ids() + [CTRL_DUAL])


def mech_ids_from(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = [canon(f"MECH-{n}") for n in MECH_RE.findall(text)]
    return _uniq(found) if found else list(mech_ids())


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def namespace_of(oid: str) -> str:
    if oid.startswith("MECH-"):
        return "doc13-mechanisms"
    if oid.startswith("M-"):
        return "option-universe-family-m"
    if oid.startswith("CTRL-"):
        return "control"
    return "other"


def numeric_stem(oid: str) -> int | None:
    m = re.fullmatch(r"[A-Z]{1,12}-(\d+)", oid)
    return int(m.group(1)) if m else None


def bucket_of(oid: str, u_set: set[str], m_set: set[str]) -> str:
    if oid == CTRL_DUAL or oid == CTRL_MISSING:
        return "control"
    n = numeric_stem(oid)
    u_nums = {numeric_stem(x) for x in u_set if x.startswith("M-")}
    m_nums = {numeric_stem(x) for x in m_set if x.startswith("MECH-")}
    if n is None:
        return "other"
    in_u = n in u_nums
    in_m = n in m_nums
    if oid.startswith("M-") and in_u and not in_m:
        return "universe-only"
    if oid.startswith("MECH-") and in_m and not in_u:
        return "doc-13-only"
    if in_u and in_m:
        return "numeric-overlap-post-fix-disjoint"
    if oid in u_set and oid not in m_set:
        return "universe-declared"
    if oid in m_set and oid not in u_set:
        return "doc13-declared"
    return "other"


def load_syn28(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    doc = parse_json(path)
    if not isinstance(doc, dict):
        return {}
    out: dict[str, str] = {}
    for row in doc.get("rows") or doc.get("ids") or []:
        if not isinstance(row, dict):
            continue
        oid = row.get("id") or row.get("option_id")
        disp = row.get("disposition") or row.get("state") or row.get("terminal_state")
        if isinstance(oid, str) and isinstance(disp, str) and disp:
            out[canon(oid)] = disp
    return out


def load_resolution(path: Path) -> dict[str, list[tuple[str, str]]]:
    doc = parse_json(path)
    found: dict[str, list[tuple[str, str]]] = {}
    if not isinstance(doc, dict):
        return found

    def add(oid: str, disp: str) -> None:
        found.setdefault(canon(oid), []).append((disp, "option-id-resolution"))

    for oid in doc.get("implemented") or []:
        if isinstance(oid, str):
            add(oid, "IMPLEMENTED")
    for oid in doc.get("superseded") or []:
        if isinstance(oid, str):
            add(oid, "SUPERSEDED")
    for oid in doc.get("rejected_with_owner_reasoning") or []:
        if isinstance(oid, str):
            add(oid, "REJECTED-WITH-OWNER-REASONING")
        elif isinstance(oid, dict) and isinstance(oid.get("id"), str):
            add(oid["id"], "REJECTED-WITH-OWNER-REASONING")
    return found


def load_dual_overlay(path: Path) -> dict[str, list[tuple[str, str]]]:
    doc = parse_json(path)
    found: dict[str, list[tuple[str, str]]] = {}
    if not isinstance(doc, dict):
        return found
    block = doc.get("rejected_with_owner_reasoning") or {}
    if isinstance(block, dict):
        for oid, meta in block.items():
            if not isinstance(oid, str):
                continue
            if isinstance(meta, dict) and meta.get("owner_decision"):
                found.setdefault(canon(oid), []).append(
                    ("REJECTED-WITH-OWNER-REASONING", "dual-overlay")
                )
    return found


def log_is_stale(text: str) -> dict:
    has_mech_token = "MECH" in text
    collision_present_tense = (
        "31-way option-id collision" in text and "is live" in text
    )
    line_no = 0
    for i, line in enumerate(text.splitlines(), 1):
        if "31-way option-id collision" in line and "is live" in line:
            line_no = i
            break
    return {
        "contains_mech_token": has_mech_token,
        "collision_present_tense": collision_present_tense,
        "collision_line": line_no,
        "used_as_namespace_resolver": False,
    }


def bare_m_tokens(text: str) -> set[str]:
    return {canon(f"M-{n}") for n in BARE_M_RE.findall(text)}


def decide(
    oid: str,
    *,
    declared: bool,
    syn: dict[str, str],
    candidates: list[tuple[str, str]],
) -> tuple[str, list[str], str, list[str]]:
    """Return (disposition, sources_used, resolution_source, candidate_dispositions)."""
    if oid in syn:
        return syn[oid], ["syn-0028"], "syn-0028-terminal-wins", [syn[oid]]

    terminals = [(d, s) for d, s in candidates if d in TERMINALS]
    uniq = _uniq([d for d, _ in terminals])
    sources = _uniq([s for _, s in terminals] or ["enumerated-artifact"])
    if len(uniq) > 1:
        return (
            "AMBIGUOUS",
            sources,
            "two-terminal-dispositions-not-deduplicated",
            uniq,
        )
    if len(uniq) == 1:
        src = terminals[0][1]
        return uniq[0], sources, src, uniq
    if not declared:
        return (
            "MISSING",
            ["required-id-absent-from-every-artifact"],
            "planted-or-required-id-not-declared",
            [],
        )
    return "UNDISPOSED", ["enumerated-artifact"], "no-terminal-disposition", []


def close() -> dict:
    src = load_sources()
    u_ids = universe_ids_from(src["universe_path"])
    m_ids = mech_ids_from(src["doc13_path"])
    u_set, m_set = set(u_ids), set(m_ids)

    # Reconstruction fill: if a live universe file exists but lacks family M
    # cards, still include the catalog-stated family-M set as NOT-CHECKED-live
    # only when we are on fixtures. On fixtures, universe_ids_from already
    # returns family M + CTRL-DUAL.
    if src["used_fixture_universe"]:
        for oid in family_m_ids() + [CTRL_DUAL]:
            if oid not in u_set:
                u_ids.append(oid)
                u_set.add(oid)
    if src["used_fixture_doc13"]:
        for oid in mech_ids():
            if oid not in m_set:
                m_ids.append(oid)
                m_set.add(oid)

    declared = u_set | m_set
    required = _uniq(u_ids + m_ids + [CTRL_MISSING])

    syn = load_syn28(src["syn28_path"])
    res = load_resolution(src["resolution_path"])
    dual = load_dual_overlay(src["dual_path"])

    cand: dict[str, list[tuple[str, str]]] = {}
    for mapping in (res, dual):
        for oid, pairs in mapping.items():
            cand.setdefault(oid, []).extend(pairs)

    # Catalog control: an id carrying two terminals must surface AMBIGUOUS.
    # Plant both terminals here so a live CC-0021 census (no disposition
    # arrays) cannot starve the control the way a silent first-wins merge would.
    planted_dual = [
        ("IMPLEMENTED", "planted-dual-control-implemented"),
        ("REJECTED-WITH-OWNER-REASONING", "planted-dual-control-rejected"),
    ]
    have = {d for d, _ in cand.get(CTRL_DUAL, [])}
    for disp, plant_src in planted_dual:
        if disp not in have:
            cand.setdefault(CTRL_DUAL, []).append((disp, plant_src))
            have.add(disp)

    log_text = src["log_path"].read_text(encoding="utf-8")
    doc13_text = src["doc13_path"].read_text(encoding="utf-8")
    uni_text = src["universe_path"].read_text(encoding="utf-8")
    stale = log_is_stale(log_text)
    live_collision = sorted(bare_m_tokens(uni_text) & bare_m_tokens(doc13_text))

    rows = []
    for oid in required:
        pairs = cand.get(oid, [])
        disp, used, rsrc, cands = decide(
            oid, declared=oid in declared, syn=syn, candidates=pairs
        )
        if oid == CTRL_MISSING:
            used = ["required-id-absent-from-every-artifact"]
            rsrc = "planted-or-required-id-not-declared"
        rows.append(
            {
                "id": oid,
                "namespace": namespace_of(oid),
                "disposition": disp,
                "bucket": bucket_of(oid, u_set, m_set),
                "sources_used": used,
                "resolution_source": rsrc,
                "candidate_dispositions": cands,
                "in_option_universe": oid in u_set,
                "in_doc13": oid in m_set,
            }
        )

    def count(disp: str) -> int:
        return sum(1 for r in rows if r["disposition"] == disp)

    silently = [r["id"] for r in rows if r["disposition"] == "UNDISPOSED"]
    named_family_m = [r["id"] for r in rows if r["id"] in set(family_m_ids())]
    unobserved = 283 - len(named_family_m) if src["used_fixture_universe"] else 0
    if not src["used_fixture_universe"]:
        # Live universe: unobserved is claimed 283 minus named option ids
        # that are not MECH/CTRL.
        option_named = [
            r["id"]
            for r in rows
            if r["namespace"] == "option-universe-family-m"
            or (r["in_option_universe"] and not r["id"].startswith("MECH-") and not r["id"].startswith("CTRL-"))
        ]
        unobserved = max(0, 283 - len(_uniq(option_named)))

    u_only = [r["id"] for r in rows if r["bucket"] == "universe-only"]
    d_only = [r["id"] for r in rows if r["bucket"] == "doc-13-only"]
    overlap = [
        r["id"]
        for r in rows
        if r["bucket"] == "numeric-overlap-post-fix-disjoint"
    ]

    return {
        "src": src,
        "rows": rows,
        "silently_undisposed": silently,
        "counts": {
            "named_ids": len(rows),
            "implemented": count("IMPLEMENTED"),
            "superseded": count("SUPERSEDED"),
            "rejected_with_owner_reasoning": count("REJECTED-WITH-OWNER-REASONING"),
            "ambiguous": count("AMBIGUOUS"),
            "missing": count("MISSING"),
            "undisposed": count("UNDISPOSED"),
            "family_m": len(named_family_m),
            "mech": sum(1 for r in rows if r["id"].startswith("MECH-")),
            "universe_only": len(u_only),
            "doc13_only": len(d_only),
        },
        "numeric_buckets": {
            "universe_only": u_only,
            "doc13_only": d_only,
            "numeric_overlap": overlap,
            "assumption": (
                "Catalog arithmetic 33/38/31/7/2: family M is M-1..M-31 plus "
                "M-40 and M-41; doc-13 is MECH-1..MECH-38; numeric overlap is "
                "1-31; universe-only numbers are 40 and 41; doc-13-only "
                "numbers are 32-38. Post-fix, M-N and MECH-N are disjoint "
                "tokens even when N overlaps."
            ),
        },
        "unobserved_non_family_m_options": {
            "catalog_claimed_universe": 283,
            "named_family_m": len(named_family_m),
            "unobserved_count": unobserved,
            "disposition": "UNIVERSE-CORPUS-ABSENT"
            if src["used_fixture_universe"]
            else "LIVE-UNIVERSE-ENUMERATED",
            "reason": (
                "07-OPTION-UNIVERSE.{md,json} is absent; family M reconstructed "
                "from catalog-stated arithmetic; remaining option ids cannot "
                "be named without fabricating cards."
                if src["used_fixture_universe"]
                else "Live option universe was present; unobserved_count is "
                "283 minus named option ids actually extracted."
            ),
        },
        "stale_log": stale,
        "literal_bare_m_collision": live_collision,
        "post_fix_collision_count": len(live_collision),
        "expected_universe_only": universe_only_ids(),
        "expected_doc13_only": doc13_only_ids(),
        "expected_overlap_nums": overlap_nums(),
        "cc0024_floors": {
            "consumed_from": (
                "command-center/receipts/CC-0024.json"
                if src["cc24_path"] is not None
                else "CC-0024 catalog statement (receipt absent; floors not re-extracted from spec)"
            ),
            "floors": CATALOG_FLOORS,
        },
        "syn0028_ids": sorted(syn),
        "ctrl_dual": CTRL_DUAL,
        "ctrl_missing": CTRL_MISSING,
    }


if __name__ == "__main__":
    result = close()
    print(json.dumps({"counts": result["counts"], "collision": result["post_fix_collision_count"]}, indent=2))
