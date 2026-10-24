#!/usr/bin/env python
"""durable-checkpoint — keep a long job's state alive across interruption.

The problem it solves: a job runs for longer than its container is guaranteed to
live. A Modal function caps at 24h, a connected FEP+ map is 12-27h, preemptible
GPUs disappear with a signal and a few seconds' notice, and laptops lose power.
The job's working directory is on fast local scratch (a network/volume
filesystem is usually too slow and too loosely consistent for MD-style I/O), so
when the container dies that scratch dies with it.

The pattern: run in fast scratch, mirror to a durable path periodically, and on
re-invocation resume from the mirror instead of starting over.

This module is the mirror, hardened. It is deliberately provider-agnostic: the
durable path is just a directory, and anything that needs doing after a mirror
(committing a mounted volume, say) is a callable you pass in. Nothing here
imports a cloud SDK, knows about accounts, or moves state between them.

WHAT THIS FIXES RELATIVE TO THE NAIVE VERSION

A first cut of this pattern usually looks like `cp -a work/. durable/` on a
timer, and it has three defects that cost real GPU time:

1. **The copy is not atomic.** Killed mid-copy, the durable path holds a torn
   mix of old and new files — and a validity sentinel written earlier is still
   sitting there, so the next run happily loads the wreckage. This exact failure
   is on record in the source program: resumes died with "Bad checkpoints,
   `ckpt_is_valid` missing after mid-write kill". Here, every file lands via
   write-temp-then-`os.replace`, and the manifest that makes a checkpoint
   loadable is written LAST and removed FIRST. A mirror interrupted at any point
   leaves no manifest, so :func:`verify` refuses it. You lose the resume, but
   you are told, instead of burning another day on corrupt state.

2. **No final checkpoint on the way out.** Preemption sends SIGINT (SIGTERM on
   many other platforms) before the container goes. With only a periodic timer,
   everything since the last tick is discarded for free. :meth:`start` installs
   handlers that take one last incremental mirror first.

3. **Resume trusts whatever it finds.** `sorted(glob(...))[-1]` is
   lexicographic, not newest, and globbing the scratch dir after a copy that
   ignored its own exit status raises IndexError on an empty list rather than
   reporting a bad resume. Here :func:`resume_into` verifies every file in the
   manifest by size and hash before a single byte is hydrated, and fails closed.

A TRAP WORTH KNOWING BEFORE YOU AUTOMATE RESTARTS
(measured by this estate's fractal-compute steward, not by me)

If a call's input status reads FAILURE while ``FunctionCall.get(timeout=0)``
still raises ``TimeoutError``, the platform is **mid-restart after preemption**;
delays of 13-20 minutes were observed. Cancelling there kills a live restart and
throws away the work it was about to resume. Only re-spawn once ``get()`` raises
a real error. Any supervisor built around this module should respect that.

COST NOTE

Hashes are computed during the mirror, in the same pass that reads a file to
copy it, so hashing is close to free. Unchanged files keep their previous hash
from the old manifest rather than being re-read. That matters on a
thermally-limited machine: a full re-hash of a multi-gigabyte job directory
every ten minutes is a cost you do not need to pay.

Stdlib only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "MANIFEST.durable-checkpoint.json"
MANIFEST_VERSION = 1
DEFAULT_INTERVAL_S = 600.0
_CHUNK = 1 << 20  # 1 MiB; big enough to be efficient, small enough to be kind


class CheckpointError(Exception):
    """A checkpoint operation failed. Message is fit for an operator."""


@dataclass(frozen=True)
class FileRecord:
    sha256: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class MirrorResult:
    copied: int
    reused: int
    removed: int
    bytes_copied: int
    seconds: float
    manifest_path: str


@dataclass(frozen=True)
class VerifyResult:
    """``ok`` is the only thing a caller should branch on. ``reason`` explains."""

    ok: bool
    reason: str
    files: int = 0
    extras: tuple[str, ...] = ()
    created: float = 0.0

    def __bool__(self) -> bool:
        return self.ok


@dataclass(frozen=True)
class ResumeResult:
    hydrated: int
    bytes_written: int
    verify: VerifyResult


@dataclass
class _Manifest:
    version: int = MANIFEST_VERSION
    created: float = 0.0
    files: dict[str, FileRecord] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "created": self.created,
                "files": {
                    k: {"sha256": v.sha256, "size": v.size, "mtime_ns": v.mtime_ns}
                    for k, v in sorted(self.files.items())
                },
            },
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def from_json(text: str) -> _Manifest:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"manifest is not valid JSON: {exc}") from None
        if not isinstance(raw, dict):
            raise CheckpointError("manifest is not a JSON object")
        version = raw.get("version")
        if version != MANIFEST_VERSION:
            raise CheckpointError(
                f"manifest version {version!r} is not supported "
                f"(this build writes and reads {MANIFEST_VERSION})"
            )
        files_raw = raw.get("files")
        if not isinstance(files_raw, dict):
            raise CheckpointError("manifest.files is missing or not an object")
        files: dict[str, FileRecord] = {}
        for rel, rec in files_raw.items():
            if not isinstance(rec, dict):
                raise CheckpointError(f"manifest.files[{rel!r}] is not an object")
            try:
                files[rel] = FileRecord(
                    sha256=str(rec["sha256"]),
                    size=int(rec["size"]),
                    mtime_ns=int(rec.get("mtime_ns") or 0),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise CheckpointError(
                    f"manifest.files[{rel!r}] is malformed: {exc}"
                ) from None
        return _Manifest(
            version=MANIFEST_VERSION,
            created=float(raw.get("created") or 0.0),
            files=files,
        )


# --------------------------------------------------------------------------- #
# Primitives                                                                  #
# --------------------------------------------------------------------------- #


def _atomic_write_text(path: Path, text: str) -> None:
    """Write via a sibling temp file then rename, so readers never see a partial.

    The temp file is a sibling so the rename stays within one filesystem, which
    is what makes it atomic.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _copy_and_hash(src: Path, dst: Path) -> tuple[str, int]:
    """Copy src to dst atomically, returning (sha256, bytes). Hash in one pass."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    digest = hashlib.sha256()
    total = 0
    try:
        with src.open("rb") as rf, tmp.open("wb") as wf:
            while True:
                chunk = rf.read(_CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
                wf.write(chunk)
                total += len(chunk)
        os.replace(tmp, dst)
    except BaseException:
        # Never leave a stray temp behind: a dot-prefixed orphan in the durable
        # path would be mistaken for junk, or worse, counted as an extra file.
        tmp.unlink(missing_ok=True)
        raise
    return digest.hexdigest(), total


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _iter_files(root: Path, exclude: tuple[str, ...]) -> list[Path]:
    """Every regular file under root, relative-path sorted, excludes applied.

    Symlinks are skipped rather than followed: following them can copy a whole
    tree from outside the job directory, or loop.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel_dir = d.relative_to(root)
        dirnames[:] = [
            n
            for n in dirnames
            if not _excluded(str((rel_dir / n).as_posix()), exclude)
            and not (d / n).is_symlink()
        ]
        for name in filenames:
            p = d / name
            rel = (rel_dir / name).as_posix()
            if rel == MANIFEST_NAME or _excluded(rel, exclude):
                continue
            if p.is_symlink() or not p.is_file():
                continue
            out.append(p)
    out.sort()
    return out


