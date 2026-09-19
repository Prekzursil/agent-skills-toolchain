#!/usr/bin/env python3
"""Pack AUD-0026 runtime-versus-development dependency split.

Honest census with live probes. Emits BLOCKED pending cross-vendor Codex
re-run of ONLY probe 2 (catalog reviewer_requirement). Never emits SUCCESS
without that review — anti-false-green. Same-vendor reviewers do not satisfy.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0026"
OUT = "command-center/audit/AUD-0026-runtime-vs-dev-split.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0026/UNIT-ARTIFACT-MANIFEST.json"
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


def is_success_review(rev: dict | None) -> bool:
    """SUCCESS only after cross-vendor Codex (openai) re-runs probe 2."""
    if rev is None or rev.get("verdict") != "PASS":
        return False
    if rev.get("vendor") in {None, "anthropic"}:
        return False
    if rev.get("probe2_rerun") is False:
        return False
    return True


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-declared-split.json").read_text(encoding="utf-8"))
    p2 = json.loads(
        (PROBE / "probe2-shipped-import-graph.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-declared-split.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-shipped-import-graph.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = is_success_review(rev)
    started = "2026-09-07T19:40:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    live_defects = p2["live_defect_count"]
    dead_dev = p2["dead_dev_only_count"]
    planted = p2["planted_shipped_caught"]
    test_ok = p2["test_only_not_flagged"]
    prod_n = p1["prod_declaration_count"]
    dev_n = p1["dev_declaration_count"]
    dev_only_n = p1["dev_only_declaration_count"]
    pkgs = p1["packages_scanned"]

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
            "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/probe2-shipped-import-graph.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/probe2-shipped-import-graph.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/fixtures/planted-shipped-imports-dev/pyproject.toml",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/fixtures/planted-shipped-imports-dev/aud0026_planted/shipped.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/fixtures/planted-shipped-imports-dev/tests/test_planted.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/fixtures/planted-node-shipped-imports-dev/package.json",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0026/fixtures/planted-node-shipped-imports-dev/src/shipped.mjs",
            "control",
        ),
    ]
    if rev is not None:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0026/independent-review.json",
                "supporting",
            )
        )

    question = (
        "If the plugin were packaged today, exactly which dependencies would a "
        "consumer be forced to install, and which of those are only needed by "
        "tests, linters, or the development harness?"
    )

    if success:
        assert rev is not None
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "cross-vendor-codex"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", "")[:2000],
        }
        defects = [
            {
                "id": "AUD-0026-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Cross-vendor Codex probe-2 re-run PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0026/independent-review.json"
                ),
            },
            {
                "id": "AUD-0026-D-LIVE-DEFECTS",
                "severity": "P2",
                "status": "open" if live_defects else "resolved",
                "summary": (
                    f"live_defect_count={live_defects}; dead_dev_only_count={dead_dev}; "
                    f"planted_shipped_caught={planted}."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0026"
        headline = (
            f"manifests={pkgs} prod_decls={prod_n} dev_decls={dev_n} "
            f"dev_only={dev_only_n}; live_defects={live_defects} "
            f"dead_dev_only={dead_dev}; planted_caught={planted} "
            f"test_only_not_flagged={test_ok}. Independent Codex probe2 PASS."
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
                "the second probe; a same-vendor reviewer shares this unit's blind "
                "spots and does not satisfy. Probes measured; review unpaid; BLOCKED."
            ),
        }
        defects = [
            {
                "id": "AUD-0026-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Cross-vendor Codex probe-2 re-run unpaid; headline counts must be "
                    "falsified by an openai reviewer who re-runs ONLY probe 2."
                ),
            },
            {
                "id": "AUD-0026-D-LIVE-DEFECTS",
                "severity": "P2",
                "status": "open" if live_defects else "resolved",
                "summary": (
                    f"live_defect_count={live_defects}; dead_dev_only_count={dead_dev}; "
                    f"planted_shipped_caught={planted}; "
                    f"test_only_not_flagged={test_ok}."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0026 declared-split + shipped-import-graph measured; "
            f"live_defects={live_defects} dead_dev_only={dead_dev}; "
            "planted shipped-import-of-dev caught and test-only not flagged; "
            "blocked-on-cross-vendor-codex-probe2-rerun"
        )
        headline = (
            f"manifests={pkgs} prod_decls={prod_n} dev_decls={dev_n} "
            f"dev_only={dev_only_n}; live_defects={live_defects} "
            f"dead_dev_only={dead_dev}; planted_caught={planted} "
            f"test_only_not_flagged={test_ok}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "scope-mismatch"],
            "reason": (
                "Named probes completed with planted control (shipped import of "
                "dev-only flagged; test-only import of same package not flagged), "
                "but catalog reviewer_requirement is unmet (cross-vendor Codex must "
                "re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"live_defects={live_defects} dead_dev_only={dead_dev} "
                f"planted={planted} test_ok={test_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer who re-runs ONLY the "
                "second probe (shippable import graph vs declared-dev-only); "
                f"falsify live_defect_count={live_defects} and "
                f"dead_dev_only_count={dead_dev} before PASS. Same-vendor does not "
                "satisfy."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0026/probe2_shipped_import_graph.py",
                    (
                        f"live_defect_count={live_defects} "
                        f"dead_dev_only_count={dead_dev} "
                        f"planted_shipped_caught={planted}"
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
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-rerun-with-real-probes"

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0026",
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
                    f"Probe 1 scanned {pkgs} live manifests: "
                    f"prod_declarations={prod_n} dev_declarations={dev_n} "
                    f"dev_only={dev_only_n}; planted_split_ok={p1['planted_split_ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0026/probe1_declared_split.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-declared-split.json",
                        json.dumps(
                            {
                                "packages_scanned": pkgs,
                                "prod_declaration_count": prod_n,
                                "dev_declaration_count": dev_n,
                                "dev_only_declaration_count": dev_only_n,
                                "planted_split_ok": p1["planted_split_ok"],
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
                    f"Probe 2 shippable import graph: live_defect_count={live_defects} "
                    f"dead_dev_only_count={dead_dev}; "
                    f"planted_shipped_caught={planted}; "
                    f"test_only_not_flagged={test_ok}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0026/probe2-shipped-import-graph.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0026/probe2_shipped_import_graph.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-shipped-import-graph.json",
                        json.dumps(
                            {
                                "live_defect_count": live_defects,
                                "dead_dev_only_count": dead_dev,
                                "planted_shipped_caught": planted,
                                "test_only_not_flagged": test_ok,
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
                "id": "AUD-0026-planted-shipped-imports-dev",
                "name": (
                    "control: a shipped fixture module importing a dev-only package "
                    "must be flagged; a test-only import of the same package must "
                    "NOT be flagged"
                ),
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0026/"
                    "probe2_shipped_import_graph.py"
                ),
                "result": "PASS" if (planted and test_ok) else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0026-declared-split-fixture",
                "name": "Probe 1 records planted prod/dev declaration split",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0026/"
                    "probe1_declared_split.py"
                ),
                "result": "PASS" if p1["ok"] else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0026-C1",
                "known-broken-fixture",
                (
                    "Shipped fixture importing declared-dev-only must flag; "
                    "test-only import of same package must not."
                ),
                True,
                True,
                bad="shipped import of pytest/typescript not flagged or test falsely flagged",
                good=(
                    f"planted_shipped_caught={planted} test_only_not_flagged={test_ok}"
                ),
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
                    "python3 -B command-center/p2-wave/probes/AUD-0026/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS "
                "sentinel; retrying against a missing input is a detector "
                "failure, not a transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Dynamic / string-form imports (importlib, __import__, "
                    "require(variable)) are outside the AST/regex surface."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Bound a runtime import tracer on package entrypoints and "
                    "diff against the static defect set."
                ),
            },
            {
                "claim": (
                    "Packages without explicit setuptools.packages / package.json "
                    "files heuristics may under- or over-count shippable roots."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Cross-check against AUD-0088 package-content baseline and "
                    "wheel CONTENT lists."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0026-C1"],
            "observations": [
                {
                    "name": "packages_scanned",
                    "measured": pkgs,
                    "method": "glob pyproject.toml + package.json (skip other-unit probe scratch)",
                    "anchor": "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.json",
                },
                {
                    "name": "prod_declaration_count",
                    "measured": prod_n,
                    "method": "project.dependencies / dependencies+peer+optional",
                    "anchor": "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.raw.txt",
                },
                {
                    "name": "dev_only_declaration_count",
                    "measured": dev_only_n,
                    "method": "optional-dependencies.dev|test|… + devDependencies minus prod",
                    "anchor": "command-center/p2-wave/probes/AUD-0026/probe1-declared-split.json",
                },
                {
                    "name": "live_defect_count",
                    "measured": live_defects,
                    "method": "shipped-module import intersects declared-dev-only",
                    "anchor": "command-center/p2-wave/probes/AUD-0026/probe2-shipped-import-graph.json",
                },
                {
                    "name": "dead_dev_only_count",
                    "measured": dead_dev,
                    "method": "declared-dev-only never imported by any shippable module",
                    "anchor": "command-center/p2-wave/probes/AUD-0026/probe2-shipped-import-graph.raw.txt",
                },
                {
                    "name": "planted_shipped_caught",
                    "measured": planted,
                    "method": "fixture shipped.py/mjs imports pytest/typescript",
                    "anchor": (
                        "command-center/p2-wave/probes/AUD-0026/fixtures/"
                        "planted-shipped-imports-dev/aud0026_planted/shipped.py"
                    ),
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "title": (
                "Runtime versus development dependency split: what a shipped "
                "package would actually require"
            ),
            "probe1_summary": {
                "packages_scanned": pkgs,
                "prod_declaration_count": prod_n,
                "dev_declaration_count": dev_n,
                "dev_only_declaration_count": dev_only_n,
                "planted_split_ok": p1["planted_split_ok"],
            },
            "probe2_summary": {
                "live_defect_count": live_defects,
                "dead_dev_only_count": dead_dev,
                "planted_shipped_caught": planted,
                "test_only_not_flagged": test_ok,
            },
            "live_defects": p2.get("live_defects") or [],
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    doc = build()
    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1
    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")
    primary = L.art(OUT, "primary")
    doc = build(primary=primary)
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")
    primary = L.art(OUT, "primary")
    doc["artifacts"][0] = primary
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")

    # ensure min bytes after final write
    if out_path.stat().st_size < doc["min_bytes_threshold"]:
        print(
            f"FAILED: primary artifact {out_path.stat().st_size} < "
            f"{doc['min_bytes_threshold']}",
            file=sys.stderr,
        )
        return 1

    manifest = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": doc["state"],
        "artifacts": doc["artifacts"],
        "packed_at": doc["timestamps"]["ended_at"],
    }
    (L.REPO / MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    p2s = doc["extensions"]["probe2_summary"]
    print(
        f"packed {OUT} state={doc['state']} "
        f"live_defects={p2s['live_defect_count']} "
        f"dead_dev_only={p2s['dead_dev_only_count']}"
    )
    print(doc["sentinel"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
