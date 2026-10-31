{
  "unit_id": "CNL-0055",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0055",
  "completion_sentinel": "SUCCESS:CNL-0055",
  "schema_version": 1,
  "report_kind": "council-design-note",
  "title": "Saturation versus quota-filling at the 100-idea target",
  "question": "How does the runtime distinguish REAL idea saturation (the next round adds nothing) from a council padding to hit a declared number - and which of the two should stop the round?",
  "claim_under_test": "A round that adds no Jaccard-unique idea is SATURATION when offered volume does not chase the remaining raw quota, and QUOTA_FILLING when it does. Only SATURATION stops the round. Padding cannot satisfy unique_ideas >= 100.",
  "dependencies_on_this_tree": {
    "CNL-0051": "absent; local token-Jaccard unique counter is the stand-in, scoped NOT-CHECKED as a delivery of CNL-0051",
    "CNL-0078": "absent; stopping expression unique_ideas >= 100 is treated as the named quota, not parsed by an A10 grammar"
  },
  "declared_signal": {
    "name": "unique-yield-and-quota-chase",
    "signal1": {
      "id": "jaccard-unique-yield",
      "mechanism": "token-set Jaccard clustering at 0.80; Y = unique_after - unique_before",
      "duplicate_threshold": 0.8,
      "anchor": "command-center/p2-wave/probes/CNL-0055/detector.py:6"
    },
    "signal2": {
      "id": "raw-volume-versus-quota-gap",
      "mechanism": "volume_chases_quota if raw_gap > 0 and offered_n >= PADDING_VOLUME_FLOOR and offered_n >= min(raw_gap, floor). Does not read Jaccard.",
      "padding_volume_floor": 20,
      "anchor": "command-center/p2-wave/probes/CNL-0055/detector.py:11"
    },
    "conjunction": "QUOTA_FILLING iff Y==0 AND volume_chases_quota; SATURATION iff Y==0 AND NOT volume_chases_quota; CONTINUE iff Y>0",
    "independent_reviewer_method": "char-trigram Jaccard clustering at 0.75, same conjunction"
  },
  "which_stops_the_round": {
    "stops": "SATURATION",
    "does_not_stop": "QUOTA_FILLING",
    "satisfy_quota_from_padding": false,
    "rationale": "Saturation means the next round adds nothing unique; further rounds waste budget. Quota-filling means the council is dumping near-duplicates to close a declared count. That dump must not stop the round and must not satisfy unique_ideas >= 100. Early saturation (unique_after < 100) still stops, but the quota arm stays unsatisfied."
  },
  "both_states": {
    "padding_decision": "QUOTA_FILLING",
    "padding_stop_round": false,
    "padding_unique_yield": 0,
    "padding_naive_yield": 60,
    "padding_unique_before": 40,
    "padding_unique_after": 40,
    "padding_volume_chases_quota": true,
    "saturated_decision": "SATURATION",
    "saturated_stop_round": true,
    "saturated_unique_yield": 0,
    "saturated_naive_yield": 3,
    "saturated_unique_before": 100,
    "saturated_unique_after": 100,
    "saturated_volume_chases_quota": false,
    "told_apart": true
  },
  "fixtures": {
    "padding": {
      "path": "command-center/p2-wave/probes/CNL-0055/fixtures/padding.json",
      "ledger_n": 40,
      "offered_n": 60,
      "decision": "QUOTA_FILLING",
      "note": "40 genuine ideas; 60 near-duplicates offered to close the raw count toward 100. Naive exact-string unique rises; Jaccard unique does not."
    },
    "saturated": {
      "path": "command-center/p2-wave/probes/CNL-0055/fixtures/saturated.json",
      "ledger_n": 100,
      "offered_n": 3,
      "decision": "SATURATION",
      "note": "100 genuine unique ideas already in the ledger. Next round offers three restatements (low volume). Next round adds nothing unique."
    },
    "continue": {
      "path": "command-center/p2-wave/probes/CNL-0055/fixtures/continue.json",
      "decision": "CONTINUE",
      "unique_yield": 20,
      "note": "20 genuinely new unique ideas; neither saturation nor padding."
    },
    "early_saturation": {
      "path": "command-center/p2-wave/probes/CNL-0055/fixtures/early_saturation.json",
      "decision": "SATURATION",
      "stop_round": true,
      "satisfy_unique_quota": false,
      "unique_after": 50,
      "note": "Idea space exhausted at 50 unique. Round stops for saturation; unique_ideas >= 100 stays unsatisfied."
    }
  },
  "claims": [
    {
      "id": "C1",
      "claim": "Padding fixture (40 genuine + 60 near-duplicates) is QUOTA_FILLING, stop_round=false, unique_yield=0, naive_yield=60.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0055/detector.py:124"
    },
    {
      "id": "C2",
      "claim": "Saturated fixture (100 genuine + 3 restatements) is SATURATION, stop_round=true, unique_yield=0.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0055/detector.py:131"
    },
    {
      "id": "C3",
      "claim": "Only SATURATION stops the round; padding cannot satisfy unique_ideas >= 100.",
      "verdict": "CONFIRMED",
      "anchor": "which_stops_the_round"
    },
    {
      "id": "C4",
      "claim": "CNL-0051 semantic unique counter is delivered on this tree and is what Jaccard yield calls.",
      "verdict": "NOT-CHECKED",
      "anchor": "dependencies_on_this_tree.CNL-0051"
    }
  ],
  "evidence": [
    {
      "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
      "line": 6,
      "kind": "command-verbatim",
      "claim": "Signal 1 (token Jaccard unique yield) classifies padding as QUOTA_FILLING with unique_yield=0 and naive_yield=60.",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0055/detector.py --fixture padding",
      "verbatim_output": "{\n  \"decision\": \"QUOTA_FILLING\",\n  \"expected_decision\": \"QUOTA_FILLING\",\n  \"fixture\": \"padding\",\n  \"independent_trigram\": {\n    \"decision\": \"QUOTA_FILLING\",\n    \"ledger_n\": 40,\n    \"low_volume\": false,\n    \"naive_after\": 100,\n    \"naive_before\": 40,\n    \"naive_yield\": 60,\n    \"offered_n\": 60,\n    \"padding_ratio\": 1.0,\n    \"quota\": 100,\n    \"raw_gap\": 60,\n    \"reason\": \"marginal unique yield is 0 while offered volume is large enough to close the remaining raw quota gap\",\n    \"satisfy_unique_quota\": false,\n    \"stop_round\": false,\n    \"unique_after\": 40,\n    \"unique_before\": 40,\n    \"unique_fn\": \"unique_trigram\",\n    \"unique_yield\": 0,\n    \"volume_chases_quota\": true\n  },\n  \"methods_agree_on_decision\": true,\n  \"satisfy_unique_quota\": false,\n  \"signal1_jaccard\": {\n    \"decision\": \"QUOTA_FILLING\",\n    \"ledger_n\": 40,\n    \"low_volume\": false,\n    \"naive_after\": 100,\n    \"naive_before\": 40,\n    \"naive_yield\": 60,\n    \"offered_n\": 60,\n    \"padding_ratio\": 1.0,\n    \"quota\": 100,\n    \"raw_gap\": 60,\n    \"reason\": \"marginal unique yield is 0 while offered volume is large enough to close the remaining raw quota gap\",\n    \"satisfy_unique_quota\": false,\n    \"stop_round\": false,\n    \"unique_after\": 40,\n    \"unique_before\": 40,\n    \"unique_fn\": \"unique_jaccard\",\n    \"unique_yield\": 0,\n    \"volume_chases_quota\": true\n  },\n  \"signal2_raw_volume\": {\n    \"naive_yield\": 60,\n    \"offered_n\": 60,\n    \"raw_gap\": 60,\n    \"raw_ledger_n\": 40,\n    \"volume_chases_quota\": true\n  },\n  \"stop_round\": false\n}"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
      "line": 11,
      "kind": "command-verbatim",
      "claim": "Signal 2 (raw volume vs quota gap) is true on padding (offered=60, raw_gap=60) and false on saturated (offered=3, raw_gap=0).",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0055/detector.py --fixture saturated",
      "verbatim_output": "{\n  \"decision\": \"SATURATION\",\n  \"expected_decision\": \"SATURATION\",\n  \"fixture\": \"saturated\",\n  \"independent_trigram\": {\n    \"decision\": \"SATURATION\",\n    \"ledger_n\": 100,\n    \"low_volume\": true,\n    \"naive_after\": 103,\n    \"naive_before\": 100,\n    \"naive_yield\": 3,\n    \"offered_n\": 3,\n    \"padding_ratio\": 1.0,\n    \"quota\": 100,\n    \"raw_gap\": 0,\n    \"reason\": \"next round adds no unique idea and the dump is not a quota chase (offered=3, raw_gap=0)\",\n    \"satisfy_unique_quota\": true,\n    \"stop_round\": true,\n    \"unique_after\": 100,\n    \"unique_before\": 100,\n    \"unique_fn\": \"unique_trigram\",\n    \"unique_yield\": 0,\n    \"volume_chases_quota\": false\n  },\n  \"methods_agree_on_decision\": true,\n  \"satisfy_unique_quota\": true,\n  \"signal1_jaccard\": {\n    \"decision\": \"SATURATION\",\n    \"ledger_n\": 100,\n    \"low_volume\": true,\n    \"naive_after\": 103,\n    \"naive_before\": 100,\n    \"naive_yield\": 3,\n    \"offered_n\": 3,\n    \"padding_ratio\": 1.0,\n    \"quota\": 100,\n    \"raw_gap\": 0,\n    \"reason\": \"next round adds no unique idea and the dump is not a quota chase (offered=3, raw_gap=0)\",\n    \"satisfy_unique_quota\": true,\n    \"stop_round\": true,\n    \"unique_after\": 100,\n    \"unique_before\": 100,\n    \"unique_fn\": \"unique_jaccard\",\n    \"unique_yield\": 0,\n    \"volume_chases_quota\": false\n  },\n  \"signal2_raw_volume\": {\n    \"naive_yield\": 3,\n    \"offered_n\": 3,\n    \"raw_gap\": 0,\n    \"raw_ledger_n\": 100,\n    \"volume_chases_quota\": false\n  },\n  \"stop_round\": true\n}"
    }
  ],
  "tests": [
    {
      "id": "both-states-padding-vs-saturated",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0055/probe1_both_states.py",
      "result": "PASS",
      "note": "Named probe re-run is the G-1 measure; emit records the live in-process classifications above."
    },
    {
      "id": "negative-control-independent-recount",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0055/probe2_negative_control.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "saturation-stop-on-padding",
      "rejects": "SATURATION-stop (stop_round=true) on a quota-filling dump",
      "observed": "SILENT",
      "verbatim": "On the padding fixture the saturation-stop check is SILENT: stop_round=False decision=QUOTA_FILLING."
    },
    {
      "id": "quota-filling-on-saturated",
      "rejects": "QUOTA_FILLING fire on a low-volume exhausted round",
      "observed": "SILENT",
      "verbatim": "On the saturated fixture the quota-filling check is SILENT: decision=SATURATION volume_chases_quota=False."
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0055-probe2-independent-trigram-recount",
    "verdict": "PASS",
    "independent": true,
    "re_ran_both_states": true,
    "scope_not_agreement": true,
    "method": "char-trigram unique counter (threshold 0.75) plus raw-volume quota-chase; must agree with token-Jaccard on both fixtures",
    "padding_trigram_decision": "QUOTA_FILLING",
    "saturated_trigram_decision": "SATURATION"
  },
  "strongest_surviving_counterargument": "A council that emits 20+ genuinely new unique ideas while closing a raw gap looks like volume-chasing on signal 2, but signal 1 Y>0 forces CONTINUE, so honest burst generation is not classified as padding. The remaining risk is a paraphraser that stays just under Jaccard 0.80 (full rewrite of the same mechanism); that class is CNL-0051's planted-mutant set and is NOT-CHECKED here.",
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0055-saturation-versus-quota-filling-at-the-100-idea-target.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "schema"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
      "exists": true,
      "role": "supporting"
    }
  ],
  "produced_by": "command-center/p2-wave/probes/CNL-0055/emit_note.py"
}
