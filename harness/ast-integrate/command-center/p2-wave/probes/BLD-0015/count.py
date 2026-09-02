#!/usr/bin/env python3
"""BLD-0015 counting rules: JSON-path vs text/markdown extractors, anti-padding.

Identity for blueprints/ideas/workflows is a body fingerprint, so a renamed
duplicate does not increment the floor. Protocol and preset floors count ids
and must be disjoint. Markdown vs JSON must agree as SETS, not merely sizes.
Taking max(protocols, presets) is the known wrong answer; the fields sum.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
H4_ID_RE = re.compile(r"^####\s+(\S+)\s*$")
H2_RE = re.compile(r"^##\s+(Protocols|Presets|Blueprints|Workflows|Architectures|Ideas)\b", re.I)

LIVE_CANDIDATES = {
    "work-units": ["command-center/WORK-UNIT-CATALOG.json"],
    "workflow-candidates": [
        "08-WORKFLOW-ARCHAEOLOGY.json",
        "08-WORKFLOW-ARCHAEOLOGY.md",
        "command-center/sources/08-WORKFLOW-ARCHAEOLOGY.json",
        "command-center/sources/08-WORKFLOW-ARCHAEOLOGY.md",
    ],
    "blueprints": [
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
        "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.md",
    ],
    "council": [
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    ],
    "options": [
        "07-OPTION-UNIVERSE.json",
        "07-OPTION-UNIVERSE.md",
        "command-center/sources/07-OPTION-UNIVERSE.json",
    ],
    "architectures-lib": [
        "13-ARCHITECTURE-CANDIDATES.json",
        "13-ARCHITECTURE-CANDIDATES.md",
        "command-center/sources/13-ARCHITECTURE-CANDIDATES.json",
    ],
    "ideas": [
        "command-center/PROMPT-ONE-FLOOR-AUDIT.json",
        "100-UNIQUE-IDEAS.json",
        "command-center/sources/100-UNIQUE-IDEAS.md",
    ],
    "prior-audit": ["command-center/PROMPT-ONE-FLOOR-AUDIT.json"],
}

FLOORS = [
    {
        "id": "work-units",
        "floor_n": 2048,
        "identity": "id",
        "counting_rule_json": "JSON path $.work_units[*].id; unique strings matching ^[A-Z]{2,5}-\\d{4}$",
        "counting_rule_md_or_text": "Streaming raw_decode of the work_units array located by text search; first id per object; same UID regex",
    },
    {
        "id": "workflow-candidates",
        "floor_n": 160,
        "identity": "fingerprint",
        "counting_rule_json": "JSON path $.workflows[*] or $.mechanisms[*]; unique body fingerprints",
        "counting_rule_md_or_text": "Markdown #### ids under ## Workflows; body until next heading; unique fingerprints",
    },
    {
        "id": "blueprints",
        "floor_n": 96,
        "identity": "fingerprint",
        "counting_rule_json": "JSON path $.blueprints[*]; unique sha256(normalize(body)); id/title ignored",
        "counting_rule_md_or_text": "Markdown #### ids under ## Blueprints; unique body fingerprints",
    },
    {
        "id": "flagship-blueprints",
        "floor_n": 40,
        "identity": "fingerprint",
        "counting_rule_json": "JSON path $.blueprints[?flagship==true]; unique body fingerprints",
        "counting_rule_md_or_text": "Markdown blueprints whose block contains 'flagship: true'; unique fingerprints",
    },
    {
        "id": "council-protocols",
        "floor_n": 48,
        "identity": "id",
        "counting_rule_json": "JSON path $.protocols[*].id; a set, never max(len(protocols), len(presets))",
        "counting_rule_md_or_text": "Markdown #### ids under ## Protocols only (not all h4 in the file)",
    },
    {
        "id": "editable-presets",
        "floor_n": 64,
        "identity": "id",
        "counting_rule_json": "JSON path $.presets[*].id; disjoint from $.protocols[*].id",
        "counting_rule_md_or_text": "Markdown #### ids under ## Presets only",
    },
    {
        "id": "architectures",
        "floor_n": 9,
        "identity": "id",
        "counting_rule_json": "JSON path $.architectures[*].id, else architecture_id in command-center/phase3/*/DESIGN.json",
        "counting_rule_md_or_text": "Markdown #### ids under ## Architectures, else same DESIGN.json files via text search",
    },
    {
        "id": "unique-ideas",
        "floor_n": 100,
        "identity": "fingerprint",
        "counting_rule_json": "JSON path $.ideas[*]; unique body fingerprints (reworded copies collapse)",
        "counting_rule_md_or_text": "Markdown #### ids under ## Ideas; unique body fingerprints",
    },
]


def normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b(copy|renamed|duplicate|v2|reword(?:ed|ing)?)\b", " ", t)
    return " ".join(t.split())


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def present(rel: str) -> bool:
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _entries(doc: dict, *keys: str) -> list[dict]:
    for k in keys:
        v = doc.get(k)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    return []


def json_ids_and_prints(entries: Iterable[dict], body_keys: tuple[str, ...] = ("body", "text", "title")) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    prints: list[str] = []
    for e in entries:
        i = str(e.get("id") or e.get("architecture_id") or "").strip()
        if not i:
            continue
        ids.append(i)
        body = ""
        for k in body_keys:
            if e.get(k):
                body = str(e.get(k))
                break
        if not body:
            body = i
        prints.append(fingerprint(body))
    return ids, prints


def parse_md_sections(text: str) -> dict[str, list[dict]]:
    """Split markdown by ## section, then #### id blocks."""
    section = None
    current: dict | None = None
    out: dict[str, list[dict]] = {
        "protocols": [],
        "presets": [],
        "blueprints": [],
        "workflows": [],
        "architectures": [],
        "ideas": [],
    }
    key_map = {
        "protocols": "protocols",
        "presets": "presets",
        "blueprints": "blueprints",
        "workflows": "workflows",
        "architectures": "architectures",
        "ideas": "ideas",
    }
    for line in text.splitlines():
        h2 = H2_RE.match(line)
        if h2:
            if current and section:
                out[section].append(current)
                current = None
            section = key_map[h2.group(1).lower()]
            continue
        h4 = H4_ID_RE.match(line)
        if h4 and section:
            if current:
                out[section].append(current)
            current = {"id": h4.group(1), "body": "", "flagship": False}
            continue
        if current is not None:
            if re.match(r"^flagship:\s*true\s*$", line.strip(), re.I):
                current["flagship"] = True
            else:
                current["body"] += line + "\n"
    if current and section:
        out[section].append(current)
    return out


