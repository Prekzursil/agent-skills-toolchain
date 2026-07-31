#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness.adapters import normalize_event, render_output
    from harness.ledger import default_state_root
    from harness.models import HookResult
    from harness.modules import build_default_modules
    from harness.redaction import redact_text
else:
    from .adapters import normalize_event, render_output
    from .ledger import default_state_root
    from .models import HookResult
    from .modules import build_default_modules
    from .redaction import redact_text


_PRIORITY = {"allow": 0, "inject": 1, "continue": 2, "block": 3}


class HarnessDispatcher:
    def __init__(self, *, modules: list[Any] | None = None, state_root: Path | str | None = None):
        self.state_root = Path(state_root or default_state_root())
        self.modules = list(modules if modules is not None else build_default_modules(self.state_root))

    def dispatch(
        self,
        raw: dict[str, Any],
        *,
        provider: str,
        event_name: str,
        transport_error: str | None = None,
    ) -> HookResult:
        # D010 parity with agent-self/harness/dispatcher.py: a pre-normalization
        # wire failure still fails open, but must not be recorded as SUCCESS/ok.
        started = time.perf_counter()
        event = normalize_event(raw, provider=provider, event_name=event_name)

        # Re-entrant Stop short-circuit (defense-in-depth). When the host
        # re-invokes a Stop/SubagentStop hook because a prior hook kept the agent
        # going (stop_hook_active is true), running the modules again risks a
        # re-block or re-inject that just forces another continue and loops up to
        # the host's stop-hook cap. Stay silent (allow) BEFORE any module runs so
        # the agent can actually stop. Fail-open: any error falls through to the
        # normal fan-out below.
        try:
            reentrant_stop = (
                event_name in {"Stop", "SubagentStop"}
                and isinstance(raw, dict)
                and str(raw.get("stop_hook_active", "")).lower() in {"true", "1"}
            )
        except Exception:
            reentrant_stop = False
        if reentrant_stop:
            silent = HookResult(
                status=f"SUCCESS:hook-{event_name.lower()}",
                action="allow",
                reason_code="reentrant_stop",
                additional_context=[],
            )
            self._record_terminal(
                silent,
                provider=provider,
                event_name=event_name,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                failed_modules=[],
            )
            return silent

        action = "allow"
        reason_code = "ok"
        contexts: list[str] = []
        continuation: str | None = None
        had_error = bool(transport_error)
        failed_modules: list[str] = [transport_error] if transport_error else []

        for module in self.modules:
            module_name = str(getattr(module, "name", module.__class__.__name__))
            try:
                result = module.run(event)
                if not isinstance(result, HookResult):
                    raise TypeError("module returned a non-HookResult")
                for context in result.additional_context:
                    clean = redact_text(str(context), max_chars=4000).strip()
                    if clean and clean not in contexts:
                        contexts.append(clean)
                if _PRIORITY[result.action] > _PRIORITY[action]:
                    action = result.action
                    reason_code = result.reason_code
                    continuation = result.continuation
                elif result.action == action and result.reason_code != "ok":
                    reason_code = result.reason_code
                if result.status.startswith("FAILED:"):
                    had_error = True
                    failed_modules.append(module_name)
                if result.action == "block":
                    # Security decisions are terminal. Later modules can write
                    # goals, ledgers, or checkpoints and must never ingest the
                    # blocked payload.
                    break
            except Exception:
                had_error = True
                failed_modules.append(module_name)

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
            failed_modules=failed_modules,
        )
        return result

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
                "failed_modules": [redact_text(name, max_chars=80) for name in failed_modules],
            }
            with (self.state_root / "terminal.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        except Exception:
            pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared Claude/Codex lifecycle dispatcher")
    parser.add_argument("--provider", required=True, choices=("claude", "codex"))
    parser.add_argument("--event", required=True)
    parser.add_argument("--state-root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
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
            sys.stdout.write(json.dumps(native, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        # Command hooks are fail-open by contract. A malformed input or internal
        # failure must never crash or block the host lifecycle.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
