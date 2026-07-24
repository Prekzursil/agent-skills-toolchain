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
import os
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


def test_newline_in_a_path_does_not_desynchronise_the_post_image_map(
    repo: Repo,
) -> None:
    """A path containing a NEWLINE must not shift another skill's post-image.

    The earlier revision resolved post-images by writing one ``<rev>:<path>``
    per LINE into ``git cat-file --batch-check`` and zipping the output back BY
    INDEX.  A name containing a newline produces TWO input lines, so every later
    path reads another file's record -- and a 0-byte ``.keep`` borrows a
    non-empty size, resurrecting the exact false negative D3 exists to close.

    The trigger is not free: the text after the newline must itself be a VALID
    rev expression for a NON-EMPTY blob, or the attack does not fire and a
    line-zip parser passes it honestly.  The fixture asserts its own trigger
    below -- the round-1 lesson from a C-quoting test whose path contained a
    space git never quotes.

    ``bbb`` is byte-for-byte identical in both branches; only an UNRELATED file
    is added.  On the ubuntu-latest runner this gate executes on, such a name is
    ordinary and needs no special flag.
    """
    real = repo.hash_blob(b"# aaa\n\nreal canonical content\n")
    proj = repo.hash_blob(b"# proj\n\nprojection content\n")
    empty = repo.hash_blob(b"")
    decoy = repo.hash_blob(b"decoy\n")

    baseline = {
        ".agents/skills/aaa/SKILL.md": ("100644", real),
        "skills/aaa/SKILL.md": ("100644", proj),
        ".agents/skills/bbb/.keep": ("100644", empty),
        "skills/bbb/SKILL.md": ("100644", proj),
    }
    repo.plumb_branch(baseline, "nl-control")
    control = run_guard(repo, "--base", "main", "--head", "nl-control", "--json")
    assert control.returncode == 1, control.stdout + control.stderr
    assert reasons(control) == {"bbb": "canonical-empty"}

    poison = ".agents/skills/aaa/z\nnl-attack:.agents/skills/aaa/SKILL.md"
    attack = {**baseline, poison: ("100644", decoy)}
    repo.plumb_branch(attack, "nl-attack")

    # The fixture must actually contain the two-line name it claims to.
    listing = repo.git(
        "diff", "--name-status", "-z", "--no-renames", "main...nl-attack"
    )
    assert any("\n" in field for field in listing.split("\0") if field), (
        f"fixture did not create a newline-bearing path: {listing!r}"
    )

    proc = run_guard(repo, "--base", "main", "--head", "nl-attack", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"bbb": "canonical-empty"}


