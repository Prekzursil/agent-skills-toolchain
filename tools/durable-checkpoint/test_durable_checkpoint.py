#!/usr/bin/env python
"""Tests for durable-checkpoint. Run: python test_durable_checkpoint.py (or pytest).

Everything runs in a temp dir on tiny files, with no network and no subprocess,
so the suite is cheap on a thermally limited machine. The periodic-loop tests
use a 50ms interval rather than the 600s default.
"""

from __future__ import annotations

import ast
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import durable_checkpoint as dc  # noqa: E402

ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "dataclasses",
        "fnmatch",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "re",
        "shutil",
        "signal",
        "threading",
        "time",
    }
)


def _mk(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _dirs(tmp: str) -> tuple[Path, Path]:
    work = Path(tmp) / "work"
    durable = Path(tmp) / "durable"
    work.mkdir(parents=True, exist_ok=True)
    return work, durable


def _ckpt(work: Path, durable: Path, **kw: object) -> dc.DurableCheckpoint:
    kw.setdefault("handle_signals", False)
    kw.setdefault("logger", lambda _m: None)
    return dc.DurableCheckpoint(work, durable, **kw)  # type: ignore[arg-type]


def _touch_newer(p: Path, text: str) -> None:
    """Rewrite a file and guarantee a visibly newer mtime.

    A same-size rewrite inside one clock tick would otherwise look unchanged to
    the incremental check.
    """
    p.write_text(text, encoding="utf-8")
    now = time.time_ns()
    os.utime(p, ns=(now, now + 5_000_000))


# --------------------------------------------------------------------------- #
# THE regression: a cut-short final checkpoint must not cost earlier ones     #
# --------------------------------------------------------------------------- #


def test_preemption_during_final_checkpoint_keeps_the_previous_generation() -> None:
    """The data-loss bug this layout exists to prevent.

    Reproduced on the in-place build of this module: a good checkpoint's four
    files sat physically intact on disk and every one was unusable, because the
    manifest vouching for them had been removed to start a final checkpoint that
    never finished. Total loss, not last-interval loss — and on the ordinary
    preemption path, since SIGINT is exactly when the final checkpoint runs.

    With generations, a cut-short final checkpoint costs only itself.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        for i in range(4):
            _mk(work, f"stage{i}.ckpt", f"hours of work {i}")
        ck = _ckpt(work, durable, interval_s=5)
        first = ck.mirror_now()
        assert dc.verify(durable).ok
        assert first.generation == 1

        # More work lands since that tick, then preemption arrives and the
        # container dies before the new generation's manifest is written.
        _mk(work, "stage4.ckpt", "the last interval of work")
        real_write = dc._atomic_write_text

        def killed_before_manifest(path: Path, text: str) -> None:
            raise OSError("container killed before the manifest was written")

        dc._atomic_write_text = killed_before_manifest  # type: ignore[assignment]
        try:
            ck._on_signal(signal.SIGTERM, None)  # must not raise
        finally:
            dc._atomic_write_text = real_write  # type: ignore[assignment]

        # Generation 1 is untouched and still the answer.
        n, result = dc.latest_verified(durable)
        assert n == 1, f"expected to fall back to generation 1, got {n}"
        assert result.ok and result.files == 4
        assert ck.failures == 1, "the failed final checkpoint is counted"

        # And it actually resumes, rather than merely verifying.
        dc.clear_work_dir(work)
        res = dc.resume_into(durable, work)
        assert res.generation == 1 and res.hydrated == 4
        assert (work / "stage0.ckpt").read_text(encoding="utf-8") == "hours of work 0"


def test_torn_newest_generation_falls_back_not_fatal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "one")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        _touch_newer(work / "a.txt", "two")
        ck.mirror_now()
        assert dc.generations(durable) == [1, 2]
        # Corrupt generation 2 the way a torn write would.
        (dc.gen_dir(durable, 2) / "a.txt").write_text("XXX", encoding="utf-8")
        n, result = dc.latest_verified(durable)
        assert n == 1 and result.ok
        assert dc.resume_into(durable, work).generation == 1


def test_generation_with_no_manifest_is_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "one")
        _ckpt(work, durable).mirror_now()
        # An interrupted generation: directory and files, no manifest.
        gdir = dc.gen_dir(durable, 7)
        gdir.mkdir(parents=True)
        (gdir / "a.txt").write_text("half-written", encoding="utf-8")
        assert dc.generations(durable) == [1, 7]
        n, _ = dc.latest_verified(durable)
        assert n == 1, "an incomplete generation must not shadow a good one"


def test_all_generations_unverifiable_refuses_resume() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "one")
        _ckpt(work, durable).mirror_now()
        (dc.gen_dir(durable, 1) / "a.txt").write_text("XXX", encoding="utf-8")
        dc.clear_work_dir(work)
        try:
            dc.resume_into(durable, work)
        except dc.CheckpointError as exc:
            assert "refusing to resume" in str(exc)
            assert "no generation verifies" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")
        assert not any(work.iterdir()), "must not half-hydrate"


# --------------------------------------------------------------------------- #
# Round trip                                                                  #
# --------------------------------------------------------------------------- #


def test_mirror_then_verify_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "sub/b.bin", "beta" * 100)
        r = _ckpt(work, durable).mirror_now()
        assert r.generation == 1 and r.copied == 2 and r.linked == 0
        assert r.verified, "a fresh generation must pass its own read-back"
        v = dc.verify(durable)
        assert v.ok and v.files == 2 and bool(v) is True


def test_resume_round_trips_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "sub/b.txt", "beta")
        _ckpt(work, durable).mirror_now()
        dc.clear_work_dir(work)
        assert not any(work.iterdir())
        res = dc.resume_into(durable, work)
        assert res.hydrated == 2
        assert (work / "a.txt").read_text(encoding="utf-8") == "alpha"
        assert (work / "sub" / "b.txt").read_text(encoding="utf-8") == "beta"


def test_generations_increment_and_are_listed_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        p = _mk(work, "a.txt", "v1")
        ck = _ckpt(work, durable, keep_generations=5)
        for i in range(3):
            ck.mirror_now()
            _touch_newer(p, f"v{i + 2}")
        assert dc.generations(durable) == [1, 2, 3]
        assert dc.gen_name(42) == "gen-00000042"


def test_has_checkpoint_is_presence_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        assert not dc.has_checkpoint(durable)
        _mk(work, "a.txt", "x")
        _ckpt(work, durable).mirror_now()
        assert dc.has_checkpoint(durable)
        # Still "present" when corrupt: presence is not integrity.
        (dc.gen_dir(durable, 1) / "a.txt").write_text("XX", encoding="utf-8")
        assert dc.has_checkpoint(durable)
        assert not dc.verify(durable).ok


# --------------------------------------------------------------------------- #
# Integrity detection within a generation                                     #
# --------------------------------------------------------------------------- #


def test_corrupted_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        # Same length, different bytes: a size check alone would miss it.
        (dc.gen_dir(durable, 1) / "a.txt").write_text("ALPHA", encoding="utf-8")
        v = dc.verify_generation(durable, 1)
        assert not v.ok and "checksum mismatch" in v.reason


def test_truncated_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alphabet")
        _ckpt(work, durable).mirror_now()
        (dc.gen_dir(durable, 1) / "a.txt").write_text("alph", encoding="utf-8")
        v = dc.verify_generation(durable, 1)
        assert not v.ok and "size mismatch" in v.reason


def test_missing_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "b.txt", "beta")
        _ckpt(work, durable).mirror_now()
        (dc.gen_dir(durable, 1) / "b.txt").unlink()
        v = dc.verify_generation(durable, 1)
        assert not v.ok and "missing file" in v.reason


def test_quick_verify_skips_hashes_but_still_catches_size() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        g = dc.gen_dir(durable, 1)
        (g / "a.txt").write_text("ALPHA", encoding="utf-8")
        assert dc.verify_generation(durable, 1, quick=True).ok, "equal size slips by"
        (g / "a.txt").write_text("a", encoding="utf-8")
        assert not dc.verify_generation(durable, 1, quick=True).ok


def test_bad_manifests_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        mp = dc.manifest_path(durable, 1)
        mp.write_text("{not json", encoding="utf-8")
        assert "not valid JSON" in dc.verify_generation(durable, 1).reason
        mp.write_text('{"version": 99, "files": {}}', encoding="utf-8")
        assert "not supported" in dc.verify_generation(durable, 1).reason
        mp.write_text('{"version": 2, "files": {}}', encoding="utf-8")
        assert "lists no files" in dc.verify_generation(durable, 1).reason
        mp.write_text('{"version": 2, "files": {"a.txt": 3}}', encoding="utf-8")
        assert "not an object" in dc.verify_generation(durable, 1).reason
        mp.write_text('{"version": 2, "files": {"a.txt": {}}}', encoding="utf-8")
        assert "malformed" in dc.verify_generation(durable, 1).reason


def test_verify_on_empty_durable_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v = dc.verify(Path(tmp) / "never-written")
        assert not v.ok and "no generations" in v.reason


# --------------------------------------------------------------------------- #
# Retention                                                                   #
# --------------------------------------------------------------------------- #


def test_prune_keeps_the_configured_number_of_generations() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        p = _mk(work, "a.txt", "v1")
        ck = _ckpt(work, durable, keep_generations=2)
        for i in range(4):
            ck.mirror_now()
            _touch_newer(p, f"v{i + 2}")
        gens = dc.generations(durable)
        assert len(gens) == 2, f"expected 2 retained, got {gens}"
        assert gens == [3, 4], "the oldest go first"
        assert dc.verify(durable).ok


def test_prune_never_runs_when_readback_fails() -> None:
    """Pruning on the strength of an unverified write is taking its word for it."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        p = _mk(work, "a.txt", "v1")
        ck = _ckpt(work, durable, keep_generations=2)
        ck.mirror_now()
        _touch_newer(p, "v2")
        ck.mirror_now()
        _touch_newer(p, "v3")

        real = dc.verify_generation

        def fail_newest(d: object, n: int, quick: bool = False) -> dc.VerifyResult:
            if n == 3:
                return dc.VerifyResult(
                    False, "simulated read-back failure", generation=n
                )
            return real(d, n, quick=quick)

        dc.verify_generation = fail_newest  # type: ignore[assignment]
        try:
            r = ck.mirror_now()
        finally:
            dc.verify_generation = real  # type: ignore[assignment]
        assert not r.verified
        assert r.pruned == (), "nothing may be pruned on an unverified generation"
        assert 1 in dc.generations(durable), "the known-good oldest is still there"


def test_keep_generations_below_two_rejected() -> None:
    """Keeping one reintroduces the bug: pruning the only good copy."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        for bad in (1, 0, -3):
            try:
                _ckpt(work, durable, keep_generations=bad)
            except dc.CheckpointError as exc:
                assert "at least 2" in str(exc)
            else:
                raise AssertionError(f"expected CheckpointError for {bad}")


# --------------------------------------------------------------------------- #
# Mirror behaviour                                                            #
# --------------------------------------------------------------------------- #


def test_unchanged_files_are_linked_not_recopied() -> None:
    """A new generation must not mean re-writing unchanged bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "b.txt", "beta")
        ck = _ckpt(work, durable)
        assert ck.mirror_now().copied == 2
        second = ck.mirror_now()
        if second.linked == 0:
            return  # filesystem will not hardlink; the fallback test covers it
        assert second.linked == 2 and second.copied == 0
        assert second.bytes_copied == 0
        assert dc.verify(durable).ok, "carried-over hashes must still verify"


