r"""Why `NUL`'s writer was never identified: Python cannot see the file at all.

`NUL` is a RESERVED DOS DEVICE NAME on Windows. Any ordinary Win32 path ending in
`NUL` is parsed as the null device BEFORE the filesystem is consulted, so
`os.path.getsize(repo/'NUL')` returns 0 for the device while `ls -la` reports the
real on-disk file. Every Python census this lane ran therefore measured the device.

The extended-length prefix `\\?\` disables that parsing and reaches the real file.

CONTROL, both states:
  * negative -- the plain path must report the DEVICE (size 0, unreadable content).
  * positive -- the `\\?\` path must report a NON-zero size matching `git ls-files -s`
    / `ls`, and its bytes must be readable. If both routes agreed, this probe would
    prove nothing.
  * a second positive control on an ORDINARY file (this script) must give the same
    answer on both routes -- proving the `\\?\` route is not simply inflating sizes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
WIN = REPO.replace("/", "\\")


def size_of(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def head_bytes(path: str, n: int = 64) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read(n).hex()
    except OSError as exc:
        return f"<error {exc.__class__.__name__}>"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def main() -> int:
    plain = f"{WIN}\\NUL"
    ext = f"\\\\?\\{WIN}\\NUL"

    self_plain = f"{WIN}\\command-center\\slop-report\\_r4_nul.py"
    self_ext = f"\\\\?\\{self_plain}"

    res = {
        "device_route": {
            "path": plain,
            "size": size_of(plain),
            "head_hex": head_bytes(plain, 16),
        },
        "real_file_route": {
            "path": ext,
            "size": size_of(ext),
            "head_hex": head_bytes(ext, 32),
        },
        "ordinary_file_control": {
            "plain_size": size_of(self_plain),
            "ext_size": size_of(self_ext),
        },
        "git_view": {
            "tracked": "NUL" in git("ls-files").split(),
            "untracked": "NUL"
            in git("ls-files", "--others", "--exclude-standard").split(),
            "ignored": "NUL"
            in git("ls-files", "--others", "--ignored", "--exclude-standard").split(),
        },
    }

    dev = res["device_route"]["size"]
    real = res["real_file_route"]["size"]
    ordp = res["ordinary_file_control"]["plain_size"]
    orde = res["ordinary_file_control"]["ext_size"]

    res["controls"] = {
        "c1_device_route_reports_zero": dev == 0,
        "c2_real_route_reports_nonzero": isinstance(real, int) and real > 0,
        "c3_routes_disagree_on_NUL": dev != real,
        "c4_routes_agree_on_ordinary_file": ordp == orde and isinstance(ordp, int),
    }
    res["verdict"] = (
        "PROVEN: python's plain path measures the DEVICE, not the file"
        if all(res["controls"].values())
        else "NOT-PROVEN"
    )

    # Only read content once the size control has passed.
    if res["controls"]["c2_real_route_reports_nonzero"]:
        try:
            with open(ext, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            res["content_lines"] = len(text.splitlines())
            res["content_first_5_lines"] = text.splitlines()[:5]
            res["content_last_2_lines"] = text.splitlines()[-2:]
        except OSError as exc:
            res["content_error"] = repr(exc)

    dest = os.path.join(REPO, "command-center/slop-report/_r4_nul.out.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
