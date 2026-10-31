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
import shutil
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


def test_mirror_refuses_to_clobber_divergent_canonical_content(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: mirror used to replace canonical alpha with its projection."""
    canonical_before = filtered.git(
        "rev-parse", "HEAD:.agents/skills/alpha/SKILL.md"
    ).strip()
    projection = filtered.git("rev-parse", "HEAD:skills/alpha/SKILL.md").strip()
    assert canonical_before != projection, "fixture must exercise the conflict"

    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-conflict",
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "canonical-conflict-route-required"
    assert data["conflicts"] == [
        {
            "destination": ".agents/skills/alpha/SKILL.md",
            "destination_mode": "100644",
            "destination_oid": canonical_before,
            "source": "skills/alpha/SKILL.md",
            "source_mode": "100644",
            "source_oid": projection,
        }
    ]
    assert filtered.git("rev-parse", "HEAD:.agents/skills/alpha/SKILL.md").strip() == (
        canonical_before
    )
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "rev-parse",
            "--verify",
            "--quiet",
            "refs/heads/fix/d001-conflict",
        ],
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0, "a refused conflict must not create a ref"


def test_project_requires_a_reviewed_plan_digest_before_overwrite(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: no canonical-to-projection operation existed at all."""
    dry = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-refused",
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    dry_data = payload(dry)
    assert dry_data["decision"] == "dry-run"
    assert len(str(dry_data["plan_digest"])) == 64
    overwrite = dry_data["overwrites"][0]  # type: ignore[index]
    assert overwrite == {
        "destination": "skills/alpha/SKILL.md",
        "destination_mode": "100644",
        "destination_oid": filtered.git(
            "rev-parse", "HEAD:skills/alpha/SKILL.md"
        ).strip(),
        "source": ".agents/skills/alpha/SKILL.md",
        "source_mode": "100644",
        "source_oid": filtered.git(
            "rev-parse", "HEAD:.agents/skills/alpha/SKILL.md"
        ).strip(),
    }

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-refused",
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "projection-plan-not-reviewed"
    assert data["overwritten_paths"] == ["skills/alpha/SKILL.md"]


def test_project_rejects_a_stale_plan_digest_after_source_ref_moves(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: a boolean acknowledgement did not bind the reviewed plan."""
    dry = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-stale",
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    reviewed = payload(dry)
    digest = str(reviewed["plan_digest"])
    assert reviewed["overwritten_paths"] == ["skills/alpha/SKILL.md"]

    canonical_new = filtered.root / ".agents" / "skills" / "alpha" / "new.md"
    projection_new = filtered.root / "skills" / "alpha" / "new.md"
    canonical_new.write_text("canonical new\n", encoding="utf-8", newline="\n")
    projection_new.write_text("unreviewed projection\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", ".agents/skills/alpha/new.md", "skills/alpha/new.md")
    filtered.git("commit", "-q", "-m", "move mutable source ref")

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-stale",
        "--plan-digest",
        digest,
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "projection-plan-not-reviewed"
    assert data["plan_digest"] != digest
    assert data["overwritten_paths"] == [
        "skills/alpha/SKILL.md",
        "skills/alpha/new.md",
    ]


def test_project_refuses_a_nonregular_canonical_source(filtered: Fixture) -> None:
    """KNOWN-BROKEN: project copied a canonical symlink that strict CI rejects."""
    target = subprocess.run(
        ["git", "-C", str(filtered.root), "hash-object", "-w", "--stdin"],
        input=b"../../../outside",
        capture_output=True,
    )
    assert target.returncode == 0, target.stderr
    oid = target.stdout.decode().strip()
    filtered.git(
        "update-index",
        "--add",
        "--cacheinfo",
        f"120000,{oid},.agents/skills/link-skill/SKILL.md",
    )
    filtered.git("commit", "-q", "-m", "canonical symlink")

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "link-skill",
        "--branch",
        "fix/d001-link",
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "nonregular-source-refused"
    assert data["nonregular_source_entries"] == [
        {
            "mode": "120000",
            "path": ".agents/skills/link-skill/SKILL.md",
            "type": "blob",
        }
    ]


def test_duplicate_skill_arguments_are_stably_deduplicated(filtered: Fixture) -> None:
    """KNOWN-BROKEN: duplicate plan rows made verification refuse a valid mirror."""
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--skill",
        "beta",
        "--branch",
        "fix/d001-duplicate",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert payload(proc)["verification"]["changed_paths"] == [  # type: ignore[index]
        ".agents/skills/beta/SKILL.md"
    ]


def test_skill_argument_cannot_be_a_pathspec(filtered: Fixture) -> None:
    """KNOWN-BROKEN: wildcard skill input reached git's pathspec parser."""
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "*",
        "--branch",
        "fix/d001-wildcard",
        "--apply",
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "one lower-case hyphen/underscore directory name" in proc.stderr


def test_branch_name_cannot_inject_the_update_ref_protocol(filtered: Fixture) -> None:
    """KNOWN-BROKEN: branch text had no structured pre-write validation."""
    branch = "fix/d001-safe\ncommit refs/heads/d001-injected deadbeef"
    assert "\n" in branch, "fixture must contain a protocol delimiter"
    proc = run(
        filtered,
        "mirror",
        "--source-ref",
        "HEAD",
        "--skill",
        "beta",
        "--branch",
        branch,
        "--apply",
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "invalid-branch-name"
    injected = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/d001-injected",
        ],
        capture_output=True,
    )
    assert injected.returncode != 0


def test_project_routes_a_legacy_underscore_skill_name(filtered: Fixture) -> None:
    """KNOWN-BROKEN: no projector could route a legacy underscore-named skill."""
    canonical = filtered.root / ".agents" / "skills" / "legacy_skill" / "SKILL.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# legacy\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", ".agents/skills/legacy_skill/SKILL.md")
    filtered.git("commit", "-q", "-m", "legacy underscore skill")

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "legacy_skill",
        "--branch",
        "fix/d001-legacy-underscore",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (
        filtered.git(
            "rev-parse", "fix/d001-legacy-underscore:skills/legacy_skill/SKILL.md"
        ).strip()
        == filtered.git(
            "rev-parse", "HEAD:.agents/skills/legacy_skill/SKILL.md"
        ).strip()
    )


