"""Repo-root shim: load production modules from tools/council.

02.09 (P2 G-1 resolution fix): this package used to be a real package of 72 generated ``_NS``
placeholders + 7 re-export stubs, and because the measurement puts the repo root before
``tools/`` on PYTHONPATH it shadowed the real ``tools/council`` code for every probe that
imported ``council.*``. Same shape as the ``marketplace``/``plugin``/``workflow_foundry``
shims, plus this directory as a SECOND search entry so the two surfaces that exist only here
(``council.builder``, ``council.tests``) keep resolving until their real implementations move
under ``tools/council``.
"""
from pathlib import Path

_HERE = Path(__file__).resolve().parent
__path__ = [str(_HERE.parent / "tools" / "council"), str(_HERE)]
