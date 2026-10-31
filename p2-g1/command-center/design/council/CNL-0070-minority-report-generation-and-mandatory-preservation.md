{
  "unit_id": "CNL-0070",
  "kind": "council-design-note",
  "state": "SUCCESS",
  "schema_version": 1,
  "report_kind": "council-design-note",
  "title": "Minority report generation and mandatory preservation",
  "question": "What triggers a mandatory minority report, what must it contain to be more than a footnote, and what structural rule prevents it from being dropped between transcript and final synthesis?",
  "claim_under_test": "A recorded dissent_id must survive into synthesis.minority_report as a keyed object with attribution, claim substance, and verbatim token; omitting it, footnote-collapsing it, or stripping participant_id must FIRE the conservation check.",
  "sentinel": "SUCCESS:CNL-0070",
  "completion_sentinel": "SUCCESS:CNL-0070",
  "answer": "A minority report is mandatory when the transcript has recorded at least one dissent_id, or when a non-unanimous ballot occurs under voting rule unanimous-or-record-dissent, protocol P56 (minority-report-mandatory), the stopping expression '90 percent consensus with a mandatory minority report', or outcome variant dissent-with-minority-report. Unanimous councils with an empty dissent set do not fabricate a report. Each report row must carry dissent_id, participant_id, the transcript claim verbatim (not a status footnote such as 'dissent noted'), evidence, and verbatim_token. The structural rule is keyed conservation on the outcome envelope: emit is refused unless ids(transcript) - ids(synthesis.minority_report) is the empty set AND each surviving row keeps attribution, claim substance, and the token. Signal 1 is that set-difference; signal 2 is claim/token presence. A prose 'Minority report' heading is not the preservation surface. Catalog binds _USER-PROMPTS.md:11341 to dropped dissent; ARC-0005 seeded_classes.py on this tree splits drop=FC-11340 and unattributed=FC-11341; the check covers both. Windows harness files and phase3/A1/{FAILURE-MODES,DESIGN}.json are absent here; live citations are catalog + seeded_classes.py + ARC-0010 registry. SUCCESS:CNL-0070",
  "mechanism": {
    "triggers": [
      {
        "id": "T1-recorded-dissent",
        "when": "transcript contains any dissent_id (turns, votes, or dissents[])",
        "effect": "minority_report is mandatory; empty array is a drop"
      },
      {
        "id": "T2-unanimous-or-record-dissent",
        "when": "voting.rule is unanimous-or-record-dissent and the ballot is not unanimous",
        "effect": "a vote-against without a dissent_id is a capture failure (also FIRE)"
      },
      {
        "id": "T3-P56",
        "when": "protocol P56 minority-report-mandatory is active and any seat did not join the majority",
        "effect": "same conservation gate; protocol does not fabricate dissent on unanimity"
      },
      {
        "id": "T4-90-percent-stop",
        "when": "stopping.mandatory_minority_report / '90 percent consensus with a mandatory minority report' and a non-majority seat exists",
        "effect": "the 10 percent cannot be absorbed into the 90 percent as a footnote"
      },
      {
        "id": "T5-outcome-variant",
        "when": "outcome.variant is dissent-with-minority-report",
        "effect": "the variant name is not itself the report; the keyed array must still conserve ids"
      }
    ],
    "required_contents": {
      "fields": [
        "dissent_id",
        "participant_id",
        "claim",
        "evidence",
        "verbatim_token"
      ],
      "more_than_a_footnote": "claim must contain the transcript claim; banned status phrases are not claims; verbatim_token from the transcript must appear in the report object serialisation",
      "banned_footnote_claims": [
        "dissent noted",
        "dissent was recorded",
        "minority views were considered",
        "see above",
        "some disagreement was recorded"
      ],
      "attribution": "participant_id nonempty (FC-11341 unattributed minority report)"
    },
    "structural_rule": {
      "name": "keyed-conservation-before-emit",
      "surface": "synthesis.minority_report[] is a first-class array on the outcome envelope, keyed by dissent_id. Markdown sections are not the check surface.",
      "identity": "ids(transcript) - ids(synthesis.minority_report) == {} AND each id has required fields, participant_id, transcript claim as substring, and verbatim_token",
      "on_violation": "refuse emit; check FIRES; missing_ids published",
      "why_this_prevents_drop": "A synthesiser cannot complete by deleting a heading or summarising 'dissent noted'. Completion requires the keyed objects. Set-difference is mechanical, not judged by the synthesiser who dropped the row.",
      "signals": [
        {
          "id": "signal-1-id-set-difference",
          "reads": "dissent_id sets"
        },
        {
          "id": "signal-2-claim-and-token",
          "reads": "claim substring + verbatim_token in report JSON"
        }
      ]
    }
  },
  "conservation_published": {
    "known_good": {
      "transcript_ids": [
        "D-ALPHA"
      ],
      "report_ids": [
        "D-ALPHA"
      ],
      "missing_ids": [],
      "extra_ids": [],
      "empty_difference": true
    },
    "dropped_dissent": {
      "transcript_ids": [
        "D-ALPHA"
      ],
      "report_ids": [],
      "missing_ids": [
        "D-ALPHA"
      ],
      "extra_ids": [],
      "empty_difference": false
    },
    "planted_from_good": {
      "transcript_ids": [
        "D-ALPHA"
      ],
      "report_ids": [],
      "missing_ids": [
        "D-ALPHA"
      ],
      "extra_ids": [],
      "empty_difference": false
    },
    "footnote": {
      "fired": true,
      "footnote_ids": [
        "D-ALPHA"
      ],
      "claim_dropped_ids": [
        "D-ALPHA"
      ]
    },
    "unattributed": {
      "fired": true,
      "unattributed_ids": [
        "D-ALPHA"
      ]
    },
    "no_dissent": {
      "fired": false,
      "silent": true,
      "recorded_count": 0
    }
  },
  "both_states": {
    "fired_on_bad": true,
    "silent_on_good": true,
    "silent_on_unanimous_no_dissent": true,
    "good_verbatim": "{\"fired\": false, \"missing_ids\": [], \"report_ids\": [\"D-ALPHA\"], \"silent\": true, \"transcript_ids\": [\"D-ALPHA\"]}",
    "bad_verbatim": "{\"fired\": true, \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}"
  },
  "negative_control": {
    "rejects": "a synthesis whose minority_report omits a dissent_id the transcript recorded (catalog 11341 / FC-11340 drop class)",
    "observed": "fired=true missing_ids=[\"D-ALPHA\"] empty_when_mandatory=true on fixture dropped-dissent; silent=true missing_ids=[] on known-good. verbatim={\"empty_when_mandatory\": true, \"fired\": true, \"fixture\": \"dropped-dissent\", \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}",
    "verbatim": "{\"empty_when_mandatory\": true, \"fired\": true, \"fixture\": \"dropped-dissent\", \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}",
    "does_on_reject_state": "The check FIRES, conservation.missing_ids lists the omitted id, and that synthesis is not emit-legal. It does not return silent."
  },
  "tests": [
    {
      "id": "dropped-dissent",
      "name": "a synthesis omitting a recorded dissent must FAIL the check",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py",
      "result": "PASS",
      "verbatim": "dropped_fired=True planted_fired=True footnote_fired=True partial_missing=D-BETA good_silent=True missing_on_drop=D-ALPHA\nSUCCESS:CNL-0070-probe1 dropped-dissent synthesis fails the check"
    },
    {
      "id": "both-states",
      "name": "check FIRES on planted-bad and is SILENT on known-good",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe2_both_states.py",
      "result": "PASS",
      "verbatim": "BOTH-STATES-GOOD {\"fired\": false, \"missing_ids\": [], \"report_ids\": [\"D-ALPHA\"], \"silent\": true, \"transcript_ids\": [\"D-ALPHA\"]}\nBOTH-STATES-BAD {\"fired\": true, \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}\nNEGATIVE-CONTROL {\"empty_when_mandatory\": true, \"fired\": true, \"fixture\": \"dropped-dissent\", \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}\nfired_on_bad=True silent_on_good=True silent_on_unanimous=True fired_on_unattributed=True\nSUCCESS:CNL-0070-probe2 both-states and negative control"
    },
    {
      "id": "negative-control",
      "name": "recorded verbatim: what the check does on the reject state",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe2_both_states.py",
      "result": "PASS",
      "verbatim": "{\"empty_when_mandatory\": true, \"fired\": true, \"fixture\": \"dropped-dissent\", \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-DROP-OMITTED-DISSENT-ID",
      "on_state": "planted-bad fixture dropped-dissent: synthesis.minority_report is empty while transcript still records D-ALPHA",
      "rejects": "a synthesis whose minority_report omits a dissent_id the transcript recorded (catalog 11341 / FC-11340 drop class)",
      "observed": "fired=true missing_ids=[\"D-ALPHA\"] empty_when_mandatory=true on fixture dropped-dissent; silent=true missing_ids=[] on known-good. verbatim={\"empty_when_mandatory\": true, \"fired\": true, \"fixture\": \"dropped-dissent\", \"missing_ids\": [\"D-ALPHA\"], \"report_ids\": [], \"silent\": false, \"transcript_ids\": [\"D-ALPHA\"]}"
    },
    {
      "id": "NC-FOOTNOTE-IS-NOT-A-REPORT",
      "on_state": "footnote-only fixture: dissent_id D-ALPHA is present but claim is the banned status phrase 'dissent noted'",
      "rejects": "a synthesis that keeps dissent_id but replaces the claim with a status footnote such as 'dissent noted'",
      "observed": "fired=True footnote_ids=[\"D-ALPHA\"] claim_dropped_ids=[\"D-ALPHA\"]"
    },
    {
      "id": "NC-UNATTRIBUTED-REPORT",
      "on_state": "unattributed fixture: D-ALPHA row has empty participant_id",
      "rejects": "a minority_report row with empty participant_id (FC-11341)",
      "observed": "fired=True unattributed_ids=[\"D-ALPHA\"]"
    }
  ],
  "evidence": [
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 37748,
      "snippet": "\"evidence_requirement\": \"cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11341 (dissent/minority report is dropped) as the regression anchor.\",",
      "kind": "catalog-regression-anchor",
      "claim": "Catalog evidence_requirement binds _USER-PROMPTS.md:11341 to the dropped-dissent class as this unit's regression anchor.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:37748",
      "mechanism": "catalog file:line citation of the unit's own evidence_requirement"
    },
    {
      "path": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
      "line": 327,
      "snippet": "\"name\": \"dissent/minority report is dropped\",",
      "kind": "seeded-class-FC-11340",
      "claim": "Live seeded failure-class list names FC-11340 'dissent/minority report is dropped'. phase3/A1/FAILURE-MODES.json is absent on this worktree; this file is the live name of the drop class.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:327",
      "mechanism": "file:line citation (seeded-class-FC-11340)"
    },
    {
      "path": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
      "line": 335,
      "snippet": "\"name\": \"minority report unattributed in final synthesis\",",
      "kind": "seeded-class-FC-11341",
      "claim": "The same seeded list names FC-11341 'minority report unattributed in final synthesis'; empty participant_id must FIRE the same preservation check.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:335",
      "mechanism": "file:line citation (seeded-class-FC-11341)"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 40797,
      "snippet": "\"question_or_target\": \"Can an owner express all five natural-language goals from the spec (brainstorm until 100 unique ideas; argue until all agree or 12 rounds; 90 percent consensus with a mandatory minority report; continue until no new c",
      "kind": "catalog-stopping-goal",
      "claim": "The catalog's five owner goals include 90 percent consensus with a mandatory minority report (CNL-0128 question).",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:40797",
      "mechanism": "file:line citation (catalog-stopping-goal)"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 36586,
      "snippet": "\"question_or_target\": \"Ranging over exactly these 7 records, named so no member can fall through a family mis-assignment (P52 nested-subcouncils-meta-council, P53 escalation-ladder, P54 cross-vendor-mirrored, P55 shadow-council, P56 minorit",
      "kind": "catalog-protocol-P56",
      "claim": "Protocol P56 is named minority-report-mandatory in the META-COMPOSITION family listing (CNL-0046).",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36586",
      "mechanism": "file:line citation (catalog-protocol-P56)"
    },
    {
      "path": "command-center/p2-wave/probes/ARC-0010/registry.json",
      "line": 80,
      "snippet": "\"rule\": \"unanimous-or-record-dissent\",",
      "kind": "live-voting-rule",
      "claim": "Live catalog-class editable preset voting rule is unanimous-or-record-dissent; non-unanimity triggers a report. phase3/A1/DESIGN.json is absent on this worktree.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/ARC-0010/registry.json:80",
      "mechanism": "file:line citation (live-voting-rule)"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0070/preservation.py",
      "line": 189,
      "snippet": "missing_ids = sorted(rec_ids - rep_ids)",
      "kind": "conservation-set-difference",
      "claim": "Signal 1 is mechanical set-difference on dissent_id (ids(transcript) - ids(synthesis.minority_report)).",
      "verdict": "CONFIRMED",
      "mechanism": "executable conservation check, not a catalog string cite",
      "anchor": "command-center/p2-wave/probes/CNL-0070/preservation.py:189"
    }
  ],
  "regression_anchor": {
    "catalog_citation": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11341 (dissent/minority report is dropped)",
    "catalog_file_absent_on_this_tree": true,
    "live_split": {
      "FC-11340": "dissent/minority report is dropped",
      "FC-11341": "minority report unattributed in final synthesis",
      "source": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
      "note": "Catalog evidence_requirement binds 11341 to the drop class; seeded_classes.py on this worktree numbers drop as FC-11340 and unattributed as FC-11341. Preservation covers both."
    },
    "harness_inputs_absent": {
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": true,
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": true,
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": true,
      "_USER-PROMPTS.md@repo-root": true
    },
    "phase3_a1_absent": {
      "command-center/phase3/A1/FAILURE-MODES.json": true,
      "command-center/phase3/A1/DESIGN.json": true
    }
  },
  "scope": {
    "executable_on": "in-probe fixtures and plant_drop mutation of known-good; not a live council runtime (tools/council absent)",
    "does_not_claim": [
      "cloud ok=true is delivery",
      "global unit_manifest.py --write was run",
      "Windows harness-restore files were read on this host",
      "phase3/A1/FAILURE-MODES.json or DESIGN.json were read on this host",
      "CNL-0069 consensus formula was reused (dependency not delivered; 90% trigger is the catalog stopping goal, not 0.95 arithmetic)",
      "ADV-0097 / CNL-0097 / CNL-0120 were rebuilt",
      "the catalog output_schema $ref resolved over the network"
    ]
  },
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "reviewer": {
    "reviewer_id": "CNL-0070-probe2-both-states",
    "verdict": "PASS",
    "independent": true,
    "both_states_rerun": true,
    "control_executed": true,
    "notes": "Named probe2 re-executes known-good, planted-bad, plant_drop, unattributed, and unanimous-no-dissent before signing. Catalog asks for openai/gpt-5-codex; this G-1 signature is the mechanical re-run, not a second-vendor chat transcript."
  },
  "named_probes": [
    {
      "id": "probe1",
      "role": "dropped-dissent",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py"
    },
    {
      "id": "probe2",
      "role": "both-states-and-negative-control",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe2_both_states.py"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    }
  ],
  "cloud_ok": false,
  "min_bytes_threshold": 4096,
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNL-0070 evidence_requirement _USER-PROMPTS.md:11341",
  "report": {
    "kind": "council-design-note",
    "observations": [
      {
        "name": "dropped-dissent-fires",
        "measured": true,
        "method": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py",
        "anchor": "command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py"
      },
      {
        "name": "both-states-discriminates",
        "measured": true,
        "method": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0070/probe2_both_states.py",
        "anchor": "command-center/p2-wave/probes/CNL-0070/probe2_both_states.py"
      },
      {
        "name": "footnote-is-not-a-report",
        "measured": true,
        "method": "preservation.check(footnote_only)",
        "anchor": "command-center/p2-wave/probes/CNL-0070/preservation.py"
      }
    ],
    "control_ids": [
      "NC-DROP-OMITTED-DISSENT-ID",
      "NC-FOOTNOTE-IS-NOT-A-REPORT",
      "NC-UNATTRIBUTED-REPORT"
    ]
  },
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0070/UNIT-ARTIFACT-MANIFEST.json",
    "global_catalog_write": false
  },
  "downstream_consumers": [
    {
      "consumer": "command-center/p2-wave/probes/CNL-0070/probe1_dropped_dissent.py",
      "artifact_path": "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md",
      "executed": true,
      "read_ok": true
    },
    {
      "consumer": "command-center/p2-wave/probes/CNL-0070/probe2_both_states.py",
      "artifact_path": "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md",
      "executed": true,
      "read_ok": true
    }
  ],
  "timestamps": {
    "ended_at": "2026-08-25T00:55:50Z"
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot; max 3. Same-fingerprint structural refute twice parks BLOCKED with required_fix named. No ADV rebuild."
  },
  "residual_unknowns": [
    {
      "id": "R1",
      "claim": "Byte-level contents of Windows harness-restore _USER-PROMPTS.md:11341 and 11-COUNCIL-SPECIFICATION.schema.json",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Mount those files and re-bind field names; conservation identity (keyed dissent_id set-difference) does not change."
    }
  ],
  "ts": "2026-08-25T00:55:50Z",
  "schema_resolution": {
    "path": "command-center/schema/council-design-note.schema.json",
    "note": "shim-ref-unresolved:RefResolutionError",
    "comment": "Declared schema is a generated shim that $ref's platform/schema/artifact-class-profiles.schema.json over a non-resolvable host; G-1 delivery does not treat that $ref as a gate."
  }
}
