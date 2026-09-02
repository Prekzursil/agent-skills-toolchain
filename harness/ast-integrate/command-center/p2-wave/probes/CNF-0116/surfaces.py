"""Two independent surfaces: zip namelist vs git plumbing.

Artifact listing never walks include-rules. Git listing never treats
.gitignore as proof of exclusion. Filenames only.
"""
from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

from inventory import FIXTURE_PLACEHOLDER, ROTATION_POOL_BASENAME, posix

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "CNF-0116",
    "GIT_AUTHOR_EMAIL": "cnf-0116@invalid",
    "GIT_COMMITTER_NAME": "CNF-0116",
    "GIT_COMMITTER_EMAIL": "cnf-0116@invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}

INCLUDE_RULES = ("README.md", "plugin.json", "dist/app.py")
IGNORE_RULES = "\n".join(
    [
        "secrets/",
        "accounts.json",
        "*.credentials.json",
        ".env",
        ".env.*",
        "",
    ]
)


def run_git(repo: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    extra = {
        "HOME": str(repo / ".cnf0116-home"),
        "XDG_CONFIG_HOME": str(repo / ".cnf0116-home"),
    }
    (repo / ".cnf0116-home").mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        ["git", "-c", "user.name=CNF-0116", "-c", "user.email=cnf-0116@invalid", *args],
        cwd=str(repo),
        env={**GIT_ENV, **extra},
        capture_output=True,
        text=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"git {args} rc={p.returncode} {(p.stderr or p.stdout)[-800:]}")
    return p


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def build_payload(root: Path) -> dict:
    """Isolated fixture tree. Rotation-pool is written once and never rewritten."""
    write_bytes(root / "README.md", b"# CNF-0116 fixture\nbenign known-present sibling\n")
    write_bytes(root / "plugin.json", b'{"id":"cnf-0116-benign-control","kind":"plugin"}\n')
    write_bytes(root / "dist" / "app.py", b"print('benign')\n")
    write_bytes(root / "rule.no-secrets.md", b"Policy text. Not a credential file.\n")
    write_bytes(root / ".gitignore", IGNORE_RULES.encode("utf-8"))
    planted = root / "secrets" / "planted.credentials.json"
    write_bytes(planted, FIXTURE_PLACEHOLDER)
    pool = root / ROTATION_POOL_BASENAME
    write_bytes(pool, FIXTURE_PLACEHOLDER)
    st = pool.stat()
    return {
        "known_present": "plugin.json",
        "planted": posix(str(planted.relative_to(root))),
        "rotation_pool": ROTATION_POOL_BASENAME,
        "rotation_pool_size": st.st_size,
        "rotation_pool_mtime_ns": st.st_mtime_ns,
        "include_rules": list(INCLUDE_RULES),
        "ignore_rules": IGNORE_RULES.splitlines(),
    }


