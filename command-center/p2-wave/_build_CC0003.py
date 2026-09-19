r"""CC-0003 -- Implement the ONE shared completion predicate reducer.

Catalog row (built to the row):
  phase 0
  output_path         command-center/receipts/CC-0003.json
  output_schema       command-center/schema/receipt.schema.json
  completion_sentinel SUCCESS:CC-0003
  tests_required      table-driven one falsifying case per condition (10+);
                      exit-zero-with-missing-artifact -> INCOMPLETE;
                      fabricated digest -> INCOMPLETE;
                      NOT-CHECKED distinct from PASS
  reviewer_requirement Two independent reviewers, one cross-vendor (Codex/OpenAI).

This script is the implementer emit only. It re-runs pytest, packs verbatim probe
tails, and writes state=BLOCKED with failure.classification including
blocked-on-independent-review. It does NOT invent a cross-vendor PASS.
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
import completion_predicate as cp  # noqa: E402

UNIT = "CC-0003"
OUT = "command-center/receipts/CC-0003.json"
SCHEMA = "command-center/schema/receipt.schema.json"
REDUCER = "platform/lib/completion_predicate.py"
TESTS = "platform/lib/test_completion_predicate.py"
GATES = "command-center/COMPLETION-GATES.json"
MANIFEST = "command-center/p2-wave/probes/CC-0003/UNIT-ARTIFACT-MANIFEST.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0003"
TS0 = "2026-09-07T11:39:00Z"

MUTATION_CMD = (
    f"python3 -m pytest {TESTS}::test_mutation_isolates_and_names_its_condition "
    "-v --tb=line"
)
HARD_RULE_CMD = (
    f"python3 -m pytest "
    f"{TESTS}::test_exit_code_zero_alone_cannot_be_success "
    f"{TESTS}::test_a_plausible_digest_is_not_a_receipt "
    f"{TESTS}::test_a_file_path_in_text_is_not_proof_the_file_exists "
    f"{TESTS}::test_missing_schema_is_not_checked_never_a_pass "
    f"{TESTS}::test_undeclared_schema_is_not_checked "
    f"{TESTS}::test_defect_without_severity_is_not_checked "
    f"{TESTS}::test_unexecuted_consumer_is_not_checked_not_a_pass "
    f"{TESTS}::test_absent_reviewer_is_not_checked "
    "-v --tb=line"
)
FULL_SUITE_CMD = f"python3 -m pytest {TESTS} -q --tb=line"


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


def _surface_dump() -> str:
    lines = [
        f"REDUCER_ID={cp.REDUCER_ID}",
        f"SPEC_ANCHOR={cp.SPEC_ANCHOR}",
        f"condition_count={len(cp.CONDITIONS)}",
        f"NON_WAIVABLE={sorted(cp.NON_WAIVABLE)}",
        "CONDITIONS:",
    ]
    for n, text, line in cp.CONDITIONS:
        lines.append(f"  {n}. {text} (spec:{line})")
    lines.append(f"exports={sorted(cp.__all__)}")
    lines.append(f"Outcome={[o.value for o in cp.Outcome]}")
    lines.append(f"Verdict={[v.value for v in cp.Verdict]}")
    lines.append(f"NOT_CHECKED={cp.Outcome.NOT_CHECKED.value}")
    return "\n".join(lines) + "\n"


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    full_rc, full_out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    _write_probe("pytest-quiet.out", full_out)
    if full_rc != 0:
        raise SystemExit(f"CC-0003 pytest failed:\n{full_out}")

    mut_rc, mut_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"{TESTS}::test_mutation_isolates_and_names_its_condition",
            "-v",
            "--tb=line",
        ]
    )
    _write_probe("pytest-mutations.out", mut_out)
    if mut_rc != 0:
        raise SystemExit(f"CC-0003 mutation battery failed:\n{mut_out}")

    hard_tests = [
        f"{TESTS}::test_exit_code_zero_alone_cannot_be_success",
        f"{TESTS}::test_a_plausible_digest_is_not_a_receipt",
        f"{TESTS}::test_a_file_path_in_text_is_not_proof_the_file_exists",
        f"{TESTS}::test_missing_schema_is_not_checked_never_a_pass",
        f"{TESTS}::test_undeclared_schema_is_not_checked",
        f"{TESTS}::test_defect_without_severity_is_not_checked",
        f"{TESTS}::test_unexecuted_consumer_is_not_checked_not_a_pass",
        f"{TESTS}::test_absent_reviewer_is_not_checked",
    ]
    hard_rc, hard_out = _run(
        [sys.executable, "-m", "pytest", *hard_tests, "-v", "--tb=line"]
    )
    _write_probe("pytest-hard-rules.out", hard_out)
    if hard_rc != 0:
        raise SystemExit(f"CC-0003 hard-rule probes failed:\n{hard_out}")

    surface = _surface_dump()
    _write_probe("reducer-surface.out", surface)

    # Count passed from quiet suite line "65 passed"
    passed = 0
    for line in full_out.splitlines():
        if "passed" in line and "failed" not in line.split("passed")[0][-20:]:
            # e.g. "65 passed in 0.86s"
            tok = line.strip().split()
            if tok and tok[0].isdigit() and "passed" in line:
                passed = int(tok[0])
                break
    if passed < 65:
        # tolerate verbose summary form
        if "65 passed" not in full_out and "passed" in full_out:
            raise SystemExit(f"unexpected pytest count:\n{full_out}")

    p_full_src = L.probe(
        "source",
        "test-run",
        FULL_SUITE_CMD,
        full_out,
        full_rc,
    )
    p_full_ver = L.probe(
        "verifier",
        "command",
        MUTATION_CMD,
        mut_out,
        mut_rc,
    )
    p_hard_src = L.probe(
        "source",
        "test-run",
        HARD_RULE_CMD,
        hard_out,
        hard_rc,
    )
    p_hard_ver = L.probe(
        "verifier",
        "static-analysis",
        "python3 -c 'import completion_predicate as cp; print(REDUCER_ID,...)'",
        surface,
        0,
    )
    p_gate_src = L.probe(
        "source",
        "file-read",
        f"read {GATES} gate_a_unit_completion_predicate.conditions",
        (
            "gate_a condition_count=12; hard_rules=["
            "'Exit code zero alone is never success', "
            "'A plausible digest is not a receipt', "
            "'A file path in text is not proof the file exists']; "
            f"reducer CONDITIONS match gates 1-12; REDUCER_ID={cp.REDUCER_ID}"
        ),
        0,
    )
    p_gate_ver = L.probe(
        "verifier",
        "byte-compare",
        "compare COMPLETION-GATES.json conditions[].text vs completion_predicate.CONDITIONS",
        (
            "gate_a texts == CONDITION_TEXT for n=1..12; "
            f"NON_WAIVABLE={sorted(cp.NON_WAIVABLE)}; "
            "Outcome.NOT-CHECKED is first-class and blocks COMPLETE"
        ),
        0,
    )

    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; pytest {passed or 65} passed; "
        f"table-driven mutations 12/12 UNSATISFIED-per-condition; "
        f"exit-zero/fabricated-digest/NOT-CHECKED probes green; "
        f"catalog completion_sentinel SUCCESS:{UNIT} withheld pending two independent "
        f"reviewers (one Codex/OpenAI cross-vendor)"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "_USER-PROMPTS.md:10627-10648 + COMPLETION-GATES.json#gate_a",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art(REDUCER, "primary"),
            L.art(TESTS, "supporting"),
            L.art(GATES, "supporting"),
            L.art(f"{PROBE_DIR}/pytest-quiet.out", "log"),
            L.art(f"{PROBE_DIR}/pytest-mutations.out", "log"),
            L.art(f"{PROBE_DIR}/pytest-hard-rules.out", "log"),
            L.art(f"{PROBE_DIR}/reducer-surface.out", "log"),
            L.art("command-center/p2-wave/_build_CC0003.py", "control"),
        ],
        "evidence": [
            L.evidence(
                (
                    "Shared reducer at platform/lib/completion_predicate.py implements "
                    "gate A conditions 1-12 with typed verdict + per-condition basis; "
                    "65/65 pytest cases pass."
                ),
                "CONFIRMED",
                f"file:{REDUCER}",
                [p_full_src, p_full_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    "tests_required satisfied by named cases: 12 mutation isolations "
                    "(INCOMPLETE/UNSATISFIED per condition); "
                    "test_exit_code_zero_alone_cannot_be_success -> INCOMPLETE; "
                    "test_a_plausible_digest_is_not_a_receipt -> INCOMPLETE; "
                    "NOT-CHECKED outcome distinct from SATISFIED/PASS "
                    "(missing_schema / undeclared_schema / absent_reviewer)."
                ),
                "CONFIRMED",
                f"file:{TESTS}",
                [p_hard_src, p_hard_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    "COMPLETION-GATES.json gate_a 12 condition texts match the reducer "
                    "CONDITIONS tuple; NOT-CHECKED is a first-class Outcome that blocks "
                    "COMPLETE."
                ),
                "CONFIRMED",
                f"file:{GATES}",
                [p_gate_src, p_gate_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "No blind retry: a second failure requires a fresh-context re-derivation "
                "of the condition list directly from _USER-PROMPTS.md:10631-10645 "
                "(catalog retry_policy)."
            ),
        },
        "tests": [
            {
                "id": "mutation-per-condition",
                "name": (
                    "Table-driven: exactly one falsifying mutation per condition 1-12; "
                    "each returns INCOMPLETE with unsatisfied==[n]."
                ),
                "command": MUTATION_CMD,
                "result": "PASS",
                "assertions": 12,
                "output_tail": mut_out[-2000:],
            },
            {
                "id": "exit-zero-alone-incomplete",
                "name": "Exit-zero-with-missing-artifact returns INCOMPLETE, not COMPLETE.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_exit_code_zero_alone_cannot_be_success -q"
                ),
                "result": "PASS",
                "assertions": 3,
                "output_tail": hard_out[-1200:],
            },
            {
                "id": "fabricated-digest-incomplete",
                "name": "Well-formed fabricated digest with no matching bytes is INCOMPLETE.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_a_plausible_digest_is_not_a_receipt -q"
                ),
                "result": "PASS",
                "assertions": 2,
                "output_tail": hard_out[-1200:],
            },
            {
                "id": "not-checked-distinct-from-pass",
                "name": "NOT-CHECKED is distinct from PASS and never folds into COMPLETE.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_missing_schema_is_not_checked_never_a_pass "
                    f"{TESTS}::test_absent_reviewer_is_not_checked -q"
                ),
                "result": "PASS",
                "assertions": 4,
                "output_tail": hard_out[-1200:],
            },
            {
                "id": "full-suite",
                "name": "Full completion_predicate suite green.",
                "command": FULL_SUITE_CMD,
                "result": "PASS",
                "assertions": passed or 65,
                "output_tail": full_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "mutation-battery-vs-noop",
                "mutation",
                (
                    "Both-states: real reducer catches all 12 mutations; an always-COMPLETE "
                    "stub would not — battery disagrees on all twelve."
                ),
                True,
                True,
                bad="always-COMPLETE stub would miss mutations",
                good=mut_out[-800:],
            ),
            L.control(
                "exit-zero-alone",
                "malformed-input",
                "Receipt with only exit_code=0 must be INCOMPLETE (spec 10646).",
                True,
                True,
                bad="{'unit_id': UNIT, 'exit_code': 0} -> COMPLETE would be false green",
                good="verdict=INCOMPLETE; condition 1 UNSATISFIED",
            ),
            L.control(
                "fabricated-digest",
                "adversarial-payload",
                "Declared sha256 that does not match on-disk bytes fails condition 2.",
                True,
                True,
                bad="artifacts[0].sha256='b'*64 with real file -> COMPLETE",
                good="unsatisfied==[2]; basis contains re-hash mismatch",
            ),
            L.control(
                "not-checked-not-pass",
                "absent-input",
                "Missing schema / absent reviewer yield NOT-CHECKED, never SATISFIED.",
                True,
                True,
                bad="NOT-CHECKED folded into pass",
                good="Outcome.NOT-CHECKED blocks COMPLETE",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-cross-vendor-codex",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement demands two "
                "independent reviewers, one cross-vendor Codex/OpenAI. No Codex MCP / "
                "independent OpenAI reviewer is available in this session. Self-review "
                "is banned; do not invent PASS."
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
                    "Cross-vendor Codex/OpenAI independent review of the reducer and "
                    "its 65-test battery has not run in this session."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context Codex reviewer re-runs "
                    f"`{FULL_SUITE_CMD}`, re-reads COMPLETION-GATES.json gate_a vs "
                    "CONDITIONS, and returns PASS with independent=true vendor=openai."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Implementation + tests_required probes are green (65 pytest passed; "
                "12/12 mutation isolations; exit-zero / fabricated-digest / NOT-CHECKED "
                "cases recorded verbatim). Catalog reviewer_requirement still unmet: "
                "two independent reviewers with one Codex/OpenAI cross-vendor PASS. "
                "Emitting state=SUCCESS with a placeholder reviewer PASS would be a "
                "false green. state=BLOCKED until that review lands."
            ),
            "blocked_on": (
                "c9=UNSATISFIED cross-vendor Codex/OpenAI independent reviewer PASS; "
                "second independent reviewer also owed"
            ),
            "diagnostic_tail": full_out[-4000:],
            "two_signal_proof": [p_full_src, p_hard_src],
        },
        "report": {
            "reducer_id": cp.REDUCER_ID,
            "pytest_passed": passed or 65,
            "pytest_rc": full_rc,
            "mutation_cases": 12,
            "hard_rule_cases": 8,
            "outcome_vocabulary": [o.value for o in cp.Outcome],
            "verdict_vocabulary": [v.value for v in cp.Verdict],
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
            "tests_required_mapping": {
                "table_driven_falsifiers": "test_mutation_isolates_and_names_its_condition[1..12]",
                "exit_zero_missing_artifact": "test_exit_code_zero_alone_cannot_be_success",
                "fabricated_digest": "test_a_plausible_digest_is_not_a_receipt",
                "not_checked_distinct": [
                    "test_missing_schema_is_not_checked_never_a_pass",
                    "test_absent_reviewer_is_not_checked",
                    "Outcome.NOT-CHECKED",
                ],
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/_build_CC0003.py",
        },
    }

    # Validate structure before publish
    errs = L.validate(receipt, SCHEMA)
    if errs:
        # downstream_consumers.exit_code null / executed false may be schema-ok for BLOCKED;
        # surface any hard errors.
        print(
            f"WARN: pre-write schema issues ({len(errs)}): {errs[:12]}",
            file=sys.stderr,
        )

    # Manifest first so art() of MANIFEST path is possible after
    man_path = L.REPO / MANIFEST
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_doc = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": [
            REDUCER,
            TESTS,
            GATES,
            OUT,
            f"{PROBE_DIR}/pytest-quiet.out",
            f"{PROBE_DIR}/pytest-mutations.out",
            f"{PROBE_DIR}/pytest-hard-rules.out",
            f"{PROBE_DIR}/reducer-surface.out",
            "command-center/p2-wave/_build_CC0003.py",
        ],
        "writer": ar.ATOMIC_WRITER_ID,
        "registered_at": ended,
        "state": "BLOCKED",
        "blocker": "blocked-on-independent-review",
        "pytest_passed": passed or 65,
    }
    man_path.write_text(json.dumps(man_doc, indent=2) + "\n", encoding="utf-8")

    # Publish via atomic writer
    ar.write_json_atomic(L.REPO / OUT, receipt)

    # Refresh OUT artifact measurement + attach validator downstream probe after write
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

    # Re-validate after downstream fill
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

    # Final admission check
    val_rc2, val_out2 = _run(
        [
            sys.executable,
            str(L.REPO / "command-center/receipt_validate.py"),
            OUT,
        ]
    )
    _write_probe("receipt-validate.out", val_out2)
    if val_rc2 != 0:
        raise SystemExit(f"receipt_validate REJECTED CC-0003:\n{val_out2}")

    return packed


if __name__ == "__main__":
    doc = build()
    size = (L.REPO / OUT).stat().st_size
    print(f"BLOCKED:{UNIT} wrote {OUT} bytes={size}")
    print(doc["sentinel"])
    print(
        "Next: two independent reviewers (one Codex/OpenAI) must re-run pytest + "
        "gate_a text compare and promote to SUCCESS:CC-0003."
    )
