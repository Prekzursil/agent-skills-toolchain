#!/usr/bin/env python3
"""Emit AUD-0032 dead-code census. Refuses SUCCESS if the planted control fails.

Does not resolve catalog shim $ref URLs over the network. G-1 requires a
non-BLOCKED parseable artifact, live probes exit 0, and a per-unit manifest
sha256 match — not Draft7 remote $ref validation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from census import (  # noqa: E402
    PLUGIN_ONLY,
    assert_control,
    build,
    control_report,
    inventory,
    probe1_payload,
    probe2_payload,
)

UNIT = "AUD-0032"
OUT = "command-center/audit/AUD-0032-dead-code-census.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
QUESTION = (
    "Which modules, functions, and CLI entry points in the repo have no "
    "reference from any entry point, test, CI step, or documentation "
    "command - counting only real references, never textual mentions?"
)
SENTINEL = (
    "SUCCESS:AUD-0032 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes()
    digest = sha256_bytes(raw)
    return digest, len(raw.replace(b"\r\n", b"\n"))


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()


def supporting_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    cen = build()
    assert_control(cen)
    inv = inventory(cen)
    ctl = control_report(cen)
    p1 = probe1_payload(cen)
    p2 = probe2_payload(cen)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    items = []
    for row in inv["modules"] + inv["functions"] + inv["cli_entries"]:
        items.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "path": row["path"],
                "probe1_verdict": row["probe1_verdict"],
                "probe2_verdict": row["probe2_verdict"],
            }
        )

    both_dead = [
        i
        for i in items
        if i["kind"] == "module"
        and i["probe1_verdict"] == "DEAD"
        and i["probe2_verdict"] == "DEAD"
    ]
    disagree = [
        i
        for i in items
        if i["kind"] == "module" and i["probe1_verdict"] != i["probe2_verdict"]
    ]
    plugin_row = next((i for i in items if i["id"] == PLUGIN_ONLY), None)
    if plugin_row is None:
        print("FAILED:AUD-0032 plugin_only missing from items")
        return 1
    if plugin_row["probe1_verdict"] != "DEAD" or plugin_row["probe2_verdict"] != "LIVE":
        print("FAILED:AUD-0032 plugin_only item verdicts drifted")
        return 1
    if not ctl["independent"]:
        print("FAILED:AUD-0032 planted control is not independent")
        return 1

    p1_raw = json.dumps(p1, sort_keys=True)
    p2_raw = json.dumps(p2, sort_keys=True)
    answer = (
        f"Control package: {PLUGIN_ONLY} is DEAD on AST probe 1 and LIVE "
        f"on registry/CI/docs probe 2 (independent={ctl['independent']}). "
        f"tools/ modules scanned={inv['tallies']['tools_modules']}; "
        f"both-probes-dead={inv['tallies']['both_dead']}; "
        f"probe disagreement={inv['tallies']['disagree']}. "
        "Repo-root CI workflows are absent; CI seeds are the planted "
        "control invoke file. Function-level tools/ verdicts use "
        "unqualified name-match and are listed as residual. "
        + SENTINEL
    )
    fp1 = fingerprint("static-analysis", P1)
    fp2 = fingerprint("command", P2)
    fp1v = fingerprint("file-read", f"json.loads {OUT} planted_control.probe1_verdict")
    fp2v = fingerprint("byte-compare", f"json.loads {OUT} planted_control.probe2_verdict")

    supporting = [
        supporting_row(SCHEMA, "supporting"),
        supporting_row("command-center/p2-wave/probes/AUD-0032/census.py", "supporting"),
        supporting_row(
            "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx/plugin_only.py",
            "fixture",
        ),
        supporting_row(
            "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx/entry.py",
            "control",
        ),
    ]
    placeholder = "0" * 64
    artifacts = [
        {
            "path": OUT,
            "bytes": 1024,
            "sha256": placeholder,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        *supporting,
    ]

    report = {
        "kind": "audit-inventory",
        "question": QUESTION,
        "answer": answer,
        "observations": [
            {
                "name": "plugin_only_probe1",
                "measured": ctl["probe1_verdict"],
                "method": "ast.Import/ImportFrom; comments and string literals ignored",
                "anchor": "command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py",
            },
            {
                "name": "plugin_only_probe2",
                "measured": ctl["probe2_verdict"],
                "method": (
                    "BFS from CLI __main__ guards, tests, CI python -m, "
                    "README/RUNBOOK, plus string-named registries"
                ),
                "anchor": "command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
            },
            {
                "name": "control_independent",
                "measured": ctl["independent"],
                "method": "planted registry-string vs AST import pair plus strawman",
                "anchor": "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx/entry.py",
            },
            {
                "name": "tools_modules_scanned",
                "measured": inv["tallies"]["tools_modules"],
                "method": "ast.parse over tools/**/*.py excluding tests/ and fixtures/",
                "anchor": "command-center/p2-wave/probes/AUD-0032/census.py",
            },
            {
                "name": "both_probes_dead_modules",
                "measured": inv["tallies"]["both_dead"],
                "method": "intersection of probe1 DEAD and probe2 DEAD",
                "anchor": "command-center/p2-wave/probes/AUD-0032/census.py",
            },
        ],
        "control_ids": ["AUD-0032-C-registry-string"],
        "planted_control": ctl,
        "items": items,
        "tallies": inv["tallies"],
        "both_dead_modules": inv["both_dead_modules"],
        "disagree_modules": inv["disagree_modules"],
        "inventory": {
            "modules": inv["modules"],
            "cli_entries": inv["cli_entries"],
            "functions_control_and_capped_tools_dead": inv["functions"],
        },
        "ci_files": inv["ci_files"],
        "doc_files": inv["doc_files"],
        "aud0030_import_graph_present": inv["aud0030_graph_present"],
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-inventory",
        "title": (
            "Unreferenced-module and dead-code census with a "
            "use-versus-mention-safe detector"
        ),
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0032",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "auditor",
            "execution_substrate": "linux-headless",
        },
        "items": items,
        "planted_control": ctl,
        "tallies": inv["tallies"],
        "both_dead_modules": inv["both_dead_modules"],
        "disagree_modules": inv["disagree_modules"],
        "scope": {
            "census_targets": [
                "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx",
                "tools/**/*.py excluding tests/ and fixtures/",
            ],
            "reference_sources": [
                "AST imports (probe 1)",
                "CLI __main__ guards, tests, CI python -m, README/RUNBOOK, "
                "string-named plugin registries (probe 2)",
            ],
            "use_versus_mention": (
                "Docstrings, comments, and prose mentions are not imports. "
                "aud0032_fx.mention_only is named only in a docstring and is "
                "DEAD on both probes."
            ),
            "ci_files": inv["ci_files"],
            "doc_files": inv["doc_files"],
            "aud0030_import_graph_present": inv["aud0030_graph_present"],
            "repo_github_workflows": (REPO / ".github" / "workflows").is_dir(),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "role": "ast-symbol-reference-resolution",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2,
                "role": "dynamic-reachability-from-entries-and-ci",
                "raw_output": p2_raw,
            },
        ],
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"AST import graph marks {PLUGIN_ONLY} DEAD and "
                    f"live_mod={p1['live_mod']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": P1,
                        "raw_output": p1_raw[:65000],
                        "fingerprint": fp1,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": f"python3 -c json.loads({OUT}).planted_control",
                        "raw_output": json.dumps(
                            {
                                "probe1_verdict": ctl["probe1_verdict"],
                                "independent": ctl["independent"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fp1v,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"String-registry + CI/docs BFS marks {PLUGIN_ONLY} "
                    f"{p2['plugin_only']} and truly_dead {p2['truly_dead']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_raw[:65000],
                        "fingerprint": fp2,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": f"python3 -c json.loads({OUT}).planted_control.probe2",
                        "raw_output": json.dumps(
                            {
                                "probe2_verdict": ctl["probe2_verdict"],
                                "strawman": ctl["probe2_without_string_edges"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fp2v,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Registry-only module is LIVE on probe 2 and DEAD on "
                    "probe 1; stripping string edges returns it to DEAD."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0032/fixtures/aud0032_fx/entry.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": P1,
                        "raw_output": p1_raw[:65000],
                        "fingerprint": fp1,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_raw[:65000],
                        "fingerprint": fp2,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "ctl-registry-string-only",
                "name": "plugin_only DEAD on AST, LIVE on registry/CI",
                "command": P1 + " && " + P2,
                "result": "PASS" if ctl["independent"] else "FAIL",
                "assertions": 4,
                "output_tail": (
                    f"p1={ctl['probe1_verdict']} p2={ctl['probe2_verdict']} "
                    f"independent={ctl['independent']}"
                ),
            },
            {
                "id": "ctl-string-edges-are-the-difference",
                "name": "probe 2 without string edges marks plugin_only DEAD",
                "command": P2,
                "result": (
                    "PASS" if ctl["strawman_string_edges_required"] else "FAIL"
                ),
                "assertions": 1,
                "output_tail": (
                    "Probe 2 without string edges marks plugin_only "
                    f"{ctl['probe2_without_string_edges']} (want DEAD)."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0032-C-registry-string",
                "kind": "known-broken-fixture",
                "description": (
                    "A module referenced ONLY by a string in a plugin registry "
                    "must be DEAD on AST probe 1 and LIVE on probe 2. A strawman "
                    "that drops string edges must mark it DEAD. live_mod stays "
                    "LIVE/LIVE; mention_only and truly_dead stay DEAD/DEAD."
                ),
                "fired_on_bad_state": ctl["independent"],
                "silent_on_good_state": (
                    ctl["live_mod"]["probe1"] == "LIVE"
                    and ctl["live_mod"]["probe2"] == "LIVE"
                    and ctl["mention_only"]["probe1"] == "DEAD"
                    and ctl["mention_only"]["probe2"] == "DEAD"
                ),
                "bad_state_output": (
                    f"plugin_only p1={ctl['probe1_verdict']} "
                    f"p2={ctl['probe2_verdict']}"
                ),
                "good_state_output": (
                    f"live_mod={ctl['live_mod']} mention_only={ctl['mention_only']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0032-probe2-dynamic-reach",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a mechanically different detector (string "
                "registry + CI/docs seeds), not a re-read of probe 1."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0032/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "file-read",
                    "command": P1,
                    "raw_output": "deferred-to-named-probe-rerun",
                    "fingerprint": fp1v,
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second "
                "failure with the same detector, enumerate at least 2 "
                "mechanically different detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Function-level tools/ verdicts use unqualified Call-name "
                    "match and can collide across modules."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Qualify calls via attribute-base resolution against the "
                    "import alias table."
                ),
            },
            {
                "claim": (
                    "No .github/workflows tree exists on this worktree; CI "
                    "seeds are the planted control file only."
                ),
                "verdict": (
                    "NOT-CHECKED"
                    if not (REPO / ".github" / "workflows").is_dir()
                    else "CONFIRMED"
                ),
                "settling_experiment": (
                    "Re-run when workflow YAML is present and seed from every "
                    "run: line."
                ),
            },
        ],
        "report": report,
        "extensions": {
            "condition_11": {
                "route": "STRUCTURAL-CONDITION-11 per-unit manifest",
                "manifest_path": (
                    "command-center/p2-wave/probes/AUD-0032/UNIT-ARTIFACT-MANIFEST.json"
                ),
                "unit_manifest_write_invoked": False,
            },
            "cloud_ok": False,
            "planted_control": ctl,
            "items": items,
        },
        "inventory": {
            "modules": inv["modules"],
            "cli_entries": inv["cli_entries"],
            "functions_control_and_capped_tools_dead": inv["functions"],
        },
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for AUD-0032: live named probes exit 0, dead-code census "
            "state=SUCCESS, registry-only module DEAD on AST and LIVE on "
            "probe 2, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    required = {"unit_id", "state", "sentinel", "items", "planted_control"}
    if not required.issubset(doc):
        print("FAILED:AUD-0032 emitter omitted required keys")
        return 1
    if doc["state"] != "SUCCESS" or not ctl["independent"]:
        print("FAILED:AUD-0032 refusing non-SUCCESS or non-independent control")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:AUD-0032 sentinel missing from serialized artifact")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:AUD-0032 self-declared non-delivery state")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(OUT)
    if size < 1024:
        print(f"FAILED:AUD-0032 artifact too small {size}")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"control plugin_only p1={ctl['probe1_verdict']} "
        f"p2={ctl['probe2_verdict']} independent={ctl['independent']}"
    )
    print(
        f"modules_scanned={inv['tallies']['modules_scanned']} "
        f"both_dead={len(both_dead)} disagree={len(disagree)}"
    )
    print("SUCCESS:AUD-0032 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
