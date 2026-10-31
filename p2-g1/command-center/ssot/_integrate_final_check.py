"""Final INTEGRATE verification: nothing deleted, and every wire still live.

Two claims, both with controls:
  1. NOTHING DELETED -- every checkout path recorded in all25.json is still on disk.
     Controlled in both directions: a fabricated path must read missing, and a real
     recorded path must read present. Without those, a reader that always returns True
     would certify a fleet that had been wiped.
  2. The lane's commits touched ONLY declared paths -- no foreign path swept into a
     shared tree. Controlled against a non-lane commit, which must show foreign paths.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
LANE_COMMITS = ["33f3f2d3", "0a07e063"]
# A commit from another lane. If the scope test cannot flag THIS as out-of-scope, the
# test is inert and the clean verdict on my own commits means nothing.
CONTROL_COMMIT = "ea37057f"
DECLARED_PREFIXES = (
    "docs/ssot/",
    "command-center/ssot/",
    "ci/tests/test_ssot_wiring.py",
    "CLAUDE.md",
    ".github/workflows/skill-dual-write.yml",
)


def paths_in(commit: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show", "--name-only", "--format=", commit],
        capture_output=True,
        text=True,
    )
    return [ln.strip() for ln in proc.stdout.split("\n") if ln.strip()]


def out_of_scope(commit: str) -> list[str]:
    return [p for p in paths_in(commit) if not p.startswith(DECLARED_PREFIXES)]


def harvest_roots(obj: object, found: set[str]) -> None:
    """Collect anything that looks like a recorded checkout path, whatever the schema."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"path", "root", "checkout", "worktree"} and isinstance(
                value, str
            ):
                found.add(value)
            harvest_roots(value, found)
    elif isinstance(obj, list):
        for item in obj:
            harvest_roots(item, found)


def main() -> int:
    rc = 0

    # ---- 1. nothing deleted -------------------------------------------------------
    data = json.loads((REPO / "command-center/ssot/all25.json").read_text("utf-8"))
    roots: set[str] = set()
    harvest_roots(data, roots)
    if not roots:
        print("FAILED:integrate-final all25.json yielded 0 roots -- reader is broken")
        return 2

    missing = sorted(r for r in roots if not pathlib.Path(r).is_dir())
    print(f"checkouts recorded: {len(roots)}  present: {len(roots) - len(missing)}")
    print(f"MISSING: {len(missing)} {missing}")
    real = sorted(roots)[0]
    ctl_fake = pathlib.Path("C:/Users/Prekzursil/__no_such_checkout__").is_dir()
    ctl_real = pathlib.Path(real).is_dir()
    print(f"control fabricated is_dir={ctl_fake} / control real is_dir={ctl_real}")
    if ctl_fake or not ctl_real:
        print("FAILED:integrate-final presence control did not discriminate")
        return 2
    if missing:
        rc = 1

    # ---- 2. commit scope ----------------------------------------------------------
    for c in LANE_COMMITS:
        foreign = out_of_scope(c)
        print(f"{c}: {len(paths_in(c))} paths, out-of-scope: {len(foreign)} {foreign}")
        if foreign:
            rc = 1
    ctl_foreign = out_of_scope(CONTROL_COMMIT)
    print(f"CONTROL {CONTROL_COMMIT}: out-of-scope {len(ctl_foreign)} (must be > 0)")
    if not ctl_foreign:
        print("FAILED:integrate-final scope control is inert -- it flags nothing")
        return 2

    print("SUCCESS:integrate-final" if rc == 0 else "FAILED:integrate-final")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
