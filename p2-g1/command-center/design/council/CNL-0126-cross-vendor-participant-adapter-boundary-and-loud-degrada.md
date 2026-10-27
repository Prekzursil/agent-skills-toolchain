{
 "answer": "Three closed capabilities may be assumed by a CouncilSpec: tool_access, context_length, structured_output. When a seated vendor lacks one of them, pretending interchangeability silently corrupts the council: missing tools fabricate reads; a short window drops earlier dissent; missing structured output lets a coercing parser invent required fields. The adapter boundary is the only comparison of assumed vs advertised. A gap MUST emit a user-visible LOUD_DEGRADATION naming capability_lost, write the partial transcript first, and return DEGRADED never SUCCESS. Measured LPI on the three gap fixtures is 1.0 (threshold 1.0). A silent SUCCESS-after-reseat is detectable (planted fires=True; capable silent=True). The adapter does not choose a paid replacement vendor: that spend question belongs to CNL-0018 and is NOT-CHECKED here. Spec _USER-PROMPTS.md:10983 already binds degrade-loudly; this unit does not invent a substitution default.",
 "answers": {
  "degradation_record": "User-visible LOUD_DEGRADATION naming capability_lost, assumed vs advertised, spec_cite=_USER-PROMPTS.md:10983, partial_artifact.sha256 of the frozen transcript, interchangeability_claimed=false, verdict=DEGRADED.",
  "substitution_rule": "An unrecorded vendor/model reseat is SILENT_SUBSTITUTION. The adapter records it, preserves the partial, returns REFUSED, and never SUCCESS. It does not auto-purchase or auto-reseat a second paid vendor (CNL-0018).",
  "what_breaks": "tool_access: fabricated reads and skipped MCP. context_length: earlier dissent drops out of the window. structured_output: coerced JSON invents required fields. All three look like a successful vote if the adapter pretends vendors are interchangeable."
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0126-cross-vendor-participant-adapter-boundary-and-loud-degrada.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0126/note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0126/taxonomy.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0126/adapter.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0126/fixtures.py",
   "role": "supporting"
  }
 ],
 "both_states": {
  "capability_known_good": "capable",
  "capability_planted_bad": "tool_access",
  "substitution_known_good": "capable",
  "substitution_planted_bad": "buggy_silent_success",
  "verbatim_bad": "PLANTED-BAD silent-swap SUCCESS: fires=True reason=silent-substitution-success swapped=True claimed=True",
  "verbatim_discard": "NEGATIVE-CONTROL mutant_discard: preservation_ok=False; the check FIRES on a DEGRADED result whose partial is missing",
  "verbatim_gap": "PLANTED-BAD gap tool_access: verdict=DEGRADED loud=True preserved=True sha256=22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
  "verbatim_good": "KNOWN-GOOD capable identical-seat: verdict=SUCCESS fires=False loud_degradation=False preserved=True gaps=[]"
 },
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0126/adapter.py:79",
   "claim": "A capability-gap fixture is DEGRADED, LOUD, and preserves the partial bytes.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "both_states.verbatim_bad",
   "claim": "Silent SUCCESS-after-reseat is detectable; a capable identical seat is SILENT.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "measurement.coverage_alone_insufficient",
   "claim": "Coverage of all three gap types without loud events is not a pass (shim LPI=0).",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "live_vendor_probe_readonly",
   "claim": "Live vendor tool/context/structured-output windows were measured via vendor APIs.",
   "id": "C4",
   "verdict": "NOT-CHECKED"
  },
  {
   "anchor": "command-center/OWNER-DECISIONS.md",
   "claim": "OWNER-DECISIONS.md records an explicit CNL-0126 sign-off.",
   "id": "C5",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0126",
 "degradation_record": {
  "kind": "LOUD_DEGRADATION",
  "never": [
   "verdict=SUCCESS on a gap",
   "silent vendor_id swap",
   "discard of the partial"
  ],
  "required_fields": [
   "capability_lost",
   "assumed",
   "advertised",
   "partial_artifact.sha256",
   "interchangeability_claimed=false",
   "spec_cite"
  ],
  "user_visible": true,
  "verdict": "DEGRADED"
 },
 "dependencies": {
  "B01": "bucket token; not re-litigated here",
  "CNL-0018": "output present; sibling forbids silent same-vendor reseat on quota exhaustion. Live dollar/remaining-quota still NOT-CHECKED (CNL-0018's own C5)."
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0126/adapter.py:79",
   "claim": "A tool_access gap is DEGRADED, user-visible LOUD, and byte-preserves the partial work.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0126/fixtures.py:29",
   "claim": "Gap algebra for the three closed capabilities is recomputed from fixture dicts independently of negotiate().",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0126/taxonomy.json:4",
   "claim": "Capability T is closed; observed vendor quirks cannot grow it.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:40673",
   "claim": "Catalog evidence_requirement cites _USER-PROMPTS.md:10983 (do not pretend full interchangeability; degrade loudly).",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:40680",
   "claim": "Catalog question and completion sentinel SUCCESS:CNL-0126 are the question and sentinel this note carries.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs_on_this_tree",
   "claim": "Harness-restore _USER-PROMPTS.md:10983 bytes were read from C:/Users/Prekzursil/.claude/harness-restore-20260806/ on this worktree.",
   "verdict": "REFUTED"
  },
  {
   "anchor": "live_vendor_probe_readonly",
   "claim": "Live vendor tool/context/structured-output windows were measured by calling vendor APIs.",
   "verdict": "NOT-CHECKED"
  },
  {
   "anchor": "command-center/design/council/CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md",
   "claim": "CNL-0018 delivered a measured live remaining-quota / dollar cost used as this unit's second-vendor spend default.",
   "verdict": "NOT-CHECKED"
  },
  {
   "anchor": "command-center/OWNER-DECISIONS.md",
   "claim": "Explicit owner sign-off for CNL-0126 is recorded in command-center/OWNER-DECISIONS.md before this unit closes.",
   "verdict": "REFUTED"
  }
 ],
 "fixture_scores": {
  "capable": {
   "bytes": 145,
   "gaps": [],
   "interchangeability_claimed": false,
   "loud": false,
   "name": "capable",
   "preserved": true,
   "sha256": "22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
   "spec_cite": null,
   "text": null,
   "verdict": "SUCCESS"
  },
  "context_length": {
   "bytes": 145,
   "gaps": [
    "context_length"
   ],
   "interchangeability_claimed": false,
   "loud": true,
   "name": "context_length",
   "preserved": true,
   "sha256": "22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
   "spec_cite": "_USER-PROMPTS.md:10983",
   "text": "LOUD: participant openai:small-window lacks context_length; work artifact preserved sha256=22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f; not interchangeable",
   "verdict": "DEGRADED"
  },
  "honest_silent_swap_attempt": {
   "audit_kinds": [
    "SILENT_SUBSTITUTION_ATTEMPT"
   ],
   "preserved": true,
   "verdict": "REFUSED"
  },
  "structured_output": {
   "bytes": 145,
   "gaps": [
    "structured_output"
   ],
   "interchangeability_claimed": false,
   "loud": true,
   "name": "structured_output",
   "preserved": true,
   "sha256": "22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
   "spec_cite": "_USER-PROMPTS.md:10983",
   "text": "LOUD: participant openai:prose-only lacks structured_output; work artifact preserved sha256=22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f; not interchangeable",
   "verdict": "DEGRADED"
  },
  "tool_access": {
   "bytes": 145,
   "gaps": [
    "tool_access"
   ],
   "interchangeability_claimed": false,
   "loud": true,
   "name": "tool_access",
   "preserved": true,
   "sha256": "22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
   "spec_cite": "_USER-PROMPTS.md:10983",
   "text": "LOUD: participant openai:codex-no-tools lacks tool_access; work artifact preserved sha256=22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f; not interchangeable",
   "verdict": "DEGRADED"
  }
 },
 "live_vendor_probe_readonly": {
  "api_calls": 0,
  "inventory": {
   "ANTHROPIC_API_KEY": "ABSENT",
   "AZURE_OPENAI_API_KEY": "ABSENT",
   "CURSOR_API_KEY": "PRESENT",
   "GOOGLE_API_KEY": "ABSENT",
   "OPENAI_API_KEY": "ABSENT"
  },
  "method": "os.environ.get name presence; values never printed",
  "note": "Presence is not capability. Advertised tool/context/schema windows were not measured against live vendors on this run."
 },
 "measured_lpi": 1.0,
 "measurement": {
  "coverage_alone_insufficient": true,
  "coverage_definition": "|{gap types exercised}| / |T|. Coverage alone is insufficient because a silent shim can touch every type and still claim SUCCESS.",
  "detector": "Capability check FIRES (DEGRADED+LOUD+preserve) on a gap fixture and is SILENT (SUCCESS, no LOUD_DEGRADATION) on a capable identical seat. Silent-substitution check FIRES on SUCCESS-after-unrecorded-reseat and is SILENT on the capable seat.",
  "formula": "LPI=(n_loud/n_gap)*(n_preserved/n_gap)*(0 if any_silent_substitution else 1); n_gap is the number of capability-gap fixture runs; coverage of gap types without a user-visible LOUD_DEGRADATION is not a pass",
  "name": "loud_preservation_index",
  "threshold_reject_below": 1.0
 },
 "min_bytes_threshold": 4096,
 "negative_controls": [
  {
   "id": "NC-DISCARD-PARTIAL",
   "rejects": "a DEGRADED result whose partial artifact was dropped",
   "verbatim": "NEGATIVE-CONTROL mutant_discard: preservation_ok=False; the check FIRES on a DEGRADED result whose partial is missing"
  },
  {
   "id": "NC-SILENT-SWAP-SUCCESS",
   "rejects": "SUCCESS after an unrecorded vendor/model reseat claiming interchangeability",
   "verbatim": "PLANTED-BAD silent-swap SUCCESS: fires=True reason=silent-substitution-success swapped=True claimed=True"
  },
  {
   "id": "NC-CAPABLE-IDENTICAL",
   "rejects": "n/a \u2014 this is the silent-on-good control",
   "verbatim": "KNOWN-GOOD capable identical-seat: verdict=SUCCESS fires=False loud_degradation=False preserved=True gaps=[]"
  }
 ],
 "owner_sign_off": {
  "file": "command-center/OWNER-DECISIONS.md",
  "file_present": true,
  "forged": false,
  "policy_source": "Catalog evidence_requirement cites _USER-PROMPTS.md:10983 (do not pretend full interchangeability; degrade loudly). This unit implements that binding. It does not guess a paid-vendor substitution default (CNL-0018). OWNER-DECISIONS.md exists but contains no CNL-0126 ruling.",
  "present": false,
  "required_by_catalog": true,
  "this_unit_mentioned": false
 },
 "partial_work_bytes": 145,
 "partial_work_sha256": "22e0f9c4f70aa27574fbb1e55b977059957f9e59cba3b8e56db2d636e003715f",
 "question": "What breaks when a participant vendor lacks a capability the CouncilSpec assumes (tool access, context length, structured output) - and what is the degradation record that preserves the work artifact instead of pretending interchangeability?",
 "report": {
  "control_ids": [
   "NC-DISCARD-PARTIAL",
   "NC-SILENT-SWAP-SUCCESS",
   "NC-CAPABLE-IDENTICAL"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0126/adapter.py:79",
    "measured": 1.0,
    "method": "adapter.lpi over three closed gap fixtures",
    "name": "loud_preservation_index"
   }
  ]
 },
 "residual_unknowns": [
  "OWNER-DECISIONS.md is present but has no CNL-0126 ruling (OQ-3 PR-ONLY and REL-0003 only). The degradation policy is the spec 10983 binding already in the catalog row, not a guessed paid-reseat. If the owner later wants auto-reseat to a second paid vendor, that is CNL-0018 plus an owner ruling \u2014 this adapter will still refuse to call that SUCCESS.",
  "Env-name presence is not a capability advertisement. A later CNL-0012-style live reachability probe may fill advertised windows; until then fixtures are synthetic."
 ],
 "reviewer": {
  "independent": true,
  "method": "Recomputes gaps via fixtures.expected_gaps (set algebra on assumed vs advertised dicts) and sha256 of PARTIAL_WORK. Does not call adapter.compute_gaps. Disagreement blocks.",
  "reviewer_id": "CNL-0126-probe2-independent-gap-recount",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0126",
 "shim_lpi_coverage_only": 0.0,
 "source_inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "CNL-0018-output": true,
  "OWNER-DECISIONS.md": true,
  "_USER-PROMPTS.md": false,
  "council/SKILL.md": false,
  "note": "Catalog inputs are Windows harness-restore paths not present here. Capability T is an operational closed set this unit supplies. Quote of 10983 is taken from the catalog evidence_requirement, not from unread prompt bytes."
 },
 "spec_anchor": "_USER-PROMPTS.md:10983",
 "spec_cite": "_USER-PROMPTS.md:10983",
 "state": "SUCCESS",
 "taxonomy": {
  "categories": [
   {
    "description": "Seat can invoke the tools the CouncilSpec names (read, write, grep, MCP). Missing this produces fabricated tool results or skipped work.",
    "id": "tool_access"
   },
   {
    "description": "Advertised token window is at least the CouncilSpec assumed window. A smaller window silently drops earlier votes and dissent.",
    "id": "context_length"
   },
   {
    "description": "Seat can emit schema-valid JSON the CouncilSpec requires. Prose, fences, or coerced defaults are not interchangeability.",
    "id": "structured_output"
   }
  ],
  "closed": true,
  "id": "council.participant-capability.v1",
  "range_rule": "CouncilSpec.assumed_capabilities is a subset of this closed T. A vendor advertisement is also a subset of T. Gaps = assumed minus advertised (context_length gaps when advertised < assumed). Observed vendor quirks cannot grow T. A vendor_id or model_id change is substitution, not a capability fulfillment.",
  "version": 1
 },
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0126/probe1_capability_gap.py",
   "id": "T-CAPABILITY-GAP-LOUD-PRESERVE",
   "name": "a capability-gap fixture must produce a LOUD degradation record and preserve the partial artifact",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0126/probe2_silent_substitution.py",
   "id": "T-SILENT-SUBSTITUTION-DETECTABLE",
   "name": "a silent-substitution attempt must be detectable in the audit record",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0126/probe1_capability_gap.py",
   "id": "T-NEGATIVE-CONTROL",
   "name": "negative control recorded verbatim: discard mutant fails preservation; capable seat is SILENT",
   "result": "PASS"
  }
 ],
 "title": "Cross-vendor participant adapter boundary and loud degradation",
 "unit_id": "CNL-0126",
 "what_breaks": [
  {
   "breakage": "A tool-less seat fabricates file reads, skips MCP, or invents citations while still looking like a grounded vote.",
   "capability": "tool_access",
   "loud_record": "LOUD_DEGRADATION capability_lost=[tool_access]; partial transcript frozen; verdict=DEGRADED."
  },
  {
   "breakage": "Earlier rounds fall out of the window: dissent and constraints disappear and a false consensus is counted.",
   "capability": "context_length",
   "loud_record": "LOUD_DEGRADATION names assumed vs advertised tokens; the prefix is the preserved artifact before any truncated prompt."
  },
  {
   "breakage": "Prose or fenced JSON is coerced into required fields (missing dissent becomes default agree).",
   "capability": "structured_output",
   "loud_record": "LOUD_DEGRADATION keeps RAW bytes as the partial; never SUCCESS with coerced JSON."
  }
 ]
}