def h4_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if H4_ID_RE.match(line))


def work_unit_ids_json(catalog: dict) -> list[str]:
    ids = []
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict):
            i = str(u.get("id") or "")
            if UID_RE.match(i):
                ids.append(i)
    return ids


def work_unit_ids_text(raw: str) -> list[str]:
    """Mechanically different: locate the array by text, decode objects one-by-one."""
    m = re.search(r'"work_units"\s*:', raw)
    if not m:
        return []
    i = raw.find("[", m.end())
    if i < 0:
        return []
    dec = json.JSONDecoder()
    n = len(raw)
    i += 1
    ids: list[str] = []
    while i < n:
        while i < n and raw[i] in " \t\r\n,":
            i += 1
        if i >= n or raw[i] == "]":
            break
        obj, end = dec.raw_decode(raw, i)
        if isinstance(obj, dict):
            uid = str(obj.get("id") or "")
            if UID_RE.match(uid):
                ids.append(uid)
        i = end
    return ids


def live_architecture_ids_json() -> list[str]:
    ids: list[str] = []
    phase3 = REPO / "command-center" / "phase3"
    if not phase3.is_dir():
        return ids
    pat = re.compile(r'"architecture_id"\s*:\s*"([^"]+)"')
    for design in sorted(phase3.glob("*/DESIGN.json")):
        aid = ""
        try:
            doc = load_json(design)
            aid = str(doc.get("architecture_id") or "")
        except (OSError, json.JSONDecodeError):
            doc = None
        if not aid:
            try:
                raw = design.read_text(encoding="utf-8")
            except OSError:
                continue
            m = pat.search(raw)
            if m:
                aid = m.group(1)
        if aid:
            ids.append(aid)
    return ids


