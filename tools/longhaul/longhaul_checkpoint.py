#!/usr/bin/env python
"""longhaul checkpoint — keep a long job's state alive across interruption.

The problem it solves: a job runs for longer than its container is guaranteed to
live. A Modal function caps at 24h, a connected FEP+ map is 12-27h, preemptible
GPUs disappear with a signal and a few seconds' notice, laptops lose power. The
job's working directory sits on fast local scratch, so when the container dies
that scratch dies with it.

The pattern: run in fast scratch, mirror to a durable path periodically, and on
re-invocation resume from the mirror instead of starting over. This module is
that mirror. It is provider-agnostic: the durable path is just a directory, and
anything needed to make writes durable (committing a mounted volume, say) is a
callable you pass in. Nothing here imports a cloud SDK, knows about accounts, or
moves state between them.

PROVENANCE

This is the durable-checkpoint module of closed PR #398 (branch
``feat/durable-checkpoint``), with the seven defects that
``spec_longhaul_checkpoint.py`` pins fixed in the implementation rather than by
monkeypatch. The on-disk layout and manifest format are unchanged, so a durable
directory written by durable-checkpoint resumes here as-is.

GENERATIONS, AND WHERE THE CORRECTNESS ACTUALLY LIVES

Each checkpoint is written into its own new, monotonically numbered generation
directory — files first, the manifest with hashes last — and only then is the
volume committed. Nothing existing is touched. The loader takes the highest
generation whose manifest verifies and falls back down the list, so at least one
complete checkpoint exists at every instant, including mid-write. There is no
pointer file and nothing is renamed: a Modal Volume promises neither atomic
rename nor durability before commit, so "highest generation that verifies" is the
pointer.

The layout is right in principle; what keeps it right is the bookkeeping around
it, and that is what changed here:

1. Retention counts only LOADABLE generations toward ``keep_generations``. A torn
   directory never takes a retained slot, so repeated preemption cannot
   converge to a single loadable copy. Unloadable generations older than the
   newest are garbage and are deleted.
2. Unchanged files are hardlinked only from a generation this process has read
   back in FULL, never from one that merely has the right sizes. When a
   read-back finds that a linked file no longer matches its carried-over hash,
   the link base is distrusted, every linked file is recopied from scratch and
   the generation is read back again, so a same-size corruption cannot be
   carried forward through a shared inode.
3. A signal handler waits at most ``SIGNAL_LOCK_BUDGET_S`` for the mirror lock.
   If a mirror is in flight it skips the final checkpoint rather than block past
   the grace window, and the signal still reaches the previous handler.
4. Any malformed manifest or unreadable file refuses THAT generation and falls
   back to the next; nothing escapes as an exception from ``verify_generation``,
   ``latest_verified`` or ``resume_into``.
5. One signal writes exactly one final generation, and neither the signal path
   nor ``stop()`` prunes: the final is taken inside a grace window, and pruning
   there could remove the last intact pre-signal copy.
6. ``start()`` installs handlers, the delivered signal chains to the previous
   handler, and ``stop()`` restores exactly the handlers it installed.
7. ``resume_into`` restores the recorded mtimes and re-hashes what it writes, so
   the first mirror after a resume links what an uninterrupted run would link
   instead of re-copying the whole tree.

A TRAP WORTH KNOWING BEFORE YOU AUTOMATE RESTARTS

If a call's input status reads FAILURE while ``FunctionCall.get(timeout=0)`` still
raises ``TimeoutError``, the platform is mid-restart after a preemption; delays of
13-20 minutes were observed. Cancelling there kills a live restart. Only re-spawn
once ``get()`` raises a real error. ``longhaul_watch`` follows that rule.

COST NOTE

Unchanged files are hardlinked from the previous generation where the
filesystem allows it, which costs no space and no I/O beyond the read-back.
Where linking is unsupported (plausible on a FUSE volume mount) it falls back to
copying, and each retained generation then costs a full copy of the job
directory. Size that against ``keep_generations`` before pointing this at a large
tree. Every new generation is read back in full before anything is pruned.

SINGLE WRITER

One process mirrors one durable path. Concurrent mirrors into the same path
would race on generation numbering.

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
#: How long a signal handler may wait for the mirror lock before it gives up on
#: the final checkpoint. Anything unbounded can outlive the grace window.
SIGNAL_LOCK_BUDGET_S = 0.25
_CHUNK = 1 << 20  # 1 MiB
# Everything reading a damaged generation can raise. UnicodeDecodeError is a
# ValueError, listed for the reader.
_UNREADABLE = (
    OSError,
    UnicodeDecodeError,
    ValueError,
    TypeError,
    OverflowError,
    RecursionError,
)


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
    repaired: int = 0


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


def _safe_rel(rel: object) -> str:
    """A manifest path must stay inside its generation and the work dir."""
    bad = (
        not isinstance(rel, str)
        or not rel
        or "\x00" in rel
        or rel.startswith("/")
        or (os.name == "nt" and ("\\" in rel or ":" in rel))
        or any(part in ("", ".", "..") for part in rel.split("/"))
    )
    if bad:
        raise CheckpointError(f"manifest path {rel!r} is not a safe relative path")
    return str(rel)


def _int_field(rec: dict, key: str, rel: str, default: int | None = None) -> int:
    value = rec.get(key, default)
    if value is None and default is not None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CheckpointError(f"manifest.files[{rel!r}] is malformed: {key}={value!r}")
    return value


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
        """Parse and validate. Every malformed shape is a CheckpointError."""
        try:
            raw = json.loads(text)
        except (ValueError, RecursionError) as exc:
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
        created_raw = raw.get("created")
        if created_raw is None:
            created = 0.0
        elif isinstance(created_raw, bool) or not isinstance(created_raw, (int, float)):
            raise CheckpointError("manifest.created is not a number")
        else:
            try:
                created = float(created_raw)
            except OverflowError:
                raise CheckpointError("manifest.created is out of range") from None
        files: dict[str, FileRecord] = {}
        for rel, rec in files_raw.items():
            _safe_rel(rel)
            if not isinstance(rec, dict):
                raise CheckpointError(f"manifest.files[{rel!r}] is not an object")
            sha = rec.get("sha256")
            if not isinstance(sha, str) or not sha:
                raise CheckpointError(f"manifest.files[{rel!r}] is malformed: sha256")
            files[rel] = FileRecord(
                sha256=sha,
                size=_int_field(rec, "size", rel),
                mtime_ns=_int_field(rec, "mtime_ns", rel, default=0),
            )
        return _Manifest(version=MANIFEST_VERSION, created=created, files=files)


# --------------------------------------------------------------------------- #
# Primitives                                                                  #
# --------------------------------------------------------------------------- #


def _atomic_write_text(path: Path, text: str) -> None:
    """Write via a sibling temp then rename.

    This keeps a reader in this container from seeing a half-written manifest.
    Correctness across a crash does NOT depend on the rename being atomic: a
    generation with no readable manifest is skipped either way.
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
    """Every regular file under root, sorted. Symlinks skipped, not followed."""
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
    """Is there any generation with a manifest? Presence only, no integrity."""
    return any(
        manifest_path(durable_dir, n).is_file() for n in generations(durable_dir)
    )


