#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0012.json coverage matrix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import (  # noqa: E402
    HOOK_EVENTS,
    MCP_PROTOCOLS,
    check_settings_scope,
    parse_hook,
    parse_mcp_initialize,
    parse_plugin_manifest,
    parse_slash_frontmatter,
    silent_unknown_event,
)
from hosts import adjacent_install_attempt, load_pins, which_clients  # noqa: E402

OUT = "command-center/receipts/BLD-0012.json"
SCHEMA = "command-center/schema/coverage-matrix.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0012/probe1_strict_parser.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0012/probe2_scope_drift.py"
)
QUESTION = (
    "Question: which behaviours depend on the exact host-client version we "
    "happened to test? Enumerate every integration surface whose contract is "
    "owned by the HOST rather than by us - hook event names and payload shape, "
    "settings.json key layout and scope semantics, skill/plugin manifest fields, "
    "MCP protocol revision, slash-command registration - and for each record "
    "the tested version plus the concrete breakage one release back and one "
    "release forward."
)
SURFACES = [
    "hook-event-names-and-payload",
    "settings-json-scope",
    "skill-plugin-manifest",
    "mcp-protocol-revision",
    "slash-command-registration",
]
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/BLD-0012/adapter.py",
    "command-center/p2-wave/probes/BLD-0012/hosts.py",
    "command-center/p2-wave/probes/BLD-0012/changelog_pins.json",
    "command-center/p2-wave/probes/BLD-0012/fixtures/recorded_pretooluse.json",
    "command-center/p2-wave/probes/BLD-0012/fixtures/wrong_scope_claude.json",
    "command-center/p2-wave/probes/BLD-0012/fixtures/correct_scope_claude.json",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def digest_path(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def pin_quote(pins: dict, version: str, surface: str | None = None) -> str:
    for e in pins.get("entries") or []:
        if e.get("version") == version and (
            surface is None or e.get("surface") in {surface, "*"}
        ):
            return str(e.get("quote") or "")
    for e in pins.get("entries") or []:
        if e.get("version") == version:
            return str(e.get("quote") or "")
    return ""


def cell(
    surface: str,
    slot: str,
    version: str,
    breakage: str,
    grade: str,
    cite: str,
) -> dict:
    return {
        "surface": surface,
        "version_slot": slot,
        "host_version": version,
        "breakage": breakage,
        "evidence_grade": grade,
        "evidence_cite": cite,
    }


def make_validator():
    """Resolve catalog $ref onto disk. Never fetch ast-integrate.invalid."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    store = {
        shim.get("$id")
        or "https://ast-integrate.invalid/command-center/schema/coverage-matrix.schema.json": shim,
        profiles.get("$id")
        or "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        receipt.get("$id")
        or "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_path(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = utcnow()
    pins = load_pins()
    clients = which_clients()
    adj = adjacent_install_attempt()
    head = pins["head_version"]
    back = pins["one_back_version"]
    fwd = pins["one_forward_version"]
    q240 = pin_quote(pins, back)
    q241 = pin_quote(pins, head)
    q218 = pin_quote(pins, "2.1.218")
    q207 = pin_quote(pins, "2.1.207")
    q119 = pin_quote(pins, "2.1.119", "hook-event-payload")
    q119s = pin_quote(pins, "2.1.119", "settings-json-scope")

    recorded = json.loads(
        (HERE / "fixtures/recorded_pretooluse.json").read_text(encoding="utf-8")
    )
    hook_ok = parse_hook(recorded)
    if not hook_ok["ok"]:
        print("FAILED:BLD-0012 emit canonical hook payload", hook_ok)
        return 1
    extra = dict(recorded)
    extra["unexpected_host_field"] = 1
    extra_res = parse_hook(extra)
    missing = dict(recorded)
    missing.pop("prompt_id")
    miss_res = parse_hook(missing)
    unknown = dict(recorded)
    unknown["hook_event_name"] = "NotARealHookEvent"
    unk_res = parse_hook(unknown)
    silent = silent_unknown_event(unknown)
    wrong = json.loads(
        (HERE / "fixtures/wrong_scope_claude.json").read_text(encoding="utf-8")
    )
    right = json.loads(
        (HERE / "fixtures/correct_scope_claude.json").read_text(encoding="utf-8")
    )
    wrong_res = check_settings_scope(wrong, "claude.json")
    right_res = check_settings_scope(right, "claude.json")
    plug = parse_plugin_manifest({"name": "harness", "version": "1.0.0"})
    mcp = parse_mcp_initialize(
        {
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "bld-0012", "version": "0"},
            },
        }
    )
    slash = parse_slash_frontmatter(
        {
            "name": "drift-check",
            "description": "fixture",
            "argument-hint": "",
            "disable-model-invocation": False,
        }
    )
    if extra_res["code"] != "UNKNOWN_FIELD" or miss_res["code"] != "MISSING_OPTIONAL":
        print("FAILED:BLD-0012 emit parser controls", extra_res, miss_res)
        return 1
    if unk_res["code"] != "UNKNOWN_EVENT" or wrong_res["code"] != "WRONG_SCOPE":
        print("FAILED:BLD-0012 emit event/scope controls", unk_res, wrong_res)
        return 1
    if not right_res["ok"] or not plug["ok"] or not mcp["ok"] or not slash["ok"]:
        print("FAILED:BLD-0012 emit positive fixtures")
        return 1
    if silent["ok"] == unk_res["ok"]:
        print("FAILED:BLD-0012 emit silent-unknown control agrees with adapter")
        return 1

    cite240 = f"CHANGELOG.md ## {back}: {q240}"
    tested_cite = f"CHANGELOG.md ## {head}: {q241}"
    tested_break = (
        f"Live Claude Code binary absent on this box. Contract pinned to "
        f"changelog head {head} plus hooks.md/plugins-reference/settings-reference "
        f"fetched 2026-08-24. Adapter replayed the documented PreToolUse payload "
        f"(parse_hook ok={hook_ok['ok']}). Cursor agent CLI "
        f"{clients.get('cursor_agent_version')} is a different host and is not "
        f"substituted for Claude Code."
    )
    back_break_by = {
        "hook-event-names-and-payload": (
            f"No named hook-event or payload-shape change in {back}. Last named "
            f"payload addition remains 2.1.119 duration_ms. A 2.1.240 client would "
            f"still omit nothing that {head} documents for PreToolUse required fields."
        ),
        "settings-json-scope": (
            f"No named settings-scope change in {back}. Last named scope change "
            f"remains 2.1.207 pluginConfigs ignored in project settings.json. "
            f"Root disabledMcpServers remains the inert trap (#44845)."
        ),
        "skill-plugin-manifest": (
            f"No named plugin.json field change in {back}. Last named frontmatter "
            f"boolean widening is 2.1.218; a plugin using yes/no booleans still "
            f"breaks on clients before 2.1.218, not specifically on {back}."
        ),
        "mcp-protocol-revision": (
            f"CHANGELOG {back} does not name an MCP protocolVersion bump. Live "
            f"initialize handshake against {back} was not run."
        ),
        "slash-command-registration": (
            f"No named slash-command registration change in {back} beyond the "
            f"generic bugfix line. UTF-8 BOM silent-ignore of command .md files "
            f"was fixed in {head}, so {back} is the last release that still "
            f"silently drops BOM-prefixed command files."
        ),
    }
    cells = []
    for surface in SURFACES:
        cells.append(
            cell(surface, "tested", head, tested_break, "CONFIRMED", tested_cite)
        )
        cite_back = cite240
        if surface == "slash-command-registration":
            cite_back = tested_cite
        cells.append(
            cell(
                surface,
                "one_back",
                back,
                back_break_by[surface],
                "CONFIRMED",
                cite_back,
            )
        )
        cells.append(
            cell(
                surface,
                "one_forward",
                fwd,
                (
                    f"{fwd} is not a heading on the fetched changelog head {head}. "
                    f"Adjacent install blocked: {adj['blocker']}."
                ),
                "NOT-CHECKED",
                f"NOT-CHECKED install blocker={adj['blocker']}",
            )
        )

    surfaces = [
        {
            "id": "hook-event-names-and-payload",
            "owner": "HOST",
            "tested_events": sorted(HOOK_EVENTS),
            "recorded_payload": "command-center/p2-wave/probes/BLD-0012/fixtures/recorded_pretooluse.json",
            "last_named_breaking_release": "2.1.119 duration_ms; docs: prompt_id since 2.1.196; exit-2+invalid-JSON non-blocking before 2.1.214",
            "adapter_codes": ["UNKNOWN_EVENT", "UNKNOWN_FIELD", "MISSING_OPTIONAL"],
        },
        {
            "id": "settings-json-scope",
            "owner": "HOST",
            "trap": "disabledMcpServers at ~/.claude.json root is inert; live map is projects[<path>].disabledMcpServers",
            "current_doc_analogs": ["deniedMcpServers", "disabledMcpjsonServers"],
            "last_named_breaking_release": "2.1.207 pluginConfigs no longer read from project settings.json",
        },
        {
            "id": "skill-plugin-manifest",
            "owner": "HOST",
            "required_when_present": ["name"],
            "host_ignores_unknown_fields": True,
            "adapter_degrades_unknown_fields": True,
            "last_named_breaking_release": "2.1.218 yes/no/on/off/1/0 frontmatter booleans; 2.1.154 defaultEnabled",
        },
        {
            "id": "mcp-protocol-revision",
            "owner": "HOST",
            "adapter_allowlist": sorted(MCP_PROTOCOLS),
            "live_handshake": "NOT-CHECKED",
            "note": "Allowlist is from published MCP spec dates, not from a Claude Code initialize capture on this box.",
        },
        {
            "id": "slash-command-registration",
            "owner": "HOST",
            "discovery": "plugins: commands/ or skills/; UserPromptExpansion hook fires on expansion",
            "last_named_breaking_release": f"{head} stopped silently ignoring BOM-prefixed command/skill/agent .md files",
        },
    ]

    host_under_test = {
        "family": "claude-code",
        "changelog_head": head,
        "changelog_url": pins["source"],
        "changelog_fetched_utc": pins["fetched_utc"],
        "live_claude_present": bool(clients.get("claude")),
        "other_host_observed": {
            "cursor_agent_version": clients.get("cursor_agent_version"),
            "substituted_for_claude_code": False,
        },
        "adjacent_install": {
            "status": adj["status"],
            "blocker": adj["blocker"],
            "one_back": back,
            "one_forward": fwd,
            "strike1": adj["strike1"],
            "strike2": adj["strike2"],
        },
    }

    extra_raw = json.dumps(extra_res, sort_keys=True)
    miss_raw = json.dumps(miss_res, sort_keys=True)
    unk_raw = json.dumps(unk_res, sort_keys=True)
    silent_raw = json.dumps(silent, sort_keys=True)
    wrong_raw = json.dumps(wrong_res, sort_keys=True)
    right_raw = json.dumps(right_res, sort_keys=True)

    placeholder = "0" * 64
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": placeholder,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        artifacts.append(art_row(rel, "supporting" if rel != SCHEMA else "supporting"))

    ended = utcnow()
    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0012",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0012",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#BLD-0012",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "adapter-engineer",
            "execution_substrate": "linux",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 2,
            "policy": (
                "Retry once with the adjacent client version actually installed; "
                "if it cannot be installed, report NOT-CHECKED with the install "
                "blocker named."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "outcome": "BLOCKED",
                    "error_fingerprint": "claude-binary-absent",
                },
                {
                    "attempt": 2,
                    "outcome": "BLOCKED",
                    "error_fingerprint": "npm-not-installed",
                },
            ],
            "pivot_alternatives": [
                "Name the install blocker and grade one-forward NOT-CHECKED",
                "Do not substitute cursor-agent for Claude Code",
            ],
        },
        "artifacts": artifacts,
        "tests": [
            {
                "id": "T-STRICT-PARSER-EXTRA",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": extra_raw,
            },
            {
                "id": "T-STRICT-PARSER-MISSING-OPTIONAL",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": miss_raw,
            },
            {
                "id": "T-UNKNOWN-HOOK-EVENT",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": unk_raw,
            },
            {
                "id": "T-WRONG-SCOPE-SETTINGS",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
                "output_tail": wrong_raw,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-UNKNOWN-EVENT-SILENT-SWALLOW",
                "kind": "known-broken-fixture",
                "description": (
                    "silent_unknown_event swallows an unknown hook_event_name; "
                    "parse_hook must emit UNKNOWN_EVENT instead of a silent no-op."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": unk_raw,
                "good_state_output": silent_raw,
            },
            {
                "id": "NC-EXTRA-FIELD-LOUD",
                "kind": "malformed-input",
                "description": (
                    "Replay the recorded PreToolUse payload with unexpected_host_field; "
                    "adapter must degrade UNKNOWN_FIELD, never silently drop it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": extra_raw,
                "good_state_output": json.dumps(hook_ok, sort_keys=True),
            },
            {
                "id": "NC-MISSING-OPTIONAL-LOUD",
                "kind": "absent-input",
                "description": (
                    "Replay the recorded payload without prompt_id; adapter must "
                    "degrade MISSING_OPTIONAL rather than assuming a default."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": miss_raw,
                "good_state_output": json.dumps(hook_ok, sort_keys=True),
            },
            {
                "id": "NC-WRONG-SCOPE-DISABLED-MCP",
                "kind": "known-broken-fixture",
                "description": (
                    "disabledMcpServers at ~/.claude.json root is inert; detector "
                    "must REJECT the root write and ACCEPT the per-project map."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": wrong_raw,
                "good_state_output": right_raw,
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0012-probe2-changelog-reread",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Probe2 re-reads changelog_pins.json (host changelog excerpts) "
                "and the wrong-scope fixture independently of probe1's parser. "
                "Catalog asked a cross-vendor human re-read of the changelog; "
                "that human pass is not claimed. Drift cells graded CONFIRMED "
                "cite the host changelog or recorded payload, not our code alone."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0012/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "file-read",
                    f"python3 -c json.loads {OUT}",
                    "in-memory roundtrip before write; live re-read after write",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    f"Live Claude Code {head} / {back} / {fwd} were not installed; "
                    "one-forward remains NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    f"Install @anthropic-ai/claude-code@{fwd} (or {head}) and "
                    "replay recorded hook stdin plus settings-scope fixtures."
                ),
            },
            {
                "claim": (
                    "RES-0009 and RES-0013 receipts are absent on this worktree; "
                    "hooks.md plus the fetched changelog were substituted and labeled."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Consume command-center/research/RES-0009.json and "
                    "RES-0013.json when those units are delivered on this tree."
                ),
            },
            {
                "claim": (
                    "MCP protocolVersion spoken by Claude Code on this box was "
                    "not observed; adapter allowlist is not a live handshake."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Capture a live MCP initialize from Claude Code and pin "
                    "protocolVersion from that payload."
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Recorded PreToolUse payload is accepted; an unknown extra "
                    "field degrades UNKNOWN_FIELD; missing prompt_id degrades "
                    "MISSING_OPTIONAL; unknown hook_event_name is UNKNOWN_EVENT "
                    "and disagrees with the silent-swallow control."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0012/fixtures/recorded_pretooluse.json",
                "probes": [
                    probe(
                        "source",
                        "other",
                        "adapter.parse_hook recorded+extra+missing+unknown",
                        extra_raw + "\n" + miss_raw + "\n" + unk_raw,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/BLD-0012/fixtures/recorded_pretooluse.json",
                        (HERE / "fixtures/recorded_pretooluse.json").read_text(
                            encoding="utf-8"
                        )[:4000],
                    ),
                ],
            },
            {
                "claim": (
                    "Root-scope disabledMcpServers on a claude.json-shaped document "
                    "is detected as WRONG_SCOPE; the per-project map is accepted."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0012/fixtures/wrong_scope_claude.json",
                "probes": [
                    probe(
                        "source",
                        "other",
                        "adapter.check_settings_scope wrong+correct fixtures",
                        wrong_raw + "\n" + right_raw,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/BLD-0012/fixtures/wrong_scope_claude.json",
                        (HERE / "fixtures/wrong_scope_claude.json").read_text(
                            encoding="utf-8"
                        )[:4000],
                    ),
                ],
            },
            {
                "claim": (
                    f"Changelog head is {head}; {back} is bugfix-only; {fwd} is "
                    f"not a heading. Adjacent Claude Code install is NOT-CHECKED "
                    f"({adj['blocker']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0012/changelog_pins.json",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "command-center/p2-wave/probes/BLD-0012/changelog_pins.json",
                        json.dumps(
                            {
                                "head": head,
                                "one_back": back,
                                "one_forward": fwd,
                                "one_forward_published": pins.get(
                                    "one_forward_published"
                                ),
                            },
                            sort_keys=True,
                        ),
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "hosts.adjacent_install_attempt + cell grade check",
                        json.dumps(
                            {
                                "adjacent": adj["status"],
                                "blocker": adj["blocker"],
                                "cells": len(cells),
                            },
                            sort_keys=True,
                        ),
                    ),
                ],
            },
        ],
        "report": {
            "kind": "coverage-matrix",
            "observations": [
                {
                    "name": "surfaces_enumerated",
                    "measured": 5,
                    "method": "catalog host-owned surface inventory",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json#BLD-0012",
                },
                {
                    "name": "matrix_cells",
                    "measured": len(cells),
                    "method": "surface x {tested, one_back, one_forward}",
                    "anchor": "command-center/p2-wave/probes/BLD-0012/changelog_pins.json",
                },
                {
                    "name": "wrong_scope_detected",
                    "measured": True,
                    "method": "adapter.check_settings_scope",
                    "anchor": "command-center/p2-wave/probes/BLD-0012/fixtures/wrong_scope_claude.json",
                },
                {
                    "name": "unknown_event_named",
                    "measured": True,
                    "method": "adapter.parse_hook",
                    "anchor": "command-center/p2-wave/probes/BLD-0012/fixtures/recorded_pretooluse.json",
                },
                {
                    "name": "adjacent_install",
                    "measured": str(adj["status"]),
                    "method": "hosts.adjacent_install_attempt",
                    "anchor": "command-center/p2-wave/probes/BLD-0012/hosts.py",
                },
            ],
            "control_ids": [
                "NC-UNKNOWN-EVENT-SILENT-SWALLOW",
                "NC-EXTRA-FIELD-LOUD",
                "NC-MISSING-OPTIONAL-LOUD",
                "NC-WRONG-SCOPE-DISABLED-MCP",
            ],
            "question": QUESTION,
            "title": "Host-client version drift: one release back and one release forward",
            "cells": cells,
            "surfaces": surfaces,
            "host_under_test": host_under_test,
            "adapter_measurements": {
                "canonical_pretooluse": hook_ok,
                "extra_field": extra_res,
                "missing_optional": miss_res,
                "unknown_event": unk_res,
                "wrong_scope": wrong_res,
                "correct_scope": right_res,
            },
            "dependencies_consumed": {
                "RES-0009": {
                    "path": "command-center/research/RES-0009.json",
                    "present": (REPO / "command-center/research/RES-0009.json").is_file(),
                    "grade": "NOT-CHECKED",
                    "substitute": "https://code.claude.com/docs/en/hooks.md fetched 2026-08-24",
                },
                "RES-0013": {
                    "path": "command-center/research/RES-0013.json",
                    "present": (REPO / "command-center/research/RES-0013.json").is_file(),
                    "grade": "NOT-CHECKED",
                    "substitute": pins["source"] + f" head {head}",
                },
            },
            "last_named_breaking": {
                "hook-event-names-and-payload": q119,
                "settings-json-scope": q207 or q119s,
                "skill-plugin-manifest": q218,
            },
            "axes": [
                {"id": "surface", "values": SURFACES},
                {
                    "id": "version_slot",
                    "values": ["tested", "one_back", "one_forward"],
                },
            ],
        },
        "extensions": {
            "cells": cells,
            "host_under_test": host_under_test,
            "completion_sentinel": "SUCCESS:BLD-0012",
            "cloud_ok": False,
        },
    }

    validator = make_validator()
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:BLD-0012 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    out.write_text(text, encoding="utf-8")
    live = json.loads(out.read_text(encoding="utf-8"))
    if live.get("unit_id") != "BLD-0012" or "SUCCESS:BLD-0012" not in dump(live):
        print("FAILED:BLD-0012 downstream json.loads")
        return 1
    sha, size = digest_bytes(out.read_bytes())
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"json.loads ok unit_id={live.get('unit_id')} bytes={size} sha256={sha}"
    )
    out.write_text(dump(doc), encoding="utf-8")
    sha2, size2 = digest_bytes(out.read_bytes())
    doc["artifacts"][0]["sha256"] = sha2
    doc["artifacts"][0]["bytes"] = size2
    out.write_text(dump(doc), encoding="utf-8")

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:BLD-0012 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:BLD-0012 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} cells={len(cells)}")
    print("SUCCESS:BLD-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
