"""Enumerate a built archive. Listing never comes from inclusion rules or a tree.

Credential-shaped filenames are classified by name only. Member bytes are not
read and are never copied into reports.
"""
from __future__ import annotations

import fnmatch
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from constants import REPO, RULES_REL

CACHE_DIRS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".cache",
        "node_modules",
        ".eggs",
        ".venv",
        "venv",
        "vendor",
        "site-packages",
    }
)
TRANSCRIPT_DIRS = frozenset(
    {"transcripts", "transcript", "sessions", "session-logs"}
)
CREDENTIAL_BASENAMES = frozenset(
    {
        ".env",
        "credentials.json",
        "credentials.yml",
        "credentials.yaml",
        "secrets.json",
        "secrets.yml",
        "secrets.yaml",
        ".pypirc",
        ".npmrc",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa.pub",
    }
)
CREDENTIAL_SUFFIXES = (
    ".pem",
    ".p12",
    ".pfx",
    ".keystore",
    ".jks",
)


def load_rules(path: Path | None = None) -> dict[str, Any]:
    p = path or (REPO / RULES_REL)
    return json.loads(p.read_text(encoding="utf-8"))


def parts(path: str) -> list[str]:
    return [x for x in path.replace("\\", "/").split("/") if x and x != "."]


def enumerate_zip(archive: Path) -> list[dict[str, Any]]:
    """Return every file member from the archive. No rules. No source tree."""
    if not archive.is_file():
        raise FileNotFoundError(archive)
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or info.is_dir():
                continue
            entries.append(
                {
                    "path": name,
                    "uncompressed_bytes": int(info.file_size),
                    "compressed_bytes": int(info.compress_size),
                }
            )
    entries.sort(key=lambda e: e["path"])
    return entries


def file_member_count(archive: Path) -> int:
    n = 0
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or info.is_dir():
                continue
            n += 1
    return n


def allowlisted(path: str, globs: list[str]) -> bool:
    rel = path.replace("\\", "/").lstrip("/")
    return any(fnmatch.fnmatch(rel, g) for g in globs)


def is_credential_filename(path: str) -> bool:
    name = parts(path)[-1] if parts(path) else path
    lower = name.lower()
    if lower in CREDENTIAL_BASENAMES or name in CREDENTIAL_BASENAMES:
        return True
    if lower.startswith(".env.") or lower == ".env":
        return True
    if lower.startswith("id_") and not lower.endswith(".md"):
        return True
    return any(lower.endswith(suf) for suf in CREDENTIAL_SUFFIXES)


def classify_path(path: str, size: int, rules: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    rel = path.replace("\\", "/").lstrip("/")
    segs = parts(rel)
    name = segs[-1] if segs else rel
    lower_name = name.lower()

    if ".git" in segs or rel.endswith(".gitmodules"):
        flags.append("repo-metadata")
    if any(s in CACHE_DIRS for s in segs) or lower_name.endswith(
        (".pyc", ".pyo")
    ):
        flags.append("cache")
    if lower_name.endswith(".log") or "logs" in segs:
        flags.append("log")
    if any(s.lower() in TRANSCRIPT_DIRS for s in segs) or (
        lower_name.endswith(".jsonl")
        and ("transcript" in rel.lower() or "session" in rel.lower())
    ) or lower_name.endswith(".transcript"):
        flags.append("transcript")
    if is_credential_filename(rel):
        flags.append("credential-filename")
    ceiling = int(rules["max_single_file_bytes"])
    if size > ceiling:
        flags.append("oversized-file")
    if not allowlisted(rel, list(rules["allowlist_globs"])):
        flags.append("allowlist-miss")
    return sorted(set(flags))


def audit_archive(archive: Path, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or load_rules()
    raw = enumerate_zip(archive)
    rows: list[dict[str, Any]] = []
    by_rule: dict[str, list[str]] = defaultdict(list)
    total_uncomp = 0
    total_comp = 0
    for item in raw:
        flags = classify_path(item["path"], item["uncompressed_bytes"], rules)
        row = {
            "path": item["path"],
            "uncompressed_bytes": item["uncompressed_bytes"],
            "compressed_bytes": item["compressed_bytes"],
            "flags": flags,
        }
        rows.append(row)
        total_uncomp += item["uncompressed_bytes"]
        total_comp += item["compressed_bytes"]
        for flag in flags:
            by_rule[flag].append(item["path"])

    max_bytes = int(rules["max_uncompressed_bytes"])
    max_count = int(rules["max_entry_count"])
    budget_flags: list[str] = []
    if total_uncomp > max_bytes:
        budget_flags.append("size-budget-exceeded")
        by_rule["size-budget-exceeded"].append("*totals*")
    if len(rows) > max_count:
        budget_flags.append("entry-count-exceeded")
        by_rule["entry-count-exceeded"].append("*totals*")

    flagged_by_rule = [
        {"rule": rule, "entries": paths}
        for rule, paths in sorted(by_rule.items())
    ]
    return {
        "archive_path": archive.as_posix(),
        "method": "zipfile.ZipFile.infolist",
        "listed_from_archive": True,
        "listed_from_inclusion_rules": False,
        "listed_from_source_tree": False,
        "contents_inspected": False,
        "entries": rows,
        "totals": {
            "entry_count": len(rows),
            "uncompressed_bytes": total_uncomp,
            "compressed_bytes": total_comp,
        },
        "flagged_by_rule": flagged_by_rule,
        "budget_flags": budget_flags,
        "within_byte_budget": total_uncomp <= max_bytes,
        "within_count_budget": len(rows) <= max_count,
        "member_count_from_infolist": file_member_count(archive),
    }


def dump_report_text(report: dict[str, Any]) -> str:
    """Serialize a report. Must never include planted credential bodies."""
    return json.dumps(report, sort_keys=True, ensure_ascii=True)


def credential_body_leaked(text: str, body: str) -> bool:
    return body in text
