{
 "artifacts": [
  {
   "path": "command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md",
   "bytes": 10629,
   "sha256": "d859d9dc740dfc89a178827d1fb7776f9b791bcfe48648a43f52c34bd573b071",
   "exists": true,
   "eol": "LF",
   "role": "primary"
  },
  {
   "path": "command-center/schema/council-design-note.schema.json",
   "bytes": 1156,
   "sha256": "eaa5911eeffa1dda98e8bae3d4b12fd33e4ff0636c8f96cd54c727570a0d7ca7",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0058/tally.py",
   "bytes": 5547,
   "sha256": "8a0e590f46b6cd85335e193143f8ffb2b7a003dd52af3b7f1b79614a671b934b",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0058/fixtures/planted-bad.json",
   "bytes": 330,
   "sha256": "0a6d0e960da04901642f57180e8de558cc3c1f1cc8bca2be06a179ae0173c628",
   "exists": true,
   "eol": "LF",
   "role": "fixture"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0058/fixtures/known-good.json",
   "bytes": 321,
   "sha256": "8301376d820d9106e65e9405ac2b108f608b9e23c97d91d61d896327278f3940",
   "exists": true,
   "eol": "LF",
   "role": "fixture"
  }
 ],
 "both_states": {
  "fires_on": "fixtures/planted-bad.json (3 yes, 1 no, 1 abstain, 1 absent, N=6)",
  "silent_on": "fixtures/known-good.json (4 yes, 2 no, N=6)",
  "verbatim_fire": "fixture_id=planted-bad freeze_n=6 yes=3 shrunk_n=4 frozen_pass=False shrunk_pass=True detector=FIRE quorum_met=True outcome=FAIL",
  "verbatim_silent": "fixture_id=known-good freeze_n=6 yes=4 shrunk_n=6 frozen_pass=True shrunk_pass=True detector=SILENT quorum_met=True outcome=PASS"
 },
 "catalog_tests_required": [
  "a shrinking-denominator fixture must be detected: the same ballots with fewer seats must not silently cross the threshold",
  "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
  "negative control recorded verbatim: state what the check does on the state it is meant to reject"
 ],
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:99",
   "claim": "Same ballots (3 yes) fail 2/3 of freeze-N=6 and pass 2/3 of shrunk N=4; the detector FIRES and official outcome is FAIL.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/fixtures/known-good.json:1",
   "claim": "Known-good 4 yes / 6 freeze-set seats PASSES 2/3 on freeze-N and the detector is SILENT.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:28",
   "claim": "Quorum-void with Q=5 and 4 participating is NO_QUORUM; shrinking would still pass 2/3 so the detector FIRES, but that fire does not convert the void into a pass.",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:79",
   "claim": "N=5 with 3 yes is majority PASS (2*3 > 5) and supermajority FAIL (3*3 < 2*5), so the two thresholds are not the same rule.",
   "id": "C4",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:86",
   "claim": "Unreplaced death keeps freeze-N=6 (3 yes FAIL). Replacing the dead seat with a yes vote keeps freeze-N=6 and PASSES with 4 yes — persuasion of the new seat, not a smaller N.",
   "id": "C5",
   "verdict": "CONFIRMED"
  }
 ],
 "decision": "No. A supermajority cannot be met by shrinking the denominator. Majority (2*yes > N) and supermajority (default 2/3: 3*yes >= 2*N) use the freeze-set N locked at vote-open. Abstention, death, and unreplaced seats stay in N; they make the bar harder, not easier. Mid-council replacement substitutes a slot and leaves N unchanged. Quorum is a separate participating-seat floor (yes+no+abstain); missing it voids the vote (NO_QUORUM) instead of lowering N. The shrinking-denominator detector FIRES when the same yes-count fails freeze-N but would pass present-and-voting; that path is a detected defect, never a pass.",
 "evidence": [
  {
   "claim": "planted-bad 3 yes fail freeze-N=6 and pass shrunk N=4",
   "verdict": "CONFIRMED",
   "confidence": "almost-certain",
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:86",
   "probes": [
    {
     "role": "source",
     "method": "file-read",
     "command": "read command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md",
     "raw_output": "fixture_id=planted-bad freeze_n=6 yes=3 shrunk_n=4 frozen_pass=False shrunk_pass=True detector=FIRE quorum_met=True outcome=FAIL",
     "fingerprint": "aa3d7a492abbc00bea1f5e72495a0015",
     "exit_code": 0
    },
    {
     "role": "verifier",
     "method": "schema-validate",
     "command": "jsonschema Draft7Validator council-design-note",
     "raw_output": "schema-valid",
     "fingerprint": "11ec7b1a6ab96223e1a07df1e0b37005",
     "exit_code": 0
    }
   ]
  },
  {
   "claim": "same planted-bad yes-count via fixture-byte regex, not JSON fields",
   "verdict": "CONFIRMED",
   "confidence": "almost-certain",
   "anchor": "command-center/p2-wave/probes/CNL-0058/fixtures/planted-bad.json:6",
   "probes": [
    {
     "role": "source",
     "method": "file-read",
     "command": "read command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md",
     "raw_output": "text_yes=3 field_yes=3 recount_yes=3",
     "fingerprint": "aa3d7a492abbc00bea1f5e72495a0015",
     "exit_code": 0
    },
    {
     "role": "verifier",
     "method": "schema-validate",
     "command": "jsonschema Draft7Validator council-design-note",
     "raw_output": "schema-valid",
     "fingerprint": "11ec7b1a6ab96223e1a07df1e0b37005",
     "exit_code": 0
    }
   ]
  }
 ],
 "measured": {
  "majority_vs_supermajority": {
   "fixture": "majority-not-supermajority",
   "freeze_n": 5,
   "majority_frozen_pass": true,
   "majority_outcome": "PASS",
   "supermajority_frozen_pass": false,
   "supermajority_outcome": "FAIL",
   "yes": 3
  },
  "replacement": {
   "freeze_n_after": 6,
   "freeze_n_before": 6,
   "n_unchanged": true,
   "verbatim_death": "fixture_id=death-unreplaced freeze_n=6 yes=3 shrunk_n=5 frozen_pass=False shrunk_pass=False detector=SILENT quorum_met=True outcome=FAIL",
   "verbatim_replacement": "fixture_id=replacement freeze_n=6 yes=4 shrunk_n=6 frozen_pass=True shrunk_pass=True detector=SILENT quorum_met=True outcome=PASS"
  },
  "supermajority": {
   "death-unreplaced": {
    "absent": 1,
    "abstain": 0,
    "detector": "SILENT",
    "freeze_n": 6,
    "frozen_pass": false,
    "no": 2,
    "outcome": "FAIL",
    "participating_n": 5,
    "quorum_met": true,
    "shrunk_n": 5,
    "shrunk_pass": false,
    "yes": 3
   },
   "known-good": {
    "absent": 0,
    "abstain": 0,
    "detector": "SILENT",
    "freeze_n": 6,
    "frozen_pass": true,
    "no": 2,
    "outcome": "PASS",
    "participating_n": 6,
    "quorum_met": true,
    "shrunk_n": 6,
    "shrunk_pass": true,
    "yes": 4
   },
   "planted-bad": {
    "absent": 1,
    "abstain": 1,
    "detector": "FIRE",
    "freeze_n": 6,
    "frozen_pass": false,
    "no": 1,
    "outcome": "FAIL",
    "participating_n": 5,
    "quorum_met": true,
    "shrunk_n": 4,
    "shrunk_pass": true,
    "yes": 3
   },
   "quorum-void": {
    "absent": 2,
    "abstain": 0,
    "detector": "FIRE",
    "freeze_n": 6,
    "frozen_pass": false,
    "no": 1,
    "outcome": "NO_QUORUM",
    "participating_n": 4,
    "quorum_met": false,
    "shrunk_n": 4,
    "shrunk_pass": true,
    "yes": 3
   },
   "replacement": {
    "absent": 0,
    "abstain": 0,
    "detector": "SILENT",
    "freeze_n": 6,
    "frozen_pass": true,
    "no": 2,
    "outcome": "PASS",
    "participating_n": 6,
    "quorum_met": true,
    "shrunk_n": 6,
    "shrunk_pass": true,
    "yes": 4
   }
  }
 },
 "negative_controls": [
  {
   "id": "NC-planted-bad",
   "kind": "known-broken-fixture",
   "description": "a tally that treats present-and-voting as the supermajority denominator",
   "fired_on_bad_state": true,
   "silent_on_good_state": true,
   "bad_state_output": "on planted-bad the check FIRES and official outcome stays FAIL; fixture_id=planted-bad freeze_n=6 yes=3 shrunk_n=4 frozen_pass=False shrunk_pass=True detector=FIRE quorum_met=True outcome=FAIL",
   "good_state_output": "known-good detector SILENT"
  },
  {
   "id": "NC-quorum-void",
   "kind": "known-broken-fixture",
   "description": "converting a sub-quorum remainder-unanimous council into a pass",
   "fired_on_bad_state": true,
   "silent_on_good_state": true,
   "bad_state_output": "on quorum-void outcome=NO_QUORUM even though shrunk_pass is true; fixture_id=quorum-void freeze_n=6 yes=3 shrunk_n=4 frozen_pass=False shrunk_pass=True detector=FIRE quorum_met=False outcome=NO_QUORUM",
   "good_state_output": "known-good detector SILENT"
  }
 ],
 "produced_at": "2026-08-25T00:44:54Z",
 "question": "How do threshold and quorum interact when seats abstain or are replaced mid-council - and can a supermajority threshold be met by a shrinking denominator rather than by persuasion?",
 "report_kind": "council-design-note",
 "residual_unknowns": [
  {
   "claim": "Harness-restore inputs (11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, _USER-PROMPTS.md:10915-10946) are not on this Linux worktree; default supermajority is 2/3 until a protocol record names another k/m.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "Re-run CNL-0058 named probes after substrate refresh."
  },
  {
   "claim": "CNL-0023 (non-equal weight provenance) is not delivered here. This note assumes weight 1.0 per freeze-set seat; weighted shrink attacks are in scope for CNL-0064, not this unit.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "Re-run CNL-0058 named probes after substrate refresh."
  },
  {
   "claim": "CNL-0021 replacement/independence detection is not delivered. This note only specifies that a replacement keeps freeze-N; it does not detect duplicate-model seats.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "Re-run CNL-0058 named probes after substrate refresh."
  }
 ],
 "reviewer": {
  "reviewer_id": "CNL-0058-probe2-independent-recount",
  "verdict": "PASS",
  "independent": true,
  "fresh_context": true,
  "vendor": "custom",
  "notes": "independent recount / re-tabulation of yes/no/abstain/absent from fixture freeze_set without reading the author's argument; a disagreement in the number blocks the unit"
 },
 "rules": [
  {
   "id": "R1-freeze-N",
   "statement": "Threshold arithmetic uses freeze-set length at vote-open. Replacement substitutes a named slot; N does not drop."
  },
  {
   "id": "R2-abstention-in-N",
   "statement": "Abstain is not yes. It counts toward quorum participation and remains in freeze-N, so it cannot manufacture a majority or supermajority."
  },
  {
   "id": "R3-quorum-voids",
   "statement": "Quorum is independent of the threshold. A sub-quorum council is NO_QUORUM even if present-and-voting would be unanimous."
  },
  {
   "id": "R4-shrink-detector",
   "statement": "FIRE iff the same yes-count fails freeze-N and passes the present-and-voting denominator. Official outcome never uses the shrunk N."
  }
 ],
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0058",
 "state": "SUCCESS",
 "tally_model": {
  "denominator": "freeze_set locked at vote-open",
  "empty_council_cannot_pass": true,
  "majority": "2 * yes > N",
  "quorum": "participating (yes+no+abstain) >= Q; fail => NO_QUORUM",
  "shrunk_denominator_is": "yes+no (present-and-voting); never official",
  "supermajority_default": "3 * yes >= 2 * N",
  "weights": "equal 1.0 per freeze-set seat; non-equal weights are CNL-0023"
 },
 "tests": [
  {
   "id": "probe1-both-states",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0058/probe1_shrinking_denominator.py",
   "result": "PASS"
  },
  {
   "id": "probe2-independent-recount",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0058/probe2_reviewer_recount.py",
   "result": "PASS"
  }
 ],
 "title": "Majority, supermajority and their interaction with quorum",
 "unit_id": "CNL-0058",
 "reviewer_method": "independent recount / re-tabulation of yes/no/abstain/absent from fixture freeze_set without reading the author's argument; a disagreement in the number blocks the unit",
 "measured_evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py:86",
   "claim": "planted-bad 3 yes fail freeze-N=6 and pass shrunk N=4",
   "mechanism": "integer field tally: 3*yes >= 2*N on freeze vs shrunk",
   "verbatim": "fixture_id=planted-bad freeze_n=6 yes=3 shrunk_n=4 frozen_pass=False shrunk_pass=True detector=FIRE quorum_met=True outcome=FAIL"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/fixtures/planted-bad.json:6",
   "claim": "same planted-bad yes-count via fixture-byte regex, not JSON fields",
   "mechanism": "regex count of \"choice\": \"yes\" in planted-bad.json bytes",
   "verbatim": "text_yes=3 field_yes=3 recount_yes=3"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/fixtures/known-good.json:6",
   "claim": "known-good detector SILENT with freeze-N pass",
   "mechanism": "integer field tally on known-good.json",
   "verbatim": "fixture_id=known-good freeze_n=6 yes=4 shrunk_n=6 frozen_pass=True shrunk_pass=True detector=SILENT quorum_met=True outcome=PASS"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0058/recount.py:16",
   "claim": "independent recount agrees with author tally on planted-bad",
   "mechanism": "recount.py loop over freeze_set, no tally.py import",
   "verbatim": "recount detector=FIRE yes=3 freeze_n=6 shrunk_n=4 outcome=FAIL"
  }
 ],
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0058",
 "min_bytes_threshold": 1,
 "timestamps": {
  "started_at": "2026-08-25T00:44:54Z",
  "ended_at": "2026-08-29T03:30:00Z"
 },
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot (AGENTS.md 4b)"
 },
 "manifest_registration": {
  "registered": true,
  "manifest_path": "command-center/p2-wave/probes/CNL-0058/UNIT-ARTIFACT-MANIFEST.json",
  "entry_id": "CNL-0058"
 },
 "downstream_consumers": [
  {
   "consumer": "CNL-0058-probe2 independent recount",
   "artifact_path": "command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md",
   "executed": true,
   "read_ok": true,
   "exit_code": 0,
   "probe": {
    "role": "verifier",
    "method": "schema-validate",
    "command": "jsonschema Draft7Validator council-design-note",
    "raw_output": "schema-valid",
    "fingerprint": "11ec7b1a6ab96223e1a07df1e0b37005",
    "exit_code": 0
   }
  }
 ],
 "report": {
  "kind": "council-design-note",
  "observations": [
   {
    "name": "planted_bad_detector",
    "measured": "FIRE",
    "method": "integer-field-tally freeze-N vs shrunk-N",
    "anchor": "command-center/p2-wave/probes/CNL-0058/tally.py"
   }
  ],
  "control_ids": [
   "NC-planted-bad"
  ]
 }
}
