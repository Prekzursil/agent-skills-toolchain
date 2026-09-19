#!/usr/bin/env python3
"""Pack AUD-0094 retirement blast-radius audit.

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

UNIT = "AUD-0094"
OUT = "command-center/audit/AUD-0094-retirement-blast-radius.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0094/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS that re-ran probe 2 is on disk."""
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
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-literal-search.json").read_text(encoding="utf-8"))
    p2 = json.loads(
        (PROBE / "probe2-execution-resolution.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-literal-search.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-execution-resolution.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:50:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dangling = p1["dangling_reference_count"]
    dangling_paths = p1["dangling_deleted_path_count"]
    dangling_files = p1["dangling_surviving_file_count"]
    mention = p1["mention_hit_count"]
    control1 = p1["planted_control"]
    naming_err = p2["resolution_errors_naming_deleted_count"]
    control2 = p2["planted_runtime_parts_control"]

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
            "command-center/p2-wave/probes/AUD-0094/probe1-literal-search.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0094/probe2-execution-resolution.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0094/probe1-literal-search.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0094/probe2-execution-resolution.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0094/deleted_paths.txt",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0094/fixtures/changelog-mention-only/CHANGELOG.md",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0094/independent-review.json",
                "supporting",
            )
        )

    question = (
        "After the owner-approved DELETE-ALL removed 77 files across 5 trees, which "
        "surviving files, manifests, tests, CI steps, or documents still reference a "
        "deleted path?"
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
        sentinel = "SUCCESS:AUD-0094"
        headline = (
            f"deleted=77 literal_dangling={dangling} paths={dangling_paths} "
            f"files={dangling_files} mentions={mention} "
            f"exec_naming_errors={naming_err}; "
            f"changelog_control_ok={control1.get('ok')} "
            f"runtime_parts_ok={control2.get('ok')}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0094-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0094-D-DANGLING",
                "severity": "P2",
                "status": "open" if dangling or naming_err else "resolved",
                "summary": (
                    f"literal_dangling={dangling} exec_naming_errors={naming_err}."
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
                "the second probe (execution-level import graph + CI collect). "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0094 literal-search + execution-resolution probes measured; "
            f"dangling={dangling} naming_errors={naming_err}; "
            "blocked-on-cross-vendor-codex-probe2-rerun"
        )
        headline = (
            f"deleted=77 literal_dangling={dangling} paths={dangling_paths} "
            f"files={dangling_files} mentions={mention} "
            f"exec_naming_errors={naming_err}; "
            f"changelog_control_ok={control1.get('ok')} "
            f"runtime_parts_ok={control2.get('ok')}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "use-vs-mention",
                "detector-failure",
            ],
            "reason": (
                "Named probes completed with planted changelog use-vs-mention control "
                "and runtime-parts execution control, but catalog reviewer_requirement "
                "is unmet (cross-vendor Codex must re-run ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"dangling={dangling} naming_errors={naming_err} "
                f"control1={control1.get('ok')} control2={control2.get('ok')} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0094/probe2_execution_resolution.py "
                "and compare the resolution-error receipt before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0094/probe2_execution_resolution.py",
                    f"naming_errors={naming_err} planted_ok={control2.get('ok')}",
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
                "id": "AUD-0094-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0094-D-DANGLING",
                "severity": "P2",
                "status": "open" if dangling or naming_err else "resolved",
                "summary": (
                    f"literal_dangling={dangling} (paths={dangling_paths}, "
                    f"files={dangling_files}); exec_naming_errors={naming_err}; "
                    f"changelog_control_ok={control1.get('ok')}."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0094",
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
                    f"Probe 1 scanned {p1['files_scanned']} surviving files for "
                    f"{p1['deleted_path_count']} deleted paths: "
                    f"use/dangling={dangling} mention={mention}; "
                    f"planted changelog control_ok={control1.get('ok')} "
                    f"(reported_as_dangling={control1.get('reported_as_dangling')})."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0094/probe1-literal-search.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0094/probe1_literal_search.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-literal-search.json",
                        json.dumps(
                            {
                                "dangling_reference_count": dangling,
                                "dangling_deleted_path_count": dangling_paths,
                                "planted_control_ok": control1.get("ok"),
                                "ok": p1.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 execution-level: python_import_errors="
                    f"{p2['python_import_graph']['resolution_error_count']} "
                    f"node_resolve_errors={p2['node_resolution']['resolution_error_count']} "
                    f"pytest_collect_hits={p2['pytest_collect']['collect_deleted_path_error_hit_count']} "
                    f"naming_deleted={naming_err}; "
                    f"runtime-parts control_ok={control2.get('ok')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0094/probe2-execution-resolution.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0094/probe2_execution_resolution.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-execution-resolution.json",
                        json.dumps(
                            {
                                "resolution_errors_naming_deleted_count": naming_err,
                                "planted_ok": control2.get("ok"),
                                "ok": p2.get("ok"),
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
                "id": "AUD-0094-use-vs-mention-changelog",
                "name": (
                    "control: a deleted path named only inside a changelog entry "
                    "describing its deletion must NOT be reported as a dangling reference"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0094/probe1_literal_search.py",
                "result": "PASS" if control1.get("ok") else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0094-runtime-parts-execution",
                "name": (
                    "Probe 2 planted runtime-joined path parts must surface the "
                    "deleted path in a resolution error"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0094/probe2_execution_resolution.py",
                "result": "PASS" if control2.get("ok") else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0094-C1",
                "other",
                control1.get("rule")
                or "Changelog mention of deleted path must not count as dangling.",
                True,
                True,
                bad="changelog mention reported as dangling",
                good=f"planted_control_ok={control1.get('ok')}",
            ),
            L.control(
                "AUD0094-C2",
                "known-broken-fixture",
                control2.get("description")
                or "Runtime-joined deleted path must appear in resolution error.",
                bool(control2.get("fired_on_bad_state")),
                bool(control2.get("silent_on_good_state", True)),
                bad="runtime parts did not name deleted path",
                good=f"planted_runtime_parts_ok={control2.get('ok')}",
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
                    "python3 -B command-center/p2-wave/probes/AUD-0094/_pack_receipt.py",
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
                    "Some mention classifications rely on deletion-narrative heuristics "
                    "and may under-count true uses in historical prose that also imports."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Hand-label a stratified sample of mention hits and measure "
                    "precision/recall of the MENTION_LINE_RE classifier."
                ),
            },
            {
                "claim": (
                    "Cross-vendor Codex has re-run ONLY probe 2 against this receipt."
                ),
                "verdict": "NOT-CHECKED" if not success else "CONFIRMED",
                "settling_experiment": (
                    "Dispatch openai/Codex reviewer to execute "
                    "probe2_execution_resolution.py and record independent-review.json."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0094-C1", "AUD0094-C2"],
            "observations": [
                {
                    "name": "deleted_path_count",
                    "measured": p1["deleted_path_count"],
                    "method": "git diff-tree --diff-filter=D 696ed513",
                    "anchor": "command-center/p2-wave/probes/AUD-0094/deleted_paths.txt",
                },
                {
                    "name": "dangling_reference_count",
                    "measured": dangling,
                    "method": "literal substring search classified as use",
                    "anchor": "command-center/p2-wave/probes/AUD-0094/probe1-literal-search.json",
                },
                {
                    "name": "mention_hit_count",
                    "measured": mention,
                    "method": "literal hit classified mention (changelog/deletion prose)",
                    "anchor": "command-center/p2-wave/probes/AUD-0094/probe1-literal-search.raw.txt",
                },
                {
                    "name": "resolution_errors_naming_deleted_count",
                    "measured": naming_err,
                    "method": "importlib + node resolve + pytest --collect-only",
                    "anchor": "command-center/p2-wave/probes/AUD-0094/probe2-execution-resolution.json",
                },
                {
                    "name": "changelog_use_vs_mention_control_ok",
                    "measured": bool(control1.get("ok")),
                    "method": "planted CHANGELOG.md mentioning deleted path",
                    "anchor": "command-center/p2-wave/probes/AUD-0094/fixtures/changelog-mention-only/CHANGELOG.md",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "retirement_commit": "696ed513b36608f29e3f29489033a12129938165",
            "probe1_summary": {
                "dangling_reference_count": dangling,
                "dangling_deleted_path_count": dangling_paths,
                "dangling_surviving_file_count": dangling_files,
                "mention_hit_count": mention,
                "planted_control_ok": control1.get("ok"),
            },
            "probe2_summary": {
                "resolution_errors_naming_deleted_count": naming_err,
                "python_resolution_error_count": p2["python_import_graph"][
                    "resolution_error_count"
                ],
                "node_resolution_error_count": p2["node_resolution"][
                    "resolution_error_count"
                ],
                "pytest_collect_hits": p2["pytest_collect"][
                    "collect_deleted_path_error_hit_count"
                ],
                "planted_runtime_parts_ok": control2.get("ok"),
            },
            "wave": "p2-wave",
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    for script in ("probe1_literal_search.py", "probe2_execution_resolution.py"):
        rc, out = L.run(["python3", "-B", str(PROBE / script)], timeout=600)
        if rc != 0:
            print(out)
            print(f"FAILED:{UNIT} {script} exit={rc}")
            return rc

    required = [
        PROBE / "probe1-literal-search.json",
        PROBE / "probe2-execution-resolution.json",
        PROBE / "probe1-literal-search.raw.txt",
        PROBE / "probe2-execution-resolution.raw.txt",
        PROBE / "deleted_paths.txt",
        PROBE / "fixtures/changelog-mention-only/CHANGELOG.md",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0094 missing probe outputs:", *missing, sep="\n")
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
    if rc_adm3 != 0:
        print(adm_out3)
        print(f"FAILED:{UNIT} receipt_validate rejected packed artifact")
        return 1

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
    print(final["report"]["headline"])
    print(adm_out3.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