def _excluded(rel: str, exclude: tuple[str, ...]) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat) for pat in exclude
    )


# --------------------------------------------------------------------------- #
# Verify and resume                                                           #
# --------------------------------------------------------------------------- #


def manifest_path(durable_dir: str | Path) -> Path:
    return Path(durable_dir) / MANIFEST_NAME


def has_checkpoint(durable_dir: str | Path) -> bool:
    """Cheap presence test. Says nothing about integrity — use :func:`verify`."""
    return manifest_path(durable_dir).is_file()


def verify(durable_dir: str | Path, quick: bool = False) -> VerifyResult:
    """Is the durable copy loadable? Fails closed on anything unexpected.

    ``quick`` checks size and mtime only, skipping hashes — useful for a cheap
    liveness poll on a huge directory. Do not resume on a quick pass alone: the
    corruption this guards against is exactly the kind that preserves size.
    """
    durable = Path(durable_dir)
    mpath = manifest_path(durable)
    if not mpath.is_file():
        # The ordinary "no checkpoint yet" case AND the "interrupted mid-mirror"
        # case both land here, which is the point: both are unsafe to load.
        return VerifyResult(False, "no manifest: nothing complete to resume from")
    try:
        man = _Manifest.from_json(mpath.read_text(encoding="utf-8"))
    except CheckpointError as exc:
        return VerifyResult(False, str(exc))
    if not man.files:
        return VerifyResult(False, "manifest lists no files")

    for rel, rec in sorted(man.files.items()):
        p = durable / rel
        if not p.is_file():
            return VerifyResult(False, f"missing file from manifest: {rel}")
        stat = p.stat()
        if stat.st_size != rec.size:
            return VerifyResult(
                False, f"size mismatch on {rel}: {stat.st_size} != {rec.size}"
            )
        if quick:
            continue
        got, _ = _hash_file(p)
        if got != rec.sha256:
            return VerifyResult(False, f"checksum mismatch on {rel}")

    on_disk = {str(p.relative_to(durable).as_posix()) for p in _iter_files(durable, ())}
    # Extras are reported, not fatal: a stray log beside a good checkpoint is
    # not a reason to refuse a resume that would otherwise succeed.
    extras = tuple(sorted(on_disk - set(man.files)))
    return VerifyResult(
        True,
        "ok" if not extras else f"ok ({len(extras)} file(s) not in manifest)",
        files=len(man.files),
        extras=extras,
        created=man.created,
    )


