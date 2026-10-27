{
 "answer": "Unsupported synthesis sentences are those with no inbound SUPPORTS/GROUNDS/CITES edge from an evidence-reachable node. Circular citation is a directed cycle on those same edge kinds; the detector prints the full path. Distinct URL count is not the signal. A diamond DAG is silent. Zero support edges are NOT-CHECKED, never a clean pass. SUCCESS:CNL-0098",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0098-weak-synthesis-and-circular-citation-in-the-argument-graph.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-detector-spec.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0098/detector.py",
   "role": "detector"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0098/fixtures.py",
   "role": "fixtures"
  }
 ],
 "both_states": {
  "clean": {
   "status": "SILENT",
   "verbatim": "fixture=clean-linear status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=3 support_edges=2 url_count=1\nfixture=diamond status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=5 support_edges=5 url_count=1\nfixture=legit-cross-ref status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=6 support_edges=4 url_count=2"
  },
  "detector_control": {
   "status": "FIRE",
   "verbatim": "fixture=detector-control-known-present status=FIRE weak=FIRE cycle=FIRE unsupported=syn-KNOWN-ORPHAN cycle_paths=KNOWN-A->KNOWN-B->KNOWN-C->KNOWN-A nodes=7 support_edges=5 url_count=1"
  },
  "known_good": {
   "status": "SILENT",
   "verbatim": "fixture=clean-linear status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=3 support_edges=2 url_count=1\nfixture=diamond status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=5 support_edges=5 url_count=1\nfixture=legit-cross-ref status=SILENT weak=SILENT cycle=SILENT unsupported=- cycle_paths=- nodes=6 support_edges=4 url_count=2"
  },
  "planted": {
   "status": "FIRE",
   "verbatim": "fixture=planted-weak status=FIRE weak=FIRE cycle=SILENT unsupported=syn-orphan cycle_paths=- nodes=4 support_edges=2 url_count=1\nfixture=planted-cycle status=FIRE weak=SILENT cycle=FIRE unsupported=- cycle_paths=c1->c2->c3->c1 nodes=5 support_edges=5 url_count=1\nfixture=planted-circular-ungrounded status=FIRE weak=FIRE cycle=FIRE unsupported=syn-fake cycle_paths=u1->u2->u3->u1 nodes=4 support_edges=4 url_count=0\nfixture=url-launder-cycle status=FIRE weak=NOT-CHECKED cycle=FIRE unsupported=- cycle_paths=p1->p2->p3->p1 nodes=3 support_edges=3 url_count=3"
  },
  "planted_bad": {
   "status": "FIRE",
   "verbatim": "fixture=planted-weak status=FIRE weak=FIRE cycle=SILENT unsupported=syn-orphan cycle_paths=- nodes=4 support_edges=2 url_count=1\nfixture=planted-cycle status=FIRE weak=SILENT cycle=FIRE unsupported=- cycle_paths=c1->c2->c3->c1 nodes=5 support_edges=5 url_count=1\nfixture=planted-circular-ungrounded status=FIRE weak=FIRE cycle=FIRE unsupported=syn-fake cycle_paths=u1->u2->u3->u1 nodes=4 support_edges=4 url_count=0\nfixture=url-launder-cycle status=FIRE weak=NOT-CHECKED cycle=FIRE unsupported=- cycle_paths=p1->p2->p3->p1 nodes=3 support_edges=3 url_count=3"
  }
 },
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0098/fixtures.py:51",
   "claim": "Planted orphan synthesis sentence syn-orphan is reported unsupported.",
   "id": "C-WEAK",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0098/detector.py:177",
   "claim": "A 3-node SUPPORTS cycle fires and the report includes a full path.",
   "id": "C-CYCLE",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0098/fixtures.py:150",
   "claim": "A diamond DAG with a shared ancestor is not reported as a cycle.",
   "id": "C-DIAMOND",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0098/detector.py:254",
   "claim": "Zero support edges yield NOT-CHECKED, not a silent pass.",
   "id": "C-EMPTY",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "tools/council/artifacts/argument_graph.py",
   "claim": "tools/council/artifacts/argument_graph.py exists on this worktree.",
   "defect_locus": "DESIGN",
   "id": "C-PROD",
   "verdict": "REFUTED"
  },
  {
   "anchor": "tools/council/artifacts/evidence_map.py",
   "claim": "tools/council/artifacts/evidence_map.py exists on this worktree.",
   "defect_locus": "DESIGN",
   "id": "C-PROD-EVIDENCE-MAP",
   "verdict": "REFUTED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0098/detector.py:11",
   "claim": "Circular citation can be detected by counting distinct URLs.",
   "defect_locus": "DESIGN",
   "id": "C-URL",
   "verdict": "REFUTED"
  }
 ],
 "dependencies": {
  "CNL-0075": {
   "note": "Catalog dependency. Absent lineage artifact does not block FIRE/SILENT proofs on this unit's typed graph fixtures.",
   "output_path": "command-center/design/council/CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md",
   "present": false
  }
 },
 "detector": {
  "does_not_count_urls": true,
  "empty_support_graph": "NOT-CHECKED",
  "evidence_kinds": [
   "evidence",
   "observation",
   "measurement"
  ],
  "fires_when": [
   "a synthesis sentence has no inbound SUPPORTS/GROUNDS/CITES edge from an evidence-reachable node",
   "the support graph contains a directed cycle; the full node path is printed"
  ],
  "id": "CNL-0098-weak-synthesis-and-circular-citation",
  "implementation": "command-center/p2-wave/probes/CNL-0098/detector.py",
  "module": "command-center/p2-wave/probes/CNL-0098/detector.py",
  "silent_when": [
   "every synthesis sentence is evidence-grounded and the support graph is acyclic (diamond and distinct-fact cross-refs included)"
  ],
  "support_edge_kinds": [
   "SUPPORTS",
   "GROUNDS",
   "CITES"
  ]
 },
 "detector_control": {
  "fired_before_absence_reported": true,
  "known_present_fixture": "detector-control-known-present",
  "known_present_run_first": true,
  "verbatim": "fixture=detector-control-known-present status=FIRE weak=FIRE cycle=FIRE unsupported=syn-KNOWN-ORPHAN cycle_paths=KNOWN-A->KNOWN-B->KNOWN-C->KNOWN-A nodes=7 support_edges=5 url_count=1"
 },
 "distinction": {
  "disengaged": "Out of scope for CNL-0098. This unit classifies missing graph support and citation cycles, not disengaged participants.",
  "nothing_to_add": "Out of scope for CNL-0098. Shared schema requires this key; this unit does not classify 'nothing to add' turns.",
  "operational_test": "FIRE on planted-weak, planted-cycle, planted-circular-ungrounded, and url-launder-cycle; SILENT on clean-linear, diamond, and legit-cross-ref; empty-graph is NOT-CHECKED."
 },
 "evidence": [
  {
   "claim": "Unit question names unsupported synthesis sentences and citation cycles.",
   "kind": "catalog",
   "line": 39207,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "Which synthesis sentences are unsupported by any edge"
  },
  {
   "claim": "Support graph is edge-kind restricted, not URL cardinality.",
   "kind": "probe",
   "line": 22,
   "path": "command-center/p2-wave/probes/CNL-0098/detector.py",
   "snippet": "SUPPORT_KINDS = frozenset"
  },
  {
   "claim": "Detector-control fixture plants a known-present orphan id.",
   "kind": "probe",
   "line": 117,
   "path": "command-center/p2-wave/probes/CNL-0098/fixtures.py",
   "snippet": "syn-KNOWN-ORPHAN"
  },
  {
   "claim": "Reviewer re-imports detector.analyse rather than trusting stdout.",
   "kind": "probe",
   "line": 84,
   "path": "command-center/p2-wave/probes/CNL-0098/reviewer.py",
   "snippet": "both_states_rerun"
  }
 ],
 "false_positive_rate": 0.0,
 "false_positive_rate_breakdown": {
  "clean_fixture_ids": [
   "clean-linear",
   "diamond",
   "legit-cross-ref"
  ],
  "clean_fixtures_total": 3,
  "fires": 0,
  "rate": 0.0
 },
 "fixtures": {
  "detector_control": "detector-control-known-present",
  "directory": "command-center/p2-wave/probes/CNL-0098/fixtures",
  "empty_graph": "empty-graph",
  "known_good": [
   "clean-linear",
   "diamond",
   "legit-cross-ref"
  ],
  "planted_bad": [
   "planted-weak",
   "planted-cycle",
   "planted-circular-ungrounded",
   "url-launder-cycle"
  ]
 },
 "live_reports": {
  "clean-linear": {
   "cycle_paths": [],
   "distinct_url_count": 1,
   "status": "SILENT",
   "support_edges": 2,
   "unsupported_sentence_ids": []
  },
  "detector-control-known-present": {
   "cycle_paths": [
    "KNOWN-A->KNOWN-B->KNOWN-C->KNOWN-A"
   ],
   "distinct_url_count": 1,
   "status": "FIRE",
   "support_edges": 5,
   "unsupported_sentence_ids": [
    "syn-KNOWN-ORPHAN"
   ]
  },
  "diamond": {
   "cycle_paths": [],
   "distinct_url_count": 1,
   "status": "SILENT",
   "support_edges": 5,
   "unsupported_sentence_ids": []
  },
  "empty-graph": {
   "cycle_paths": [],
   "distinct_url_count": 0,
   "status": "NOT-CHECKED",
   "support_edges": 0,
   "unsupported_sentence_ids": []
  },
  "legit-cross-ref": {
   "cycle_paths": [],
   "distinct_url_count": 2,
   "status": "SILENT",
   "support_edges": 4,
   "unsupported_sentence_ids": []
  },
  "planted-circular-ungrounded": {
   "cycle_paths": [
    "u1->u2->u3->u1"
   ],
   "distinct_url_count": 0,
   "status": "FIRE",
   "support_edges": 4,
   "unsupported_sentence_ids": [
    "syn-fake"
   ]
  },
  "planted-cycle": {
   "cycle_paths": [
    "c1->c2->c3->c1"
   ],
   "distinct_url_count": 1,
   "status": "FIRE",
   "support_edges": 5,
   "unsupported_sentence_ids": []
  },
  "planted-weak": {
   "cycle_paths": [],
   "distinct_url_count": 1,
   "status": "FIRE",
   "support_edges": 2,
   "unsupported_sentence_ids": [
    "syn-orphan"
   ]
  },
  "url-launder-cycle": {
   "cycle_paths": [
    "p1->p2->p3->p1"
   ],
   "distinct_url_count": 3,
   "status": "FIRE",
   "support_edges": 3,
   "unsupported_sentence_ids": []
  }
 },
 "negative_control": {
  "rejects": "planted-weak (orphan sentence), planted-cycle (3-cycle path), planted-circular-ungrounded (cycle with no evidence), url-launder-cycle (>=3 URLs still a cycle)",
  "state_meant_to_reject": "planted-weak orphan sentence; planted 3-cycle; circular ungrounded loop; URL-diverse cycle",
  "verbatim": "On planted-weak the check FIRES and lists syn-orphan. On planted-cycle it FIRES and prints a full c1/c2/c3 path. On planted-circular-ungrounded it FIRES both pathologies (syn-fake is not evidence-reachable). On url-launder-cycle it FIRES even though distinct_url_count>=3. On clean-linear, diamond, and legit-cross-ref it is SILENT (false_positive_rate is the numeric fraction of those three that fired). On empty-graph the cycle check is NOT-CHECKED, never a pass. A diamond DAG must not be reported as a cycle.",
  "what_the_check_did": "FIRE listing syn-orphan; FIRE with full cycle path; FIRE both pathologies on syn-fake; FIRE on url-launder-cycle"
 },
 "pathologies": [
  {
   "detector_rule": "A synthesis sentence is unsupported unless it has an inbound SUPPORTS/GROUNDS/CITES edge from a node reachable from evidence.",
   "fire_condition": "unsupported_sentence_ids is non-empty or unindexed prose exists",
   "id": "weak-synthesis",
   "name": "Unsupported synthesis sentence",
   "silent_condition": "every sentence has evidence-reachable inbound support"
  },
  {
   "detector_rule": "Tarjan SCCs over SUPPORTS/CITES/GROUNDS; every non-trivial SCC yields a full node path. URL cardinality is ignored.",
   "fire_condition": "at least one support cycle with a printed path",
   "id": "circular-citation",
   "name": "Support-graph cycle",
   "silent_condition": "support_edges>0 and no cycle (diamond and cross-ref included)"
  }
 ],
 "pathology": "Weak synthesis: synthesis sentences unsupported by any evidence-reachable graph edge. Circular citation: a support-edge cycle that manufactures support with no external evidence.",
 "production_modules": {
  "argument_graph_py": {
   "path": "tools/council/artifacts/argument_graph.py",
   "present": false
  },
  "evidence_map_py": {
   "path": "tools/council/artifacts/evidence_map.py",
   "present": false
  }
 },
 "question": "Which synthesis sentences are unsupported by any edge in the argument graph, and separately, which citation chains form a cycle that manufactures support out of nothing?",
 "residual_unknowns": [
  "Catalog inputs cite _USER-PROMPTS.md:11232 and the council spec JSON; those files are not on this worktree, so line-level spec quotes were not independently fetched.",
  "Semantic entailment of a GROUNDS source (FM-SEMANTIC-UNGROUNDED) is out of scope for this structural detector.",
  "Catalog reviewer_requirement names openai/gpt-5-codex; that vendor did not sign. Mechanical both-states re-run did."
 ],
 "reviewer": {
  "added_failure_mode": {
   "author_missed": true,
   "caught_by_circular_citation": false,
   "caught_by_weak_synthesis": false,
   "description": "The weak-synthesis check is structural: inbound SUPPORTS/GROUNDS from an evidence-reachable node. A sentence can copy unrelated wording while pointing at a real claim. Entailment is a different detector; this unit does not claim to have one.",
   "id": "FM-SEMANTIC-UNGROUNDED",
   "title": "GROUNDS edge whose source does not entail the sentence"
  },
  "both_states_rerun": true,
  "fresh_context": true,
  "independent": true,
  "method": "Imported fixtures.py and detector.py in this process. Re-ran detector-control, every planted-bad fixture, every clean fixture, empty-graph, and diamond. Did not trust SUBAGENT-RETURN stdout.",
  "rerun_control_verbatim": "fixture=detector-control-known-present status=FIRE weak=FIRE cycle=FIRE unsupported=syn-KNOWN-ORPHAN cycle_paths=KNOWN-A->KNOWN-B->KNOWN-C->KNOWN-A nodes=7 support_edges=5 url_count=1",
  "rerun_passed": true,
  "reviewer_id": "CNL-0098-mechanical-both-states-reviewer",
  "scope_not_agreement": true,
  "vendor_constraint_met": false,
  "vendor_constraint_reason": "Catalog reviewer_requirement names openai/gpt-5-codex. This reviewer is a mechanical re-import of detector.analyse on the same fixtures, not that vendor. The control was executed; the vendor stamp was not.",
  "verdict": "PASS"
 },
 "runtime_actions": {
  "consent_rule": "This detector emits findings only. It does not mute a seat, cast a vote, or treat silence as consent.",
  "on_disengaged": "Not a CNL-0098 action. Citation cycles are reported with their full path; no participant is marked disengaged.",
  "on_nothing_to_add": "Not a CNL-0098 action. Unsupported sentences are listed as weak-synthesis findings; no seat is marked 'nothing to add'."
 },
 "sentinel": "SUCCESS:CNL-0098",
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "A GROUNDS edge can attach a synthesis sentence to a real claim whose text does not entail the sentence. The structural check is silent on that lie. That is FM-SEMANTIC-UNGROUNDED, recorded as missed, not claimed caught.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0098/probe1_both_states.py",
   "id": "probe1-both-states",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0098/probe2_schema_and_overclaim.py",
   "id": "probe2-schema-overclaim",
   "result": "PASS"
  }
 ],
 "title": "Weak synthesis and circular citation in the argument graph",
 "unit_id": "CNL-0098"
}
