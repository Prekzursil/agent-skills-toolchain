"""VERIFY lane probe: independently sweep the 8 ALWAYS-ON live rules for broken path references.

The BUILD lane scoped its contradiction list as "a floor, not a census" and named the settling
experiment: extract every checkable assertion citing a file/path and assert it mechanically.
This runs a slice of that experiment -- the path-reference slice -- to test whether a tenth
contradiction is reachable, and to give the exhaustiveness caveat a number instead of a shrug.

DETECTOR CONTROL: a known-good path and a known-bad path are injected into the same matcher.
If the known-bad one is not reported MISSING, the sweep is inert and its silence means nothing.

SUPERSEDED 2026-08-13 by ``r2_pathrefs.py`` -- kept as the evidence for the round-1 verdict, not
as the current instrument. The adversarial round showed ``resolve()`` below falls back to
``REPO.rglob(basename)``, so a reference whose PATH is wrong but whose FILENAME exists elsewhere
resolves as satisfied, and the known-bad control uses a filename absent everywhere so that
fallback is never exercised. The successor classifies three ways (EXACT / BASENAME-ONLY /
MISSING) with the middle state under a control, and scans 176 files across both trees instead
of 8. Do not cite this file's "0 unresolvable" as current coverage.
"""

from __future__ import annotations

import re
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]
LIVE_RULES = HOME / ".claude" / "rules"

ALWAYS_ON = [
    "common/agents.md",
    "common/bash-hud-and-terminal-emit.md",
    "common/cross-vendor-dispatch.md",
    "common/fan-out-contract.md",
    "common/harness-vcs-hygiene.md",
    "common/single-signal-verification.md",
    "common/stale-megapr-reconcile.md",
    "common/windows-shell.md",
]

# Backticked tokens that look like a repo-relative path with a real extension or a known dir.
PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|ps1|sh|md|json|yml|yaml|toml|mjs|js))`"
)


def resolve(token: str) -> tuple[bool, str]:
    """A reference is satisfied if it exists under the repo root or under ~/.claude."""
    for base, label in ((REPO, "repo"), (HOME / ".claude", "live"), (HOME, "home")):
        if (base / token).exists():
            return True, label
    # bare filename anywhere in the repo (rules cite `check.py`, `notify.py`, ...)
    name = token.split("/")[-1]
    if any(REPO.rglob(name)):
        return True, "repo-glob"
    return False, "MISSING"


def main() -> int:
    # --- DETECTOR CONTROL: both states, before any real result is trusted ------------------
    good_ok, _ = resolve("scripts/sync-rules.ps1")
    bad_ok, _ = resolve("scripts/__definitely_not_here__.ps1")
    print(f"CONTROL known-good -> found={good_ok} (must be True)")
    print(f"CONTROL known-bad  -> found={bad_ok} (must be False)")
    if not good_ok or bad_ok:
        print("FAILED:verify_pathrefs detector cannot distinguish present from absent")
        return 1
    print("")

    total = 0
    missing: list[tuple[str, str]] = []
    for rel in ALWAYS_ON:
        path = LIVE_RULES / rel
        if not path.is_file():
            print(f"FAILED:verify_pathrefs always-on rule absent from live tree: {rel}")
            return 1
        text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
        for token in sorted(set(PATH_RE.findall(text))):
            total += 1
            ok, _ = resolve(token)
            if not ok:
                missing.append((rel, token))

    print(
        f"path references checked across {len(ALWAYS_ON)} always-on live rules: {total}"
    )
    print(f"unresolvable: {len(missing)}")
    for rel, token in missing:
        print(f"  MISSING  {rel}  ->  {token}")
    print("")
    print(f"SUCCESS:verify_pathrefs checked={total} missing={len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
