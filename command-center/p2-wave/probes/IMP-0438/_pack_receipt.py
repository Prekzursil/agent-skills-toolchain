#!/usr/bin/env python3
"""Pack IMP-0438 — validate.py mutation battery as honest BLOCKED receipt.

Catalog reviewer_requirement: adversarial refuter designs a seventeenth
mutation the battery has never seen. Never invent SUCCESS. Never invent
adversarial-review.json / independent-review.json.

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

UNIT = "IMP-0438"
OUT = "command-center/receipts/IMP-0438.json"
SCHEMA = "command-center/schema/receipt.schema.json"
ALSO = ["command-center/schema/mutation-report.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/IMP-0438"
VALIDATE = "tools/command-center/validate.py"
TESTS_VALIDATE = "tools/command-center/tests/test_validate.py"
TESTS_BATTERY = f"{PROBE_DIR}/test_battery.py"
BATTERY = f"{PROBE_DIR}/battery.py"
MEASURE = f"{PROBE_DIR}/measure_battery.py"
TABLE = f"{PROBE_DIR}/sixteen-row-table.json"
SUMMARY = f"{PROBE_DIR}/battery-summary.json"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "adversarial-review.json"
KNOWN_IDS = {f"M{i:02d}" for i in range(1, 18)}  # M01..M17 excluded from "novel"
TS0 = "2026-09-08T02:24:00Z"
SENTINEL_OK = "SENTINEL:IMP-0438:MUTATION-BATTERY-COMPLETE"


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


def load_adversarial_review() -> dict | None:
    """Promote only when an adversarial refuter plants a novel 17th mutation.

    Required fields:
      - verdict in {PASS, FAIL} (FAIL = novel mutant survived; documented honestly)
      - independent=true, fresh_context=true
      - novel_mutation.id not in M01..M17 / battery MUTATIONS
      - novel_mutation.caught is bool
    SUCCESS path requires verdict=PASS and caught=true.
    A documented FAIL (caught=false) must NOT invent SUCCESS.
    """
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    novel = rev.get("novel_mutation") or rev.get("seventeenth_mutation") or {}
    mid = str(novel.get("id") or "")
    if not mid or mid in KNOWN_IDS:
        return None
    if "caught" not in novel:
        return None
    if rev.get("verdict") == "PASS" and novel.get("caught") is True:
        return rev
    # Honest FAIL documentation is loadable but does not promote SUCCESS.
    if rev.get("verdict") == "FAIL" and novel.get("caught") is False:
        rev["_honest_fail"] = True
        return rev
    return None


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    dep = json.loads(
        (L.REPO / "command-center/receipts/IMP-0437.json").read_text(encoding="utf-8")
    )
    if dep.get("state") != "SUCCESS":
        raise SystemExit(
            f"IMP-0438 refuses pack: IMP-0437 state={dep.get('state')!r} (need SUCCESS)"
        )

    rc, out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            TESTS_VALIDATE,
            TESTS_BATTERY,
            "-q",
            "--tb=line",
        ]
    )
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"IMP-0438 pytest failed:\n{out}")

    m_rc, m_out = _run([sys.executable, "-B", str(L.REPO / MEASURE)])
    (L.REPO / PROBE_DIR / "measure.out").write_text(m_out, encoding="utf-8")
    if m_rc != 0:
        raise SystemExit(f"IMP-0438 measure_battery failed:\n{m_out}")

    summary = json.loads((L.REPO / SUMMARY).read_text(encoding="utf-8"))
    table = json.loads((L.REPO / TABLE).read_text(encoding="utf-8"))
    if not summary.get("ok"):
        raise SystemExit(f"IMP-0438 battery summary ok=false:\n{summary}")

    v_rc, v_out = _run([sys.executable, str(L.REPO / VALIDATE)])
    (L.REPO / PROBE_DIR / "validate.out").write_text(v_out, encoding="utf-8")
    if v_rc != 0:
        raise SystemExit(f"IMP-0438 live validate failed:\n{v_out}")

    rev = load_adversarial_review()
    honest_fail = bool(rev and rev.get("_honest_fail"))
    success = bool(rev) and not honest_fail and rev.get("verdict") == "PASS"

    closed = summary["surviving_mutation_closed"]
    armed_n = summary["armed_caught"]
    m16_armed = closed["tip_armed_exit"]
    m16_soft = closed["tip_disarmed_exit"]

    p_pytest = L.probe(
        "source",
        "test-run",
        f"python3 -m pytest {TESTS_VALIDATE} {TESTS_BATTERY} -q --tb=line",
        out,
        rc,
    )
    p_meas = L.probe(
        "verifier", "command", f"python3 -B {MEASURE}", m_out, m_rc
    )
    p_val = L.probe(
        "source", "command", f"python3 {VALIDATE}", v_out, v_rc
    )

    if success:
        state = "SUCCESS"
        sentinel = SENTINEL_OK
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "adversarial-refuter"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-adversarial-novel-17th-caught"
        novel = rev.get("novel_mutation") or rev.get("seventeenth_mutation") or {}
        downstream = [
            {
                "consumer": "validate.mutation-battery",
                "artifact_path": TABLE,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            },
            {
                "consumer": "adversarial.novel-17th",
                "artifact_path": f"{PROBE_DIR}/adversarial-review.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0 if novel.get("caught") else 1,
                "probe": p_meas,
            },
        ]
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-adversarial-17th-mutation-review; "
            f"battery={armed_n}/16 caught; historical_survivor=M16 closed "
            f"(armed_exit={m16_armed} disarmed_exit={m16_soft} via V-DEFAULTS); "
            f"known_M17_control_caught={summary['known_expansion_control_m17']['armed_caught']}; "
            f"SUCCESS:{UNIT} withheld pending adversarial refuter novel mutation "
            f"the battery has never seen; {SENTINEL_OK} withheld"
        )
        if honest_fail:
            novel = rev.get("novel_mutation") or {}
            reviewer_notes = (
                "Adversarial review present with honest FAIL: novel mutation "
                f"{novel.get('id')!r} SURVIVED the battery. Catalog retry_policy: "
                "expand the battery rather than declaring done. SUCCESS not invented. "
                f"Implementer notes: Linux Cloud single-checkout; tip battery "
                f"{armed_n}/16; M16 closed (armed={m16_armed}, soft={m16_soft})."
            )
            residual = [
                {
                    "claim": (
                        f"Novel mutation {novel.get('id')} survived; battery must expand."
                    ),
                    "verdict": "REFUTED",
                    "settling_experiment": (
                        "Expand MUTATIONS with the novel mutant as a named row, "
                        "close the unprotected check in validate.py, re-run measure, "
                        "then request a fresh adversarial 17th on the expanded set."
                    ),
                }
            ]
            failure = {
                "classification": ["mutation-survives", "battery-incomplete"],
                "reason": (
                    "Adversarial novel 17th mutation survived. Do not emit SUCCESS; "
                    "expand the battery per catalog retry_policy."
                ),
                "blocked_on": "adversarial-novel-17th-survivor",
                "diagnostic_tail": (m_out + "\n" + json.dumps(novel)[:2000])[-4000:],
                "two_signal_proof": [p_meas, p_pytest],
            }
            anti = "BLOCKED-honest-FAIL-novel-17th-survived"
        else:
            reviewer_notes = (
                "Implementer emit only on Linux Cloud single-checkout. Catalog "
                "reviewer_requirement unmet: adversarial refuter must design a "
                "seventeenth mutation the battery has never seen (id not in "
                "M01..M17), run it against the live battery, and write "
                f"{PROBE_DIR}/adversarial-review.json with independent=true, "
                "fresh_context=true, novel_mutation={{id,caught,...}}, and "
                "verdict=PASS only if caught (or verdict=FAIL with caught=false "
                "documented honestly — still not SUCCESS). Self-review banned; "
                "adversarial-review.json not invented; SUCCESS not invented. "
                f"Measured: armed battery {armed_n}/16; historical survivor M16 "
                f"closed (armed exit={m16_armed}, disarmed exit={m16_soft} via "
                "IMP-0436 V-DEFAULTS — tip cannot reproduce historical exit 0). "
                "Known expansion control M17 (delete defaults.timeout_seconds) is "
                "caught but does not satisfy the adversarial gate. Scope: "
                "Prompt-One Windows trees unmounted."
            )
            residual = [
                {
                    "claim": (
                        "Adversarial refuter has not planted a novel seventeenth "
                        "mutation the battery has never seen."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Fresh-context adversarial refuter designs a mutant absent "
                        f"from {BATTERY} MUTATIONS/M17, measures caught vs survived "
                        f"via python3 -B {BATTERY} (or equivalent), writes "
                        f"{PROBE_DIR}/adversarial-review.json; then re-pack may emit "
                        f"{SENTINEL_OK} only if caught=true and verdict=PASS."
                    ),
                }
            ]
            failure = {
                "classification": ["blocked-on-adversarial-review"],
                "reason": (
                    f"Battery + pytest + live validate are green ({armed_n}/16; "
                    f"pytest rc={rc}; validate rc={v_rc}; M16 closed "
                    f"armed={m16_armed}/soft={m16_soft}). Catalog "
                    "reviewer_requirement demands an adversarial novel 17th "
                    "mutation; do not emit SUCCESS without that."
                ),
                "blocked_on": "adversarial-refuter (novel 17th mutation)",
                "diagnostic_tail": (out + "\n" + m_out + "\n" + v_out)[-4000:],
                "two_signal_proof": [p_pytest, p_meas],
            }
            anti = "BLOCKED-pending-adversarial-novel-17th"

        reviewer = {
            "reviewer_id": "awaiting-adversarial-refuter",
            "verdict": "NOT-REVIEWED" if not honest_fail else "FAIL",
            "independent": False if not honest_fail else True,
            "fresh_context": False if not honest_fail else True,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": reviewer_notes[:4000],
        }
        downstream = [
            {
                "consumer": "validate.mutation-battery",
                "artifact_path": TABLE,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_meas,
            },
            {
                "consumer": "validate.V-DEFAULTS",
                "artifact_path": SUMMARY,
                "executed": True,
                "read_ok": True,
                "exit_code": m16_soft,
                "probe": p_meas,
            },
            {
                "consumer": "cc-validate-live",
                "artifact_path": f"{PROBE_DIR}/validate.out",
                "executed": True,
                "read_ok": True,
                "exit_code": v_rc,
                "probe": p_val,
            },
            {
                "consumer": "battery.control-M01",
                "artifact_path": TABLE,
                "executed": True,
                "read_ok": True,
                "exit_code": 1,
                "probe": p_meas,
            },
        ]

    arts = [
        L.art(VALIDATE, "primary"),
        L.art(BATTERY, "primary"),
        L.art(TESTS_VALIDATE, "supporting"),
        L.art(TESTS_BATTERY, "supporting"),
        L.art(TABLE, "log"),
        L.art(SUMMARY, "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/measure.out", "log"),
        L.art(f"{PROBE_DIR}/validate.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(MEASURE, "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/adversarial-review.json", "supporting"))

    m16_row = next(r for r in table["rows"] if r["id"] == "M16")

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0438",
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
                    "Sixteen-row mutation battery under bare CI: "
                    f"{armed_n}/16 caught; CONTROL exit 0; control mutation M01 "
                    "still caught with REACH-1 attribution. Historical survivor "
                    "M16 (delete-entire-defaults-block) named before the fix and "
                    f"closed on tip (armed exit={m16_armed})."
                ),
                "CONFIRMED",
                f"file:{TABLE}",
                [p_meas, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "M16 unprotected behavior (historical): V-FIELDS silent under "
                    "bare CI when require_complete defaulted False. Tip honesty: "
                    f"disarmed exit={m16_soft} via always-on V-DEFAULTS (IMP-0436); "
                    "historical exit-0-when-disarmed is REFUTED and not invented."
                ),
                "CONFIRMED",
                f"file:{SUMMARY}",
                [p_meas, p_val],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Adversarial 17th-mutation review gate is open: known M17 "
                    "expansion control is caught but does not satisfy "
                    "reviewer_requirement; SUCCESS withheld."
                ),
                "NOT-CHECKED" if not success else "CONFIRMED",
                f"file:{PROBE_DIR}/_pack_receipt.py",
                [p_meas],
                "likely",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "max 2 attempts; if the seventeenth mutation also survives, expand "
                "the battery rather than declaring done"
            ),
        },
        "tests": [
            {
                "id": "battery-16-of-16-armed",
                "name": "Armed bare-CI battery catches all sixteen mutations.",
                "command": f"python3 -B {MEASURE}",
                "result": "PASS" if armed_n == 16 else "FAIL",
                "assertions": 2,
                "output_tail": m_out[-800:],
            },
            {
                "id": "control-m01-still-caught",
                "name": "Known-caught control mutation M01 remains caught after the fix.",
                "command": f"python3 -m pytest {TESTS_BATTERY}::test_control_mutation_m01_still_caught -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": out[-600:],
            },
            {
                "id": "m16-historical-survivor-closed",
                "name": "Historical survivor M16 exits nonzero under armed CI.",
                "command": f"python3 -B {MEASURE}  # M16 post_fix",
                "result": "PASS" if m16_armed != 0 else "FAIL",
                "assertions": 2,
                "output_tail": (
                    f"armed={m16_armed} disarmed={m16_soft}\n"
                    + json.dumps(m16_row.get("honesty", {}))[:400]
                ),
            },
            {
                "id": "pytest-validate-and-battery",
                "name": "test_validate.py + IMP-0438 test_battery.py pass.",
                "command": (
                    f"python3 -m pytest {TESTS_VALIDATE} {TESTS_BATTERY} -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 1,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "m01-dangling-dep-caught",
                "mutation",
                "Control mutation M01 (dangling dependency) must stay red.",
                True,
                True,
                bad="REACH-1 on R-DOES-NOT-EXIST",
                good="CONTROL exit 0 on unmutated slim catalog",
            ),
            L.control(
                "m16-defaults-deleted-caught",
                "mutation",
                "Historical survivor M16 must exit nonzero under armed CI.",
                True,
                True,
                bad=f"armed exit={m16_armed}",
                good=f"CONTROL exit={summary['control_exit_armed']}",
            ),
            L.control(
                "m16-disarmed-also-caught-v-defaults",
                "mutation",
                "On tip, M16 is caught even under --no-require-complete via V-DEFAULTS.",
                True,
                True,
                bad=f"disarmed exit={m16_soft} (V-DEFAULTS)",
                good="historical exit 0 REFUTED; not invented",
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
            "kind": "mutation-report",
            "observations": [
                {
                    "name": "sixteen_row_table",
                    "measured": (
                        f"rows=16 armed_caught={armed_n} "
                        f"armed_survivors={summary['armed_survivors']} "
                        f"disarmed_survivors={summary['disarmed_survivors']}"
                    ),
                    "method": f"python3 -B {MEASURE}",
                    "anchor": TABLE,
                },
                {
                    "name": "surviving_mutation_m16",
                    "measured": (
                        f"M16 historical=SURVIVES tip_armed={closed['tip_armed_post_fix']} "
                        f"exit_armed={closed['tip_armed_exit']} "
                        f"exit_disarmed={closed['tip_disarmed_exit']}"
                    ),
                    "method": "named before fix; tip re-measure armed+disarmed",
                    "anchor": SUMMARY,
                },
                {
                    "name": "adversarial_17th_gate",
                    "measured": (
                        f"status={summary['adversarial_17th_slot']['status']} "
                        f"reserved_for={summary['adversarial_17th_slot']['reserved_for']}"
                    ),
                    "method": "review gate; adversarial-review.json not invented",
                    "anchor": f"{PROBE_DIR}/_pack_receipt.py",
                },
            ],
            "control_ids": [
                "m01-dangling-dep-caught",
                "m16-defaults-deleted-caught",
                "m16-disarmed-also-caught-v-defaults",
            ],
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": True,
            "catalog_completion_sentinel": SENTINEL_OK,
            "battery_size": 16,
            "surviving_mutations_closed": ["M16"],
            "sixteen_row_table_path": TABLE,
            "known_expansion_control_m17": summary["known_expansion_control_m17"],
            "reviewer_requirement": {
                "required": "adversarial-refuter",
                "must_design": "novel seventeenth mutation absent from M01..M17",
                "adversarial_review_present": REVIEW.is_file(),
                "reviews_loaded": 1 if rev else 0,
            },
            "scope": {
                "execution_substrate": "linux-cloud-agent",
                "checkout": "single",
                "ci_invocation": "python tools/command-center/validate.py",
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
                    BATTERY,
                    TABLE,
                    SUMMARY,
                    MEASURE,
                    TESTS_BATTERY,
                ],
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "adversarial refuter designs a seventeenth mutation the "
                    "battery has never seen"
                ),
                "battery": {
                    "size": 16,
                    "armed_caught": armed_n,
                    "m16_armed_exit": m16_armed,
                    "m16_disarmed_exit": m16_soft,
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
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(
        v_out2, encoding="utf-8"
    )
    if v_rc2 != 0 or "ACCEPT" not in v_out2:
        raise SystemExit(f"receipt_validate rejected:\n{v_out2}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(
        f"battery {armed_n}/16; M16 armed={m16_armed} soft={m16_soft}; "
        f"adversarial_review={REVIEW.is_file()}; success_invented=False"
    )
    return receipt


if __name__ == "__main__":
    build()
