"""In-process Anthropic and OpenAI work-unit adapters.

These are the vendor runtimes this confirmation can actually execute on this
worktree: live `codex`/`claude` CLIs are optional extras. Behaviour is taken
from the B07/IMP-0420/IMP-0421/IMP-0422 contracts (prompt-by-file, blocking
foreground, severed-stream AND-gate, permission enforcement, win-arg-limit).

Observation is via returned DispatchResult fields. Adapter self-report is
deliberately allowed to be wrong so the confirmer cannot treat it as evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WIN_ARG_LIMIT = 32767
MEASURED_INLINE_PROMPT = 34472
DEFAULT_TIMEOUT = 3600


class DetachedForbidden(RuntimeError):
    """Raised at the API boundary; a detached result cannot fan-in."""


class QuotaStorm(RuntimeError):
    """Vendor 429/529 — must not be converted into REFUTED."""


@dataclass
class DispatchResult:
    vendor: str
    classification: str
    exit_code: int
    prompt_transport: str
    prompt_chars: int
    timeout_applied: int
    timeout_declared: int
    background_attempted: bool
    write_attempted: bool
    write_refused: bool
    owner_approval_blocked: bool
    owner_approval_required: bool
    output_present: bool
    output_parseable: bool
    output_text: str | None
    user_config_applied: bool
    ignore_user_config: bool
    argv_preview: list[str]
    self_reported_leaks: list[str] = field(default_factory=list)
    self_reported_honored: list[str] = field(default_factory=list)
    quota: str | None = None


def _write_output(path: Path | None, payload: dict[str, Any]) -> tuple[bool, bool, str | None]:
    if path is None:
        return False, False, None
    text = json.dumps(payload, indent=2, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    try:
        json.loads(path.read_text(encoding="utf-8"))
        parseable = True
    except json.JSONDecodeError:
        parseable = False
    return True, parseable, text


class AnthropicAdapter:
    """IMP-0420: enforce tool_permissions and declared timeout; no win-arg-limit."""

    vendor = "anthropic"

    def dispatch(
        self,
        unit: dict[str, Any],
        *,
        prompt: str,
        prompt_by_file: bool = False,
        background: bool = False,
        ignore_user_config: bool = True,
        output_path: Path | None = None,
        attempt_write: bool = False,
        approved: bool = False,
        user_config: dict[str, Any] | None = None,
        omit_output: bool = False,
        inject_quota: str | None = None,
        allow_detached: bool = False,
    ) -> DispatchResult:
        if inject_quota:
            raise QuotaStorm(inject_quota)
        # CNF0158-FIX:refuse-detached
        if background and not allow_detached:
            raise DetachedForbidden("anthropic adapter refuses detached dispatch")

        declared = int(unit.get("timeout_seconds") or DEFAULT_TIMEOUT)
        timeout_applied = declared  # honors timeout_seconds
        perms = list(unit.get("tool_permissions") or [])
        owner_req = bool(unit.get("owner_approval_required"))
        transport = "file" if prompt_by_file else "inline"

        write_refused = False
        if attempt_write and "Write" not in perms and not any(
            str(p).startswith("Write") for p in perms
        ):
            write_refused = True

        # owner_approval_required is documented, not enforced — real leak.
        owner_blocked = False

        user_applied = bool(user_config) and not ignore_user_config

        if omit_output:
            # CNF0158-FIX:severed-and-gate
            return DispatchResult(
                vendor=self.vendor,
                classification="SEVERED-STREAM",
                exit_code=0,
                prompt_transport=transport,
                prompt_chars=len(prompt),
                timeout_applied=timeout_applied,
                timeout_declared=declared,
                background_attempted=background,
                write_attempted=attempt_write,
                write_refused=write_refused,
                owner_approval_blocked=owner_blocked,
                owner_approval_required=owner_req,
                output_present=False,
                output_parseable=False,
                output_text=None,
                user_config_applied=user_applied,
                ignore_user_config=ignore_user_config,
                argv_preview=["claude", "--print", "--prompt-file" if prompt_by_file else "--prompt"],
                self_reported_leaks=["owner_approval_required"],
                self_reported_honored=[
                    "timeout_seconds",
                    "tool_permissions",
                    "blocking_foreground",
                    "output_schema",
                ],
            )

        present, parseable, text = _write_output(
            output_path,
            {
                "vendor": self.vendor,
                "ok": not write_refused,
                "timeout_applied": timeout_applied,
                "approved_ignored": owner_req and not approved,
            },
        )
        classification = "PERMISSION-DENIED" if write_refused else "SUCCESS"
        return DispatchResult(
            vendor=self.vendor,
            classification=classification,
            exit_code=0 if classification == "SUCCESS" else 2,
            prompt_transport=transport,
            prompt_chars=len(prompt),
            timeout_applied=timeout_applied,
            timeout_declared=declared,
            background_attempted=background,
            write_attempted=attempt_write,
            write_refused=write_refused,
            owner_approval_blocked=owner_blocked,
            owner_approval_required=owner_req,
            output_present=present,
            output_parseable=parseable,
            output_text=text,
            user_config_applied=user_applied,
            ignore_user_config=ignore_user_config,
            argv_preview=["claude", "--print", transport],
            self_reported_leaks=["owner_approval_required"],
            self_reported_honored=[
                "timeout_seconds",
                "tool_permissions",
                "blocking_foreground",
                "output_schema",
                "prompt_body_inline",
            ],
        )


class OpenAIAdapter:
    """IMP-0421: prompt-by-file, blocking foreground, ignore-user-config, AND-gate.

    Codex permission model does not map 1:1 onto catalog tool_permissions, so a
    Write attempt can succeed even when Write is absent from the unit — the
    adapter still self-reports tool_permissions as honored (the lie).
    """

    vendor = "openai"

    def dispatch(
        self,
        unit: dict[str, Any],
        *,
        prompt: str,
        prompt_by_file: bool = True,
        background: bool = False,
        ignore_user_config: bool = True,
        output_path: Path | None = None,
        attempt_write: bool = False,
        approved: bool = False,
        user_config: dict[str, Any] | None = None,
        omit_output: bool = False,
        inject_quota: str | None = None,
        allow_detached: bool = False,
        honor_timeout: bool = True,
        honor_permissions: bool = False,
    ) -> DispatchResult:
        if inject_quota:
            raise QuotaStorm(inject_quota)
        # CNF0158-FIX:refuse-detached
        if background and not allow_detached:
            raise DetachedForbidden("codex adapter refuses detached dispatch")

        if (not prompt_by_file) and len(prompt) > WIN_ARG_LIMIT:
            return DispatchResult(
                vendor=self.vendor,
                classification="WIN-ARG-LIMIT",
                exit_code=206,
                prompt_transport="inline",
                prompt_chars=len(prompt),
                timeout_applied=DEFAULT_TIMEOUT,
                timeout_declared=int(unit.get("timeout_seconds") or DEFAULT_TIMEOUT),
                background_attempted=background,
                write_attempted=False,
                write_refused=False,
                owner_approval_blocked=False,
                owner_approval_required=bool(unit.get("owner_approval_required")),
                output_present=False,
                output_parseable=False,
                output_text=None,
                user_config_applied=False,
                ignore_user_config=ignore_user_config,
                argv_preview=["codex", "--prompt", "<inline>"],
                self_reported_leaks=["prompt_body_inline"],
                self_reported_honored=["blocking_foreground", "timeout_seconds"],
            )

        declared = int(unit.get("timeout_seconds") or DEFAULT_TIMEOUT)
        timeout_applied = declared if honor_timeout else DEFAULT_TIMEOUT
        owner_req = bool(unit.get("owner_approval_required"))
        transport = "file" if prompt_by_file else "inline"
        user_applied = bool(user_config) and not ignore_user_config

        write_refused = False
        if attempt_write and honor_permissions:
            perms = list(unit.get("tool_permissions") or [])
            if "Write" not in perms and not any(str(p).startswith("Write") for p in perms):
                write_refused = True
        # else: permission leak — Write proceeds

        if omit_output:
            # CNF0158-FIX:severed-and-gate
            return DispatchResult(
                vendor=self.vendor,
                classification="SEVERED-STREAM",
                exit_code=0,
                prompt_transport=transport,
                prompt_chars=len(prompt),
                timeout_applied=timeout_applied,
                timeout_declared=declared,
                background_attempted=background,
                write_attempted=attempt_write,
                write_refused=write_refused,
                owner_approval_blocked=False,
                owner_approval_required=owner_req,
                output_present=False,
                output_parseable=False,
                output_text=None,
                user_config_applied=user_applied,
                ignore_user_config=ignore_user_config,
                argv_preview=["codex", "--ignore-user-config", "--prompt-file"],
                self_reported_leaks=[],
                self_reported_honored=[
                    "blocking_foreground",
                    "timeout_seconds",
                    "tool_permissions",
                    "output_schema",
                ],
            )

        present, parseable, text = _write_output(
            output_path,
            {
                "vendor": self.vendor,
                "ok": not write_refused,
                "timeout_applied": timeout_applied,
                "user_config_applied": user_applied,
            },
        )
        classification = "PERMISSION-DENIED" if write_refused else "SUCCESS"
        # Self-report lies about tool_permissions (claims honored).
        return DispatchResult(
            vendor=self.vendor,
            classification=classification,
            exit_code=0 if classification == "SUCCESS" else 2,
            prompt_transport=transport,
            prompt_chars=len(prompt),
            timeout_applied=timeout_applied,
            timeout_declared=declared,
            background_attempted=background,
            write_attempted=attempt_write,
            write_refused=write_refused,
            owner_approval_blocked=False,
            owner_approval_required=owner_req,
            output_present=present,
            output_parseable=parseable,
            output_text=text,
            user_config_applied=user_applied,
            ignore_user_config=ignore_user_config,
            argv_preview=["codex", "--ignore-user-config", "--prompt-file" if prompt_by_file else "--prompt"],
            self_reported_leaks=["prompt_body_inline"] if not prompt_by_file else [],
            self_reported_honored=[
                "blocking_foreground",
                "timeout_seconds",
                "tool_permissions",
                "output_schema",
            ],
        )


def adapters() -> dict[str, Any]:
    return {"anthropic": AnthropicAdapter(), "openai": OpenAIAdapter()}
