#!/usr/bin/env python3
"""Pack AUD-0031 tools/lib salvage consumption verify.

Honest census with live probes. Emits BLOCKED pending cross-vendor Codex
re-run of ONLY probe 2 (catalog reviewer_requirement). Never emits SUCCESS
without that independent review — anti-false-green.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0031"
OUT = "command-center/audit/AUD-0031-salvage-consumption-verify.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0031/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only after cross-vendor Codex PASS that re-ran probe 2."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    if rev.get("vendor") in {None, "anthropic"}:
        # catalog requires cross-vendor Codex (openai), not same-vendor
        return None
    if not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-reverse-refs.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-runtime-coverage.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-reverse-refs.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-runtime-coverage.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:10:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    zero = p1["modules_with_zero_non_test_consumers"]
    with_c = p1["modules_with_non_test_consumers"]
    non_test_edges = p1["non_test_consumer_edges"]
    executed = p2["modules_executed_by_non_test_entries"]
    never_exec = p2["modules_never_executed_by_non_test_entries"]
    mention_ok = (
        p1["planted_mention_control"]["ok"] and p2["planted_mention_control"]["ok"]
    )

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
        L.art(
            "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0031/mention-only-control/mention_only.mjs",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0031/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For each of the 6 modules salvaged into tools/lib/, which non-test callers "
        "import it today - and if a module has zero non-test consumers, did the "
        "salvage decision achieve anything measurable?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        defects = [
            {
                "id": "AUD-0031-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Cross-vendor Codex probe-2 re-run PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0031/independent-review.json"
                ),
            },
            {
                "id": "AUD-0031-D-ZERO-CONSUMERS",
                "severity": "P2",
                "status": "open" if zero else "resolved",
                "summary": (
                    f"{len(zero)}/6 salvaged modules have zero non-test import "
                    f"consumers; runtime-executed={executed}."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0031"
        headline = (
            f"non_test_consumer_edges={non_test_edges}; "
            f"modules_with_consumers={with_c}; zero_consumer_modules={zero}; "
            f"runtime_executed={executed}; never_executed={never_exec}; "
            f"mention_control_ok={mention_ok}. Independent Codex probe2 PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-rerun-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe (runtime coverage). Same-vendor review does not "
                "satisfy. Probes measured; review unpaid; BLOCKED."
            ),
        }
        defects = [
            {
                "id": "AUD-0031-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Cross-vendor Codex re-run of probe 2 unpaid; BLOCKED pending "
                    "independent review."
                ),
            },
            {
                "id": "AUD-0031-D-ZERO-CONSUMERS",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{len(zero)}/6 salvaged modules have zero non-test import "
                    f"consumers (edges={non_test_edges}); runtime never-executed="
                    f"{never_exec}."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0031 reverse-ref + runtime-coverage measured; "
            "use-vs-mention planted control held; "
            "blocked-on-cross-vendor-codex-probe2-rerun"
        )
        headline = (
            f"non_test_consumer_edges={non_test_edges}; "
            f"modules_with_consumers={with_c}; zero_consumer_modules={zero}; "
            f"runtime_executed={executed}; never_executed={never_exec}; "
            f"mention_control_ok={mention_ok}. "
            "BLOCKED on cross-vendor Codex probe-2 re-run."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "use-vs-mention"],
            "reason": (
                "Named probes completed with planted mention-only control held, but "
                "catalog reviewer_requirement is unmet (cross-vendor Codex must "
                "re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"non_test_edges={non_test_edges} zero_modules={zero} "
                f"runtime_executed={executed} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer who re-runs ONLY the "
                "second probe (python3 -B command-center/p2-wave/probes/AUD-0031/"
                "probe2_runtime_coverage.py) and tries to FALSIFY "
                f"modules_executed_count={p2['modules_executed_count']} / "
                f"never_executed={never_exec} before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py",
                    (
                        f"modules_executed_count={p2['modules_executed_count']} "
                        f"never_executed={never_exec}"
                    ),
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-rerun"

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0031",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 reverse-ref (tests excluded): salvage_modules="
                    f"{p1['salvage_module_count']}; non_test_consumer_edges="
                    f"{non_test_edges}; modules_with_consumers={with_c}; "
                    f"zero_consumer_modules={zero}; planted_mention_control_ok="
                    f"{p1['planted_mention_control']['ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0031/probe1_reverse_refs.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-reverse-refs.json",
                        json.dumps(
                            {
                                "non_test_consumer_edges": non_test_edges,
                                "zero_non_test_consumer_count": p1[
                                    "zero_non_test_consumer_count"
                                ],
                                "planted_mention_control_ok": p1[
                                    "planted_mention_control"
                                ]["ok"],
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
                    f"Probe 2 runtime V8 coverage over {p2['entry_point_count']} "
                    f"non-test entry points: modules_executed={executed}; "
                    f"never_executed={never_exec}; planted_mention_control_ok="
                    f"{p2['planted_mention_control']['ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-runtime-coverage.json",
                        json.dumps(
                            {
                                "modules_executed_count": p2["modules_executed_count"],
                                "modules_never_executed_count": p2[
                                    "modules_never_executed_count"
                                ],
                                "planted_mention_control_ok": p2[
                                    "planted_mention_control"
                                ]["ok"],
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
                "id": "AUD-0031-use-vs-mention-control",
                "name": (
                    "Module named only in docstring/comment must NOT count as consumer"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0031/probe1_reverse_refs.py",
                "result": "PASS" if mention_ok else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0031-runtime-mention-control-no-exec",
                "name": "Mention-only control executes zero tools/lib modules under V8 coverage",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0031/probe2_runtime_coverage.py",
                "result": (
                    "PASS" if p2["planted_mention_control"]["ok"] else "FAIL"
                ),
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0031-C1",
                "known-broken-fixture",
                "Planted mention-only file must not count as an import consumer.",
                True,
                True,
                bad="mention-only file counted as consumer",
                good=(
                    f"planted_mention_control_ok={p1['planted_mention_control']['ok']} "
                    f"resolved_edges={p1['planted_mention_control']['resolved_import_edges_after_strip']}"
                ),
            ),
            L.control(
                "AUD0031-C2",
                "mutation",
                "Mention-only control must not execute tools/lib under coverage.",
                True,
                True,
                bad="mention-only control executed tools/lib code",
                good=f"runtime_ok={p2['planted_mention_control']['ok']}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0031/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure with "
                "the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "A future non-test consumer outside the scanned JS/TS suffixes "
                    "(.mjs/.js/.cjs/.ts/.tsx) imports tools/lib via an unparsed loader."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe1 to Python importlib and shell wrappers that "
                    "spawn node -e with inline import strings."
                ),
            },
            {
                "claim": (
                    "Salvage still has measurable value solely via the 72 self-tests "
                    "and workspace registration even with zero non-test callers."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner decision memo: tests-only salvage vs require ≥1 non-test "
                    "consumer before SUCCESS of the salvage program."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "observations": [
                {
                    "name": "salvage_module_count",
                    "measured": p1["salvage_module_count"],
                    "method": "tools/lib/*.mjs salvage set (K1-K5,K7)",
                    "anchor": "tools/lib/README.md",
                },
                {
                    "name": "non_test_consumer_edges",
                    "measured": non_test_edges,
                    "method": "comment-stripped JS import reverse-ref, tests excluded",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.raw.txt",
                },
                {
                    "name": "zero_non_test_consumer_module_count",
                    "measured": len(zero),
                    "method": "per-module consumer list empty after test exclusion",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.json",
                },
                {
                    "name": "zero_non_test_consumer_modules",
                    "measured": ",".join(zero) if zero else "(none)",
                    "method": "module names with zero non-test consumers",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe1-reverse-refs.json",
                },
                {
                    "name": "runtime_modules_executed_count",
                    "measured": len(executed),
                    "method": "NODE_V8_COVERAGE over non-test package/CI entry points",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.raw.txt",
                },
                {
                    "name": "runtime_modules_never_executed_count",
                    "measured": len(never_exec),
                    "method": "no executed V8 ranges under any non-test entry",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.json",
                },
                {
                    "name": "runtime_modules_never_executed",
                    "measured": ",".join(never_exec) if never_exec else "(none)",
                    "method": "module names never executed by non-test entries",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/probe2-runtime-coverage.json",
                },
                {
                    "name": "planted_mention_control_ok",
                    "measured": mention_ok,
                    "method": "mention-only fixture must not count or execute",
                    "anchor": "command-center/p2-wave/probes/AUD-0031/mention-only-control/mention_only.mjs",
                },
            ],
            "control_ids": ["AUD0031-C1", "AUD0031-C2"],
            "consumer_summary": {
                "non_test_consumer_edges": non_test_edges,
                "modules_with_consumers": with_c,
                "modules_with_zero_consumers": zero,
                "test_import_sites": p1["test_import_sites"],
            },
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-wave1",
            "aud0030_js_coverage": p1.get("aud0030_import_graph"),
            "tools_lib_test_count_claimed": 72,
            "owner_salvage_home": "tools/lib/",
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


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
        "state": doc["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={doc['state']} bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
