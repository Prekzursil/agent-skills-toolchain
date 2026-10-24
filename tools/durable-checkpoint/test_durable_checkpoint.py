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


# --------------------------------------------------------------------------- #
# Round trip                                                                  #
# --------------------------------------------------------------------------- #


def test_mirror_then_verify_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "sub/b.bin", "beta" * 100)
        r = _ckpt(work, durable).mirror_now()
        assert r.copied == 2 and r.reused == 0
        v = dc.verify(durable)
        assert v.ok, v.reason
        assert v.files == 2
        assert bool(v) is True, "VerifyResult must be truthy when ok"


def test_resume_round_trips_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "sub/b.txt", "beta")
        _ckpt(work, durable).mirror_now()
        dc.clear_work_dir(work)
        assert not any(work.iterdir()), "scratch emptied, as if the container died"
        res = dc.resume_into(durable, work)
        assert res.hydrated == 2
        assert (work / "a.txt").read_text(encoding="utf-8") == "alpha"
        assert (work / "sub" / "b.txt").read_text(encoding="utf-8") == "beta"


def test_has_checkpoint_is_presence_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        assert not dc.has_checkpoint(durable)
        _mk(work, "a.txt", "x")
        _ckpt(work, durable).mirror_now()
        assert dc.has_checkpoint(durable)


# --------------------------------------------------------------------------- #
# The central guarantee: a torn mirror must never look loadable               #
# --------------------------------------------------------------------------- #


def test_interrupted_mirror_leaves_no_manifest() -> None:
    """The defect this module exists to fix.

    The source program's committer copied straight into the live durable path,
    so a mid-write kill left a torn mix with an older validity sentinel still
    present, and the next run loaded the wreckage ("Bad checkpoints,
    ckpt_is_valid missing after mid-write kill"). Here the manifest is removed
    FIRST, so an interrupted mirror is refused instead.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "one")
        _mk(work, "b.txt", "two")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        assert dc.verify(durable).ok, "good checkpoint first"

        # Now a second mirror dies partway through.
        real = dc._copy_and_hash
        calls = {"n": 0}

        def boom(src: Path, dst: Path) -> tuple[str, int]:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated container death mid-copy")
            return real(src, dst)

        _mk(work, "a.txt", "one-changed")
        _mk(work, "b.txt", "two-changed")
        dc._copy_and_hash = boom  # type: ignore[assignment]
        try:
            raised = False
            try:
                ck.mirror_now()
            except OSError:
                raised = True
            assert raised, "the failure must propagate, not be swallowed"
        finally:
            dc._copy_and_hash = real  # type: ignore[assignment]

        assert not dc.has_checkpoint(durable), "no manifest after a torn mirror"
        v = dc.verify(durable)
        assert not v.ok
        assert "no manifest" in v.reason


def test_corrupted_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        # Same length, different bytes: size checks alone would miss this.
        (durable / "a.txt").write_text("ALPHA", encoding="utf-8")
        v = dc.verify(durable)
        assert not v.ok
        assert "checksum mismatch" in v.reason


def test_truncated_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alphabet")
        _ckpt(work, durable).mirror_now()
        (durable / "a.txt").write_text("alph", encoding="utf-8")
        v = dc.verify(durable)
        assert not v.ok
        assert "size mismatch" in v.reason


def test_missing_file_fails_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "b.txt", "beta")
        _ckpt(work, durable).mirror_now()
        (durable / "b.txt").unlink()
        v = dc.verify(durable)
        assert not v.ok
        assert "missing file" in v.reason


def test_resume_refuses_and_hydrates_nothing_when_corrupt() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        (durable / "a.txt").write_text("ALPHA", encoding="utf-8")
        dc.clear_work_dir(work)
        try:
            dc.resume_into(durable, work)
        except dc.CheckpointError as exc:
            assert "refusing to resume" in str(exc)
        else:
            raise AssertionError("expected CheckpointError")
        assert not any(work.iterdir()), "must not half-hydrate a bad checkpoint"


def test_quick_verify_skips_hashes_but_still_catches_size() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        (durable / "a.txt").write_text("ALPHA", encoding="utf-8")
        assert dc.verify(durable, quick=True).ok, "quick cannot see equal-size edits"
        (durable / "a.txt").write_text("a", encoding="utf-8")
        assert not dc.verify(durable, quick=True).ok


def test_empty_and_bad_manifests_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _ckpt(work, durable).mirror_now()
        mp = dc.manifest_path(durable)
        mp.write_text("{not json", encoding="utf-8")
        assert "not valid JSON" in dc.verify(durable).reason
        mp.write_text('{"version": 99, "files": {}}', encoding="utf-8")
        assert "not supported" in dc.verify(durable).reason
        mp.write_text('{"version": 1, "files": {}}', encoding="utf-8")
        assert "lists no files" in dc.verify(durable).reason
        mp.write_text('{"version": 1, "files": {"a.txt": 3}}', encoding="utf-8")
        assert "not an object" in dc.verify(durable).reason


def test_verify_on_empty_durable_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        v = dc.verify(Path(tmp) / "never-written")
        assert not v.ok and "no manifest" in v.reason


# --------------------------------------------------------------------------- #
# Mirror behaviour                                                            #
# --------------------------------------------------------------------------- #


def test_unchanged_files_are_reused_not_recopied() -> None:
    """Hashing a multi-GB tree every tick is a cost worth not paying."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "b.txt", "beta")
        ck = _ckpt(work, durable)
        assert ck.mirror_now().copied == 2
        second = ck.mirror_now()
        assert second.copied == 0 and second.reused == 2
        assert second.bytes_copied == 0
        assert dc.verify(durable).ok


