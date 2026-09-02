"""Hermetic wheel install into a prefix. Does not put the repo on sys.path."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BUILDER = REPO / "tools" / "packaging" / "ast_examples" / "build_wheel.py"
SRC_PKG = REPO / "tools" / "packaging" / "ast_examples" / "src"


def repo_on_path(path: str | Path) -> bool:
    resolved = str(Path(path).resolve())
    root = str(REPO.resolve())
    return resolved == root or resolved.startswith(root + os.sep)


def build_wheel(work: Path) -> Path:
    dist = work / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-B", str(BUILDER), str(dist)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"wheel build failed: {proc.stdout}\n{proc.stderr}")
    wheels = list(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel, got {wheels}")
    return wheels[0]


def install_wheel(wheel: Path, prefix: Path) -> dict[str, Path]:
    site = prefix / "lib" / "site-packages"
    bindir = prefix / "bin"
    site.mkdir(parents=True, exist_ok=True)
    bindir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        if any(n.endswith("_source_tree_only.py") for n in names):
            raise RuntimeError("wheel contains source-tree-only module")
        zf.extractall(site)
    launcher = bindir / "ast-examples"
    site_s = str(site.resolve())
    # python -I ignores PYTHONPATH and cwd; SITE is the only extra path.
    script = (
        "#!/bin/sh\n"
        f'exec {sys.executable} -I -B -c '
        f'"import sys; sys.path.insert(0, {site_s!r}); '
        f'from ast_examples.cli import main; raise SystemExit(main())" "$@"\n'
    )
    launcher.write_text(script, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return {"prefix": prefix, "site": site, "launcher": launcher}


def isolated_python_cmd(site: Path, snippet: str) -> list[str]:
    site_s = str(site.resolve())
    return [
        sys.executable,
        "-I",
        "-B",
        "-c",
        f"import sys; sys.path.insert(0, {site_s!r}); {snippet}",
    ]


def clean_profile(work: Path) -> Path:
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def with_workspace() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="tst0115-")
