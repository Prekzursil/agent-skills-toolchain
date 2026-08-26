#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness import modules as _modules
    from harness.adapters import normalize_event, render_output
    from harness.ledger import _FileLock, default_state_root
    from harness.models import HookEvent, HookResult
    from harness.modules import build_default_modules
    from harness.redaction import redact_text
    from harness.storage import atomic_write_json, read_json
    from harness.workspace_index import WorkspaceIndex, WorkspaceIndexFailure
else:
    from . import modules as _modules
    from .adapters import normalize_event, render_output
    from .ledger import _FileLock, default_state_root
    from .models import HookEvent, HookResult
    from .modules import build_default_modules
    from .redaction import redact_text
    from .storage import atomic_write_json, read_json
    from .workspace_index import WorkspaceIndex, WorkspaceIndexFailure


_PRIORITY = {"allow": 0, "inject": 1, "continue": 2, "block": 3}

PRIORITY_SAFETY = 100
PRIORITY_GOAL = 80
PRIORITY_VERIFY = 60
PRIORITY_LOOP = 50
PRIORITY_ADVISORY = 20

_DUCK_FLOOR = 30
_INJECT_DEFAULT_PRIORITY = PRIORITY_ADVISORY
_INJECT_TOTAL_CAP = 6000

INJECT_PRIORITY: dict[str, int] = {
    "secret_literal": PRIORITY_SAFETY,
    "irreversible_operation": PRIORITY_SAFETY,
    "credential_read": PRIORITY_SAFETY,
    "sensitive_artifact": PRIORITY_SAFETY,
    "injection_quarantine": PRIORITY_SAFETY,
    "config_drift": PRIORITY_SAFETY,
    "config_baseline_unreadable": PRIORITY_SAFETY,
    "goal_reinjection": PRIORITY_GOAL,
    "subagent_handoff": PRIORITY_GOAL,
    "ipass_readback": PRIORITY_GOAL,
    "postcompact_reanchor": PRIORITY_GOAL,
    "owner_ops_authorization": PRIORITY_GOAL,
    "unverified_completion_claim": PRIORITY_VERIFY,
    "receipt_gate": PRIORITY_VERIFY,
    "zero_diff": PRIORITY_VERIFY,
    "repro_fingerprint": PRIORITY_VERIFY,
    "compchem_claim": PRIORITY_VERIFY,
    "bc_offset": PRIORITY_VERIFY,
    "repeated_no_progress": PRIORITY_LOOP,
    "tool_memo": PRIORITY_LOOP,
    "stigmergic_prior": PRIORITY_LOOP,
    "design_tool_reminder": PRIORITY_ADVISORY,
    "code_first_drift": PRIORITY_ADVISORY,
    "lexical_recall": PRIORITY_ADVISORY,
    "budget_pacing": PRIORITY_ADVISORY,
    "metered_mcp": PRIORITY_ADVISORY,
    "instructions_audit": PRIORITY_ADVISORY,
}

CONTRACT_INJECTION_MIXER = {
    "metric": "injected_char_volume_p95_per_event",
    "owner": "prekzursil",
    "deadline": "2026-09-30",
    "fire_rate": "mixer trims >0 chars on <20% of multi-inject events and NEVER drops a SAFETY inject",
}
CONTRACT_GUARD_BREAKER = {
    "metric": "module_error_streak + failed_modules_spike",
    "owner": "prekzursil",
    "deadline": "2026-09-30",
    "fire_rate": "<1 quarantine/module/week and <1 spike alarm/day under healthy operation",
}

_STERILE_RE = re.compile(
    r"(?i)(?:\bgit\b[^\r\n;&|]*\b(?:commit|push)\b"
    r"|\bgh\b[^\r\n;&|]*\brelease\b"
    r"|(?<![\w-])deploy(?![\w-]))"
)

