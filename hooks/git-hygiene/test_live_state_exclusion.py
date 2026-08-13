r"""Red-first regression for the ONE git-hygiene false positive that reproduces.

THE DEFECT. Every Stop firing reports:

    [YOURS] agent-skills-toolchain: 2 uncommitted file(s) at a detached HEAD, no upstream

Measured directly (`git status --porcelain=v2 --branch` in that repo), the two entries are:

    1 .M N... ... tools/mcp/cloud-hub/accounts.json
    1 .M N... ... tools/mcp/search-hub/accounts.json

That is the live credential-rotation pool. A standing owner constraint forbids staging or
modifying it, so UNCOMMITTED IS THE CORRECT STATE and always will be. The hook therefore
flags this repo on every turn forever, and the remedy it prints -- "commit, then:
git push -u origin HEAD" -- is an action that must never be taken. A guard that cannot
reach green trains the reader to skip it, and it costs on the day one of the flags is real.

WHAT THIS FILE DOES NOT CLAIM. A sibling claim in the same hand-off -- that `ast-patch167`
is caught by the squash-merge `ahead_by` trap -- did NOT reproduce and no fix is built for
it. Measured: that repo reports `# branch.ab +0 -0`, i.e. git already knows it is not
ahead; its single dirty entry is `? e2e/`, an untracked directory. The hook never made the
ahead claim attributed to it. `test_squash_merge_claim_does_not_reproduce` pins that
measurement so the refutation is re-runnable rather than asserted.

PAIRED CASES -- every suppression case has a FIRE case beside it, so a "fix" that merely
stops finding things fails this file:
  * accounts.json alone            -> silent
  * accounts.json + a real file    -> FIRES, and counts only the real one
  * a non-live-state file alone    -> FIRES
  * GIT_HYGIENE_NO_SKIP=1          -> FIRES even on accounts.json (suppression auditable)

Run:  python hooks/git-hygiene/test_live_state_exclusion.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "gh_check_lse", str(HERE / "check.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gh_check_lse"] = mod
    spec.loader.exec_module(mod)
    return mod


check = _load()

FAILS: list[str] = []
OKS = 0


def expect(label: str, got, want) -> None:
    global OKS
    if got == want:
        OKS += 1
        print(f"OK  {label}: {got!r}")
    else:
        FAILS.append(f"{label}: got={got!r} want={want!r}")
        print(f"XX  {label}: got={got!r} want={want!r}")


# --- the raw porcelain=v2 text the real repo emits, byte-shaped ---------------------
ACCT = (
    "# branch.oid 53c37c6cfb3e7bd1a48edbe604e1ea06a77b50b1\n"
    "# branch.head (detached)\n"
    "1 .M N... 100644 100644 100644 b7bf37a b7bf37a tools/mcp/cloud-hub/accounts.json\n"
    "1 .M N... 100644 100644 100644 316d8c0 316d8c0 tools/mcp/search-hub/accounts.json\n"
)
ACCT_PLUS_REAL = ACCT + "1 .M N... 100644 100644 100644 aaa bbb src/real_module.py\n"
REAL_ONLY = (
    "# branch.oid 53c37c6\n"
    "# branch.head main\n"
    "# branch.upstream origin/main\n"
    "# branch.ab +0 -0\n"
    "1 .M N... 100644 100644 100644 aaa bbb src/real_module.py\n"
)
RENAMED_ACCT = (
    "# branch.oid 53c37c6\n"
    "# branch.head main\n"
    "2 R. N... 100644 100644 100644 aaa bbb R100 tools/mcp/x/accounts.json\ttools/mcp/y/accounts.json\n"
)
UNTRACKED_ACCT = (
    "# branch.oid 53c37c6\n# branch.head main\n? tools/mcp/z/accounts.json\n"
)


def dirty_of(text: str) -> int:
    """Whatever the parser reports as the count that reaches the message."""
    parsed = check._parse_status_v2(text)
    # dirty is the 4th element in the pre-fix 5-tuple and stays in position after it.
    return parsed[3]


def main() -> int:
    cfg = check.Config()

    # 1. THE DEFECT. Two accounts.json entries must not read as work at risk.
    expect("accounts.json only -> dirty count", dirty_of(ACCT), 0)

    # 2. PAIRED FIRE. A real file alongside them still counts -- and counts ONCE.
    expect("accounts.json + one real file -> dirty count", dirty_of(ACCT_PLUS_REAL), 1)

    # 3. PAIRED FIRE. Nothing excluded here at all.
    expect("a real file alone -> dirty count", dirty_of(REAL_ONLY), 1)

    # 4. The exclusion must survive the OTHER porcelain record shapes, or a rename or an
    #    untracked copy of the same file walks straight back into the report.
    expect("renamed accounts.json (record type 2) -> dirty", dirty_of(RENAMED_ACCT), 0)
    expect(
        "untracked accounts.json (record type ?) -> dirty", dirty_of(UNTRACKED_ACCT), 0
    )

    # 5. SUPPRESSION MUST BE AUDITABLE. With the escape hatch set it fires again.
    os.environ["GIT_HYGIENE_NO_SKIP"] = "1"
    try:
        mod2 = _load()
        expect(
            "NO_SKIP=1 -> accounts.json counts again", mod2._parse_status_v2(ACCT)[3], 2
        )
    finally:
        os.environ.pop("GIT_HYGIENE_NO_SKIP", None)

    # 6. END TO END through classify(): the repo goes silent, and the reason is stated.
    st = check.RepoState(
        path="C:/Users/Prekzursil/source/agent-skills-toolchain",
        origin="https://github.com/Prekzursil/agent-skills-toolchain",
        has_remote=True,
        branch="",  # detached, exactly as measured
        dirty=dirty_of(ACCT),
        dirty_excluded=2,
    )
    v = check.classify(st, cfg)
    expect("classify(accounts.json-only detached repo).report", v.report, False)

    # 7. PAIRED FIRE end to end -- one real dirty file and it reports again.
    st2 = check.RepoState(
        path="C:/Users/Prekzursil/source/agent-skills-toolchain",
        origin="https://github.com/Prekzursil/agent-skills-toolchain",
        has_remote=True,
        branch="main",
        upstream="origin/main",
        dirty=1,
        dirty_excluded=2,
    )
    expect(
        "classify(one real dirty file).report", check.classify(st2, cfg).report, True
    )

    # 8. The refuted sibling claim, pinned as a live measurement rather than asserted.
    #    If this repo is gone the case is SKIPPED, never silently passed.
    p = Path("C:/Users/Prekzursil/source/ast-patch167")
    if (p / ".git").exists():
        out = subprocess.run(
            ["git", "-C", str(p), "status", "--porcelain=v2", "--branch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        ).stdout
        _, _, ahead, _, _ = check._parse_status_v2(out)[:5]
        expect("REFUTED squash-merge claim: ast-patch167 ahead count", ahead, 0)
    else:
        print("--  ast-patch167 absent; refutation case SKIPPED (not passed)")

    print(
        f"\nRESULT: {'ALL PASS' if not FAILS else 'FAILURES PRESENT'} "
        f"({OKS} ok, {len(FAILS)} failed)"
    )
    for f in FAILS:
        print(f"   {f}")
    print(
        "SUCCESS:git-hygiene-live-state"
        if not FAILS
        else "FAILED:git-hygiene-live-state"
    )
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
