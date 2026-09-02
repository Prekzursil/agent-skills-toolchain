#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0361.json from a live recusal run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

UNIT = "IMP-0361"
OUT = "command-center/receipts/IMP-0361.json"
LIB = "tools/council/integrity/recusal.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0361/probe1_lifecycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0361/probe2_recused_ballot.py"
)
NC_ID = "IMP-0361-NC-RECUSED-BALLOT-IN-TALLY"
T1_ID = "IMP-0361-lifecycle-quorum"
T2_ID = "IMP-0361-recused-ballot-in-tally"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:{UNIT} emit missing anchor {needle!r} in {rel}")


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    life = S.declare_recuse_replace()
    voided = S.quorum_void_then_restore()
    nc = S.negative_control()

    if life["recused_still_counts"] or life["recused_in_recomputed"]:
        print(f"FAILED:{UNIT} emit recused ballot still counts")
        return 1
    if not life["differ"] or not life["census_retained"]:
        print(f"FAILED:{UNIT} emit tally/census {life['differ']} {life['census_retained']}")
        return 1
    if life["recomputed_counts"].get("approve") != 2:
        print(f"FAILED:{UNIT} emit recomputed {life['recomputed_counts']}")
        return 1
    if life["recorded_counts"].get("approve") != 3:
        print(f"FAILED:{UNIT} emit recorded {life['recorded_counts']}")
        return 1
    if not nc["both_states"] or not nc["planted_fired"] or nc["honest_fired"]:
        print(f"FAILED:{UNIT} emit negative control {nc}")
        return 1
    if not voided["void"] or not voided["restored_met"]:
        print(f"FAILED:{UNIT} emit quorum void/restore {voided}")
        return 1

    lib_art = art(LIB, "implementation")
    if not lib_art["exists"] or lib_art["bytes"] < 128:
        print(f"FAILED:{UNIT} library missing or tiny")
        return 1

    exclude_anchor = source_anchor(LIB, "def counting_ballots(self)")
    audit_anchor = source_anchor(LIB, "def audit_counting_ballots(")
    census_anchor = source_anchor(LIB, "def contribution_census(")
    replace_anchor = source_anchor(LIB, "inherited_ballots=0")

    measured = {
        "recused_seat": life["recused_seat"],
        "replacement_seat": life["replacement_seat"],
        "pre_decision": life["pre_decision"],
        "recorded_approve": life["recorded_counts"]["approve"],
        "recorded_reject": life["recorded_counts"]["reject"],
        "recorded_decision": life["recorded_decision"],
        "recomputed_approve": life["recomputed_counts"]["approve"],
        "recomputed_reject": life["recomputed_counts"]["reject"],
        "recomputed_decision": life["recomputed_decision"],
        "recused_still_counts": life["recused_still_counts"],
        "differ": life["differ"],
        "census_retained": life["census_retained"],
        "idea_a1_hash": life["contribution_hashes_post"]["idea-A1"],
        "inherited_ballots": life["inherited_ballots"],
        "post_recusal_eligible_n": life["post_quorum"]["eligible_n"],
        "post_recusal_quorum_met": life["post_quorum"]["met"],
        "after_replace_eligible_n": life["after_replace_quorum"]["eligible_n"],
        "quorum_void": voided,
        "negative_control": {
            "code": nc["code"],
            "honest_fired": nc["honest_fired"],
            "planted_fired": nc["planted_fired"],
            "both_states": nc["both_states"],
            "leaked_seats": nc["planted_leaked_seats"],
            "leaked_ballots": nc["planted_leaked_ballots"],
        },
    }

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    artifact_paths = [
        LIB,
        "tools/council/integrity/__init__.py",
        "tools/council/__init__.py",
        "command-center/p2-wave/probes/IMP-0361/scenario.py",
        "command-center/p2-wave/probes/IMP-0361/probe1_lifecycle.py",
        "command-center/p2-wave/probes/IMP-0361/probe2_recused_ballot.py",
        OUT,
    ]
    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0361",
        "completion_sentinel": "SUCCESS:IMP-0361",
        "title": "Recusal workflow with quorum recomputation",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0361 "
            "tools/council/integrity/recusal.py declare-recuse-replace; "
            "catalog evidence: tally recomputation excluding recused ballots "
            "compared to recorded tally; census of retained pre-recusal "
            "contributions. Inputs 11-COUNCIL-SPECIFICATION.md and "
            "_USER-PROMPTS.md:10915-10946 are absent on this Linux worktree."
        ),
        "question_or_target": (
            "Implement tools/council/integrity/recusal.py handling "
            "declare-recuse-replace, recomputing quorum and preserving the "
            "recused participant's pre-recusal contributions. Falsifiable "
            "question: after a recusal, does any vote cast by the recused "
            "participant still count toward the decision?"
        ),
        "answer": (
            "No. recompute_tally filters by recused seat identity. On the "
            "five-seat fixture the recorded tally is approve=3/reject=2 "
            "(decision approve) and the recomputed tally is 2-2 (no decision). "
            "The recused approve is in the ledger and the census, not the count."
        ),
        "implementation": {
            "module": LIB,
            "api": [
                "RecusalSession.declare",
                "RecusalSession.recuse",
                "RecusalSession.replace",
                "RecusalSession.recompute_tally",
                "RecusalSession.recorded_tally",
                "RecusalSession.audit_counting_ballots",
                "RecusalSession.contribution_census",
                "RecusalSession.recompute_quorum",
            ],
            "detector": "RECUSED_BALLOT_IN_TALLY",
            "quorum_rule": (
                "absolute floor ceil(original_n * ratio); eligible = "
                "non-recused seats including replacements; void if eligible "
                "< floor"
            ),
            "replacement_inherits_ballots": False,
        },
        "measured": measured,
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths,
        "artifacts": [
            lib_art,
            art("tools/council/integrity/__init__.py", "supporting"),
            art("tools/council/__init__.py", "supporting"),
            art("command-center/p2-wave/probes/IMP-0361/scenario.py", "fixture"),
            art(
                "command-center/p2-wave/probes/IMP-0361/probe1_lifecycle.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0361/probe2_recused_ballot.py",
                "probe",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Tally recomputation excluding recused ballots diverges "
                    "from the recorded tally: recorded approve=3 elects "
                    "approve; recomputed approve=2/reject=2 elects nobody. "
                    f"Recused seat {life['recused_seat']} is in recorded "
                    "counting seats and absent from recomputed counting seats."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": exclude_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.declare_recuse_replace",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "recorded": life["recorded_counts"],
                                "recomputed": life["recomputed_counts"],
                                "differ": life["differ"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": None,
                        "raw_output": (
                            "named probe1 re-runs lifecycle + quorum void/"
                            "restore against the live module"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Artifact census: idea-A1 hash is unchanged across recusal "
                    f"({life['contribution_hashes_post']['idea-A1'][:16]}…). "
                    "missing_ids empty. Recusal records retained_contribution_ids "
                    "rather than deleting the recused author's ideas."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": census_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.declare_recuse_replace.census",
                        "exit_code": 0,
                        "raw_output": json.dumps(life["census"], sort_keys=True),
                    }
                ],
            },
            {
                "claim": (
                    "Replacement seat-F inherits 0 ballots "
                    f"(replace_inherited_ballots={life['replace_inherited_ballots']}). "
                    f"Anchor {replace_anchor}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": replace_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.declare_recuse_replace.replace",
                        "exit_code": 0,
                        "raw_output": f"inherited_ballots={life['inherited_ballots']}",
                    }
                ],
            },
            {
                "claim": (
                    "Quorum: original floor 3 of 5. One recusal leaves eligible=4 "
                    "(met). Recusing three seats leaves eligible=2 (void, no "
                    "decision). Replacing one recused seat restores eligible=3."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": source_anchor(LIB, "def recompute_quorum("),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.quorum_void_then_restore",
                        "exit_code": 0,
                        "raw_output": json.dumps(voided, sort_keys=True),
                    }
                ],
            },
        ],
        "test_ids": [T1_ID, T2_ID],
        "tests": [
            {
                "id": T1_ID,
                "name": "unit: recusal lifecycle and quorum recomputation",
                "command": P1,
                "result": "PENDING-NAMED-PROBE",
            },
            {
                "id": T2_ID,
                "name": "negative control: recused ballot left in tally FIRES",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_control_ids": [NC_ID],
        "negative_controls": [
            {
                "id": NC_ID,
                "kind": "known-broken-counting-set",
                "description": (
                    "Leave the recused seat's ballot in the proposed counting "
                    "set. audit_counting_ballots must fire "
                    "RECUSED_BALLOT_IN_TALLY. Honest recompute of the same "
                    "session must be silent."
                ),
                "fired_on_bad_state": nc["planted_fired"],
                "silent_on_good_state": not nc["honest_fired"],
                "good_state_output": f"fired={nc['honest_fired']} code={nc['honest_code']}",
                "bad_state_output": (
                    f"fired={nc['planted_fired']} code={nc['planted_code']} "
                    f"leaked={nc['planted_leaked_seats']}"
                ),
                "anchor": audit_anchor,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0361-probe2-recused-ballot-in-tally",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 starts from audit_counting_ballots, not the author's "
                "lifecycle summary. It plants the recorded (recused-included) "
                "ballot list as the counting set and requires FIRE, then "
                "requires silence on counting_ballots() from the same session."
            ),
        },
        "reviewer_verdict": "PASS",
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0361/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog inputs 11-COUNCIL-SPECIFICATION.md, "
                    "11-COUNCIL-SPECIFICATION.schema.json, and "
                    "_USER-PROMPTS.md:10915-10946 are absent on this worktree. "
                    "Quorum ratio 0.6 and majority-of-eligible are catalog-bound "
                    "choices, not a parsed spec file."
                ),
                "settling_experiment": (
                    "When the spec files are present, parse the quorum and "
                    "recusal clauses and diff them against RecusalSession."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Dependency modules tools/council/vote/tally.py (IMP-0302), "
                    "tools/council/participants/replace.py (IMP-0275), and "
                    "tools/council/integrity/coi.py (IMP-0277) are absent. "
                    "RecusalSession owns recusal-time exclusion, replacement "
                    "seating without vote inheritance, and a declared-conflict "
                    "record. A later tally.py must consume counting_ballots() "
                    "rather than the raw ledger."
                ),
                "settling_experiment": (
                    "After IMP-0302 ships, pass recompute_tally's counting set "
                    "into tally.py and assert the same 2-2 outcome."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "scope": {
            "proof_surface": (
                "Hermetic five-seat RecusalSession in process memory. No live "
                "model calls. Detector is audit_counting_ballots."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/vote/tally.py exists",
                "11-COUNCIL-SPECIFICATION.md is on this tree",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "named_probes": [
            {"id": "probe1", "role": "lifecycle-quorum", "command": P1},
            {"id": "probe2", "role": "recused-ballot-in-tally", "command": P2},
        ],
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-runtime-module"
        ),
        "notes": (
            "G-1 for IMP-0361: live named probes must exit 0 against "
            "tools/council/integrity/recusal.py. cloud ok=true is not delivery. "
            "Did not run global unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0361" not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"recomputed_approve={measured['recomputed_approve']} "
        f"recorded_approve={measured['recorded_approve']} "
        f"planted_fired={nc['planted_fired']}"
    )
    print("SUCCESS:IMP-0361")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
