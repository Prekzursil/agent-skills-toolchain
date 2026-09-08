#!/usr/bin/env python3
"""Pack IMP-0437 — field-completeness CI arm as honest BLOCKED receipt.

Catalog reviewer_requirement: independent-claude-reviewer reproduces both the
before and after exit codes. Never invent SUCCESS. Never invent
independent-review.json.

Linux Cloud / single-checkout scope disclosed in reviewer.notes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "IMP-0437"
OUT = "command-center/receipts/IMP-0437.json"
SCHEMA = "command-center/schema/receipt.schema.json"
ALSO = ["command-center/schema/receipt.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/IMP-0437"
VALIDATE = "tools/command-center/validate.py"
WORKFLOW = ".github/workflows/quality.yml"
TESTS = "tools/command-center/tests/test_validate.py"
MEASURE = f"{PROBE_DIR}/measure_mutations.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T02:10:00Z"


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


def load_review() -> dict | None:
    """Promote only when independent review reproduces before/after exit codes."""
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
    # Must claim reproduction of both exit codes.
    if not rev.get("reproduced_before_after_exit_codes"):
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            TESTS,
            "tools/command-center/tests/test_catalog_overrides.py",
            "-q",
            "--tb=line",
        ]
    )
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"IMP-0437 pytest failed:\n{out}")

    m_rc, m_out = _run([sys.executable, "-B", str(L.REPO / MEASURE)])
    (L.REPO / PROBE_DIR / "measure.out").write_text(m_out, encoding="utf-8")
    if m_rc != 0:
        raise SystemExit(f"IMP-0437 measure_mutations failed:\n{m_out}")

    mutation = json.loads(
        (L.REPO / PROBE_DIR / "mutation-exit-codes.json").read_text(encoding="utf-8")
    )
    if not mutation.get("ok"):
        raise SystemExit(f"IMP-0437 mutation report ok=false:\n{mutation}")

    v_rc, v_out = _run(
        [sys.executable, str(L.REPO / VALIDATE), "--require-complete"]
    )
    (L.REPO / PROBE_DIR / "validate.out").write_text(v_out, encoding="utf-8")
    if v_rc != 0:
        raise SystemExit(f"IMP-0437 live validate --require-complete failed:\n{v_out}")

    rev = load_review()
    success = rev is not None

    del_m = mutation["mutations"]["defaults_block_deleted"]
    one_m = mutation["mutations"]["single_default_field_deleted"]
    vf_m = mutation["mutations"]["blank_completion_sentinel_v_fields"]

    p_pytest = L.probe(
        "source",
        "test-run",
        f"python3 -m pytest {TESTS} tools/command-center/tests/test_catalog_overrides.py -q --tb=line",
        out,
        rc,
    )
    p_meas = L.probe(
        "verifier", "command", f"python3 -B {MEASURE}", m_out, m_rc
    )
    p_val = L.probe(
        "source",
        "command",
        f"python3 {VALIDATE} --require-complete",
        v_out,
        v_rc,
    )

    before_d = del_m["before_exit_code"]
    after_d = del_m["after_exit_code"]
    before_s = one_m["before_exit_code"]
    after_s = one_m["after_exit_code"]
    before_vf = vf_m["before_exit_code"]
    after_vf = vf_m["after_exit_code"]

    if success:
        state = "SUCCESS"
        sentinel = "SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "independent-claude-reviewer"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-exit-code-reproduction"
        downstream = [
            {
                "consumer": "ci.validate.require_complete",
                "artifact_path": f"{PROBE_DIR}/mutation-exit-codes.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            }
        ]
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"defaults_deletion before={before_d} after={after_d}; "
            f"single_field before={before_s} after={after_s}; "
            f"v_fields soft={before_vf} armed={after_vf}; "
            f"ci=validate.py --require-complete; "
            f"IMP-0436 V-DEFAULTS already made defaults-deletion soft-path "
            f"nonzero (catalog before=0 REFUTED on tip); "
            f"SUCCESS:{UNIT} withheld pending independent-claude-reviewer "
            f"reproduction of before/after exit codes; "
            f"SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED withheld"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-claude-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux Cloud single-checkout. Catalog "
                "reviewer_requirement unmet: independent-claude-reviewer must "
                "reproduce both before and after exit codes for the "
                "defaults-block-deleted mutation (and the single-field control) "
                "from the same command line. Self-review banned; "
                "independent-review.json not invented; SUCCESS not invented. "
                f"Measured on tip: defaults soft/before={before_d} "
                f"CI-armed/after={after_d}; single soft={before_s} "
                f"armed={after_s}; V-FIELDS blank soft={before_vf} "
                f"armed={after_vf} (soft silent proves the arm). Honesty: "
                "IMP-0436 always-on V-DEFAULTS already makes soft-path "
                "defaults deletion exit nonzero — catalog claim of before=0 "
                "is REFUTED on this tip; recorded verbatim. Scope: Prompt-One "
                "Windows trees unmounted."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent Claude reviewer has not reproduced the "
                    "before/after exit codes on a fresh context."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context independent-claude-reviewer re-runs "
                    f"{MEASURE} (or equivalent scratch mutations) and confirms "
                    f"defaults before={before_d}/after={after_d}, single "
                    f"before={before_s}/after={after_s}, V-FIELDS "
                    f"soft={before_vf}/armed={after_vf}; writes "
                    f"{PROBE_DIR}/independent-review.json with "
                    "verdict=PASS, independent=true, fresh_context=true, "
                    "reproduced_before_after_exit_codes=true; then re-pack may "
                    "emit SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "CI arm + CLI default-on + pytest + mutation both-states are "
                f"green (pytest rc={rc}; measure ok; live validate "
                f"--require-complete rc={v_rc}; defaults {before_d}->{after_d}; "
                f"single {before_s}->{after_s}; V-FIELDS {before_vf}->{after_vf}). "
                "Catalog reviewer_requirement demands independent reproduction "
                "of before/after exit codes; do not emit SUCCESS without that."
            ),
            "blocked_on": "independent-claude-reviewer (before/after exit codes)",
            "diagnostic_tail": (out + "\n" + m_out + "\n" + v_out)[-4000:],
            "two_signal_proof": [p_pytest, p_meas],
        }
        anti = "BLOCKED-pending-independent-exit-code-reproduction"
        downstream = [
            {
                "consumer": "ci.validate.require_complete",
                "artifact_path": WORKFLOW,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            },
            {
                "consumer": "validate.V-FIELDS",
                "artifact_path": f"{PROBE_DIR}/mutation-exit-codes.json",
                "executed": True,
                "read_ok": True,
                "exit_code": after_vf,
                "probe": p_meas,
            },
            {
                "consumer": "validate.V-DEFAULTS",
                "artifact_path": f"{PROBE_DIR}/mutation-exit-codes.json",
                "executed": True,
                "read_ok": True,
                "exit_code": after_d,
                "probe": p_meas,
            },
            {
                "consumer": "cc-validate-live-require-complete",
                "artifact_path": f"{PROBE_DIR}/validate.out",
                "executed": True,
                "read_ok": True,
                "exit_code": v_rc,
                "probe": p_val,
            },
        ]

    arts = [
        L.art(VALIDATE, "primary"),
        L.art(WORKFLOW, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/mutation-exit-codes.json", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/measure.out", "log"),
        L.art(f"{PROBE_DIR}/validate.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(MEASURE, "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0437",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "tooling-implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Armed field-completeness: validate.py require_complete "
                    "defaults True (CLI BooleanOptionalAction + library "
                    "default); quality.yml invokes "
                    "`python tools/command-center/validate.py --require-complete`. "
                    f"Defaults-block deletion: soft/before exit={before_d}, "
                    f"CI-armed/after exit={after_d} (both nonzero on tip because "
                    "IMP-0436 V-DEFAULTS is always-on; catalog before=0 REFUTED)."
                ),
                "CONFIRMED",
                f"file:{VALIDATE}",
                [p_meas, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Single-field control: delete defaults.timeout_seconds → "
                    f"soft/before exit={before_s}, CI-armed/after exit={after_s}; "
                    "both fire V-DEFAULTS (gate red)."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/mutation-exit-codes.json",
                [p_meas, p_val],
                "almost-certain",
            ),
            L.evidence(
                (
                    "V-FIELDS arm proof (remaining silence hole): blank "
                    f"R-M01.completion_sentinel soft/before exit={before_vf} "
                    f"(silent), CI-armed/after exit={after_vf} (V-FIELDS); "
                    f"bare CLI default also exits {vf_m.get('bare_exit_code')}."
                ),
                "CONFIRMED",
                f"file:{WORKFLOW}",
                [p_meas, p_pytest],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; exit-code disputes require a fresh "
                "independent Claude reviewer, not a third implementer attempt."
            ),
        },
        "tests": [
            {
                "id": "defaults-block-deletion-ci-red",
                "name": "Defaults-block deletion exits nonzero under CI command.",
                "command": (
                    f"python3 -B {MEASURE}  # defaults_block_deleted after_exit_code"
                ),
                "result": "PASS" if after_d != 0 else "FAIL",
                "assertions": 2,
                "output_tail": (
                    f"before={before_d} after={after_d}\n" + m_out[-600:]
                ),
            },
            {
                "id": "single-field-deletion-ci-red",
                "name": "Deleting one default field also fails the gate.",
                "command": (
                    f"python3 -B {MEASURE}  # single_default_field_deleted"
                ),
                "result": "PASS" if after_s != 0 else "FAIL",
                "assertions": 2,
                "output_tail": f"before={before_s} after={after_s}\n" + m_out[-600:],
            },
            {
                "id": "v-fields-soft-silent-armed-red",
                "name": "Blank field silent under soft; red under --require-complete.",
                "command": (
                    f"python3 -B {MEASURE}  # blank_completion_sentinel_v_fields"
                ),
                "result": "PASS"
                if before_vf == 0 and after_vf != 0
                else "FAIL",
                "assertions": 3,
                "output_tail": (
                    f"soft={before_vf} armed={after_vf} "
                    f"bare={vf_m.get('bare_exit_code')}\n" + m_out[-600:]
                ),
            },
            {
                "id": "ci-workflow-require-complete",
                "name": "quality.yml passes --require-complete to validate.py.",
                "command": (
                    "python3 -m pytest "
                    f"{TESTS}::test_ci_workflow_passes_require_complete -q"
                ),
                "result": "PASS"
                if mutation["workflow"]["require_complete_flag_present"]
                else "FAIL",
                "assertions": 1,
                "output_tail": out[-600:],
            },
            {
                "id": "pytest-validate-suite",
                "name": "test_validate.py + test_catalog_overrides.py pass.",
                "command": (
                    f"python3 -m pytest {TESTS} "
                    "tools/command-center/tests/test_catalog_overrides.py -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 1,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "defaults-block-deleted-ci-red",
                "mutation",
                "Deleting catalog.defaults under CI --require-complete must exit nonzero.",
                True,
                True,
                bad=del_m["after_ci_require_complete"].get("failed_line", ""),
                good=f"before_soft_exit={before_d} after_armed_exit={after_d}",
            ),
            L.control(
                "single-default-field-deleted-ci-red",
                "mutation",
                "Deleting defaults.timeout_seconds under CI must exit nonzero.",
                True,
                True,
                bad=one_m["after_ci_require_complete"].get("failed_line", ""),
                good=f"before_soft_exit={before_s} after_armed_exit={after_s}",
            ),
            L.control(
                "v-fields-soft-silent-armed-fires",
                "mutation",
                "Blank completion_sentinel silent under --no-require-complete; fires under armed CI.",
                True,
                True,
                bad=vf_m["after_ci_require_complete"].get("failed_line", ""),
                good=f"soft_exit={before_vf} (silent); armed_exit={after_vf}",
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "kind": "field-completeness-ci-arm",
            "observations": [
                {
                    "name": "defaults_deletion_exit_codes",
                    "measured": {"before": before_d, "after": after_d},
                    "method": (
                        "scratch catalog del defaults; soft=--no-require-complete; "
                        "armed=--require-complete (CI line)"
                    ),
                    "anchor": f"{PROBE_DIR}/mutation-exit-codes.json",
                },
                {
                    "name": "single_field_deletion_exit_codes",
                    "measured": {"before": before_s, "after": after_s},
                    "method": "scratch del defaults.timeout_seconds",
                    "anchor": f"{PROBE_DIR}/mutation-exit-codes.json",
                },
                {
                    "name": "v_fields_arm_both_states",
                    "measured": {
                        "soft_before": before_vf,
                        "armed_after": after_vf,
                        "bare_cli": vf_m.get("bare_exit_code"),
                    },
                    "method": "blank R-M01.completion_sentinel",
                    "anchor": f"{PROBE_DIR}/mutation-exit-codes.json",
                },
                {
                    "name": "imp_0436_honesty",
                    "measured": mutation["honesty"],
                    "method": "recorded verbatim; no invented before=0 run",
                    "anchor": "tools/command-center/validate.py#V-DEFAULTS",
                },
            ],
            "control_ids": [
                "defaults-block-deletion-ci-red",
                "single-field-deletion-ci-red",
                "v-fields-soft-silent-armed-red",
                "ci-workflow-require-complete",
            ],
            "reviewer_requirement": {
                "required": "independent-claude-reviewer",
                "must_reproduce": ["before_exit_code", "after_exit_code"],
                "independent_review_present": REVIEW.is_file(),
                "reviews_loaded": 1 if rev else 0,
            },
            "scope": {
                "execution_substrate": "linux-cloud-agent",
                "checkout": "single",
                "ci_command": mutation["ci_invocation"],
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": True,
            "catalog_completion_sentinel": "SENTINEL:IMP-0437:FIELD-COMPLETENESS-ARMED",
            "exit_codes": {
                "defaults_block_deleted": {
                    "before": before_d,
                    "after": after_d,
                },
                "single_default_field_deleted": {
                    "before": before_s,
                    "after": after_s,
                },
                "blank_completion_sentinel": {
                    "before_soft": before_vf,
                    "after_armed": after_vf,
                    "bare_cli": vf_m.get("bare_exit_code"),
                },
            },
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    VALIDATE,
                    WORKFLOW,
                    TESTS,
                    f"{PROBE_DIR}/mutation-exit-codes.json",
                    MEASURE,
                ],
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "independent-claude-reviewer reproduces both the before "
                    "and after exit codes"
                ),
                "exit_codes": {
                    "defaults_before": before_d,
                    "defaults_after": after_d,
                    "single_before": before_s,
                    "single_after": after_s,
                    "vfields_soft": before_vf,
                    "vfields_armed": after_vf,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc2 != 0:
        raise SystemExit(rc2)

    v_rc2, v_out2 = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out2, encoding="utf-8")
    if v_rc2 != 0 or "ACCEPT" not in v_out2:
        raise SystemExit(f"receipt_validate rejected:\n{v_out2}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(
        f"defaults {before_d}->{after_d}; single {before_s}->{after_s}; "
        f"vfields {before_vf}->{after_vf}; independent_review={REVIEW.is_file()}"
    )
    return receipt


if __name__ == "__main__":
    build()
