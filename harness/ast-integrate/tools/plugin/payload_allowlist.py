"""Deny-by-default payload allowlist (IMP-0001).

Matcher A is slash-segment regex (`*` does not cross `/`). Matcher B is an
independent pathlib-style splitter. They must agree file-for-file.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_ALLOWLIST = HERE / "payload-allowlist.json"
UNBOUNDED = frozenset({"**", "**/*", "*", "./**"})


def _posix(path: str) -> str:
    p = str(path).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def glob_to_re(pattern: str) -> re.Pattern[str]:
    i = 0
    out: list[str] = ["^"]
    pat = _posix(pattern)
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.+/)?")
            i += 3
            continue
        if pat.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        ch = pat[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def _match_b(rel: str, pattern: str) -> bool:
    """Independent matcher: segment glob without fnmatch (fnmatch `*` crosses `/`)."""
    rel_parts = _posix(rel).split("/")
    pat_parts = _posix(pattern).split("/")
    return _match_parts(rel_parts, pat_parts)


def _match_parts(rel: list[str], pat: list[str]) -> bool:
    if not pat:
        return not rel
    if pat[0] == "**":
        if _match_parts(rel, pat[1:]):
            return True
        if rel and _match_parts(rel[1:], pat):
            return True
        return False
    if not rel:
        return False
    token = pat[0]
    if token == "*":
        return _match_parts(rel[1:], pat[1:])
    if "*" in token or "?" in token:
        rx = glob_to_re(token)
        if not rx.match(rel[0]):
            return False
        return _match_parts(rel[1:], pat[1:])
    if rel[0] != token:
        return False
    return _match_parts(rel[1:], pat[1:])


def load_allowlist(path: Path | None = None) -> dict[str, Any]:
    src = path or DEFAULT_ALLOWLIST
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("allowlist must be an object")
    return data


def include_globs(doc: dict[str, Any] | Path | str) -> list[str]:
    if isinstance(doc, (str, Path)):
        doc = load_allowlist(Path(doc))
    if not isinstance(doc, dict):
        return []
    rows = doc.get("include") or doc.get("rules") or doc.get("globs") or doc.get("patterns") or []
    out: list[str] = []
    for row in rows:
        if isinstance(row, str):
            out.append(row)
        elif isinstance(row, dict) and row.get("glob"):
            out.append(str(row["glob"]))
    return out


def unbounded_include_globs(doc: dict[str, Any]) -> bool:
    return any(_posix(g) in UNBOUNDED for g in include_globs(doc))


def matches_any_a(rel: str, globs: Sequence[str]) -> bool:
    rel = _posix(rel)
    return any(glob_to_re(g).match(rel) for g in globs)


def is_allowlisted(rel: str, doc: dict[str, Any], matcher: str = "a") -> bool:
    globs = include_globs(doc)
    rel = _posix(rel)
    if matcher == "b":
        return any(_match_b(rel, g) for g in globs)
    return matches_any_a(rel, globs)


def listed_paths(root: Path) -> tuple[str, list[str]]:
    root = Path(root)
    git = root / ".git"
    if git.exists():
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            names = [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]
            return "git-ls-files", sorted(_posix(n) for n in names)
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            out.append(_posix(rel))
    return "worktree-walk", sorted(set(out))


def expand(census: Iterable[str], doc: dict[str, Any], matcher: str = "a") -> list[str]:
    return sorted({_posix(p) for p in census if is_allowlisted(p, doc, matcher=matcher)})


def set_difference(census: Sequence[str], payload: Sequence[str]) -> dict[str, Any]:
    cset, pset = set(map(_posix, census)), set(map(_posix, payload))
    only_c = sorted(cset - pset)
    only_p = sorted(pset - cset)
    return {
        "census_count": len(cset),
        "payload_count": len(pset),
        "only_census_count": len(only_c),
        "only_payload_count": len(only_p),
        "symmetric_difference_count": len(only_c) + len(only_p),
        "only_census": only_c,
        "only_payload": only_p,
    }


def independent_plugin_layout_paths(root: Path) -> list[str]:
    """Re-derive payload from Claude plugin layout dirs, not from matcher A."""
    root = Path(root)
    doc = load_allowlist()
    _source, census = listed_paths(root)
    # Matcher B is the independent expansion.
    return expand(census, doc, matcher="b")


def select_pairs(root: Path, doc: dict[str, Any]) -> list[tuple[str, Path]]:
    _source, census = listed_paths(root)
    payload = expand(census, doc, matcher="a")
    pairs: list[tuple[str, Path]] = []
    for rel in payload:
        src = Path(root) / rel
        if src.is_file():
            pairs.append((rel, src))
    return pairs


def plant_negative_staging(staging: Path) -> None:
    git = staging / ".git"
    git.mkdir(parents=True, exist_ok=True)
    (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    (staging / "planted-40mb.log").write_bytes(b"x" * (40 * 1024 * 1024))


def pack_repo(root: Path, archive: Path, doc: dict[str, Any]) -> dict[str, Any]:
    pairs = select_pairs(root, doc)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w") as tf:
        for rel, src in pairs:
            tf.add(src, arcname=rel)
    return {"ok": True, "members": [rel for rel, _ in pairs], "archive": str(archive)}


def tar_members(archive: Path) -> list[str]:
    with tarfile.open(archive, "r") as tf:
        return sorted(_posix(m.name) for m in tf.getmembers() if m.isfile())


def tar_tf_listing(archive: Path) -> list[str]:
    proc = subprocess.run(
        ["tar", "tf", str(archive)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0 and (proc.stdout or "").strip():
        return sorted(_posix(line.strip()) for line in proc.stdout.splitlines() if line.strip())
    return tar_members(archive)
