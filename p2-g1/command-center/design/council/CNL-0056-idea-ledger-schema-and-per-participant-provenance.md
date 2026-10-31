{
  "unit_id": "CNL-0056",
  "state": "SUCCESS",
  "status": "DELIVERED",
  "sentinel": "SUCCESS:CNL-0056",
  "completion_sentinel": "SUCCESS:CNL-0056",
  "title": "Idea ledger schema and per-participant provenance",
  "phase": "2C",
  "output_schema": "command-center/schema/councilspec.v2.schema.json",
  "output_schema_on_disk": true,
  "output_schema_note": "Catalog points at command-center/schema/councilspec.v2.schema.json (CNL-0001). On this worktree the file is a generated shim that $ref's platform/schema/artifact-class-profiles.schema.json#/$defs/councilspec.v2; it is not the full CouncilSpec v2 root envelope. This note carries the idea-ledger $defs that CNL-0001 must absorb.",
  "report": {
    "kind": "councilspec.v2",
    "observations": [
      {
        "name": "known-good-silent",
        "measured": true,
        "method": "ledger.check_disappearance set-difference",
        "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json"
      },
      {
        "name": "planted-bad-fires",
        "measured": true,
        "method": "ledger.check_disappearance set-difference",
        "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/planted-bad.json"
      },
      {
        "name": "runtime-drop-IDEA-0003-fires",
        "measured": true,
        "method": "drop_idea_from_synthesis then check_disappearance",
        "anchor": "command-center/p2-wave/probes/CNL-0056/ledger.py:188"
      }
    ],
    "control_ids": [
      "known-good",
      "planted-bad",
      "runtime-drop-IDEA-0003",
      "ghost-id-only"
    ]
  },
  "question": "What does the idea ledger record so that an idea can be traced to its originator, its duplicates, its supporters and its fate in the final synthesis - and what is the check that no idea silently disappears between ledger and synthesis?",
  "answer": "The ledger is an append-only array of idea records. Each record stores a stable idea_id, a canonical_mechanism (the CNL-0051 dedup key; statement text is never identity), an immutable originator (participant_id, seat, round, seq, recorded_at), a duplicate_of pointer plus the inverse duplicates list, a supporters list with stance in {endorse,second,qualify,oppose}, and a fate object (status in {ADOPTED,MERGED,REJECTED,DEFERRED,DISSENTED,UNRESOLVED} plus synthesis_node_ids). A canonical idea (duplicate_of is null) must appear in the synthesis. The disappearance check FIRES when either Signal A (required idea_id set minus cites_idea_ids) or Signal B (required canonical_mechanism set minus covers_mechanisms) is non-empty. Duplicates are traced through duplicate_of and are not themselves required citations. SILENT only when both missing sets are empty.",
  "depends_on": {
    "CNL-0051": "Semantic unique-idea counter defines when two statements are the SAME idea. This unit records the resulting duplicate_of edge; it does not re-implement Jaccard/rewrite recall."
  },
  "inputs_on_this_worktree": {
    "_USER-PROMPTS.md:10746-10767": false,
    "_USER-PROMPTS.md:10915-10946": false,
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "command-center/schema/councilspec.v2.schema.json": true,
    "note": "Harness restore paths from the catalog are not on this Linux tree. Design is operationalised from the catalog question, tests_required, CNL-0051 dependency, and IMP-0291 ledger fields (author/round/canonical-mechanism)."
  },
  "idea_ledger_schema": {
    "id": "idea-ledger/v1",
    "append_only": true,
    "identity": {
      "idea_id": "stable record id; never recycled",
      "canonical_mechanism": "dedup key from CNL-0051; two records with the same mechanism are the same idea even if statement text differs",
      "statement": "surface wording; not identity; not a quota token"
    },
    "originator": {
      "required": [
        "participant_id",
        "seat",
        "round",
        "seq",
        "recorded_at"
      ],
      "immutable": true,
      "rule": "The first writer of a canonical_mechanism is originator. Later restatements become new rows with duplicate_of set; they MUST NOT overwrite originator."
    },
    "duplicates": {
      "duplicate_of": "null on the canonical row; idea_id of canonical on later rows",
      "duplicates": "inverse list on the canonical row",
      "not_required_in_synthesis": true,
      "fate_of_duplicate": "MERGED"
    },
    "supporters": {
      "item": [
        "participant_id",
        "round",
        "seq",
        "stance",
        "recorded_at"
      ],
      "stance_vocab": [
        "endorse",
        "oppose",
        "qualify",
        "second"
      ],
      "rule": "supporters append; they never become originator"
    },
    "fate": {
      "status_vocab": [
        "ADOPTED",
        "DEFERRED",
        "DISSENTED",
        "MERGED",
        "REJECTED",
        "UNRESOLVED"
      ],
      "synthesis_node_ids": "nodes in the synthesis artifact that dispose this idea",
      "rule": "Fate on the ledger is a claim. The disappearance check does not trust it: it re-reads synthesis citations."
    },
    "required_keys": [
      "idea_id",
      "canonical_mechanism",
      "statement",
      "originator",
      "duplicate_of",
      "duplicates",
      "supporters",
      "fate"
    ],
    "$defs": {
      "IdeaRecord": {
        "type": "object",
        "required": [
          "idea_id",
          "canonical_mechanism",
          "statement",
          "originator",
          "duplicate_of",
          "duplicates",
          "supporters",
          "fate"
        ],
        "additionalProperties": false,
        "properties": {
          "idea_id": {
            "type": "string",
            "minLength": 1
          },
          "canonical_mechanism": {
            "type": "string",
            "minLength": 1
          },
          "statement": {
            "type": "string",
            "minLength": 1
          },
          "originator": {
            "type": "object",
            "required": [
              "participant_id",
              "seat",
              "round",
              "seq",
              "recorded_at"
            ],
            "properties": {
              "participant_id": {
                "type": "string"
              },
              "seat": {
                "type": "string"
              },
              "round": {
                "type": "integer",
                "minimum": 1
              },
              "seq": {
                "type": "integer",
                "minimum": 1
              },
              "recorded_at": {
                "type": "string"
              }
            }
          },
          "duplicate_of": {
            "type": [
              "string",
              "null"
            ]
          },
          "duplicates": {
            "type": "array",
            "items": {
              "type": "string"
            }
          },
          "supporters": {
            "type": "array"
          },
          "fate": {
            "type": "object",
            "required": [
              "status",
              "synthesis_node_ids"
            ],
            "properties": {
              "status": {
                "enum": [
                  "ADOPTED",
                  "DEFERRED",
                  "DISSENTED",
                  "MERGED",
                  "REJECTED",
                  "UNRESOLVED"
                ]
              },
              "synthesis_node_ids": {
                "type": "array",
                "items": {
                  "type": "string"
                }
              },
              "rationale": {
                "type": "string"
              }
            }
          }
        }
      }
    }
  },
  "disappearance_check": {
    "name": "check_disappearance",
    "implementation": "command-center/p2-wave/probes/CNL-0056/ledger.py",
    "required_set": "canonical rows only (duplicate_of is null). IDEA-0004 in the fixture is a paraphrase and must not be required.",
    "signal_a": {
      "mechanism": "set difference",
      "left": "canonical idea_id",
      "right": "synthesis node cites_idea_ids",
      "fires_when": "missing idea_ids non-empty",
      "source": "command-center/p2-wave/probes/CNL-0056/ledger.py:56"
    },
    "signal_b": {
      "mechanism": "set difference on a different field",
      "left": "canonical canonical_mechanism",
      "right": "synthesis node covers_mechanisms",
      "fires_when": "missing mechanisms non-empty",
      "source": "command-center/p2-wave/probes/CNL-0056/ledger.py:68"
    },
    "combine": "FIRE if A or B fires; SILENT iff both missing sets are empty",
    "signals_disagree_means": "citation dump on one field only (ghost ID or ghost mechanism). Still FIRE. Independence is proven by dropping only cites_idea_ids.",
    "does_not_trust": [
      "ledger fate.synthesis_node_ids without a matching synthesis node",
      "an empty synthesis section that merely exists",
      "string-equality unique counts"
    ]
  },
  "tests": {
    "disappearing_idea": {
      "method": "drop_idea_from_synthesis(known-good, IDEA-0003)",
      "fired": true,
      "missing_ids": [
        "IDEA-0003"
      ],
      "missing_mechs": [
        "mech.provenance.per-participant-origin"
      ],
      "n_missing_ids": 1,
      "independent_recount": "ok",
      "duplicate_not_required": true
    },
    "both_states": {
      "known_good_silent": true,
      "known_good_n_missing_ids": 0,
      "known_good_n_missing_mechs": 0,
      "planted_bad_fired": true,
      "planted_bad_missing_ids": [
        "IDEA-0003"
      ],
      "planted_bad_missing_mechs": [
        "mech.provenance.per-participant-origin"
      ]
    }
  },
  "negative_control": {
    "reject_state": "a synthesis that omits a canonical ledger idea_id or its canonical_mechanism; the check must FIRE, not stay silent",
    "fixture": "command-center/p2-wave/probes/CNL-0056/fixtures/planted-bad.json",
    "what_the_check_does": "On the planted-bad fixture (synthesis node SYN-03 removed, ledger still holds IDEA-0003 with originator P-dave, supporter P-alice, fate DISSENTED), the check FIRES. signal_a.missing=['IDEA-0003'] signal_b.missing=['mech.provenance.per-participant-origin'] fired=True silent=False.",
    "fires": true,
    "silent": false
  },
  "reviewer": {
    "reviewer_id": "CNL-0056-recount-tabulator",
    "method": "recursive JSON walk collecting idea records / cites_idea_ids / covers_mechanisms (recount.py), not the author's set-difference helpers. A disagreement in n_canonical, n_missing_ids, or n_missing_mechs blocks the unit.",
    "independent": true,
    "verdict": "PASS",
    "known_good_agree": true,
    "planted_bad_agree": true,
    "runtime_drop_agree": true,
    "numbers": {
      "known_good": {
        "n_required": 3,
        "n_missing_ids": 0,
        "n_missing_mechs": 0
      },
      "planted_bad": {
        "n_required": 3,
        "n_missing_ids": 1,
        "n_missing_mechs": 1,
        "missing_ids": [
          "IDEA-0003"
        ]
      }
    }
  },
  "evidence": [
    {
      "claim": "Known-good fixture is SILENT on both signals.",
      "signal_1": {
        "kind": "command+output",
        "command": "python3 -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0056'); import ledger, json as J; d=J.load(open('command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json')); print(ledger.check_disappearance(d)['silent'], ledger.check_disappearance(d)['signal_a']['n_missing'])\"",
        "verbatim": "silent=True n_missing_ids=0"
      },
      "signal_2": {
        "kind": "file:line plus independent walk",
        "anchor": "command-center/p2-wave/probes/CNL-0056/recount.py:32",
        "verbatim": "n_required=3 n_missing_ids=0 n_missing_mechs=0 agree=True"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Removing IDEA-0003 from synthesis makes the check FIRE with missing_ids=[IDEA-0003] and the matching mechanism.",
      "signal_1": {
        "kind": "command+output",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0056/probe1_disappearing_idea.py",
        "verbatim": "fired=True missing_ids=['IDEA-0003'] missing_mechs=['mech.provenance.per-participant-origin']"
      },
      "signal_2": {
        "kind": "different field",
        "anchor": "command-center/p2-wave/probes/CNL-0056/ledger.py:68",
        "verbatim": "signal_b.missing=['mech.provenance.per-participant-origin'] n_missing=1 field=canonical_mechanism vs covers_mechanisms"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Planted-bad fixture FIRES; known-good is SILENT (both-states).",
      "signal_1": {
        "kind": "command+output",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0056/probe2_both_states.py",
        "verbatim": "good.silent=True bad.fired=True bad.missing_ids=['IDEA-0003']"
      },
      "signal_2": {
        "kind": "independent recount numbers",
        "anchor": "command-center/p2-wave/probes/CNL-0056/recount.py",
        "verbatim": "good n_missing_ids=0 bad n_missing_ids=1 bad missing_ids=['IDEA-0003']"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "An originator, duplicate, supporter, and fate can be traced for every fixture idea.",
      "signal_1": {
        "kind": "file:line",
        "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json",
        "verbatim": "IDEA-0001 originator=P-alice duplicates=[IDEA-0004] supporters=[P-bob] fate=ADOPTED/SYN-01; IDEA-0003 originator=P-dave supporters=[P-alice] fate=DISSENTED/SYN-03"
      },
      "signal_2": {
        "kind": "schema keys present",
        "anchor": "idea_ledger_schema required_keys",
        "verbatim": [
          "idea_id",
          "canonical_mechanism",
          "statement",
          "originator",
          "duplicate_of",
          "duplicates",
          "supporters",
          "fate"
        ]
      },
      "verdict": "CONFIRMED"
    }
  ],
  "failure_classes_addressed": {
    "detector-failure": "both-states plus runtime drop of IDEA-0003",
    "uncontrolled-silence": "SILENT only on known-good; FIRE on planted-bad",
    "gameable-metric": "citing idea_ids without covers_mechanisms still FIREs (ghost); duplicates do not inflate the required set",
    "overclaim": "scoped to four-idea fixtures on this worktree; not a 100-idea production run; CouncilSpec v2 root schema is absent"
  },
  "residual_unknowns": [
    "Harness restore files named in catalog inputs are absent here.",
    "CNL-0051 catalog artifact is not on this tree; duplicate_of is assumed emitted by it.",
    "councilspec.v2.schema.json is a generated class shim, not a CouncilSpec v2 root envelope."
  ],
  "does_not_claim": [
    "cloud ok=true is delivery",
    "global unit_manifest.py --write was run",
    "the 100-unique-idea production target was measured",
    "semantic duplicate recall (rename/paraphrase/rewrite) \u2014 that is CNL-0051",
    "CouncilSpec v2 root envelope exists on disk"
  ],
  "named_probes": [
    {
      "id": "probe1",
      "role": "disappearing-idea",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0056/probe1_disappearing_idea.py"
    },
    {
      "id": "probe2",
      "role": "both-states-negative-control",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0056/probe2_both_states.py"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0056-idea-ledger-schema-and-per-participant-provenance.md",
      "role": "primary",
      "exists": true
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0056/ledger.py",
      "role": "supporting",
      "exists": true
    }
  ],
  "cloud_ok": false,
  "registered": true,
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  }
}
