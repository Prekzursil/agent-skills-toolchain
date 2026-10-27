#!/usr/bin/env python3
"""Insert the stdlib-shadow scrub into affected probe entry files."""
from __future__ import annotations

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

TARGETS = [
    "command-center/p2-wave/probes/AUD-0033/probe1_extract_existence.py",
    "command-center/p2-wave/probes/AUD-0033/probe2_git_log_missing.py",
    "command-center/p2-wave/probes/AUD-0043/probe1_source_pytest.py",
    "command-center/p2-wave/probes/AUD-0043/probe2_installed_console.py",
    "command-center/p2-wave/probes/AUD-0066/probe1_os_state.py",
    "command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health.py",
]


def main() -> int:
    for rel in TARGETS:
        p = P2 / rel
        if not p.is_file():
            print(rel, "ABSENT")
            continue
        text = p.read_text(encoding="utf-8")
        if "shard2-resume 2026-10-24" in text:
            print(rel, "already-patched")
            continue
        marker = "from __future__ import annotations\n"
        idx = text.find(marker)
        if idx < 0:
            print(rel, "no-future-import; skipped")
            continue
        at = idx + len(marker)
        p.write_text(text[:at] + SCRUB + text[at:], encoding="utf-8", newline="\n")
        print(rel, "patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
