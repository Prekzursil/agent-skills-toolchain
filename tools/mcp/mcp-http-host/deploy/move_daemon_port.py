#!/usr/bin/env python3
"""Move the Basic Memory daemon off the client-facing port - the exact, reversible edit.

The session-healing proxy (``bm_session_proxy.py``) takes over ``127.0.0.1:8765``,
so the daemon's launcher and watchdog must name the INTERNAL port instead. Both
scripts carry the port in several places (``$Port = 8765``, the probe URL, and the
kill-stale filter ``'*basic-memory*8765*'`` that must keep matching the daemon's
own command line) - so the edit is "every whole-number ``8765`` in these two files
becomes ``8766``", nothing else. Every client keeps ``http://127.0.0.1:8765/mcp``.

Dry run by default: prints a unified diff and the replacement count per file.

    python move_daemon_port.py                       # dry run against C:\\Users\\Prekzursil\\.basic-memory
    python move_daemon_port.py --apply               # back up to backups\\<name>.bak_<date>-portmove, then edit
    python move_daemon_port.py --check               # exit 0 when no 8765 remains in the files
    python move_daemon_port.py --rollback            # restore the newest -portmove backups

Bytes are edited in place: encoding, BOM and CRLF line endings are preserved,
and a file that is missing stops the whole run before anything is written.
stdlib only; runs on the bundled C:\\Python314\\python.exe.
"""

from __future__ import annotations

import argparse
import difflib
import re
from datetime import datetime
from pathlib import Path

DEFAULT_DIR = r"C:\Users\Prekzursil\.basic-memory"
DEFAULT_FILES = ("bm-http-server.ps1", "bm-watchdog.ps1")
DEFAULT_FROM = 8765
DEFAULT_TO = 8766
BACKUP_SUFFIX = "-portmove"


def rewrite(data: bytes, from_port: int, to_port: int) -> tuple[bytes, int]:
    """Replace whole-number occurrences of ``from_port`` only (18765 / 87650 untouched)."""
    pattern = re.compile(rb"(?<!\d)" + str(from_port).encode("ascii") + rb"(?!\d)")
    return pattern.subn(str(to_port).encode("ascii"), data)


def _diff(name: str, before: bytes, after: bytes) -> str:
    old = before.decode("utf-8", errors="replace").splitlines()
    new = after.decode("utf-8", errors="replace").splitlines()
    return "\n".join(
        difflib.unified_diff(
            old, new, f"{name} (before)", f"{name} (after)", lineterm=""
        )
    )


def _backup_path(backups: Path, name: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    candidate = backups / f"{name}.bak_{stamp}{BACKUP_SUFFIX}"
    counter = 2
    while candidate.exists():
        candidate = backups / f"{name}.bak_{stamp}-{counter}{BACKUP_SUFFIX}"
        counter += 1
    return candidate


def _newest_backup(backups: Path, name: str) -> Path | None:
    if not backups.is_dir():
        return None
    matches = [
        p
        for p in backups.iterdir()
        if p.name.startswith(f"{name}.bak_") and p.name.endswith(BACKUP_SUFFIX)
    ]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def run(
    directory: Path,
    files: list[str],
    from_port: int,
    to_port: int,
    *,
    apply: bool,
    check: bool,
    rollback: bool,
) -> int:
    paths = [directory / name for name in files]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"missing: {p}")
        print("FAILED: nothing was touched")
        return 2
    backups = directory / "backups"

    if rollback:
        restored = 0
        for path in paths:
            backup = _newest_backup(backups, path.name)
            if backup is None:
                print(
                    f"{path.name}: no backup ending in {BACKUP_SUFFIX} under {backups}"
                )
                continue
            path.write_bytes(backup.read_bytes())
            print(f"{path.name}: restored from {backup.name}")
            restored += 1
        if restored != len(paths):
            print("FAILED: rollback incomplete")
            return 1
        print(
            f"ROLLED BACK {restored} file(s); the daemon scripts name :{from_port} again"
        )
        return 0

    if check:
        leftovers: list[str] = []
        for path in paths:
            for lineno, line in enumerate(path.read_bytes().splitlines(), 1):
                if rewrite(line, from_port, to_port)[1]:
                    text = line.decode("utf-8", errors="replace").strip()
                    leftovers.append(f"{path.name}:{lineno}: {text}")
        if leftovers:
            print("\n".join(leftovers))
            print(f"FAILED: {len(leftovers)} line(s) still name :{from_port}")
            return 1
        print(
            f"SUCCESS: no :{from_port} left in {', '.join(files)}; daemon on :{to_port}"
        )
        return 0

    label = "APPLIED" if apply else "DRY RUN"
    total = 0
    for path in paths:
        before = path.read_bytes()
        after, count = rewrite(before, from_port, to_port)
        total += count
        print(f"{path.name}: {count} replacement(s)")
        if count:
            print(_diff(path.name, before, after))
        if apply and count:
            backups.mkdir(parents=True, exist_ok=True)
            backup = _backup_path(backups, path.name)
            backup.write_bytes(before)
            path.write_bytes(after)
            print(f"{path.name}: backup {backup}")
    print(
        f"{label}: {total} replacement(s) across {len(paths)} file(s)"
        + ("" if apply else " - re-run with --apply to write them")
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dir", default=DEFAULT_DIR, help="the .basic-memory directory"
    )
    parser.add_argument(
        "--files", nargs="+", default=list(DEFAULT_FILES), help="scripts to edit"
    )
    parser.add_argument("--from-port", type=int, default=DEFAULT_FROM)
    parser.add_argument("--to-port", type=int, default=DEFAULT_TO)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="write the edit (with backups)"
    )
    mode.add_argument(
        "--check", action="store_true", help="verify the move is complete"
    )
    mode.add_argument(
        "--rollback", action="store_true", help="restore the newest backups"
    )
    args = parser.parse_args(argv)
    return run(
        Path(args.dir),
        list(args.files),
        args.from_port,
        args.to_port,
        apply=args.apply,
        check=args.check,
        rollback=args.rollback,
    )


if __name__ == "__main__":
    raise SystemExit(main())
