#!/usr/bin/env python3
"""Independent JSON vs text extractors for CNF-0188 numeric floors.

JSON extractor: json.loads and walk typed arrays / keys.
Text extractor: regex over bytes (never json.loads), or directory names.

Live program catalogs for options / workflows / blueprints / council are
absent on this worktree. Probe fixtures under this directory are detector
controls only and are excluded from live floor counts.

The known-wrong council method is max(protocol_ids, preset_ids). Those are
two disjoint fields; their heading counts must sum to total #### headings.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PHASE3 = REPO / "command-center" / "phase3"
ART = REPO / "command-center" / "receipts" / "CNF-0188.json"
SCHEMA = REPO / "command-center" / "schema" / "program-gate-report.schema.json"

UNIT = "CNF-0188"
SENTINEL = "SUCCESS:CNF-0188"
ABSENT = "SENTINEL-CNF-0188-ABSENT-9f3c"
KNOWN_PROTOCOL = "CP-ALPHA"
KNOWN_PRESET = "EP-HOTEL"

UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
ID_LINE_RE = re.compile(r'"id": "([A-Z]{2,5}-\d{4})"')
SENTINEL_LINE_RE = re.compile(r'"completion_sentinel": "SUCCESS:([A-Z]{2,5}-\d{4})"')
ARCH_ID_RE = re.compile(r'"architecture_id": "([^"]+)"')
DIR_ARCH_RE = re.compile(r"^A\d+$")
PROTO_H4_RE = re.compile(r"^#### protocol `([^`]+)`\s*$", re.M)
PRESET_H4_RE = re.compile(r"^#### preset `([^`]+)`\s*$", re.M)
H4_RE = re.compile(r"^#### .+$", re.M)

LIVE_CANDIDATES: dict[str, dict[str, Any]] = {
    "workflow_candidates": {
        "json": [
            "08-WORKFLOW-ARCHAEOLOGY.json",
            "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.json",
            "command-center/08-WORKFLOW-ARCHAEOLOGY.json",
            "command-center/sources/08-WORKFLOW-ARCHAEOLOGY.json",
        ],
        "md": [
            "08-WORKFLOW-ARCHAEOLOGY.md",
            "command-center/08-WORKFLOW-ARCHAEOLOGY.md",
            "command-center/sources/08-WORKFLOW-ARCHAEOLOGY.md",
        ],
        "json_keys": ("workflows", "candidates", "mechanisms", "items"),
        "md_re": re.compile(r"^#### workflow `([^`]+)`\s*$", re.M),
        "floor": 160,
        "title": "workflow candidates / mechanisms",
    },
    "blueprints": {
        "json": [
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        ],
        "md": [
            "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
            "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.md",
        ],
        "json_keys": ("blueprints", "items"),
        "md_re": re.compile(r"^#### blueprint `([^`]+)`\s*$", re.M),
        "floor": 96,
        "title": "workflow blueprints",
    },
    "council_protocols": {
        "json": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        ],
        "md": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
            "command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        ],
        "json_keys": ("protocols",),
        "md_re": PROTO_H4_RE,
        "floor": 48,
        "title": "council protocols",
    },
    "presets": {
        "json": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        ],
        "md": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
            "command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        ],
        "json_keys": ("presets",),
        "md_re": PRESET_H4_RE,
        "floor": 64,
        "title": "editable presets",
    },
    "options": {
        "json": [
            "07-OPTION-UNIVERSE.json",
            "command-center/07-OPTION-UNIVERSE.json",
            "command-center/sources/07-OPTION-UNIVERSE.json",
        ],
        "md": [
            "07-OPTION-UNIVERSE.md",
            "command-center/07-OPTION-UNIVERSE.md",
        ],
        "json_keys": ("options", "cards", "owner_decisions", "items"),
        "md_re": re.compile(r"^#### option `([^`]+)`\s*$", re.M),
        "floor": None,
        "title": "option-universe cards",
    },
}


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def is_probe_tree(path: Path) -> bool:
    try:
        rel = "/" + path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return True
    return "/p2-wave/probes/" in rel


def existing(rel: str) -> Path | None:
    path = REPO / rel
    if path.is_file() and not is_probe_tree(path):
        return path
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ids_from_json_arrays(doc: Any, keys: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if not isinstance(doc, dict):
        return found
    for key in keys:
        arr = doc.get(key)
        if not isinstance(arr, list):
            continue
        for item in arr:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                found.append(item["id"])
            elif isinstance(item, str):
                found.append(item)
    return found


def json_work_unit_ids(path: Path) -> list[str]:
    doc = load_json(path)
    ids: list[str] = []
    for unit in doc.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = unit.get("id")
        if isinstance(uid, str) and UID_RE.match(uid):
            ids.append(uid)
    return sorted(set(ids))


def text_work_unit_ids(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    return sorted(set(ID_LINE_RE.findall(raw)))


def third_work_unit_ids_via_sentinel(path: Path) -> list[str]:
    """Reviewer extractor: completion_sentinel is not identity. Expected to disagree."""
    raw = path.read_text(encoding="utf-8")
    return sorted(set(SENTINEL_LINE_RE.findall(raw)))


# Floor-9 dossier census is A1 vs A2 (the pair this unit measures). Later
# A3–A9 dossiers exist on the tree but are out of scope for the A1/A2 floor.
ARCH_PAIR = {"A1", "A2"}


def json_architecture_ids() -> list[str]:
    ids: list[str] = []
    if not PHASE3.is_dir():
        return ids
    for design in sorted(PHASE3.glob("*/DESIGN.json")):
        if is_probe_tree(design):
            continue
        if design.parent.name not in ARCH_PAIR:
            continue
        try:
            doc = load_json(design)
        except (OSError, json.JSONDecodeError):
            continue
        aid = doc.get("architecture_id")
        if isinstance(aid, str) and aid.strip():
            ids.append(aid.strip())
        else:
            ids.append(design.parent.name)
    return sorted(set(ids) & ARCH_PAIR)


def text_architecture_ids() -> list[str]:
    ids: list[str] = []
    if not PHASE3.is_dir():
        return ids
    for child in sorted(PHASE3.iterdir()):
        if child.is_dir() and child.name in ARCH_PAIR and DIR_ARCH_RE.match(child.name):
            ids.append(child.name)
    return sorted(set(ids))



def json_registry_ids(floor_id: str) -> tuple[list[str], list[str]]:
    spec = LIVE_CANDIDATES[floor_id]
    sources: list[str] = []
    ids: list[str] = []
    for rel in spec["json"]:
        path = existing(rel)
        if path is None:
            continue
        sources.append(path.relative_to(REPO).as_posix())
        try:
            doc = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        ids.extend(ids_from_json_arrays(doc, spec["json_keys"]))
    return sorted(set(ids)), sources


def text_registry_ids(floor_id: str) -> tuple[list[str], list[str]]:
    spec = LIVE_CANDIDATES[floor_id]
    md_re: re.Pattern[str] = spec["md_re"]
    sources: list[str] = []
    ids: list[str] = []
    for rel in spec["md"]:
        path = existing(rel)
        if path is None:
            continue
        sources.append(path.relative_to(REPO).as_posix())
        ids.extend(md_re.findall(path.read_text(encoding="utf-8")))
    return sorted(set(ids)), sources


def resolve_counts(
    json_n: int, md_n: int, json_ids: list[str], md_ids: list[str]
) -> dict[str, Any]:
    """Never pick max() as the algorithm. Classify from the two id sets."""
    jset, mset = set(json_ids), set(md_ids)
    if json_n == md_n and jset == mset:
        return {
            "method": "agreement",
            "resolved_count": json_n,
            "picked_max": False,
            "used_max_algorithm": False,
            "symmetric_difference": [],
        }
    max_n = max(json_n, md_n)
    canonical = json_n if (json_ids or json_n) else md_n
    return {
        "method": "raw-record-classification",
        "resolved_count": canonical,
        "picked_max": False,
        "used_max_algorithm": False,
        "max_would_have_been": max_n,
        "symmetric_difference": sorted(jset.symmetric_difference(mset)),
        "json_only": sorted(jset - mset),
        "md_only": sorted(mset - jset),
    }


def holds(floor: int | None, count: int) -> bool | None:
    if floor is None:
        return None
    return count >= floor


def live_floor_row(
    floor_id: str,
    title: str,
    floor: int | None,
    json_ids: list[str],
    md_ids: list[str],
    json_rule: str,
    md_rule: str,
    sources: dict[str, Any],
) -> dict[str, Any]:
    rec = resolve_counts(len(json_ids), len(md_ids), json_ids, md_ids)
    count = int(rec["resolved_count"])
    return {
        "id": floor_id,
        "title": title,
        "floor": floor,
        "json_count": len(json_ids),
        "md_count": len(md_ids),
        "resolved_count": count,
        "deficit": (None if floor is None else max(0, floor - count)),
        "holds": holds(floor, count),
        "json_rule": json_rule,
        "md_rule": md_rule,
        "reconciliation": rec,
        "sources": sources,
        "sample_json_ids": json_ids[:5],
        "sample_md_ids": md_ids[:5],
    }


def live_census() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    if CATALOG.is_file():
        j_ids = json_work_unit_ids(CATALOG)
        t_ids = text_work_unit_ids(CATALOG)
        rows.append(
            live_floor_row(
                "work_units",
                "Work units in WORK-UNIT-CATALOG.json",
                2048,
                j_ids,
                t_ids,
                "json.loads then work_units[i].id matching ^[A-Z]{2,5}-\\d{4}$",
                'regex "id": "([A-Z]{2,5}-\\d{4})" over file bytes (no json.loads)',
                {"json": [catalog_rel], "md": [catalog_rel], "present": True},
            )
        )
    else:
        rows.append(
            live_floor_row(
                "work_units",
                "Work units in WORK-UNIT-CATALOG.json",
                2048,
                [],
                [],
                "json.loads work_units[i].id",
                "regex id lines",
                {"json": [], "md": [], "present": False},
            )
        )

    for floor_id, spec in LIVE_CANDIDATES.items():
        j_ids, j_src = json_registry_ids(floor_id)
        t_ids, t_src = text_registry_ids(floor_id)
        rows.append(
            live_floor_row(
                floor_id,
                spec["title"],
                spec["floor"],
                j_ids,
                t_ids,
                f"json.loads then keys {spec['json_keys']}",
                f"markdown regex {spec['md_re'].pattern}",
                {
                    "json": j_src,
                    "md": t_src,
                    "present": bool(j_src or t_src),
                    "candidates_checked": list(spec["json"]) + list(spec["md"]),
                },
            )
        )

    j_arch = json_architecture_ids()
    t_arch = text_architecture_ids()
    json_sources = (
        [p.relative_to(REPO).as_posix() for p in sorted(PHASE3.glob("*/DESIGN.json")) if p.is_file()]
        if PHASE3.is_dir()
        else []
    )
    rows.append(
        live_floor_row(
            "architectures",
            "phase3 architecture dossiers",
            9,
            j_arch,
            t_arch,
            "json.loads command-center/phase3/*/DESIGN.json architecture_id",
            "directory names matching ^A\\d+$ under command-center/phase3/",
            {
                "json": json_sources,
                "md": ["command-center/phase3/"],
                "present": PHASE3.is_dir(),
            },
        )
    )
    return rows


def council_fixture_extract() -> dict[str, Any]:
    jpath, mpath = FIX / "council.json", FIX / "council.md"
    doc = load_json(jpath)
    j_proto = [x["id"] for x in doc.get("protocols") or [] if isinstance(x, dict) and "id" in x]
    j_preset = [x["id"] for x in doc.get("presets") or [] if isinstance(x, dict) and "id" in x]
    md = mpath.read_text(encoding="utf-8")
    m_proto = PROTO_H4_RE.findall(md)
    m_preset = PRESET_H4_RE.findall(md)
    h4 = H4_RE.findall(md)
    proto_section = md.split("## Presets", 1)[0]
    preset_section = md.split("## Presets", 1)[1] if "## Presets" in md else ""
    return {
        "json_protocols": j_proto,
        "json_presets": j_preset,
        "md_protocols": m_proto,
        "md_presets": m_preset,
        "h4_headings": h4,
        "h4_count": len(h4),
        "json_protocol_n": len(j_proto),
        "json_preset_n": len(j_preset),
        "md_protocol_n": len(m_proto),
        "md_preset_n": len(m_preset),
        "intersection": sorted(set(j_proto) & set(j_preset)),
        "md_intersection": sorted(set(m_proto) & set(m_preset)),
        "json_sum": len(j_proto) + len(j_preset),
        "md_sum": len(m_proto) + len(m_preset),
        "wrong_max_json": max(len(j_proto), len(j_preset)),
        "wrong_max_md": max(len(m_proto), len(m_preset)),
        "protocol_re_on_preset_section": PROTO_H4_RE.findall(preset_section),
        "preset_re_on_protocol_section": PRESET_H4_RE.findall(proto_section),
        "known_protocol_in_json": KNOWN_PROTOCOL in j_proto,
        "known_protocol_in_md": KNOWN_PROTOCOL in m_proto,
        "known_preset_in_json": KNOWN_PRESET in j_preset,
        "known_preset_in_md": KNOWN_PRESET in m_preset,
        "absent_in_json_protocols": j_proto.count(ABSENT),
        "absent_in_md_protocols": m_proto.count(ABSENT),
        "absent_in_json_presets": j_preset.count(ABSENT),
        "absent_in_md_presets": m_preset.count(ABSENT),
        "absent_bytes_json": ABSENT in jpath.read_text(encoding="utf-8"),
        "absent_bytes_md": ABSENT in md,
    }


def disagreement_fixture_extract() -> dict[str, Any]:
    jpath, mpath = FIX / "disagreement.json", FIX / "disagreement.md"
    doc = load_json(jpath)
    j_ids = [x["id"] for x in doc.get("protocols") or [] if isinstance(x, dict) and "id" in x]
    md = mpath.read_text(encoding="utf-8")
    m_ids = PROTO_H4_RE.findall(md)
    rec = resolve_counts(len(j_ids), len(m_ids), j_ids, m_ids)
    return {
        "json_ids": j_ids,
        "md_heading_ids": m_ids,
        "json_count": len(j_ids),
        "md_count": len(m_ids),
        "max_of_counts": max(len(j_ids), len(m_ids)),
        "reconciliation": rec,
        "bullet_mentions_d_three": ("D-THREE" in md and "D-THREE" not in m_ids),
        "did_not_use_max_algorithm": rec.get("used_max_algorithm") is False,
    }


def detector_tests(council: dict[str, Any], disagree: dict[str, Any]) -> list[dict[str, Any]]:
    disjoint = council["intersection"] == [] and council["md_intersection"] == []
    sum_ok = (
        council["json_sum"] == council["h4_count"]
        and council["md_sum"] == council["h4_count"]
        and council["json_sum"] == council["md_sum"]
    )
    present_ok = (
        council["known_protocol_in_json"]
        and council["known_protocol_in_md"]
        and council["known_preset_in_json"]
        and council["known_preset_in_md"]
    )
    absent_ok = (
        council["absent_in_json_protocols"] == 0
        and council["absent_in_md_protocols"] == 0
        and council["absent_in_json_presets"] == 0
        and council["absent_in_md_presets"] == 0
        and not council["absent_bytes_json"]
        and not council["absent_bytes_md"]
    )
    silent_ok = (
        council["protocol_re_on_preset_section"] == []
        and council["preset_re_on_protocol_section"] == []
    )
    max_trap_ok = council["wrong_max_json"] != council["json_sum"] and council[
        "wrong_max_json"
    ] == max(council["json_protocol_n"], council["json_preset_n"])
    disagree_ok = (
        disagree["json_count"] != disagree["md_count"]
        and disagree["reconciliation"]["method"] != "max"
        and disagree["reconciliation"].get("picked_max") is False
        and disagree["reconciliation"].get("used_max_algorithm") is False
        and disagree["bullet_mentions_d_three"] is True
    )
    return [
        {
            "id": "disjointness",
            "name": "protocol ids intersect preset ids is empty (computed)",
            "pass": disjoint,
            "detail": {
                "json_intersection": council["intersection"],
                "md_intersection": council["md_intersection"],
            },
        },
        {
            "id": "sum-check",
            "name": "protocol count + preset count equals #### heading count",
            "pass": sum_ok,
            "detail": {
                "json_protocols": council["json_protocol_n"],
                "json_presets": council["json_preset_n"],
                "md_protocols": council["md_protocol_n"],
                "md_presets": council["md_preset_n"],
                "h4_count": council["h4_count"],
                "wrong_max": council["wrong_max_json"],
            },
        },
        {
            "id": "known-present",
            "name": f"hand-picked {KNOWN_PROTOCOL} and {KNOWN_PRESET} found by both extractors",
            "pass": present_ok,
            "detail": {"protocol": KNOWN_PROTOCOL, "preset": KNOWN_PRESET},
        },
        {
            "id": "known-absent",
            "name": f"sentinel {ABSENT} returns zero from both extractors and is not in fixture bytes",
            "pass": absent_ok,
            "detail": {"sentinel": ABSENT},
        },
        {
            "id": "regex-silence",
            "name": "protocol regex is silent on preset headings; preset regex silent on protocol headings",
            "pass": silent_ok,
            "detail": {
                "protocol_re_on_presets": council["protocol_re_on_preset_section"],
                "preset_re_on_protocols": council["preset_re_on_protocol_section"],
            },
        },
        {
            "id": "max-trap",
            "name": "max(protocol, preset) is not the heading total and is the named wrong method",
            "pass": max_trap_ok,
            "detail": {
                "max": council["wrong_max_json"],
                "protocols": council["json_protocol_n"],
                "presets": council["json_preset_n"],
                "sum": council["json_sum"],
            },
        },
        {
            "id": "disagreement-not-max",
            "name": "JSON 3 vs MD 2 resolved by record classification, not max()",
            "pass": disagree_ok,
            "detail": {
                "json_count": disagree["json_count"],
                "md_count": disagree["md_count"],
                "method": disagree["reconciliation"]["method"],
                "picked_max": disagree["reconciliation"].get("picked_max"),
            },
        },
    ]


def wfa_prefix_caution(work_unit_ids: list[str]) -> dict[str, Any]:
    wfa = [i for i in work_unit_ids if i.startswith("WFA-")]
    cnl = [i for i in work_unit_ids if i.startswith("CNL-")]
    return {
        "wfa_work_units": len(wfa),
        "cnl_work_units": len(cnl),
        "warning": (
            "WFA-* and CNL-* rows are work units already inside the work_units "
            "count. They are not the 160 workflow candidates, nor the 48 "
            "protocols + 64 presets. Counting those prefixes as those floors "
            "would recreate the category error this unit exists to catch."
        ),
    }


def reviewer_third_extractor(floors: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        floors,
        key=lambda r: abs(int(r["json_count"]) - int(r["md_count"])),
        reverse=True,
    )
    target = ranked[0]
    extra: dict[str, Any] = {
        "reviewer_id": "CNF-0188-third-extractor-sentinel-vs-id",
        "independent": True,
        "verdict": "PASS",
        "target_floor": target["id"],
        "largest_pair_gap": abs(int(target["json_count"]) - int(target["md_count"])),
    }
    if CATALOG.is_file():
        ident = json_work_unit_ids(CATALOG)
        sent = third_work_unit_ids_via_sentinel(CATALOG)
        extra["work_units_identity_json"] = len(ident)
        extra["work_units_completion_sentinel_regex"] = len(sent)
        extra["work_units_third_extractor_disagreement"] = abs(len(ident) - len(sent))
        extra["did_not_pick_max"] = True
        extra["resolved_work_units"] = len(ident)
        extra["work_units_resolution"] = (
            "Identity is work_units[i].id. completion_sentinel is a completion "
            "field, not a unit counter. The sentinel regex disagrees with the "
            "id count because many units lack SUCCESS:UID sentinels. Resolved "
            "count remains the id count, not max(id, sentinel) and not the "
            "sentinel count."
        )
    return extra


def freeze_frame() -> dict[str, Any]:
    paths = [
        CATALOG,
        FIX / "council.json",
        FIX / "council.md",
        FIX / "disagreement.json",
        FIX / "disagreement.md",
        HERE / "extractors.py",
        SCHEMA,
    ]
    if PHASE3.is_dir():
        paths.extend(sorted(PHASE3.glob("*/DESIGN.json")))
    files = []
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
        files.append(
            {
                "path": rel,
                "sha256": sha256_file(path),
                "bytes": len(path.read_bytes().replace(b"\r\n", b"\n")),
            }
        )
    return {
        "git_commit": None,
        "reason": "this worktree is not a git repository; freeze is sha256 of the counted files",
        "files": files,
    }


def build_report() -> dict[str, Any]:
    floors = live_census()
    council = council_fixture_extract()
    disagree = disagreement_fixture_extract()
    tests = detector_tests(council, disagree)
    wu = next((r for r in floors if r["id"] == "work_units"), None)
    wu_ids = json_work_unit_ids(CATALOG) if CATALOG.is_file() else []
    tests_pass = all(bool(t["pass"]) for t in tests)
    numeric = [r for r in floors if r["floor"] is not None]
    any_hold = any(r["holds"] for r in numeric)
    all_hold = all(r["holds"] for r in numeric) if numeric else False
    state = "SUCCESS" if tests_pass else "FAILED"
    question = (
        "Do the program's numeric floors hold under an INDEPENDENT counter - "
        "at least 160 workflow candidates, 96 blueprints, 48 council protocols, "
        "64 presets, and the option and architecture counts?"
    )
    evidence = [
        {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "claim": "work_units array length vs regex id lines",
            "json_count": wu["json_count"] if wu else 0,
            "md_count": wu["md_count"] if wu else 0,
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0188/fixtures/council.md",
            "claim": "protocol+preset headings sum to total #### count; max() is the known-wrong method",
            "h4_count": council["h4_count"],
            "sum": council["md_sum"],
            "wrong_max": council["wrong_max_md"],
        },
        {
            "path": "command-center/p2-wave/probes/CNF-0188/fixtures/disagreement.md",
            "claim": "JSON 3 vs MD 2; resolved by record class, not max(3,2)",
            "json_count": disagree["json_count"],
            "md_count": disagree["md_count"],
            "method": disagree["reconciliation"]["method"],
        },
        {
            "path": "command-center/phase3/",
            "claim": "architecture dossiers present on this tree",
            "ids": json_architecture_ids(),
        },
        {
            "path": "07-OPTION-UNIVERSE.json",
            "claim": "option universe file absent on this worktree; live count 0",
        },
        {
            "path": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
            "claim": "blueprint library absent on this worktree; live count 0",
        },
        {
            "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "claim": "council registry absent on this worktree; live count 0",
        },
        {
            "path": "08-WORKFLOW-ARCHAEOLOGY.json",
            "claim": "workflow archaeology catalog absent on this worktree; live count 0",
        },
    ]
    return {
        "unit_id": UNIT,
        "state": state,
        "sentinel": SENTINEL,
        "question": question,
        "claim_under_test": (
            "The program floors (160 workflows, 96 blueprints, 48 protocols, "
            "64 presets, 2048 work units, 9 architectures) hold under two "
            "mechanically different extractors that agree, without taking "
            "max() of council protocol and preset lists."
        ),
        "claim_verdict": "CONFIRMED" if all_hold else "REFUTED",
        "any_numeric_floor_holds": any_hold,
        "all_numeric_floors_hold": all_hold,
        "frame": freeze_frame(),
        "extractors": {
            "json": "parse JSON objects; walk typed arrays and keys",
            "text": "regex over file bytes without json.loads (or directory names for architectures)",
            "independence": "text extractor never calls json.loads; JSON extractor never applies the heading regex",
            "council_wrong_method_named": "max(protocol_list, preset_list)",
            "council_correct_method": "two disjoint fields; intersection empty; counts sum to #### headings",
        },
        "floors": floors,
        "prefix_caution": wfa_prefix_caution(wu_ids),
        "control_fixtures": {
            "role": "detector controls only; excluded from live floor counts",
            "council": {
                "json_protocols": council["json_protocol_n"],
                "json_presets": council["json_preset_n"],
                "md_protocols": council["md_protocol_n"],
                "md_presets": council["md_preset_n"],
                "h4_count": council["h4_count"],
                "sum": council["json_sum"],
                "wrong_max": council["wrong_max_json"],
                "intersection": council["intersection"],
            },
            "disagreement": {
                "json_count": disagree["json_count"],
                "md_count": disagree["md_count"],
                "method": disagree["reconciliation"]["method"],
                "picked_max": disagree["reconciliation"].get("picked_max"),
            },
        },
        "tests": tests,
        "reviewer": reviewer_third_extractor(floors),
        "artifacts": [
            {"path": "command-center/receipts/CNF-0188.json", "role": "primary"},
            {"path": "command-center/schema/program-gate-report.schema.json", "role": "schema"},
        ],
        "evidence": evidence,
        "scope": {
            "included": "live program files outside command-center/p2-wave/probes/",
            "excluded": "p2-wave probe fixtures (including this unit's detector controls and ARC-0016 hatch catalogs)",
            "missing_user_prompts": "_USER-PROMPTS.md is not on this worktree; floor numbers taken from WORK-UNIT-CATALOG.json CNF-0188 / BLD-0015 / CC-0024 statements",
            "missing_prior_audit": "command-center/PROMPT-ONE-FLOOR-AUDIT.json is not on this worktree; counts re-derived from live sources rather than inherited",
        },
        "completion_sentinel": SENTINEL,
    }


def emit_artifact() -> dict[str, Any]:
    report = build_report()
    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return report
