#!/usr/bin/env python
"""EXECUTABLE SPEC for the checkpoint component of `longhaul`.

Not a test suite for this directory. This is a specification the implementer
codes against, written as six checks that each encode an ORDERING rather than an
assertion, plus a minimal fix for each so every requirement is demonstrated from
both sides.

HOW TO USE IT IN `longhaul`

Change one line — ``MODULE`` below — to the new module path. Everything else goes
through the public API (`DurableCheckpoint`, `generations`, `verify_generation`,
`latest_verified`, `resume_into`, `gen_dir`), so nothing here depends on this
directory's internals except the deliberate monkeypatches in the `fix_*`
functions, which exist only to prove each check is satisfiable.

    python spec_longhaul_checkpoint.py

prints a two-column matrix: the result with the defect present, and the result
with the minimal fix applied. A row reading `FAIL -> PASS` is a real regression
test. A row reading `PASS -> PASS` is a coverage gap being closed over behaviour
that already works, and is labelled as such rather than dressed up as a bug.

WHY THE CHECKS ARE NAMED AFTER ORDERINGS

The 38 tests on `7430bee97` all pass, and five of the six defects below are real.
The reason is a single structural gap: **the suite never ran a successful mirror
after an incomplete or failed one.** Every test was either a clean sequence or a
failure in isolation. So each check here is stated as a sequence, and the
sequence is in the function name, so a future reader cannot satisfy it by adding
another assertion about pruning to a clean-path test.

THE ONE-SENTENCE HISTORY THE IMPLEMENTER NEEDS

The in-place design lost everything to a cut-short final checkpoint. The
generations design replaced that with leaving exactly one copy — better, and
still broken. **The generations layout is correct in principle; the correctness
actually lives in the retention rule.** Check 1 is where that bites.

Stdlib only. Nothing here needs a cloud provider.

IN LONGHAUL (2026-10-30)

Copied from branch ``feat/durable-checkpoint`` at 522dbbf3 with ``MODULE`` pointed
at ``longhaul_checkpoint``. The checks and the fixes are unchanged. The runner
changed: by default it now requires every row to PASS against the implementation
and, two-sidedly, to behave as recorded against the frozen pre-fix module (rows
1-5 and 7 FAIL there, row 6 PASSES). The original as-is / with-fix matrix is
still available as ``--demonstrate-fixes``.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

# ─────────────────────────── THE ONE LINE TO CHANGE ───────────────────────────
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
MODULE = "longhaul_checkpoint"
#: The pre-fix module (durable-checkpoint at 7430bee97, frozen as a fixture), so
#: every run also proves each row still fails where the defect is present.
PRE_FIX_MODULE = "fixtures.durable_checkpoint_pre_longhaul"
# ──────────────────────────────────────────────────────────────────────────────

import importlib  # noqa: E402

dc = importlib.import_module(MODULE)
IMPLEMENTATION = dc


# ╭──────────────────────────── helpers ────────────────────────────╮


def _ckpt(work: Path, durable: Path, **kw):
    kw.setdefault("handle_signals", False)
    kw.setdefault("logger", lambda _m: None)
    return dc.DurableCheckpoint(work, durable, **kw)


def _write(p: Path, text: str) -> None:
    """Write and force a visibly newer mtime, so the incremental check sees it."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    now = time.time_ns()
    os.utime(p, ns=(now, now + 7_000_000))


def _loadable(durable: Path) -> list[int]:
    return [g for g in dc.generations(durable) if dc.verify_generation(durable, g).ok]


def _tear(durable: Path, n: int) -> None:
    """Fabricate the on-disk shape a container killed mid-generation leaves:
    a numbered directory with files and NO manifest."""
    g = dc.gen_dir(durable, n)
    g.mkdir(parents=True, exist_ok=True)
    (g / "state.ckpt").write_text("torn", encoding="utf-8")


# ╭──────────────── 1. retention must count only LOADABLE copies ────────────────╮


