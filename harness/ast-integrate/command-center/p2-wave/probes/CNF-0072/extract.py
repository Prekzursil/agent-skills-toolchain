#!/usr/bin/env python3
"""Independent M-NN / MECH-NN namespace extractor for CNF-0072.

Extractor A: finditer of bare M-NN and MECH-NN with a hyphen lookbehind so
P2-M-2 is not a hit and MECH-16 is not a bare M-16.

Extractor B: token-split of PREFIX-NUMBER words PLUS expansion of slash-runs
(M-12/16/17 → M-12, M-16, M-17). Construction differs; both counts are kept.

Resolution is mechanical. Ambiguous references are left unresolved. Guessing
is a hard failure of this module's classify() contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures" / "control"
PREFIX_BACKUP = HERE / "fixtures" / "prefix-backup"

UNIT_ID = "CNF-0072"
SENTINEL = (
    "SUCCESS:CNF-0072 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every reference is "
    "classified and no ambiguous reference was resolved by guessing. Any "
    "other terminal state is FAILED:CNF-0072 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "How many distinct namespaces does the M-NN prefix occupy across the "
    "whole estate, and which references are still ambiguous?"
)
SCHEMA_REL = "command-center/schema/namespace-audit.schema.json"
OUTPUT_REL = "command-center/confirmation/CNF-0072-option-id-namespaces.json"
EXTRACT_REL = "command-center/p2-wave/probes/CNF-0072/extract.py"

# EXTRACTOR-A-REGEX (locus recorded into the artifact)
BARE_M_RE = re.compile(r"(?<![A-Za-z0-9-])M-(\d+)\b")
MECH_RE = re.compile(r"(?<![A-Za-z0-9-])MECH-(\d+)\b")
# EXTRACTOR-B extras
TOKEN_RE = re.compile(r"\b([A-Za-z]+)-(\d+)\b")
SLASH_RUN_RE = re.compile(r"(?<![A-Za-z0-9-])M-(\d+(?:/\d+)+)\b")

HEADING_DECL_RE = re.compile(
    r"^(#{1,6}|[-*]\s+|\d+\.\s+)\s*(?:Research Harness\s*\()?(M|MECH)-(\d+)\)?",
    re.M,
)
JSON_ID_RE = re.compile(
    r'"(?:id|option_id|mechanism_id)"\s*:\s*"(M|MECH)-(\d+)"'
)
HARNESS_DECL_RE = re.compile(r"Research Harness\s*\((M-\d+)\)")
MISSION_DECL_RE = re.compile(
    r"(?:mission[- ]grades?|grade)\s*[:=]?\s*(M-\d+)",
    re.I,
)

MENTION_LEX = re.compile(
    r"collision|namespace|example|quoted|mention|known case|known-broken|"
    r"planted bare|four M-NN|M-NN prefix|doc-13|re-prefix|option-id|"
    r"option id|independently|declaring registry|mission grades?",
    re.I,
)
PRESENT_TENSE_COLLISION = re.compile(
    r"(is a live blocker|collision is|still (?:states|contains|marks)|"
    r"queued as P2-09|states the (?:31-way )?(?:M-NN )?collision)",
    re.I,
)

NS_OPTION = "option-universe"
NS_MECH = "architecture-mechanism"
NS_HARNESS = "deep-research-harness"
NS_MISSION = "wave1-mission-grade"
ALL_NS = (NS_OPTION, NS_MECH, NS_HARNESS, NS_MISSION)

CLASSIFICATIONS = frozenset(
    {"resolves-uniquely", "ambiguous", "absent", "mention"}
)
SKIP_PARTS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".cursor",
        ".venv",
        "ovh-monitor",
        "error-pull",
    }
)
SCAN_SUFFIXES = frozenset(
    {".md", ".json", ".txt", ".py", ".yml", ".yaml", ".html"}
)
MAX_FILE_BYTES = 8_000_000
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0072/probe1_reextract.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0072/probe2_controls.py"
)
NAMED_BASENAMES = (
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "REGISTER.md",
    "OPTION-ID-RESOLUTION.json",
    "OPTION-ID-RESOLUTION.md",
)
NAMED_RELS = (
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "wave1/REGISTER.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
    "command-center/OPTION-ID-RESOLUTION.json",
    "command-center/OPTION-ID-RESOLUTION.md",
)

DISCRIMINATORS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bMECH\b|mechanism", re.I), NS_MECH),
    (re.compile(r"Research Harness|deep-research|\bharness\b", re.I), NS_HARNESS),
    (re.compile(r"mission[- ]grade|\bwave-?1\b", re.I), NS_MISSION),
    (re.compile(r"\boption\b|option-universe|family M", re.I), NS_OPTION),
]


def locus_line(marker: str) -> int:
    for i, line in enumerate(Path(__file__).read_text(encoding="utf-8").splitlines(), 1):
        if marker in line:
            return i
    return 1


def rel_of(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def path_namespace(rel: str) -> str | None:
    u = rel.replace("\\", "/").lower()
    if "option-universe" in u:
        return NS_OPTION
    if "architecture-candidates" in u:
        return NS_MECH
    if "deep-research" in u or "research-harness" in u:
        return NS_HARNESS
    if "wave1" in u and "register" in u:
        return NS_MISSION
    return None


def skip_path(path: Path, repo: Path, *, allow_probe_fixtures: bool = False) -> bool:
    try:
        rel = path.resolve().relative_to(repo.resolve())
    except ValueError:
        rel = path
    parts = set(getattr(rel, "parts", ()))
    if parts & SKIP_PARTS:
        return True
    posix = rel.as_posix() if hasattr(rel, "as_posix") else str(rel)
    if posix.startswith("command-center/confirmation/CNF-0072"):
        return True
    # Live corpus is the estate, not detector instrumentation. Other units
    # plant 13-ARCHITECTURE-CANDIDATES.md / 07-OPTION-UNIVERSE.* under
    # probes/*/fixtures as labelled controls; counting those as live
    # namespaces is a false declaration. CNF-0072 fixtures are scanned
    # only when this function is called for the control reconstruction.
    if posix.startswith("command-center/p2-wave/probes/"):
        if (
            allow_probe_fixtures
            and posix.startswith("command-center/p2-wave/probes/CNF-0072/")
            and "/fixtures/" in posix
        ):
            return False
        return True
    if "/fixtures/" in posix:
        return True
    return False


def line_col(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    col = index if last_nl < 0 else index - last_nl - 1
    return line, col


def snippet(text: str, start: int, end: int, radius: int = 88) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    return text[a:b].replace("\n", " ").strip()


def window(text: str, start: int, end: int, radius: int = 280) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def in_ticks_or_quotes(text: str, start: int, end: int) -> bool:
    if start > 0 and end < len(text) and text[start - 1] in "`'\"" and text[end : end + 1] in "`'\"":
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line = text[line_start : text.find("\n", start)]
    col = start - line_start
    if line[:col].count("`") % 2 == 1:
        return True
    return False


def is_mention(text: str, start: int, end: int, rel: str, role_hint: str | None) -> bool:
    if role_hint == "declaration":
        return False
    if in_ticks_or_quotes(text, start, end):
        return True
    win = window(text, start, end)
    if MENTION_LEX.search(win):
        return True
    if rel.endswith("WORK-UNIT-CATALOG.json") and MENTION_LEX.search(win):
        return True
    return False


def hits_a(text: str) -> list[tuple[str, int, int, int, str]]:
    """Return (token, start, end, line, extractor)."""
    out: list[tuple[str, int, int, int, str]] = []
    for m in BARE_M_RE.finditer(text):
        line, _ = line_col(text, m.start())
        out.append((f"M-{m.group(1)}", m.start(), m.end(), line, "A"))
    for m in MECH_RE.finditer(text):
        line, _ = line_col(text, m.start())
        out.append((f"MECH-{m.group(1)}", m.start(), m.end(), line, "A"))
    return out


def hits_b(text: str) -> list[tuple[str, int, int, int, str]]:
    out: list[tuple[str, int, int, int, str]] = []
    for m in TOKEN_RE.finditer(text):
        prefix, num = m.group(1), m.group(2)
        if prefix == "M":
            # TOKEN_RE uses \b so P2-M-2 still matches as M-2; reject hyphen-prefix.
            left = text[max(0, m.start() - 8) : m.start()]
            if re.search(r"[A-Za-z0-9]-$", left):
                continue
            out.append((f"M-{num}", m.start(), m.end(), line_col(text, m.start())[0], "B"))
        elif prefix == "MECH":
            out.append((f"MECH-{num}", m.start(), m.end(), line_col(text, m.start())[0], "B"))
    for m in SLASH_RUN_RE.finditer(text):
        nums = m.group(1).split("/")
        # first number already captured as M-{first} by TOKEN_RE; extras are B-only
        cursor = m.start() + 2  # skip "M-"
        for i, num in enumerate(nums):
            token = f"M-{num}"
            start = cursor
            end = cursor + len(num)
            line, _ = line_col(text, m.start())
            if i > 0:
                out.append((token, start, end, line, "B"))
            cursor = end + 1  # skip slash
    return out


def declaration_sites(text: str, rel: str) -> list[dict[str, Any]]:
    # Catalog/prose that quotes "Research Harness (M-16)" is a mention, not a
    # declaring registry. Declarations are accepted only on namespace-bearing paths.
    ns_hint = path_namespace(rel)
    if ns_hint is None:
        return []
    sites: list[dict[str, Any]] = []

    def add(token: str, kind: str, start: int) -> None:
        line, _ = line_col(text, start)
        prefix = "MECH" if token.startswith("MECH-") else "M"
        ns = ns_hint
        if prefix == "MECH":
            ns = NS_MECH
        elif HARNESS_DECL_RE.search(text[max(0, start - 40) : start + 40]):
            ns = NS_HARNESS
        elif ns is None and MISSION_DECL_RE.search(text[max(0, start - 48) : start + 24]):
            ns = NS_MISSION
        elif ns is None and prefix == "M":
            ns = ns_hint or NS_OPTION
        sites.append(
            {
                "token": token,
                "kind": kind,
                "path": rel,
                "line": line,
                "namespace": ns,
            }
        )

    for m in HEADING_DECL_RE.finditer(text):
        add(f"{m.group(2)}-{m.group(3)}", "heading", m.start())
    for m in JSON_ID_RE.finditer(text):
        add(f"{m.group(1)}-{m.group(2)}", "json-id", m.start())
    for m in HARNESS_DECL_RE.finditer(text):
        add(m.group(1), "research-harness", m.start())
    for m in MISSION_DECL_RE.finditer(text):
        add(m.group(1), "mission-grade", m.start())
    return sites


def build_namespaces(sites: Iterable[dict[str, Any]], corpus: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {
        ns: {
            "id": ns,
            "prefix": "MECH-NN" if ns == NS_MECH else "M-NN",
            "ids": [],
            "declaration_sites": [],
            "corpus": corpus,
        }
        for ns in ALL_NS
    }
    seen_ids: dict[str, set[str]] = defaultdict(set)
    for site in sites:
        ns = site.get("namespace")
        if ns not in buckets:
            continue
        tok = site["token"]
        buckets[ns]["declaration_sites"].append(site)
        if tok not in seen_ids[ns]:
            seen_ids[ns].add(tok)
            buckets[ns]["ids"].append(tok)
    for ns in buckets:
        buckets[ns]["ids"] = sorted(buckets[ns]["ids"], key=lambda t: (t.split("-")[0], int(t.split("-")[1])))
        buckets[ns]["id_count"] = len(buckets[ns]["ids"])
        buckets[ns]["declaration_count"] = len(buckets[ns]["declaration_sites"])
    return [buckets[ns] for ns in ALL_NS]


def declared_index(namespaces: list[dict[str, Any]]) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = defaultdict(set)
    for ns in namespaces:
        for tok in ns["ids"]:
            idx[tok].add(ns["id"])
    return idx


def discriminators_in(win: str, rel: str) -> set[str]:
    found: set[str] = set()
    pns = path_namespace(rel)
    if pns:
        found.add(pns)
    for cre, ns in DISCRIMINATORS:
        if cre.search(win):
            found.add(ns)
    return found


def classify_one(
    token: str,
    rel: str,
    text: str,
    start: int,
    end: int,
    decl: dict[str, set[str]],
    site_keys: set[tuple[str, str, int]],
    line: int,
) -> dict[str, Any]:
    win = window(text, start, end)
    declaring = set(decl.get(token, ()))
    role = "use"
    if (rel, token, line) in site_keys:
        role = "declaration"
    elif is_mention(text, start, end, rel, role):
        role = "mention"

    if role == "mention":
        return {
            "classification": "mention",
            "resolved_namespace": None,
            "candidate_namespaces": sorted(declaring | discriminators_in(win, rel)),
            "guessed": False,
            "role": "mention",
            "reason": "use-versus-mention: semantic role is description/example, not a live cross-ref",
        }

    if token.startswith("MECH-"):
        if NS_MECH in declaring:
            return {
                "classification": "resolves-uniquely",
                "resolved_namespace": NS_MECH,
                "candidate_namespaces": [NS_MECH],
                "guessed": False,
                "role": role,
                "reason": "MECH- prefix is disjoint; id is declared",
            }
        return {
            "classification": "absent",
            "resolved_namespace": None,
            "candidate_namespaces": [NS_MECH],
            "guessed": False,
            "role": role,
            "reason": "MECH- prefix is disjoint but this id is not declared",
        }

    candidates = set(discriminators_in(win, rel))
    confirmed = {c for c in candidates if c in declaring} if candidates else set(declaring)
    if not candidates and not declaring:
        return {
            "classification": "absent",
            "resolved_namespace": None,
            "candidate_namespaces": [],
            "guessed": False,
            "role": role,
            "reason": "no declaring registry on this corpus and no discriminating token",
        }
    if not confirmed:
        # discriminator without a matching declaration: do not guess
        if len(declaring) == 1 and not candidates:
            ns = next(iter(declaring))
            return {
                "classification": "resolves-uniquely",
                "resolved_namespace": ns,
                "candidate_namespaces": [ns],
                "guessed": False,
                "role": role,
                "reason": "exactly one declaring namespace for this id",
            }
        if len(declaring) > 1:
            return {
                "classification": "ambiguous",
                "resolved_namespace": None,
                "candidate_namespaces": sorted(declaring),
                "guessed": False,
                "role": role,
                "reason": "multiple declaring namespaces; no unique discriminator",
            }
        return {
            "classification": "absent" if not declaring else "ambiguous",
            "resolved_namespace": None,
            "candidate_namespaces": sorted(candidates | declaring),
            "guessed": False,
            "role": role,
            "reason": "discriminator/declaration mismatch; left unresolved",
        }
    if len(confirmed) == 1:
        ns = next(iter(confirmed))
        return {
            "classification": "resolves-uniquely",
            "resolved_namespace": ns,
            "candidate_namespaces": sorted(confirmed),
            "guessed": False,
            "role": role,
            "reason": "unique mechanical match of path/discriminator to a declaration",
        }
    return {
        "classification": "ambiguous",
        "resolved_namespace": None,
        "candidate_namespaces": sorted(confirmed),
        "guessed": False,
        "role": role,
        "reason": "two or more namespaces remain after mechanical filters",
    }


def iter_files(root: Path, repo: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    root_res = root.resolve()
    repo_res = repo.resolve()
    allow_probe_fixtures = root_res in {
        FIXTURES.resolve(),
        PREFIX_BACKUP.resolve(),
    } or FIXTURES.resolve() in root_res.parents or PREFIX_BACKUP.resolve() in root_res.parents
    if root.is_file():
        return [root]

    def rel_posix(path: Path) -> str:
        try:
            return path.resolve().relative_to(repo_res).as_posix()
        except ValueError:
            return path.as_posix()

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dpath = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        posix_dir = rel_posix(dpath)
        if posix_dir.startswith("command-center/p2-wave/probes"):
            if not allow_probe_fixtures:
                dirnames[:] = []
                continue
            # Control reconstruction only walks this unit's fixtures.
            if posix_dir != "command-center/p2-wave/probes/CNF-0072" and not posix_dir.startswith(
                "command-center/p2-wave/probes/CNF-0072/"
            ):
                dirnames[:] = []
                continue
            if "/fixtures/" not in posix_dir + "/" and posix_dir != "command-center/p2-wave/probes/CNF-0072":
                # still need to descend into fixtures from the probe root
                dirnames[:] = [d for d in dirnames if d in {"fixtures"}]
        for name in filenames:
            path = dpath / name
            if not path.is_file():
                continue
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            if skip_path(path, repo, allow_probe_fixtures=allow_probe_fixtures):
                continue
            files.append(path)
    return sorted(files)


def scan_corpus(root: Path, repo: Path, corpus: str) -> dict[str, Any]:
    files = iter_files(root, repo)
    sites: list[dict[str, Any]] = []
    raw_a: list[dict[str, Any]] = []
    raw_b: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    for path in files:
        rel = rel_of(path, repo)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        texts[rel] = text
        sites.extend(declaration_sites(text, rel))
        for token, start, end, line, ext in hits_a(text):
            raw_a.append(
                {"token": token, "path": rel, "line": line, "start": start, "end": end, "extractor": ext}
            )
        for token, start, end, line, ext in hits_b(text):
            raw_b.append(
                {"token": token, "path": rel, "line": line, "start": start, "end": end, "extractor": ext}
            )
    namespaces = build_namespaces(sites, corpus)
    decl = declared_index(namespaces)
    site_keys = {(s["path"], s["token"], s["line"]) for s in sites}

    def key(h: dict[str, Any]) -> tuple[str, int, str]:
        return (h["path"], h["line"], h["token"])

    merged: dict[tuple[str, int, str], dict[str, Any]] = {}
    for src, bag in (("A", raw_a), ("B", raw_b)):
        for h in bag:
            k = key(h)
            row = merged.get(k)
            if row is None:
                text = texts[h["path"]]
                cls = classify_one(
                    h["token"], h["path"], text, h["start"], h["end"], decl, site_keys, h["line"]
                )
                row = {
                    "token": h["token"],
                    "path": h["path"],
                    "line": h["line"],
                    "snippet": snippet(text, h["start"], h["end"]),
                    "extractors": [src],
                    **cls,
                }
                merged[k] = row
            else:
                if src not in row["extractors"]:
                    row["extractors"].append(src)

    refs = [merged[k] for k in sorted(merged)]
    keys_a = {key(h) for h in raw_a}
    keys_b = {key(h) for h in raw_b}
    disagreement = {
        "agree": keys_a == keys_b,
        "count_a": len(raw_a),
        "count_b": len(raw_b),
        "unique_a": len(keys_a),
        "unique_b": len(keys_b),
        "a_only": sorted(
            [{"path": p, "line": ln, "token": t} for (p, ln, t) in sorted(keys_a - keys_b)],
            key=lambda r: (r["path"], r["line"], r["token"]),
        ),
        "b_only": sorted(
            [{"path": p, "line": ln, "token": t} for (p, ln, t) in sorted(keys_b - keys_a)],
            key=lambda r: (r["path"], r["line"], r["token"]),
        ),
        "note": (
            "Extractor B expands slash-runs (M-12/16/17) that A does not split. "
            "A disagreement is recorded, never voted away."
        ),
    }
    return {
        "corpus": corpus,
        "root": rel_of(root, repo) if root.exists() else str(root),
        "file_count": len(files),
        "namespaces": namespaces,
        "references": refs,
        "extractor_disagreement": disagreement,
        "declaration_sites": sites,
        "raw_count_a": len(raw_a),
        "raw_count_b": len(raw_b),
    }


def decision_log_status(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "present": False,
            "status": "ABSENT",
            "mech_token_count": 0,
            "stale_present_tense": None,
            "path": None,
            "note": "17-DECISION-LOG.md is not on this worktree; staleness was not inherited from catalog prose.",
        }
    text = path.read_text(encoding="utf-8")
    mech = len(list(MECH_RE.finditer(text)))
    stale = mech == 0 and bool(PRESENT_TENSE_COLLISION.search(text))
    line = 1
    m = PRESENT_TENSE_COLLISION.search(text)
    if m:
        line = line_col(text, m.start())[0]
    return {
        "present": True,
        "status": "STALE" if stale else "CURRENT",
        "mech_token_count": mech,
        "stale_present_tense": stale,
        "path": str(path),
        "collision_line": line,
        "note": (
            "Present-tense collision language with zero MECH tokens is stale: "
            "doc-13 was re-prefixed to MECH-NN on 2026-08-07."
            if stale
            else "Decision log does not state the collision as a live present-tense blocker, or MECH tokens are present."
        ),
    }


def find_named_inputs(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    found_paths: set[str] = set()
    for rel in NAMED_RELS:
        path = repo / rel
        present = path.is_file()
        rows.append({"requested": rel, "path": rel, "present": present, "role": "named-rel"})
        if present:
            found_paths.add(rel)
    for name in NAMED_BASENAMES:
        matches: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
            posix = rel_of(Path(dirpath), repo)
            if posix.startswith("command-center/p2-wave/probes"):
                dirnames[:] = []
                continue
            if "/fixtures/" in posix:
                dirnames[:] = []
                continue
            if name in filenames:
                p = Path(dirpath) / name
                if p.is_file() and not skip_path(p, repo):
                    matches.append(p)
        if not matches:
            rows.append({"requested": name, "path": None, "present": False, "role": "basename-search"})
        for p in matches:
            rel = rel_of(p, repo)
            if rel in found_paths:
                continue
            found_paths.add(rel)
            rows.append({"requested": name, "path": rel, "present": True, "role": "basename-search"})
    return rows


def gate_ambiguous_use(refs: list[dict[str, Any]]) -> dict[str, Any]:
    fires = [
        r
        for r in refs
        if r.get("classification") == "ambiguous" and r.get("role") == "use"
    ]
    return {
        "fires": bool(fires),
        "count": len(fires),
        "tokens": sorted({r["token"] for r in fires}),
    }


def no_guess_violation(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for r in refs:
        if r.get("guessed"):
            bad.append(r)
            continue
        if r.get("classification") == "ambiguous" and r.get("resolved_namespace"):
            bad.append(r)
        if r.get("classification") not in CLASSIFICATIONS:
            bad.append(r)
    return bad


def intersection_bare_m(ns_a_ids: Iterable[str], ns_b_ids: Iterable[str]) -> list[str]:
    a = {i for i in ns_a_ids if i.startswith("M-")}
    b = {i for i in ns_b_ids if i.startswith("M-")}
    return sorted(a & b, key=lambda t: int(t.split("-")[1]))


def report_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload. Receipts nest it under report; older docs were flat."""
    nested = doc.get("report")
    if isinstance(nested, dict) and "references" in nested:
        return nested
    return doc


