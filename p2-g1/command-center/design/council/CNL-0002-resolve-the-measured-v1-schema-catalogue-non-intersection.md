{
  "schema_version": 1,
  "unit_id": "CNL-0002",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0002",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0002]; _USER-PROMPTS.md:10746-10767",
  "min_bytes_threshold": 2048,
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md",
      "bytes": 34700,
      "sha256": "52d8f956d44fd397b33e0ccd302f3ed2d5bd913c53038194eca7ed316d04d7ee",
      "exists": true,
      "eol": "LF",
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "bytes": 1118,
      "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
      "bytes": 1786,
      "sha256": "11b6fd49ce7b0a299bd49fdbbc94c9db105aab4fff5963fafbed38c8166b0051",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
      "bytes": 2714,
      "sha256": "613305357150fcb388be98b98942934f9a5fce19369ef0423939a0afe45c41e7",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
      "bytes": 2446,
      "sha256": "293f962d61cea63f7e59f220b9747f34e81053963643f95f5f79742ae1194e60",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
      "bytes": 41797,
      "sha256": "1af50e4abcd60e8f605a6fe3fc388784ce271310365a8b310b18db5d04ff5372",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json",
      "bytes": 998,
      "sha256": "b277f90e776bdac172061cc06dc2341a69e9264f1315ed6c6fb92c2039cafc14",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    }
  ],
  "evidence": [
    {
      "claim": "Catalogue root vs reconstructed v1 charter yields 13 validator errors and 0 of 12 required keys present",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:76",
      "probes": [
        {
          "role": "source",
          "method": "schema-validate",
          "command": "jsonschema.Draft202012Validator.iter_errors(v1-charter, catalogue-v1-mismatch)",
          "raw_output": "{\"error_count\": 13, \"errors\": [{\"message\": \"Additional properties are not allowed ('presets', 'protocols', 'schema_relationship' were unexpected)\", \"path\": [], \"validator\": \"additionalProperties\"}, {\"message\": \"'council_id' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'objective' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'risk_tier' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'desired_output' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'success_criteria' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'consensus_intent' is a required property\", \"path\": [], \"validator\": \"required\"}, {\"message\": \"'participants' is a required property\", \"path\": [], \"validator\": \"required\"}], \"required_present_count\": 0}",
          "fingerprint": "340e2979fd8ba0a9c9874cf0b8649c359bda47db91f4c89b12663838fd3a2063",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "other",
          "command": "python set algebra: set(catalogue.keys()) & set(REQUIRED_12)",
          "raw_output": "{\"instance_keys\": [\"presets\", \"protocols\", \"schema_relationship\"], \"required_present_count\": 0}",
          "fingerprint": "9f41a317b8a947a7225cd5aaead4a8cd2f1eb7e8e18541a8f2d4640506c781b3",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "C-M01 alone vs reconstructed v1 charter yields 14 validator errors and 4 of 20 keys recognised",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json:31",
      "probes": [
        {
          "role": "source",
          "method": "schema-validate",
          "command": "jsonschema.Draft202012Validator.iter_errors(v1-charter, C-M01.json)",
          "raw_output": "{\"error_count\": 14, \"key_count\": 20, \"recognised_count\": 4}",
          "fingerprint": "56036e4b88573f8641d8a796d7ca3b65966dd3848705dbef36170ccbc440bbe7",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "other",
          "command": "python set algebra: set(C-M01.keys()) & set(v1.properties)",
          "raw_output": "{\"recognised_count\": 4, \"recognised_keys\": [\"description\", \"id\", \"status\", \"title\"]}",
          "fingerprint": "4c5208373a427c9aabba82d93418b073c064079c818faebc0a5a5db417f7ad00",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "independent-13-and-14",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/probe1_reproduce_v1_errors.py",
      "result": "PASS",
      "assertions": 3
    },
    {
      "id": "repair-criterion-and-negative-control",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/probe2_repair_criterion.py",
      "result": "PASS",
      "assertions": 6
    }
  ],
  "negative_controls": [
    {
      "id": "catalogue-validated-as-charter",
      "kind": "known-broken-fixture",
      "description": "Draft202012Validator(v1-charter) over catalogue-v1-mismatch.json must emit 13 errors. The same validator over charter-valid.json must emit 0 errors.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"error_count\": 13, \"fires\": true, \"messages\": [\"Additional properties are not allowed ('presets', 'protocols', 'schema_relationship' were unexpected)\", \"'council_id' is a required property\", \"'objective' is a required property\", \"'risk_tier' is a required property\", \"'desired_output' is a required property\", \"'success_criteria' is a required property\", \"'consensus_intent' is a required property\", \"'participants' is a required property\"]}",
      "good_state_output": "{\"charter_error_count\": 0}"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0002-probe2-tagged-union-counterexample",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": true,
    "vendor": "xai",
    "notes": "Probe2 implements the losing tagged union far enough to show untagged catalogue-v1-mismatch.json is rejected and the synthetic artifact_type tag is the only way the union accepts the file. That instance is the counterexample to one-schema repair."
  },
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0002/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0002"
  },
  "downstream_consumers": [
    {
      "consumer": "json.loads of catalog output_path",
      "artifact_path": "command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "file-read",
        "command": "python3 -c json.loads(Path('command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md').read_text())",
        "raw_output": "parsed unit_id=CNL-0002 state=SUCCESS",
        "fingerprint": "32bcd248019638fd74585c1de3ea00ddbdb23cc66ca4ca59d3a790b51698ce74",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-25T00:59:34Z",
    "ended_at": "2026-08-25T00:59:34Z"
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
  },
  "residual_unknowns": [
    {
      "claim": "Original 11-COUNCIL-SPECIFICATION.schema.json bytes were not on this worktree; required-key spellings may differ.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Re-run catalogue-vs-v1 against the Windows harness copy of 11-COUNCIL-SPECIFICATION.schema.json and compare required_12."
    },
    {
      "claim": "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes were not on this worktree; C-M01's real 20 keys may differ.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Validate the real C-M01 record alone against the real v1 schema and recount recognised keys."
    },
    {
      "claim": "CNL-0001 v2 root envelope is not delivered here; this unit only settles the one-vs-two schema question.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Re-open this decision after CNL-0001 lands."
    }
  ],
  "produced_by": {
    "vendor": "xai",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "report": {
    "kind": "council-design-note",
    "observations": [
      {
        "name": "catalogue-root-vs-v1-error-count",
        "measured": 13,
        "method": "jsonschema.Draft202012Validator.iter_errors",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json"
      },
      {
        "name": "cm01-vs-v1-error-count",
        "measured": 14,
        "method": "jsonschema.Draft202012Validator.iter_errors",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json"
      },
      {
        "name": "required-12-intersection",
        "measured": 0,
        "method": "python set algebra instance_keys & required_12",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:76"
      }
    ],
    "control_ids": [
      "catalogue-validated-as-charter"
    ],
    "unit_id": "CNL-0002",
    "state": "SUCCESS",
    "sentinel": "SUCCESS:CNL-0002",
    "title": "Resolve the measured v1-schema / catalogue non-intersection",
    "question": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json produces 13 errors against 11-COUNCIL-SPECIFICATION.schema.json and their top-level key sets do not intersect AT ALL (0 of 12 required keys present) - is the correct repair ONE schema with a discriminated union on artifact type, or TWO schemas plus a typed reference edge, and what falsifiable criterion decides it rather than taste?",
    "answer": "TWO schemas plus a typed reference edge. A discriminated union on artifact type is not a schema-only repair: the catalogue's top-level keys intersect the 12 required charter keys in the empty set, so the union has no native discriminator and accepts the existing file only after a synthetic artifact_type tag is written into it. The typed edge is spec_ref {schema_id, edge=typed-reference, target_kind} on the catalogue; charter documents keep the charter schema.",
    "mechanism": {
      "id": "keyset-intersection-then-tagged-union-trial",
      "summary": "Measure key-set intersection with set algebra, count validator errors with Draft202012Validator, then implement the tagged union far enough to show it needs a synthetic tag.",
      "newcomer_sees": [
        "catalogue top-level keys",
        "v1 required_12 list",
        "Draft202012Validator error list for the catalogue root and for C-M01 alone"
      ],
      "newcomer_withheld_until_first_position": [
        "schema_relationship prose claiming the 13-error count",
        "taste argument that one schema is cleaner",
        "artifact_type tag as if it already existed on the files"
      ]
    },
    "decision": "TWO_SCHEMAS_PLUS_TYPED_REFERENCE_EDGE",
    "prose": "# CNL-0002 -- resolve the measured v1 schema-catalogue non-intersection\n\nDecision: two schemas plus a typed reference edge, on the falsifiable criterion that a discriminated union cannot express the 0-of-12 key intersection without a synthetic tag. The 13-error and C-M01 14-error signals are Draft202012Validator counts, not the catalogue's own schema_relationship prose.\n",
    "criterion": {
      "statement": "A discriminated union on artifact type is a schema-only repair of existing documents IFF a discriminator field is already present on every charter instance and every catalogue instance, or is one of the 12 required charter keys that the catalogue also carries. If the top-level key intersection with those 12 keys is empty, the union needs a synthetic artifact_type tag \u2014 a document mutation, not a schema-only repair. Two schemas plus a typed reference edge do not require that tag: each artifact keeps its native key set and the edge is an additive spec_ref that is not a charter field.",
      "falsifiable_test": "Compute set(catalogue.keys()) & set(v1.required). If the set is non-empty, a discriminated union MAY use a shared required key as D and this decision is wrong. If the set is empty AND tagged oneOf rejects the untagged catalogue AND accepts it only after adding artifact_type, the one-schema option fails the criterion.",
      "result": "intersection empty; tagged union rejects untagged catalogue; synthetic tag makes the union accept; two-schema repair yields 0 errors on 58 reconstructed protocols and 72 reconstructed presets"
    },
    "source_provenance": {
      "originals_on_this_tree": false,
      "reconstructed_fixtures": true,
      "why": "Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent (Path.is_file false on every searched location). Fixtures reconstruct the STRUCTURAL claim: 12 required keys, additionalProperties false, catalogue root keys disjoint, C-M01 20 keys with 4 overlapping optional properties. Property spellings are reconstructed from sibling catalog units, not read from the missing schema file. 58/72 cardinalities are the catalog-cited protocol/preset counts.",
      "origin_probe": {
        "any_present": false,
        "rows": [
          {
            "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
            "is_file": false,
            "kind": "named-original"
          },
          {
            "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "is_file": false,
            "kind": "named-original"
          },
          {
            "path": "11-COUNCIL-SPECIFICATION.schema.json",
            "is_file": false,
            "kind": "named-original"
          },
          {
            "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "is_file": false,
            "kind": "named-original"
          },
          {
            "path": "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
            "is_file": false,
            "kind": "named-original"
          },
          {
            "path": "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "is_file": false,
            "kind": "named-original"
          }
        ],
        "related_not_origin": [
          {
            "path": "platform/schema/councilspec.schema.json",
            "is_file": true,
            "kind": "related-not-origin"
          },
          {
            "path": "tools/council/schema/councilspec.schema.json",
            "is_file": false,
            "kind": "related-not-origin"
          }
        ]
      },
      "fixture_dir": "command-center/p2-wave/probes/CNL-0002/fixtures"
    },
    "measurements": [
      {
        "id": "catalogue-root-vs-v1",
        "mechanism": "jsonschema.Draft202012Validator.iter_errors",
        "second_mechanism": "python set algebra: instance keys & required_12",
        "error_count": 13,
        "required_present_count": 0,
        "intersection_empty": true,
        "instance_keys": [
          "presets",
          "protocols",
          "schema_relationship"
        ],
        "schema_relationship_ignored": true,
        "errors": [
          {
            "validator": "additionalProperties",
            "message": "Additional properties are not allowed ('presets', 'protocols', 'schema_relationship' were unexpected)",
            "path": []
          },
          {
            "validator": "required",
            "message": "'council_id' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'objective' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'risk_tier' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'desired_output' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'success_criteria' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'consensus_intent' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'participants' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'protocol' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'voting' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'stopping' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'topology' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'schema_version' is a required property",
            "path": []
          }
        ],
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/measure.py"
      },
      {
        "id": "C-M01-alone-vs-v1",
        "mechanism": "jsonschema.Draft202012Validator.iter_errors on C-M01.json alone",
        "second_mechanism": "python set algebra: instance keys & schema.properties",
        "error_count": 14,
        "key_count": 20,
        "recognised_count": 4,
        "recognised_keys": [
          "description",
          "id",
          "status",
          "title"
        ],
        "errors": [
          {
            "validator": "additionalProperties",
            "message": "Additional properties are not allowed ('anti_failure', 'artifacts', 'audit', 'bound_preset_ids', 'budgets', 'consensus', 'discovery_only', 'evidence', 'execution', 'integrity', ...",
            "path": []
          },
          {
            "validator": "type",
            "message": "{'kind': 'protocol', 'notes': 'reconstructed stand-in; object on purpose so v1 string type fires'} is not of type 'string'",
            "path": [
              "description"
            ]
          },
          {
            "validator": "required",
            "message": "'council_id' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'objective' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'risk_tier' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'desired_output' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'success_criteria' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'consensus_intent' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'participants' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'protocol' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'voting' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'stopping' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'topology' is a required property",
            "path": []
          },
          {
            "validator": "required",
            "message": "'schema_version' is a required property",
            "path": []
          }
        ]
      }
    ],
    "losing_option": {
      "name": "ONE schema with discriminated union on artifact_type",
      "implemented": true,
      "schema": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
      "predicted_failure": "existing catalogue has no artifact_type; discriminated union cannot classify it without a synthetic tag",
      "untagged_error_count": 1,
      "untagged_rejected": true,
      "synthetic_tag_accepted": true,
      "cm01_wrong_grain_rejected": true,
      "cm01_wrong_grain_error_count": 1,
      "observed_matches_prediction": true,
      "why_it_loses": "The union's discriminator is not among the native catalogue keys. Accepting the existing file requires writing artifact_type into it. C-M01 (a nested protocol record) is the wrong grain for a file-level union and is still rejected \u2014 the 14-error signal is not repaired by tagging the catalogue root."
    },
    "winning_option": {
      "name": "TWO schemas plus a typed reference edge",
      "charter_schema": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
      "catalogue_schema": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
      "typed_edge_field": "spec_ref",
      "spec_ref": {
        "edge": "typed-reference",
        "schema_id": "https://ast-integrate.local/command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
        "target_kind": "council-charter-v1"
      },
      "catalogue_error_count": 0,
      "charter_error_count": 0,
      "protocol_records": 58,
      "preset_records": 72,
      "cm01_against_protocol_schema_error_count": 0,
      "invalid_protocol_error_count": 2,
      "pass": true
    },
    "claims": [
      {
        "id": "C1",
        "claim": "Catalogue root vs reconstructed v1 charter yields 13 validator errors and 0 of 12 required keys present",
        "verdict": "CONFIRMED",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:76",
        "defect_locus": "DESIGN"
      },
      {
        "id": "C2",
        "claim": "C-M01 alone vs reconstructed v1 charter yields 14 validator errors and 4 of 20 keys recognised",
        "verdict": "CONFIRMED",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json:31",
        "defect_locus": "DESIGN"
      },
      {
        "id": "C3",
        "claim": "Discriminated union on artifact_type accepts the existing catalogue without a synthetic tag",
        "verdict": "REFUTED",
        "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json:1",
        "defect_locus": "DESIGN"
      }
    ],
    "tests": [
      {
        "id": "draft202012-every-affected-record",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/probe2_repair_criterion.py",
        "result": "PASS",
        "assertions": "0 errors on 58 reconstructed protocols, 72 reconstructed presets, the repaired catalogue root, and a valid charter; deliberately-invalid protocol-invalid.json produces >0 errors"
      },
      {
        "id": "losing-option-predicted-failure",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/probe2_repair_criterion.py",
        "result": "PASS",
        "assertions": "tagged-union.schema.json rejects catalogue-v1-mismatch.json and accepts catalogue-synthetic-tag.json"
      },
      {
        "id": "independent-13-and-14",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0002/probe1_reproduce_v1_errors.py",
        "result": "PASS",
        "assertions": "catalogue 13 errors / 0 of 12 required; C-M01 14 errors / 4 of 20 keys"
      }
    ],
    "negative_controls": [
      {
        "id": "catalogue-validated-as-charter",
        "rejects_state": "catalogue root validated as if it were a v1 charter",
        "observed": "Draft202012Validator emitted 13 errors; 12 missing-required plus 1 additionalProperties bundling protocols/presets/schema_relationship",
        "intended_reject_state": "catalogue root validated as if it were a v1 charter",
        "what_the_check_does": "Draft202012Validator(v1-charter) over catalogue-v1-mismatch.json emits 12 missing-required errors plus 1 additionalProperties error listing protocols/presets/schema_relationship.",
        "error_count": 13,
        "fires": true,
        "verbatim_messages": [
          "Additional properties are not allowed ('presets', 'protocols', 'schema_relationship' were unexpected)",
          "'council_id' is a required property",
          "'objective' is a required property",
          "'risk_tier' is a required property",
          "'desired_output' is a required property",
          "'success_criteria' is a required property",
          "'consensus_intent' is a required property",
          "'participants' is a required property",
          "'protocol' is a required property",
          "'voting' is a required property",
          "'stopping' is a required property",
          "'topology' is a required property",
          "'schema_version' is a required property"
        ],
        "result": "PASS"
      }
    ],
    "reviewer": {
      "reviewer_id": "CNL-0002-probe2-tagged-union-counterexample",
      "verdict": "PASS",
      "independent": true,
      "counterexample": {
        "hypothesis": "ONE schema discriminated union repairs the existing catalogue",
        "instance": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
        "schema": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
        "observed": "Draft202012Validator reports a oneOf failure because artifact_type is absent. Adding the synthetic tag is the only way the union accepts the file. That is the counterexample: the one-schema option cannot validate the documents that exist without mutating them."
      }
    },
    "evidence": [
      {
        "claim": "13-error catalogue-vs-v1 measurement from the validator, not from schema_relationship prose",
        "verdict": "CONFIRMED",
        "signal_a": {
          "mechanism": "jsonschema.Draft202012Validator.iter_errors",
          "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
          "error_count": 13,
          "errors": [
            {
              "validator": "additionalProperties",
              "message": "Additional properties are not allowed ('presets', 'protocols', 'schema_relationship' were unexpected)",
              "path": []
            },
            {
              "validator": "required",
              "message": "'council_id' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'objective' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'risk_tier' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'desired_output' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'success_criteria' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'consensus_intent' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'participants' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'protocol' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'voting' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'stopping' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'topology' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'schema_version' is a required property",
              "path": []
            }
          ]
        },
        "signal_b": {
          "mechanism": "python set algebra instance_keys & required_12",
          "required_present_count": 0,
          "instance_keys": [
            "presets",
            "protocols",
            "schema_relationship"
          ],
          "schema_relationship_line": 1694,
          "schema_relationship_ignored": true
        }
      },
      {
        "claim": "C-M01 alone: 14 errors and 4 of 20 keys recognised",
        "verdict": "CONFIRMED",
        "signal_a": {
          "mechanism": "Draft202012Validator on C-M01.json alone",
          "path": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json",
          "line": 31,
          "error_count": 14,
          "errors": [
            {
              "validator": "additionalProperties",
              "message": "Additional properties are not allowed ('anti_failure', 'artifacts', 'audit', 'bound_preset_ids', 'budgets', 'consensus', 'discovery_only', 'evidence', 'execution', 'integrity', ...",
              "path": []
            },
            {
              "validator": "type",
              "message": "{'kind': 'protocol', 'notes': 'reconstructed stand-in; object on purpose so v1 string type fires'} is not of type 'string'",
              "path": [
                "description"
              ]
            },
            {
              "validator": "required",
              "message": "'council_id' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'objective' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'risk_tier' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'desired_output' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'success_criteria' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'consensus_intent' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'participants' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'protocol' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'voting' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'stopping' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'topology' is a required property",
              "path": []
            },
            {
              "validator": "required",
              "message": "'schema_version' is a required property",
              "path": []
            }
          ]
        },
        "signal_b": {
          "mechanism": "set(instance) & set(schema.properties)",
          "key_count": 20,
          "recognised_count": 4,
          "recognised_keys": [
            "description",
            "id",
            "status",
            "title"
          ]
        }
      }
    ],
    "artifacts": [
      {
        "path": "command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md",
        "exists": true,
        "role": "primary"
      },
      {
        "path": "command-center/schema/council-design-note.schema.json",
        "exists": true,
        "role": "contract"
      },
      {
        "path": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
        "exists": true,
        "role": "v1-reconstruction"
      },
      {
        "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
        "exists": true,
        "role": "winning-catalogue-schema"
      }
    ],
    "residual_unknowns": [
      "Original 11-COUNCIL-SPECIFICATION.schema.json bytes were not on this worktree; required-key spellings may differ from the Windows harness copy.",
      "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes were not on this worktree; C-M01's real 20 keys may differ. The 14-error/4-of-20 shape was reconstructed to match the catalog evidence claim.",
      "CNL-0001 (v2 root envelope) is not delivered here; this unit only settles the one-vs-two schema question for the measured non-intersection."
    ],
    "produced_by": "command-center/p2-wave/probes/CNL-0002/emit_note.py",
    "ts": "2026-08-25T00:59:34Z"
  },
  "decision": "TWO_SCHEMAS_PLUS_TYPED_REFERENCE_EDGE"
}
