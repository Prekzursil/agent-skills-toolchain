"""Acceptance tests for the D-001 dual-write guard.

Every behavioural assertion drives the guard as a REAL SUBPROCESS and reads
``CompletedProcess.returncode`` directly.  Nothing is piped: a pipeline replaces
the guard's own exit status with the last stage's, which is exactly how an
earlier verification pass printed ``EXIT=0`` next to output that read
``D-001 DUAL-WRITE VIOLATION``.

Naming: ``test_control_*`` are the both-states controls (a detector that is
silent in both states measures nothing); the defect tests carry the defect id
from the lane's remediation matrix.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dual_write_fixtures import Repo

GUARD = Path(__file__).resolve().parents[1] / "check_skill_dual_write.py"

NEW_SKILL = "# probe-skill\n\nreal content\n"
EDIT = "# existing-skill\n\nedited content\n"


def run_guard(repo: Repo, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), "--repo", str(repo.root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_range(repo: Repo, *args: str) -> subprocess.CompletedProcess[str]:
    return run_guard(repo, "--base", "main", "--head", "feature", *args)


def reasons(proc: subprocess.CompletedProcess[str]) -> dict[str, str]:
    payload = json.loads(proc.stdout)
    return {k: str(v["reason"]) for k, v in payload["violations"].items()}


# --------------------------------------------------------------------------
# Both-states controls
# --------------------------------------------------------------------------


def test_control_projection_only_new_skill_fires(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.add("skills/probe-skill/SKILL.md")
    repo.commit("projection only")
    proc = run_range(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "D-001 DUAL-WRITE VIOLATION" in proc.stdout
    assert "probe-skill" in proc.stdout


def test_control_correct_dual_write_passes(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write(".agents/skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write("skills/existing-skill/SKILL.md", EDIT)
    repo.write(".agents/skills/existing-skill/SKILL.md", EDIT)
    repo.add("skills", ".agents")
    repo.commit("dual write")
    proc = run_range(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: no skills/ change lacks" in proc.stdout


def test_control_null_range_passes(repo: Repo) -> None:
    proc = run_guard(repo, "--base", "main", "--head", "main")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_control_loose_file_under_skills_is_not_a_skill(repo: Repo) -> None:
    repo.write("skills/SKILLS-MANIFEST.md", "# manifest v2\n")
    repo.write("skills/DEPLOYED-MANIFEST.json", "{}\n")
    repo.add("skills/SKILLS-MANIFEST.md", "skills/DEPLOYED-MANIFEST.json")
    repo.commit("loose files only")
    proc = run_range(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------
# D2 -- canonical DELETE must not discharge the dual-write obligation
# --------------------------------------------------------------------------


def test_d2_canonical_delete_with_projection_edit_fires(repo: Repo) -> None:
    """input: canonical status=D, projection status=M -> guard must FIRE."""
    repo.write("skills/existing-skill/SKILL.md", EDIT)
    repo.add("skills/existing-skill/SKILL.md")
    repo.remove(".agents/skills/existing-skill/SKILL.md")
    repo.commit("canonical deleted, projection edited")

    status = repo.git("diff", "--name-status", "--no-renames", "main...feature")
    assert "D\t.agents/skills/existing-skill/SKILL.md" in status
    assert "M\tskills/existing-skill/SKILL.md" in status

    proc = run_range(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "existing-skill" in proc.stdout
    assert reasons(run_range(repo, "--json")) == {"existing-skill": "canonical-deleted"}


def test_d2_negative_control_canonical_delete_alone_is_not_a_violation(
    repo: Repo,
) -> None:
    """The fix must not fire on everything: a canonical-only deletion is legal."""
    repo.remove(".agents/skills/existing-skill/SKILL.md")
    repo.commit("canonical deleted only")
    proc = run_range(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_d2_negative_control_canonical_internal_rename_still_discharges(
    repo: Repo,
) -> None:
    """Canonical D **plus** canonical A for the same skill is a real dual-write."""
    repo.write("skills/existing-skill/SKILL.md", EDIT)
    repo.write(".agents/skills/existing-skill/GUIDE.md", EDIT)
    repo.add("skills/existing-skill/SKILL.md", ".agents/skills/existing-skill/GUIDE.md")
    repo.remove(".agents/skills/existing-skill/SKILL.md")
    repo.commit("canonical rename + projection edit")
    proc = run_range(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------
# D3 -- an EMPTY canonical placeholder must not discharge the obligation
# --------------------------------------------------------------------------


def test_d3_empty_canonical_placeholder_does_not_discharge(repo: Repo) -> None:
    """input: .agents/skills/foo/.keep (0 bytes) + skills/foo/SKILL.md."""
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write_bytes(".agents/skills/probe-skill/.keep", b"")
    repo.add("skills/probe-skill/SKILL.md", ".agents/skills/probe-skill/.keep")
    repo.commit("placeholder canonical")

    size = repo.git("cat-file", "-s", "feature:.agents/skills/probe-skill/.keep")
    assert size.strip() == "0"

    proc = run_range(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(run_range(repo, "--json")) == {"probe-skill": "canonical-empty"}


def test_d3_negative_control_canonical_content_discharges(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write(".agents/skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.add("skills/probe-skill/SKILL.md", ".agents/skills/probe-skill/SKILL.md")
    repo.commit("real canonical content")
    proc = run_range(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_d3_residual_one_byte_placeholder_still_discharges(repo: Repo) -> None:
    """PINNED RESIDUAL, not a passing feature.

    The default rule is non-empty-content-level, not equivalence-level, so a
    one-byte placeholder still discharges.  --strict-parity closes it; this test
    exists so the gap cannot silently change without someone noticing.
    """
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write_bytes(".agents/skills/probe-skill/.keep", b"x")
    repo.add("skills/probe-skill/SKILL.md", ".agents/skills/probe-skill/.keep")
    repo.commit("one-byte placeholder")
    assert run_range(repo).returncode == 0
    assert run_range(repo, "--strict-parity").returncode == 1


# --------------------------------------------------------------------------
# --strict-parity (opt-in) -- byte-identical counterpart per relative path
# --------------------------------------------------------------------------


def test_strict_parity_fires_on_divergent_content(repo: Repo) -> None:
    repo.write("skills/existing-skill/SKILL.md", EDIT)
    repo.write(".agents/skills/existing-skill/SKILL.md", EDIT + "drifted\n")
    repo.add("skills", ".agents")
    repo.commit("both touched, different content")
    assert run_range(repo).returncode == 0  # documented default-mode residual
    proc = run_range(repo, "--strict-parity")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(run_range(repo, "--strict-parity", "--json")) == {
        "existing-skill": "canonical-divergent"
    }


def test_strict_parity_negative_control_identical_content_passes(repo: Repo) -> None:
    repo.write("skills/existing-skill/SKILL.md", EDIT)
    repo.write(".agents/skills/existing-skill/SKILL.md", EDIT)
    repo.add("skills", ".agents")
    repo.commit("both touched, identical content")
    assert run_range(repo, "--strict-parity").returncode == 0


# --------------------------------------------------------------------------
# Modes, parsing and usage
# --------------------------------------------------------------------------


def test_staged_mode_fires_before_the_commit_exists(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.add("skills/probe-skill/SKILL.md")
    proc = run_guard(repo, "--staged")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert repo.git("rev-parse", "HEAD") == repo.git("rev-parse", "main")


def test_staged_mode_control_passes_on_a_correct_dual_write(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write(".agents/skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.add("skills/probe-skill/SKILL.md", ".agents/skills/probe-skill/SKILL.md")
    assert run_guard(repo, "--staged").returncode == 0


def test_staged_mode_detects_the_empty_placeholder_too(repo: Repo) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.write_bytes(".agents/skills/probe-skill/.keep", b"")
    repo.add("skills/probe-skill/SKILL.md", ".agents/skills/probe-skill/.keep")
    proc = run_guard(repo, "--staged", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"probe-skill": "canonical-empty"}


def test_path_that_git_c_quotes_is_parsed_not_dropped(repo: Repo) -> None:
    """A non-ASCII path is C-quoted by --name-status; -z parsing must survive it.

    The first revision of this test used a path containing a SPACE, which git
    does NOT quote (the field separator is a tab).  It therefore passed against
    a line-based parser that cannot handle quoting at all -- mutation M3
    survived and exposed it.  The fixture now asserts the quoting ACTUALLY
    happens before it asserts anything about the guard's verdict.

    This is not a hypothetical: two commits on origin/main add
    ``skills/swfoc-modding/...\\uf03aZone.Identifier`` paths, which git emits as
    ``"skills/swfoc-modding/SKILL.md\\357\\200\\272Zone.Identifier"``.  A
    line-based parser sees a leading quote, fails the ``skills/`` prefix test,
    and silently drops the skill.
    """
    name = "café-skill"
    repo.write(f"skills/{name}/SKILL.md", NEW_SKILL)
    repo.add(f"skills/{name}/SKILL.md")
    repo.commit("non-ascii skill dir")

    unquoted = repo.git("diff", "--name-status", "--no-renames", "main...feature")
    assert '"' in unquoted, f"fixture did not trigger C-quoting: {unquoted!r}"
    assert "\\3" in unquoted, f"fixture did not trigger octal escaping: {unquoted!r}"

    proc = run_range(repo, "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {name: "canonical-missing"}


def test_path_containing_a_space_is_parsed(repo: Repo) -> None:
    """Separate case: a space is NOT quoted, but must still parse correctly."""
    repo.write("skills/has space/SKILL.md", NEW_SKILL)
    repo.add("skills/has space/SKILL.md")
    repo.commit("spaced skill dir")
    proc = run_range(repo, "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"has space": "canonical-missing"}


def test_allowlist_suppresses_a_named_skill(repo: Repo, tmp_path: Path) -> None:
    repo.write("skills/probe-skill/SKILL.md", NEW_SKILL)
    repo.add("skills/probe-skill/SKILL.md")
    repo.commit("projection only")
    allow = tmp_path / "allow.txt"
    allow.write_text("# reasoned exception\nprobe-skill\n", encoding="utf-8")
    assert run_range(repo, "--allowlist", str(allow)).returncode == 0
    assert run_range(repo).returncode == 1


def test_usage_staged_with_base_is_rejected(repo: Repo) -> None:
    proc = run_guard(repo, "--staged", "--base", "main")
    assert proc.returncode == 2
    assert "cannot be combined" in proc.stderr


def test_usage_unknown_revision_is_exit_2_not_a_false_green(repo: Repo) -> None:
    proc = run_guard(repo, "--base", "no-such-ref", "--head", "feature")
    assert proc.returncode == 2, proc.stdout + proc.stderr
