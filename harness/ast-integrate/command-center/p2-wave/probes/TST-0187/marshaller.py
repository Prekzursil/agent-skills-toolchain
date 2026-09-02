#!/usr/bin/env python3
"""Windows CreateProcess command-line length guard + file-route marshaller.

Catalog TST-0187 / IMP-0018 / IMP-0424: payloads that would make the marshalled
CreateProcess lpCommandLine hit 32,767 characters (including the terminating
NUL, per MSDN) must go to a temp file; the child receives a PATH, never the
blob, so spawn argv stays under the ceiling.

This Linux box cannot observe CreateProcess OS error 206. The guard uses the
documented ceiling plus a live-measured prefix length. Unguarded inline of
payload_len=34472 is classified as error 206 by the Windows length metric;
a live Linux spawn of the same inline payload is recorded separately so the
platform gap is not laundered into a pass.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHILD = HERE / "child_echo.py"

# MSDN CreateProcessW lpCommandLine: max 32,767 characters including NUL.
WINDOWS_CREATEPROCESS_CEILING = 32767
# ERROR_FILENAME_EXCED_RANGE — the regression seed in cross-vendor-dispatch.md:3.
ERROR_FILENAME_EXCED_RANGE = 206
REGRESSION_PAYLOAD_LEN = 34472
TEN_X_CEILING = WINDOWS_CREATEPROCESS_CEILING * 10

# Headroom so the guard fires BELOW the ceiling even if the executable path
# grows (MAX_PATH, quoting, extra flags). Live prefix is measured at dispatch.
HEADROOM_CHARS = 4096
GUARD_THRESHOLD_CHARS = WINDOWS_CREATEPROCESS_CEILING - HEADROOM_CHARS  # 28671


def list2cmdline(seq: list[str]) -> str:
    """MS C-runtime / CreateProcess quoting (CPython subprocess.list2cmdline)."""
    result: list[str] = []
    for arg in seq:
        bs_buf: list[str] = []
        if result:
            result.append(" ")
        needquote = (" " in arg) or ("\t" in arg) or (not arg)
        if needquote:
            result.append('"')
        for c in arg:
            if c == "\\":
                bs_buf.append(c)
            elif c == '"':
                result.append("\\" * (len(bs_buf) * 2))
                bs_buf = []
                result.append('\\"')
            else:
                if bs_buf:
                    result.extend(bs_buf)
                    bs_buf = []
                result.append(c)
        if bs_buf:
            result.extend(bs_buf)
        if needquote:
            result.extend(bs_buf)
            result.append('"')
    return "".join(result)


def win_string_chars(argv: list[str]) -> int:
    return len(list2cmdline(argv))


def win_cmdline_chars(argv: list[str]) -> int:
    """Character count CreateProcessW would see, including terminating NUL."""
    return win_string_chars(argv) + 1


def argv_utf8_bytes(argv: list[str]) -> int:
    return sum(len(a.encode("utf-8")) for a in argv)


def argv_nul_joined_bytes(argv: list[str]) -> int:
    return sum(len(a.encode("utf-8")) + 1 for a in argv)


def prefix_argv() -> list[str]:
    return [sys.executable, "-B", str(CHILD)]


def inline_argv(payload: str) -> list[str]:
    return prefix_argv() + ["--payload", payload]


def file_argv(path: str) -> list[str]:
    return prefix_argv() + ["--payload-file", path]


def would_hit_windows_ceiling(argv: list[str]) -> bool:
    return win_cmdline_chars(argv) > WINDOWS_CREATEPROCESS_CEILING


def should_route_to_file(payload: str) -> bool:
    return win_cmdline_chars(inline_argv(payload)) >= GUARD_THRESHOLD_CHARS


@dataclass
class DispatchResult:
    argv_nul_joined_bytes_at_dispatch: int
    argv_utf8_bytes_at_dispatch: int
    expected_child_argv_utf8_bytes: int
    child_argv_utf8_bytes: int | None
    child_payload_len: int | None
    child_payload_sha256: str | None
    child_source: str | None
    exit_code: int
    file_cleaned: bool
    file_path: str | None
    live_spawned: bool
    payload_len: int
    payload_sha256: str
    transport: str
    win_cmdline_chars_at_spawn: int
    win_cmdline_chars_inline_hypothetical: int
    win_string_chars_at_spawn: int
    windows_error: int | None
    windows_sim_applied: bool


def _write_payload_file(payload: str) -> Path:
    fd, name = tempfile.mkstemp(prefix="tst0187-payload-", suffix=".txt", text=True)
    path = Path(name)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        path.unlink(missing_ok=True)
        raise
    return path


def _parse_child(stdout: str) -> dict:
    line = (stdout or "").strip().splitlines()
    if not line:
        return {}
    try:
        doc = json.loads(line[-1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _dispatch(
    payload: str,
    *,
    force_inline: bool,
    windows_sim: bool,
    live_spawn: bool,
) -> DispatchResult:
    if not isinstance(payload, str):
        raise TypeError("payload must be str")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    inline = inline_argv(payload)
    hypo = win_cmdline_chars(inline)
    use_file = (not force_inline) and (hypo >= GUARD_THRESHOLD_CHARS)
    tmp: Path | None = None
    result: DispatchResult | None = None
    try:
        if use_file:
            tmp = _write_payload_file(payload)
            argv = file_argv(str(tmp))
            transport = "file"
        else:
            argv = inline
            transport = "inline"
        win_at = win_cmdline_chars(argv)
        win_str = win_string_chars(argv)
        parent_utf8 = argv_utf8_bytes(argv)
        parent_nul = argv_nul_joined_bytes(argv)
        # subprocess argv is [python, -B, child, ...]; child's sys.argv is argv[2:]
        expected_child_utf8 = argv_utf8_bytes(argv[2:])
        hit = would_hit_windows_ceiling(argv)
        if windows_sim and hit:
            result = DispatchResult(
                argv_nul_joined_bytes_at_dispatch=parent_nul,
                argv_utf8_bytes_at_dispatch=parent_utf8,
                expected_child_argv_utf8_bytes=expected_child_utf8,
                child_argv_utf8_bytes=None,
                child_payload_len=None,
                child_payload_sha256=None,
                child_source=None,
                exit_code=206,
                file_cleaned=False,
                file_path=str(tmp) if tmp else None,
                live_spawned=False,
                payload_len=len(payload),
                payload_sha256=digest,
                transport=transport,
                win_cmdline_chars_at_spawn=win_at,
                win_cmdline_chars_inline_hypothetical=hypo,
                win_string_chars_at_spawn=win_str,
                windows_error=ERROR_FILENAME_EXCED_RANGE,
                windows_sim_applied=True,
            )
        elif not live_spawn:
            result = DispatchResult(
                argv_nul_joined_bytes_at_dispatch=parent_nul,
                argv_utf8_bytes_at_dispatch=parent_utf8,
                expected_child_argv_utf8_bytes=expected_child_utf8,
                child_argv_utf8_bytes=None,
                child_payload_len=None,
                child_payload_sha256=None,
                child_source=None,
                exit_code=0,
                file_cleaned=False,
                file_path=str(tmp) if tmp else None,
                live_spawned=False,
                payload_len=len(payload),
                payload_sha256=digest,
                transport=transport,
                win_cmdline_chars_at_spawn=win_at,
                win_cmdline_chars_inline_hypothetical=hypo,
                win_string_chars_at_spawn=win_str,
                windows_error=None,
                windows_sim_applied=False,
            )
        else:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                argv,
                cwd=str(HERE.parents[3]),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            child = _parse_child(proc.stdout)
            result = DispatchResult(
                argv_nul_joined_bytes_at_dispatch=parent_nul,
                argv_utf8_bytes_at_dispatch=parent_utf8,
                expected_child_argv_utf8_bytes=expected_child_utf8,
                child_argv_utf8_bytes=child.get("argv_utf8_bytes"),
                child_payload_len=child.get("payload_len"),
                child_payload_sha256=child.get("payload_sha256"),
                child_source=child.get("source"),
                exit_code=int(proc.returncode),
                file_cleaned=False,
                file_path=str(tmp) if tmp else None,
                live_spawned=True,
                payload_len=len(payload),
                payload_sha256=digest,
                transport=transport,
                win_cmdline_chars_at_spawn=win_at,
                win_cmdline_chars_inline_hypothetical=hypo,
                win_string_chars_at_spawn=win_str,
                windows_error=None,
                windows_sim_applied=False,
            )
    finally:
        cleaned = True
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            cleaned = not tmp.exists()
        if result is not None:
            result.file_cleaned = cleaned
    if result is None:
        raise RuntimeError("dispatch produced no result")
    return result


def invoke(payload: str) -> DispatchResult:
    """Production entry: never inlines a payload that would approach the ceiling."""
    return _dispatch(
        payload, force_inline=False, windows_sim=True, live_spawn=True
    )


def unguarded_inline_windows(payload: str) -> DispatchResult:
    """Test-only known-bad path: force inline, apply Windows ceiling sim."""
    return _dispatch(
        payload, force_inline=True, windows_sim=True, live_spawn=True
    )


def unguarded_inline_linux_live(payload: str) -> DispatchResult:
    """Test-only: force inline with no Windows sim (Linux ARG_MAX contrast)."""
    return _dispatch(
        payload, force_inline=True, windows_sim=False, live_spawn=True
    )


def payload_for_inline_win_chars(target: int, alphabet: str = "A") -> str:
    """Build an ASCII payload whose *hypothetical inline* win_cmdline_chars == target.

    Uses binary search against the live prefix. Raises if the target is below
    the empty-payload baseline.
    """
    if len(alphabet) != 1 or ord(alphabet) > 127:
        raise ValueError("alphabet must be one ASCII character")
    lo, hi = 0, max(target, 1)
    baseline = win_cmdline_chars(inline_argv(""))
    if target < baseline:
        raise ValueError(f"target {target} < empty-payload baseline {baseline}")
    found: str | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        n = win_cmdline_chars(inline_argv(alphabet * mid))
        if n == target:
            found = alphabet * mid
            break
        if n < target:
            lo = mid + 1
        else:
            hi = mid - 1
    if found is None:
        # list2cmdline is monotonic in unquoted ASCII; land on the closest
        # length and pad/trim.
        n = max(0, lo)
        cand = alphabet * n
        got = win_cmdline_chars(inline_argv(cand))
        if got < target:
            cand = alphabet * (n + (target - got))
        elif got > target:
            trim = got - target
            if trim > n:
                raise ValueError(f"cannot land on target={target} got={got}")
            cand = alphabet * (n - trim)
        found = cand
    got = win_cmdline_chars(inline_argv(found))
    if got != target:
        raise ValueError(f"payload_for_inline_win_chars missed: want={target} got={got}")
    return found


def to_dict(result: DispatchResult) -> dict:
    return asdict(result)


if __name__ == "__main__":
    # Tiny self-check; probes are the contract.
    p = "ok"
    r = invoke(p)
    print(json.dumps(to_dict(r), separators=(",", ":")))
    raise SystemExit(0 if r.exit_code == 0 else 1)
