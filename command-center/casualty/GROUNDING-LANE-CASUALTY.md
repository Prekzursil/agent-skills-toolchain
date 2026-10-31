---
title: GROUNDING-LANE-CASUALTY
type: note
permalink: dqverify-repo-20261013/command-center/casualty/grounding-lane-casualty
---

# GROUNDING — LANE CASUALTY

STATUS: COMPLETE for the grounding mandate. Every number below was executed, not asserted.
Measured 2026-08-12, local, between 01:05 and 01:40. Lane: grounding (measure + prior art +
ranked plan; NO production code written).
Scope owned: `command-center/casualty/**`. `command-center/adversarial/**` was READ-ONLY INPUT.

## COVERAGE
- [x] C1 recovery executed; both casualties precisely identified (2 independent agreeing signals)
- [x] C2/C3 both authoritative contracts read from the CATALOG (not inferred from filenames)
- [x] C4 harvest file inspected
- [x] C5 prior art found — a completeness gate ALREADY EXISTS (see F7); do not rebuild it
- [x] C6 ADV artifact inventory (40 artifacts, twice, for a delta)
- [x] C7 discriminating detector built AND control-proven (6/6 vs 0/6, bimodal, no mid-band)
- [x] C8 ADV-0002 settled definitively: NEVER DISPATCHED
- [x] C9 external SOTA fetched (checkpoint vs durable execution)
- [x] C10 ranked plan below
- [ ] RESIDUAL: I did not re-run either unit's probes. I verified their OUTPUTS parse and are
      substantive; I did not re-derive their numbers. Settling experiment: re-execute
      `adv0021_probe1.py` / `adv0022_probe2.py` and diff against the saved outputs.

## F1 — `recover_failed_agents.py` OVER-MATCHES: 42/42, zero discrimination
`python command-center/recover_failed_agents.py wf_9cb1a66a-36f ADV-0021 ADV-0022`
→ `run wf_9cb1a66a-36f: 42 transcripts, 42 journal results`, then a section for effectively every
transcript. Its docstring discloses text-matching; measured, the match rate is 100%, so the
detector carries no information. almost-certain (99%).

## F2 — precise identification, two mechanically independent agreeing signals
`command-center/casualty/_probe_identify_units.py`. S1 = a Write/Edit `file_path` containing the
unit id. S2 = the spawn prompt naming the unit as ITS unit. Exactly ONE candidate each:
- ADV-0021 → `agent-ae7e589262e107d7e.jsonl` (124 records, 627,092 B)
- ADV-0022 → `agent-ab0075824d478040c.jsonl` (123 records, 564,827 B)
Journal row keys are `['agentId','key','result','type']` — there is NO label field, so a
label-join is structurally impossible, not merely absent. The HARVEST file does carry `label`
and is the better join source (F8).

## F3 — BOTH units died at the artifact-ASSEMBLY step, after all measurement completed
ADV-0021 final two assistant texts: *"All claims now have controls. Writing the artifact."* →
*"API Error: Connection closed mid-response."*
ADV-0022 final two: *"Let me build the final artifact in Python — reading both probe outputs
verbatim, computing md5 fingerprints…"* → the same API error.
This is the load-bearing finding: the expensive part is DONE. almost-certain (95%).

## F4 — the measurement outputs survive on disk AND ARE USABLE (verified, not assumed)
Scratchpad `…/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/scratchpad/`. I parsed each one rather than
trusting its presence:
| file | bytes | verified content |
|---|---|---|
| adv0021_probe1_out.json | 53,286 | parses; 10 modules, `sink_site_count=100`, `control_site_count=48`, `path_join_count=24`, `unguarded_external_joins` with anchors `cli.py:62`, `lifecycle.py:182` |
| adv0021_results_b.json | 6,114 | parses; **24 cases**, each absence claim paired with an `X.detector-control → PROVEN` |
| adv0021_results.json | 9,018 | parses; run A (3 detectors self-diagnosed broken, superseded by run B) |
| adv0022_probe1_out.txt | 5,037 | escape-harness JSON; `op3_write_outside_root=SUCCEEDED`, `op4_invoke_wider_sibling=SUCCEEDED escaped_declaration=true` |
| adv0022_probe2_out.txt | 3,721 | static audit; `scanner_discriminates=true`, `scanner_control_found_known_present_COUNT=13`, `runtime_consumers_in_hooks_COUNT=0`; **`P2_FINGERPRINT_MD5=93e61cf6dbccabb8a8f46883cb793a45` already computed** |
Re-runnable probe scripts also survive (adv0021_probe1/2/2b.py, adv0022_escape_harness.py,
adv0022_probe2.py) plus workspaces `adv0022_canon_ws`, `adv0022_local_ws`.

