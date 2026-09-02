# OPEN-LOOPS — units the loop cannot close by writing real code (02.09 cloud run)

Fail-closed register (gem-hunt meta F8 / frontier F8): a unit here is still counted as FAIL in every
census; the register exists so the reason is recorded once, with evidence, instead of being
re-diagnosed by each wave. Categories: **CONFLICT** = two probes/contracts contradict each other,
**PROBE-SIDE** = the unit's own probe/emitter is inconsistent with its own schema or CLI,
**ENV** = needs something this VM cannot provide (network, root, a mount), **XDEP** = depends on
another unit's run-time output. An entry closes only when the owner decides (CONFLICT/PROBE-SIDE)
or the environment is provided (ENV). Rows appended by the orchestrator from writer reports.

| unit | category | evidence (writer, file:line) | what would close it |
|---|---|---|---|
| ADV-0004 | PROBE-SIDE | probe-side `synth.py` `PATTERN_EXACT` lacks the live unit_id regex; 11 schemas still fail even with it patched (p00-ADV). Also depended on the RecursionError fix in the jsonschema hook (`$defs` fragment) | probe owner updates `synth.py` |
| ADV-0006 | PROBE-SIDE | `emit_artifact.py` emits 507 evidence items vs `receipt_core.evidence` `maxItems=256` → the emitter fails its own schema (p00-ADV) | owner: raise the schema cap or cap the emitter |
| ADV-0009 | CONFLICT | probe2 wants bare `validate.py` DISARMED; the captured CLI arms `V-FIELDS` by default (a hardening) (p00-ADV) | owner: probe passes `--no-require-complete`, or CLI default changes |
| ADV-0020 | ENV | probe2 sweeps 226 unique Wayback URLs sequentially at 0.4–4.4 s each = 6–18 min vs the 180 s probe cap; rc=124 on every run (p00-ADV) | network-bound probe; owner decision (cap or cache) |
| ADV-0033 | CONFLICT | probe2 asserts IMP-0064's `exec-policy.schema.json` / `test_exec_policy.py` are ABSENT; IMP-0064 requires them present (p00-ADV) | owner adjudicates the two units |
| ADV-0135 | CONFLICT | `probe2_reviewer_and_coc.py:104-118` demands top-level `reviewer.labels_hidden` / `control_executed` / `control_of_the_control.fired`; the unit's own `emit_artifact.py` writes them under `extensions.*` (w2) | owner: probe or emitter |
| RES-0165 | PROBE-SIDE | artifact lacks `measurements.published`; refresh needs `emit_run.py`, blocked by its docstring anchor into a degraded `unique_ideas.py` (w2) | restore `unique_ideas.py` (IMP-0300 deliverable, 14829 B, unrecoverable from the capture) |
| WFA-0160 | XDEP | reads `probes/WFA-0042/_inspect_source_out.json`, written by WFA-0042's probes at run time | persistent mirror: passes once WFA-0042 has run in the same mirror (to verify) |
| TST-0025 | PROBE-SIDE | `fixtures.py` hashes `sys.executable` + absolute probe-dir paths into `input_fingerprint`, so the artifact is bound to the capture path (p42-TST); also needs `tools/router/shadow_catalog.json` (CAPTURE-GAP) | regen at the final census root after the gap is filled, or a probe fix |
| TST-0026 | PROBE-SIDE | probes read top-level `frozen_set.hash`; the unit's own `write_receipts.py` emits only `extensions.frozen_set.hash`, so its seed receipt fails its own probes; live hash drifts with every `schema/*.json` edit (p42-TST) | owner: probe or emitter; regenerate last |
| WFA-0133 | ENV (capture) | probe2 requires `probes/WFA-0133/baselines-closed.marker` mtime <= ledger ts 2026-08-24; every captured file carries the 2026-09-02 03:21 extraction mtime (p42-TST) | mtime-preserving capture, or owner waiver |
| TST-0006 | FINGERPRINT (regen last) | corpus census over live `SUBAGENT-RETURN.json` payloads: `receipt=255 live=232` differs per mirror (p42-TST + orchestrator) | regenerate in the final mirror right before the final census |
| ADV-0103 (emitter) | PROBE-SIDE (informational) | the unit now passes, but its `emit_artifact.py:269-274` writes `downstream_consumers` rows without `executed/read_ok/probe`, which the current `receipt.schema.json#/$defs/downstream_consumer` requires; the emitter can only run without the jsonschema hook (w10). The measurer does not schema-validate, so this is emitter-vs-schema drift, not a gate issue | owner: align emitter or schema |
| ADV-0126 | ROOT-REQUIRED (EVAL R6) | `harness.py:123` `mount -t tmpfs -o size=1M` exit 32 as ubuntu; `SUCCESS:delivered ADV-0126` under `sudo -n` (w1b + orchestrator, sha f686b0b7) | measured in the labelled root pass of the final census |
