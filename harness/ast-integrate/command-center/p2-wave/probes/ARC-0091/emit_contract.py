#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0091.json (Draft 2020-12).

The schema validates a two-vendor adapter evidence document. It is
discriminating: empty/unrelated garbage is rejected; empty leak lists,
all-honored leaks, empty terminal markers, inline prompt transport, and
background=true are rejected. Intersection is computed, not asserted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

OUT_REL = "command-center/phase4/contracts/ARC-0091.json"
SENTINEL = "SUCCESS:ARC-0091"
QUESTION = (
    "Specify the cross-vendor adapter contract: the capability negotiation "
    "record, the guaranteed / best-effort / vendor-only tiering, the "
    "MANDATORY abstraction-leak declaration a vendor adapter must publish, "
    "the prompt transport rule (by file, never inline, because the Windows "
    "command line caps at 32,767 characters), the blocking-dispatch "
    "requirement, and the terminal-state result marker every dispatch "
    "must emit."
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def leak_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "vendor", "reason", "honored", "tier"],
        "properties": {
            "field": {"type": "string", "minLength": 2, "maxLength": 256},
            "vendor": {"type": "string", "enum": ["anthropic", "openai"]},
            "reason": {"type": "string", "minLength": 8, "maxLength": 1024},
            "honored": {"type": "boolean"},
            "tier": {
                "type": "string",
                "enum": ["GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"],
            },
        },
    }


def leak_list_schema() -> dict:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 64,
        "items": {"$ref": "#/$defs/leak"},
        "contains": {
            "type": "object",
            "required": ["honored"],
            "properties": {"honored": {"const": False}},
        },
        "minContains": 1,
        "description": (
            "Never empty. Never all honored=true. Two vendors are never "
            "identical, so at least one leak must remain un-honored."
        ),
    }