def check_1_torn_generation_then_successful_mirror_keeps_two_loadable() -> str:
    """ORDERING: good, good, torn, then a SUCCESSFUL mirror.

    REQUIREMENT: after that mirror, at least two generations must verify.

    Reproduced on `7430bee97`: retention keeps the newest `keep-1` by NUMBER, so
    the torn directory takes the retained slot and the last good copy — the one
    the process just resumed from — is deleted. Repeated preemption converges to
    a single loadable copy, which is the failure the layout exists to prevent.
    """
    with tempfile.TemporaryDirectory() as t:
        work, durable = Path(t) / "w", Path(t) / "d"
        work.mkdir()
        ck = _ckpt(work, durable, keep_generations=2)
        _write(work / "state.ckpt", "v1")
        ck.mirror_now()
        _write(work / "state.ckpt", "v2")
        ck.mirror_now()
        _tear(durable, max(dc.generations(durable)) + 1)
        resumed_from, _ = dc.latest_verified(durable)
        _write(work / "state.ckpt", "v3")
        ck.mirror_now()
        loadable = _loadable(durable)
        if len(loadable) < 2:
            return (
                f"only {len(loadable)} loadable generation(s) {loadable}; "
                f"gen{resumed_from} (the one resumed from) was pruned while the "
                f"torn directory kept its slot"
            )
        if resumed_from not in loadable and resumed_from is not None:
            return f"gen{resumed_from} was resumed from and then deleted"
        return ""


@contextlib.contextmanager
def fix_1():
    """MINIMAL FIX: count only generations that verify toward the floor, and
    treat unverifiable ones older than the newest as garbage to delete."""
    original = dc.DurableCheckpoint._prune_generations

    def patched(self, keep_newest: int):
        removed = []
        others = [g for g in dc.generations(self.durable) if g != keep_newest]
        good = [
            g for g in others if dc.verify_generation(self.durable, g, quick=True).ok
        ]
        junk = [g for g in others if g not in good and g < keep_newest]
        keep_good = (
            good[-(self.keep_generations - 1) :] if self.keep_generations > 1 else []
        )
        for g in junk + [g for g in good if g not in keep_good]:
            try:
                import shutil

                shutil.rmtree(dc.gen_dir(self.durable, g))
                removed.append(g)
            except OSError:
                pass
        return tuple(sorted(removed))

    dc.DurableCheckpoint._prune_generations = patched
    try:
        yield
    finally:
        dc.DurableCheckpoint._prune_generations = original


# ╭───────────── 2. a failed read-back must not propagate forward ─────────────╮


def check_2_failed_readback_then_successful_mirror_stops_propagation() -> str:
    """ORDERING: good mirror, same-size corruption, mirror whose read-back FAILS,
    then a successful mirror.

    REQUIREMENT: the corrupted bytes must not survive into the newest generation,
    and the known-good older generation must still verify.

    On `7430bee97` the link base comes from `latest_verified(quick=True)` — size
    only — and the old hash is carried over, so a same-size corruption is
    hardlinked forward through a shared inode. A failed read-back is logged but
    the mirror still counts as a success, which makes one corruption permanent.
    """
    with tempfile.TemporaryDirectory() as t:
        work, durable = Path(t) / "w", Path(t) / "d"
        work.mkdir()
        ck = _ckpt(work, durable, keep_generations=4)
        _write(work / "state.ckpt", "GOOD-CONTENT")
        ck.mirror_now()
        first = max(dc.generations(durable))
        # Same-size corruption inside the durable copy: quick verify cannot see it.
        (dc.gen_dir(durable, first) / "state.ckpt").write_text(
            "BAD!-CONTENT", encoding="utf-8"
        )
        ck.mirror_now()  # link base is the corrupt generation
        ck.mirror_now()
        newest = max(dc.generations(durable))
        got = (dc.gen_dir(durable, newest) / "state.ckpt").read_text(encoding="utf-8")
        if got != "GOOD-CONTENT":
            return (
                f"newest generation holds {got!r}: the corruption was carried "
                f"forward instead of being recopied from scratch"
            )
        return ""


