"""WRAP of the live Codex blocking prompt-by-file contract.

tools/work-unit-adapters/codex.py is absent on this worktree (IMP-0421/IMP-0422
undelivered). This adapter does not spawn a Codex binary. It builds argv through
the live agentspec.argv.build_argv rail so the prompt travels by FILE and
--background/--detach never appear.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AGENTSPEC = REPO / "tools" / "agentspec"
if str(AGENTSPEC) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC))

from agentspec.argv import build_argv  # noqa: E402

DETACHED = frozenset({"&", "--background", "--detach", "--detached"})


class CodexAdapter:
    def __init__(self, repo: Path | str | None = None, **_kwargs: Any) -> None:
        self.repo = Path(repo) if repo is not None else REPO

    def build_plan(self, unit: Mapping[str, Any]) -> dict[str, Any]:
        uid = str(unit.get("id") or "")
        timeout = int(unit.get("timeout_seconds") or 3600)
        rel, body = self._prompt(unit)
        last_msg = (
            f"command-center/p2-wave/probes/ARC-0042/fixtures/last-message/{uid}.json"
        )
        flags = (
            "exec",
            "--ignore-user-config",
            "--timeout",
            str(timeout),
            "--output-last-message",
            last_msg,
        )
        plan = build_argv(
            exe="codex",
            prompt=body,
            transport="file",
            flags=flags,
            prompt_flag="--prompt-file",
            prompt_path=rel,
        )
        argv = list(plan.argv)
        if any(tok in DETACHED for tok in argv):
            raise RuntimeError(f"{uid}: detached token on Codex argv")
        if "--prompt-file" not in argv or "--ignore-user-config" not in argv:
            raise RuntimeError(f"{uid}: missing prompt-file or ignore-user-config")
        if "--background" in argv:
            raise RuntimeError(f"{uid}: background on argv")
        return {
            "blocking": True,
            "detached_forbidden": True,
            "prompt_transport": "file",
            "prompt_file": rel,
            "argv": argv,
            "ignore_user_config": True,
            "timeout_seconds": timeout,
        }

    def _prompt(self, unit: Mapping[str, Any]) -> tuple[str, str]:
        uid = str(unit.get("id") or "")
        rel = f"command-center/p2-wave/probes/ARC-0042/fixtures/prompts/{uid}.md"
        path = self.repo / rel
        if path.is_file():
            body = path.read_text(encoding="utf-8")
            if not body.strip():
                raise RuntimeError(f"{uid}: empty prompt file {rel}")
            return rel, body
        body = str(unit.get("question_or_target") or uid).strip()
        if not body:
            body = uid
        return rel, body
