# memory-bench — basic-memory recall regression suite

Deep-research item **#5** (modus-operandi scan, 2026-06-15). Converts "memory
feels useful" into a single measured pass-rate by probing whether **basic-memory
actually recalls correctly** across sessions. Based on LongMemEval
(arXiv:2410.10813) + LoCoMo-style probes.

## What it measures

Five recall ability-classes, scored with a deterministic substring/abstention
scorer (NO LLM-as-judge — that would be a same-context placebo):

| Class | What it tests |
|---|---|
| information-extraction | recall a fact stated in an earlier note |
| multi-session-temporal | fact spans multiple notes / dates |
| knowledge-update | a later note overrides an earlier one → recall the CURRENT value |
| abstention | asked about something never stored → correct answer is "not found" |
| contradiction | conflicting notes → resolve correctly |

## Baseline (first run, 2026-06-15) — `results.json`

**Overall: 13/16 = 81.25%.** Per-class: abstention 3/3, knowledge-update 3/3,
information-extraction 4/5, multi-session-temporal 2/3, **contradiction 1/2**.
The weak spots (contradiction, temporal) are the expected hard cases for flat
top-k semantic recall — this is the number to beat after any future memory change.

## Run it

```bash
python tools/memory-bench/memory_bench.py
```

Uses a **scratch** basic-memory project under a temp `BASIC_MEMORY_HOME` — it
**never touches the real `D:\basic-memory` vault**. Requires the `basic-memory`
CLI on PATH. Emits the overall + per-class pass-rate and writes `results.json`.

## Extend with the full datasets

The bundled `probes.jsonl` (16 probes) is a smoke-grade proxy. For a rigorous
run, download **LongMemEval-S** + a **LoCoMo** slice and convert each into the
same `{id, class, setup_notes[], question, expected_substrings[], should_abstain}`
schema, append to `probes.jsonl`, and re-run. Wire as a weekly CronCreate/Ralph
step so any memory-layer change is graded as a measured A/B, not a faith adoption.
