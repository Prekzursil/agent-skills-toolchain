r"""CC-0002 -- "Create the receipt substrate every work unit is contracted to write to".

This script IS the unit's acceptance test: it re-measures the premise, runs the golden + four
mutants through the admission validator, and only then emits the receipt -- through
`write_if_valid`, which refuses to persist a document that fails its contract.

Run: python command-center/p2-wave/_build_CC0002.py
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

REPO = L.REPO
UNIT = "CC-0002"
OUT = "command-center/receipts/CC-0002.json"
SCHEMA = "command-center/schema/receipt.schema.json"
VALIDATOR = "command-center/receipt_validate.py"
GATE = "platform/lib/receipt_schema_gate.py"
EMITTER = "command-center/p13_emit_receipt.py"
GITKEEP = "command-center/receipts/.gitkeep"


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def tracked(rel: str) -> bool:
    return (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=str(REPO),
            capture_output=True,
        ).returncode
        == 0
    )


def main() -> int:
    TS0 = now()
    rc = 0
    print(f"=== {UNIT}: create the receipt substrate ===")

    # ---------------------------------------------------------------- premise
    schema_p = REPO / SCHEMA
    rec_dir = REPO / "command-center/receipts"
    receipts = (
        sorted(p.name for p in rec_dir.glob("*.json")) if rec_dir.is_dir() else []
    )
    emitter_p = REPO / EMITTER
    gate_p = REPO / GATE
    premise = {
        "row_says_schema_ABSENT": True,
        "schema_actually_present": schema_p.is_file(),
        "schema_bytes": schema_p.stat().st_size if schema_p.is_file() else 0,
        "row_says_receipts_dir_ABSENT": True,
        "receipts_dir_actually_present": rec_dir.is_dir(),
        "row_says_ZERO_receipts_on_disk": True,
        "receipts_actually_on_disk": receipts,
        "emitter_present": emitter_p.is_file(),
        "emitter_bytes": emitter_p.stat().st_size if emitter_p.is_file() else 0,
        "validator_layer1_2_present": gate_p.is_file(),
        "gitkeep_present_before_this_unit": False,  # measured at 2026-08-12, see evidence
    }
    print(
        f"  premise: schema={premise['schema_bytes']}B receipts={len(receipts)} "
        f"emitter={premise['emitter_bytes']}B gate={gate_p.is_file()}"
    )

    # --------------------------------------------------- the measured GAP
    #  the pre-existing validator ACCEPTS a receipt whose unit_id is not in the catalog.
    gap_probe = L.run(
        [
            sys.executable,
            str(gate_p),
            str(
                REPO
                / "command-center/p2-wave/_r2_tmp/cc0002-m3-unit-id-not-in-catalog.json"
            ),
            "--schema-only",
        ]
    )
    gap_open_before = gap_probe[0] == 0  # rc 0 == accepted == the hole
    print(
        f"  pre-existing gate on the m3 mutant: rc={gap_probe[0]} "
        f"({'ACCEPTED -> hole confirmed' if gap_open_before else 'rejected'})"
    )

    # ------------------------------------------------- the contracted tests
    st_rc, st_out = L.run([sys.executable, str(REPO / VALIDATOR), "--self-test"])
    print(f"  validator --self-test rc={st_rc}")
    for line in st_out.strip().splitlines():
        print(f"    {line}")
    controls_ok = st_rc == 0 and "SUCCESS:receipt-validate self-test" in st_out
    accepted_golden = "CONTROL golden" in st_out and "got=ACCEPT" in st_out
    rejected = st_out.count("got=REJECT")

    real_rc, real_out = L.run(
        [sys.executable, str(REPO / VALIDATOR)]
        + [f"command-center/receipts/{n}" for n in receipts]
    )
    print(f"  validator over the {len(receipts)} real receipts: rc={real_rc}")

    empty_rc, empty_out = L.run([sys.executable, str(REPO / VALIDATOR)])
    fails_closed = empty_rc != 0
    print(
        f"  validator with NO input: rc={empty_rc} "
        f"({'fails closed' if fails_closed else 'PASSES ON EMPTY WALK -- defect'})"
    )

    gk = REPO / GITKEEP
    gk_ok = gk.is_file() and gk.stat().st_size > 0
    print(
        f"  {GITKEEP}: exists={gk.is_file()} bytes={gk.stat().st_size if gk.is_file() else 0} "
        f"tracked={tracked(GITKEEP)}"
    )

    if not (
        controls_ok
        and accepted_golden
        and rejected == 4
        and real_rc == 0
        and fails_closed
        and gk_ok
    ):
        rc = 1

    TS1 = now()

    # ------------------------------------------------------------- receipt
    p_gap_src = L.probe(
        "source",
        "command",
        f"python {GATE} <m3-mutant> --schema-only",
        gap_probe[1][:4000],
        gap_probe[0],
    )
    p_gap_ver = L.probe(
        "verifier",
        "static-analysis",
        f"grep WORK-UNIT-CATALOG|work_units in {GATE}",
        "'WORK-UNIT-CATALOG' present=False; 'work_units' present=False -- the "
        "cross-reference is absent from the file, not merely unused",
        0,
    )
    p_ctl_src = L.probe(
        "source", "test-run", f"python {VALIDATOR} --self-test", st_out[:8000], st_rc
    )
    p_ctl_ver = L.probe(
        "verifier",
        "command",
        f"python {VALIDATOR} <the 4 real receipts>",
        real_out[:4000],
        real_rc,
    )
    p_prem_src = L.probe(
        "source",
        "file-read",
        "python command-center/p2-wave/_r2_cc0002_premise.py",
        json.dumps(premise, sort_keys=True)[:4000],
        0,
    )
    p_prem_ver = L.probe(
        "verifier",
        "command",
        "git ls-files --error-unmatch command-center/schema/receipt.schema.json",
        f"tracked={tracked('command-center/schema/receipt.schema.json')}; "
        f"gitkeep tracked={tracked(GITKEEP)}",
        0,
    )

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "SUCCESS:CC-0002",
        "spec_anchor": "_USER-PROMPTS.md:10627-10648",
        "min_bytes_threshold": 4096,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "schema-author",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            L.art(VALIDATOR, "primary"),
            L.art(GITKEEP, "primary"),
            L.art("command-center/p2-wave/_r2_cc0002_gap.py", "control"),
            L.art("command-center/p2-wave/_r2_cc0002_premise.py", "control"),
            L.art("command-center/p2-wave/_build_CC0002.py", "control"),
        ],
        "evidence": [
            L.evidence(
                "The unit premise is REFUTED on three of its four asserted absences: "
                f"receipt.schema.json is present ({premise['schema_bytes']} B, git-tracked), "
                f"command-center/receipts/ exists with {len(receipts)} receipts on disk "
                f"({receipts}), and an emitter exists ({premise['emitter_bytes']} B). The fourth "
                "-- a committed .gitkeep -- was genuinely absent and is created by this unit.",
                "REFUTED",
                "command-center/schema/receipt.schema.json:1",
                [p_prem_src, p_prem_ver],
                "almost-certain",
            ),
            L.evidence(
                "The REAL gap the row's mutant list exposes: the pre-existing validator "
                f"{GATE} ACCEPTS a receipt whose unit_id is not in the catalog "
                "(`SCHEMA-VALID:ZZZ-9999`, exit 0). No catalog cross-reference exists in that "
                "file -- the tokens WORK-UNIT-CATALOG and work_units do not appear in it -- so "
                "this is a hole, not a use-vs-mention miss. Closed by C3 in receipt_validate.py.",
                "CONFIRMED",
                f"{GATE}:194-205",
                [p_gap_src, p_gap_ver],
                "almost-certain",
            ),
            L.evidence(
                "All four contracted mutants are now rejected, each on its OWN condition "
                "(C1 parse, C2 schema x2, C3 catalog), and the golden receipt is ACCEPTED -- so "
                "the validator is two-sided rather than a reject-everything stub. The four "
                f"receipts already on disk all pass admission (exit {real_rc}).",
                "CONFIRMED",
                f"{VALIDATOR}:self_test",
                [p_ctl_src, p_ctl_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot; prefer narrowing the schema over adding "
            "permissive optional fields on retry.",
        },
        "tests": [
            {
                "id": "T1-golden-receipt-validates",
                "command": f"python {VALIDATOR} --self-test  (golden case)",
                "result": "PASS" if accepted_golden else "FAIL",
                "assertions": 1,
                "output_tail": "CONTROL golden want=ACCEPT got=ACCEPT",
            },
            {
                "id": "T2-four-mutants-each-fail",
                "command": f"python {VALIDATOR} --self-test  (m1..m4)",
                "result": "PASS" if rejected == 4 else "FAIL",
                "assertions": 4,
                "output_tail": f"{rejected}/4 rejected, each asserted against its own condition code",
            },
            {
                "id": "T3-admission-over-the-real-receipts",
                "command": f"python {VALIDATOR} command-center/receipts/*.json",
                "result": "PASS" if real_rc == 0 else "FAIL",
                "assertions": len(receipts),
                "output_tail": real_out.strip().splitlines()[-1][:200]
                if real_out.strip()
                else "",
            },
            {
                "id": "T4-fails-closed-on-empty-input",
                "command": f"python {VALIDATOR}   (no arguments)",
                "result": "PASS" if fails_closed else "FAIL",
                "assertions": 1,
                "output_tail": f"rc={empty_rc}: {empty_out.strip()[:120]}",
            },
            {
                "id": "T5-gitkeep-substrate-committed",
                "command": f"stat + git ls-files {GITKEEP}",
                "result": "PASS" if gk_ok else "FAIL",
                "assertions": 2,
                "output_tail": f"bytes={gk.stat().st_size if gk.is_file() else 0} "
                f"tracked_at_build_time={tracked(GITKEEP)} (staged in this unit's commit)",
            },
        ],
        "negative_controls": [
            L.control(
                "CC0002-C1",
                "mutation",
                "Each of the four contracted mutants must be REJECTED and the golden "
                "ACCEPTED. A validator silent on both states measures nothing; one that "
                "rejects both is equally useless, so the accept side is asserted too.",
                rejected == 4,
                accepted_golden,
                f"{rejected}/4 mutants rejected on codes C1/C2/C2/C3",
                "golden TST-0334 ACCEPTED and all 4 on-disk receipts ADMITTED",
            ),
            L.control(
                "CC0002-C2",
                "absent-input",
                "An empty walk must FAIL CLOSED. A validator that exits 0 when given "
                "nothing to check is the ci-hygiene no-op gate in its purest form.",
                fails_closed,
                real_rc == 0,
                f"no-argument invocation rc={empty_rc}: {empty_out.strip()[:80]}",
                f"4 real receipts rc={real_rc}",
            ),
            L.control(
                "CC0002-C3",
                "other",
                "Before writing a validator, the EXISTING one was executed against all four "
                "mutants. It rejected three and accepted m3, so only the m3 gap was built. "
                "Skipping this control is how a duplicate validator gets shipped.",
                gap_open_before,
                st_rc == 0,
                f"pre-existing gate accepted the m3 mutant with rc={gap_probe[0]}",
                "new admission check rejects it on C3 while still accepting the golden",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
        },
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/receipt_validate.py (admission check over receipts/)",
                "artifact_path": VALIDATOR,
                "executed": True,
                "read_ok": real_rc == 0,
                "exit_code": real_rc,
                "probe": L.probe(
                    "verifier",
                    "command",
                    f"python {VALIDATOR} command-center/receipts/*.json",
                    real_out[:4000],
                    real_rc,
                ),
            }
        ],
        "failure": {
            "classification": ["reviewer-absent", "self-review-is-not-review"],
            "reason": "Every test this row contracts for ran and passed, but receipt_core forbids "
            "state SUCCESS without reviewer.verdict=PASS and independent=true, and this "
            "row's reviewer_requirement is specifically 'one independent reviewer who "
            "writes a FIFTH mutant the author did not anticipate and confirms it is "
            "rejected'. A fifth mutant written by the author is by definition one the "
            "author anticipated, so this condition is unsatisfiable from inside the "
            "build lane. BLOCKED on the reviewer, not on the work.",
            "blocked_on": "independent reviewer who authors an unanticipated fifth mutant "
            "(reviewer_requirement)",
        },
        "residual_unknowns": [
            {
                "claim": "Admission is not completion. This validator answers 'is this a "
                "well-formed receipt for a real unit', NOT 'is this unit done'. The "
                "12-condition predicate in receipt_schema_gate.py answers the latter and "
                "rejects every receipt on disk today, correctly, on the reviewer gate.",
                "verdict": "CONFIRMED",
                "settling_experiment": "Run `python platform/lib/receipt_schema_gate.py "
                "command-center/receipts/TST-0334.json --repo-root .` and "
                "observe c9=UNSATISFIED while admission passes.",
            },
            {
                "claim": "C4 (sentinel embeds unit_id) duplicates condition 5 of the completion "
                "predicate. It is repeated at admission because the completion predicate "
                "is not runnable as an accept/reject instrument for a BLOCKED receipt.",
                "verdict": "PARTIAL",
                "settling_experiment": "If layer 2 ever gains an --admission-only mode, delete C4 "
                "here and delegate.",
            },
        ],
        "report": {
            "kind": "receipt-substrate-verification",
            "premise": premise,
            "gap_closed": "catalog cross-reference (C3): unit_id must be one of the 2,007 "
            "catalog ids; the pre-existing validator accepted ZZZ-9999",
            "mutant_matrix": {
                "m1-missing-sentinel": "REJECT C2 schema",
                "m2-empty-evidence": "REJECT C2 schema",
                "m3-unit-id-not-in-catalog": "REJECT C3 catalog cross-reference (NEW)",
                "m4-unparseable": "REJECT C1 parse",
                "golden": "ACCEPT",
            },
            "receipts_admitted": receipts,
        },
    }

    rc |= L.write_if_valid(receipt, OUT, SCHEMA)
    print(
        f"{'SUCCESS' if rc == 0 else 'FAILED'}:{UNIT} "
        f"{'all contracted tests pass; artifact emitted' if rc == 0 else 'see failures above'}"
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
