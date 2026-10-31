{
 "answer": "When the pairwise majority graph has no unique Condorcet winner, the frozen completion is Schulze (beatpath / widest path). The rule is hashed into freeze_token before any ballot is ingested; rebinding cycle_completion after ingest is rejected so the operator cannot pick a completion to favour an outcome. A unique Condorcet winner is elected and cycle-completion is not applied. On the constructed 3-cycle, declared Schulze elects B and plurality-in-Smith elects A, so the choice is load-bearing.",
 "answers": {
  "condorcet_winner_overrides_completion": "A unique Condorcet winner is elected and cycle-completion is not applied; swapping the completion on that profile must not change the winner.",
  "cycle_completion_declared": "When the pairwise majority graph has no unique Condorcet winner, the frozen completion is Schulze (beatpath / widest path). The rule is hashed into freeze_token before any ballot is ingested.",
  "freeze_before_ballots": "cycle_completion and candidate_order are declared and hashed before ingest; rebinding after ingest is rejected so the operator cannot pick a completion to favour an outcome."
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0063-pairwise-condorcet-tabulation-and-the-cycle-rule.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0063/tabulate.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0063/recount.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0063/fixtures.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0063/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  }
 ],
 "catalog_tests_required": [
  "a constructed 3-cycle must be resolved by the declared rule, and swapping in a different completion rule must be shown to change the winner - proving the choice is load-bearing",
  "negative control recorded verbatim: state what the check does on the state it is meant to reject"
 ],
 "claimed_rule": {
  "cycle_completion_declared": "schulze",
  "cycle_completion_swap": "plurality_in_smith",
  "method": "pairwise_condorcet",
  "when_condorcet_winner": "Elect the unique Condorcet winner. Cycle-completion is not applied and must not change the winner if swapped.",
  "when_cycle": "Elect the Schulze (beatpath) winner of the Smith set. Do not pick a completion by inspecting which candidate the operator prefers."
 },
 "claims": [
  {
   "claim": "On the constructed 3-cycle, declared Schulze elects B and plurality-in-Smith elects A, so the completion is load-bearing.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "An independent recount walking rank-pairs and Dijkstra widest paths reproduces the same pairwise cells and the same Schulze winner.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "The cycle detector is silent on a unique Condorcet winner and post-hoc rebind after ingest is rejected.",
   "id": "C3",
   "verdict": "CONFIRMED"
  }
 ],
 "dependency_note": "CNL-0023 (vote-weight provenance) is not delivered on this tree. This unit treats missing provenance as weight=1 only and rejects non-equal weight without provenance_ref. It does not wait on CNL-0023.",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0063/tabulate.py:170",
   "claim": "On the constructed 3-cycle, declared Schulze elects B and plurality-in-Smith elects A, so the completion is load-bearing.",
   "kind": "live-tree",
   "line": 170,
   "mechanism": "Floyd-Warshall Schulze plus plurality-in-Smith on the same ballots",
   "path": "command-center/p2-wave/probes/CNL-0063/tabulate.py",
   "snippet": "def schulze_paths(",
   "verbatim": "cycle_detected=True smith=['A', 'B', 'C'] declared=schulze winner=B swap=plurality_in_smith winner=A pairwise={'A': {'A': 0, 'B': 8, 'C': 5}, 'B': {'A': 6, 'B': 0, 'C': 9}, 'C': {'A': 9, 'B': 5, 'C': 0}}",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0063/recount.py:15",
   "claim": "An independent recount walking rank-pairs and Dijkstra widest paths reproduces the same pairwise cells and the same Schulze winner.",
   "kind": "live-tree",
   "line": 15,
   "mechanism": "rank-pair accumulation and Dijkstra widest-path, not Floyd-Warshall",
   "path": "command-center/p2-wave/probes/CNL-0063/recount.py",
   "snippet": "def pairwise_by_rank_pairs(",
   "verbatim": "recount_winner=B pairwise={'A': {'A': 0, 'B': 8, 'C': 5}, 'B': {'A': 6, 'B': 0, 'C': 9}, 'C': {'A': 9, 'B': 5, 'C': 0}} schulze_scores={'A': 0, 'B': 2, 'C': 1}",
   "verdict": "CONFIRMED"
  }
 ],
 "freeze_contract": {
  "declared_completion": "schulze",
  "moment": "before-ballot-ingest",
  "post_ingest_rebind": "rejected",
  "rule": "cycle_completion and candidate_order are hashed before ingest; after ingest the token is immutable.",
  "token": "028b630b97af0274eb0eb6982c49432930add44821ca905da733892872bbf334",
  "token_algorithm": "sha256(canonical-json(candidate_order,cycle_completion,method))"
 },
 "independent_recount": {
  "mechanism": "rank-pair accumulation plus Dijkstra widest-path Schulze",
  "pairwise": {
   "A": {
    "A": 0,
    "B": 8,
    "C": 5
   },
   "B": {
    "A": 6,
    "B": 0,
    "C": 9
   },
   "C": {
    "A": 9,
    "B": 5,
    "C": 0
   }
  },
  "pairwise_cells_match": true,
  "schulze_scores": {
   "A": 0,
   "B": 2,
   "C": 1
  },
  "winner": "B",
  "winner_match": true
 },
 "kind": "council-design-note",
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0063/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "markdown": "# Pairwise / Condorcet tabulation and the cycle rule (CNL-0063)\n\nWhat is the completion rule when the pairwise matrix contains a Condorcet cycle, and is the chosen rule declared BEFORE the ballots are seen so it cannot be picked to favour an outcome?\n\n## Declared rule (frozen before ballots)\n\nMethod: pairwise Condorcet. Each ranked ballot of weight w contributes\nw to every pair (higher, lower). A unique Condorcet winner (beats every\nother candidate pairwise) is elected and the cycle-completion is not used.\n\nWhen the majority graph contains a cycle (no Condorcet winner; Smith set\nsize > 1), the frozen completion is Schulze (beatpath / widest path).\nSchulze is declared in the spec; it is not selected by inspecting the\nmatrix. The freeze token is sha256 of the canonical JSON\n{\"candidate_order\":...,\"cycle_completion\":\"schulze\",\"method\":\"pairwise_condorcet\"}.\nAfter ingest, rebinding cycle_completion is rejected.\n\nNon-equal ballot weights require a provenance_ref (CNL-0023). This unit\ndoes not invent a weight; fixtures use weight 1.\n\n## Load-bearing 3-cycle\n\nBallots: 5\u00d7 A>B>C, 4\u00d7 B>C>A, 3\u00d7 C>A>B, 2\u00d7 C>B>A.\nLive pairwise: {'A': {'A': 0, 'B': 8, 'C': 5}, 'B': {'A': 6, 'B': 0, 'C': 9}, 'C': {'A': 9, 'B': 5, 'C': 0}}.\nDeclared Schulze winner: B.\nSwap plurality-in-Smith winner: A.\nThe completion choice changes the winner, so it cannot be left implicit.\n\n## Negative control\n\nOn a unique-Condorcet-winner profile the detector is silent\n(cycle_detected=False condorcet_winner=A declared_winner=A swap_winner=A completion_used=None recount_cycle=False). The state the check rejects is a cycle claim or a\ncompletion override when a Condorcet winner exists, and a post-hoc\nrebind after ingest (ok=False reason=cycle_completion frozen after ballot ingest declared=schulze rejected=plurality_in_smith).\n\nSUCCESS:CNL-0063",
 "measured_condorcet_winner": {
  "ballots": [
   {
    "count": 6,
    "ranking": [
     "A",
     "B",
     "C"
    ]
   },
   {
    "count": 3,
    "ranking": [
     "B",
     "A",
     "C"
    ]
   },
   {
    "count": 2,
    "ranking": [
     "C",
     "B",
     "A"
    ]
   }
  ],
  "completion_used": null,
  "condorcet_winner": "A",
  "cycle_detected": false,
  "fixture_id": "unique-condorcet-winner",
  "swap_winner": "A",
  "verbatim": "cycle_detected=False condorcet_winner=A declared_winner=A swap_winner=A completion_used=None recount_cycle=False",
  "winner": "A"
 },
 "measured_cycle": {
  "ballots": [
   {
    "count": 5,
    "ranking": [
     "A",
     "B",
     "C"
    ]
   },
   {
    "count": 4,
    "ranking": [
     "B",
     "C",
     "A"
    ]
   },
   {
    "count": 3,
    "ranking": [
     "C",
     "A",
     "B"
    ]
   },
   {
    "count": 2,
    "ranking": [
     "C",
     "B",
     "A"
    ]
   }
  ],
  "condorcet_winner": null,
  "cycle_detected": true,
  "declared_winner": "B",
  "fixture_id": "constructed-3-cycle",
  "load_bearing": true,
  "pairwise": {
   "A": {
    "A": 0,
    "B": 8,
    "C": 5
   },
   "B": {
    "A": 6,
    "B": 0,
    "C": 9
   },
   "C": {
    "A": 9,
    "B": 5,
    "C": 0
   }
  },
  "smith_set": [
   "A",
   "B",
   "C"
  ],
  "swap_winner": "A",
  "verbatim": "cycle_detected=True smith=['A', 'B', 'C'] declared=schulze winner=B swap=plurality_in_smith winner=A pairwise={'A': {'A': 0, 'B': 8, 'C': 5}, 'B': {'A': 6, 'B': 0, 'C': 9}, 'C': {'A': 9, 'B': 5, 'C': 0}}"
 },
 "measured_posthoc": {
  "ok": false,
  "reason": "cycle_completion frozen after ballot ingest",
  "verbatim": "ok=False reason=cycle_completion frozen after ballot ingest declared=schulze rejected=plurality_in_smith"
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0063/probe1_cycle_load_bearing.py",
   "id": "probe1",
   "role": "cycle-load-bearing"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0063/probe2_negative_and_recount.py",
   "id": "probe2",
   "role": "independent-recount-negative-control"
  }
 ],
 "negative_controls": [
  {
   "fired_on_bad_state": true,
   "id": "CNL0063-C1-false-cycle",
   "kind": "known-good-condorcet-winner",
   "rejects": "Reporting cycle_detected=true or applying a cycle completion when a unique Condorcet winner exists",
   "rejects_state": "Reporting cycle_detected=true or applying a cycle completion when a unique Condorcet winner exists",
   "silent_on_good_state": true,
   "verbatim": "cycle_detected=False condorcet_winner=A declared_winner=A swap_winner=A completion_used=None recount_cycle=False",
   "verbatim_bad": "check FIRES if cycle_detected is true on unique-condorcet-winner or if swap changes that winner",
   "verbatim_good": "cycle_detected=False condorcet_winner=A declared_winner=A swap_winner=A completion_used=None recount_cycle=False"
  },
  {
   "fired_on_bad_state": true,
   "id": "CNL0063-C2-posthoc-rebind",
   "kind": "post-hoc-completion-pick",
   "rejects": "Selecting cycle_completion after ballots have been ingested, which would let the operator pick a winner",
   "rejects_state": "Selecting cycle_completion after ballots have been ingested, which would let the operator pick a winner",
   "silent_on_good_state": true,
   "verbatim": "ok=False reason=cycle_completion frozen after ballot ingest declared=schulze rejected=plurality_in_smith",
   "verbatim_bad": "ok=False reason=cycle_completion frozen after ballot ingest declared=schulze rejected=plurality_in_smith",
   "verbatim_good": "rebind-allowed-before-ingest when ingested=false; freeze token computed before any ballot is read (028b630b97af0274...)"
  }
 ],
 "pairwise_tabulation": {
  "cell": "sum of ballot weights ranking row strictly above column",
  "condorcet_winner": "candidate who pairwise-beats every other",
  "declared_completion_algorithm": "Schulze strongest paths (Floyd-Warshall max-min)",
  "input": "complete rankings over the frozen candidate_order",
  "non_equal_weight": "requires provenance_ref; otherwise SpecError (CNL-0023)",
  "smith_set": "source SCCs of the majority graph (Kosaraju)",
  "swap_completion_algorithm": "plurality inside the Smith set, first-ranked Smith member, ties broken by frozen candidate_order",
  "weight_default": 1
 },
 "question": "What is the completion rule when the pairwise matrix contains a Condorcet cycle, and is the chosen rule declared BEFORE the ballots are seen so it cannot be picked to favour an outcome?",
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot (AGENTS.md 4b)"
 },
 "reviewer": {
  "independent": true,
  "method": "Re-tabulated the fixtures with recount.py (rank-pair walk + Dijkstra widest paths). Disagreement in any pairwise cell or in the Schulze winner blocks the unit.",
  "reviewer_id": "CNL-0063-probe2-independent-recount",
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0063",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0063/probe1_cycle_load_bearing.py",
   "id": "T1-constructed-3-cycle-load-bearing-completion",
   "name": "A constructed 3-cycle is resolved by declared Schulze; swapping to plurality-in-Smith changes the winner",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0063/probe2_negative_and_recount.py",
   "id": "T2-negative-control-condorcet-winner-and-posthoc",
   "name": "Independent recount matches; cycle detector silent on a unique Condorcet winner; post-hoc rebind rejected",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:55:42Z"
 },
 "title": "Pairwise / Condorcet tabulation and the cycle rule",
 "unit_id": "CNL-0063"
}
