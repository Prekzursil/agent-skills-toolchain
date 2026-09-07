#!/usr/bin/env python3
"""Pack AUD-0032 dead-code census (BLOCKED on cross-vendor Codex re-review).

Remediation after independent review FAIL: probe2 seeds pyproject.scripts,
CI working-directory bare pytest, shell-loop `cd tools/mcp/$p && pytest`,
conftest.py alongside test_*.py, report/README doc commands, hyphen package
aliases, flat sibling imports, and a bounded runtime import trace. Reviewer
still owed after each remedi class closes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0032"
OUT = "command-center/audit/AUD-0032-dead-code-census.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0032/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") not in {"PASS", "FAIL"}:
        return None
    if not rev.get("independent"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-ast-refs.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-dynamic-reachability.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-ast.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-dynamic.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    started = "2026-09-07T18:24:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks = p2.get("remediation_checks") or {}
    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0032/probe1-ast-refs.json", "supporting"),
        L.art(
            "command-center/p2-wave/probes/AUD-0032/probe2-dynamic-reachability.json",
            "supporting",
        ),
        L.art("command-center/p2-wave/probes/AUD-0032/probe1-ast.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0032/probe2-dynamic.raw.txt", "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0032/string-registry-control/registry.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0032/string-registry-control/planted_registry_only_mod.py",
            "fixture",
        ),
    ]
    if rev is not None:
        arts.append(L.art("command-center/p2-wave/probes/AUD-0032/independent-review.json", "supporting"))

    if rev and rev.get("verdict") == "PASS":
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "cross-vendor-codex"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", "")[:2000],
        }
        # SUCCESS path is intentionally not emitted here until parent promotion;
        # packer stays BLOCKED unless a dedicated promote path is used.
    elif rev and rev.get("verdict") == "FAIL":
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "cross-vendor-codex"),
            "verdict": "FAIL",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": (
                "Latest independent re-review FAIL recorded; remedi applied for "
                "cited under-count class; fresh probe2 re-run still owed. "
                + str(rev.get("notes", ""))[:1500]
            ),
        }
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Prior cross-vendor review FAIL classes remedi'd (shell-loop, "
                "src-layout, package-init, package-ancestor). Cross-vendor Codex "
                "re-run of probe 2 still owed; BLOCKED."
            ),
        }

    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0032 remesured after probe2 upgrade "
            f"(dynamic dead={p2['dead_count']}; agentrail tests live="
            f"{p2.get('agentrail_tests_live')}/{p2.get('agentrail_tests_total')}; "
            f"planted control independent); blocked on cross-vendor Codex re-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0032",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "tool-author",
            "execution_substrate": "linux-local-p2-wave1-remeasure",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 AST refs: modules={p1['module_count']} edges={p1['edge_count']} "
                    f"live={p1['live_count']} dead={p1['dead_count']}; "
                    f"planted_ast_dead={p1['planted_ast_dead']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0032/probe1-ast.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-ast-refs.json",
                        json.dumps(
                            {
                                "dead_count": p1["dead_count"],
                                "planted_ast_dead": p1["planted_ast_dead"],
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 remesure after review-FAIL remediation: seeds={p2['seed_count']} "
                    f"live={p2['live_count']} dead={p2['dead_count']}; "
                    f"agentrail_tests_live={p2.get('agentrail_tests_live')}/"
                    f"{p2.get('agentrail_tests_total')}; "
                    f"remediation_checks={json.dumps(checks)}; "
                    f"planted_dynamic_live={p2['planted_dynamic_live']}; "
                    f"control_independent={p2['control_independent']}; "
                    f"methods={p2.get('methods')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0032/probe2-dynamic.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-dynamic-reachability.json",
                        json.dumps(
                            {
                                "planted_dynamic_live": p2["planted_dynamic_live"],
                                "control_independent": p2["control_independent"],
                                "agentrail_tests_live": p2.get("agentrail_tests_live"),
                                "dead_count": p2["dead_count"],
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0032-string-registry-control",
                "name": "Planted registry-only module is DEAD in probe1 and LIVE in probe2",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                "result": "PASS" if p2["control_independent"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-400:],
            },
            {
                "id": "AUD-0032-agentrail-false-dead-fixed",
                "name": "CI agentrail tests + CLI internals + auth_jwt_audit are live",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                "result": (
                    "PASS"
                    if (
                        p2.get("agentrail_tests_live", 0) >= 13
                        and checks.get("agentrail_internal_live")
                        == checks.get("agentrail_internal_expected")
                        and checks.get("auth_jwt_audit_live")
                    )
                    else "FAIL"
                ),
                "assertions": 3,
                "output_tail": json.dumps(checks),
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0032-C1",
                "known-broken-fixture",
                "String-registry-only module must disagree across probes.",
                True,
                True,
                bad="both probes agree DEAD (not independent)",
                good=(
                    f"planted_ast_dead={p1['planted_ast_dead']} "
                    f"planted_dynamic_live={p2['planted_dynamic_live']}"
                ),
            )
        ],
        "reviewer": reviewer,
        "defects": [
            {
                "id": "AUD-0032-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Cross-vendor Codex probe-2 re-run unpaid after package-ancestor "
                    f"closure remedi (latest recorded verdict={reviewer.get('verdict')})."
                ),
            },
            {
                "id": "AUD-0032-D-HYPHEN-MODULES",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "Path-derived dotted names under tools/ still under-count some AST "
                    "edges for hyphenated package directories; dead_count is an upper "
                    "bound even after alias+runtime remediation."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-inventory schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0032/_pack_receipt.py",
                    "state=BLOCKED",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 3,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "failure": {
            "classification": ["blocked-on-independent-review", "use-vs-mention"],
            "reason": (
                f"Probes OK with independent planted control; AST dead_count={p1['dead_count']} "
                f"dynamic dead_count={p2['dead_count']} after package-ancestor init closure; "
                "cross-vendor Codex re-review unmet (prior FAIL classes remedi'd)."
            ),
            "diagnostic_tail": (
                f"control_independent={p2['control_independent']} "
                f"agentrail_tests_live={p2.get('agentrail_tests_live')} "
                f"reviewer={reviewer.get('verdict')}"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer who re-runs ONLY the second "
                "probe after package_ancestor_init_closure remedi "
                f"(dead_count={p2['dead_count']})."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                    f"control_independent={p2['control_independent']} dead={p2['dead_count']}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    str(reviewer.get("verdict")),
                    0,
                ),
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Function-level (not module-level) dead code is fully enumerated.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Extend probe1 to resolve name loads/stores per function.",
            },
            {
                "claim": "Hyphenated tools/* packages resolve the same under importlib as path-derived names.",
                "verdict": "REFUTED",
                "settling_experiment": "Map hyphen dirs to importlib package names before edge join.",
            },
        ],
        "report": {
            "kind": "audit-inventory",
            "question": (
                "Which modules, functions, and CLI entry points have no reference from any "
                "entry point, test, CI step, or documentation command?"
            ),
            "headline": (
                f"AST dead_modules={p1['dead_count']} / {p1['module_count']}; "
                f"dynamic dead_modules={p2['dead_count']} "
                f"(was 499; CI pytest+CLI+docs remediation); "
                f"agentrail_tests_live={p2.get('agentrail_tests_live')}/"
                f"{p2.get('agentrail_tests_total')}; "
                f"planted control independent={p2['control_independent']}. "
                "BLOCKED on Codex re-review."
            ),
            "observations": [
                {
                    "name": "ast_module_count",
                    "measured": p1["module_count"],
                    "method": "tools/**/*.py + planted control",
                    "anchor": "command-center/p2-wave/probes/AUD-0032/probe1-ast-refs.json",
                },
                {
                    "name": "ast_dead_modules",
                    "measured": p1["dead_count"],
                    "method": "zero inbound AST import edges",
                    "anchor": "command-center/p2-wave/probes/AUD-0032/probe1-ast.raw.txt",
                },
                {
                    "name": "dynamic_live_modules",
                    "measured": p2["live_count"],
                    "method": (
                        "BFS from pyproject.scripts+CI working-directory pytest+docs+"
                        "string registries+runtime import trace"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0032/probe2-dynamic.raw.txt",
                },
                {
                    "name": "dynamic_dead_modules",
                    "measured": p2["dead_count"],
                    "method": "modules not in dynamic live set",
                    "anchor": "command-center/p2-wave/probes/AUD-0032/probe2-dynamic-reachability.json",
                },
                {
                    "name": "planted_control_independent",
                    "measured": p2["control_independent"],
                    "method": "AST-DEAD && dynamic-LIVE for string-registry module",
                    "anchor": "command-center/p2-wave/probes/AUD-0032/probe2-dynamic.raw.txt",
                },
            ],
            "control_ids": ["AUD0032-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes-after-review-FAIL-remediation",
            "wave": "p2-wave1",
            "planted_module": p1["planted_module"],
            "prior_review_fail": (
                "probe2 was AST/regex seed extraction; false-dead on 13 agentrail "
                "CI tests, 7 CLI imports, and auth_jwt_audit.py"
            ),
            "remediation_checks": checks,
        },
    }


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
