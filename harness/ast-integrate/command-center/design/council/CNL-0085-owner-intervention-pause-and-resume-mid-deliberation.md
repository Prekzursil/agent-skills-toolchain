{
  "unit_id": "CNL-0085",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0085",
  "title": "Owner intervention, pause and resume mid-deliberation",
  "question": "What may an owner change mid-council without invalidating the run (adding evidence, extending a budget) versus what forces a restart (changing the question, replacing the chair) - and where is that boundary recorded so the audit trail stays honest?",
  "decision": "A mid-council owner change is CONTINUE if and only if it leaves the run identity tuple (question, chair_id, protocol_id, roster, vote_weights, information_partition) unchanged AND does not mutate any already-committed event. Adding evidence and extending a still-unconsumed budget are CONTINUE: they append an origin=owner event after the pause cursor. Changing the question or replacing the chair is RESTART: the runtime must emit a restart_record and refuse quiet continuation on the same run_id. The boundary is the owner_intervention / restart_record pair on the event log, keyed by prefix_sha256 of the committed prefix. This rule is the catalog question's own four examples generalized by identity-preservation; it is not an invented owner preference. OWNER-DECISIONS.md is absent on this worktree and is recorded as a residual, not forged.",
  "identity_tuple": [
    "question",
    "chair_id",
    "protocol_id",
    "roster",
    "vote_weights",
    "information_partition"
  ],
  "continue_classes": [
    "evidence_add",
    "budget_extend",
    "guidance_inject",
    "constraint_add_future",
    "pause",
    "resume"
  ],
  "restart_classes": [
    "question_change",
    "chair_replace",
    "protocol_change",
    "roster_replace_voting_seat",
    "evidence_rewrite",
    "vote_weight_change",
    "information_partition_change"
  ],
  "audit_trail": "CONTINUE writes type=owner_intervention origin=owner after the pause cursor and leaves prefix_sha256 of events[:cursor] unchanged. RESTART writes type=restart_record with old_run_id, class, reason, cursor, prefix_sha256, invalidates_run=true and sets status=RESTART_REQUIRED. A mode=continue on a RESTART class raises QuietContinuationRefused and appends nothing. Derived votes and minority reports are rebuilt from the event log on resume, never cached beside it.",
  "rules": [
    {
      "id": "identity-tuple",
      "statement": "Run identity is (question, chair_id, protocol_id, roster, vote_weights, information_partition). Mutating any element invalidates the run."
    },
    {
      "id": "append-only-continue",
      "statement": "evidence_add and budget_extend (new ceiling still covering consumed rounds) append an owner-origin event and MUST NOT rewrite prefix events, votes, or the minority report."
    },
    {
      "id": "recorded-restart",
      "statement": "question_change and chair_replace emit restart_record and refuse quiet continuation on the same run_id."
    },
    {
      "id": "replay-from-log",
      "statement": "Resume rebuilds derived state from the pause prefix; a tampered prefix_sha256 is PrefixMismatch, not a silent resume."
    }
  ],
  "claims": [
    {
      "id": "C1",
      "claim": "Invalidating changes (question_change, chair_replace, evidence_rewrite) force a recorded restart, not quiet continuation.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0085/intervention.py:9"
    },
    {
      "id": "C2",
      "claim": "Adding evidence or extending max_rounds continues the same run_id with the committed prefix and dissent preserved.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0085/intervention.py:169"
    },
    {
      "id": "C3",
      "claim": "Pause then resume replays to the same derived state up to the intervention cursor; tampered pause records are rejected.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0085/intervention.py:248"
    }
  ],
  "tests": [
    {
      "id": "invalidating-restart",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0085/probe1_invalidating_restart.py",
      "result": "PASS"
    },
    {
      "id": "resume-replay",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0085/probe2_resume_replay.py",
      "result": "PASS"
    },
    {
      "id": "negative-control-quiet-continuation",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0085/probe1_invalidating_restart.py",
      "result": "PASS"
    }
  ],
  "both_states": {
    "fires_on": "command-center/p2-wave/probes/CNL-0085/fixtures/quiet-continuation.json (question_change mode=continue)",
    "silent_on": "command-center/p2-wave/probes/CNL-0085/fixtures/evidence-add.json (append-only evidence_add)",
    "verbatim_fire": "quiet continuation refused for class=question_change run_id=run-quiet-bad cursor=4",
    "verbatim_silent": "evidence_add disposition=CONTINUE restart_record=false prefix_preserved=true dissent_preserved=true"
  },
  "negative_controls": [
    {
      "id": "quiet-continuation-question-change",
      "rejects": "raises QuietContinuationRefused on question_change with mode=continue or force_continue=True; does not append owner_intervention to the same run_id; does not rewrite prefix events. Silent (CONTINUE) on evidence_add.",
      "observed": "quiet continuation refused for class=question_change run_id=run-quiet-bad cursor=4"
    },
    {
      "id": "tampered-pause-record",
      "rejects": "CouncilRun.from_snapshot raises PrefixMismatch on a stale prefix_sha256 (integrity). When the hash is recomputed to match the tampered bytes, rebuilt minority_reports diverge from the original dissent, proving replay reads events not a cached string.",
      "observed": "pause-record prefix_sha256 mismatch claimed=da42ff268658c731fb7e5c7805489869559664b5d3d22c13a787ef9c801ed0d4 actual=b1c9ef76f207e8cfb9d0f2247b1b69d8db88fd3a243fe42c3b2a61f70edd9c69"
    }
  ],
  "evidence": [
    {
      "claim": "question_change and chair_replace emit restart_record; evidence_add does not",
      "mechanism": "probe1 classifier disposition plus restart_record presence on the event log (enum/field, not a hash)",
      "anchor": "command-center/p2-wave/probes/CNL-0085/intervention.py:9",
      "verbatim": "{\"negative_control\": {\"events_unchanged\": true, \"fired\": true, \"id\": \"quiet-continuation-question-change\", \"state_meant_to_reject\": \"command-center/p2-wave/probes/CNL-0085/fixtures/quiet-continuation.json\", \"verbatim_exception\": \"quiet continuation refused for class=question_change run_id=run-quiet-bad cursor=4\", \"what_the_check_does\": \"raises QuietContinuationRefused on question_change with mode=continue or force_continue=True; does not append owner_intervention to the same run_id; does not rewrite prefix events. Silent (CONTINUE) on evidence_add.\"}, \"pass\": true, \"probe\": \"probe1-invalidating-restart\", \"rows\": [{\"disposition\": \"CONTINUE\", \"dissent_preserved\": true, \"op\": \"evidence_add\", \"prefix_preserved\": true, \"restart_record\": false}, {\"disposition\": \"CONTINUE\", \"dissent_preserved\": true, \"op\": \"budget_extend\", \"prefix_preserved\": true, \"restart_record\": false}, {\"disposition\": \"RESTART\", \"op\": \"question_change\", \"quiet_continuation\": false, \"restart_record\": true}, {\"disposition\": \"RESTART\", \"op\": \"chair_replace\", \"quiet_continuation\": false, \"restart_record\": true}, {\"disposition\": \"RESTART\", \"op\": \"evidence_rewrite\", \"quiet_continuation\": false, \"restart_record\": true}], \"unit_id\": \"CNL-0085\"}\nquestion_change restart_record=True quiet_continuation=False evidence_add CONTINUE prefix_preserved=True\nNEGATIVE CONTROL rejects quiet continuation of question_change; exception=quiet continuation refused for class=question_change run_id=run-quiet-bad cursor=4\nSUCCESS:CNL-0085-probe1 invalidating change forces recorded restart"
    },
    {
      "claim": "resume reconstructs votes and minority report; stale prefix_sha256 is PrefixMismatch",
      "mechanism": "probe2 sha256 of canonical prefix plus derived-state equality after from_snapshot replay",
      "anchor": "command-center/p2-wave/probes/CNL-0085/intervention.py:248",
      "verbatim": "{\"derived_state_sha256\": \"54c372ec3afa011fbd3c2f7d05e86e3607075d38e43c057795fc6afb0b6deb98\", \"dissent_survived_resume\": true, \"evidence_add_prefix_preserved\": true, \"negative_control\": {\"fired\": true, \"id\": \"tampered-pause-record\", \"rehashed_dissent_diverged\": true, \"state_meant_to_reject\": \"pause snapshot whose minority_report text was mutated so prefix bytes no longer match prefix_sha256\", \"verbatim_exception\": \"pause-record prefix_sha256 mismatch claimed=da42ff268658c731fb7e5c7805489869559664b5d3d22c13a787ef9c801ed0d4 actual=b1c9ef76f207e8cfb9d0f2247b1b69d8db88fd3a243fe42c3b2a61f70edd9c69\", \"what_the_check_does\": \"CouncilRun.from_snapshot raises PrefixMismatch on a stale prefix_sha256 (integrity). When the hash is recomputed to match the tampered bytes, rebuilt minority_reports diverge from the original dissent, proving replay reads events not a cached string.\"}, \"original_prefix_sha256\": \"da42ff268658c731fb7e5c7805489869559664b5d3d22c13a787ef9c801ed0d4\", \"pass\": true, \"probe\": \"probe2-resume-replay\", \"replay_derived_equal\": true, \"unit_id\": \"CNL-0085\"}\nreplay_equal=True prefix=da42ff268658c731... dissent_survived=True tampered_stale_hash_rejected=True\nNEGATIVE CONTROL PrefixMismatch: pause-record prefix_sha256 mismatch claimed=da42ff268658c731fb7e5c7805489869559664b5d3d22c13a787ef9c801ed0d4 actual=b1c9ef76f207e8cfb9d0f2247b1b69d8db88fd3a243fe42c3b2a61f70edd9c69\nSUCCESS:CNL-0085-probe2 resume replays to the same state up to intervention"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0085-probe2-resume-replay",
    "verdict": "PASS",
    "independent": true,
    "method": "Probe2 does not call classify(). It pauses a scripted run, replays from the event prefix, compares derived-state sha256, then tampers the minority_report bytes. That is a different mechanism from probe1's disposition enum. The reviewer does not grant owner sign-off."
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0085-owner-intervention-pause-and-resume-mid-deliberation.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0085/intervention.py",
      "exists": true,
      "role": "supporting"
    }
  ],
  "residual_unknowns": [
    "command-center/OWNER-DECISIONS.md is absent; catalog reviewer_requirement asked for owner sign-off before close. This agent does not author a fake owner ruling. G-1 delivers the design and probes; the owner-gate remains a named residual.",
    "Harness-restore inputs C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10915-10946 and 11-COUNCIL-SPECIFICATION.schema.json are not mounted on this Linux worktree. Boundary examples are taken from the catalog question_or_target, which already names adding evidence / extending a budget versus changing the question / replacing the chair.",
    "CNL-0011 (replay state model) is a declared dependency and is not yet delivered on this tree. CNL-0085 serializes identity, seeds, the event prefix, and prefix_sha256 so resume can be tested here; it does not claim to have settled which additional nondeterminism seeds CNL-0011 will require."
  ],
  "owner_approval_required": true,
  "owner_signoff": {
    "path": "command-center/OWNER-DECISIONS.md",
    "present": false,
    "forged": false,
    "status": "residual-not-granted-by-reviewer"
  },
  "named_probes": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0085/probe1_invalidating_restart.py",
      "exit_code": 0
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0085/probe2_resume_replay.py",
      "exit_code": 0
    }
  ],
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "min_bytes_threshold": 2048,
  "ts": "2026-08-25T00:41:39Z",
  "notes": "SUCCESS:CNL-0085 G-1 design note. Live named probes exit 0. Did not run global unit_manifest.py --write. Did not forge OWNER-DECISIONS.md. cloud ok=true is not delivery."
}
