#!/usr/bin/env python3
"""Reap abandoned plugin-install staging clones from ~/.claude/plugins/cache.

WHAT THIS IS: a MITIGATION, not a fix.

The writer is Claude Code itself (measured on the native binary, version
2.1.220 at C:/Users/Prekzursil/.local/bin/claude.exe) -- vendor code we cannot
patch. When a plugin whose marketplace entry declares a remote source is
materialised, the CLI clones into a staging directory directly under
``~/.claude/plugins/cache``:

    temp_subdir_<epoch_ms>_<rand6>.clone   for a ``git-subdir`` plugin source
    temp_git_<epoch_ms>_<rand6>            for a ``url`` / ``git`` plugin source

Measured behaviour (see tools/plugin-cache-reaper/README.md for the exact
commands and output):

* SUCCESS path      -> the staging dir IS removed. No leak.
* clone FAILS fast  -> the staging dir IS removed. No leak.
* process is KILLED mid-clone -> the staging dir SURVIVES, holding a partial
  ``.git`` and nothing checked out. This is the leak.

The reproduced husk resembles the live ones in the way that matters -- a partial
``.git`` with no worktree -- but NOT in shape. An earlier version of this note
claimed "a husk's only child is ``.git``"; measuring six live husks gave child
counts of 20, 1, 4, 19, 22 and 15, so exactly one of six matched. How far a clone
got before it died varies, so the child count varies with it. Nothing here depends
on that: candidacy is decided by NAME (``STAGING_RE``) alone and never by counting
children, so the reaper is unaffected. The claim was false and is corrected in
place rather than quietly dropped.

There is no on-exit handler and no start-up sweep in the CLI, so every
interrupted materialisation leaks one staging tree forever. This module is the
sweep the vendor does not do.

Safety rules encoded here, because the target is a live user directory:

* Only entries whose name matches STAGING_RE are ever candidates. A real plugin
  cache entry is ``cache/<marketplace>/<plugin>/<version>`` and can never match.
* Candidates are found with a SINGLE non-recursive scan of the cache root. We
  never glob into the husks: they hold deep ``.git`` trees that blow MAX_PATH
  (the ENAMETOOLONG hazard already documented in tools/glob-argv-guard).
* An age gate with TWO independent signals, AND-ed: the epoch-ms embedded in the
  directory NAME and the directory's own mtime must BOTH be older than the
  threshold. A single signal is not enough -- an in-flight clone has a fresh
  mtime, and a clock-skewed name must not be able to authorise a delete on its
  own. See rules/common/single-signal-verification.md.
* Dry-run is the default. ``--apply`` is required to delete anything.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

# The staging "kind" tokens the CLI can emit. Recovered from the string pool of
# the 2.1.220 native binary at offset 109756512 ("local", "npm", "github",
# "git", "subdir", "unknown", "temp_", "_") -- i.e. the name is built as
# f"temp_{kind}_{Date.now()}_{rand6}". Only ``subdir`` and ``git`` have been
# observed live; the rest are accepted because the binary can emit them.
KINDS = ("git", "subdir", "github", "npm", "local", "unknown")

STAGING_RE = re.compile(
    r"^temp_(?P<kind>"
    + "|".join(KINDS)
    + r")_(?P<ms>\d{13})_[0-9a-z]{6}(?P<clone>\.clone)?$"
)

DEFAULT_MIN_AGE_MINUTES = 120

# Resolved once at import so no function needs a platform branch (a branch that
# can only be taken on one OS is a branch the coverage gate can never close).
IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# IMP-0042: retention for the development-loop cache is tools/plugin/cache_policy
# (``apply_retention``) -- imported, never forked.  The reaper is ALSO run from
# places where that module is not importable: the mutation probe copies reap.py
# alone into a scratch directory, and the scheduled task launches it by absolute
# path with an empty sys.path[0].  So the import is resolved, not assumed: try the
# normal import (same module object as any caller that already imported it), then
# the sibling ``tools/plugin`` directory, and otherwise record the absence.  With
# ``cp`` None the staging sweep still works; only retention argv is refused.
# ---------------------------------------------------------------------------


def _load_cache_policy():
    try:
        import cache_policy as module  # noqa: PLC0415

        return module
    except ImportError:
        pass
    sibling = Path(__file__).resolve().parents[1] / "plugin"
    if (sibling / "cache_policy.py").is_file():
        if str(sibling) not in sys.path:
            sys.path.insert(0, str(sibling))
        try:
            import cache_policy as module  # noqa: PLC0415

            return module
        except ImportError:
            return None
    return None


cp = _load_cache_policy()

# The ONE scheduled task this tool owns.  The installer updates it in place
# (Set-ScheduledTask) when it exists and registers it (Register-ScheduledTask)
# exactly once when it does not; retention argv rides on that same task.
TASK_NAME = "PluginCacheReaper"
LEGACY_TASK_NAMES = ("ClaudePluginCacheReaper",)
RETENTION_ARGV = ("--max-entries", "--max-bytes", "--retention-floor")
DEFAULT_IDLE_TTL_MINUTES = 0  # 0 = no idle-TTL eviction; ceilings and floor only


def installer_path() -> Path:
    return Path(__file__).resolve().with_name("install_reaper_task.ps1")


def task_identity() -> dict[str, object]:
    """What the installer actually binds, read from its text -- not asserted.

    ``task_name`` is the installer's ``$TaskName`` default; ``replaced`` is True only
    if the install path drops and re-creates the task instead of updating it in
    place; ``retention_via`` names the retention control plane the task's argv
    reaches (``cache_policy.apply_retention``) or is None when that module is not
    importable from here.
    """
    path = installer_path()
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    match = re.search(r"\[string\]\$TaskName\s*=\s*'([^']+)'", text)
    task_name = match.group(1) if match else TASK_NAME
    registers = text.count("Register-ScheduledTask")
    updates_in_place = "Set-ScheduledTask" in text
    install_section = text.split("if ($Uninstall)", 1)[-1]
    # Any Unregister on the install path that is not the legacy-name migration
    # means the task is torn down and re-created, i.e. replaced.
    unregisters_current = bool(
        re.search(r"Unregister-ScheduledTask\s+-TaskName\s+\$TaskName\b", install_section)
    )
    replaced = (not updates_in_place) or registers != 1 or unregisters_current
    return {
        "task_name": task_name,
        "legacy_task_names": [n for n in LEGACY_TASK_NAMES if n in text],
        "replaced": replaced,
        "retention_via": "cache_policy.apply_retention" if cp is not None else None,
        "retention_argv": [flag for flag in RETENTION_ARGV if flag in text],
        "installer": path.name,
        "installer_present": path.is_file(),
        "installer_has_set_scheduled_task": updates_in_place,
        "register_scheduled_task_count": registers,
        "binds_reap_py": "reap.py" in text,
    }


def default_dev_cache_root() -> Path:
    """The development-loop cache retention bounds (sibling of the vendor cache)."""
    if cp is not None and hasattr(cp, "default_dev_cache_root"):
        return Path(cp.default_dev_cache_root())
    return Path.home() / ".claude" / "plugins" / "dev-cache"


def retain_dev_cache(
    root: Path,
    *,
    max_entries: int,
    max_bytes: int,
    retention_floor: int,
    idle_ttl_minutes: int = DEFAULT_IDLE_TTL_MINUTES,
    apply: bool,
    now_ns: int | None = None,
) -> dict[str, object]:
    """Bound the dev cache through ``cache_policy`` -- the plan is theirs, not ours.

    Dry-run (the default, like the staging sweep) reports the plan and touches
    nothing; ``apply`` executes ``cache_policy.apply_retention`` on that plan.
    """
    if cp is None:
        raise RuntimeError("cache_policy is not importable from here; retention unavailable")
    root = Path(root)
    idle_ttl_ns = int(idle_ttl_minutes) * 60_000_000_000 if int(idle_ttl_minutes) > 0 else None
    plan = cp.retention_plan(
        root,
        max_entries=max_entries,
        max_bytes=max_bytes,
        retention_floor=retention_floor,
        idle_ttl_ns=idle_ttl_ns,
        now_ns=now_ns,
    )
    if apply and plan["index_present"]:
        cp.apply_retention(
            root,
            max_entries=max_entries,
            max_bytes=max_bytes,
            retention_floor=retention_floor,
            idle_ttl_ns=idle_ttl_ns,
            now_ns=now_ns,
        )
    return {
        "root": str(root),
        "applied": bool(apply and plan["index_present"]),
        "index_present": plan["index_present"],
        "evicted": [str(v.get("name")) for v in plan["victims"]],
        "kept": len(plan["kept"]),
        "bytes_before": plan["bytes_before"],
        "bytes_after": plan["bytes_after"],
        "via": "cache_policy.apply_retention",
    }


PAYLOAD_NAME = "payload.bin"
SOURCE_NAME = "source.bin"
META_NAME = "entry.json"

# ---------------------------------------------------------------------------
# IMP-0040: content-addressed plugin cache.  The cache key is derived from the
# plugin version AND the sha256 of the source bytes that produced the artefact,
# so a fixed package can never be masked by a stale entry: when the source hash
# changes the key changes and the old entry is unreachable by construction, not
# by an expiry heuristic.  Layout: <root>/<plugin_version>/<source_sha256>/payload.bin
# (the on-disk key IS the directory pair, so a listing shows the change).
# tools/plugin/cache.py is a facade that re-exports these names; the layout is
# defined here and nowhere else.
# ---------------------------------------------------------------------------
_VERSION_SAFE_RE = re.compile(r"[^A-Za-z0-9._+-]")


def source_digest_of(source: bytes) -> str:
    """sha256 of the source bytes with CRLF normalised to LF (the source identity)."""
    import hashlib

    return hashlib.sha256(bytes(source).replace(b"\r\n", b"\n")).hexdigest()


def _safe_version(plugin_version: str) -> str:
    text = str(plugin_version).strip()
    if not text:
        raise ValueError("plugin_version must be non-empty")
    return _VERSION_SAFE_RE.sub("_", text)


def content_addressed_key(plugin_version: str, source_digest: str) -> str:
    """Cache key is ``<plugin_version>/<source_digest>``: version AND source hash, never a counter."""
    digest = str(source_digest).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"source_digest must be a sha256 hex, got {source_digest!r}")
    return f"{_safe_version(plugin_version)}/{digest}"


def cache_key(plugin_version: str, source_digest: str) -> str:
    return content_addressed_key(plugin_version, source_digest)


def default_produce(source: bytes) -> bytes:
    """The identity build: the artefact is the LF-normalised source.  Real callers inject theirs."""
    return bytes(source).replace(b"\r\n", b"\n")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Sibling temp file + ``os.replace`` so a concurrent reader sees old or new, never torn."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{id(data) & 0xFFFF:x}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


class ContentAddressedPluginCache:
    """Entries keyed by plugin version + sha256(source); a source change makes the old key unreachable."""

    def __init__(self, root, produce=None) -> None:
        self.root = Path(root)
        self.produce = produce or default_produce
        self.computed = 0
        self.served_from_disk = 0

    def key(self, plugin_version: str, source: bytes) -> str:
        return content_addressed_key(plugin_version, source_digest_of(source))

    def entry_dir(self, key: str) -> Path:
        version, _, digest = key.partition("/")
        if not version or not digest or "/" in digest or ".." in (version, digest):
            raise ValueError(f"malformed cache key {key!r}")
        return self.root / version / digest

    def payload_path(self, key: str) -> Path:
        return self.entry_dir(key) / PAYLOAD_NAME

    def has(self, key: str) -> bool:
        return self.payload_path(key).is_file()

    def get_or_compute(self, plugin_version: str, source: bytes, produce=None) -> bytes:
        """Serve the artefact for (version, sha256(source)); derive and persist it on a miss."""
        key = self.key(plugin_version, source)
        return self.get_or_compute_key(key, source, produce)

    def get_or_compute_key(self, key: str, source: bytes, produce=None) -> bytes:
        path = self.payload_path(key)
        if path.is_file():
            self.served_from_disk += 1
            return path.read_bytes()
        builder = produce or self.produce
        payload = bytes(builder(bytes(source)))
        entry = self.entry_dir(key)
        _atomic_write_bytes(entry / SOURCE_NAME, bytes(source))
        _atomic_write_bytes(
            entry / META_NAME,
            (
                '{"key": "%s", "source_sha256": "%s", "payload_bytes": %d}\n'
                % (key, source_digest_of(source), len(payload))
            ).encode("utf-8"),
        )
        _atomic_write_bytes(path, payload)
        self.computed += 1
        return payload

    def keys(self) -> list[str]:
        """On-disk keys as ``version/source_sha256`` pairs (directory listing, not a counter)."""
        found: list[str] = []
        if not self.root.is_dir():
            return found
        for version_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for digest_dir in sorted(p for p in version_dir.iterdir() if p.is_dir()):
                if (digest_dir / PAYLOAD_NAME).is_file():
                    found.append(f"{version_dir.name}/{digest_dir.name}")
        return found


class TimeBasedPluginCache:
    """NEGATIVE CONTROL: keyed by plugin id + version only, expiring by TTL.

    Inside its TTL window it keeps serving the artefact built from the OLD
    source after the source changed -- exactly the staleness the
    content-addressed cache makes impossible.  Kept so the oracle can be shown
    to fire on the bad design and stay silent on the good one.
    """

    def __init__(self, root, ttl_seconds: float = 3600.0, clock=None, produce=None) -> None:
        import time as _time

        self.root = Path(root)
        self.ttl_seconds = float(ttl_seconds)
        self.clock = clock or _time.time
        self.produce = produce or default_produce
        self.computed = 0

    def key(self, plugin_id: str, plugin_version: str) -> str:
        return f"{_VERSION_SAFE_RE.sub('_', str(plugin_id))}@{_safe_version(plugin_version)}"

    def entry_dir(self, key: str) -> Path:
        return self.root / key

    def _stamp_path(self, key: str) -> Path:
        return self.entry_dir(key) / "built-at.txt"

    def is_fresh(self, key: str) -> bool:
        stamp = self._stamp_path(key)
        payload = self.entry_dir(key) / PAYLOAD_NAME
        if not stamp.is_file() or not payload.is_file():
            return False
        built_at = float(stamp.read_text(encoding="ascii").strip() or "0")
        return (float(self.clock()) - built_at) < self.ttl_seconds

    def get_or_compute(self, plugin_id: str, plugin_version: str, source: bytes, produce=None) -> bytes:
        """Serve whatever was built within the TTL, regardless of the source bytes passed now."""
        key = self.key(plugin_id, plugin_version)
        payload_path = self.entry_dir(key) / PAYLOAD_NAME
        if self.is_fresh(key):
            return payload_path.read_bytes()
        builder = produce or self.produce
        payload = bytes(builder(bytes(source)))
        _atomic_write_bytes(payload_path, payload)
        _atomic_write_bytes(self._stamp_path(key), f"{float(self.clock()):.6f}\n".encode("ascii"))
        self.computed += 1
        return payload

    def keys(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / PAYLOAD_NAME).is_file())


def get_or_compute(root, key: str, source: bytes, produce=None) -> bytes:
    """Module-level convenience: serve ``key`` from ``root`` or derive it from ``source``."""
    return ContentAddressedPluginCache(root, produce).get_or_compute_key(key, source, produce)


@dataclass(frozen=True)
class Candidate:
    """One reapable staging directory."""

    path: Path
    kind: str
    name_ms: int
    mtime_ms: int
    size_bytes: int


def parse_staging_name(name: str) -> tuple[str, int] | None:
    """Return ``(kind, epoch_ms)`` for a staging dir name, else ``None``."""
    match = STAGING_RE.match(name)
    if match is None:
        return None
    return match.group("kind"), int(match.group("ms"))


def is_reapable(*, name_ms: int, mtime_ms: int, now_ms: int, min_age_ms: int) -> bool:
    """AND-gate the two independent age signals.

    ``name_ms`` comes from the directory name (what the writer stamped) and
    ``mtime_ms`` from the filesystem (what actually last touched it). Both must
    clear the threshold, so neither a skewed clock nor a stale name can retire a
    clone that is still being written.
    """
    return (now_ms - name_ms) >= min_age_ms and (now_ms - mtime_ms) >= min_age_ms


def long_path(path: Path, *, windows: bool = IS_WINDOWS) -> str:
    """Return a filesystem string safe for paths longer than MAX_PATH.

    On Windows the extended-length ``\\\\?\\`` prefix is required or a nested
    ``.git`` tree inside a husk raises ENOENT/ENAMETOOLONG. Elsewhere the plain
    string is correct. ``windows`` is injectable so both branches are testable
    on one platform.
    """
    text = str(path)
    if not windows or text.startswith("\\\\?\\"):
        return text
    return "\\\\?\\" + text


def tree_size_bytes(path: Path, *, windows: bool = IS_WINDOWS) -> int:
    """Sum file sizes under ``path`` without ever raising on a long path."""
    total = 0
    stack = [long_path(path, windows=windows)]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def _force_remove(target: str) -> None:
    """Delete one file, clearing the read-only bit git sets on pack files."""
    try:
        os.unlink(target)
    except PermissionError:
        os.chmod(target, stat.S_IWRITE)
        os.unlink(target)


def remove_tree(path: Path, *, windows: bool = IS_WINDOWS) -> None:
    """Recursively delete ``path``, long-path- and read-only-safe.

    Implemented directly rather than via ``shutil.rmtree``: the ``onerror``
    callback needed for the read-only ``.git`` objects is removed in Python 3.14
    and its replacement ``onexc`` does not exist in the 3.11 the CI lane pins.
    """
    root = long_path(path, windows=windows)
    dirs: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        dirs.append(current)
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                stack.append(entry.path)
            else:
                _force_remove(entry.path)
    for directory in reversed(dirs):
        try:
            os.rmdir(directory)
        except OSError:
            pass


def default_cache_root() -> Path:
    """The live plugin cache for this user."""
    return Path.home() / ".claude" / "plugins" / "cache"


def validate_root(root: Path) -> None:
    """Refuse to operate anywhere that is not a plugin cache directory.

    A typo in ``--root`` must not turn this into a generic deleter, so the last
    two path components are asserted rather than trusted.
    """
    parts = root.parts
    if len(parts) < 2 or parts[-1] != "cache" or parts[-2] != "plugins":
        raise ValueError(f"refusing to scan {root}: not a .../plugins/cache path")


def find_candidates(
    root: Path,
    *,
    now_ms: int,
    min_age_ms: int,
    windows: bool = IS_WINDOWS,
    measure: bool = True,
) -> list[Candidate]:
    """One non-recursive scan of ``root`` -> the reapable staging dirs."""
    validate_root(root)
    found: list[Candidate] = []
    try:
        entries = list(os.scandir(long_path(root, windows=windows)))
    except OSError:
        return found
    for entry in entries:
        parsed = parse_staging_name(entry.name)
        if parsed is None:
            continue
        if not entry.is_dir(follow_symlinks=False):
            continue
        kind, name_ms = parsed
        mtime_ms = int(entry.stat(follow_symlinks=False).st_mtime * 1000)
        if not is_reapable(
            name_ms=name_ms, mtime_ms=mtime_ms, now_ms=now_ms, min_age_ms=min_age_ms
        ):
            continue
        path = root / entry.name
        size = tree_size_bytes(path, windows=windows) if measure else 0
        found.append(
            Candidate(
                path=path,
                kind=kind,
                name_ms=name_ms,
                mtime_ms=mtime_ms,
                size_bytes=size,
            )
        )
    return sorted(found, key=lambda c: c.name_ms)


def reap(
    root: Path,
    *,
    now_ms: int,
    min_age_ms: int,
    apply: bool,
    windows: bool = IS_WINDOWS,
    measure: bool = True,
) -> dict[str, object]:
    """Find (and optionally delete) abandoned staging dirs. Returns a report."""
    candidates = find_candidates(
        root, now_ms=now_ms, min_age_ms=min_age_ms, windows=windows, measure=measure
    )
    removed: list[str] = []
    if apply:
        for candidate in candidates:
            remove_tree(candidate.path, windows=windows)
            removed.append(candidate.path.name)
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
    return {
        "root": str(root),
        "applied": apply,
        "count": len(candidates),
        "bytes": sum(c.size_bytes for c in candidates),
        "by_kind": by_kind,
        "removed": removed,
        "oldest": candidates[0].path.name if candidates else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reap.py",
        description=(
            "Reap abandoned Claude Code plugin-install staging clones. "
            "MITIGATION for a vendor leak, not a fix. Dry-run unless --apply."
        ),
    )
    parser.add_argument("--root", type=Path, default=None, help="cache dir to scan")
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=DEFAULT_MIN_AGE_MINUTES,
        help=f"only reap dirs older than this (default {DEFAULT_MIN_AGE_MINUTES})",
    )
    parser.add_argument("--apply", action="store_true", help="actually delete")
    parser.add_argument(
        "--no-measure", action="store_true", help="skip the byte tally (faster)"
    )
    # IMP-0042: dev-cache retention rides on the SAME task and the same --apply
    # switch.  Defaults are None so "not passed" is distinguishable from a value:
    # with no retention argv and no dev cache on disk, nothing retention-related
    # happens and the output is unchanged.
    retention = parser.add_argument_group("dev-cache retention (cache_policy)")
    retention.add_argument(
        "--dev-cache-root",
        type=Path,
        default=None,
        help="development-loop cache to bound (default: cache_policy.default_dev_cache_root())",
    )
    retention.add_argument("--max-entries", type=int, default=None, help="entry ceiling")
    retention.add_argument("--max-bytes", type=int, default=None, help="byte ceiling")
    retention.add_argument(
        "--retention-floor", type=int, default=None, help="never evict below this many newest"
    )
    retention.add_argument(
        "--idle-ttl-minutes",
        type=int,
        default=None,
        help="also evict entries idle longer than this (0 disables; floor still wins)",
    )
    retention.add_argument(
        "--skip-retention", action="store_true", help="staging sweep only, never touch the dev cache"
    )
    return parser


def _retention_requested(args: argparse.Namespace) -> bool:
    return any(
        getattr(args, name) is not None
        for name in ("dev_cache_root", "max_entries", "max_bytes", "retention_floor", "idle_ttl_minutes")
    )


def _retention_summary(result: dict[str, object]) -> str:
    evicted = result["evicted"]
    count = len(evicted) if isinstance(evicted, list) else 0
    verb = "evicted" if result["applied"] else "would evict"
    return (
        f"retention={verb} {count} dev-cache entries "
        f"(kept {result['kept']}, {result['bytes_before']}->{result['bytes_after']} bytes) "
        f"under {result['root']} via {result['via']}"
    )


def main(argv: list[str] | None = None, *, now_ms: int | None = None) -> int:
    """CLI entry point. Emits an AGENTS.md-section-4 terminal-state marker."""
    args = build_parser().parse_args(argv)
    if args.min_age_minutes < 1:
        print(
            "FAILED:plugin-cache-reap --min-age-minutes must be >= 1", file=sys.stderr
        )
        return 2
    for name in ("max_entries", "max_bytes", "retention_floor", "idle_ttl_minutes"):
        value = getattr(args, name)
        if value is not None and value < 0:
            print(f"FAILED:plugin-cache-reap --{name.replace('_', '-')} must be >= 0", file=sys.stderr)
            return 2
    retention_wanted = _retention_requested(args) and not args.skip_retention
    if retention_wanted and cp is None:
        print(
            "FAILED:plugin-cache-reap retention argv given but tools/plugin/cache_policy "
            "is not importable from here",
            file=sys.stderr,
        )
        return 2
    root = args.root if args.root is not None else default_cache_root()
    if now_ms is None:  # pragma: no cover - wall clock
        import time

        now_ms = int(time.time() * 1000)
    try:
        report = reap(
            root,
            now_ms=now_ms,
            min_age_ms=args.min_age_minutes * 60_000,
            apply=args.apply,
            measure=not args.no_measure,
        )
    except ValueError as exc:
        print(f"FAILED:plugin-cache-reap {exc}", file=sys.stderr)
        return 2
    verb = "reaped" if args.apply else "would reap"
    line = (
        f"SUCCESS:plugin-cache-reap {verb} {report['count']} staging dirs "
        f"({report['bytes']} bytes) under {report['root']} by_kind={report['by_kind']}"
    )
    dev_root = args.dev_cache_root if args.dev_cache_root is not None else None
    if cp is not None and not args.skip_retention and dev_root is None:
        candidate = default_dev_cache_root()
        # Unrequested retention only when a dev cache already exists: never create one.
        if (candidate / "index.json").is_file():
            dev_root = candidate
    if retention_wanted or dev_root is not None:
        if dev_root is None:
            dev_root = default_dev_cache_root()
        try:
            result = retain_dev_cache(
                dev_root,
                max_entries=args.max_entries if args.max_entries is not None else cp.DEFAULT_MAX_ENTRIES,
                max_bytes=args.max_bytes if args.max_bytes is not None else cp.DEFAULT_MAX_BYTES,
                retention_floor=(
                    args.retention_floor if args.retention_floor is not None else cp.DEFAULT_RETENTION_FLOOR
                ),
                idle_ttl_minutes=(
                    args.idle_ttl_minutes if args.idle_ttl_minutes is not None else DEFAULT_IDLE_TTL_MINUTES
                ),
                apply=args.apply,
                now_ns=now_ms * 1_000_000,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"FAILED:plugin-cache-reap retention {exc}", file=sys.stderr)
            return 2
        line += " " + _retention_summary(result)
    print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
