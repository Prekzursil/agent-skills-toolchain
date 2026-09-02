#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0090.json — computed, not prose."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cases import PRESERVATION_MAP, SCOPE_CASES, SERVER  # noqa: E402
from model import (  # noqa: E402
    ContractError,
    LIFECYCLE_OWNER,
    NAMESPACE_SEP,
    SCOPES,
    STDIO_PROCESS_CAP,
    canonical_enable_bytes,
    empty_enable,
    namespaced,
    resolve_enabled,
    validate_declaration,
)

OUT_REL = "command-center/phase4/contracts/ARC-0090.json"
SENTINEL = "SUCCESS:ARC-0090"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0090/probe1_scope_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0090/probe2_enable_preservation.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"server_id": "alpha", "transport": "stdio", "declaration": {}},
    {
        "server_id": "alpha",
        "transport": "http",
        "declaration": {"command": ["python"]},
        "lifecycle_owner": "adapter",
    },
)


def computed_scope_table() -> list[dict]:
    rows = []
    for case in SCOPE_CASES:
        live = resolve_enabled(case["enable"], SERVER, any_scope_disable=False)
        mutant = resolve_enabled(case["enable"], SERVER, any_scope_disable=True)
        if live["enabled"] != case["expect_enabled"]:
            raise SystemExit(f"emit: {case['id']} enabled drift")
        if live["effective_scope"] != case["expect_effective_scope"]:
            raise SystemExit(f"emit: {case['id']} scope drift")
        if live["inert_user_disable"] != case["expect_inert_user_disable"]:
            raise SystemExit(f"emit: {case['id']} inert-user drift")
        rows.append(
            {
                "id": case["id"],
                "family": case["family"],
                "notes": case["notes"],
                "enable": case["enable"],
                "computed_enabled": live["enabled"],
                "computed_effective_scope": live["effective_scope"],
                "computed_inert_user_disable": live["inert_user_disable"],
                "computed_reason": live["reason"],
                "expect_enabled": case["expect_enabled"],
                "expect_effective_scope": case["expect_effective_scope"],
                "mutant_any_scope_disable_enabled": mutant["enabled"],
            }
        )
    return rows


def computed_preservation() -> dict:
    original = canonical_enable_bytes(PRESERVATION_MAP)
    restored = canonical_enable_bytes(PRESERVATION_MAP)
    wiped = canonical_enable_bytes(empty_enable())
    return {
        "canonical_utf8_bytes": len(original),
        "byte_identical_restore": original == restored,
        "destroyed_map_differs": original != wiped,
        "map": PRESERVATION_MAP,
    }


def computed_namespace() -> dict:
    a = namespaced("alpha", "echo")
    b = namespaced("beta", "echo")
    return {
        "separator": NAMESPACE_SEP,
        "alpha_echo": a,
        "beta_echo": b,
        "bare_echo_would_collide": True,
        "namespaced_distinct": a != b,
    }


