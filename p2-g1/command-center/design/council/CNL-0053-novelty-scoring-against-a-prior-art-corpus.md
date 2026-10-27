{
 "artifacts": [
  {
   "bytes": 6117,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0053/novelty.py",
   "role": "supporting",
   "sha256": "0716984980ff6ea7ac3180817ca1dc9ef54e2e586f39bf988d43e5235abc21ba"
  },
  {
   "bytes": 3023,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py",
   "role": "supporting",
   "sha256": "20a416c6d35d3fcc59b49598001f09d08bc14c5784261c21cf2a96ebc51088e5"
  },
  {
   "bytes": 7467,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0053/probe2_both_states.py",
   "role": "supporting",
   "sha256": "145a73ca4a48a88b3b50133571f6e40c4eab533c99fb9e5aee1b459401309a0d"
  },
  {
   "bytes": 1662,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json",
   "role": "fixture",
   "sha256": "019afdbe1ddbc8dd61b4d0282bf6c2b8d29411f6bab0b09f3fe7f267e997c446"
  },
  {
   "bytes": 2182,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json",
   "role": "fixture",
   "sha256": "a45c8dd0c6a40a95842227b4b59ef2ca51809abc2e0dbc4c7d7b3f9e93dda181"
  }
 ],
 "defects": [],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json",
   "consumer": "python3 json.loads of the pinned prior-art corpus fixture",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "python3 -c \"import json; from pathlib import Path; p=Path('command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json'); d=json.loads(p.read_text(encoding='utf-8')); print(d['corpus_id'], len(d['items']))\"",
    "exit_code": 0,
    "fingerprint": "consumer:json-loads-corpus",
    "method": "command",
    "raw_output": "CNL-0053-prior-art-v1 5",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json:3",
   "claim": "Known-good checksum restatement already in the corpus scores novelty=0.0 quality=1.0 (low-N/high-Q); known-bad in-corpus scores novelty=0.0 quality=0.0.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py",
     "exit_code": 0,
     "fingerprint": "probe1:separable-axes",
     "method": "command",
     "raw_output": "{\"corpus_id\": \"CNL-0053-prior-art-v1\", \"corpus_pin_sha256\": \"019afdbe1ddbc8dd61b4d0282bf6c2b8d29411f6bab0b09f3fe7f267e997c446\", \"scores\": {\"known_bad_in_corpus\": {\"band\": \"low-N/low-Q\", \"check\": \"SILENT\", \"match_id\": \"PA-003\", \"match_kind\": \"mechanism-id\", \"novelty\": 0.0, \"quality\": 0.0}, \"known_good\": {\"band\": \"low-N/high-Q\", \"check\": \"SILENT\", \"match_id\": \"PA-001\", \"match_kind\": \"mechanism-id\", \"novelty\": 0.0, \"quality\": 1.0}, \"novel_good\": {\"band\": \"high-N/high-Q\", \"check\": \"SILENT\", \"match_id\": null, \"match_kind\": \"surface-jaccard\", \"novelty\": 1.0, \"quality\": 1.0}, \"planted_bad\": {\"band\": \"high-N/low-Q\", \"check\": \"FIRE\", \"match_id\": null, \"match_kind\": \"surface-jaccard\", \"novelty\": 1.0, \"quality\": 0.0}}, \"separable\": true}\nknown_good low-N high-Q N=0.0 Q=1.0 known_bad N=0.0 Q=0.0 junk N=1.0 Q=0.0 novel_good N=1.0 Q=1.0\nSUCCESS:CNL-0053-probe1 separable-axes",
     "role": "source"
    },
    {
     "command": "command-center/p2-wave/probes/CNL-0053/novelty.py:120",
     "exit_code": 0,
     "fingerprint": "file-read:quality_score-body",
     "method": "file-read",
     "raw_output": "def quality_score(idea: dict) -> float:\n    \"\"\"Independent of corpus membership and of novelty.\"\"\"\n    if idea.get(\"contradicts_known\") is True:\n        return 0.0\n    score = 0.0\n    mech = str(idea.get(\"mechanism\") or \"\")\n    if MECH_RE.fullmatch(mech):\n        score += 0.30\n    if str(idea.get(\"falsifier\") or \"\").strip():\n        score += 0.35\n    if str(idea.get(\"evidence_kind\") or \"\") in {\n        \"experiment\",\n        \"measurement\",\n        \"named-failure-class\",\n    }:\n        score += 0.25\n    if idea.get(\"contradicts_known\") is False:\n        score += 0.10\n    return min(1.0, score)",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0053/novelty.py:189",
   "claim": "junk_novelty_check FIRES on planted-bad high-N/low-Q junk and is SILENT on the known-good restatement; reviewer char-3gram is a second measurement and does not collapse C-CHECKSUM-CACHE-KEY into PA-001.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe2_both_states.py",
     "exit_code": 0,
     "fingerprint": "probe2:both-states-reviewer",
     "method": "command",
     "raw_output": "{\"both_states\": {\"known_good_check\": \"SILENT\", \"known_good_novelty\": 0.0, \"known_good_quality\": 1.0, \"planted_bad_check\": \"FIRE\", \"planted_bad_novelty\": 1.0, \"planted_bad_quality\": 0.0}, \"negative_control\": {\"check_on_known_good\": \"SILENT\", \"check_on_that_state\": \"FIRE\", \"state_meant_to_reject\": \"planted_bad high-novelty low-quality junk that a novelty-only gate would accept\"}}\nBOTH-STATES known_good=SILENT planted_bad=FIRE good(N=0.0,Q=1.0) bad(N=1.0,Q=0.0)\nNEGATIVE-CONTROL verbatim: on the planted-bad high-novelty low-quality fixture the check returns FIRE; on the known-good in-corpus restatement it returns SILENT.\n{\"reviewer\": {\"author_related_but_distinct\": {\"match_id\": \"PA-001\", \"match_kind\": \"surface-jaccard\", \"novelty\": 0.9, \"quality\": 1.0}, \"author_unlabeled_paraphrase\": {\"match_id\": \"PA-001\", \"novelty\": 0.0, \"surface_jaccard\": 1.0}, \"known_good\": {\"match_id\": \"PA-001\", \"match_text\": \"Use a checksum to detect data corruption\", \"method\": \"char-3gram-jaccard\", \"novelty\": 0.272727, \"trigram_jaccard\": 0.727273}, \"method\": \"char-3gram-jaccard\", \"paraphrase_unlabeled\": {\"match_id\": \"PA-001\", \"match_text\": \"Use a checksum to detect data corruption\", \"method\": \"char-3gram-jaccard\", \"novelty\": 0.272727, \"trigram_jaccard\": 0.727273}, \"planted_bad\": {\"match_id\": \"PA-005\", \"match_text\": \"Lexical Jaccard on idea wording is the unique-idea counter\", \"method\": \"char-3gram-jaccard\", \"novelty\": 0.968421, \"trigram_jaccard\": 0.031579}, \"related_but_distinct\": {\"match_id\": \"PA-001\", \"match_text\": \"Use a checksum to detect data corruption\", \"method\": \"char-3gram-jaccard\", \"novelty\": 0.837838, \"trigram_jaccard\": 0.162162}}}\nREVIEWER counterexample instance C-CHECKSUM-CACHE-KEY: shares the word checksum with PA-001 but is a different mechanism; author N=0.9 match_kind=surface-jaccard reviewer_3gram N=0.837838 match=PA-001. Paraphrase without mechanism id remains low-N on both author Jaccard (N=0.0) and reviewer 3-gram (N=0.272727). No refutation of separable axes. Verdict PASS.\nSUCCESS:CNL-0053-probe2 both-states reviewer-counterexample",
     "role": "source"
    },
    {
     "command": "command-center/p2-wave/probes/CNL-0053/novelty.py:189",
     "exit_code": 0,
     "fingerprint": "file-read:junk_novelty_check-body",
     "method": "file-read",
     "raw_output": "def junk_novelty_check(scored: dict) -> str:\n    \"\"\"FIRES on high-novelty low-quality junk. SILENT otherwise.\n\n    This is the check the both-states control exercises. It rejects using\n    novelty as a quality proxy: a novelty-only gate would ACCEPT this junk.\n    \"\"\"\n    nov = float(scored[\"novelty\"])\n    qual = float(scored[\"quality\"])\n    if nov >= FIRE_NOVELTY_MIN and qual < FIRE_QUALITY_MAX:\n        return \"FIRE\"\n    return \"SILENT\"",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "completion_sentinel": "SUCCESS:CNL-0053",
  "negative_control_verbatim": "on the planted-bad high-novelty low-quality fixture the check returns FIRE; on the known-good in-corpus restatement it returns SILENT.",
  "output_schema": "command-center/schema/council-design-note.schema.json"
 },
 "manifest_registration": {
  "entry_id": "CNL-0053",
  "manifest_path": "command-center/p2-wave/probes/CNL-0053/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 4000,
 "negative_controls": [
  {
   "bad_state_output": "planted_bad check=FIRE N=1.0 Q=0.0",
   "description": "junk_novelty_check must FIRE when novelty>=0.55 and quality<0.40 (planted-bad quota-padding). A novelty-only gate would accept that state. The same check must stay SILENT on the known-good restatement.",
   "fired_on_bad_state": true,
   "good_state_output": "known_good check=SILENT N=0.0 Q=1.0",
   "id": "CNL0053-NC1",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "xai"
 },
 "profile": "council-design-note",
 "report": {
  "answer": "Novelty is relative to a named, versioned, inspectable prior-art corpus pin, not to 'truth', not to model pretraining, and not to the current-run unique-idea ledger. On this worktree the executable corpus is command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json (corpus_id=CNL-0053-prior-art-v1, pin_sha256=019afdbe1ddbc8dd61b4d0282bf6c2b8d29411f6bab0b09f3fe7f267e997c446). An idea's novelty is 0 when its mechanism id already appears in the corpus, else 1 minus max synonym-folded token Jaccard against corpus surfaces. Quality is a disjoint function of falsifier, evidence_kind, and contradicts_known and is never 1-novelty. A correct idea already in the corpus therefore scores low novelty and high quality, fills a quality quota, and does not fill a novelty quota. A novelty-only gate that would accept high-novelty junk is the planted-bad state: junk_novelty_check FIRES. The check is SILENT on the known-good restatement.",
  "catalog_id_line": "command-center/WORK-UNIT-CATALOG.json:36926",
  "catalog_tests_required": [
   {
    "result": "PASS",
    "text": "a known-good idea already present in the corpus must score low on novelty and high on quality, proving the two axes are separable"
   },
   {
    "result": "PASS",
    "text": "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim"
   },
   {
    "result": "PASS",
    "text": "negative control recorded verbatim: state what the check does on the state it is meant to reject"
   }
  ],
  "control_ids": [
   "CNL0053-NC1"
  ],
  "kind": "council-design-note",
  "live_scores": {
   "known_bad_in_corpus": {
    "band": "low-N/low-Q",
    "check": "SILENT",
    "match_id": "PA-003",
    "match_kind": "mechanism-id",
    "novelty": 0.0,
    "quality": 0.0,
    "surface_jaccard": 1.0
   },
   "known_good": {
    "band": "low-N/high-Q",
    "check": "SILENT",
    "match_id": "PA-001",
    "match_kind": "mechanism-id",
    "novelty": 0.0,
    "quality": 1.0,
    "surface_jaccard": 1.0
   },
   "novel_good": {
    "band": "high-N/high-Q",
    "check": "SILENT",
    "match_id": null,
    "match_kind": "surface-jaccard",
    "novelty": 1.0,
    "quality": 1.0,
    "surface_jaccard": 0.0
   },
   "paraphrase_unlabeled": {
    "band": "low-N/high-Q",
    "check": "SILENT",
    "match_id": "PA-001",
    "match_kind": "surface-jaccard",
    "novelty": 0.0,
    "quality": 0.7,
    "surface_jaccard": 1.0
   },
   "planted_bad": {
    "band": "high-N/low-Q",
    "check": "FIRE",
    "match_id": null,
    "match_kind": "surface-jaccard",
    "novelty": 1.0,
    "quality": 0.0,
    "surface_jaccard": 0.0
   },
   "reviewer_related_but_distinct": {
    "band": "high-N/high-Q",
    "check": "SILENT",
    "match_id": "PA-001",
    "match_kind": "surface-jaccard",
    "novelty": 0.9,
    "quality": 1.0,
    "surface_jaccard": 0.1
   }
  },
  "named_probes": [
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py",
    "id": "probe1",
    "role": "separable-axes"
   },
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe2_both_states.py",
    "id": "probe2",
    "role": "both-states-reviewer"
   }
  ],
  "notes": "Catalog output_path ends in .md; G-1 _measure_one_delivered.py json.loads the file, so the payload is the design-note JSON. Did not run unit_manifest.py --write. No ADV rebuild circle. Schema validation uses platform/lib/schema_resolver.py against council-design-note (disk-only).",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json:3",
    "measured": 0.0,
    "method": "mechanism-id collapse against pinned corpus",
    "name": "known_good_novelty"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0053/novelty.py:120",
    "measured": 1.0,
    "method": "quality_score(falsifier, evidence_kind, contradicts_known)",
    "name": "known_good_quality"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json:21",
    "measured": "FIRE",
    "method": "junk_novelty_check both-states",
    "name": "planted_bad_check"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json:6",
    "measured": true,
    "method": "2x2 fixture matrix including known-bad in-corpus",
    "name": "axes_separable"
   }
  ],
  "phase": "2C",
  "prior_art_corpus": {
   "corpus_id": "CNL-0053-prior-art-v1",
   "honest_scope": "G-1 for this unit scores against the pinned fixture corpus. It does not claim a live recount of a protocol/preset catalog, which is absent here. Waiting on CNL-0051 before closing novelty-vs-corpus would deadlock G-1. Session uniqueness and corpus novelty are different axes.",
   "intended_production_union": [
    "C_library: already-admitted idea / mechanism cards on disk",
    "C_protocol: protocol and preset mechanism names when those catalogs exist",
    "C_session_prior: ideas accepted in earlier rounds of the same run"
   ],
   "items": [
    {
     "id": "PA-001",
     "mechanism": "checksum_detect_corruption",
     "role": "known-good-prior-art"
    },
    {
     "id": "PA-002",
     "mechanism": "both_states_fire_and_silent",
     "role": "known-good-prior-art"
    },
    {
     "id": "PA-003",
     "mechanism": "skip_all_validation_to_save_tokens",
     "role": "known-bad-prior-art"
    },
    {
     "id": "PA-004",
     "mechanism": "two_mechanically_different_signals",
     "role": "known-good-prior-art"
    },
    {
     "id": "PA-005",
     "mechanism": "lexical_jaccard_unique_idea_counter",
     "role": "known-limited-prior-art"
    }
   ],
   "libraries_on_this_tree": {
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "CNL-0051 artifact": false
   },
   "membership_rule": "An idea is already-known iff (a) its mechanism id equals a corpus row's mechanism, or (b) unlabeled surface Jaccard after stopword strip and synonym fold is >= 0.55 against some corpus row.",
   "name": "the named pin, not the world",
   "not_the_corpus": [
    "Model pretraining data (uninspectable, unpinnable, not a fixture)",
    "The set of all true or correct statements",
    "The current council run's unique-idea ledger (CNL-0051 session-internal dedup)",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json on this tree (file absent; not silently substituted)"
   ],
   "path": "command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json",
   "pin_sha256": "019afdbe1ddbc8dd61b4d0282bf6c2b8d29411f6bab0b09f3fe7f267e997c446"
  },
  "question": "Novel relative to WHAT - what prior-art corpus does a novelty score compare against, and how does the score avoid punishing a correct idea merely because it was already known?",
  "scoring": {
   "anti_punishment_rule": "Stopping rules keep separate counters. quality_count increments when quality >= HIGH_QUALITY_MIN, regardless of novelty. novelty_count increments when novelty >= HIGH_NOVELTY_MIN. A known-correct corpus restatement may satisfy a quality target and must not be rejected for low novelty. Novelty must not gate quality.",
   "novelty": "novelty = 0 if mechanism_id in corpus else (1 - max_surface_jaccard). Surface tokens are [a-z0-9]+, stopword-stripped, synonym-folded (hash/digest->checksum, corrupt*->corruption).",
   "quality": "quality = 0 if contradicts_known is true; else 0.30 for a stable mechanism id + 0.35 for a non-empty falsifier + 0.25 for evidence_kind in {experiment, measurement, named-failure-class} + 0.10 if contradicts_known is explicitly false. Quality does not read novelty or corpus membership.",
   "thresholds": {
    "FIRE_NOVELTY_MIN": 0.55,
    "FIRE_QUALITY_MAX": 0.4,
    "HIGH_NOVELTY_MIN": 0.55,
    "HIGH_QUALITY_MIN": 0.7,
    "LOW_NOVELTY_MAX": 0.45,
    "LOW_QUALITY_MAX": 0.4
   }
  },
  "separable_axes": {
   "known_bad_in_corpus": {
    "idea_id": "C-KNOWN-BAD",
    "novelty": 0.0,
    "observed": "low-N/low-Q",
    "quality": 0.0,
    "required": "low novelty AND low quality (proves quality is not 1-novelty)"
   },
   "known_good_in_corpus": {
    "idea_id": "C-KNOWN-GOOD",
    "novelty": 0.0,
    "observed": "low-N/high-Q",
    "quality": 1.0,
    "required": "low novelty AND high quality"
   },
   "novel_good": {
    "idea_id": "C-NOVEL-GOOD",
    "novelty": 1.0,
    "observed": "high-N/high-Q",
    "quality": 1.0,
    "required": "high novelty AND high quality"
   },
   "planted_bad_junk": {
    "idea_id": "C-JUNK-NOVELTY",
    "novelty": 1.0,
    "observed": "high-N/low-Q",
    "quality": 0.0,
    "required": "high novelty AND low quality"
   }
  },
  "title": "Novelty scoring against a prior-art corpus"
 },
 "residual_unknowns": [
  {
   "claim": "G-1 scores novelty against the pinned fixture corpus CNL-0053-prior-art-v1, not against a live 58-protocol / 72-preset catalog. Those source files are absent on this worktree.",
   "settling_experiment": "When 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is present, pin it as C_protocol, re-run the 2x2 fixtures against the union, and record whether any known-good restatement flips band.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "CNL-0051 unique-idea counter artifact is a catalog dependency and is absent on this worktree. Session uniqueness and corpus novelty are different axes.",
   "settling_experiment": "Deliver CNL-0051, then confirm a session-internal duplicate still scores high corpus-novelty if it is not in the prior-art pin.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)."
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Character 3-gram Jaccard on compact text. Does not read mechanism-id and does not reuse author word-Jaccard. Counterexample instance C-CHECKSUM-CACHE-KEY: shares the token 'checksum' with PA-001 but uses it as a cache key. Author novelty=0.9 match_kind=surface-jaccard match_id=PA-001. Unlabeled paraphrase novelty=0.0 via surface Jaccard. Axes not refuted. Catalog required a counterexample instance or REFUTED-NOT-ATTEMPTED; this is the instance.",
  "reviewed_at": "2026-08-25T00:56:36Z",
  "reviewer_id": "CNL-0053-probe2-char-3gram-reviewer",
  "vendor": "unassigned",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0053",
 "spec_anchor": "_USER-PROMPTS.md:10746-10767",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py",
   "id": "T1-separable-axes",
   "name": "Known-good in-corpus idea scores low novelty and high quality; 2x2 disproves quality=1-novelty",
   "output_tail": "known_good low-N high-Q N=0.0 Q=1.0 known_bad N=0.0 Q=0.0 junk N=1.0 Q=0.0 novel_good N=1.0 Q=1.0\nSUCCESS:CNL-0053-probe1 separable-axes",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0053/probe2_both_states.py",
   "id": "T2-both-states-and-reviewer",
   "name": "junk_novelty_check FIRES on planted-bad and is SILENT on known-good; reviewer 3-gram counterexample",
   "output_tail": "BOTH-STATES known_good=SILENT planted_bad=FIRE good(N=0.0,Q=1.0) bad(N=1.0,Q=0.0)\nNEGATIVE-CONTROL verbatim: on the planted-bad high-novelty low-quality fixture the check returns FIRE; on the known-good in-corpus restatement it returns SILENT.\nREVIEWER counterexample instance C-CHECKSUM-CACHE-KEY: shares the word checksum with PA-001 but is a different mechanism; author N=0.9 match_kind=surface-jaccard reviewer_3gram N=0.837838 match=PA-001. Paraphrase without mechanism id remains low-N on both author Jaccard (N=0.0) and reviewer 3-gram (N=0.272727). No refutation of separable axes. Verdict PASS.\nSUCCESS:CNL-0053-probe2 both-states reviewer-counterexample",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "duration_seconds": 0.127325,
  "ended_at": "2026-08-25T00:56:36Z",
  "started_at": "2026-08-25T00:56:36Z"
 },
 "unit_id": "CNL-0053"
}
