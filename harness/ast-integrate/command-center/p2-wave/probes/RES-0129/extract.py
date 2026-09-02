#!/usr/bin/env python3
"""Extract plugin-manifest field names from captured schemas/specs (not prose mentions)."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"

CONCEPTS = (
    "name",
    "version",
    "entrypoint",
    "permissions",
    "tool_declarations",
    "hooks",
    "compatibility_ranges",
)

# Only top-level manifest keys that *are* the concept. Nested MCP `command` is not entrypoint.
ALIASES: dict[str, frozenset[str]] = {
    "name": frozenset({"name"}),
    "version": frozenset({"version"}),
    "entrypoint": frozenset({"main", "entry", "entrypoint", "entryPoint", "bin", "module"}),
    "permissions": frozenset(
        {
            "permissions",
            "permission",
            "requiredPermissions",
            "required_permissions",
            "allowedTools",
            "allowed_tools",
            "permissionMode",
        }
    ),
    "tool_declarations": frozenset(
        {
            "mcpServers",
            "mcp_servers",
            "tools",
            "contributes",
        }
    ),
    "hooks": frozenset({"hooks"}),
    "compatibility_ranges": frozenset(
        {
            "engines",
            "engine",
            "compatibility",
            "minClientVersion",
            "min_client_version",
            "vscodeEngine",
        }
    ),
}

CLIENTS = (
    "claude-code",
    "codex-cli",
    "gemini-cli",
    "cursor",
    "continue-dev",
    "copilot-extensions",
)


def _camel(name: str) -> str:
    parts = name.split("_")
    if len(parts) == 1:
        return name
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)


def json_schema_properties(text: str) -> set[str]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return set()
    props = doc.get("properties")
    if not isinstance(props, dict):
        return set()
    return {str(k) for k in props.keys() if not str(k).startswith("$")}


def ts_top_level_keys(text: str) -> set[str]:
    """Keys from `export interface X {` blocks and `z.object({ key:`.

    Scoped to object-level properties indented 2 spaces inside an interface, or
    `key: z.` lines in a zod object. Nested interface fields at deeper indent
    are ignored for completeness of the *manifest* top level.
    """
    keys: set[str] = set()
    # zod: `  name: z.string()`
    for m in re.finditer(r"^  ([A-Za-z][A-Za-z0-9_]*)\??:\s*z\.", text, re.M):
        keys.add(m.group(1))
    # interface ExtensionConfig { ... }
    for block in re.finditer(
        r"export interface [A-Za-z0-9_]+\s*\{(.*?)\n\}",
        text,
        re.S,
    ):
        body = block.group(1)
        for m in re.finditer(r"^  ([A-Za-z][A-Za-z0-9_]*)\??\s*:", body, re.M):
            keys.add(m.group(1))
    return keys


def rs_struct_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for m in re.finditer(r"^\s+(?:pub\s+)?([a-z][a-z0-9_]*)\s*:", text, re.M):
        raw = m.group(1)
        keys.add(raw)
        keys.add(_camel(raw))
    return keys


def html_code_keys(text: str) -> set[str]:
    """First-column <code>name</code> cells in HTML tables (GitHub docs HTML)."""
    keys: set[str] = set()
    for m in re.finditer(
        r"<tr[^>]*>\s*<td[^>]*>\s*(?:<code>|<tt>)([A-Za-z][A-Za-z0-9_$]*)(?:</code>|</tt>)",
        text,
        re.I,
    ):
        keys.add(m.group(1))
    return keys


def md_field_table_keys(text: str) -> set[str]:
    """Backticked identifiers in markdown tables and `- `field`` spec bullets.

    Restricted to lines that look like schema field listings, not running prose.
    """
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        # table row: | `name` | string | ...
        if stripped.startswith("|") and "`" in stripped:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not cells:
                continue
            first = cells[0]
            m = re.fullmatch(r"`([A-Za-z][A-Za-z0-9_$]*)`", first)
            if m:
                keys.add(m.group(1))
                continue
            # | Field | `name` |
            for cell in cells[1:2]:
                m2 = re.fullmatch(r"`([A-Za-z][A-Za-z0-9_$]*)`", cell.strip())
                if m2 and cells[0].lower() in {"field", "key", "property", "name"}:
                    keys.add(m2.group(1))
        # spec bullet: - `name` (`string`)
        m = re.match(r"^- `([A-Za-z][A-Za-z0-9_$]*)`", stripped)
        if m:
            keys.add(m.group(1))
    keys |= html_code_keys(text)
    return keys


def json_example_keys(text: str) -> set[str]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return set()
    if not isinstance(doc, dict):
        return set()
    return {str(k) for k in doc.keys() if not str(k).startswith("$")}


EXTRACTORS = {
    "json-schema": json_schema_properties,
    "ts-source": ts_top_level_keys,
    "rs-source": rs_struct_keys,
    "md-spec": md_field_table_keys,
    "json-example": json_example_keys,
}


def load_index() -> dict:
    path = CAP / "_index.json"
    if not path.is_file():
        raise RuntimeError("captures/_index.json missing; run capture.py")
    return json.loads(path.read_text(encoding="utf-8"))


def body_for(meta: dict) -> str:
    rel = Path(meta["capture_path"]).name
    path = CAP / rel
    if not path.is_file():
        # fall back to source_id naming
        sid = f"{meta['client']}__{meta['source_id']}"
        for cand in CAP.glob(sid + ".*"):
            if cand.suffix == ".json" and cand.name.endswith(".meta.json"):
                continue
            path = cand
            break
    raw = path.read_bytes()
    return raw.decode("utf-8", errors="replace")


def fields_from_source(meta: dict) -> set[str]:
    kind = meta.get("kind")
    fn = EXTRACTORS.get(kind)
    if fn is None:
        return set()
    return fn(body_for(meta))


def mention_words(text: str) -> set[str]:
    """Prose substring mentions of concept aliases (the forbidden extractor)."""
    lower = text.lower()
    hits: set[str] = set()
    for concept, aliases in ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower:
                hits.add(concept)
                break
    return hits


def extract_client(client: str, index: dict | None = None) -> dict:
    index = index or load_index()
    rows = [s for s in index["sources"] if s.get("client") == client]
    complete_fields: set[str] = set()
    example_fields: set[str] = set()
    mention: set[str] = set()
    rails = []
    complete_ok = False
    prose_ok = False
    for meta in rows:
        if not (meta.get("ok") and meta.get("http_status") == 200):
            continue
        body = body_for(meta)
        kind = meta.get("kind")
        if kind in EXTRACTORS:
            got = EXTRACTORS[kind](body)
            if meta.get("complete_field_list") and kind != "json-example":
                complete_fields |= got
                complete_ok = True
            else:
                example_fields |= got
        if kind in {"docs-prose", "md-spec"}:
            mention |= mention_words(body)
            prose_ok = True
        rails.append(
            {
                "source_id": meta.get("source_id"),
                "kind": kind,
                "url": meta.get("final_url") or meta.get("url"),
                "fetched_at": meta.get("fetched_at"),
                "http_status": meta.get("http_status"),
                "sha256": meta.get("sha256"),
                "bytes": meta.get("bytes"),
                "complete_field_list": bool(meta.get("complete_field_list")),
                "capture_path": meta.get("capture_path"),
            }
        )
    statuses: dict[str, str] = {}
    matched: dict[str, list[str]] = {}
    for concept in CONCEPTS:
        aliases = ALIASES[concept]
        hit = sorted(complete_fields & aliases)
        matched[concept] = hit
        if not complete_ok:
            statuses[concept] = "NOT-CHECKED"
        elif hit:
            statuses[concept] = "SUPPORTED"
        else:
            statuses[concept] = "UNSUPPORTED"
    return {
        "client": client,
        "complete_fields": sorted(complete_fields),
        "example_fields": sorted(example_fields),
        "mention_concepts": sorted(mention),
        "statuses": statuses,
        "matched_aliases": matched,
        "complete_ok": complete_ok,
        "prose_ok": prose_ok,
        "rails": rails,
    }


def extract_all() -> dict[str, dict]:
    index = load_index()
    return {c: extract_client(c, index) for c in CLIENTS}


def mention_mutant_statuses(extracted: dict[str, dict]) -> dict[str, dict[str, str]]:
    """If a concept word appears in captured bytes, mark SUPPORTED (use=mention)."""
    out: dict[str, dict[str, str]] = {}
    for client, row in extracted.items():
        mentions = set(row.get("mention_concepts") or [])
        mutated = {}
        for concept in CONCEPTS:
            mutated[concept] = "SUPPORTED" if concept in mentions else row["statuses"][concept]
        out[client] = mutated
    return out


if __name__ == "__main__":
    data = extract_all()
    print(json.dumps({c: v["statuses"] for c, v in data.items()}, indent=2, sort_keys=True))
