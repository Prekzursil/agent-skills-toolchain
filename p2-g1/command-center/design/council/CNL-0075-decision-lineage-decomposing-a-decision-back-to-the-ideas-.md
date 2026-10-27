{
 "answer": "Not on this worktree: no live council runtime, no idea-ledger artifact, and no typed parent pointers for the chain exist on disk. Under the scripted council in probes/CNL-0075/fixtures, a recommendation CAN be decomposed: each sentence may cite only a decision or action_plan id, and a parent-pointer walk must reach at least one idea ledger id. Two walkers (stack chase vs relational join) agreed: the good fixture resolves both sentences to idea.http-cache; an orphan sentence with empty cites fails as s3. The link that is missing TODAY, so the trace breaks even after the other hops are named in the catalog, is option_card->claim: no CNL/IMP unit other than CNL-0075 requires about_option_card_ids, and grepping that field outside this probe is empty. IMP-0339 authors idea->option_card; IMP-0313 authors a graph of claims extracted from turns, not from option cards. Severing about_option_card_ids on the otherwise-good fixture orphans every recommendation sentence (no-idea-reached).",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0075/lineage.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0075/fixtures/good.json",
   "role": "fixture"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0075/fixtures/orphan.json",
   "role": "negative-control"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0075/design-note.schema.json",
   "role": "supporting"
  }
 ],
 "catalog_note_schema": "command-center/schema/council-design-note.schema.json",
 "completion_sentinel": "SUCCESS:CNL-0075",
 "declared_output_schema": "command-center/schema/councilspec.v2.schema.json",
 "decomposition_counts": {
  "good_ideas_s1": [
   "idea.http-cache"
  ],
  "good_ideas_s2": [
   "idea.http-cache"
  ],
  "good_resolved": 2,
  "good_sentences": 2,
  "orphan_ids": [
   "s3"
  ],
  "severed_orphan_ids": [
   "s1",
   "s2"
  ]
 },
 "evidence": [
  {
   "claim": "IMP-0339 is the only CNL/IMP unit that names idea and option card together; idea->option_card is catalog-authored.",
   "line": 16,
   "mechanism": "catalog-needle-scan",
   "path": "command-center/p2-wave/probes/CNL-0075/census.py",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0075/census.py:16",
    "kind": "file_line"
   },
   "snippet": "COUNCIL_UID = re.compile(r\"^(CNL|IMP)-\\d+$\")",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "No CNL/IMP unit other than CNL-0075 names option card and claim together, so option_card->claim is the first unspecified hop.",
   "line": 26,
   "mechanism": "catalog-needle-scan",
   "path": "command-center/p2-wave/probes/CNL-0075/lineage.py",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0075/lineage.py:26",
    "kind": "file_line"
   },
   "snippet": "\"to_kind\": \"claim\"",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "Chase walker and join walker agree: good fixture has 0 orphans; both sentences resolve to idea.http-cache.",
   "line": 131,
   "mechanism": "parent-chase-walk",
   "path": "command-center/p2-wave/probes/CNL-0075/lineage.py",
   "signal": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0075'); import lineage as L; from pathlib import Path; r=L.sentence_report(L.load_council(Path('command-center/p2-wave/probes/CNL-0075/fixtures/good.json'))); print(r['pass'], r['orphan_ids'], r['sentences'][0]['ideas'])\"",
    "kind": "command_output",
    "output": "True [] ['idea.http-cache']"
   },
   "snippet": "def chase_ideas(",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "Negative control: empty-cites sentence s3 fails; good fixture stays silent.",
   "line": 95,
   "mechanism": "relational-join-orphan",
   "path": "command-center/p2-wave/probes/CNL-0075/fixtures/orphan.json",
   "signal": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0075/probe1_decompose.py",
    "kind": "command_output",
    "output": "orphan pass=False sentences=3 resolved=2 orphans=['s3'] s3_reasons=['empty-cites', 'no-idea-reached']"
   },
   "snippet": "\"id\": \"s3\"",
   "verdict": "CONFIRMED"
  }
 ],
 "hop_table": [
  {
   "catalog_authors_cnl_or_imp": [
    "IMP-0339"
   ],
   "child_module": "tools/council/artifacts/option_cards.py",
   "child_module_exists": false,
   "from_kind": "idea",
   "parent_field": "promoted_from_idea_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "option_card"
  },
  {
   "catalog_authors_cnl_or_imp": [],
   "child_module": "tools/council/artifacts/claims.py",
   "child_module_exists": false,
   "from_kind": "option_card",
   "parent_field": "about_option_card_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "claim"
  },
  {
   "catalog_authors_cnl_or_imp": [
    "IMP-0313"
   ],
   "child_module": "tools/council/artifacts/argument_graph.py",
   "child_module_exists": false,
   "from_kind": "claim",
   "parent_field": "cites_claim_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "argument"
  },
  {
   "catalog_authors_cnl_or_imp": [
    "CNL-0087",
    "IMP-0356"
   ],
   "child_module": "tools/council/protocol/vote.py",
   "child_module_exists": false,
   "from_kind": "argument",
   "parent_field": "rests_on_argument_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "vote"
  },
  {
   "catalog_authors_cnl_or_imp": [
    "CNL-0023",
    "CNL-0057",
    "IMP-0306",
    "IMP-0307",
    "IMP-0354",
    "IMP-0361"
   ],
   "child_module": "tools/council/outcomes/lineage_export.py",
   "child_module_exists": false,
   "from_kind": "vote",
   "parent_field": "tally_of_vote_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "decision"
  },
  {
   "catalog_authors_cnl_or_imp": [
    "IMP-0027",
    "IMP-0036",
    "IMP-0335",
    "IMP-0340"
   ],
   "child_module": "tools/council/outcomes/action_plan.py",
   "child_module_exists": false,
   "from_kind": "decision",
   "parent_field": "implements_decision_ids",
   "parent_field_present_on_disk": false,
   "to_kind": "action_plan"
  }
 ],
 "lineage_rules": {
  "chain": [
   "idea",
   "option_card",
   "claim",
   "argument",
   "vote",
   "decision",
   "action_plan"
  ],
  "orphan_if": [
   "empty-cites",
   "dangling-cite",
   "illegal-cite-kind",
   "no-idea-reached"
  ],
  "parent_fields": {
   "action_plan": "implements_decision_ids",
   "argument": "cites_claim_ids",
   "claim": "about_option_card_ids",
   "decision": "tally_of_vote_ids",
   "option_card": "promoted_from_idea_ids",
   "vote": "rests_on_argument_ids"
  },
  "sentence_cite_kinds": [
   "action_plan",
   "decision"
  ],
  "walkers_must_agree": [
   "chase",
   "join"
  ]
 },
 "missing_link": "option_card->claim",
 "missing_link_rule": "First forward hop with zero CNL-* or IMP-* catalog authors other than CNL-0075 (needles = both hop names in title or question). Loose scans that include CC/AUD/ARC coincidences (e.g. CC-0019 option-cards-plus-claims normalization) are discarded. Disk modules and parent-field greps are the second signal, not the ranking key.",
 "negative_controls": [
  {
   "bad_state_output": "orphan pass=False sentences=3 resolved=2 orphans=['s3'] s3_reasons=['empty-cites', 'no-idea-reached']",
   "fired_on_bad_state": true,
   "good_state_output": "good pass=True sentences=2 resolved=2 orphans=[]",
   "id": "orphan-sentence",
   "rejects": "A recommendation sentence with empty cites (s3: Also migrate billing to another continent.) must FAIL; the checker must name s3 and empty-cites.",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "severed pass=False sentences=2 resolved=0 orphans=['s1', 's2'] s1_reasons=['no-idea-reached']",
   "fired_on_bad_state": true,
   "good_state_output": "good pass=True sentences=2 resolved=2 orphans=[]",
   "id": "severed-option-card-to-claim",
   "rejects": "A claim with about_option_card_ids=[] severs option_card->claim; walking from decision/action_plan must not reach an idea, so s1 and s2 FAIL with no-idea-reached.",
   "silent_on_good_state": true
  }
 ],
 "on_disk": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "command-center/design/council/CNL-0056-idea-ledger-schema-and-per-participant-provenance.md": false,
  "command-center/schema/council-design-note.schema.json": true,
  "command-center/schema/councilspec.v2.schema.json": true,
  "platform/schema/councilspec.schema.json": true,
  "tools/council/artifacts/argument_graph.py": false,
  "tools/council/artifacts/option_cards.py": false,
  "tools/council/outcomes/action_plan.py": false
 },
 "question": "Can a final recommendation and its action plan be decomposed back through synthesis, votes, arguments, option cards and claims to the originating ideas - and what link in that chain (idea -> option card -> claim -> argument -> vote -> decision -> action plan) is missing today so the trace breaks?",
 "residual_unknowns": [
  "Declared output_schema command-center/schema/councilspec.v2.schema.json exists as a generated shim ($ref to https://ast-integrate.invalid/...). Draft202012Validator raises RefResolutionError offline, so this note is validated against the per-unit design-note.schema.json.",
  "command-center/schema/council-design-note.schema.json is the same class of shim; it is not a closed schema for this design note.",
  "CNL-0056 idea-ledger artifact is absent; this unit consumes a scripted ledger fixture rather than a live CNL-0056 schema.",
  "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree; hop authorship was read from WORK-UNIT-CATALOG.json, not from those inputs.",
  "argument->vote has CNL-0087/IMP-0356 needle hits; those units do not require rests_on_argument_ids. Ranked after option_card->claim because they are not the first empty hop."
 ],
 "reviewer": {
  "counterexample": {
   "attempted": true,
   "id": "orphan-s3",
   "refutes": false
  },
  "independent": true,
  "recount_good_sentences": 2,
  "recount_orphan_ids": [
   "s3"
  ],
  "reviewer_id": "CNL-0075-probe2-independent-recount",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0075",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0075/probe1_decompose.py",
   "id": "decompose-scripted-council",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0075/probe2_recount.py",
   "id": "independent-recount",
   "result": "PASS"
  }
 ],
 "title": "Decision lineage: decomposing a decision back to the ideas that made it",
 "unit_id": "CNL-0075",
 "validated_against": "command-center/p2-wave/probes/CNL-0075/design-note.schema.json"
}
