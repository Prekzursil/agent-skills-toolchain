{
  "answer": "A participant is obliged to respond only when an accepted graph node records requires_response=true and a named addressee, and the reply hop (parent-walk depth + 1) is still inside the rebuttal_depth budget. Unnamed addressees create no obligation. An obligation is ANSWERED only by a discharge-kind turn (rebuttal, concession, or explicit_pass) from that addressee that addresses the same claim_id; a topic_change or acknowledgement does not discharge. At synthesis, remaining OPEN obligations become IGNORED nodes on the argument graph and must not be dropped. Rebuttal depth is hop-count from the root claim. A hop whose depth exceeds the budget is HARD-STOPPED: the node is refused and the would-be obligation is CUT_BY_DEPTH, which is neither consensus nor an ignore. CNL-0047 is a scheduler plug (entitled-to-speak); this unit does not claim turn order. Harness files 11-COUNCIL-SPECIFICATION and 12-COUNCIL-PROTOCOLS-AND-PRESETS are absent on this worktree; the contract is operationalized from the catalog question and tests_required.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0048-response-obligations-and-rebuttal-depth.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0048/engine.py",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "supporting"
    }
  ],
  "both_states": {
    "depth_cut": {
      "fires": false,
      "n2_accepted": false,
      "verbatim": "depth_cut unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=['cut:n2']"
    },
    "ignored_argument": {
      "fires": true,
      "ignored_ids": [
        "obl:n0"
      ],
      "ignored_visible": true,
      "verbatim": "ignored_argument unanswered_fires=True ignored=['obl:n0'] silent_drop=[] ignored_visible=True cuts=[]"
    },
    "known_good": {
      "fires": false,
      "verbatim": "known_good unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=[]"
    }
  },
  "contract": {
    "answered": "addressee posted a discharge-kind turn addressing the claim_id",
    "cut": "reply hop would exceed budget; status=CUT_BY_DEPTH; not IGNORED",
    "discharge_kinds": [
      "concession",
      "explicit_pass",
      "rebuttal"
    ],
    "ignored": "OPEN at synthesis; remains a graph node with status=IGNORED",
    "oblige_when": [
      "requires_response is true on an accepted node",
      "addressee is a named seat",
      "reply_depth = hop_depth(parent)+1 is <= rebuttal_depth_budget"
    ],
    "scheduler_plug": "entitled_to_speak(seat) from CNL-0047; not implemented here"
  },
  "dependency_note": "CNL-0047 (turn-taking) is specified as a plug: this engine assumes the addressee is entitled to speak when an OPEN obligation exists. CNL-0047's artifact is not required to execute the fixtures.",
  "evidence": [
    {
      "claim": "Obligation creation requires a named addressee; unnamed requires_response creates no OPEN obligation.",
      "signal": {
        "anchor": "command-center/p2-wave/probes/CNL-0048/engine.py:5",
        "kind": "file_line",
        "snippet": "NAMED_ADDRESSEE_REQUIRED"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Ignored obligations remain visible on the synthesized argument graph.",
      "signal": {
        "anchor": "command-center/p2-wave/probes/CNL-0048/engine.py:13",
        "kind": "file_line",
        "snippet": "IGNORED_SURVIVES_SYNTHESIS"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Depth exhaustion hard-stops the next hop as CUT_BY_DEPTH, not as ignore or consensus.",
      "signal": {
        "anchor": "command-center/p2-wave/probes/CNL-0048/engine.py:18",
        "kind": "file_line",
        "snippet": "DEPTH_HARD_STOP_NOT_CONSENSUS"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "A topic_change by the addressee does not discharge the obligation.",
      "signal": {
        "anchor": "command-center/p2-wave/probes/CNL-0048/engine.py:9",
        "kind": "file_line",
        "snippet": "NON_ANSWER_DOES_NOT_DISCHARGE"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Both-states: unanswered check FIRES on ignored_argument and is SILENT on known_good.",
      "signal": {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0048/probe1_both_states.py",
        "kind": "command_output",
        "output": "known_good unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=[]\nignored_argument unanswered_fires=True ignored=['obl:n0'] silent_drop=[] ignored_visible=True cuts=[]"
      },
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Independent set-algebra recount of ignored_argument matches labeled ignored_ids.",
      "signal": {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0048/probe2_independent_recount.py",
        "kind": "command_output",
        "output": "recount_ignored=['obl:n0'] labeled_ignored=['obl:n0'] fires=True"
      },
      "verdict": "CONFIRMED"
    }
  ],
  "inputs_on_this_tree": {
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "catalog_question_used": true
  },
  "negative_controls": [
    {
      "bad_state_output": "ignored_argument unanswered_fires=True ignored=['obl:n0'] silent_drop=[] ignored_visible=True cuts=[]",
      "fired_on_bad_state": true,
      "good_state_output": "known_good unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=[]",
      "id": "NC-unanswered-on-ignored",
      "rejects": "an unanswered named obligation silently omitted at synthesis or treated as answered",
      "silent_on_good_state": true
    },
    {
      "bad_state_output": "silent_drop_mutant unanswered_fires=False ignored=[] silent_drop=['obl:n0'] ignored_visible=False cuts=[]",
      "fired_on_bad_state": true,
      "good_state_output": "known_good unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=[]",
      "id": "NC-silent-drop-mutant",
      "rejects": "a synthesizer that drops IGNORED rows so the unanswered check goes silent",
      "silent_on_good_state": true
    },
    {
      "bad_state_output": "non_answer unanswered_fires=True ignored=['obl:n0'] silent_drop=[] ignored_visible=True cuts=[]",
      "fired_on_bad_state": true,
      "good_state_output": "known_good unanswered_fires=False ignored=[] silent_drop=[] ignored_visible=True cuts=[]",
      "id": "NC-non-answer-is-not-discharge",
      "rejects": "counting any addressee utterance as a response",
      "silent_on_good_state": true
    }
  ],
  "question": "When is a participant OBLIGED to respond to a specific argument, how deep may rebuttal chains go before the depth budget cuts them, and what marks an argument as answered versus ignored?",
  "reviewer": {
    "counterexample": {
      "attempted": true,
      "detail": "A topic_change by the addressee leaves obl:n0 IGNORED. The competing rule 'any reply discharges' is refuted.",
      "fixture": "non_answer",
      "id": "any-reply-discharges",
      "refutes": true
    },
    "independent": true,
    "mechanism": "set-algebra created-minus-discharged-minus-cut",
    "note": "Mechanical independent re-run of both-states via parent-walk set algebra (probe2). A live cross-vendor model session was not invoked on this worktree.",
    "re_ran_both_states": true,
    "reviewer_id": "CNL-0048-probe2-independent-recount",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0048",
  "state": "SUCCESS",
  "tests": [
    {
      "assertion": "unanswered obligation obl:n0 remains on the synthesized graph as IGNORED",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0048/probe1_both_states.py",
      "id": "T1-ignored-argument-visible",
      "result": "PASS"
    },
    {
      "assertion": "unanswered check FIRES on ignored_argument and is SILENT on known_good",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0048/probe1_both_states.py",
      "id": "T2-both-states",
      "result": "PASS"
    },
    {
      "assertion": "set-algebra recount agrees with labels; topic_change does not discharge",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0048/probe2_independent_recount.py",
      "id": "T3-independent-recount-non-answer",
      "result": "PASS"
    }
  ],
  "title": "Response obligations and rebuttal depth",
  "ts": "2026-08-25T00:52:36Z",
  "unit_id": "CNL-0048"
}
