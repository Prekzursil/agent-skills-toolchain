"""Argv-array marshaller: over-limit payloads travel via a 0600 payload file."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

HERE = Path(__file__).resolve().parent
RECEIVER = HERE / "payload_receiver.py"

WINDOWS_CREATEPROCESS_LIMIT = 32767
ERROR_FILENAME_EXCED_RANGE = 206
CONSERVATIVE_THRESHOLD = 8191


def make_over_limit_payload(n: int) -> str:
    return "P" * int(n)


def default_prefix() -> list[str]:
    return [sys.executable, "-B", str(RECEIVER)]


def windows_cmdline_length(argv: Sequence[str]) -> int:
    if os.name == "nt":
        return len(subprocess.list2cmdline(list(argv)))
    # Same CreateProcess formula the Windows probe is proving: quoted join.
    total = 0
    for i, arg in enumerate(argv):
        if i:
            total += 1
        if not arg or any(ch in arg for ch in ' \t"'):
            total += 2 + len(arg.replace('"', '\\"'))
        else:
            total += len(arg)
    return total


def is_createprocess_206(exc: BaseException) -> bool:
    if not isinstance(exc, OSError):
        return False
    if int(getattr(exc, "winerror", 0) or 0) == ERROR_FILENAME_EXCED_RANGE:
        return True
    return int(getattr(exc, "errno", 0) or 0) == ERROR_FILENAME_EXCED_RANGE


class CreateProcessTooLong(OSError):
    def __init__(self, length: int) -> None:
        super().__init__(
            ERROR_FILENAME_EXCED_RANGE,
            "The filename or extension is too long",
        )
        self.errno = ERROR_FILENAME_EXCED_RANGE
        self.winerror = ERROR_FILENAME_EXCED_RANGE
        self.cmdline_length = length


@dataclass
class PreparedPayload:
    argv: list[str]
    payload_path: str | None
    payload_dir: str | None
    transport: str
    inline_cmdline_length: int
    argv_cmdline_length: int
    file_mode: int | None = None
    env: dict[str, str] | None = None
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.payload_path:
            try:
                os.unlink(self.payload_path)
            except OSError:
                pass
        if self.payload_dir:
            try:
                os.rmdir(self.payload_dir)
            except OSError:
                pass


@dataclass
class SpawnResult:
    returncode: int
    stdout: str
    stderr: str
    transport: str
    child_reported_bytes: int
    child_source: str
    child_sha256: str
    inline_cmdline_length: int
    argv_cmdline_length: int
    cleaned: bool
    payload_path_exists_after: bool
    file_mode: int | None


class ArgMarshaller:
    def prepare(self, prefix: Sequence[str], payload: str) -> PreparedPayload:
        inline = list(prefix) + [payload]
        inline_len = windows_cmdline_length(inline)
        tmp = tempfile.mkdtemp(prefix="argmarshall-")
        os.chmod(tmp, 0o700)
        path = os.path.join(tmp, "payload.txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
        os.chmod(path, 0o600)
        argv = list(prefix) + ["--file", path]
        env = os.environ.copy()
        env["IMP0018_PAYLOAD_FILE"] = path
        env["ARG_MARSHALL_PAYLOAD_FILE"] = path
        return PreparedPayload(
            argv=argv,
            payload_path=path,
            payload_dir=tmp,
            transport="payload-file",
            inline_cmdline_length=inline_len,
            argv_cmdline_length=windows_cmdline_length(argv),
            file_mode=stat.S_IMODE(os.stat(path).st_mode),
            env=env,
        )

    def run(
        self,
        prepared: PreparedPayload,
        spawn: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            if spawn is None:
                return subprocess.run(
                    prepared.argv,
                    capture_output=True,
                    text=True,
                    env=prepared.env,
                    timeout=30,
                )
            return spawn(prepared.argv, env=prepared.env)
        finally:
            prepared.close()


def spawn_payload(payload: str, force_inline: bool = False) -> SpawnResult:
    prefix = default_prefix()
    inline = list(prefix) + [payload]
    inline_len = windows_cmdline_length(inline)
    if force_inline:
        raise CreateProcessTooLong(inline_len)
    marshaller = ArgMarshaller()
    prepared = marshaller.prepare(prefix, payload)
    path = prepared.payload_path
    file_mode = prepared.file_mode
    argv_len = prepared.argv_cmdline_length
    try:
        proc = marshaller.run(prepared)
    except Exception:
        exists = bool(path and os.path.exists(path))
        raise
    exists = bool(path and os.path.exists(path))
    stdout = proc.stdout or ""
    child_bytes = 0
    child_source = ""
    child_sha = ""
    try:
        rec = __import__("json").loads(stdout.splitlines()[-1])
        child_bytes = int(rec.get("bytes") or 0)
        child_source = str(rec.get("source") or "")
        child_sha = str(rec.get("sha256") or "")
    except Exception:
        pass
    return SpawnResult(
        returncode=int(proc.returncode),
        stdout=stdout,
        stderr=proc.stderr or "",
        transport="payload-file",
        child_reported_bytes=child_bytes,
        child_source=child_source,
        child_sha256=child_sha,
        inline_cmdline_length=inline_len,
        argv_cmdline_length=argv_len,
        cleaned=not exists,
        payload_path_exists_after=exists,
        file_mode=file_mode,
    )


def arg_marshalling(*args, **kwargs):
    return spawn_payload(args[0] if args else make_over_limit_payload(8))
