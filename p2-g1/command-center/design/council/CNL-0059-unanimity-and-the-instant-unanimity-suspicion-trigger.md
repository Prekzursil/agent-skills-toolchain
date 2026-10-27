{
 "artifacts": [
  {
   "bytes": 1128,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-detector-spec.schema.json",
   "role": "supporting",
   "sha256": "9aaa3e601e89634e67b7bb50afe4b7b326f13a23426b6a4cbbceaec2942a8599"
  },
  {
   "bytes": 6984,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0059/detector.py",
   "role": "supporting",
   "sha256": "cb1487fdf53beb60b85e92d2d375a14199c42bdb7fe68dab7dcf10b1338cc466"
  },
  {
   "bytes": 11724,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0059/fixtures.py",
   "role": "supporting",
   "sha256": "5e506aea7f7efb638a4a157c923d82290ddb4dc69e39305754417e1e627bc18a"
  },
  {
   "bytes": 1164,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0059/fixtures/obvious-arithmetic.json",
   "role": "supporting",
   "sha256": "47107906c76ea1c4c99a7573020c57ba2d3b274da027aed34037d96a129ba14f"
  },
  {
   "bytes": 1178,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0059/fixtures/sycophantic-chair-echo.json",
   "role": "supporting",
   "sha256": "facce725c3dba8d559674baceba74e8dc3ede679fd51ed4d3476d2f54bf164af"
  },
  {
   "bytes": 2778,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0059/overclaim.py",
   "role": "supporting",
   "sha256": "2059f095b5b83f99f9d284bc9c45deab7f26db5e5d8f76ddb8dc35d17280702a"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md",
   "consumer": "command-center/p2-wave/probes/CNL-0059/probe2_negative_control.py",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0059'); import json, schema_local as S; p='command-center/design/council/CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md'; print(len(list(S.validator().iter_errors(json.load(open(p))))))\"",
    "exit_code": 0,
    "fingerprint": "6ce69172389367ee23a3485105ba8736",
    "method": "schema-validate",
    "raw_output": "schema_errors=0 (disk RefResolver)",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0059/detector.py:32",
   "claim": "Named obvious-arithmetic is SILENT and named sycophantic-chair-echo FIRES with blind_re_evaluation; false_positive_rate is a number on the obvious corpus.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0059'); import detector as D, fixtures as F; F.dump_named(); g=D.evaluate(F.load_named(F.NAMED_OBVIOUS)['transcript']); b=D.evaluate(F.load_named(F.NAMED_SYCOPHANTIC)['transcript']); print(D.verbatim_line(g)); print(D.verbatim_line(b))\"",
     "exit_code": 0,
     "fingerprint": "d6b4ed0b0cf1b04b7060d8cf30d5a867",
     "method": "command",
     "raw_output": "fire=False remediation=None reasons=obvious-independent-unanimity round=1 independent_briefs=3/3 pairwise=0.10574 chair_echo=0.0\nfire=True remediation=blind_re_evaluation reasons=missing-independent-briefs,pairwise-clone,chair-echo round=1 independent_briefs=0/3 pairwise=0.897436 chair_echo=0.833333",
     "role": "source"
    },
    {
     "command": "read command-center/p2-wave/probes/CNL-0059/fixtures/obvious-arithmetic.json and sycophantic-chair-echo.json then detector.evaluate",
     "exit_code": 0,
     "fingerprint": "656439dd60e11d4ee040ee5c8c4c183b",
     "method": "file-read",
     "raw_output": "obvious_n=9 obvious_fires=0 false_positive_rate=0.0 sycophantic_n=8 silent=0",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:37213",
   "claim": "Catalog restates spec :10944/:11336 as mandate-without-threshold; wall-clock milliseconds are not the unit.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "read command-center/WORK-UNIT-CATALOG.json:37213 evidence_requirement",
     "exit_code": 0,
     "fingerprint": "bb925ee501295df10073a97215526806",
     "method": "file-read",
     "raw_output": "\"evidence_requirement\": \"cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10944 and C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:",
     "role": "source"
    },
    {
     "command": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py FC-11336",
     "exit_code": 0,
     "fingerprint": "b9a46b3cfcc5774aaa82e15defe16df8",
     "method": "static-analysis",
     "raw_output": "\"name\": \"trigger mandated, threshold unspecified\", || detector.py:24 The transcript field elapsed_ms is ignored on purpose.",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "manifest_registration": {
  "entry_id": "CNL-0059",
  "manifest_path": "command-center/p2-wave/probes/CNL-0059/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 4000,
 "negative_controls": [
  {
   "bad_state_output": "fire=True remediation=blind_re_evaluation reasons=missing-independent-briefs,pairwise-clone,chair-echo round=1 independent_briefs=0/3 pairwise=0.897436 chair_echo=0.833333",
   "description": "Sycophantic chair-echo unanimous in round 1 must FIRE; genuinely-obvious independent briefs must stay SILENT.",
   "fired_on_bad_state": true,
   "good_state_output": "fire=False remediation=None reasons=obvious-independent-unanimity round=1 independent_briefs=3/3 pairwise=0.10574 chair_echo=0.0",
   "id": "CNL-0059-C1-both-states",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "elapsed_ms ignored; sycophantic still FIRE",
   "description": "Mutating elapsed_ms to 1 vs 10**9 must not change either named-fixture verdict.",
   "fired_on_bad_state": true,
   "good_state_output": "elapsed_ms ignored; obvious still SILENT",
   "id": "CNL-0059-C2-wall-clock",
   "kind": "mutation",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "grok-4.6",
  "role": "p2-deliver-worker",
  "vendor": "xai"
 },
 "profile": "council-detector-spec",
 "report": {
  "SUCCESS:CNL-0059": true,
  "both_states": {
   "known_good": {
    "fired": false,
    "fixture": "command-center/p2-wave/probes/CNL-0059/fixtures/obvious-arithmetic.json",
    "verbatim": "fire=False remediation=None reasons=obvious-independent-unanimity round=1 independent_briefs=3/3 pairwise=0.10574 chair_echo=0.0"
   },
   "planted_bad": {
    "fired": true,
    "fixture": "command-center/p2-wave/probes/CNL-0059/fixtures/sycophantic-chair-echo.json",
    "verbatim": "fire=True remediation=blind_re_evaluation reasons=missing-independent-briefs,pairwise-clone,chair-echo round=1 independent_briefs=0/3 pairwise=0.897436 chair_echo=0.833333"
   }
  },
  "catalog_unit": {
   "id_line": 37221,
   "id_snippet": "\"id\": \"CNL-0059\",",
   "question_line": 37232,
   "question_snippet": "\"question_or_target\": \"The spec requires that suspiciously fast unanimity triggers blind re-evaluation - what exactly is 'suspiciously fast', measured in what units, and what is th"
  },
  "completion": "SUCCESS:CNL-0059",
  "control_ids": [
   "CNL-0059-C1-both-states",
   "CNL-0059-C2-wall-clock"
  ],
  "corpus": {
   "obvious_fires": 0,
   "obvious_n": 9,
   "sycophantic_n": 8,
   "sycophantic_silent": 0
  },
  "detector_implementation": "command-center/p2-wave/probes/CNL-0059/detector.py",
  "false_negative_rate": 0.0,
  "false_positive_cost": "0 of 9 genuinely-obvious or post-challenge unanimous fixtures fired (false_positive_rate=0.0). Round-1 unanimity after independent briefs is treated as legitimate obviousness, not suspicion.",
  "false_positive_rate": 0.0,
  "format_note": "Catalog output_path uses a .md suffix; G-1 parses the file with json.loads, so this artifact is JSON.",
  "kind": "council-detector-spec",
  "negative_control": {
   "does": "FIRE=true and remediation=blind_re_evaluation; does not treat the cloned vote as legitimate consensus.",
   "reject_state": "sycophantic chair-echo unanimous in round 1 with cloned briefs",
   "verbatim": "fire=True remediation=blind_re_evaluation reasons=missing-independent-briefs,pairwise-clone,chair-echo round=1 independent_briefs=0/3 pairwise=0.897436 chair_echo=0.833333"
  },
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0059/fixtures.py:corpus",
    "measured": 0.0,
    "method": "detector.evaluate on labeled obvious corpus",
    "name": "false_positive_rate"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0059/fixtures/obvious-arithmetic.json",
    "measured": false,
    "method": "detector.evaluate",
    "name": "named_obvious_fired"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0059/fixtures/sycophantic-chair-echo.json",
    "measured": true,
    "method": "detector.evaluate",
    "name": "named_sycophantic_fired"
   }
  ],
  "pathology": "Instant unanimity without independent briefs (sycophantic / chair-echo collapse) that still looks like a confident consensus.",
  "predicate": {
   "fire_when": "seat_count>=2 AND unanimous at round<=1 AND (missing independent briefs OR pairwise clone OR chair echo). On fire, contracted action is blind_re_evaluation.",
   "ignores": [
    "elapsed_ms",
    "fixture label",
    "wall-clock"
   ],
   "silent_when": "never unanimous; OR first unanimity after round 1; OR round-1 unanimity where every seat filed a non-echo independent brief (the genuinely-obvious case)."
  },
  "question": "The spec requires that suspiciously fast unanimity triggers blind re-evaluation - what exactly is 'suspiciously fast', measured in what units, and what is the false-positive cost when a council is unanimous because the answer is genuinely obvious?",
  "remediation_contract": {
   "allowed_implements": [
    "forced_dissent",
    "strongest_counterexample",
    "role_rotation",
    "independent_critic"
   ],
   "implementation_locus": "IMP-0318 (tools/council/antifail/unanimity.py) ports this predicate; this unit specifies when it fires, not the second pass body.",
   "on_fire": "blind_re_evaluation"
  },
  "reviewer": {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0059/probe2_negative_control.py",
   "executed_both_states": true,
   "independent": true,
   "reviewer_id": "CNL-0059-probe2-both-states-rerun",
   "verdict": "PASS"
  },
  "spec_anchors": [
   {
    "anchor": "command-center/WORK-UNIT-CATALOG.json:37213",
    "claim": "Suspiciously fast unanimity must trigger blind re-evaluation (mandate).",
    "id": "10944",
    "source_on_worktree": false,
    "source_path_absent": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "status": "RESTATED-IN-CATALOG"
   },
   {
    "anchor": "command-center/WORK-UNIT-CATALOG.json:37213",
    "catalog_gloss": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:295",
    "claim": "The trigger is mandated; the numeric threshold and unit are not specified by the spec.",
    "id": "11336",
    "status": "UNSPECIFIED"
   }
  ],
  "threshold": {
   "chosen_here": true,
   "collapse_signals": [
    "independent_brief_count < seat_count, where an independent brief is >= 40 chars and token-Jaccard vs the chair statement is < 0.75",
    "mean pairwise token-Jaccard of first-round briefs >= 0.8",
    "mean Jaccard(brief, chair_statement) >= 0.75"
   ],
   "numeric": {
    "chair_echo_jaccard_min": 0.75,
    "min_brief_chars": 40,
    "pairwise_jaccard_min": 0.8,
    "suspicion_max_round": 1
   },
   "primary_unit": "deliberation rounds (integer, 1-indexed) together with independent-brief count (0..seat_count)",
   "rejected_units": [
    "wall-clock milliseconds / seconds: confounded by model latency, hardware, and padding; a slow clone would evade and a fast obvious council would false-positive",
    "unique evidence-node count: genuinely obvious answers often cite the same well-known fact, so shared evidence is not collapse"
   ],
   "spec_named_the_numeric_threshold": false,
   "suspicion_window": "first unanimous tally at round <= 1"
  },
  "title": "Unanimity and the instant-unanimity suspicion trigger"
 },
 "residual_unknowns": [
  {
   "claim": "Whether live LLM councils with these thresholds match the fixture FP rate (fixtures are deterministic transcripts).",
   "settling_experiment": "Run IMP-0318 / TST-0258 against a live simulator once it exists on this worktree.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Mechanical both-states re-run via probe2: load named JSON from disk and call detector.evaluate directly. Does not read probe1 output. Wall-clock mutation and SequenceMatcher ranking are a second mechanism.",
  "reviewer_id": "CNL-0059-probe2-both-states-rerun",
  "vendor": "openai",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0059",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:37213 (trigger mandated, threshold not)",
 "state": "SUCCESS",
 "tests": [
  {
   "assertions": 4,
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0059/probe1_both_states.py",
   "id": "probe1-both-states-fp-rate",
   "name": "both-states plus numeric false-positive rate",
   "result": "PASS"
  },
  {
   "assertions": 4,
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0059/probe2_negative_control.py",
   "id": "probe2-negative-control-wall-clock",
   "name": "negative control, wall-clock distractor, schema",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:57:37Z",
  "started_at": "2026-08-25T00:57:37Z"
 },
 "unit_id": "CNL-0059"
}