## F5 — `recover_failed_agents.py` also UNDER-counts artifacts (second, opposite defect)
It records only `Write`/`Edit`/`NotebookEdit`. The dominant pattern in this wave is
`python build_artifact.py` (a Bash write). Measured: ADV-0021's own skeleton exists on disk
(2,100 B) but is absent from that agent's Write list — it was emitted by an inline `python -c` at
transcript record 37. Therefore its `WROTE NOTHING -- total loss for this agent` line is UNSAFE
as a verdict. almost-certain (95%).

## F6 — ADV-0002 was NEVER DISPATCHED (definitive), and it is not alone
`_probe_dispatch_census.py` reads the literal `YOUR WORK UNIT: <ID>` line from every spawn prompt
across both runs. Detector control: positive (finds the two known-dispatched units) = True;
negative (does not invent `ADV-9999`) = True. 51 transcripts scanned.
- ADV units dispatched: **40**. ADV artifacts on disk: **40**. Dispatched-without-artifact:
  **none**. Artifact-without-dispatch: **none**. A perfect 1:1.
- **ADV-0002: dispatched=False, artifact=False.** Also **ADV-0038: dispatched=False**.
  (The orchestrator flagged only ADV-0002; ADV-0038 is the same class and was not mentioned.)
- ADV-0002 IS in the catalog (`ADV-0002-predicate-crosssite-differential.json`, deps
  `['B07','ADV-0001']`). Its dependency ADV-0001 was itself completed *in this same wave*, so the
  most likely reading is that ADV-0002 became READY only after the dispatch set was frozen —
  likely (65%), UNVERIFIED; settling experiment: read the wave's dispatch-selection code/log and
  check whether it snapshots READY units once at launch.
- Conclusion: ADV-0002's absence is a **dispatch-set** fact, not a casualty. almost-certain (95%).

## F7 — PRIOR ART: the completeness gate ALREADY EXISTS. Do not rebuild it.
`platform/lib/receipt_schema_gate.py` (27,686 B) + `test_receipt_schema_gate.py` (34,494 B), and
`platform/lib/completion_predicate.py` (49,956 B) + `test_completion_predicate.py` (37,184 B).
It is two deliberate layers: JSON-Schema validation, then the **12-condition completion
predicate** from `command-center/COMPLETION-GATES.json`. It has a CLI:
`python platform/lib/receipt_schema_gate.py <receipt…> --repo-root . [--json] [--schema-only]`.
There is also a `command-center/schema/completion-census.schema.json` for the census output shape.

**But its BINARY verdict FAILS the both-states control** — measured:
| file | binary marker | unsatisfied conditions |
|---|---|---|
| ADV-0024 (88,395 B, known-COMPLETE) | `FAILED` | c1,c3,c5,c9,c10,c11 |
| ADV-0021 (2,100 B, known-SKELETON) | `FAILED` | c1,c3,c5,c6,c7,c8,c9,c11,c12 |
Both print FAILED, so the binary flag is **saturated** and carries no information — the exact
shape of the UNKNOWN-sentinel failure. The reason is a family-wide convention: completed
adversarial units deliberately ship `state=BLOCKED` + a `FAILED:` sentinel (ADV-0028's own agent
wrote *"Receipt state=BLOCKED (matching the sibling convention for completed adversarial
units)"*), which permanently pins c1 and c5. c9/c11 are reviewer/manifest, not the builder's job.
**The information lives in the per-condition vector, specifically the substance conditions
c6/c7/c8/c12** — use those, not the marker.

