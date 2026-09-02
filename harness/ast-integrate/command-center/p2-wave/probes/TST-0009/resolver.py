"""Evidence-anchor resolvability by kind.

Kinds:
  file:line  — path exists on the worktree AND has at least that many lines.
               A line number past EOF is unresolved.
  command    — re-execute and compare against the recorded exit code.
  inferred   — explicit 'inferred from <named source>'; unnamed source fails.

Unknown kind is unresolved. This module does not count an anchor as resolved
just because a string looks like a path.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

FILE_LINE = "file:line"
COMMAND = "command"
INFERRED = "inferred"
UNKNOWN = "unknown"

RESOLVED = "resolved"
UNRESOLVED = "unresolved"
NOT_REEXECUTED = "not-reexecuted"

FILE_LINE_RE = re.compile(
    r"^(?P<path>(?:[A-Za-z]:)?[^\s:*?\"<>|]+):(?P<line>\d+)$"
)
INFERRED_RE = re.compile(
    r"(?is)^inferred\s+from\s+(?P<source>\S(?:.*\S)?)\s*$"
)
SAFE_COMMAND_RE = re.compile(
    r"^(?:"
    r"(?:PYTHONDONTWRITEBYTECODE=1\s+)?"
    r"(?:/usr/bin/env\s+)?"
    r"(?:python3|true|false|/bin/true|/bin/false|/usr/bin/true|/usr/bin/false)"
    r"(?:\s+-c\s+.+)?|"
    r"echo\s+.+"
    r")$"
)

_ALNUM = re.compile(r"[A-Za-z0-9]")


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def named_source(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not _ALNUM.search(text):
        return ""
    low = text.lower()
    if low in {"x", "n/a", "na", "none", "unknown", "tbd", "?", "-"}:
        return ""
    return text


def classify(spec: Any) -> str:
    if isinstance(spec, dict):
        kind = str(spec.get("kind") or spec.get("method") or "").strip().lower()
        kind = kind.replace("_", "-").replace(" ", "")
        if kind in {"file:line", "file-line", "path:line", "fileline"}:
            return FILE_LINE
        if kind in {"command", "cmd", "shell"}:
            return COMMAND
        if kind in {"inferred", "inferred-from", "inferredfrom"}:
            return INFERRED
        if _as_int(spec.get("line")) is not None and (
            spec.get("path") or spec.get("file") or spec.get("relpath")
        ):
            return FILE_LINE
        if spec.get("command") or spec.get("cmd"):
            return COMMAND
        src = spec.get("source") or spec.get("inferred_from") or spec.get("inferredFrom")
        if src and (kind.startswith("infer") or spec.get("inferred") is True):
            return INFERRED
        raw = spec.get("anchor") or spec.get("detail") or spec.get("ref") or ""
        return classify(raw)
    if not isinstance(spec, str):
        return UNKNOWN
    text = spec.strip()
    if not text:
        return UNKNOWN
    if INFERRED_RE.match(text):
        return INFERRED
    m = FILE_LINE_RE.match(text)
    if m:
        path = m.group("path")
        if "/" in path or "\\" in path or "." in Path(path).name:
            return FILE_LINE
    if SAFE_COMMAND_RE.match(text) or text.startswith("python3 ") or text.startswith(
        "PYTHONDONTWRITEBYTECODE="
    ):
        return COMMAND
    return UNKNOWN


def parse_spec(spec: Any) -> dict[str, Any]:
    kind = classify(spec)
    out: dict[str, Any] = {"kind": kind, "raw": spec}
    if isinstance(spec, dict):
        if kind == FILE_LINE:
            out["path"] = str(
                spec.get("path") or spec.get("file") or spec.get("relpath") or ""
            ).replace("\\", "/")
            out["line"] = _as_int(spec.get("line"))
            if not out["path"]:
                parsed = parse_spec(str(spec.get("anchor") or ""))
                out["path"] = parsed.get("path") or ""
                out["line"] = parsed.get("line")
        elif kind == COMMAND:
            out["command"] = str(spec.get("command") or spec.get("cmd") or "").strip()
            rec = spec.get("recorded_exit")
            if rec is None:
                rec = spec.get("exit_code")
            if rec is None:
                rec = spec.get("expected_exit")
            out["recorded_exit"] = _as_int(rec)
        elif kind == INFERRED:
            src = spec.get("source") or spec.get("inferred_from") or spec.get("inferredFrom")
            if not src:
                m = INFERRED_RE.match(str(spec.get("anchor") or spec.get("detail") or ""))
                src = m.group("source") if m else ""
            out["source"] = named_source(src)
        return out
    text = str(spec or "").strip()
    if kind == FILE_LINE:
        m = FILE_LINE_RE.match(text)
        if m:
            out["path"] = m.group("path").replace("\\", "/")
            out["line"] = int(m.group("line"))
    elif kind == COMMAND:
        out["command"] = text
        out["recorded_exit"] = None
    elif kind == INFERRED:
        m = INFERRED_RE.match(text)
        out["source"] = named_source(m.group("source") if m else "")
    return out


def line_count(path: Path) -> int:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not data:
        return 0
    n = data.count(b"\n")
    if data.endswith(b"\n"):
        return n
    return n + 1


def resolve_file_line(repo: Path, rel: str, line: int | None) -> dict[str, Any]:
    rel_n = (rel or "").replace("\\", "/").lstrip("/")
    if not rel_n or line is None:
        return {
            "outcome": UNRESOLVED,
            "reason": "file-line-missing-path-or-line",
            "line_count": None,
        }
    path = (repo / rel_n).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError:
        return {
            "outcome": UNRESOLVED,
            "reason": "path-escapes-repo",
            "line_count": None,
        }
    if not path.is_file():
        return {
            "outcome": UNRESOLVED,
            "reason": "file-missing",
            "line_count": None,
        }
    n = line_count(path)
    if line < 1:
        return {
            "outcome": UNRESOLVED,
            "reason": "line-not-positive",
            "line_count": n,
        }
    if line > n:
        return {
            "outcome": UNRESOLVED,
            "reason": "line-beyond-eof",
            "line_count": n,
        }
    return {"outcome": RESOLVED, "reason": "file-has-line", "line_count": n}


def command_is_safe(command: str) -> bool:
    cmd = " ".join((command or "").split())
    if not cmd:
        return False
    if SAFE_COMMAND_RE.match(cmd):
        return True
    if cmd.startswith("python3 -c ") or cmd.startswith("python3 -c'") or cmd.startswith(
        'python3 -c"'
    ):
        return True
    if cmd.startswith("PYTHONDONTWRITEBYTECODE=1 python3 -c "):
        return True
    return False


def reexec_command(repo: Path, command: str, timeout: float = 20.0) -> tuple[int | None, str]:
    if not command_is_safe(command):
        return None, "command-not-safely-reexecutable"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            command,
            cwd=str(repo),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None, "command-timeout"
    except OSError as exc:
        return None, f"command-oserror:{type(exc).__name__}"
    return proc.returncode, "reexecuted"


def resolve_command(repo: Path, command: str, recorded_exit: int | None) -> dict[str, Any]:
    if not (command or "").strip():
        return {
            "outcome": UNRESOLVED,
            "reason": "command-missing",
            "observed_exit": None,
        }
    if recorded_exit is None:
        return {
            "outcome": UNRESOLVED,
            "reason": "recorded-exit-missing",
            "observed_exit": None,
        }
    observed, why = reexec_command(repo, command)
    if observed is None:
        outcome = NOT_REEXECUTED if why == "command-not-safely-reexecutable" else UNRESOLVED
        return {"outcome": outcome, "reason": why, "observed_exit": None}
    if observed != recorded_exit:
        return {
            "outcome": UNRESOLVED,
            "reason": f"exit-mismatch:recorded={recorded_exit}:observed={observed}",
            "observed_exit": observed,
        }
    return {
        "outcome": RESOLVED,
        "reason": "exit-matches-recorded",
        "observed_exit": observed,
    }


def resolve_inferred(source: str) -> dict[str, Any]:
    named = named_source(source)
    if not named:
        return {"outcome": UNRESOLVED, "reason": "inferred-source-unnamed"}
    return {"outcome": RESOLVED, "reason": f"inferred-from:{named}", "source": named}


def resolve(repo: Path, spec: Any) -> dict[str, Any]:
    parsed = parse_spec(spec)
    kind = parsed["kind"]
    row = {
        "kind": kind,
        "raw": parsed.get("raw"),
        "path": parsed.get("path"),
        "line": parsed.get("line"),
        "command": parsed.get("command"),
        "recorded_exit": parsed.get("recorded_exit"),
        "source": parsed.get("source"),
        "outcome": UNRESOLVED,
        "reason": "unclassified",
        "line_count": None,
        "observed_exit": None,
    }
    if kind == FILE_LINE:
        got = resolve_file_line(repo, parsed.get("path") or "", parsed.get("line"))
    elif kind == COMMAND:
        got = resolve_command(
            repo, parsed.get("command") or "", parsed.get("recorded_exit")
        )
    elif kind == INFERRED:
        got = resolve_inferred(parsed.get("source") or "")
    else:
        got = {"outcome": UNRESOLVED, "reason": "unknown-kind"}
    row.update({k: v for k, v in got.items() if v is not None or k == "outcome"})
    return row
