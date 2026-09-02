"""Long-path write matrix for TST-0065.

Exercise estate writers at 250, 270 and 400 character absolute paths.
Classify each attempt as CORRECT, LOUD, SILENT_PARTIAL, SILENT_TRUNCATE
or SILENT_SWALLOW. Planted silent controls prove the detector is live.
Win32 MAX_PATH=260 is simulated beside native Linux outcomes.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Import implementation modules directly. tools/plugin/__init__.py pulls
# plugin.repair, which is not present on this worktree.
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cc_catalog  # noqa: E402
from permission_enforcement import (  # noqa: E402
    PermissionEnforcer,
    PermissionManifest,
)

WIN32_MAX_PATH = 260
LENGTHS = (250, 270, 400)
PAYLOAD = b"TST-0065-PAYLOAD-v1\n"
MARKER = PAYLOAD.decode("ascii")
EXTENDED_PREFIX = "\\\\?\\"
LEAF = "a.json"
SILENT = frozenset({"SILENT_PARTIAL", "SILENT_TRUNCATE", "SILENT_SWALLOW"})

WriterFn = Callable[[Path, bytes], None]


@dataclass
class Outcome:
    writer: str
    kind: str
    length: int
    intended_len: int
    intended_path: str
    verdict: str
    exception_type: str | None
    exception_text: str | None
    bytes_written: int | None
    on_disk_path: str | None
    on_disk_len: int | None
    used_extended_prefix: bool
    notes: str

    def as_dict(self) -> dict:
        return asdict(self)


def path_of_length(root: Path, n: int, leaf: str = LEAF) -> Path:
    """Build an absolute path whose str() length is exactly n."""
    root = Path(root).resolve()
    extra = n - len(str(root)) - 1 - len(leaf)
    if extra < 2:
        raise ValueError(
            f"cannot build path of length {n} under {root} (len={len(str(root))})"
        )
    dirs: list[str] = []
    remain = extra
    while remain > 0:
        if remain < 2:
            if not dirs or len(dirs[-1]) < 2:
                raise ValueError(f"cannot split remainder under {root} n={n}")
            dirs[-1] = dirs[-1][:-1]
            remain += 1
            dirs.append("z")
            remain -= 2
            continue
        name_len = min(40, remain - 1)
        leftover = remain - (1 + name_len)
        if leftover == 1:
            name_len -= 1
        if name_len < 1:
            raise ValueError(f"name_len stuck n={n} remain={remain}")
        dirs.append("x" * name_len)
        remain -= 1 + name_len
    path = root.joinpath(*dirs, leaf)
    got = len(str(path))
    if got != n:
        raise AssertionError(f"built length {got} want {n}: {path}")
    return path


def _content_ok(path: Path, payload: bytes, mode: str) -> bool:
    if not path.is_file():
        return False
    raw = path.read_bytes()
    if mode == "raw":
        return raw == payload
    if mode == "json":
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(doc, dict) and doc.get("marker") == MARKER
    return False


def _find_payload(scratch: Path, payload: bytes, mode: str) -> list[Path]:
    found: list[Path] = []
    for dirpath, _, filenames in os.walk(scratch):
        for name in filenames:
            candidate = Path(dirpath) / name
            try:
                if _content_ok(candidate, payload, mode):
                    found.append(candidate)
            except OSError:
                continue
    return found


def classify(
    *,
    writer: str,
    kind: str,
    length: int,
    intended: Path,
    payload: bytes,
    mode: str,
    scratch: Path,
    fn: WriterFn,
    mkdir: bool,
    used_extended_prefix: bool = False,
) -> Outcome:
    if mkdir:
        intended.parent.mkdir(parents=True, exist_ok=True)
    exc_type = None
    exc_text = None
    try:
        fn(intended, payload)
    except Exception as exc:  # noqa: BLE001 — classification needs the text
        exc_type = type(exc).__name__
        exc_text = f"{type(exc).__name__}: {exc}"

    intended_len = len(str(intended))
    bytes_written = None
    on_disk: Path | None = None
    notes = ""

    if exc_text:
        verdict = "LOUD"
        notes = "exception surfaced; no silent success"
    elif _content_ok(intended, payload, mode):
        verdict = "CORRECT"
        on_disk = intended
        bytes_written = intended.stat().st_size
        notes = "intended path holds the full payload"
    elif intended.is_file():
        verdict = "SILENT_PARTIAL"
        on_disk = intended
        bytes_written = intended.stat().st_size
        notes = "intended path exists but payload is incomplete or transformed"
    else:
        misplaced = [
            p
            for p in _find_payload(scratch, payload, mode)
            if p.resolve() != intended.resolve()
        ]
        if misplaced:
            verdict = "SILENT_TRUNCATE"
            on_disk = misplaced[0]
            bytes_written = on_disk.stat().st_size
            notes = (
                f"payload landed at a different path "
                f"(len={len(str(on_disk))}, intended={intended_len})"
            )
        else:
            verdict = "SILENT_SWALLOW"
            notes = "no exception and no payload on disk"

    return Outcome(
        writer=writer,
        kind=kind,
        length=length,
        intended_len=intended_len,
        intended_path=str(intended),
        verdict=verdict,
        exception_type=exc_type,
        exception_text=exc_text,
        bytes_written=bytes_written,
        on_disk_path=str(on_disk) if on_disk is not None else None,
        on_disk_len=len(str(on_disk)) if on_disk is not None else None,
        used_extended_prefix=used_extended_prefix,
        notes=notes,
    )


def _write_pathlib_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _write_pathlib_text(path: Path, data: bytes) -> None:
    path.write_text(data.decode("utf-8"), encoding="utf-8", newline="\n")


def _write_builtin_open(path: Path, data: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(data)


def _write_os_open(path: Path, data: bytes) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _write_shutil_copy2(path: Path, data: bytes) -> None:
    src = path.with_name(path.name + ".src")
    src.write_bytes(data)
    shutil.copy2(src, path)
    src.unlink()


def _write_catalog_save(path: Path, data: bytes) -> None:
    cc_catalog.save({"id": "TST-0065", "marker": data.decode("utf-8")}, path)


def _make_plugin_writer(root: Path) -> WriterFn:
    enforcer = PermissionEnforcer(
        PermissionManifest(
            fs_write_roots=(str(root),),
            allow_spawn=False,
            allow_network=False,
            component="tst-0065",
        )
    )

    def write(path: Path, data: bytes) -> None:
        enforcer.write_file(path, data)

    write.__name__ = "plugin_enforcer_write_file"
    return write


def _planted_silent_truncate(path: Path, data: bytes) -> None:
    s = os.path.abspath(str(path))
    if len(s) <= WIN32_MAX_PATH:
        Path(s).write_bytes(data)
        return
    cut = s[:WIN32_MAX_PATH]
    if cut.endswith(os.sep):
        cut = cut[:-1] + "T"
    dest = Path(cut)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.is_dir():
        dest = dest / "TRUNCATED"
    dest.write_bytes(data)


def _planted_swallow_oserror(path: Path, data: bytes) -> None:
    try:
        raise OSError(
            errno.ENAMETOOLONG,
            f"The filename or extension is too long "
            f"(Win32 MAX_PATH={WIN32_MAX_PATH}, got {len(str(path))})",
        )
    except OSError:
        return


def _planted_partial_write(path: Path, data: bytes) -> None:
    path.write_bytes(data[: max(1, len(data) // 2)])


def _win32_capped_write(path: Path, data: bytes) -> None:
    s = os.path.abspath(str(path))
    if s.startswith(EXTENDED_PREFIX):
        s = s[len(EXTENDED_PREFIX) :]
    if len(s) > WIN32_MAX_PATH:
        raise OSError(
            errno.ENAMETOOLONG,
            f"The filename or extension is too long "
            f"(Win32 MAX_PATH={WIN32_MAX_PATH}, got {len(s)})",
        )
    Path(s).write_bytes(data)


def apply_extended_length_prefix(path: Path) -> str:
    s = os.path.abspath(str(path))
    if os.name == "nt":
        if s.startswith(EXTENDED_PREFIX):
            return s
        if s.startswith("\\\\"):
            return EXTENDED_PREFIX + "UNC\\" + s.lstrip("\\")
        return EXTENDED_PREFIX + s
    return EXTENDED_PREFIX + s


def _win32_extended_write(path: Path, data: bytes) -> None:
    prefixed = apply_extended_length_prefix(path)
    if os.name == "nt":
        dest = Path(prefixed)
    elif prefixed.startswith(EXTENDED_PREFIX):
        dest = Path(prefixed[len(EXTENDED_PREFIX) :])
    else:
        dest = Path(prefixed)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def production_specs(scratch: Path) -> list[tuple[str, WriterFn, str]]:
    return [
        ("pathlib.write_bytes", _write_pathlib_bytes, "raw"),
        ("pathlib.write_text", _write_pathlib_text, "raw"),
        ("builtins.open", _write_builtin_open, "raw"),
        ("os.open+os.write", _write_os_open, "raw"),
        ("shutil.copy2", _write_shutil_copy2, "raw"),
        ("plugin.PermissionEnforcer.write_file", _make_plugin_writer(scratch), "raw"),
        ("command-center.catalog.save", _write_catalog_save, "json"),
    ]


def planted_specs() -> list[tuple[str, WriterFn, str]]:
    return [
        ("planted.silent_truncate_path", _planted_silent_truncate, "raw"),
        ("planted.swallow_oserror", _planted_swallow_oserror, "raw"),
        ("planted.partial_write", _planted_partial_write, "raw"),
    ]


def win32_specs() -> list[tuple[str, WriterFn, str, bool]]:
    return [
        ("win32.capped_no_prefix", _win32_capped_write, "raw", False),
        ("win32.extended_length_prefix", _win32_extended_write, "raw", True),
    ]


def run_matrix(lengths: Iterable[int] = LENGTHS) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix="t65-", dir="/tmp"))
    rows: list[Outcome] = []
    try:
        for length in lengths:
            for name, fn, mode in production_specs(scratch):
                trial = scratch / f"p-{name.replace('.', '_')}-{length}"
                trial.mkdir()
                target = path_of_length(trial, length)
                rows.append(
                    classify(
                        writer=name,
                        kind="production",
                        length=length,
                        intended=target,
                        payload=PAYLOAD,
                        mode=mode,
                        scratch=trial,
                        fn=fn,
                        mkdir=True,
                    )
                )
            for name, fn, mode in planted_specs():
                trial = scratch / f"c-{name.replace('.', '_')}-{length}"
                trial.mkdir()
                target = path_of_length(trial, length)
                rows.append(
                    classify(
                        writer=name,
                        kind="planted-control",
                        length=length,
                        intended=target,
                        payload=PAYLOAD,
                        mode=mode,
                        scratch=trial,
                        fn=fn,
                        mkdir=True,
                    )
                )
            for name, fn, mode, extended in win32_specs():
                trial = scratch / f"w-{name.replace('.', '_')}-{length}"
                trial.mkdir()
                target = path_of_length(trial, length)
                rows.append(
                    classify(
                        writer=name,
                        kind="win32-sim",
                        length=length,
                        intended=target,
                        payload=PAYLOAD,
                        mode=mode,
                        scratch=trial,
                        fn=fn,
                        mkdir=True,
                        used_extended_prefix=extended,
                    )
                )
        return {
            "host": os.uname().sysname,
            "path_max": os.pathconf("/tmp", "PC_PATH_MAX"),
            "name_max": os.pathconf("/tmp", "PC_NAME_MAX"),
            "win32_max_path": WIN32_MAX_PATH,
            "lengths": list(lengths),
            "payload": MARKER,
            "outcomes": [row.as_dict() for row in rows],
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def production_rows(matrix: dict) -> list[dict]:
    return [r for r in matrix["outcomes"] if r["kind"] == "production"]


def planted_rows(matrix: dict) -> list[dict]:
    return [r for r in matrix["outcomes"] if r["kind"] == "planted-control"]


def win32_rows(matrix: dict) -> list[dict]:
    return [r for r in matrix["outcomes"] if r["kind"] == "win32-sim"]