def zip_named(src: Path, dest: Path, rels: list[str]) -> list[str]:
    """Pack names only. Never copy file bytes (rotation-pool / huge fixtures)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
        for rel in rels:
            path = src / rel
            if path.is_file():
                info = zipfile.ZipInfo(posix(rel))
                info.external_attr = 0o644 << 16
                zf.writestr(info, b"")
    return zip_namelist(dest)


def zip_namelist(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as zf:
        return sorted(posix(n) for n in zf.namelist() if n and not n.endswith("/"))


LIVE_SKIP_PARTS = {
    "__pycache__",
    ".cnf0116-home",
    ".git",
    "node_modules",
    ".venv",
    # Other units' probe trees are a moving surface (and include a 2GiB blob).
    # Known-present lives at command-center/WORK-UNIT-CATALOG.json, not under probes/.
    "probes",
}


def walk_files(root: Path, skip_parts: set[str] | None = None) -> list[str]:
    skip = skip_parts or {"__pycache__", ".cnf0116-home", ".git"}
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".cnf")]
        base = Path(dirpath)
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            rel = posix(str((base / name).relative_to(root)))
            out.append(rel)
    return sorted(out)


def zip_tree(src: Path, dest: Path, skip_parts: set[str] | None = None) -> list[str]:
    rels = walk_files(src, skip_parts=skip_parts)
    return zip_named(src, dest, rels)


def enumerate_by_include_rules(src: Path, rules: list[str]) -> list[str]:
    found: list[str] = []
    for rel in rules:
        if (src / rel).is_file():
            found.append(posix(rel))
    return sorted(found)


def init_git_repo(src: Path) -> None:
    run_git(src, ["init", "-q", "-b", "main"])
    run_git(src, ["add", "-f", "README.md", "plugin.json", "dist/app.py", ".gitignore", "rule.no-secrets.md"])
    run_git(src, ["commit", "-q", "-m", "cnf-0116 baseline benign"])
    # History name that is later deleted: proves history listing is not working-tree-only.
    write_bytes(src / ".env", FIXTURE_PLACEHOLDER)
    run_git(src, ["add", "-f", ".env"])
    run_git(src, ["commit", "-q", "-m", "cnf-0116 history credential-shaped name"])
    run_git(src, ["rm", "-f", "-q", ".env"])
    run_git(src, ["commit", "-q", "-m", "cnf-0116 remove working-tree env name"])
    # Force-track a gitignored credential-shaped file: ignore is not evidence.
    run_git(src, ["add", "-f", "secrets/planted.credentials.json"])
    run_git(src, ["commit", "-q", "-m", "cnf-0116 ignored-but-tracked planted name"])
    # Rotation-pool stays on disk, never added.


def git_names(repo: Path, args: list[str]) -> list[str]:
    p = run_git(repo, args, check=False)
    if p.returncode != 0:
        return []
    names = []
    for line in (p.stdout or "").split("\0" if "-z" in args else "\n"):
        line = line.strip()
        if line and not line.startswith("commit ") and " " not in line[:2]:
            if line.startswith("commit") or line.startswith("Author") or line.startswith("Date"):
                continue
            names.append(posix(line))
    # git log --name-only prints headers; filter empties and commit subjects we skipped poorly
    cleaned: list[str] = []
    skip_hdr = {"commit", "author:", "date:", "merge:"}
    for n in names:
        low = n.lower()
        if any(low.startswith(h) for h in skip_hdr):
            continue
        if n.endswith(".json") or n.endswith(".md") or n.endswith(".py") or n.startswith(".") or "/" in n or n.endswith(".credentials.json"):
            cleaned.append(n)
        elif Path(n).suffix or n in {ROTATION_POOL_BASENAME, ".env", "plugin.json"}:
            cleaned.append(n)
    return sorted(set(cleaned))


def git_ls_files(repo: Path) -> list[str]:
    p = run_git(repo, ["ls-files", "-z", "--cached"])
    return sorted({posix(x) for x in (p.stdout or "").split("\0") if x})


def git_staged(repo: Path) -> list[str]:
    p = run_git(repo, ["diff", "--cached", "--name-only", "-z"], check=False)
    return sorted({posix(x) for x in (p.stdout or "").split("\0") if x})


def git_history_names(repo: Path) -> list[str]:
    p = run_git(repo, ["log", "--all", "--name-only", "--pretty=format:"])
    names = []
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line:
            names.append(posix(line))
    return sorted(set(names))


def git_check_ignore(repo: Path, rel: str) -> bool:
    # --no-index: match the rule even when the path is already tracked.
    p = run_git(repo, ["check-ignore", "--no-index", "-q", rel], check=False)
    return p.returncode == 0


def git_is_tracked(repo: Path, rel: str) -> bool:
    p = run_git(repo, ["ls-files", "--error-unmatch", rel], check=False)
    return p.returncode == 0


def rotation_pool_state(repo: Path, expected_size: int, expected_mtime_ns: int) -> dict:
    path = repo / ROTATION_POOL_BASENAME
    exists = path.is_file()
    st = path.stat() if exists else None
    # Do not read bytes into the returned document. Size + mtime only.
    unmodified = bool(
        exists and st is not None and st.st_size == expected_size and st.st_mtime_ns == expected_mtime_ns
    )
    tracked = git_is_tracked(repo, ROTATION_POOL_BASENAME) if exists else False
    staged = ROTATION_POOL_BASENAME in git_staged(repo)
    ignored = git_check_ignore(repo, ROTATION_POOL_BASENAME) if exists else False
    return {
        "path": ROTATION_POOL_BASENAME,
        "exists": exists,
        "bytes": int(st.st_size) if st else 0,
        "tracked": tracked,
        "staged": staged,
        "ignored_by_rule": ignored,
        "unmodified": unmodified,
        "contents": None,
    }


def live_git_state(repo: Path) -> dict:
    p = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    inside = p.returncode == 0 and (p.stdout or "").strip() == "true"
    if not inside:
        return {
            "present": False,
            "unmeasurable": True,
            "reason": "not a git repository",
            "tracked": [],
            "staged": [],
            "history_names": [],
            "known_present_found": False,
            "method": "git rev-parse --is-inside-work-tree",
        }
    tracked = git_ls_files(repo)
    return {
        "present": True,
        "unmeasurable": False,
        "reason": None,
        "tracked": tracked,
        "staged": git_staged(repo),
        "history_names": git_history_names(repo),
        "known_present_found": False,  # filled by caller
        "method": "git ls-files -z --cached; git diff --cached --name-only -z; git log --all --name-only",
    }