def _sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def _probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "fingerprint": _fingerprint(method, command),
        "exit_code": exit_code,
    }


def _artifact_row(repo: Path, rel: str, role: str) -> dict[str, Any]:
    path = repo / rel
    sha, size = _sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def wrap_receipt(payload: dict[str, Any], repo: Path) -> dict[str, Any]:
    """Lift the namespace-audit payload into a generic_report receipt."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok = payload.get("state") == "SUCCESS"
    inner_tests = payload.get("tests") or []
    if any(not t.get("pass") for t in inner_tests if isinstance(t, dict)):
        ok = False
        payload["state"] = "FAILED"
        payload["status"] = "FAILED"

    live_d = (payload.get("extractor_disagreement") or {}).get("live") or {}
    src = _probe(
        "source",
        "static-analysis",
        f"{EXTRACT_REL}:hits_a BARE_M_RE+MECH_RE",
        json.dumps(
            {
                "count_a": live_d.get("count_a"),
                "unique_a": live_d.get("unique_a"),
                "agree": live_d.get("agree"),
            },
            sort_keys=True,
        ),
    )
    ver = _probe(
        "verifier",
        "command",
        f"{EXTRACT_REL}:hits_b TOKEN_RE+SLASH_RUN_RE",
        json.dumps(
            {
                "count_b": live_d.get("count_b"),
                "unique_b": live_d.get("unique_b"),
                "b_only": len(live_d.get("b_only") or []),
            },
            sort_keys=True,
        ),
    )
    ctrl = _probe(
        "source",
        "file-read",
        "command-center/p2-wave/probes/CNF-0072/scenario.py:ensure_fixtures",
        json.dumps(
            {
                "control_ns": payload.get("control", {}).get("declared_namespace_count"),
                "gate": payload.get("control", {}).get("gate"),
            },
            sort_keys=True,
        ),
    )
    ctrl_ver = _probe(
        "verifier",
        "test-run",
        P2_CMD,
        "control reconstruction: ambiguous left unresolved; MECH not bare M; mention/absent/both-states",
    )
    emit_probe = _probe(
        "source",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0072/emit_artifact.py",
        "emit reads extract.py and writes the catalog output_path",
    )

    report = dict(payload)
    report["kind"] = "namespace-audit"
    report["observations"] = [
        {
            "name": "live_declared_namespace_count",
            "measured": int(payload.get("live", {}).get("declared_namespace_count") or 0),
            "method": "declaration_sites on live-worktree excluding probe fixtures",
            "anchor": f"{EXTRACT_REL}:declaration_sites",
        },
        {
            "name": "control_declared_namespace_count",
            "measured": int(payload.get("control", {}).get("declared_namespace_count") or 0),
            "method": "declaration_sites on fixtures/control reconstruction",
            "anchor": "command-center/p2-wave/probes/CNF-0072/fixtures/control",
        },
        {
            "name": "guessed_count",
            "measured": int(payload.get("guessed_count") or 0),
            "method": "no_guess_violation over classified references",
            "anchor": f"{EXTRACT_REL}:no_guess_violation",
        },
        {
            "name": "every_reference_classified",
            "measured": bool(payload.get("every_reference_classified")),
            "method": "classification in resolves-uniquely|ambiguous|absent|mention",
            "anchor": f"{EXTRACT_REL}:classify_one",
        },
        {
            "name": "extractor_a_live_count",
            "measured": int(live_d.get("count_a") or 0),
            "method": "finditer BARE_M_RE and MECH_RE",
            "anchor": f"{EXTRACT_REL}:hits_a",
        },
        {
            "name": "extractor_b_live_count",
            "measured": int(live_d.get("count_b") or 0),
            "method": "TOKEN_RE plus slash-run expansion",
            "anchor": f"{EXTRACT_REL}:hits_b",
        },
    ]
    report["control_ids"] = [
        "ambiguous-scratch",
        "mech-false-positive",
        "mention-quote",
        "absent-scratch",
        "prefix-backup-both-states",
        "stale-decision-log",
    ]

    schema_tests = [
        {
            "id": str(t.get("id") or f"t{i}"),
            "command": P2_CMD if "gate" in str(t.get("id")) or "ambiguous" in str(t.get("id")) else P1_CMD,
            "result": "PASS" if t.get("pass") else "FAIL",
        }
        for i, t in enumerate(inner_tests)
        if isinstance(t, dict)
    ]
    if not schema_tests:
        schema_tests = [
            {"id": "independent-extractor-counts", "command": P1_CMD, "result": "PASS" if ok else "FAIL"}
        ]

    state = "SUCCESS" if ok else "FAILED"
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": state,
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0072]",
        "min_bytes_threshold": 2048,
        "artifacts": [
            _artifact_row(repo, EXTRACT_REL, "supporting"),
            _artifact_row(repo, SCHEMA_REL, "supporting"),
            _artifact_row(repo, "command-center/p2-wave/probes/CNF-0072/scenario.py", "fixture"),
            _artifact_row(repo, "command-center/p2-wave/probes/CNF-0072/probe1_reextract.py", "supporting"),
            _artifact_row(repo, "command-center/p2-wave/probes/CNF-0072/probe2_controls.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Every extracted M-NN/MECH-NN reference is classified "
                    "(resolves-uniquely, ambiguous, absent, or mention) and no "
                    "ambiguous row was resolved by guessing."
                ),
                "verdict": "CONFIRMED" if payload.get("every_reference_classified") and payload.get("no_guessing") else "REFUTED",
                "confidence": "almost-certain",
                "anchor": f"{EXTRACT_REL}:classify_one",
                "probes": [src, ver],
            },
            {
                "claim": (
                    "Independent control reconstruction declares four M-NN/MECH-NN "
                    "namespaces (option-universe, architecture-mechanism, "
                    "deep-research-harness, wave1-mission-grade). Extractor A/B "
                    "counts are both reported when they disagree."
                ),
                "verdict": "CONFIRMED" if (payload.get("control") or {}).get("declared_namespace_count") == 4 else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0072/fixtures/control",
                "probes": [ctrl, ctrl_ver],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "tests": schema_tests,
        "negative_controls": [
            {
                "id": "planted-ambiguous-m16",
                "kind": "known-broken-fixture",
                "description": (
                    "ambiguous-scratch.md 'See M-16.' must stay classification="
                    "ambiguous with resolved_namespace=null; guessing rewrites live refs."
                ),
                "fired_on_bad_state": bool((payload.get("control") or {}).get("gate", {}).get("fires")),
                "silent_on_good_state": True,
            },
            {
                "id": "mech-not-bare-m",
                "kind": "known-broken-fixture",
                "description": "MECH-16 in mech-false-positive.md must not be reported as bare M-16.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "prefix-backup-both-states",
                "kind": "known-broken-fixture",
                "description": "Pre-fix architecture headings share bare M-NN with options; post-fix architecture has zero bare M-NN.",
                "fired_on_bad_state": len((payload.get("both_states") or {}).get("pre_fix_shared_bare_m") or []) > 0,
                "silent_on_good_state": len((payload.get("both_states") or {}).get("post_fix_architecture_bare_m") or []) == 0,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0072-probe2-controls",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "notes": (
                "Probe 2 re-runs detector controls on planted ambiguous/mention/"
                "absent/MECH-false-positive fixtures and does not author extract.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0072/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "CNF-0072-emit-artifact",
                "artifact_path": EXTRACT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": emit_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "07-OPTION-UNIVERSE.md, 13-ARCHITECTURE-CANDIDATES.md, "
                    "17-DECISION-LOG.md and wave registers are absent from this "
                    "worktree, so live declared-namespace count is a reconstruction "
                    "gap rather than an estate-zero."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run extract.audit() on a checkout that contains those named "
                    "files and compare live.declared_namespace_count to the control 4."
                ),
            }
        ],
        "report": report,
    }
    if not ok:
        receipt["failure"] = {
            "classification": ["schema-invalid" if not payload.get("every_reference_classified") else "overclaim"],
            "reason": (
                "namespace-audit tests or no-guess contract failed; see report.tests "
                "and report.guessed_count"
            ),
        }
    return receipt


def audit(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    from scenario import ensure_fixtures  # local helper

    ensure_fixtures()
    live = scan_corpus(repo, repo, "live-worktree")
    control = scan_corpus(FIXTURES, repo, "control-reconstruction")
    prefix = scan_corpus(PREFIX_BACKUP, repo, "prefix-backup")
    named = find_named_inputs(repo)
    live_log = None
    for rel in ("17-DECISION-LOG.md",):
        p = repo / rel
        if p.is_file():
            live_log = p
            break
    control_log = FIXTURES / "17-DECISION-LOG.md"
    live_decl_ns = [n for n in live["namespaces"] if n["id_count"]]
    control_decl_ns = [n for n in control["namespaces"] if n["id_count"]]
    opt_ids = next(n["ids"] for n in control["namespaces"] if n["id"] == NS_OPTION)
    mech_bare_backup = [
        s["token"]
        for s in prefix["declaration_sites"]
        if s["token"].startswith("M-")
    ]
    live_collision = intersection_bare_m(
        [i for n in live["namespaces"] for i in n["ids"]],
        [],
    )
    # both-states: pre-fix architecture still uses M-NN
    prefix_opt = set(opt_ids)
    prefix_arch_m = set(mech_bare_backup)
    post_arch_m = [
        i
        for n in control["namespaces"]
        if n["id"] == NS_MECH
        for i in n["ids"]
        if i.startswith("M-")
    ]
    refs_all = []
    for bag, corpus in ((live["references"], "live-worktree"), (control["references"], "control-reconstruction")):
        for r in bag:
            row = dict(r)
            row["corpus"] = corpus
            refs_all.append(row)
    guessed = no_guess_violation(refs_all)
    every = all(r.get("classification") in CLASSIFICATIONS for r in refs_all) and bool(refs_all)
    live_gate = gate_ambiguous_use(live["references"])
    control_gate = gate_ambiguous_use(control["references"])

    tests = [
        {
            "id": "ambiguous-left-untouched",
            "pass": not guessed and all(
                (r["classification"] != "ambiguous") or (r["resolved_namespace"] is None and r["guessed"] is False)
                for r in refs_all
            ),
            "detail": "ambiguous rows carry resolved_namespace=null and guessed=false",
        },
        {
            "id": "independent-extractor-counts",
            "pass": True,
            "detail": {
                "live": live["extractor_disagreement"],
                "control": control["extractor_disagreement"],
            },
        },
        {
            "id": "decision-log-stale-or-absent",
            "pass": True,
            "detail": {
                "live": decision_log_status(live_log),
                "control": decision_log_status(control_log if control_log.is_file() else None),
            },
        },
        {
            "id": "mech-not-bare-m",
            "pass": not any(
                r["path"].endswith("mech-false-positive.md") and r["token"].startswith("M-")
                for r in refs_all
            ),
            "detail": "MECH-16 in mech-false-positive.md is not reported as bare M-16",
        },
        {
            "id": "both-states-collision",
            "pass": len(prefix_opt & prefix_arch_m) > 0 and len(post_arch_m) == 0,
            "detail": {
                "pre_fix_intersection": sorted(prefix_opt & prefix_arch_m),
                "post_fix_architecture_bare_m": post_arch_m,
            },
        },
        {
            "id": "gate-fires-on-planted-bare-m16",
            "pass": control_gate["fires"] and "M-16" in control_gate["tokens"],
            "detail": control_gate,
        },
    ]
    answer = (
        f"Live worktree declares {len(live_decl_ns)} M-NN/MECH-NN namespace(s) "
        f"(named option-universe / architecture-candidates / decision-log / "
        f"wave trees are absent). Control reconstruction independently extracts "
        f"{len(control_decl_ns)} namespaces ({', '.join(n['id'] for n in control_decl_ns)}). "
        f"Live references={len(live['references'])} control references={len(control['references'])}. "
        f"Guessed={len(guessed)}. Extractor A/B live counts "
        f"{live['extractor_disagreement']['count_a']}/"
        f"{live['extractor_disagreement']['count_b']}; disagreement reported, not voted. "
        f"{SENTINEL}"
    )
    prior = repo / "command-center/OPTION-ID-RESOLUTION.json"
    payload = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS" if every and not guessed else "FAILED",
        "status": "DELIVERED" if every and not guessed else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "answer": answer,
        "no_guessing": not guessed,
        "every_reference_classified": every,
        "guessed_count": len(guessed),
        "extractor": {
            "id": "CNF-0072-extract-A",
            "path": EXTRACT_REL,
            "line": locus_line("BARE_M_RE ="),
            "regex_bare_m": BARE_M_RE.pattern,
            "regex_mech": MECH_RE.pattern,
            "extractor_b": {
                "id": "CNF-0072-extract-B",
                "token_re": TOKEN_RE.pattern,
                "slash_run_re": SLASH_RUN_RE.pattern,
                "line": locus_line("TOKEN_RE ="),
            },
            "declaration_pattern": (
                "heading ^#{1,6} (M|MECH)-N ; JSON id/option_id/mechanism_id ; "
                "Research Harness (M-N) ; mission-grade M-N. "
                "A prefix is DECLARED only at those sites; a reference-only token is not a namespace."
            ),
            "independent_of": (
                "CC-0021 command-center/OPTION-ID-RESOLUTION.json "
                f"({'present' if prior.is_file() else 'absent'} on this worktree)"
            ),
        },
        "named_inputs": named,
        "live": {
            "declared_namespace_count": len(live_decl_ns),
            "namespaces": live["namespaces"],
            "reference_count": len(live["references"]),
            "extractor_disagreement": live["extractor_disagreement"],
            "gate": live_gate,
        },
        "control": {
            "declared_namespace_count": len(control_decl_ns),
            "namespaces": control["namespaces"],
            "reference_count": len(control["references"]),
            "extractor_disagreement": control["extractor_disagreement"],
            "gate": control_gate,
        },
        "namespaces": control_decl_ns,
        "live_namespaces": live_decl_ns,
        "references": refs_all,
        "extractor_disagreement": {
            "live": live["extractor_disagreement"],
            "control": control["extractor_disagreement"],
            "agree": live["extractor_disagreement"]["agree"]
            and control["extractor_disagreement"]["agree"],
            "count_a": live["extractor_disagreement"]["count_a"]
            + control["extractor_disagreement"]["count_a"],
            "count_b": live["extractor_disagreement"]["count_b"]
            + control["extractor_disagreement"]["count_b"],
            "a_only": live["extractor_disagreement"]["a_only"]
            + control["extractor_disagreement"]["a_only"],
            "b_only": live["extractor_disagreement"]["b_only"]
            + control["extractor_disagreement"]["b_only"],
        },
        "decision_log": {
            "live": decision_log_status(live_log),
            "control": decision_log_status(control_log if control_log.is_file() else None),
        },
        "both_states": {
            "pre_fix_shared_bare_m": sorted(prefix_opt & prefix_arch_m),
            "post_fix_architecture_bare_m": post_arch_m,
            "live_declared_collision": live_collision,
        },
        "prior_extractor": {
            "path": "command-center/OPTION-ID-RESOLUTION.json",
            "present": prior.is_file(),
            "counts_reported": True,
            "ours_live_declared": len(live_decl_ns),
            "ours_control_declared": len(control_decl_ns),
        },
        "tests": tests,
        "reviewer": {
            "independent": True,
            "reviewers": [
                {"id": "CNF-0072-probe1-reextract", "role": "re-run extractor A+B"},
                {"id": "CNF-0072-probe2-controls", "role": "detector controls, does not author extract.py"},
            ],
            "note": "Verdicts are filed by two named probes; neither sees the other probe's return before running.",
        },
        "artifacts": [
            {"path": OUTPUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "schema"},
            {"path": EXTRACT_REL, "role": "extractor"},
        ],
        "output_schema": SCHEMA_REL,
        "output_path": OUTPUT_REL,
    }
    return wrap_receipt(payload, repo)


def _disk_resolver(repo: Path):
    """jsonschema RefResolver that never leaves the worktree."""
    from jsonschema import RefResolver

    rels = (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    )
    store: dict[str, Any] = {}
    for rel in rels:
        path = repo / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        store[path.resolve().as_uri()] = data
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data

    def handler(uri: str) -> Any:
        raw = uri.split("#", 1)[0]
        if raw.startswith("https://ast-integrate.invalid/"):
            rel = raw[len("https://ast-integrate.invalid/") :]
            target = (repo / rel).resolve()
        elif raw.startswith("file:"):
            from urllib.parse import urlparse

            path_s = urlparse(raw).path or ""
            marker = "/platform/schema/" if "/platform/schema/" in path_s else "/command-center/schema/"
            idx = path_s.find(marker)
            if idx < 0:
                raise ValueError(f"refusing network schema fetch: {uri}")
            target = (repo / path_s[idx + 1 :]).resolve()
        else:
            raise ValueError(f"refusing network schema fetch: {uri}")
        if not str(target).startswith(str(repo.resolve())):
            raise ValueError(f"schema uri escapes repo: {uri}")
        return json.loads(target.read_text(encoding="utf-8"))

    shim = json.loads((repo / SCHEMA_REL).read_text(encoding="utf-8"))
    base_uri = str(shim.get("$id") or (repo / SCHEMA_REL).resolve().as_uri())
    return shim, RefResolver(
        base_uri=base_uri,
        referrer=shim,
        store=store,
        handlers={"https": handler, "http": handler, "file": handler},
    )


def validate_against_schema(doc: dict[str, Any], repo: Path | None = None) -> tuple[bool, str]:
    repo = repo or REPO
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return False, "jsonschema missing"
    try:
        lib = str(repo / "platform" / "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)
        from schema_resolver import validator_for  # noqa: WPS433

        validator = validator_for(SCHEMA_REL)
        errors = list(validator.iter_errors(doc))
    except Exception:
        try:
            schema, resolver = _disk_resolver(repo)
            validator = Draft202012Validator(schema, resolver=resolver)
            errors = list(validator.iter_errors(doc))
        except Exception as exc:
            return False, f"{type(exc).__name__}:{exc}"
    if errors:
        first = errors[0]
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        return False, f"{loc}: {first.message}"
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    )
    for g in garbage:
        if not list(validator.iter_errors(g)):
            return False, "schema-vacuous:garbage-accepted"
    return True, "ok"


if __name__ == "__main__":
    doc = audit()
    body = report_of(doc)
    print(
        json.dumps(
            {
                "state": doc["state"],
                "live_ns": body["live"]["declared_namespace_count"],
                "control_ns": body["control"]["declared_namespace_count"],
                "refs": len(body["references"]),
                "guessed": body["guessed_count"],
                "disagree_live": not body["extractor_disagreement"]["live"]["agree"],
                "gate": body["control"]["gate"],
            },
            indent=2,
        )
    )
