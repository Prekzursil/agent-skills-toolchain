"""Claude adapter with permission allowlist + declared timeout. IMP-0420 / TST-0210."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Callable

CATALOG_DEFAULT_TIMEOUT_SECONDS = 1800
VOCAB = ("Read", "Grep", "Glob", "Write", "Edit", "Bash", "PowerShell")
_PYTHON_EXE = re.compile(r"^(python3?|python3?\.\d+)(\.exe)?$", re.IGNORECASE)


class PermissionDenied(RuntimeError):
    pass


class AdapterTimeout(RuntimeError):
    pass


class TimeoutUndeclared(RuntimeError):
    pass


def resolve_timeout_seconds(unit: dict[str, Any]) -> float:
    """Return the unit's declared timeout. Missing is an error, never a default."""
    if not isinstance(unit, dict):
        raise TimeoutUndeclared("unit is not a mapping")
    if "timeout_seconds" not in unit:
        raise TimeoutUndeclared("timeout_seconds missing")
    raw = unit["timeout_seconds"]
    if raw is None:
        raise TimeoutUndeclared("timeout_seconds is null")
    return float(raw)


def bound_tools(permissions: list[str] | None) -> list[str]:
    return list(permissions or [])


def abstraction_leaks_for(_unit: dict[str, Any]) -> list[str]:
    return []


def _is_python_command(cmd: str) -> bool:
    tok = (cmd or "").strip().split()
    if not tok:
        return False
    exe = Path(tok[0]).name
    return bool(_PYTHON_EXE.match(exe))


class PermissionAllowlist:
    def __init__(self, allowed: list[str] | None = None):
        self.allowed = list(allowed or [])

    def allows(self, tool: str) -> bool:
        if tool in self.allowed:
            return True
        if tool == "Bash" and any(
            item == "Bash" or str(item).startswith("Bash:") for item in self.allowed
        ):
            return True
        return False

    def allows_command(self, tool: str, command: str) -> bool:
        if tool != "Bash":
            return self.allows(tool)
        specs = [
            item
            for item in self.allowed
            if item == "Bash" or str(item).startswith("Bash:")
        ]
        if not specs:
            return False
        if "Bash" in specs:
            return True
        if any(item == "Bash:python" for item in specs):
            return _is_python_command(command)
        return False


class _ToolProxy:
    def __init__(
        self,
        adapter: "ClaudeAdapter",
        root: Path,
        allow: PermissionAllowlist,
        trace: list[dict],
    ):
        self._adapter = adapter
        self._root = root
        self._allow = allow
        self._trace = trace

    def _check(self, tool: str) -> None:
        if not self._allow.allows(tool):
            self._trace.append({"event": "tool-refused", "tool": tool})
            raise PermissionDenied(tool)
        self._trace.append({"event": "tool-ok", "tool": tool})

    def Read(self, rel: str) -> str:
        self._check("Read")
        return (self._root / rel).read_text(encoding="utf-8")

    def Grep(self, pattern: str, rel: str) -> str:
        self._check("Grep")
        text = (self._root / rel).read_text(encoding="utf-8")
        return "\n".join(ln for ln in text.splitlines() if pattern in ln)

    def Glob(self, rel: str) -> list[str]:
        self._check("Glob")
        return [rel]

    def Write(self, rel: str, body: str) -> None:
        self._check("Write")
        path = self._root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def Edit(self, rel: str, body: str) -> None:
        self._check("Edit")
        (self._root / rel).write_text(body, encoding="utf-8")

    def Bash(self, cmd: str) -> str:
        self._check("Bash")
        if not self._allow.allows_command("Bash", cmd):
            self._trace.append({"event": "tool-refused", "tool": "Bash"})
            raise PermissionDenied("Bash")
        env = self._adapter.child_env()
        p = subprocess.run(
            cmd,
            shell=True,
            cwd=str(self._root),
            capture_output=True,
            text=True,
            env=env,
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "").strip() or f"bash rc={p.returncode}")
        return p.stdout

    def PowerShell(self, cmd: str) -> str:
        self._check("PowerShell")
        env = self._adapter.child_env()
        exe = shutil.which("pwsh") or shutil.which("powershell")
        if exe:
            p = subprocess.run(
                [exe, "-NoProfile", "-Command", cmd],
                cwd=str(self._root),
                capture_output=True,
                text=True,
                env=env,
            )
            if p.returncode != 0:
                raise RuntimeError((p.stderr or p.stdout or "").strip())
            return p.stdout
        return _powershell_subset(cmd)


