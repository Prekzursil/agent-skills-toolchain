"""Shared helpers for AUD-0077. Never return or log secret values."""
from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0077"
OUT_REL = "command-center/audit/AUD-0077-secret-scan-repo-live.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0077 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0077/probe1_gitleaks.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0077/probe2_entropy.py"
)
SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".bin",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cursor",
        ".tox",
        "htmlcov",
    }
)
# Concurrent P2 writers mutate these trees; including them makes live
# fingerprint equality fail between emit and re-measure. Coverage records
# the exclusion instead of pretending the scan was whole-tree.
SKIP_PREFIXES = (
    "command-center/p2-wave/probes/",
    "command-center/receipts/",
    "command-center/audit/",
    "command-center/adversarial/",
    "command-center/research/",
    "command-center/p2-wave/ovh-monitor/",
)
SKIP_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".so",
        ".dylib",
        ".bin",
        ".pyc",
        ".gz",
        ".zip",
        ".tar",
        ".whl",
    }
)
MAX_FILE_BYTES = 8 * 1024 * 1024
ASSIGN_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_.-]{0,120})\s*[:=]\s*\S"
)
JSON_KEY_RE = re.compile(
    r'["\'](?P<lhs>[A-Za-z_][A-Za-z0-9_.-]{0,120})["\']\s*:'
)
HARNESS_CANDIDATES = [
    Path.home() / ".claude/harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/opt/p2/harness-restore-20260806"),
    REPO / "harness-restore-20260806",
    REPO / "command-center/sources/harness-restore-20260806",
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806"),
]
SELF_MARKERS = (
    "command-center/audit/AUD-0077-secret-scan-repo-live.json",
    "command-center/p2-wave/probes/AUD-0077/",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def relpath(path: Path | str) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def is_self_artifact(rel: str) -> bool:
    r = rel.replace("\\", "/")
    return any(m in r for m in SELF_MARKERS)


def should_skip_rel(rel: str) -> bool:
    r = rel.replace("\\", "/").lstrip("./")
    if is_self_artifact(r):
        return True
    for prefix in SKIP_PREFIXES:
        p = prefix.rstrip("/")
        if r == p or r.startswith(p + "/"):
            return True
    return False


def iter_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")
        )
        rel_dir = relpath(Path(dirpath))
        if Path(dirpath).resolve() != root and should_skip_rel(rel_dir):
            dirnames[:] = []
            continue
        kept: list[str] = []
        for d in dirnames:
            child_rel = relpath(Path(dirpath) / d)
            if not should_skip_rel(child_rel):
                kept.append(d)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = relpath(path)
            if should_skip_rel(rel):
                continue
            yield path


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 0 or size > MAX_FILE_BYTES:
        return False
    try:
        chunk = path.open("rb").read(8192)
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    return True


def shannon(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def lhs_from_line(line: str) -> str:
    stripped = line.strip()
    m = ASSIGN_RE.search(stripped)
    if m:
        return m.group("lhs")
    m = JSON_KEY_RE.search(stripped)
    if m:
        return m.group("lhs")
    return ""


def variable_name_at(path: Path, line_no: int) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = raw.splitlines()
    if line_no < 1 or line_no > len(lines):
        return ""
    name = lhs_from_line(lines[line_no - 1])
    return name


def classify(rel: str, variable_name: str) -> str:
    p = rel.replace("\\", "/").lower()
    n = (variable_name or "").lower()
    if "aud77_synthetic" in n:
        return "FIXTURE"
    if any(
        tok in p
        for tok in (
            "/fixtures/",
            "/fixture-",
            "/detector-fixtures/",
            "/_work/fixtures/",
            "/cases/",
            "known-bad",
            "planted",
        )
    ):
        return "FIXTURE"
    if (
        p.endswith((".html", ".raw", ".md"))
        or "/snapshots/" in p
        or "/captures/" in p
        or "/sources/" in p
    ):
        return "DOCUMENTATION-EXAMPLE"
    if any(tok in n for tok in ("example", "placeholder", "dummy", "sample", "fake", "changeme")):
        return "PLACEHOLDER"
    if "redact" in n:
        return "REDACTED-MARKER"
    return "CREDENTIAL-SHAPED-UNVERIFIED"


def scope_for(rel: str, variable_name: str) -> str:
    p = rel.replace("\\", "/").lower()
    if variable_name:
        if p.endswith((".env", ".ini", ".toml", ".yml", ".yaml", ".properties")):
            return f"assignment:{variable_name}"
        if p.endswith((".json", ".jsonl")):
            return f"json-key:{variable_name}"
        return f"identifier:{variable_name}"
    if p.endswith((".env", ".ini")):
        return "env-file"
    if "private key" in p or p.endswith((".pem", ".key")):
        return "pem-or-key-file"
    return "unscoped-line"


def harness_census() -> dict:
    rows = []
    present = []
    for cand in HARNESS_CANDIDATES:
        exists = cand.exists()
        row = {"path": str(cand), "exists": exists}
        rows.append(row)
        if exists:
            present.append(str(cand))
    return {
        "candidates_checked": len(rows),
        "present": present,
        "absent_count": sum(1 for r in rows if not r["exists"]),
        "rows": rows,
        "live_harness_scanned": bool(present),
        "scan_exclusions": list(SKIP_PREFIXES),
    }


def git_coverage() -> dict:
    git_dir = REPO / ".git"
    present = git_dir.exists()
    return {
        "git_dir_present": present,
        "history_scanned": False,
        "tracked_untracked_split": "UNAVAILABLE" if not present else "git-ls-files",
        "working_tree_scanned": True,
        "reason": (
            "no .git directory on this Linux worktree; gitleaks ran with --no-git "
            "over the working tree. Tracked vs untracked cannot be split. History "
            "was not scanned because it is not present."
        ),
    }


def strip_secret_fields(hit: dict) -> dict:
    banned = {
        "Secret",
        "Match",
        "secret",
        "match",
        "value",
        "raw",
        "Author",
        "Email",
        "Message",
    }
    return {k: v for k, v in hit.items() if k not in banned}


def assert_absent(haystack: str, needle: str, label: str) -> None:
    if needle and needle in haystack:
        raise RuntimeError(f"secret-body-leaked:{label}")


def fingerprint(rel: str, line: int, rule_id: str, detector: str) -> str:
    return f"{rel}:{line}:{rule_id}:{detector}"