@contextlib.contextmanager
def fix_2():
    """MINIMAL FIX: never link from a generation that has not passed a FULL
    verify. The real implementation should remember the generation this process
    last read back successfully rather than re-deriving it with ``quick=True``."""
    original = dc.DurableCheckpoint._try_link

    def patched(self, src: Path, dst: Path) -> bool:
        try:
            gen_root = src.parent
            while gen_root.parent != Path(self.durable) and gen_root.parent != gen_root:
                gen_root = gen_root.parent
            n = int(gen_root.name.removeprefix(dc.GEN_PREFIX))
        except (ValueError, AttributeError):
            return False
        if not dc.verify_generation(self.durable, n, quick=False).ok:
            return False
        return original(self, src, dst)

    dc.DurableCheckpoint._try_link = patched
    try:
        yield
    finally:
        dc.DurableCheckpoint._try_link = original


# ╭──────────── 3. a signal during a mirror must not deadlock ────────────╮


def check_3_signal_while_a_mirror_holds_the_lock_does_not_deadlock() -> str:
    """ORDERING: a mirror is in progress on THIS thread, then a signal arrives.

    REQUIREMENT: the handler must return promptly. It must not block on the
    non-reentrant lock the same thread already holds.

    On `7430bee97` ``_on_signal`` calls ``mirror_now()`` unconditionally on a
    plain ``threading.Lock``; same-thread re-entry deadlocks outright, and
    timer-thread contention blocks for the length of a mirror, which on a large
    tree exceeds the grace window.
    """
    # NOTE ON WHAT IS AND IS NOT EXERCISED HERE. The same-thread case — the
    # handler firing while THIS thread is inside mirror_now() — is a hard hang on
    # a non-reentrant lock, so exercising it in-process would wedge the spec run
    # itself and leave a thread holding the durable dir (an earlier draft of this
    # check did exactly that, and the temp-dir teardown then masked the result
    # with WinError 145). What is exercised is the contention case the reviewer
    # confirmed: a mirror in progress on the TIMER thread. Both have the same fix,
    # and this one is deterministic and cleans up.
    HOLD = 2.0
    BUDGET = 1.0
    t = tempfile.mkdtemp(prefix="spec3-")
    try:
        work, durable = Path(t) / "w", Path(t) / "d"
        work.mkdir()
        _write(work / "state.ckpt", "v1")
        ck = _ckpt(work, durable, keep_generations=2)
        ck._prev_handlers[signal.SIGTERM] = lambda *_a: None
        holding = threading.Event()

        def hold_the_lock() -> None:
            with ck._lock:
                holding.set()
                time.sleep(HOLD)

        th = threading.Thread(target=hold_the_lock, daemon=True)
        th.start()
        holding.wait(timeout=5.0)
        started = time.monotonic()
        ck._on_signal(signal.SIGTERM, None)
        elapsed = time.monotonic() - started
        th.join(timeout=HOLD + 3.0)
        if elapsed >= BUDGET:
            return (
                f"the signal handler blocked {elapsed:.2f}s waiting on a lock a "
                f"mirror already held (budget {BUDGET:.1f}s). On a large tree the "
                f"wait is the length of a mirror, which outlives the grace window, "
                f"so the final checkpoint is lost and further signals cannot stop "
                f"the process"
            )
        return ""
    finally:
        import shutil

        shutil.rmtree(t, ignore_errors=True)


#: How long a signal handler may wait for the mirror lock before giving up on
#: taking a final checkpoint. Anything unbounded outlives the grace window.
SIGNAL_LOCK_BUDGET_S = 0.25


