#!/usr/bin/env python3
"""A2 generated-SSOT registry generator (dependency fixture for ARC-0010).

Materialized 2026-10-24 by the p2-g1 shard-1 builder from the delivered A2
dossier (command-center/phase3/A2/DESIGN.json) because the original
probes/ARC-0010 fixture tree was absent on this worktree.

Determinism contract (A2 DESIGN): generate(registry) is a pure function of
registry bytes and generator_version; two invocations are byte-identical.
Every generated file carries a provenance header naming registry_id,
generator_id and generator_version. BANNED_KEYS are policy vocabulary and are
never serialized from registry entries.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GENERATOR_ID = "a2-ssot-generator"
GENERATOR_VERSION = "1.0.0"
DEFAULT_REGISTRY = Path(__file__).resolve().parent / "registry.json"

# Policy vocabulary a registry entry may never carry. The typed schema keeps
# additionalProperties false; this list is the generator-side backstop.
BANNED_KEYS = (
    "executable_policy",
    "review_status",
    "signature",
    "approval",
    "attestation",
)

_MD_HEADER_RE = re.compile(r"\A<!-- provenance (.*?)-->", re.S)


def load_json(path) -> dict[str, Any]:
    """Load a JSON file (registry or schema) from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical deterministic JSON bytes: sorted keys, indent 2, LF, trailing newline."""
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def check_banned(entry: dict[str, Any]) -> None:
    for key in entry:
        if str(key).lower() in BANNED_KEYS:
            raise ValueError(f"banned policy key in registry entry: {key}")


def provenance(entry: dict[str, Any]) -> dict[str, str]:
    """Machine-readable provenance stamped onto every generated artifact."""
    return {
        "generator_id": GENERATOR_ID,
        "registry_id": str(entry.get("id") or ""),
        "generator_version": GENERATOR_VERSION,
    }


def md_header(entry: dict[str, Any]) -> str:
    """Provenance header for generated markdown artifacts."""
    prov = provenance(entry)
    lines = "".join(f"{k}: {v}\n" for k, v in sorted(prov.items()))
    return f"<!-- provenance {lines}-->\n"


def json_with_prov(entry: dict[str, Any], content: dict[str, Any]) -> bytes:
    """Canonical JSON artifact bytes with the provenance block on top."""
    doc: dict[str, Any] = {}
    doc.update(provenance(entry))
    doc["content"] = content
    return canonical_json_bytes(doc)


def _render_skill(entry: dict[str, Any]) -> bytes:
    lines = [
        md_header(entry),
        f"# {entry.get('name')}\n\n",
        f"{entry.get('description')}\n\n",
        "## Instructions\n\n",
        f"{entry.get('instructions')}\n\n",
        "## Roles\n\n",
    ]
    for role in entry.get("roles") or []:
        lines.append(f"- {role}\n")
    return "".join(lines).encode("utf-8")


def _render_markdown(entry: dict[str, Any], body_lines: list[str]) -> bytes:
    parts = [md_header(entry), f"# {entry.get('title')}\n\n"]
    parts.extend(line + "\n" for line in body_lines)
    return "".join(parts).encode("utf-8")


def render_entry(entry: dict[str, Any]) -> tuple[str, bytes]:
    """Render one registry entry to (relative path, artifact bytes)."""
    check_banned(entry)
    kind = str(entry.get("kind") or "")
    eid = str(entry.get("id") or "")
    if kind == "plugin_manifest":
        return "plugin.json", json_with_prov(entry, dict(entry))
    if kind == "marketplace_entry":
        return f"marketplace/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "skill":
        return f"skills/{eid}/SKILL.md", _render_skill(entry)
    if kind == "hook":
        return f"hooks/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "rule":
        return (
            f"rules/{eid}.md",
            _render_markdown(entry, [str(entry.get("body") or "")]),
        )
    if kind == "doc":
        return (
            f"docs/{eid}.md",
            _render_markdown(entry, [str(entry.get("body") or "")]),
        )
    if kind == "workflow_blueprint":
        return f"workflows/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "workflow_catalog":
        return f"workflows/catalog-{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "council_preset":
        return f"councils/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "council_catalog":
        return f"councils/catalog-{eid}.json", json_with_prov(entry, dict(entry))
    raise ValueError(f"untyped registry entry kind: {kind!r}")


def generate(registry: dict[str, Any]) -> dict[str, bytes]:
    """Deterministically render every registry entry. Pure function of inputs."""
    entries = [e for e in (registry.get("entries") or []) if isinstance(e, dict)]
    files: dict[str, bytes] = {}
    for entry in sorted(
        entries, key=lambda e: (str(e.get("kind") or ""), str(e.get("id") or ""))
    ):
        rel, data = render_entry(entry)
        files[rel] = data
    return files


def write_tree(files: dict[str, bytes], root) -> None:
    """Materialize a generate() file map under root."""
    root = Path(root)
    for rel, data in sorted(files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def parse_provenance(raw: bytes) -> dict[str, str]:
    """Extract the provenance block from generated artifact bytes."""
    text = raw.decode("utf-8")
    if text.lstrip().startswith("<!--"):
        m = _MD_HEADER_RE.search(text)
        if m:
            out: dict[str, str] = {}
            for line in m.group(1).strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    out[key.strip()] = value.strip()
            return out
        return {}
    try:
        doc = json.loads(text)
    except ValueError:
        return {}
    if not isinstance(doc, dict):
        return {}
    return {
        "generator_id": str(doc.get("generator_id") or ""),
        "registry_id": str(doc.get("registry_id") or ""),
        "generator_version": str(doc.get("generator_version") or ""),
    }


if __name__ == "__main__":
    reg = load_json(DEFAULT_REGISTRY)
    tree = generate(reg)
    write_tree(tree, Path(__file__).resolve().parent / "generated-preview")
    print(f"generated {len(tree)} files from {DEFAULT_REGISTRY.name}")