_STARTUP_ALLOWANCE_SEC = 0.6
_MIN_BUDGET_SEC = 0.25
_DEFAULT_HOST_DEADLINE_SEC = 5.0
_BREAKER_LOCK_TIMEOUT_SEC = 0.25
_OUTPUT_MARGIN_SEC = 0.35
_WORKSPACE_CANCEL_CLEANUP_ALLOWANCE_SEC = 4.0
_ADVISORY_FAILURE_LABEL = "advisory_dispatch"
_ADVISORY_DEADLINE_LABEL = "advisory_deadline"
_WORKSPACE_CANCEL_FALSE_LABEL = "workspace_cancel_false"
_WORKSPACE_CANCEL_EXCEPTION_LABEL = "workspace_cancel_exception"
_CLI_EXCEPTION_LABEL = "_cli:exception"
_TRANSPORT_INVALID_UTF8 = "_transport:invalid_utf8"
_WORKSPACE_RESERVING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "apply_patch"})


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_int(name: str, default: int, floor: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw.strip() else int(default)
    except (TypeError, ValueError):
        value = int(default)
    return max(floor, value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _safe_json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _host_deadline_sec(event_name: str) -> float:
    try:
        if __package__ in {None, ""}:
            from harness.registration import _TIMEOUTS
        else:
            from .registration import _TIMEOUTS

        return float(_TIMEOUTS[str(event_name)])
    except Exception:
        return _DEFAULT_HOST_DEADLINE_SEC


def _dispatch_budget_sec(event_name: str) -> float:
    raw = os.environ.get("HARNESS_DISPATCH_BUDGET_MS", "").strip()
    if raw:
        try:
            return max(0.0, float(raw) / 1000.0)
        except (TypeError, ValueError):
            pass
    return max(_MIN_BUDGET_SEC, _host_deadline_sec(event_name) - _OUTPUT_MARGIN_SEC)


def _mode_env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip().lower()
    return value if value in {"off", "shadow", "enforce"} else default


def _inject_priority(reason_code: str) -> int:
    return INJECT_PRIORITY.get(str(reason_code or ""), _INJECT_DEFAULT_PRIORITY)


def _remaining_budget_seconds(deadline_monotonic: float | None) -> float:
    if deadline_monotonic is None:
        return float("inf")
    return max(0.0, deadline_monotonic - time.monotonic())


def _cleanup_deadline_monotonic(deadline_monotonic: float | None) -> float | None:
    if deadline_monotonic is None:
        return time.monotonic() + _WORKSPACE_CANCEL_CLEANUP_ALLOWANCE_SEC
    return min(
        deadline_monotonic,
        time.monotonic() + _WORKSPACE_CANCEL_CLEANUP_ALLOWANCE_SEC,
    )


def _pending_command(event: Any) -> str:
    tool = getattr(event, "tool", None)
    candidate = getattr(tool, "input", None)
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict):
        if isinstance(candidate.get("command"), str):
            return candidate["command"]
        if isinstance(candidate.get("cmd"), str):
            return candidate["cmd"]
    return ""


def _sterile_cockpit(event: Any) -> bool:
    if getattr(event, "event", "") != "PreToolUse":
        return False
    command = _pending_command(event)
    return bool(command) and _STERILE_RE.search(command) is not None


def _apply_total_cap(sequence: list[tuple[int, str, str]], total_cap: int) -> list[str]:
    out: list[str] = []
    used = 0
    for _priority, _reason, text in sequence:
        if used >= total_cap:
            break
        room = total_cap - used
        if len(text) <= room:
            out.append(text)
            used += len(text)
        else:
            trimmed = text[:room].rstrip()
            if trimmed:
                out.append(trimmed)
            break
    return out


def mix_injections(
    items: list[tuple[int, str, str]],
    *,
    has_safety: bool,
    sterile: bool,
    total_cap: int = _INJECT_TOTAL_CAP,
) -> list[str]:
    ordered = sorted(enumerate(items), key=lambda pair: (-pair[1][0], pair[0]))
    sequence = [item for _index, item in ordered]
    if sterile:
        sequence = [item for item in sequence if item[0] >= PRIORITY_SAFETY]
    elif has_safety:
        sequence = [item for item in sequence if item[0] >= _DUCK_FLOOR]
    return _apply_total_cap(sequence, total_cap)


def _shadow_tier(name: str, fallback: str) -> str:
    return str(getattr(_modules, name, fallback) or fallback)


def _emit_shadow(
    gate: str, tier: str, event: Any, reason_code: str, detail: str = ""
) -> None:
    log = getattr(_modules, "shadow_log", None)
    if not callable(log):
        return
    try:
        raw = HookResult.success(
            reason_code=reason_code,
            additional_context=[detail] if detail else [],
        )
        log(gate, tier, event, raw)
    except Exception:
        pass


def _fail_closed_pretooluse_transport(
    event: Any, transport_error: str | None
) -> HookResult | None:
    if getattr(event, "event", "") != "PreToolUse":
        return None
    marker = str(transport_error or "")
    if not marker:
        return None
    module_cls = getattr(_modules, "WorkspaceIntegrityModule", None)
    if module_cls is not None:
        factory = getattr(module_cls, "failure_result", None)
        if callable(factory):
            try:
                result = factory(event, "transport")
                if isinstance(result, HookResult):
                    return result
            except Exception:
                pass
    return HookResult(
        status=f"FAILED:hook-{event.event.lower()}",
        action="block",
        reason_code="workspace_integrity_unavailable",
        additional_context=["Workspace integrity unavailable during transport."],
        continuation=None,
    )


def _normalize_breaker_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    if not isinstance(value.get("modules"), dict):
        value["modules"] = {}
    if not isinstance(value.get("alerts"), list):
        value["alerts"] = []
    return value


def _write_terminal_record(
    state_root: Path,
    result: HookResult,
    *,
    provider: str,
    event_name: str,
    elapsed_ms: float,
    failed_modules: list[str],
) -> None:
    try:
        state_root.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "terminal": result.status,
            "provider": str(provider),
            "event": str(event_name),
            "action": result.action,
            "reason_code": result.reason_code,
            "elapsed_ms": round(elapsed_ms, 3),
            "failed_modules": [
                redact_text(name, max_chars=80) for name in failed_modules
            ],
        }
        with (state_root / "terminal.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
            )
    except Exception:
        pass


