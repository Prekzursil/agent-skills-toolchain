#!/usr/bin/env python3
"""AUD-0064 probe 1 - dispatcher surface enumeration (fail-closed tomllib).

Enumerates every live and repo-export monitor registry, resolves the mon
launcher, and verifies each declared route entry exists on disk. Windows
host adaptation: the prior wave measured the Linux worktree (tables ABSENT,
mon ABSENT); this host deploys the tables, so presence states are measured
live rather than compared against the Linux record.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[4]
UNIT = "AUD-0064"
TABLES = {
    "live-agents": HOME / ".agents" / "skills" / "monitor-launcher" / "monitors.toml",
    "live-claude": HOME / ".claude" / "skills" / "monitor-launcher" / "monitors.toml",
    "repo-export": REPO / "skills" / "monitor-launcher" / "monitors.toml",
}
LAUNCH_DIRS = [HOME / ".agents" / "skills" / "monitor-launcher"]


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    parsed: dict[str, dict] = {}
    for label, path in TABLES.items():
        if not path.is_file():
            print(f"TABLE|{label}|status=ABSENT|path={path.as_posix()}")
            continue
        try:
            with open(path, "rb") as fh:
                doc = tomllib.load(fh)
        except (tomllib.TOMLDecodeError, OSError) as exc:
            return fail(f"table {label} failed-closed parse: {exc}")
        parsed[label] = doc
        print(f"TABLE|{label}|status=PRESENT|path={path.as_posix()}|routes={len(doc)}")

    if not parsed:
        return fail("no monitor registry present on any surface")
    base = parsed.get("live-agents") or next(iter(parsed.values()))
    if not base:
        return fail("live table declares no routes")
    launcher = None
    for d in LAUNCH_DIRS:
        for cand in ("mon.cmd", "mon.exe", "mon.bat", "mon"):
            if (d / cand).is_file():
                launcher = d / cand
                break
        if launcher:
            break
    state = "PRESENT" if launcher else "ABSENT"
    print(f"LAUNCHER|mon|resolved={state}" + (f"|path={launcher.as_posix()}" if launcher else ""))
    missing = []
    for name in sorted(base):
        row = base[name]
        d = str(row.get("dir") or "")
        entry = str(row.get("entry") or "")
        if not d or not entry:
            return fail(f"route {name} missing dir/entry")
        dpath = Path(d)
        if not dpath.is_absolute():
            dpath = HOME / ".agents" / "skills" / d
        if not (dpath / entry).is_file():
            missing.append(f"{name}: {(dpath / entry).as_posix()}")
    if missing:
        for m in missing:
            print(f"  ENTRY-MISSING {m}")
        return fail(f"{len(missing)} route entries unresolved")
    print(f"routes={len(base)} all entry scripts resolve on disk")
    print(f"SUCCESS:{UNIT}-probe1 dispatcher surfaces enumerated fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
