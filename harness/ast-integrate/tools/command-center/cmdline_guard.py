"""Windows CreateProcess 32767-char guard with prompt-file switch (TST-0063).

CreateProcessW's ``lpCommandLine`` holds at most 32767 characters INCLUDING the
terminating NUL; a longer inline prompt dies with WinError 206
(``ERROR_FILENAME_EXCED_RANGE``). Linux ``ARG_MAX`` is far larger, so a green
spawn on this box proves nothing about Windows. The marshaller therefore
MEASURES the would-be inline command line (``subprocess.list2cmdline`` quoting,
the MS C runtime rules CPython applies on Windows) and, when strlen+NUL would
exceed the ceiling, writes the prompt to a file and passes ``--prompt-file``
instead, logging the switch so a near-miss stays visible.

The regression seed is a real prompt of ``payload_len == 34472`` that died
inline; ``INLINE_PAYLOAD_THAT_DIED`` is that length.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

WINDOWS_CREATEPROCESS_CHAR_CEILING = 32767  # lpCommandLine characters incl. NUL
WINERROR_FILENAME_EXCED_RANGE = 206
INLINE_PAYLOAD_THAT_DIED = 34472  # payload_len of the inline prompt that died
SWITCH_EVENT = "switched-to-prompt-file"
PROMPT_FILE_NAME = "prompt.txt"
TRANSPORT_INLINE = "inline"
TRANSPORT_FILE = "prompt-file"
E2BIG = 7


def windows_cmdline_chars(argv: Sequence[str]) -> int:
    """Characters of the command line CreateProcessW would receive (before NUL).

    ``subprocess.list2cmdline`` is the quoting CPython uses on Windows, so the
    count is the one the 32767 ceiling applies to."""
    return len(subprocess.list2cmdline([str(arg) for arg in argv]))


def would_raise_206(cmdline_chars: int) -> bool:
    """True when strlen + the terminating NUL exceeds the CreateProcessW ceiling."""
    return int(cmdline_chars) + 1 > WINDOWS_CREATEPROCESS_CHAR_CEILING


def payload_digest(payload: str) -> str:
    """sha256 hex of the UTF-8 payload; the child echoes it to prove intact delivery."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def inline_argv(vendor: Sequence[str], payload: str, extra: Sequence[str] = ()) -> list[str]:
    """The argv an unguarded dispatcher would spawn: prompt body on the command line."""
    return [str(a) for a in vendor] + ["--prompt", payload] + [str(a) for a in extra]


def pad_payload_for_inline_chars(
    vendor: Sequence[str], extra: Sequence[str], target: int
) -> str:
    """A payload whose INLINE command line measures exactly ``target`` characters.

    Fixed-point search over the payload length: quoting is monotone in the
    payload for the plain 'P' fill, so the delta converges in one or two steps."""
    extra = list(extra)
    n = max(0, int(target))
    payload = "P" * n
    for _ in range(8):
        got = windows_cmdline_chars(inline_argv(vendor, payload, extra))
        delta = int(target) - got
        if delta == 0:
            return payload
        n = max(0, n + delta)
        payload = "P" * n
    got = windows_cmdline_chars(inline_argv(vendor, payload, extra))
    if got != target:
        raise RuntimeError(f"pad missed target={target} got={got}")
    return payload


@dataclass
class Marshal:
    """How one prompt was marshalled onto the child's command line."""

    transport: str  # TRANSPORT_INLINE | TRANSPORT_FILE
    switched: bool
    inline_chars: int  # chars of the would-be inline command line
    would_raise_206_if_inline: bool
    windows_chars: int  # chars of the command line actually spawned
    payload_chars: int
    argv: list[str]
    prompt_file: str | None = None
    ceiling: int = WINDOWS_CREATEPROCESS_CHAR_CEILING
    log: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "switched": self.switched,
            "inline_chars": self.inline_chars,
            "would_raise_206_if_inline": self.would_raise_206_if_inline,
            "windows_chars": self.windows_chars,
            "payload_chars": self.payload_chars,
            "prompt_file": self.prompt_file,
            "ceiling": self.ceiling,
            "log": list(self.log),
        }


