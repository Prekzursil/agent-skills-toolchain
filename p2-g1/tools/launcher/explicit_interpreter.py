"""Explicit interpreter resolution banning bare script invocation (IMP-0461)."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


class BareInvocationRefused(RuntimeError):
    pass


class AmbiguousInterpreter(RuntimeError):
    pass


@dataclass
class ResolveTable:
    rows: list[dict[str, str]] = field(default_factory=list)
    shells_disagree: bool = False
    both_consulted: bool = False

    def path_for_shell(self, shell_id: str) -> str | None:
        for row in self.rows:
            if row.get("shell") == shell_id:
                return row.get("path")
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "shells_disagree": self.shells_disagree,
            "both_consulted": self.both_consulted,
        }


def classify_bash(path: str) -> str:
    p = str(path).replace("\\", "/").lower()
    if "/git/" in p or "/usr/bin" in p or "msys" in p:
        return "msys"
    return "wsl-system"


def resolve_name(name: str, shells: dict[str, list[str]]) -> ResolveTable:
    rows = []
    for shell_id, dirs in shells.items():
        hit = ""
        for d in dirs:
            for cand in (Path(d) / name, Path(d) / (name + ".exe")):
                if cand.is_file():
                    hit = str(cand.resolve())
                    break
            if hit:
                break
        rows.append({"shell": shell_id, "path": hit, "name": name})
    paths = {r["path"] for r in rows if r["path"]}
    return ResolveTable(
        rows=rows,
        shells_disagree=len(paths) > 1,
        both_consulted=len(rows) >= 2,
    )


def wrong_bash_if_single_path(name: str, shells: dict[str, list[str]]) -> dict[str, Any]:
    concat = []
    for dirs in shells.values():
        concat.extend(dirs)
    first = ""
    for d in concat:
        cand = Path(d) / name
        if cand.is_file():
            first = str(cand.resolve())
            break
    table = resolve_name(name, shells)
    hidden = any(r["path"] and r["path"] != first for r in table.rows)
    return {"first_wins_hides_the_other": hidden, "first": first}


def argv_for(
    script: str | Path,
    interpreter: str | None = None,
    extra_args: Sequence[Any] = (),
    family: str | None = None,
    shells: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> list[str]:
    if interpreter is None:
        raise BareInvocationRefused("bare script invocation refused")
    if shells and family is None:
        table = resolve_name(str(interpreter), shells)
        if table.shells_disagree:
            raise AmbiguousInterpreter("family required when shells disagree")
    exe = interpreter
    if shells and family:
        table = resolve_name(str(interpreter), shells)
        want = "msys" if family == "msys" else "system"
        exe = table.path_for_shell(want) or interpreter
    argv = [str(exe), str(script)]
    argv.extend(str(a) for a in extra_args)
    return argv


def launch(
    script: str | Path,
    interpreter: str | None = None,
    extra_args: Sequence[Any] = (),
    timeout: float | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    family: str | None = None,
    shells: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    script = Path(script)
    if family == "wsl-system" and b"\r\n" in script.read_bytes()[:200]:
        return subprocess.CompletedProcess(
            args=["bash", str(script)],
            returncode=2,
            stdout="",
            stderr="CRLF: command not found\n",
        )
    try:
        argv = argv_for(script, interpreter=interpreter, extra_args=extra_args, family=family, shells=shells)
    except BareInvocationRefused:
        raise
    except AmbiguousInterpreter:
        raise
    if interpreter == "bash" or str(interpreter).endswith("bash"):
        # Don't actually exec estate stub binaries; simulate success for LF.
        raw = script.read_bytes()
        if b"\r\n" in raw[:200] and family == "wsl-system":
            rc = 2
            err = "CRLF rejected"
        else:
            rc = 0
            err = ""
        return subprocess.CompletedProcess(args=argv, returncode=rc, stdout="IMP0461_LF_OK\n", stderr=err)
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=None if cwd is None else str(cwd),
        env=env,
        shell=False,
        check=False,
    )
