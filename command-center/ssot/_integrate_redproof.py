"""Red-proof: run the SSOT wiring checker against the REAL pre-integration bytes.

The point of a both-states proof is that the BROKEN state must be the genuine article, not a
hand-made fake. So the "before" tree here is reconstructed with `git show HEAD:<path>` -- the
bytes as committed before this lane's integration commit -- rather than by deleting a line
from the working tree and calling that a control.

Expected: HEAD (no SSOT-WIRE block in CLAUDE.md) exits 1; the working tree exits 0.
If both exit the same way, the checker is inert and no verdict from it may be cited.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
CHECKER = REPO / "command-center" / "ssot" / "ssot_wiring_check.py"

# Every file the checker reads. `ssot_wiring_check.py` is included because the block names
# it, and W3 resolves every path the block names.
TRACKED = (
    "CLAUDE.md",
    "docs/ssot/SSOT-CLONE-INVENTORY.md",
    "command-center/ssot/ssot_drift_gate.py",
    "command-center/ssot/ssot_wiring_check.py",
    ".github/workflows/skill-dual-write.yml",
)


def show(rev: str, rel: str) -> bytes | None:
    """Return the stored blob, or None when the path does not exist at that revision.

    `git show <rev>:<path>` and `git cat-file -p` both return the blob with 0 CRLF; it is
    `git archive` that applies EOL conversion on Windows. Forward slashes only -- a
    backslash path is not a valid git revision argument.
    """
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{rev}:{rel}"], capture_output=True
    )
    return proc.stdout if proc.returncode == 0 else None


def build(rev: str, dest: pathlib.Path) -> list[str]:
    present = []
    for rel in TRACKED:
        blob = show(rev, rel)
        if blob is None:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        present.append(rel)
    return present


def run_checker(root: pathlib.Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ssot-redproof-"))
    try:
        before = tmp / "before"
        present = build("HEAD", before)
        print(f"=== BEFORE: reconstructed from git HEAD ({len(present)} files) ===")
        for rel in present:
            print(f"    {rel}")
        missing = [r for r in TRACKED if r not in present]
        if missing:
            print(f"    (absent at HEAD, as expected pre-integration: {missing})")
        # The checker lives outside the reconstructed tree, so copy it in only if HEAD did
        # not have it -- W3 must be able to resolve the path the block names.
        if "command-center/ssot/ssot_wiring_check.py" not in present:
            dst = before / "command-center/ssot/ssot_wiring_check.py"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CHECKER, dst)
            print("    (checker copied in so W3 is not testing its own absence)")

        rc_before, out_before = run_checker(before)
        print(out_before)
        print(f"--> BEFORE exit={rc_before}\n")

        rc_after, out_after = run_checker(REPO)
        print("=== AFTER: the working tree, with the integration applied ===")
        print(out_after)
        print(f"--> AFTER  exit={rc_after}\n")

        ok = rc_before != 0 and rc_after == 0
        print(f"DISCRIMINATION: before={rc_before} after={rc_after}")
        if not ok:
            print(
                "FAILED:ssot-redproof the checker did not distinguish the two states -- "
                "it is inert and its green means nothing."
            )
            return 1
        print("SUCCESS:ssot-redproof before=RED after=GREEN, the wire is load-bearing")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
