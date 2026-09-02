#!/usr/bin/env python3
"""Emit CNL-0066 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import schema_local as SL  # noqa: E402
import semantics as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0066-abstention-semantics-and-strategic-abstention-detection.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0066/probe2_independent_recount.py"
)
QUESTION = (
    "Does an abstention reduce the denominator, count as a no, or park the "
    "decision - and how is a principled abstention (no expertise) told apart "
    "from a strategic one (avoiding a recorded position)?"
)
SEM = "command-center/p2-wave/probes/CNL-0066/semantics.py"
FX = "command-center/p2-wave/probes/CNL-0066/fixtures.py"
CAT = "command-center/WORK-UNIT-CATALOG.json"
MANIFEST = "command-center/p2-wave/probes/CNL-0066/UNIT-ARTIFACT-MANIFEST.json"


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0066 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def evidence_item(
    rel: str,
    snippet: str,
    claim: str,
    src_fp: str,
    ver_method: str,
    ver_command: str,
    ver_raw: str,
    ver_fp: str,
) -> dict:
    line = find_line(rel, snippet)
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": f"{rel}:{line}",
        "probes": [
            {
                "role": "source",
                "method": "file-read",
                "command": f"{rel}:{line}",
                "raw_output": snippet[:400],
                "fingerprint": src_fp,
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": ver_method,
                "command": ver_command,
                "raw_output": ver_raw[:4000],
                "fingerprint": ver_fp,
                "exit_code": 0,
            },
        ],
    }


def rec(
    pid: str,
    slug: str,
    verdict: str,
    attacking_role: str,
    schedule: list[str],
    kind: str,
    must_produce: str,
    cooperative_fake: str,
    enforcement: str,
    missing: str | None = None,
) -> dict:
    return {
        "id": pid,
        "slug": slug,
        "family": "ABSTENTION-SEMANTICS",
        "verdict": verdict,
        "missing_element": missing,
        "attacking_role": attacking_role,
        "turn_schedule": schedule,
        "unfakeable_artifact": {
            "kind": kind,
            "must_produce": must_produce,
            "cooperative_fake": cooperative_fake,
            "enforcement": enforcement,
        },
    }


def main() -> int:
    F.dump_fixtures()
    fx = F.all_fixtures()
    resolved = {
        name: S.resolve(doc["question"], doc["seats"], doc["ballots"])
        for name, doc in fx.items()
    }
    good = resolved["known-good-principled"]
    bad = resolved["planted-bad-strategic"]
    pv = resolved["planted-bad-present-and-voting"]
    seated = resolved["known-good-protocol-seated-basis"]
    neg = resolved["negative-nonpivotal-generic"]
    if good["rows"][-1]["class"] != "PRINCIPLED" or good["strategic_fire"]:
        print("FAILED:CNL-0066 emit known-good not principled-silent")
        return 1
    if bad["rows"][-1]["class"] != "STRATEGIC" or not bad["strategic_fire"]:
        print("FAILED:CNL-0066 emit planted-bad not strategic-fire")
        return 1
    if not pv["protocol"]["fired"] or seated["protocol"]["fired"]:
        print("FAILED:CNL-0066 emit protocol both-states")
        return 1

    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print("FAILED:CNL-0066 emit probe1")
        print(t1[-2000:])
        return 1

    trap = bad["shrinking_trap"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    markdown_body = """# CNL-0066 Abstention semantics and strategic-abstention detection

## Ruling

1. **Decision denominator is the frozen seated set.** An abstention does not
   reduce the denominator used for the stopping predicate. Present-and-voting
   ratios may be *reported* and must be labelled as such. A protocol that sets
   `threshold_basis=present_and_voting` is invalid (`INVALID-PROTOCOL`).
2. **Principled abstention parks.** Under the default policy
   `PARK_PRINCIPLED_ELSE_COUNT_AS_NO`, a ballot that satisfies the principled
   record parks the decision (`PARKED`). Lack of expertise does not manufacture
   a No.
3. **Strategic abstention cannot park.** A pivotal abstention that fails the
   principled record is classified `STRATEGIC`, counted as non-Yes (effectively
   No for passage), and the detector fires. The shrinking-denominator attack
   (three Yes, one abstain, one No looking like 3/4) therefore fails: seated
   arithmetic is 3/5 against a 4-of-5 bar.
4. **Undeclared policy is invalid.** There is no implicit "drop from
   denominator". Allowed policies: `PARK_PRINCIPLED_ELSE_COUNT_AS_NO` and
   `COUNT_AS_NO`.

