{
 "answer": "A balance constraint ranges over a closed, pre-declared partition of interest-bearing stakeholder classes, not over model, vendor, expertise, or protocol role. Each seat carries exactly one stakeholder_class from that catalog. The metric is L1 / total-variation distance from a declared occupancy target T: I = (1/2) * sum_c |O[c] - T[c]|. A roster is balanced iff I <= I_star, with I_star written before any roster is scored. Richness D = |{c : O[c] > 0}| is not the metric: a roster can seat every class and still miss quota, and a uniform 1-each roster can miss a non-uniform target. Nobody disputes the arithmetic once C, T, O, and I_star are declared; they can only dispute those declarations.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0017-stakeholder-balanced-selection-the-taxonomy-and-the-balanc.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "catalog-named-schema-shim"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0017/note.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0017/metric.py",
   "role": "metric"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0017/fixtures/threshold.json",
   "role": "a-priori-threshold"
  }
 ],
 "claims": [
  {
   "anchor": "taxonomy.classes",
   "claim": "Balance ranges over a closed stakeholder_class catalog, not over the nine CNL-0005 dials.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py",
   "claim": "I_unbalanced > I_balanced and I_star declared before scoring.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/probe2_both_states.py",
   "claim": "The check FIRES on planted-bad and is SILENT on known-good.",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs",
   "claim": "Catalog source files 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json were read on this tree.",
   "id": "C4",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0017",
 "dependency_CNL_0005": {
  "artifact": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
  "catalog_nine_dials": [
   "model",
   "vendor",
   "expertise",
   "role",
   "authority",
   "vote_weight",
   "tools",
   "effort",
   "context"
  ],
  "note": "stakeholder_class is an additional per-seat label. Protocol role is a CNL-0005 dial; interest class is not. Fixtures carry both so a chair can be an owner or an adversary.",
  "on_this_tree": false,
  "verdict": "NOT-CHECKED"
 },
 "distinction": "Balance is L1 distance from a declared occupancy target. Diversity is richness D (how many classes appear). A roster can have D=|C| and still have I>0; a uniform 1-each roster can have I>0 against a non-uniform target. The two are not interchangeable.",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py:counter_census",
   "claim": "Signal 1: collections.Counter census matches I_balanced=0 and I_unbalanced=1 at I_star=0.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/probe1_score_order.py:shell_census",
   "claim": "Signal 2: sort | uniq -c on the same class column agrees with Counter; different process, not a second Python Counter.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/probe2_both_states.py",
   "claim": "Both-states: SILENT on roster-balanced, FIRES on roster-unbalanced-merely-diverse.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0017/fixtures/roster-negative.json",
   "claim": "Negative control: all-owner roster FIRES with I=6 and five unfilled target classes.",
   "verdict": "CONFIRMED"
  }
 ],
 "format": "council-design-note+json",
 "generated_at": "2026-08-25T00:57:16Z",
 "irreducible_verdict_requirements": [
  "A deliberately unbalanced roster must score worse than a balanced one, and I_star must be declared before fixtures are scored.",
  "Both-states: the check FIRES on a planted-bad fixture and is SILENT on the known-good one; both runs recorded verbatim.",
  "Negative control recorded verbatim: state what the check does on the state it is meant to reject."
 ],
 "markdown_body": "# CNL-0017 Stakeholder-balanced selection\n\nWhat stakeholder taxonomy does a balance constraint range over, and what metric decides that a roster is balanced rather than merely diverse in a way nobody can dispute?\n\nA balance constraint ranges over a closed, pre-declared partition of interest-bearing stakeholder classes, not over model, vendor, expertise, or protocol role. Each seat carries exactly one stakeholder_class from that catalog. The metric is L1 / total-variation distance from a declared occupancy target T: I = (1/2) * sum_c |O[c] - T[c]|. A roster is balanced iff I <= I_star, with I_star written before any roster is scored. Richness D = |{c : O[c] > 0}| is not the metric: a roster can seat every class and still miss quota, and a uniform 1-each roster can miss a non-uniform target. Nobody disputes the arithmetic once C, T, O, and I_star are declared; they can only dispute those declarations.\n\n## Taxonomy (closed)\nAxis: stakeholder_class. One label per seat. Labels are not CNL-0005 dials.\n\n- owner: authority to accept or reject\n- operator: duty to run the result\n- end_user: lives with the output\n- implementer: must build or maintain\n- adversary: tasked to reject or break\n- compliance: policy or constraint bearer\n\n## Metric\nI = (1/2) sum |O-T|. Balanced iff I <= I_star. This fixture: I_star=0.\nRejected: richness, min-share (equal on the 2-1-2 vs 3-1-1 pair),\nmax/min ratio (punishes a declared non-uniform target).\n\n## Loud unfilled class\nAny c with T[c] > 0 and O[c] == 0 is listed in unfilled[]. The selector does not proceed as if the mix were satisfied.\n\nSUCCESS:CNL-0017",
 "metric": {
  "I_star": 0,
  "I_star_declared_before_scoring": true,
  "decision": "balanced iff I <= I_star",
  "formula": "I = (1/2) * sum_c |O[c] - T[c]|",
  "id": "l1-tv-to-declared-target",
  "rejected_metrics": [
   {
    "id": "richness-D",
    "why": "roster-unbalanced-merely-diverse has D=|C| and I=1; richness cannot fail it"
   },
   {
    "id": "min-share",
    "why": "balanced 2-1-2-1-1-1 and unbalanced 3-1-1-1-1-1 both have min share 1/8"
   },
   {
    "id": "max-min-ratio",
    "why": "a declared target of 2 owners among 6 seats has max/min=2 when exact; evenness would punish a legal mix"
   }
  ],
  "target": {
   "adversary": 1,
   "compliance": 1,
   "end_user": 2,
   "implementer": 1,
   "operator": 1,
   "owner": 2
  },
  "threshold_path": "command-center/p2-wave/probes/CNL-0017/fixtures/threshold.json"
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0017/probe1_score_order.py",
   "id": "probe1"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0017/probe2_both_states.py",
   "id": "probe2"
  }
 ],
 "negative_controls": [
  {
   "fixture": "command-center/p2-wave/probes/CNL-0017/fixtures/roster-negative.json",
   "id": "all-owner-roster",
   "intended_reject_state": "every seat labelled owner",
   "silent_on_known_good": true,
   "what_the_check_does": "FIRES because I=6 > I_star=0; unfilled=['operator', 'end_user', 'implementer', 'adversary', 'compliance']; D=1"
  }
 ],
 "question": "What stakeholder taxonomy does a balance constraint range over, and what metric decides that a roster is balanced rather than merely diverse in a way nobody can dispute?",
 "reviewer": {
  "author_metric_refute": "REFUTE-ATTEMPTED-NO-COUNTEREXAMPLE",
  "counterexample_instance": {
   "D": 6,
   "I": 1,
   "I_star": 0,
   "against": "richness-as-balance (D == |C| implies balanced)",
   "effect": "REFUTES richness-as-balance. Does not refute L1-to-target.",
   "roster_id": "roster-unbalanced-merely-diverse"
  },
  "independent": true,
  "method": "Reverse-walk seat tally and re-derive I as half the L1 gap. Did not accept the design-note prose as evidence.",
  "reviewer_id": "CNL-0017-independent-reverse-recount",
  "scope_not_agreement": true,
  "second_instance": {
   "D": 6,
   "I": 1,
   "against": "evenness-as-balance",
   "effect": "Uniform 1-each is even and richer than a target that wants 2 owners and 0 compliance, but I=1 so it is not balanced.",
   "roster_id": "roster-even-off-target"
  },
  "verdict": "STANDS"
 },
 "schema": "command-center/schema/council-design-note.schema.json",
 "schema_note": "Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... . jsonschema 4.10 fetches that URL. Live validation uses the per-unit note.schema.json so the state enum and metric/scores requirements stay non-vacuous without a network retrieve.",
 "scores": {
  "I_star": 0,
  "balanced": {
   "D": 6,
   "I": 0,
   "fires": false,
   "observed": {
    "adversary": 1,
    "compliance": 1,
    "end_user": 2,
    "implementer": 1,
    "operator": 1,
    "owner": 2
   }
  },
  "even_off_target": {
   "D": 6,
   "I": 1,
   "fires": true
  },
  "negative": {
   "D": 1,
   "I": 6,
   "fires": true,
   "unfilled": [
    "operator",
    "end_user",
    "implementer",
    "adversary",
    "compliance"
   ]
  },
  "threshold_sha256": "53273cecb734d9f311145a76e62b26dd9985937d71188faa2c083558523cf773",
  "unbalanced": {
   "D": 6,
   "I": 1,
   "fires": true,
   "observed": {
    "adversary": 1,
    "compliance": 1,
    "end_user": 1,
    "implementer": 1,
    "operator": 1,
    "owner": 3
   }
  }
 },
 "sentinel": "SUCCESS:CNL-0017",
 "source_inputs": [
  {
   "on_this_tree": false,
   "path": "_USER-PROMPTS.md:10746-10767",
   "verdict": "NOT-CHECKED"
  },
  {
   "on_this_tree": false,
   "path": "_USER-PROMPTS.md:10915-10946",
   "verdict": "NOT-CHECKED"
  },
  {
   "on_this_tree": false,
   "path": "11-COUNCIL-SPECIFICATION.schema.json",
   "verdict": "NOT-CHECKED"
  },
  {
   "on_this_tree": false,
   "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "verdict": "NOT-CHECKED"
  },
  {
   "on_this_tree": false,
   "path": "CNL-0005 design note",
   "verdict": "NOT-CHECKED"
  }
 ],
 "state": "SUCCESS",
 "taxonomy": {
  "axis": "stakeholder_class",
  "classes": [
   {
    "id": "owner",
    "interest": "authority to accept or reject the decision"
   },
   {
    "id": "operator",
    "interest": "duty to run the result day to day"
   },
   {
    "id": "end_user",
    "interest": "lives with the output; no implementation duty"
   },
   {
    "id": "implementer",
    "interest": "must build or maintain the change"
   },
   {
    "id": "adversary",
    "interest": "tasked to reject or break the proposal"
   },
   {
    "id": "compliance",
    "interest": "policy or constraint bearer"
   }
  ],
  "closed": true,
  "disjoint_from_cnl_0005_dials": [
   "model",
   "vendor",
   "expertise",
   "role",
   "authority",
   "vote_weight",
   "tools",
   "effort",
   "context"
  ],
  "id": "CNL-0017.stakeholder.v1",
  "one_label_per_seat": true,
  "undeclared_is_invalid": true
 },
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0017/probe1_score_order.py",
   "id": "probe1-score-order",
   "requirement": "unbalanced I worse than balanced; I_star declared before scoring",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0017/probe2_both_states.py",
   "id": "probe2-both-states",
   "requirement": "FIRES on planted-bad, SILENT on known-good, negative control verbatim",
   "result": "PASS"
  }
 ],
 "tests_required_record": [
  "a deliberately unbalanced roster must score worse than a balanced one, and the threshold must be declared before the fixtures are scored",
  "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
  "negative control recorded verbatim: state what the check does on the state it is meant to reject"
 ],
 "title": "Stakeholder-balanced selection: the taxonomy and the balance metric",
 "unfilled_class_rule": "If T[c] > 0 and O[c] == 0 the class is reported in unfilled[] and balanced is false. The council does not silently continue as if the mix were met. Downstream IMP-0271 implements the selector; this unit only defines the census and the loud miss.",
 "unit_id": "CNL-0017",
 "validated_against": "command-center/p2-wave/probes/CNL-0017/note.schema.json"
}
