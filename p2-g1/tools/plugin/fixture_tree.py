"""Git fixture trees for IMP-0045 conformance mutations."""
from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Callable


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    e = os.environ.copy()
    if env:
        e.update(env)
    e.setdefault("GIT_AUTHOR_NAME", "imp0045")
    e.setdefault("GIT_AUTHOR_EMAIL", "imp0045@example.invalid")
    e.setdefault("GIT_COMMITTER_NAME", "imp0045")
    e.setdefault("GIT_COMMITTER_EMAIL", "imp0045@example.invalid")
    p = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=e,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr or p.stdout)
    return (p.stdout or "").strip()


def good_files() -> dict[str, bytes]:
    manifest = {
        "name": "demo-plugin",
        "version": "1.0.0",
        "license": "MIT",
        "interpreters": ["python3"],
        "entrypoints": ["plugin.py"],
        "permissions": ["fs:read"],
        "projection": {"plugin.py": "plugin.py"},
    }
    return {
        "plugin.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "plugin.py": b"print('ok')\n",
        "LICENSE": b"MIT License\n",
    }


def _mut_manifest(files: dict[str, bytes], **patch) -> dict[str, bytes]:
    out = deepcopy(files)
    doc = json.loads(out["plugin.json"].decode("utf-8"))
    doc.update(patch)
    out["plugin.json"] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    return out


def _drop_license(files: dict[str, bytes]) -> dict[str, bytes]:
    out = deepcopy(files)
    out.pop("LICENSE", None)
    return out


def _drop_entry(files: dict[str, bytes]) -> dict[str, bytes]:
    out = deepcopy(files)
    out.pop("plugin.py", None)
    return out


def _bad_json(files: dict[str, bytes]) -> dict[str, bytes]:
    out = deepcopy(files)
    out["plugin.json"] = b"{not-json"
    return out


def _perm_mismatch(files: dict[str, bytes]) -> dict[str, bytes]:
    return _mut_manifest(files, permissions=["net:connect"])


def _bad_projection(files: dict[str, bytes]) -> dict[str, bytes]:
    return _mut_manifest(files, projection={"plugin.py": "missing.py"})


def _missing_interpreter(files: dict[str, bytes]) -> dict[str, bytes]:
    return _mut_manifest(files, interpreters=["python99-missing"])


MUTATIONS: list[tuple[str, str, Callable]] = [
    ("MANIFEST_SCHEMA", "corrupt plugin.json", _bad_json),
    ("INTERPRETER_MISSING", "unknown interpreter", _missing_interpreter),
    ("ENTRYPOINT_MISSING", "drop plugin.py", _drop_entry),
    ("PERMISSION_MISMATCH", "declare unused net", _perm_mismatch),
    ("PROJECTION_STALE", "projection target missing", _bad_projection),
    ("LICENSE_ABSENT", "drop LICENSE", _drop_license),
    ("DIGEST_MISMATCH", "empty name", lambda f: _mut_manifest(f, name="")),
]


def build_tree(files: dict[str, bytes], dest: Path) -> tuple[Path, str]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    work = dest / "wt"
    git_dir = dest / "git"
    work.mkdir()
    git_dir.mkdir()
    env = {"GIT_DIR": str(git_dir), "GIT_WORK_TREE": str(work)}
    _git(work, "init", env=env)
    _git(work, "config", "core.autocrlf", "false", env=env)
    for rel, data in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        _git(work, "add", rel, env=env)
    _git(work, "commit", "-m", "fixture", env=env)
    tree = _git(work, "rev-parse", "HEAD^{tree}", env=env)
    return git_dir, tree
