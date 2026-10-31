{
  "answer": "Two ideas are the SAME idea when they share a canonical mechanism key (action|object), or when token-set Jaccard over title+body is >= 0.50. Lexical Jaccard on this fixture fires at 0.9259\u20130.9630 on exact_rename / paraphrase / one_parameter_fork and at 0.0167 on a full rewrite \u2014 the same band as a genuinely distinct decoy (0.0222). The second signal is therefore NOT another lexical overlap score (char-3gram Jaccard on the rewrite is 0.1119, still below 0.50) and NOT an embedding cosine (no embedding runtime on this worktree; NOT-CHECKED). It is equality of an authored canonical mechanism key whose parameter slot is excluded, so a one-parameter fork does not mint a new idea. Pairwise AND of the two signals is the wrong gate: it misses the rewrite (caught_by_and_gate=False). The count that may bind unique_ideas in a stopping rule is corroborated_unique = min(lexical_unique, mechanism_unique). On the planted-bad ledger that claims 5 unique wording variants, corroborated_unique=1 and the gaming check FIRES. On six mechanistically distinct ideas it is SILENT. SUCCESS:CNL-0051",
  "both_states": {
    "fired_on_planted_bad": true,
    "known_good": {
      "claimed_unique": 6,
      "corroborated_unique": 6,
      "lexical_unique": 6,
      "mechanism_unique": 6,
      "reason": "claimed_unique=6 <= corroborated_unique=6",
      "verdict": "SILENT"
    },
    "known_good_verbatim": "KNOWN_GOOD_VERBATIM {\"claimed_unique\": 6, \"corroborated_unique\": 6, \"fired\": false, \"lexical_unique\": 6, \"mechanism_unique\": 6, \"reason\": \"claimed_unique=6 <= corroborated_unique=6\", \"verdict\": \"SILENT\"}",
    "planted_bad": {
      "claimed_unique": 5,
      "corroborated_unique": 1,
      "lexical_unique": 2,
      "mechanism_unique": 1,
      "reason": "claimed_unique=5 > corroborated_unique=1",
      "verdict": "FIRE"
    },
    "planted_bad_verbatim": "PLANTED_BAD_VERBATIM {\"claimed_unique\": 5, \"corroborated_unique\": 1, \"fired\": true, \"lexical_unique\": 2, \"mechanism_unique\": 1, \"reason\": \"claimed_unique=5 > corroborated_unique=1\", \"verdict\": \"FIRE\"}",
    "silent_on_known_good": true
  },
  "dependency_CNL_0009": {
    "artifact_on_this_worktree": false,
    "declared": true,
    "scope": "CNL-0009 names unique-idea as one of eight targets. This unit supplies the operational unique_ideas counter a stopping expression may bind. It does not inherit a CNL-0009 measurement."
  },
  "detector": {
    "id": "F01",
    "lexical_threshold_a_priori": 0.5,
    "name": "corroborated unique-idea counter",
    "not_checked": [
      {
        "id": "embedding-cosine",
        "reason": "no embedding model or API on this worktree",
        "scope": "NOT-CHECKED"
      }
    ],
    "pair_and_gate_reason": "AND at the pair level requires L to fire, so it cannot catch the full-rewrite class that L is known not to see. AND belongs on the two COUNTS, not on each pair verdict.",
    "pair_and_gate_rejected": true,
    "signals": [
      {
        "blind_spot": "full rewrite of the same mechanism",
        "id": "L",
        "mechanism": "token-set Jaccard over title+body after stoplist; a priori threshold 0.50",
        "role": "collapse exact_rename / paraphrase / one_parameter_fork"
      },
      {
        "blind_spot": "an author who forges a distinct key for the same mechanism; that attack is CNL-0052, not this unit",
        "id": "M",
        "mechanism": "equality of canonical mechanism key action|object; parameter slot excluded from identity",
        "role": "collapse full rewrites and one-parameter forks that lexical overlap either misses or should not mint"
      }
    ],
    "stopping_bind": "unique_ideas in a stopping expression binds only to corroborated_unique = min(lexical_unique, mechanism_unique). A missing mechanism key is fail-closed (cannot increment the corroborated count)."
  },
  "evidence_requirement": "the planted-mutant control is the evidence; report per-mutant-class recall as numbers, and scope the claim to the classes actually planted (an unplanted class is NOT-CHECKED).",
  "negative_control": {
    "on_known_good": "claimed_unique=6 <= corroborated_unique=6",
    "state_meant_to_reject": "a ledger of wording variants of one mechanism that claims each variant as a unique idea (planted-bad, claimed_unique=5)",
    "verbatim": "NEGATIVE_CONTROL_VERBATIM state_meant_to_reject=planted-bad-claimed-unique-inflated-by-wording-variants; check_does=FIRE because claimed_unique=5 > corroborated_unique=1; on_known_good=SILENT because claimed_unique=6 <= corroborated_unique=6",
    "what_the_check_does": "FIRES because claimed_unique exceeds corroborated_unique; verbatim reason: claimed_unique=5 > corroborated_unique=1"
  },
  "output_schema": "command-center/schema/council-detector-spec.schema.json",
  "planted_mutant_control": {
    "decoy": {
      "caught_as_duplicate": false,
      "id": "D-distinct",
      "jaccard": 0.022222
    },
    "measured_jaccard_bands": {
      "full_rewrite": 0.016667,
      "genuinely_distinct_decoy": 0.022222,
      "rename_paraphrase_fork": {
        "max": 0.962963,
        "min": 0.925926
      }
    },
    "per_class_recall": [
      {
        "caught": 1,
        "class": "exact_rename",
        "planted": 1,
        "recall": 1.0,
        "scope": "planted-on-this-fixture"
      },
      {
        "caught": 1,
        "class": "full_rewrite",
        "planted": 1,
        "recall": 1.0,
        "scope": "planted-on-this-fixture"
      },
      {
        "caught": 1,
        "class": "one_parameter_fork",
        "planted": 1,
        "recall": 1.0,
        "scope": "planted-on-this-fixture"
      },
      {
        "caught": 1,
        "class": "paraphrase",
        "planted": 1,
        "recall": 1.0,
        "scope": "planted-on-this-fixture"
      },
      {
        "caught": 0,
        "class": "genuinely_distinct",
        "must": "NOT-merge",
        "planted": 1,
        "recall": 0.0,
        "scope": "planted-on-this-fixture"
      }
    ],
    "rows": [
      {
        "caught_as_duplicate": true,
        "caught_by_and_gate": true,
        "char3_jaccard": 0.963636,
        "class": "exact_rename",
        "jaccard": 0.962963,
        "lexical_hit": true,
        "mechanism_hit": true,
        "mutant_id": "A-rename"
      },
      {
        "caught_as_duplicate": true,
        "caught_by_and_gate": true,
        "char3_jaccard": 0.897778,
        "class": "paraphrase",
        "jaccard": 0.925926,
        "lexical_hit": true,
        "mechanism_hit": true,
        "mutant_id": "A-paraphrase"
      },
      {
        "caught_as_duplicate": true,
        "caught_by_and_gate": true,
        "char3_jaccard": 0.967742,
        "class": "one_parameter_fork",
        "jaccard": 0.962963,
        "lexical_hit": true,
        "mechanism_hit": true,
        "mutant_id": "A-fork"
      },
      {
        "caught_as_duplicate": true,
        "caught_by_and_gate": false,
        "char3_jaccard": 0.111857,
        "class": "full_rewrite",
        "jaccard": 0.016667,
        "lexical_hit": false,
        "mechanism_hit": true,
        "mutant_id": "A-rewrite"
      }
    ],
    "scope": "recall reported only for classes actually planted in command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
    "unplanted_classes": [
      "embedding-near-duplicate",
      "cross-language-translation",
      "partial-overlap-blend"
    ]
  },
  "question": "What deduplication mechanism decides that two ideas are the SAME idea \u2014 and given that lexical Jaccard was measured to fire at 0.93\u20131.00 on renames but cannot see a full rewrite, what second mechanically different signal must corroborate the count before it gates a stopping rule?",
  "report": {
    "control_ids": [
      "probe1_mutant_recall",
      "probe2_both_states"
    ],
    "kind": "council-detector-spec",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
        "measured": 0.925926,
        "method": "token-set Jaccard over title+body after stoplist",
        "name": "lexical_jaccard_rename_paraphrase_fork_min"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0051/fixtures/corpus.json",
        "measured": 0.016667,
        "method": "token-set Jaccard over title+body after stoplist",
        "name": "lexical_jaccard_full_rewrite"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0051/counter.py",
        "measured": 1,
        "method": "min(lexical_unique, mechanism_unique)",
        "name": "planted_bad_corroborated_unique"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0051/counter.py",
        "measured": 6,
        "method": "min(lexical_unique, mechanism_unique)",
        "name": "known_good_corroborated_unique"
      }
    ]
  },
  "reviewer": {
    "independent": true,
    "method": "R1 reloads fixtures and reruns F01. R2 uses a second tokenizer (alnum, no stoplist) and raw action|object string equality. Duplicate verdicts must agree. Unique counts recounted from keys: planted-bad 1, known-good 6.",
    "recount_agrees": true,
    "reviewer_id": "CNL-0051-independent-recount",
    "verdict": "PASS"
  },
  "schema": {
    "catalog_schema": "command-center/schema/council-detector-spec.schema.json",
    "catalog_schema_note": "shim $ref to ast-integrate.invalid is not resolved on this worktree (jsonschema 4.10.3 RefResolver). No ADV rebuild.",
    "engine": "jsonschema.Draft7Validator+local-contract",
    "errors": [],
    "path": "command-center/schema/council-detector-spec.schema.json",
    "validated": true
  },
  "sentinel": "SUCCESS:CNL-0051",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0051/probe1_mutant_recall.py",
      "exit_code": 0,
      "id": "probe1_mutant_recall",
      "result": "PASS",
      "stdout": "probe=probe1_mutant_recall unit=CNL-0051\nparent=A lexical_threshold=0.5\nMUTANT_CLASS_TABLE\nCLASS exact_rename id=A-rename jaccard=0.962963 char3=0.963636 lexical_hit=True mechanism_hit=True caught=True and_gate=True\nCLASS paraphrase id=A-paraphrase jaccard=0.925926 char3=0.897778 lexical_hit=True mechanism_hit=True caught=True and_gate=True\nCLASS one_parameter_fork id=A-fork jaccard=0.962963 char3=0.967742 lexical_hit=True mechanism_hit=True caught=True and_gate=True\nCLASS full_rewrite id=A-rewrite jaccard=0.016667 char3=0.111857 lexical_hit=False mechanism_hit=True caught=True and_gate=False\nDECOY id=D-distinct jaccard=0.022222 char3=0.116883 lexical_hit=False mechanism_hit=False caught=False\nPER_CLASS_RECALL\nRECALL class=exact_rename planted=1 caught=1 recall=1.0\nRECALL class=full_rewrite planted=1 caught=1 recall=1.0\nRECALL class=one_parameter_fork planted=1 caught=1 recall=1.0\nRECALL class=paraphrase planted=1 caught=1 recall=1.0\nRECALL class=genuinely_distinct planted=1 caught=0 recall=0.0 (must NOT merge)\nUNPLANTED_CLASSES=embedding-near-duplicate,cross-language-translation,partial-overlap-blend => NOT-CHECKED\nLEXICAL_BLINDSPOT full_rewrite jaccard=0.016667 (below 0.5); char3_jaccard=0.111857 still lexical; pairwise AND would MISS this class; mechanism key catches it\nBANDS rename/paraphrase/fork jaccard in [0.9259, 0.9630] rewrite=0.0167 decoy=0.0222\nSUCCESS:CNL-0051-probe1 planted-mutant recall"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0051/probe2_both_states.py",
      "exit_code": 0,
      "id": "probe2_both_states",
      "result": "PASS",
      "stdout": "probe=probe2_both_states unit=CNL-0051\nPLANTED_BAD_VERBATIM {\"claimed_unique\": 5, \"corroborated_unique\": 1, \"fired\": true, \"lexical_unique\": 2, \"mechanism_unique\": 1, \"reason\": \"claimed_unique=5 > corroborated_unique=1\", \"verdict\": \"FIRE\"}\nKNOWN_GOOD_VERBATIM {\"claimed_unique\": 6, \"corroborated_unique\": 6, \"fired\": false, \"lexical_unique\": 6, \"mechanism_unique\": 6, \"reason\": \"claimed_unique=6 <= corroborated_unique=6\", \"verdict\": \"SILENT\"}\nBOTH_STATES fired_on_bad=True silent_on_good=True\nNEGATIVE_CONTROL_VERBATIM state_meant_to_reject=planted-bad-claimed-unique-inflated-by-wording-variants; check_does=FIRE because claimed_unique=5 > corroborated_unique=1; on_known_good=SILENT because claimed_unique=6 <= corroborated_unique=6\nREVIEWER_RECOUNT planted_bad_keys=1 known_good_keys=6 r1_corroborated_bad=1 r1_corroborated_good=6 r2_tokenizer_agrees=True independent=True\nSUCCESS:CNL-0051-probe2 both-states and independent recount"
    }
  ],
  "title": "Semantic unique-idea counter: the anti-gaming core",
  "ts": "2026-08-25T00:55:05Z",
  "unit_id": "CNL-0051"
}
