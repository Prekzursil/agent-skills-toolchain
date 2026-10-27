"""Deploy repo `.agents/skills` -> `~/.claude/skills.daily`, the ONE tree Claude Code reads.

WHY THIS EXISTS
---------------
`ci/check_skill_deploy_drift.py` recorded the root cause on 2026-07-29 and it is still true:
**not one script in `scripts/` or `ci/` writes to `skills.daily`.**

    scripts/sync-skills.ps1      repo `skills/`      -> `~/.agents/skills`
    scripts/sync-from-live.ps1   `~/.agents/skills`  -> repo `.agents/skills`
    ci/check_skill_dual_write.py repo `skills/`     <-> repo `.agents/skills`

Every one of those stops one hop short of the loaded tree, so the last hop is performed BY HAND.
That is why drift regenerates after every fix, and why work authored in `skills.daily` is
orphaned from version control. This script is that missing hop, and it is deliberately the most
timid script in the repo.

FOUR SAFETY PROPERTIES -- all four enforced; WHERE each is proven differs
-------------------------------------------------------------------------
P1/P2/P3 are proven by ``--self-test`` below, which is a hard precondition of ``--apply`` and
therefore runs on every real use.  **P4 is NOT reachable by ``--self-test``** and claiming
otherwise was an overclaim in the first version of this file: ``--self-test`` returns before
``main()`` ever reaches the ``--apply`` branch, so two mutants -- deleting the ``--apply``
precondition, and forcing ``apply=True`` -- were measured SURVIVING it.  P4 is proven instead by
``ci/tests/test_deploy_skills_daily.py``, wired into ``.github/workflows/skill-dual-write.yml``
as the ``gate-skill-deploy-hop`` step; that suite kills both mutants (measured 2026-08-12,
against an unmutated CONTROL that stays green on both probes).
P1  COPIES ONLY `safe_to_deploy`.  That list comes from `check_skill_deploy_drift.reconcile()`
    and contains only RIGHT-AHEAD (repo strictly contains the deployed copy) and
    RIGHT-ONLY-FILE (the deployed tree has no bytes there).  A DIVERGED file is never touched.
    Measured 2026-08-12 on the real pair: 431 files need a human merge and 95 are safe.

P2  NEVER RESURRECTS A SKILL.  `reconcile()` builds `safe_to_deploy` from SHARED skills only, so
    a repo-only skill is structurally unreachable -- and this script re-checks the target skill
    directory exists before every write, because "structurally impossible" is a claim that
    should still be asserted.  Measured: 18 skills exist in the repo but in NEITHER live tree,
    including the NINE retired per-mode wrappers codex-audit / -brainstorm / -coordinate /
    -curate / -discuss / -fix / -governance / -review / -triage, whose replacement
    `codex-orchestrate` is already live.  A naive mirror re-ambiguates Codex routing and
    re-spends the description budget that 26 already-dark skills are starved of.

P3  NEVER DELETES.  There is no prune, no mirror-delete, no `rmtree` in this file at all.
    Measured why: `microsoft-foundry` and `qdx-rush` are present in BOTH live trees and absent
    from repo `skills/`, so a prune-style sync deletes two real skills.

P4  DRY RUN BY DEFAULT.  `--apply` is required, and `--apply` runs `--self-test` FIRST and
    aborts on failure.  A gate that has never gone red is indistinguishable from a no-op, so
    P1/P2/P3 are re-proven against a purpose-built broken fixture on every single real use.
    P4 itself is the one property that fixture cannot reach -- see the header above; its
    red-proof lives in `ci/tests/test_deploy_skills_daily.py` and runs in CI.

AGENT-FACING ROUTE
    `.agents/skills/writing-skills/SKILL.md` ("Where to author, and the last hop") is the
    curated skill that tells an agent this command exists.  That link is itself asserted by the
    CI suite: a tool with no skill, hook or workflow reference is unreachable in practice, which
    is exactly how `tools/detector-self-test/` came to run green while wired nowhere.

USAGE
    python scripts/deploy-skills-daily.py                 # report + dry run
    python scripts/deploy-skills-daily.py --self-test     # prove the guards fire
    python scripts/deploy-skills-daily.py --apply         # self-test, then copy safe files only
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / ".agents" / "skills"
DEFAULT_TARGET = Path.home() / ".claude" / "skills.daily"

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2


def _load_drift():
    """Import the drift reporter by path so this script works from any cwd."""
    path = REPO_ROOT / "ci" / "check_skill_deploy_drift.py"
    spec = importlib.util.spec_from_file_location("_skill_drift", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def deployable(rel: str, source: Path, target: Path) -> str | None:
    """P2/P-file guard as a directly-callable predicate. Returns a refusal reason, or None.

    This is a SEAM ON PURPOSE. When the guard lived inline in ``plan()`` the self-test could not
    kill a mutant that deleted it: ``safe_to_deploy`` is built from SHARED skills only, so a
    repo-only skill never reaches the guard and "no repo-only skill was copied" stayed true with
    the guard removed. That assertion was measuring the drift reporter, not this tool. Exposing
    the predicate lets the self-test hand it the case the integration path cannot produce, which
    is the only way the mutant dies.
    """
    skill = rel.split("/", 1)[0]
    if not (target / skill).is_dir():
        return "P2 would resurrect a skill absent from the curated tree"
    if not (source / rel).is_file():
        return "source path is not a regular file"
    return None


def plan(source: Path, target: Path, only: set[str] | None = None) -> dict[str, object]:
    """The deploy plan: what is safe, what is refused, and why.

    ``only`` narrows the deploy to named skills.  It can only ever REMOVE candidates from an
    already-safe list, never add one, so it cannot weaken P1/P2/P3.
    """
    drift = _load_drift()
    # left = the DEPLOYED tree, right = the tree claimed authoritative.
    report = drift.reconcile(target, source)
    safe = list(report["safe_to_deploy"])
    if only:
        safe = [r for r in safe if r.split("/", 1)[0] in only]
    refused = list(report["needs_merge"])

    copyable: list[str] = []
    blocked: list[tuple[str, str]] = []
    for rel in safe:
        why = deployable(rel, source, target)
        if why:
            blocked.append((rel, why))
            continue
        copyable.append(rel)

    return {
        "report": report,
        "copyable": copyable,
        "blocked": blocked,
        "needs_merge": refused,
        "repo_only_skills": list(report["right_only_skills"]),
    }


def deploy(
    source: Path, target: Path, apply: bool, only: set[str] | None = None
) -> int:
    p = plan(source, target, only)
    rep = p["report"]
    print(f"SOURCE (repo, authoritative) {source}")
    print(f"TARGET (loaded by Claude)    {target}")
    print(f"  summary {rep['summary']}")
    print(f"  safe to deploy  {len(p['copyable'])}")
    print(f"  refused by P2   {len(p['blocked'])}")
    print(f"  needs a human merge (NEVER touched) {len(p['needs_merge'])}")
    print(f"  repo-only skills NOT resurrected    {len(p['repo_only_skills'])}")

    for rel, why in p["blocked"]:
        print(f"  ! REFUSED {rel}  [{why}]")

    for rel in p["copyable"]:
        print(f"  {'COPY' if apply else 'WOULD-COPY'} {rel}")
        if apply:
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, dst)

    if not apply:
        print("\nDRY RUN -- nothing written. Pass --apply to deploy.")
    print(
        f"\n{'SUCCESS' if apply else 'DRY-RUN-OK'}:deploy-skills-daily "
        f"copied={len(p['copyable']) if apply else 0} "
        f"needs_merge={len(p['needs_merge'])}"
    )
    return EXIT_OK


def self_test() -> int:
    """Prove each guard FIRES against a purpose-built broken fixture (the both-states rule).

    Every case below is constructed so that a guard-less implementation would do the WRONG
    thing -- overwrite a diverged file, create a new skill, or delete a live-only file.  If a
    case passed with the guard removed it would prove nothing, so each asserts the specific
    wrong outcome does NOT happen while a control asserts the RIGHT one still does.
    """
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(
            f"  {'PASS' if cond else 'FAIL'}  {name}"
            + (f"  -- {detail}" if detail else "")
        )
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src, dst = root / "repo", root / "daily"

        def write(base: Path, rel: str, text: str) -> None:
            p = base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

        # shared skill "alpha"
        write(src, "alpha/SKILL.md", "a\nb\nc\n")  # repo strictly ahead
        write(dst, "alpha/SKILL.md", "a\nb\n")
        write(src, "alpha/new.md", "brand new\n")  # RIGHT-ONLY-FILE
        write(
            dst, "alpha/liveonly.md", "must survive\n"
        )  # LEFT-ONLY-FILE -> must NOT be deleted
        # shared skill "beta" -- genuinely two-directional, must never be touched
        write(src, "beta/SKILL.md", "shared\nrepo-unique\n")
        write(dst, "beta/SKILL.md", "shared\nlive-unique\n")
        # repo-only skill "gamma" -- must never be created in the target
        write(src, "gamma/SKILL.md", "resurrect me\n")

        p = plan(src, dst)
        copyable = set(p["copyable"])

        check(
            "CONTROL: a repo-ahead file IS offered",
            "alpha/SKILL.md" in copyable,
            "if this failed the tool would be a no-op and every other PASS meaningless",
        )
        check(
            "CONTROL: a repo-only FILE in a shared skill IS offered",
            "alpha/new.md" in copyable,
        )
        check("P1 a DIVERGED file is NOT offered", "beta/SKILL.md" not in copyable)
        check(
            "P2 a repo-only SKILL is NOT offered (integration path)",
            not any(r.startswith("gamma/") for r in copyable),
        )
        # The line above CANNOT kill a mutant that deletes the P2 guard: safe_to_deploy is built
        # from SHARED skills, so gamma never reaches the guard and the assertion holds either
        # way.  Measured -- the P2 mutant SURVIVED until these two direct cases were added.
        check(
            "P2 the guard itself refuses an absent target skill",
            deployable("gamma/SKILL.md", src, dst) is not None,
            "direct call: this is the case the integration path cannot construct",
        )
        check(
            "CONTROL: the guard ACCEPTS a present target skill",
            deployable("alpha/SKILL.md", src, dst) is None,
            "a guard that refuses everything would also pass the line above",
        )

        deploy(src, dst, apply=True)

        check(
            "P1 the diverged file was left untouched",
            (dst / "beta/SKILL.md").read_text(encoding="utf-8")
            == "shared\nlive-unique\n",
        )
        check("P2 the repo-only skill was not created", not (dst / "gamma").exists())
        check(
            "P3 the live-only file still exists (no prune)",
            (dst / "alpha/liveonly.md").exists(),
        )
        check(
            "CONTROL: the safe copies actually landed",
            (dst / "alpha/SKILL.md").read_text(encoding="utf-8") == "a\nb\nc\n"
            and (dst / "alpha/new.md").exists(),
        )

    if failures:
        print(
            f"\nFAILED:deploy-skills-daily-selftest {len(failures)} guard(s) did not hold: {failures}"
        )
        return EXIT_REFUSED
    print(
        "\nSUCCESS:deploy-skills-daily-selftest all guards fired on the broken fixture"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="deploy repo skills into the loaded curated tree"
    )
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--target", default=str(DEFAULT_TARGET))
    ap.add_argument(
        "--apply", action="store_true", help="actually write (runs --self-test first)"
    )
    ap.add_argument(
        "--self-test", action="store_true", help="prove the guards fire, write nothing"
    )
    ap.add_argument(
        "--only",
        action="append",
        default=[],
        help="narrow to named skills (repeatable); can only remove candidates",
    )
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    source, target = Path(args.source), Path(args.target)
    if not source.is_dir():
        print(f"FAILED:deploy-skills-daily source not a directory: {source}")
        return EXIT_USAGE
    if not target.is_dir():
        print(f"FAILED:deploy-skills-daily target not a directory: {target}")
        return EXIT_USAGE

    if args.apply:
        print("running --self-test before any write (P4)")
        if self_test() != EXIT_OK:
            print(
                "FAILED:deploy-skills-daily self-test did not pass; refusing to deploy"
            )
            return EXIT_REFUSED
        print()
    return deploy(source, target, apply=args.apply, only=set(args.only) or None)


if __name__ == "__main__":
    raise SystemExit(main())