def switch_event(inline_chars: int, payload_chars: int) -> dict[str, Any]:
    """The structured log record emitted when the marshaller switches transport."""
    return {
        "event": SWITCH_EVENT,
        "from": TRANSPORT_INLINE,
        "to": TRANSPORT_FILE,
        "inline_chars": int(inline_chars),
        "ceiling": WINDOWS_CREATEPROCESS_CHAR_CEILING,
        "winerror_if_inline": WINERROR_FILENAME_EXCED_RANGE,
        "payload_chars": int(payload_chars),
        "prompt_file": PROMPT_FILE_NAME,
    }


def format_switch_line(event: dict[str, Any]) -> str:
    """One deterministic stderr line per switch (no paths, no timestamps)."""
    return (
        f"{event['event']} inline_chars={event['inline_chars']} "
        f"ceiling={event['ceiling']} to={event['to']} "
        f"payload_chars={event['payload_chars']} "
        f"winerror_if_inline={event['winerror_if_inline']}"
    )


def marshal_prompt(
    vendor: Sequence[str],
    payload: str,
    workdir: Path,
    *,
    extra: Sequence[str] = (),
    force_inline: bool = False,
    log_switch: bool = True,
) -> Marshal:
    """Measure the inline command line; switch to ``--prompt-file`` when it would die.

    ``force_inline`` keeps the prompt on argv regardless (the unguarded path the
    probes drive under the CreateProcess emulator). ``log_switch=False`` is the
    silent-switch mutant: it still switches but records nothing, which is the
    failure mode TST-0063 must be able to detect."""
    argv_inline = inline_argv(vendor, payload, extra)
    chars = windows_cmdline_chars(argv_inline)
    over = would_raise_206(chars)
    if over and not force_inline:
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        prompt_file = workdir / PROMPT_FILE_NAME
        prompt_file.write_text(payload, encoding="utf-8", newline="\n")
        argv = [str(a) for a in vendor] + ["--prompt-file", str(prompt_file)]
        argv += [str(a) for a in extra]
        marshal = Marshal(
            transport=TRANSPORT_FILE,
            switched=True,
            inline_chars=chars,
            would_raise_206_if_inline=True,
            windows_chars=windows_cmdline_chars(argv),
            payload_chars=len(payload),
            argv=argv,
            prompt_file=PROMPT_FILE_NAME,
        )
        if log_switch:
            marshal.log.append(switch_event(chars, len(payload)))
        return marshal
    return Marshal(
        transport=TRANSPORT_INLINE,
        switched=False,
        inline_chars=chars,
        would_raise_206_if_inline=over,
        windows_chars=chars,
        payload_chars=len(payload),
        argv=argv_inline,
    )


@dataclass
class SpawnResult:
    """Outcome of one guarded (or deliberately unguarded) vendor spawn."""

    exit_code: int
    winerror: int | None
    marshal: Marshal
    child: dict[str, Any] | None = None
    stderr: str = ""
    stdout: str = ""
    host: str = sys.platform
    guarded: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "winerror": self.winerror,
            "transport": self.marshal.transport,
            "switched": self.marshal.switched,
            "inline_chars": self.marshal.inline_chars,
            "windows_chars": self.marshal.windows_chars,
            "payload_chars": self.marshal.payload_chars,
            "would_raise_206_if_inline": self.marshal.would_raise_206_if_inline,
            "log": list(self.marshal.log),
            "child": self.child,
            "host": self.host,
            "guarded": self.guarded,
        }