def _read_manifest(durable_dir: str | Path, n: int) -> _Manifest:
    """Load generation ``n``'s manifest; every failure is a CheckpointError."""
    try:
        text = manifest_path(durable_dir, n).read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckpointError(f"manifest is not valid UTF-8: {exc}") from None
    except OSError as exc:
        raise CheckpointError(f"manifest is unreadable: {exc}") from None
    return _Manifest.from_json(text)


def _verify(durable_dir: str | Path, n: int, quick: bool) -> VerifyResult:
    gdir = gen_dir(durable_dir, n)
    if not manifest_path(durable_dir, n).is_file():
        # Nothing written yet, or interrupted before its manifest: unsafe either way.
        return VerifyResult(
            False, "no manifest: generation is incomplete", generation=n
        )
    man = _read_manifest(durable_dir, n)
    if not man.files:
        return VerifyResult(False, "manifest lists no files", generation=n)
    for rel, rec in sorted(man.files.items()):
        p = gdir / rel
        if not p.is_file():
            return VerifyResult(
                False, f"missing file from manifest: {rel}", generation=n
            )
        size = p.stat().st_size
        if size != rec.size:
            return VerifyResult(
                False, f"size mismatch on {rel}: {size} != {rec.size}", generation=n
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


def verify_generation(
    durable_dir: str | Path, n: int, quick: bool = False
) -> VerifyResult:
    """Is generation ``n`` loadable? Fails closed, and never raises.

    ``quick`` checks presence and size only, skipping hashes: fine for a cheap
    poll, not for deciding to resume, because the corruption this guards against
    preserves size. Any malformed manifest or unreadable file is a refusal of
    this generation, so a caller can always fall back to an older one.
    """
    try:
        return _verify(durable_dir, n, quick)
    except CheckpointError as exc:
        return VerifyResult(False, str(exc), generation=n)
    except _UNREADABLE as exc:
        return VerifyResult(
            False,
            f"unreadable generation ({type(exc).__name__}: {exc})",
            generation=n,
        )


def latest_verified(
    durable_dir: str | Path, quick: bool = False
) -> tuple[int | None, VerifyResult]:
    """Highest-numbered generation that verifies, walking down on failure.

    This IS the pointer: implicit, derived on read, and needing no rename.
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

    Refuses with :class:`CheckpointError`, writing nothing, if no generation
    verifies. Every hydrated file is re-hashed as it is written and checked
    against the manifest (verify-on-read), and its recorded mtime is restored,
    so the resumed tree IS the recorded tree and the next mirror can link it.
    """
    n, result = latest_verified(durable_dir, quick=quick)
    if n is None:
        raise CheckpointError(f"refusing to resume: {result.reason}")
    man = _read_manifest(durable_dir, n)
    gdir = gen_dir(durable_dir, n)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    written = 0
    count = 0
    for rel in sorted(man.files):
        rec = man.files[rel]
        target = work / rel
        sha, size = _copy_and_hash(gdir / rel, target)
        if sha != rec.sha256 or size != rec.size:
            raise CheckpointError(
                f"refusing to resume: {rel} changed while being hydrated from "
                f"generation {n}"
            )
        if rec.mtime_ns:
            os.utime(target, ns=(rec.mtime_ns, rec.mtime_ns))
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
    main thread (a CPython restriction). Pass ``handle_signals=False`` from a
    worker thread and call :meth:`mirror_now` yourself on the way out.
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
        # Serialises a timer tick against a signal-driven final mirror. A signal
        # handler only ever waits SIGNAL_LOCK_BUDGET_S for it.
        self._lock = threading.Lock()
        self._prev_handlers: dict[int, object] = {}
        self._installed: list[int] = []
        # Generations this process read back in FULL (link bases), and ones that
        # failed a full read. Both are guarded by _lock.
        self._good: set[int] = set()
        self._bad: set[int] = set()
        self._final_done = False
        self.mirrors = 0
        self.failures = 0
        self.skipped_finals = 0

    def _say(self, msg: str) -> None:
        if self._log is None:
            print(f"[ckpt] {msg}", flush=True)
        else:
            self._log(f"[ckpt] {msg}")  # type: ignore[operator]

    # -- the mirror ------------------------------------------------------- #

    def mirror_now(self) -> MirrorResult:
        """Write one new generation. Nothing existing is modified.

        Files first, manifest last, then commit, then a full read-back, then
        prune. Interrupted at any point, every previously complete generation is
        still exactly where it was and still verifies.
        """
        with self._lock:
            return self._mirror_locked(prune=True)

    def _link_base(self) -> int | None:
        """The newest generation this process has read back in full.

        A fresh process (just resumed, say) has none yet, so it pays for one full
        verification walk here and remembers the result. A generation that only
        passes the size check is never used: linking from it is how a same-size
        corruption propagates forward.
        """
        for g in sorted(self._good - self._bad, reverse=True):
            if verify_generation(self.durable, g, quick=True).ok:
                return g
            self._good.discard(g)
        for g in reversed(generations(self.durable)):
            if g in self._bad:
                continue
            if verify_generation(self.durable, g).ok:
                self._good.add(g)
                return g
            self._bad.add(g)
        return None

    def _base_manifest(self, base: int | None) -> tuple[int | None, _Manifest]:
        if base is None:
            return None, _Manifest()
        try:
            return base, _read_manifest(self.durable, base)
        except CheckpointError as exc:
            self._say(f"link base {base} unreadable ({exc}); copying everything")
            self._bad.add(base)
            self._good.discard(base)
            return None, _Manifest()

    def _write_manifest(self, n: int, files: dict[str, FileRecord]) -> None:
        _atomic_write_text(
            manifest_path(self.durable, n),
            _Manifest(created=time.time(), files=files).to_json(),
        )
        # On a volume nothing written above is durable until commit returns.
        if self._commit is not None:
            self._commit()  # type: ignore[operator]

    def _mirror_locked(self, prune: bool) -> MirrorResult:
        started = time.time()
        if not self.work.is_dir():
            raise CheckpointError(f"work_dir does not exist: {self.work}")
        self.durable.mkdir(parents=True, exist_ok=True)

        base, base_man = self._base_manifest(self._link_base())
        existing = generations(self.durable)
        n = (max(existing) + 1) if existing else 1
        gdir = gen_dir(self.durable, n)
        gdir.mkdir(parents=True, exist_ok=False)

        new_files: dict[str, FileRecord] = {}
        linked_rels: list[str] = []
        copied = 0
        bytes_copied = 0
        for src in _iter_files(self.work, self.exclude):
            rel = src.relative_to(self.work).as_posix()
            stat = src.stat()
            old = base_man.files.get(rel)
            dst = gdir / rel
            reusable = (
                base is not None
                and old is not None
                and old.size == stat.st_size
                and old.mtime_ns == stat.st_mtime_ns
            )
            if reusable and self._try_link(gen_dir(self.durable, base) / rel, dst):
                new_files[rel] = old  # type: ignore[assignment]
                linked_rels.append(rel)
                continue
            sha, size = _copy_and_hash(src, dst)
            new_files[rel] = FileRecord(
                sha256=sha, size=size, mtime_ns=stat.st_mtime_ns
            )
            copied += 1
            bytes_copied += size

        if not new_files:
            # An empty generation would never verify and would shadow nothing.
            shutil.rmtree(gdir, ignore_errors=True)
            raise CheckpointError(
                f"nothing to checkpoint: no files under {self.work} after excludes"
            )

        # The manifest, last. Only now is this generation loadable.
        self._write_manifest(n, new_files)
        check = verify_generation(self.durable, n)
        repaired = 0
        if not check.ok and linked_rels:
            # A linked file failed its carried-over hash: the link base itself is
            # damaged. Stop trusting it, recopy every linked file from scratch
            # (unlinking first, never writing through the shared inode), and read
            # the generation back again.
            self._say(
                f"generation {n} failed read-back ({check.reason}); distrusting "
                f"link base {base} and recopying {len(linked_rels)} linked file(s)"
            )
            if base is not None:
                self._bad.add(base)
                self._good.discard(base)
            for rel in linked_rels:
                dst = gdir / rel
                dst.unlink(missing_ok=True)
                src = self.work / rel
                stat = src.stat()
                sha, size = _copy_and_hash(src, dst)
                new_files[rel] = FileRecord(
                    sha256=sha, size=size, mtime_ns=stat.st_mtime_ns
                )
                bytes_copied += size
            repaired = len(linked_rels)
            copied += repaired
            linked_rels = []
            self._write_manifest(n, new_files)
            check = verify_generation(self.durable, n)

        pruned: tuple[int, ...] = ()
        if check.ok:
            self._good.add(n)
            self._bad.discard(n)
            if prune:
                pruned = self._prune_generations(keep_newest=n)
        else:
            self._bad.add(n)
            self._good.discard(n)
            self._say(f"generation {n} failed read-back ({check.reason}); keeping all")

        self.mirrors += 1
        return MirrorResult(
            generation=n,
            copied=copied,
            linked=len(linked_rels),
            bytes_copied=bytes_copied,
            seconds=round(time.time() - started, 3),
            pruned=pruned,
            verified=check.ok,
            generation_dir=str(gdir),
            repaired=repaired,
        )

    def _try_link(self, src: Path, dst: Path) -> bool:
        """Hardlink an unchanged file from the link base, if the filesystem can.

        Returns False on any filesystem that will not do it, so the caller
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

    def _is_loadable(self, g: int) -> bool:
        if g in self._bad:
            return False
        if g in self._good:
            return verify_generation(self.durable, g, quick=True).ok
        result = verify_generation(self.durable, g)  # a full read, once per process
        (self._good if result.ok else self._bad).add(g)
        return result.ok

    def _prune_generations(self, keep_newest: int) -> tuple[int, ...]:
        """Keep ``keep_generations - 1`` LOADABLE generations beside ``keep_newest``.

        Only ever called after ``keep_newest`` has been committed and read back.
        Unloadable generations never count toward the floor; those older than
        ``keep_newest`` are garbage and are deleted.
        """
        good: list[int] = []
        junk: list[int] = []
        for g in generations(self.durable):
            if g == keep_newest:
                continue
            if self._is_loadable(g):
                good.append(g)
            elif g < keep_newest:
                junk.append(g)
        keep = set(good[-(self.keep_generations - 1) :])
        removed: list[int] = []
        for g in sorted(junk + [g for g in good if g not in keep]):
            try:
                shutil.rmtree(gen_dir(self.durable, g))
            except OSError as exc:
                self._say(f"could not prune generation {g}: {exc!r}")
                continue
            removed.append(g)
            self._good.discard(g)
            self._bad.discard(g)
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
        """One final checkpoint, then hand back to whatever handler was there.

        The lock wait is bounded: if a mirror is in flight (on the timer thread,
        or on this very thread), the final checkpoint is skipped rather than
        blocking past the grace window. The final never prunes, and a second
        signal does not write a second final.
        """
        if not self._lock.acquire(timeout=SIGNAL_LOCK_BUDGET_S):
            self.skipped_finals += 1
            self._say(
                f"signal {signum}: a mirror holds the lock; skipping the final "
                f"checkpoint so the signal is not swallowed"
            )
        else:
            try:
                if not self._final_done:
                    self._say(f"signal {signum}: taking a final checkpoint")
                    try:
                        r = self._mirror_locked(prune=False)
                        self._final_done = True
                        self._say(
                            f"final checkpoint ok: generation {r.generation} "
                            f"in {r.seconds}s"
                        )
                    except Exception as exc:  # noqa: BLE001 - must not mask the signal
                        self.failures += 1
                        self._say(f"final checkpoint FAILED: {exc!r}")
            finally:
                self._lock.release()
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
        self._final_done = False
        if self.handle_signals:
            for signum in (signal.SIGINT, signal.SIGTERM):
                try:
                    self._prev_handlers[signum] = signal.getsignal(signum)
                    signal.signal(signum, self._on_signal)
                    self._installed.append(signum)
                except (ValueError, OSError) as exc:
                    # Not the main thread, or the platform lacks it.
                    self._say(f"no handler for signal {signum} ({exc}); periodic only")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="longhaul-checkpoint", daemon=True
        )
        self._thread.start()
        return self

    def stop(self, final: bool = True) -> MirrorResult | None:
        """Stop the timer, restore the handlers start() installed, and by default
        write one last generation (none if a signal already wrote it). Never
        prunes: the next run's first mirror does that."""
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=5.0)
        for signum in self._installed:
            try:
                signal.signal(signum, self._prev_handlers.get(signum, signal.SIG_DFL))  # type: ignore[arg-type]
            except (ValueError, OSError, TypeError):
                pass
        self._installed = []
        self._prev_handlers.clear()
        if not final or self._final_done:
            return None
        try:
            with self._lock:
                return self._mirror_locked(prune=False)
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
