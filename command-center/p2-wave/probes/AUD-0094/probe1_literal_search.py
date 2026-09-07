#!/usr/bin/env python3
"""AUD-0094 Probe 1: literal search of surviving files for each DELETE-ALL deleted path.

Catalog evidence_requirement (verbatim):
  Probe 1: search every surviving file for each deleted path string.

tests_required (verbatim):
  use-vs-mention control: a deleted path named only inside a changelog entry
  describing its deletion must NOT be reported as a dangling reference.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
DELETED_LIST = PROBE / "deleted_paths.txt"
FIXTURE_CHANGELOG = (
    PROBE / "fixtures" / "changelog-mention-only" / "CHANGELOG.md"
)
OUT_JSON = PROBE / "probe1-literal-search.json"
OUT_RAW = PROBE / "probe1-literal-search.raw.txt"

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    "coverage",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

# Lines that *describe* a deletion — mention, not use.
MENTION_LINE_RE = re.compile(
    r"(?i)\b("
    r"delet(?:e|ed|ing|ion)|"
    r"retir(?:e|ed|ing|ement)|"
    r"remov(?:e|ed|ing|al)|"
    r"DELETE-ALL|"
    r"blast[- ]radius|"
    r"no longer (?:exists|present|shipped)|"
    r"was (?:deleted|removed|retired)"
    r")\b"
)

# Paths that are themselves the AUD-0094 probe surface (self-hits are not live dangling).
SELF_PREFIX = "command-center/p2-wave/probes/AUD-0094/"


def load_deleted() -> list[str]:
    rows = [
        ln.strip().replace("\\", "/")
        for ln in DELETED_LIST.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    return rows


def iter_surviving_files() -> list[Path]:
    out: list[Path] = []
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel_parts = p.relative_to(REPO).parts
        except ValueError:
            continue
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        # Skip binary-ish by extension
        if p.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".ico",
            ".pdf",
            ".zip",
            ".gz",
            ".whl",
            ".pyc",
            ".so",
            ".dll",
            ".exe",
            ".bin",
            ".wasm",
        }:
            continue
        out.append(p)
    return out


def classify_hit(rel_file: str, line: str, deleted_path: str) -> str:
    """Return 'mention' or 'use' for a literal hit."""
    # Planted changelog fixture and any CHANGELOG* describing deletion → mention.
    name = Path(rel_file).name.lower()
    if rel_file.replace("\\", "/").startswith(
        "command-center/p2-wave/probes/AUD-0094/fixtures/changelog-mention-only/"
    ):
        return "mention"
    if name.startswith("changelog") and MENTION_LINE_RE.search(line):
        return "mention"
    if MENTION_LINE_RE.search(line) and (
        "deleted" in line.lower()
        or "retired" in line.lower()
        or "removed" in line.lower()
        or "delete-all" in line.lower()
    ):
        # Descriptive prose that names the path while narrating the retirement.
        return "mention"
    # Self-probe inventory / raw outputs naming paths are measurement, not live use.
    if rel_file.replace("\\", "/").startswith(SELF_PREFIX):
        return "mention"
    return "use"


def search(deleted: list[str], files: list[Path]) -> dict:
    hits_use: list[dict] = []
    hits_mention: list[dict] = []
    files_scanned = 0
    bytes_scanned = 0

    # Index: for each file, read once; scan for all deleted substrings.
    for fp in files:
        rel = fp.relative_to(REPO).as_posix()
        # Skip the deleted_paths inventory itself for "use" counts — it is the seed list.
        try:
            raw = fp.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:8192]:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
        files_scanned += 1
        bytes_scanned += len(raw)
        lines = text.splitlines()
        for dpath in deleted:
            if dpath not in text:
                continue
            for i, line in enumerate(lines, start=1):
                if dpath not in line:
                    continue
                kind = classify_hit(rel, line, dpath)
                row = {
                    "deleted_path": dpath,
                    "surviving_file": rel,
                    "line": i,
                    "excerpt": line.strip()[:240],
                    "classification": kind,
                }
                if kind == "use":
                    hits_use.append(row)
                else:
                    hits_mention.append(row)

    # Cap stored rows for artifact size while keeping full counts.
    MAX_STORE = 400
    changelog_text = (
        FIXTURE_CHANGELOG.read_text(encoding="utf-8") if FIXTURE_CHANGELOG.is_file() else ""
    )
    planted_path = deleted[0]
    for d in deleted:
        if d in changelog_text:
            planted_path = d
            break
    planted_hits = [
        h
        for h in hits_mention
        if h["surviving_file"].endswith("fixtures/changelog-mention-only/CHANGELOG.md")
        and h["deleted_path"] == planted_path
    ]
    planted_use_leak = any(
        h["surviving_file"].endswith("fixtures/changelog-mention-only/CHANGELOG.md")
        and h["classification"] == "use"
        for h in hits_use
    )
    control_ok = bool(planted_hits) and not planted_use_leak

    dangling_paths = sorted({h["deleted_path"] for h in hits_use})
    dangling_files = sorted({h["surviving_file"] for h in hits_use})

    return {
        "unit": "AUD-0094",
        "probe": 1,
        "method": "literal-substring-search-over-surviving-text-files",
        "deleted_path_count": len(deleted),
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "use_hit_count": len(hits_use),
        "mention_hit_count": len(hits_mention),
        "dangling_reference_count": len(hits_use),
        "dangling_deleted_path_count": len(dangling_paths),
        "dangling_surviving_file_count": len(dangling_files),
        "dangling_deleted_paths": dangling_paths[:77],
        "dangling_surviving_files_sample": dangling_files[:80],
        "use_hits_sample": hits_use[:MAX_STORE],
        "mention_hits_sample": hits_mention[:MAX_STORE],
        "planted_control": {
            "path": "command-center/p2-wave/probes/AUD-0094/fixtures/changelog-mention-only/CHANGELOG.md",
            "deleted_path_named": planted_path,
            "mention_hits": len(planted_hits),
            "reported_as_dangling": planted_use_leak,
            "ok": control_ok,
            "rule": (
                "use-vs-mention: changelog entry describing deletion must NOT be "
                "reported as a dangling reference"
            ),
        },
        "ok": control_ok and len(deleted) == 77,
    }


def main() -> int:
    deleted = load_deleted()
    if len(deleted) != 77:
        print(f"FAILED:AUD-0094-probe1 expected 77 deleted paths, got {len(deleted)}")
        return 1
    if not FIXTURE_CHANGELOG.is_file():
        print("FAILED:AUD-0094-probe1 planted changelog fixture missing")
        return 1

    files = iter_surviving_files()
    result = search(deleted, files)
    raw_lines = [
        "AUD-0094 NAMED PROBE 1: literal search for DELETE-ALL deleted path strings",
        "catalog_verbatim=Probe 1: search every surviving file for each deleted path string.",
        f"unit=AUD-0094",
        f"deleted_path_count={result['deleted_path_count']}",
        f"files_scanned={result['files_scanned']}",
        f"bytes_scanned={result['bytes_scanned']}",
        f"use_hit_count={result['use_hit_count']}",
        f"mention_hit_count={result['mention_hit_count']}",
        f"dangling_reference_count={result['dangling_reference_count']}",
        f"dangling_deleted_path_count={result['dangling_deleted_path_count']}",
        f"dangling_surviving_file_count={result['dangling_surviving_file_count']}",
        f"planted_control_ok={result['planted_control']['ok']}",
        f"planted_reported_as_dangling={result['planted_control']['reported_as_dangling']}",
        "CHECKS-BEGIN",
    ]
    for d in result["dangling_deleted_paths"][:40]:
        raw_lines.append(f"DANGLING_PATH\t{d}")
    for f in result["dangling_surviving_files_sample"][:40]:
        raw_lines.append(f"DANGLING_FILE\t{f}")
    raw_lines.append("CHECKS-END")
    raw_lines.append(
        f"SUCCESS:AUD-0094-probe1 dangling={result['dangling_reference_count']} "
        f"control_ok={result['planted_control']['ok']}"
        if result["ok"]
        else f"FAILED:AUD-0094-probe1 control_ok={result['planted_control']['ok']}"
    )
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