@contextlib.contextmanager
def fix_3():
    """MINIMAL FIX: the handler acquires the mirror lock with a BOUNDED timeout
    and skips the final checkpoint if it cannot get it, rather than blocking.

    An earlier draft of this fix tracked the mirror's owning thread in a flag.
    That is strictly weaker and this spec proved it: the flag only sees mirrors
    started through ``mirror_now()``, so any other holder of the lock still
    blocks the handler indefinitely. A bounded acquire is both simpler and
    independent of who holds it — which is the property that actually matters,
    since the handler must return within the grace window no matter what the
    rest of the process is doing. Skipping a final checkpoint costs one interval;
    blocking past the grace window costs the process's ability to die.
    """
    original_signal = dc.DurableCheckpoint._on_signal

    def on_signal(self, signum, frame):
        if not self._lock.acquire(timeout=SIGNAL_LOCK_BUDGET_S):
            self._say(
                f"signal {signum}: a mirror is in flight and the lock did not free "
                f"within {SIGNAL_LOCK_BUDGET_S}s; skipping the final checkpoint so "
                f"the signal is not swallowed"
            )
            self._stop.set()
            prev = self._prev_handlers.get(signum)
            if callable(prev):
                prev(signum, frame)
            return None
        self._lock.release()
        return original_signal(self, signum, frame)

    dc.DurableCheckpoint._on_signal = on_signal
    try:
        yield
    finally:
        dc.DurableCheckpoint._on_signal = original_signal


# ╭────────── 4. a damaged manifest must fall back, never raise ──────────╮


def check_4_damaged_manifest_then_resume_falls_back_instead_of_raising() -> str:
    """ORDERING: two good generations, the newest manifest is damaged in four
    different ways in turn, then resume and a further mirror are attempted.

    REQUIREMENT: every damage shape degrades to a refusal of THAT generation and
    a fallback to the older one. Nothing may escape as an exception.

    On `7430bee97` only ``CheckpointError`` is caught, so ``OSError``,
    ``UnicodeDecodeError``, ``ValueError`` and ``TypeError`` escape
    ``latest_verified`` and break resume AND every future mirror even though an
    older generation is intact. The ``created`` parse sits outside the per-file
    try, which is one of the reachable paths.
    """
    damages = {
        "invalid utf-8 bytes": lambda p: p.write_bytes(b'{"version": 2, \xff\xfe}'),
        "created is a dict": lambda p: p.write_text(
            json.dumps(
                {
                    "version": 2,
                    "created": {},
                    "files": {"a": {"sha256": "x", "size": 1}},
                }
            ),
            encoding="utf-8",
        ),
        "size is not a number": lambda p: p.write_text(
            json.dumps(
                {
                    "version": 2,
                    "created": 1.0,
                    "files": {"a": {"sha256": "x", "size": "big"}},
                }
            ),
            encoding="utf-8",
        ),
        "files is a list": lambda p: p.write_text(
            json.dumps({"version": 2, "created": 1.0, "files": []}), encoding="utf-8"
        ),
    }
    problems = []
    for label, damage in damages.items():
        with tempfile.TemporaryDirectory() as t:
            work, durable = Path(t) / "w", Path(t) / "d"
            work.mkdir()
            ck = _ckpt(work, durable, keep_generations=3)
            _write(work / "state.ckpt", "v1")
            ck.mirror_now()
            _write(work / "state.ckpt", "v2")
            ck.mirror_now()
            newest = max(dc.generations(durable))
            damage(dc.manifest_path(durable, newest))
            try:
                n, _ = dc.latest_verified(durable)
                if n is None:
                    problems.append(
                        f"{label}: no fallback although an older generation is intact"
                    )
                dc.resume_into(durable, Path(t) / "w2")
            except dc.CheckpointError:
                problems.append(f"{label}: refused outright instead of falling back")
            except Exception as exc:  # noqa: BLE001 - the point of the check
                problems.append(f"{label}: escaped as {type(exc).__name__}: {exc}")
    return "; ".join(problems)