def test_project_keeps_distinct_invalid_utf8_path_bytes(filtered: Fixture) -> None:
    """KNOWN-BROKEN: errors=replace collapsed distinct canonical path bytes."""
    skill = "byte-skill"
    raw_leaf = os.fsdecode(b"\xff.md")
    replacement_leaf = "\ufffd.md"
    raw_source = f".agents/skills/{skill}/{raw_leaf}"
    replacement_source = f".agents/skills/{skill}/{replacement_leaf}"
    for rel in (raw_source, replacement_source):
        path = filtered.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("same blob\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", raw_source, replacement_source)
    filtered.git("commit", "-q", "-m", "distinct raw canonical paths")

    source_listing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            "HEAD",
            "--",
            f".agents/skills/{skill}/",
        ],
        capture_output=True,
    )
    assert source_listing.returncode == 0, source_listing.stderr
    assert os.fsencode(raw_source) in source_listing.stdout
    assert replacement_source.encode() in source_listing.stdout
    assert os.fsencode(raw_source) != replacement_source.encode(), (
        "fixture path bytes collapsed"
    )

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        skill,
        "--branch",
        "fix/d001-byte-paths",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    projection_listing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            "fix/d001-byte-paths",
            "--",
            f"skills/{skill}/",
        ],
        capture_output=True,
    )
    assert projection_listing.returncode == 0, projection_listing.stderr
    paths = set(projection_listing.stdout.rstrip(b"\0").split(b"\0"))
    assert paths == {
        os.fsencode(f"skills/{skill}/{raw_leaf}"),
        f"skills/{skill}/{replacement_leaf}".encode(),
    }