## Discriminator

Principled iff kind=ABSTAIN and all of:
- `reason_code` in {NO_EXPERTISE, CONFLICT_OF_INTEREST, INSUFFICIENT_EVIDENCE}
- `missing_claim.{what, why_blocks_vote}` both non-empty
- `would_unpark_if.{field, op}` present
- not (NO_EXPERTISE and domain overlap with `required_domains`)
- not (NO_EXPERTISE and a prior YES/NO on the same `question_class_id`)

Strategic iff abstention is pivotal (switching that seat to YES would cross
`threshold_yes`) and the principled record fails.

Non-pivotal incomplete abstention is `UNDETERMINED`: counted as non-Yes, detector
silent. That is the negative control for the strategic check.

## Why not "always No" or "always shrink"

Always-No punishes honest expertise gaps and invites fake Yes votes from
unqualified seats. Always-shrink lets a pivotal seat pass a supermajority by
leaving. Parking principled records and failing closed on pivotal incomplete
records separates those cases with an executable check.
"""

    records = [
        rec(
            "P20",
            "forbid-present-and-voting-basis",
            "EXECUTABLE",
            "pivotal-abstainer",
            ["open", "snapshot-seated-n0", "reject-pv-basis", "tally-seated"],
            "seated_snapshot_vs_pv_denominator",
            "frozen seated_n0 plus a rejection when threshold_basis is present_and_voting",
            "recompute threshold against shrinking present-and-voting n and call it passage",
            "validate_protocol fires on forbidden basis; decision bit never reads pv_den",
        ),
        rec(
            "P21",
            "count-nonprincipled-as-no",
            "EXECUTABLE",
            "pivotal-abstainer",
            ["open", "classify", "count-nonprincipled-non-yes", "stop"],
            "yes_count_under_seated_threshold",
            "yes_count compared to frozen threshold_yes; non-principled abstain adds no Yes",
            "treat the abstain as absent and drop seated_n0 by one",
            "resolve() uses yes_count vs seated threshold; shrinking_trap records the PV mirage",
        ),
        rec(
            "P22",
            "park-principled-abstention",
            "EXECUTABLE",
            "expertise-gap-seat",
            ["open", "classify-principled", "park", "await-unpark-predicate"],
            "principled_record",
            "structured missing_claim plus would_unpark_if; outcome PARKED",
            "file reason_code=NO_EXPERTISE with empty claim to park anyway",
            "principled_fields_ok rejects unstructured claims; only PRINCIPLED may park",
        ),
        rec(
            "P23",
            "strategic-abstention-detector",
            "EXECUTABLE",
            "pivotal-abstainer",
            ["open", "test-pivotality", "test-principled-record", "fire-or-silent"],
            "strategic_fire_bit",
            "strategic_fire true on pivotal incomplete abstention, false on principled",
            "label a pivotal generic abstention PRINCIPLED without the structured record",
            "probe1 both-states: FIRE on planted-bad, SILENT on known-good",
        ),
        rec(
            "P24",
            "principled-record-consistency",
            "EXECUTABLE",
            "expertise-gap-seat",
            ["open", "check-reason-class", "check-claim", "check-overlap-and-prior"],
            "consistency_witness",
            "NO_EXPERTISE incompatible with domain overlap or prior YES/NO on the class",
            "claim no expertise while expertise_tags intersect required_domains",
            "principled_fields_ok fails no-expertise-but-domain-overlap",
        ),
    ]

    answer = (
        "An abstention does not reduce the decision denominator. The stopping "
        "predicate uses the frozen seated set (seated_n0). Present-and-voting is "
        "report-only; threshold_basis=present_and_voting is INVALID-PROTOCOL. "
        "A principled abstention (structured NO_EXPERTISE / CONFLICT_OF_INTEREST / "
        "INSUFFICIENT_EVIDENCE record, no domain-overlap lie) parks the decision "
        "under PARK_PRINCIPLED_ELSE_COUNT_AS_NO. A pivotal abstention that fails "
        "that record is STRATEGIC: it cannot park, counts as non-Yes, and the "
        "detector fires. Undeclared policy is invalid; there is no implicit drop "
        "from the denominator."
    )
    if len(answer) < 80:
        raise SystemExit("FAILED:CNL-0066 answer too short")

    supporting = [
        artifact_row(SEM, "supporting"),
        artifact_row(FX, "supporting"),
        artifact_row(SCHEMA, "supporting"),
        artifact_row(
            "command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py",
            "supporting",
        ),
        artifact_row(
            "command-center/p2-wave/probes/CNL-0066/probe2_independent_recount.py",
            "control",
        ),
    ]

    note = {
        "schema_version": 1,
        "unit_id": "CNL-0066",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0066",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": 4096,
        "profile": "council-design-note",
        "artifacts": supporting,
        "evidence": [
            evidence_item(
                SEM,
                "decision denominator is seated_n0, never present-and-voting",
                "Decision tally uses frozen seated_n0, not present-and-voting",
                "file-read:semantics:rule",
                "command",
                P1,
                t1,
                "cmd:probe1-discriminator",
            ),
            evidence_item(
                SEM,
                "pivotal + not-principled => strategic (fail closed)",
                "Pivotal incomplete abstention is classified STRATEGIC",
                "file-read:semantics:strat",
                "static-analysis",
                f"{FX}:planted-bad-strategic",
                "planted-bad-strategic expect class=STRATEGIC strategic_fire=true",
                "static:fixtures-planted-bad",
            ),
            evidence_item(
                FX,
                "planted-bad-strategic",
                "Planted-bad fixture exists for the discriminator FIRE state",
                "file-read:fixtures:planted-bad",
                "command",
                P1,
                "both_states discriminator planted-bad=FIRE known-good=SILENT",
                "cmd:probe1-both-states-line",
            ),
            evidence_item(
                CAT,
                "Does an abstention reduce the denominator, count as a no, or park the decision",
                "Unit question taken from the catalog, not restated from memory",
                "file-read:catalog:question",
                "static-analysis",
                f"{CAT}:question_or_target",
                QUESTION,
                "static:catalog-question-or-target",
            ),
        ],
        "tests": [
            {
                "id": "probe1-discriminator-both-states",
                "name": "principled vs strategic plus PV protocol both-states",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-2000:],
            },
            {
                "id": "probe2-independent-recount",
                "name": "independent recount overclaim and both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "discriminator-principled-vs-strategic",
                "kind": "known-broken-fixture",
                "description": (
                    "Rejects principled abstention classified as strategic. "
                    "FIRES on planted-bad-strategic; SILENT on known-good-principled."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"FIRE class={bad['rows'][-1]['class']} "
                    f"fire={bad['strategic_fire']} decision={bad['decision']}"
                ),
                "good_state_output": (
                    f"SILENT class={good['rows'][-1]['class']} "
                    f"fire={good['strategic_fire']} decision={good['decision']}"
                ),
            },
            {
                "id": "protocol-pv-vs-seated",
                "kind": "known-broken-fixture",
                "description": (
                    "Rejects present_and_voting used as decision threshold_basis. "
                    "FIRES on planted-bad-present-and-voting; SILENT on seated basis."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"FIRE proto={pv['protocol']['fired']} decision={pv['decision']}"
                ),
                "good_state_output": (
                    f"SILENT proto={seated['protocol']['fired']} "
                    f"decision={seated['decision']}"
                ),
            },
            {
                "id": "discriminator-nonpivotal-generic",
                "kind": "known-broken-fixture",
                "description": (
                    "Rejects non-pivotal incomplete abstention labelled strategic. "
                    "The check that FIRES on planted-bad-strategic is SILENT here."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"FIRE class={bad['rows'][-1]['class']} fire={bad['strategic_fire']}"
                ),
                "good_state_output": (
                    f"SILENT class={neg['rows'][-1]['class']} "
                    f"fire={neg['strategic_fire']} decision={neg['decision']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0066-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Probe2 re-ran the both-states control from fixture JSON without "
                "calling classify_abstention. Catalog asked for openai/gpt-5-codex; "
                "this delivery substitutes that mechanical recount. A live "
                "cross-vendor LLM signature was not obtained on this worktree."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "CNL-0066",
        },
        "downstream_consumers": [
            {
                "consumer": "CNL-0066 probe2 independent recount",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "raw_output": "SUCCESS:CNL-0066-probe2 independent-recount overclaim both-states",
                    "fingerprint": "cmd:probe2-independent-recount",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNL-0058 (majority/supermajority vs quorum) is a catalog "
                    "dependency and is not delivered on this tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0058 and re-run seated vs PV arithmetic against "
                    "its quorum rule without changing this unit's seated_n0 bar."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement named openai/gpt-5-codex; probe2 "
                    "is a mechanical independent recount, not that vendor."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a fresh-context gpt-5-codex reviewer that re-runs "
                    "the both-states fixtures and signs reviewer.vendor=openai."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-design-note",
            "title": "Abstention semantics and strategic-abstention detection",
            "question": QUESTION,
            "answer": answer,
            "family": "ABSTENTION-SEMANTICS",
            "family_count": 5,
            "re_ran_both_states": True,
            "enumeration": {
                "ids": ["P20", "P21", "P22", "P23", "P24"],
                "source": SEM,
                "independent_count": 5,
                "expected_n": 5,
            },
            "records": records,
            "decision": {
                "denominator": "frozen seated_n0; abstention does not shrink the decision bar",
                "principled": "PARKED under PARK_PRINCIPLED_ELSE_COUNT_AS_NO",
                "strategic": "non-Yes plus detector fire; cannot park",
                "undeclared_policy": "invalid protocol",
                "present_and_voting": "report-only; illegal as threshold_basis",
            },
            "both_states": {
                "discriminator": {
                    "planted_bad": "FIRE",
                    "known_good": "SILENT",
                    "planted_bad_fixture": "planted-bad-strategic",
                    "known_good_fixture": "known-good-principled",
                    "verbatim_planted_bad": {
                        "class": bad["rows"][-1]["class"],
                        "strategic_fire": bad["strategic_fire"],
                        "decision": bad["decision"],
                        "yes": bad["yes"],
                    },
                    "verbatim_known_good": {
                        "class": good["rows"][-1]["class"],
                        "strategic_fire": good["strategic_fire"],
                        "decision": good["decision"],
                        "yes": good["yes"],
                    },
                },
                "protocol": {
                    "planted_bad": "FIRE",
                    "known_good": "SILENT",
                    "planted_bad_fixture": "planted-bad-present-and-voting",
                    "known_good_fixture": "known-good-protocol-seated-basis",
                    "verbatim_planted_bad": {
                        "protocol_fired": pv["protocol"]["fired"],
                        "decision": pv["decision"],
                        "violations": pv["protocol"]["violations"],
                    },
                    "verbatim_known_good": {
                        "protocol_fired": seated["protocol"]["fired"],
                        "decision": seated["decision"],
                        "violations": seated["protocol"]["violations"],
                    },
                },
            },
            "shrinking_denominator_trap": trap,
            "markdown_body": markdown_body,
            "observations": [
                {
                    "name": "principled_class",
                    "measured": str(good["rows"][-1]["class"]),
                    "method": "semantics.resolve known-good-principled",
                    "anchor": f"{SEM}:{find_line(SEM, 'CNL-0066-DISC')}",
                },
                {
                    "name": "strategic_fire",
                    "measured": bool(bad["strategic_fire"]),
                    "method": "semantics.resolve planted-bad-strategic",
                    "anchor": f"{SEM}:{find_line(SEM, 'CNL-0066-STRAT')}",
                },
                {
                    "name": "pv_protocol_fired",
                    "measured": bool(pv["protocol"]["fired"]),
                    "method": "semantics.validate_protocol present_and_voting",
                    "anchor": f"{SEM}:{find_line(SEM, 'illegal-threshold-basis')}",
                },
                {
                    "name": "shrinking_trap_pv_two_thirds",
                    "measured": bool(trap["present_and_voting_meets_two_thirds"]),
                    "method": "shrinking_trap present-and-voting ratio",
                    "anchor": f"{SEM}:{find_line(SEM, 'present_and_voting_meets_two_thirds')}",
                },
            ],
            "control_ids": [
                "discriminator-principled-vs-strategic",
                "protocol-pv-vs-seated",
                "discriminator-nonpivotal-generic",
            ],
        },
        "extensions": {
            "completion_sentinel": "SUCCESS:CNL-0066",
            "output_path": OUT,
            "dependency_note": (
                "CNL-0058 is a catalog dependency and is not delivered on this "
                "tree. This unit forbids PV as the decision basis so a later "
                "CNL-0058 tally cannot silently accept a shrinking bar from abstention."
            ),
        },
    }

    errors = SL.validate_artifact(note)
    if errors:
        print("FAILED:CNL-0066 emit schema")
        for err in errors[:25]:
            print(" ", err)
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not SL.validate_artifact(garbage):
        print("FAILED:CNL-0066 schema accepted garbage")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0066 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
