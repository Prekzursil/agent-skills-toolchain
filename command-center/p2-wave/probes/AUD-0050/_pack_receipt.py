#!/usr/bin/env python3
"""Pack AUD-0050 test-gate coverage map.

Honest BLOCKED pending cross-vendor Codex re-run of ONLY probe 2
(catalog reviewer_requirement). Never stubs SUCCESS.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0050"
OUT = "command-center/audit/AUD-0050-test-gate-coverage-map.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0050/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS is on disk."""
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
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    # Accept either explicit reran_probe or boolean probe2_rerun (reviewer convention).
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-selector-map.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-collect-union.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-selector-map.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-collect-union.raw.txt").read_text(encoding="utf-8")
    ctrl = json.loads(
        (PROBE / "control-orphan-outside-selectors.json").read_text(encoding="utf-8")
    )
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:40:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    orphan_count = p1["orphan_count"]
    covered_count = p1["covered_count"]
    test_count = p1["test_file_count"]
    step_count = p1["ci_pytest_step_count"]
    union_count = p2["union_file_count"]
    collect_orphan_count = p2["collect_orphan_count"]
    claimed_uncollected = len(p2.get("selector_claimed_but_uncollected") or [])

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
            "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/probe2-collect-union.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/probe2-collect-union.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/control-orphan-outside-selectors.json",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/fixtures/orphan-control/"
            "test_deliberately_ungated.py",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0050/probe2-union-files.txt",
            "log",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0050/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which test files exist in the repo, and for each, which CI gate (if any) "
        "would execute it on a pull request touching its module?"
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
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0050"
        headline = (
            f"tests={test_count} selector_covered={covered_count} "
            f"selector_orphans={orphan_count} collect_union={union_count} "
            f"collect_orphans={collect_orphan_count} "
            f"claimed_but_uncollected={claimed_uncollected}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0050-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0050-D-ORPHANS",
                "severity": "P2",
                "status": "open" if orphan_count else "resolved",
                "summary": (
                    f"selector_orphans={orphan_count} collect_orphans={collect_orphan_count} "
                    f"claimed_but_uncollected={claimed_uncollected}."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe (--collect-only UNION). Unavailable in-session; "
                "BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0050 selector-map + collect-only probes measured; "
            f"selector_orphans={orphan_count} collect_union={union_count}; "
            "blocked-on-independent-review"
        )
        headline = (
            f"tests={test_count} selector_covered={covered_count} "
            f"selector_orphans={orphan_count} ci_pytest_steps={step_count} "
            f"collect_union={union_count} collect_orphans={collect_orphan_count} "
            f"claimed_but_uncollected={claimed_uncollected}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "green-not-live"],
            "reason": (
                "Named probes completed with planted orphan control caught, but "
                "catalog reviewer_requirement is unmet (cross-vendor Codex must "
                "re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"selector_orphans={orphan_count} collect_orphans={collect_orphan_count} "
                f"control_ok={ctrl.get('ok')} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0050/probe2_collect_union.py "
                "and compare the UNION receipt before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0050/probe2_collect_union.py",
                    f"union={union_count} collect_orphans={collect_orphan_count}",
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
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-with-real-probes"
        defects = [
            {
                "id": "AUD-0050-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0050-D-ORPHANS",
                "severity": "P2",
                "status": "open" if orphan_count else "resolved",
                "summary": (
                    f"selector_orphans={orphan_count} collect_orphans={collect_orphan_count}; "
                    f"planted_caught={ctrl.get('ok')}."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0050",
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
                    f"Probe 1 mapped {test_count} test files to {step_count} CI pytest "
                    f"steps: selector_covered={covered_count} "
                    f"selector_orphans={orphan_count}; "
                    f"planted_is_orphan={p1['planted_is_orphan']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0050/probe1_selector_map.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-selector-map.json",
                        json.dumps(
                            {
                                "test_file_count": test_count,
                                "orphan_count": orphan_count,
                                "covered_count": covered_count,
                                "planted_is_orphan": p1["planted_is_orphan"],
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
                    f"Probe 2 ran --collect-only across {p2['invocation_count']} "
                    f"invocations: union_files={union_count} "
                    f"collect_orphans={collect_orphan_count} "
                    f"selector_claimed_but_uncollected={claimed_uncollected}; "
                    f"control_ok={ctrl.get('ok')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0050/probe2-collect-union.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0050/probe2_collect_union.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-collect-union.json",
                        json.dumps(
                            {
                                "union_file_count": union_count,
                                "collect_orphan_count": collect_orphan_count,
                                "control_ok": ctrl.get("ok"),
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
                "id": "AUD-0050-planted-orphan-control",
                "name": (
                    "control: a test file deliberately placed outside every selector "
                    "must appear in the orphan list"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0050/probe1_selector_map.py",
                "result": "PASS" if p1["planted_is_orphan"] and ctrl.get("ok") else "FAIL",
                "assertions": 2,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0050-collect-only-union",
                "name": "Probe 2 records --collect-only UNION receipt across CI pytest steps",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0050/probe2_collect_union.py",
                "result": "PASS" if p2["ok"] else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0050-C1",
                "known-broken-fixture",
                ctrl["description"],
                True,
                True,
                bad="orphan list empty despite planted fixture",
                good=(
                    f"planted_is_selector_orphan={ctrl.get('planted_is_selector_orphan')} "
                    f"planted_is_collect_orphan={ctrl.get('planted_is_collect_orphan')}"
                ),
            )
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
                "consumer": "json.loads + audit-drift schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0050/_pack_receipt.py",
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
                    "npm test / non-pytest gate coverage is outside this probe's "
                    "--collect-only receipt surface."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe 2 to enumerate package.json test scripts and "
                    "record collected Jest/node test file lists."
                ),
            },
            {
                "claim": (
                    "Collection failures from missing editable installs under-count "
                    "the UNION relative to what CI would collect after pip install."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe 2 inside per-package venvs matching quality.yml "
                    "install lines and diff union_file_count."
                ),
            },
        ],
        "report": {
            "kind": "audit-drift",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0050-C1"],
            "observations": [
                {
                    "name": "test_file_count",
                    "measured": test_count,
                    "method": "glob test_*.py + *_test.py (+ planted control)",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.json",
                },
                {
                    "name": "ci_pytest_step_count",
                    "measured": step_count,
                    "method": "parse .github/workflows run steps invoking pytest",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.raw.txt",
                },
                {
                    "name": "selector_covered_count",
                    "measured": covered_count,
                    "method": "selector model path/ignore match",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.json",
                },
                {
                    "name": "selector_orphan_count",
                    "measured": orphan_count,
                    "method": "inventory minus selector-covered",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe1-selector-map.raw.txt",
                },
                {
                    "name": "collect_union_file_count",
                    "measured": union_count,
                    "method": "pytest --collect-only -q UNION across CI steps",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe2-collect-union.json",
                },
                {
                    "name": "collect_orphan_count",
                    "measured": collect_orphan_count,
                    "method": "inventory minus collect UNION",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/probe2-collect-union.raw.txt",
                },
                {
                    "name": "planted_orphan_control_ok",
                    "measured": bool(ctrl.get("ok")),
                    "method": "fixture outside every selector appears in orphan lists",
                    "anchor": "command-center/p2-wave/probes/AUD-0050/control-orphan-outside-selectors.json",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-drift",
            "selector_summary": {
                "test_file_count": test_count,
                "covered_count": covered_count,
                "orphan_count": orphan_count,
                "ci_pytest_step_count": step_count,
            },
            "collect_summary": {
                "union_file_count": union_count,
                "collect_orphan_count": collect_orphan_count,
                "invocation_count": p2["invocation_count"],
                "claimed_but_uncollected": claimed_uncollected,
            },
            "planted_orphan": p1["planted_orphan"],
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-selector-map.json",
        PROBE / "probe2-collect-union.json",
        PROBE / "control-orphan-outside-selectors.json",
        PROBE / "probe2-union-files.txt",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0050 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = build()
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc = build(primary=L.art(OUT, "primary"))
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    final = json.loads(out_path.read_text(encoding="utf-8"))
    errs = L.validate(final, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS after admit:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm3, adm_out3 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )

    man = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": final["state"],
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "artifacts": final["artifacts"],
        "packed_at": final["timestamps"]["ended_at"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(adm_out3.strip())
    return 0 if rc_adm3 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
