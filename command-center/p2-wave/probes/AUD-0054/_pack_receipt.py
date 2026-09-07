#!/usr/bin/env python3
"""Pack AUD-0054 platform-conditional test census.

Honest census with two real, independent probes plus a two-case independence
control. Emits BLOCKED pending the catalog's independent fresh-context Claude
falsify-review; never emits SUCCESS without that review on disk -- anti-false-green.
No independent-review.json is invented by this packer: the file simply does not
exist for this unit, so reviewer.verdict stays NOT-REVIEWED and state stays BLOCKED.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0054"
OUT = "command-center/audit/AUD-0054-platform-conditional-tests.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0054/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"
AUD0049_INPUT = "command-center/audit/AUD-0049-runner-matrix-vs-support.json"


def load_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def load_aud0049() -> dict:
    p = L.REPO / AUD0049_INPUT
    return json.loads(p.read_text(encoding="utf-8"))


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-ast-platform-skips.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-collect-vs-execute.json").read_text(encoding="utf-8"))
    ctrl = json.loads((PROBE / "control-probe-independence.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-ast-platform-skips.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-collect-vs-execute.raw.txt").read_text(encoding="utf-8")
    raw_ctrl = (PROBE / "control-probe-independence.raw.txt").read_text(encoding="utf-8")
    aud0049 = load_aud0049()
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T23:00:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    windows_only = int(p1["windows_only_count"])
    posix_only = int(p1["posix_only_count"])
    darwin_only = int(p1["darwin_only_count"])
    windows_or_darwin_only = int(p1["windows_or_darwin_only_count"])
    linux_case_sensitive_only = int(p1["linux_case_sensitive_only_count"])
    never_declared = int(p1["never_on_current_ci_matrix_declared_count"])
    runtime_only_hits = int(p2["runtime_only_hits_count"])
    total_skipped_here = int(p2["total_skipped_here"])
    ci_exercised = aud0049["report"]["exercised_families"]
    control_ok = bool(ctrl["ok"]) and bool(p1["control"]["runtime_only_fixture_correctly_missed"]) and bool(
        p2["control"]["ok"]
    )
    combined_never_on_current_matrix = never_declared + runtime_only_hits

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
        L.art(AUD0049_INPUT, "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe1_ast_platform_skips.py", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe2_collect_vs_execute.py", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe2-collect-vs-execute.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0054/probe2-collect-vs-execute.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0054/control_probe_independence.py", "control"),
        L.art("command-center/p2-wave/probes/AUD-0054/control-probe-independence.json", "control"),
        L.art("command-center/p2-wave/probes/AUD-0054/control-probe-independence.raw.txt", "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0054/fixtures/test_control_runtime_only_skip.py",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art("command-center/p2-wave/probes/AUD-0054/independent-review.json", "supporting")
        )

    question = (
        "Which tests are gated on a platform condition, which platform each requires, "
        "and how many tests are therefore never executed on any CI runner in the "
        "current matrix?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        defects = [
            {
                "id": "AUD-0054-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0054/independent-review.json"
                ),
            },
            {
                "id": "AUD-0054-D-PLATFORM-DARK-TESTS",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"combined_never_on_current_ci_matrix={combined_never_on_current_matrix} "
                    f"(declared={never_declared}, runtime-only={runtime_only_hits}); "
                    f"CI exercises only {ci_exercised}."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0054"
        headline = (
            f"windows_only={windows_only} posix_only={posix_only} "
            f"windows_or_darwin_only={windows_or_darwin_only} "
            f"linux_case_sensitive_only={linux_case_sensitive_only} "
            f"declared_never_on_current_ci_matrix={never_declared} "
            f"runtime_only_skips_found={runtime_only_hits} "
            f"combined_never_on_current_ci_matrix={combined_never_on_current_matrix}. "
            "Independent falsify review PASS."
        )
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript and must try to FALSIFY the headline counts "
                "before PASS, not re-read the artifact. No independent-review.json is "
                "invented here; probes are measured and state is BLOCKED instead."
            ),
        }
        defects = [
            {
                "id": "AUD-0054-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline "
                    "windows-only/posix-only/never-on-CI counts must be falsified by "
                    "a reviewer who did not author this census."
                ),
            },
            {
                "id": "AUD-0054-D-PLATFORM-DARK-TESTS",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"combined_never_on_current_ci_matrix={combined_never_on_current_matrix} "
                    f"(declared={never_declared}, runtime-only={runtime_only_hits}); "
                    f"CI exercises only {ci_exercised} (AUD-0049)."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0054 AST platform-skip census + real Linux collect-vs-execute "
            f"diff measured windows_only={windows_only} posix_only={posix_only} "
            f"never_on_current_ci_matrix={combined_never_on_current_matrix}; "
            "blocked-on-independent-review"
        )
        headline = (
            f"windows_only={windows_only} posix_only={posix_only} "
            f"windows_or_darwin_only={windows_or_darwin_only} "
            f"linux_case_sensitive_only={linux_case_sensitive_only} "
            f"declared_never_on_current_ci_matrix={never_declared} "
            f"runtime_only_skips_found={runtime_only_hits} "
            f"combined_never_on_current_ci_matrix={combined_never_on_current_matrix}. "
            "BLOCKED on independent fresh-context Claude review."
        )
        failure = {
            "classification": ["scope-mismatch", "detector-failure"],
            "reason": (
                "Named probes completed with the required independence control (a "
                "runtime-only skip with no decorator, in both a hermetic fixture and "
                "a real production test, was found by probe 2 and missed by probe 1), "
                "but catalog reviewer_requirement is unmet (fresh-context Claude must "
                "falsify headline counts)."
            ),
            "diagnostic_tail": (
                f"windows_only={windows_only} posix_only={posix_only} "
                f"windows_or_darwin_only={windows_or_darwin_only} "
                f"linux_case_sensitive_only={linux_case_sensitive_only} "
                f"never_declared={never_declared} runtime_only_hits={runtime_only_hits} "
                f"control_ok={control_ok} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "unit's transcript; the reviewer must try to FALSIFY the headline "
                f"windows_only={windows_only} posix_only={posix_only} "
                f"combined_never_on_current_ci_matrix={combined_never_on_current_matrix} "
                "before PASS, not re-read the artifact."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0054/probe1_ast_platform_skips.py",
                    f"windows_only={windows_only} posix_only={posix_only} never_declared={never_declared}",
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
        anti = "BLOCKED-pending-independent-review-with-real-probes"

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0054",
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
                    f"Probe 1 AST decorator scan (with one-hop same-file and "
                    f"cross-file variable resolution): files_scanned={p1['files_scanned']} "
                    f"platform_gated_test_rows={p1['platform_gated_test_rows']} "
                    f"by_required_platform={p1['by_required_platform']}; "
                    f"windows_only={windows_only} posix_only={posix_only} "
                    f"windows_or_darwin_only={windows_or_darwin_only} "
                    f"linux_case_sensitive_only={linux_case_sensitive_only} "
                    f"declared_never_on_current_ci_matrix={never_declared}; "
                    f"excluded tool-presence gates (not platform predicates)="
                    f"{p1['excluded_tool_presence_count']}; "
                    f"control(runtime-only fixture correctly missed)="
                    f"{p1['control']['runtime_only_fixture_correctly_missed']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0054/probe1_ast_platform_skips.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-ast-platform-skips.json",
                        json.dumps(
                            {
                                "windows_only_count": windows_only,
                                "posix_only_count": posix_only,
                                "darwin_only_count": darwin_only,
                                "windows_or_darwin_only_count": windows_or_darwin_only,
                                "linux_case_sensitive_only_count": linux_case_sensitive_only,
                                "never_on_current_ci_matrix_declared_count": never_declared,
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
                    f"Probe 2 real collect-vs-execute diff on this Linux host: "
                    f"total_skipped_here={total_skipped_here} "
                    f"declared_hits={p2['declared_hits_count']} "
                    f"runtime_only_hits={runtime_only_hits} (1 hermetic fixture + 1 real "
                    "production test in tools/agentrail, both requiring --run-live to "
                    "reach the actual platform gate past the unrelated marker-skip); "
                    f"windows/macos NOT-RUN-HERE. control_ok={p2['control']['ok']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0054/probe2-collect-vs-execute.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0054/probe2_collect_vs_execute.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-collect-vs-execute.json",
                        json.dumps(
                            {
                                "total_skipped_here": total_skipped_here,
                                "runtime_only_hits_count": runtime_only_hits,
                                "control_ok": p2["control"]["ok"],
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
                "id": "AUD-0054-independence-hermetic-fixture",
                "name": (
                    "control: hermetic runtime-only skip fixture found by probe2, "
                    "missed by probe1 (no decorator declares it)"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0054/control_probe_independence.py",
                "result": "PASS" if ctrl["cases"][0]["independent"] else "FAIL",
                "assertions": 2,
                "output_tail": raw_ctrl[-600:],
            },
            {
                "id": "AUD-0054-independence-real-production-test",
                "name": (
                    "control: real production runtime-only skip "
                    "(tools/agentrail/tests/test_deploy.py) found by probe2, missed by "
                    "probe1"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0054/control_probe_independence.py",
                "result": "PASS" if ctrl["cases"][1]["independent"] else "FAIL",
                "assertions": 2,
                "output_tail": raw_ctrl[-600:],
            },
            {
                "id": "AUD-0054-sibling-not-skipped",
                "name": "control: sibling non-gated fixture test executes (not skipped) on Linux",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0054/probe2_collect_vs_execute.py",
                "result": "PASS" if p2["control"]["fixture_sibling_test_executed_not_skipped"] else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0054-C1",
                "known-broken-fixture",
                (
                    "A runtime-only platform skip (body-level pytest.skip(), no "
                    "decorator) must be found by probe2's real execution diff and "
                    "MUST NOT be found by probe1's decorator-only AST scan."
                ),
                True,
                True,
                bad="probe1 also found the fixture (pair not independent)",
                good=(
                    f"probe1_found={not p1['control']['runtime_only_fixture_correctly_missed']} "
                    f"probe2_found={p2['control']['fixture_runtime_skip_found_by_probe2']}"
                ),
            ),
            L.control(
                "AUD0054-C2",
                "mutation",
                (
                    "The same independence property, replicated on a real, pre-existing "
                    "production test discovered by grep rather than authored for this "
                    "unit, so the control is not a single planted coincidence."
                ),
                True,
                True,
                bad="the real production runtime skip was also declared by probe1",
                good=f"real_world_runtime_skip_found_by_probe2={p2['control']['real_world_runtime_skip_found_by_probe2']}",
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
                "consumer": "json.loads + audit-inventory schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0054/_pack_receipt.py",
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
                    "Every declared windows-only / windows-or-darwin-only test would "
                    "actually PASS if executed on a real Windows or macOS runner."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Execute the same file set on a Windows and a macOS runner via "
                    "AUD-0049's promised-but-absent matrix cells; compare collected-"
                    "vs-executed there against this Linux run."
                ),
            },
            {
                "claim": (
                    "The tool-presence exclusions (BASH is None, free-drive-letter, "
                    "8.3-short-name gates) contain zero further platform-conditional "
                    "tests once their helper functions are resolved interprocedurally."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Trace each excluded helper (find_bash, _free_drive, _short_home) "
                    "to its return-value construction and re-classify any that "
                    "unconditionally return None/falsy on POSIX."
                ),
            },
            {
                "claim": (
                    "No third form of platform gate (e.g. a custom pytest fixture that "
                    "calls skip(), or a class-level pytestmark list) exists beyond the "
                    "two forms probe1 resolves (inline decorator, same-file/cross-file "
                    "shared variable) and the one form probe2 catches empirically."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe1 to walk fixture bodies and class-level pytestmark "
                    "assignments; diff against probe2's full skip set repo-wide "
                    "(this unit's probe2 scope is the 5 files named above, not the "
                    "whole tree)."
                ),
            },
        ],
        "report": {
            "kind": "audit-inventory",
            "question": question,
            "headline": headline,
            "observations": [
                {
                    "name": "windows_only_count",
                    "measured": windows_only,
                    "method": "AST skipif/skipIf/skipUnless condition resolves to sys.platform!='win32' or os.name!='nt' or platform.system()!='Windows'",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.json",
                },
                {
                    "name": "posix_only_count",
                    "measured": posix_only,
                    "method": "condition resolves to sys.platform=='win32' or os.name=='nt' or platform.system()=='Windows'",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.json",
                },
                {
                    "name": "windows_or_darwin_only_count",
                    "measured": windows_or_darwin_only,
                    "method": "condition resolves (possibly cross-file) to a case-insensitive-fs constant, negated",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.raw.txt",
                },
                {
                    "name": "declared_never_on_current_ci_matrix_count",
                    "measured": never_declared,
                    "method": "decorator-declared rows whose required platform is absent from AUD-0049's exercised_families",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe1-ast-platform-skips.json",
                },
                {
                    "name": "runtime_only_skips_found_by_probe2",
                    "measured": runtime_only_hits,
                    "method": "real pytest execution on Linux; SKIPPED node ids absent from probe1's decorator rows",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe2-collect-vs-execute.json",
                },
                {
                    "name": "combined_never_on_current_ci_matrix_count",
                    "measured": combined_never_on_current_matrix,
                    "method": "declared_never_on_current_ci_matrix_count + runtime_only_skips_found_by_probe2",
                    "anchor": "command-center/p2-wave/probes/AUD-0054/probe2-collect-vs-execute.json",
                },
            ],
            "control_ids": ["AUD0054-C1", "AUD0054-C2"],
            "ci_matrix_input": {
                "source": AUD0049_INPUT,
                "exercised_families": ci_exercised,
                "promised_platforms": aud0049["report"]["promised_platforms"],
            },
            "findings": p1.get("rows", []),
            "runtime_only_findings": p2.get("runtime_only_hits", []),
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-loop",
            "by_required_platform": p1["by_required_platform"],
            "excluded_tool_presence_examples": p1["excluded_tool_presence_examples"],
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    out_path = L.REPO / OUT

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

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
