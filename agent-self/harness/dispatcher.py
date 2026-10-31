#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness import modules as _modules
    from harness.adapters import normalize_event, render_output
    from harness.ledger import default_state_root
    from harness.models import HookResult
    from harness.modules import build_default_modules
    from harness.redaction import redact_text
    from harness.storage import atomic_write_json, read_json
else:
    from . import modules as _modules
    from .adapters import normalize_event, render_output
    from .ledger import default_state_root
    from .models import HookResult
    from .modules import build_default_modules
    from .redaction import redact_text
    from .storage import atomic_write_json, read_json


# Provider-neutral arbitration of the winning ACTION (allow < inject < continue < block).
_PRIORITY = {"allow": 0, "inject": 1, "continue": 2, "block": 3}


# --------------------------------------------------------------------------- #
# SI-4 · INJECTION-MIXER PRIORITY TAGS (G3)
#
# The dispatcher tags every collected context with the priority of the winning
# module's HookResult.reason_code family, then the mixer (mix_injections) sorts,
# sidechain-ducks, sterile-cockpit-mutes, and LUFS-normalizes the total volume.
# Modules keep STABLE reason_codes so this map holds — do not rename them here or
# in modules.py without updating both sides.
# --------------------------------------------------------------------------- #
PRIORITY_SAFETY = 100
PRIORITY_GOAL = 80
PRIORITY_VERIFY = 60
PRIORITY_LOOP = 50
PRIORITY_ADVISORY = 20

# sidechain-duck removes injects strictly below this floor when any SAFETY inject
# (or a block) is present. ADVISORY (20) < 30 => ducked; LOOP/VERIFY/GOAL survive.
_DUCK_FLOOR = 30
# Unmapped / "ok" reason_codes (e.g. the design-tool reminder emits reason_code
# "ok") are treated as advisory chatter. No context-bearing "ok" result co-occurs
# with a SAFETY inject in the current module set, so this never silently drops a
# safety/verify/goal message; it only classes genuinely-advisory nudges as advisory.
_INJECT_DEFAULT_PRIORITY = PRIORITY_ADVISORY
# LUFS-normalize: soft cap on total injected characters per event (env override).
_INJECT_TOTAL_CAP = 6000

INJECT_PRIORITY: dict[str, int] = {
    # SAFETY = 100 (existing ENFORCE safety branches + future config/injection gates)
    "secret_literal": PRIORITY_SAFETY,
    "irreversible_operation": PRIORITY_SAFETY,
    "credential_read": PRIORITY_SAFETY,
    "sensitive_artifact": PRIORITY_SAFETY,
    "injection_quarantine": PRIORITY_SAFETY,
    "config_drift": PRIORITY_SAFETY,
    # Same gate, different verdict: the baseline itself is unparseable, so drift
    # detection is DISABLED. Ranks with config_drift — an operator must not read a
    # silent gate as a clean one.
    "config_baseline_unreadable": PRIORITY_SAFETY,
    # GOAL = 80
    "goal_reinjection": PRIORITY_GOAL,
    # The SessionStart / first-prompt basic-memory vault digest (RecallModule)
    # ranks with goal re-injection: it is the session's read-side anchor.
    "bm_vault_digest": PRIORITY_GOAL,
    "subagent_handoff": PRIORITY_GOAL,
    "ipass_readback": PRIORITY_GOAL,
    "postcompact_reanchor": PRIORITY_GOAL,
    # owner explicitly authorized these work classes — do not over-refuse
    "owner_ops_authorization": PRIORITY_GOAL,
    # VERIFY = 60
    "unverified_completion_claim": PRIORITY_VERIFY,
    "receipt_gate": PRIORITY_VERIFY,
    "zero_diff": PRIORITY_VERIFY,
    "repro_fingerprint": PRIORITY_VERIFY,
    "compchem_claim": PRIORITY_VERIFY,
    "bc_offset": PRIORITY_VERIFY,
    # LOOP = 50
    "repeated_no_progress": PRIORITY_LOOP,
    "tool_memo": PRIORITY_LOOP,
    "stigmergic_prior": PRIORITY_LOOP,
    # ADVISORY = 20
    "design_tool_reminder": PRIORITY_ADVISORY,
    "code_first_drift": PRIORITY_ADVISORY,
    "lexical_recall": PRIORITY_ADVISORY,
    "budget_pacing": PRIORITY_ADVISORY,
    "metered_mcp": PRIORITY_ADVISORY,
    "instructions_audit": PRIORITY_ADVISORY,
}

