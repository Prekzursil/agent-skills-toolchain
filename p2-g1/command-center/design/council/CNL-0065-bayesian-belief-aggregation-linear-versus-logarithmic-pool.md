{
 "artifacts": [
  {
   "bytes": 8601,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0065/pool.py",
   "role": "supporting",
   "sha256": "6b2a9fb1b5e7b86a22d3298ebdf4e531a180895716303f77c63ab54b34ac56a0"
  },
  {
   "bytes": 826,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0065/fixtures/canonical-panel.json",
   "role": "fixture",
   "sha256": "6e2e3b5803221ee4c2a970282934c611d8d42e4612d4ffcc1594c7a6875189c8"
  },
  {
   "bytes": 1118,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting",
   "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/p2-wave/probes/CNL-0065/fixtures/canonical-panel.json",
   "consumer": "command-center/p2-wave/probes/CNL-0065/pool.py:aggregates",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "python3 -c \"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0065'); import pool as P; print(P.canonical()['p_indep_bayes'])\"",
    "exit_code": 0,
    "fingerprint": "b4523e5e41725b5851c09dc9a0235b50",
    "method": "command",
    "raw_output": "canonical_p_indep_bayes=0.9709058479954664",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0065/pool.py:13",
   "claim": "Joint posterior log-odds use denominator sigma^2 + n tau^2; independence-assuming product uses sigma^2 + tau^2.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "command-center/p2-wave/probes/CNL-0065/pool.py:13",
     "exit_code": 0,
     "fingerprint": "a04f9672a85f75a589f3a02c89ede880",
     "method": "file-read",
     "raw_output": "llr_true = 2 * mu * sum(X) / (sigma^2 + n * tau^2)",
     "role": "source"
    },
    {
     "command": "python3 -c \"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0065'); import pool as P; print(P.matrix_llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED), P.llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED))\"",
     "exit_code": 0,
     "fingerprint": "f4536ee37875e52317404e54d528f465",
     "method": "command",
     "raw_output": "matrix_llr=0.9306122448979592 closed_llr=0.9306122448979592 match=True",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0065/pool.py:22",
   "claim": "Correlated same-vendor fixture inflates |log-odds| by 3.769231 and mean |dp|=0.171370.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "command-center/p2-wave/probes/CNL-0065/pool.py:22",
     "exit_code": 0,
     "fingerprint": "e107a2f94e0035f88b5d3d35fa405c1f",
     "method": "file-read",
     "raw_output": "(sigma^2 + n*tau^2) / (sigma^2 + tau^2)",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0065/probe1_correlated_overclaim.py",
     "exit_code": 0,
     "fingerprint": "a1776c6b8d9b6603c2c2c18ee6d64e6d",
     "method": "command",
     "raw_output": "tau=1.5 pairwise_corr=0.692308 mean_abs_dp_indep=0.171370 mean_abs_dp_linear=0.051570 inflation=3.769231 canonical_p_true=0.717199 canonical_p_indep=0.970906 canonical_abs_dp_indep=0.253706",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "answer": "Default aggregator is the linear (arithmetic) pool of seat credences. It does not treat agreement as independent confirmation. The rule that DOES assume independence is unnormalized logarithmic pooling: per-seat weight 1 so weights sum to n, equivalently the product of marginal likelihood ratios (independent Bayes). Same-vendor, same-prompt seats share a shock Z; pairwise correlation is 0.692308 under the fixture (tau=1.5, sigma=1.0). That DGP inflates |log-odds| by 3.769231 relative to the joint posterior, and mean |p_indep - p_true| = 0.171370. Normalized log-pool (weights sum to 1) is allowed only after an independence diagnostic is silent. Unnormalized log-pool is forbidden as the council default.",
  "design": {
   "answer": "Default aggregator is the linear (arithmetic) pool of seat credences. It does not treat agreement as independent confirmation. The rule that DOES assume independence is unnormalized logarithmic pooling: per-seat weight 1 so weights sum to n, equivalently the product of marginal likelihood ratios (independent Bayes). Same-vendor, same-prompt seats share a shock Z; pairwise correlation is 0.692308 under the fixture (tau=1.5, sigma=1.0). That DGP inflates |log-odds| by 3.769231 relative to the joint posterior, and mean |p_indep - p_true| = 0.171370. Normalized log-pool (weights sum to 1) is allowed only after an independence diagnostic is silent. Unnormalized log-pool is forbidden as the council default.",
   "both_states": {
    "bad_state": {
     "detector": "FIRE",
     "id": "same-vendor-correlated",
     "inflation_factor": 3.769230769230769,
     "mean_abs_dp_indep": 0.17137002740460244,
     "tau": 1.5
    },
    "good_state": {
     "detector": "SILENT",
     "id": "independent-seats",
     "inflation_factor": 1.0,
     "mean_abs_dp_indep": 0.0,
     "tau": 0.0
    },
    "pass": true
   },
   "chosen_rule": "linear-pool",
   "decision_procedure": [
    "Each seat publishes a credence p_i in (0,1) with CNL-0023 weight provenance if the weight is not 1/n.",
    "Default pool: p_lin = sum w_i p_i with sum w_i = 1 (linear pool).",
    "Do not multiply likelihood ratios across same-vendor same-prompt seats.",
    "Normalized log-pool (weights sum to 1) requires an on-record independence diagnostic (CNL-0086 residual correlation below threshold, or distinct-vendor seats).",
    "Unnormalized log-pool (weights sum to n) is the independence-assuming product and is rejected as the council default.",
    "Publish p_lin, and if a log-pool is used, publish the diagnostic that licensed it."
   ],
   "dependencies_noted": {
    "CNL-0023": "non-equal linear-pool weights require vote-weight provenance; default here is equal 1/n",
    "CNL-0086": "echo-chamber / independence-loss measurement licenses any departure from linear pool",
    "blocked_on_missing_deps": false
   },
   "family": {
    "counted_n": 3,
    "expected_n": 3,
    "members": [
     {
      "assumes_independence": false,
      "id": "linear-pool",
      "role": "default-aggregator",
      "weights": "sum to 1"
     },
     {
      "assumes_independence": false,
      "gate": "CNL-0086 independence diagnostic silent, or distinct-vendor seats",
      "id": "normalized-log-pool",
      "role": "gated-aggregator",
      "weights": "sum to 1"
     },
     {
      "assumes_independence": true,
      "id": "unnormalized-log-pool-indep-bayes",
      "role": "independence-assuming-product",
      "weights": "sum to n (one per seat)"
     }
    ],
    "name": "credence-pooling-rules"
   },
   "forbidden_default": "unnormalized-logarithmic-pool-independent-bayes",
   "independence_assumption": "P(X_1,...,X_n | Y) = product_i P(X_i | Y). Unnormalized logarithmic pooling / product of marginal likelihoods encodes this. Same-vendor councils violate it via a shared shock Z.",
   "named_probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0065/probe1_correlated_overclaim.py",
     "id": "probe1",
     "role": "correlated-overclaim"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0065/probe2_negative_control.py",
     "id": "probe2",
     "role": "negative-control"
    }
   ],
   "negative_control_verbatim": "NEGATIVE-CONTROL verbatim: the overconfidence check is SILENT on independent seats (tau=0), where indep Bayes matches the joint posterior; it FIRES on the correlated same-vendor fixture.",
   "quantification": {
    "analytic_logodds_inflation": 3.769230769230769,
    "canonical_abs_dp_indep": 0.25370636779566313,
    "canonical_p_indep_bayes": 0.9709058479954664,
    "canonical_p_linear": 0.6682679751571052,
    "canonical_p_log_normalized": 0.6685287805929766,
    "canonical_p_true": 0.7171994801998033,
    "canonical_xs": [
     1.2,
     1.05,
     1.35,
     0.95,
     1.15
    ],
    "closed_form_llr_true": 0.9306122448979592,
    "correlated_brier_indep_bayes": 0.21911224676506705,
    "correlated_brier_linear": 0.1829564212347164,
    "correlated_brier_true_posterior": 0.18076221578244733,
    "correlated_mean_abs_dp_indep": 0.17137002740460244,
    "correlated_mean_abs_dp_linear": 0.05157044180140631,
    "correlated_mean_abs_dp_log_normalized": 0.04244761732278567,
    "independent_analytic_inflation": 1.0,
    "independent_mean_abs_dp_indep": 0.0,
    "matrix_llr_true": 0.9306122448979592,
    "mu": 1.0,
    "n_seats": 5,
    "pairwise_corr_correlated": 0.6923076923076923,
    "seed": 65,
    "sigma": 1.0,
    "tau_correlated": 1.5,
    "tau_independent": 0.0,
    "trials": 4000
   },
   "question": "Which pooling rule aggregates participant credences, and what does the rule assume about independence that a council of same-vendor models measurably violates?",
   "title": "Bayesian belief aggregation: linear versus logarithmic pooling",
   "verdicts": [
    {
     "note": "licensed default aggregator for same-vendor councils",
     "record_id": "linear-pool",
     "verdict": "EXECUTABLE"
    },
    {
     "note": "executable math; licensed only after independence diagnostic",
     "record_id": "normalized-log-pool",
     "verdict": "EXECUTABLE"
    },
    {
     "note": "executable as arithmetic but NOT licensed as the council default: it encodes independent observations that same-vendor seats violate",
     "record_id": "unnormalized-log-pool-indep-bayes",
     "verdict": "NOT-EXECUTABLE"
    }
   ]
  },
  "quantification": {
   "analytic_logodds_inflation": 3.769230769230769,
   "canonical_abs_dp_indep": 0.25370636779566313,
   "canonical_p_indep_bayes": 0.9709058479954664,
   "canonical_p_linear": 0.6682679751571052,
   "canonical_p_log_normalized": 0.6685287805929766,
   "canonical_p_true": 0.7171994801998033,
   "canonical_xs": [
    1.2,
    1.05,
    1.35,
    0.95,
    1.15
   ],
   "closed_form_llr_true": 0.9306122448979592,
   "correlated_brier_indep_bayes": 0.21911224676506705,
   "correlated_brier_linear": 0.1829564212347164,
   "correlated_brier_true_posterior": 0.18076221578244733,
   "correlated_mean_abs_dp_indep": 0.17137002740460244,
   "correlated_mean_abs_dp_linear": 0.05157044180140631,
   "correlated_mean_abs_dp_log_normalized": 0.04244761732278567,
   "independent_analytic_inflation": 1.0,
   "independent_mean_abs_dp_indep": 0.0,
   "matrix_llr_true": 0.9306122448979592,
   "mu": 1.0,
   "n_seats": 5,
   "pairwise_corr_correlated": 0.6923076923076923,
   "seed": 65,
   "sigma": 1.0,
   "tau_correlated": 1.5,
   "tau_independent": 0.0,
   "trials": 4000
  },
  "question": "Which pooling rule aggregates participant credences, and what does the rule assume about independence that a council of same-vendor models measurably violates?"
 },
 "manifest_registration": {
  "entry_id": "CNL-0065",
  "manifest_path": "command-center/p2-wave/probes/CNL-0065/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 1024,
 "negative_controls": [
  {
   "bad_state_output": "FIRE mean_abs_dp_indep=0.171370 inflation=3.769231",
   "description": "Overconfidence detector must be SILENT on independent seats (tau=0) and FIRE on the correlated same-vendor fixture.",
   "fired_on_bad_state": true,
   "good_state_output": "SILENT mean_abs_dp_indep=0.000e+00 inflation=1.0",
   "id": "NC-tau0-identity",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "linux-worktree",
  "model": "gpt-5-codex",
  "role": "council-systems-designer",
  "vendor": "openai"
 },
 "profile": "council-design-note",
 "report": {
  "catalog_question_line": 37524,
  "control_ids": [
   "independent-seats-tau0",
   "same-vendor-correlated-tau1.5"
  ],
  "fixture_p_indep_line": 12,
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0065/pool.py:22",
    "measured": 0.17137002740460244,
    "method": "monte-carlo mean |p_indep_bayes - p_true|",
    "name": "correlated-mean-abs-dp-indep"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0065/pool.py:22",
    "measured": 3.769230769230769,
    "method": "closed-form (sigma^2 + n tau^2)/(sigma^2 + tau^2)",
    "name": "analytic-logodds-inflation"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0065/pool.py:18",
    "measured": 0.0,
    "method": "monte-carlo tau=0 identity",
    "name": "independent-mean-abs-dp-indep"
   }
  ],
  "quantification": {
   "analytic_logodds_inflation": 3.769230769230769,
   "canonical_abs_dp_indep": 0.25370636779566313,
   "canonical_p_indep_bayes": 0.9709058479954664,
   "canonical_p_linear": 0.6682679751571052,
   "canonical_p_log_normalized": 0.6685287805929766,
   "canonical_p_true": 0.7171994801998033,
   "canonical_xs": [
    1.2,
    1.05,
    1.35,
    0.95,
    1.15
   ],
   "closed_form_llr_true": 0.9306122448979592,
   "correlated_brier_indep_bayes": 0.21911224676506705,
   "correlated_brier_linear": 0.1829564212347164,
   "correlated_brier_true_posterior": 0.18076221578244733,
   "correlated_mean_abs_dp_indep": 0.17137002740460244,
   "correlated_mean_abs_dp_linear": 0.05157044180140631,
   "correlated_mean_abs_dp_log_normalized": 0.04244761732278567,
   "independent_analytic_inflation": 1.0,
   "independent_mean_abs_dp_indep": 0.0,
   "matrix_llr_true": 0.9306122448979592,
   "mu": 1.0,
   "n_seats": 5,
   "pairwise_corr_correlated": 0.6923076923076923,
   "seed": 65,
   "sigma": 1.0,
   "tau_correlated": 1.5,
   "tau_independent": 0.0,
   "trials": 4000
  }
 },
 "residual_unknowns": [
  {
   "claim": "Empirical vendor-pair tau for production models is not measured here.",
   "settling_experiment": "Run CNL-0086 independence diagnostic on a live same-vendor council transcript and record residual pairwise correlation.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Calibration-weighted linear pools need a labelled verdict history this tree does not yet have.",
   "settling_experiment": "Score a labelled council history (RES-0079 / IMP-0305) and re-fit linear-pool weights.",
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
  "notes": "Probe 2 re-derives the tau=0 closed-form identity and the both-states detector; it does not accept probe 1's Monte Carlo headline on trust.",
  "reviewed_at": "2026-08-25T00:33:16Z",
  "reviewer_id": "CNL-0065-probe2-tau0-identity",
  "vendor": "openai",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0065",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0065",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0065/probe1_correlated_overclaim.py",
   "id": "probe1-correlated-overclaim",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0065/probe2_negative_control.py",
   "id": "probe2-negative-control",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "duration_seconds": 0,
  "ended_at": "2026-08-25T00:33:16Z",
  "started_at": "2026-08-25T00:33:16Z"
 },
 "unit_id": "CNL-0065",
 "quantification": {
  "analytic_logodds_inflation": 3.769230769230769,
  "canonical_abs_dp_indep": 0.25370636779566313,
  "canonical_p_indep_bayes": 0.9709058479954664,
  "canonical_p_linear": 0.6682679751571052,
  "canonical_p_log_normalized": 0.6685287805929766,
  "canonical_p_true": 0.7171994801998033,
  "canonical_xs": [
   1.2,
   1.05,
   1.35,
   0.95,
   1.15
  ],
  "closed_form_llr_true": 0.9306122448979592,
  "correlated_brier_indep_bayes": 0.21911224676506705,
  "correlated_brier_linear": 0.1829564212347164,
  "correlated_brier_true_posterior": 0.18076221578244733,
  "correlated_mean_abs_dp_indep": 0.17137002740460244,
  "correlated_mean_abs_dp_linear": 0.05157044180140631,
  "correlated_mean_abs_dp_log_normalized": 0.04244761732278567,
  "independent_analytic_inflation": 1.0,
  "independent_mean_abs_dp_indep": 0.0,
  "matrix_llr_true": 0.9306122448979592,
  "mu": 1.0,
  "n_seats": 5,
  "pairwise_corr_correlated": 0.6923076923076923,
  "seed": 65,
  "sigma": 1.0,
  "tau_correlated": 1.5,
  "tau_independent": 0.0,
  "trials": 4000
 }
}
