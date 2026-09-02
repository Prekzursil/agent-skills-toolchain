"""Isolated git repo + zip package + deployed tree for REL-0021 controls."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Optional

from parity import run_git

KNOWN_PATH = "shipped/known.txt"
KNOWN_LF = b"alpha\nbeta\ngamma\ndelta\n"

# git / package / deployed bytes; None means absent from that copy.
CONTROL_SPEC: dict[str, dict[str, Optional[bytes]]] = {
    "shipped/ok.txt": {
        "git": b"shared-ok-body\n",
        "package": b"shared-ok-body\n",
        "deployed": b"shared-ok-body\n",
    },
    "shipped/eol.txt": {
        "git": b"line-a\nline-b\n",
        "package": b"line-a\r\nline-b\r\n",
        "deployed": b"line-a\r\nline-b\r\n",
    },
    KNOWN_PATH: {
        "git": KNOWN_LF,
        "package": KNOWN_LF,
        "deployed": KNOWN_LF,
    },
    "shipped/pkg-only.txt": {
        "git": None,
        "package": b"only-in-package\n",
        "deployed": None,
    },
    "shipped/owner-note.txt": {
        "git": None,
        "package": None,
        "deployed": b"OWNER-AUTHORED keep this file\nunique-deployed-payload\n",
    },
    "shipped/twoway.txt": {
        "git": b"SHARED-LINE\nREPO-UNIQUE-alpha\n",
        "package": b"SHARED-LINE\nREPO-UNIQUE-alpha\n",
        "deployed": b"SHARED-LINE\nDEPLOYED-UNIQUE-omega\n",
    },
}

HEALTHY_PATHS = ("shipped/ok.txt", "shipped/eol.txt", KNOWN_PATH)


def _subset(
    spec: dict[str, dict[str, Optional[bytes]]], paths: tuple[str, ...]
) -> dict[str, dict[str, Optional[bytes]]]:
    return {p: spec[p] for p in paths}


def _write_git_repo(repo: Path, spec: dict[str, dict[str, Optional[bytes]]]) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run_git(repo, ["init", "-q"])
    run_git(repo, ["config", "user.email", "rel-0021@fixture.test"])
    run_git(repo, ["config", "user.name", "REL-0021 fixture"])
    run_git(repo, ["config", "core.autocrlf", "false"])
    run_git(repo, ["config", "core.eol", "lf"])
    for rel, copies in spec.items():
        blob = copies.get("git")
        if blob is None:
            continue
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    run_git(repo, ["add", "-A"])
    run_git(repo, ["commit", "-qm", "REL-0021 LF blobs"])
    (repo / ".gitattributes").write_text(f"{KNOWN_PATH} text eol=crlf\n", encoding="utf-8")
    run_git(repo, ["add", ".gitattributes"])
    run_git(repo, ["commit", "-qm", "REL-0021 archive-filter attr"])


def _write_package(zip_path: Path, spec: dict[str, dict[str, Optional[bytes]]]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel, copies in spec.items():
            data = copies.get("package")
            if data is None:
                continue
            zf.writestr(rel, data)


def _write_deployed(root: Path, spec: dict[str, dict[str, Optional[bytes]]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, copies in spec.items():
        data = copies.get("deployed")
        if data is None:
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def materialize(root: Path, spec: dict[str, dict[str, Optional[bytes]]]) -> dict[str, Any]:
    repo = root / "git"
    deployed = root / "deployed"
    package = root / "package.zip"
    _write_git_repo(repo, spec)
    _write_package(package, spec)
    _write_deployed(deployed, spec)
    return {
        "root": root,
        "repo": repo,
        "deployed": deployed,
        "package_zip": package,
        "spec": spec,
        "known_path": KNOWN_PATH,
    }


def build_control(root: Path) -> dict[str, Any]:
    world = materialize(root, CONTROL_SPEC)
    world["kind"] = "control"
    return world


def build_healthy(root: Path) -> dict[str, Any]:
    world = materialize(root, _subset(CONTROL_SPEC, HEALTHY_PATHS))
    world["kind"] = "healthy"
    return world
