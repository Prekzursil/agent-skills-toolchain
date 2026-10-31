{
  "anonymity_minimum": {
    "dependency": "CNL-0007",
    "dependency_artifact_on_this_tree": false,
    "payload_rule": "Strip seat ids; sort by (evidence_class, private_signal, rationale_id); rationale_id is a catalog string not free text; no timestamps.",
    "residual": "CNL-0007 is not delivered on this tree; this note specifies the payload minimum Delphi needs, not the full anonymity lattice."
  },
  "answer": "Return anonymous arguments between Delphi rounds: each other seat's evidence_class, private_signal, and catalog rationale_id, identity stripped and sorted, with NO distinguished group median. Of the three named payloads on the heterogeneous wrong-majority panel (theta=70, round-0 median=30.000000, no new private evidence): median_only herds (var 422.222222->105.555556, MAE 29.555556->34.333333); full_distribution also herds (var 422.222222->156.602042, MAE 29.555556->33.543210) because the labeled center remains the regression target; arguments revises (var 422.222222->0.000000, MAE 29.555556->7.818182) by reliability-weighted pooling of private signals. Relabeling the median as extra social weight (median_plus_arguments) worsens MAE to 22.300000 versus arguments-only. A homogeneous unanchored_guess panel makes even arguments FIRE the herding gate: variance collapse with no evidence differential is herding, not consensus. The runtime must compute that gate on observed estimates before claiming convergence. SUCCESS:CNL-0035",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0035-delphi-topology-iterated-anonymous-estimates-with-controll.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0035/delphi.py",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0035/fixtures/panel_heterogeneous.json",
      "role": "fixture"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0035/fixtures/panel_homogeneous_guesses.json",
      "role": "fixture"
    }
  ],
  "both_states": {
    "known_good": {
      "expect": "SILENT",
      "fixture": "fixtures/panel_heterogeneous.json",
      "herding": false,
      "mode": "arguments",
      "verbatim": "NEGATIVE_CONTROL known_good=heterogeneous-wrong-majority mode=arguments check=herding_gate SILENT herding=False verdict=REVISION reason=collapse-with-accuracy-and-evidence var0=422.222222222222 var1=0.000000000000 mae0=29.555555555556 mae1=7.818181818182"
    },
    "planted_bad": {
      "expect": "FIRE",
      "fixture": "fixtures/panel_homogeneous_guesses.json",
      "herding": true,
      "mode": "arguments",
      "verbatim": "NEGATIVE_CONTROL rejected_state=homogeneous-unanchored-guesses mode=arguments check=herding_gate FIRE herding=True verdict=HERDING reason=collapse-with-homogeneous-evidence var0=422.222222222222 var1=0.000000000000 mae0=29.555555555556 mae1=28.666666666667"
    }
  },
  "claims": [
    {
      "claim": "median_only herds toward the wrong majority median.",
      "id": "C1",
      "verdict": "CONFIRMED"
    },
    {
      "claim": "full_distribution still herds while the median stays labeled.",
      "id": "C2",
      "verdict": "CONFIRMED"
    },
    {
      "claim": "arguments without a distinguished median revises when evidence_class differs.",
      "id": "C3",
      "verdict": "CONFIRMED"
    }
  ],
  "completion_sentinel": "SUCCESS:CNL-0035",
  "distinction": "Herding is variance collapse without accuracy gain, or any collapse when every seat shares one evidence_class. Genuine revision is collapse that also cuts MAE against theta under differentiated evidence. Publishing a labeled median is not the same payload as anonymous arguments even if both shrink spread.",
  "duplicate_criterion": "Two payloads are duplicates only if they return the same fields to seats. Sharing a herding verdict does not make median_only the same protocol as full_distribution.",
  "duplicates": [],
  "enumeration": {
    "agreement": true,
    "expected_n": 3,
    "measured_n": 3,
    "signals": [
      "len(NAMED_MODES) in probes/CNL-0035/delphi.py",
      "len(taxonomy.classes) in this note"
    ]
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0035/probe1_herding.py:59",
      "claim": "median_only collapses variance toward the wrong majority median and raises MAE vs theta (herding, not convergence).",
      "line": 59,
      "path": "command-center/p2-wave/probes/CNL-0035/probe1_herding.py",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0035/delphi.py:21",
      "claim": "arguments without a distinguished median revises toward the reliability-weighted private-signal pool and lowers MAE.",
      "line": 21,
      "path": "command-center/p2-wave/probes/CNL-0035/delphi.py",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0035/probe2_negative.py:63",
      "claim": "The herding gate FIRES on a homogeneous unanchored_guess panel even under arguments, and is SILENT on heterogeneous arguments.",
      "line": 63,
      "path": "command-center/p2-wave/probes/CNL-0035/probe2_negative.py",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0035/delphi.py:86",
      "claim": "Reviewer recount of fixture variance uses E[x^2]-(E[x])^2 (second-moment identity), a different mechanism than the author's population-variance column.",
      "line": 86,
      "path": "command-center/p2-wave/probes/CNL-0035/delphi.py",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "windows-inputs-absent",
      "claim": "Windows council spec and _USER-PROMPTS.md were read from this worktree and used as the byte source for the design.",
      "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
      "verdict": "NOT-CHECKED"
    }
  ],
  "family": "delphi-anonymous-rounds",
  "herding_experiment": {
    "heterogeneous": {
      "arguments": {
        "accuracy_improved": true,
        "collapsed": true,
        "evidence_differentiated": true,
        "herding": false,
        "mae0": 29.555555555555557,
        "mae1": 7.818181818181819,
        "median0": 30.0,
        "median1": 62.18181818181818,
        "mode": "arguments",
        "panel_id": "heterogeneous-wrong-majority",
        "reason": "collapse-with-accuracy-and-evidence",
        "var0": 422.22222222222223,
        "var1": 0.0,
        "verdict": "REVISION"
      },
      "full_distribution": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": true,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 33.543209876543216,
        "median0": 30.0,
        "median1": 30.0,
        "mode": "full_distribution",
        "panel_id": "heterogeneous-wrong-majority",
        "reason": "collapse-without-accuracy-gain",
        "var0": 422.22222222222223,
        "var1": 156.6020423715897,
        "verdict": "HERDING"
      },
      "median_only": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": true,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 34.333333333333336,
        "median0": 30.0,
        "median1": 30.0,
        "mode": "median_only",
        "panel_id": "heterogeneous-wrong-majority",
        "reason": "collapse-without-accuracy-gain",
        "var0": 422.22222222222223,
        "var1": 105.55555555555556,
        "verdict": "HERDING"
      },
      "median_plus_arguments": {
        "accuracy_improved": true,
        "collapsed": true,
        "evidence_differentiated": true,
        "herding": false,
        "mae0": 29.555555555555557,
        "mae1": 22.299999999999997,
        "median0": 30.0,
        "median1": 47.7,
        "mode": "median_plus_arguments",
        "panel_id": "heterogeneous-wrong-majority",
        "reason": "collapse-with-accuracy-and-evidence",
        "var0": 422.22222222222223,
        "var1": 0.0,
        "verdict": "REVISION"
      }
    },
    "homogeneous": {
      "arguments": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": false,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 28.666666666666668,
        "median0": 30.0,
        "median1": 41.333333333333336,
        "mode": "arguments",
        "panel_id": "homogeneous-unanchored-guesses",
        "reason": "collapse-with-homogeneous-evidence",
        "var0": 422.22222222222223,
        "var1": 0.0,
        "verdict": "HERDING"
      },
      "full_distribution": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": false,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 33.543209876543216,
        "median0": 30.0,
        "median1": 30.0,
        "mode": "full_distribution",
        "panel_id": "homogeneous-unanchored-guesses",
        "reason": "collapse-with-homogeneous-evidence",
        "var0": 422.22222222222223,
        "var1": 156.6020423715897,
        "verdict": "HERDING"
      },
      "median_only": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": false,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 34.333333333333336,
        "median0": 30.0,
        "median1": 30.0,
        "mode": "median_only",
        "panel_id": "homogeneous-unanchored-guesses",
        "reason": "collapse-with-homogeneous-evidence",
        "var0": 422.22222222222223,
        "var1": 105.55555555555556,
        "verdict": "HERDING"
      },
      "median_plus_arguments": {
        "accuracy_improved": false,
        "collapsed": true,
        "evidence_differentiated": false,
        "herding": true,
        "mae0": 29.555555555555557,
        "mae1": 37.166666666666664,
        "median0": 30.0,
        "median1": 32.833333333333336,
        "mode": "median_plus_arguments",
        "panel_id": "homogeneous-unanchored-guesses",
        "reason": "collapse-with-homogeneous-evidence",
        "var0": 422.22222222222223,
        "var1": 0.0,
        "verdict": "HERDING"
      }
    },
    "n_agents": 9,
    "no_new_private_evidence": true,
    "prescribed_because": "Only arguments is REVISION on the heterogeneous fixture; median_only and full_distribution are HERDING.",
    "prescribed_mode": "arguments",
    "theta": 70
  },
  "id": "CNL-0035",
  "irreducible_verdict_requirements": [
    "Name the three feedback payloads: median_only, full_distribution, arguments.",
    "On a wrong-majority panel with no new private evidence, measure var and MAE after one round under each payload.",
    "Call herding when variance collapses without MAE gain, or when evidence_class is homogeneous.",
    "A planted homogeneous unanchored_guess panel must FIRE; heterogeneous arguments must be SILENT.",
    "A second-moment recount of fixture variance must match the author's population-variance column."
  ],
  "kind": "council-design-note",
  "manifest_registration": {
    "manifest_path": "command-center/p2-wave/probes/CNL-0035/UNIT-ARTIFACT-MANIFEST.json",
    "registered": true
  },
  "metric": {
    "I_star": 1,
    "decision": "FIRE herding and refuse a consensus claim when the gate is true; SILENT when variance collapse is accompanied by accuracy gain and differentiated evidence_class.",
    "formula": "herding := (var1 < 0.5*var0) AND ((unique evidence_class count == 1) OR NOT (mae1 < 0.9*mae0))",
    "id": "herding-gate"
  },
  "min_bytes_threshold": 4096,
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0035/probe1_herding.py",
      "id": "probe1",
      "role": "herding-control"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0035/probe2_negative.py",
      "id": "probe2",
      "role": "negative-control-and-recount"
    }
  ],
  "negative_control": {
    "check": "herding_gate",
    "rejected_state": "homogeneous unanchored_guess panel under arguments feedback: variance collapses with no reliability differential",
    "verbatim": "NEGATIVE_CONTROL rejected_state=homogeneous-unanchored-guesses mode=arguments check=herding_gate FIRE herding=True verdict=HERDING reason=collapse-with-homogeneous-evidence var0=422.222222222222 var1=0.000000000000 mae0=29.555555555556 mae1=28.666666666667 | NEGATIVE_CONTROL known_good=heterogeneous-wrong-majority mode=arguments check=herding_gate SILENT herding=False verdict=REVISION reason=collapse-with-accuracy-and-evidence var0=422.222222222222 var1=0.000000000000 mae0=29.555555555556 mae1=7.818181818182"
  },
  "negative_controls": [
    {
      "check": "herding_gate",
      "does": "FIRE (herding=true) because evidence is homogeneous",
      "id": "homogeneous-arguments-herding",
      "rejected_state": "all seats unanchored_guess; arguments payload; no new evidence",
      "verbatim": "NEGATIVE_CONTROL rejected_state=homogeneous-unanchored-guesses mode=arguments check=herding_gate FIRE herding=True verdict=HERDING reason=collapse-with-homogeneous-evidence var0=422.222222222222 var1=0.000000000000 mae0=29.555555555556 mae1=28.666666666667"
    }
  ],
  "produced_by": {
    "execution_substrate": "linux-local",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "vendor": "xai"
  },
  "protocols": [
    {
      "artifact": {
        "herding_on_het": true,
        "mode": "median_only"
      },
      "executability": "EXECUTABLE",
      "family": "delphi-anonymous-rounds",
      "name": "median-only-feedback",
      "record_id": "P20"
    },
    {
      "artifact": {
        "herding_on_het": true,
        "mode": "full_distribution"
      },
      "executability": "EXECUTABLE",
      "family": "delphi-anonymous-rounds",
      "name": "full-distribution-feedback",
      "record_id": "P21"
    },
    {
      "artifact": {
        "herding_on_het": false,
        "mode": "arguments"
      },
      "executability": "EXECUTABLE",
      "family": "delphi-anonymous-rounds",
      "name": "arguments-without-distinguished-median",
      "record_id": "P22"
    }
  ],
  "question": "What feedback is returned between Delphi rounds (median only, full distribution, arguments), and which choice produces genuine revision rather than regression to the reported median?",
  "report": {
    "control_ids": [
      "homogeneous-arguments-herding"
    ],
    "kind": "council-design-note",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0035/probe1_herding.py:59",
        "measured": true,
        "method": "population-variance-and-mae",
        "name": "het.median_only.herding"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0035/delphi.py:21",
        "measured": false,
        "method": "population-variance-and-mae",
        "name": "het.arguments.herding"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0035/probe2_negative.py:63",
        "measured": true,
        "method": "herding-gate-on-homogeneous-fixture",
        "name": "hom.arguments.herding"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0035/delphi.py:86",
        "measured": true,
        "method": "second-moment-variance",
        "name": "var0_second_moment_identity"
      }
    ]
  },
  "residual_unknowns": [
    {
      "claim": "Live LLM seats follow the bounded-rational update models.",
      "settling_experiment": "Run the same fixtures through the Phase-7A Delphi runtime with live seats and apply the herding gate to observed estimates.",
      "verdict": "NOT-CHECKED"
    }
  ],
  "retry": {
    "count": 1,
    "policy": "two strikes then pivot: first attempt used catalog council-design-note.schema.json $ref which fetches https://ast-integrate.invalid over the network; pivoted to local note_schema.py (same pattern as CNL-0071)"
  },
  "reviewer": {
    "independent": true,
    "method": "Recompute var0 as E[x^2]-(E[x])^2 from fixture private signals and from live round estimates; disagreeing numbers block.",
    "reviewer_id": "CNL-0035-probe2-second-moment-recount",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0035",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:36030",
  "state": "SUCCESS",
  "status": "SUCCESS",
  "taxonomy": {
    "axis": "inter-round-information",
    "classes": [
      {
        "id": "median_only",
        "interest": "Distinguished group median; no reasons; no spread."
      },
      {
        "id": "full_distribution",
        "interest": "Quartiles and histogram with the median still labeled."
      },
      {
        "id": "arguments",
        "interest": "Anonymous evidence-classed estimates; no group median."
      }
    ],
    "closed": true,
    "id": "delphi-feedback-payload"
  },
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0035/probe1_herding.py",
      "id": "probe1-herding",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0035/probe2_negative.py",
      "id": "probe2-negative-recount",
      "result": "PASS"
    }
  ],
  "timestamps": {
    "ended_at": "2026-08-25T00:56:26Z",
    "started_at": "2026-08-25T00:56:26Z"
  },
  "title": "Delphi topology: iterated anonymous estimates with controlled feedback",
  "ts": "2026-08-25T00:56:26Z",
  "unit_id": "CNL-0035",
  "windows_inputs": {
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": false,
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": false
  }
}
