"""Cross-platform probe: does the gated launch actually work on LINUX, not just on this box?

`launchpath.py` runs in CI on `ubuntu-latest`, and every local run of it so far has been Windows.
A Windows-only green is exactly the shape this program keeps getting burnt by, so this
materialises the SAME committed blobs the gate materialises and runs the entry under the local
WSL2 Ubuntu interpreter instead of the Windows one.

It is a PROBE, not a gate: it is never wired into CI (it needs `wsl.exe`, which no runner has),
and it exits non-zero only to make a failure visible to the operator who ran it.

Control: every probed entry is run twice, once under Windows Python and once under Linux Python,
and BOTH must render that probe's own marker. If the Linux leg cannot even start (no WSL, no
python3), that is reported as NOT-CHECKED rather than folded into a pass.

WHY THIS READS THE REGISTRY AND `lp.PROBES` INSTEAD OF HARDCODING ONE ENTRY. Measured 2026-08-15:
this file used to pin `ENTRY = unified_board.py` with the cockpit's arguments while taking its
marker from `lp.PROBES[0].require`. Those are two sources of truth for one fact, and the moment a
second Probe was added ahead of the cockpit the marker silently became another monitor's. Both
legs then reported FAIL with `marker=False` against stdout that had rendered perfectly - a false
red produced entirely by the index. Resolving each entry and each marker from the SAME Probe
removes the coupling, and iterating every probe means a monitor promoted into the CI-wired gate
cannot reach `ubuntu-latest` without having been run on Linux here first.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launchpath as lp  # noqa: E402

TARGET = "skills/workflow-monitor"
REGISTRY = "skills/monitor-launcher/monitors.toml"


def _wsl_path(win: Path) -> str:
    drive, rest = str(win.resolve()).split(":", 1)
    return f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"


def _resolve_entries(oids: dict[str, str], blobs: dict[str, bytes]) -> dict[str, str]:
    """monitor name -> repo-relative entry path, read from the registry the gate uses."""
    stanzas = lp.parse_stanzas(blobs[oids[REGISTRY]], REGISTRY)
    root = lp.skills_root(REGISTRY)
    entries: dict[str, str] = {}
    for name, stanza in stanzas.items():
        directory, entry = stanza.get("dir"), stanza.get("entry")
        if isinstance(directory, str) and isinstance(entry, str):
            entries[name] = f"{root}/{directory}/{entry}"
    return entries


def _materialise_argv(
    probe: lp.Probe, dest: Path, *, as_linux: bool
) -> tuple[list[str], list[Path]]:
    """Substitute each EMPTY_DIR token with a FRESH directory, addressed for the target OS."""
    argv: list[str] = []
    made: list[Path] = []
    for item in probe.argv_tail:
        if item != lp.EMPTY_DIR:
            argv.append(item)
            continue
        created = dest / f"_empty_{probe.monitor}_{len(made)}"
        created.mkdir(parents=True, exist_ok=True)
        made.append(created)
        argv.append(_wsl_path(created) if as_linux else str(created))
    return argv, made


def _verdict(label: str, probe: lp.Probe, code: int | None, out: str) -> bool:
    if code is None:
        print(f"  [NOT-CHECKED] {label}: interpreter unavailable")
        return False
    marker = probe.require in out
    ok = code == 0 and marker
    tail = " | ".join(ln.strip() for ln in out.splitlines() if ln.strip())[:110]
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}: exit={code} "
        f"marker={marker!s:5} want={probe.require!r} :: {tail}"
    )
    return ok


def main() -> int:
    oids = lp.index_oids(lp.REPO)
    if REGISTRY not in oids:
        print(f"FAILED:launchpath-linux {REGISTRY} is not tracked")
        return 1
    subtree = {p: o for p, o in oids.items() if p.startswith(f"{TARGET}/")}
    if not subtree:
        print(f"FAILED:launchpath-linux {TARGET}/ holds ZERO tracked files")
        return 1
    blobs = lp.read_blobs(lp.REPO, [*subtree.values(), oids[REGISTRY]])
    entries = _resolve_entries(oids, blobs)

    probes = [
        p for p in lp.PROBES if entries.get(p.monitor, "").startswith(f"{TARGET}/")
    ]
    if not probes:
        print(f"FAILED:launchpath-linux no shipped Probe resolves into {TARGET}/")
        return 1

    have_wsl = shutil.which("wsl.exe") is not None
    legs: list[bool] = []

    with tempfile.TemporaryDirectory(prefix="launchpath-linux-") as tmp:
        dest = Path(tmp)
        written = lp.materialise(blobs, subtree, dest)
        print(f"  materialised {written} committed blobs to {dest}")
        if written == 0:
            print("FAILED:launchpath-linux materialised ZERO files")
            return 1

        for probe in probes:
            entry = entries[probe.monitor]
            print(f"  --- [{probe.monitor}] -> {entry}")

            win_argv, _ = _materialise_argv(probe, dest, as_linux=False)
            win = subprocess.run(
                [sys.executable, str(dest / entry), *win_argv],
                capture_output=True,
                cwd=str(dest),
                timeout=240,
                check=False,
            )
            legs.append(
                _verdict(
                    f"windows {sys.version.split()[0]}",
                    probe,
                    win.returncode,
                    win.stdout.decode("utf-8", "replace"),
                )
            )

            if not have_wsl:
                legs.append(_verdict("linux (wsl)", probe, None, ""))
                continue
            linux_argv, _ = _materialise_argv(probe, dest, as_linux=True)
            wsl = subprocess.run(
                [
                    "wsl.exe",
                    "-d",
                    "Ubuntu",
                    "-e",
                    "python3",
                    f"{_wsl_path(dest)}/{entry}",
                    *linux_argv,
                ],
                capture_output=True,
                timeout=300,
                check=False,
            )
            legs.append(
                _verdict(
                    "linux (wsl Ubuntu)",
                    probe,
                    wsl.returncode,
                    wsl.stdout.decode("utf-8", "replace"),
                )
            )

    if all(legs) and legs:
        print(
            f"SUCCESS:launchpath-linux {len(probes)} probed monitor(s) render on BOTH platforms"
        )
        return 0
    print("FAILED:launchpath-linux at least one platform did not render (see above)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
