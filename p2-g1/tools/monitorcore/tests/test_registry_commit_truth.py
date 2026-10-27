"""The cockpit must be launchable from the COMMIT, not merely from this working tree.

Why this module exists, and why ``test_registry_shipped.py`` did not make it redundant.

``test_registry_shipped.py`` grades the artifact rather than a fixture, which was the right
fix for its own defect -- but every assertion in it reads the WINDOWS WORKING TREE
(``Path.read_bytes`` / ``Path.is_file``). CI checks out the COMMIT. Those two are not the
same tree, and the divergence is not hypothetical: commit ``3bdcaf56`` in this repo is
titled *"worktree was green, the COMMIT was not"* -- one registry mirror had been committed
and the other was still only an uncommitted working-tree edit, so every worktree assertion
passed on the authoring box while a fresh clone would have materialised two different
registries.

That is the same class as the whole-program lesson (working-tree green != clone green) and
the same class as ``rules/common/windows-shell.md`` section 8b (a local formatter green
measured against CRLF bytes CI never sees).

So this module re-asks the two reachability questions of the COMMITTED TREE:

* are the two committed registry mirrors the same registry?
* does every stanza's entry script exist as a TRACKED path -- i.e. would a fresh clone
  actually have the file that ``mon <name>`` is about to run?

SCOPE, stated because the honest scope is narrower than the sentence wants to be: as of
2026-08-12 both questions already answer YES at HEAD (measured: both blobs 3,874 B, raw
identical, 0 CRLF; 12 of 12 stanza entry paths present in ``git ls-tree -r HEAD``). This is
therefore a LATENT-hole closure, not a live-defect fix -- it converts a failure that was
previously visible only to a human reading a diff into one the suite reports. The settling
experiment for the claim that it works is the both-states control below, which builds a
throwaway object database whose COMMITTED tree diverges while the working tree agrees, and
requires the blob check to fire where the worktree check stays silent.

Fail-closed by design (``rules/common/ci-hygiene.md`` section 1). A missing ``git``, an
unreadable revision or an empty tree listing raises rather than skipping: a gate that
no-ops when its instrument is absent is indistinguishable from no gate, and reporting that
silence as a pass is the exact defect this directory exists to prevent.

Deliberately NOT mtime-based. File timestamps cannot distinguish a stalled writer from a
long-finished one; they support exactly one honest signal ("N files written in the last T
seconds = currently active"), which is not a question this module asks. Everything here is
content-addressed: blob bytes and tree membership.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

from monitorcore import monitors as m

#: tests/ -> monitorcore/ -> tools/ -> repo root
REPO = Path(__file__).resolve().parents[3]

#: Repo-relative POSIX paths of the two committed registry mirrors. Kept as strings
#: (not Path) because these are git pathspecs: a Windows backslash path is not a valid
#: one, and forward slashes work on every platform.
REGISTRY_RELS: tuple[str, ...] = (
    "skills/monitor-launcher/monitors.toml",
    ".agents/skills/monitor-launcher/monitors.toml",
)

CRLF = b"\r\n"
LF = b"\n"


class GitProbeError(RuntimeError):
    """The instrument could not run. Never downgraded to a skip."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run git in ``repo``, resolving the executable explicitly.

    ``shutil.which`` rather than a bare ``"git"`` so that an absent git is a NAMED
    failure instead of a ``FileNotFoundError`` from deep inside subprocess, and so the
    absence can be simulated in a control.
    """
    exe = shutil.which("git")
    if exe is None:
        raise GitProbeError(
            "git is not on PATH, so the committed tree cannot be read. Failing closed: "
            "this check measures the COMMIT and has no worktree fallback by design."
        )
    return subprocess.run(
        [exe, "-C", str(repo), *args], capture_output=True, check=False
    )


def committed_blob(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    """The stored bytes of ``rel`` at ``rev`` -- what a fresh clone materialises.

    ``git cat-file -p`` applies no EOL conversion on any platform. ``git archive`` does
    (measured on this box: it hands back the CRLF working-tree form), which is why it is
    not used here. ``git show <rev>:<path>`` is equivalent to cat-file and would also be
    correct; cat-file is used because it is the narrower, plumbing-level command.
    """
    proc = _git(repo, "cat-file", "-p", f"{rev}:{rel}")
    if proc.returncode != 0:
        raise GitProbeError(
            f"{rel!r} is not readable at {rev!r}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    return proc.stdout


@functools.cache
def tracked_paths(repo: Path, rev: str = "HEAD") -> frozenset[str]:
    """Every path present in the committed tree at ``rev``.

    Memoised per ``(repo, rev)``: a tree listing is content-addressed, so within one run
    the answer cannot change, and ``ls-tree -r`` over this repo's 10,034 paths is the
    slowest call in the module. Exceptions are not memoised, so a fail-closed raise stays
    a raise on every call.

    An empty listing is treated as an instrument failure, not as "nothing is tracked":
    an empty walk that returns a pass is the fail-open shape ci-hygiene section 1 bans.
    """
    proc = _git(repo, "ls-tree", "-r", "--name-only", rev)
    if proc.returncode != 0:
        raise GitProbeError(
            f"cannot list the tree at {rev!r}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:200]}"
        )
    names = frozenset(line for line in proc.stdout.decode("utf-8").splitlines() if line)
    if not names:
        raise GitProbeError(
            f"the tree at {rev!r} listed zero paths -- failing closed rather than "
            "reporting every entry as untracked or as present"
        )
    return names


def mirror_divergence(
    repo: Path, rels: Sequence[str], rev: str = "HEAD"
) -> tuple[str, str] | None:
    """``None`` when the mirrors are byte-identical in the commit, else (class, detail).

    The class is reported separately for line-endings and for content because the two
    have different remedies and conflating them is how a CRLF phantom gets mistaken for
    a real divergence (and vice versa).
    """
    if len(rels) < 2:
        raise GitProbeError(
            f"mirror comparison needs at least two paths, got {list(rels)!r}"
        )
    bodies = {rel: committed_blob(repo, rel, rev) for rel in rels}
    raw = {v for v in bodies.values()}
    if len(raw) == 1:
        return None
    sizes = ", ".join(f"{rel}={len(body)}B" for rel, body in bodies.items())
    normalised = {v.replace(CRLF, LF) for v in bodies.values()}
    if len(normalised) == 1:
        return ("line-endings", f"identical after LF-normalisation ({sizes})")
    return ("content", f"the committed bodies differ in content ({sizes})")


def untracked_entries(
    repo: Path, pairs: Iterable[tuple[Path, Path]], rev: str = "HEAD"
) -> dict[str, str]:
    """Stanza entries that this box can run but a fresh clone of ``rev`` could not.

    ``pairs`` is ``(registry_path, skills_root)``. The returned mapping is
    ``"<registry>::<stanza>" -> <repo-relative entry path>``; empty means every entry is
    in the committed tree.
    """
    tracked = tracked_paths(repo, rev)
    missing: dict[str, str] = {}
    root = repo.resolve()
    for registry, skills_root in pairs:
        for name, spec in m.load_monitors(str(registry)).items():
            entry = Path(m.resolve_entry(spec, str(skills_root))).resolve()
            try:
                rel = entry.relative_to(root).as_posix()
            except ValueError:
                missing[f"{registry.name}::{name}"] = f"<outside the repo> {entry}"
                continue
            if rel not in tracked:
                missing[f"{registry.name}::{name}"] = rel
    return missing


# --------------------------------------------------------------------------------------
# The shipped gates: the real repo, at HEAD.
# --------------------------------------------------------------------------------------


def test_registry_mirrors_are_byte_identical_in_the_COMMIT() -> None:
    """The worktree twin of this assertion cannot see a half-committed mirror pair."""
    divergence = mirror_divergence(REPO, REGISTRY_RELS)
    assert divergence is None, (
        f"the two committed monitors.toml mirrors have diverged [{divergence}] -- a "
        "fresh clone would deploy two different registries even though this working "
        "tree may look consistent"
    )


def test_every_shipped_entry_is_tracked_in_the_COMMIT() -> None:
    """Reachable HERE is not reachable EVERYWHERE unless the entry script is committed."""
    pairs = [(REPO / rel, (REPO / rel).parent.parent) for rel in REGISTRY_RELS]
    missing = untracked_entries(REPO, pairs)
    assert not missing, (
        f"stanza entry scripts absent from the committed tree: {missing} -- `mon <name>` "
        "would work on this box and launch nothing from a fresh clone"
    )


def test_the_cockpit_entry_specifically_is_in_the_commit() -> None:
    """Named rather than left to the sweep, so deleting it fails with the reason."""
    tracked = tracked_paths(REPO)
    for rel in REGISTRY_RELS:
        registry = REPO / rel
        root = registry.parent.parent
        spec = m.load_monitors(str(registry))["cockpit"]
        entry = Path(m.resolve_entry(spec, str(root))).resolve()
        rel_entry = entry.relative_to(REPO.resolve()).as_posix()
        assert rel_entry in tracked, (
            f"the cockpit entry {rel_entry} is not in the committed tree"
        )


# --------------------------------------------------------------------------------------
# Both-states controls. Each builds a throwaway object database and requires the check to
# FIRE. A probe that is silent in the broken state measures nothing, so the passes above
# are only meaningful because these fail.
#
# No `git commit` is issued anywhere: the trees are built with hash-object / update-index /
# write-tree and addressed by TREE SHA. That keeps the controls independent of user.name,
# user.email and of the owner's commit-signing configuration, which a test has no business
# touching.
# --------------------------------------------------------------------------------------


def _init(tmp: Path) -> Path:
    proc = _git(tmp, "init", "-q")
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return tmp


def _stage(repo: Path, rel: str, body: bytes) -> str:
    """Write ``body`` into the object DB verbatim and stage it at ``rel``.

    ``hash-object --no-filters`` is deliberate: with ``core.autocrlf=true`` (common on
    this box) a plain add would normalise CRLF away and the line-endings control could
    never reach the state it exists to exercise.
    """
    blob_file = repo / "_stage_tmp"
    blob_file.write_bytes(body)
    made = _git(repo, "hash-object", "-w", "--no-filters", "--", "_stage_tmp")
    assert made.returncode == 0, made.stderr.decode("utf-8", "replace")
    oid = made.stdout.decode("ascii").strip()
    blob_file.unlink()
    upd = _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{oid},{rel}")
    assert upd.returncode == 0, upd.stderr.decode("utf-8", "replace")
    return oid


def _tree(repo: Path) -> str:
    proc = _git(repo, "write-tree")
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout.decode("ascii").strip()


def test_control_identical_mirrors_are_silent(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    for rel in REGISTRY_RELS:
        _stage(repo, rel, b"[cockpit]\nentry = 'unified_board.py'\n")
    assert mirror_divergence(repo, REGISTRY_RELS, _tree(repo)) is None


def test_control_content_divergence_fires(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    _stage(repo, REGISTRY_RELS[0], b"[cockpit]\nentry = 'unified_board.py'\n")
    _stage(repo, REGISTRY_RELS[1], b"[cockpit]\nentry = 'SOMETHING_ELSE.py'\n")
    divergence = mirror_divergence(repo, REGISTRY_RELS, _tree(repo))
    assert divergence is not None
    assert divergence[0] == "content", divergence


def test_control_line_ending_divergence_is_classified_separately(
    tmp_path: Path,
) -> None:
    repo = _init(tmp_path)
    _stage(repo, REGISTRY_RELS[0], b"[cockpit]\nentry = 'unified_board.py'\n")
    _stage(repo, REGISTRY_RELS[1], b"[cockpit]\r\nentry = 'unified_board.py'\r\n")
    divergence = mirror_divergence(repo, REGISTRY_RELS, _tree(repo))
    assert divergence is not None
    assert divergence[0] == "line-endings", divergence


def test_control_the_worktree_green_commit_red_split_is_caught(tmp_path: Path) -> None:
    """THE control: the exact 3bdcaf56 state -- worktree agrees, the commit does not.

    The old worktree assertion is reproduced verbatim here so the two verdicts can be
    compared in one run. It must stay SILENT while the committed-tree check FIRES; if
    both fired, this module would be redundant rather than additive.
    """
    repo = _init(tmp_path)
    agreed = b"[cockpit]\nentry = 'unified_board.py'\n"
    stale = b"[cockpit]\nentry = 'OLD.py'\n"
    # committed: one mirror updated, the other left at the stale body
    _stage(repo, REGISTRY_RELS[0], agreed)
    _stage(repo, REGISTRY_RELS[1], stale)
    tree = _tree(repo)
    # working tree: BOTH files already carry the agreed body, so a worktree read agrees
    for rel in REGISTRY_RELS:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(agreed)

    worktree_bodies = [
        (repo / rel).read_bytes().replace(CRLF, LF) for rel in REGISTRY_RELS
    ]
    assert worktree_bodies[0] == worktree_bodies[1], (
        "control precondition: the working tree must LOOK consistent"
    )
    assert mirror_divergence(repo, REGISTRY_RELS, tree) is not None, (
        "the committed-tree check failed to fire on the worktree-green/commit-red state "
        "it exists to catch"
    )


def test_control_an_untracked_entry_is_reported(tmp_path: Path) -> None:
    """A stanza pointing at a file that exists on disk but not in the tree."""
    repo = _init(tmp_path)
    rel = REGISTRY_RELS[0]
    body = b"[ghost]\ndir = 'ghost-skill'\nentry = 'ghost.py'\n"
    _stage(repo, rel, body)
    tree = _tree(repo)
    registry = repo / rel
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_bytes(body)
    ghost = repo / "skills" / "ghost-skill" / "ghost.py"
    ghost.parent.mkdir(parents=True, exist_ok=True)
    ghost.write_text("print('only on this box')\n", encoding="utf-8")

    assert ghost.is_file(), "control precondition: the entry exists in the working tree"
    missing = untracked_entries(repo, [(registry, registry.parent.parent)], tree)
    assert missing, (
        "an entry present only in the working tree was reported as reachable"
    )
    assert "ghost" in next(iter(missing)), missing


def test_control_a_tracked_entry_is_not_reported(tmp_path: Path) -> None:
    """The inverted control: the same shape, but committed, must be silent."""
    repo = _init(tmp_path)
    rel = REGISTRY_RELS[0]
    body = b"[real]\ndir = 'real-skill'\nentry = 'real.py'\n"
    _stage(repo, rel, body)
    _stage(repo, "skills/real-skill/real.py", b"print('committed')\n")
    tree = _tree(repo)
    registry = repo / rel
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_bytes(body)
    assert untracked_entries(repo, [(registry, registry.parent.parent)], tree) == {}


def test_control_absent_git_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(GitProbeError, match="not on PATH"):
        committed_blob(tmp_path, "anything")


def test_control_an_unreadable_revision_fails_closed(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    with pytest.raises(GitProbeError, match="not readable"):
        committed_blob(repo, "skills/monitor-launcher/monitors.toml", "HEAD")


def test_control_an_empty_tree_fails_closed(tmp_path: Path) -> None:
    """An empty walk must raise, never report "no untracked entries"."""
    repo = _init(tmp_path)
    empty_tree = _tree(repo)
    with pytest.raises(GitProbeError, match="zero paths"):
        tracked_paths(repo, empty_tree)


def test_control_a_single_path_cannot_be_compared_to_itself(tmp_path: Path) -> None:
    with pytest.raises(GitProbeError, match="at least two paths"):
        mirror_divergence(tmp_path, REGISTRY_RELS[:1])


# --- controls that exercise the REAL repo at HEAD -------------------------------------
# The temp-object-database controls above prove the FUNCTIONS fire. They do not prove the
# SHIPPED assertions are wired to a working instrument, because those run against a
# different repo, a different revision and a different tracked set. These two close that
# gap: same code path, same REPO, same HEAD, deliberately wrong inputs.


def test_control_the_shipped_mirror_check_is_not_vacuous() -> None:
    """Two genuinely different tracked files at HEAD must be reported as diverged."""
    divergence = mirror_divergence(
        REPO,
        ("tools/monitorcore/pyproject.toml", "tools/monitorcore/tests/__init__.py"),
    )
    assert divergence is not None and divergence[0] == "content", (
        "mirror_divergence returned 'identical' for two different committed files at "
        f"HEAD -- the instrument is broken, so the shipped green means nothing: {divergence}"
    )


def test_control_the_shipped_tracked_check_is_not_vacuous(tmp_path: Path) -> None:
    """A stanza naming a path absent from the REAL HEAD tree must be reported."""
    registry = tmp_path / "monitor-launcher" / "monitors.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_bytes(
        b"[ghost]\ndir = 'definitely-not-a-skill'\nentry = 'ghost.py'\n"
    )
    missing = untracked_entries(REPO, [(registry, REPO / "skills")])
    assert missing == {
        "monitors.toml::ghost": "skills/definitely-not-a-skill/ghost.py"
    }, missing