# CONTRACT constants (SI-2 anti-zombie): the F1 scorer + native Cron read these to
# retire a gate that never earns its keep. They attach the falsifiable hypothesis
# next to each gate's branch; they are inert data here.
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

# Pending-tool detection for the sterile-cockpit mute: a git commit/push, a
# gh release, or a deploy on PreToolUse. Bounded to a single shell token run so a
# ';'-chained unrelated command does not spuriously arm the mute.
_STERILE_RE = re.compile(
    r"(?i)(?:\bgit\b[^\r\n;&|]*\b(?:commit|push)\b"
    r"|\bgh\b[^\r\n;&|]*\brelease\b"
    r"|(?<![\w-])deploy(?![\w-]))"
)


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
    """Tolerant int() for externally-written state (breaker.json is on disk and
    can be corrupted out-of-band). A bad slot must degrade to the default, never
    raise — the breaker bookkeeping runs inside the module except-handler, where
    a raise escapes dispatch() entirely and discards an already-computed block."""
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


# The host kills the hook process at its registered per-event timeout
# (registration._TIMEOUTS — hot events 25s, SessionStart/Stop 60s as of 2026-10-13). module.run() is synchronous,
# so ONE module that outlives that deadline takes the whole dispatch with it: no
# terminal record, no liveness stamp, every later module silently skipped. The
# fan-out therefore runs under a wall-clock budget; on expiry the in-flight module
# is abandoned (daemon thread, dies with the process) and the failure is recorded
# instead of vanishing.
#
# Budget = host deadline - _STARTUP_ALLOWANCE_SEC, because the deadline covers the
# WHOLE process, not just the fan-out: interpreter start + imports +
# build_default_modules measured ~0.3s on the live box, and the terminal write and
# native stdout have to land inside the remainder. Measured on 260k live terminal
# records, this truncates the tail of ~1.5% of UserPromptSubmit events (the 2s
# cap's slowest) — events of which 2.3% already exceeded 2s and were SIGKILLed
# with no record at all, so the trade is strictly in favour of recording.
_STARTUP_ALLOWANCE_SEC = 0.6
_MIN_BUDGET_SEC = 0.25
_DEFAULT_HOST_DEADLINE_SEC = 5.0


def _host_deadline_sec(event_name: str) -> float:
    """The host's registered timeout for this event. Resolved lazily and
    tolerantly so this file still works standalone and in a vendored tree that
    ships no registration module (flat 5s there)."""
    try:
        if __package__ in {None, ""}:
            from harness.registration import _TIMEOUTS
        else:
            from .registration import _TIMEOUTS

        return float(_TIMEOUTS[str(event_name)])
    except Exception:
        return _DEFAULT_HOST_DEADLINE_SEC


def _dispatch_budget_sec(event_name: str) -> float:
    """Wall-clock budget for the module fan-out. 0 disables the watchdog."""
    raw = os.environ.get("HARNESS_DISPATCH_BUDGET_MS", "").strip()
    if raw:
        try:
            return max(0.0, float(raw) / 1000.0)
        except (TypeError, ValueError):
            pass
    deadline = _host_deadline_sec(event_name)
    return max(_MIN_BUDGET_SEC, deadline - _STARTUP_ALLOWANCE_SEC)


def _mode_env(name: str, default: str) -> str:
    """Resolve an off/shadow/enforce mode from the environment.

    Every gem in this file ships SHADOW by default (observe + log only, never
    alters output or nags) per the program's shadow-mode law; enforce is opt-in.
    """
    value = os.environ.get(name, "").strip().lower()
    return value if value in {"off", "shadow", "enforce"} else default


def _inject_priority(reason_code: str) -> int:
    return INJECT_PRIORITY.get(str(reason_code or ""), _INJECT_DEFAULT_PRIORITY)


def _pending_command(event: Any) -> str:
    tool = getattr(event, "tool", None)
    candidate = getattr(tool, "input", None)
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict) and isinstance(candidate.get("command"), str):
        return candidate["command"]
    return ""


def _sterile_cockpit(event: Any) -> bool:
    """True on a PreToolUse whose pending command is a commit/push/release/deploy."""
    if getattr(event, "event", "") != "PreToolUse":
        return False
    command = _pending_command(event)
    return bool(command) and _STERILE_RE.search(command) is not None