def test_falls_back_to_copying_when_links_are_unsupported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        real_link = os.link

        def no_links(src: object, dst: object, **kw: object) -> None:
            raise OSError("hardlinks not supported on this mount")

        os.link = no_links  # type: ignore[assignment]
        try:
            r = ck.mirror_now()
        finally:
            os.link = real_link  # type: ignore[assignment]
        assert r.linked == 0 and r.copied == 1
        assert dc.verify(durable).ok
        strays = [p.name for p in durable.rglob("*") if p.name.endswith(".tmp")]
        assert not strays, f"a failed link must leave nothing behind: {strays}"


def test_link_disabled_by_flag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, link_unchanged=False)
        ck.mirror_now()
        r = ck.mirror_now()
        assert r.linked == 0 and r.copied == 1


def test_changed_file_is_recopied() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        p = _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        _touch_newer(p, "omega")
        r = ck.mirror_now()
        assert r.copied == 1
        assert dc.verify(durable).ok
        assert (dc.gen_dir(durable, 2) / "a.txt").read_text(encoding="utf-8") == "omega"


def test_deleted_file_is_absent_from_the_new_generation() -> None:
    """Each generation is built from current scratch, so pruning is implicit.

    Without that, a resumed job sees a directory that never existed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "gone.txt", "bye")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        (work / "gone.txt").unlink()
        r = ck.mirror_now()
        assert not (dc.gen_dir(durable, r.generation) / "gone.txt").exists()
        assert (dc.gen_dir(durable, 1) / "gone.txt").exists(), "history is immutable"
        dc.clear_work_dir(work)
        dc.resume_into(durable, work)
        assert not (work / "gone.txt").exists()


def test_excludes_are_honoured() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "keep.txt", "k")
        _mk(work, "scratch.tmp", "junk")
        _mk(work, "logs/debug.log", "noise")
        r = _ckpt(work, durable, exclude=("*.tmp", "logs")).mirror_now()
        assert r.copied == 1
        g = dc.gen_dir(durable, r.generation)
        assert (g / "keep.txt").exists()
        assert not (g / "scratch.tmp").exists()
        assert not (g / "logs").exists()


def test_no_temp_files_left_behind() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        strays = [p.name for p in durable.rglob("*") if p.name.endswith(".tmp")]
        assert not strays, f"atomic writes must clean up: {strays}"


def test_symlinks_are_skipped_not_followed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "real.txt", "data")
        outside = Path(tmp) / "outside.txt"
        outside.write_text("should not be copied", encoding="utf-8")
        try:
            (work / "link.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            return  # Windows without developer mode
        r = _ckpt(work, durable).mirror_now()
        assert r.copied == 1
        assert not (dc.gen_dir(durable, r.generation) / "link.txt").exists()


def test_commit_runs_after_the_manifest_and_before_readback() -> None:
    """On a volume nothing is durable until commit returns, so the order is:
    manifest, commit, then trust it."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        seen: list[bool] = []
        _ckpt(
            work,
            durable,
            commit=lambda: seen.append(dc.manifest_path(durable, 1).is_file()),
        ).mirror_now()
        assert seen == [True], "commit must see a written manifest"


