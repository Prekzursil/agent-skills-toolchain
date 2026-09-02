"""Repo-root shim: load production modules from tools/router.

02.09 (P2 G-1 resolution fix): the root package held 7 generated ``_NS`` placeholders and
3 re-export stubs and shadowed the real ``tools/router`` code (repo root precedes ``tools/`` on
the measurement PYTHONPATH). Same shape as the ``marketplace``/``plugin``/``workflow_foundry``
shims; this directory stays as a second search entry only until its remaining files are
retired.
"""
from pathlib import Path

_HERE = Path(__file__).resolve().parent
__path__ = [str(_HERE.parent / "tools" / "router"), str(_HERE)]