## F8 — the census detector, and its control
`command-center/casualty/_probe_census.py` scores 6 structural substance axes (evidence items
carrying REAL probe `raw_output`; non-empty `tests[]`; non-empty `negative_controls[]`; ≥2
non-placeholder observations; ≥2 distinct real probe fingerprints; bytes ≥ the artifact's OWN
declared `min_bytes_threshold`). It refuses to print a citable number unless its control passes.

**CONTROL: complete(ADV-0024)=6/6 vs skeleton(ADV-0021)=0/6 → SEPARATES.**
Distribution over 40 artifacts: `{0: 9, 1: 2, 5: 4, 6: 25}` — **bimodal with an empty 2–4 band**,
which is a much stronger separation than the size split alone.
Note the size heuristic would have been *nearly* right here but is not the same instrument:
`ADV-0034` is 33,222 B yet scores 5, and `ADV-0041` is 5,155 B and scores 1.

## F9 — the LIVE-WAVE caveat is REAL, and I caught it happening three times
The orchestrator's warning ("I nearly called 8 live agents dead") reproduced inside my own
~30-minute measurement window:
| unit | first sample | later sample |
|---|---|---|
| ADV-0033 | 2,535 B (would have scored 0) | 83,141 B, score 6 |
| ADV-0026 | 2,431 B, score 0 | 80,248 B, score 6 |
| ADV-0041 | did not exist | 5,155 B, score 1 |
Census totals moved `{0:10,1:2,5:4,6:24}` → `{0:9,1:2,5:4,6:25}` between two runs minutes apart.
**A low score is NOT a casualty verdict.**

## F10 — the AND-gate that actually separates casualty from mid-flight
`command-center/casualty/_probe_liveness.py`. CASUALTY requires all three: G1 score<2, G2 artifact
not written in 900 s, **G3 the dispatching agent's TRANSCRIPT also stale by 900 s** (a different
file written by a different mechanism, so G2⊥G3). Result at 2026-08-12T01:35:32:

**`{'SUBSTANTIVE': 29, 'CASUALTY': 2, 'MID-FLIGHT': 9}`**

The separation is not marginal: the 2 casualties have agent-transcript age **9,293 s / 9,294 s**,
while all 9 low-scoring live units have agent age **0–102 s**. The only two CASUALTY rows are
ADV-0021 and ADV-0022 — the gate independently rediscovers exactly the two known deaths and
clears the other nine. almost-certain (95%).

## F11 — external SOTA (fetched 2026-08-12, not recalled)
Diagrid, *"Checkpoints Are Not Durable Execution"*: *"There is no supervisor, no watchdog, no
heartbeat mechanism. Your workflow is simply dead until something external notices."* and
checkpointing *"says: I saved your state. You take it from here"* whereas durable execution
guarantees run-to-completion. Failure modes named: no automatic detection, manual recovery
(locate the checkpoint, resume by hand), duplicate-execution risk on concurrent resume, and loss
of in-flight progress unless each tool call is modelled as its own persisted step.
This maps exactly onto tonight: the write-as-you-go artifact is the CHECKPOINT, the transcript is
the EVENT JOURNAL, and recovery was manual because nothing watches. Sources:
- https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
- https://vadim.blog/durable-execution-llm-agents/
- https://zylos.ai/research/2026-04-24-durable-execution-agent-runtimes/

## ARTIFACTS I PRODUCED (all under command-center/casualty/)
| path | what |
|---|---|
| `GROUNDING-LANE-CASUALTY.md` | this file |
| `ADV-COMPLETENESS-CENSUS.json` | 40 rows, per-axis, control result, live-wave caveat embedded |
| `ADV-DISPATCH-CENSUS.json` | dispatched-vs-on-disk cross-tab; settles ADV-0002 |
| `ADV-LIVENESS.json` | the 3-gate casualty/mid-flight/substantive verdicts |
| `ADV-UNIT-INDEX.json` | all 144 ADV-* catalog units with output_path + existence |
| `recovered/ADV-0021-spec.json`, `ADV-0022-spec.json` | authoritative contracts |
| `recovered/ADV-002{1,2}-worklog.md`, `-spawn-prompt.txt`, `-scratch-index.json` | recovery dossiers |
| `_probe_identify_units.py`, `_probe_extract_dossier.py`, `_probe_catalog_adv.py`, `_probe_census.py`, `_probe_dispatch_census.py`, `_probe_liveness.py` | the probes, all re-runnable |

