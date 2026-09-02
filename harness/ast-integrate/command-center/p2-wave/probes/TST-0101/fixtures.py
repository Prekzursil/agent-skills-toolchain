"""Deterministic isolated-repo fixtures for TST-0101. Shared index is never used."""
from __future__ import annotations

from sandbox import GitSandbox, temporary_sandbox

KEEP_FILES = 24
NEWER_ON_MAIN = 40
LINES_PER_FILE = 20


def _body(tag: str, n: int = LINES_PER_FILE) -> str:
    return "".join(f"{tag} line {i:03d}\n" for i in range(n))


def seed_main(box: GitSandbox) -> None:
    box.write("README.md", "integration base\n")
    for i in range(KEEP_FILES):
        box.write(f"keep/file-{i:02d}.txt", _body(f"keep-{i:02d}"))
    box.commit_all("seed main with keep files")


def add_newer_main_work(box: GitSandbox) -> None:
    box.checkout("main")
    for i in range(NEWER_ON_MAIN):
        box.write(f"newer/work-{i:02d}.txt", _body(f"newer-{i:02d}"))
    box.commit_all("main gained newer work after the feature branched")


def fixture_stale_mass_deletion(box: GitSandbox) -> None:
    """Branch deletes the keep-set; main also moves forward with newer files."""
    seed_main(box)
    box.checkout("stale-delete", create=True)
    for i in range(KEEP_FILES):
        box.rm(f"keep/file-{i:02d}.txt")
    box.write("feature/note.txt", "tiny leftover change\n")
    box.commit_all("stale branch deletes the keep-set")
    add_newer_main_work(box)
    box.checkout("stale-delete")


def fixture_stale_but_small_proposal(box: GitSandbox) -> None:
    """Main moved forward; branch only added one file. Two-dot looks like mass delete."""
    seed_main(box)
    box.checkout("stale-small", create=True)
    box.write("feature/small.txt", "one authored addition\n")
    box.commit_all("feature adds one file")
    add_newer_main_work(box)
    box.checkout("stale-small")
    # Uncommitted worktree noise: two-dot worktree diff must not be the gate surface.
    box.rm("README.md")
    box.write("scratch-uncommitted.txt", "working-tree noise\n")


def fixture_fresh_small(box: GitSandbox) -> None:
    seed_main(box)
    add_newer_main_work(box)
    box.checkout("fresh-small", create=True)
    box.write("feature/fresh.txt", "freshly based addition\n")
    box.commit_all("fresh branch adds one file")


def fixture_squash_merged_ahead(box: GitSandbox) -> None:
    seed_main(box)
    box.checkout("feature-squash", create=True)
    box.write("feature/landed.txt", "this content is squash-merged to main\n")
    box.commit_all("feature commit that will be squash-merged")
    box.checkout("main")
    box.git("merge", "--squash", "feature-squash")
    box.git("commit", "-m", "squash merge feature-squash")
    box.checkout("feature-squash")


def with_fixture(name: str):
    builders = {
        "stale-mass-deletion": fixture_stale_mass_deletion,
        "stale-small-proposal": fixture_stale_but_small_proposal,
        "fresh-small": fixture_fresh_small,
        "squash-merged-ahead": fixture_squash_merged_ahead,
    }
    if name not in builders:
        raise KeyError(name)

    class _Ctx:
        def __enter__(self):
            self._cm = temporary_sandbox(prefix=f"tst0101-{name}-")
            self.box = self._cm.__enter__()
            builders[name](self.box)
            return self.box

        def __exit__(self, exc_type, exc, tb):
            return self._cm.__exit__(exc_type, exc, tb)

    return _Ctx()
