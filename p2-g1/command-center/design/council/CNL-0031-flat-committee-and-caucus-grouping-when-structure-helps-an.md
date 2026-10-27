{
 "algorithm": {
  "id": "CNL-0031.v1-partition-grain",
  "inputs": [
   "n:roster-size",
   "k:partition-grain",
   "c:fan-in-capacity"
  ],
  "outputs": [
   "family-label",
   "lost_count",
   "lost_ids",
   "fragmentation_fires"
  ],
  "steps": [
   "Require k divides n; form g = n/k disjoint cells of cardinality k.",
   "Each cell holds one unique fact per member; fan-in emits min(k, c) highest-priority facts unless g==1 identity.",
   "lost_ids = set(cell transcripts) minus set(plenary payloads); fire if planted F00 is in group-0 and absent from plenary.",
   "Label family: k==n is flat-peer, k==1 is singleton-fanin, g<=3 is committee, else caucus."
  ]
 },
 "answer": "The unifying parameter is partition grain k: the cardinality of each cell in a partition of an n-member roster (k must divide n). Group count g = n/k. Fan-in capacity c is the number of facts a cell may emit to plenary. Flat-peer is k = n (g = 1) with identity fan-in (the plenary IS the cell). Committee and caucus are the same operator at smaller k: for n=12, k in {6,4} (g<=3) is committee and k in {3,2} (g>3) is caucus. Unique cell information is lost iff k > c under lossy fan-in. On the n=12 c=2 fixture that inequality first holds at k*=3 (lost=4). Pair-caucus k=c=2 is lossless (lost=0, g=6) so subgrouping adds parallelism without fragmenting. The first cut away from flat (k=6 two-committee) already overflows (lost=8, planted F00 in group-0 transcript, absent from plenary). Best lossless parallel setting is k=1 net_score=12.0.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0031/note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0031/topology.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0031/recount.py",
   "role": "supporting"
  }
 ],
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0031/topology.py:3",
   "claim": "Flat-peer, committee and caucus are one family parameterized by partition grain k.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0031/topology.py:48",
   "claim": "Under lossy fan-in of capacity c=2, unique facts are lost iff k > c; on n=12 the first such k is 3.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0031/topology.py:47",
   "claim": "Flat identity fan-in (g==1) measures lost_count==0 including planted F00.",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0031/topology.py:75",
   "claim": "Subgrouping never fragments: every caucus/committee forwards its full transcript.",
   "counterexample": {
    "c": 2,
    "in_group0": true,
    "in_plenary": false,
    "k": 6,
    "lost_count": 8,
    "lost_ids": [
     "F00",
     "F01",
     "F02",
     "F03",
     "F06",
     "F07",
     "F08",
     "F09"
    ],
    "planted": "F00"
   },
   "id": "C4",
   "verdict": "REFUTED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0031/topology.py:48",
   "claim": "Any k < n fragments cross-group information.",
   "counterexample": {
    "c": 2,
    "family": "caucus",
    "g": 6,
    "k": 2,
    "lost_count": 0,
    "lost_ids": [],
    "n": 12,
    "planted_in_plenary": true,
    "what_it_refutes": "any k<n subgrouping fragments cross-group information"
   },
   "id": "C5",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0031",
 "defaults": {
  "protocol": "partition-grain-plenary",
  "roles": [
   "cell-member",
   "rapporteur",
   "plenary"
  ],
  "stopping_rule": "one-fan-in-then-set-difference",
  "voting_method": "rapporteur-capacity-c"
 },
 "dependency_note": {
  "blocks_this_unit": false,
  "catalog_dependencies": [
   "CNL-0022"
  ],
  "on_disk": false,
  "why_not_blocked": "CNL-0031 measures grouping grain and fan-in loss on a fixture; it does not import CNL-0022 role-mandate schema records."
 },
 "evidence": [
  {
   "claim": "Signal A: topology.simulate lost_ids is set(caucus)-set(plenary); k=6 lost_count=8 includes planted F00.",
   "kind": "live-tree",
   "line": 48,
   "mechanism": "simulate-set-difference",
   "path": "command-center/p2-wave/probes/CNL-0031/topology.py",
   "snippet": "MARKER_OVERFLOW k > c"
  },
  {
   "claim": "Signal B: recount.recount unique-ifies serialized fact_ids via dict.fromkeys and list membership, a different field path than set difference.",
   "kind": "live-tree",
   "line": 35,
   "mechanism": "dict.fromkeys-then-list-membership",
   "path": "command-center/p2-wave/probes/CNL-0031/recount.py",
   "snippet": "dict.fromkeys-then-list-membership"
  },
  {
   "claim": "Flat k=12 identity fan-in: lost_count=0.",
   "kind": "live-tree",
   "line": 47,
   "mechanism": "simulate-set-difference",
   "path": "command-center/p2-wave/probes/CNL-0031/topology.py",
   "snippet": "MARKER_FLAT_IDENTITY"
  },
  {
   "claim": "Rapporteur ranked[:c] drops F00 when k>c; the fragmentation probe measures that drop.",
   "kind": "live-tree",
   "line": 75,
   "mechanism": "simulate-set-difference",
   "path": "command-center/p2-wave/probes/CNL-0031/topology.py",
   "snippet": "MARKER_FANIN rapporteur capacity c"
  }
 ],
 "explanation_contract": {
  "dials": [
   "partition-grain-k",
   "fan-in-c",
   "roster-n",
   "identity-fan-in"
  ],
  "missing_reason_fails": true,
  "owner_contest": "Owner contests k (cell cardinality) or c (rapporteur capacity) per grouping; an off-default grain with an empty reason fails."
 },
 "fixtures": [
  {
   "explanation": {
    "c": 2,
    "family": "flat-peer",
    "fragmentation_fires": false,
    "g": 1,
    "identity_fan_in": true,
    "k": 12,
    "lost_count": 0,
    "lost_ids": [],
    "n": 12,
    "reason": "flat identity: plenary is the cell"
   },
   "id": "F01",
   "risk_tier": "T0",
   "task_description": "Roster n=12 grouped at partition grain k=12 with fan-in c=2: flat identity: plenary is the cell"
  },
  {
   "explanation": {
    "c": 2,
    "family": "singleton-fanin",
    "fragmentation_fires": false,
    "g": 12,
    "identity_fan_in": false,
    "k": 1,
    "lost_count": 0,
    "lost_ids": [],
    "n": 12,
    "reason": "singleton fan-in: each cell emits its only fact"
   },
   "id": "F02",
   "risk_tier": "T1",
   "task_description": "Roster n=12 grouped at partition grain k=1 with fan-in c=2: singleton fan-in: each cell emits its only fact"
  },
  {
   "explanation": {
    "c": 2,
    "family": "caucus",
    "fragmentation_fires": false,
    "g": 6,
    "identity_fan_in": false,
    "k": 2,
    "lost_count": 0,
    "lost_ids": [],
    "n": 12,
    "reason": "pair-caucus k=c: lossless subgrouping"
   },
   "id": "F03",
   "risk_tier": "T1",
   "task_description": "Roster n=12 grouped at partition grain k=2 with fan-in c=2: pair-caucus k=c: lossless subgrouping"
  },
  {
   "explanation": {
    "c": 2,
    "family": "caucus",
    "fragmentation_fires": true,
    "g": 4,
    "identity_fan_in": false,
    "k": 3,
    "lost_count": 4,
    "lost_ids": [
     "F00",
     "F03",
     "F06",
     "F09"
    ],
    "n": 12,
    "reason": "first lossy k>c on n=12 c=2"
   },
   "id": "F04",
   "risk_tier": "T2",
   "task_description": "Roster n=12 grouped at partition grain k=3 with fan-in c=2: first lossy k>c on n=12 c=2"
  },
  {
   "explanation": {
    "c": 2,
    "family": "committee",
    "fragmentation_fires": true,
    "g": 3,
    "identity_fan_in": false,
    "k": 4,
    "lost_count": 6,
    "lost_ids": [
     "F00",
     "F01",
     "F04",
     "F05",
     "F08",
     "F09"
    ],
    "n": 12,
    "reason": "three-committee overflow"
   },
   "id": "F05",
   "risk_tier": "T2",
   "task_description": "Roster n=12 grouped at partition grain k=4 with fan-in c=2: three-committee overflow"
  },
  {
   "explanation": {
    "c": 2,
    "family": "committee",
    "fragmentation_fires": true,
    "g": 2,
    "identity_fan_in": false,
    "k": 6,
    "lost_count": 8,
    "lost_ids": [
     "F00",
     "F01",
     "F02",
     "F03",
     "F06",
     "F07",
     "F08",
     "F09"
    ],
    "n": 12,
    "reason": "first cut from flat: two-committee overflow"
   },
   "id": "F06",
   "risk_tier": "T3",
   "task_description": "Roster n=12 grouped at partition grain k=6 with fan-in c=2: first cut from flat: two-committee overflow"
  },
  {
   "explanation": {
    "c": 3,
    "family": "caucus",
    "fragmentation_fires": false,
    "g": 4,
    "identity_fan_in": false,
    "k": 3,
    "lost_count": 0,
    "lost_ids": [],
    "n": 12,
    "reason": "k=c=3 caucus: capacity covers the cell"
   },
   "id": "F07",
   "risk_tier": "T1",
   "task_description": "Roster n=12 grouped at partition grain k=3 with fan-in c=3: k=c=3 caucus: capacity covers the cell"
  },
  {
   "explanation": {
    "c": 2,
    "family": "committee",
    "fragmentation_fires": true,
    "g": 2,
    "identity_fan_in": false,
    "k": 4,
    "lost_count": 4,
    "lost_ids": [
     "F00",
     "F01",
     "F04",
     "F05"
    ],
    "n": 8,
    "reason": "n=8 committee k=4 c=2 overflow"
   },
   "id": "F08",
   "risk_tier": "T2",
   "task_description": "Roster n=8 grouped at partition grain k=4 with fan-in c=2: n=8 committee k=4 c=2 overflow"
  },
  {
   "explanation": {
    "c": 2,
    "family": "caucus",
    "fragmentation_fires": false,
    "g": 4,
    "identity_fan_in": false,
    "k": 2,
    "lost_count": 0,
    "lost_ids": [],
    "n": 8,
    "reason": "n=8 pair-caucus lossless"
   },
   "id": "F09",
   "risk_tier": "T1",
   "task_description": "Roster n=8 grouped at partition grain k=2 with fan-in c=2: n=8 pair-caucus lossless"
  },
  {
   "explanation": {
    "c": 2,
    "family": "committee",
    "fragmentation_fires": true,
    "g": 2,
    "identity_fan_in": false,
    "k": 3,
    "lost_count": 2,
    "lost_ids": [
     "F00",
     "F03"
    ],
    "n": 6,
    "reason": "n=6 k=3 c=2 overflow"
   },
   "id": "F10",
   "risk_tier": "T2",
   "task_description": "Roster n=6 grouped at partition grain k=3 with fan-in c=2: n=6 k=3 c=2 overflow"
  }
 ],
 "fragmentation_threshold": {
  "best_lossless_parallel_k": 1,
  "c": 2,
  "crossover_k": 3,
  "first_subdivision_from_flat_k": 6,
  "measured": {
   "caucus_k2_lost_count": 0,
   "caucus_k3_lost_count": 4,
   "committee_k6_lost_count": 8,
   "flat_lost_count": 0,
   "planted_fact": "F00",
   "sweep": [
    {
     "caucus_count": 12,
     "family": "singleton-fanin",
     "fragmentation_fires": false,
     "g": 12,
     "identity_fan_in": false,
     "k": 1,
     "lost_count": 0,
     "lost_ids": [],
     "net_score": 12.0,
     "planted_in_group0": true,
     "planted_in_plenary": true,
     "plenary_count": 12,
     "retention": 1.0
    },
    {
     "caucus_count": 12,
     "family": "caucus",
     "fragmentation_fires": false,
     "g": 6,
     "identity_fan_in": false,
     "k": 2,
     "lost_count": 0,
     "lost_ids": [],
     "net_score": 6.0,
     "planted_in_group0": true,
     "planted_in_plenary": true,
     "plenary_count": 12,
     "retention": 1.0
    },
    {
     "caucus_count": 12,
     "family": "caucus",
     "fragmentation_fires": true,
     "g": 4,
     "identity_fan_in": false,
     "k": 3,
     "lost_count": 4,
     "lost_ids": [
      "F00",
      "F03",
      "F06",
      "F09"
     ],
     "net_score": 2.6666666666666665,
     "planted_in_group0": true,
     "planted_in_plenary": false,
     "plenary_count": 8,
     "retention": 0.6666666666666666
    },
    {
     "caucus_count": 12,
     "family": "committee",
     "fragmentation_fires": true,
     "g": 3,
     "identity_fan_in": false,
     "k": 4,
     "lost_count": 6,
     "lost_ids": [
      "F00",
      "F01",
      "F04",
      "F05",
      "F08",
      "F09"
     ],
     "net_score": 1.5,
     "planted_in_group0": true,
     "planted_in_plenary": false,
     "plenary_count": 6,
     "retention": 0.5
    },
    {
     "caucus_count": 12,
     "family": "committee",
     "fragmentation_fires": true,
     "g": 2,
     "identity_fan_in": false,
     "k": 6,
     "lost_count": 8,
     "lost_ids": [
      "F00",
      "F01",
      "F02",
      "F03",
      "F06",
      "F07",
      "F08",
      "F09"
     ],
     "net_score": 0.6666666666666666,
     "planted_in_group0": true,
     "planted_in_plenary": false,
     "plenary_count": 4,
     "retention": 0.3333333333333333
    },
    {
     "caucus_count": 12,
     "family": "flat-peer",
     "fragmentation_fires": false,
     "g": 1,
     "identity_fan_in": true,
     "k": 12,
     "lost_count": 0,
     "lost_ids": [],
     "net_score": 1.0,
     "planted_in_group0": true,
     "planted_in_plenary": true,
     "plenary_count": 12,
     "retention": 1.0
    }
   ]
  },
  "n": 12,
  "rule": "lossy fan-in loses unique cell facts iff k > c; flat g==1 is identity"
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0031/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0031/probe1_fragmentation.py",
   "id": "probe1",
   "role": "fragmentation"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0031/probe2_negative_control.py",
   "id": "probe2",
   "role": "negative-control-reviewer"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "FIRES planted=F00 in_caucus=True in_plenary=False lost_count=8 k=6 family=committee",
   "description": "The check FIRES when planted F00 exists in group-0 transcript and is absent from plenary (lossy committee k=6 c=2). It is SILENT on flat identity fan-in where F00 reaches plenary and lost_count=0.",
   "fired_on_bad_state": true,
   "fires_on": "k=6 c=2 committee overflow",
   "fires_on_bad": true,
   "good_state_output": "SILENT planted=F00 in_caucus=True in_plenary=True lost_count=0 k=12 family=flat-peer",
   "id": "CNL0031-C1",
   "kind": "both-states-fragmentation",
   "rejects": "lossy committee k=6 c=2 that drops planted F00 from plenary while claiming no fragmentation",
   "silent_on": "k=12 flat identity fan-in",
   "silent_on_good": true,
   "silent_on_good_state": true
  }
 ],
 "output_schema_catalog": "command-center/schema/council-design-note.schema.json",
 "output_schema_note": "Catalog output_schema is a $ref shim to ast-integrate.invalid; jsonschema 4.10 on this host tries to fetch it and raises RefResolutionError. Local note.schema.json is the live contract and requires negative_controls[].rejects so a stripped-rejects mutant is a schema failure. G-1 is parse+sentinel+named probes.",
 "output_schema_on_tree": "command-center/p2-wave/probes/CNL-0031/note.schema.json",
 "question": "Flat peer, committee and caucus are the same topology family at different grouping granularity - what is the parameter that unifies them, and at what setting does sub-grouping start losing cross-group information instead of adding parallelism?",
 "reviewer": {
  "counterexample": {
   "c": 2,
   "family": "caucus",
   "g": 6,
   "k": 2,
   "lost_count": 0,
   "lost_ids": [],
   "n": 12,
   "planted_in_plenary": true,
   "what_it_refutes": "any k<n subgrouping fragments cross-group information"
  },
  "fresh_context": true,
  "independent": true,
  "method": "Named probe2 re-tabulates lost_count from serialized fact_ids via recount.py (not the author's answer prose) and requires a live k==c lossless instance.",
  "reviewer_id": "CNL-0031-probe2-recount-counterexample",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0031",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0031/probe1_fragmentation.py",
   "id": "T1-fragmentation",
   "name": "Fragmentation probe: caucus-exclusive fact never reaching plenary; flat demonstrates zero loss",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0031/probe2_negative_control.py",
   "id": "T2-negative-control",
   "name": "Negative control recorded verbatim plus independent lossless counterexample",
   "result": "PASS"
  }
 ],
 "title": "Flat, committee and caucus grouping: when structure helps and when it fragments",
 "ts": "2026-08-25T00:55:58Z",
 "unifying_parameter": {
  "companion": "c",
  "companion_definition": "Fan-in / rapporteur capacity: facts each cell may emit to plenary. Flat identity fan-in sets c_eff = n when g==1.",
  "definition": "Cell cardinality of a partition of an n-member roster. Flat-peer, committee and caucus are labels on ranges of k, not distinct topology families.",
  "family_labels_n12": {
   "1": "singleton-fanin",
   "12": "flat-peer",
   "2": "caucus",
   "3": "caucus",
   "4": "committee",
   "6": "committee"
  },
  "name": "partition-grain",
  "symbol": "k"
 },
 "unit_id": "CNL-0031"
}
