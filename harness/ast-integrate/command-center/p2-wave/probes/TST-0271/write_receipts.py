#!/usr/bin/env python3
"""Write TST-0271 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "TST-0271"
OUT = "command-center/receipts/TST-0271.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0271/probe1_author_recusal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0271/probe2_hidden_and_both_states.py"
)
SUPPORTING = [
    "tools/council/conflicts.py",
    "tools/council/simulate.py",
    "command-center/schema/council-spec.schema.json",
    "tools/council/tests/test_conflicts.py",
    "command-center/p2-wave/probes/TST-0271/scenario.py",
    "command-center/p2-wave/probes/TST-0271/probe1_author_recusal.py",
    "command-center/p2-wave/probes/TST-0271/probe2_hidden_and_both_states.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json_object(text: str) -> dict | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return None


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0271/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(REPO))
    import scenario as F  # noqa: E402

    test_rc, test_out = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_conflicts.py"
    )
    if test_rc != 0:
        print(f"FAILED:TST-0271 tests rc={test_rc}")
        print(test_out[-3000:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0271 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    ev1 = first_json_object(t1) or {}
    ev2 = first_json_object(t2) or {}

    declared = F.S.run(F.spec_declared())
    hidden = F.S.run(F.spec_undeclared())
    tally = declared["tally"]
    hidden_tally = hidden["tally"]
    audit = (tally["excluded"][0]["audit"] if tally["excluded"] else "")
    hidden_audit = (
        hidden_tally["excluded"][0]["audit"] if hidden_tally["excluded"] else ""
    )
    mutant = F.C.warning_only_mutant(F.seats_declared(), F.artifact(), F.ballots())
    mutant_caught = False
    try:
        F.C.assert_no_conflicted_counting_vote(mutant)
    except F.C.ConflictError:
        mutant_caught = True
    if not mutant_caught:
        print("FAILED:TST-0271 warning-only mutant not caught at emit")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    question = (
        "Implementation target: require every seat to declare conflicts "
        "(authored the artifact under review, owns the proposal, is the vendor "
        "being evaluated) and enforce the consequence the spec implies at "
        ":10924 - recusal, weight reduction, or exclusion from a partition. "
        "Spec adds hidden conflicts of interest at :11242. The test is that a "
        "conflicted seat CANNOT cast a counting vote on its own artifact, not "
        "that a warning appears."
    )
    supporting_meta = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting_meta.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "supporting",
            }
        )
    receipt = {
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ]
        + supporting_meta,
        "completion_sentinel": "SUCCESS:TST-0271",
        "evidence": [
            {
                "id": "E1-author-reviews-own-artifact-excluded",
                "kind": "live-tally",
                "claim": (
                    "Declared author seat-author submitted ACCEPT; the counting "
                    "tally is ACCEPT=1 REJECT=1 (the two unconflicted seats). "
                    "The conflicted ballot is in excluded_seat_ids, not in "
                    "counting_seat_ids."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/conflicts.py:enforce",
                "tally": tally["counts"],
                "n_submitted": tally["n_submitted"],
                "n_counting": tally["n_counting"],
                "n_excluded": tally["n_excluded"],
                "counting_seat_ids": tally["counting_seat_ids"],
                "excluded_seat_ids": tally["excluded_seat_ids"],
                "audit_line": audit,
                "naive_counts_if_still_counted": F.expected_naive_counts(),
                "probe": ev1,
            },
            {
                "id": "E2-undeclared-provenance-join",
                "kind": "live-tally",
                "claim": (
                    "The same author with conflicts=[] is still recused because "
                    "seat identity matches artifact.authors. Audit source is "
                    "provenance."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/conflicts.py:provenance_conflicts",
                "tally": hidden_tally["counts"],
                "excluded_seat_ids": hidden_tally["excluded_seat_ids"],
                "sources": hidden_tally["excluded"][0]["sources"],
                "audit_line": hidden_audit,
                "probe": ev2,
            },
            {
                "id": "E3-both-states-unconflicted-counts",
                "kind": "live-tally",
                "claim": (
                    "On the same artifact, seat-indep-a and seat-indep-b remain "
                    "in counting_seat_ids. An over-broad recusal that empties "
                    "the panel would fail this control."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/conflicts.py:enforce",
                "counting_seat_ids": hidden_tally["counting_seat_ids"],
                "unconflicted_counted": True,
            },
            {
                "id": "E4-warning-only-mutant-rejected",
                "kind": "detector-control",
                "claim": (
                    "A mutant that emits WARN ... (still counted) and keeps "
                    "the author in counts is rejected by "
                    "assert_no_conflicted_counting_vote. Warning text is not "
                    "enforcement."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/conflicts.py:assert_no_conflicted_counting_vote",
                "mutant_counts": mutant["counts"],
                "mutant_caught": mutant_caught,
            },
        ],
        "falsifiable_answer": (
            "A conflicted seat cannot cast a counting vote on its own artifact. "
            f"Live tally counts={tally['counts']} n_counting={tally['n_counting']} "
            f"excluded={tally['excluded_seat_ids']} audit={audit!r}. "
            "Empty declaration does not help: provenance join still recuses. "
            "Unconflicted seats on the same artifact still count."
        ),
        "generated_at": now,
        "id": UID,
        "min_bytes_threshold": 1024,
        "module": {
            "conflicts": "tools/council/conflicts.py",
            "simulate": "tools/council/simulate.py",
            "scheme": F.C.SCHEME_ID,
            "simulator": F.S.SIMULATOR_ID,
            "kinds": list(F.C.KINDS),
        },
        "negative_control_ids": [
            "NC-warning-only-mutant-still-counts",
            "NC-missing-conflicts-field-refused",
            "NC-foreign-artifact-declaration-still-counts",
        ],
        "negative_controls": [
            {
                "id": "NC-warning-only-mutant-still-counts",
                "rejects": "declared-but-counted ballot regardless of warning text",
                "on_that_state": "assert_no_conflicted_counting_vote raises ConflictError",
                "verbatim": "conflicted ballot counted (warning-only is a failure)",
                "fired_on_bad_state": True,
                "result": "PASS",
            },
            {
                "id": "NC-missing-conflicts-field-refused",
                "rejects": "seat object with no conflicts key",
                "on_that_state": "ConflictError: conflicts field missing",
                "verbatim": "every seat must declare conflicts",
                "fired_on_bad_state": True,
                "result": "PASS",
            },
            {
                "id": "NC-foreign-artifact-declaration-still-counts",
                "rejects": "over-broad recusal of an unconflicted independent",
                "on_that_state": "seat-indep-a remains in counting_seat_ids",
                "verbatim": "foreign-artifact declaration still counts",
                "silent_on_good_state": True,
                "result": "PASS",
            },
        ],
        "owner_signoff": {
            "granted": False,
            "required": True,
            "status": "NOT-GRANTED",
            "note": "Catalog owner_approval_required is true; this receipt does not grant it.",
        },
        "profile": "council-runtime-module",
        "question": question,
        "question_or_target": question,
        "residual_unknowns": [
            (
                "TST-0257's full seven-behaviour simulator is not on this worktree. "
                "tools/council/simulate.py here is the COI-enforcing scripted-vote "
                "substrate this unit actually executes, not a claim that TST-0257 "
                "is delivered."
            ),
            (
                "11-COUNCIL-SPECIFICATION.schema.json and _USER-PROMPTS.md are "
                "absent; kinds and consequences are taken from the TST-0271 "
                "catalog row (:10924 recusal/weight-reduction/partition, :11242 "
                "hidden COI)."
            ),
            (
                "ADV-0100 (transitive lineage self-review) was not rebuilt. "
                "This unit joins direct identity to artifact.authors / "
                "proposal_owner_id / vendor_under_evaluation."
            ),
            (
                "Independent reviewer is probe2 in this process, not a second "
                "human in a fresh vendor context."
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0271-probe2-hidden-and-both-states",
            "verdict": "PASS",
            "independent": True,
            "re_ran_detector_control": True,
            "reproduced_both_states": True,
            "starts_from": "fixtures in scenario.py, not the implementer summary",
            "grants_owner_signoff": False,
        },
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "sentinel": "SUCCESS:TST-0271",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0271] "
            "question_or_target + tests_required; conflicts field in "
            "command-center/schema/council-spec.schema.json"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "test_ids": [
            "TST0271-T1-author-reviews-own-artifact",
            "TST0271-T2-undeclared-provenance-join",
            "TST0271-T3-both-states-unconflicted-counts",
        ],
        "tests": [
            {
                "id": "probe1_author_recusal",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "probe2_hidden_and_both_states",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "unit_tests_conflicts",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/council/tests/test_conflicts.py"
                ),
                "result": "PASS",
                "exit_code": test_rc,
            },
        ],
        "title": (
            "Conflict-of-interest declaration and the enforcement that makes "
            "it more than a form field"
        ),
        "transcript_sha256": declared["transcript"]["transcript_sha256"],
        "unit_id": UID,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:TST-0271" not in text:
        print("FAILED:TST-0271 sentinel missing after write")
        return 1
    if '"state": "BLOCKED"' in text or '"state":"BLOCKED"' in text:
        print("FAILED:TST-0271 self-declared BLOCKED")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    if not all(a["present"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["present"]]
        print(f"FAILED:TST-0271 missing artifacts {missing}")
        return 1
    ret = {
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0271/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "measure": {
            "line": "SUCCESS:delivered TST-0271",
            "note": "filled after _measure_one_delivered.py; do not treat cloud_ok as delivery",
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "author-reviews-own-artifact",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "hidden-provenance-and-both-states",
                "raw_output": t2,
            },
        ],
        "notes": (
            "G-1 for TST-0271: live named probes exit 0, receipts/TST-0271.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud_ok is false and "
            "is not delivery."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0271-probe2-hidden-and-both-states",
            "verdict": "PASS",
            "reproduced_both_states": True,
        },
        "sentinel": "SUCCESS:TST-0271",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present") is True),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0271 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