def parse_child_report(stdout: str, returncode: int) -> dict[str, Any] | None:
    """The child's JSON report (last stdout line, else the whole stream), if any."""
    text = (stdout or "").strip()
    if not text:
        return None
    for candidate in (text.splitlines()[-1], text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {"ok": returncode == 0, "raw": text[:200]}


def _resolve_workdir(workdir: Path | str | None) -> Path:
    if workdir is None:
        return Path(tempfile.mkdtemp(prefix="cmdline-guard-"))
    path = Path(workdir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def emulated_206(marshal: Marshal, *, guarded: bool = True) -> SpawnResult:
    """What CreateProcessW does with an over-ceiling command line: no child, 206."""
    message = (
        f"[WinError {WINERROR_FILENAME_EXCED_RANGE}] The filename or extension is "
        f"too long (ERROR_FILENAME_EXCED_RANGE): command line "
        f"{marshal.windows_chars}+NUL chars exceeds {WINDOWS_CREATEPROCESS_CHAR_CEILING}"
    )
    return SpawnResult(
        exit_code=WINERROR_FILENAME_EXCED_RANGE,
        winerror=WINERROR_FILENAME_EXCED_RANGE,
        marshal=marshal,
        child=None,
        stderr="".join(format_switch_line(e) + "\n" for e in marshal.log) + message + "\n",
        host="windows-createprocess-emulated",
        guarded=guarded,
    )


def spawn_guarded(
    vendor: Sequence[str],
    payload: str,
    workdir: Path | str | None = None,
    *,
    extra: Sequence[str] = (),
    force_inline: bool = False,
    emulate_createprocess: bool = False,
    log_switch: bool = True,
    timeout: float = 120.0,
) -> SpawnResult:
    """Marshal the prompt, then spawn the vendor CLI with the safe transport.

    With ``emulate_createprocess=True`` an over-ceiling command line is refused
    exactly as CreateProcessW refuses it (WinError 206, no child) instead of
    being handed to the Linux kernel, whose ARG_MAX would let it through."""
    root = _resolve_workdir(workdir)
    marshal = marshal_prompt(
        vendor, payload, root, extra=extra, force_inline=force_inline, log_switch=log_switch
    )
    if emulate_createprocess and would_raise_206(marshal.windows_chars):
        return emulated_206(marshal)
    switch_lines = "".join(format_switch_line(e) + "\n" for e in marshal.log)
    if switch_lines:
        sys.stderr.write(switch_lines)
        sys.stderr.flush()
    proc = subprocess.run(
        marshal.argv, cwd=str(root), capture_output=True, text=True, timeout=timeout
    )
    return SpawnResult(
        exit_code=proc.returncode,
        winerror=None,
        marshal=marshal,
        child=parse_child_report(proc.stdout, proc.returncode),
        stderr=switch_lines + (proc.stderr or ""),
        stdout=proc.stdout or "",
        host=sys.platform,
        guarded=True,
    )


def naive_linux_spawn(
    vendor: Sequence[str],
    payload: str,
    workdir: Path | str | None = None,
    *,
    extra: Sequence[str] = (),
    timeout: float = 120.0,
) -> SpawnResult:
    """The unguarded control: prompt inline on argv, straight to the host kernel.

    Succeeding here past the Windows ceiling is the point — Linux ARG_MAX is not
    the detector, so a green spawn on this box must never be read as PASS for
    the Windows guard."""
    root = _resolve_workdir(workdir)
    argv = inline_argv(vendor, payload, extra)
    chars = windows_cmdline_chars(argv)
    marshal = Marshal(
        transport=TRANSPORT_INLINE,
        switched=False,
        inline_chars=chars,
        would_raise_206_if_inline=would_raise_206(chars),
        windows_chars=chars,
        payload_chars=len(payload),
        argv=argv,
    )
    try:
        proc = subprocess.run(
            argv, cwd=str(root), capture_output=True, text=True, timeout=timeout
        )
    except OSError as exc:  # E2BIG: even ARG_MAX has a ceiling
        return SpawnResult(
            exit_code=getattr(exc, "errno", None) or E2BIG,
            winerror=None,
            marshal=marshal,
            child=None,
            stderr=f"{type(exc).__name__}: {exc}\n",
            host=sys.platform,
            guarded=False,
        )
    return SpawnResult(
        exit_code=proc.returncode,
        winerror=None,
        marshal=marshal,
        child=parse_child_report(proc.stdout, proc.returncode),
        stderr=proc.stderr or "",
        stdout=proc.stdout or "",
        host=sys.platform,
        guarded=False,
    )


__all__ = [
    "E2BIG",
    "INLINE_PAYLOAD_THAT_DIED",
    "Marshal",
    "PROMPT_FILE_NAME",
    "SWITCH_EVENT",
    "SpawnResult",
    "TRANSPORT_FILE",
    "TRANSPORT_INLINE",
    "WINDOWS_CREATEPROCESS_CHAR_CEILING",
    "WINERROR_FILENAME_EXCED_RANGE",
    "emulated_206",
    "format_switch_line",
    "inline_argv",
    "marshal_prompt",
    "naive_linux_spawn",
    "pad_payload_for_inline_chars",
    "parse_child_report",
    "payload_digest",
    "spawn_guarded",
    "switch_event",
    "windows_cmdline_chars",
    "would_raise_206",
]