def test_project_replaces_a_projection_symlink_with_a_regular_file(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: verification rejected the planned safe typechange status."""
    canonical = filtered.root / ".agents" / "skills" / "type-skill" / "SKILL.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# regular\n", encoding="utf-8", newline="\n")
    target = subprocess.run(
        ["git", "-C", str(filtered.root), "hash-object", "-w", "--stdin"],
        input=b"../../../outside",
        capture_output=True,
    )
    assert target.returncode == 0, target.stderr
    oid = target.stdout.decode().strip()
    filtered.git("add", "--", ".agents/skills/type-skill/SKILL.md")
    filtered.git(
        "update-index",
        "--add",
        "--cacheinfo",
        f"120000,{oid},skills/type-skill/SKILL.md",
    )
    filtered.git("commit", "-q", "-m", "regular canonical over projection symlink")

    dry = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "type-skill",
        "--branch",
        "fix/d001-typechange",
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    report = payload(dry)
    overwrite = report["overwrites"][0]  # type: ignore[index]
    assert (overwrite["destination_mode"], overwrite["source_mode"]) == (
        "120000",
        "100644",
    )

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "type-skill",
        "--branch",
        "fix/d001-typechange",
        "--plan-digest",
        str(report["plan_digest"]),
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    verification = payload(proc)["verification"]
    assert verification["statuses"] == ["T"]  # type: ignore[index]
    assert verification["additive_only"] is True  # type: ignore[index]
    mode = filtered.git(
        "ls-tree", "fix/d001-typechange", "--", "skills/type-skill/SKILL.md"
    ).split()[0]
    assert mode == "100644"


def test_verifier_refuses_an_executable_mode_regression(
    filtered: Fixture, tmp_path: Path
) -> None:
    """KNOWN-BROKEN: post-build verification compared OIDs but ignored modes."""
    rel = ".agents/skills/executable-skill/tool.sh"
    canonical = filtered.root / rel
    canonical.parent.mkdir(parents=True)
    canonical.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    canonical.chmod(0o755)
    filtered.git("add", "--", rel)
    filtered.git("commit", "-q", "-m", "canonical executable skill")
    source_entry = filtered.git("ls-tree", "HEAD", "--", rel)
    assert source_entry.startswith("100755 blob "), "fixture lost executable mode"

    real_git = shutil.which("git")
    assert real_git is not None
    wrapper_dir = tmp_path / "mode-wrapper"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    wrapper.write_text(
        f"""#!{sys.executable}
import os
import sys

real = os.environ["D001_REAL_GIT"]
args = sys.argv[1:]
if "update-index" in args and "--cacheinfo" in args:
    index = args.index("--cacheinfo") + 1
    entry = args[index]
    if entry.startswith("100755,") and entry.endswith(",skills/executable-skill/tool.sh"):
        args[index] = "100644," + entry.removeprefix("100755,")
os.execv(real, [real, *args])
""",
        encoding="utf-8",
        newline="\n",
    )
    wrapper.chmod(0o755)

    proc = subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(filtered.root),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            "project",
            "--source-ref",
            "HEAD",
            "--skill",
            "executable-skill",
            "--branch",
            "fix/d001-mode-regression",
            "--apply",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PATH": f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "D001_REAL_GIT": real_git,
        },
    )
    assert proc.returncode == 7, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["reason"] == "verification-failed"
    verification = data["verification"]
    assert verification["all_blobs_identical"] is True  # type: ignore[index]
    assert verification["all_modes_identical"] is False  # type: ignore[index]
    pair = verification["blob_pairs"][0]  # type: ignore[index]
    assert (pair["source_mode"], pair["destination_mode"]) == ("100755", "100644")
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/fix/d001-mode-regression",
        ],
        capture_output=True,
    )
    assert missing.returncode != 0


def test_project_generates_from_canonical_and_preserves_projection_union(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: the only overlay ran in the authority-clobbering direction."""
    legacy = filtered.root / "skills" / "alpha" / "projection-only.md"
    legacy.write_text("route me later\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", "skills/alpha/projection-only.md")
    filtered.git("commit", "-q", "-m", "add projection routing debt")

    protected_before = signature(filtered.protected)
    canonical = filtered.git("rev-parse", "HEAD:.agents/skills/alpha/SKILL.md").strip()
    beta = filtered.git("rev-parse", "HEAD:skills/beta/SKILL.md").strip()
    legacy_oid = filtered.git(
        "rev-parse", "HEAD:skills/alpha/projection-only.md"
    ).strip()

    dry = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project",
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    digest = str(payload(dry)["plan_digest"])

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project",
        "--plan-digest",
        digest,
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = payload(proc)
    assert data["preserved_paths"] == ["skills/alpha/projection-only.md"]
    assert data["overwritten_paths"] == ["skills/alpha/SKILL.md"]
    verification = data["verification"]
    assert verification["changed_paths"] == ["skills/alpha/SKILL.md"]  # type: ignore[index]
    assert verification["statuses"] == ["M"]  # type: ignore[index]
    assert verification["scope_exact"] is True  # type: ignore[index]
    assert verification["additive_only"] is True  # type: ignore[index]
    assert verification["all_blobs_identical"] is True  # type: ignore[index]

    assert (
        filtered.git("rev-parse", "fix/d001-project:skills/alpha/SKILL.md").strip()
        == canonical
    )
    assert (
        filtered.git(
            "rev-parse", "fix/d001-project:.agents/skills/alpha/SKILL.md"
        ).strip()
        == canonical
    )
    assert filtered.git(
        "rev-parse", "fix/d001-project:skills/beta/SKILL.md"
    ).strip() == (beta)
    assert (
        filtered.git(
            "rev-parse", "fix/d001-project:skills/alpha/projection-only.md"
        ).strip()
        == legacy_oid
    )
    assert signature(filtered.protected) == protected_before


def test_project_adds_a_missing_projection_without_overwrite_ack(
    filtered: Fixture,
) -> None:
    """KNOWN-BROKEN: canonical-only skills had no projection operation."""
    canonical = filtered.root / ".agents" / "skills" / "gamma" / "SKILL.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# gamma\n\ncanonical only\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", ".agents/skills/gamma/SKILL.md")
    filtered.git("commit", "-q", "-m", "add canonical-only gamma")

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "gamma",
        "--branch",
        "fix/d001-project-gamma",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    left = filtered.git("rev-parse", "HEAD:.agents/skills/gamma/SKILL.md").strip()
    right = filtered.git(
        "rev-parse", "fix/d001-project-gamma:skills/gamma/SKILL.md"
    ).strip()
    assert left == right
    assert payload(proc)["overwritten_paths"] == []


