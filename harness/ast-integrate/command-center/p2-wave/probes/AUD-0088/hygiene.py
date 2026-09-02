"""Name-only hygiene classifier for shipped-package paths (AUD-0088).

Flags .git / VCS metadata, caches, logs, transcripts, and credential-shaped
basenames. Never reads or returns file bodies.
"""
from __future__ import annotations

from pathlib import PurePosixPath

REPO_METADATA_PARTS = frozenset({".git", ".svn", ".hg"})
CACHE_PARTS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".eggs",
        ".cache",
    }
)
CACHE_SUFFIXES = frozenset({".pyc", ".pyo"})
LOG_SUFFIXES = frozenset({".log"})
TRANSCRIPT_PARTS = frozenset({"transcript", "transcripts"})
CREDENTIAL_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".env.test",
        "credentials.json",
        "credentials.yml",
        "credentials.yaml",
        "secrets.json",
        "auth.json",
        "service-account.json",
        "id_rsa",
        "id_dsa",
        "id_ed25519",
        "id_ecdsa",
        ".npmrc",
        ".pypirc",
        ".netrc",
        "aws-credentials",
        "gcloud-credentials.json",
    }
)
CREDENTIAL_SUFFIXES = frozenset({".pem", ".p12", ".pfx", ".kdbx"})
# Detector / schema source is not a credential-shaped *path*.
NOT_CREDENTIAL = frozenset(
    {
        "secret_gate.py",
        "secret-finding.schema.json",
        "gitleaks.toml",
        "gitleaks_engine.py",
        "canary.py",
        "redact.py",
        "entropy_scan.py",
    }
)


def posix(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def classify_path(rel: str) -> list[str]:
    """Return zero or more rule ids. Empty means the path is not prohibited."""
    rel = posix(rel)
    if not rel or rel.endswith("/"):
        return []
    p = PurePosixPath(rel)
    parts = set(p.parts)
    name = p.name
    name_l = name.lower()
    flags: list[str] = []
    git_names = {"config", "head", "index", "packed-refs"}
    git_shaped = bool(parts & REPO_METADATA_PARTS) or rel.startswith(".git/") or "/.git/" in f"/{rel}"
    if not git_shaped and name_l in git_names:
        # Zip members may drop a leading dot (".git/config" -> "git/config").
        parent = p.parent.as_posix().lower()
        git_shaped = parent == "git" or parent.endswith("/git") or parent.endswith("/.git")
    if git_shaped:
        flags.append("repo-metadata")
    if parts & CACHE_PARTS or p.suffix.lower() in CACHE_SUFFIXES:
        flags.append("cache")
    if p.suffix.lower() in LOG_SUFFIXES or name_l.endswith(".log"):
        flags.append("log")
    if parts & TRANSCRIPT_PARTS or "transcript" in name_l:
        flags.append("transcript")
    if name not in NOT_CREDENTIAL:
        if name_l in {n.lower() for n in CREDENTIAL_NAMES} or p.suffix.lower() in CREDENTIAL_SUFFIXES:
            flags.append("credential-shaped")
    # Preserve rule order without duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def prohibited_rows(paths: list[str]) -> list[dict]:
    rows = []
    for rel in paths:
        flags = classify_path(rel)
        if flags:
            rows.append({"path": posix(rel), "flags": flags})
    return rows