def _powershell_subset(cmd: str) -> str:
    text = (cmd or "").strip()
    low = text.lower()
    if low.startswith("write-output"):
        rest = text[len("Write-Output") :].strip()
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in {"'", '"'}:
            rest = rest[1:-1]
        return rest + "\n"
    if low in {"", "1"}:
        return "1\n"
    raise FileNotFoundError("pwsh")


class ClaudeAdapter:
    def __init__(self) -> None:
        self.timeout_s = 8.0

    def child_env(self) -> dict[str, str]:
        keep = (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "HOME",
            "USERPROFILE",
            "LANG",
            "LC_ALL",
            "TERM",
            "PATHEXT",
            "SYSTEMDRIVE",
            "COMSPEC",
        )
        env = {k: v for k, v in os.environ.items() if k in keep}
        return env

    def descriptor(self) -> dict[str, Any]:
        return {
            "vendor": "anthropic",
            "adapter": "claude-synchronous-typed",
            "tools": list(VOCAB),
            "timeout_policy": "declared-only",
            "catalog_default_timeout_seconds_not_applied": CATALOG_DEFAULT_TIMEOUT_SECONDS,
        }

    def invoke(
        self,
        unit: dict[str, Any],
        fn: Callable,
        sandbox_root: Path | str | None = None,
        sentinel: str | None = None,
    ) -> dict[str, Any]:
        return self.dispatch(unit, fn, sandbox_root=sandbox_root, sentinel=sentinel)

    def dispatch(
        self,
        unit: dict[str, Any],
        fn: Callable,
        sandbox_root: Path | str | None = None,
        sentinel: str | None = None,
    ) -> dict[str, Any]:
        root = Path(sandbox_root or ".")
        root.mkdir(parents=True, exist_ok=True)
        allowed = bound_tools(list(unit.get("tool_permissions") or []))
        allow = PermissionAllowlist(allowed)
        trace: list[dict] = []
        tools = _ToolProxy(self, root, allow, trace)
        base = {
            "dispatch_trace": trace,
            "bound_tools": list(allowed),
            "unit_id": unit.get("id"),
        }
        try:
            timeout = resolve_timeout_seconds(unit)
        except TimeoutUndeclared as exc:
            row = {
                **base,
                "state": "DENIED",
                "applied_timeout_seconds": None,
                "timeout_source": "refused-undeclared",
                "result": {
                    "outcome": "timeout-not-declared",
                    "error": str(exc),
                    "sentinel": sentinel,
                    "catalog_default_not_applied": CATALOG_DEFAULT_TIMEOUT_SECONDS,
                },
            }
            return row

        def _run() -> Any:
            return fn(tools)

        outcome = "completed"
        error = None
        state = "SUCCESS"
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_run)
                fut.result(timeout=timeout)
        except PermissionDenied as exc:
            outcome = "permission-denied"
            error = str(exc)
            state = "DENIED"
        except FuturesTimeout:
            outcome = "timeout"
            error = f"exceeded declared timeout_seconds={timeout}"
            state = "TIMEOUT"
        except AdapterTimeout as exc:
            outcome = "timeout"
            error = str(exc)
            state = "TIMEOUT"
        return {
            **base,
            "state": state,
            "applied_timeout_seconds": timeout,
            "timeout_source": "unit.timeout_seconds",
            "result": {
                "outcome": outcome,
                "error": error,
                "sentinel": sentinel,
            },
        }
