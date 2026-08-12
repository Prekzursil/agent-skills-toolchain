"""Acceptance suite for the LAST deploy hop, ``scripts/deploy-skills-daily.py``.

WHY THIS FILE EXISTS
--------------------
The tool it tests was shipped with **zero** references anywhere outside its own file and the
lane's scratch notes -- 0 in ``.github/``, 0 in ``ci/``, 0 in ``.agents/skills/``, 0 in
``skills/``, 0 in ``hooks/`` (measured 2026-08-12 with ``git grep -l deploy-skills-daily``).
A 256-line script that writes into ``~/.claude/skills.daily`` -- the ONE tree Claude Code
reads -- was therefore both unreachable by an agent and unproven by CI.

Two independent reviewers measured the specific hole this suite closes.  The tool's own
``--self-test`` proves P1/P2/P3 and is a hard precondition of ``--apply``, but it CANNOT prove
P4, because P4 is a property of ``main()`` and ``--self-test`` returns before ``main()`` ever
reaches the ``--apply`` branch.  Two mutants survived it:

    M5  delete the ``--apply`` self-test precondition   -> ``--self-test`` still exits 0
    M6  force ``apply=True`` regardless of the flag     -> ``--self-test`` still exits 0

``test_apply_refuses_when_the_self_test_fails`` and
``test_dry_run_is_the_default_and_writes_nothing`` are the two cases that kill them, and they
are the reason this file is a pytest suite rather than one more ``check()`` line inside
``self_test()``.

Every behavioural test is hermetic (``tmp_path`` only): the CI runner has no ``~/.claude``
tree, and this tool is a LOCAL operator command against the live trees, never a CI gate over
them.  The wiring and reachability tests read the repo and are the ones that go RED if the
integration is removed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "scripts" / "deploy-skills-daily.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"

CANONICAL_SKILL_ROOT = REPO_ROOT / ".agents" / "skills"
PROJECTED_SKILL_ROOT = REPO_ROOT / "skills"

# The exact invocation an agent is told to run.  Asserting the COMMAND (not the file name)
# keeps this a use-check rather than a mention-check: a document that merely names the script
# in prose does not satisfy it.
INVOCATION_MARKER = "python scripts/deploy-skills-daily.py"
# The workflow step that runs this suite by explicit path.  This repository has no test
# autodiscovery, so a directory glob is one refactor away from silently un-wiring the gate --
# the same reasoning already recorded on the L10 step in the workflow itself.
WORKFLOW_EXPLICIT_MARKER = "python -m pytest ci/tests/test_deploy_skills_daily.py"
WORKFLOW_GLOB_MARKER = "python -m pytest ci/tests tools/d001-dual-write/tests"


def _load():
    spec = importlib.util.spec_from_file_location("_deploy_skills_daily", TOOL_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture()
def pair(tmp_path: Path) -> tuple[Path, Path]:
    """A source/target pair carrying one of every class the guards must distinguish."""
    src, dst = tmp_path / "repo", tmp_path / "daily"

    def write(base: Path, rel: str, text: str) -> None:
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    write(src, "alpha/SKILL.md", "a\nb\nc\n")           # repo strictly ahead  -> safe
    write(dst, "alpha/SKILL.md", "a\nb\n")
    write(src, "alpha/new.md", "brand new\n")            # repo-only FILE      -> safe
    write(dst, "alpha/liveonly.md", "must survive\n")    # live-only FILE      -> P3
    write(src, "beta/SKILL.md", "shared\nrepo-unique\n")  # two-directional    -> P1
    write(dst, "beta/SKILL.md", "shared\nlive-unique\n")
    write(src, "gamma/SKILL.md", "resurrect me\n")       # repo-only SKILL     -> P2
    return src, dst


# --------------------------------------------------------------------------------------
# P4 -- the property the tool's own --self-test structurally cannot reach.
# --------------------------------------------------------------------------------------


def test_dry_run_is_the_default_and_writes_nothing(pair: tuple[Path, Path]) -> None:
    """Kills M6 (``apply=True`` forced).  No flag => the target is byte-for-byte untouched."""
    src, dst = pair
    before = {p: p.read_bytes() for p in dst.rglob("*") if p.is_file()}

    rc = mod.main(["--source", str(src), "--target", str(dst)])

    assert rc == mod.EXIT_OK
    after = {p: p.read_bytes() for p in dst.rglob("*") if p.is_file()}
    assert after == before, "a bare run wrote to the target; dry-run-by-default is broken"


def test_apply_refuses_when_the_self_test_fails(
    pair: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kills M5 (precondition deleted).  A red self-test must abort the write, not warn."""
    src, dst = pair
    before = {p: p.read_bytes() for p in dst.rglob("*") if p.is_file()}
    monkeypatch.setattr(mod, "self_test", lambda: mod.EXIT_REFUSED)

    rc = mod.main(["--source", str(src), "--target", str(dst), "--apply"])

    assert rc == mod.EXIT_REFUSED, "a failing self-test did not refuse the deploy"
    after = {p: p.read_bytes() for p in dst.rglob("*") if p.is_file()}
    assert after == before, "the deploy wrote despite a failing self-test"


def test_apply_copies_when_the_self_test_passes(pair: tuple[Path, Path]) -> None:
    """CONTROL.  Without this, a tool that refused EVERYTHING would pass both tests above."""
    src, dst = pair

    rc = mod.main(["--source", str(src), "--target", str(dst), "--apply"])

    assert rc == mod.EXIT_OK
    assert (dst / "alpha/SKILL.md").read_text(encoding="utf-8") == "a\nb\nc\n"
    assert (dst / "alpha/new.md").is_file()