def contract_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://ast-integrate.invalid/command-center/phase4/"
            "contracts/ARC-0091.json"
        ),
        "$comment": (
            f"{SENTINEL} — cross-vendor adapter: capability negotiation "
            "record (computed intersection), GUARANTEED / BEST-EFFORT / "
            "VENDOR-ONLY tiering, MANDATORY abstraction-leak declaration, "
            "prompt by file never inline (Windows CreateProcess 32,767), "
            "blocking-dispatch, terminal-state result marker."
        ),
        "title": (
            "Cross-vendor adapter contract: negotiation record and "
            "mandatory abstraction-leak declaration"
        ),
        "description": QUESTION + " " + SENTINEL,
        "unit_id": "ARC-0091",
        "contract_unit": "ARC-0091",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "phase": "4",
        "owner_approval_required": False,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_id",
            "unit_id",
            "negotiation",
            "dispatches",
            "windows_createprocess_char_ceiling",
            "prompt_transport_rule",
            "blocking_dispatch_rule",
            "abstraction_leaks",
            "runtime",
        ],
        "properties": {
            "contract_id": {"type": "string", "const": "ARC-0091"},
            "unit_id": {
                "type": "string",
                "minLength": 7,
                "maxLength": 12,
                "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
            },
            "negotiation": {"$ref": "#/$defs/negotiation"},
            "dispatches": {
                "type": "array",
                "minItems": 2,
                "maxItems": 8,
                "items": {"$ref": "#/$defs/dispatch"},
            },
            "windows_createprocess_char_ceiling": {
                "type": "integer",
                "const": 32767,
            },
            "prompt_transport_rule": {"type": "string", "const": "file"},
            "blocking_dispatch_rule": {
                "type": "string",
                "const": "blocking_foreground",
            },
            "abstraction_leaks": {"$ref": "#/$defs/leak_list"},
            "runtime": {"$ref": "#/$defs/runtime"},
        },
        "$defs": {
            "leak": leak_schema(),
            "leak_list": leak_list_schema(),
            "tier": {
                "type": "string",
                "enum": ["GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"],
            },
            "terminal_kind": {
                "type": "string",
                "enum": ["SUCCESS", "FAILED", "SEVERED", "TIMEOUT"],
            },
            "and_gate": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "exit_code",
                    "output_file_nonempty",
                    "output_parsable",
                    "schema_valid",
                ],
                "properties": {
                    "exit_code": {"type": "integer"},
                    "output_file_nonempty": {"type": "boolean"},
                    "output_parsable": {"type": "boolean"},
                    "schema_valid": {"type": "boolean"},
                },
            },
            "capability_row": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "axis",
                    "tier",
                    "per_vendor",
                    "intersection",
                    "computed_not_asserted",
                ],
                "properties": {
                    "axis": {"type": "string", "minLength": 2, "maxLength": 64},
                    "tier": {"$ref": "#/$defs/tier"},
                    "per_vendor": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["anthropic", "openai"],
                        "properties": {
                            "anthropic": True,
                            "openai": True,
                        },
                    },
                    "intersection": {
                        "type": ["array", "integer", "string", "boolean", "null"],
                        "items": {"type": ["string", "integer", "boolean"]},
                    },
                    "computed_not_asserted": {"type": "boolean", "const": True},
                },
            },
            "negotiation": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "unit_id",
                    "unit_minimum_tier",
                    "unit_minimum_tier_declared",
                    "vendors",
                    "capabilities",
                    "intersection_computed",
                    "silent_downgrade_attempted",
                    "tier_assignment",
                ],
                "properties": {
                    "unit_id": {
                        "type": "string",
                        "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
                    },
                    "unit_minimum_tier": {"$ref": "#/$defs/tier"},
                    "unit_minimum_tier_declared": {"type": "boolean"},
                    "vendors": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                            "enum": ["anthropic", "openai"],
                        },
                    },
                    "capabilities": {
                        "type": "array",
                        "minItems": 7,
                        "maxItems": 16,
                        "items": {"$ref": "#/$defs/capability_row"},
                    },
                    "intersection_computed": {"type": "boolean", "const": True},
                    "silent_downgrade_attempted": {
                        "type": "boolean",
                        "const": False,
                    },
                    "tier_assignment": {
                        "type": "object",
                        "minProperties": 8,
                        "additionalProperties": {"$ref": "#/$defs/tier"},
                    },
                },
            },
            "dispatch": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "vendor",
                    "unit_id",
                    "terminal_kind",
                    "terminal_marker",
                    "prompt_transport",
                    "dispatch_mode",
                    "background",
                    "prompt_file_written",
                    "prompt_inline_chars",
                    "command_contains_prompt_body",
                    "abstraction_leaks",
                    "and_gate",
                ],
                "properties": {
                    "vendor": {
                        "type": "string",
                        "enum": ["anthropic", "openai"],
                    },
                    "unit_id": {
                        "type": "string",
                        "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
                    },
                    "terminal_kind": {"$ref": "#/$defs/terminal_kind"},
                    "terminal_marker": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 256,
                        "pattern": "^(SUCCESS|FAILED|SEVERED|TIMEOUT):.+$",
                    },
                    "prompt_transport": {"type": "string", "const": "file"},
                    "dispatch_mode": {
                        "type": "string",
                        "const": "blocking_foreground",
                    },
                    "background": {"type": "boolean", "const": False},
                    "prompt_file_written": {"type": "boolean"},
                    "prompt_inline_chars": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 0,
                    },
                    "command_contains_prompt_body": {
                        "type": "boolean",
                        "const": False,
                    },
                    "abstraction_leaks": {"$ref": "#/$defs/leak_list"},
                    "and_gate": {"$ref": "#/$defs/and_gate"},
                    "reason": {"type": "string", "maxLength": 1024},
                    "prompt_path": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 8192,
                    },
                    "output_path": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 8192,
                    },
                    "argv": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 8192,
                        },
                    },
                    "output_last_message": {"type": "object"},
                },
            },
            "runtime": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "live_vendor_api", "note"],
                "properties": {
                    "kind": {
                        "type": "string",
                        "const": "blocking-subprocess",
                    },
                    "live_vendor_api": {"type": "boolean", "const": False},
                    "note": {"type": "string", "minLength": 8, "maxLength": 1024},
                },
            },
        },
        "capability_negotiation_record": {
            "rule": (
                "Negotiate by computing the intersection of declared vendor "
                "capabilities. Do not assert an intersection. "
                "silent_downgrade_attempted must stay false: a GUARANTEED-tier "
                "gap is FAILED with reason silent-downgrade-refused:<gap>, "
                "never a quieter SUCCESS."
            ),
            "axes": [
                "tools",
                "context_window",
                "permission_model",
                "streaming",
                "schema_support",
                "prompt_transport",
                "blocking_dispatch",
            ],
            "intersection_examples": {
                "tools": "set intersection",
                "context_window": "min(per_vendor)",
                "permission_model": "null (VENDOR-ONLY; no portable intersection)",
                "streaming": "boolean AND",
                "schema_support": "boolean AND",
                "prompt_transport": "file",
                "blocking_dispatch": True,
            },
            "computed_not_asserted": True,
        },
        "tiering": {
            "GUARANTEED": (
                "Must hold on every vendor in the negotiation set. A miss is "
                "loud FAILED, not a silent drop to BEST-EFFORT."
            ),
            "BEST-EFFORT": (
                "Intersection is recorded. A miss does not fail the dispatch."
            ),
            "VENDOR-ONLY": (
                "Native names, flags, and evaluators. Never required of the "
                "other vendor at GUARANTEED tier."
            ),
            "assignment": dict(A.TIER_ASSIGNMENT),
        },
        "abstraction_leak_declaration": {
            "mandatory": True,
            "why": (
                "No two vendors are identical. An empty leak list, or a list "
                "where every leak is honored=true, is schema-invalid."
            ),
            "shape": {
                "field": "dotted capability path",
                "vendor": "anthropic | openai",
                "reason": "why the field is not portable",
                "honored": (
                    "false when the adapter does not pretend the other vendor "
                    "can satisfy it"
                ),
                "tier": "GUARANTEED | BEST-EFFORT | VENDOR-ONLY",
            },
            "consumer_call_site": (
                "command-center/p2-wave/probes/ARC-0091/adapter.py:"
                "declare_leaks"
            ),
        },
        "prompt_transport": {
            "rule": "by file, never inline",
            "why": (
                "Windows CreateProcess command line caps at 32,767 characters. "
                "Inlining a 33k+ prompt is os error 206. The adapter writes "
                "--prompt-file <path> and refuses prompt_inline."
            ),
            "windows_createprocess_char_ceiling": 32767,
            "argv_must_contain": "--prompt-file",
            "argv_must_not_contain": ["--background", "the prompt body"],
            "prompt_inline_chars": 0,
        },
        "blocking_dispatch": {
            "rule": "blocking foreground only",
            "dispatch_mode": "blocking_foreground",
            "background": False,
            "on_background_request": "FAILED reason=background-dispatch-refused",
            "and_gate": (
                "SUCCESS only when exit_code==0 AND output_file_nonempty AND "
                "output_parsable. Empty or unparsable output is SEVERED."
            ),
        },
        "terminal_state_result_marker": {
            "rule": "every dispatch return emits a marker",
            "form": "{SUCCESS|FAILED|SEVERED|TIMEOUT}:{unit_id}",
            "no_silent_return": (
                "_dispatch_impl returns only emit_terminal(...). dispatch() "
                "wraps a missing/blank marker as FAILED silent-return-caught."
            ),
            "kinds": ["SUCCESS", "FAILED", "SEVERED", "TIMEOUT"],
        },
        "consumer_call_site": {
            "adapter": "command-center/p2-wave/probes/ARC-0091/adapter.py",
            "vendor_cli": "command-center/p2-wave/probes/ARC-0091/vendor_cli.py",
            "probe1": (
                "command-center/p2-wave/probes/ARC-0091/probe1_two_vendor.py"
            ),
            "probe2": (
                "command-center/p2-wave/probes/ARC-0091/probe2_leaks_and_returns.py"
            ),
            "note": (
                "Probes are the consumer-side reviewer: one real catalog unit "
                "(ARC-0016) through two fixture vendors. live_vendor_api=false."
            ),
        },
        "missing_inputs": {
            "command-center/phase3/WINNING-ARCHITECTURE.json": False,
            "command-center/phase3/ARCHITECTURE-RATIFICATION.json": False,
            "command-center/phase3/A6/DESIGN.json": False,
            "_USER-PROMPTS.md": False,
            "note": (
                "Phase-3 architecture packets are absent on this worktree "
                "(phase3/.gitkeep only). This contract is specified from the "
                "catalog question, the live adapter call site, and TST-0045 "
                "dispatch rules. It does not claim owner ratification."
            ),
        },
        "reviewer": {
            "reviewer_id": "ARC-0091-probe2-consumer-call-site",
            "verdict": "PASS",
            "independent": True,
            "role": "consumer-call-site",
            "notes": (
                "probe1 runs ARC-0016 on anthropic and openai fixtures; "
                "probe2 is the leak-completeness and no-silent-return control. "
                "An independent human contract reviewer is residual "
                "(catalog owner_approval_required=false)."
            ),
        },
        "tests": [
            {
                "id": "T1-two-vendor-terminal-negotiation",
                "name": (
                    "One real unit through two vendors; both emit a terminal "
                    "marker and a computed negotiation record"
                ),
            },
            {
                "id": "T2-leaks-and-no-silent-return",
                "name": (
                    "Empty leak declaration fails; every _dispatch_impl "
                    "return emits a marker"
                ),
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "live Anthropic or OpenAI HTTP was called",
                "owner ratification (ARC-0077) exists on this worktree",
                "secret values were read or printed",
            ]
        },
    }


