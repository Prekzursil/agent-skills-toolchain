"""Make ``import plugin`` work no matter where pytest is invoked from.

``platform/`` is prepended to ``sys.path`` so the package resolves by its own name, matching
``platform/lib/wfdsl/conftest.py``. There is deliberately no ``platform/__init__.py``: a regular
stdlib module always outranks an implicit namespace package, so ``import platform`` keeps
resolving to the standard library — but turning the build root into a real package would shadow it.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

BUILD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def built_package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the real package once per session; every package-level test reads this artifact."""
    from plugin.build import build

    out = tmp_path_factory.mktemp("dist")
    result, _payload = build(REPO_ROOT, out)
    return result.archive


@pytest.fixture
def workdir() -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix="astplugin-test-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
