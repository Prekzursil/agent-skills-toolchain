#!/usr/bin/env python3
"""WFA-0003 id-namespace auditor.

Signal A and signal B are separate code paths:
  A - regex token extraction + set intersection (no title lookup)
  B - reverse id->title maps from JSON id fields / markdown headings
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent

# Prefix-number (M-16, MECH-12, BP-001, MAP-001) plus kebab workflow ids.
PREFIX_NUM_RE = re.compile(r"\b([A-Z]{1,8})-(\d{1,4})\b")
WF_RE = re.compile(r"\b(wf-[a-z0-9]+(?:-[a-z0-9]+)*)\b")
HEADING_RE = re.compile(
    r"^#{1,3}\s+((?:MECH|M|BP|MAP|wf)-[A-Za-z0-9-]+)\s+(.*)$",
    re.MULTILINE,
)
JSON_ID_RE = re.compile(
    r'"id"\s*:\s*"(?P<id>(?:[A-Z]{1,8}-\d{1,4}|wf-[a-z0-9]+(?:-[a-z0-9]+)*|BP-\d{3}))"'
)

PLANT_TOKEN = "SYN-99"
PLANT_TITLE_A = "Planted collision record A"
PLANT_TITLE_B = "Planted collision record B"
ABSENT_CLASS = ("M-12", "M-16", "M-17", "M-19", "M-28", "M-30", "M-38")


def canonical_prefix_num(prefix: str, number: str) -> str:
    # Keep the matched spelling (BP-001 vs BP-1). Do not int()-collapse zeros.
    return f"{prefix.upper()}-{number}"


def extract_tokens_regex(text: str) -> set[str]:
    """Signal A extractor: regex only. Does not read titles."""
    found: set[str] = set()
    for prefix, number in PREFIX_NUM_RE.findall(text):
        found.add(canonical_prefix_num(prefix, number))
    found.update(WF_RE.findall(text))
    return found


def artifact_token_sets(paths: dict[str, Path]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for name, path in paths.items():
        text = path.read_text(encoding="utf-8")
        out[name] = extract_tokens_regex(text)
    return out


def intersecting_tokens(sets: dict[str, set[str]]) -> dict[str, list[str]]:
    """Tokens that appear in two or more artifacts, with the artifact names."""
    inverted: dict[str, list[str]] = defaultdict(list)
    for name, tokens in sets.items():
        for tok in tokens:
            inverted[tok].append(name)
    return {
        tok: sorted(names)
        for tok, names in inverted.items()
        if len(names) >= 2
    }


def _title_from_obj(obj: dict) -> str:
    for key in ("title", "name", "does"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    notes = obj.get("notes")
    if isinstance(notes, str) and notes.strip():
        return notes.strip()
    return ""


def _walk_json_records(node, sink: dict[str, list[dict]], source: str) -> None:
    if isinstance(node, dict):
        cid = node.get("id")
        if isinstance(cid, str) and cid:
            sink[cid].append(
                {
                    "id": cid,
                    "title": _title_from_obj(node) or cid,
                    "source": source,
                    "kind": "json-id",
                }
            )
        for val in node.values():
            _walk_json_records(val, sink, source)
    elif isinstance(node, list):
        for item in node:
            _walk_json_records(item, sink, source)


def title_map_from_text(text: str, source: str) -> dict[str, list[dict]]:
    """Signal B extractor: headings + JSON id objects. Independent of set intersection."""
    sink: dict[str, list[dict]] = defaultdict(list)
    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            doc = None
        if doc is not None:
            _walk_json_records(doc, sink, source)
    for match in HEADING_RE.finditer(text):
        cid = match.group(1)
        title = match.group(2).strip()
        if re.match(r"^(?:MECH|M|BP|MAP|SYN)-", cid):
            prefix, _, rest = cid.partition("-")
            if rest.isdigit() or re.fullmatch(r"\d+", rest):
                cid = canonical_prefix_num(prefix, rest)
        sink[cid].append(
            {
                "id": cid,
                "title": title or cid,
                "source": source,
                "kind": "heading",
            }
        )
    return dict(sink)


def merge_title_maps(maps: Iterable[dict[str, list[dict]]]) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = defaultdict(list)
    for amap in maps:
        for cid, rows in amap.items():
            merged[cid].extend(rows)
    return dict(merged)


def unique_records(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = (row.get("source"), row.get("id"), row.get("title"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def classify_token(token: str, records: list[dict], cited_in: list[str]) -> dict:
    recs = unique_records(records)
    titles = sorted({r["title"] for r in recs})
    sources = sorted({r["source"] for r in recs})
    if len(recs) == 0:
        kind = "ABSENT"
    elif len(recs) == 1:
        kind = "CITATION-ONLY" if len(cited_in) >= 2 else "RESOLVES-ONE"
    elif len(titles) == 1:
        kind = "SAME-TITLE-COINCIDENCE"
    else:
        kind = "SEMANTIC-CLASH"
    return {
        "token": token,
        "kind": kind,
        "record_count": len(recs),
        "titles": titles,
        "sources": sources,
        "cited_in": sorted(cited_in),
        "records": recs,
        "identical_titles": len(titles) == 1 and len(recs) >= 2,
    }


def reverse_lookup(
    colliding: dict[str, list[str]],
    title_maps: dict[str, dict[str, list[dict]]],
) -> list[dict]:
    """Signal B: for each intersecting token, print both resolved titles."""
    merged = merge_title_maps(title_maps.values())
    rows = []
    for token, artifacts in sorted(colliding.items()):
        recs = merged.get(token) or []
        rows.append(classify_token(token, recs, artifacts))
    return rows


def declarations_by_prefix(title_maps: dict[str, dict[str, list[dict]]]) -> dict[str, list[str]]:
    prefix_sources: dict[str, set[str]] = defaultdict(set)
    for source, amap in title_maps.items():
        for cid in amap:
            if cid.startswith("wf-"):
                prefix = "wf"
            else:
                prefix = cid.split("-", 1)[0]
            prefix_sources[prefix].add(source)
    return {p: sorted(s) for p, s in sorted(prefix_sources.items())}


def colliding_prefixes(prefix_sources: dict[str, list[str]]) -> dict[str, list[str]]:
    return {p: srcs for p, srcs in prefix_sources.items() if len(srcs) >= 2}


def resolve_against(token: str, title_map: dict[str, list[dict]]) -> str:
    recs = title_map.get(token) or []
    return "PRESENT" if recs else "ABSENT"


def plant_pair() -> tuple[dict, dict]:
    return (
        {"id": PLANT_TOKEN, "title": PLANT_TITLE_A},
        {"id": PLANT_TOKEN, "title": PLANT_TITLE_B},
    )


def inject_planted_collision(text_a: str, text_b: str) -> tuple[str, str]:
    a, b = plant_pair()
    needle = '"candidates"'
    if needle in text_a:
        text_a = text_a.replace(
            '"candidates": [',
            '"candidates": [\n    ' + json.dumps(a) + ",",
            1,
        )
    else:
        text_a = text_a + "\n" + json.dumps({"id": a["id"], "title": a["title"]})
    if '"blueprints"' in text_b:
        text_b = text_b.replace(
            '"blueprints": [',
            '"blueprints": [\n    ' + json.dumps(b) + ",",
            1,
        )
    else:
        text_b = text_b + "\n" + json.dumps({"id": b["id"], "title": b["title"]})
    return text_a, text_b


def decision_log_facts(text: str) -> dict:
    lines = text.splitlines()
    line_175 = lines[174] if len(lines) >= 175 else ""
    mech_count = len(re.findall(r"\bMECH-\d+\b", text))
    present_tense = (
        "still live" in line_175.lower()
        or "is still live" in line_175.lower()
        or "queued as p2-09" in line_175.lower()
    )
    return {
        "line_count": len(lines),
        "line_175": line_175,
        "mech_token_count": mech_count,
        "present_tense_collision_claim": present_tense,
        "zero_mech_tokens": mech_count == 0,
    }


def run_signal_a(paths: dict[str, Path]) -> dict:
    sets = artifact_token_sets(paths)
    colliding = intersecting_tokens(sets)
    return {
        "token_regex": r"\\b([A-Z]{1,8})-(\\d{1,4})\\b | \\b(wf-[a-z0-9]+(?:-[a-z0-9]+)*)\\b",
        "per_artifact_counts": {k: len(v) for k, v in sorted(sets.items())},
        "per_artifact_tokens": {k: sorted(v) for k, v in sorted(sets.items())},
        "intersecting": colliding,
        "intersecting_count": len(colliding),
        "intersecting_tokens": sorted(colliding),
    }


def run_signal_b(paths: dict[str, Path], colliding: dict[str, list[str]]) -> dict:
    maps = {
        name: title_map_from_text(path.read_text(encoding="utf-8"), name)
        for name, path in paths.items()
    }
    classified = reverse_lookup(colliding, maps)
    clashes = [r for r in classified if r["kind"] == "SEMANTIC-CLASH"]
    same = [r for r in classified if r["kind"] == "SAME-TITLE-COINCIDENCE"]
    citation = [r for r in classified if r["kind"] == "CITATION-ONLY"]
    absent = [r for r in classified if r["kind"] == "ABSENT"]
    prefixes = declarations_by_prefix(maps)
    return {
        "classified": classified,
        "semantic_clash_count": len(clashes),
        "semantic_clash_tokens": [r["token"] for r in clashes],
        "same_title_count": len(same),
        "citation_only_count": len(citation),
        "absent_from_intersection_count": len(absent),
        "identical_titles_among_clashes": sum(1 for r in clashes if r["identical_titles"]),
        "prefix_declaration_sources": prefixes,
        "colliding_declaration_prefixes": colliding_prefixes(prefixes),
        "title_maps_record_counts": {k: len(v) for k, v in sorted(maps.items())},
    }


def historical_mnn_control(estate: Path) -> dict:
    """Pre-fix architecture uses M-; option universe uses M-. Independent title maps."""
    opt = estate / "07-OPTION-UNIVERSE.json"
    arch = estate / "13-ARCHITECTURE-CANDIDATES.pre-fix.md"
    opt_text = opt.read_text(encoding="utf-8")
    arch_text = arch.read_text(encoding="utf-8")
    # Signal A on the pair only.
    sets = {
        "07-OPTION-UNIVERSE.json": extract_tokens_regex(opt_text),
        "13-ARCHITECTURE-CANDIDATES.pre-fix.md": extract_tokens_regex(arch_text),
    }
    colliding = intersecting_tokens(sets)
    maps = {
        "07-OPTION-UNIVERSE.json": title_map_from_text(opt_text, "07-OPTION-UNIVERSE.json"),
        "13-ARCHITECTURE-CANDIDATES.pre-fix.md": title_map_from_text(
            arch_text, "13-ARCHITECTURE-CANDIDATES.pre-fix.md"
        ),
    }
    classified = reverse_lookup(colliding, maps)
    clashes = [r for r in classified if r["kind"] == "SEMANTIC-CLASH"]
    identical = [r for r in clashes if r["identical_titles"]]
    slice_31 = [r for r in clashes if r["token"].startswith("M-") and _m_number(r["token"]) <= 31]
    identical_31 = [r for r in slice_31 if r["identical_titles"]]
    return {
        "intersecting_count": len(colliding),
        "semantic_clash_count": len(clashes),
        "identical_title_count": len(identical),
        "zero_identical_titles": len(identical) == 0 and len(clashes) > 0,
        "published_control_slice": {
            "n": 31,
            "clash_count": len(slice_31),
            "identical_title_count": len(identical_31),
            "zero_of_31_identical_titles": len(slice_31) == 31 and len(identical_31) == 0,
        },
        "clashes": [
            {
                "token": r["token"],
                "titles": r["titles"],
                "sources": r["sources"],
            }
            for r in clashes
        ],
    }


def _m_number(token: str) -> int:
    try:
        return int(token.split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def absent_class_resolution(estate: Path) -> list[dict]:
    arch = (estate / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
    amap = title_map_from_text(arch, "13-ARCHITECTURE-CANDIDATES.md")
    rows = []
    for token in ABSENT_CLASS:
        mech = "MECH-" + token.split("-", 1)[1]
        rows.append(
            {
                "token": token,
                "resolve_bare_m_in_doc13": resolve_against(token, amap),
                "resolve_mech_in_doc13": resolve_against(mech, amap),
                "class": "doc-13-bare-M-ABSENT",
            }
        )
    return rows


def planted_detector_control(estate: Path) -> dict:
    cand = (estate / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text(encoding="utf-8")
    blue = (estate / "09-WORKFLOW-BLUEPRINT-LIBRARY.json").read_text(encoding="utf-8")
    planted_a, planted_b = inject_planted_collision(cand, blue)
    sets = {
        "08-WORKFLOW-CANDIDATE-REGISTRY.json": extract_tokens_regex(planted_a),
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": extract_tokens_regex(planted_b),
    }
    colliding = intersecting_tokens(sets)
    maps = {
        "08-WORKFLOW-CANDIDATE-REGISTRY.json": title_map_from_text(
            planted_a, "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json": title_map_from_text(
            planted_b, "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
        ),
    }
    classified = reverse_lookup({PLANT_TOKEN: colliding.get(PLANT_TOKEN, [])}, maps)
    row = classified[0] if classified else {}
    return {
        "planted_token": PLANT_TOKEN,
        "intersection_reported": PLANT_TOKEN in colliding,
        "kind": row.get("kind"),
        "titles": row.get("titles"),
        "pass": (
            PLANT_TOKEN in colliding
            and row.get("kind") == "SEMANTIC-CLASH"
            and set(row.get("titles") or []) == {PLANT_TITLE_A, PLANT_TITLE_B}
        ),
    }