class HarnessDispatcher:
    def __init__(
        self,
        *,
        modules: list[Any] | None = None,
        state_root: Path | str | None = None,
    ):
        self.state_root = Path(state_root or default_state_root())
        initial_modules = list(
            modules if modules is not None else build_default_modules(self.state_root)
        )
        self.modules = list(initial_modules)
        self.workspace_module, self.advisory_modules = self._split_modules(
            initial_modules
        )

    @staticmethod
    def _split_modules(modules: list[Any]) -> tuple[Any | None, list[Any]]:
        if modules and HarnessDispatcher._is_workspace_integrity_runtime(modules[0]):
            return modules[0], list(modules[1:])
        return None, list(modules)

    def dispatch(
        self,
        raw: dict[str, Any],
        *,
        provider: str,
        event_name: str,
        transport_error: str | None = None,
    ) -> HookResult:
        started = time.perf_counter()
        event = normalize_event(raw, provider=provider, event_name=event_name)
        fail_closed = _fail_closed_pretooluse_transport(event, transport_error)
        if fail_closed is not None:
            self._record_terminal(
                fail_closed,
                provider=provider,
                event_name=event_name,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                failed_modules=[str(transport_error)],
            )
            return fail_closed

        action = "allow"
        reason_code = "ok"
        collected: list[tuple[int, str, str]] = []
        seen: set[str] = set()
        continuation: str | None = None
        had_error = bool(transport_error)
        failed_modules: list[str] = [transport_error] if transport_error else []
        breaker_events: list[tuple[str, str]] = []
        breaker_mode = _mode_env("HARNESS_BREAKER_MODE", "shadow")
        breaker = self._load_breaker()
        now = time.time()
        dispatch_deadline = time.monotonic() + _dispatch_budget_sec(event_name)
        workspace_module_name: str | None = None
        workspace_reserved = False

        def ingest(result: HookResult) -> None:
            nonlocal action, reason_code, continuation
            priority = _inject_priority(result.reason_code)
            for context in result.additional_context:
                clean = redact_text(str(context), max_chars=4000).strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    collected.append((priority, result.reason_code, clean))
            if _PRIORITY[result.action] > _PRIORITY[action]:
                action = result.action
                reason_code = result.reason_code
                continuation = result.continuation
            elif result.action == action and result.reason_code != "ok":
                reason_code = result.reason_code

        def note_breaker(state_obj: dict[str, Any], op: str, module_name: str) -> None:
            breaker_events.append((op, module_name))
            if op == "success":
                self._breaker_on_success(state_obj, module_name)
            else:
                self._breaker_on_error(state_obj, module_name)

        if self.workspace_module is not None and self._module_applies(
            self.workspace_module, event
        ):
            module = self.workspace_module
            module_name, name_error = self._module_name(module)
            workspace_module_name = module_name
            is_closed = self._is_closed_module(module, event)
            if name_error is not None:
                had_error = True
                failed_modules.append(module_name)
                note_breaker(breaker, "error", module_name)
            elif breaker_mode == "enforce" and self._is_quarantined(
                breaker, module_name, now
            ):
                had_error = True
                failed_modules.append(module_name)
                note_breaker(breaker, "error", module_name)
                if is_closed:
                    ingest(self._closed_failure(module, event, "quarantine"))
            elif _remaining_budget_seconds(dispatch_deadline) <= 0:
                had_error = True
                failed_modules.append(module_name)
                note_breaker(breaker, "error", module_name)
                if is_closed:
                    ingest(self._closed_failure(module, event, "deadline"))
            else:
                self._set_module_deadline(module, dispatch_deadline)
                try:
                    result = module.run(event)
                    if not isinstance(result, HookResult):
                        raise TypeError("module returned a non-HookResult")
                    if _remaining_budget_seconds(dispatch_deadline) <= 0:
                        had_error = True
                        failed_modules.append(module_name)
                        note_breaker(breaker, "error", module_name)
                        if is_closed:
                            ingest(self._closed_failure(module, event, "deadline"))
                    else:
                        ingest(result)
                        workspace_reserved = self._workspace_reservation_created(
                            event, result
                        )
                        if result.status.startswith("FAILED:"):
                            had_error = True
                            failed_modules.append(module_name)
                            note_breaker(breaker, "error", module_name)
                        else:
                            note_breaker(breaker, "success", module_name)
                except Exception:
                    had_error = True
                    failed_modules.append(module_name)
                    note_breaker(breaker, "error", module_name)
                    if is_closed:
                        ingest(self._closed_failure(module, event, "exception"))
                finally:
                    self._set_module_deadline(module, None)

        if action != "block" and self.advisory_modules:
            advisory_state = self._run_advisory_modules(
                event,
                list(self.advisory_modules),
                self._normalize_breaker(_safe_json_copy(breaker)),
                breaker_mode,
                now,
                dispatch_deadline,
            )
            advisory_action = advisory_state["action"]
            advisory_reason = advisory_state["reason_code"]
            advisory_continuation = advisory_state["continuation"]
            for priority, item_reason, text in advisory_state["collected"]:
                if text and text not in seen:
                    seen.add(text)
                    collected.append((priority, item_reason, text))
            if _PRIORITY[advisory_action] > _PRIORITY[action]:
                action = advisory_action
                reason_code = advisory_reason
                continuation = advisory_continuation
            elif advisory_action == action and advisory_reason != "ok":
                reason_code = advisory_reason
            had_error = bool(advisory_state["had_error"] or had_error)
            failed_modules.extend(advisory_state["failed_modules"])
            breaker = self._normalize_breaker(advisory_state["breaker"])
            breaker_events.extend(advisory_state["breaker_events"])
            if (
                advisory_action == "block"
                and self.workspace_module is not None
                and getattr(event, "event", "") == "PreToolUse"
                and workspace_reserved
            ):
                canceled, cancel_failure = self._cancel_workspace_reservation(
                    self.workspace_module,
                    event,
                    dispatch_deadline,
                )
                if not canceled and cancel_failure:
                    had_error = True
                    failed_modules.append(cancel_failure)
                    if workspace_module_name:
                        note_breaker(breaker, "error", workspace_module_name)

        failed = list(failed_modules)
        self._finalize_breaker(
            breaker,
            event,
            failed,
            now,
            breaker_mode,
            breaker_events=breaker_events,
            deadline_monotonic=dispatch_deadline,
        )

        contexts = self._mix_contexts(event, list(collected), action)
        terminal = (
            f"FAILED:hook-{event_name.lower()}"
            if had_error
            else f"SUCCESS:hook-{event_name.lower()}"
        )
        if action not in _PRIORITY:
            had_error = True
            action = "allow"
            reason_code = "internal_error"
            terminal = f"FAILED:hook-{event_name.lower()}"
        elif had_error and action == "allow":
            reason_code = "internal_error"

        typed_action = cast(Literal["allow", "block", "inject", "continue"], action)
        result = HookResult(
            status=terminal,
            action=typed_action,
            reason_code=reason_code,
            additional_context=contexts,
            continuation=continuation,
        )
        self._record_terminal(
            result,
            provider=provider,
            event_name=event_name,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            failed_modules=failed,
        )
        return result

    def _run_advisory_modules(
        self,
        event: HookEvent,
        modules: list[Any],
        seed_breaker: dict[str, Any],
        breaker_mode: str,
        now: float,
        deadline_monotonic: float | None,
    ) -> dict[str, Any]:
        action_local = "allow"
        reason_local = "ok"
        continuation_local: str | None = None
        seen_local: set[str] = set()
        collected_local: list[tuple[int, str, str]] = []
        had_error_local = False
        failed_local: list[str] = []
        breaker_local = self._normalize_breaker(_safe_json_copy(seed_breaker))
        breaker_events_local: list[tuple[str, str]] = []

        def ingest_local(result: HookResult) -> None:
            nonlocal action_local, reason_local, continuation_local
            priority = _inject_priority(result.reason_code)
            for context in result.additional_context:
                clean = redact_text(str(context), max_chars=4000).strip()
                if clean and clean not in seen_local:
                    seen_local.add(clean)
                    collected_local.append((priority, result.reason_code, clean))
            if _PRIORITY[result.action] > _PRIORITY[action_local]:
                action_local = result.action
                reason_local = result.reason_code
                continuation_local = result.continuation
            elif result.action == action_local and result.reason_code != "ok":
                reason_local = result.reason_code

        for module in modules:
            if _remaining_budget_seconds(deadline_monotonic) <= 0:
                had_error_local = True
                failed_local.append(_ADVISORY_DEADLINE_LABEL)
                break
            module_name, name_error = self._module_name(module)
            if name_error is not None:
                had_error_local = True
                failed_local.append(module_name)
                breaker_events_local.append(("error", module_name))
                self._breaker_on_error(breaker_local, module_name)
                continue
            is_closed = self._is_closed_module(module, event)
            if breaker_mode == "enforce" and self._is_quarantined(
                breaker_local, module_name, now
            ):
                had_error_local = True
                failed_local.append(module_name)
                breaker_events_local.append(("error", module_name))
                self._breaker_on_error(breaker_local, module_name)
                if is_closed:
                    ingest_local(self._closed_failure(module, event, "quarantine"))
                    break
                continue
            try:
                self._set_module_deadline(module, deadline_monotonic)
                result = module.run(event)
                if not isinstance(result, HookResult):
                    raise TypeError("module returned a non-HookResult")
                if _remaining_budget_seconds(deadline_monotonic) <= 0:
                    had_error_local = True
                    failed_local.append(_ADVISORY_DEADLINE_LABEL)
                    breaker_events_local.append(("error", module_name))
                    self._breaker_on_error(breaker_local, module_name)
                    if is_closed:
                        ingest_local(self._closed_failure(module, event, "deadline"))
                    break
                ingest_local(result)
                if result.status.startswith("FAILED:"):
                    had_error_local = True
                    failed_local.append(module_name)
                    breaker_events_local.append(("error", module_name))
                    self._breaker_on_error(breaker_local, module_name)
                else:
                    breaker_events_local.append(("success", module_name))
                    self._breaker_on_success(breaker_local, module_name)
                if result.action == "block":
                    break
            except Exception:
                had_error_local = True
                failed_local.append(module_name)
                breaker_events_local.append(("error", module_name))
                self._breaker_on_error(breaker_local, module_name)
                if is_closed:
                    ingest_local(self._closed_failure(module, event, "exception"))
                    break
                continue
            finally:
                self._set_module_deadline(module, None)

        return {
            "action": action_local,
            "reason_code": reason_local,
            "continuation": continuation_local,
            "collected": collected_local,
            "had_error": had_error_local,
            "failed_modules": failed_local,
            "breaker": breaker_local,
            "breaker_events": breaker_events_local,
        }

    @staticmethod
    def _workspace_reservation_created(event: HookEvent, result: HookResult) -> bool:
        return bool(
            getattr(event, "event", "") == "PreToolUse"
            and getattr(getattr(event, "tool", None), "name", "")
            in _WORKSPACE_RESERVING_TOOLS
            and result.action == "allow"
            and not result.status.startswith("FAILED:")
        )

    def _cancel_workspace_reservation(
        self,
        module: Any,
        event: HookEvent,
        deadline_monotonic: float | None,
    ) -> tuple[bool, str | None]:
        cancel = getattr(module, "cancel_pre", None)
        if not callable(cancel):
            return False, _WORKSPACE_CANCEL_FALSE_LABEL
        self._set_module_deadline(module, deadline_monotonic)
        try:
            canceled = bool(cancel(event))
        except Exception:
            self._invalidate_workspace_reservation(
                module, event, deadline_monotonic, reason="cancel_pre raised"
            )
            return False, _WORKSPACE_CANCEL_EXCEPTION_LABEL
        finally:
            self._set_module_deadline(module, None)
        if canceled:
            return True, None
        self._invalidate_workspace_reservation(
            module, event, deadline_monotonic, reason="cancel_pre returned false"
        )
        return False, _WORKSPACE_CANCEL_FALSE_LABEL

    def _invalidate_workspace_reservation(
        self,
        module: Any,
        event: HookEvent,
        deadline_monotonic: float | None,
        *,
        reason: str,
    ) -> None:
        git_executable = getattr(module, "git_executable", None)
        if git_executable is None:
            return
        cleanup_deadline = _cleanup_deadline_monotonic(deadline_monotonic)
        while True:
            try:
                index = WorkspaceIndex(
                    state_root=Path(getattr(module, "state_root", self.state_root)),
                    repo_path=event.cwd,
                    git_executable=git_executable,
                    deadline_monotonic=cleanup_deadline,
                )
                index.invalidate(reason=f"PreToolUse cancel failure: {reason}")
                return
            except WorkspaceIndexFailure:
                remaining = _remaining_budget_seconds(cleanup_deadline)
                if remaining <= 0:
                    return
            except Exception:
                remaining = _remaining_budget_seconds(cleanup_deadline)
                if remaining <= 0:
                    return
            sleep_for = min(0.05, _remaining_budget_seconds(cleanup_deadline))
            if sleep_for <= 0:
                return
            time.sleep(sleep_for)

    def _mix_contexts(
        self, event: Any, collected: list[tuple[int, str, str]], action: str
    ) -> list[str]:
        raw_contexts = [text for _priority, _reason, text in collected]
        mixer_mode = _mode_env("HARNESS_INJECT_MIXER", "shadow")
        if mixer_mode == "off" or not collected:
            return raw_contexts
        has_safety = action == "block" or any(
            priority >= PRIORITY_SAFETY for priority, _reason, _text in collected
        )
        sterile = _sterile_cockpit(event)
        mixed = mix_injections(
            collected,
            has_safety=has_safety,
            sterile=sterile,
            total_cap=_env_int("HARNESS_INJECT_CAP", _INJECT_TOTAL_CAP, 256),
        )
        if mixer_mode == "enforce":
            return mixed
        if mixed != raw_contexts:
            _emit_shadow(
                "injection_mixer",
                _shadow_tier("TIER_ADVISORY", "advisory"),
                event,
                "injection_mixer_delta",
                f"raw={len(raw_contexts)} mixed={len(mixed)} "
                f"safety={int(has_safety)} sterile={int(sterile)}",
            )
        return raw_contexts

    def _breaker_path(self) -> Path:
        return self.state_root / "breaker.json"

    @staticmethod
    def _normalize_breaker(state: Any) -> dict[str, Any]:
        return _normalize_breaker_payload(state)

    def _load_breaker(self) -> dict[str, Any]:
        try:
            return self._normalize_breaker(read_json(self._breaker_path(), {}))
        except Exception:
            return {"modules": {}, "alerts": []}

    def _breaker_lock_path(self) -> Path:
        return self.state_root / "breaker.lock"

    @staticmethod
    def _module_name(module: Any) -> tuple[str, Exception | None]:
        try:
            return str(getattr(module, "name", module.__class__.__name__)), None
        except Exception as exc:
            return module.__class__.__name__, exc

    @staticmethod
    def _set_module_deadline(module: Any, deadline: float | None) -> None:
        setter = getattr(module, "set_deadline", None)
        if callable(setter):
            try:
                setter(deadline)
            except Exception:
                pass

    @staticmethod
    def _is_workspace_integrity_runtime(module: Any) -> bool:
        workspace_cls = getattr(_modules, "WorkspaceIntegrityModule", None)
        return workspace_cls is not None and isinstance(module, workspace_cls)

    @staticmethod
    def _module_applies(module: Any, event: Any) -> bool:
        applies = getattr(module, "applies", None)
        if callable(applies):
            try:
                return bool(applies(event))
            except Exception:
                return True
        return True

    def _is_closed_module(self, module: Any, event: Any) -> bool:
        if str(getattr(module, "failure_policy", "") or "").lower() != "closed":
            return False
        applies = getattr(module, "applies", None)
        if callable(applies):
            try:
                return bool(applies(event))
            except Exception:
                return True
        return True

    def _closed_failure(self, module: Any, event: Any, phase: str) -> HookResult:
        factory = getattr(module, "failure_result", None)
        if callable(factory):
            try:
                result = factory(event, phase)
                if isinstance(result, HookResult):
                    return result
            except Exception:
                pass
        return HookResult.success(
            action="block",
            reason_code="workspace_integrity_unavailable",
            additional_context=[f"Workspace integrity unavailable during {phase}."],
        )

    def _module_slot(self, state: dict[str, Any], name: str) -> dict[str, Any]:
        slot = state["modules"].get(name)
        if not isinstance(slot, dict):
            slot = {"streak": 0, "quarantined_until": 0.0}
            state["modules"][name] = slot
        return slot

    def _is_quarantined(self, state: dict[str, Any], name: str, now: float) -> bool:
        slot = state["modules"].get(name)
        if not isinstance(slot, dict):
            return False
        try:
            return float(slot.get("quarantined_until") or 0.0) > now
        except (TypeError, ValueError):
            return False

    def _breaker_on_error(self, state: dict[str, Any], name: str) -> None:
        slot = self._module_slot(state, name)
        slot["streak"] = _as_int(slot.get("streak")) + 1
        slot["last_error_ts"] = _iso_now()

    def _breaker_on_success(self, state: dict[str, Any], name: str) -> None:
        slot = state["modules"].get(name)
        if isinstance(slot, dict) and _as_int(slot.get("streak")):
            slot["streak"] = 0

    def _append_alert(
        self, state: dict[str, Any], module: str, kind: str, detail: Any
    ) -> None:
        state["alerts"].append(
            {
                "ts": _iso_now(),
                "module": redact_text(str(module), max_chars=80),
                "kind": kind,
                "detail": detail,
            }
        )
        state["alerts"] = state["alerts"][-20:]

    def _finalize_breaker(
        self,
        state: dict[str, Any],
        event: Any,
        failed_modules: list[str],
        now: float,
        mode: str,
        *,
        breaker_events: list[tuple[str, str]] | None = None,
        deadline_monotonic: float | None = None,
    ) -> None:
        if mode == "off":
            return
        timeout = min(
            _BREAKER_LOCK_TIMEOUT_SEC,
            _remaining_budget_seconds(deadline_monotonic),
        )
        if timeout <= 0:
            return
        try:
            with _FileLock(self._breaker_lock_path(), timeout=timeout):
                merged = self._load_breaker()
                for op, module_name in breaker_events or []:
                    if op == "success":
                        self._breaker_on_success(merged, module_name)
                    else:
                        self._breaker_on_error(merged, module_name)
                self._write_breaker_state(merged, event, failed_modules, now)
        except Exception:
            pass

    def _write_breaker_state(
        self,
        state: dict[str, Any],
        event: Any,
        failed_modules: list[str],
        now: float,
    ) -> None:
        streak_n = _env_int("HARNESS_BREAKER_STREAK", 5, 1)
        cooldown = _env_int("HARNESS_BREAKER_COOLDOWN_SEC", 3600, 1)
        spike_n = _env_int("HARNESS_FAILED_SPIKE", 3, 2)
        tier = _shadow_tier("TIER_DETERMINISTIC", "deterministic")
        for name, slot in list(state["modules"].items()):
            if not isinstance(slot, dict):
                continue
            if _as_int(slot.get("streak")) >= streak_n and not self._is_quarantined(
                state, name, now
            ):
                slot["quarantined_until"] = now + cooldown
                slot["streak"] = 0
                slot["last_alert_ts"] = _iso_now()
                self._append_alert(state, name, "breaker_quarantine", cooldown)
                _emit_shadow(
                    "guard_breaker",
                    tier,
                    event,
                    "breaker_quarantine",
                    f"module={redact_text(str(name), max_chars=80)} cooldown={cooldown}s",
                )
        if len(failed_modules) >= spike_n:
            self._append_alert(state, "*", "failed_modules_spike", len(failed_modules))
            _emit_shadow(
                "guard_breaker",
                tier,
                event,
                "failed_modules_spike",
                f"failed={len(failed_modules)}",
            )
        state["heartbeat"] = _iso_now()
        atomic_write_json(self._breaker_path(), state)

    def _record_terminal(
        self,
        result: HookResult,
        *,
        provider: str,
        event_name: str,
        elapsed_ms: float,
        failed_modules: list[str],
    ) -> None:
        _write_terminal_record(
            self.state_root,
            result,
            provider=provider,
            event_name=event_name,
            elapsed_ms=elapsed_ms,
            failed_modules=failed_modules,
        )


