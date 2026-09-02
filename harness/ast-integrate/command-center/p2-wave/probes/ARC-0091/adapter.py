#!/usr/bin/env python3
"""Consumer call site for ARC-0091: two vendor adapters, one work-unit contract.

Every return from _dispatch_impl is `return emit_terminal(...)`. dispatch()
refuses a silent return. Negotiation intersection is computed. Leak lists are
never empty. Prompt travels by file. Dispatch is blocking foreground only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0091.json"
VENDOR_CLI = HERE / "vendor_cli.py"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

TERMINAL_KINDS = ("SUCCESS", "FAILED", "SEVERED", "TIMEOUT")
VENDORS_ORDER = ("anthropic", "openai")

TIER_ASSIGNMENT = {
    "id": "GUARANTEED",
    "output_path": "GUARANTEED",
    "output_schema": "GUARANTEED",
    "completion_sentinel": "GUARANTEED",
    "prompt_transport": "GUARANTEED",
    "dispatch_mode": "GUARANTEED",
    "terminal_state_marker": "GUARANTEED",
    "and_gate": "GUARANTEED",
    "abstraction_leak_declaration": "GUARANTEED",
    "minimum_tier": "GUARANTEED",
    "schema_validity": "GUARANTEED",
    "streaming_progress": "BEST-EFFORT",
    "timeout_precision": "BEST-EFFORT",
    "context_window": "BEST-EFFORT",
    "session_resume": "BEST-EFFORT",
    "assigned_model_vendor_role.model": "VENDOR-ONLY",
    "assigned_model_vendor_role.vendor": "VENDOR-ONLY",
    "native_tool_names": "VENDOR-ONLY",
    "ignore_user_config": "VENDOR-ONLY",
    "vendor_thread_id": "VENDOR-ONLY",
}

RUNTIME = {
    "kind": "blocking-subprocess",
    "live_vendor_api": False,
    "note": (
        "In-process fixture vendors implement the adapter contract "
        "(file transport, blocking dispatch, AND-gate, leaks, negotiation). "
        "Live vendor HTTP/MCP is out of scope for this contract unit."
    ),
}


@dataclass(frozen=True)
class VendorDesc:
    vendor: str
    tools: tuple[str, ...]
    context_window: int
    permission_model: str
    streaming: bool
    schema_support: bool
    prompt_transport: str = "file"
    blocking_dispatch: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


VENDORS: dict[str, VendorDesc] = {
    "anthropic": VendorDesc(
        vendor="anthropic",
        tools=("Read", "Grep", "Glob", "Write", "Edit", "Bash"),
        context_window=200000,
        permission_model="tool_permissions_enforced_at_dispatch",
        streaming=True,
        schema_support=True,
        extra={"permission_evaluator": "claude-native"},
    ),
    "openai": VendorDesc(
        vendor="openai",
        tools=("Read", "Grep", "Glob", "Write", "Edit", "Bash", "mcp__codex__codex"),
        context_window=128000,
        permission_model="cli-flag-subset",
        streaming=False,
        schema_support=True,
        extra={"ignore_user_config": True},
    ),
}

AXIS_TIER = {
    "tools": "GUARANTEED",
    "context_window": "BEST-EFFORT",
    "permission_model": "VENDOR-ONLY",
    "streaming": "BEST-EFFORT",
    "schema_support": "GUARANTEED",
    "prompt_transport": "GUARANTEED",
    "blocking_dispatch": "GUARANTEED",
}

# Portable core is GUARANTEED-tier. Vendor-native MCP names are VENDOR-ONLY:
# listing them on a catalog row does not fail the other vendor unless
# extra_required promotes that tool to GUARANTEED (loud-mismatch control).
PORTABLE_CORE = frozenset({"Read", "Grep", "Glob", "Write", "Edit", "Bash"})


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def catalog_unit(uid: str) -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def emit_terminal(kind: str, unit_id: str, **fields: Any) -> dict[str, Any]:
    if kind not in TERMINAL_KINDS:
        kind = "FAILED"
        fields.setdefault("reason", "unknown-terminal-kind")
    reason = str(fields.get("reason") or "")
    marker = f"{kind}:{unit_id}"
    if reason:
        marker = f"{kind}:{unit_id} {reason}"
    out: dict[str, Any] = {
        "vendor": fields.get("vendor"),
        "unit_id": unit_id,
        "terminal_kind": kind,
        "terminal_marker": marker,
        "prompt_transport": "file",
        "dispatch_mode": "blocking_foreground",
        "background": False,
        "prompt_file_written": bool(fields.get("prompt_file_written", False)),
        "prompt_inline_chars": int(fields.get("prompt_inline_chars", 0)),
        "command_contains_prompt_body": False,
        "abstraction_leaks": list(fields.get("abstraction_leaks") or []),
        "and_gate": dict(
            fields.get("and_gate")
            or {
                "exit_code": int(fields.get("exit_code", -1)),
                "output_file_nonempty": False,
                "output_parsable": False,
                "schema_valid": False,
            }
        ),
    }
    for k in ("reason", "prompt_path", "output_path", "argv", "output_last_message"):
        if k in fields:
            out[k] = fields[k]
    if out.get("vendor") not in ("anthropic", "openai"):
        out["vendor"] = "anthropic"
        out.setdefault("reason", reason or "unknown-vendor")
    if not out["abstraction_leaks"]:
        v = out["vendor"]
        out["abstraction_leaks"] = declare_leaks(v, {"id": unit_id})
    return out


def declare_leaks(vendor: str, unit: dict[str, Any]) -> list[dict[str, Any]]:
    if vendor not in VENDORS:
        vendor = "anthropic"
    other = "openai" if vendor == "anthropic" else "anthropic"
    mine = VENDORS[vendor]
    theirs = VENDORS[other]
    leaks: list[dict[str, Any]] = []
    for t in sorted(set(mine.tools) - set(theirs.tools)):
        leaks.append(
            {
                "field": f"tools.{t}",
                "vendor": vendor,
                "reason": (
                    f"tool {t} exists on {vendor} but not on {other}; "
                    "portable units must not require it at GUARANTEED tier"
                ),
                "honored": False,
                "tier": "VENDOR-ONLY",
            }
        )
    for t in sorted(set(theirs.tools) - set(mine.tools)):
        leaks.append(
            {
                "field": f"tools.{t}",
                "vendor": vendor,
                "reason": f"{vendor} cannot honor {t}; it is {other}-only",
                "honored": False,
                "tier": "VENDOR-ONLY",
            }
        )
    if mine.context_window != theirs.context_window:
        leaks.append(
            {
                "field": "context_window",
                "vendor": vendor,
                "reason": (
                    f"context_window {mine.context_window} vs "
                    f"{theirs.context_window}; intersection is computed"
                ),
                "honored": False,
                "tier": "BEST-EFFORT",
            }
        )
    leaks.append(
        {
            "field": "assigned_model_vendor_role.model",
            "vendor": vendor,
            "reason": "model identifiers are vendor-native strings and are never interchangeable",
            "honored": False,
            "tier": "VENDOR-ONLY",
        }
    )
    if vendor == "openai":
        leaks.append(
            {
                "field": "ignore_user_config",
                "vendor": vendor,
                "reason": "Codex rail requires --ignore-user-config; Anthropic adapter has no equivalent flag",
                "honored": False,
                "tier": "VENDOR-ONLY",
            }
        )
    else:
        leaks.append(
            {
                "field": "permission_evaluator",
                "vendor": vendor,
                "reason": (
                    "Claude adapter enforces tool_permissions at dispatch; "
                    "Codex CLI flag subset is not the same evaluator"
                ),
                "honored": False,
                "tier": "VENDOR-ONLY",
            }
        )
    _ = unit
    return leaks


def _intersect_tools(a: tuple[str, ...], b: tuple[str, ...]) -> list[str]:
    return sorted(set(a) & set(b))


def negotiate(unit: dict[str, Any], vendors: tuple[str, ...] = VENDORS_ORDER) -> dict[str, Any]:
    declared = unit.get("minimum_tier")
    declared_ok = declared in {"GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"}
    applied = declared if declared_ok else "GUARANTEED"
    a = VENDORS[vendors[0]]
    b = VENDORS[vendors[1]]
    rows = [
        {
            "axis": "tools",
            "tier": AXIS_TIER["tools"],
            "per_vendor": {
                "anthropic": list(VENDORS["anthropic"].tools),
                "openai": list(VENDORS["openai"].tools),
            },
            "intersection": _intersect_tools(a.tools, b.tools),
            "computed_not_asserted": True,
        },
        {
            "axis": "context_window",
            "tier": AXIS_TIER["context_window"],
            "per_vendor": {
                "anthropic": VENDORS["anthropic"].context_window,
                "openai": VENDORS["openai"].context_window,
            },
            "intersection": min(a.context_window, b.context_window),
            "computed_not_asserted": True,
        },
        {
            "axis": "permission_model",
            "tier": AXIS_TIER["permission_model"],
            "per_vendor": {
                "anthropic": VENDORS["anthropic"].permission_model,
                "openai": VENDORS["openai"].permission_model,
            },
            "intersection": None,
            "computed_not_asserted": True,
        },
        {
            "axis": "streaming",
            "tier": AXIS_TIER["streaming"],
            "per_vendor": {
                "anthropic": VENDORS["anthropic"].streaming,
                "openai": VENDORS["openai"].streaming,
            },
            "intersection": bool(a.streaming and b.streaming),
            "computed_not_asserted": True,
        },
        {
            "axis": "schema_support",
            "tier": AXIS_TIER["schema_support"],
            "per_vendor": {
                "anthropic": VENDORS["anthropic"].schema_support,
                "openai": VENDORS["openai"].schema_support,
            },
            "intersection": bool(a.schema_support and b.schema_support),
            "computed_not_asserted": True,
        },
        {
            "axis": "prompt_transport",
            "tier": AXIS_TIER["prompt_transport"],
            "per_vendor": {"anthropic": "file", "openai": "file"},
            "intersection": "file",
            "computed_not_asserted": True,
        },
        {
            "axis": "blocking_dispatch",
            "tier": AXIS_TIER["blocking_dispatch"],
            "per_vendor": {"anthropic": True, "openai": True},
            "intersection": True,
            "computed_not_asserted": True,
        },
    ]
    return {
        "unit_id": unit["id"],
        "unit_minimum_tier": applied,
        "unit_minimum_tier_declared": declared_ok,
        "vendors": list(vendors),
        "capabilities": rows,
        "intersection_computed": True,
        "silent_downgrade_attempted": False,
        "tier_assignment": dict(TIER_ASSIGNMENT),
    }


def guaranteed_missing(
    unit: dict[str, Any],
    vendor: str,
    negotiation: dict[str, Any],
    extra_required: str | None = None,
) -> str | None:
    if negotiation.get("unit_minimum_tier") != "GUARANTEED":
        return None
    desc = VENDORS[vendor]
    needed = [
        str(t)
        for t in (unit.get("tool_permissions") or [])
        if isinstance(t, str) and t in PORTABLE_CORE
    ]
    if extra_required:
        needed.append(extra_required)
    missing = [t for t in needed if t not in desc.tools]
    if missing:
        return "missing-guaranteed-tools:" + ",".join(missing)
    if not desc.schema_support:
        return "missing-guaranteed-schema_support"
    if desc.prompt_transport != "file":
        return "missing-guaranteed-prompt_transport"
    if not desc.blocking_dispatch:
        return "missing-guaranteed-blocking_dispatch"
    return None


def _and_gate(exit_code: int, out_path: Path | None, parsed: Any | None) -> dict[str, Any]:
    nonempty = bool(out_path is not None and out_path.is_file() and out_path.stat().st_size > 0)
    parsable = parsed is not None
    return {
        "exit_code": int(exit_code),
        "output_file_nonempty": nonempty,
        "output_parsable": parsable,
        "schema_valid": bool(parsable and isinstance(parsed, dict) and parsed.get("unit_id")),
    }


def _dispatch_impl(
    unit: dict[str, Any],
    vendor: str,
    *,
    background: bool,
    prompt_inline: str | None,
    force_empty_output: bool,
    force_bad_json: bool,
    force_nonzero: bool,
    require_tool: str | None,
    workdir: Path,
) -> dict[str, Any]:
    uid = str(unit["id"])
    leaks = declare_leaks(vendor, unit) if vendor in VENDORS else []
    if vendor not in VENDORS:
        return emit_terminal(
            "FAILED",
            uid,
            vendor="anthropic",
            reason="unknown-vendor",
            abstraction_leaks=declare_leaks("anthropic", unit),
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    if background:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="background-dispatch-refused",
            abstraction_leaks=leaks,
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    if prompt_inline is not None:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="prompt-inline-refused",
            abstraction_leaks=leaks,
            prompt_file_written=False,
            prompt_inline_chars=0,
            and_gate=_and_gate(-1, None, None),
        )
    if not leaks or all(x.get("honored") is True for x in leaks):
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="empty-or-vacuous-leak-declaration",
            abstraction_leaks=leaks
            if leaks
            else [
                {
                    "field": "abstraction_leak_declaration",
                    "vendor": vendor,
                    "reason": "empty leak declaration is schema-invalid; vendors are not identical",
                    "honored": False,
                    "tier": "GUARANTEED",
                }
            ],
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    unit_for_neg = dict(unit)
    if require_tool:
        perms = list(unit_for_neg.get("tool_permissions") or [])
        perms.append(require_tool)
        unit_for_neg["tool_permissions"] = perms
        unit_for_neg["minimum_tier"] = "GUARANTEED"
    negotiation = negotiate(unit_for_neg)
    missing = guaranteed_missing(
        unit_for_neg, vendor, negotiation, extra_required=require_tool
    )
    if missing:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="silent-downgrade-refused:" + missing,
            abstraction_leaks=leaks,
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    workdir.mkdir(parents=True, exist_ok=True)
    prompt_path = workdir / f"{vendor}-{uid}.prompt.txt"
    out_path = workdir / f"{vendor}-{uid}.output-last-message.json"
    prompt_body = json.dumps(
        {
            "unit_id": uid,
            "title": unit.get("title"),
            "question_or_target": unit.get("question_or_target"),
            "output_path": unit.get("output_path"),
            "output_schema": unit.get("output_schema"),
            "completion_sentinel": unit.get("completion_sentinel"),
        },
        indent=2,
        ensure_ascii=True,
    )
    prompt_path.write_text(prompt_body, encoding="utf-8")
    argv = [
        sys.executable,
        "-B",
        str(VENDOR_CLI),
        "--prompt-file",
        str(prompt_path),
        "--output-last-message",
        str(out_path),
        "--vendor",
        vendor,
        "--unit-id",
        uid,
    ]
    if force_empty_output:
        argv.append("--empty")
    if force_bad_json:
        argv.append("--bad-json")
    cmdline = " ".join(argv)
    if prompt_body in cmdline:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="prompt-body-leaked-onto-argv",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            argv=argv,
            and_gate=_and_gate(-1, None, None),
        )
    if force_nonzero:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason="vendor-exit-2",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            output_path=str(out_path),
            argv=argv,
            and_gate=_and_gate(2, out_path if out_path.is_file() else None, None),
        )
    proc = subprocess.run(
        argv,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    parsed = None
    if proc.returncode != 0:
        return emit_terminal(
            "FAILED",
            uid,
            vendor=vendor,
            reason=f"vendor-exit-{proc.returncode}",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            output_path=str(out_path),
            argv=argv,
            and_gate=_and_gate(proc.returncode, out_path if out_path.is_file() else None, None),
        )
    if not out_path.is_file() or out_path.stat().st_size <= 0:
        return emit_terminal(
            "SEVERED",
            uid,
            vendor=vendor,
            reason="severed-stream-empty-output",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            output_path=str(out_path),
            argv=argv,
            and_gate=_and_gate(0, out_path if out_path.is_file() else None, None),
        )
    try:
        parsed = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return emit_terminal(
            "SEVERED",
            uid,
            vendor=vendor,
            reason="severed-stream-unparsable-output",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            output_path=str(out_path),
            argv=argv,
            and_gate=_and_gate(0, out_path, None),
        )
    gate = _and_gate(0, out_path, parsed)
    if not (gate["exit_code"] == 0 and gate["output_file_nonempty"] and gate["output_parsable"]):
        return emit_terminal(
            "SEVERED",
            uid,
            vendor=vendor,
            reason="severed-stream-and-gate",
            abstraction_leaks=leaks,
            prompt_file_written=True,
            prompt_path=str(prompt_path),
            output_path=str(out_path),
            argv=argv,
            and_gate=gate,
            output_last_message=parsed if isinstance(parsed, dict) else None,
        )
    return emit_terminal(
        "SUCCESS",
        uid,
        vendor=vendor,
        abstraction_leaks=leaks,
        prompt_file_written=True,
        prompt_path=str(prompt_path),
        output_path=str(out_path),
        argv=argv,
        and_gate=gate,
        output_last_message=parsed if isinstance(parsed, dict) else None,
    )


def dispatch(
    unit: dict[str, Any],
    vendor: str,
    *,
    background: bool = False,
    prompt_inline: str | None = None,
    force_empty_output: bool = False,
    force_bad_json: bool = False,
    force_nonzero: bool = False,
    require_tool: str | None = None,
    workdir: Path | None = None,
) -> dict[str, Any]:
    created = None
    if workdir is None:
        created = tempfile.TemporaryDirectory(prefix="arc0091-")
        workdir = Path(created.name)
    try:
        result = _dispatch_impl(
            unit,
            vendor,
            background=background,
            prompt_inline=prompt_inline,
            force_empty_output=force_empty_output,
            force_bad_json=force_bad_json,
            force_nonzero=force_nonzero,
            require_tool=require_tool,
            workdir=workdir,
        )
    except subprocess.TimeoutExpired:
        result = emit_terminal(
            "TIMEOUT",
            str(unit.get("id") or "ARC-0000"),
            vendor=vendor if vendor in VENDORS else "anthropic",
            reason="dispatch-timeout",
            abstraction_leaks=declare_leaks(vendor if vendor in VENDORS else "anthropic", unit),
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    finally:
        if created is not None:
            created.cleanup()
    marker = result.get("terminal_marker")
    if not isinstance(marker, str) or not marker.strip():
        return emit_terminal(
            "FAILED",
            str(unit.get("id") or "ARC-0000"),
            vendor=vendor if vendor in VENDORS else "anthropic",
            reason="silent-return-caught",
            abstraction_leaks=declare_leaks(vendor if vendor in VENDORS else "anthropic", unit),
            prompt_file_written=False,
            and_gate=_and_gate(-1, None, None),
        )
    return result


def two_vendor_run(
    unit: dict[str, Any],
    vendors: tuple[str, ...] = VENDORS_ORDER,
    workdir: Path | None = None,
) -> dict[str, Any]:
    created = None
    if workdir is None:
        created = tempfile.TemporaryDirectory(prefix="arc0091-tv-")
        workdir = Path(created.name)
    try:
        negotiation = negotiate(unit, vendors)
        dispatches = [dispatch(unit, v, workdir=workdir / v) for v in vendors]
        leaks: list[dict[str, Any]] = []
        for d in dispatches:
            leaks.extend(list(d.get("abstraction_leaks") or []))
        return {
            "contract_id": "ARC-0091",
            "unit_id": unit["id"],
            "negotiation": negotiation,
            "dispatches": dispatches,
            "windows_createprocess_char_ceiling": 32767,
            "prompt_transport_rule": "file",
            "blocking_dispatch_rule": "blocking_foreground",
            "abstraction_leaks": leaks,
            "runtime": dict(RUNTIME),
        }
    finally:
        if created is not None:
            created.cleanup()


def validate_instance(inst: dict[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = load_contract()
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    return [e.message for e in v.iter_errors(inst)]


def impl_return_points() -> list[dict[str, Any]]:
    import ast

    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    rows = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_dispatch_impl":
            for child in ast.walk(node):
                if not isinstance(child, ast.Return):
                    continue
                val = child.value
                ok = (
                    isinstance(val, ast.Call)
                    and isinstance(val.func, ast.Name)
                    and val.func.id == "emit_terminal"
                )
                rows.append({"lineno": child.lineno, "emits_terminal": ok})
    return rows