def _apply_total_cap(sequence: list[tuple[int, str, str]], total_cap: int) -> list[str]:
    """Keep whole contexts from the highest priority down; when the budget runs
    out, truncate the current (lowest so far) context to fit and drop the rest —
    LUFS-normalize by truncating lowest-priority first."""
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
    """G3 injection mixer (SI-4) — a pure, deterministic context-assembly filter.

    ``items`` are (priority, reason_code, text) tuples in collection order. The
    mixer: sorts descending by priority (stable within a tier); sterile-cockpit-
    mutes to SAFETY-only when a commit/push/release/deploy is pending; else
    sidechain-ducks advisory chatter (< _DUCK_FLOOR) when a SAFETY inject/block is
    present; then LUFS-normalizes to a total-char cap, truncating lowest-priority
    first. Returns the final ordered list of context strings.
    """
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
    """Route F6/G3 telemetry through modules.shadow_log (SI-2). Resolved lazily so
    it composes once the modules lane lands the primitive, and is an inert no-op
    until then (keeps the dispatcher fail-open and standalone). shadow_log writes
    ONLY the separate bounded shadow sink — never terminal.jsonl or the ledger."""
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


class HarnessDispatcher:
    def __init__(
        self, *, modules: list[Any] | None = None, state_root: Path | str | None = None
    ):
        self.state_root = Path(state_root or default_state_root())
        self.modules = list(
            modules if modules is not None else build_default_modules(self.state_root)
        )

    def dispatch(
        self,
        raw: dict[str, Any],
        *,
        provider: str,
        event_name: str,
        transport_error: str | None = None,
    ) -> HookResult:
        """Run the module chain over one normalized event.

        ``transport_error`` names a failure that happened BEFORE normalization —
        the caller could not turn the host's stdin into an event payload, so the
        modules are about to run over an empty ``raw``. Staying fail-open there is
        deliberate (D010), but the durable record must not read SUCCESS/ok: the
        hook did no real work, and a promotion or smoke oracle that grades the
        terminal record would otherwise score that silent loss as green.
        """
        started = time.perf_counter()
        event = normalize_event(raw, provider=provider, event_name=event_name)
        action = "allow"
        reason_code = "ok"
        # (priority, reason_code, text) per surviving context — feeds the G3 mixer.
        collected: list[tuple[int, str, str]] = []
        seen: set[str] = set()
        continuation: str | None = None
        had_error = bool(transport_error)
        failed_modules: list[str] = [transport_error] if transport_error else []
        in_flight = ""

        # F6 · per-module error-streak circuit-breaker (SHADOW by default).
        breaker_mode = _mode_env("HARNESS_BREAKER_MODE", "shadow")
        breaker = self._load_breaker()
        now = time.time()

        def _fan_out() -> None:
            nonlocal action, reason_code, continuation, had_error, in_flight
            for module in self.modules:
                module_name = str(getattr(module, "name", module.__class__.__name__))
                in_flight = module_name
                if breaker_mode == "enforce" and self._is_quarantined(
                    breaker, module_name, now
                ):
                    # Cooldown quarantine: a reliably-crashing module already
                    # provides no protection under fail-open, so skip it (and stop
                    # paying its cost) until the window elapses; it auto-resumes
                    # afterwards. The hook is DEGRADED while a detector is skipped,
                    # so mark it — terminal health must never report a clean
                    # measurement for a detector that never ran.
                    had_error = True
                    failed_modules.append(module_name)
                    continue
                try:
                    result = module.run(event)
                    if not isinstance(result, HookResult):
                        raise TypeError("module returned a non-HookResult")
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
                    if result.status.startswith("FAILED:"):
                        had_error = True
                        failed_modules.append(module_name)
                        self._breaker_on_error(breaker, module_name)
                    else:
                        self._breaker_on_success(breaker, module_name)
                    if result.action == "block":
                        # Security decisions are terminal. Later modules can write
                        # goals, ledgers, or checkpoints and must never ingest the
                        # blocked payload.
                        break
                except Exception:
                    # A raised exception in one branch must not suppress the others
                    # (each module owns its own try/except boundary).
                    had_error = True
                    failed_modules.append(module_name)
                    self._breaker_on_error(breaker, module_name)

        budget = _dispatch_budget_sec(event_name)
        if budget <= 0:
            _fan_out()
        else:
            worker = threading.Thread(
                target=_fan_out, name="harness-fanout", daemon=True
            )
            worker.start()
            worker.join(budget)
            if worker.is_alive():
                # Out of budget: the host is about to kill this process. Abandon
                # the in-flight module (daemon thread — it dies with the process)
                # and keep going, so the terminal record and whatever the finished
                # modules produced still reach the host.
                had_error = True
                failed_modules.append(in_flight or "dispatch")

        # Snapshot: an abandoned worker may still be appending to these lists.
        failed = list(failed_modules)

        # F6 · persist streaks, trip quarantines, raise the failed_modules spike
        # alarm, and stamp the liveness heartbeat. Fail-open (never raises).
        self._finalize_breaker(breaker, event, failed, now, breaker_mode)

        # G3 · assemble the injected contexts through the mixer (SHADOW by default).
        contexts = self._mix_contexts(event, list(collected), action)

        terminal = (
            f"FAILED:hook-{event_name.lower()}"
            if had_error
            else f"SUCCESS:hook-{event_name.lower()}"
        )
        if had_error and action == "allow":
            reason_code = "internal_error"
        result = HookResult(
            status=terminal,
            action=action,
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

    # -- G3 injection mixer -------------------------------------------------- #

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
        # SHADOW: observe-only. Never drop or reorder context until the mixer is
        # explicitly promoted to enforce; just log what it WOULD have done.
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

    # -- F6 guard-liveness circuit-breaker ----------------------------------- #

    def _breaker_path(self) -> Path:
        return self.state_root / "breaker.json"

    @staticmethod
    def _normalize_breaker(state: Any) -> dict[str, Any]:
        if not isinstance(state, dict):
            state = {}
        if not isinstance(state.get("modules"), dict):
            state["modules"] = {}
        if not isinstance(state.get("alerts"), list):
            state["alerts"] = []
        return state

    def _load_breaker(self) -> dict[str, Any]:
        try:
            return self._normalize_breaker(read_json(self._breaker_path(), {}))
        except Exception:
            return {"modules": {}, "alerts": []}

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
    ) -> None:
        if mode == "off":
            return
        try:
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
                self._append_alert(
                    state, "*", "failed_modules_spike", len(failed_modules)
                )
                _emit_shadow(
                    "guard_breaker",
                    tier,
                    event,
                    "failed_modules_spike",
                    f"failed={len(failed_modules)}",
                )
            state["heartbeat"] = _iso_now()
            atomic_write_json(self._breaker_path(), state)
        except Exception:
            # Fail-open: a breaker bookkeeping error must never affect the hook.
            pass

    # -- terminal record ----------------------------------------------------- #

    def _record_terminal(
        self,
        result: HookResult,
        *,
        provider: str,
        event_name: str,
        elapsed_ms: float,
        failed_modules: list[str],
    ) -> None:
        try:
            self.state_root.mkdir(parents=True, exist_ok=True)
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
            with (self.state_root / "terminal.jsonl").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(
                    json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
                )
        except Exception:
            pass


