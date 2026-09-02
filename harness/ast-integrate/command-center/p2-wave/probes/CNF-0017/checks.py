"""Named baseline-failure checks. Read HOME (and PATH) from the environment.

Exit convention used by run_check.py: return True when the failure is
OBSERVED (the baseline defect still fires), False when it does not fire.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CRLF_FIXTURE = HERE / "fixtures" / "crlf_sample.txt"
TDD_DIR = HERE / "fixtures" / "tdd"


def home() -> Path:
    raw = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    if not raw:
        raise RuntimeError("HOME/USERPROFILE unset")
    return Path(raw)


def ensure_tree_fixtures() -> None:
    """Tree-local fixtures (not HOME). Identical for both profile runs."""
    CRLF_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    CRLF_FIXTURE.write_bytes(b"gated-crlf-sample\r\nline-two\r\n")
    TDD_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        (TDD_DIR / f"red_{i}.py").write_text(
            f"# sibling TDD red stand-in {i}\n"
            f"VALUE_{i} = 'RED'\n"
            f"assert VALUE_{i} == 'GREEN'\n",
            encoding="utf-8",
        )


def _listing(rel_under_home: str) -> list[Path]:
    root = home() / rel_under_home
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def check_crlf_worktree_fixture() -> bool:
    """Recorded CRLF class: committed/fixture bytes contain CR. Tree property."""
    ensure_tree_fixtures()
    raw = CRLF_FIXTURE.read_bytes()
    return b"\r\n" in raw


def check_git_autocrlf() -> bool:
    """Recorded CRLF class mediated by user gitconfig (HOME)."""
    p = subprocess.run(
        ["git", "config", "--global", "--get", "core.autocrlf"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    val = (p.stdout or "").strip().lower()
    return val in {"true", "1", "on"}


def check_scratch_checkout_crlf() -> bool:
    """Recorded CRLF class: checkout under this HOME's gitconfig yields CRLF."""
    git = shutil.which("git")
    if not git:
        return False
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "cnf-0017")
    env.setdefault("GIT_AUTHOR_EMAIL", "cnf-0017@local")
    env.setdefault("GIT_COMMITTER_NAME", "cnf-0017")
    env.setdefault("GIT_COMMITTER_EMAIL", "cnf-0017@local")
    with tempfile.TemporaryDirectory(prefix="cnf0017-scratch-") as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        (src / "sample.txt").write_bytes(b"hello-lf\n")
        def git_cmd(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [git, *args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                env=env,
            )
        # Seed repo with identity local to the repo, not the profile.
        for cmd in (
            ["init", "-q"],
            ["config", "user.email", "cnf-0017@local"],
            ["config", "user.name", "cnf-0017"],
            ["add", "sample.txt"],
            ["commit", "-q", "-m", "seed"],
        ):
            r = git_cmd(*cmd, cwd=src)
            if r.returncode != 0:
                return False
        dest = Path(tmp) / "clone"
        r = git_cmd("clone", "-q", str(src), str(dest), cwd=Path(tmp))
        if r.returncode != 0:
            return False
        raw = (dest / "sample.txt").read_bytes()
        return b"\r\n" in raw


def check_tdd(n: int) -> bool:
    """Recorded sibling-TDD-red class: tree fixture still red (not HOME)."""
    ensure_tree_fixtures()
    path = TDD_DIR / f"red_{n}.py"
    p = subprocess.run(
        [sys.executable, "-B", str(path)],
        capture_output=True,
        text=True,
        cwd=str(TDD_DIR),
    )
    return p.returncode != 0


def check_posix_only() -> bool:
    """Recorded POSIX-only class. Fires on POSIX regardless of HOME."""
    return os.name == "posix" and Path("/dev/null").exists()


def check_plugin_accum() -> bool:
    files = _listing(".claude/plugins") + _listing(".cursor/plugins")
    return len(files) > 0


def check_skill_accum() -> bool:
    files = _listing(".claude/skills") + _listing(".cursor/skills")
    return len(files) > 0


def check_mcp_accum() -> bool:
    for rel in (".cursor/mcp.json", ".claude/mcp.json", ".cursor/mcp.json"):
        p = home() / rel
        if p.is_file() and p.stat().st_size > 0:
            return True
    return False


def check_path_shim() -> bool:
    found = shutil.which("cnf0017-shim")
    return found is not None


CHECKS: dict[str, callable] = {
    "BL-CRLF-01-worktree-fixture": check_crlf_worktree_fixture,
    "BL-CRLF-02-git-autocrlf": check_git_autocrlf,
    "BL-CRLF-03-scratch-checkout": check_scratch_checkout_crlf,
    "BL-TDD-01": lambda: check_tdd(1),
    "BL-TDD-02": lambda: check_tdd(2),
    "BL-TDD-03": lambda: check_tdd(3),
    "BL-TDD-04": lambda: check_tdd(4),
    "BL-POSIX-01": check_posix_only,
    "BL-PLUGIN-ACCUM": check_plugin_accum,
    "BL-SKILL-ACCUM": check_skill_accum,
    "BL-MCP-ACCUM": check_mcp_accum,
    "BL-PATH-SHIM": check_path_shim,
}

CHECK_IDS = list(CHECKS.keys())