def test_changed_file_is_recopied() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        p = _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        # Bump mtime explicitly: a same-size rewrite inside one clock tick
        # would otherwise look unchanged.
        p.write_text("omega", encoding="utf-8")
        os.utime(p, ns=(time.time_ns(), time.time_ns() + 1_000_000))
        r = ck.mirror_now()
        assert r.copied == 1
        assert dc.verify(durable).ok
        assert (durable / "a.txt").read_text(encoding="utf-8") == "omega"


def test_deleted_file_is_pruned_from_the_mirror() -> None:
    """Otherwise a resumed job sees a directory that never existed."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        _mk(work, "gone.txt", "bye")
        ck = _ckpt(work, durable)
        ck.mirror_now()
        (work / "gone.txt").unlink()
        r = ck.mirror_now()
        assert r.removed == 1
        assert not (durable / "gone.txt").exists()
        assert dc.verify(durable).ok


def test_excludes_are_honoured() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "keep.txt", "k")
        _mk(work, "scratch.tmp", "junk")
        _mk(work, "logs/debug.log", "noise")
        r = _ckpt(work, durable, exclude=("*.tmp", "logs")).mirror_now()
        assert r.copied == 1
        assert (durable / "keep.txt").exists()
        assert not (durable / "scratch.tmp").exists()
        assert not (durable / "logs").exists()


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
            return  # Windows without developer mode; nothing to assert
        r = _ckpt(work, durable).mirror_now()
        assert r.copied == 1
        assert not (durable / "link.txt").exists()


def test_commit_hook_runs_after_the_manifest() -> None:
    """Order matters: the local durable dir must be self-consistent first."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        seen: list[bool] = []
        _ckpt(
            work, durable, commit=lambda: seen.append(dc.has_checkpoint(durable))
        ).mirror_now()
        assert seen == [True], "commit must see a written manifest"


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
                dc.DurableCheckpoint(
                    work, durable, interval_s=bad, handle_signals=False
                )
            except dc.CheckpointError as exc:
                assert "must be positive" in str(exc)
            else:
                raise AssertionError(f"expected CheckpointError for {bad}")


# --------------------------------------------------------------------------- #
# Lifecycle: timer, signals, failure isolation                                #
# --------------------------------------------------------------------------- #


def test_periodic_loop_mirrors_and_stop_takes_a_final() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=0.05)
        ck.start()
        deadline = time.time() + 5.0
        while ck.mirrors == 0 and time.time() < deadline:
            time.sleep(0.02)
        assert ck.mirrors >= 1, "the timer must fire"
        _mk(work, "late.txt", "written just before exit")
        ck.stop(final=True)
        assert dc.verify(durable).ok
        assert (durable / "late.txt").exists(), "stop() must capture late writes"


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
        assert dc.verify(durable).ok
        assert (durable / "during.txt").exists()


def test_signal_takes_a_final_checkpoint_and_chains() -> None:
    """Preemption sends a signal; the naive version loses everything since the
    last tick. The previous handler must still run afterwards."""
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=5)
        chained: list[int] = []
        ck._prev_handlers[signal.SIGTERM] = lambda signum, _f: chained.append(signum)
        _mk(work, "unsaved.txt", "since the last tick")
        ck._on_signal(signal.SIGTERM, None)
        assert dc.verify(durable).ok
        assert (durable / "unsaved.txt").exists(), "final checkpoint must capture it"
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


def test_signal_handler_failure_is_reported_not_raised() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work, durable = _dirs(tmp)
        _mk(work, "a.txt", "alpha")
        ck = _ckpt(work, durable, interval_s=5)
        real = dc._copy_and_hash

        def boom(src: Path, dst: Path) -> tuple[str, int]:
            raise OSError("no space left on device")

        dc._copy_and_hash = boom  # type: ignore[assignment]
        try:
            ck._on_signal(signal.SIGTERM, None)  # must not raise
            assert ck.failures >= 1
        finally:
            dc._copy_and_hash = real  # type: ignore[assignment]


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
    This module must stay provider-agnostic, so anything that could reach a
    provider API has to show up here first.
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
MIN_TESTS = 30


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
