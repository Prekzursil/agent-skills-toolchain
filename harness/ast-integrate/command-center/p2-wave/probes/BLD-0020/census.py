#!/usr/bin/env python3
"""PREFIX-NUMBER declaration-site census for BLD-0020.

A token is DECLARED only at a card/entry identity site (JSON identity key,
markdown heading, markdown table first cell, markdown definition). Every other
occurrence is a REFERENCE. A prefix with only references is DANGLING, not a
namespace. A prefix with declarations in two or more logical registries is a
collision.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

TOKEN_RE = re.compile(r"\b([A-Z]{1,8})-(\d{1,4})\b")
ID_KEYS = (
    "id",
    "unit_id",
    "option_id",
    "card_id",
    "deliverable_id",
    "mech_id",
    "grade_id",
    "namespace_id",
    "work_unit_id",
    "artifact_id",
    "entry_id",
)
ID_KEY_ALT = "|".join(ID_KEYS)
DECL_JSON = re.compile(
    rf'"(?P<key>{ID_KEY_ALT})"\s*:\s*"(?P<tok>([A-Z]{{1,8}})-(\d{{1,4}}))"'
)
DECL_YAML = re.compile(
    rf"^\s*(?:{ID_KEY_ALT})\s*:\s*['\"]?(?P<tok>([A-Z]{{1,8}})-(\d{{1,4}}))",
    re.IGNORECASE,
)
DECL_HEADING = re.compile(r"^(#{1,6})\s+.*\b([A-Z]{1,8}-\d{1,4})\b")
DECL_TABLE = re.compile(r"^\|\s*([A-Z]{1,8}-\d{1,4})\s*\|")
DECL_DEF = re.compile(
    r"^(\s*[-*]\s+)?(?:\*\*)?([A-Z]{1,8}-\d{1,4})(?:\*\*)?\s*:"
)
TEXT_SUFFIX = {".md", ".json", ".yml", ".yaml", ".txt"}
SKIP_DIR = {".git", "__pycache__", "node_modules", ".venv", ".tox"}
NOISE_PREFIXES = frozenset(
    {
        "UTF",
        "ISO",
        "SHA",
        "MD",
        "CRC",
        "RFC",
        "CVE",
        "CWE",
        "PEP",
        "HTTP",
        "TLS",
        "SSL",
        "AES",
        "RSA",
        "CPU",
        "ARM",
        "PDF",
        "PNG",
        "HTML",
        "CSS",
        "XML",
        "JSON",
        "YAML",
        "TOML",
        "CSV",
        "UUID",
        "IPV",
    }
)
PATTERN_DOC = {
    "token": r"\b([A-Z]{1,8})-(\d{1,4})\b",
    "json_identity_keys": list(ID_KEYS),
    "markdown": {
        "heading": r"^(#{1,6})\s+.*\bPREFIX-NUMBER\b",
        "table_first_cell": r"^\|\s*PREFIX-NUMBER\s*\|",
        "definition": r"^(?:[-*]\s+)?(?:\*\*)?PREFIX-NUMBER(?:\*\*)?\s*:",
        "yaml_identity": r"^\s*(?:id|option_id|card_id|deliverable_id)\s*:\s*PREFIX-NUMBER",
    },
    "rule": (
        "A prefix is DECLARED only where a card/entry defines it (JSON identity "
        "key, markdown heading, table-first-cell, or definition). A prefix that "
        "only ever appears as a reference is DANGLING and is not a namespace."
    ),
    "fenced_code": "skipped",
    "retry_pivot": (
        "Two strikes then pivot: if the declaration-site pattern misses a known "
        "namespace twice, enumerate declaration sites per-registry by hand."
    ),
}

KNOWN_M_NN = [
    {
        "id": "option-universe.M",
        "prefix": "M",
        "registry": "option-universe",
        "kind": "option-card",
        "in_cc0021": True,
        "note": "07-OPTION-UNIVERSE family M (33 ids on the full estate)",
    },
    {
        "id": "architecture-candidates.MECH",
        "prefix": "MECH",
        "historical_prefix": "M",
        "registry": "architecture-candidates",
        "kind": "mechanism-card",
        "in_cc0021": True,
        "note": "13-ARCHITECTURE-CANDIDATES re-prefixed M-NN to MECH-NN on 2026-08-07",
    },
    {
        "id": "deep-research.M",
        "prefix": "M",
        "registry": "deep-research",
        "kind": "deliverable-id",
        "in_cc0021": True,
        "note": "wave3 deep-research SKILL.md Research Harness (M-16)",
    },
    {
        "id": "wave1-register.M",
        "prefix": "M",
        "registry": "wave1-register",
        "kind": "mission-grade",
        "in_cc0021": False,
        "note": "wave1/REGISTER.md single-digit M-1/M-3; known CC-0021 omission",
    },
]

HAND_PIVOT_SNIPPETS = {
    "option-universe.M": ("07-OPTION-UNIVERSE.md", "## M-01 "),
    "architecture-candidates.MECH": ("13-ARCHITECTURE-CANDIDATES.md", "## MECH-01 "),
    "deep-research.M": ("SKILL.md", "Research Harness (M-16)"),
    "wave1-register.M": ("REGISTER.md", "| M-1 |"),
}

CC0021_NAMESPACES = {
    "option-universe.M",
    "architecture-candidates.MECH",
    "deep-research.M",
}


@dataclass
class Hit:
    path: str
    line: int
    prefix: str
    number: str
    token: str
    kind: str
    pattern: str
    registry: str


@dataclass
class Census:
    hits: list[Hit] = field(default_factory=list)
    files_scanned: int = 0
    roots: list[str] = field(default_factory=list)


def logical_registry(rel: str) -> str:
    posix = rel.replace("\\", "/")
    name = Path(posix).name
    lower = posix.lower()
    if "07-option-universe" in lower:
        return "option-universe"
    if "13-architecture-candidates" in lower:
        return "architecture-candidates"
    if "deep-research" in lower and name.upper() == "SKILL.MD":
        return "deep-research"
    if "wave1" in lower and name.upper() == "REGISTER.MD":
        return "wave1-register"
    if "planted-qq/registry-a" in lower:
        return "planted-qq-a"
    if "planted-qq/registry-b" in lower:
        return "planted-qq-b"
    if name == "WORK-UNIT-CATALOG.json":
        return "work-unit-catalog"
    if "dangling-notes" in lower:
        return "dangling-notes"
    parent = str(Path(posix).with_suffix("")).replace("\\", "/")
    return parent


def _iter_unfenced(text: str) -> Iterable[tuple[int, str]]:
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, line


def _decl_patterns(line: str, suffix: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if suffix == ".json":
        for m in DECL_JSON.finditer(line):
            found.append((m.group("tok"), "json-identity-key"))
        return found
    if suffix in {".yml", ".yaml"}:
        m = DECL_YAML.match(line)
        if m:
            found.append((m.group("tok"), "yaml-identity-key"))
        return found
    m = DECL_HEADING.match(line)
    if m:
        found.append((m.group(2), "markdown-heading"))
    m = DECL_TABLE.match(line)
    if m:
        found.append((m.group(1), "markdown-table-first-cell"))
    m = DECL_DEF.match(line)
    if m:
        found.append((m.group(2), "markdown-definition"))
    return found


def scan_file(path: Path, rel: str) -> list[Hit]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    suffix = path.suffix.lower()
    registry = logical_registry(rel)
    hits: list[Hit] = []
    declared_on_line: dict[int, set[str]] = defaultdict(set)
    for i, line in _iter_unfenced(text):
        for tok, pat in _decl_patterns(line, suffix):
            m = TOKEN_RE.fullmatch(tok)
            if not m:
                continue
            prefix, number = m.group(1), m.group(2)
            if prefix in NOISE_PREFIXES:
                continue
            declared_on_line[i].add(tok)
            hits.append(
                Hit(
                    path=rel,
                    line=i,
                    prefix=prefix,
                    number=number,
                    token=tok,
                    kind="declaration",
                    pattern=pat,
                    registry=registry,
                )
            )
        for m in TOKEN_RE.finditer(line):
            tok = m.group(0)
            prefix, number = m.group(1), m.group(2)
            if prefix in NOISE_PREFIXES:
                continue
            if tok in declared_on_line[i]:
                continue
            hits.append(
                Hit(
                    path=rel,
                    line=i,
                    prefix=prefix,
                    number=number,
                    token=tok,
                    kind="reference",
                    pattern="prose-or-non-identity",
                    registry=registry,
                )
            )
    return hits


def walk(roots: list[Path], *, skip_parts: tuple[str, ...] = ()) -> Census:
    census = Census(roots=[str(r) for r in roots])
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIX:
                continue
            if any(part in SKIP_DIR for part in path.parts):
                continue
            posix = path.as_posix()
            if any(part in posix.replace("\\", "/") for part in skip_parts):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = posix
            census.files_scanned += 1
            census.hits.extend(scan_file(path, rel))
    return census


def declarations_by_prefix(census: Census) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for hit in census.hits:
        if hit.kind == "declaration":
            out[hit.prefix].add(hit.registry)
    return dict(out)


def references_by_prefix(census: Census) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for hit in census.hits:
        if hit.kind == "reference":
            out[hit.prefix].add(hit.registry)
    return dict(out)


def colliding(decls: dict[str, set[str]]) -> list[dict]:
    rows = []
    for prefix, regs in sorted(decls.items()):
        if len(regs) >= 2:
            rows.append(
                {
                    "prefix": prefix,
                    "declaring_registry_count": len(regs),
                    "registries": sorted(regs),
                }
            )
    return rows


def dangling(census: Census) -> list[dict]:
    decls = declarations_by_prefix(census)
    refs = references_by_prefix(census)
    rows = []
    for prefix, regs in sorted(refs.items()):
        if prefix in decls:
            continue
        rows.append(
            {
                "prefix": prefix,
                "classification": "DANGLING",
                "reference_registries": sorted(regs),
            }
        )
    return rows


def _hand_pivot_found(roots: list[Path], ns_id: str) -> bool:
    needle_file, snippet = HAND_PIVOT_SNIPPETS[ns_id]
    for root in roots:
        for path in root.rglob(needle_file):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if snippet in text:
                return True
    return False


def known_namespaces(census: Census, roots: list[Path]) -> tuple[list[dict], str]:
    decls = declarations_by_prefix(census)
    method = "declaration-site-pattern"
    rows = []
    misses = 0
    for spec in KNOWN_M_NN:
        regs = decls.get(spec["prefix"], set())
        found = spec["registry"] in regs
        how = "declaration-site-pattern"
        if not found:
            misses += 1
            if _hand_pivot_found(roots, spec["id"]):
                found = True
                how = "hand-enumeration-pivot"
                method = "hand-enumeration-pivot"
        rows.append(
            {
                "id": spec["id"],
                "prefix": spec["prefix"],
                "historical_prefix": spec.get("historical_prefix"),
                "registry": spec["registry"],
                "kind": spec["kind"],
                "found": found,
                "detection": how,
                "in_cc0021_registry": spec["in_cc0021"],
                "note": spec["note"],
            }
        )
    if misses >= 2 and any(not r["found"] for r in rows):
        method = "hand-enumeration-pivot-exhausted"
    return rows, method


def load_cc0021(path: Path) -> dict:
    if not path.is_file():
        return {
            "on_disk": False,
            "reconstructed": True,
            "namespaces": sorted(CC0021_NAMESPACES),
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    nss = []
    for item in doc.get("namespaces") or []:
        if isinstance(item, dict) and item.get("id"):
            nss.append(str(item["id"]))
        elif isinstance(item, str):
            nss.append(item)
    return {"on_disk": True, "reconstructed": False, "namespaces": nss}


def not_in_registry(known_rows: list[dict], cc0021: dict) -> list[dict]:
    registered = set(cc0021.get("namespaces") or [])
    out = []
    for row in known_rows:
        if not row["found"]:
            continue
        in_cc = bool(row.get("in_cc0021_registry") or row.get("in_cc0021_registry"))
        if row["id"] in registered or in_cc:
            continue
        out.append(
            {
                "id": row["id"],
                "prefix": row["prefix"],
                "registry": row["registry"],
                "reason": row["note"],
            }
        )
    # Explicit known omission even if reconstructed registry lists only the three.
    if not any(r["id"] == "wave1-register.M" for r in out):
        wave = next((r for r in known_rows if r["id"] == "wave1-register.M"), None)
        if wave and wave["found"] and "wave1-register.M" not in registered:
            out.append(
                {
                    "id": "wave1-register.M",
                    "prefix": "M",
                    "registry": "wave1-register",
                    "reason": wave["note"],
                }
            )
    return out
