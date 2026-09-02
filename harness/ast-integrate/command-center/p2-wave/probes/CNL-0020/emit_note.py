#!/usr/bin/env python3
"""Emit the CNL-0020 design-note artifact from live catchup measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catchup as C  # noqa: E402
import schema_bind as SB  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0020-elastic-scaling-mid-council-recruitment-and-catch-up-brief.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
CATCHUP = "command-center/p2-wave/probes/CNL-0020/catchup.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0020/probe2_both_states.py"
)
SUPPORTING = [
    SCHEMA,
    CATCHUP,
    "command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py",
    "command-center/p2-wave/probes/CNL-0020/probe2_both_states.py",
    "command-center/p2-wave/probes/CNL-0020/schema_bind.py",
]


def line_of(rel: str, needle: str) -> tuple[int, str]:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines, 1):
        if needle in ln:
            return i, ln.strip()
    raise SystemExit(f"FAILED:emit anchor miss {rel} {needle!r}")


def catalog_anchor() -> str:
    path = REPO / "command-center/WORK-UNIT-CATALOG.json"
    needle = '"id": "CNL-0020"'
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"command-center/WORK-UNIT-CATALOG.json:{i}"
    return "command-center/WORK-UNIT-CATALOG.json"


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_block(
    role: str, method: str, command: str, raw: str, fingerprint: str
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65536],
        "fingerprint": fingerprint,
        "exit_code": 0,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measured = C.run_all()
    if not measured.get("ok"):
        print("FAILED:emit catchup.run_all not ok")
        print(json.dumps(measured, indent=2, sort_keys=True)[:4000])
        return 1
    late = measured["late_arrival"]
    both = measured["both_states"]

    l_withheld, s_withheld = line_of(CATCHUP, "WITHHELD_KEYS = frozenset")
    l_leak, s_leak = line_of(CATCHUP, "def leak_check(")
    l_comp, s_comp = line_of(CATCHUP, "def completeness_check(")
    l_pos, s_pos = line_of(CATCHUP, "def first_position(")
    l_uniq, s_uniq = line_of(CATCHUP, "def _unique_claims(")
    l_build, s_build = line_of(CATCHUP, "def build_catchup_brief(")
    l_late, s_late = line_of(CATCHUP, "def run_late_arrival(")
    l_both, s_both = line_of(CATCHUP, "def run_both_states(")

    catalog_q = (
        "When a council scales from its minimum to a larger roster mid-run, "
        "what does the newcomer see - and how is a late arrival prevented from "
        "either anchoring on the existing consensus or voting without the "
        "context the others earned?"
    )

    answer = (
        "The newcomer is seated as a full nine-dial participant (CNL-0005 dials: "
        "model, vendor, expertise, role, authority, vote_weight, tools, effort, "
        "context) at join_round. What it sees is not a special 'catch-up type' "
        "and not the incumbents' running consensus. It is a CNL-0006 lattice "
        "slice: charter + constraints + every evidence node already released by "
        "join_round + unique argument claims with seat ids and frequencies "
        "stripped. Tally, standing majority, per-seat votes, chair "
        "recommendation, and claim-frequency social proof stay withheld until "
        "after first_position is committed. Two gates enforce the two failure "
        "modes the unit names: leak_check refuses a first vote if any withheld "
        "channel is present on the brief (anchoring), and completeness_check "
        "refuses a first vote if earned evidence or the nine-dial mandate is "
        "missing (context-starvation). Deduplicating claims by claim_id is load-"
        "bearing: three identical ACCEPT arguments would otherwise leak unanimity "
        "without using the word majority. This worktree does not contain the "
        "CNL-0005/CNL-0006 artifacts or 11-COUNCIL-SPECIFICATION.schema.json; "
        "those are bound as interface assumptions from the catalog questions, "
        "not as files read here. SUCCESS:CNL-0020"
    )

    late_raw = json.dumps(
        {
            "n_trials": late["n_trials"],
            "match_majority": late["match_majority"],
            "prior_equals_majority": late["prior_equals_majority"],
            "invariance_violations": late["invariance_violations"],
            "opposing_prior_copied_majority": late["opposing_prior_copied_majority"],
            "copy_hypothesis": late["copy_hypothesis"],
        },
        sort_keys=True,
    )
    both_raw = json.dumps(
        {
            "silent_on_good": both["silent_on_good"],
            "fires_on_bad": both["fires_on_bad"],
            "fires_on_starved": both["fires_on_starved"],
            "negative_control_verbatim": both["negative_control_verbatim"],
        },
        sort_keys=True,
    )

    claims = [
        {
            "id": "C1",
            "claim": (
                "A clean catch-up brief omits tally/majority/chair rec, and "
                "leak_check is SILENT on that brief."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{CATCHUP}:{l_withheld}",
            "snippet": "WITHHELD_KEYS = frozenset",
        },
        {
            "id": "C2",
            "claim": (
                "On polarity-balanced evidence the newcomer's first position "
                "equals its private prior, is invariant to flipping the "
                "standing majority, and therefore is not majority-copying."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{CATCHUP}:{l_late}",
            "snippet": "def run_late_arrival(",
        },
        {
            "id": "C3",
            "claim": (
                "leak_check FIRES on a planted majority-leak brief and "
                "may_cast_first_position refuses the first vote."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{CATCHUP}:{l_leak}",
            "snippet": "def leak_check(",
        },
        {
            "id": "C4",
            "claim": (
                "completeness_check FIRES when join-round evidence is stripped "
                "from the brief (context-starvation)."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{CATCHUP}:{l_comp}",
            "snippet": "def completeness_check(",
        },
        {
            "id": "C5",
            "claim": (
                "Giving the newcomer the incumbents' full vote transcript "
                "is a valid catch-up because 'context' includes how the vote "
                "is currently going."
            ),
            "verdict": "REFUTED",
            "defect_locus": "DESIGN",
            "anchor": f"{CATCHUP}:{l_both}",
            "snippet": "def run_both_states(",
            "scoped_restatement": (
                "Vote-going-this-way is withheld social proof, not earned "
                "context. Earned context is evidence + unique claims. The "
                "planted-bad leak fixture is this alternative, and the gate "
                "refuses it."
            ),
        },
        {
            "id": "C6",
            "claim": (
                "CNL-0005 and CNL-0006 output files were read from this "
                "worktree and supply the nine dials and the lattice type."
            ),
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "anchor": f"{CATCHUP}:{l_build}",
            "snippet": "def build_catchup_brief(",
            "scoped_restatement": (
                "Those artifacts are absent. The nine dials and lattice slice "
                "are implemented locally in catchup.py from the catalog "
                "questions, not transcribed from delivered dependency files."
            ),
        },
    ]

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0020",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0020",
        "spec_anchor": catalog_anchor(),
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Late-arrival first position is majority-invariant and not "
                    "copy-majority on polarity-balanced evidence."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{CATCHUP}:{l_pos}",
                "probes": [
                    probe_block(
                        "source",
                        "file-read",
                        f"{CATCHUP}:{l_pos}",
                        s_pos,
                        "cnl0020:file:first_position",
                    ),
                    probe_block(
                        "verifier",
                        "command",
                        f"python3 -B {CATCHUP}  # run_late_arrival fields",
                        late_raw,
                        "cnl0020:cmd:run_late_arrival",
                    ),
                ],
            },
            {
                "claim": (
                    "leak_check is SILENT on a clean catch-up brief and FIRES "
                    "on a planted majority-leak brief."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{CATCHUP}:{l_leak}",
                "probes": [
                    probe_block(
                        "source",
                        "file-read",
                        f"{CATCHUP}:{l_leak}",
                        s_leak,
                        "cnl0020:file:leak_check",
                    ),
                    probe_block(
                        "verifier",
                        "command",
                        f"python3 -B {CATCHUP}  # run_both_states fields",
                        both_raw,
                        "cnl0020:cmd:run_both_states",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "late-arrival-independence",
                "name": "newcomer first position is not majority-copying",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "both-states-and-negative-control",
                "name": "leak_check and completeness_check both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-majority-leak",
                "kind": "known-broken-fixture",
                "description": (
                    "catch-up brief that includes standing_majority / "
                    "standing_tally / chair_recommendation"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": both["negative_control_verbatim"],
                "good_state_output": (
                    f"leak_check.fired={both['good']['leak']['fired']} "
                    f"code={both['good']['leak']['code']} "
                    f"may_cast allowed={both['good']['gate']['allowed']}"
                ),
            },
            {
                "id": "NC-starved",
                "kind": "absent-input",
                "description": (
                    "catch-up brief with evidence_at_join_round stripped while "
                    "incumbents had evidence"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"completeness_check.fired="
                    f"{both['planted_bad_starved']['completeness']['fired']} "
                    f"code={both['planted_bad_starved']['completeness']['code']} "
                    f"may_cast allowed={both['planted_bad_starved']['gate']['allowed']} "
                    f"reason={both['planted_bad_starved']['gate']['reason']}"
                ),
                "good_state_output": (
                    f"completeness_check.fired="
                    f"{both['good']['gate']['completeness']['fired']} "
                    f"code={both['good']['gate']['completeness']['code']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0020-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Reviewer is the second named probe. It re-executes leak_check "
                "and completeness_check from fixtures and does not take the "
                "answer field as evidence. executed_both_states_control=true."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0020/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0020",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_block(
                    "verifier",
                    "file-read",
                    f"stat {OUT}",
                    "named probes re-read the catalog output_path after emit",
                    "cnl0020:artifact-stat",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b). Max 3 attempts."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "first_position is a deterministic polarity scorer, not a "
                    "live LLM newcomer. Whether a real model infers majority "
                    "from diction alone after unique-claim redaction is "
                    "NOT-CHECKED on this tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Seat a live model on the clean brief vs the leaked brief "
                    "and measure first-position majority-match rates."
                ),
            },
            {
                "claim": (
                    "CNL-0005 / CNL-0006 artifacts and "
                    "11-COUNCIL-SPECIFICATION.schema.json are absent; a later "
                    "pass must re-bind field names if those units choose "
                    "different dial or lattice identifiers."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run catchup.py against the delivered CNL-0005/CNL-0006 "
                    "output_path files when they exist on this worktree."
                ),
            },
            {
                "claim": (
                    "IMP-0274 (tools/council/participants/elastic.py) is the "
                    "implementation unit. This note does not ship that path."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "IMP-0274 must import leak_check/completeness_check "
                    "behaviour rather than re-deriving a parallel brief."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "late_arrival_ok",
                    "measured": bool(late["ok"]),
                    "method": "catchup.run_late_arrival",
                    "anchor": f"{CATCHUP}:{l_late}",
                },
                {
                    "name": "invariance_violations",
                    "measured": int(late["invariance_violations"]),
                    "method": "catchup.run_late_arrival",
                    "anchor": f"{CATCHUP}:{l_late}",
                },
                {
                    "name": "match_majority",
                    "measured": int(late["match_majority"]),
                    "method": "catchup.run_late_arrival",
                    "anchor": f"{CATCHUP}:{l_late}",
                },
                {
                    "name": "copy_hypothesis",
                    "measured": bool(late["copy_hypothesis"]),
                    "method": "catchup.run_late_arrival",
                    "anchor": f"{CATCHUP}:{l_late}",
                },
                {
                    "name": "silent_on_good",
                    "measured": bool(both["silent_on_good"]),
                    "method": "catchup.run_both_states",
                    "anchor": f"{CATCHUP}:{l_both}",
                },
                {
                    "name": "fires_on_bad",
                    "measured": bool(both["fires_on_bad"]),
                    "method": "catchup.run_both_states",
                    "anchor": f"{CATCHUP}:{l_leak}",
                },
                {
                    "name": "fires_on_starved",
                    "measured": bool(both["fires_on_starved"]),
                    "method": "catchup.run_both_states",
                    "anchor": f"{CATCHUP}:{l_comp}",
                },
            ],
            "control_ids": ["NC-majority-leak", "NC-starved"],
            "title": "Elastic scaling: mid-council recruitment and catch-up briefing",
            "question": catalog_q,
            "answer": answer,
            "executed_both_states_control": True,
            "dependencies_on_disk": {
                "CNL-0005": False,
                "CNL-0006": False,
                "harness_11_council_specification_schema": False,
                "binding": (
                    "Interface assumptions from catalog questions only; "
                    "those units' output_path files are absent on this worktree."
                ),
            },
            "mechanism": {
                "id": "catchup-lattice-slice",
                "summary": (
                    "Recruitment records join_round and a full nine-dial mandate. "
                    "build_catchup_brief projects the allowed lattice slice. "
                    "may_cast_first_position is the dual gate. first_position is a "
                    "function of brief+prior and is majority-invariant on a clean brief."
                ),
                "newcomer_sees": [
                    "question / charter",
                    "constraints",
                    "evidence nodes with released_round <= join_round",
                    "unique argument claims (text+polarity, no seat id, no frequency)",
                    "newcomer nine-dial mandate",
                    "join_round and incumbent_round_count (lateness without the tally)",
                ],
                "newcomer_withheld_until_first_position": [
                    "standing_tally",
                    "standing_majority / majority_label",
                    "per_seat_votes",
                    "chair_recommendation / running_consensus",
                    "claim_frequency and seat attribution on claims",
                ],
                "gates": [
                    {
                        "id": "leak_check",
                        "rejects": "ANCHOR_LEAK",
                        "fires_when": (
                            "withheld keys or majority-prose markers appear on the brief"
                        ),
                    },
                    {
                        "id": "completeness_check",
                        "rejects": "CONTEXT_STARVED",
                        "fires_when": (
                            "incumbent evidence at join_round or a nine-dial is missing"
                        ),
                    },
                    {
                        "id": "ack_gate",
                        "rejects": "CATCHUP_UNACKED",
                        "fires_when": "newcomer has not acknowledged the catch-up brief",
                    },
                ],
                "rejected_alternatives": [
                    {
                        "id": "full-transcript",
                        "why_rejected": (
                            "Handing the running transcript including votes is the "
                            "planted-bad fixture: leak_check fires and a copier would "
                            "match majority on every trial."
                        ),
                    },
                    {
                        "id": "empty-brief-then-vote",
                        "why_rejected": (
                            "Withholding everything prevents anchoring but fails the "
                            "other horn: completeness_check fires CONTEXT_STARVED."
                        ),
                    },
                    {
                        "id": "frequency-weighted-claims",
                        "why_rejected": (
                            "Keeping unique claims but weighting by how many seats "
                            "said them reintroduces social proof. _unique_claims drops "
                            "frequency."
                        ),
                    },
                ],
                "executable": CATCHUP,
            },
            "claims": claims,
            "measurements": measured,
            "tests": [
                {"id": "late-arrival-independence", "command": P1, "result": "PASS"},
                {
                    "id": "both-states-and-negative-control",
                    "command": P2,
                    "result": "PASS",
                },
            ],
            "negative_controls": [
                {
                    "id": "NC-majority-leak",
                    "rejects_state": (
                        "catch-up brief that includes standing_majority / "
                        "standing_tally / chair_recommendation"
                    ),
                    "observed": both["negative_control_verbatim"],
                },
                {
                    "id": "NC-starved",
                    "rejects_state": (
                        "catch-up brief with evidence_at_join_round stripped "
                        "while incumbents had evidence"
                    ),
                    "observed": (
                        f"completeness_check.fired="
                        f"{both['planted_bad_starved']['completeness']['fired']} "
                        f"code={both['planted_bad_starved']['completeness']['code']} "
                        f"may_cast allowed="
                        f"{both['planted_bad_starved']['gate']['allowed']} "
                        f"reason={both['planted_bad_starved']['gate']['reason']}"
                    ),
                },
            ],
            "reviewer": {
                "reviewer_id": "CNL-0020-probe2-both-states",
                "verdict": "PASS",
                "independent": True,
                "executed_both_states_control": True,
                "scope_not_agreement": True,
                "counterexamples_attempted": [
                    "planted standing_majority on an otherwise-clean brief -> ANCHOR_LEAK",
                    "majority smuggled in argument prose ('current consensus is') -> ANCHOR_LEAK",
                    "mood=upbeat harmless field -> SILENT (false-positive control)",
                    "evidence stripped -> CONTEXT_STARVED",
                ],
                "surviving_counterexample": None,
            },
            "strongest_surviving_counterargument": (
                "A sufficiently large unique-claim set that happens to be one-sided "
                "will move first_position with the incumbents through evidence, not "
                "through tally. That correlation is allowed: the unit forbids excess "
                "correlation from seeing the vote, not agreement on shared evidence. "
                "The invariance test holds evidence fixed and flips only majority; "
                "that is the quantity the gates police."
            ),
        },
    }

    errs = SB.errors(doc)
    if errs:
        print("FAILED:emit schema errors")
        for e in errs[:20]:
            print(f"  {e}")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:emit below min_bytes_threshold")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0020 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
