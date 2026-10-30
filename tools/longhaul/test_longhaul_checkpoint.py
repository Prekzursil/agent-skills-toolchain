#!/usr/bin/env python
"""Tests for longhaul_checkpoint. Run: python test_longhaul_checkpoint.py (or pytest).

Ported unchanged from durable-checkpoint's suite (closed PR #398, 41 tests), with the
module renamed; new tests for the longhaul fixes follow the ported ones. The seven
ordering rows live in spec_longhaul_checkpoint.py.

Everything runs in a temp dir on tiny files, with no network and no subprocess,
so the suite is cheap on a thermally limited machine. The periodic-loop tests
use a 50ms interval rather than the 600s default.
"""

from __future__ import annotations

import ast
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import longhaul_checkpoint as dc  # noqa: E402

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
    tree = ast.parse((HERE / "longhaul_checkpoint.py").read_text(encoding="utf-8"))
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


# --------------------------------------------------------------------------- #
# Mutation-review follow-ups (adversarial review, 2026-10-24)                 #
# --------------------------------------------------------------------------- #


def test_incomplete_generation_refused_whatever_the_write_order() -> None:
    """Pins the REAL guarantee, which is stronger than "manifest last".

    The review flagged that no test catches a mutant writing the manifest
    BEFORE the files. Measured: that mutant is harmless here, because a
    manifest enumerates its own generation's files with hashes and
    verify_generation checks every one. An interrupted generation therefore
    fails verification whichever order it was written in, and latest_verified
    falls back. Manifest-last is defence in depth; this is the guarantee.
    """
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        for i in range(4):
            _mk(work, f"f{i}.txt", f"content {i}")
        _ckpt(work, durable).mirror_now()
        assert dc.verify(durable).ok

        # Generation 2 built the mutant way: manifest first, files incomplete.
        g2 = dc.gen_dir(durable, 2)
        g2.mkdir()
        files = {}
        for i in range(4):
            src_f = work / f"f{i}.txt"
            sha, size = dc._hash_file(src_f)
            files[f"f{i}.txt"] = {
                "sha256": sha,
                "size": size,
                "mtime_ns": src_f.stat().st_mtime_ns,
            }
        (g2 / dc.MANIFEST_NAME).write_text(
            json.dumps(
                {"version": dc.MANIFEST_VERSION, "created": 1.0, "files": files}
            ),
            encoding="utf-8",
        )
        (g2 / "f0.txt").write_text("content 0", encoding="utf-8")  # 1 of 4

        v2 = dc.verify_generation(durable, 2)
        assert not v2.ok
        assert "missing file from manifest" in v2.reason
        n, best = dc.latest_verified(durable)
        assert n == 1 and best.ok, "falls back to the last complete generation"


def test_same_mtime_different_size_is_not_reused() -> None:
    """Closes a real review gap: the SIZE half of the changed-file check.

    Reuse requires size AND mtime to match. Drop the size half and a file
    rewritten to a different length within one mtime tick is hardlinked from
    the previous generation under its OLD hash — a checkpoint that verifies
    while silently holding stale content, which is the worst failure shape.
    """
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        p = _mk(work, "a.txt", "short")
        ck = _ckpt(work, durable, keep_generations=3)
        first = ck.mirror_now()
        stat0 = p.stat()

        # Longer content, mtime forced back to the original: only the size
        # differs, which is exactly the signal the mutant removes.
        p.write_text("considerably longer content", encoding="utf-8")
        os.utime(p, ns=(stat0.st_atime_ns, stat0.st_mtime_ns))
        assert p.stat().st_mtime_ns == stat0.st_mtime_ns, "mtime really is unchanged"

        second = ck.mirror_now()
        assert second.generation != first.generation
        assert second.copied == 1, "a size change alone must force a re-copy"
        assert second.linked == 0
        got = (dc.gen_dir(durable, second.generation) / "a.txt").read_text(
            encoding="utf-8"
        )
        assert got == "considerably longer content", "must not hold stale content"
        assert dc.verify(durable).ok