def test_empty_work_dir_refused_and_leaves_no_generation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        try:
            _ckpt(work, durable).mirror_now()
        except dc.CheckpointError as exc:
            assert "nothing to checkpoint" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")
        assert dc.generations(durable) == [], "no stub generation may be left"


def test_mirror_requires_an_existing_work_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        work.rmdir()
        try:
            _ckpt(work, durable).mirror_now()
        except dc.CheckpointError as exc:
            assert "work_dir does not exist" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")


# --------------------------------------------------------------------------- #
# Construction guards                                                         #
# --------------------------------------------------------------------------- #


def test_same_dir_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "w"
        work.mkdir()
        try:
            dc.DurableCheckpoint(work, work, handle_signals=False)
        except dc.CheckpointError as exc:
            assert "must differ" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")


def test_nonpositive_interval_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        for bad in (0, -5):
            try:
                _ckpt(work, durable, interval_s=bad)
            except dc.CheckpointError as exc:
                assert "must be positive" in str(exc)
            else:
                raise AssertionError(f"expected CheckpointError for {bad}")


# --------------------------------------------------------------------------- #
# Lifecycle                                                                   #
# --------------------------------------------------------------------------- #


def test_periodic_loop_mirrors_and_stop_takes_a_final() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=0.05, keep_generations=4)
        ck.start()
        deadline = time.time() + 5.0
        while ck.mirrors == 0 and time.time() < deadline:
            time.sleep(0.02)
        assert ck.mirrors >= 1, "the timer must fire"
        _mk(work, "late.txt", "written just before exit")
        ck.stop(final=True)
        n, result = dc.latest_verified(durable)
        assert result.ok and n is not None
        assert (dc.gen_dir(durable, n) / "late.txt").exists(), "stop() captures it"