def _parse_args(argv: list[str] | None = None) -> Any:
    import argparse  # lazy (import-diet): only the CLI entrypoint needs argparse.

    parser = argparse.ArgumentParser(
        description="Shared Claude/Codex/Grok lifecycle dispatcher"
    )
    # Keep in lockstep with adapters.SUPPORTED_PROVIDERS — a value accepted here
    # but missing there is a silent no-op hook (the ValueError is swallowed by
    # main()'s fail-open except), which is strictly worse than a wrong label.
    parser.add_argument(
        "--provider", required=True, choices=("claude", "codex", "grok")
    )
    parser.add_argument("--event", required=True)
    parser.add_argument("--state-root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    # D010 · a wire payload the harness cannot parse still fails OPEN (rc 0, no
    # stdout, modules run over {}), but it is named so the terminal record reads
    # FAILED:hook-<event>/internal_error instead of a false SUCCESS. Empty stdin
    # is NOT an error - several hosts send nothing for some events.
    transport_error: str | None = None
    try:
        raw_text = sys.stdin.read()
        raw = json.loads(raw_text or "{}")
        if not isinstance(raw, dict):
            raw = {}
            transport_error = "_transport:non_object_payload"
    except Exception:
        raw = {}
        transport_error = "_transport:malformed_json"

    try:
        dispatcher = HarnessDispatcher(state_root=args.state_root)
        result = dispatcher.dispatch(
            raw,
            provider=args.provider,
            event_name=args.event,
            transport_error=transport_error,
        )
        native = render_output(result, provider=args.provider, event_name=args.event)
        if native or args.event in {"Stop", "SubagentStop"}:
            sys.stdout.write(
                json.dumps(native, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    except Exception:
        # Command hooks are fail-open by contract. A malformed input or internal
        # failure must never crash or block the host lifecycle.
        return 0
    return 0


if __name__ == "__main__":
    _code = main()
    # A module abandoned at the dispatch budget keeps running on a daemon thread,
    # and normal interpreter finalization waits on it (~0.4s measured on the live
    # box) — long enough to push the process past the host's kill deadline (exit
    # 124) AFTER the native output was already written. Nothing else is pending at
    # this point (no atexit handlers, no background writers), so exit immediately.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