# --------------------------------------------------------------------------------------
# P1 / P2 / P3 -- also covered by --self-test; re-asserted here so CI catches a regression
# even when nobody runs the tool.
# --------------------------------------------------------------------------------------


def test_a_diverged_file_is_never_offered_or_written(pair: tuple[Path, Path]) -> None:
    src, dst = pair
    plan = mod.plan(src, dst)
    assert "beta/SKILL.md" not in set(plan["copyable"])

    mod.main(["--source", str(src), "--target", str(dst), "--apply"])

    assert (dst / "beta/SKILL.md").read_text(encoding="utf-8") == "shared\nlive-unique\n"


def test_a_repo_only_skill_is_never_resurrected(pair: tuple[Path, Path]) -> None:
    src, dst = pair
    mod.main(["--source", str(src), "--target", str(dst), "--apply"])
    assert not (dst / "gamma").exists()


def test_the_p2_guard_itself_refuses_an_absent_target_skill(pair: tuple[Path, Path]) -> None:
    """Direct call on the seam: the integration path cannot construct this case.

    ``safe_to_deploy`` is built from SHARED skills only, so ``gamma`` never reaches the guard
    and the integration assertion above holds even with the guard deleted.  Measured: the P2
    mutant survived until this direct case existed.
    """
    src, dst = pair
    assert mod.deployable("gamma/SKILL.md", src, dst) is not None


def test_the_p2_guard_accepts_a_present_target_skill(pair: tuple[Path, Path]) -> None:
    """CONTROL for the line above -- a guard that refused everything would also pass it."""
    src, dst = pair
    assert mod.deployable("alpha/SKILL.md", src, dst) is None


def test_a_live_only_file_survives_a_deploy(pair: tuple[Path, Path]) -> None:
    """P3.  There is no prune in this tool and there must never be one."""
    src, dst = pair
    mod.main(["--source", str(src), "--target", str(dst), "--apply"])
    assert (dst / "alpha/liveonly.md").read_text(encoding="utf-8") == "must survive\n"


def test_only_narrows_the_deploy_and_cannot_widen_it(pair: tuple[Path, Path]) -> None:
    """``--only`` is advertised in the agent-facing skill body, so CI must prove it works."""
    src, dst = pair
    full = set(mod.plan(src, dst)["copyable"])
    narrowed = set(mod.plan(src, dst, only={"alpha"})["copyable"])
    assert narrowed <= full and narrowed
    assert all(rel.split("/", 1)[0] == "alpha" for rel in narrowed)
    assert set(mod.plan(src, dst, only={"nosuchskill"})["copyable"]) == set()


def test_the_builtin_self_test_passes() -> None:
    """The precondition of every real ``--apply`` runs in CI too, not only on the operator's box."""
    assert mod.self_test() == mod.EXIT_OK


def test_a_missing_target_is_a_usage_error_not_a_silent_pass(tmp_path: Path) -> None:
    """Fail closed: an absent live tree must not read as "nothing to do"."""
    src = tmp_path / "repo"
    (src / "alpha").mkdir(parents=True)
    (src / "alpha" / "SKILL.md").write_text("x\n", encoding="utf-8")
    rc = mod.main(["--source", str(src), "--target", str(tmp_path / "absent")])
    assert rc == mod.EXIT_USAGE


# --------------------------------------------------------------------------------------
# INTEGRATION -- these are the assertions that go RED if the wiring is removed.
# --------------------------------------------------------------------------------------


def test_the_tool_this_suite_guards_exists() -> None:
    assert TOOL_PATH.is_file(), f"missing {TOOL_PATH}"


def test_the_workflow_runs_this_suite_by_explicit_path() -> None:
    """Un-wiring the named step fails loudly instead of quietly de-gating the tool."""
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert WORKFLOW_EXPLICIT_MARKER in WORKFLOW.read_text(encoding="utf-8"), (
        "skill-dual-write.yml no longer invokes this suite by explicit path"
    )


def test_the_workflow_glob_still_covers_this_directory() -> None:
    """The second, independent route.  Both must hold; either one alone is a single signal."""
    rel = Path(__file__).resolve().parent.relative_to(REPO_ROOT).as_posix()
    assert rel == "ci/tests"
    assert WORKFLOW_GLOB_MARKER in WORKFLOW.read_text(encoding="utf-8")


def _skills_carrying_the_invocation(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {
        p.parent.name
        for p in root.glob("*/SKILL.md")
        if INVOCATION_MARKER in p.read_text(encoding="utf-8", errors="replace")
    }


def test_the_deploy_hop_has_an_agent_facing_surface() -> None:
    """The measured defect class: a tool with no skill/hook/CI reference is unreachable.

    ``tools/detector-self-test/`` and ``tools/measure-guard/`` were both shipped with zero
    agent-facing surface and were never invoked.  This asserts the route exists, in the
    canonical root, as a runnable command rather than a prose mention.
    """
    carriers = _skills_carrying_the_invocation(CANONICAL_SKILL_ROOT)
    assert carriers, (
        f"no curated skill tells an agent to run `{INVOCATION_MARKER}`; the last deploy hop "
        "is unreachable and skills authored in the live tree stay orphaned from git"
    )


def test_the_agent_facing_surface_is_dual_written() -> None:
    """`.agents/skills` is canonical and `skills/` its projection -- a half-edit is drift."""
    canonical = _skills_carrying_the_invocation(CANONICAL_SKILL_ROOT)
    projected = _skills_carrying_the_invocation(PROJECTED_SKILL_ROOT)
    assert canonical == projected, (
        f"the deploy-hop reference is not dual-written: only in .agents/skills="
        f"{sorted(canonical - projected)} only in skills={sorted(projected - canonical)}"
    )