def test_signal_re_raises_when_the_previous_handler_was_default() -> None:
    """Closes a real review gap: the SIG_DFL re-raise.

    With SIG_DFL installed before us, taking the final checkpoint and then
    returning would swallow the signal and leave the process alive, so a
    preemption would not actually stop it. The handler must restore the default
    and re-deliver. os.kill is injected rather than real, for obvious reasons.
    """
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=5)
        ck._prev_handlers[signal.SIGTERM] = signal.SIG_DFL

        restored: list[tuple[int, object]] = []
        killed: list[tuple[int, int]] = []
        real_signal, real_kill = signal.signal, os.kill
        signal.signal = lambda s, h: restored.append((s, h))
        os.kill = lambda pid, sig: killed.append((pid, sig))
        try:
            ck._on_signal(signal.SIGTERM, None)
        finally:
            signal.signal, os.kill = real_signal, real_kill

        assert (signal.SIGTERM, signal.SIG_DFL) in restored, "default restored first"
        assert killed == [(os.getpid(), signal.SIGTERM)], "then re-delivered to self"
        assert dc.verify(durable).ok, "and the final checkpoint still landed"


# --------------------------------------------------------------------------- #
# longhaul additions: the behaviour behind the seven spec rows, unit by unit  #
# --------------------------------------------------------------------------- #


def test_manifest_path_that_escapes_the_generation_is_refused() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        g2 = dc.gen_dir(durable, 2)
        g2.mkdir()
        (g2 / dc.MANIFEST_NAME).write_text(
            json.dumps(
                {
                    "version": dc.MANIFEST_VERSION,
                    "created": 1.0,
                    "files": {"../outside.txt": {"sha256": "x", "size": 1}},
                }
            ),
            encoding="utf-8",
        )
        v = dc.verify_generation(durable, 2)
        assert not v.ok and "not a safe relative path" in v.reason
        n, best = dc.latest_verified(durable)
        assert n == 1 and best.ok, "falls back past the escaping manifest"


def test_resume_restores_the_recorded_mtimes() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        p = _mk(work, "a.txt", "alpha")
        recorded = p.stat().st_mtime_ns
        _ckpt(work, durable).mirror_now()
        dc.clear_work_dir(work)
        dc.resume_into(durable, work)
        assert (work / "a.txt").stat().st_mtime_ns == recorded


def test_resume_refuses_bytes_that_do_not_match_the_manifest() -> None:
    """Verify-on-read: what is hydrated is re-hashed against the manifest."""
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        dc.clear_work_dir(work)
        real = dc._copy_and_hash

        def lying_copy(src: Path, dst: Path) -> tuple[str, int]:
            _sha, size = real(src, dst)
            return "0" * 64, size

        dc._copy_and_hash = lying_copy  # type: ignore[assignment]
        try:
            dc.resume_into(durable, work)
        except dc.CheckpointError as exc:
            assert "changed while being hydrated" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")
        finally:
            dc._copy_and_hash = real  # type: ignore[assignment]


def test_signal_skips_the_final_when_a_mirror_holds_the_lock() -> None:
    import threading

    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable)
        chained: list[int] = []
        ck._prev_handlers[signal.SIGTERM] = lambda s, _f: chained.append(s)
        held = threading.Event()
        release = threading.Event()

        def hold() -> None:
            with ck._lock:
                held.set()
                release.wait(5.0)

        th = threading.Thread(target=hold, daemon=True)
        th.start()
        held.wait(5.0)
        t0 = time.monotonic()
        ck._on_signal(signal.SIGTERM, None)
        elapsed = time.monotonic() - t0
        release.set()
        th.join(5.0)
        assert elapsed < 1.0, f"handler blocked {elapsed:.2f}s"
        assert ck.skipped_finals == 1
        assert chained == [signal.SIGTERM], (
            "the signal still reaches the previous handler"
        )
        assert dc.generations(durable) == [], "no final was written"


