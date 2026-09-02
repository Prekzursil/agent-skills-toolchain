"""Packaging include-list resolver for AUD-0078.

Grounded in spec line 10842 (never ship .git, caches, logs, transcripts,
credentials) and the IMP-0003 path-role classes in tools/plugin/forbidden_scan.py,
plus IMP-0004 credential path names from tools/plugin/secret_gate.py.

The resolver is proven on a scratch tree before any live scan count is used.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Spec 10842 / IMP-0003 path-role excludes.
GIT_SEGMENT = ".git"
NODE_MODULES = "node_modules"
PYCACHE = "__pycache__"
OS_CACHE = frozenset(
    {
        ".cache",
        "__macosx",
        ".ds_store",
        "thumbs.db",
        "ehthumbs.db",
        ".spotlight-v100",
        ".trashes",
        ".fseventsd",
        "$recycle.bin",
        "system volume information",
        ".temporaryitems",
        ".appledouble",
        ".trash-1000",
        ".trash",
        ".venv",
        "venv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
    }
)
TRANSCRIPT_DIRS = frozenset({"transcript", "transcripts", "session", "sessions"})
MAX_FILE_BYTES = 8 * 1024 * 1024

# Spec 10842 credentials + IMP-0004 secret basenames/suffixes.
SECRET_BASENAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials",
        "credentials.json",
        "secrets.json",
        "auth.json",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "service-account.json",
    }
)
SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".key", ".decrypted")

CORPUS_CANDIDATES = (
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path.home() / ".claude" / "harness-restore-20260806",
    REPO / "harness-restore-20260806",
)

SKIP_SELF_ARTIFACT = "command-center/audit/AUD-0078-corpus-bundle-privacy-scan.json"


def posix_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def exclude_reason(rel: str, size: int | None = None) -> str | None:
    """Return the packaging exclude class, or None if the path may ship."""
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1].lower() if parts else ""
    for part in parts:
        folded = part.casefold()
        if folded == GIT_SEGMENT:
            return "git"
        if folded == NODE_MODULES:
            return "node_modules"
        if folded == PYCACHE:
            return "pycache"
        if folded in OS_CACHE:
            return "os_cache"
        if folded in TRANSCRIPT_DIRS:
            return "transcript"
    if name.endswith(".log"):
        return "log"
    if name.endswith(".jsonl") and (
        any(p.casefold() in TRANSCRIPT_DIRS for p in parts[:-1])
        or "transcript" in name
        or "session" in name
    ):
        return "transcript"
    if name in SECRET_BASENAMES or name.startswith(".env.") or "credential" in name:
        return "credential"
    if name.endswith(SECRET_SUFFIXES):
        return "credential"
    if size is not None and size > MAX_FILE_BYTES:
        return "oversize"
    return None


def included(rel: str, size: int | None = None) -> bool:
    return exclude_reason(rel, size) is None


def prove_resolver() -> dict:
    """Control: exclude a packaging-excluded file and include a packaging-included file."""
    with tempfile.TemporaryDirectory(prefix="aud0078-pack-") as tmp:
        root = Path(tmp)
        keep = root / "keep" / "readme.md"
        keep.parent.mkdir(parents=True)
        keep.write_text("included-by-packaging-rules\n", encoding="utf-8")
        git_head = root / ".git" / "HEAD"
        git_head.parent.mkdir(parents=True)
        git_head.write_text("ref: refs/heads/main\n", encoding="utf-8")
        envf = root / ".env"
        envf.write_text("PLACEHOLDER=not-a-live-secret\n", encoding="utf-8")
        logf = root / "debug.log"
        logf.write_text("noise\n", encoding="utf-8")
        tr = root / "transcripts" / "session-1.jsonl"
        tr.parent.mkdir(parents=True)
        tr.write_text("{}\n", encoding="utf-8")

        keep_rel = posix_rel(root, keep)
        git_rel = posix_rel(root, git_head)
        env_rel = posix_rel(root, envf)
        log_rel = posix_rel(root, logf)
        tr_rel = posix_rel(root, tr)

        keep_in = included(keep_rel, keep.stat().st_size)
        git_out = not included(git_rel, git_head.stat().st_size)
        env_out = not included(env_rel, envf.stat().st_size)
        log_out = not included(log_rel, logf.stat().st_size)
        tr_out = not included(tr_rel, tr.stat().st_size)
        ok = keep_in and git_out and env_out and log_out and tr_out
        return {
            "ok": ok,
            "included_sample": keep_rel,
            "included_sample_kept": keep_in,
            "excluded": {
                git_rel: {"reason": exclude_reason(git_rel), "excluded": git_out},
                env_rel: {"reason": exclude_reason(env_rel), "excluded": env_out},
                log_rel: {"reason": exclude_reason(log_rel), "excluded": log_out},
                tr_rel: {"reason": exclude_reason(tr_rel), "excluded": tr_out},
            },
            "rule_source": [
                "spec-10842",
                "command-center/p2-wave/probes/AUD-0078/packaging.py",
                "IMP-0003-path-role-classes (tools/plugin/forbidden_scan.py ABSENT on this tree)",
                "IMP-0004-credential-names (tools/plugin/secret_gate.py ABSENT on this tree)",
            ],
        }


def _redact_home(path: Path) -> str:
    text = str(path)
    return re.sub(r"(?i)(/Users/|/home/|Users[/\\])[^/\\]+", r"\1<redacted>", text)


def corpus_roots() -> list[dict]:
    rows = []
    for path in CORPUS_CANDIDATES:
        rows.append(
            {
                "path": _redact_home(path),
                "present": path.is_dir(),
            }
        )
    return rows


def live_candidate_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = [("command-center", REPO / "command-center")]
    plugin = REPO / ".claude-plugin"
    if plugin.is_dir():
        roots.append((".claude-plugin", plugin))
    for path in CORPUS_CANDIDATES:
        if path.is_dir():
            roots.append(("harness-restore-corpus", path))
            break
    return roots


def iter_included_files() -> Iterator[dict]:
    for label, root in live_candidate_roots():
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            rel_dir = posix_rel(root, Path(dirpath)) if Path(dirpath) != root else ""
            # Prune excluded directories so we do not walk .git / caches.
            kept = []
            for name in dirnames:
                rel = f"{rel_dir}/{name}".lstrip("/") if rel_dir else name
                if exclude_reason(rel + "/") is None and exclude_reason(rel) is None:
                    kept.append(name)
            dirnames[:] = kept
            for name in filenames:
                path = Path(dirpath) / name
                if not path.is_file() or path.is_symlink():
                    continue
                rel = posix_rel(root, path)
                repo_rel = (
                    f"{root.relative_to(REPO).as_posix()}/{rel}"
                    if root.is_relative_to(REPO)
                    else f"{label}/{rel}"
                )
                if repo_rel.replace("\\", "/") == SKIP_SELF_ARTIFACT:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                reason = exclude_reason(rel, size)
                if reason:
                    continue
                yield {
                    "tree": label,
                    "rel": rel,
                    "repo_rel": repo_rel.replace("\\", "/"),
                    "path": path,
                    "bytes": size,
                }


def include_census() -> dict:
    files = list(iter_included_files())
    by_tree: dict[str, int] = {}
    bytes_by_tree: dict[str, int] = {}
    for row in files:
        by_tree[row["tree"]] = by_tree.get(row["tree"], 0) + 1
        bytes_by_tree[row["tree"]] = bytes_by_tree.get(row["tree"], 0) + row["bytes"]
    return {
        "file_count": len(files),
        "byte_count": sum(r["bytes"] for r in files),
        "by_tree": by_tree,
        "bytes_by_tree": bytes_by_tree,
        "corpus_roots": corpus_roots(),
        "corpus_present": any(r["present"] for r in corpus_roots()),
        "files": files,
    }
