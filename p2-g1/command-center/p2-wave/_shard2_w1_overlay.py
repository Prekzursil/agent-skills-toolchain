#!/usr/bin/env python3
"""Deployed-overlay re-application for shard2 resume.

port_probes() re-copies pristine canonical probe files, which would clobber
the deployed repairs. This module holds every overlay as an idempotent,
marker-checked function applied AFTER each port:
  * stdlib-shadow scrub into probe[12]*.py entry files (all units)
  * AUD-0084 fixture rebuild (vanished from canonical)
  * AUD-0096 loadset copy-tolerance (vanish-race)
  * AUD-0080 probe1 live-control re-anchor (Shell(ls) -> Shell(*) estate drift)
"""
from __future__ import annotations

import sys
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
PROBES = P2 / "command-center/p2-wave/probes"

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


def apply_scrub(uid: str) -> list[str]:
    done = []
    pdir = PROBES / uid
    for entry in sorted(pdir.glob("probe[12]*.py")):
        if entry.name in ("probe1.py", "probe2.py"):
            continue
        text = entry.read_text(encoding="utf-8")
        if "shard2-resume 2026-10-24" in text:
            continue
        marker = "from __future__ import annotations\n"
        idx = text.find(marker)
        if idx < 0:
            continue
        at = idx + len(marker)
        entry.write_text(text[:at] + SCRUB + text[at:], encoding="utf-8", newline="\n")
        done.append(entry.name + "+scrub")
    return done


def apply_fixture_0084() -> list[str]:
    fixdir = PROBES / "AUD-0084" / "fixtures"
    fixdir.mkdir(parents=True, exist_ok=True)
    fixture = fixdir / "use_vs_mention_fixture.py"
    if fixture.exists():
        return []
    script = P2 / "command-center/p2-wave/_shard2_w1_fixtures.py"
    if script.is_file():
        code = script.read_text(encoding="utf-8")
        ns = {"__name__": "overlay"}
        exec(compile(code, str(script), "exec"), ns)  # noqa: S102 - own script
        ns["main"]()
        return ["fixture-0084-rebuilt"]
    return ["fixture-0084-MISSING-SCRIPT"]


def _run_patch_script(script: Path, tag: str) -> list[str]:
    if not script.is_file():
        return [tag + "-MISSING-SCRIPT"]
    code = script.read_text(encoding="utf-8")
    ns = {"__name__": "overlay"}
    exec(compile(code, str(script), "exec"), ns)  # noqa: S102 - own script
    rc = ns["main"]()
    return [tag + (":ok" if rc == 0 else ":rc%s" % rc)]


def apply_overlays(uid: str) -> list[str]:
    applied = apply_scrub(uid)
    if uid == "AUD-0084":
        applied += apply_fixture_0084()
    if uid == "AUD-0096":
        applied += _run_patch_script(
            P2 / "command-center/p2-wave/_shard2_w1_loadset.py", "loadset-0096")
    if uid == "AUD-0080":
        applied += _run_patch_script(
            P2 / "command-center/p2-wave/_shard2_w1_anchor.py", "anchor-0080")
    return applied


if __name__ == "__main__":
    import sys as _s
    for _uid in (_s.argv[1:] or []):
        for _line in apply_overlays(_uid):
            print(_line)
