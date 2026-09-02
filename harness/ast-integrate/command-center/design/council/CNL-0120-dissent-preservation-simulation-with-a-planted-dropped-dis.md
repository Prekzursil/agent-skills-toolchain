{
  "answer": "YES: the single scripted dissent survives intact synthesis (GREEN); planting a drop turns the same check RED. A nonempty synthesis dummy stays GREEN in both states and therefore measures nothing. Negative control (verbatim): planted drop fires RED with lost_claim_ids=[D-CNL0120-01], token_present=false, generic_phrase_only=true. SUCCESS:CNL-0120",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0120-dissent-preservation-simulation-with-a-planted-dropped-dis.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-simulation-spec.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0120/harness.py",
      "role": "harness"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0120/preserve.py",
      "role": "check"
    }
  ],
  "both_states": {
    "intact": {
      "counterexample_present": true,
      "fired": false,
      "lost_claim_ids": [],
      "recount_lost": [],
      "token_present": true,
      "vacuous_nonempty": true,
      "verdict": "GREEN"
    },
    "planted_drop": {
      "counterexample_present": false,
      "fired": true,
      "generic_phrase_only": true,
      "lost_claim_ids": [
        "D-CNL0120-01"
      ],
      "recount_lost": [
        "D-CNL0120-01"
      ],
      "token_present": false,
      "vacuous_nonempty": true,
      "verdict": "RED"
    }
  },
  "claim_under_test": "A claim-id set-difference plus token/counterexample check is GREEN on an intact one-dissent synthesis and RED when that dissent is planted-dropped from synthesis only; a nonempty-synthesis dummy stays green in both states.",
  "cloud_ok": false,
  "dependency_status": {
    "CNL-0070": "absent \u2014 minority-report attachment implemented locally",
    "CNL-0097": "absent \u2014 lost-dissent set-diff implemented locally",
    "CNL-0117": "absent \u2014 unit-local scripted harness used"
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0120/fixtures/council.json:30",
      "claim": "Fixture encodes exactly one NO vote with claim_id, token and counterexample.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0120/harness.py:104",
      "claim": "Planted drop strips minority_report and dissent residue from synthesis only.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0120/preserve.py:72",
      "claim": "Preservation check fires on lost claim-id or missing token/counterexample.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0120/recount.py:32",
      "claim": "Independent recount recomputes lost ids without calling preserve.check.",
      "verdict": "CONFIRMED"
    }
  ],
  "min_bytes_threshold": 4096,
  "negative_control": {
    "check_does": "FIRES; verdict=RED; lost_claim_ids=[D-CNL0120-01]; token_present=false; counterexample_present=false; generic_phrase_only=true",
    "state_meant_to_reject": "synthesis with the recorded dissent stripped and only the generic phrase 'Dissent was considered.' left",
    "verbatim": "{\"counterexample_present\": false, \"fired\": true, \"generic_phrase_only\": true, \"lost_claim_ids\": [\"D-CNL0120-01\"], \"reason\": \"lost-or-stripped\", \"token_present\": false, \"verdict\": \"RED\"}"
  },
  "output_schema": "command-center/schema/council-simulation-spec.schema.json",
  "output_schema_resolution": {
    "declared": "command-center/schema/council-simulation-spec.schema.json",
    "fallback": "local-structural",
    "reason": "command-center/schema/council-simulation-spec.schema.json is a $ref shim to ast-integrate.invalid; jsonschema 4.10 raises RefResolutionError (no network id). Local schema still rejects garbage and requires both-states polarity.",
    "resolved": false
  },
  "question": "Given a scripted council containing exactly one dissent, does that dissent survive into the synthesis \u2014 and does the check FAIL when the dissent is deliberately removed?",
  "required_fix": null,
  "reviewer": {
    "independent": true,
    "re_ran_both_states": true,
    "reviewer_id": "CNL-0120-probe2-independent-recount",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0120",
  "simulation": {
    "dissent": {
      "claim_id": "D-CNL0120-01",
      "counterexample": "Writer A commits k=1; Writer B overwrites k=1 without invalidating Reader C cached v0.",
      "participant_id": "skeptic",
      "token": "CNL0120-DISSENT-TOKEN-A7F3"
    },
    "dissent_count": 1,
    "fixture": "command-center/p2-wave/probes/CNL-0120/fixtures/council.json",
    "harness": "command-center/p2-wave/probes/CNL-0120/harness.py",
    "note": "CNL-0117 / CNL-0070 / CNL-0097 artifacts are absent on this worktree. This unit ships a local scripted harness and preservation check so the simulation is runnable here."
  },
  "state": "SUCCESS",
  "strongest_surviving_counterargument": "A synthesis could keep the token and the counterexample string while gutting the surrounding argument. This check would still go GREEN. That is a remaining substance-vs-presence gap (ADV-0116 class 2), not a reason to skip the planted-drop control, which this unit does run.",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0120/probe1_intact_green.py",
      "id": "intact-green",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0120/probe2_planted_drop.py",
      "id": "planted-drop-red",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0120/probe2_planted_drop.py",
      "id": "negative-control-verbatim",
      "result": "PASS"
    }
  ],
  "title": "Dissent-preservation simulation with a planted dropped dissent",
  "ts": "2026-08-25T00:55:56Z",
  "unit_id": "CNL-0120",
  "vacuous_control": {
    "check": "synthesis nonempty AND decision string present",
    "intact": "GREEN",
    "measures_nothing": true,
    "planted_drop": "GREEN"
  },
  "verdict": "YES: the single scripted dissent survives intact synthesis (GREEN); planting a drop turns the same check RED."
}