def live_architecture_ids_text() -> list[str]:
    """Regex extractor: first architecture_id string per DESIGN.json, no json.loads."""
    ids: list[str] = []
    phase3 = REPO / "command-center" / "phase3"
    if not phase3.is_dir():
        return ids
    pat = re.compile(r'"architecture_id"\s*:\s*"([^"]+)"')
    for design in sorted(phase3.glob("*/DESIGN.json")):
        try:
            raw = design.read_text(encoding="utf-8")
        except OSError:
            continue
        m = pat.search(raw)
        if m:
            ids.append(m.group(1))
    return ids


def first_existing(rels: list[str]) -> Path | None:
    for rel in rels:
        p = REPO / rel
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def pair_status(json_rel: str, md_rel: str) -> str:
    j = present(json_rel) if json_rel else False
    m = present(md_rel) if md_rel else False
    if j and m:
        return "PRESENT"
    if j or m:
        return "PARTIAL"
    return "ABSENT"


def unique_in_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def extract_library_json(path: Path) -> dict[str, list[dict]]:
    doc = load_json(path)
    return {
        "protocols": _entries(doc, "protocols"),
        "presets": _entries(doc, "presets"),
        "blueprints": _entries(doc, "blueprints"),
        "workflows": _entries(doc, "workflows", "mechanisms", "candidates"),
        "architectures": _entries(doc, "architectures"),
        "ideas": _entries(doc, "ideas"),
    }


