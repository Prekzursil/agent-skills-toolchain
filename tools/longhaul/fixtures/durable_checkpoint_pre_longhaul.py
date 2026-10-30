# FROZEN FIXTURE - do not fix or reformat. This is durable-checkpoint as it stood at
# 7430bee97 (blob 8485a661e8 on branch feat/durable-checkpoint, closed PR #398): the
# module spec_longhaul_checkpoint.py's rows 1-5 and 7 must still FAIL against, so the
# spec stays two-sided in CI. The maintained module is ../longhaul_checkpoint.py.
#!/usr/bin/env python
"""durable-checkpoint — keep a long job's state alive across interruption.

The problem it solves: a job runs for longer than its container is guaranteed to
live. A Modal function caps at 24h, a connected FEP+ map is 12-27h, preemptible
GPUs disappear with a signal and a few seconds' notice, laptops lose power. The
job's working directory sits on fast local scratch (a volume or network
filesystem is usually too slow and too loosely consistent for MD-style I/O), so
when the container dies that scratch dies with it.

The pattern: run in fast scratch, mirror to a durable path periodically, and on
re-invocation resume from the mirror instead of starting over.

This module is that mirror. It is deliberately provider-agnostic: the durable
path is just a directory, and anything that needs doing to make writes durable
(committing a mounted volume, say) is a callable you pass in. Nothing here
imports a cloud SDK, knows about accounts, or moves state between them.

WHY GENERATIONS, AND NOT AN IN-PLACE MIRROR

An in-place mirror has a fatal window, and it is not an exotic edge case — it is
exactly where a preemption lands. Writing into the live durable path means
invalidating the existing checkpoint before the new one is complete, so a kill
in between leaves nothing loadable. Measured on an earlier build of this module:
four complete checkpoint files sat physically intact on disk and every one was
unusable, because the manifest vouching for them had been removed to begin a
final checkpoint that never finished. That is total loss, not last-interval
loss, and it is the one failure a durability tool must never have.

So each checkpoint is written into its own **new, monotonically numbered
generation directory** — files first, the manifest with hashes last — and only
then is the volume committed. Nothing existing is touched. The loader takes the
highest-numbered generation whose manifest verifies and falls back down the
list, so **at least one complete checkpoint exists at every instant**, including
mid-write. An interrupted generation has no manifest, so it is simply skipped.

There is no pointer file and nothing is renamed, which matters because a Modal
Volume promises neither: its docs make no atomicity claim for rename, writes
become durable only on commit, background commits happen "every few seconds",
and v2 is beta and "may lose data". A design whose correctness rested on an
atomic rename would be resting on an unsupported assumption. Highest-verifying
generation wins is correct even if a rename or a background commit tears.

An older generation is deleted only once a newer one has been committed AND
re-verified by reading it back, and never below ``keep_generations`` (minimum
two). Pruning is therefore always a no-op on the only good copy.

A TRAP WORTH KNOWING BEFORE YOU AUTOMATE RESTARTS
(measured by this estate's fractal-compute steward, not by me)

If a call's input status reads FAILURE while ``FunctionCall.get(timeout=0)``
still raises ``TimeoutError``, the platform is **mid-restart after preemption**;
delays of 13-20 minutes were observed. Cancelling there kills a live restart and
throws away the work it was about to resume. Only re-spawn once ``get()`` raises
a real error. Any supervisor built around this module should respect that.

COST NOTE

A new generation does not mean re-writing unchanged bytes. Unchanged files are
**hardlinked** from the previous generation where the filesystem allows it, which
costs no space and no I/O, and their hashes are carried over rather than
recomputed. Where linking is unsupported — a plausible outcome on a FUSE volume
mount — it falls back to copying, and then each retained generation costs a full
copy of the job directory. Size that against ``keep_generations`` before pointing
this at a 15 GB tree.

SINGLE WRITER

One process mirrors one durable path. Concurrent mirrors into the same path
would race on generation numbering, and Modal's own guidance is that a given
file should be written by a single container at a time anyway.

Stdlib only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "MANIFEST.durable-checkpoint.json"
MANIFEST_VERSION = 2
GEN_PREFIX = "gen-"
GEN_WIDTH = 8
_GEN_RE = re.compile(rf"\A{GEN_PREFIX}(\d{{{GEN_WIDTH}}})\Z")
DEFAULT_INTERVAL_S = 600.0
DEFAULT_KEEP_GENERATIONS = 2
MIN_KEEP_GENERATIONS = 2
_CHUNK = 1 << 20  # 1 MiB


class CheckpointError(Exception):
    """A checkpoint operation failed. Message is fit for an operator."""


@dataclass(frozen=True)
class FileRecord:
    sha256: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class MirrorResult:
    generation: int
    copied: int
    linked: int
    bytes_copied: int
    seconds: float
    pruned: tuple[int, ...]
    verified: bool
    generation_dir: str


@dataclass(frozen=True)
class VerifyResult:
    """``ok`` is the only thing to branch on. ``reason`` explains a refusal."""

    ok: bool
    reason: str
    generation: int = 0
    files: int = 0
    extras: tuple[str, ...] = ()
    created: float = 0.0

    def __bool__(self) -> bool:
        return self.ok


@dataclass(frozen=True)
class ResumeResult:
    generation: int
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
        if raw.get("version") != MANIFEST_VERSION:
            raise CheckpointError(
                f"manifest version {raw.get('version')!r} is not supported "
                f"(this build reads {MANIFEST_VERSION})"
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
    """Write via a sibling temp then rename.

    Note what this is and is not relied upon for: it keeps a *reader in this
    container* from seeing a half-written manifest. Correctness across a crash
    does NOT depend on the rename being atomic, because a generation with no
    readable manifest is skipped either way. That distinction is deliberate —
    see the module docstring on Modal Volumes.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _copy_and_hash(src: Path, dst: Path) -> tuple[str, int]:
    """Copy src to dst, returning (sha256, bytes), hashing in the same pass."""
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


