"""Catalog-faithful secret/PII gate facsimiles, instrumented at the open() seam.

IMP-0004, IMP-0458 and IMP-0113 are unbuilt in this worktree (no receipt, no
tools/plugin secret_gate). COVERED is still measured by running the gate
*behaviour* those units specify — gitleaks-style path filters plus a Shannon
pass — and logging every path whose bytes were actually read, never the glob
list. A glob that never matches looks identical to one that matches nothing;
open() logging does not.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

# Synthetic non-credential. Never a real token, never printed past a prefix.
CANARY = "ADV0141_CANARY_SYNTHETIC_NOT_A_CREDENTIAL"
CANARY_PREFIX = CANARY[:4]
CANARY_RE = re.compile(re.escape(CANARY).encode("ascii"))

WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        *{f"COM{i}" for i in range(1, 10)},
        *{f"LPT{i}" for i in range(1, 10)},
    }
)

TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".json",
        ".md",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".env",
        ".jsonl",
        ".js",
        ".mjs",
        ".ts",
        ".cfg",
        ".ini",
    }
)
ARCHIVE_SUFFIXES = frozenset({".zip", ".whl", ".gz", ".tgz", ".tar", ".jar"})
BINARY_SUFFIXES = frozenset({".pyc", ".bin", ".ckpt", ".so", ".o"})

Opener = Callable[[Path], bytes]


def win_ext_len(path: Path) -> str:
    """Windows extended-length prefix; identity on POSIX."""
    p = str(path)
    if os.name != "nt":
        return p
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + str(path.resolve())


def is_reserved_basename(name: str) -> bool:
    stem = name.split(".")[0].upper()
    return stem in WINDOWS_RESERVED or name.upper() in WINDOWS_RESERVED


def default_opener(path: Path) -> bytes:
    with open(win_ext_len(path), "rb") as fh:
        return fh.read()


def shannon_entropy(blob: bytes) -> float:
    if not blob:
        return 0.0
    n = len(blob)
    return -sum((c / n) * math.log2(c / n) for c in Counter(blob).values())


def _prefix_only(match: bytes) -> str:
    text = match.decode("ascii", errors="replace")
    return text[:4]


def scan_bytes(blob: bytes) -> list[dict]:
    """Report path-free hits. Body past a zero-entropy prefix is dropped."""
    hits: list[dict] = []
    for m in CANARY_RE.finditer(blob):
        hits.append(
            {
                "rule": "synthetic-canary",
                "offset": int(m.start()),
                "prefix": _prefix_only(m.group(0)),
            }
        )
    # High-entropy window on long tokens; prefix only, never the body.
    for m in re.finditer(rb"[A-Za-z0-9+/=_\-]{24,}", blob):
        tok = m.group(0)
        if CANARY.encode("ascii") in tok:
            continue
        if shannon_entropy(tok) >= 4.5:
            hits.append(
                {
                    "rule": "high-entropy-token",
                    "offset": int(m.start()),
                    "prefix": tok[:4].decode("ascii", errors="replace"),
                    "entropy": round(shannon_entropy(tok), 3),
                }
            )
    return hits


# Per-gate include/exclude. These are the CONFIGURED globs; COVERED must not
# be derived from them.
GATE_SPECS = (
    {
        "id": "IMP-0004",
        "role": "credential-exposure-pre-emit",
        "exclude_dirs": frozenset(
            {"excluded_by_config", "node_modules", ".git", "__pycache__", ".cache"}
        ),
        "skip_suffixes": ARCHIVE_SUFFIXES | BINARY_SUFFIXES,
        "include_suffixes": TEXT_SUFFIXES,
        "include_basenames": frozenset({".env"}),
    },
    {
        "id": "IMP-0458",
        "role": "secret-scrub-corpus",
        "exclude_dirs": frozenset({"excluded_by_config", "node_modules", ".git"}),
        "skip_suffixes": ARCHIVE_SUFFIXES | BINARY_SUFFIXES,
        "include_suffixes": frozenset({".json", ".jsonl", ".md", ".txt", ".yml"}),
        "include_basenames": frozenset(),
    },
    {
        "id": "IMP-0113",
        "role": "package-linter-secrets",
        "exclude_dirs": frozenset({"excluded_by_config", "nested", "reserved"}),
        "skip_suffixes": ARCHIVE_SUFFIXES | BINARY_SUFFIXES,
        "include_suffixes": TEXT_SUFFIXES,
        "include_basenames": frozenset(),
        "only_under": "pkg_src",
    },
)


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def should_scan(spec: dict, root: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    if is_reserved_basename(path.name):
        return False
    rel = _rel(root, path)
    parts = rel.split("/")
    if any(p in spec["exclude_dirs"] for p in parts):
        return False
    only = spec.get("only_under")
    if only and not rel.startswith(only.rstrip("/") + "/") and rel != only:
        return False
    suf = path.suffix.lower()
    if suf in spec["skip_suffixes"]:
        return False
    if path.name in spec["include_basenames"]:
        return True
    return suf in spec["include_suffixes"]


def walk_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            yield Path(dirpath) / name


def run_one_gate(
    spec: dict, root: Path, opener: Opener
) -> tuple[list[str], list[dict]]:
    opened: list[str] = []
    findings: list[dict] = []
    for path in walk_files(root):
        if not should_scan(spec, root, path):
            continue
        blob = opener(path)
        opened.append(_rel(root, path))
        for hit in scan_bytes(blob):
            rec = dict(hit)
            rec["gate"] = spec["id"]
            rec["path"] = _rel(root, path)
            findings.append(rec)
    return opened, findings


def run_all_gates(root: Path, opener: Opener | None = None) -> dict:
    opener = opener or default_opener
    union: dict[str, None] = {}
    findings: list[dict] = []
    per_gate: list[dict] = []
    for spec in GATE_SPECS:
        opened, hits = run_one_gate(spec, root, opener)
        for p in opened:
            union[p] = None
        findings.extend(hits)
        per_gate.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "opened": opened,
                "finding_count": len(hits),
            }
        )
    return {
        "opened_paths": list(union.keys()),
        "findings": findings,
        "per_gate": per_gate,
    }
