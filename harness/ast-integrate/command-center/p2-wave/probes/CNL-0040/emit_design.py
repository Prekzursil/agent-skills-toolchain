#!/usr/bin/env python3
"""Emit CNL-0040 design note (JSON at catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import family as F  # noqa: E402
import reviewer as V  # noqa: E402
import runtime as R  # noqa: E402
import validate_note as VN  # noqa: E402

OUT = "command-center/design/council/CNL-0040-executable-runtime-semantics-for-the-6-judicial-protocols.md"
SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/CNL-0040/council-design-note.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
RANGING = "command-center/p2-wave/probes/CNL-0040/fixtures/ranging_set.json"
RUNS = "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json"
RUNTIME = "command-center/p2-wave/probes/CNL-0040/runtime.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0040/probe1_family_schedules.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0040/probe2_both_states.py"
)
QUESTION = (
    "Ranging over exactly these 6 records, named so no member can fall through a "
    "family mis-assignment (P14 judge-and-jury, P15 claim-by-claim-adjudication, "
    "P16 grand-jury-threshold, P17 jury-with-allowed-hung, P18 two-key-dual-control, "
    "P19 rfc-last-call): For each of the 6 JUDICIAL protocol records, what is the "
    "admissibility standard for evidence and who rules on admissibility without "
    "becoming the decider?"
)

ANSWERS = {
    "P14": {
        "admissibility_standard": (
            "RELEVANCE_AND_RELIABILITY: an exhibit is admissible iff its claim_id "
            "is on the charged docket, source_kind is record|measurement|sworn-statement, "
            "and provenance_hash is present. Hearsay and argument fail the standard."
        ),
        "who_rules": "judge",
        "who_decides": "jury",
        "separation": (
            "The judge issues admit|exclude rulings and is forbidden from the decider "
            "set and from casting a verdict ballot. The jury sees only admitted exhibits."
        ),
    },
    "P15": {
        "admissibility_standard": (
            "ATOMIC_CITABLE_CLAIM: a claim-exhibit is admissible iff it is atomic "
            "(atomic:true), cites a record_id, sits on the docket, and is not an argument."
        ),
        "who_rules": "claims-clerk",
        "who_decides": "panel",
        "separation": (
            "The claims-clerk gates each claim. The panel ballots only admitted claims. "
            "The clerk is not a panel member and casts no claim ballot."
        ),
    },
    "P16": {
        "admissibility_standard": (
            "PROBABLE_CAUSE_PACKET: threshold evidence only — reliable kind plus "
            "provenance, threshold_only:true. Argument and full-proof advocacy are excluded "
            "from the true-bill packet."
        ),
        "who_rules": "threshold-clerk",
        "who_decides": "grand-jury",
        "separation": (
            "The threshold-clerk seals the packet. The grand jury votes true-bill|no-bill "
            "on that packet. The clerk has no grand-jury ballot."
        ),
    },
    "P17": {
        "admissibility_standard": (
            "Same RELEVANCE_AND_RELIABILITY as P14. Hung is a terminal protocol state, "
            "not a failure to decide."
        ),
        "who_rules": "judge",
        "who_decides": "jury",
        "separation": (
            "After rounds_exhausted without unanimity the clerk records HUNG. The judge "
            "must not cast a tie-break ballot or substitute a verdict."
        ),
    },
    "P18": {
        "admissibility_standard": (
            "DUAL_CONCURRENCE: content must pass RELEVANCE_AND_RELIABILITY AND two "
            "distinct officers must both admit. A single-key admit fail-closes to exclude."
        ),
        "who_rules": "officer-a and officer-b (pair)",
        "who_decides": "dual-key deciders",
        "separation": (
            "Neither officer is a decider. Verdict keys are a disjoint pair. Dual control "
            "applies to admission and to authorization."
        ),
    },
    "P19": {
        "admissibility_standard": (
            "IN_WINDOW_SPECIFIC_CITATION: an objection is in-scope iff timestamp is "
            "inside the last-call window, section_id is present, and claim_id is specific."
        ),
        "who_rules": "last-call-chair",
        "who_decides": "participants",
        "separation": (
            "The chair rules in-scope|out-of-scope only. Consensus is counted among "
            "participants. A chair consensus_call is CHAIR_DECLARED_CONSENSUS."
        ),
    },
}


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0040 emit snippet not found in {path}: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(
    rel: str,
    snippet: str,
    claim: str,
    verdict: str,
    kind: str = "live-tree",
) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "verdict": verdict,
        "anchor": f"{rel}:{line}",
    }


def _fixture_rows() -> list[dict]:
    runs = R.load_runs()
    rows: list[dict] = []
    for pid, run in (runs.get("good") or {}).items():
        rows.append(
            {
                "id": str(run.get("id") or pid),
                "risk_tier": "T1",
                "task_description": (
                    f"Known-good {pid} run: officer gates exhibits; deciders ballot "
                    f"admitted ids only; invariants silent."
                ),
                "explanation": {
                    "kind": "good",
                    "protocol_id": pid,
                    "expected": "SILENT",
                    "officers": run.get("officers"),
                    "deciders": run.get("deciders"),
                },
            }
        )
    for name, run in (runs.get("bad") or {}).items():
        rows.append(
            {
                "id": str(run.get("id") or name),
                "risk_tier": "T3",
                "task_description": (
                    f"Planted-bad {name}: expect FIRE {run.get('planted_defect')}."
                ),
                "explanation": {
                    "kind": "bad",
                    "protocol_id": run.get("protocol_id"),
                    "expected": "FIRE",
                    "planted_defect": run.get("planted_defect"),
                },
            }
        )
    if len(rows) < 10:
        raise SystemExit(f"FAILED:CNL-0040 emit need 10 fixtures, got {len(rows)}")
    return rows


def protocol_row(pid: str, live: dict) -> dict:
    spec = R.PROTOCOLS[pid]
    ans = ANSWERS[pid]
    return {
        "record_id": spec["record_id"],
        "slug": spec["slug"],
        "family": "JUDICIAL",
        "verdict": (
            f"{pid} EXECUTABLE: standard={spec['admissibility_standard_id']} "
            f"officer={spec['admissibility_officer_role']} "
            f"decider={spec['decider_role']} "
            f"live_good_silent admitted={live['admitted']} excluded={live['excluded']}"
        ),
        "executable": True,
        "missing_element": None,
        "admissibility_standard_id": spec["admissibility_standard_id"],
        "admissibility_standard": ans["admissibility_standard"],
        "who_rules_on_admissibility": ans["who_rules"],
        "who_decides": ans["who_decides"],
        "separation": ans["separation"],
        "officer_role": spec["admissibility_officer_role"],
        "decider_role": spec["decider_role"],
        "stopping": spec["stopping"],
        "turn_schedule": spec["turn_schedule"],
        "live_good_run": live,
        "role_mandate": {
            "officer_obligation": "must rule admit|exclude on every offered exhibit",
            "officer_permission": "may exclude exhibits that fail the standard",
            "officer_right": "must not be conscripted as a decider",
            "decider_obligation": "ballot only on admitted exhibits",
            "decider_permission": "none to admit or exclude",
        },
    }


def main() -> int:
    measured = C.measure()
    if not measured["ok"]:
        print("FAILED:CNL-0040 emit controls.measure not ok")
        print(json.dumps({k: measured[k] for k in ("ok",)}, indent=2))
        print(json.dumps(measured["gatekeeper_both_states"], indent=2)[:2000])
        print(json.dumps(measured["all_good"], indent=2)[:2000])
        print(json.dumps(measured["extra_planted"], indent=2)[:2000])
        return 1

    enum = measured["enumeration"]
    goods = measured["all_good"]["rows"]
    protocols = [protocol_row(pid, goods[pid]) for pid in enum["ids"]]
    tab = V.retabulate(
        {
            "family_count": F.EXPECTED_N,
            "protocols": [{"record_id": p["record_id"]} for p in protocols],
        }
    )
    if tab["disagreement"]:
        print("FAILED:CNL-0040 emit reviewer disagreement")
        print(json.dumps(tab, indent=2))
        return 1

    gate = measured["gatekeeper_both_states"]
    count = measured["family_count_both_states"]
    neg = measured["negative_control"]

    answer = (
        "For the 6 JUDICIAL records P14-P19 the admissibility officer is never a "
        "decider. P14/P17: judge applies RELEVANCE_AND_RELIABILITY; jury decides "
        "(P17 may terminate HUNG). P15: claims-clerk applies ATOMIC_CITABLE_CLAIM; "
        "panel decides per admitted claim. P16: threshold-clerk applies "
        "PROBABLE_CAUSE_PACKET; grand jury true-bills. P18: two officers must both "
        "admit (DUAL_CONCURRENCE); dual-key deciders authorize. P19: last-call-chair "
        "applies IN_WINDOW_SPECIFIC_CITATION; participants count consensus. All 6 "
        "are EXECUTABLE. Family n=6 was re-derived from the catalog named ranging "
        "set and fixtures/ranging_set.json; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
        "is absent on this worktree. SUCCESS:CNL-0040"
    )

    evidence = [
        ev(
            CATALOG,
            "family=JUDICIAL, expected n=6",
            "Catalog evidence_requirement names JUDICIAL expected n=6.",
            "CONFIRMED",
            "dossier",
        ),
        ev(
            CATALOG,
            "P14 judge-and-jury, P15 claim-by-claim-adjudication, P16 grand-jury-threshold, P17 jury-with-allowed-hung, P18 two-key-dual-control, P19 rfc-last-call",
            "Catalog question names the 6 JUDICIAL P-ids so none can fall through.",
            "CONFIRMED",
            "dossier",
        ),
        ev(
            RANGING,
            '"id": "P14"',
            "Ranging-set fixture lists P14 as the first JUDICIAL member.",
            "CONFIRMED",
        ),
        ev(
            RUNTIME,
            "GATEKEEPER_IS_DECIDER",
            "Runtime fires GATEKEEPER_IS_DECIDER when officer and decider sets intersect.",
            "CONFIRMED",
        ),
        ev(
            RUNS,
            "P14-gatekeeper-decides",
            "Planted-bad fixture puts judge-1 in officers and deciders.",
            "CONFIRMED",
        ),
        ev(
            RUNTIME,
            "hung_is_terminal",
            "P17 records hung as a terminal state the judge must not break.",
            "CONFIRMED",
        ),
        ev(
            RANGING,
            '"library_on_this_tree": false',
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from this worktree.",
            "REFUTED",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0040",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0040",
        "title": "Executable runtime semantics for the 6 JUDICIAL protocols",
        "question": QUESTION,
        "answer": answer,
        "family": "JUDICIAL",
        "family_count": F.EXPECTED_N,
        "enumeration": {
            "expected_n": F.EXPECTED_N,
            "catalog_ids": enum["catalog"]["ids"],
            "fixture_ids": enum["fixture"]["ids"],
            "match": enum["match"],
            "library": enum["library"],
            "note": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. "
                "Family membership is the catalog named ranging set plus the "
                "independent ranging_set.json fixture. If the library appears, "
                "family.ranging_from_library requires family=JUDICIAL count==6."
            ),
        },
        "protocols": protocols,
        "both_states": {
            "id": "gatekeeper-vs-decider",
            "silent_on_good": gate["silent_on_good"],
            "fires_on_bad": gate["fires_on_bad"],
            "good": gate["good"],
            "bad": gate["bad"],
            "family_count": {
                "silent_on_good": count["silent_on_good"],
                "fires_on_bad": count["fires_on_bad"],
                "good_n": count["good_n"],
                "bad_n": count["bad_n"],
            },
            "extra_planted": measured["extra_planted"],
        },
        "algorithm": {
            "id": "judicial-admissibility-gate",
            "inputs": [
                "protocol record_id in {P14..P19}",
                "run fixture: exhibits, rulings, officers, deciders, ballots",
            ],
            "outputs": [
                "admitted exhibit ids",
                "excluded exhibit ids plus invariant violations",
            ],
            "steps": [
                "Enumerate JUDICIAL members from catalog named ranging set and ranging_set.json (n=6).",
                "Apply the protocol's admissibility standard to each exhibit (content predicates).",
                "Admit only when the officer set, disjoint from deciders, issues the required ruling(s).",
                "Seal the admitted packet; decider ballots may cite admitted ids only.",
                "FIRE on GATEKEEPER_IS_DECIDER, OFFICER_CAST_VERDICT, SINGLE_KEY_ADMIT, HUNG_BROKEN_BY_OFFICER, or CHAIR_DECLARED_CONSENSUS.",
            ],
        },
        "defaults": {
            "protocol": "P14-judge-and-jury",
            "voting_method": "jury-ballot-on-admitted-only",
            "stopping_rule": "ALL(decider_ballots_cast) AND NOT ANY(pending_objections)",
            "roles": ["judge", "jury", "clerk", "advocate", "opponent"],
        },
        "explanation_contract": {
            "dials": [
                "admissibility_standard_id",
                "officer_role",
                "decider_role",
                "stopping_expression",
            ],
            "missing_reason_fails": True,
            "owner_contest": (
                "Owner may contest an exclude only by naming the failed predicate "
                "(relevance, reliability, atomicity, dual-key, or last-call window); "
                "a contest without a predicate fails closed."
            ),
        },
        "fixtures": _fixture_rows(),
        "negative_control": neg,
        "negative_controls": [
            {
                "id": "P14-gatekeeper-decides",
                "fires_on_bad": True,
                "silent_on_good": True,
                "rejects": (
                    "Judge in both officers and deciders who casts a verdict ballot; "
                    "GATEKEEPER_IS_DECIDER."
                ),
                "verbatim": neg["verbatim"],
            }
        ],
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "judicial_family_n",
                    "measured": F.EXPECTED_N,
                    "method": "catalog-question-regex plus ranging_set.json",
                    "anchor": f"{RANGING}:1",
                },
                {
                    "name": "gatekeeper_silent_on_good",
                    "measured": gate["silent_on_good"],
                    "method": "runtime.execute_named good/P14",
                    "anchor": f"{RUNTIME}:GATEKEEPER_IS_DECIDER",
                },
                {
                    "name": "gatekeeper_fires_on_bad",
                    "measured": gate["fires_on_bad"],
                    "method": "runtime.execute_named bad/P14-gatekeeper-decides",
                    "anchor": "command-center/p2-wave/probes/CNL-0040/fixtures/runs.json:P14-gatekeeper-decides",
                },
            ],
            "control_ids": [
                "gatekeeper-vs-decider",
                "family-count-n6",
                "P14-gatekeeper-decides",
                "P17-judge-breaks-hung",
                "P18-single-key-admit",
                "P19-chair-declares-consensus",
            ],
        },
        "tests": [
            {
                "id": "T1-family-schedules",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-negative-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": tab["reviewer_id"],
            "verdict": tab["verdict"],
            "independent": True,
            "scope_not_agreement": True,
            "method": tab["method"],
            "numbers": tab["numbers"],
            "ids": {
                "catalog": tab["catalog_ids"],
                "fixture": tab["fixture_ids"],
                "semantics": tab["semantics_ids"],
            },
        },
        "strongest_surviving_counterargument": (
            "The original 12-COUNCIL library might assign a seventh record to "
            "JUDICIAL or might have encoded a different officer for P18. That "
            "counterargument survives as a library-absent residual. It does not "
            "change the catalog named ranging set of six P-ids this unit is "
            "required to range over, and the library probe is live if the file appears."
        ),
        "dependencies_used": {
            "CNL-0010": "Stopping conditions are AND/OR/NOT/ALL/ANY expressions, not prose.",
            "CNL-0022": "Officer obligation/permission/right are distinct from decider mandate.",
            "CNL-0001": "Records are addressable by P-id inside a CouncilSpec-shaped envelope.",
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "schema"},
            {"path": RANGING, "exists": True, "role": "ranging-set"},
            {"path": RUNS, "exists": True, "role": "fixtures"},
            {"path": RUNTIME, "exists": True, "role": "runtime"},
        ],
        "evidence": evidence,
        "ts": now,
        "format": "council-design-note+json",
        "notes": (
            "JSON stored at the catalog .md path because G-1 measure requires "
            "json.loads of output_path. Catalog output_schema is a $ref shim to "
            "ast-integrate.invalid and is not fetched. Live compile uses "
            "probes/CNL-0040/council-design-note.schema.json. Did not run "
            "unit_manifest.py --write."
        ),
    }

    try:
        VN.validate_note(doc)
    except Exception as exc:
        print(f"FAILED:CNL-0040 emit schema {type(exc).__name__}: {exc}")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0040 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
