"""Degrade-loudly channel that cannot be silently swallowed (IMP-0054).

A degraded path must not look identical to a healthy one.  ``warn()`` writes
every warning to a *durable* sink before it returns -- JSONL append under an
advisory lock, flushed and ``os.fsync``'d -- so a caller that ignores the return
value (or dies right after) still leaves a record on disk.  The record is
surfaced twice more:

* by the next :meth:`Sink.health_check` -- in this process or any later one --
  which reads the sink from disk and returns an explicit verdict.  An EMPTY sink
  is declared (``verdict=NO_WARNINGS``, ``empty_sink_declared=True``, explicit
  text) rather than omitted: silence is never the healthy signal;
* at process exit -- an ``atexit`` hook writes ``exit-surface.json`` into the
  sink and prints the count to stderr, so a process that warned and exited
  still tells the user.

The sink is bounded: the active ``warnings.jsonl`` rotates at
``max_file_bytes`` into ``warnings.jsonl.1`` .. ``.N`` (``max_files`` total) and
the whole sink is kept under ``hard_ceiling_bytes`` by dropping the oldest
rotation.  The defaults (64 KiB x 8, 512 KiB ceiling) sit below the 774 KiB
unbounded-log pathology this unit closes.  ``rotate=False`` exists only as the
negative control that proves the bound detector can fail.

CLI (used by the named probes as a separate writer/reader process)::

    degrade_loudly.py warn         --sink DIR --code C --message M [bounds]
    degrade_loudly.py discard-warn --sink DIR --code C --message M   # ignores the handle
    degrade_loudly.py health       --sink DIR                       # JSON report, last line
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

try:  # POSIX advisory lock; Windows falls back to a best-effort no-op lock
    import fcntl
except ImportError:  # pragma: no cover - windows
    fcntl = None  # type: ignore[assignment]

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schema" / "warning-record.schema.json"
ENV_SINK = "PLUGIN_WARNING_SINK"
ACTIVE_NAME = "warnings.jsonl"
EXIT_SURFACE_NAME = "exit-surface.json"

DEFAULT_MAX_FILE_BYTES = 65536
DEFAULT_MAX_FILES = 8
DEFAULT_HARD_CEILING_BYTES = 524288
PATHOLOGY_REFERENCE_BYTES = 774 * 1024
MESSAGE_TRUNCATE_AT = 2048

NO_WARNINGS = "NO_WARNINGS"
WARNINGS_PRESENT = "WARNINGS_PRESENT"
EMPTY_EXPLICIT = "no warnings recorded; sink empty"

assert DEFAULT_HARD_CEILING_BYTES < PATHOLOGY_REFERENCE_BYTES


def default_sink_dir() -> Path:
    env = os.environ.get(ENV_SINK)
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "warnings"


@dataclass(frozen=True)
class SinkConfig:
    directory: Path
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_files: int = DEFAULT_MAX_FILES
    hard_ceiling_bytes: int = DEFAULT_HARD_CEILING_BYTES
    rotate: bool = True
    message_truncate_at: int = MESSAGE_TRUNCATE_AT

    def __post_init__(self) -> None:
        object.__setattr__(self, "directory", Path(self.directory))
        if self.max_files < 1 or self.max_file_bytes < 64 or self.hard_ceiling_bytes < 64:
            raise ValueError("sink bounds must be positive (max_files>=1, bytes>=64)")


@dataclass
class WarningRecord:
    ts: str
    code: str
    message: str
    pid: int
    seq: int
    level: str = "warning"
    truncated: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WriteHandle:
    """What ``warn`` returns.  Deliberately ignorable: the disk is the proof."""

    path: Path
    bytes_written: int
    record: WarningRecord
    total_bytes_after: int
    rotated: bool


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _Lock:
    def __init__(self, directory: Path) -> None:
        self.path = directory / ".sink.lock"
        self.fd: int | None = None

    def __enter__(self) -> "_Lock":
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        if fcntl is not None:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.fd is not None:
            if fcntl is not None:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


class Sink:
    """Durable, bounded JSONL warning sink."""

    def __init__(self, config: SinkConfig | None = None) -> None:
        self.config = config or SinkConfig(directory=default_sink_dir())
        self.directory = self.config.directory
        self.active = self.directory / ACTIVE_NAME
        self._seq = 0
        self._written_this_process: list[str] = []
        self._exit_registered = False

    # --- files ---------------------------------------------------------------

    def files(self) -> list[Path]:
        """Active file first, then rotations oldest-last (.1 newer than .2)."""
        if not self.directory.is_dir():
            return []
        out = []
        if self.active.is_file():
            out.append(self.active)
        rotated = []
        for p in self.directory.glob(ACTIVE_NAME + ".*"):
            suffix = p.name[len(ACTIVE_NAME) + 1 :]
            if suffix.isdigit():
                rotated.append((int(suffix), p))
        out.extend(p for _, p in sorted(rotated))
        return out

    def total_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.files() if p.is_file())

    def _rotated_path(self, n: int) -> Path:
        return self.directory / f"{ACTIVE_NAME}.{n}"

    def _rotate(self) -> None:
        """Shift .N -> .N+1, active -> .1; drop anything beyond max_files."""
        keep = self.config.max_files - 1
        for n in range(self.config.max_files + 5, 0, -1):
            p = self._rotated_path(n)
            if not p.exists():
                continue
            if n >= keep:
                p.unlink()
            else:
                os.replace(p, self._rotated_path(n + 1))
        if self.active.exists():
            if keep >= 1:
                os.replace(self.active, self._rotated_path(1))
            else:
                self.active.unlink()

    def _enforce_ceiling(self) -> None:
        """Drop oldest rotations, then trim the active file, until under the ceiling."""
        ceiling = self.config.hard_ceiling_bytes
        while self.total_bytes() > ceiling:
            files = self.files()
            rotations = [p for p in files if p != self.active]
            if rotations:
                rotations[-1].unlink()
                continue
            if not self.active.is_file():
                break
            lines = self.active.read_bytes().splitlines(keepends=True)
            kept: list[bytes] = []
            size = 0
            for line in reversed(lines):
                if size + len(line) > ceiling:
                    break
                kept.insert(0, line)
                size += len(line)
            self.active.write_bytes(b"".join(kept))
            break

    # --- write ---------------------------------------------------------------

    def _register_exit_surface(self) -> None:
        if not self._exit_registered:
            atexit.register(self._exit_surface)
            self._exit_registered = True

    def _exit_surface(self) -> None:
        if not self._written_this_process:
            return
        payload = {
            "pid": os.getpid(),
            "ts": _utc_now(),
            "count": len(self._written_this_process),
            "codes": sorted(set(self._written_this_process)),
            "sink": str(self.directory),
        }
        try:
            (self.directory / EXIT_SURFACE_NAME).write_text(
                json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
            )
        except OSError:
            pass
        try:
            sys.stderr.write(
                f"degrade-loudly: {payload['count']} warning(s) recorded in {self.directory}\n"
            )
            sys.stderr.flush()
        except (OSError, ValueError):
            pass

    def warn(self, code: str, message: str, **context: Any) -> WriteHandle:
        """Append one record; durable (locked, flushed, fsync'd) before returning."""
        code = str(code)
        text = str(message)
        truncated = False
        if len(text) > self.config.message_truncate_at:
            text = text[: self.config.message_truncate_at]
            truncated = True
        self.directory.mkdir(parents=True, exist_ok=True)
        with _Lock(self.directory):
            self._seq += 1
            record = WarningRecord(
                ts=_utc_now(),
                code=code,
                message=text,
                pid=os.getpid(),
                seq=self._seq,
                truncated=truncated,
                context={k: str(v) for k, v in context.items()},
            )
            line = (json.dumps(record.as_dict(), sort_keys=True) + "\n").encode("utf-8")
            rotated = False
            if self.config.rotate:
                active_size = self.active.stat().st_size if self.active.is_file() else 0
                if active_size and active_size + len(line) > self.config.max_file_bytes:
                    self._rotate()
                    rotated = True
            fd = os.open(self.active, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
            if self.config.rotate:
                self._enforce_ceiling()
            total = self.total_bytes()
        self._written_this_process.append(code)
        self._register_exit_surface()
        return WriteHandle(
            path=self.active,
            bytes_written=len(line),
            record=record,
            total_bytes_after=total,
            rotated=rotated,
        )

    # --- read ----------------------------------------------------------------

    def records(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in reversed(self.files()):  # oldest rotation first, active last
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    out.append({"code": "DEGRADE_LOUDLY.CORRUPT_LINE", "message": line[:200], "corrupt": True})
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
        return out

    def health_check(self) -> dict[str, Any]:
        """Explicit verdict from disk.  Never silent: an empty sink says so."""
        recs = self.records()
        files = self.files()
        present = bool(recs)
        counts: dict[str, int] = {}
        for r in recs:
            counts[str(r.get("code"))] = counts.get(str(r.get("code")), 0) + 1
        exit_surface = None
        surface = self.directory / EXIT_SURFACE_NAME
        if surface.is_file():
            try:
                exit_surface = json.loads(surface.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                exit_surface = {"corrupt": True}
        report: dict[str, Any] = {
            "kind": "degrade-loudly-health",
            "sink": str(self.directory),
            "sink_exists": self.directory.is_dir(),
            "verdict": WARNINGS_PRESENT if present else NO_WARNINGS,
            "warnings_present": present,
            "count": len(recs),
            "codes": counts,
            "records": recs[-200:],
            "files": [p.name for p in files],
            "total_bytes": self.total_bytes(),
            "bounds": {
                "max_file_bytes": self.config.max_file_bytes,
                "max_files": self.config.max_files,
                "hard_ceiling_bytes": self.config.hard_ceiling_bytes,
                "rotate": self.config.rotate,
                "within_ceiling": self.total_bytes() <= self.config.hard_ceiling_bytes,
            },
            "empty_sink": not present,
            "empty_sink_declared": not present,
            "exit_surface": exit_surface,
        }
        report["explicit"] = (
            EMPTY_EXPLICIT
            if not present
            else f"{len(recs)} warning(s) recorded across {len(files)} file(s)"
        )
        return report


# --- module-level convenience ----------------------------------------------------

_DEFAULT: Sink | None = None


def default_sink() -> Sink:
    global _DEFAULT
    if _DEFAULT is None or _DEFAULT.directory != default_sink_dir():
        _DEFAULT = Sink(SinkConfig(directory=default_sink_dir()))
    return _DEFAULT


def warn(code: str, message: str, **context: Any) -> WriteHandle:
    return default_sink().warn(code, message, **context)


def health_check(directory: Path | None = None) -> dict[str, Any]:
    sink = default_sink() if directory is None else Sink(SinkConfig(directory=directory))
    return sink.health_check()


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_record(rec: dict[str, Any]) -> list[str]:
    """Stdlib check of a record against warning-record.schema.json."""
    schema = load_schema()
    errs = []
    for key in schema.get("required", []):
        if key not in rec:
            errs.append(f"missing {key}")
    types = {"string": str, "integer": int, "boolean": bool, "object": dict}
    for key, sub in schema.get("properties", {}).items():
        if key in rec and "type" in sub and not isinstance(rec[key], types[sub["type"]]):
            errs.append(f"{key}: expected {sub['type']}")
        if key in rec and "minLength" in sub and len(rec[key]) < sub["minLength"]:
            errs.append(f"{key}: too short")
    if schema.get("additionalProperties") is False:
        errs.extend(f"unexpected {k}" for k in rec if k not in schema.get("properties", {}))
    return errs


# --- CLI ---------------------------------------------------------------------------


def _config_from_args(args: argparse.Namespace) -> SinkConfig:
    return SinkConfig(
        directory=Path(args.sink) if args.sink else default_sink_dir(),
        max_file_bytes=args.max_file_bytes,
        max_files=args.max_files,
        hard_ceiling_bytes=args.hard_ceiling_bytes,
        rotate=not args.no_rotate,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def bounds(p: argparse.ArgumentParser) -> None:
        p.add_argument("--sink", default=None, help=f"sink directory (default ${ENV_SINK})")
        p.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
        p.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
        p.add_argument("--hard-ceiling-bytes", type=int, default=DEFAULT_HARD_CEILING_BYTES)
        p.add_argument("--no-rotate", action="store_true", help="negative control: unbounded")

    for name in ("warn", "discard-warn"):
        p = sub.add_parser(name)
        bounds(p)
        p.add_argument("--code", required=True)
        p.add_argument("--message", required=True)
    h = sub.add_parser("health")
    bounds(h)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sink = Sink(_config_from_args(args))
    if args.command == "warn":
        handle = sink.warn(args.code, args.message)
        print(
            json.dumps(
                {"written": True, "path": str(handle.path), "bytes": handle.bytes_written,
                 "total_bytes": handle.total_bytes_after, "rotated": handle.rotated},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "discard-warn":
        sink.warn(args.code, args.message)  # return value deliberately dropped
        print("discarded-return=true")
        return 0
    if args.command == "health":
        report = sink.health_check()
        print(json.dumps(report, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
