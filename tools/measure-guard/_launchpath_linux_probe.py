"""Cross-platform probe: does the gated launch actually work on LINUX, not just on this box?

`launchpath.py` runs in CI on `ubuntu-latest`, and every local run of it so far has been Windows.
A Windows-only green is exactly the shape this program keeps getting burnt by, so this
materialises the SAME committed blobs the gate materialises and runs the entry under the local
WSL2 Ubuntu interpreter instead of the Windows one.

It is a PROBE, not a gate: it is never wired into CI (it needs `wsl.exe`, which no runner has),
and it exits non-zero only to make a failure visible to the operator who ran it.

Control: the same script is run twice, once under Windows Python and once under Linux Python, and
BOTH must render the marker. If the Linux leg cannot even start (no WSL, no python3), that is
reported as NOT-CHECKED rather than folded into a pass.
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
ENTRY = f"{TARGET}/unified_board.py"
ARGS = ["--once", "--pane", "health", "--width", "100"]


def _wsl_path(win: Path) -> str:
    drive, rest = str(win.resolve()).split(":", 1)
    return f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"


def _verdict(label: str, code: int | None, out: str) -> bool:
    if code is None:
        print(f"  [NOT-CHECKED] {label}: interpreter unavailable")
        return False
    marker = lp.PROBES[0].require in out
    ok = code == 0 and marker
    tail = " | ".join(ln.strip() for ln in out.splitlines() if ln.strip())[:120]
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}: exit={code} marker={marker} :: {tail}"
    )
    return ok


def main() -> int:
    oids = lp.index_oids(lp.REPO)
    subtree = {p: o for p, o in oids.items() if p.startswith(f"{TARGET}/")}
    if ENTRY not in subtree:
        print(f"FAILED:launchpath-linux {ENTRY} is not tracked")
        return 1
    blobs = lp.read_blobs(lp.REPO, subtree.values())

    with tempfile.TemporaryDirectory(prefix="launchpath-linux-") as tmp:
        dest = Path(tmp)
        written = lp.materialise(blobs, subtree, dest)
        print(f"  materialised {written} committed blobs to {dest}")

        win = subprocess.run(
            [sys.executable, str(dest / ENTRY), *ARGS],
            capture_output=True,
            cwd=str(dest),
            timeout=240,
            check=False,
        )
        legs = [
            _verdict(
                "windows " + sys.version.split()[0],
                win.returncode,
                win.stdout.decode("utf-8", "replace"),
            )
        ]

        if shutil.which("wsl.exe") is None:
            legs.append(_verdict("linux (wsl)", None, ""))
        else:
            linux_entry = f"{_wsl_path(dest)}/{ENTRY}"
            wsl = subprocess.run(
                ["wsl.exe", "-d", "Ubuntu", "-e", "python3", linux_entry, *ARGS],
                capture_output=True,
                timeout=300,
                check=False,
            )
            legs.append(
                _verdict(
                    "linux (wsl Ubuntu)",
                    wsl.returncode,
                    wsl.stdout.decode("utf-8", "replace"),
                )
            )

    if all(legs):
        print("SUCCESS:launchpath-linux the gated launch renders on BOTH platforms")
        return 0
    print("FAILED:launchpath-linux at least one platform did not render (see above)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
