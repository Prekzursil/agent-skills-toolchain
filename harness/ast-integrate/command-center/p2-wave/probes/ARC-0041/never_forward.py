"""Never-forward proof: env canary + forbidden outbound fields.

Two leak signals (recursive walk vs json.dumps). Disagreement is BLOCKED.
Fail-open mutant must leak the canary so the detector is live.
"""
from __future__ import annotations

from typing import Any, Mapping

from corpus import leaky_vendor_payload
from sanitizer import (
    CANARY_ENV,
    CANARY_VALUE,
    KIND,
    canary_present_dump,
    canary_present_walk,
    seal_adapter_result,
)


def planted_env() -> dict[str, str]:
    return {
        CANARY_ENV: CANARY_VALUE,
        "ANTHROPIC_API_KEY": CANARY_VALUE,
        "PATH": "/usr/bin",
    }


def adapter_result_with_leak(payload: Any) -> dict[str, Any]:
    return {
        "unit_id": "ARC-0041",
        "vendor": "openai",
        "adapter": "codex",
        "state": "SUCCESS",
        "classification": None,
        "sentinel": "SUCCESS:ARC-0041",
        "invocation": {
            "prompt_file": "/tmp/arc0041.prompt.txt",
            "prompt_file_on_argv": True,
            "prompt_body_on_argv": False,
            "exit_code": 0,
            "argv": ["codex", "exec", CANARY_VALUE],
            "os_error": None,
        },
        "parsed": payload,
        "error": None,
        "leaks": [{"field": "tool_permissions", "reason": "unhonored"}],
        "env": planted_env(),
    }


def _forbidden_in_payload(sealed: Mapping[str, Any]) -> list[str]:
    parsed = sealed.get("parsed") or {}
    payload = parsed.get("payload")
    found: list[str] = []
    if isinstance(payload, dict):
        for key in (
            "tool_permissions",
            "hooks",
            "hook_configuration",
            "credential_store_path",
        ):
            if key in payload:
                found.append(key)
    return found


def run_never_forward() -> dict[str, Any]:
    env = planted_env()
    raw = adapter_result_with_leak(leaky_vendor_payload())
    sealed = seal_adapter_result(raw, env=env, fail_open=False)
    open_mutant = seal_adapter_result(raw, env=env, fail_open=True)

    walk_closed = canary_present_walk(sealed, CANARY_VALUE)
    dump_closed = canary_present_dump(sealed, CANARY_VALUE)
    walk_open = canary_present_walk(open_mutant, CANARY_VALUE)
    dump_open = canary_present_dump(open_mutant, CANARY_VALUE)
    signals_agree_closed = walk_closed == dump_closed
    signals_agree_open = walk_open == dump_open

    parsed = sealed.get("parsed") or {}
    forbidden = _forbidden_in_payload(sealed)
    outbound_keys = sorted(sealed.keys())
    argv_forwarded = "argv" in (sealed.get("invocation") or {})
    env_copied = "env" in sealed

    closed_clean = (
        (not walk_closed)
        and (not dump_closed)
        and signals_agree_closed
        and not forbidden
        and not argv_forwarded
        and not env_copied
        and parsed.get("kind") == KIND
        and parsed.get("instructions_forbidden") is True
        and parsed.get("fail_closed") is True
        and "tool-permission-grant" in (parsed.get("never_forward_stripped") or [])
        and "hook-configuration" in (parsed.get("never_forward_stripped") or [])
        and "credential-store-path" in (parsed.get("never_forward_stripped") or [])
    )
    open_leaks = walk_open and dump_open and signals_agree_open
    return {
        "probe": "never-forward",
        "unit_id": "ARC-0041",
        "canary_env": CANARY_ENV,
        "walk_closed_leaks": walk_closed,
        "dump_closed_leaks": dump_closed,
        "signals_agree_closed": signals_agree_closed,
        "walk_open_leaks": walk_open,
        "dump_open_leaks": dump_open,
        "signals_agree_open": signals_agree_open,
        "forbidden_payload_keys": forbidden,
        "outbound_keys": outbound_keys,
        "argv_forwarded": argv_forwarded,
        "env_copied": env_copied,
        "never_forward_stripped": list(parsed.get("never_forward_stripped") or []),
        "parsed_kind": parsed.get("kind"),
        "fail_open_mutant_leaks_canary": open_leaks,
        "fail_closed_clean": closed_clean,
        "pass": bool(closed_clean and open_leaks),
    }
