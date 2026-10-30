"""D4 -- the gate must actually be EXECUTED, not merely committed.

This repository has no repo-wide test autodiscovery.  ``quality.yml`` runs a
short, explicit list of per-package ``run:`` blocks; dropping a file into a
directory does NOT get it executed, and the ``ci/checks/`` path an earlier
proposal targeted does not exist on any branch.  A check runs here only when a
workflow step invokes it by an explicit path -- the ``ci/gen_hooks.py`` /
``.quality/charter_check.sh`` precedent.

These tests assert the structural link between this suite and the workflow step
that runs it, so moving or renaming either side fails loudly instead of quietly
un-wiring the gate.  The both-states proof for D4 (break an assertion -> the CI
command goes RED; revert -> GREEN) is run against the workflow's own command
line and recorded in the lane evidence.
"""

from __future__ import annotations

import json

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
GUARD = REPO_ROOT / "ci" / "check_skill_dual_write.py"
INDEX = REPO_ROOT / "ci" / "gen_skill_index.py"
APPLIER = REPO_ROOT / "tools" / "d001-dual-write" / "d001_apply.py"

SELFTEST_MARKER = "python -m pytest ci/tests tools/d001-dual-write/tests"
GATE_MARKER = "python ci/check_skill_dual_write.py"
INDEX_GATE_MARKER = "python ci/gen_skill_index.py --check --fail-on-drift"
README = REPO_ROOT / "README.md"
PROJECT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
MARKETPLACE_ADD_MARKER = (
    "claude plugin marketplace add Prekzursil/agent-skills-toolchain "
    "--sparse .claude-plugin .agents/skills skills skills-claude-only"
)
PLUGIN_INSTALL_MARKER = (
    "claude plugin install agent-skills-toolchain@agent-skills-toolchain"
)
CONSOLIDATED_WEB_SKILL_MARKER = (
    "- skills: `chatgpt5-web` (modes: query / discuss / curate)"
)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_file_exists() -> None:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"


def test_guard_and_applier_paths_referenced_by_the_workflow_exist() -> None:
    assert GUARD.is_file()
    assert APPLIER.is_file()


def test_workflow_selftest_step_covers_this_test_directory() -> None:
    """If these tests move, the workflow must move with them."""
    rel = Path(__file__).resolve().parent.relative_to(REPO_ROOT).as_posix()
    assert rel == "ci/tests"
    assert SELFTEST_MARKER in workflow_text()


def test_workflow_selftest_step_covers_the_applier_test_directory() -> None:
    rel = APPLIER.parent.joinpath("tests").relative_to(REPO_ROOT).as_posix()
    assert rel == "tools/d001-dual-write/tests"
    assert rel in workflow_text()


def test_workflow_invokes_the_guard_by_explicit_path() -> None:
    text = workflow_text()
    assert GATE_MARKER in text
    assert "--base origin/main --head HEAD" in text


def test_workflow_invokes_the_generated_index_gate_by_explicit_path() -> None:
    """Known-broken pre-change: the A01 generator is never executed by CI."""
    assert INDEX.is_file()
    assert INDEX_GATE_MARKER in workflow_text()


def test_workflow_job_carries_a_gate_marker_name() -> None:
    assert "name: gate-skill-dual-write" in workflow_text()


def test_workflow_pins_every_action_by_sha() -> None:
    """Repo policy: all actions are SHA-pinned (supply-chain hardening)."""
    uses = [
        line.split("uses:", 1)[1].strip()
        for line in workflow_text().splitlines()
        if "uses:" in line
    ]
    assert uses, "workflow declares no actions"
    for ref in uses:
        action, _, sha = ref.partition("@")
        sha = sha.split()[0]
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), (
            f"{action} is not SHA-pinned: {ref}"
        )


def test_workflow_fetches_main_so_the_three_dot_base_resolves() -> None:
    text = workflow_text()
    assert "fetch-depth: 0" in text
    assert "refs/remotes/origin/main" in text


def test_guard_index_and_applier_paths_referenced_by_the_workflow_exist() -> None:
    assert GUARD.is_file()
    assert INDEX.is_file()
    assert APPLIER.is_file()


def test_workflow_invokes_the_skill_index_gate_by_explicit_path() -> None:
    """Known-broken pre-F14: no production workflow executes the shipped generator."""
    assert INDEX_GATE_MARKER in workflow_text()


def test_readme_exposes_the_plugin_install_and_consolidated_skill_callsite() -> None:
    """Known-broken pre-F14: install is missing and docs invoke six dangling aliases."""
    text = README.read_text(encoding="utf-8")
    assert MARKETPLACE_ADD_MARKER in text
    assert PLUGIN_INSTALL_MARKER in text
    assert CONSOLIDATED_WEB_SKILL_MARKER in text


def test_project_settings_register_and_enable_the_skill_surface() -> None:
    """Known-broken pre-F14: no project registry points Claude at the shipped plugin."""
    assert PROJECT_SETTINGS.is_file()
    settings = json.loads(PROJECT_SETTINGS.read_text(encoding="utf-8"))
    source = settings["extraKnownMarketplaces"]["agent-skills-toolchain"]["source"]
    assert source == {
        "source": "github",
        "repo": "Prekzursil/agent-skills-toolchain",
    }
    assert settings["enabledPlugins"] == {
        "agent-skills-toolchain@agent-skills-toolchain": True
    }


STRICT_GATE_MARKER = (
    "run: python ci/check_skill_dual_write.py "
    "--base origin/main --head HEAD --strict-parity"
)


def workflow_run_lines() -> set[str]:
    return {
        line.strip()
        for line in workflow_text().splitlines()
        if not line.lstrip().startswith("#")
    }


def test_workflow_adopts_final_tree_strict_parity() -> None:
    """KNOWN-BROKEN: CI invoked only the weaker non-empty same-skill rule."""
    assert STRICT_GATE_MARKER in workflow_run_lines()


def test_workflow_does_not_advertise_null_range_events() -> None:
    # The original defect: push/dispatch ran the D-001 step as
    # --base origin/main --head HEAD, which on a push event diffs main against
    # itself (a null range, silently green). Since the 2026-10-30 main-parity
    # change the workflow HAS push triggers, so this guard enforces the FIX
    # instead of the trigger ban: the origin/main form must be event-gated to
    # pull_request only, and the push path must diff the merge delta (HEAD^1).
    text = workflow_text()
    for chunk in text.split("- name: ")[1:]:
        chunk = "- name: " + chunk
        if "--base origin/main --head HEAD" in chunk:
            assert "github.event_name" in chunk, (
                "unconditional null-range D-001 step is back"
            )
        if "--base HEAD^1" in chunk:
            assert "github.event_name" in chunk, "push-mode D-001 lost its gate"
    assert "--base HEAD^1" in text, "push-mode D-001 missing - main parity regressed"