def resume_into(
    durable_dir: str | Path, work_dir: str | Path, quick: bool = False
) -> ResumeResult:
    """Verify the durable copy, then hydrate ``work_dir`` from it.

    Raises :class:`CheckpointError` rather than hydrating anything if verify
    fails. Refusing loudly beats resuming a job onto corrupt state and
    discovering it hours of GPU time later.
    """
    result = verify(durable_dir, quick=quick)
    if not result.ok:
        raise CheckpointError(f"refusing to resume: {result.reason}")
    durable = Path(durable_dir)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    man = _Manifest.from_json(manifest_path(durable).read_text(encoding="utf-8"))
    written = 0
    count = 0
    for rel in sorted(man.files):
        _, n = _copy_and_hash(durable / rel, work / rel)
        written += n
        count += 1
    return ResumeResult(hydrated=count, bytes_written=written, verify=result)


# --------------------------------------------------------------------------- #
# The mirror                                                                  #
# --------------------------------------------------------------------------- #


class DurableCheckpoint:
    """Mirror ``work_dir`` to ``durable_dir``, atomically and on a timer.

    Typical use, where ``commit`` is whatever makes a volume durable::

        ckpt = DurableCheckpoint(work, durable, interval_s=600, commit=vol.commit)
        if has_checkpoint(durable):
            resume_into(durable, work)   # raises if the mirror is torn
        with ckpt:                       # periodic + final-on-signal
            run_the_job()

    ``start`` installs SIGINT/SIGTERM handlers, so it must be called from the
    main thread; that is a CPython restriction, not a choice here. Pass
    ``handle_signals=False`` for a worker thread, and call
    :meth:`mirror_now` yourself on the way out.
    """

    def __init__(
        self,
        work_dir: str | Path,
        durable_dir: str | Path,
        interval_s: float = DEFAULT_INTERVAL_S,
        commit: object = None,
        exclude: tuple[str, ...] = (),
        logger: object = None,
        handle_signals: bool = True,
    ) -> None:
        self.work = Path(work_dir)
        self.durable = Path(durable_dir)
        if self.durable == self.work:
            raise CheckpointError("work_dir and durable_dir must differ")
        if interval_s <= 0:
            raise CheckpointError(f"interval_s must be positive, got {interval_s}")
        self.interval_s = float(interval_s)
        self._commit = commit
        self.exclude = tuple(exclude)
        self._log = logger
        self.handle_signals = handle_signals
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Serialises the timer tick against a signal-driven final mirror, so the
        # two cannot interleave and write a half-and-half manifest.
        self._lock = threading.Lock()
        self._prev_handlers: dict[int, object] = {}
        self.mirrors = 0
        self.failures = 0

    # -- logging ---------------------------------------------------------- #

    def _say(self, msg: str) -> None:
        if self._log is None:
            print(f"[ckpt] {msg}", flush=True)
        else:
            self._log(f"[ckpt] {msg}")  # type: ignore[operator]

    # -- the mirror ------------------------------------------------------- #

    def _read_prev(self) -> _Manifest:
        mpath = manifest_path(self.durable)
        if not mpath.is_file():
            return _Manifest()
        try:
            return _Manifest.from_json(mpath.read_text(encoding="utf-8"))
        except CheckpointError:
            # An unreadable previous manifest costs us incremental reuse and
            # nothing else: everything gets re-copied and re-hashed.
            return _Manifest()

    def mirror_now(self) -> MirrorResult:
        """One mirror pass. Manifest removed first, written last.

        That ordering is the whole guarantee. Interrupted at any point, the
        durable path has no manifest, so :func:`verify` refuses it rather than a
        later run loading a half-written checkpoint and believing it.
        """
        with self._lock:
            return self._mirror_locked()

    def _mirror_locked(self) -> MirrorResult:
        started = time.time()
        if not self.work.is_dir():
            raise CheckpointError(f"work_dir does not exist: {self.work}")
        self.durable.mkdir(parents=True, exist_ok=True)
        prev = self._read_prev()
        mpath = manifest_path(self.durable)

        # STEP 1 - invalidate. From here until step 3 there is no loadable
        # checkpoint, by design: a crash in this window must not look resumable.
        mpath.unlink(missing_ok=True)

        # STEP 2 - copy what changed, hashing in the same read.
        files = _iter_files(self.work, self.exclude)
        new_files: dict[str, FileRecord] = {}
        copied = reused = 0
        bytes_copied = 0
        for src in files:
            rel = src.relative_to(self.work).as_posix()
            stat = src.stat()
            old = prev.files.get(rel)
            dst = self.durable / rel
            if (
                old is not None
                and old.size == stat.st_size
                and old.mtime_ns == stat.st_mtime_ns
                and dst.is_file()
                and dst.stat().st_size == old.size
            ):
                new_files[rel] = old
                reused += 1
                continue
            sha, n = _copy_and_hash(src, dst)
            new_files[rel] = FileRecord(sha256=sha, size=n, mtime_ns=stat.st_mtime_ns)
            copied += 1
            bytes_copied += n

        removed = self._prune(set(new_files))

        # STEP 3 - the manifest, last. Now the checkpoint is loadable.
        man = _Manifest(created=time.time(), files=new_files)
        _atomic_write_text(mpath, man.to_json())

        # The volume commit comes after the manifest: if it fails, the local
        # durable dir is already self-consistent, and the next pass retries.
        if self._commit is not None:
            self._commit()  # type: ignore[operator]

        self.mirrors += 1
        return MirrorResult(
            copied=copied,
            reused=reused,
            removed=removed,
            bytes_copied=bytes_copied,
            seconds=round(time.time() - started, 3),
            manifest_path=str(mpath),
        )

    def _prune(self, keep: set[str]) -> int:
        """Drop durable files the job has deleted, so the mirror stays a mirror.

        Without this, a file removed in scratch lingers in the durable copy and
        a resumed job sees a directory that never existed.
        """
        removed = 0
        for p in _iter_files(self.durable, ()):
            rel = p.relative_to(self.durable).as_posix()
            if rel in keep:
                continue
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    # -- lifecycle -------------------------------------------------------- #

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                r = self.mirror_now()
                self._say(
                    f"mirrored {r.copied} new / {r.reused} unchanged "
                    f"({r.bytes_copied / 1e6:.1f} MB) in {r.seconds}s"
                )
            except Exception as exc:  # noqa: BLE001 - a mirror must never kill the job
                self.failures += 1
                self._say(f"MIRROR FAILED ({self.failures}): {exc!r}")

    def _on_signal(self, signum: int, frame: object) -> None:
        """Final mirror, then hand back to whatever was there before us.

        Incremental, so it is usually quick — but a preemption grace period is
        seconds, and a large first mirror can exceed it. Mirror often enough
        that the final one has little left to do.
        """
        self._say(f"signal {signum}: taking a final checkpoint")
        try:
            r = self.mirror_now()
            self._say(f"final checkpoint ok ({r.copied} new, {r.seconds}s)")
        except Exception as exc:  # noqa: BLE001 - still must not mask the signal
            self.failures += 1
            self._say(f"final checkpoint FAILED: {exc!r}")
        self._stop.set()
        prev = self._prev_handlers.get(signum)
        if callable(prev):
            prev(signum, frame)
        elif prev == signal.SIG_DFL:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

    def start(self) -> DurableCheckpoint:
        if self._thread is not None:
            raise CheckpointError("already started")
        if self.handle_signals:
            for signum in (signal.SIGINT, signal.SIGTERM):
                try:
                    self._prev_handlers[signum] = signal.getsignal(signum)
                    signal.signal(signum, self._on_signal)
                except (ValueError, OSError) as exc:
                    # Not the main thread, or the platform lacks it. Degrade to
                    # periodic-only rather than refusing to run at all.
                    self._say(f"no handler for signal {signum} ({exc}); periodic only")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="durable-checkpoint", daemon=True
        )
        self._thread.start()
        return self

    def stop(self, final: bool = True) -> MirrorResult | None:
        """Stop the timer and, by default, take one last mirror."""
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=5.0)
        for signum, prev in self._prev_handlers.items():
            try:
                signal.signal(signum, prev)  # type: ignore[arg-type]
            except (ValueError, OSError, TypeError):
                pass
        self._prev_handlers.clear()
        if not final:
            return None
        try:
            return self.mirror_now()
        except Exception as exc:  # noqa: BLE001 - reported, never raised at exit
            self.failures += 1
            self._say(f"final mirror on stop FAILED: {exc!r}")
            return None

    def __enter__(self) -> DurableCheckpoint:
        return self.start()

    def __exit__(self, *exc: object) -> bool:
        self.stop(final=True)
        return False


def clear_work_dir(work_dir: str | Path) -> None:
    """Empty a scratch dir without removing it. For tests and clean restarts."""
    work = Path(work_dir)
    if not work.is_dir():
        return
    for child in work.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