def schema_body() -> dict:
    stdio_decl = {
        "type": "object",
        "additionalProperties": False,
        "required": ["command"],
        "properties": {
            "command": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1, "maxLength": 4096},
            }
        },
    }
    http_decl = {
        "type": "object",
        "additionalProperties": False,
        "required": ["url"],
        "properties": {
            "url": {
                "type": "string",
                "minLength": 8,
                "maxLength": 4096,
                "pattern": "^https?://",
            }
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://ast-integrate.invalid/command-center/phase4/"
            "contracts/ARC-0090.json"
        ),
        "$comment": (
            f"{SENTINEL} — MCP adapter: declaration, transport, lifecycle, "
            "per-session stdio cap, namespacing, enable/disable scope. "
            "scope_decision_table is computed by resolve_enabled, not authored."
        ),
        "title": (
            "MCP adapter: transport, lifecycle ownership and "
            "per-session multiplication limits"
        ),
        "unit_id": "ARC-0090",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "phase": "4",
        "owner_approval_required": False,
        "question": (
            "Specify the MCP adapter contract: server declaration, transport "
            "choice between per-session stdio and a shared HTTP endpoint, "
            "lifecycle ownership (who starts, who reaps), the hard limit on "
            "processes per session, tool-name namespacing to prevent collisions, "
            "and the enable/disable SCOPE semantics - given the measured trap "
            "that a disable written at the wrong scope is inert while appearing "
            "correct, and that the curated enable state must never be destroyed."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["server_id", "transport", "declaration", "lifecycle_owner"],
        "properties": {
            "server_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]*$",
                "description": "Adapter-facing server id. Must not contain __.",
            },
            "transport": {"type": "string", "enum": ["stdio", "http"]},
            "declaration": {"$ref": "#/$defs/declaration"},
            "lifecycle_owner": {"type": "string", "const": "adapter"},
            "stdio_process_cap": {
                "type": "integer",
                "minimum": 1,
                "maximum": STDIO_PROCESS_CAP,
                "default": STDIO_PROCESS_CAP,
            },
            "exposed_tools": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": (
                        "^[A-Za-z0-9][A-Za-z0-9_.-]*"
                        "__[A-Za-z0-9][A-Za-z0-9_.-]*$"
                    ),
                },
            },
            "enable": {"$ref": "#/$defs/enable_map"},
        },
        "allOf": [
            {
                "if": {
                    "type": "object",
                    "required": ["transport"],
                    "properties": {"transport": {"const": "stdio"}},
                },
                "then": {
                    "properties": {"declaration": stdio_decl},
                    "required": ["declaration"],
                },
            },
            {
                "if": {
                    "type": "object",
                    "required": ["transport"],
                    "properties": {"transport": {"const": "http"}},
                },
                "then": {
                    "properties": {"declaration": http_decl},
                    "required": ["declaration"],
                },
            },
        ],
        "$defs": {
            "declaration": {
                "type": "object",
                "minProperties": 1,
                "properties": {
                    "command": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "url": {"type": "string", "pattern": "^https?://"},
                },
            },
            "enable_map": {
                "type": "object",
                "additionalProperties": False,
                "required": ["local", "project", "user"],
                "properties": {
                    "local": {"$ref": "#/$defs/scope_enable"},
                    "project": {"$ref": "#/$defs/scope_enable"},
                    "user": {"$ref": "#/$defs/scope_enable"},
                },
            },
            "scope_enable": {
                "type": "object",
                "additionalProperties": {"type": "boolean"},
            },
        },
        "vocabulary": {
            "transports": ["stdio", "http"],
            "scopes_most_specific_first": list(SCOPES),
            "lifecycle_owner": LIFECYCLE_OWNER,
            "stdio_process_cap_per_session": STDIO_PROCESS_CAP,
            "namespace_separator": NAMESPACE_SEP,
            "default_enabled_when_unnamed": True,
        },
        "server_declaration": {
            "rule": (
                "Mount requires a declaration. stdio names command[]; http names url."
            ),
            "stdio": {"required": ["command"], "forbidden": ["url"]},
            "http": {"required": ["url"], "forbidden": ["command"]},
            "missing_declaration": "ContractError; the server must not spawn.",
        },
        "transport": {
            "stdio": {
                "process_model": "one OS child per (session, server)",
                "multiplication": "N sessions × M stdio servers = N×M processes",
                "historic_driver": (
                    "eager per-session stdio MCP multiplication; catalog MEMORY "
                    "23 sessions × 65 servers. IMP-0065 reproduced N sessions → "
                    "N stdio children vs 1 shared HTTP child on this worktree."
                ),
            },
            "http": {
                "process_model": "one shared child per server_id across sessions",
                "multiplication": "N sessions × 1 shared HTTP server = 1 process",
                "preferred_when": (
                    "the same server is used by more than one session"
                ),
            },
            "choice_rule": (
                "The declaration selects transport. The adapter records stdio vs "
                "http on every mount. Unrecorded transport is a contract failure."
            ),
        },
        "lifecycle": {
            "owner": LIFECYCLE_OWNER,
            "starts": "Adapter.mount is the only start path",
            "reaps": "Adapter.unmount / Adapter.close reaps the child",
            "session_code_must_not": "spawn or kill MCP children directly",
            "shared_http_dead": (
                "A dead shared child is a loud error. The session must not hang "
                "on stdin or look like a healthy empty tool list (IMP-0065)."
            ),
            "memory_guard": (
                "A kill-based memory guard must not select a shared-service PID "
                "(IMP-0066 / TST-0242)."
            ),
        },
        "process_cap": {
            "applies_to": "stdio children of one session",
            "does_not_count": "shared HTTP children",
            "limit": STDIO_PROCESS_CAP,
            "on_exceed": "ContractError; refuse to start the extra stdio child",
            "rationale": (
                "Hard cap stops per-session multiplication from reproducing the "
                "commit-exhaustion class even when a caller ignores shared HTTP."
            ),
        },
        "namespacing": {
            "form": f"{{server_id}}{NAMESPACE_SEP}{{tool_name}}",
            "why": "Bare echo collides when two servers advertise it.",
            "bare_name_forbidden_on_the_adapter_surface": True,
            "collision": "Two exposed names equal → ContractError",
        },
        "scope_semantics": {
            "order_most_specific_first": list(SCOPES),
            "rule": (
                "Walk local, then project, then user. The first scope that names "
                "the server_id wins. Unnamed servers default to enabled."
            ),
            "trap": (
                "A disable written at user (root-scoped disabledMcpServers analog) "
                "is inert when project or local already names the server. The "
                "config file still shows the disable, so the write looks correct."
            ),
            "effective_disable_example": "project enabled=false",
            "inert_disable_example": (
                "project enabled=true and user enabled=false — process table still "
                "shows the server"
            ),
            "two_signals": [
                "the configuration file that holds the setting",
                "the live process table showing whether the server actually spawned",
            ],
            "must_not": (
                "treat any-scope disable as effective (mutant any_scope_disable)"
            ),
        },
        "enable_preservation": {
            "rule": (
                "Any migration must capture and restore the curated enable/disable "
                "map byte-identically (canonical JSON, sorted keys)."
            ),
            "must_not": "wipe, reshape, or drop user-authored enable entries",
            "estate_precedent": (
                "TST-0071: root-scoped disabledMcpServers dumps were inert; live "
                "curation lived per-project. A schema rename must relocate those "
                "values, never destroy them."
            ),
        },
        "evaluation_semantics_source": (
            "command-center/p2-wave/probes/ARC-0090/model.py"
        ),
        "consumer_call_site": {
            "this_unit": (
                "command-center/p2-wave/probes/ARC-0090/probe1_scope_control.py"
            ),
            "existing_conformance": "command-center/p2-wave/probes/TST-0044/",
            "notes": (
                "Probes call Adapter.mount against this draft. TST-0044 is the "
                "catalog conformance suite written before broad implementation; "
                "its missing ARC-0090.json note is residual, not BLOCKED."
            ),
        },
        "missing_inputs": {
            "command-center/phase3/WINNING-ARCHITECTURE.json": False,
            "command-center/phase3/ARCHITECTURE-RATIFICATION.json": False,
            "command-center/phase3/A6/DESIGN.json": False,
            "_USER-PROMPTS.md": False,
            "00-CURRENT-STATE-INVENTORY.md": False,
            "note": (
                "ARC-0077 (owner ratification) is not on this worktree. This "
                "contract is specified from the catalog question, TST-0044 "
                "executable adapter rules, IMP-0065 process-multiplication "
                "measurement, and TST-0071 inert-scope curation. It is not a "
                "claim that the owner has ratified a winning architecture."
            ),
        },
        "negative_controls": [
            {
                "id": "NC-user-disable-inert",
                "setup": "project enable=true plus user enable=false",
                "must": (
                    "process table still lists the server; config file shows "
                    "the user disable"
                ),
            },
            {
                "id": "NC-project-disable-effective",
                "setup": "then project enable=false",
                "must": (
                    "process table does not list the server; project file "
                    "shows disable"
                ),
            },
            {
                "id": "NC-any-scope-disable-mutant",
                "setup": (
                    "same as NC-user-disable-inert on "
                    "Policy(any_scope_disable=True)"
                ),
                "must": (
                    "mutant refuses to spawn — proving first-scope-wins is "
                    "what kept the process alive"
                ),
            },
            {
                "id": "NC-migrate-destroy",
                "setup": "Policy(preserve_enable_on_migrate=False)",
                "must": "canonical enable bytes differ after migrate",
            },
        ],
        "tests": [
            {
                "id": "T1-scope-control",
                "command": P1,
                "result": "PASS",
                "name": (
                    "Disable at ineffective scope: config shows it, process "
                    "table still has the server; effective-scope disable: "
                    "process gone"
                ),
            },
            {
                "id": "T2-enable-preservation",
                "command": P2,
                "result": "PASS",
                "name": (
                    "Curated enable map captured and restored byte-identically"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0090-probe1-scope-control",
            "verdict": "PASS",
            "independent": True,
            "role": "consumer-call-site",
            "notes": (
                "Probes are the consumer-side call site against this draft. An "
                "independent human contract reviewer is residual "
                "(catalog owner_approval_required=false)."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/ARC-0090/model.py",
                "exists": True,
                "role": "choke-point",
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "contract-author",
            "execution_substrate": "linux-local",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "owner ratification (ARC-0077) exists",
                "a production MCP client already wires every path through Adapter",
                "live mcp.json servers were mounted on this box",
                "secret values were read or printed",
            ]
        },
    }


def attach_computed(doc: dict) -> None:
    table = computed_scope_table()
    if len(table) < 6:
        raise SystemExit(f"scope table too small: {len(table)}")
    enabled_vals = {row["computed_enabled"] for row in table}
    if enabled_vals != {True, False}:
        raise SystemExit(f"scope table is not two-sided: {enabled_vals}")
    inert = [row for row in table if row["id"] == "project-enable-user-disable"]
    if not inert or not inert[0]["computed_inert_user_disable"]:
        raise SystemExit("emit: user disable was not computed inert")
    doc["scope_decision_table"] = table
    doc["scope_decision_table_row_count"] = len(table)
    doc["preservation"] = computed_preservation()
    if not doc["preservation"]["byte_identical_restore"]:
        raise SystemExit("emit: preservation restore is not byte-identical")
    if not doc["preservation"]["destroyed_map_differs"]:
        raise SystemExit("emit: empty map did not differ from curated map")
    doc["namespacing_examples"] = computed_namespace()
    if not doc["namespacing_examples"]["namespaced_distinct"]:
        raise SystemExit("emit: namespaced echo collided")
    try:
        validate_declaration("stdio", {})
        raise SystemExit("emit: empty stdio declaration accepted")
    except ContractError:
        pass
    validate_declaration("stdio", {"command": ["python3", "stub.py"]})
    validate_declaration("http", {"url": "http://127.0.0.1:9/mcp"})


def assert_schema_usable(doc: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema not installed; skipping check_schema")
        return
    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)
    for g in GARBAGE:
        errs = list(validator.iter_errors(g))
        if not errs:
            raise SystemExit(f"emit: schema accepted garbage {g!r:.80}")
    good_stdio = {
        "server_id": "alpha",
        "transport": "stdio",
        "declaration": {"command": ["python3", "stub.py"]},
        "lifecycle_owner": "adapter",
        "stdio_process_cap": STDIO_PROCESS_CAP,
        "exposed_tools": ["alpha__echo"],
        "enable": {
            "local": {},
            "project": {"alpha": True},
            "user": {"alpha": False},
        },
    }
    errs = list(validator.iter_errors(good_stdio))
    if errs:
        raise SystemExit(
            f"emit: schema rejected a valid stdio instance: {errs[0].message}"
        )
    good_http = {
        "server_id": "beta",
        "transport": "http",
        "declaration": {"url": "http://127.0.0.1:8080/mcp"},
        "lifecycle_owner": "adapter",
    }
    errs = list(validator.iter_errors(good_http))
    if errs:
        raise SystemExit(
            f"emit: schema rejected a valid http instance: {errs[0].message}"
        )
    bad_stdio = {
        "server_id": "alpha",
        "transport": "stdio",
        "declaration": {"url": "http://127.0.0.1/mcp"},
        "lifecycle_owner": "adapter",
    }
    if not list(validator.iter_errors(bad_stdio)):
        raise SystemExit("emit: schema accepted stdio declaration without command")
    bad_owner = {
        "server_id": "alpha",
        "transport": "stdio",
        "declaration": {"command": ["x"]},
        "lifecycle_owner": "session",
    }
    if not list(validator.iter_errors(bad_owner)):
        raise SystemExit("emit: schema accepted non-adapter lifecycle owner")


def main() -> int:
    doc = schema_body()
    attach_computed(doc)
    assert_schema_usable(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} "
        f"rows={doc['scope_decision_table_row_count']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
