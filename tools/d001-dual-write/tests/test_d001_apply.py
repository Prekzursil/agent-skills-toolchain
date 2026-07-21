"""Acceptance tests for the filter-safe D-001 applier.

D1 -- the hazard fires on the FIRST command of the old procedure, not the third.
      Creating a second worktree of a repository whose content filter has been
      neutralised writes the STORED bytes into the new working tree for every
      protected path.  Scoping a later per-file step therefore does not remove
      the hazard: the tree is already corrupt.  Every known-good assertion below
      is anchored AFTER that first command's equivalent, and asserts byte AND
      mtime identity of the protected file.

D6 -- ``git status`` is a false green in exactly that window.  With an identity
      filter installed, ``clean`` maps the stored bytes back to the same blob, so
      ``git status --porcelain`` reports a CLEAN tree over ciphertext.  The
      applier's detector inspects CONTENT with two independent signals instead.

No real credential file is read, written, moved or referenced anywhere in this
suite; see ``d001_fixtures`` for the synthetic payload.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from d001_fixtures import (
    MAGIC,
    MAGIC_HEX,
    PROTECTED,
    Fixture,
    signature,
    stat_dirty,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
APPLIER = REPO_ROOT / "tools" / "d001-dual-write" / "d001_apply.py"
README = REPO_ROOT / "tools" / "d001-dual-write" / "README.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skill-dual-write.yml"
GUARD = REPO_ROOT / "ci" / "check_skill_dual_write.py"


def run(fx: Fixture, *args: str) -> subprocess.CompletedProcess[str]:
    """Drive the applier as a real subprocess; read its own returncode."""
    return subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(fx.root),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def payload(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(proc.stdout)


def problems(proc: subprocess.CompletedProcess[str]) -> set[str]:
    data = payload(proc)
    findings = data.get("findings")
    if findings is None:
        pre = data.get("preflight", {})
        findings = pre.get("findings", []) if isinstance(pre, dict) else []
    return {str(f["problem"]) for f in findings}  # type: ignore[index]


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def run_traced(
    fx: Fixture, trace: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    """Drive the applier with GIT_TRACE pointed at ``trace``.

    ``GIT_TRACE=<absolute file>`` makes every git process append its real argv
    to that file.  That is an observation of BEHAVIOUR -- what the tool actually
    executed -- rather than of the source text, and it survives a mutant that
    creates a worktree and then tidies it away.
    """
    return subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(fx.root),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_TRACE": str(trace)},
    )


def traced_subcommands(trace: Path) -> list[str]:
    """Every git SUBCOMMAND that actually ran, read off the traced argv."""
    marker = "trace: built-in: git "
    subs: list[str] = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if marker in line:
            rest = line.split(marker, 1)[1].split()
            if rest:
                subs.append(rest[0].strip("'\""))
    return subs


# --------------------------------------------------------------------------
# D1 -- known-BROKEN: the hazard fires at the FIRST command
# --------------------------------------------------------------------------


def test_d1_known_broken_creating_a_worktree_alone_writes_stored_bytes(
    filtered: Fixture, tmp_path: Path
) -> None:
    filtered.neutralize()
    second = tmp_path / "second-worktree"
    filtered.git("worktree", "add", "-q", "--detach", str(second), "HEAD")

    landed = (second / PROTECTED).read_bytes()
    stored = filtered.stored_bytes()
    assert landed.startswith(MAGIC), "expected the stored form in the new worktree"
    assert hashlib.sha256(landed).hexdigest() == hashlib.sha256(stored).hexdigest()
    # ... and this is before any per-file materialisation step has been reached.


def test_d6_git_status_is_empty_over_that_ciphertext_worktree(
    filtered: Fixture, tmp_path: Path
) -> None:
    """The false green REPRODUCES: status measures nothing in this window."""
    filtered.neutralize()
    second = tmp_path / "second-worktree"
    filtered.git("worktree", "add", "-q", "--detach", str(second), "HEAD")
    status = subprocess.run(
        ["git", "-C", str(second), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert status.returncode == 0
    assert status.stdout == "", (
        f"expected a false-green clean tree, got {status.stdout!r}"
    )


def test_d6_preflight_flags_the_same_state_by_content_not_status(
    filtered: Fixture, tmp_path: Path
) -> None:
    filtered.neutralize()
    second = tmp_path / "second-worktree"
    filtered.git("worktree", "add", "-q", "--detach", str(second), "HEAD")

    proc = subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(second),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            "preflight",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    found = {str(f["problem"]) for f in payload(proc)["findings"]}  # type: ignore[index,union-attr]
    assert "filter-neutralized" in found
    assert "stored-form-in-worktree" in found


def test_d6_double_encryption_is_detected_by_content_not_by_status(
    filtered: Fixture, tmp_path: Path
) -> None:
    """Restoring the filter does NOT reliably make the corruption visible.

    ``git status`` consults the index stat cache.  If the corrupted file's
    (size, mtime) still matches its index entry, git never re-runs the clean
    filter and reports a CLEAN tree even though committing that file now would
    store a re-encrypted blob.  BOTH outcomes were observed on this box across
    two runs of the same fixture, so an assertion on ``git status`` here is
    racy -- which is exactly why the detector must not depend on it.  The value
    is recorded below and deliberately NOT asserted.
    """
    filtered.neutralize()
    second = tmp_path / "second-worktree"
    filtered.git("worktree", "add", "-q", "--detach", str(second), "HEAD")
    filtered.restore()  # shared config -> the linked worktree sees it too

    racy = subprocess.run(
        ["git", "-C", str(second), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert racy.returncode == 0  # recorded, not asserted on: see the docstring

    # Bypass the stat cache and git DOES see it -- so the corruption is real and
    # git-visible, it is only `status` that cannot be trusted to surface it.
    os.utime(second / PROTECTED, None)
    forced = subprocess.run(
        ["git", "-C", str(second), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert forced.stdout.strip().endswith(PROTECTED), forced.stdout

    would_stage = subprocess.run(
        ["git", "-C", str(second), "hash-object", "--path", PROTECTED, "--", PROTECTED],
        capture_output=True,
        text=True,
    ).stdout.strip()
    on_record = subprocess.run(
        ["git", "-C", str(second), "rev-parse", f"HEAD:{PROTECTED}"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert would_stage != on_record, "expected a double-encrypted staging result"

    proc = subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(second),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            "preflight",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    found = {str(f["problem"]) for f in payload(proc)["findings"]}  # type: ignore[index,union-attr]
    assert "double-encryption-risk" in found


def test_d6_negative_control_healthy_repository_preflight_is_ok(
    filtered: Fixture,
) -> None:
    """The detector must not simply fire on everything."""
    proc = run(filtered, "preflight")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert payload(proc)["ok"] is True


def test_sparse_skip_worktree_path_is_reported_not_flagged(
    filtered: Fixture,
) -> None:
    """A sparse checkout is a LEGITIMATE context; the detector must not fire on it.

    The path is absent from the worktree, but git itself marks it skip-worktree,
    so absence is expected rather than corruption.  It is counted and NAMED, not
    silently ignored.
    """
    filtered.git("update-index", "--skip-worktree", "--", PROTECTED)
    filtered.protected.unlink()
    proc = run(filtered, "preflight")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["sparse_skipped_count"] == 1
    assert data["sparse_skipped_paths"] == [PROTECTED]
    assert data["findings"] == []


def test_absent_path_without_the_skip_worktree_bit_still_fires(
    filtered: Fixture,
) -> None:
    """The exemption must not swallow a genuinely missing filtered path."""
    filtered.protected.unlink()
    proc = run(filtered, "preflight")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    found = {str(f["problem"]) for f in payload(proc)["findings"]}  # type: ignore[index,union-attr]
    assert found == {"not-materialized"}
    assert payload(proc)["sparse_skipped_count"] == 0


def test_preflight_is_byte_inert(filtered: Fixture) -> None:
    before = tree_hash(filtered.root)
    assert run(filtered, "preflight").returncode == 0
    assert tree_hash(filtered.root) == before


# --------------------------------------------------------------------------
# D1 -- known-GOOD: the repaired procedure never materialises anything
# --------------------------------------------------------------------------


def test_d1_known_good_mirror_leaves_protected_bytes_and_mtime_identical(
    filtered: Fixture,
) -> None:
    before = signature(filtered.protected)
    worktrees_before = filtered.git("worktree", "list")

    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-mirror",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    assert signature(filtered.protected) == before, "protected file was touched"
    assert filtered.git("worktree", "list") == worktrees_before
    assert filtered.git("status", "--porcelain") == ""

    data = payload(proc)
    verification = data["verification"]
    assert verification["scope_exact"] is True  # type: ignore[index]
    assert verification["additive_only"] is True  # type: ignore[index]
    assert verification["all_blobs_identical"] is True  # type: ignore[index]
    assert verification["changed_paths"] == [  # type: ignore[index]
        ".agents/skills/beta/SKILL.md"
    ]

    left = filtered.git("rev-parse", "HEAD:skills/beta/SKILL.md").strip()
    right = filtered.git(
        "rev-parse", "fix/d001-mirror:.agents/skills/beta/SKILL.md"
    ).strip()
    assert left == right


def test_d1_mirror_dry_run_writes_nothing(filtered: Fixture) -> None:
    before = tree_hash(filtered.root)
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-mirror",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert payload(proc)["decision"] == "dry-run"
    assert tree_hash(filtered.root) == before
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "rev-parse",
            "--verify",
            "--quiet",
            "refs/heads/fix/d001-mirror",
        ],
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0


# --------------------------------------------------------------------------
# D1 -- prevention: the unsafe operation is stopped BEFORE any mutation
# --------------------------------------------------------------------------


def test_d1_prevention_broad_materialization_is_refused(filtered: Fixture) -> None:
    before = signature(filtered.protected)
    proc = run(filtered, "materialize", "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "broad-materialization-refused"
    assert "named explicitly" in str(data["message"])
    assert signature(filtered.protected) == before


def test_d1_prevention_filtered_path_materialization_is_refused(
    filtered: Fixture,
) -> None:
    before = signature(filtered.protected)
    proc = run(filtered, "materialize", "--path", PROTECTED, "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "filtered-path-refused"
    assert signature(filtered.protected) == before


PATHSPECS = (":/", "*", ":(glob)**", "secrets", "secrets/")


def test_d1_known_broken_a_pathspec_argument_materializes_the_whole_index(
    filtered: Fixture,
) -> None:
    """The hazard the pathspec gate exists to stop, anchored on real git.

    ``git checkout -- :/`` is what the previous revision handed to git once its
    three checks passed: ``:/`` is git's pathspec for the repository ROOT, and
    none of ``:/``, ``*`` or a bare directory name IS a protected file name, so
    an exact-membership test against the argument never engaged.

    The filter here is an identity passthrough spelled outside the applier's
    known-identity set, so the config audit cannot see it either.  The protected
    file is left in place holding plaintext and merely made stat-dirty, because
    git skips paths whose stat data still matches the index.
    """
    filtered.neutralize_unnamed()
    stat_dirty(filtered.protected)
    before = signature(filtered.protected)

    filtered.git("checkout", "--", ":/")

    landed = filtered.protected.read_bytes()
    assert landed.startswith(MAGIC), "expected the stored form to land"
    assert (
        hashlib.sha256(landed).hexdigest()
        == hashlib.sha256(filtered.stored_bytes()).hexdigest()
    )
    assert signature(filtered.protected) != before


def test_d1_prevention_pathspec_gate_is_the_load_bearing_one(
    filtered: Fixture,
) -> None:
    """Decompose WHICH gate refuses -- "it was refused" is not an answer.

    Both other gates report this repository healthy, so a refusal below can only
    come from the pathspec gate.  Without this arm a green could be an accident
    of the config audit firing for an unrelated reason.
    """
    filtered.neutralize_unnamed()
    stat_dirty(filtered.protected)
    proc = run(filtered, "preflight")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["ok"] is True
    assert data["findings"] == []


def test_d1_prevention_pathspec_materialization_is_refused_before_any_write(
    filtered: Fixture,
) -> None:
    """Every broad pathspec is REFUSED, and nothing is written.

    Byte AND mtime identity, which is the standard the known-good mirror run is
    held to -- a restore that merely rewrites identical content still churns the
    mtime of every protected file it touches.
    """
    filtered.neutralize_unnamed()
    stat_dirty(filtered.protected)
    before = signature(filtered.protected)

    for spec in PATHSPECS:
        proc = run(filtered, "materialize", "--path", spec, "--apply")
        assert proc.returncode == 7, f"{spec}: {proc.stdout}{proc.stderr}"
        data = payload(proc)
        assert data["reason"] == "pathspec-refused", spec
        assert "literal tracked file path" in str(data["message"])
        assert signature(filtered.protected) == before, (
            f"{spec} wrote to a protected path"
        )
        assert not filtered.protected.read_bytes().startswith(MAGIC)


def test_d1_prevention_pathspec_refusal_names_the_protected_paths_it_covers(
    filtered: Fixture,
) -> None:
    """The refusal must be actionable, not merely non-zero."""
    proc = run(filtered, "materialize", "--path", ":/", "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["not_a_literal_tracked_file"] == [":/"]
    assert data["protected_in_expansion"] == [PROTECTED]
    assert int(str(data["would_have_covered_count"])) > 1


def test_d1_prevention_untracked_path_is_refused_not_passed_to_git(
    filtered: Fixture,
) -> None:
    proc = run(filtered, "materialize", "--path", "no/such/file.md", "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "pathspec-refused"
    assert data["not_tracked"] == ["no/such/file.md"]


def test_d1_negative_control_narrow_restore_survives_the_pathspec_gate(
    filtered: Fixture,
) -> None:
    """The gate must not fire on the legitimate operation it exists to permit."""
    filtered.neutralize_unnamed()
    protected_before = signature(filtered.protected)
    target = filtered.root / "skills" / "alpha" / "SKILL.md"
    original = target.read_bytes()
    target.unlink()

    proc = run(filtered, "materialize", "--path", "skills/alpha/SKILL.md", "--apply")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert target.read_bytes() == original
    assert signature(filtered.protected) == protected_before


def test_d1_prevention_materialize_refused_when_the_worktree_holds_stored_bytes(
    filtered: Fixture,
) -> None:
    """The CONTENT detector now guards the one command that writes.

    ``audit_filters`` is a config-level check; it cannot see an identity filter
    spelled as a script.  The two-signal content detector can, once the stored
    form is on disk -- and it used to be consulted only by ``preflight``.
    """
    filtered.neutralize_unnamed()
    filtered.protected.write_bytes(filtered.stored_bytes())
    before = signature(filtered.protected)

    proc = run(filtered, "materialize", "--path", "skills/alpha/SKILL.md", "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "worktree-content-unsafe"
    assert "stored-form-in-worktree" in {
        str(f["problem"])  # type: ignore[index]
        for f in data["findings"]  # type: ignore[union-attr]
    }
    assert signature(filtered.protected) == before


def test_d1_prevention_materialize_refused_while_filters_are_neutralized(
    filtered: Fixture,
) -> None:
    filtered.neutralize()
    target = filtered.root / "skills" / "alpha" / "SKILL.md"
    before = signature(filtered.protected)
    target.unlink()
    proc = run(filtered, "materialize", "--path", "skills/alpha/SKILL.md", "--apply")
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "filter-config-unsafe"
    assert not target.exists(), "nothing should have been restored"
    assert signature(filtered.protected) == before


def test_d1_prevention_mirror_refused_while_filters_are_neutralized(
    filtered: Fixture,
) -> None:
    filtered.neutralize()
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-mirror",
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "preflight-unsafe"
    assert "filter-neutralized" in problems(proc)
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "rev-parse",
            "--verify",
            "--quiet",
            "refs/heads/fix/d001-mirror",
        ],
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0, "no ref may be created by a refused run"


def test_d1_mirror_refuses_to_move_an_existing_branch(filtered: Fixture) -> None:
    filtered.git("branch", "fix/d001-mirror")
    before = filtered.git("rev-parse", "fix/d001-mirror").strip()
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-mirror",
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "branch-exists"
    assert filtered.git("rev-parse", "fix/d001-mirror").strip() == before


# --------------------------------------------------------------------------
# D1 -- negative control: a legitimate narrow operation must still SUCCEED
# --------------------------------------------------------------------------


def test_d1_negative_control_narrow_legitimate_materialize_succeeds(
    filtered: Fixture,
) -> None:
    target = filtered.root / "skills" / "alpha" / "SKILL.md"
    protected_before = signature(filtered.protected)
    original = target.read_bytes()
    target.unlink()

    proc = run(filtered, "materialize", "--path", "skills/alpha/SKILL.md", "--apply")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert target.read_bytes() == original
    assert signature(filtered.protected) == protected_before


def test_materialize_rejects_an_absolute_path(filtered: Fixture) -> None:
    proc = run(filtered, "materialize", "--path", str(filtered.protected), "--apply")
    assert proc.returncode == 2, proc.stdout + proc.stderr


# --------------------------------------------------------------------------
# D1 -- the shipped instructions must not carry the hazard at all
# --------------------------------------------------------------------------


def test_d1_shipped_instructions_do_not_NAME_the_broad_commands() -> None:
    """A DOCUMENTATION check, and named as one.

    This asserts only that the shipped prose does not tell a reader to run the
    hazardous commands.  It is a substring scan over source text, so it proves
    nothing about behaviour: the applier calls git with an ARGUMENT LIST, in
    which the substring "worktree add" never appears.  The behavioural property
    is pinned by ``test_d1_known_good_mirror_runs_no_materializing_git_command``.
    """
    banned = ("checkout-index", "worktree add", "checkout -f -a")
    for path in (README, APPLIER, WORKFLOW, GUARD):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} still names {token!r}"


# Subcommands that materialise files through the smudge filter.  `mirror` is
# pure plumbing against a temporary index and must invoke NONE of them.
MATERIALIZING = frozenset(
    {
        "worktree",
        "checkout",
        "checkout-index",
        "restore",
        "reset",
        "stash",
        "clone",
        "switch",
    }
)


def test_d1_known_good_mirror_runs_no_materializing_git_command(
    filtered: Fixture, tmp_path: Path
) -> None:
    """Observe BEHAVIOUR: no materialising git command is executed at all.

    The previous revision pinned this property with a substring grep over the
    source, which any different spelling defeats -- a mutant that creates a
    second worktree through ``run_git(repo, ["worktree", "add", ...])`` and then
    removes it left the suite fully green while reintroducing the original D1
    defect verbatim.  ``git worktree remove`` deletes ``.git/worktrees``
    entirely (measured), so an artefact check cannot see it either.

    GIT_TRACE records the real argv of every git process the applier spawns.
    The observer is calibrated INSIDE the assertion: it must SEE the plumbing
    the mirror really does use, otherwise its silence about ``worktree`` would
    measure nothing at all.
    """
    trace = tmp_path / "git-trace.log"
    before = signature(filtered.protected)

    proc = run_traced(
        filtered,
        trace,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-mirror",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    subs = traced_subcommands(trace)
    # Detector calibration: the observer speaks.
    assert {"read-tree", "write-tree", "commit-tree", "update-ref"} <= set(subs), (
        f"GIT_TRACE saw nothing recognisable; observer is blind: {subs}"
    )
    # The property itself.
    assert not (MATERIALIZING & set(subs)), (
        f"mirror executed a materialising git command: {sorted(MATERIALIZING & set(subs))}"
    )
    # Two further independent signals on the same property.
    assert not (filtered.root / ".git" / "worktrees").exists()
    assert signature(filtered.protected) == before


def test_readme_documents_the_repaired_ordered_procedure() -> None:
    text = README.read_text(encoding="utf-8")
    for marker in ("preflight", "mirror", "--apply", "check_skill_dual_write.py"):
        assert marker in text