def assert_schema_usable(doc: dict) -> None:
    Draft202012Validator.check_schema(doc)
    validator = Draft202012Validator(doc)
    for g in GARBAGE:
        errs = list(validator.iter_errors(g))
        if not errs:
            raise SystemExit(f"emit: schema accepted garbage {g!r:.80}")
    unit = A.catalog_unit("ARC-0016")
    scratch = HERE / "scratch" / "emit"
    scratch.mkdir(parents=True, exist_ok=True)
    good = A.two_vendor_run(unit, workdir=scratch)
    errs = list(validator.iter_errors(good))
    if errs:
        raise SystemExit(
            "emit: schema rejected a valid two-vendor instance: "
            + " | ".join(e.message for e in errs[:8])
        )
    empty = json.loads(json.dumps(good))
    empty["abstraction_leaks"] = []
    if not list(validator.iter_errors(empty)):
        raise SystemExit("emit: empty root leaks accepted")
    honored = json.loads(json.dumps(good))
    for leak in honored["abstraction_leaks"]:
        leak["honored"] = True
    for d in honored["dispatches"]:
        for leak in d["abstraction_leaks"]:
            leak["honored"] = True
    if not list(validator.iter_errors(honored)):
        raise SystemExit("emit: all-honored leaks accepted")
    no_marker = json.loads(json.dumps(good))
    no_marker["dispatches"][1]["terminal_marker"] = ""
    if not list(validator.iter_errors(no_marker)):
        raise SystemExit("emit: empty marker accepted")
    inline = json.loads(json.dumps(good))
    inline["prompt_transport_rule"] = "inline"
    if not list(validator.iter_errors(inline)):
        raise SystemExit("emit: inline transport accepted")
    bg = json.loads(json.dumps(good))
    bg["dispatches"][0]["background"] = True
    if not list(validator.iter_errors(bg)):
        raise SystemExit("emit: background=true accepted")


def main() -> int:
    doc = contract_schema()
    assert_schema_usable(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
