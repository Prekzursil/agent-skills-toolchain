"""Materialize a fake site-packages + console scripts without pip/setuptools."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

PROBE_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_FILES = [
    "tst0128pkg/__init__.py",
    "tst0128pkg/core.py",
    "tst0128pkg/extra.py",
    "tst0128run/__init__.py",
    "tst0128run/__main__.py",
    "tst0128run/collect.py",
    "tst0128run/console.py",
    "tst0128run/ci.py",
]
TEST_FILES = [
    "tests/test_core.py",
    "tests/test_extra.py",
]
PLANTED_OMIT = frozenset({"tst0128pkg/extra.py"})

WRAPPER = '''\
#!{python}
import os
import sys
from pathlib import Path

lib = Path(__file__).resolve().parents[1] / "lib"
cwd = os.getcwd()
stripped = [p for p in sys.path if p not in ("", cwd)]
sys.path[:] = [str(lib)] + stripped
from tst0128run.{mod} import main

if __name__ == "__main__":
    raise SystemExit(main())
'''


def materialize(dest: Path, planted: bool = False) -> Path:
    dest = dest.resolve()
    lib = dest / "lib"
    bindir = dest / "bin"
    lib.mkdir(parents=True, exist_ok=True)
    bindir.mkdir(parents=True, exist_ok=True)
    omit = PLANTED_OMIT if planted else frozenset()
    for rel in PACKAGE_FILES:
        if rel in omit:
            continue
        src = PROBE_ROOT / "src" / rel
        dst = lib / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    for rel in TEST_FILES:
        src = PROBE_ROOT / rel
        dst = lib / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    _write_wrapper(bindir / "tst0128-pytest", "console")
    _write_wrapper(bindir / "tst0128-ci", "ci")
    return dest


def _write_wrapper(path: Path, mod: str) -> None:
    text = WRAPPER.format(python=sys.executable, mod=mod)
    path.write_text(text, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
