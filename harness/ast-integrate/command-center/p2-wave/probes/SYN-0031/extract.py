#!/usr/bin/env python3
"""Independent floor extractors for SYN-0031.

Extractor A: json.loads + typed array path.
Extractor B: brace-scanner over the named array (never calls json.loads),
or ATX heading regex on markdown twins.

Protocol vs preset heading regexes are disjoint by the kind word and are
proven silent on each other's items in regex_cross_silence().
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PRIOR_AUDIT_REL = "command-center/PROMPT-ONE-FLOOR-AUDIT.json"
OUT_REL = "command-center/receipts/SYN-0031.json"
SCHEMA_REL = "command-center/schema/floor-recount.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA_REL = "platform/schema/receipt.schema.json"
UNIT_ID = "SYN-0031"

# Catalog T-02 cited Prompt One JSON-record recount (claim, not a fact).
PRIOR_CLAIMS = {
    "platform_options": 283,
    "workflow_candidates": 284,
    "blueprints": 108,
    "council_protocols": 58,
    "presets": 72,
    "work_units": 2048,
}

FLOORS = [
    {
        "id": "workflow_candidates",
        "name": "workflow candidates",
        "floor": 160,
        "corpus": "08",
        "json_keys": ["candidates", "workflows", "workflow_candidates"],
        "md_kind": "Workflow",
    },
    {
        "id": "blueprints",
        "name": "blueprints",
        "floor": 96,
        "corpus": "09",
        "json_keys": ["blueprints", "workflow_blueprints"],
        "md_kind": "Blueprint",
    },
    {
        "id": "council_protocols",
        "name": "council protocols",
        "floor": 48,
        "corpus": "12",
        "json_keys": ["protocols"],
        "md_kind": "Protocol",
    },
    {
        "id": "presets",
        "name": "presets",
        "floor": 64,
        "corpus": "12",
        "json_keys": ["presets"],
        "md_kind": "Preset",
    },
    {
        "id": "work_units",
        "name": "work units",
        "floor": 2048,
        "corpus": "catalog",
        "json_keys": ["work_units"],
        "md_kind": None,
    },
    {
        "id": "platform_options",
        "name": "platform options",
        "floor": 160,
        "corpus": "07",
        "json_keys": ["options", "cards", "option_universe"],
        "md_kind": "Option",
    },
]

CORPUS_NAMES = {
    "07": [
        "07-OPTION-UNIVERSE.json",
        "07-OPTION-UNIVERSE.md",
        "07-OPTION-UNIVERSE.json",
        "07-OPTION-UNIVERSE.md",
    ],
    "08": [
        "08-WORKFLOW-ARCHAEOLOGY.json",
        "08-WORKFLOW-ARCHAEOLOGY.md",
        "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.json",
        "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "08-WORKFLOW-CANDIDATE-REGISTRY.md",
    ],
    "09": [
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
    ],
    "12": [
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    ],
}

PROTOCOL_HEADING_RE = re.compile(
    r"(?m)^#{2,4}\s+Protocol\s+([A-Z][A-Z0-9._-]*)"
)
PRESET_HEADING_RE = re.compile(
    r"(?m)^#{2,4}\s+Preset\s+([A-Z][A-Z0-9._-]*)"
)

JSON_PATH_RULE = (
    "Extractor A (json.loads): unique string values of the `id` field on each "
    "object in the named JSON array (work_units / options|cards / "
    "candidates|workflows / blueprints / protocols / presets). Does not count "
    "`items[]`, nested dependency ids, or heading text."
)
BRACE_RULE = (
    "Extractor B (brace scanner, no json.loads): locate the named array at root "
    "object depth 1, then take the first depth-1 `id` string of each top-level "
    "array object. Markdown twin: ATX heading `#{2,4} <Kind> <ID>`."
)


def catalog_unit(repo: Path | None = None) -> dict:
    root = repo or REPO
    data = json.loads((root / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise SystemExit("FAILED:SYN-0031 catalog unit missing")


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def search_roots(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    candidates = [
        root,
        root / "command-center",
        root / "command-center" / "sources",
        root / "command-center" / "corpus",
        Path("/opt/p2/harness-restore-20260806"),
        Path.home() / ".claude" / "harness-restore-20260806",
    ]
    env = os.environ.get("HARVEST_RESTORE")
    if env:
        candidates.append(Path(env))
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.is_dir():
            out.append(path)
    return out


def _rel_or_abs(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def locate_corpus(repo: Path | None = None) -> dict:
    root = repo or REPO
    roots = search_roots(root)
    hits: dict[str, dict] = {}
    for label, names in CORPUS_NAMES.items():
        found_json = None
        found_md = None
        for base in roots:
            for name in names:
                cand = base / name
                if not cand.is_file():
                    continue
                if cand.suffix.lower() == ".json" and found_json is None:
                    found_json = cand
                elif cand.suffix.lower() == ".md" and found_md is None:
                    found_md = cand
        hits[label] = {
            "json": None if found_json is None else _rel_or_abs(root, found_json),
            "md": None if found_md is None else _rel_or_abs(root, found_md),
            "json_present": found_json is not None,
            "md_present": found_md is not None,
        }
    return {"searched_roots": [str(p) for p in roots], "hits": hits}


def json_array_ids(path: Path, keys: list[str]) -> list[str]:
    if not path.is_file() or path.suffix.lower() != ".json":
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    for key in keys:
        arr = doc.get(key)
        if not isinstance(arr, list):
            continue
        ids: list[str] = []
        seen: set[str] = set()
        for item in arr:
            if not isinstance(item, dict):
                continue
            value = item.get("id")
            if isinstance(value, str) and value and value not in seen:
                seen.add(value)
                ids.append(value)
        return ids
    return []


def _read_string(text: str, i: int) -> tuple[str, int]:
    i += 1
    n = len(text)
    chars: list[str] = []
    while i < n:
        c = text[i]
        if c == "\\":
            if i + 1 < n:
                chars.append(text[i + 1])
                i += 2
                continue
            break
        if c == '"':
            return "".join(chars), i + 1
        chars.append(c)
        i += 1
    return "".join(chars), n


def find_root_array_start(text: str, key: str) -> int | None:
    n = len(text)
    i = 0
    depth = 0
    in_str = False
    needle = f'"{key}"'
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            if depth == 1 and text.startswith(needle, i):
                j = i + len(needle)
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j < n and text[j] == ":":
                    j += 1
                    while j < n and text[j] in " \t\r\n":
                        j += 1
                    if j < n and text[j] == "[":
                        return j
            in_str = True
            i += 1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        i += 1
    return None


def first_id_in_object(text: str, start: int) -> tuple[str | None, int]:
    i = start + 1
    depth = 1
    n = len(text)
    found: str | None = None
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            if depth == 1 and text.startswith('"id"', i):
                j = i + 4
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j < n and text[j] == ":":
                    j += 1
                    while j < n and text[j] in " \t\r\n":
                        j += 1
                    if j < n and text[j] == '"':
                        value, k = _read_string(text, j)
                        if found is None:
                            found = value
                        i = k
                        continue
            in_str = True
            i += 1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return found, i + 1
        i += 1
    return found, i


def brace_array_ids(text: str, keys: list[str]) -> list[str]:
    """Extractor B for JSON text: brace walk only, never the stdlib JSON parser."""
    for key in keys:
        start = find_root_array_start(text, key)
        if start is None:
            continue
        ids: list[str] = []
        seen: set[str] = set()
        i = start + 1
        n = len(text)
        arr_depth = 1
        in_str = False
        while i < n:
            c = text[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == '"':
                    in_str = False
                i += 1
                continue
            if c == '"':
                in_str = True
                i += 1
                continue
            if c == "{":
                if arr_depth == 1:
                    obj_id, end_i = first_id_in_object(text, i)
                    if obj_id and obj_id not in seen:
                        seen.add(obj_id)
                        ids.append(obj_id)
                    i = end_i
                    continue
                arr_depth += 1
                i += 1
                continue
            if c == "[":
                arr_depth += 1
            elif c == "]":
                arr_depth -= 1
                if arr_depth == 0:
                    return ids
            elif c == "}":
                arr_depth -= 1
            i += 1
        return ids
    return []


def markdown_kind_ids(text: str, kind: str) -> list[str]:
    if not kind:
        return []
    pat = re.compile(
        rf"(?m)^#{{2,4}}\s+{re.escape(kind)}\s+([A-Z][A-Z0-9._-]*)"
    )
    ids: list[str] = []
    seen: set[str] = set()
    for match in pat.finditer(text):
        value = match.group(1)
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def unique_in_order(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def recount_sources(
    json_path: Path | None,
    md_path: Path | None,
    keys: list[str],
    md_kind: str | None,
) -> dict:
    json_ids = json_array_ids(json_path, keys) if json_path else []
    brace_ids = (
        brace_array_ids(json_path.read_text(encoding="utf-8"), keys)
        if json_path and json_path.is_file()
        else []
    )
    md_ids = (
        markdown_kind_ids(md_path.read_text(encoding="utf-8"), md_kind or "")
        if md_path and md_path.is_file() and md_kind
        else []
    )
    if json_path is not None and json_path.is_file():
        a, b = json_ids, brace_ids
        this = json_ids
    elif md_path is not None and md_path.is_file():
        a, b = md_ids, markdown_kind_ids(
            md_path.read_text(encoding="utf-8"), md_kind or ""
        )
        this = md_ids
    else:
        a, b, this = [], [], []
    a_set, b_set = set(a), set(b)
    if a == b:
        verdict = "AGREE"
        resolution = (
            "Both extractors returned the same ordered unique id list "
            f"(n={len(this)})."
        )
    else:
        verdict = "DISAGREE"
        only_a = sorted(a_set - b_set)
        only_b = sorted(b_set - a_set)
        if json_path is not None and json_path.is_file():
            this = json_ids
            resolution = (
                "DISAGREE resolved from the JSON document: json.loads of the "
                f"typed array is the record (n={len(json_ids)}). Brace scanner "
                f"delta only_A={only_a[:6]} only_B={only_b[:6]}."
            )
        elif md_path is not None and md_path.is_file():
            this = md_ids
            resolution = (
                "DISAGREE resolved from the markdown document: ATX headings of "
                f"kind {md_kind} are the record (n={len(md_ids)}). "
                f"delta only_A={only_a[:6]} only_B={only_b[:6]}."
            )
        else:
            this = []
            resolution = "Both extractors empty; source files are absent."
    this = unique_in_order(this)
    return {
        "json_ids": json_ids,
        "brace_ids": brace_ids,
        "md_ids": md_ids,
        "json_count": len(json_ids),
        "regex_count": len(b),
        "this_ids": this,
        "this_count": len(this),
        "extractor_verdict": verdict,
        "resolution": resolution,
        "json_md_symmetric_difference": sorted(set(json_ids) ^ set(md_ids)),
        "json_md_symmetric_difference": sorted(set(json_ids) ^ set(md_ids)),
    }


def path_from_hit(repo: Path, rel_or_abs: str | None) -> Path | None:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if p.is_file():
        return p
    cand = repo / rel_or_abs
    if cand.is_file():
        return cand
    return None


def catalog_declared_count(repo: Path) -> dict:
    data = json.loads((repo / CATALOG_REL).read_text(encoding="utf-8"))
    meta = data.get("work_units_meta") or {}
    return {
        "target": meta.get("target"),
        "work_unit_count": meta.get("work_unit_count"),
        "shortfall": meta.get("shortfall"),
        "items": len(data.get("items") or []),
    }


def quote_ids_from_document(path: Path, ids: list[str]) -> list[dict]:
    if not path.is_file() or not ids:
        return []
    text = path.read_text(encoding="utf-8")
    quotes = []
    for item in ids:
        needle = f'"{item}"'
        idx = text.find(needle)
        if idx < 0:
            needle = item
            idx = text.find(item)
        if idx < 0:
            quotes.append(
                {"id": item, "quoted": False, "line": None, "snippet": ""}
            )
            continue
        line = text[:idx].count("\n") + 1
        start = max(0, idx - 20)
        end = min(len(text), idx + len(needle) + 20)
        snippet = text[start:end].replace("\n", "\\n")
        quotes.append(
            {"id": item, "quoted": True, "line": line, "snippet": snippet}
        )
    return quotes


def recount_floor(repo: Path, spec: dict, locator: dict) -> dict:
    floor_id = spec["id"]
    prior = PRIOR_CLAIMS[floor_id]
    if spec["corpus"] == "catalog":
        catalog = repo / CATALOG_REL
        measured = recount_sources(catalog, None, spec["json_keys"], spec["md_kind"])
        source_files = [CATALOG_REL]
    else:
        hit = locator["hits"][spec["corpus"]]
        json_path = path_from_hit(repo, hit.get("json"))
        md_path = path_from_hit(repo, hit.get("md"))
        measured = recount_sources(
            json_path, md_path, spec["json_keys"], spec["md_kind"]
        )
        source_files = []
        if hit.get("json"):
            source_files.append(hit["json"])
        if hit.get("md"):
            source_files.append(hit["md"])
        if not source_files:
            measured = {
                "json_ids": [],
                "brace_ids": [],
                "md_ids": [],
                "json_count": 0,
                "regex_count": 0,
                "this_ids": [],
                "this_count": 0,
                "extractor_verdict": "AGREE",
                "resolution": (
                    f"DISAGREE with Prompt One claim {prior}: corpus "
                    f"{spec['corpus']} JSON/markdown twins are absent on this "
                    "worktree (Path.is_file is false). this_count=0 from the "
                    "documents, not restated from Prompt One."
                ),
                "json_md_symmetric_difference": [],
            }
    this_ids = measured["this_ids"]
    this_count = measured["this_count"]
    vs_prior = "AGREE" if this_count == prior else "DISAGREE"
    if spec["corpus"] != "catalog" and not source_files:
        resolution = measured["resolution"]
    elif spec["corpus"] == "catalog" and vs_prior == "DISAGREE":
        meta_note = catalog_declared_count(repo)
        resolution = (
            f"{measured['resolution']} vs_prior DISAGREE: Prompt Two floor / "
            f"claim is {prior}; live $.work_units[*].id unique count is "
            f"{this_count}. WORK-UNIT-CATALOG.json work_units_meta.target="
            f"{meta_note.get('target')} work_unit_count="
            f"{meta_note.get('work_unit_count')} shortfall="
            f"{meta_note.get('shortfall')}. Did not count items[] "
            f"(n={meta_note.get('items')}) as work units."
        )
    else:
        resolution = (
            f"{measured['resolution']} vs_prior {vs_prior}: claim {prior}, "
            f"this_count {this_count}."
        )
    rule = (
        JSON_PATH_RULE
        + " "
        + BRACE_RULE
        + f" Named array keys tried: {spec['json_keys']}."
    )
    return {
        "id": floor_id,
        "name": spec["name"],
        "floor": spec["floor"],
        "prior_count": prior,
        "this_count": this_count,
        "json_count": measured["json_count"],
        "regex_count": measured["regex_count"],
        "extraction_rule": rule,
        "first_three_ids": this_ids[:3],
        "last_three_ids": this_ids[-3:] if this_ids else [],
        "extractor_verdict": measured["extractor_verdict"],
        "vs_prior": vs_prior,
        "resolution": resolution,
        "floor_met": this_count >= spec["floor"],
        "source_files": source_files,
        "this_ids": this_ids,
    }


def protocol_preset_disjoint(protocol_ids: list[str], preset_ids: list[str]) -> dict:
    inter = sorted(set(protocol_ids) & set(preset_ids))
    return {
        "protocol_ids_count": len(protocol_ids),
        "preset_ids_count": len(preset_ids),
        "intersection_ids": inter,
        "empty_intersection": len(inter) == 0,
        "did_not_sum_blind": True,
        "did_not_take_max": True,
        "sum_would_have_been": len(protocol_ids) + len(preset_ids),
        "max_would_have_been": max(len(protocol_ids), len(preset_ids))
        if (protocol_ids or preset_ids)
        else 0,
    }


def heading_items(text: str, kind: str) -> list[str]:
    pat = re.compile(rf"(?m)^#{{2,4}}\s+{re.escape(kind)}\s+[^\n]+")
    return [m.group(0) for m in pat.finditer(text)]


def regex_cross_silence(protocol_text: str, preset_text: str) -> dict:
    combined = protocol_text + ("\n" if protocol_text and preset_text else "") + preset_text
    protocol_items = heading_items(combined, "Protocol")
    preset_items = heading_items(combined, "Preset")
    proto_on_presets = [
        item for item in preset_items if PROTOCOL_HEADING_RE.search(item)
    ]
    preset_on_protos = [
        item for item in protocol_items if PRESET_HEADING_RE.search(item)
    ]
    silent_proto = len(proto_on_presets) == 0
    silent_preset = len(preset_on_protos) == 0
    return {
        "protocol_regex": PROTOCOL_HEADING_RE.pattern,
        "preset_regex": PRESET_HEADING_RE.pattern,
        "protocol_silent_on_preset_items": silent_proto,
        "preset_silent_on_protocol_items": silent_preset,
        "protocol_silent_on_preset_items": silent_proto,
        "preset_silent_on_protocol_items": silent_preset,
        "protocol_hits_on_presets": proto_on_presets,
        "preset_hits_on_protocols": preset_on_protos,
        "protocol_hits_on_presets": proto_on_presets,
        "preset_hits_on_protocols": preset_on_protos,
    }


def brace_scanner_calls_json_loads() -> bool:
    src = (HERE / "extract.py").read_text(encoding="utf-8")
    start = src.find("def brace_array_ids")
    end = src.find("\ndef markdown_kind_ids")
    body = src[start:end]
    return "json.loads" in body


def measure_live(repo: Path | None = None) -> dict:
    root = repo or REPO
    locator = locate_corpus(root)
    floors = [recount_floor(root, spec, locator) for spec in FLOORS]
    by_id = {row["id"]: row for row in floors}
    proto = by_id["council_protocols"]["this_ids"]
    preset = by_id["presets"]["this_ids"]
    disjoint = protocol_preset_disjoint(proto, preset)
    good12 = (
        HERE
        / "fixtures"
        / "corpus-good"
        / "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
    )
    md = good12.read_text(encoding="utf-8") if good12.is_file() else ""
    silence = regex_cross_silence(md, md)
    catalog = root / CATALOG_REL
    wu = by_id["work_units"]
    quote_ids = []
    if wu["first_three_ids"]:
        quote_ids.append(wu["first_three_ids"][0])
    if wu["last_three_ids"]:
        quote_ids.append(wu["last_three_ids"][-1])
    quotes = quote_ids_from_document(catalog, quote_ids)
    return {
        "locator": locator,
        "floors": floors,
        "by_id": by_id,
        "disjoint": disjoint,
        "silence": silence,
        "work_unit_quotes": quotes,
        "catalog_declared": catalog_declared_count(root),
        "prior_audit_present": (root / PRIOR_AUDIT_REL).is_file(),
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_record(repo: Path, rel: str, role: str) -> dict:
    path = repo / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_record(
    role: str, method: str, command: str, raw: str, exit_code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def local_validator(repo: Path | None = None):
    """Draft7 validator with catalog shim $ids loaded from this worktree.

    command-center/schema/floor-recount.schema.json is a generated $ref shim
    whose target lives on https://ast-integrate.invalid/. jsonschema 4.x
    Draft7Validator without a store tries the network and raises
    RefResolutionError (first structural fingerprint). A second attempt
    on that same fingerprint is a grind; this resolver is the named pivot.
    """
    root = repo or REPO
    schema = json.loads((root / SCHEMA_REL).read_text(encoding="utf-8"))
    profiles = json.loads((root / PROFILES_REL).read_text(encoding="utf-8"))
    receipt = json.loads((root / RECEIPT_SCHEMA_REL).read_text(encoding="utf-8"))
    store = {
        schema.get("$id", ""): schema,
        profiles.get("$id", ""): profiles,
        receipt.get("$id", ""): receipt,
        "https://ast-integrate.invalid/command-center/schema/floor-recount.schema.json": schema,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def schema_errors(doc: object, repo: Path | None = None) -> list[str]:
    try:
        validator = local_validator(repo)
        return [
            f"{list(err.path)}: {err.message}"
            for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        ]
    except Exception as exc:
        return [f"{type(exc).__name__}: {exc}"]


def domain_from_artifact(doc: dict) -> dict:
    """Read SYN-0031 domain fields from report (envelope) or top-level (legacy)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}

    def pick(key: str, default=None):
        if key in report:
            return report[key]
        return doc.get(key, default)

    floors = pick("floors") or []
    return {
        "floors": floors if isinstance(floors, list) else [],
        "protocol_preset_disjointness": pick("protocol_preset_disjointness") or {},
        "regex_cross_silence": pick("regex_cross_silence") or {},
        "known_present_quotes": pick("known_present_quotes") or [],
        "kind": report.get("kind") or doc.get("kind"),
    }


# Aliases matching emit/probe call sites.
catalog_unit = catalog_unit
find_line = find_line
json_array_ids = json_array_ids
brace_array_ids = brace_array_ids
recount_sources = recount_sources
protocol_preset_disjoint = protocol_preset_disjoint
regex_cross_silence = regex_cross_silence
brace_scanner_calls_json_loads = brace_scanner_calls_json_loads
measure_live = measure_live
local_validator = local_validator
schema_errors = schema_errors
domain_from_artifact = domain_from_artifact
JSON_PATH_RULE = JSON_PATH_RULE
BRACE_RULE = BRACE_RULE
PRIOR_CLAIMS = PRIOR_CLAIMS