@contextlib.contextmanager
def fix_4():
    """MINIMAL FIX: treat any malformed manifest or unreadable file as a refusal
    of that generation, not as an exception for the caller to handle."""
    original = dc.verify_generation

    def patched(durable_dir, n, quick=False):
        try:
            return original(durable_dir, n, quick=quick)
        except dc.CheckpointError as exc:
            return dc.VerifyResult(False, str(exc), generation=n)
        except (
            OSError,
            ValueError,
            TypeError,
            UnicodeDecodeError,
            OverflowError,
        ) as exc:
            return dc.VerifyResult(
                False,
                f"unreadable manifest ({type(exc).__name__}: {exc})",
                generation=n,
            )

    dc.verify_generation = patched
    try:
        yield
    finally:
        dc.verify_generation = original


# ╭────────── 5. one signal, one final, and no pruning on that path ──────────╮


def check_5_one_signal_writes_one_final_and_never_prunes() -> str:
    """ORDERING: a context-managed run, then ONE signal, then normal unwind.

    REQUIREMENT: exactly one final mirror, and no generation deleted on the
    signal path. Pruning there can remove the last intact pre-signal copy, and a
    full read-back inside a 30 s grace window starves the job's own shutdown.
    """
    with tempfile.TemporaryDirectory() as t:
        work, durable = Path(t) / "w", Path(t) / "d"
        work.mkdir()
        _write(work / "state.ckpt", "v1")
        ck = _ckpt(work, durable, keep_generations=2, interval_s=3600)
        ck.mirror_now()
        before = set(dc.generations(durable))
        ck._prev_handlers[signal.SIGTERM] = lambda *_a: None
        mirrors_before = ck.mirrors
        ck._on_signal(signal.SIGTERM, None)
        ck.stop(final=True)
        finals = ck.mirrors - mirrors_before
        after = set(dc.generations(durable))
        problems = []
        if finals > 1:
            problems.append(f"{finals} final mirrors for one signal (expected 1)")
        deleted = before - after
        if deleted:
            problems.append(f"the signal path deleted generation(s) {sorted(deleted)}")
        return "; ".join(problems)


@contextlib.contextmanager
def fix_5():
    """MINIMAL FIX: mark the signal final as done so the unwind does not repeat
    it, and never prune from a signal-driven or stop-driven final."""
    original_signal = dc.DurableCheckpoint._on_signal
    original_stop = dc.DurableCheckpoint.stop
    original_prune = dc.DurableCheckpoint._prune_generations

    def no_prune(self, keep_newest):
        return ()

    def on_signal(self, signum, frame):
        self._final_done = True
        dc.DurableCheckpoint._prune_generations = no_prune
        try:
            return original_signal(self, signum, frame)
        finally:
            dc.DurableCheckpoint._prune_generations = original_prune

    def stop(self, final=True):
        if getattr(self, "_final_done", False):
            final = False
        return original_stop(self, final=final)

    dc.DurableCheckpoint._on_signal = on_signal
    dc.DurableCheckpoint.stop = stop
    try:
        yield
    finally:
        dc.DurableCheckpoint._on_signal = original_signal
        dc.DurableCheckpoint.stop = original_stop
        dc.DurableCheckpoint._prune_generations = original_prune


# ╭────────── 6. real signals: install, restore, chain, re-raise ──────────╮


