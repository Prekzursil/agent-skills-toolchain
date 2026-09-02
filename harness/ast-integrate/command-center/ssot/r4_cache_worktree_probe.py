"""R4, measured: which cache-held worktree registrations point at LIVE directories.

The inventory's residual R4 says the Codex plugin cache holds a copy of canonical's worktree
admin dir whose `gitdir` files point at the real live directories, and closes with "never run
a `worktree` subcommand from the plugin cache". That was carried as a description; this
measures it, names the armed subset, and resolves an apparent contradiction.

THE CONTRADICTION, resolved. Probing the cache row that `classify_population.py` reports as
`kind-signals-disagree` shows its `.git` is a FILE -- and a file cannot contain
`worktrees/*/gitdir`. That reads as a refutation of R4 until you notice there are TWO cache
copies of this repo, and they are in different states:

    .../cache/agent-skills-toolchain/agent-skills-toolchain/0.2.0        .git is a DIRECTORY
    .../cache/agent-skills-toolchain/plugin-install-64I3il/.../0.2.0     .git is a FILE

R4 is about the first. The `kind-signals-disagree` row is the second, and it is SEVERED: its
pointer names `<canonical>/.git/worktrees/agent-skills-toolchain`, which does not exist, so
every git command there exits 128. Both rows are in the population; neither was mis-enumerated.
A self-contradicting reading was a two-paths problem, not a detector failure -- but it had to
be measured to know that.

WHAT ARMED MEANS. A registration is armed when its `gitdir` names a path that exists. `git
worktree remove`/`prune` executed in the cache resolves these registrations, so an armed row
is a real directory a cache-side worktree subcommand can reach. This probe does NOT run any
worktree subcommand -- that is the destructive experiment R4 declines, and declining it is
still the right call.

CONTROLS, both states:
  reader     a gitdir file known to exist must parse to a non-empty path, and a fabricated
             registration name must yield nothing -- so an empty result means "no such
             registration", not "the reader cannot read".
  existence  a path known to exist must test ARMED and a fabricated path must test stale,
             through the same predicate used for the verdict.

Read-only: reads text files and runs `git worktree list`. Nothing written outside this
directory, nothing removed, no worktree subcommand that mutates state.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "r4-cache-worktrees.json"

CACHE_ADMIN = Path(
    "C:/Users/Prekzursil/.codex/plugins/cache/agent-skills-toolchain"
    "/agent-skills-toolchain/0.2.0"
)
CACHE_SEVERED = Path(
    "C:/Users/Prekzursil/.codex/plugins/cache/agent-skills-toolchain"
    "/plugin-install-64I3il/agent-skills-toolchain/0.2.0"
)
CANONICAL = "C:/Users/Prekzursil/source/agent-skills-toolchain"
FABRICATED = Path("C:/Users/Prekzursil/source/this-path-does-not-exist-92f1a")


def read_gitdir(admin_root: Path, name: str) -> str:
    fp = admin_root / ".git" / "worktrees" / name / "gitdir"
    try:
        return fp.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def armed(gitdir_value: str) -> bool:
    """A registration is armed when the .git it names exists on disk."""
    return bool(gitdir_value) and Path(gitdir_value).exists()


def main() -> int:
    wt_dir = CACHE_ADMIN / ".git" / "worktrees"
    names = sorted(p.name for p in wt_dir.iterdir()) if wt_dir.is_dir() else []
    print(f"cache admin dir: {wt_dir}")
    print(f"registrations found: {len(names)}")

    # ------------------------------------------------------------------ CONTROLS
    pos = read_gitdir(CACHE_ADMIN, names[0]) if names else ""
    neg = read_gitdir(CACHE_ADMIN, "no-such-registration-92f1a")
    reader_ok = bool(pos) and neg == ""
    print(
        f"CONTROL reader: known registration -> {bool(pos)}; fabricated -> {neg == ''}"
    )
    exist_ok = armed(str(Path(CANONICAL) / ".git")) and not armed(str(FABRICATED))
    print(f"CONTROL existence predicate discriminates: {exist_ok}")
    if not (reader_ok and exist_ok) or not names:
        print("FAILED:r4-cache-worktrees controls did not discriminate")
        return 3

    rows = []
    for n in names:
        g = read_gitdir(CACHE_ADMIN, n)
        a = armed(g)
        rows.append({"registration": n, "gitdir": g, "armed": a})
        print(f"  {'ARMED ' if a else 'stale '} {n:<26} -> {g}")

    # The severed second copy, measured rather than assumed.
    dotgit = CACHE_SEVERED / ".git"
    severed = {
        "path": str(CACHE_SEVERED).replace("\\", "/"),
        "dotgit_is_file": dotgit.is_file(),
        "pointer": dotgit.read_text(encoding="utf-8", errors="replace").strip()
        if dotgit.is_file()
        else "",
    }
    severed["target_exists"] = bool(
        severed["pointer"]
        and Path(severed["pointer"].removeprefix("gitdir:").strip()).exists()
    )
    print(f"\nsevered copy: .git is a file = {severed['dotgit_is_file']}")
    print(f"  pointer      : {severed['pointer']}")
    print(
        f"  target exists: {severed['target_exists']}   (False => every git cmd exits 128)"
    )

    # What canonical itself still registers -- an independent second view of the same question.
    p = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=CANONICAL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    live = [
        ln.split(" ", 1)[1].strip().replace("\\", "/")
        for ln in p.stdout.splitlines()
        if ln.startswith("worktree ")
    ]
    print(f"\ncanonical currently registers {len(live)} worktree(s)")

    armed_rows = [r for r in rows if r["armed"]]
    report = {
        "cache_admin_root": str(CACHE_ADMIN).replace("\\", "/"),
        "controls": {
            "reader_positive": bool(pos),
            "reader_fabricated_empty": neg == "",
            "existence_discriminates": exist_ok,
        },
        "registrations": rows,
        "armed_count": len(armed_rows),
        "armed": [r["gitdir"] for r in armed_rows],
        "severed_copy": severed,
        "canonical_live_worktrees": live,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    print(
        f"SUCCESS:r4-cache-worktrees registrations={len(rows)} armed={len(armed_rows)} "
        f"severed_copy_target_exists={severed['target_exists']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