def _parse_args(argv: list[str] | None = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        description="Shared Claude/Codex lifecycle dispatcher"
    )
    parser.add_argument(
        "--provider", required=True, choices=("claude", "codex", "grok")
    )
    parser.add_argument("--event", required=True)
    parser.add_argument("--state-root")
    return parser.parse_args(argv)


def _parse_cli_payload(event_name: str) -> tuple[dict[str, Any], str | None]:
    transport_error: str | None = None
    raw_bytes = sys.stdin.buffer.read()
    if not raw_bytes.strip():
        if event_name == "PreToolUse":
            transport_error = "_transport:empty_stdin"
        return {}, transport_error
    try:
        raw_text = raw_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return {}, _TRANSPORT_INVALID_UTF8
    try:
        raw = json.loads(raw_text)
    except Exception:
        return {}, "_transport:malformed_json"
    if not isinstance(raw, dict):
        return {}, "_transport:non_object_payload"
    return raw, None


def _cli_failure_result(event_name: str) -> HookResult:
    status = f"FAILED:hook-{event_name.lower()}"
    if event_name == "PreToolUse":
        return HookResult(
            status=status,
            action="block",
            reason_code="workspace_integrity_unavailable",
            additional_context=["Workspace integrity unavailable during cli."],
            continuation=None,
        )
    return HookResult(
        status=status,
        action="allow",
        reason_code="internal_error",
        additional_context=[],
        continuation=None,
    )