def check_6_real_signal_installs_restores_and_chains() -> str:
    """ORDERING: install handlers via start(), deliver a REAL signal, then stop().

    REQUIREMENT: start() installs, the delivered signal runs our handler, the
    previously installed handler still runs, and stop() restores it.

    This one is expected to PASS on `7430bee97`. It is a COVERAGE GAP being
    closed, not a defect: the 38 tests never install a handler or deliver a
    signal — the helper forces ``handle_signals=False`` and the two signal tests
    call ``_on_signal`` directly with a hand-filled ``_prev_handlers``. The
    `quality.yml` step comment nonetheless claimed this path was gated. Keep this
    check so that claim becomes true.
    """
    if threading.current_thread() is not threading.main_thread():
        return "SKIP: signal handlers can only be installed from the main thread"
    with tempfile.TemporaryDirectory() as t:
        work, durable = Path(t) / "w", Path(t) / "d"
        work.mkdir()
        _write(work / "state.ckpt", "v1")
        seen: list[int] = []
        sentinel = lambda signum, _f: seen.append(signum)  # noqa: E731
        previous = signal.signal(signal.SIGTERM, sentinel)
        problems = []
        try:
            ck = _ckpt(work, durable, handle_signals=True, interval_s=3600)
            ck.start()
            if signal.getsignal(signal.SIGTERM) is sentinel:
                problems.append("start() did not install a handler")
            signal.raise_signal(signal.SIGTERM)
            if not dc.latest_verified(durable)[1].ok:
                problems.append("the delivered signal produced no loadable generation")
            if seen != [signal.SIGTERM]:
                problems.append(f"the previous handler did not run (saw {seen})")
            ck.stop(final=False)
            if signal.getsignal(signal.SIGTERM) is not sentinel:
                problems.append("stop() did not restore the previous handler")
        finally:
            signal.signal(signal.SIGTERM, previous)
        return "; ".join(problems)


@contextlib.contextmanager
def fix_6():
    """No fix: the behaviour already works, it was simply never exercised."""
    yield


# ╭──────────────────────────── the runner ────────────────────────────╮


def check_7_resume_then_mirror_matches_an_uninterrupted_baseline() -> str:
    """ORDERING: mirror, interrupt, resume, mirror — differentialled against the
    same sequence WITHOUT the interrupt.

    REQUIREMENT: the mirror after a resume must behave as it would have without
    one. Same retained loadable count, and no re-copying of content that is
    byte-identical to the previous generation.

    This row exists because rows 1-6 each assert against a FIXED expectation, and
    none compares resumed behaviour against an uninterrupted baseline. That
    differential is its own test shape, and it is the shape that catches a resume
    which preserves the DATA while corrupting state DERIVED from it. A third
    independent instance of that class turned up elsewhere in this estate the same
    week: a checker whose per-level counters diverged only on the one run that was
    preempted, with the liveness watchdog firing NO events — because a silently
    mis-accounting resume looks exactly like a healthy one.

    THE CONCRETE DEFECT, and it is not cosmetic. ``resume_into`` rewrites every
    file, so every mtime differs from the manifest that described it. The reuse
    predicate is ``(size, mtime_ns)``, so the first tick after ANY resume
    re-copies the entire tree and hardlinks nothing. On the 15 GB tree this design
    exists for, that silently turns each preemption into a full rewrite — the
    opposite of the README's cost claim, and worst exactly when the job has just
    lost time to a preemption.
    """

    def one_run(root: Path, interrupt: bool) -> tuple[int, int, int]:
        work, durable = root / "w", root / "d"
        work.mkdir(parents=True)
        for i in range(3):
            _write(work / f"f{i}.ckpt", f"payload {i}")
        ck = _ckpt(work, durable, keep_generations=3)
        ck.mirror_now()
        if interrupt:
            # The container died and came back: scratch is gone, rehydrate it.
            dc.clear_work_dir(work)
            dc.resume_into(durable, work)
        r = ck.mirror_now()
        return r.copied, r.linked, len(_loadable(durable))

    base = tempfile.mkdtemp(prefix="spec7-base-")
    resumed = tempfile.mkdtemp(prefix="spec7-resume-")
    try:
        b_copied, b_linked, b_loadable = one_run(Path(base), interrupt=False)
        r_copied, r_linked, r_loadable = one_run(Path(resumed), interrupt=True)
        problems = []
        if b_linked and not r_linked:
            problems.append(
                f"uninterrupted linked {b_linked} unchanged file(s) and copied "
                f"{b_copied}; after a resume it linked {r_linked} and copied "
                f"{r_copied} — the whole tree is re-copied because resume_into "
                f"rewrote every mtime"
            )
        elif (r_copied, r_linked) != (b_copied, b_linked):
            problems.append(
                f"copy/link decision diverged: uninterrupted (copied={b_copied}, "
                f"linked={b_linked}) vs resumed (copied={r_copied}, "
                f"linked={r_linked})"
            )
        if r_loadable != b_loadable:
            problems.append(
                f"retained loadable generations diverged: uninterrupted "
                f"{b_loadable} vs resumed {r_loadable}"
            )
        return "; ".join(problems)
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(resumed, ignore_errors=True)