def write_fixtures(dest: Path | None = None) -> Path:
    dest = dest or FIX
    dest.mkdir(parents=True, exist_ok=True)

    blueprints = [
        {
            "id": "bp.catalog-class.discovery-only",
            "title": "Catalog-class discovery only",
            "flagship": True,
            "body": "Discover candidates from a static registry. Do not execute. Stop after the candidate list is written.",
        },
        {
            "id": "bp.catalog-class.discovery-only-renamed",
            "title": "Catalog class discovery-only (renamed copy)",
            "flagship": True,
            "body": "Discover candidates from a static registry. Do not execute. Stop after the candidate list is written.",
        },
        {
            "id": "bp.repair-loop",
            "title": "Repair loop",
            "flagship": True,
            "body": "Repair a broken workflow spec by applying a finite checklist of declared fixers, then halt.",
        },
        {
            "id": "bp.translate-spec",
            "title": "Translate spec",
            "flagship": False,
            "body": "Translate a markdown procedure into a typed JSON workflow without evaluating expressions.",
        },
        {
            "id": "bp.merge-graphs",
            "title": "Merge graphs",
            "flagship": False,
            "body": "Merge two workflow graphs by id union. Collision on the same id is fail-closed, not a silent overlay.",
        },
        {
            "id": "bp.distill-logs",
            "title": "Distill logs",
            "flagship": False,
            "body": "Distill a run log into a static summary record. No live tail, no resident watcher.",
        },
    ]
    workflows = [
        {"id": "mech.import", "body": "Import an external workflow document into the candidate queue."},
        {"id": "mech.repair", "body": "Repair a candidate that fails schema validation."},
        {"id": "mech.translate", "body": "Translate a candidate into the executable blueprint form."},
        {"id": "mech.benchmark", "body": "Benchmark a blueprint against a frozen fixture corpus."},
    ]
    protocols = [
        {"id": "proto.deliberate", "body": "Round-robin deliberation with a recorded dissent column."},
        {"id": "proto.critique", "body": "Adversarial critique pass; every claim needs a counterclaim."},
        {"id": "proto.vote", "body": "Unanimous-or-record-dissent vote. No majority shortcut."},
        {"id": "proto.consensus", "body": "Consensus only after every role has spoken once."},
        {"id": "proto.audit", "body": "Audit pass that cites path:line for every finding."},
        {"id": "proto.stop", "body": "Declarative stop: max_rounds or halt flag. No runtime predicate."},
        {"id": "proto.escalate", "body": "Escalate unresolved dissent to the owner question packet."},
        {"id": "proto.dissent", "body": "Preserve minority dissent as a first-class record, never collapse it."},
    ]
    presets = [
        {"id": "preset.catalog-class.editable", "body": "Four-voice catalog-class preset, owner-editable fields only."},
        {"id": "preset.adversarial", "body": "Skeptic-weighted voice mix for refutation sessions."},
        {"id": "preset.fast-path", "body": "Two-voice fast path: architect plus critic, no pragmatist."},
        {"id": "preset.four-voice", "body": "Architect, Skeptic, Pragmatist, Critic with equal weight."},
        {"id": "preset.skeptic-heavy", "body": "Double skeptic slot; used when the claim is a numeric floor."},
        {"id": "preset.architect-lead", "body": "Architect speaks first and last; others fill the middle."},
        {"id": "preset.pragmatic", "body": "Pragmatist-led preset for implementation-shaped questions."},
        {"id": "preset.critic-last", "body": "Critic always closes; veto recorded if the critic refuses."},
        {"id": "preset.silent-observer", "body": "Observer role records but does not vote."},
        {"id": "preset.owner-override", "body": "Owner override slot; if filled, council output is advisory."},
    ]
    architectures = [
        {"id": "A1", "body": "Config-first minimal static JSON tree, no generated layer."},
        {"id": "A2", "body": "Registry-generated typed hatch with a freeze hook."},
        {"id": "A3", "body": "Hybrid: static declarations plus a forbidden runtime stopper."},
    ]
    ideas = [
        {"id": "idea.static-ssot", "body": "One typed registry is the single source of truth for generated files."},
        {"id": "idea.static-ssot-reword", "body": "One typed registry is the single source of truth for generated files."},
        {"id": "idea.freeze-hook", "body": "A freeze hook rejects live bytes that were not in the last accepted snapshot."},
        {"id": "idea.anti-padding", "body": "Renamed duplicates must not increment a numeric floor."},
        {"id": "idea.two-extractors", "body": "Every floor needs a JSON extractor and a mechanically different text extractor."},
        {"id": "idea.disjoint-council", "body": "Protocol ids and preset ids must intersect to the empty set."},
    ]
    council = {"protocols": protocols, "presets": presets}
    lib = {
        "blueprints": blueprints,
        "workflows": workflows,
        "architectures": architectures,
        "ideas": ideas,
        **council,
    }
    (dest / "library.json").write_text(json.dumps(lib, indent=2) + "\n", encoding="utf-8")
    (dest / "council.json").write_text(json.dumps(council, indent=2) + "\n", encoding="utf-8")

    def md_block(section: str, rows: list[dict], flagship_key: bool = False) -> str:
        lines = [f"## {section}", ""]
        for r in rows:
            lines.append(f"#### {r['id']}")
            if flagship_key and r.get("flagship"):
                lines.append("flagship: true")
            lines.append(r["body"])
            lines.append("")
        return "\n".join(lines)

    md = "\n".join(
        [
            "# BLD-0015 fixture library (md twin of library.json)",
            "",
            md_block("Blueprints", blueprints, True),
            md_block("Workflows", workflows),
            md_block("Protocols", protocols),
            md_block("Presets", presets),
            md_block("Architectures", architectures),
            md_block("Ideas", ideas),
        ]
    )
    (dest / "library.md").write_text(md + "\n", encoding="utf-8")
    council_md = "\n".join(
        [
            "# Council protocols and presets (md twin)",
            "",
            md_block("Protocols", protocols),
            md_block("Presets", presets),
        ]
    )
    (dest / "council.md").write_text(council_md + "\n", encoding="utf-8")
    return dest


