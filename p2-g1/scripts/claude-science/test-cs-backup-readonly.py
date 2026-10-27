"""Prove `cs doctor` does not WRITE into the backup root.

WHY THIS EXISTS. cs-doctor.ps1 is documented read-only, and its restorability row has to OPEN the
newest snapshot to be worth anything ("a backup you cannot restore is false safety"). Round 1 did
that in place with `sqlite3 -readonly "file:$B?mode=ro"`, which reads as safe and is not: in WAL
mode SQLite still maps and stamps the `-shm` index beside the database. Measured 2026-08-12 --

    CHANGED operon-20260812-093431.db-shm  mtime_ns 1786520529508095000 -> 1786521751710545500

-- so the read-only health check mutated the backup directory on every single run. The fix copies
the snapshot to a temp dir and checks the COPY; this probe is the thing that proves it, and it is
kept because a property nobody measures is a property that regresses.

BOTH-STATES. This probe is only meaningful because it FIRED against the broken doctor and went
silent against the fixed one, same probe, same backup root, minutes apart. To re-derive that, point
it at a cs-doctor.ps1 that still opens the snapshot in place -- it must report a CHANGED entry.

WHAT IT CANNOT SEE (stated so it is not assumed): access times. It compares name, size and mtime,
which is what matters for snapshot integrity; an atime bump from reading is not a corruption risk
and is not measured here.

Usage:
    python test-cs-backup-readonly.py [label] [path-to-cs-doctor.ps1] [backup-root]

Defaults: label "check", the sibling cs-doctor.ps1, and CS_BACKUP_ROOT from cs.conf.

Exit 0 = the backup root is byte-and-stamp identical after the run.
Exit 1 = the doctor wrote into it (the detector fired).
Exit 2 = could not measure (no backup root / doctor not found) -- NOT a pass.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def default_root() -> str | None:
    """Windows form of CS_BACKUP_ROOT, read from the SSOT rather than hardcoded.

    cs.conf is the single source of truth for this path and it stores the WSL form; writing the
    derived Windows form out again here would have made this file the only config bypass left
    outside the seam, which is the exact thing the round-2 config work removed everywhere else.
    Precedence matches the rest of the tool: environment > cs.conf.
    """
    wsl = os.environ.get("CS_BACKUP_ROOT")
    if not wsl:
        try:
            with open(os.path.join(HERE, "cs.conf"), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("CS_BACKUP_ROOT="):
                        wsl = line.split("=", 1)[1].strip()
                        break
        except OSError:
            return None
    m = re.match(r"^/mnt/([a-zA-Z])(/.*)?$", wsl or "")
    if not m:
        return None
    return m.group(1).upper() + ":" + (m.group(2) or "").replace("/", "\\")


def snapshot_dir(root: str) -> dict[str, tuple[int, int]]:
    """name -> (size, mtime_ns) for every entry, sidecars included."""
    out: dict[str, tuple[int, int]] = {}
    with os.scandir(root) as it:
        for entry in it:
            st = entry.stat()
            out[entry.name] = (st.st_size, st.st_mtime_ns)
    return out


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "check"
    doctor = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "cs-doctor.ps1")
    root = sys.argv[3] if len(sys.argv) > 3 else default_root()

    if not root:
        print(
            "NOT-CHECKED could not derive CS_BACKUP_ROOT from cs.conf or the environment"
        )
        return 2
    if not os.path.isdir(root):
        print(f"NOT-CHECKED backup root not found: {root}")
        return 2
    if not os.path.isfile(doctor):
        print(f"NOT-CHECKED doctor not found: {doctor}")
        return 2

    before = snapshot_dir(root)
    print(f"[{label}] {root}: {len(before)} entries before")

    started = time.time()
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["pwsh", "-NoProfile", "-File", doctor],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    elapsed = time.time() - started
    after = snapshot_dir(root)
    print(
        f"[{label}] doctor exit={proc.returncode} in {elapsed:.1f}s; {len(after)} entries after"
    )

    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])

    for name in created:
        print(f"  CREATED  {name}  size={after[name][0]}")
    for name in deleted:
        print(f"  DELETED  {name}")
    for name in changed:
        old, new = before[name], after[name]
        print(
            f"  CHANGED  {name}  size {old[0]}->{new[0]}  mtime_ns {old[1]}->{new[1]}"
        )

    # Echo the rows this is about, so a green run also shows the check actually ran rather than
    # silently skipping (a probe that measures nothing is the failure mode being guarded against).
    for line in proc.stdout.splitlines():
        if (
            "Backup restorable" in line
            or "Backup freshness" in line
            or "summary:" in line
        ):
            print("  DOCTOR| " + line.rstrip())

    dirty = bool(created or deleted or changed)
    print(
        json.dumps(
            {
                "label": label,
                "root": root,
                "wrote_to_backup_root": dirty,
                "created": created,
                "deleted": deleted,
                "changed": changed,
            }
        )
    )
    if dirty:
        print(f"FAILED:cs-backup-readonly [{label}] doctor WROTE into the backup root")
        return 1
    print(f"SUCCESS:cs-backup-readonly [{label}] backup root byte-and-stamp identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
