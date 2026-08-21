"""Test suite for scripts/sync-skills.ps1 -- the repo `skills/` -> `~/.agents/skills` deploy hop.

WHY THIS EXISTS
    This script is the LAST hop before code executes. `mon.cmd` puts
    `~/.agents/skills/workflow-monitor` on PYTHONPATH and runs `python -m
    monitorcore.monitors`, so whatever this script last deployed IS what every registered
    monitor runs. Measured 2026-08-17 (bug WF-5): the live monitorcore was 37 modules
    against the repo's 38 -- `remote_workers.py` absent and five modules hash-differing --
    because this hop had not run since before 2026-08-12. Every repo gate was green
    throughout: `vendordrift` compares committed copies by index OID, so the deploy lag is
    structurally invisible to it.

    The script shipped with ZERO tests while being per-skill DESTRUCTIVE
    (`Remove-Item -Recurse -Force` then `Copy-Item -Recurse`). Measured on the real trees,
    a bulk run wipes+recopies 326 shared skill dirs and deletes 244 live-only files, so a
    regression here is silent data loss across the whole live harness rather than a bad
    copy of one skill.

    The `-Skill` filter and its `-Prune` guard are the behaviour under test. Both are
    exercised in BOTH states (rules/common/single-signal-verification.md 3b): every test
    that asserts a file SURVIVED is paired with a control proving the same fixture loses
    that file when the filter is absent -- otherwise "it survived" would be equally true of
    a script that copies nothing at all.

SAFETY
    Every test builds a throwaway repo and a throwaway live dir under pytest's tmp_path and
    points the script at them with -Root / -Dest. No test reads or writes the real
    ~/.agents/skills or the real repository.

NOTE ON `run_sync`
    scripts/test_sync_from_live.py defines a helper of the same name. It drives a DIFFERENT
    script through a DIFFERENT CLI (`sync-from-live.ps1`, `-LiveHome`); this one drives
    `sync-skills.ps1` via `-Dest`. Deliberately separate, not a duplicated implementation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "sync-skills.ps1"


# --------------------------------------------------------------------------- helpers


def run_sync(root: Path, dest: Path, *args: str, timeout: int = 300):
    """Invoke the real script as a black box via `pwsh -File`."""
    cmd = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT),
        "-Root",
        str(root),
        "-Dest",
        str(dest),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def run_sync_in_session(root: Path, dest: Path, skill_expr: str, timeout: int = 300):
    """Invoke via `pwsh -Command`, where a real PowerShell array is bound to -Skill.

    `-File` and `-Command` bind arguments differently, so the two styles are separate
    measurements and both are pinned.
    """
    expr = f"& '{SCRIPT}' -Root '{root}' -Dest '{dest}' -Skill {skill_expr}"
    cmd = ["pwsh", "-NoProfile", "-NonInteractive", "-Command", expr]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def make_skill(root: Path, name: str, files: dict[str, str] | None = None) -> Path:
    """Create a repo-side skill dir. A dir only counts as a skill if it has SKILL.md."""
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    for rel, body in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return d


@pytest.fixture
def trees(tmp_path: Path):
    """A three-skill repo and an empty live dir."""
    root = tmp_path / "repo"
    dest = tmp_path / "live"
    dest.mkdir(parents=True)
    make_skill(root, "alpha", {"mod.py": "ALPHA_V2\n"})
    make_skill(root, "beta", {"mod.py": "BETA_V2\n"})
    make_skill(root, "gamma", {"mod.py": "GAMMA_V2\n"})
    return root, dest


def seed_live(dest: Path, name: str, files: dict[str, str]) -> None:
    """Plant a pre-existing live copy of a skill."""
    d = dest / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    for rel, body in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def seed_all_v1(dest: Path) -> None:
    for name in ("alpha", "beta", "gamma"):
        seed_live(dest, name, {"mod.py": f"{name.upper()}_V1\n"})


def body(dest: Path, name: str) -> str:
    return (dest / name / "mod.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- environment


def test_pwsh_and_script_are_present():
    """A missing interpreter must fail loudly, not silently skip the whole suite."""
    assert SCRIPT.is_file(), f"script not found: {SCRIPT}"
    p = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert p.returncode == 0, f"pwsh unavailable: {p.stderr}"


# --------------------------------------------------------------------------- baseline


def test_bulk_run_still_syncs_every_skill(trees):
    """Regression guard: adding -Skill must not change the default (unfiltered) path."""
    root, dest = trees
    p = run_sync(root, dest)
    assert p.returncode == 0, p.stderr
    for name in ("alpha", "beta", "gamma"):
        assert body(dest, name) == f"{name.upper()}_V2\n"


# --------------------------------------------------------------------------- -Skill


def test_skill_filter_deploys_only_the_named_skill(trees):
    """The named skill is updated and the others are left byte-untouched."""
    root, dest = trees
    seed_all_v1(dest)

    p = run_sync(root, dest, "-Skill", "beta")
    assert p.returncode == 0, p.stderr

    assert body(dest, "beta") == "BETA_V2\n"
    # untouched skills keep their OLD content -- the filter is what protects them
    assert body(dest, "alpha") == "ALPHA_V1\n"
    assert body(dest, "gamma") == "GAMMA_V1\n"


def test_control_unfiltered_run_does_update_the_other_skills(trees):
    """BOTH-STATES control for the test above.

    Without it, "alpha still says V1" would also pass for a script that copies nothing.
    Same fixture, filter removed: every skill must move to V2.
    """
    root, dest = trees
    seed_all_v1(dest)

    p = run_sync(root, dest)
    assert p.returncode == 0, p.stderr
    for name in ("alpha", "beta", "gamma"):
        assert body(dest, name) == f"{name.upper()}_V2\n"


def test_comma_joined_names_work_under_pwsh_file(trees):
    """`pwsh -File` passes arguments as LITERAL STRINGS and does not split on commas.

    Measured 2026-08-17: `-Skill ALPHA,Gamma` arrived as a single array element and was
    rejected as an unknown skill -- while that exact comma form was the documented
    .EXAMPLE in the script. The script now splits the value itself. This test is the pin;
    it FAILED against the pre-split implementation.
    """
    root, dest = trees
    seed_all_v1(dest)

    p = run_sync(root, dest, "-Skill", "ALPHA,Gamma")
    assert p.returncode == 0, p.stdout + p.stderr
    assert body(dest, "alpha") == "ALPHA_V2\n"  # also pins case-insensitive matching
    assert body(dest, "gamma") == "GAMMA_V2\n"
    assert body(dest, "beta") == "BETA_V1\n"


def test_real_array_binding_works_under_pwsh_command(trees):
    """The other invocation style: a genuine PowerShell array bound to -Skill."""
    root, dest = trees
    seed_all_v1(dest)

    p = run_sync_in_session(root, dest, "@('alpha','gamma')")
    assert p.returncode == 0, p.stdout + p.stderr
    assert body(dest, "alpha") == "ALPHA_V2\n"
    assert body(dest, "gamma") == "GAMMA_V2\n"
    assert body(dest, "beta") == "BETA_V1\n"


def test_live_only_file_survives_in_an_unsynced_skill(trees):
    """The real reason -Skill exists: a live-only artifact in another skill is not deleted."""
    root, dest = trees
    seed_live(dest, "alpha", {"scratch.db": "live-only\n"})

    p = run_sync(root, dest, "-Skill", "beta")
    assert p.returncode == 0, p.stderr
    assert (dest / "alpha" / "scratch.db").is_file()


def test_control_unfiltered_run_deletes_that_live_only_file(trees):
    """BOTH-STATES control: the same artifact IS destroyed by a bulk run.

    This is what makes the previous assertion meaningful -- and it pins the destructive
    wipe+recopy semantics that motivated the filter.
    """
    root, dest = trees
    seed_live(dest, "alpha", {"scratch.db": "live-only\n"})

    p = run_sync(root, dest)
    assert p.returncode == 0, p.stderr
    assert not (dest / "alpha" / "scratch.db").exists()


# --------------------------------------------------------------------------- guards


def test_unknown_skill_name_fails_and_copies_nothing(trees):
    """A typo must not degrade into a successful no-op run."""
    root, dest = trees
    p = run_sync(root, dest, "-Skill", "workflow-moniter")
    assert p.returncode != 0
    assert "unknown skill" in (p.stdout + p.stderr).lower()
    for name in ("alpha", "beta", "gamma"):
        assert not (dest / name).exists()


def test_one_bad_name_among_good_ones_still_fails_closed(trees):
    root, dest = trees
    p = run_sync(root, dest, "-Skill", "alpha,nope")
    assert p.returncode != 0
    assert not (dest / "alpha").exists(), "a partial deploy happened before validation"


def test_skill_with_prune_is_refused(trees):
    """-Skill + -Prune would delete every live skill outside the filter.

    $synced holds only the filtered names, and the prune pass deletes any live skill dir
    missing from it -- so the combination destroys exactly what the filter protects.
    """
    root, dest = trees
    seed_all_v1(dest)

    p = run_sync(root, dest, "-Skill", "beta", "-Prune")
    assert p.returncode != 0
    assert "-prune" in (p.stdout + p.stderr).lower()
    # nothing was pruned and nothing was copied
    for name in ("alpha", "beta", "gamma"):
        assert body(dest, name) == f"{name.upper()}_V1\n"


def test_control_prune_without_skill_still_prunes(trees):
    """BOTH-STATES control: -Prune alone remains functional after the guard was added."""
    root, dest = trees
    seed_live(dest, "retired", {"mod.py": "OLD\n"})

    p = run_sync(root, dest, "-Prune")
    assert p.returncode == 0, p.stderr
    assert not (dest / "retired").exists(), "-Prune stopped working"
    assert (dest / "alpha").is_dir()


def test_whatif_with_skill_writes_nothing(trees):
    root, dest = trees
    p = run_sync(root, dest, "-Skill", "beta", "-WhatIf")
    assert p.returncode == 0, p.stderr
    assert not (dest / "beta").exists()