def test_double_start_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=5)
        ck.start()
        try:
            ck.start()
        except dc.CheckpointError as exc:
            assert "already started" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")
        finally:
            ck.stop(final=False)


def test_context_manager_mirrors_on_exit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        with _ckpt(work, durable, interval_s=5):
            _mk(work, "during.txt", "work happened")
        n, result = dc.latest_verified(durable)
        assert result.ok and n is not None
        assert (dc.gen_dir(durable, n) / "during.txt").exists()


def test_signal_chains_to_the_previous_handler() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=5)
        chained: list[int] = []
        ck._prev_handlers[signal.SIGTERM] = lambda signum, _f: chained.append(signum)
        _mk(work, "unsaved.txt", "since the last tick")
        ck._on_signal(signal.SIGTERM, None)
        n, result = dc.latest_verified(durable)
        assert result.ok and n is not None
        assert (dc.gen_dir(durable, n) / "unsaved.txt").exists()
        assert chained == [signal.SIGTERM], "previous handler must still run"


def test_failed_mirror_in_the_loop_does_not_kill_the_job() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=0.05)
        real = dc._copy_and_hash

        def boom(src: Path, dst: Path) -> tuple[str, int]:
            raise OSError("durable path went away")

        dc._copy_and_hash = boom  # type: ignore[assignment]
        try:
            ck.start()
            deadline = time.time() + 5.0
            while ck.failures == 0 and time.time() < deadline:
                time.sleep(0.02)
            assert ck.failures >= 1, "failures are counted"
            assert ck._thread is not None and ck._thread.is_alive(), "loop survives"
        finally:
            dc._copy_and_hash = real  # type: ignore[assignment]
            ck.stop(final=False)