def test_control_a_newline_path_in_a_correct_change_stays_silent(
    repo: Repo,
) -> None:
    """The other state: the fix must not block an author for a legal filename."""
    real = repo.hash_blob(b"# eee\n\nreal canonical content\n")
    proj = repo.hash_blob(b"# proj\n\nprojection content\n")
    decoy = repo.hash_blob(b"decoy\n")
    entries = {
        ".agents/skills/eee/SKILL.md": ("100644", real),
        "skills/eee/SKILL.md": ("100644", proj),
        ".agents/skills/eee/z\nmain:README.md": ("100644", decoy),
    }
    repo.plumb_branch(entries, "nl-legit")
    proc = run_guard(repo, "--base", "main", "--head", "nl-legit", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_symlink_canonical_side_does_not_discharge_the_obligation(
    repo: Repo,
) -> None:
    """A symlink's blob is its non-empty TARGET STRING, not skill content."""
    proj = repo.hash_blob(b"# proj\n\nprojection content\n")
    target = repo.hash_blob(b"../../../skills/ccc/SKILL.md")
    repo.plumb_branch(
        {
            ".agents/skills/ccc/SKILL.md": ("120000", target),
            "skills/ccc/SKILL.md": ("100644", proj),
        },
        "sym",
    )
    proc = run_guard(repo, "--base", "main", "--head", "sym", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"ccc": "canonical-not-a-file"}
    assert (
        "not a regular file"
        in run_guard(repo, "--base", "main", "--head", "sym").stdout
    )


def test_gitlink_canonical_side_does_not_discharge_the_obligation(
    repo: Repo,
) -> None:
    proj = repo.hash_blob(b"# proj\n\nprojection content\n")
    head = repo.git("rev-parse", "main").strip()
    repo.plumb_branch(
        {
            ".agents/skills/ddd/vendored": ("160000", head),
            "skills/ddd/SKILL.md": ("100644", proj),
        },
        "sub",
    )
    proc = run_guard(repo, "--base", "main", "--head", "sub", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"ddd": "canonical-not-a-file"}


def test_post_image_sizes_refuse_to_guess_on_a_record_count_mismatch(
    repo: Repo,
) -> None:
    """Fail CLOSED: a mis-aligned batch is an error, never a silent zip.

    This is the guard against the defect class itself rather than one spelling
    of it -- if a future git changes the batch protocol, the gate errors (exit
    2, CI red) instead of quietly reading the wrong file's size.
    """
    sys.path.insert(0, str(GUARD.parent))
    import check_skill_dual_write as guard  # noqa: PLC0415

    original = guard._run_git
    try:
        guard._run_git = lambda *a, **k: "one line only\n"  # type: ignore[assignment]
        try:
            guard.blob_sizes(str(repo.root), ["a" * 40, "b" * 40])
        except guard.GitError as exc:
            assert "refusing to guess" in str(exc)
        else:
            raise AssertionError("expected a GitError on a record-count mismatch")
    finally:
        guard._run_git = original  # type: ignore[assignment]


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


def test_strict_parity_fires_on_a_canonical_only_edit(repo: Repo) -> None:
    """KNOWN-BROKEN: strict mode used to build obligations from projection rows only."""
    repo.write(".agents/skills/existing-skill/SKILL.md", EDIT)
    repo.add(".agents/skills/existing-skill/SKILL.md")
    repo.commit("canonical edit without generated projection")

    proc = run_range(repo, "--strict-parity", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"existing-skill": "canonical-divergent"}


def test_strict_parity_accepts_a_projection_repair_to_unchanged_canonical(
    repo: Repo,
) -> None:
    """KNOWN-BROKEN: same-diff parity rejected repairs to an older canonical blob."""
    repo.git("checkout", "-q", "main")
    repo.write(".agents/skills/repair-me/SKILL.md", NEW_SKILL)
    repo.add(".agents/skills/repair-me/SKILL.md")
    repo.commit("canonical baseline")
    repo.git("branch", "-D", "feature")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("skills/repair-me/SKILL.md", NEW_SKILL)
    repo.add("skills/repair-me/SKILL.md")
    repo.commit("repair generated projection")

    proc = run_range(repo, "--strict-parity")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "final-tree counterparts" in proc.stdout


def test_strict_parity_fires_when_a_projection_is_deleted_but_canonical_survives(
    repo: Repo,
) -> None:
    """KNOWN-BROKEN: projection deletions were absent from the A/M obligation set."""
    repo.remove("skills/existing-skill/SKILL.md")
    repo.commit("delete generated projection only")

    proc = run_range(repo, "--strict-parity", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"existing-skill": "canonical-divergent"}


def test_strict_parity_allows_an_explicit_deletion_from_both_trees(repo: Repo) -> None:
    """KNOWN-BROKEN: old strict mode ignored, rather than adjudicated, deletions."""
    repo.remove("skills/existing-skill/SKILL.md")
    repo.remove(".agents/skills/existing-skill/SKILL.md")
    repo.commit("explicit dual removal")
    proc = run_range(repo, "--strict-parity")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "final-tree counterparts" in proc.stdout


def test_strict_parity_refuses_unpaired_projection_only_deletion(repo: Repo) -> None:
    """KNOWN-BROKEN: final absent==absent treated legacy pruning as parity."""
    repo.git("checkout", "-q", "main")
    repo.write("skills/legacy-only/SKILL.md", NEW_SKILL)
    repo.add("skills/legacy-only/SKILL.md")
    repo.commit("projection-only baseline")
    repo.git("branch", "-D", "feature")
    repo.git("checkout", "-q", "-b", "feature")
    repo.remove("skills/legacy-only/SKILL.md")
    repo.commit("attempt to prune legacy projection")

    proc = run_range(repo, "--strict-parity", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"legacy-only": "canonical-divergent"}


def test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct(
    repo: Repo,
) -> None:
    """KNOWN-BROKEN: errors=replace collapsed byte 0xff and 0xfe to one name."""
    projection_name = os.fsdecode(b"\xff")
    canonical_name = os.fsdecode(b"\xfe")
    projection_path = f"skills/{projection_name}/SKILL.md"
    canonical_path = f".agents/skills/{canonical_name}/SKILL.md"
    repo.write(projection_path, NEW_SKILL)
    repo.write(canonical_path, NEW_SKILL)
    repo.add(projection_path, canonical_path)
    repo.commit("distinct non-utf8 skill names")

    raw = subprocess.run(
        ["git", "-C", str(repo.root), "diff", "--name-only", "-z", "main...feature"],
        capture_output=True,
    )
    assert raw.returncode == 0
    assert b"\xff" in raw.stdout and b"\xfe" in raw.stdout, "fixture bytes collapsed"

    proc = run_range(repo, "--strict-parity", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert set(reasons(proc)) == {projection_name, canonical_name}


def test_staged_strict_parity_fires_on_a_canonical_only_edit(repo: Repo) -> None:
    """KNOWN-BROKEN: staged strict mode ignored canonical-only index changes."""
    repo.write(".agents/skills/existing-skill/SKILL.md", EDIT)
    repo.add(".agents/skills/existing-skill/SKILL.md")
    proc = run_guard(repo, "--staged", "--strict-parity", "--json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert reasons(proc) == {"existing-skill": "canonical-divergent"}


def test_staged_strict_parity_accepts_repair_to_head_canonical(repo: Repo) -> None:
    """KNOWN-BROKEN: same-diff strict mode rejected staged projection-only repairs."""
    repo.write(".agents/skills/repair-me/SKILL.md", NEW_SKILL)
    repo.add(".agents/skills/repair-me/SKILL.md")
    repo.commit("canonical baseline")
    repo.write("skills/repair-me/SKILL.md", NEW_SKILL)
    repo.add("skills/repair-me/SKILL.md")
    proc = run_guard(repo, "--staged", "--strict-parity")
    assert proc.returncode == 0, proc.stdout + proc.stderr
