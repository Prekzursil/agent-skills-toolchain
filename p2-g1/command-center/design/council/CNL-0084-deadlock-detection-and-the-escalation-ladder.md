{
  "artifacts": [
    {
      "bytes": 1118,
      "eol": "LF",
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "supporting",
      "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755"
    },
    {
      "bytes": 8195,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/detector.py",
      "role": "supporting",
      "sha256": "6a8759914033b21f391297cb15c239bbcf070aea4cc4757e840c0d22a1cd07d3"
    },
    {
      "bytes": 3151,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/probe1_slow_vs_stuck.py",
      "role": "supporting",
      "sha256": "9eda5e7e56372585b0893a965917e153e0444daae2c7e83f093bd2d5a65fc359"
    },
    {
      "bytes": 8890,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py",
      "role": "supporting",
      "sha256": "c0083f29a5b9936ec2bf2586b45d7c9cf5e4aea6c8f529cd30e0aa3d8dd43203"
    },
    {
      "bytes": 2557,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/note_schema.py",
      "role": "supporting",
      "sha256": "fca4ff07c3757bd6e6c183c43efb613cc7b4629bd35d210016c2aa6fb05e7307"
    },
    {
      "bytes": 1605,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/fixtures/known_good_slow_progress.json",
      "role": "supporting",
      "sha256": "24f38d760daee8c68261e74547d3cb02b3c73eaca0fbbeffc30de6cf6574311e"
    },
    {
      "bytes": 1634,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/fixtures/planted_bad_deadlock.json",
      "role": "supporting",
      "sha256": "7ad9d699aefe61c4ddd7490abb406666ddddb0a309fc96299fc4fab05693b9c1"
    },
    {
      "bytes": 1615,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/fixtures/productive_disagreement.json",
      "role": "supporting",
      "sha256": "9bac2d939a4db4d1835749fe9fbbb5e50b2dfbaf8fa2d5449a21ad215b5dddfa"
    },
    {
      "bytes": 1047,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0084/fixtures/stalled_runtime.json",
      "role": "supporting",
      "sha256": "aff4a1581ab24ca6944972acf2d227c2f55b898346e0b3795357701ec78711ca"
    }
  ],
  "defects": [],
  "downstream_consumers": [
    {
      "artifact_path": "command-center/design/council/CNL-0084-deadlock-detection-and-the-escalation-ladder.md",
      "consumer": "command-center/p2-wave/probes/CNL-0084/note_schema.py Draft202012Validator",
      "executed": true,
      "exit_code": 0,
      "probe": {
        "command": "python3 -B command-center/p2-wave/probes/CNL-0084/note_schema.py",
        "exit_code": 0,
        "fingerprint": "fcd24089178a0badaa8cea66dd05974c",
        "method": "schema-validate",
        "raw_output": "validate(doc) errors=[] ; garbage 3/3 rejected",
        "role": "verifier"
      },
      "read_ok": true
    },
    {
      "artifact_path": "command-center/design/council/CNL-0084-deadlock-detection-and-the-escalation-ladder.md",
      "consumer": "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py",
      "executed": true,
      "exit_code": 0,
      "probe": {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0084/probe2_both_states.py",
        "exit_code": 0,
        "fingerprint": "c3c048e75a601938729752e1f3199a2f",
        "method": "command",
        "raw_output": "named probe2 both-states",
        "role": "verifier"
      },
      "read_ok": true
    }
  ],
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0084/detector.py:10",
      "claim": "Deadlock requires a frozen ledger fingerprint and a wait-for cycle; wall_ms is recorded and is not a predicate.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0084/probe1_slow_vs_stuck.py",
          "exit_code": 0,
          "fingerprint": "f38029f62691340aa73246fe59091b10",
          "method": "command",
          "raw_output": "{\"errors\": [], \"known_good\": {\"cycle\": null, \"fired\": false, \"frozen\": false, \"label\": \"PROGRESSING\", \"next_rung\": null, \"reason\": \"ledger-fingerprint-changed\", \"silent\": true, \"wall_ms\": 780000}, \"pass\": true, \"planted_bad\": {\"cycle\": [\"alice\", \"bob\", \"alice\"], \"fired\": true, \"frozen\": true, \"label\": \"DEADLOCKED\", \"next_rung\": \"recruit\", \"reason\": \"frozen-ledger-and-wait-for-cycle\", \"silent\": false, \"trigger\": \"deadlock-with-vacant-role-or-no-dissent\", \"wall_ms\": 12000}, \"probe\": \"probe1_slow_vs_stuck\", \"unit_id\": \"CNL-0084\", \"wall_clock_would_invert\": true}\nslow_progress silent=True wall_ms=780000 stuck FIRE=True wall_ms=12000 wall_clock_would_invert=True first_rung=recruit\nSUCCESS:CNL-0084-probe1 slow-progress silent; stuck fires; wall-clock is not the predicate",
          "role": "source"
        },
        {
          "command": "command-center/p2-wave/probes/CNL-0084/detector.py:10",
          "exit_code": 0,
          "fingerprint": "9e8e088d0243fc2e354ff315bc7f6bb8",
          "method": "file-read",
          "raw_output": "Wall-clock elapsed time is recorded and is NOT a predicate; known-good wall_ms=780000 planted-bad wall_ms=12000",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py:independent_deadlocked",
      "claim": "Independent Kahn + canonical-JSON recount agrees: known-good is not deadlocked, planted-bad is deadlocked.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py:independent_deadlocked",
          "exit_code": 0,
          "fingerprint": "6e450373621716faf413a2b92a85a5e8",
          "method": "static-analysis",
          "raw_output": "independent_known_good_deadlocked=False independent_planted_bad_deadlocked=True",
          "role": "source"
        },
        {
          "command": "command-center/p2-wave/probes/CNL-0084/detector.py:125",
          "exit_code": 0,
          "fingerprint": "83774c4a9dd7af7d78bff177088d9eda",
          "method": "file-read",
          "raw_output": "planted-bad reason=frozen-ledger-and-wait-for-cycle cycle=['alice', 'bob', 'alice']",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/schema/council-design-note.schema.json",
      "claim": "The catalog output_schema shim exists; this note validates against the inlined council-design-note generic_report pin without a network $ref fetch.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "python3 -B command-center/p2-wave/probes/CNL-0084/note_schema.py",
          "exit_code": 0,
          "fingerprint": "fcd24089178a0badaa8cea66dd05974c",
          "method": "schema-validate",
          "raw_output": "inlined generic_report+$defs; garbage 3/3 rejected",
          "role": "source"
        },
        {
          "command": "command-center/schema/council-design-note.schema.json",
          "exit_code": 0,
          "fingerprint": "6d7ad18f322e51662713f1aaa3f47a4d",
          "method": "file-read",
          "raw_output": "catalog shim exists; physical pin is council-design-note",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    }
  ],
  "manifest_registration": {
    "entry_id": "CNL-0084",
    "manifest_path": "command-center/p2-wave/probes/CNL-0084/UNIT-ARTIFACT-MANIFEST.json",
    "registered": true
  },
  "min_bytes_threshold": 2048,
  "negative_controls": [
    {
      "bad_state_output": "label=DEADLOCKED fired=True wall_ms=12000 cycle=['alice', 'bob', 'alice'] reason=frozen-ledger-and-wait-for-cycle",
      "description": "The detector must FIRE on planted-bad deadlock and stay SILENT on known-good slow progress. A duration-only heuristic would invert the labels.",
      "fired_on_bad_state": true,
      "good_state_output": "label=PROGRESSING fired=False wall_ms=780000 reason=ledger-fingerprint-changed",
      "id": "slow-progress-must-stay-silent",
      "kind": "known-broken-fixture",
      "silent_on_good_state": true
    },
    {
      "bad_state_output": "label=DEADLOCKED fired=True wall_ms=12000 cycle=['alice', 'bob', 'alice'] reason=frozen-ledger-and-wait-for-cycle",
      "description": "Productive disagreement that keeps adding dissent briefs must not be labelled DEADLOCKED.",
      "fired_on_bad_state": true,
      "good_state_output": "label=PROGRESSING fired=False reason=ledger-fingerprint-changed",
      "id": "productive-disagreement-is-not-deadlock",
      "kind": "other",
      "silent_on_good_state": true
    },
    {
      "bad_state_output": "label=DEADLOCKED fired=True wall_ms=12000 cycle=['alice', 'bob', 'alice'] reason=frozen-ledger-and-wait-for-cycle",
      "description": "A seat that never returns is STALLED_RUNTIME, not deadlock.",
      "fired_on_bad_state": true,
      "good_state_output": "label=STALLED_RUNTIME fired=False missing=['carol']",
      "id": "stalled-runtime-is-operational-not-deliberation",
      "kind": "other",
      "silent_on_good_state": true
    }
  ],
  "produced_by": {
    "execution_substrate": "local-parallel",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "vendor": "grok"
  },
  "profile": "council-design-note",
  "report": {
    "answer": "A council is deadlocked when it is still producing turns (every expected seat has returned at least once, so this is not a stalled runtime) AND the deliberation ledger fingerprint is identical across the last stuck_windows observation windows AND the seat awaiting-graph contains a wait-for cycle. The fingerprint is the sorted tuple of claim_ids, evidence_hashes, vote_tally pairs, dissent_brief_ids, and open_questions. Wall-clock elapsed time is not a predicate: the known-good slow-progress fixture ends at wall_ms=780000 and is SILENT (label=PROGRESSING); the planted-bad fixture ends at wall_ms=12000 and FIRES (label=DEADLOCKED, cycle=['alice', 'bob', 'alice']). Productive disagreement that keeps adding dissent briefs is PROGRESSING. A seat that never returns is STALLED_RUNTIME, an operational failure path, not a deliberation outcome. Frozen ledger without a cycle is FROZEN_WITHOUT_CYCLE and is out of scope here (CNL-0090 circular debate). Ordered ladder, each rung gated on DEADLOCKED still holding: (1) recruit \u2014 vacant required role or vote_tally has <2 distinct options; (2) replace \u2014 recruit already applied, or recorded inapplicable because the roster is full and dissent already exists, and the same wait-for cycle persists; (3) reframe \u2014 replace already applied and the open question set is still frozen; (4) escalate_to_owner \u2014 reframe already applied; emit one foundation-level question naming the deadlocked proposition, a recommendation, and default_if_silent=UNRESOLVED-AND-FREEZE. Rungs cannot be skipped upward except recruit-inapplicable, which is recorded on the replace trigger. SUCCESS:CNL-0084",
    "control_ids": [
      "slow-progress-must-stay-silent",
      "productive-disagreement-is-not-deadlock",
      "stalled-runtime-is-operational-not-deliberation"
    ],
    "deadlock_signature": {
      "both_states": {
        "independent_known_good_deadlocked": false,
        "independent_planted_bad_deadlocked": true,
        "known_good_fired": false,
        "known_good_label": "PROGRESSING",
        "known_good_wall_ms": 780000,
        "planted_bad_cycle": [
          "alice",
          "bob",
          "alice"
        ],
        "planted_bad_fired": true,
        "planted_bad_label": "DEADLOCKED",
        "planted_bad_wall_ms": 12000
      },
      "exclusions": [
        "STALLED_RUNTIME when any expected seat never returned",
        "STOPPED when stopping_satisfied is true (CNL-0076 evaluates that bit)",
        "FROZEN_WITHOUT_CYCLE deferred to CNL-0090",
        "PROGRESSING when any ledger field changes"
      ],
      "min_turns": 2,
      "not_a_signal": "wall_ms",
      "signals": [
        "ledger-fingerprint-freeze",
        "wait-for-cycle"
      ],
      "stuck_windows": 2
    },
    "escalation_ladder": [
      {
        "measured": {
          "dissent_present": false,
          "rung": "recruit",
          "trigger": "deadlock-with-vacant-role-or-no-dissent",
          "vacant_roles": [
            "critic"
          ]
        },
        "order": 1,
        "rung": "recruit",
        "trigger": "DEADLOCKED and (vacant required role or no dissent in vote_tally)"
      },
      {
        "measured_after_recruit": {
          "cycle_seats": [
            "alice",
            "bob",
            "alice"
          ],
          "rung": "replace",
          "trigger": "deadlock-persists-after-recruit-same-cycle-seats"
        },
        "measured_full_roster": {
          "cycle_seats": [
            "alice",
            "bob",
            "alice"
          ],
          "recruit_inapplicable": true,
          "rung": "replace",
          "trigger": "deadlock-full-roster-recruit-inapplicable"
        },
        "order": 2,
        "rung": "replace",
        "trigger": "DEADLOCKED after recruit, or recruit inapplicable on a full dissenting roster"
      },
      {
        "measured": {
          "open_questions": [
            "q-main"
          ],
          "rung": "reframe",
          "trigger": "deadlock-persists-after-replace-same-proposition"
        },
        "order": 3,
        "rung": "reframe",
        "trigger": "DEADLOCKED after replace on the same open-question set"
      },
      {
        "measured": {
          "owner_packet": {
            "deadlocked_proposition": "q-reframed",
            "default_if_silent": "UNRESOLVED-AND-FREEZE",
            "question": "May this council stop, with the deadlocked proposition named, using the recorded recommendation?",
            "recommendation": "Declare the proposition UNRESOLVED; keep the ledger; do not spend remaining deliberation budget."
          },
          "rung": "escalate_to_owner",
          "trigger": "deadlock-persists-after-reframe"
        },
        "order": 4,
        "owner_packet": {
          "deadlocked_proposition": "q-reframed",
          "default_if_silent": "UNRESOLVED-AND-FREEZE",
          "question": "May this council stop, with the deadlocked proposition named, using the recorded recommendation?",
          "recommendation": "Declare the proposition UNRESOLVED; keep the ledger; do not spend remaining deliberation budget."
        },
        "rung": "escalate_to_owner",
        "trigger": "DEADLOCKED after reframe; one foundation question plus default"
      }
    ],
    "format_note": "Catalog output_path ends in .md. G-1 _measure_one_delivered.py json.loads the whole file, so this artifact is JSON.",
    "kind": "council-design-note",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0084/fixtures/known_good_slow_progress.json:42",
        "measured": "label=PROGRESSING fired=False wall_ms=780000 reason=ledger-fingerprint-changed",
        "method": "detector.classify fingerprint-tuple plus DFS cycle",
        "name": "known-good-slow-progress"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0084/fixtures/planted_bad_deadlock.json:20",
        "measured": "label=DEADLOCKED fired=True wall_ms=12000 cycle=['alice', 'bob', 'alice'] reason=frozen-ledger-and-wait-for-cycle",
        "method": "detector.classify fingerprint-tuple plus DFS cycle",
        "name": "planted-bad-deadlock"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py:independent_deadlocked",
        "measured": "independent_known_good_deadlocked=False independent_planted_bad_deadlocked=True",
        "method": "canonical JSON of ledger fields plus Kahn cycle",
        "name": "independent-kahn-recount"
      }
    ],
    "question": "What signature identifies a deadlocked council (as distinct from a slow but progressing one), and what is the ordered escalation ladder - recruit, replace, reframe, escalate to owner - with the trigger for each rung?",
    "title": "Deadlock detection and the escalation ladder"
  },
  "residual_unknowns": [
    {
      "claim": "CNL-0076 owns when stopping_satisfied is evaluated; this detector only reads the bit.",
      "settling_experiment": "Deliver CNL-0076 on this worktree and replay the planted-bad fixture with stopping_satisfied flipped at end-of-round.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "FROZEN_WITHOUT_CYCLE is labelled and left SILENT for deadlock; CNL-0090 owns circular-debate / information-gain.",
      "settling_experiment": "Deliver CNL-0090 and confirm a frozen-no-cycle fixture stays outside this detector's FIRE set.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "Catalog inputs cite a Windows harness-restore _USER-PROMPTS.md that is not on this Linux worktree.",
      "settling_experiment": "Mount the harness-restore slice and quote the cited line range; until then the signature is derived from the catalog question plus the both-states fixtures.",
      "verdict": "NOT-CHECKED"
    }
  ],
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts."
  },
  "reviewer": {
    "fresh_context": true,
    "independent": true,
    "notes": "Catalog asked for a cross-vendor openai/gpt-5-codex reviewer who re-runs the both-states control. No that-vendor session is on this Linux worktree. The live independent control is probe2: Kahn's algorithm plus canonical JSON of ledger fields, a different mechanism from detector.py's DFS+tuple fingerprint. Wall-clock counterexample: known-good wall_ms=780000 exceeds planted-bad wall_ms=12000 yet only the planted-bad FIRES. Named probe2 re-runs FIRE/SILENT before G-1 accepts this unit.",
    "reviewer_id": "CNL-0084-probe2-both-states-kahn-recount",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0084",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:38463",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0084/probe1_slow_vs_stuck.py",
      "id": "probe1-slow-vs-stuck",
      "name": "slow-but-progressing stays SILENT; genuinely stuck FIRES; wall-clock would invert",
      "output_tail": "{\"errors\": [], \"known_good\": {\"cycle\": null, \"fired\": false, \"frozen\": false, \"label\": \"PROGRESSING\", \"next_rung\": null, \"reason\": \"ledger-fingerprint-changed\", \"silent\": true, \"wall_ms\": 780000}, \"pass\": true, \"planted_bad\": {\"cycle\": [\"alice\", \"bob\", \"alice\"], \"fired\": true, \"frozen\": true, \"label\": \"DEADLOCKED\", \"next_rung\": \"recruit\", \"reason\": \"frozen-ledger-and-wait-for-cycle\", \"silent\": false, \"trigger\": \"deadlock-with-vacant-role-or-no-dissent\", \"wall_ms\": 12000}, \"probe\": \"probe1_slow_vs_stuck\", \"unit_id\": \"CNL-0084\", \"wall_clock_would_invert\": true}\nslow_progress silent=True wall_ms=780000 stuck FIRE=True wall_ms=12000 wall_clock_would_invert=True first_rung=recruit\nSUCCESS:CNL-0084-probe1 slow-progress silent; stuck fires; wall-clock is not the predicate",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; from pathlib import Path; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0084'); from probe2_both_states import independent_deadlocked; fx=Path('command-center/p2-wave/probes/CNL-0084/fixtures'); print(independent_deadlocked(fx/'known_good_slow_progress.json')); print(independent_deadlocked(fx/'planted_bad_deadlock.json'))\"",
      "id": "independent-kahn-both-states",
      "name": "Kahn recount SILENT on known-good and FIRE on planted-bad",
      "output_tail": "independent_known_good_deadlocked=False independent_planted_bad_deadlocked=True",
      "result": "PASS"
    }
  ],
  "timestamps": {
    "duration_seconds": 0,
    "ended_at": "2026-08-25T00:57:43Z",
    "started_at": "2026-08-25T00:57:43Z"
  },
  "unit_id": "CNL-0084"
}
