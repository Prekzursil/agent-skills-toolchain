#!/usr/bin/env python3
"""Emit the ARC-0089 skill contract: a discriminating JSON Schema 2020-12 document."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0089.json"

SENTINEL = "SUCCESS:ARC-0089"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)

MEASUREMENT_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0089/probe2_load_semantics.py"
)

QUESTION = (
    "Specify the skill contract: directory and file shape, the frontmatter and "
    "description fields the capability router consumes, path-scoping semantics, "
    "always-on versus lazily-loaded semantics and which frontmatter field "
    "controls that, and the deploy-parity requirement between the repository "
    "copy and the live skill trees."
)


def schema_doc() -> dict:
    str1 = {"type": "string", "minLength": 1}
    id_token = {
        "type": "string",
        "minLength": 1,
        "maxLength": 64,
        "pattern": "^[a-z][a-z0-9-]*$",
    }
    id_list = {"type": "array", "items": str1}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.invalid/command-center/phase4/contracts/ARC-0089.json",
        "$comment": (
            f"{SENTINEL}. Skill contract pack. Load mode is measured from the "
            "turn-zero context bag (injected body bytes), not inferred by a "
            "frontmatter classifier. Control field is `paths`: absence means "
            "ALWAYS-ON (body injected at turn zero); presence — including "
            'paths: ["**/*"] — means LAZY (index card only until a matching '
            "path is touched). Deploy parity: every repo skill id must exist "
            "with identical SKILL.md sha256 in BOTH live trees "
            "(~/.claude/skills and ~/.agents/skills). Named failure class: "
            "skill exists in repo but not in a live directory. "
            f"Measurement command: {MEASUREMENT_COMMAND}"
        ),
        "title": "Skill contract: package shape, router-facing description, load mode, repo-to-live deploy parity",
        "description": (
            "Draft 2020-12 bundle for skill packages, turn-zero load traces, "
            "and three-way deploy-parity censuses. "
            + QUESTION
            + " "
            + SENTINEL
        ),
        "oneOf": [
            {"$ref": "#/$defs/SkillPackage"},
            {"$ref": "#/$defs/TurnZeroLoadTrace"},
            {"$ref": "#/$defs/DeployParityCensus"},
        ],
        "$defs": {
            "SkillFrontmatter": {
                "type": "object",
                "required": ["name", "description"],
                "additionalProperties": False,
                "properties": {
                    "name": id_token,
                    "description": {
                        "type": "string",
                        "minLength": 16,
                        "maxLength": 1024,
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    "disable-model-invocation": {"type": "boolean"},
                },
            },
            "SkillPackage": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "kind",
                    "id",
                    "directory",
                    "entrypoint",
                    "package_shape",
                    "frontmatter",
                    "router_consumes",
                    "load_mode_control_field",
                    "paths_key_present",
                    "load_mode",
                    "body_injected_at_turn_zero",
                    "deploy_parity_required",
                ],
                "properties": {
                    "kind": {"const": "skill-package"},
                    "id": id_token,
                    "directory": id_token,
                    "entrypoint": {"const": "SKILL.md"},
                    "package_shape": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["required_files"],
                        "properties": {
                            "required_files": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"const": "SKILL.md"},
                            },
                            "optional_files": {
                                "type": "array",
                                "items": str1,
                            },
                        },
                    },
                    "frontmatter": {"$ref": "#/$defs/SkillFrontmatter"},
                    "router_consumes": {
                        "const": ["name", "description"],
                    },
                    "load_mode_control_field": {"const": "paths"},
                    "paths_key_present": {"type": "boolean"},
                    "load_mode": {"enum": ["ALWAYS-ON", "LAZY"]},
                    "body_injected_at_turn_zero": {"type": "boolean"},
                    "deploy_parity_required": {"const": True},
                },
                "allOf": [
                    {
                        "if": {
                            "properties": {"paths_key_present": {"const": True}},
                            "required": ["paths_key_present"],
                        },
                        "then": {
                            "properties": {
                                "load_mode": {"const": "LAZY"},
                                "body_injected_at_turn_zero": {"const": False},
                            }
                        },
                    },
                    {
                        "if": {
                            "properties": {"paths_key_present": {"const": False}},
                            "required": ["paths_key_present"],
                        },
                        "then": {
                            "properties": {
                                "load_mode": {"const": "ALWAYS-ON"},
                                "body_injected_at_turn_zero": {"const": True},
                            }
                        },
                    },
                ],
            },
            "TurnZeroLoadTrace": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "kind",
                    "instrument",
                    "measurement_command",
                    "injected_ids",
                    "always_on_ids",
                    "lazy_ids",
                    "known_always_on_named",
                    "index_card_ids",
                    "router_fields",
                    "load_mode_control_field",
                ],
                "properties": {
                    "kind": {"const": "turn-zero-load-trace"},
                    "instrument": {"type": "string", "minLength": 16},
                    "measurement_command": {"type": "string", "minLength": 16},
                    "touched_path": {"type": ["string", "null"]},
                    "injected_ids": {"type": "array", "minItems": 1, "items": str1},
                    "always_on_ids": {"type": "array", "minItems": 1, "items": str1},
                    "lazy_ids": id_list,
                    "known_always_on_named": {"const": True},
                    "index_card_ids": {"type": "array", "minItems": 1, "items": str1},
                    "router_fields": {"const": ["name", "description"]},
                    "load_mode_control_field": {"const": "paths"},
                },
            },
            "HashMismatch": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "present_in", "sha256", "bytes"],
                "properties": {
                    "id": str1,
                    "present_in": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "enum": ["repo", "live_claude", "live_agents"]
                        },
                    },
                    "sha256": {
                        "type": "object",
                        "minProperties": 1,
                        "additionalProperties": {
                            "type": "string",
                            "minLength": 64,
                            "maxLength": 64,
                            "pattern": "^[a-f0-9]{64}$",
                        },
                    },
                    "bytes": {
                        "type": "object",
                        "minProperties": 1,
                        "additionalProperties": {
                            "type": "integer",
                            "minimum": 1,
                        },
                    },
                },
            },
            "DifferenceSet": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "repo_not_in_live_claude",
                    "repo_not_in_live_agents",
                    "live_claude_not_in_repo",
                    "live_agents_not_in_repo",
                    "live_claude_not_in_live_agents",
                    "live_agents_not_in_live_claude",
                    "hash_mismatch",
                ],
                "properties": {
                    "repo_not_in_live_claude": id_list,
                    "repo_not_in_live_agents": id_list,
                    "live_claude_not_in_repo": id_list,
                    "live_agents_not_in_repo": id_list,
                    "live_claude_not_in_live_agents": id_list,
                    "live_agents_not_in_live_claude": id_list,
                    "hash_mismatch": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/HashMismatch"},
                    },
                },
            },
            "DeployParityCensus": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "kind",
                    "trees",
                    "ids",
                    "identical",
                    "difference_set",
                    "parity_ok",
                    "failure_class_repo_not_in_live",
                    "signals",
                ],
                "properties": {
                    "kind": {"const": "deploy-parity-census"},
                    "trees": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["repo", "live_claude", "live_agents"],
                        "properties": {
                            "repo": str1,
                            "live_claude": str1,
                            "live_agents": str1,
                        },
                    },
                    "ids": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "repo",
                            "live_claude",
                            "live_agents",
                            "union",
                        ],
                        "properties": {
                            "repo": id_list,
                            "live_claude": id_list,
                            "live_agents": id_list,
                            "union": id_list,
                        },
                    },
                    "identical": id_list,
                    "difference_set": {"$ref": "#/$defs/DifferenceSet"},
                    "parity_ok": {"type": "boolean"},
                    "failure_class_repo_not_in_live": {"type": "boolean"},
                    "signals": {
                        "const": ["sha256", "byte-size"],
                    },
                },
            },
        },
        "x-unit-id": "ARC-0089",
        "x-completion-sentinel": SENTINEL,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "x-load-semantics": {
            "control_field": "paths",
            "absent": "ALWAYS-ON: full body injected at turn zero",
            "present": "LAZY: router index only at turn zero; body on path match",
            "demotion": "adding paths, including [\"**/*\"], demotes always-on to lazy",
            "do_not": "infer load behaviour from frontmatter without a context-bag measurement",
            "measurement_command": MEASUREMENT_COMMAND,
        },
        "x-package-shape": {
            "directory": "<skill-id>/",
            "required": ["SKILL.md"],
            "optional": ["reference.md", "examples.md", "scripts/"],
            "live_trees": ["~/.claude/skills", "~/.agents/skills"],
            "repo_trees": ["skills/", ".claude/skills", ".cursor/skills"],
        },
        "x-router-consumes": ["name", "description"],
    }


def valid_skill_package() -> dict:
    return {
        "kind": "skill-package",
        "id": "always-on",
        "directory": "always-on",
        "entrypoint": "SKILL.md",
        "package_shape": {
            "required_files": ["SKILL.md"],
            "optional_files": ["reference.md", "examples.md", "scripts/*"],
        },
        "frontmatter": {
            "name": "always-on",
            "description": "Known always-on skill. Router consumes name and description.",
        },
        "router_consumes": ["name", "description"],
        "load_mode_control_field": "paths",
        "paths_key_present": False,
        "load_mode": "ALWAYS-ON",
        "body_injected_at_turn_zero": True,
        "deploy_parity_required": True,
    }


def invalid_skill_missing_description() -> dict:
    doc = valid_skill_package()
    del doc["frontmatter"]["description"]
    return doc


def inverted_load_mode() -> dict:
    doc = valid_skill_package()
    doc["paths_key_present"] = True
    doc["load_mode"] = "ALWAYS-ON"
    doc["body_injected_at_turn_zero"] = True
    return doc


def errors(validator: Draft202012Validator, instance: object) -> list[str]:
    return [
        f"{list(e.absolute_path)}: {e.message}"
        for e in validator.iter_errors(instance)
    ]


def ready_units_verdict(doc: dict) -> tuple[bool, str]:
    path = REPO / "command-center" / "ready_units.py"
    spec = importlib.util.spec_from_file_location("ready_units_arc0089", path)
    if spec is None or spec.loader is None:
        return False, "ready_units-unimportable"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.schema_doc_verdict(doc)


def main() -> int:
    doc = schema_doc()
    Draft202012Validator.check_schema(doc)
    validator = Draft202012Validator(doc)
    for i, probe in enumerate(GARBAGE):
        errs = errors(validator, probe)
        if not errs:
            print(f"FAILED:ARC-0089 schema accepts garbage[{i}]")
            return 1
    if errors(validator, valid_skill_package()):
        print("FAILED:ARC-0089 valid skill package rejected:")
        print("\n".join(errors(validator, valid_skill_package())))
        return 1
    if not errors(validator, invalid_skill_missing_description()):
        print("FAILED:ARC-0089 missing description was accepted")
        return 1
    if not errors(validator, inverted_load_mode()):
        print("FAILED:ARC-0089 inverted load mode was accepted")
        return 1
    ok, stage = ready_units_verdict(doc)
    if not ok or "discriminates" not in stage:
        print(f"FAILED:ARC-0089 schema_doc_verdict {ok} {stage}")
        return 1
    text = json.dumps(doc, indent=2) + "\n"
    if SENTINEL not in text:
        print("FAILED:ARC-0089 sentinel missing from artifact text")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} stage={stage}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
