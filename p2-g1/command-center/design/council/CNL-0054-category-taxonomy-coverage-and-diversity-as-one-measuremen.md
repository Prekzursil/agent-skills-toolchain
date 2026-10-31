{
 "answer": "Category targets range over the closed, versioned taxonomy council.idea-category.v1 (8 ids). Coverage is support/|T| against that declared set, never against observed labels. High coverage does NOT distinguish genuine spread from clustering in one popular category: the token-coverage bag and the spread bag both score C=1.000, while the joint Pielou score over T is 0.563225 vs 1.000000. The one measurement that gates a stopping rule is Pielou evenness H/ln(|T|) over the full declared taxonomy; threshold 0.75. Clustered (2 categories, same n=24) scores 0.333333 and the detector FIRES; spread is SILENT.",
 "answers": {
  "coverage_computation": "C = |{c in T : occupancy[c] >= 1}| / |T|, equivalently |set(labels) \u2229 T| / |T|. The denominator is the declared taxonomy, never the set of observed labels.",
  "high_coverage_does_not_distinguish_spread": "No. Token-coverage and genuine spread both score C=1.000. Joint Pielou over full T is 0.563225 vs 1.000000; the stopping gate uses the joint score, not coverage alone.",
  "taxonomy_range": "Category targets range only over the closed declared set council.idea-category.v1: mechanism, interface, verification, failure-mode, economics, governance, security, operability (|T|=8). Observed labels do not extend T."
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0054/artifact.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0054/taxonomy.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0054/measure.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0054/fixtures.py",
   "role": "supporting"
  }
 ],
 "both_states": {
  "known_good": "spread",
  "known_good_silent": true,
  "planted_bad": "clustered",
  "planted_bad_fires": true,
  "verbatim_bad": "PLANTED-BAD clustered: valid=True n=24 coverage=0.250000000000 joint=0.333333333333 fires=True reason=below-threshold",
  "verbatim_good": "KNOWN-GOOD spread: valid=True n=24 coverage=1.000000000000 joint=1.000000000000 fires=False reason=at-or-above-threshold"
 },
 "claims": [
  {
   "claim": "At the same raw count n=24, the 2-category clustered bag scores joint=0.333333333333 strictly below the 8-category spread bag joint=1.000000000000.",
   "id": "C-CLUSTERED-LT-SPREAD",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "Coverage is identical for token-coverage and spread (C=1.0); the joint score distinguishes them and the detector FIRES on token-coverage.",
   "id": "C-COVERAGE-NOT-SPREAD",
   "verdict": "CONFIRMED"
  },
  {
   "claim": "A label outside T is a validity failure (reason=out-of-taxonomy-label), not extra coverage.",
   "id": "C-OUT-OF-TAXONOMY",
   "verdict": "CONFIRMED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0054",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0054/taxonomy.json:4",
   "claim": "T is a closed 8-id taxonomy; observed labels do not extend it.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0054/fixtures.py:41",
   "claim": "Clustered (2 categories) joint score is strictly lower than spread at the same raw count n=24.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0054/measure.py:63",
   "claim": "Coverage-only is identical for token-coverage and spread (C=1.0); the joint Pielou score distinguishes them.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:36975",
   "claim": "Catalog question is the question this note answers; completion sentinel SUCCESS:CNL-0054 is on the artifact.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs_on_this_tree",
   "claim": "Harness-restore council spec bytes were read on this worktree and the taxonomy was copied from them.",
   "verdict": "REFUTED"
  }
 ],
 "fixture_scores": {
  "clustered": {
   "coverage": 0.25,
   "fires": true,
   "joint": 0.33333333333333337,
   "n": 24,
   "occupancy": {
    "economics": 0,
    "failure-mode": 0,
    "governance": 0,
    "interface": 12,
    "mechanism": 12,
    "operability": 0,
    "security": 0,
    "verification": 0
   },
   "reason": "below-threshold",
   "threshold": 0.75,
   "valid": true
  },
  "invalid_label": {
   "coverage": null,
   "fires": true,
   "invalid_ids": [
    "X01"
   ],
   "joint": null,
   "n": 23,
   "occupancy": {
    "economics": 3,
    "failure-mode": 3,
    "governance": 3,
    "interface": 3,
    "mechanism": 2,
    "operability": 3,
    "security": 3,
    "verification": 3
   },
   "reason": "out-of-taxonomy-label",
   "threshold": 0.75,
   "valid": false
  },
  "spread": {
   "coverage": 1.0,
   "fires": false,
   "joint": 1.0,
   "n": 24,
   "occupancy": {
    "economics": 3,
    "failure-mode": 3,
    "governance": 3,
    "interface": 3,
    "mechanism": 3,
    "operability": 3,
    "security": 3,
    "verification": 3
   },
   "reason": "at-or-above-threshold",
   "threshold": 0.75,
   "valid": true
  },
  "token_coverage": {
   "coverage": 1.0,
   "fires": true,
   "joint": 0.5632254405007219,
   "n": 24,
   "occupancy": {
    "economics": 1,
    "failure-mode": 1,
    "governance": 1,
    "interface": 1,
    "mechanism": 17,
    "operability": 1,
    "security": 1,
    "verification": 1
   },
   "reason": "below-threshold",
   "threshold": 0.75,
   "valid": true
  }
 },
 "measurement": {
  "coverage_alone_insufficient": true,
  "coverage_definition": "C = |{c in T : n_c >= 1}| / |T|. Diagnostic only. Token-coverage (one idea per category, remainder dumped into one popular category) yields C=1.0 and must not pass the joint gate.",
  "detector": "FIRES when joint < 0.75 or any idea label is outside T. SILENT when every label is in T and joint >= 0.75.",
  "formula": "H / ln(|T|) where H is Shannon entropy of occupancy p_i = n_i / N over every declared category including unoccupied ones (p_i=0 contributes 0 to H). This is one number: unoccupied categories lower H, so coverage and evenness are not separately gated.",
  "name": "pielou_evenness_over_declared_taxonomy",
  "threshold_reject_below": 0.75
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0054/probe1_cluster_vs_spread.py",
   "id": "probe1"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0054/probe2_independent_recount.py",
   "id": "probe2"
  }
 ],
 "negative_controls": [
  {
   "id": "NC-CLUSTERED",
   "rejects": "24 ideas in exactly 2 of 8 declared categories at the same raw count as the spread bag",
   "verbatim": "on clustered the check FIRES (joint=0.333333333333 < threshold=0.75); it does not stay silent and it does not treat C=0.25 as spread"
  },
  {
   "id": "NC-TOKEN-COVERAGE",
   "rejects": "one idea in every category with the remainder dumped into mechanism (C=1.0, not genuine spread)",
   "verbatim": "coverage token=1.0 spread=1.0; joint token=0.563225440501 spread=1.000000000000; detector FIRES on token-coverage"
  },
  {
   "id": "NC-OUT-OF-TAXONOMY",
   "rejects": "label 'popular' which is not in T",
   "verbatim": "invalid_label fires=True reason=out-of-taxonomy-label invalid_ids=['X01']"
  }
 ],
 "question": "What taxonomy do category targets range over, how is coverage computed against it, and does a high coverage score distinguish genuine spread from many ideas clustered in one popular category?",
 "residual_unknowns": [
  "Whether a later CouncilSpec file on another tree already names a different closed category list. If it does, this v1 list is the operational range until that file is present and a remap unit runs. Unoccupied-category Shannon vs occupied-only evenness is settled here in favour of full-T Pielou because occupied-only evenness scores 1.0 on a 50/50 two-category bag.",
  "Catalog output_schema council-design-note.schema.json is a generated $ref shim. jsonschema 4.10 RefResolver fetches https://ast-integrate.invalid/... and raises RefResolutionError. This unit validates against the local artifact.schema.json instead of rebuilding the catalog shim."
 ],
 "reviewer": {
  "independent": true,
  "method": "Occupancy via len(list of idea ids) per category; coverage via |set(labels) \u2229 T| / |T|. Does not call measure.score.",
  "reviewer_id": "CNL-0054-probe2-independent-recount",
  "verdict": "PASS"
 },
 "schema_validation": {
  "catalog_schema": "command-center/schema/council-design-note.schema.json",
  "catalog_schema_live": false,
  "garbage_rejected": 3,
  "good_error_count": 0,
  "schema": "command-center/p2-wave/probes/CNL-0054/artifact.schema.json"
 },
 "sentinel": "SUCCESS:CNL-0054",
 "source_inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false,
  "note": "Catalog inputs are Windows harness-restore paths not present here. The taxonomy is an operational definition this unit supplies, not a transcription of unread bytes."
 },
 "state": "SUCCESS",
 "taxonomy": {
  "categories": [
   {
    "description": "How a proposed idea works as a mechanism, algorithm, or control.",
    "id": "mechanism"
   },
   {
    "description": "Agent- or user-facing surface: prompts, APIs, files, UX.",
    "id": "interface"
   },
   {
    "description": "How we know it worked: probes, both-states controls, oracles.",
    "id": "verification"
   },
   {
    "description": "How it breaks, silent-loss shapes, and named residuals.",
    "id": "failure-mode"
   },
   {
    "description": "Cost, quota, budget dials, and exhaustion behaviour.",
    "id": "economics"
   },
   {
    "description": "Who decides, review, roster, recusal, owner gates.",
    "id": "governance"
   },
   {
    "description": "Trust boundaries, secrets, abuse, and authorization.",
    "id": "security"
   },
   {
    "description": "Run, observe, recover, retry, and operational cadence.",
    "id": "operability"
   }
  ],
  "closed": true,
  "declaration": "T is declared before scoring. Observed labels cannot grow T. An out-of-taxonomy label is a validity failure, not extra coverage.",
  "id": "council.idea-category.v1",
  "range_rule": "Category targets and coverage scores range only over this declared set. Observed idea labels do not extend the range. A label outside the set is invalid, not a new category and not extra coverage.",
  "version": 1
 },
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0054/probe1_cluster_vs_spread.py",
   "id": "T-CLUSTERED-LT-SPREAD",
   "name": "a clustered fixture (all ideas in 2 categories) must score lower than a spread fixture at the same raw count",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0054/probe1_cluster_vs_spread.py",
   "id": "T-BOTH-STATES",
   "name": "the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0054/probe2_independent_recount.py",
   "id": "T-INDEPENDENT-RECOUNT",
   "name": "reviewer re-tabulates occupancy via list-of-ids length and coverage via set intersection; disagreement blocks",
   "result": "PASS"
  }
 ],
 "title": "Category taxonomy, coverage and diversity as one measurement",
 "unit_id": "CNL-0054"
}
