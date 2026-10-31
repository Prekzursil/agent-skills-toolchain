{
 "alternatives_rejected": [
  {
   "id": "ALT-BREAK-NEWEST-EDGE",
   "why": "Dropping the newest edge to break a cycle silently disenfranchises whoever delegated last; CNL-0067 requires detection, not a silent repair."
  },
  {
   "id": "ALT-CLIP-TO-CAP",
   "why": "Clipping D from 4/5 down to 0.5 would hide the accumulation the concentration test is meant to catch."
  }
 ],
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0067-delegation-and-proxy-voting-without-delegation-cycles.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0067/delegate.py",
   "role": "engine"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0067/recount.py",
   "role": "independent-recount"
  }
 ],
 "both_states": {
  "fires_on": "fixtures/cycle-abc.json and fixtures/accumulate-to-D.json",
  "silent_on": "fixtures/good-under-cap.json",
  "verbatim_fire": "status=DELEGATION_CYCLE tabulated=False winner=None cycles=A->B->C->A offenders=- || status=CONCENTRATION_CAP tabulated=False winner=None cycles=- offenders=D",
  "verbatim_silent": "status=TABULATED tabulated=True winner=YES cycles=- offenders=-"
 },
 "catalog_inputs_absent": [
  "11-COUNCIL-SPECIFICATION.schema.json",
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
  "_USER-PROMPTS.md"
 ],
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/delegate.py:259",
   "claim": "Fixture cycle-abc (A->B->C->A) is detected as DELEGATION_CYCLE and tabulate is not invoked.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/delegate.py:275",
   "claim": "Fixture accumulate-to-D gives D effective weight 4 of 5 (share 0.8 > 0.5) and is CONCENTRATION_CAP, not tabulated.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/recount.py:13",
   "claim": "Independent Kahn leftover on cycle-abc is {A,B,C}; independent walk gives D=4 on accumulate-to-D and B=2 on good-under-cap.",
   "id": "C3",
   "verdict": "CONFIRMED"
  }
 ],
 "decision": "Delegation is total and liquid: a seat that sets delegates_to transfers its entire current weight along the unique chain to a terminal voter and does not also cast a ballot. Before any tally, process() runs DFS cycle detection; a non-empty cycle list (including self-loops) returns DELEGATION_CYCLE with tabulated=false and winner=null. After acyclicity is proven, weights are resolved and any terminal whose effective weight exceeds cap_share of total base weight (default 0.5, a simple-majority controlling share) returns CONCENTRATION_CAP with tabulated=false. Silent clipping, newest-edge cycle breaks, and mixing a residual vote with a proxy are rejected: they hide the accumulation or drop a bloc without a recorded refuse. Dangling delegates are UNKNOWN_DELEGATE, also pre-tabulation. Conservation (sum effective == sum base) holds on every accepted DAG.",
 "dependency_note": "CNL-0064 (weight provenance) is not delivered on this worktree. This note treats each seat's base_weight as an already-justified input; it does not mint provenance.",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/delegate.py:259",
   "claim": "cycle detection runs before tabulation",
   "mechanism": "file:line of CYCLE-GATE in delegate.process plus spy tabulate_fn call count == 0 on cycle-abc",
   "verbatim": "status=DELEGATION_CYCLE tabulated=False winner=None cycles=A->B->C->A offenders=-"
  },
  {
   "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0067/probe1_cycle_before_tabulation.py",
   "claim": "cycle detection runs before tabulation",
   "mechanism": "live probe1 command output (different mechanism: subprocess spy call-count, not the source comment)",
   "verbatim": "see probe1 stdout; requires tabulate_calls=0 on cycle-abc and compact status=DELEGATION_CYCLE tabulated=False winner=None cycles=A->B->C->A offenders=-"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/delegate.py:275",
   "claim": "accumulation fixture trips the concentration cap",
   "mechanism": "file:line of CAP-GATE plus offender share arithmetic",
   "verbatim": "status=CONCENTRATION_CAP tabulated=False winner=None cycles=- offenders=D"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0067/recount.py:13",
   "claim": "accumulation fixture trips the concentration cap",
   "mechanism": "independent walk in recount.independent_effective (different field: D weight 4.0 / total 5.0, not DFS)",
   "verbatim": "independent D=4.0 total=5.0 share=0.8"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:37610",
   "claim": "catalog names the two tests this note executes",
   "mechanism": "catalog row id=CNL-0067 tests_required",
   "verbatim": "a constructed delegation cycle must be detected before tabulation; an accumulation fixture must trip a concentration cap"
  }
 ],
 "find_cycles_def_line": 79,
 "measured": {
  "accumulate_to_D": {
   "effective": {
    "A": 0.0,
    "B": 0.0,
    "C": 0.0,
    "D": 4.0,
    "E": 1.0
   },
   "offenders": [
    {
     "cap_share": 0.5,
     "cap_weight": 2.5,
     "effective_weight": 4.0,
     "seat": "D",
     "share": 0.8,
     "total": 5.0
    }
   ],
   "status": "CONCENTRATION_CAP",
   "tabulated": false,
   "winner": null
  },
  "cycle_abc": {
   "cycles": [
    [
     "A",
     "B",
     "C",
     "A"
    ]
   ],
   "effective": {},
   "offenders": [],
   "status": "DELEGATION_CYCLE",
   "tabulated": false,
   "tally": null,
   "winner": null
  },
  "good_under_cap": {
   "conservation_ok": true,
   "effective": {
    "A": 0.0,
    "B": 2.0,
    "C": 1.0,
    "D": 1.0,
    "E": 1.0
   },
   "status": "TABULATED",
   "tabulated": true,
   "tally": {
    "abstain": 0.0,
    "no": 2.0,
    "unused": 0.0,
    "winner": "YES",
    "yes": 3.0
   },
   "winner": "YES"
  },
  "self_loop": {
   "cycles": [
    [
     "A",
     "A"
    ]
   ],
   "effective": {},
   "offenders": [],
   "status": "DELEGATION_CYCLE",
   "tabulated": false,
   "tally": null,
   "winner": null
  },
  "unknown_delegate": {
   "cycles": [],
   "dangling": [
    {
     "from": "A",
     "to": "Z"
    }
   ],
   "effective": {},
   "offenders": [],
   "status": "UNKNOWN_DELEGATE",
   "tabulated": false,
   "tally": null,
   "winner": null
  }
 },
 "negative_controls": [
  {
   "id": "NC-CYCLE",
   "observed": "find_cycles + CYCLE-GATE: tabulated=false winner=null status=DELEGATION_CYCLE; compact=status=DELEGATION_CYCLE tabulated=False winner=None cycles=A->B->C->A offenders=-; skip_cycle_check mutant leaves the DFS gate and hits resolve_weights RuntimeError or a non-CYCLE status",
   "rejects": "constructed cycle A->B->C->A, the state the cycle check is meant to reject"
  },
  {
   "id": "NC-CAP",
   "observed": "concentration_offenders + CAP-GATE: tabulated=false winner=null status=CONCENTRATION_CAP; compact=status=CONCENTRATION_CAP tabulated=False winner=None cycles=- offenders=D; skip_cap_check mutant calls tabulate and produces a winner",
   "rejects": "three unit-weight seats delegating to D plus D's own weight (4/5 > 0.5), the state the concentration check rejects"
  },
  {
   "id": "NC-SELF-LOOP",
   "observed": "status=DELEGATION_CYCLE tabulated=False winner=None cycles=A->A offenders=-",
   "rejects": "self-delegation A->A"
  },
  {
   "id": "NC-DANGLING",
   "observed": "status=UNKNOWN_DELEGATE tabulated=False winner=None cycles=- offenders=-",
   "rejects": "delegates_to a seat id not in the freeze set"
  }
 ],
 "output_schema": "command-center/schema/council-design-note.schema.json",
 "produced_at": "2026-08-25T00:41:28Z",
 "question": "When a seat delegates its vote, what prevents a delegation cycle and what prevents one delegate from silently accumulating a controlling share of the weight?",
 "residual_unknowns": [
  "CNL-0064 is unbuilt, so this note cannot cite a live weight-provenance receipt for base_weight; it assumes the input weights.",
  "Harness restore inputs (11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, _USER-PROMPTS.md) are absent on this Linux worktree; protocol-id mapping is NOT-CHECKED."
 ],
 "reviewer": {
  "independent": true,
  "independent_accumulate_D": 4.0,
  "independent_good_B": 2.0,
  "kahn_cycle_abc": [
   "A",
   "B",
   "C"
  ],
  "method": "Re-tabulate from fixtures without the author's DFS: Kahn indegree peeling for cycle membership; a second terminal-walk for effective weights. Disagreement in those numbers blocks.",
  "reviewer_id": "CNL-0067-probe2-kahn-and-second-walk",
  "verdict": "PASS"
 },
 "rules": [
  {
   "id": "R-CYCLE-FAIL-CLOSED",
   "statement": "A directed delegation graph with a cycle, including a self-loop, is refused with DELEGATION_CYCLE before tabulate() runs."
  },
  {
   "id": "R-CAP-FAIL-CLOSED",
   "statement": "After liquid resolution, a terminal whose effective_weight > cap_share * total_base is refused with CONCENTRATION_CAP before tabulate() runs. Default cap_share is 1/2."
  },
  {
   "id": "R-NO-SILENT-CLIP",
   "statement": "Excess weight is not clipped to the cap. Clipping would silently shrink a bloc; the refuse is the record."
  },
  {
   "id": "R-TOTAL-LIQUID",
   "statement": "A delegating seat transfers all of its current weight and does not cast a parallel ballot. Chains are followed to a terminal."
  },
  {
   "id": "R-CONSERVATION",
   "statement": "On every accepted DAG, sum(effective) equals sum(base_weight)."
  }
 ],
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0067",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0067/probe1_cycle_before_tabulation.py",
   "id": "probe1-cycle-before-tabulation",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0067/probe2_cap_and_independent_recount.py",
   "id": "probe2-cap-and-independent-recount",
   "result": "PASS"
  }
 ],
 "title": "Delegation and proxy voting without delegation cycles",
 "unit_id": "CNL-0067"
}