@contextlib.contextmanager
def fix_7():
    """MINIMAL FIX, and note WHERE it belongs: in ``resume_into``, not in the
    reuse predicate.

    The manifest already records ``mtime_ns`` for every file it describes, so a
    hydrate can restore the mtimes of the tree it is reconstructing instead of
    stamping every file with 'now'. Then the existing ``(size, mtime_ns)``
    predicate is simply correct again and the next mirror links as it would have.

    The alternative — teaching the predicate to fall back to hashing when the
    mtime differs but the size matches — costs a full read of the tree on exactly
    the tick that is already recovering from a preemption. Restoring metadata that
    was always in the manifest is cheaper and more honest: the resumed tree IS the
    recorded tree, so it should carry the recorded mtimes.
    """
    original = dc.resume_into

    def patched(durable_dir, work_dir, quick=False):
        result = original(durable_dir, work_dir, quick=quick)
        man = dc._Manifest.from_json(
            dc.manifest_path(durable_dir, result.generation).read_text(encoding="utf-8")
        )
        for rel, rec in man.files.items():
            target = Path(work_dir) / rel
            if target.is_file() and rec.mtime_ns:
                os.utime(target, ns=(rec.mtime_ns, rec.mtime_ns))
        return result

    dc.resume_into = patched
    try:
        yield
    finally:
        dc.resume_into = original


CHECKS = [
    (
        "1 retention counts only loadable",
        check_1_torn_generation_then_successful_mirror_keeps_two_loadable,
        fix_1,
        True,
    ),
    (
        "2 failed read-back stops propagation",
        check_2_failed_readback_then_successful_mirror_stops_propagation,
        fix_2,
        True,
    ),
    (
        "3 signal during mirror no deadlock",
        check_3_signal_while_a_mirror_holds_the_lock_does_not_deadlock,
        fix_3,
        True,
    ),
    (
        "4 damaged manifest falls back",
        check_4_damaged_manifest_then_resume_falls_back_instead_of_raising,
        fix_4,
        True,
    ),
    (
        "5 one signal, one final, no prune",
        check_5_one_signal_writes_one_final_and_never_prunes,
        fix_5,
        True,
    ),
    (
        "6 real signal install/restore/chain",
        check_6_real_signal_installs_restores_and_chains,
        fix_6,
        False,
    ),
    (
        "7 post-resume matches uninterrupted",
        check_7_resume_then_mirror_matches_an_uninterrupted_baseline,
        fix_7,
        True,
    ),
]

CANNOT_TEST = """
WHAT THIS SPEC DOES NOT COVER, AND WHY

* **Modal Volume semantics.** Every check runs on a local filesystem. The volume
  docs promise no atomic rename, durability only on commit, background commits
  "every few seconds", and v2 is beta and "may lose data". None of that is
  reproducible here, so the design must not depend on rename atomicity — which is
  why "highest generation that verifies" is the pointer. Verifying that property
  against a real volume needs a live account and is out of scope for a spec.
* **fsync ordering.** There is no `fsync` anywhere in the implementation, so with
  `commit=None` and a local durable dir a prune can reach disk before the data it
  depends on. Demonstrating that needs a crash-consistency harness (a VM snapshot
  or a device-level fault injector), not a temp dir.
* **The stat-before-copy race.** The unchanged-file predicate reads `(size,
  mtime_ns)` before copying, so a file written DURING the copy records a stale
  mtime and is skipped next tick. Reproducing it reliably needs a writer racing
  the mirror at a controlled offset; it is real, and it is cheaper to fix than to
  test.
* **Real preemption.** `signal.raise_signal` is not a container kill. Check 3
  approximates the dangerous case with lock contention; it cannot reproduce a
  `TerminateProcess` mid-write.
* **Manifest path escapes.** `..`, absolute paths and case-collision entries are
  not validated. A malicious manifest is out of threat model (we write it), so
  this is defence in depth and is listed rather than tested.
"""