def measure_pair(json_path: Path, md_path: Path) -> dict:
    jdoc = extract_library_json(json_path)
    md_text = md_path.read_text(encoding="utf-8")
    mdoc = parse_md_sections(md_text)
    h4 = h4_count(md_text)

    def pack(kind: str, identity: str, flagship_only: bool = False) -> dict:
        j_entries = list(jdoc.get(kind) or [])
        m_entries = list(mdoc.get(kind) or [])
        if flagship_only:
            j_entries = [e for e in j_entries if e.get("flagship") is True]
            m_entries = [e for e in m_entries if e.get("flagship") is True]
        j_ids, j_fp = json_ids_and_prints(j_entries)
        m_ids, m_fp = json_ids_and_prints(m_entries)
        if identity == "fingerprint":
            j_set = unique_in_order(j_fp)
            m_set = unique_in_order(m_fp)
        else:
            j_set = unique_in_order(j_ids)
            m_set = unique_in_order(m_ids)
        return {
            "json_ids": unique_in_order(j_ids),
            "md_ids": unique_in_order(m_ids),
            "json_unique": j_set,
            "md_unique": m_set,
            "measured_json": len(j_set),
            "measured_md": len(m_set),
            "raw_json_n": len(j_ids),
            "raw_md_n": len(m_ids),
            "sets_identical": set(j_set) == set(m_set),
            "id_sets_identical": set(j_ids) == set(m_ids),
        }

    proto = pack("protocols", "id")
    preset = pack("presets", "id")
    proto_ids = set(proto["json_ids"])
    preset_ids = set(preset["json_ids"])
    h4_council = len(mdoc.get("protocols") or []) + len(mdoc.get("presets") or [])
    return {
        "blueprints": pack("blueprints", "fingerprint"),
        "flagship-blueprints": pack("blueprints", "fingerprint", True),
        "workflow-candidates": pack("workflows", "fingerprint"),
        "council-protocols": proto,
        "editable-presets": preset,
        "architectures": pack("architectures", "id"),
        "unique-ideas": pack("ideas", "fingerprint"),
        "h4_all": h4,
        "h4_total": h4_council,
        "protocol_n": proto["measured_json"],
        "preset_n": preset["measured_json"],
        "sum_protocols_presets": proto["measured_json"] + preset["measured_json"],
        "disjoint": sorted(proto_ids & preset_ids),
        "max_would_be": max(proto["measured_json"], preset["measured_json"]),
    }


