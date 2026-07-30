"""Make every genuinely-unpushed commit across the estate durable, without rewriting anything.

CALIBRATION (why this does not trust the hook's count): the git-hygiene hook reported ~14 at-risk
commits across 4 repos; definitive measurement found 2. `git cherry` marks a commit '+' whenever
no patch-id matches upstream, and a rebase or squash-merge changes the patch-id while leaving the
content byte-identical. 4 of 6 flagged commits were ALREADY_UPSTREAM. So "ahead of remote" is a
hypothesis, not a finding.

Definitive content test, per commit, on a probe branch off the remote tip:
    git cherry-pick -n <sha>   then   git status --porcelain
Empty status => applying it changes nothing => content already upstream.

SAFETY RULES, in force for every repo:
  * NEVER push a default branch (main/master). Hard ban. Those get a tag only.
  * NEVER force-push, never rebase, never rewrite history.
  * Tag BEFORE anything else, so a commit cannot become unreachable mid-operation.
  * A branch absent from the remote is pushed under its own name (purely additive).
  * A branch that exists and has diverged is NOT pushed - tag it and report for a human merge.
  * Dirt is stashed before probing and popped after; on the first attempt a dirty tree
    masqueraded as a merge conflict and produced a wrong verdict.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# FIVE roots, matching scripts/repo-sweep.ps1. The first version of this file scanned only
# ~/source and then reported "swept all 114 repos" - false. momentstudio-fix, PrimariRo,
# pbinfo-scrape and _verify_momentstudio live under ~/Documents/GitHub and were never examined.
# repo-sweep.ps1's own header records the identical bug ("the scan root list simply did not
# include ~/Documents ... widen -Roots rather than trusting" a narrow list), so this was a
# documented trap walked into a second time. A narrow scan reporting zero findings is a DETECTOR
# failure, not a clean estate.
HOME = Path("C:/Users/Prekzursil")
ROOTS = [
    HOME / "source",
    HOME / "source/repos",
    HOME / "Documents/GitHub",
    HOME / "Documents",
    HOME / ".local/opt",
]
ENV = {**os.environ, "MSYS_NO_PATHCONV": "1"}
PROTECTED = {"main", "master", "trunk", "HEAD"}
# Already definitively classified in a prior pass; re-probing them wastes time.
DONE = {"ast-sshclean", "ast-statusline-capture", "ast-c16-taxonomy"}
SKIP_DIRS = {"_wu", "_wu2", "_est", "ast-patch167", "ast-integrate"}


def g(repo: Path, *a: str) -> tuple[int, str]:
    r = subprocess.run(
        ["git", "-C", str(repo), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
        check=False,
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def candidates() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for root in ROOTS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir() or d.name in SKIP_DIRS or d.name in DONE:
                continue
            if not (d / ".git").exists():
                continue
            # The same clone can be reachable from two roots; resolve so it is probed once.
            key = str(d.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
    return out


def main() -> int:
    report: list[str] = []
    for repo in candidates():
        rc, br = g(repo, "rev-parse", "--abbrev-ref", "HEAD")
        if rc != 0 or not br:
            continue
        # What are we ahead OF? Prefer the branch's own remote ref, else origin/main.
        g(repo, "fetch", "--quiet", "origin")
        rc_rb, _ = g(repo, "rev-parse", "--verify", f"origin/{br}")
        remote_exists = rc_rb == 0
        base = f"origin/{br}" if remote_exists else "origin/main"
        rc_b, _ = g(repo, "rev-parse", "--verify", base)
        if rc_b != 0:
            continue
        _, ahead = g(repo, "rev-list", "--count", f"{base}..HEAD")
        if not ahead.isdigit() or int(ahead) == 0:
            continue

        _, cherry = g(repo, "cherry", base, "HEAD")
        flagged = [ln.split()[1] for ln in cherry.splitlines() if ln.startswith("+")]
        if not flagged:
            continue

        print(f"\n=== {repo.name} :: {br}  (ahead {ahead} of {base}) ===")
        # Tag first - nothing can become unreachable after this point.
        for sha in flagged:
            g(repo, "tag", "-f", f"rescue/{sha[:8]}", sha)

        _, dirt = g(repo, "status", "--porcelain")
        stashed = False
        if dirt.strip():
            rc_s, _ = g(repo, "stash", "push", "-u", "-m", "rescue-autostash")
            stashed = rc_s == 0

        real: list[str] = []
        probe = "probe/rescue-classify"
        rc_p, _ = g(repo, "checkout", "-B", probe, base)
        if rc_p == 0:
            for sha in flagged:
                g(repo, "reset", "--hard", "--quiet", base)
                rc_c, out = g(repo, "cherry-pick", "-n", sha)
                _, st = g(repo, "status", "--porcelain")
                if rc_c == 0 and not st.strip():
                    verdict = "already-upstream"
                else:
                    verdict = "GENUINELY-ABSENT"
                    real.append(sha)
                print(f"    {sha[:8]} {verdict}")
                g(repo, "cherry-pick", "--abort")
                g(repo, "reset", "--hard", "--quiet", base)
            g(repo, "checkout", "--quiet", br)
            g(repo, "branch", "-D", probe)
        if stashed:
            g(repo, "stash", "pop")

        if not real:
            print("    -> nothing genuinely absent; no action needed")
            continue

        if br in PROTECTED:
            for sha in real:
                g(repo, "push", "origin", f"refs/tags/rescue/{sha[:8]}")
            report.append(
                f"{repo.name}: {len(real)} absent on PROTECTED branch '{br}' "
                f"-> tags pushed, branch NOT pushed (hard ban)"
            )
            print(f"    on protected branch '{br}': tags pushed, branch left alone")
        elif not remote_exists:
            rc_pu, out = g(repo, "push", "origin", f"HEAD:refs/heads/{br}")
            ok = rc_pu == 0
            report.append(
                f"{repo.name}: pushed NEW branch '{br}' ({len(real)} commits) -> "
                f"{'OK' if ok else 'FAILED'}"
            )
            print(
                f"    pushed new branch {br}: {'OK' if ok else 'FAILED ' + out[:120]}"
            )
        else:
            rc_pu, out = g(repo, "push", "origin", f"HEAD:refs/heads/{br}")
            if rc_pu == 0:
                report.append(
                    f"{repo.name}: fast-forwarded '{br}' ({len(real)} commits)"
                )
                print("    fast-forward push OK")
            else:
                for sha in real:
                    g(repo, "push", "origin", f"refs/tags/rescue/{sha[:8]}")
                report.append(
                    f"{repo.name}: '{br}' DIVERGED, {len(real)} absent -> tags pushed, "
                    f"needs human merge"
                )
                print(
                    "    diverged: tags pushed, NOT force-pushing; needs a human merge"
                )

    print("\n=== ACTION SUMMARY ===")
    if not report:
        print(
            "  nothing genuinely at risk anywhere - the hook's count was all patch-id noise"
        )
    for line in report:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