def test_project_noop_does_not_create_an_empty_branch(filtered: Fixture) -> None:
    """KNOWN-BROKEN: no project command could report an inert generation run."""
    canonical = (filtered.root / ".agents" / "skills" / "alpha" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    projection = filtered.root / "skills" / "alpha" / "SKILL.md"
    projection.write_text(canonical, encoding="utf-8", newline="\n")
    filtered.git("add", "--", "skills/alpha/SKILL.md")
    filtered.git("commit", "-q", "-m", "reconcile alpha")

    proc = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-noop",
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert payload(proc)["decision"] == "no-op"
    missing = subprocess.run(
        [
            "git",
            "-C",
            str(filtered.root),
            "rev-parse",
            "--verify",
            "--quiet",
            "refs/heads/fix/d001-project-noop",
        ],
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0


def test_atomic_ref_create_refuses_a_branch_created_after_precheck(
    filtered: Fixture, tmp_path: Path
) -> None:
    """KNOWN-BROKEN: no atomic create gate protected a raced dangling symref."""
    canonical = filtered.root / ".agents" / "skills" / "gamma" / "SKILL.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# gamma\n\ncanonical only\n", encoding="utf-8", newline="\n")
    filtered.git("add", "--", ".agents/skills/gamma/SKILL.md")
    filtered.git("commit", "-q", "-m", "add gamma for ref race")
    main_before = filtered.git("rev-parse", "refs/heads/main").strip()

    real_git = shutil.which("git")
    assert real_git is not None
    wrapper_dir = tmp_path / "git-wrapper"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    marker = tmp_path / "race-injected"
    target_ref = "refs/heads/fix/d001-race"
    dangling_target = "refs/heads/d001-missing"
    wrapper.write_text(
        f"""#!{sys.executable}
import os
from pathlib import Path
import subprocess
import sys

real = os.environ["D001_REAL_GIT"]
args = sys.argv[1:]
target = os.environ["D001_RACE_REF"]
if "update-ref" in args:
    repo = args[args.index("-C") + 1]
    Path(os.environ["D001_RACE_MARKER"]).write_text("injected\\n", encoding="utf-8")
    subprocess.run(
        [real, "-C", repo, "symbolic-ref", target, os.environ["D001_DANGLING_TARGET"]],
        check=True,
    )
os.execv(real, [real, *args])
""",
        encoding="utf-8",
        newline="\n",
    )
    wrapper.chmod(0o755)

    proc = subprocess.run(
        [
            sys.executable,
            str(APPLIER),
            "--repo",
            str(filtered.root),
            "--json",
            "--magic-hex",
            MAGIC_HEX,
            "project",
            "--source-ref",
            "HEAD",
            "--skill",
            "gamma",
            "--branch",
            "fix/d001-race",
            "--apply",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PATH": f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "D001_REAL_GIT": real_git,
            "D001_RACE_REF": target_ref,
            "D001_RACE_MARKER": str(marker),
            "D001_DANGLING_TARGET": dangling_target,
        },
    )
    assert marker.is_file(), "race injector never observed update-ref"
    assert proc.returncode == 7, proc.stdout + proc.stderr
    assert payload(proc)["reason"] == "branch-create-conflict"
    assert filtered.git("symbolic-ref", target_ref).strip() == dangling_target
    assert filtered.git("rev-parse", "refs/heads/main").strip() == main_before


def test_project_runs_no_materializing_git_command(
    filtered: Fixture, tmp_path: Path
) -> None:
    """KNOWN-BROKEN: no forward projector existed to satisfy this safety contract."""
    dry = run(
        filtered,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-traced",
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    digest = str(payload(dry)["plan_digest"])
    trace = tmp_path / "project-git-trace.log"
    before = signature(filtered.protected)

    proc = run_traced(
        filtered,
        trace,
        "project",
        "--source-ref",
        "HEAD",
        "--skill",
        "alpha",
        "--branch",
        "fix/d001-project-traced",
        "--plan-digest",
        digest,
        "--apply",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    subs = traced_subcommands(trace)
    assert {"read-tree", "write-tree", "commit-tree", "update-ref"} <= set(subs), (
        f"GIT_TRACE saw nothing recognisable; observer is blind: {subs}"
    )
    assert not (MATERIALIZING & set(subs)), (
        f"project executed a materialising git command: {sorted(MATERIALIZING & set(subs))}"
    )
    assert not (filtered.root / ".git" / "worktrees").exists()
    assert signature(filtered.protected) == before