def _excluded(rel: str, exclude: tuple[str, ...]) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat) for pat in exclude
    )


def _iter_files(root: Path, exclude: tuple[str, ...]) -> list[Path]:
    """Every regular file under root, sorted. Symlinks skipped, not followed.

    Following them can copy a tree from outside the job directory, or loop.
    """
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        rel_dir = d.relative_to(root)
        dirnames[:] = [
            n
            for n in dirnames
            if not _excluded((rel_dir / n).as_posix(), exclude)
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


# --------------------------------------------------------------------------- #
# Generations                                                                 #
# --------------------------------------------------------------------------- #


def gen_name(n: int) -> str:
    return f"{GEN_PREFIX}{n:0{GEN_WIDTH}d}"


def gen_dir(durable_dir: str | Path, n: int) -> Path:
    return Path(durable_dir) / gen_name(n)


def generations(durable_dir: str | Path) -> list[int]:
    """Every generation number present, ascending. Cheap: a directory listing."""
    durable = Path(durable_dir)
    if not durable.is_dir():
        return []
    out: list[int] = []
    for child in durable.iterdir():
        if not child.is_dir():
            continue
        m = _GEN_RE.match(child.name)
        if m:
            out.append(int(m.group(1)))
    out.sort()
    return out


def manifest_path(durable_dir: str | Path, n: int) -> Path:
    return gen_dir(durable_dir, n) / MANIFEST_NAME


def has_checkpoint(durable_dir: str | Path) -> bool:
    """Is there any generation with a manifest? Presence only, no integrity.

    Cheap by design, so a caller can ask before paying for hashes. Use
    :func:`latest_verified` before trusting anything.
    """
    return any(
        manifest_path(durable_dir, n).is_file() for n in generations(durable_dir)
    )


def verify_generation(
    durable_dir: str | Path, n: int, quick: bool = False
) -> VerifyResult:
    """Is generation ``n`` loadable? Fails closed on anything unexpected.

    ``quick`` checks size only, skipping hashes — fine for a cheap poll, not
    for deciding to resume: the corruption this guards against preserves size.
    """
    gdir = gen_dir(durable_dir, n)
    mpath = manifest_path(durable_dir, n)
    if not mpath.is_file():
        # Either nothing was written yet, or a generation was interrupted before
        # its manifest. Both are unsafe to load, which is why this is one case.
        return VerifyResult(
            False, "no manifest: generation is incomplete", generation=n
        )
    try:
        man = _Manifest.from_json(mpath.read_text(encoding="utf-8"))
    except CheckpointError as exc:
        return VerifyResult(False, str(exc), generation=n)
    if not man.files:
        return VerifyResult(False, "manifest lists no files", generation=n)

    for rel, rec in sorted(man.files.items()):
        p = gdir / rel
        if not p.is_file():
            return VerifyResult(
                False, f"missing file from manifest: {rel}", generation=n
            )
        if p.stat().st_size != rec.size:
            return VerifyResult(
                False,
                f"size mismatch on {rel}: {p.stat().st_size} != {rec.size}",
                generation=n,
            )
        if quick:
            continue
        got, _ = _hash_file(p)
        if got != rec.sha256:
            return VerifyResult(False, f"checksum mismatch on {rel}", generation=n)

    on_disk = {p.relative_to(gdir).as_posix() for p in _iter_files(gdir, ())}
    extras = tuple(sorted(on_disk - set(man.files)))
    return VerifyResult(
        True,
        "ok" if not extras else f"ok ({len(extras)} file(s) not in manifest)",
        generation=n,
        files=len(man.files),
        extras=extras,
        created=man.created,
    )


def latest_verified(
    durable_dir: str | Path, quick: bool = False
) -> tuple[int | None, VerifyResult]:
    """Highest-numbered generation that verifies, walking down on failure.

    This IS the pointer: implicit, derived on read, and needing no rename. A
    torn newest generation costs you that generation and nothing more.
    """
    gens = generations(durable_dir)
    if not gens:
        return None, VerifyResult(False, "no generations: nothing to resume from")
    worst = VerifyResult(False, "no generations: nothing to resume from")
    for n in reversed(gens):
        result = verify_generation(durable_dir, n, quick=quick)
        if result.ok:
            return n, result
        worst = result
    return None, VerifyResult(
        False,
        f"no generation verifies (newest failure: {worst.reason})",
        generation=worst.generation,
    )


def verify(durable_dir: str | Path, quick: bool = False) -> VerifyResult:
    """Is there a loadable checkpoint at all? Delegates to :func:`latest_verified`."""
    return latest_verified(durable_dir, quick=quick)[1]


def resume_into(
    durable_dir: str | Path, work_dir: str | Path, quick: bool = False
) -> ResumeResult:
    """Hydrate ``work_dir`` from the newest generation that verifies.

    Raises :class:`CheckpointError` rather than hydrating anything if no
    generation verifies. Refusing loudly beats resuming onto corrupt state and
    discovering it hours of GPU time later.
    """
    n, result = latest_verified(durable_dir, quick=quick)
    if n is None:
        raise CheckpointError(f"refusing to resume: {result.reason}")
    gdir = gen_dir(durable_dir, n)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    man = _Manifest.from_json(manifest_path(durable_dir, n).read_text(encoding="utf-8"))
    written = 0
    count = 0
    for rel in sorted(man.files):
        _, size = _copy_and_hash(gdir / rel, work / rel)
        written += size
        count += 1
    return ResumeResult(
        generation=n, hydrated=count, bytes_written=written, verify=result
    )


# --------------------------------------------------------------------------- #
# The mirror                                                                  #
# --------------------------------------------------------------------------- #


class DurableCheckpoint:
    """Write successive generations of ``work_dir`` under ``durable_dir``.

    Typical use, where ``commit`` is whatever makes a volume durable::

        ckpt = DurableCheckpoint(work, durable, interval_s=600, commit=vol.commit)
        if has_checkpoint(durable):
            resume_into(durable, work)   # newest generation that verifies
        with ckpt:                       # periodic + final-on-signal
            run_the_job()

    ``start`` installs SIGINT/SIGTERM handlers, so it must be called from the
    main thread; that is a CPython restriction, not a choice here. Pass
    ``handle_signals=False`` from a worker thread and call :meth:`mirror_now`
    yourself on the way out.
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
        keep_generations: int = DEFAULT_KEEP_GENERATIONS,
        link_unchanged: bool = True,
    ) -> None:
        self.work = Path(work_dir)
        self.durable = Path(durable_dir)
        if self.durable == self.work:
            raise CheckpointError("work_dir and durable_dir must differ")
        if interval_s <= 0:
            raise CheckpointError(f"interval_s must be positive, got {interval_s}")
        if keep_generations < MIN_KEEP_GENERATIONS:
            # Keeping one would reintroduce the whole bug: pruning the only good
            # copy to make room for a generation that might not finish.
            raise CheckpointError(
                f"keep_generations must be at least {MIN_KEEP_GENERATIONS}, "
                f"got {keep_generations}"
            )
        self.interval_s = float(interval_s)
        self._commit = commit
        self.exclude = tuple(exclude)
        self._log = logger
        self.handle_signals = handle_signals
        self.keep_generations = int(keep_generations)
        self.link_unchanged = bool(link_unchanged)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Serialises a timer tick against a signal-driven final mirror, so the
        # two cannot interleave and produce one mixed generation.
        self._lock = threading.Lock()
        self._prev_handlers: dict[int, object] = {}
        self.mirrors = 0
        self.failures = 0

    def _say(self, msg: str) -> None:
        if self._log is None:
            print(f"[ckpt] {msg}", flush=True)
        else:
            self._log(f"[ckpt] {msg}")  # type: ignore[operator]

    # -- the mirror ------------------------------------------------------- #

    def mirror_now(self) -> MirrorResult:
        """Write one new generation. Nothing existing is modified.

        Files first, manifest last, then commit, then read-back verify, then
        prune. Interrupted at any point, every previously complete generation
        is still exactly where it was and still verifies.
        """
        with self._lock:
            return self._mirror_locked()

    def _mirror_locked(self) -> MirrorResult:
        started = time.time()
        if not self.work.is_dir():
            raise CheckpointError(f"work_dir does not exist: {self.work}")
        self.durable.mkdir(parents=True, exist_ok=True)

        prev_n, _ = latest_verified(self.durable, quick=True)
        prev_man = (
            _Manifest.from_json(
                manifest_path(self.durable, prev_n).read_text(encoding="utf-8")
            )
            if prev_n is not None
            else _Manifest()
        )
        existing = generations(self.durable)
        n = (max(existing) + 1) if existing else 1
        gdir = gen_dir(self.durable, n)
        gdir.mkdir(parents=True, exist_ok=False)

        files = _iter_files(self.work, self.exclude)
        new_files: dict[str, FileRecord] = {}
        copied = linked = 0
        bytes_copied = 0
        for src in files:
            rel = src.relative_to(self.work).as_posix()
            stat = src.stat()
            old = prev_man.files.get(rel)
            dst = gdir / rel
            reusable = (
                old is not None
                and prev_n is not None
                and old.size == stat.st_size
                and old.mtime_ns == stat.st_mtime_ns
            )
            if reusable and self._try_link(gen_dir(self.durable, prev_n) / rel, dst):
                new_files[rel] = old  # type: ignore[assignment]
                linked += 1
                continue
            sha, size = _copy_and_hash(src, dst)
            new_files[rel] = FileRecord(
                sha256=sha, size=size, mtime_ns=stat.st_mtime_ns
            )
            copied += 1
            bytes_copied += size

        if not new_files:
            # An empty generation would verify as "manifest lists no files",
            # i.e. never, and would shadow nothing. Refuse rather than leave a
            # permanently-unverifiable directory behind.
            shutil.rmtree(gdir, ignore_errors=True)
            raise CheckpointError(
                f"nothing to checkpoint: no files under {self.work} after excludes"
            )

        # The manifest, last. Only now is this generation loadable.
        _atomic_write_text(
            manifest_path(self.durable, n),
            _Manifest(created=time.time(), files=new_files).to_json(),
        )

        # Commit before trusting the generation: on a volume, nothing written
        # above is durable until this returns.
        if self._commit is not None:
            self._commit()  # type: ignore[operator]

        # Read it back. Pruning anything on the strength of a generation we have
        # not re-read would be taking the write's word for it.
        check = verify_generation(self.durable, n)
        pruned: tuple[int, ...] = ()
        if check.ok:
            pruned = self._prune_generations(keep_newest=n)
        else:
            self._say(f"generation {n} failed read-back ({check.reason}); keeping all")

        self.mirrors += 1
        return MirrorResult(
            generation=n,
            copied=copied,
            linked=linked,
            bytes_copied=bytes_copied,
            seconds=round(time.time() - started, 3),
            pruned=pruned,
            verified=check.ok,
            generation_dir=str(gdir),
        )

    def _try_link(self, src: Path, dst: Path) -> bool:
        """Hardlink an unchanged file from the previous generation, if we can.

        Costs no space and no I/O. Returns False on any filesystem that will not
        do it — a plausible outcome on a FUSE volume mount — so the caller
        falls back to copying.
        """
        if not self.link_unchanged or not src.is_file():
            return False
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(src, dst)
        except (OSError, NotImplementedError, AttributeError):
            dst.unlink(missing_ok=True)
            return False
        return True

    def _prune_generations(self, keep_newest: int) -> tuple[int, ...]:
        """Drop the oldest generations beyond ``keep_generations``.

        Only ever called after ``keep_newest`` has been committed and verified
        by read-back, and it never removes that generation or takes the retained
        count below the floor.
        """
        gens = [g for g in generations(self.durable) if g != keep_newest]
        # Keep the newest (keep_generations - 1) older ones alongside keep_newest.
        drop = gens[: max(0, len(gens) - (self.keep_generations - 1))]
        removed: list[int] = []
        for g in drop:
            try:
                shutil.rmtree(gen_dir(self.durable, g))
                removed.append(g)
            except OSError as exc:
                self._say(f"could not prune generation {g}: {exc!r}")
        return tuple(removed)

    # -- lifecycle -------------------------------------------------------- #

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                r = self.mirror_now()
                self._say(
                    f"generation {r.generation}: {r.copied} copied / {r.linked} linked "
                    f"({r.bytes_copied / 1e6:.1f} MB) in {r.seconds}s"
                    + (f", pruned {list(r.pruned)}" if r.pruned else "")
                )
            except Exception as exc:  # noqa: BLE001 - a mirror must never kill the job
                self.failures += 1
                self._say(f"MIRROR FAILED ({self.failures}): {exc!r}")

    def _on_signal(self, signum: int, frame: object) -> None:
        """Final checkpoint, then hand back to whatever handler was there.

        Safe to be cut short: this writes a NEW generation, so a kill partway
        through costs only the generation in progress. Every earlier one still
        verifies. That is the whole reason for the generation layout.
        """
        self._say(f"signal {signum}: taking a final checkpoint")
        try:
            r = self.mirror_now()
            self._say(f"final checkpoint ok: generation {r.generation} in {r.seconds}s")
        except Exception as exc:  # noqa: BLE001 - must not mask the signal
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
                    # periodic-only rather than refusing to run.
                    self._say(f"no handler for signal {signum} ({exc}); periodic only")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="durable-checkpoint", daemon=True
        )
        self._thread.start()
        return self

    def stop(self, final: bool = True) -> MirrorResult | None:
        """Stop the timer and, by default, write one last generation."""
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
