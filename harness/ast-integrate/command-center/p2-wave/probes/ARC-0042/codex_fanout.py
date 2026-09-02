"""WRAP of Codex fan-out profiles onto the live agentspec.argv rail.

tools/import-adapters/codex_fanout.py is absent on this worktree (IMP-0161
undelivered). This module does not introduce a local argv builder: argv is
produced by agentspec.argv.build_argv. Fire-and-forget / background profiles
stay KEEP-REFUSAL rather than being replaced by a wrap that would succeed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AGENTSPEC = REPO / "tools" / "agentspec"
if str(AGENTSPEC) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC))

from agentspec.argv import PromptOnArgv, build_argv  # noqa: E402

ADAPTER_ID = "codex-fanout-wrap/v1"
CLOSED_REASON_IDS = frozenset(
    {
        "dispatch.fire-and-forget",
        "dispatch.background-flagged",
        "dispatch.missing-timeout",
        "dispatch.prompt-on-argv",
        "dispatch.missing-prompt-file",
    }
)


class ImportRefused(Exception):
    def __init__(self, reason_id: str, message: str = "") -> None:
        super().__init__(message or reason_id)
        self.reason_id = reason_id


def _as_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def import_fanout_path(path: Path | str) -> dict[str, Any]:
    target = _as_path(path)
    profile = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ImportRefused("dispatch.malformed-profile", "profile is not an object")
    return import_fanout_profile(profile)


def import_fanout_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    if profile.get("fire_and_forget") is True:
        raise ImportRefused("dispatch.fire-and-forget")
    if profile.get("background") is True:
        raise ImportRefused("dispatch.background-flagged")
    timeout = profile.get("timeout_seconds")
    units_in = profile.get("units") or []
    if not isinstance(units_in, list) or not units_in:
        raise ImportRefused("dispatch.missing-units", "profile has no units")
    binary = str(profile.get("binary") or "codex")
    planned: list[dict[str, Any]] = []
    for src in units_in:
        if not isinstance(src, dict):
            raise ImportRefused("dispatch.malformed-unit")
        uid = str(src.get("id") or "")
        unit_timeout = src.get("timeout_seconds", timeout)
        if unit_timeout is None:
            raise ImportRefused("dispatch.missing-timeout")
        extra = src.get("extra_argv") or []
        if src.get("prompt") or any(
            str(tok) in {"--prompt", "--message"} or str(tok).startswith("--prompt=")
            for tok in extra
        ):
            raise ImportRefused("dispatch.prompt-on-argv")
        prompt_file = src.get("prompt_file")
        if not prompt_file:
            raise ImportRefused("dispatch.missing-prompt-file")
        prompt_file = str(prompt_file)
        body = _prompt_body(prompt_file, uid)
        flags = (
            "exec",
            "--ignore-user-config",
            "--timeout",
            str(int(unit_timeout)),
        )
        try:
            plan = build_argv(
                exe=binary,
                prompt=body,
                transport="file",
                flags=flags,
                prompt_flag="--prompt-file",
                prompt_path=prompt_file,
            )
        except PromptOnArgv as exc:
            raise ImportRefused("dispatch.prompt-on-argv") from exc
        argv = list(plan.argv)
        if any(tok in {"&", "--background", "--detach"} for tok in argv):
            raise ImportRefused("dispatch.background-flagged")
        planned.append(
            {
                "id": uid,
                "timeout_seconds": int(unit_timeout),
                "prompt_file": prompt_file,
                "argv": argv,
                "blocking": True,
                "prompt_transport": "file",
            }
        )
    return {
        "id": profile.get("id"),
        "kind": "Workflow",
        "nodes": [
            {"kind": "FanOut", "width": len(planned), "units": planned},
            {"kind": "Barrier", "await": [u["id"] for u in planned]},
        ],
    }


def _prompt_body(prompt_file: str, uid: str) -> str:
    path = Path(prompt_file)
    if not path.is_absolute():
        path = REPO / prompt_file
    if path.is_file():
        body = path.read_text(encoding="utf-8")
        if body.strip():
            return body
    return f"ARC-0042-wrap-prompt:{uid}:{prompt_file}"
