#!/usr/bin/env python3
"""Probe 2: vendor-only requirements are refused, never silently downgraded.

Both-states:
  * a unit requiring only SHARED capabilities is NEGOTIATED on both vendors
  * a unit requiring an openai-only capability is NEGOTIATED on openai and
    REFUSED on anthropic, with the missing atom named and granted empty

A banned silent-downgrade dispatcher (drop missing, return NEGOTIATED) is
shown to disagree with the real dispatcher. The openai/codex column is
recomputed from the published descriptor, not copied from the matrix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import  # noqa: E402

ensure_import()
from vendor_adapter.negotiate import (  # noqa: E402
    VERDICT_NEGOTIATED,
    VERDICT_REFUSED,
    atoms_from_descriptor,
    is_silent_downgrade,
    load_published_descriptors,
    negotiate_cross_vendor,
    negotiate_for_vendor,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0419-probe2 {msg}")
    return 1


def silent_downgrade_dispatcher(unit: dict, vendor: str, descriptors: dict) -> dict:
    """Banned path: drop missing requirements and still call it NEGOTIATED."""
    from vendor_adapter.negotiate import unit_required_atoms

    required = set(unit_required_atoms(unit))
    available = set(atoms_from_descriptor(descriptors[vendor]))
    missing = required - available
    granted = required & available
    return {
        "verdict": VERDICT_NEGOTIATED,
        "vendor": vendor,
        "required": sorted(required),
        "available": sorted(available),
        "missing": sorted(missing),
        "granted": sorted(granted),
        "silent_downgrade": True,
    }


def independent_openai_atoms(doc: dict) -> set[str]:
    """Codex-column recompute from the typed descriptor fields."""
    atoms = {f"tool:{t}" for t in doc["tools"]}
    perm = doc["permission_model"]
    atoms.add(f"permission_model:{perm['kind']}")
    if perm.get("output_last_message_file") is True:
        atoms.add("permission:output_last_message_file")
    if perm.get("fail_closed") is True:
        atoms.add("permission:fail_closed")
    if doc["streaming"].get("token_stream") is True:
        atoms.add("streaming:token_stream")
    if doc["streaming"].get("blocking_foreground") is True:
        atoms.add("streaming:blocking_foreground")
    if doc["prompt_transport"].get("file_required") is True:
        atoms.add("prompt:file_required")
    if doc["prompt_transport"].get("inline_allowed") is True:
        atoms.add("prompt:inline_allowed")
    return atoms


def main() -> int:
    descriptors = load_published_descriptors()
    openai = descriptors["openai"]
    anthropic = descriptors["anthropic"]

    shared_unit = {
        "id": "unit-shared-only",
        "required_tools": ["Read", "Write", "Edit", "Bash:python"],
        "required_capabilities": ["schema:json_schema", "streaming:blocking_foreground"],
    }
    codex_unit = {
        "id": "unit-codex-only",
        "required_tools": ["Read", "Bash:codex"],
        "require_prompt_file": True,
    }
    stream_unit = {
        "id": "unit-stream-only",
        "required_tools": ["Read"],
        "require_streaming": True,
    }
    one_m_unit = {
        "id": "unit-1m-context",
        "required_tools": ["Read"],
        "min_context_window_tokens": 1_000_000,
    }

    # --- both-states: shared vs openai-only ---------------------------------
    shared_a = negotiate_for_vendor(shared_unit, "anthropic", descriptors)
    shared_o = negotiate_for_vendor(shared_unit, "openai", descriptors)
    shared_x = negotiate_cross_vendor(shared_unit, descriptors)
    print(
        json.dumps(
            {
                "shared_anthropic": shared_a.as_dict(),
                "shared_openai": shared_o.as_dict(),
                "shared_cross": shared_x.as_dict(),
            }
        )
    )
    for result in (shared_a, shared_o, shared_x):
        if result.verdict != VERDICT_NEGOTIATED:
            return fail(f"shared unit refused: {result.as_dict()}")
        if result.missing or is_silent_downgrade(result):
            return fail(f"shared unit silent-downgrade shaped: {result.as_dict()}")

    codex_o = negotiate_for_vendor(codex_unit, "openai", descriptors)
    codex_a = negotiate_for_vendor(codex_unit, "anthropic", descriptors)
    codex_x = negotiate_cross_vendor(codex_unit, descriptors)
    print(
        json.dumps(
            {
                "codex_openai": codex_o.as_dict(),
                "codex_anthropic": codex_a.as_dict(),
                "codex_cross": codex_x.as_dict(),
            }
        )
    )
    if codex_o.verdict != VERDICT_NEGOTIATED:
        return fail("openai-only unit refused on openai")
    if codex_a.verdict != VERDICT_REFUSED:
        return fail(
            f"openai-only unit silently accepted on anthropic: {codex_a.as_dict()}"
        )
    if "tool:Bash:codex" not in codex_a.missing:
        return fail(f"anthropic refusal did not name Bash:codex: {codex_a.missing}")
    if "prompt:file_required" not in codex_a.missing:
        return fail(f"anthropic refusal did not name prompt:file_required: {codex_a.missing}")
    if codex_a.granted:
        return fail("REFUSED path granted a partial subset (silent downgrade)")
    if codex_x.verdict != VERDICT_REFUSED:
        return fail("cross-vendor accepted a VENDOR-ONLY requirement")
    if is_silent_downgrade(codex_a) or is_silent_downgrade(codex_x):
        return fail("library produced a silent-downgrade shaped result")

    banned = silent_downgrade_dispatcher(codex_unit, "anthropic", descriptors)
    print(f"banned_silent_downgrade={banned}")
    if not is_silent_downgrade(banned):
        return fail("control: banned dispatcher was not classified as silent downgrade")
    if banned["verdict"] == VERDICT_NEGOTIATED and banned["missing"]:
        print("control: banned path would NEGOTIATE while dropping requirements")
    if codex_a.verdict == banned["verdict"]:
        return fail("real dispatcher matched the banned silent-downgrade verdict")

    # --- anthropic-only streaming -------------------------------------------
    stream_a = negotiate_for_vendor(stream_unit, "anthropic", descriptors)
    stream_o = negotiate_for_vendor(stream_unit, "openai", descriptors)
    print(
        json.dumps(
            {"stream_anthropic": stream_a.as_dict(), "stream_openai": stream_o.as_dict()}
        )
    )
    if stream_a.verdict != VERDICT_NEGOTIATED:
        return fail("streaming unit refused on anthropic")
    if stream_o.verdict != VERDICT_REFUSED:
        return fail("streaming unit silently accepted on openai")
    if "streaming:token_stream" not in stream_o.missing:
        return fail(f"openai refusal did not name token_stream: {stream_o.missing}")
    if stream_o.granted:
        return fail("openai streaming refusal granted a partial subset")

    # --- 1M context: anthropic yes, openai no, cross-vendor no ---------------
    ctx_a = negotiate_for_vendor(one_m_unit, "anthropic", descriptors)
    ctx_o = negotiate_for_vendor(one_m_unit, "openai", descriptors)
    ctx_x = negotiate_cross_vendor(one_m_unit, descriptors)
    print(
        json.dumps(
            {
                "ctx_anthropic": ctx_a.as_dict(),
                "ctx_openai": ctx_o.as_dict(),
                "ctx_cross": ctx_x.as_dict(),
            }
        )
    )
    if ctx_a.verdict != VERDICT_NEGOTIATED:
        return fail("1M context refused on anthropic")
    if ctx_o.verdict != VERDICT_REFUSED:
        return fail("1M context silently accepted on openai")
    if not any(g.startswith("context_window") for g in ctx_o.missing):
        return fail(f"openai 1M refusal did not name context: {ctx_o.missing}")
    if ctx_x.verdict != VERDICT_REFUSED:
        return fail("cross-vendor accepted 1M context despite 272k floor")

    # --- Codex column independently recomputed from openai.json -------------
    recomputed = independent_openai_atoms(openai)
    library_openai = set(atoms_from_descriptor(openai))
    print(f"codex_column_recomputed={sorted(recomputed)}")
    if "tool:Bash:codex" not in recomputed:
        return fail("codex column missing tool:Bash:codex")
    if "prompt:file_required" not in recomputed:
        return fail("codex column missing prompt:file_required")
    if "permission:output_last_message_file" not in recomputed:
        return fail("codex column missing output_last_message_file")
    if "streaming:token_stream" in recomputed:
        return fail("codex column falsely claims token_stream")
    if "tool:Task" in recomputed:
        return fail("codex column falsely claims Task")
    # Library atoms are a superset (schema + context thresholds). Column flags
    # recomputed here must agree with the library on those same flags.
    if not recomputed <= library_openai:
        return fail("codex recompute disagrees with library openai atoms")
    anthropic_atoms = set(atoms_from_descriptor(anthropic))
    if "tool:Bash:codex" in anthropic_atoms:
        return fail("anthropic descriptor unexpectedly lists Bash:codex")
    print("codex_column_accurate=True exclusive_Bash:codex=True no_token_stream=True")

    print("both-states: shared NEGOTIATED; vendor-only REFUSED with named missing")
    print("SUCCESS:IMP-0419-probe2 vendor-only refused; not silently downgraded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
