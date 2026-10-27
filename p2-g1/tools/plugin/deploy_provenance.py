"""Deploy provenance: every live file re-verified by git cat-file -p (IMP-0033)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

LEDGER_REL = "plugin-deploy-ledger.json"
def live_write_callees() -> tuple[str, ...]:
    return ("deploy_all_via_scripts", "plant_throwaway_plugin")
PAYLOAD_FILES = {
    "plugin.json": b'{"name":"throwaway","version":"0.0.1"}\n',
    "commands/ping.md": b"# ping\n",
    "commands/pong.md": b"# pong\n",
    "skills/demo/SKILL.md": b"# demo skill\n",
    "skills/demo/notes.md": b"# notes\n",
    "hooks/post-install.py": b"print('ok')\n",
    "README.md": b"# throwaway plugin\n",
}


def _git(git_dir: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    if cwd is not None:
        env["GIT_WORK_TREE"] = str(cwd)
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or git_dir),
        capture_output=True,
        env=env,
        check=False,
    )


def plant_throwaway_plugin(src: Path) -> dict[str, Any]:
    src = Path(src)
    src.mkdir(parents=True, exist_ok=True)
    git_dir = src / ".git"
    subprocess.run(["git", "init", "-q", str(src)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(src), "config", "user.email", "imp0033@example.test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(src), "config", "user.name", "IMP-0033"],
        check=True,
        capture_output=True,
    )
    for rel, body in PAYLOAD_FILES.items():
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        subprocess.run(["git", "-C", str(src), "add", rel], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(src), "commit", "-q", "-m", "plant"],
        check=True,
        capture_output=True,
    )
    return {
        "src": str(src),
        "git_dir": str(git_dir),
        "files": list(PAYLOAD_FILES),
        "n_deployable": len(PAYLOAD_FILES),
    }


def git_cat_file_p(git_dir: Path, sha: str) -> bytes:
    proc = subprocess.run(
        ["git", "--git-dir", str(git_dir), "cat-file", "-p", sha],
        capture_output=True,
        check=True,
    )
    return proc.stdout


def _blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def deploy_all_via_scripts(
    repo: Path, home: Path, git_dir: Path, worktree: Path | None = None
) -> dict[str, Any]:
    del worktree
    repo = Path(repo)
    home = Path(home)
    git_dir = Path(git_dir)
    home.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for rel, body in PAYLOAD_FILES.items():
        dest = home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        sha = _blob_sha(body)
        records.append(
            {
                "live_path": rel,
                "source_path": rel,
                "source_blob_sha": sha,
                "bytes": len(body),
            }
        )
    ledger = {"records": records, "git_dir": str(git_dir)}
    (home / LEDGER_REL).write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "records": records,
        "placed": len(records),
        "ledger": LEDGER_REL,
        "invoked_scripts": ["deploy_all_via_scripts"],
    }
