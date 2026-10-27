{
 "artifacts": [
  {
   "bytes": 17202,
   "eol": "LF",
   "exists": true,
   "path": "command-center/design/council/CNL-0047-turn-taking-and-speaking-order-engine-as-one-shared-primit.md",
   "role": "primary",
   "sha256": "3a7df99f0265c6866311347d089212fa7e3c9abec66d38d9efd6220b5e97ef22"
  },
  {
   "bytes": 1118,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting",
   "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755"
  },
  {
   "bytes": 6344,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0047/scheduler.py",
   "role": "supporting",
   "sha256": "5eeb9e748d11ad38b983715cbf3d4ceca52c4cd843550f107581912433a0f360"
  },
  {
   "bytes": 710,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0047/broken.py",
   "role": "supporting",
   "sha256": "07f27b71a83b27982b01745397606194ced9c70424bfcc4be78ba1a81774a836"
  },
  {
   "bytes": 2263,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0047/detect.py",
   "role": "supporting",
   "sha256": "1a809adcacda2e818421dde8633263f9ee430ab836f3d4be08fd3f087d086cba"
  },
  {
   "bytes": 3963,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
   "role": "supporting",
   "sha256": "2f65db52c50706686fb5429be577a7143ded77180c37fb96f7982ff768d33c3e"
  },
  {
   "bytes": 2846,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
   "role": "supporting",
   "sha256": "11b3ca9e41009def0f009709a93104f1d32c098b581c6a7be74453463f37c49c"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0047-turn-taking-and-speaking-order-engine-as-one-shared-primit.md",
   "consumer": "json.loads of catalog output_path",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "python3 -c json.loads(command-center/design/council/CNL-0047-turn-taking-and-speaking-order-engine-as-one-shared-primit.md)",
    "exit_code": 0,
    "fingerprint": "9b3c728ab3ed2e5cc8cfe791abd10d79a621ff091bd44cf56aee5fd51d16f8d8",
    "method": "schema-validate",
    "raw_output": "consumer=json.loads of catalog output_path\nunit_id=CNL-0047\nstate=SUCCESS\nSUCCESS:CNL-0047",
    "role": "source"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
   "claim": "A dominant seat is throttled at its own 50-token quota without silencing a legitimately prolific seat that finishes its 45-token bag.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
     "exit_code": 0,
     "fingerprint": "19b22585143f6dbcdfd44cb7138948f209f11d19da60d136f8759f757f8c081c",
     "method": "command",
     "raw_output": "quota-starvation log [[\"SPEAK\", \"dominant\", 20], [\"SPEAK\", \"prolific\", 20], [\"YIELD\", \"quiet\", 0], [\"SPEAK\", \"dominant\", 20], [\"SPEAK\", \"prolific\", 20], [\"YIELD\", \"quiet\", 0], [\"SPEAK\", \"dominant\", 10], [\"SPEAK\", \"prolific\", 5], [\"YIELD\", \"quiet\", 0], [\"THROTTLE\", \"dominant\", 0], [\"YIELD\", \"prolific\", 0], [\"YIELD\", \"quiet\", 0]]\nspoken={\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0} independent_recount={\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0} yields={\"dominant\": 0, \"prolific\": 1, \"quiet\": 4, \"observer\": 0} throttles={\"dominant\": 1, \"prolific\": 0, \"quiet\": 0, \"observer\": 0}\nSUCCESS:CNL-0047-probe1 quota-starvation both directions and entitled-empty YIELD",
     "role": "source"
    },
    {
     "command": "sum SPEAK tokens from Scheduler.log not seat.spoken_tokens",
     "exit_code": 0,
     "fingerprint": "e86fc12fe3514f1eb9ca65f92e1260b645662e2835551961b4ebd41176479836",
     "method": "byte-compare",
     "raw_output": "spoken={\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0} throttles={\"dominant\": 1, \"prolific\": 0, \"quiet\": 0, \"observer\": 0} yields={\"dominant\": 0, \"prolific\": 1, \"quiet\": 4, \"observer\": 0}",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
   "claim": "prolific_silenced_after_dominant_throttle FIRES on the equalizing planted-bad scheduler and is SILENT on the known-good Scheduler.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
     "exit_code": 0,
     "fingerprint": "d347f51d2ee9b08feec054b290674bff9c418406b1ea5d6ea496154126a6edc9",
     "method": "command",
     "raw_output": "both-states known-good {\"fired\": false, \"reason\": \"throttle_at=9 prolific_then=45 remaining_quota=5 remaining_content=0 prolific_after=0 fired=False\", \"spoken\": {\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0}}\nboth-states planted-bad {\"fired\": true, \"reason\": \"throttle_at=9 prolific_then=30 remaining_quota=20 remaining_content=15 prolific_after=0 fired=True\", \"spoken\": {\"dominant\": 50, \"prolific\": 30, \"quiet\": 0, \"observer\": 0}}\nnegative-control check=prolific_silenced_after_dominant_throttle reject_state=equalizing-scheduler-silences-prolific-when-dominant-hits-quota on_reject_state=True on_known_good=False\nreviewer {\"counterexample\": {\"attempted\": true, \"id\": \"remainder-cap-quota-5-vs-turn-length-20\", \"instance\": {\"expected_last_speak\": 5, \"expected_total\": 25, \"quota_tokens\": 25, \"turn_length_tokens\": 20}, \"note\": \"REFUTED-NOT-ATTEMPTED is forbidden; this instance was run. A whole-turn throttle when remaining < turn_length would refute the remainder-cap clause of the contract.\", \"partial_speak_sizes\": [20, 5], \"refuted\": false, \"spoken_from_log\": {\"other\": 25, \"partial\": 25}}, \"independent\": true, \"method\": \"Re-sum SPEAK tokens from the offer log (not seat.spoken_tokens) and run a remainder-cap instance the author did not use as probe1.\", \"pass\": true, \"reviewer_id\": \"CNL-0047-independent-log-recount\", \"verdict\": \"PASS\"}\nSUCCESS:CNL-0047-probe2 both-states FIRE on planted-bad SILENT on known-good",
     "role": "source"
    },
    {
     "command": "command-center/p2-wave/probes/CNL-0047/reviewer.py remainder-cap instance",
     "exit_code": 0,
     "fingerprint": "12c1335ca2d23bd2e158cf132af2147bddb6071208b8a7628743ddf8cfa2b45f",
     "method": "test-run",
     "raw_output": "{\"attempted\": true, \"id\": \"remainder-cap-quota-5-vs-turn-length-20\", \"instance\": {\"expected_last_speak\": 5, \"expected_total\": 25, \"quota_tokens\": 25, \"turn_length_tokens\": 20}, \"note\": \"REFUTED-NOT-ATTEMPTED is forbidden; this instance was run. A whole-turn throttle when remaining < turn_length would refute the remainder-cap clause of the contract.\", \"partial_speak_sizes\": [20, 5], \"refuted\": false, \"spoken_from_log\": {\"other\": 25, \"partial\": 25}}",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "cloud_ok_is_not_delivery": true,
  "completion_sentinel": "SUCCESS:CNL-0047",
  "global_unit_manifest_write": false,
  "harness_files_present": false
 },
 "manifest_registration": {
  "entry_id": "CNL-0047",
  "manifest_path": "command-center/p2-wave/probes/CNL-0047/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true,
  "registered_at": "2026-08-25T00:30:35Z"
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "bad_state_output": "{\"dominant_throttle_at\": 9, \"fired\": true, \"prolific_after\": 0, \"prolific_spoken_at_throttle\": 30, \"reason\": \"throttle_at=9 prolific_then=30 remaining_quota=20 remaining_content=15 prolific_after=0 fired=True\"}",
   "description": "Check prolific_silenced_after_dominant_throttle is meant to reject an equalizing scheduler that silences a still-entitled prolific seat once the dominant seat hits quota.",
   "fired_on_bad_state": true,
   "good_state_output": "{\"dominant_throttle_at\": 9, \"fired\": false, \"prolific_after\": 0, \"prolific_spoken_at_throttle\": 45, \"reason\": \"throttle_at=9 prolific_then=45 remaining_quota=5 remaining_content=0 prolific_after=0 fired=False\"}",
   "id": "NC-equalizing-silences-prolific",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "xai"
 },
 "report": {
  "answer": "The four dials are not four engines. They are four inputs to one next_offer machine (round-robin cursor, per-seat speaking_right, turn_length_tokens, per-seat quota_tokens). next_offer walks the roster from the cursor, skips any seat without speaking_right without emitting an offer, THROTTLEs a right-holding seat whose remaining quota is 0, otherwise offers min(turn_length, remaining quota). SPEAK consumes that many tokens from the seat's quota and advances the cursor. A seat that is entitled (right, remaining quota, cursor) but has nothing to add MUST YIELD: the cursor still advances, quota is not consumed, the seat is not marked disengaged (disengagement is CNL-0089's consecutive-yield floor, not this unit). Remainder smaller than turn_length is a partial SPEAK, not a whole-turn THROTTLE. Protocols do not implement their own airtime. SUCCESS:CNL-0047",
  "both_states": {
   "check": "prolific_silenced_after_dominant_throttle",
   "known_good_fired": false,
   "known_good_spoken": {
    "dominant": 50,
    "observer": 0,
    "prolific": 45,
    "quiet": 0
   },
   "planted_bad_fired": true,
   "planted_bad_spoken": {
    "dominant": 50,
    "observer": 0,
    "prolific": 30,
    "quiet": 0
   }
  },
  "contract": {
   "dials": {
    "order": "Cursor starts at 0. After SPEAK, YIELD, or THROTTLE the cursor becomes (index+1) mod roster. Seats without speaking_right are skipped and never appear in the offer log.",
    "quota": "Quota counts SPEAK tokens only. YIELD does not consume quota. THROTTLE fires iff remaining_quota==0 for a right-holding seat at the cursor.",
    "speaking_right": "A seat with speaking_right=false is never offered. Absence of right is not YIELD and is not disengagement.",
    "turn_length": "Each offer's cap is min(turn_length_tokens, remaining_quota). Remainder smaller than turn_length is still offered."
   },
   "entitled_but_empty": {
    "act": "YIELD",
    "consumes_quota": false,
    "consumes_turn_slot": true,
    "handoff": "Consecutive-yield disengagement is CNL-0089, not this scheduler.",
    "marks_disengaged": false
   },
   "not_four_engines": true,
   "primitive": "Scheduler.next_offer"
  },
  "control_ids": [
   "NC-equalizing-silences-prolific"
  ],
  "family": {
   "counted_n": 4,
   "expected_n": 4,
   "members": [
    "round-robin order",
    "speaking rights",
    "turn length",
    "per-seat speaking quotas"
   ],
   "name": "TURN-TAKING-DIALS"
  },
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
    "measured": 50,
    "method": "live Scheduler.run on quota-starvation fixture",
    "name": "dominant_spoken_tokens"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0047/scheduler.py",
    "measured": 45,
    "method": "independent sum of SPEAK tokens from the offer log",
    "name": "prolific_spoken_tokens"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
    "measured": false,
    "method": "quiet.remaining() == quiet.quota_tokens after YIELD",
    "name": "quiet_yield_consumed_quota"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0047/broken.py",
    "measured": true,
    "method": "prolific_silenced_after_dominant_throttle on EqualizingScheduler",
    "name": "planted_bad_detector_fired"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0047/detect.py",
    "measured": true,
    "method": "same detector on Scheduler",
    "name": "known_good_detector_silent"
   }
  ],
  "question": "Round-robin order, speaking rights, turn length and per-seat speaking quotas are four dials on one scheduler - what is that scheduler's contract, and what happens to a seat that is entitled to speak but has nothing to add?",
  "title": "Turn-taking and speaking-order engine as one shared primitive"
 },
 "residual_unknowns": [
  {
   "claim": "Exact field names in 11-COUNCIL-SPECIFICATION.schema.json for speaking quotas and turn length.",
   "settling_experiment": "Re-open this unit when 11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are present on this worktree and map dial names to those fields.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt. Two same-fingerprint structural refutes park BLOCKED with required_fix named. No ADV rebuild circle."
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Re-sum SPEAK tokens from the offer log (not seat.spoken_tokens) and run remainder-cap-quota-5-vs-turn-length-20, an instance probe1 does not use. {\"attempted\": true, \"id\": \"remainder-cap-quota-5-vs-turn-length-20\", \"instance\": {\"expected_last_speak\": 5, \"expected_total\": 25, \"quota_tokens\": 25, \"turn_length_tokens\": 20}, \"note\": \"REFUTED-NOT-ATTEMPTED is forbidden; this instance was run. A whole-turn throttle when remaining < turn_length would refute the remainder-cap clause of the contract.\", \"partial_speak_sizes\": [20, 5], \"refuted\": false, \"spoken_from_log\": {\"other\": 25, \"partial\": 25}}",
  "reviewed_at": "2026-08-25T00:30:35Z",
  "reviewer_id": "CNL-0047-independent-log-recount",
  "vendor": "xai",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0047",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0047",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
   "id": "probe1-quota-starvation",
   "name": "Dominant throttled; prolific finishes 45; quiet YIELD does not consume quota",
   "output_tail": "quota-starvation log [[\"SPEAK\", \"dominant\", 20], [\"SPEAK\", \"prolific\", 20], [\"YIELD\", \"quiet\", 0], [\"SPEAK\", \"dominant\", 20], [\"SPEAK\", \"prolific\", 20], [\"YIELD\", \"quiet\", 0], [\"SPEAK\", \"dominant\", 10], [\"SPEAK\", \"prolific\", 5], [\"YIELD\", \"quiet\", 0], [\"THROTTLE\", \"dominant\", 0], [\"YIELD\", \"prolific\", 0], [\"YIELD\", \"quiet\", 0]]\nspoken={\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0} independent_recount={\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0} yields={\"dominant\": 0, \"prolific\": 1, \"quiet\": 4, \"observer\": 0} throttles={\"dominant\": 1, \"prolific\": 0, \"quiet\": 0, \"observer\": 0}\nSUCCESS:CNL-0047-probe1 quota-starvation both directions and entitled-empty YIELD",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
   "id": "probe2-both-states",
   "name": "Detector FIRE on planted-bad, SILENT on known-good",
   "output_tail": "both-states known-good {\"fired\": false, \"reason\": \"throttle_at=9 prolific_then=45 remaining_quota=5 remaining_content=0 prolific_after=0 fired=False\", \"spoken\": {\"dominant\": 50, \"prolific\": 45, \"quiet\": 0, \"observer\": 0}}\nboth-states planted-bad {\"fired\": true, \"reason\": \"throttle_at=9 prolific_then=30 remaining_quota=20 remaining_content=15 prolific_after=0 fired=True\", \"spoken\": {\"dominant\": 50, \"prolific\": 30, \"quiet\": 0, \"observer\": 0}}\nnegative-control check=prolific_silenced_after_dominant_throttle reject_state=equalizing-scheduler-silences-prolific-when-dominant-hits-quota on_reject_state=True on_known_good=False\nreviewer {\"counterexample\": {\"attempted\": true, \"id\": \"remainder-cap-quota-5-vs-turn-length-20\", \"instance\": {\"expected_last_speak\": 5, \"expected_total\": 25, \"quota_tokens\": 25, \"turn_length_tokens\": 20}, \"note\": \"REFUTED-NOT-ATTEMPTED is forbidden; this instance was run. A whole-turn throttle when remaining < turn_length would refute the remainder-cap clause of the contract.\", \"partial_speak_sizes\": [20, 5], \"refuted\": false, \"spoken_from_log\": {\"other\": 25, \"partial\": 25}}, \"independent\": true, \"method\": \"Re-sum SPEAK tokens from the offer log (not seat.spoken_tokens) and run a remainder-cap instance the author did not use as probe1.\", \"pass\": true, \"reviewer_id\": \"CNL-0047-independent-log-recount\", \"verdict\": \"PASS\"}\nSUCCESS:CNL-0047-probe2 both-states FIRE on planted-bad SILENT on known-good",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:30:35Z",
  "started_at": "2026-08-25T00:30:35Z"
 },
 "unit_id": "CNL-0047"
}
