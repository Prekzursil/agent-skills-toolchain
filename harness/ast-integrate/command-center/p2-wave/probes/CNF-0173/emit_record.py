#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0173.json (confirmation record)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import scenarios as S  # noqa: E402

OUT = "command-center/receipts/CNF-0173.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0173/probe1_confirmer_unanimity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0173/probe2_both_states_siblings.py"
)
QUESTION = (
    "Question: does suspiciously fast unanimity actually trigger blind "
    "re-evaluation, forced dissent or independent-critic recruitment "
    "(spec:10944) when the scenario is written by someone who did not "
    "build the detector?"
)


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fingerprint(label: str, path: Path) -> dict:
    sha = digest_file(path)
    return {
        "id": label,
        "path": path.relative_to(REPO).as_posix(),
        "sha256": sha,
        "fingerprint": hashlib.sha256(f"{label}:{sha}".encode("utf-8")).hexdigest(),
    }


def main() -> int:
    for sc in S.confirmer_pack():
        S.assert_not_reused(sc)

    live = H.bind_live()
    pack = {sc["id"]: H.evaluate_oracle(sc) for sc in S.confirmer_pack()}
    seawall = pack["cnf0173-seawall-clone-panel"]
    harbor = pack["cnf0173-harbor-after-briefs"]
    slow = pack["cnf0173-role-clone-slow"]
    ideas = pack["cnf0173-hundred-echo-ideas"]
    reviewer = pack["cnf0173-reviewer-ferry-snap"]

    sweep = []
    for vr in range(1, 6):
        for briefs in (0, 1, 3):
            sc = S.clone_at_vote_round(vr, briefs)
            ev = H.evaluate_oracle(sc)
            sweep.append(
                {
                    "id": sc["id"],
                    "first_vote_round": vr,
                    "distinct_briefs": briefs,
                    "instant_unanimity_fired": bool(
                        ev["instant_unanimity"]["fired"]
                    ),
                }
            )
    fire_knee = [
        row
        for row in sweep
        if row["distinct_briefs"] == 0 and row["instant_unanimity_fired"]
    ]
    silent_knee = [
        row
        for row in sweep
        if row["distinct_briefs"] == 0 and not row["instant_unanimity_fired"]
    ]
    starts_firing_at = (
        min(r["first_vote_round"] for r in fire_knee) if fire_knee else None
    )

    obs = seawall["instant_unanimity"].get("observable") or {}
    live_fired = bool(live.get("any_live_control_fired"))
    live_present = bool(live.get("any_module_present"))

    # Primary question is about the LIVE runtime, not the confirmer oracle.
    if live_fired:
        verdict = "CONFIRMED"
        residual = (
            "Live antifail module fired on the confirmer-authored seawall "
            "scenario. Residual: confirm the same named observable on a "
            "third vendor's scenario pack."
        )
    elif live_present and not live_fired:
        verdict = "REFUTED"
        residual = (
            "A live antifail module is present but did not fire on the "
            "confirmer-authored seawall clone panel. The detector is fitted "
            "to its author's fixture or is inert."
        )
    else:
        verdict = "REFUTED"
        residual = (
            "tools/council/antifail/unanimity.py is absent on this worktree. "
            "Zero production controls fired. The confirmer oracle DID trip "
            "spec:10944 on the seawall pack (so the scenario is not vacuous) "
            "and stayed silent on harbor-after-briefs. IMP-0318 is the named "
            "required_fix for a live re-run; this record is not a CONFIRMED "
            "of a detector that does not exist."
        )

    p1 = fingerprint("probe1_confirmer_unanimity", HERE / "probe1_confirmer_unanimity.py")
    p2 = fingerprint("probe2_both_states_siblings", HERE / "probe2_both_states_siblings.py")
    if p1["fingerprint"] == p2["fingerprint"]:
        raise SystemExit("FAILED:CNF-0173 same-probe-rerun fingerprints collided")

    blinding_payload = json.dumps(
        {
            "claim_id": "CNF-0173-live-instant-unanimity",
            "question": QUESTION,
            "scenario_ids": [sc["id"] for sc in S.confirmer_pack()],
            "excluded": [
                "command-center/receipts/IMP-0318.json",
                "command-center/receipts/CNF-0092.json",
                "implementer conclusions",
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    blinding = hashlib.sha256(blinding_payload.encode("utf-8")).hexdigest()

    tests = [
        {
            "id": "both-states-genuine-consensus-silent",
            "result": "PASS"
            if (not harbor["instant_unanimity"]["fired"] and seawall["instant_unanimity"]["fired"])
            else "FAIL",
            "detail": (
                "seawall instant_unanimity fired="
                f"{seawall['instant_unanimity']['fired']}; "
                "harbor-after-briefs fired="
                f"{harbor['instant_unanimity']['fired']}"
            ),
        },
        {
            "id": "trigger-sensitivity-sweep",
            "result": "PASS"
            if starts_firing_at == 1
            and any(r["first_vote_round"] >= 2 and not r["instant_unanimity_fired"] and r["distinct_briefs"] == 0 for r in sweep)
            else "FAIL",
            "starts_firing_at_first_vote_round": starts_firing_at,
            "units": "first_vote_round (with independent_brief_count==0)",
            "sweep": sweep,
        },
        {
            "id": "role-collapse-distinct-from-fast-unanimity",
            "result": "PASS"
            if (
                slow["role_collapse"]["fired"]
                and not slow["instant_unanimity"]["fired"]
                and seawall["instant_unanimity"]["fired"]
            )
            else "FAIL",
            "detail": (
                "slow role_collapse="
                f"{slow['role_collapse']['fired']} instant="
                f"{slow['instant_unanimity']['fired']}"
            ),
        },
        {
            "id": "idea-count-gaming-novelty",
            "result": "PASS"
            if ideas["novelty"]["fired"]
            and int(ideas["novelty"].get("unique_after_dedup") or 0) < 100
            else "FAIL",
            "claimed": ideas["novelty"].get("claimed_unique_ideas"),
            "unique_after_dedup": ideas["novelty"].get("unique_after_dedup"),
        },
        {
            "id": "reviewer-third-scenario-generalises-oracle",
            "result": "PASS" if reviewer["instant_unanimity"]["fired"] else "FAIL",
            "reviewer": "reviewer.anthropic.opus",
            "scenario_id": "cnf0173-reviewer-ferry-snap",
            "live_generalises": live_fired,
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "id": "CNF-0173",
        "unit_id": "CNF-0173",
        "claim_id": "CNF-0173-live-instant-unanimity",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0173",
        "completion_sentinel": "SUCCESS:CNF-0173",
        "verdict": verdict,
        "question": QUESTION,
        "title": (
            "Reproduce the anti-sycophancy trigger from a confirmer-authored "
            "scenario, not the implementer's fixture"
        ),
        "confirmer": {
            "identity": "independent-confirmer.openai.gpt-5-codex",
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "independent-confirmer",
        },
        "reviewer": {
            "reviewer_id": "reviewer.anthropic.opus",
            "vendor": "anthropic",
            "independent": True,
            "scenario_id": "cnf0173-reviewer-ferry-snap",
            "verdict": "oracle-fires-live-absent" if not live_present else "see-live-bind",
        },
        "blinding_attestation_hash": blinding,
        "blinding_attestation": {
            "hash": blinding,
            "payload_sha256": blinding,
            "excluded_implementer_receipts": True,
            "recompute": "sha256(canonical JSON of claim_id+question+scenario_ids+excluded)",
        },
        "source_probe": {
            **p1,
            "command": P1,
            "role": "confirmer-authored fast-unanimity vs live bind",
        },
        "verifier_probe": {
            **p2,
            "command": P2,
            "role": "both-states, sensitivity, role-collapse, novelty",
        },
        "baseline_repro": {
            "method": "import-or-stat tools/council/antifail/unanimity.py then run confirmer seawall scenario",
            "live_module_present": live_present,
            "live_control_fired": live_fired,
            "oracle_control_fired": seawall["instant_unanimity"]["fired"],
        },
        "corrected_repro": {
            "required_fix": "IMP-0318 tools/council/antifail/unanimity.py",
            "note": (
                "A later CONFIRMED requires the live module to fire on "
                "cnf0173-seawall-clone-panel AND stay silent on "
                "cnf0173-harbor-after-briefs. This run is terminal as REFUTED "
                "and is not re-run hoping for CONFIRMED."
            ),
        },
        "rollback_repro": {
            "method": "remove tools/council/antifail/unanimity.py; bind_live any_module_present returns false",
        },
        "regression_diff": {
            "production_controls_fired": live.get("live_controls_that_fired"),
            "oracle_controls_fired_on_seawall": seawall["controls_fired"],
        },
        "discrepancies": [
            {
                "id": "D1-live-absent-vs-spec-10944",
                "kind": "detector-failure",
                "detail": (
                    "Spec:10944 requires suspiciously fast unanimity to trigger "
                    "blind re-evaluation / forced dissent / independent-critic "
                    "recruitment. Live module absent; production observable is none."
                ),
            }
        ]
        if not live_present
        else [],
        "residual_caveat": residual,
        "live_bind": live,
        "named_control_that_fired": (
            (live.get("live_controls_that_fired") or [None])[0]
            if live_fired
            else (
                "instant_unanimity"
                if seawall["instant_unanimity"]["fired"]
                else None
            )
        ),
        "named_control_scope": (
            "live-production" if live_fired else "confirmer-oracle-only"
        ),
        "observable": obs,
        "evidence": [
            {
                "kind": "named-control",
                "control_id": "instant_unanimity",
                "fired_on": "cnf0173-seawall-clone-panel",
                "scope": "confirmer-oracle",
                "observable": obs,
                "note": (
                    "Oracle emitted re-evaluation round "
                    f"{obs.get('reevaluation_round_id')} and recruited "
                    f"{obs.get('recruited_critic')}. This is NOT a live "
                    "IMP-0318 firing."
                ),
            },
            {
                "kind": "live-bind",
                "path": "tools/council/antifail/unanimity.py",
                "present": live_present,
                "fired": live_fired,
            },
            {
                "kind": "both-states",
                "silent_on": "cnf0173-harbor-after-briefs",
                "instant_unanimity_fired": harbor["instant_unanimity"]["fired"],
            },
            {
                "kind": "reviewer-third-scenario",
                "scenario_id": "cnf0173-reviewer-ferry-snap",
                "oracle_fired": reviewer["instant_unanimity"]["fired"],
                "critic": (reviewer["instant_unanimity"].get("observable") or {}).get(
                    "recruited_critic"
                ),
            },
        ],
        "scenarios": pack,
        "tests": tests,
        "failure_classification": []
        if live_fired
        else ["detector-failure"],
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "note_on_schema": (
            "CNF-0129 has not landed confirmation-record.schema.json on this "
            "tree. This record carries the CNF-0129 required fields "
            "(claim_id, confirmer identity+vendor, blinding attestation hash, "
            "baseline_repro, corrected_repro, rollback_repro, regression_diff, "
            "discrepancies, verdict, source_probe, verifier_probe, "
            "residual_caveat). CONFIRMED/REFUTED with empty source_probe is "
            "not representable here: source_probe.sha256 is mandatory."
        ),
        "ts": now,
    }
    if not doc["source_probe"].get("sha256"):
        raise SystemExit("FAILED:CNF-0173 empty source_probe")
    if verdict in {"CONFIRMED", "REFUTED"} and not doc["source_probe"].get("fingerprint"):
        raise SystemExit("FAILED:CNF-0173 unsourced terminal verdict")

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} verdict={verdict}")
    print("SUCCESS:CNF-0173")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
