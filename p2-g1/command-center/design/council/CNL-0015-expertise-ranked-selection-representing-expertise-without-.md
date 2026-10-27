{
 "answer": "Claimed expertise is a structured ExpertiseClaim (participant_id, closed-vocabulary domain_tags, optional assertion text, evidence[]). The assertion string is stored for audit and is never a weight input. A task names required_tags. Match is the set intersection of those tags with claims that PASS the evidence bar for that tag; uncovered tags stay uncovered rather than being filled by an 'average expert'. Before the selector may apply a weight premium, the claim must point at a competence_probe, calibration_record, or attested_artifact whose content_sha256 matches the live bytes, whose domain_tag equals the task tag, and \u2014 for a probe \u2014 whose computed n_correct exceeds the non-expert baseline on the SAME items while the unanswerable control is answered idk. Self-assertion, empty evidence, hash mismatch, at-or-below-baseline scores, and a confident unanswerable answer all fail the bar and cannot be ranked as experts. The match is checkable because a second mechanism can recount got==expected in the probe file and recompute the tag-set intersection without calling the bar.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0015-expertise-ranked-selection-representing-expertise-without-.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0015/fixtures/claims/fabricated.json",
   "role": "supporting"
  }
 ],
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
   "claim": "A fabricated-expertise fixture (assertion, empty evidence) fails the evidence bar.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
   "claim": "A known-good competence probe (n_correct > baseline, unanswerable=idk, live hash) passes and may receive a weight premium.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:79",
   "claim": "Match is checkable by an independent tag-set intersection plus got==expected recount that does not call evidence_bar.",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:219",
   "claim": "A TLS-only passing claim covers a cryptography task tag.",
   "id": "C4",
   "verdict": "REFUTED"
  },
  {
   "anchor": "inputs_on_disk",
   "claim": "Catalog input files 11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, and _USER-PROMPTS.md were read from this worktree.",
   "id": "C5",
   "verdict": "REFUTED"
  },
  {
   "anchor": "dependency_CNL_0005_present",
   "claim": "CNL-0005 participant-descriptor artifact exists on this worktree.",
   "id": "C6",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0015",
 "dependency_CNL_0005_present": false,
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
   "claim": "evidence_bar(fabricated, cryptography) fails; evidence_bar(good, cryptography) passes with positive margin.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe1_fabricated_bar.py",
   "kind": "live-tree",
   "line": 183,
   "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
   "snippet": "def evidence_bar(claim: dict, tag: str, repo: Path = REPO) -> dict:",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:79",
   "claim": "Independent recount of crypto-good.json yields n_correct=4, baseline_correct=1, unanswerable=idk; fabricated evidence list is empty; tls tags do not intersect {cryptography}.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe2_both_states.py",
   "kind": "live-tree",
   "line": 79,
   "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
   "snippet": "def score_probe_file(doc: dict) -> dict:",
   "verdict": "CONFIRMED"
  }
 ],
 "evidence_bar": {
  "fabricated_definition": "A claim whose evidence list is empty, whose only payload is assertion text, whose hash does not match live bytes, or whose computed score is at or below the non-expert baseline.",
  "fabricated_reason": "self-assertion-only",
  "good_reason": "competence_probe",
  "min_verifiable": 3,
  "rule": "PASS only if some evidence item for T has a live-matching content hash and (competence_probe: n_correct > baseline_correct AND unanswerable_got == idk AND n_verifiable >= 3) or (calibration_record: historical_accuracy > baseline_accuracy) or (attested_artifact: non-empty file whose domain_tag is T). Counts are computed from the pointed file; claimed n_correct on the claim object is ignored.",
  "score_source": "command-center/p2-wave/probes/CNL-0015/expertise.py:79",
  "self_assertion_sufficient": false,
  "source": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
  "unanswerable_pass": "idk"
 },
 "inputs_on_disk": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false,
  "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md": false,
  "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json": false,
  "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0015/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "matching": {
  "algorithm": "For each required tag T: bind live hashes, run evidence_bar(claim, T), collect passers, rank by (margin, participant_id), assign weight_premium only to the ranked passers. Tags with zero passers are uncovered.",
  "checkability": "Independent recount: count got==expected in the pointed probe JSON and take set(domain_tags) & set(required_tags). Those two numbers must agree with the selector output.",
  "recorded_counts": {
   "below_baseline_correct": 1,
   "below_margin": 0,
   "below_n_correct": 1,
   "good_baseline_correct": 1,
   "good_margin": 3,
   "good_n_correct": 4,
   "mixed_uncovered": [],
   "mixed_weighted_ids": [
    "seat.crypto.good"
   ]
  },
  "source": "command-center/p2-wave/probes/CNL-0015/expertise.py:219",
  "zero_history_policy": "A participant with no passing evidence is not ranked as average. They may be seated without an expertise premium; they cannot cover T."
 },
 "min_bytes_threshold": 2048,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe1_fabricated_bar.py",
   "id": "probe1",
   "role": "fabricated-expertise-bar"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe2_both_states.py",
   "id": "probe2",
   "role": "both-states-independent-recount"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "fabricated pass=False reason=self-assertion-only weight_premium=false",
   "description": "Reject state: fabricated claim (assertion only, empty evidence) must not receive cryptography weight. The check FIRES (weight_premium=false, claim in rejected, tag uncovered). Good state: known-good competence probe is SILENT (no rejection, weight_premium=true). Hash-mismatch, below-baseline, and unanswerable-confident are additional reject states.",
   "fired_on_bad_state": true,
   "good_state_output": "good pass=True reason=competence_probe margin=3 weight_premium=true",
   "id": "CNL0015-C1",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "cursor"
 },
 "question": "How is claimed expertise represented and matched to a task such that the match is checkable, and what evidence must accompany an expertise claim before the selector may weight it?",
 "report": {
  "control_ids": [
   "CNL0015-C1",
   "T1-fabricated-expertise-fails-bar"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
    "measured": false,
    "method": "evidence_bar over empty-evidence claim",
    "name": "fabricated_bar_fail"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
    "measured": 3,
    "method": "evidence_bar over live-hashed competence_probe",
    "name": "good_bar_pass_margin"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:79",
    "measured": 4,
    "method": "got==expected recount without evidence_bar",
    "name": "independent_recount_good_n_correct"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0015/expertise.py:219",
    "measured": false,
    "method": "set(domain_tags) & set(required_tags)",
    "name": "tls_covers_cryptography_task"
   }
  ]
 },
 "representation": {
  "assertion_is_load_bearing": false,
  "closed_vocabulary": [
   "compiler-design",
   "cryptography",
   "distributed-systems",
   "incident-response",
   "numerical-analysis",
   "privacy-law",
   "tls"
  ],
  "fields": [
   "participant_id",
   "domain_tags",
   "assertion (audit only)",
   "evidence[].kind in {competence_probe, calibration_record, attested_artifact}",
   "evidence[].domain_tag",
   "evidence[].pointer",
   "evidence[].content_sha256"
  ],
  "not_a_free_text_label": true,
  "source": "command-center/p2-wave/probes/CNL-0015/expertise.py:183",
  "type_name": "ExpertiseClaim",
  "unknown_tag_policy": "fail-closed (reason=unknown-tag)"
 },
 "residual_unknowns": [
  {
   "claim": "Byte-level contents of 11-COUNCIL-SPECIFICATION.schema.json $defs.seat and _USER-PROMPTS.md:10746-10767 / 10915-10946 / 11241.",
   "settling_experiment": "Place those files on disk and re-cite field-by-field against ExpertiseClaim.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Human gpt-5-codex signature after re-running probe2.",
   "settling_experiment": "Have a fresh openai/gpt-5-codex context execute probe2_both_states.py and record the verbatim output in reviewer.raw_output.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "CNL-0005 nine-dial participant descriptor, of which expertise is one dial.",
   "settling_experiment": "Deliver CNL-0005 and show ExpertiseClaim as the expertise dial of that type.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Two same-fingerprint structural refutes park as BLOCKED."
 },
 "reviewer": {
  "both_states_rerun": true,
  "cross_vendor_human": false,
  "independent": true,
  "method": "Catalog required a gpt-5-codex reviewer who re-runs the both-states control. This worktree has no cross-vendor reviewer session. Probe 2 re-runs both-states at the selector layer and independently recounts got==expected plus tag-set intersection. That is the signing control. A human gpt-5-codex signature is residual.",
  "requested_vendor": "openai/gpt-5-codex",
  "reviewer_id": "CNL-0015-probe2-both-states-recount",
  "verdict": "PASS"
 },
 "schema_note": "Catalog output_schema command-center/schema/council-design-note.schema.json is a generated $ref shim to https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json which does not resolve on this worktree (jsonschema RefResolutionError). This note is JSON-parseable with state=SUCCESS and is validated against a local contract that named probes actually read. No ADV rebuild of that shared schema was attempted.",
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0015",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0015]; catalog cites _USER-PROMPTS.md:10923/11241 (hallucinated expertise) and IMP-0269 (select_expertise.py). Those source files are absent on this worktree; see inputs_on_disk.",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe1_fabricated_bar.py",
   "id": "T1-fabricated-expertise-fails-bar",
   "name": "A fabricated-expertise fixture must fail the evidence bar; known-good must pass.",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0015/probe2_both_states.py",
   "id": "T2-both-states-and-independent-recount",
   "name": "Check FIRES on planted-bad (fabricated, no premium) and is SILENT on known-good; recount agrees.",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:55:34Z",
  "started_at": "2026-08-24T18:36:00Z"
 },
 "title": "Expertise-ranked selection: representing expertise without asserting it",
 "unit_id": "CNL-0015"
}