def _fallback_native_output(event_name: str) -> dict[str, Any]:
    if event_name == "PreToolUse":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "workspace integrity unavailable",
            }
        }
    return {}


def _emit_native_output(
    result: HookResult,
    *,
    provider: str,
    event_name: str,
) -> None:
    try:
        native = render_output(result, provider=provider, event_name=event_name)
    except Exception:
        native = _fallback_native_output(event_name)
    payload = native if isinstance(native, dict) else {}
    sys.stdout.buffer.write(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    args = _parse_args(argv)
    raw, transport_error = _parse_cli_payload(args.event)
    state_root = Path(args.state_root or default_state_root())

    try:
        dispatcher = HarnessDispatcher(state_root=args.state_root)
        result = dispatcher.dispatch(
            raw,
            provider=args.provider,
            event_name=args.event,
            transport_error=transport_error,
        )
        _emit_native_output(result, provider=args.provider, event_name=args.event)
    except Exception:
        result = _cli_failure_result(args.event)
        _write_terminal_record(
            state_root,
            result,
            provider=args.provider,
            event_name=args.event,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            failed_modules=[_CLI_EXCEPTION_LABEL],
        )
        _emit_native_output(result, provider=args.provider, event_name=args.event)
        return 0
    return 0


if __name__ == "__main__":
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
