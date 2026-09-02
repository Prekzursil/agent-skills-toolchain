"""EOL-contract detectors for AUD-0019.

Probe 1 compares `git cat-file -p` blobs to working-tree bytes (never archive).
Probe 2 maps .gitattributes eol pins by extension.
Three-route control uses archive only as a named control, not as the blob source.
"""
from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "dist",
    "build",
}
TEXT_EXTS = {
    ".bat",
    ".cfg",
    ".cmd",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def lf_norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def eol_kind(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    # Count bare CR and LF remaining after CRLF is removed.
    stripped = data.replace(b"\r\n", b"")
    cr = stripped.count(b"\r")
    lf = stripped.count(b"\n")
    if crlf and lf:
        return "mixed"
    if crlf:
        return "CRLF"
    if cr and not lf:
        return "CR"
    if lf:
        return "LF"
    return "none"


def classify_blob_vs_worktree(blob: bytes, worktree: bytes) -> str:
    if blob == worktree:
        return "identical"
    if lf_norm(blob) == lf_norm(worktree):
        return "eol-only"
    return "content"


def parse_gitattributes(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        pattern = parts[0]
        attrs: dict[str, str | bool] = {}
        for token in parts[1:]:
            if token.startswith("-"):
                attrs[token[1:]] = False
                continue
            if "=" in token:
                key, val = token.split("=", 1)
                attrs[key] = val
            else:
                attrs[token] = True
        rules.append({"line": lineno, "pattern": pattern, "attrs": attrs, "raw": raw})
    return rules


def pattern_matches(pattern: str, relpath: str) -> bool:
    name = relpath.replace("\\", "/").split("/")[-1]
    if pattern == "*":
        return True
    if pattern.startswith("*."):
        return name.endswith(pattern[1:])
    return relpath.replace("\\", "/") == pattern.replace("\\", "/")


def eol_pin_for_path(relpath: str, rules: list[dict[str, Any]]) -> str | None:
    pin: str | None = None
    for rule in rules:
        if not pattern_matches(str(rule["pattern"]), relpath):
            continue
        attrs = rule["attrs"]
        if "eol" in attrs:
            val = attrs["eol"]
            pin = str(val) if val not in (True, False) else pin
        elif attrs.get("eol") is False:
            pin = None
    return pin


def coverage_by_extension(
    extensions: list[str], rules: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    uncovered = []
    for ext in sorted(set(extensions)):
        sample = f"file{ext}" if ext.startswith(".") else f"file.{ext}"
        pin = eol_pin_for_path(sample, rules)
        rows.append({"extension": ext, "eol_pin": pin, "pinned": pin is not None})
        if pin is None:
            uncovered.append(ext)
    pinned_n = sum(1 for r in rows if r["pinned"])
    return {
        "rule_count": len(rules),
        "extension_count": len(rows),
        "pinned_count": pinned_n,
        "unpinned_count": len(uncovered),
        "unpinned_extensions": uncovered,
        "pinned_count": pinned_n,
        "unpinned_extensions": uncovered,
        "rows": rows,
    }


def git_env(git_dir: Path, work_tree: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    if work_tree is not None:
        env["GIT_WORK_TREE"] = str(work_tree)
    env.setdefault("GIT_AUTHOR_NAME", "AUD-0019")
    env.setdefault("GIT_AUTHOR_EMAIL", "aud0019@fixture.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "AUD-0019")
    env.setdefault("GIT_COMMITTER_EMAIL", "aud0019@fixture.invalid")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def git_bytes(args: list[str], *, env: dict[str, str], check: bool = True) -> bytes:
    proc = subprocess.run(["git", *args], capture_output=True, env=env)
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {err.strip()}")
    return proc.stdout


def cat_file_p(git_dir: Path, relpath: str, rev: str = "HEAD") -> bytes:
    env = git_env(git_dir)
    return git_bytes(["cat-file", "-p", f"{rev}:{relpath}"], env=env)


def git_show_path(git_dir: Path, relpath: str, rev: str = "HEAD") -> bytes:
    env = git_env(git_dir)
    return git_bytes(["show", f"{rev}:{relpath}"], env=env)


def git_archive_path(git_dir: Path, relpath: str, rev: str = "HEAD") -> bytes:
    env = git_env(git_dir)
    with tempfile.TemporaryDirectory(prefix="aud0019-arch-") as td:
        tarp = Path(td) / "one.tar"
        git_bytes(["archive", "-o", str(tarp), rev, "--", relpath], env=env)
        with tarfile.open(tarp) as tf:
            member = None
            for m in tf.getmembers():
                if m.name == relpath and m.isfile():
                    member = m
                    break
            if member is None:
                raise RuntimeError(f"git archive missing file member {relpath}")
            fh = tf.extractfile(member)
            if fh is None:
                raise RuntimeError(f"git archive extract failed for {relpath}")
            return fh.read()


def three_route(git_dir: Path, relpath: str) -> dict[str, Any]:
    cat = cat_file_p(git_dir, relpath)
    show = git_show_path(git_dir, relpath)
    archive = git_archive_path(git_dir, relpath)
    routes = {
        "git cat-file -p": cat,
        "git show <rev>:<path>": show,
        "git archive": archive,
    }
    norms = [lf_norm(v) for v in routes.values()]
    return {
        "path": relpath,
        "method_note": (
            "archive is a control only; blob comparison uses cat-file -p, never archive"
        ),
        "routes": {
            name: {
                "bytes": len(data),
                "eol": eol_kind(data),
                "crlf_count": data.count(b"\r\n"),
            }
            for name, data in routes.items()
        },
        "cat_file_equals_show": cat == show,
        "archive_differs_from_blob": archive != cat,
        "identical_after_lf_normalisation": bool(norms[0])
        and all(n == norms[0] for n in norms),
        "all_three_agree": cat == show == archive,
        # Aliases used by probes/emit
        "cat_file_equals_show": cat == show,
        "archive_differs_from_blob": archive != cat,
        "identical_after_lf_normalisation": bool(norms[0])
        and all(n == norms[0] for n in norms),
        "all_three_agree": cat == show == archive,
    }


def list_blob_paths(git_dir: Path, rev: str = "HEAD") -> list[str]:
    env = git_env(git_dir)
    out = git_bytes(["ls-tree", "-r", "--name-only", rev], env=env)
    return [ln for ln in out.decode("utf-8").splitlines() if ln]


def is_probably_text(data: bytes) -> bool:
    if b"\0" in data[:8192]:
        return False
    return True


def compare_paths(git_dir: Path, work_tree: Path, paths: list[str]) -> dict[str, Any]:
    rows = []
    counts = {"identical": 0, "eol-only": 0, "content": 0, "skipped-binary": 0}
    for rel in paths:
        blob = cat_file_p(git_dir, rel)
        wt_path = work_tree / rel
        wt = wt_path.read_bytes() if wt_path.is_file() else b""
        if not is_probably_text(blob) or not is_probably_text(wt):
            counts["skipped-binary"] += 1
            rows.append(
                {
                    "path": rel,
                    "class": "skipped-binary",
                    "blob_eol": eol_kind(blob),
                    "worktree_eol": eol_kind(wt),
                    "blob_bytes": len(blob),
                    "worktree_bytes": len(wt),
                }
            )
            continue
        klass = classify_blob_vs_worktree(blob, wt)
        counts[klass] += 1
        rows.append(
            {
                "path": rel,
                "class": klass,
                "blob_eol": eol_kind(blob),
                "worktree_eol": eol_kind(wt),
                "blob_bytes": len(blob),
                "worktree_bytes": len(wt),
            }
        )
    return {
        "counts": counts,
        "row_count": len(rows),
        "row_count": len(rows),
        "rows": rows,
    }


def find_gitattributes(root: Path) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        if ".gitattributes" in filenames:
            found.append(
                (Path(dirpath) / ".gitattributes").relative_to(root).as_posix()
            )
    return sorted(found)


def live_git_present(root: Path) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def read_autocrlf() -> dict[str, str | None]:
    def one(scope: str) -> str | None:
        proc = subprocess.run(
            ["git", "config", "--" + scope, "--get", "core.autocrlf"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None
        val = proc.stdout.strip()
        return val or None

    return {"global": one("global"), "system": one("system")}


def live_worktree_eol_inventory(root: Path, limit: int = 4000) -> dict[str, Any]:
    crlf_paths: list[str] = []
    mixed_paths: list[str] = []
    ext_counts: dict[str, dict[str, int]] = {}
    scanned = 0
    skipped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""
        for name in filenames:
            if scanned >= limit:
                break
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            ext = path.suffix.lower() or "(none)"
            try:
                if path.stat().st_size > 2_000_000:
                    skipped += 1
                    continue
                data = path.read_bytes()
            except OSError:
                skipped += 1
                continue
            if not is_probably_text(data):
                skipped += 1
                continue
            scanned += 1
            kind = eol_kind(data)
            bucket = ext_counts.setdefault(ext, {"LF": 0, "CRLF": 0, "mixed": 0, "other": 0})
            if kind == "LF":
                bucket["LF"] += 1
            elif kind == "CRLF":
                bucket["CRLF"] += 1
                if len(crlf_paths) < 50:
                    crlf_paths.append(rel)
            elif kind == "mixed":
                bucket["mixed"] += 1
                if len(mixed_paths) < 50:
                    mixed_paths.append(rel)
            else:
                bucket["other"] += 1
        if scanned >= limit:
            break
    return {
        "root": str(root),
        "scanned_text_files": scanned,
        "skipped": skipped,
        "crlf_file_count": sum(v["CRLF"] for v in ext_counts.values()),
        "mixed_file_count": sum(v["mixed"] for v in ext_counts.values()),
        "crlf_sample": crlf_paths,
        "mixed_sample": mixed_paths,
        "by_extension": ext_counts,
        "extensions_seen": sorted(ext_counts),
        "extensions_seen": sorted(ext_counts),
        "scanned_text_files": scanned,
    }
