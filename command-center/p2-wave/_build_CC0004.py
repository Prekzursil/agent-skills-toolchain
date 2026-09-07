r"""CC-0004 -- Detect fan-in sites that compute completion locally.

Catalog row (built to the row):
  phase 0
  output_path         command-center/receipts/CC-0004.json
  output_schema       command-center/schema/receipt.schema.json
  completion_sentinel SUCCESS:CC-0004
  tests_required      planted local predicate reported with file:line;
                      legitimate import site found;
                      use-vs-mention: prose mentioning the fork must NOT be reported
  reviewer_requirement One independent reviewer who re-runs the planted-control
                      experiment themselves rather than reading the author's transcript.

This script is the implementer emit only. It re-runs pytest + planted/live scans,
packs verbatim probe tails, and writes state=BLOCKED with
blocked-on-independent-review. It does NOT invent a reviewer PASS.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

sys.path.insert(0, str(L.REPO / "command-center/p2-wave/probes/CC-0004"))
import fanin_detector as det  # noqa: E402

UNIT = "CC-0004"
OUT = "command-center/receipts/CC-0004.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0004"
DETECTOR = f"{PROBE_DIR}/fanin_detector.py"
TESTS = f"{PROBE_DIR}/test_fanin_detector.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
FIXTURES = f"{PROBE_DIR}/fixtures"
TS0 = "2026-09-07T18:30:00Z"

PYTEST_CMD = f"python3 -m pytest {TESTS} -v --tb=short"
CONTROL_CMD = (
    f"python3 {DETECTOR} {FIXTURES}/planted_local_predicate.py "
    f"{FIXTURES}/good_shared_import.py {FIXTURES}/prose_mention_fork.md"
)
LIVE_CMD = f"python3 {DETECTOR} --json"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _write_probe(name: str, text: str) -> Path:
    path = L.REPO / PROBE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pytest_rc, pytest_out = _run(
        [sys.executable, "-m", "pytest", TESTS, "-v", "--tb=short"]
    )
    _write_probe("pytest.out", pytest_out)
    if pytest_rc != 0:
        raise SystemExit(f"CC-0004 pytest failed:\n{pytest_out}")

    # Both-states planted control (fixtures only)
    control_report = det.scan_paths(
        [
            L.REPO / FIXTURES / "planted_local_predicate.py",
            L.REPO / FIXTURES / "good_shared_import.py",
            L.REPO / FIXTURES / "prose_mention_fork.md",
        ],
        repo=L.REPO,
    )
    control_rc, control_out = _run(
        [
            sys.executable,
            DETECTOR,
            f"{FIXTURES}/planted_local_predicate.py",
            f"{FIXTURES}/good_shared_import.py",
            f"{FIXTURES}/prose_mention_fork.md",
        ]
    )
    _write_probe("control-scan.raw.txt", control_out)
    _write_probe(
        "control-scan.json",
        json.dumps(control_report.to_dict(), indent=2, sort_keys=True) + "\n",
    )

    planted = [
        f
        for f in control_report.local_predicates
        if f.path.endswith("planted_local_predicate.py")
    ]
    if not planted:
        raise SystemExit("CC-0004 planted control did not fire")
    prose_hits = [
        f
        for f in control_report.local_predicates
        if f.path.endswith("prose_mention_fork.md")
    ]
    if prose_hits:
        raise SystemExit(f"CC-0004 use-vs-mention failure: {prose_hits}")
    if not control_report.shared_imports:
        raise SystemExit("CC-0004 known-present import site not found")

    # Live tree scan
    live_report = det.scan(repo=L.REPO)
    live_rc, live_out = _run([sys.executable, DETECTOR])
    _write_probe("live-scan.raw.txt", live_out)
    _write_probe(
        "live-scan.json",
        json.dumps(live_report.to_dict(), indent=2, sort_keys=True) + "\n",
    )

    # Clean-only both-states half: good+prose must be silent on forks
    clean = det.scan_paths(
        [
            L.REPO / FIXTURES / "good_shared_import.py",
            L.REPO / FIXTURES / "prose_mention_fork.md",
        ],
        repo=L.REPO,
    )
    if clean.local_predicates or not clean.shared_imports:
        raise SystemExit(f"CC-0004 clean-half control failed: {clean.to_dict()}")

    planted_file_lines = sorted({f.file_line for f in planted})
    live_locals = [
        f"{f.file_line} {f.symbol}" for f in live_report.local_predicates
    ]

    p_pytest_src = L.probe(
        "source",
        "test-run",
        PYTEST_CMD,
        pytest_out,
        pytest_rc,
    )
    p_control_src = L.probe(
        "source",
        "static-analysis",
        CONTROL_CMD,
        control_out,
        control_rc,
    )
    p_control_ver = L.probe(
        "verifier",
        "file-read",
        f"read {PROBE_DIR}/control-scan.json",
        json.dumps(
            {
                "planted_file_lines": planted_file_lines,
                "shared_import_count": len(control_report.shared_imports),
                "prose_reported": False,
                "skipped_non_python": control_report.skipped_non_python,
            },
            indent=2,
        ),
        0,
    )
    p_live_src = L.probe(
        "source",
        "static-analysis",
        LIVE_CMD,
        live_out[-12000:],
        live_rc,
    )
    p_live_ver = L.probe(
        "verifier",
        "byte-compare",
        f"summarize {PROBE_DIR}/live-scan.json",
        (
            f"files_scanned={live_report.files_scanned} "
            f"shared={len(live_report.shared_imports)} "
            f"local={len(live_report.local_predicates)}; "
            f"locals={live_locals}"
        ),
        0,
    )

    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; "
        f"pytest 5 passed; planted control fired at {planted_file_lines}; "
        f"legitimate import found; prose mention not reported; "
        f"live scan files={live_report.files_scanned} "
        f"shared={len(live_report.shared_imports)} "
        f"local_forks={len(live_report.local_predicates)}; "
        f"catalog completion_sentinel SUCCESS:{UNIT} withheld until an independent "
        f"reviewer re-runs the planted-control experiment"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": (
            "_USER-PROMPTS.md:10648 (same shared reducer everywhere) + "
            ":11314 (two completion predicates disagree) + WORK-UNIT-CATALOG#CC-0004"
        ),
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art(DETECTOR, "primary"),
            L.art(TESTS, "supporting"),
            L.art(f"{FIXTURES}/planted_local_predicate.py", "control"),
            L.art(f"{FIXTURES}/good_shared_import.py", "fixture"),
            L.art(f"{FIXTURES}/prose_mention_fork.md", "fixture"),
            L.art(f"{PROBE_DIR}/pytest.out", "log"),
            L.art(f"{PROBE_DIR}/control-scan.raw.txt", "log"),
            L.art(f"{PROBE_DIR}/control-scan.json", "supporting"),
            L.art(f"{PROBE_DIR}/live-scan.raw.txt", "log"),
            L.art(f"{PROBE_DIR}/live-scan.json", "supporting"),
            L.art("command-center/p2-wave/_build_CC0004.py", "control"),
            L.art("platform/lib/completion_predicate.py", "supporting"),
        ],
        "evidence": [
            L.evidence(
                (
                    "Planted local predicate control FIRES with file:line "
                    f"{planted_file_lines}; clean fixture set (good import + prose) "
                    "is SILENT on local_predicates and finds the shared import."
                ),
                "CONFIRMED",
                f"file:{FIXTURES}/planted_local_predicate.py",
                [p_control_src, p_control_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    "tests_required mapping: planted file:line reported; "
                    "legitimate import site found in fixtures/good_shared_import.py "
                    "and live platform/coordination/reducer.py; "
                    "prose_mention_fork.md is SKIP_PROSE / not in local_predicates."
                ),
                "CONFIRMED",
                f"file:{TESTS}",
                [p_pytest_src, p_control_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Live AST/import-graph scan over tools/, scripts/, command-center/, "
                    f"platform/coordination, platform/lib: files_scanned="
                    f"{live_report.files_scanned}, shared_imports="
                    f"{len(live_report.shared_imports)}, local_predicates="
                    f"{len(live_report.local_predicates)} "
                    f"(real forks include monitorcore dbx_completion and "
                    f"receipt_schema_gate.evaluate_gate_a)."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/live-scan.json",
                [p_live_src, p_live_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot from regex matching to AST/import-graph "
                "resolution; a third regex attempt is banned (catalog retry_policy)."
            ),
        },
        "tests": [
            {
                "id": "planted-local-predicate-file-line",
                "name": (
                    "Known-broken: planted local predicate reported with file:line."
                ),
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_planted_local_predicate_reported_with_file_line -v"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": pytest_out[-1500:],
            },
            {
                "id": "legitimate-shared-import-found",
                "name": "Known-present: legitimate single import site found.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_legitimate_shared_import_site_found -v"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": pytest_out[-1500:],
            },
            {
                "id": "use-vs-mention-prose-silent",
                "name": (
                    "Use-vs-mention: prose documenting the fork is NOT reported."
                ),
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_prose_mention_of_fork_is_not_reported -v"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": pytest_out[-1500:],
            },
            {
                "id": "both-states-control",
                "name": "Planted fires; good+prose clean set is silent.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_both_states_planted_fires_and_good_is_silent -v"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": control_out[-1200:],
            },
            {
                "id": "full-suite",
                "name": "Full CC-0004 detector suite green.",
                "command": PYTEST_CMD,
                "result": "PASS",
                "assertions": 5,
                "output_tail": pytest_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-local-predicate",
                "mutation",
                (
                    "Both-states: planted fixtures/planted_local_predicate.py must be "
                    "reported with file:line; clean good+prose set must have zero "
                    "local_predicates."
                ),
                True,
                True,
                bad=str(planted_file_lines),
                good=json.dumps(
                    {
                        "clean_local_predicates": [],
                        "clean_shared_imports": len(clean.shared_imports),
                        "ok_clean": clean.ok_clean,
                    }
                ),
            ),
            L.control(
                "use-vs-mention-prose",
                "adversarial-payload",
                (
                    "prose_mention_fork.md names evaluate/is_complete/COMPLETE in "
                    "markdown; detector must SKIP_PROSE and not emit local_predicate."
                ),
                True,
                True,
                bad="prose_mention_fork.md reported as local_predicate",
                good=f"skipped_non_python={control_report.skipped_non_python}",
            ),
            L.control(
                "known-present-import",
                "absent-input",
                (
                    "Matcher must find completion_predicate import on the good fixture "
                    "and on platform/coordination/reducer.py — otherwise 'zero forks' "
                    "is a silent matcher."
                ),
                True,
                True,
                bad="shared_imports=[]",
                good=(
                    f"fixture_shared={len(control_report.shared_imports)}; "
                    f"live_shared={len(live_report.shared_imports)}"
                ),
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-independent-planted-control-rerun",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement: one independent "
                "reviewer who re-runs the planted-control experiment themselves rather "
                "than reading this transcript. Self-review is banned; do not invent PASS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [],
        "residual_unknowns": [
            {
                "claim": (
                    "Independent reviewer has not re-run the planted-control experiment "
                    "in a fresh context."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer runs "
                    f"`{PYTEST_CMD}` and `{CONTROL_CMD}`, confirms planted file:line "
                    "fires, prose is silent, legitimate import is found, and returns "
                    "PASS with independent=true."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Detector + tests_required probes are green (5/5 pytest; planted "
                f"control fired at {planted_file_lines}; use-vs-mention silent; "
                "known-present import found; live scan recorded). Catalog "
                "reviewer_requirement still unmet: an independent reviewer must "
                "re-run the planted-control experiment. Emitting state=SUCCESS with "
                "a placeholder reviewer PASS would be a false green. "
                "state=BLOCKED until that review lands."
            ),
            "blocked_on": (
                "independent reviewer re-run of planted-control "
                f"({CONTROL_CMD})"
            ),
            "diagnostic_tail": control_out[-4000:],
            "two_signal_proof": [p_control_src, p_pytest_src],
        },
        "report": {
            "detector": DETECTOR,
            "shared_reducer": "platform/lib/completion_predicate.py",
            "pytest_passed": 5,
            "pytest_rc": pytest_rc,
            "planted_file_lines": planted_file_lines,
            "control": control_report.to_dict(),
            "live": {
                "files_scanned": live_report.files_scanned,
                "shared_import_count": len(live_report.shared_imports),
                "local_predicate_count": len(live_report.local_predicates),
                "local_predicates": [f.__dict__ for f in live_report.local_predicates],
                "shared_imports_sample": [
                    f.__dict__ for f in live_report.shared_imports[:12]
                ],
            },
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
            "tests_required_mapping": {
                "planted_file_line": "test_planted_local_predicate_reported_with_file_line",
                "legitimate_import": "test_legitimate_shared_import_site_found",
                "use_vs_mention": "test_prose_mention_of_fork_is_not_reported",
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/_build_CC0004.py",
        },
    }

    errs = L.validate(receipt, SCHEMA)
    if errs:
        print(
            f"WARN: pre-write schema issues ({len(errs)}): {errs[:12]}",
            file=sys.stderr,
        )

    man_path = L.REPO / MANIFEST
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_doc = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": [
            DETECTOR,
            TESTS,
            f"{FIXTURES}/planted_local_predicate.py",
            f"{FIXTURES}/good_shared_import.py",
            f"{FIXTURES}/prose_mention_fork.md",
            OUT,
            f"{PROBE_DIR}/pytest.out",
            f"{PROBE_DIR}/control-scan.raw.txt",
            f"{PROBE_DIR}/control-scan.json",
            f"{PROBE_DIR}/live-scan.raw.txt",
            f"{PROBE_DIR}/live-scan.json",
            "command-center/p2-wave/_build_CC0004.py",
        ],
        "writer": ar.ATOMIC_WRITER_ID,
        "registered_at": ended,
        "state": "BLOCKED",
        "blocker": "blocked-on-independent-review",
        "pytest_passed": 5,
        "planted_file_lines": planted_file_lines,
    }
    man_path.write_text(json.dumps(man_doc, indent=2) + "\n", encoding="utf-8")

    ar.write_json_atomic(L.REPO / OUT, receipt)

    val_rc, val_out = _run(
        [
            sys.executable,
            str(L.REPO / "command-center/receipt_validate.py"),
            OUT,
        ]
    )
    _write_probe("receipt-validate.out", val_out)

    receipt["artifacts"].append(L.art(OUT, "primary"))
    receipt["artifacts"].append(L.art(MANIFEST, "supporting"))
    receipt["downstream_consumers"] = [
        {
            "consumer": "receipt_validate.py admission of this receipt",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": val_rc == 0 and "ACCEPT:" in val_out,
            "exit_code": val_rc,
            "probe": L.probe(
                "verifier",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                val_out,
                val_rc,
            ),
        }
    ]

    errs2 = L.validate(receipt, SCHEMA)
    if errs2:
        print(
            f"WARN: post-fill schema issues ({len(errs2)}): {errs2[:12]}",
            file=sys.stderr,
        )

    ar.write_json_atomic(L.REPO / OUT, receipt)

    packed = ar.read_json(L.REPO / OUT)
    assert packed["unit_id"] == UNIT
    assert packed["state"] == "BLOCKED"
    assert "blocked-on-independent-review" in packed["failure"]["classification"]

    val_rc2, val_out2 = _run(
        [
            sys.executable,
            str(L.REPO / "command-center/receipt_validate.py"),
            OUT,
        ]
    )
    _write_probe("receipt-validate.out", val_out2)
    if val_rc2 != 0:
        raise SystemExit(f"receipt_validate REJECTED CC-0004:\n{val_out2}")

    return packed


if __name__ == "__main__":
    doc = build()
    size = (L.REPO / OUT).stat().st_size
    print(f"BLOCKED:{UNIT} wrote {OUT} bytes={size}")
    print(doc["sentinel"])
    print(
        "Next: independent reviewer must re-run planted-control pytest + "
        "fixture scan and promote to SUCCESS:CC-0004."
    )