def test_clear_work_dir_handles_nested_and_absent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "w"
        work.mkdir()
        _mk(work, "a.txt", "x")
        _mk(work, "deep/nested/b.txt", "y")
        dc.clear_work_dir(work)
        assert work.is_dir() and not any(work.iterdir())
        dc.clear_work_dir(Path(tmp) / "absent")  # must not raise


# --------------------------------------------------------------------------- #
# Structural                                                                  #
# --------------------------------------------------------------------------- #


def test_imports_match_the_allowlist() -> None:
    """No network, no subprocess, no cloud SDK — checked on the AST.

    The allowlist is the reviewable surface: adding to it is a visible act.
    """
    tree = ast.parse((HERE / "durable_checkpoint.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module.split(".")[0] if node.module else ".")
    unexpected = found - ALLOWED_IMPORTS
    assert not unexpected, f"unexpected imports: {sorted(unexpected)}"


def test_allowlist_excludes_provider_and_network_modules() -> None:
    for banned in (
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
        "subprocess",
        "importlib",
        "modal",
        "boto3",
    ):
        assert banned not in ALLOWED_IMPORTS, f"{banned} must not be allowlisted"


# Floor, not just "no failures": a discovery break (a rename, a decorator that
# hides the test_ functions) would otherwise report PASS on 0/0 and gate
# nothing. Raise it when tests are added; a drop below it is a lost test.
MIN_TESTS = 38


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    if len(tests) < MIN_TESTS:
        print(f"RESULT: FAIL  (collected {len(tests)} tests, floor is {MIN_TESTS})")
        return 1
    failures: list[str] = []
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - the runner reports everything
            failures.append(name)
            print(f"  BAD  {name}: {exc}")
        else:
            print(f"  OK   {name}")
    print(
        f"\nRESULT: {'PASS' if not failures else 'FAIL'}  "
        f"({len(tests) - len(failures)}/{len(tests)} passed)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
