#!/usr/bin/env python3
"""Shard2 resume fix batch (2026-10-24): three failure classes.

1. stdlib-shadow scrub: the G-1 runner puts the repo root on PYTHONPATH; the
   repo's namespace dirs (platform/ ...) shadow stdlib modules on this
   interpreter (attrs does `import platform` and dies). Patch = strip the repo
   root from sys.path/PYTHONPATH at the top of affected probe entries.
2. AUD-0084 fixture rebuild: fixtures/use_vs_mention_fixture.py vanished from
   both trees; rebuilt from the asserted contract in census.evaluate_control
   and verified locally against census's own classifier.
3. AUD-0096 loadset copy tolerance: skip files that vanish mid-copy (race with
   concurrent sessions touching ~/.claude/skills) instead of crashing.
"""
from __future__ import annotations

import sys
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")

SCRUB = """
# shard2-resume 2026-10-24: the G-1 runner puts the repo root on sys.path via
# PYTHONPATH; the repo's namespace dirs (platform/, schema/, ...) shadow stdlib
# modules on this interpreter (attrs does `import platform` and dies). Strip
# the repo root from sys.path and PYTHONPATH before any third-party import.
import os as _os, sys as _sys  # noqa: E401
from pathlib import Path as _Path

_repo = None
for _cand in _Path(__file__).resolve().parents:
    if (_cand / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
        _repo = _cand
        break
if _repo is not None:
    _sys.path = [p for p in _sys.path if not p or _Path(p).resolve() != _repo]
    _os.environ["PYTHONPATH"] = _os.pathsep.join(
        p for p in _os.environ.get("PYTHONPATH", "").split(_os.pathsep)
        if p and _Path(p).resolve() != _repo)
"""


def scrub_entry(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "shard2-resume 2026-10-24" in text:
        return "already-patched"
    marker = "from __future__ import annotations\n"
    idx = text.find(marker)
    if idx < 0:
        return "no-future-import; skipped"
    at = idx + len(marker)
    path.write_text(text[:at] + SCRUB + text[at:], encoding="utf-8", newline="\n")
    return "patched"