## RANKED PLAN FOR THE BUILD LANE
Ordered by value-per-minute. Steps 1–2 are the whole point; step 0 prevents the biggest waste.

**0. DO NOT RE-MEASURE, AND DO NOT BUILD A NEW COMPLETENESS GATE.** (F4, F7)
   Both casualties' probes are complete, parseable and fingerprinted on disk; a completion gate
   with 34 KB of tests already exists. Re-running either is pure loss.

**1. ADV-0021 — assemble only.** Inputs: `adv0021_probe1_out.json` (Probe 1: 100 sinks / 48
   controls / 24 joins / unguarded joins with anchors) + `adv0021_results_b.json` (Probe 2: 24
   cases, each absence paired with a PROVEN control). Remaining real work: (a) project the Probe-1
   boundaries into the STRIDE cell matrix the spec demands; (b) satisfy `tests_required` — every
   unmitigated cell becomes a **named follow-up unit or an explicitly accepted residual risk with
   an owner-visible impact statement** (a bare unmitigated cell is a unit failure); (c) emit
   against `command-center/schema/threat-model.schema.json`. Prefer run B over run A and say so —
   run A self-diagnosed three broken detectors.

**2. ADV-0022 — assemble, and scope the sandbox claim honestly.** Inputs:
   `adv0022_probe1_out.txt` (4/4 escape, wide-control unimpeded) + `adv0022_probe2_out.txt`
   (`scanner_discriminates=true`, 13 known-present found vs 0 in `hooks/`) with its md5 already
   computed. Two disclosures that MUST be inline, not trailing:
   (i) `tests_required` says *"all attempts run inside a disposable sandbox"*; Modal returned
   `Token missing`, so the run used a local disposable `%TEMP%` workspace. State the substrate
   actually used and mark the Modal leg NOT-CHECKED with the settling experiment. Do NOT create
   credentials (AGENTS.md §9).
   (ii) `reviewer_requirement` demands **two different-vendor** reviewers independently
   reproducing; that is unmet → NOT-CHECKED, never self-certified.
   Also carry forward the agent's own mid-run correction: `security-first.md` **is** tracked — do
   not repeat the retracted "untracked architecture" claim.

**3. Validate both with the EXISTING gate, and read the vector not the marker.**
   `python platform/lib/receipt_schema_gate.py command-center/adversarial/ADV-002{1,2}-*.json
   --repo-root . --json`. Target: c6/c7/c8/c12 all SATISFIED. Expect c1/c5 to stay UNSATISFIED
   (family convention) and c9/c11 to stay UNSATISFIED (reviewer/manifest, not the builder's).
   Do not report the binary `FAILED:` marker as a failure — it is saturated (F7).

**4. Ship the census with its control, its timestamp and its caveat.** Re-run
   `_probe_census.py` + `_probe_liveness.py` immediately before publishing and quote the fresh
   tally, because the directory moved three times during this lane (F9). Publish the AND-gate
   verdicts, not the raw score: `{'SUBSTANTIVE': 29, 'CASUALTY': 2, 'MID-FLIGHT': 9}` at
   2026-08-12T01:35:32.

**5. Account for ADV-0002 (and ADV-0038) as NEVER-DISPATCHED, not missing.** (F6) Recommend to the
   owner: re-evaluate READY after each wave rather than snapshotting once at launch.

**6. (Scope expansion, justified) Fix the recovery tool's two measured defects.** It over-matches
   42/42 (F1) and under-counts Bash-written artifacts (F5) — the two failure directions of the one
   tool this whole lane depends on. Cheap fix: join on the harvest file's `label` field, and count
   artifacts by the unit's declared `output_path` existing on disk rather than by Write-tool calls.
   The file is outside my lane scope, so I did not edit it.