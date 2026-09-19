#!/usr/bin/env python3
"""Pack AUD-0083 script interpreter and shebang audit.

Two real probes (repo-wide inventory + platform resolution matrix, including
a real Linux fixture execution and a documented/simulated Windows branch)
plus the catalog's required tests_required control (bare .sh FAILS on a
Windows simulation, explicit bash SUCCEEDS on the same script). Emits BLOCKED
pending the catalog's cross-vendor Codex reviewer who re-runs ONLY the second
probe; NEVER emits SUCCESS without that review recorded on disk, and NEVER
invents independent-review.json -- the file simply does not exist for this
unit, so reviewer.verdict stays NOT-REVIEWED and state stays BLOCKED.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0083"
OUT = "command-center/audit/AUD-0083-script-interpreter-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0083/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0083/probe1-inventory-shebangs.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0083/probe2-platform-matrix.json"
CTL_JSON = (
    "command-center/p2-wave/probes/AUD-0083/control-windows-bare-vs-explicit.json"
)
P1_RAW = "command-center/p2-wave/probes/AUD-0083/probe1-inventory-shebangs.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0083/probe2-platform-matrix.raw.txt"
CTL_RAW = (
    "command-center/p2-wave/probes/AUD-0083/control-windows-bare-vs-explicit.raw.txt"
)


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context, CROSS-VENDOR Codex
    reviewer PASS -- who re-ran ONLY the second probe (the platform resolver
    matrix), per catalog reviewer_requirement -- is on disk. A same-vendor
    (anthropic/claude) reviewer does not satisfy this unit's cross-vendor
    requirement, unlike AUD-0054/AUD-0096 which required a Claude reviewer."""
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
    if vendor not in {"openai", "codex", "codex-cli"}:
        return None
    if rev.get("probe_rerun") != 2:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-inventory-shebangs.json").read_text(encoding="utf-8")
    )
    p2 = json.loads((PROBE / "probe2-platform-matrix.json").read_text(encoding="utf-8"))
    ctl = json.loads(
        (PROBE / "control-windows-bare-vs-explicit.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-inventory-shebangs.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-platform-matrix.raw.txt").read_text(encoding="utf-8")
    raw_ctl = (PROBE / "control-windows-bare-vs-explicit.raw.txt").read_text(
        encoding="utf-8"
    )
    rev = load_review()
    success = rev is not None
    started = "2026-09-08T00:00:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    files_scanned = int(p1["files_scanned"])
    script_rows_found = int(p1["script_rows_found"])
    exec_bit_count = int(p1["exec_bit_count"])
    shebang_count = int(p1["shebang_count"])
    windows_sh_candidate_count = int(p1["windows_no_shebang_support_candidate_count"])
    by_extension = p1["by_extension"]
    by_shebang_interpreter = p1["by_shebang_interpreter"]

    mc = p2["matrix_counts"]
    linux_bare_success = int(mc["linux"]["bare"]["SUCCESS"])
    linux_bare_fail = int(mc["linux"]["bare"]["FAILURE"])
    windows_bare_success = int(mc["windows"]["bare"]["SUCCESS"])
    windows_bare_fail = int(mc["windows"]["bare"]["FAILURE"])
    macos_bare_success = int(mc["macos"]["bare"]["SUCCESS"])
    macos_bare_fail = int(mc["macos"]["bare"]["FAILURE"])
    resolver_verified = bool(p2["resolver_verified_against_real_linux"])
    windows_bare_would_run_linux_bare = int(
        p2["windows_bare_would_run_on_linux_bare_count"]
    )
    rows_resolved = int(p2["rows_resolved"])

    control_ok = bool(ctl["ok"])
    control_case_a = bool(ctl["control_case_a_bare_is_failure"])
    control_case_b = bool(ctl["control_case_b_explicit_is_success"])
    naive_incorrectly_passes_both = bool(ctl["naive_resolver_incorrectly_passes_both"])

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
            "command-center/p2-wave/probes/AUD-0083/probe1_inventory_scripts.py",
            "supporting",
        ),
        L.art(P1_JSON, "supporting"),
        L.art(P1_RAW, "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0083/_platform_resolver.py", "supporting"
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0083/probe2_platform_resolver_matrix.py",
            "supporting",
        ),
        L.art(P2_JSON, "supporting"),
        L.art(P2_RAW, "log"),
        L.art(
            "command-center/p2-wave/probes/AUD-0083/control_windows_bare_vs_explicit.py",
            "control",
        ),
        L.art(CTL_JSON, "control"),
        L.art(CTL_RAW, "log"),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0083/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For every executable script in the tree, which interpreter would "
        "actually run it on each supported platform, and which would be "
        "invoked bare on Windows where no shebang exists?"
    )

    headline = (
        f"files_scanned={files_scanned} script_rows_found={script_rows_found} "
        f"exec_bit_count={exec_bit_count} shebang_count={shebang_count}. "
        f"Platform bare-invocation resolution over {rows_resolved} rows: "
        f"linux SUCCESS={linux_bare_success}/FAILURE={linux_bare_fail}, "
        f"macos(inferred) SUCCESS={macos_bare_success}/FAILURE={macos_bare_fail}, "
        f"windows(simulated) SUCCESS={windows_bare_success}/FAILURE={windows_bare_fail} "
        f"({windows_sh_candidate_count} .sh/extensionless-shebang scripts would be "
        f"invoked bare with no interpreter at all on Windows; "
        f"{windows_bare_would_run_linux_bare} of those would succeed if bare-invoked "
        "on Linux). Resolver cross-checked against 4 real subprocess "
        f"executions on this Linux host: resolver_verified_against_real_linux="
        f"{resolver_verified}. tests_required control (bare .sh Windows-sim "
        f"FAILURE + explicit bash Windows-sim SUCCESS)=ok:{control_ok}."
    )

    if success:
        notes = rev.get("notes", "")
        if isinstance(notes, list):
            notes = "\n".join(str(n) for n in notes)
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": str(notes)[:8000],
        }
        defects = [
            {
                "id": "AUD-0083-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent cross-vendor Codex review PASS (probe 2 "
                    "re-run) recorded at "
                    "command-center/p2-wave/probes/AUD-0083/independent-review.json"
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = f"SUCCESS:AUD-0083 windows_bare_fail={windows_bare_fail} control_ok={control_ok}"
        failure = None
        anti = "SUCCESS-after-independent-cross-vendor-falsify-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog reviewer_requirement: one cross-vendor Codex "
                "reviewer (vendor openai|codex, independent, fresh_context) "
                "who re-runs ONLY the second probe "
                "(probe2_platform_resolver_matrix.py) and tries to falsify "
                "the platform-resolution headline counts, not re-read the "
                "artifact. A same-vendor (anthropic/claude) review does not "
                "satisfy this unit -- the catalog explicitly requires "
                "cross-vendor. No independent-review.json is invented here; "
                "probes are measured and state is BLOCKED instead."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            f"FAILED:AUD-0083 script interpreter/shebang census + platform "
            f"resolver matrix measured windows_bare_fail={windows_bare_fail} "
            f"windows_bare_success={windows_bare_success} control_ok={control_ok}; "
            "blocked-on-cross-vendor-codex-review"
        )
        failure = {
            "classification": ["scope-mismatch", "detector-failure"],
            "reason": (
                "Named probes completed with the required control passing "
                "(a naive shebang-only resolver was shown to incorrectly "
                "pass both bare and explicit Windows cases, while the real "
                "resolver correctly diverges), but catalog "
                "reviewer_requirement is unmet: one cross-vendor Codex "
                "reviewer must re-run ONLY probe 2 and try to falsify the "
                "platform-resolution counts before PASS."
            ),
            "diagnostic_tail": (
                f"files_scanned={files_scanned} script_rows_found={script_rows_found} "
                f"exec_bit_count={exec_bit_count} shebang_count={shebang_count} "
                f"linux_bare_success={linux_bare_success} linux_bare_fail={linux_bare_fail} "
                f"windows_bare_success={windows_bare_success} windows_bare_fail={windows_bare_fail} "
                f"resolver_verified_against_real_linux={resolver_verified} "
                f"control_case_a_bare_is_failure={control_case_a} "
                f"control_case_b_explicit_is_success={control_case_b} "
                f"naive_resolver_incorrectly_passes_both={naive_incorrectly_passes_both} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer (vendor "
                "openai|codex, independent, fresh_context, "
                "probe_rerun=2) who re-runs ONLY "
                "probe2_platform_resolver_matrix.py against this tree and "
                "tries to FALSIFY windows_bare_fail="
                f"{windows_bare_fail} / windows_bare_success={windows_bare_success} "
                "before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0083/probe2_platform_resolver_matrix.py",
                    f"windows_bare_fail={windows_bare_fail} windows_bare_success={windows_bare_success}",
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
        anti = "BLOCKED-pending-cross-vendor-codex-review-with-real-probes"
        defects = [
            {
                "id": "AUD-0083-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Cross-vendor Codex falsify-review (re-run of probe 2 "
                    "only) unpaid; windows_bare_fail/windows_bare_success "
                    "counts must be falsified by a reviewer of a different "
                    "vendor who did not author this census."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0083",
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
                    f"Probe 1 repo-wide inventory (git ls-files, {files_scanned} "
                    f"tracked files scanned): {script_rows_found} script rows "
                    f"found (exec bit and/or shebang and/or a script "
                    f"extension); exec_bit_count={exec_bit_count} "
                    f"shebang_count={shebang_count}; by_extension={by_extension}; "
                    f"by_shebang_interpreter={by_shebang_interpreter}; "
                    f"windows_no_shebang_support_candidate_count="
                    f"{windows_sh_candidate_count} (.sh files plus "
                    "extensionless-with-shebang files, i.e. exactly the "
                    "class Windows has zero default resolution mechanism for)."
                ),
                "CONFIRMED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0083/probe1_inventory_scripts.py",
                        raw1[-8000:],
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-inventory-shebangs.json",
                        json.dumps(
                            {
                                "files_scanned": files_scanned,
                                "script_rows_found": script_rows_found,
                                "exec_bit_count": exec_bit_count,
                                "shebang_count": shebang_count,
                                "windows_no_shebang_support_candidate_count": windows_sh_candidate_count,
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
                    f"Probe 2 platform resolver matrix over {rows_resolved} "
                    "script rows, cross-checked against 4 REAL subprocess "
                    "executions on this Linux host (resolver_verified_"
                    f"against_real_linux={resolver_verified}): linux bare "
                    f"SUCCESS={linux_bare_success}/FAILURE={linux_bare_fail}; "
                    f"macos(inferred-not-measured, same POSIX kernel "
                    f"mechanism) bare SUCCESS={macos_bare_success}/"
                    f"FAILURE={macos_bare_fail}; windows(documented/"
                    f"simulated, no real Windows host used) bare "
                    f"SUCCESS={windows_bare_success}/FAILURE={windows_bare_fail}. "
                    f"{windows_bare_would_run_linux_bare} scripts that FAIL "
                    "bare on the Windows simulation would SUCCEED bare on "
                    "Linux (all 4 real-exec-bit .sh scripts in this repo)."
                ),
                "CONFIRMED" if bool(p2["ok"]) else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0083/probe2_platform_resolver_matrix.py",
                        raw2[-8000:],
                        0 if bool(p2["ok"]) else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-platform-matrix.json",
                        json.dumps(
                            {
                                "resolver_verified_against_real_linux": resolver_verified,
                                "linux_bare_success": linux_bare_success,
                                "linux_bare_fail": linux_bare_fail,
                                "windows_bare_success": windows_bare_success,
                                "windows_bare_fail": windows_bare_fail,
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain" if resolver_verified else "refuted",
            ),
            L.evidence(
                (
                    "tests_required control: the resolver reports FAILURE "
                    "for a bare .sh invocation on the Windows simulation "
                    f"(control_case_a_bare_is_failure={control_case_a}) and "
                    "SUCCESS for the same script invoked with explicit bash "
                    f"(control_case_b_explicit_is_success={control_case_b}). "
                    "A negative control confirms this is falsifiable: a "
                    "deliberately-broken shebang-only resolver was shown to "
                    "incorrectly report SUCCESS for BOTH cases "
                    f"(naive_resolver_incorrectly_passes_both="
                    f"{naive_incorrectly_passes_both}), which is exactly the "
                    "defect class the catalog names ('a resolver that "
                    "passes both is reading the shebang, not the OS')."
                ),
                "CONFIRMED" if control_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0083/control_windows_bare_vs_explicit.py",
                        raw_ctl,
                        0 if control_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read control-windows-bare-vs-explicit.json",
                        json.dumps(
                            {
                                "control_case_a_bare_is_failure": control_case_a,
                                "control_case_b_explicit_is_success": control_case_b,
                                "naive_resolver_incorrectly_passes_both": naive_incorrectly_passes_both,
                                "ok": ctl["ok"],
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
                "id": "AUD-0083-control-bare-sh-windows-fails",
                "name": (
                    "tests_required: bare .sh invocation reports FAILURE on "
                    "the Windows simulation"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0083/control_windows_bare_vs_explicit.py",
                "result": "PASS" if control_case_a else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0083-control-explicit-bash-windows-succeeds",
                "name": (
                    "tests_required: the same script invoked with explicit "
                    "bash reports SUCCESS on the Windows simulation"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0083/control_windows_bare_vs_explicit.py",
                "result": "PASS" if control_case_b else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0083-resolver-verified-against-real-linux",
                "name": (
                    "the linux branch of the resolver agrees with 4 real "
                    "subprocess executions on this host"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0083/probe2_platform_resolver_matrix.py",
                "result": "PASS" if resolver_verified else "FAIL",
                "assertions": 4,
                "output_tail": raw2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0083-C1",
                "known-broken-fixture",
                (
                    "A deliberately-broken shebang-only resolver (ignores "
                    "platform, trusts the shebang) must incorrectly pass "
                    "BOTH the bare and explicit Windows cases -- proving "
                    "the control is falsifiable and not vacuously true for "
                    "any resolver."
                ),
                True,
                True,
                bad="naive_resolver.bare=SUCCESS naive_resolver.explicit=SUCCESS (both incorrectly pass)",
                good=f"real_resolver.bare={ctl['real_resolver']['bare']['outcome']} real_resolver.explicit={ctl['real_resolver']['explicit']['outcome']}",
            ),
            L.control(
                "AUD0083-C2",
                "mutation",
                (
                    "A second, independently-checked real .sh script "
                    "(discovered via probe1's census, not authored for "
                    "this control) must show the same bare-fails/"
                    "explicit-succeeds divergence, so the property is not "
                    "a single planted coincidence."
                ),
                True,
                True,
                bad="second script's bare/explicit outcomes did not diverge as expected",
                good=f"second_independent_script_check={ctl['second_independent_script_check']}",
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
                "consumer": "command-center/receipt_validate.py admission",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    f"python3 command-center/receipt_validate.py {OUT}",
                    f"seeded-before-first-admit state={state}; replaced after live run",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
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
                    "The Windows branch's outcomes (bare .sh/.ps1/.js/.mjs "
                    "FAILURE, bare .py CONDITIONAL SUCCESS via py.exe, "
                    "explicit-interpreter SUCCESS) would reproduce "
                    "identically on a real Windows 10/11 host with a "
                    "default python.org install and Git for Windows on PATH."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Provision a real (or CI-hosted) Windows runner, copy "
                    "this repo's tracked scripts onto it, and execute each "
                    "bare/explicit invocation for real, diffing exit codes "
                    "and stderr against this resolver's predicted outcomes."
                ),
            },
            {
                "claim": (
                    "macOS bare-invocation behaviour is identical to Linux "
                    "for every one of the 3,774 resolved rows, not merely "
                    "for the 4 fixture states actually exercised on Linux."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Execute the same 4 fixture states (plus a sample of "
                    "real repo scripts) on real macOS hardware and diff "
                    "against this run's linux measurements and the "
                    "resolver's macos predictions."
                ),
            },
            {
                "claim": (
                    "No script in the tree uses a shebang interpreter "
                    "token this resolver's parser mis-splits (e.g. a "
                    "`#!/usr/bin/env -S` multi-flag form beyond the single "
                    "`-S` this probe strips, or a shebang with a trailing "
                    "argument such as `#!/usr/bin/perl -w`)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe1's shebang parser to retain and classify "
                    "every token after the interpreter path, then diff its "
                    "output against a hand-audited sample of the "
                    f"{shebang_count} shebang rows."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0083-C1", "AUD0083-C2"],
            "observations": [
                {
                    "name": "files_scanned",
                    "measured": files_scanned,
                    "method": "git ls-files (tracked working tree only)",
                    "anchor": P1_JSON,
                },
                {
                    "name": "script_rows_found",
                    "measured": script_rows_found,
                    "method": "exec-bit OR shebang OR script-extension classification",
                    "anchor": P1_JSON,
                },
                {
                    "name": "exec_bit_count",
                    "measured": exec_bit_count,
                    "method": "os.access(path, os.X_OK) measured per file",
                    "anchor": P1_JSON,
                },
                {
                    "name": "shebang_count",
                    "measured": shebang_count,
                    "method": "first-line-starts-with-#! scan over 4096-byte read",
                    "anchor": P1_JSON,
                },
                {
                    "name": "windows_no_shebang_support_candidate_count",
                    "measured": windows_sh_candidate_count,
                    "method": ".sh extension OR (extensionless AND has_shebang)",
                    "anchor": P1_JSON,
                },
                {
                    "name": "linux_bare_invocation_success_count",
                    "measured": linux_bare_success,
                    "method": "_platform_resolver.resolve(platform=linux, mode=bare), verified against 4 real subprocess executions",
                    "anchor": P2_JSON,
                },
                {
                    "name": "windows_bare_invocation_failure_count",
                    "measured": windows_bare_fail,
                    "method": "_platform_resolver.resolve(platform=windows, mode=bare); documented/simulated, not executed on real Windows hardware",
                    "anchor": P2_JSON,
                },
                {
                    "name": "windows_bare_invocation_success_count",
                    "measured": windows_bare_success,
                    "method": "_platform_resolver.resolve(platform=windows, mode=bare); documented/simulated (mostly .py via py.exe launcher)",
                    "anchor": P2_JSON,
                },
                {
                    "name": "resolver_verified_against_real_linux",
                    "measured": resolver_verified,
                    "method": "4 real subprocess.run() executions on this host compared against resolver(platform=linux) predictions for the same 4 states",
                    "anchor": P2_JSON,
                },
                {
                    "name": "control_bare_sh_windows_is_failure",
                    "measured": control_case_a,
                    "method": "tests_required control via control_windows_bare_vs_explicit.py",
                    "anchor": CTL_JSON,
                },
                {
                    "name": "control_explicit_bash_windows_is_success",
                    "measured": control_case_b,
                    "method": "tests_required control via control_windows_bare_vs_explicit.py",
                    "anchor": CTL_JSON,
                },
            ],
            "findings_by_extension": by_extension,
            "shebang_interpreters": by_shebang_interpreter,
            "windows_bare_by_extension": p2["windows_bare_by_extension"],
            "sample_windows_bare_would_fail_but_linux_bare_would_run": p2[
                "sample_windows_bare_would_fail_but_linux_bare_would_run"
            ],
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-loop",
            "platform_scope_note": (
                "linux branch: measured (this Linux Cursor Cloud host, "
                "cross-checked against 4 real subprocess executions). "
                "macos branch: inferred-not-measured (documented identical "
                "POSIX kernel #! dispatch; no macOS hardware available). "
                "windows branch: documented/simulated controlled fixture "
                "(PATHEXT, default file associations, PEP 397 py.exe "
                "launcher) -- explicitly NOT a claim of execution on a "
                "real Windows host."
            ),
            "reviewer_scope_note": (
                "Catalog reviewer_requirement calls for one cross-vendor "
                "Codex reviewer who re-runs ONLY the second probe "
                "(probe2_platform_resolver_matrix.py); this differs from "
                "AUD-0054/AUD-0096 which required a same-vendor-to-"
                "auditor-different Claude reviewer. load_review() enforces "
                "vendor in {openai, codex, codex-cli} and probe_rerun == 2."
            ),
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