def test_a_second_signal_writes_no_second_final() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable)
        ck._prev_handlers[signal.SIGINT] = lambda *_a: None
        ck._prev_handlers[signal.SIGTERM] = lambda *_a: None
        ck._on_signal(signal.SIGINT, None)
        ck._on_signal(signal.SIGTERM, None)
        assert dc.generations(durable) == [1] and ck.mirrors == 1
        assert ck.stop(final=True) is None, "stop() does not repeat the final"


def test_stop_restores_only_the_handlers_start_installed() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "alpha")
        before = signal.getsignal(signal.SIGTERM)
        ck = _ckpt(work, durable)
        ck._prev_handlers[signal.SIGTERM] = lambda *_a: None  # never installed
        ck.stop(final=False)
        assert signal.getsignal(signal.SIGTERM) is before


def test_same_size_corruption_of_the_link_base_is_repaired_not_carried() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "GOOD")
        _mk(work, "b.txt", "keep")
        ck = _ckpt(work, durable, keep_generations=3)
        ck.mirror_now()
        (dc.gen_dir(durable, 1) / "a.txt").write_text("EVIL", encoding="utf-8")
        r = ck.mirror_now()
        if r.repaired == 0 and r.linked == 0:
            return  # filesystem will not hardlink, so nothing could be carried
        assert r.verified and r.repaired == 2 and r.linked == 0
        got = (dc.gen_dir(durable, r.generation) / "a.txt").read_text(encoding="utf-8")
        assert got == "GOOD"
        assert 1 not in dc.generations(durable), (
            "the corrupt base is garbage, not a slot"
        )


def test_a_fresh_process_never_links_from_an_unverified_generation() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        _mk(work, "a.txt", "GOOD")
        _ckpt(work, durable).mirror_now()
        (dc.gen_dir(durable, 1) / "a.txt").write_text("EVIL", encoding="utf-8")
        fresh = _ckpt(work, durable)  # a new container: knows nothing yet
        r = fresh.mirror_now()
        assert r.linked == 0 and r.copied == 1 and r.verified
        got = (dc.gen_dir(durable, r.generation) / "a.txt").read_text(encoding="utf-8")
        assert got == "GOOD"


def test_torn_generation_never_holds_a_retained_slot() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        p = _mk(work, "a.txt", "v1")
        ck = _ckpt(work, durable, keep_generations=2)
        ck.mirror_now()
        _touch_newer(p, "v2")
        ck.mirror_now()
        torn = dc.gen_dir(durable, 3)
        torn.mkdir()
        (torn / "a.txt").write_text("torn", encoding="utf-8")
        _touch_newer(p, "v3")
        r = ck.mirror_now()
        assert r.pruned == (1, 3), f"torn gen3 and the oldest good go: {r.pruned}"
        assert dc.generations(durable) == [2, 4]


def test_unreadable_manifest_bytes_fall_back() -> None:
    with tempfile.TemporaryDirectory() as d:
        work, durable = _dirs(d)
        p = _mk(work, "a.txt", "v1")
        ck = _ckpt(work, durable, keep_generations=3)
        ck.mirror_now()
        _touch_newer(p, "v2")
        ck.mirror_now()
        dc.manifest_path(durable, 2).write_bytes(b'{"version": 2, \xff}')
        v = dc.verify_generation(durable, 2)
        assert not v.ok and "UTF-8" in v.reason
        assert dc.resume_into(durable, Path(d) / "w2").generation == 1


# Floor, not just "no failures": a discovery break (a rename, a decorator that
# hides the test_ functions) would otherwise report PASS on 0/0 and gate
# nothing. Raise it when tests are added; a drop below it is a lost test.
MIN_TESTS = 51


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
