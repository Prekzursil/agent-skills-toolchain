"""Codex adapter: spawn injection with honest TIMEOUT / SEVERED classification."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

class DetachedInvocationError(ValueError):
    pass


CLASS_SEVERED_STREAM = "severed-stream"
STATE_SEVERED = "SEVERED"
STATE_SUCCESS = "SUCCESS"
STATE_TIMEOUT = "TIMEOUT"
STATE_FAILED = "FAILED"


@dataclass
class SpawnRecord:
    argv: list[str] = field(default_factory=list)
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


# Windows CreationFlags bit for DETACHED_PROCESS; any spawn carrying it is
# a backgrounding attempt and is refused at the API boundary.
DETACHED_PROCESS = 0x00000008


class CodexAdapter:
    def __init__(
        self,
        spawn: Callable[..., SpawnRecord] | None = None,
        codex_bin: Sequence[str] | None = None,
    ) -> None:
        self.spawn = spawn or self._spawn
        self.codex_bin = list(codex_bin or ["codex"])

    def _spawn(self, argv: list[str], timeout: float) -> SpawnRecord:
        """Blocking spawn: subprocess.run only — never Popen, never shell."""
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=float(timeout),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SpawnRecord(argv=list(argv), exit_code=124, timed_out=True)
        return SpawnRecord(
            argv=list(argv),
            exit_code=int(proc.returncode),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            timed_out=False,
        )

    def dispatch(
        self,
        unit: dict[str, Any],
        prompt: str = "",
        work_dir: Path | str | None = None,
        background: bool = False,
        extra_argv: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        extra_argv = list(extra_argv or [])
        creationflags = int(kwargs.get("creationflags") or 0)
        if (
            background
            or kwargs.get("detached")
            or "--background" in extra_argv
            or kwargs.get("DETACHED_PROCESS")
            or creationflags & DETACHED_PROCESS
        ):
            raise DetachedInvocationError(
                "detached/background invocation is refused "
                "(background=True, detached=True, --background, and "
                "DETACHED_PROCESS creationflags all raise before any spawn)"
            )
        timeout = float(unit.get("timeout_seconds") or unit.get("timeout") or 30)
        root = Path(work_dir) if work_dir is not None else Path(".")
        root.mkdir(parents=True, exist_ok=True)
        prompt_file = root / "prompt.txt"
        prompt_file.write_text(prompt or "", encoding="utf-8")
        out_file = root / "output-last-message.json"
        argv = [
            *self.codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--output-last-message",
            str(out_file),
            "--prompt-file",
            str(prompt_file),
            str(unit.get("id") or "unit"),
        ]
        rec = self.spawn(argv, timeout)
        invocation = {
            "argv": list(rec.argv),
            "exit_code": rec.exit_code,
            "timed_out": rec.timed_out,
            "stdout": rec.stdout,
            "stderr": rec.stderr,
            "prompt_body_on_argv": bool(prompt) and prompt in " ".join(rec.argv),
            "prompt_file_on_argv": "--prompt-file" in rec.argv,
            "ignore_user_config": "--ignore-user-config" in rec.argv,
        }
        if rec.timed_out:
            return {
                "state": STATE_TIMEOUT,
                "classification": "codex-exit-n",
                "error": "timeout",
                "parsed": None,
                "invocation": invocation,
            }
        if rec.exit_code != 0:
            return {
                "state": STATE_FAILED,
                "classification": "codex-exit-n",
                "error": f"exit-{rec.exit_code}",
                "parsed": None,
                "invocation": invocation,
            }
        if not out_file.is_file():
            return {
                "state": STATE_SEVERED,
                "classification": CLASS_SEVERED_STREAM,
                "error": "missing-output-last-message",
                "parsed": None,
                "invocation": invocation,
            }
        raw = out_file.read_text(encoding="utf-8")
        if not raw.strip():
            return {
                "state": STATE_SEVERED,
                "classification": CLASS_SEVERED_STREAM,
                "error": "empty-output-last-message",
                "parsed": None,
                "invocation": invocation,
            }
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "state": STATE_SEVERED,
                "classification": CLASS_SEVERED_STREAM,
                "error": "unparseable-output-last-message",
                "parsed": None,
                "invocation": invocation,
            }
        if not isinstance(parsed, dict):
            return {
                "state": STATE_SEVERED,
                "classification": CLASS_SEVERED_STREAM,
                "error": "non-object-output-last-message",
                "parsed": parsed,
                "invocation": invocation,
            }
        return {
            "state": STATE_SUCCESS,
            "classification": None,
            "error": None,
            "parsed": parsed,
            "invocation": invocation,
        }