def _run(check) -> str:
    try:
        return check()
    except Exception as exc:  # noqa: BLE001
        return f"raised {type(exc).__name__}: {exc}"


def _use(module) -> None:
    global dc
    dc = module


def demonstrate_fixes() -> int:
    """The original two-column matrix, against the frozen pre-fix module."""
    _use(importlib.import_module(PRE_FIX_MODULE))
    try:
        print(f"{'check':<40} {'as-is':<10} {'with fix':<10} verdict")
        print("-" * 78)
        bad = 0
        for name, check, fix, expect_fail_asis in CHECKS:
            asis = _run(check)
            with fix():
                fixed = _run(check)
            a = "PASS" if not asis else "FAIL"
            f = "PASS" if not fixed else "FAIL"
            ok = (a == "FAIL" if expect_fail_asis else a == "PASS") and f == "PASS"
            bad += not ok
            verdict = (
                ("two-sided OK" if expect_fail_asis else "coverage gap")
                if ok
                else "SPEC PROBLEM"
            )
            print(f"{name:<40} {a:<10} {f:<10} {verdict}")
        return 1 if bad else 0
    finally:
        _use(IMPLEMENTATION)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--demonstrate-fixes"]:
        return demonstrate_fixes()
    if argv:
        print("usage: spec_longhaul_checkpoint.py [--demonstrate-fixes]")
        return 2
    print(f"EXECUTABLE SPEC — checkpoint component of longhaul (module: {MODULE})\n")
    pre_fix = importlib.import_module(PRE_FIX_MODULE)
    print(f"{'check':<40} {'longhaul':<10} {'pre-fix':<10} verdict")
    print("-" * 78)
    rows = []
    for name, check, _fix, expect_fail_asis in CHECKS:
        _use(IMPLEMENTATION)
        now = _run(check)
        _use(pre_fix)
        try:
            before = _run(check)
        finally:
            _use(IMPLEMENTATION)
        n = "PASS" if not now else "FAIL"
        b = "PASS" if not before else "FAIL"
        if n != "PASS":
            verdict = "IMPLEMENTATION FAILS"
        elif expect_fail_asis and b != "FAIL":
            verdict = "NOT TWO-SIDED"
        elif not expect_fail_asis and b != "PASS":
            verdict = "PRE-FIX REGRESSED"
        else:
            verdict = "regression test" if expect_fail_asis else "coverage gap closed"
        rows.append((name, verdict, now, before))
        print(f"{name:<40} {n:<10} {b:<10} {verdict}")
    print()
    for name, verdict, now, before in rows:
        if now:
            print(f"[{name}] longhaul: {now}")
        elif before:
            print(f"[{name}] pre-fix: {before}")
    print(CANNOT_TEST)
    bad = [r for r in rows if r[1] not in ("regression test", "coverage gap closed")]
    passed = sum(1 for r in rows if not r[2])
    if bad:
        print(f"RESULT: FAIL  ({len(bad)} row(s): {', '.join(r[0] for r in bad)})")
        return 1
    print(
        f"RESULT: PASS  ({passed}/{len(rows)} rows pass on longhaul; the pre-fix module fails the "
        f"{sum(1 for c in CHECKS if c[3])} it should)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