def drop_one(json_path: Path, md_path: Path, kind: str, drop_id: str, dest: Path) -> tuple[Path, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    jdoc = load_json(json_path)
    key = {
        "blueprints": "blueprints",
        "flagship-blueprints": "blueprints",
        "workflow-candidates": "workflows",
        "council-protocols": "protocols",
        "editable-presets": "presets",
        "architectures": "architectures",
        "unique-ideas": "ideas",
    }[kind]
    rows = [e for e in (jdoc.get(key) or []) if e.get("id") != drop_id]
    jdoc[key] = rows
    j_out = dest / "library.json"
    j_out.write_text(json.dumps(jdoc, indent=2) + "\n", encoding="utf-8")
    md = md_path.read_text(encoding="utf-8")
    # Drop the #### block for drop_id.
    lines = md.splitlines(keepends=True)
    out_lines: list[str] = []
    skipping = False
    for line in lines:
        if H4_ID_RE.match(line.rstrip("\n")):
            skipping = H4_ID_RE.match(line.rstrip("\n")).group(1) == drop_id
        if skipping:
            if H4_ID_RE.match(line.rstrip("\n")) and H4_ID_RE.match(line.rstrip("\n")).group(1) != drop_id:
                skipping = False
                out_lines.append(line)
            elif H2_RE.match(line.rstrip("\n")):
                skipping = False
                out_lines.append(line)
            continue
        out_lines.append(line)
    m_out = dest / "library.md"
    m_out.write_text("".join(out_lines), encoding="utf-8")
    return j_out, m_out


def plant_overlap(json_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    jdoc = load_json(json_path)
    presets = list(jdoc.get("presets") or [])
    if not presets:
        raise ValueError("no presets")
    proto0 = (jdoc.get("protocols") or [{}])[0].get("id")
    presets[0] = dict(presets[0])
    presets[0]["id"] = proto0
    jdoc["presets"] = presets
    out = dest / "council-overlap.json"
    out.write_text(json.dumps(jdoc, indent=2) + "\n", encoding="utf-8")
    return out


def live_census() -> dict:
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"
    cat_path = REPO / cat_rel
    wu_json: list[str] = []
    wu_text: list[str] = []
    if cat_path.is_file():
        raw = cat_path.read_text(encoding="utf-8")
        wu_text = work_unit_ids_text(raw)
        wu_json = work_unit_ids_json(json.loads(raw))
    arch_json = live_architecture_ids_json()
    arch_text = live_architecture_ids_text()
    sources = {k: [r for r in v if present(r)] for k, v in LIVE_CANDIDATES.items()}
    absent = {k: [r for r in v if not present(r)] for k, v in LIVE_CANDIDATES.items()}
    return {
        "work_unit_ids_json": unique_in_order(wu_json),
        "work_unit_ids_text": unique_in_order(wu_text),
        "work_unit_sets_identical": set(wu_json) == set(wu_text),
        "architecture_ids_json": unique_in_order(arch_json),
        "architecture_ids_text": unique_in_order(arch_text),
        "architecture_ids_live": unique_in_order(arch_json),
        "architecture_rule": "command-center/phase3/*/DESIGN.json architecture_id",
        "sources_present": sources,
        "sources_absent": absent,
        "catalog_rel": cat_rel,
        "catalog_present": cat_path.is_file(),
        "prior_audit_present": present("command-center/PROMPT-ONE-FLOOR-AUDIT.json"),
    }


def floor_rows(fixture: dict, live: dict) -> list[dict]:
    rows = []
    live_map = {
        "work-units": (
            live["work_unit_ids_json"],
            live["work_unit_ids_text"],
            "PRESENT" if live["catalog_present"] else "ABSENT",
            [live["catalog_rel"]],
        ),
        "architectures": (
            live["architecture_ids_live"],
            live["architecture_ids_live"],
            "PARTIAL" if live["architecture_ids_live"] else "ABSENT",
            ["command-center/phase3/*/DESIGN.json"],
        ),
    }
    for spec in FLOORS:
        fid = spec["id"]
        floor_n = spec["floor_n"]
        if fid == "work-units":
            jset, tset, state, paths = live_map[fid]
            unique = unique_in_order(jset)
            row_meas_j = len(unique)
            row_meas_t = len(unique_in_order(tset))
            sets_ok = set(jset) == set(tset)
            fx = None
        elif fid == "architectures":
            jset = live["architecture_ids_json"]
            tset = live["architecture_ids_text"]
            state = "PARTIAL" if jset else "ABSENT"
            paths = ["command-center/phase3/*/DESIGN.json"]
            unique = unique_in_order(jset)
            row_meas_j = len(unique)
            row_meas_t = len(unique_in_order(tset))
            sets_ok = set(jset) == set(tset)
            fx = fixture.get("architectures")
        else:
            fx = fixture.get(fid)
            lib_key = {
                "workflow-candidates": "workflow-candidates",
                "blueprints": "blueprints",
                "flagship-blueprints": "blueprints",
                "council-protocols": "council",
                "editable-presets": "council",
                "unique-ideas": "ideas",
            }[fid]
            present_files = live["sources_present"].get(lib_key, []) or live["sources_present"].get(fid, [])
            state = "PRESENT" if present_files else "ABSENT"
            paths = present_files or LIVE_CANDIDATES.get(lib_key, LIVE_CANDIDATES.get("blueprints", []))
            # Live libraries are absent on this tree; measured live count is 0.
            row_meas_j = 0
            row_meas_t = 0
            unique = []
            sets_ok = True
        deficit = floor_n - row_meas_j
        rows.append(
            {
                "id": fid,
                "floor_n": floor_n,
                "identity": spec["identity"],
                "counting_rule_json": spec["counting_rule_json"],
                "counting_rule_md_or_text": spec["counting_rule_md_or_text"],
                "measured_json": row_meas_j,
                "measured_md_or_text": row_meas_t,
                "sets_identical": sets_ok,
                "unique_count": row_meas_j,
                "unique_ids_or_fingerprints": unique,
                "deficit": deficit,
                "holds": deficit <= 0,
                "source_state": state,
                "source_paths": paths,
                "fixture_control": {
                    "measured_json": fx["measured_json"] if fx else None,
                    "measured_md": fx["measured_md"] if fx else None,
                    "sets_identical": fx["sets_identical"] if fx else None,
                    "raw_json_n": fx.get("raw_json_n") if fx else None,
                    "anti_padding_gap": (fx["raw_json_n"] - fx["measured_json"]) if fx else None,
                }
                if fx
                else None,
            }
        )
    return rows
