---
title: receipt-gate
type: note
permalink: dqverify-repo-20261013/skills/workflow-foundry/references/receipt-gate
---

# The fan-in receipt gate — schema, precedence, prior art, and what it does NOT prove

Companion to `../scripts/receipt_gate.py` (workflow-foundry L2/L3/L6).

## Manifest

```json
{
  "defaults": {
    "min_bytes": 1024,
    "trailer_template": "UNIT-COMPLETE: {id}",
    "tail_bytes": 4096
  },
  "units": [
    {"id": "F01", "path": "C:/.../artifacts/consistency/F01-lifetime-consistency.md"},
    {"id": "E02", "path": "C:/.../artifacts/control-plane/E02-generation-pin.md", "min_bytes": 4096},
    {"id": "auth-src-map", "path": "C:/.../artifacts/auth-infra/auth-source-map.md",
     "trailer": "UNIT-COMPLETE: auth-src-map",
     "digest": "<the text the agent returned, optional>"}
  ]
}
```

**Always write `id` explicitly. Never derive it from the filename.** MEASURED 2026-08-08
over the 55 real artifacts in `~/scratch/codex-auth-research-fanout/artifacts/`:
**1 of 55** has a filename stem that differs from its trailer id
(`auth-infra/auth-source-map.md` carries `UNIT-COMPLETE: auth-src-map`). A caller that
keys the trailer on the stem reports that unit NOT-DONE forever — a false negative that
looks exactly like a dead agent. The `trailer` field exists to pin this.

## Verdict precedence

A single unit can match several broken shapes. Highest first:

```
NOT-CHECKED > BACKGROUND-RECEIPT > MISSING > UNDERSIZE > NO-TRAILER > DELIVERED
```

`NOT-CHECKED` outranks everything because "I could not tell" must never be silently
resolved in either direction. An empty manifest returns `NOT-CHECKED` overall, not
`CLEAN` — zero inputs measure nothing.

## Overall verdict

| overall | when |
|---|---|
| `CLEAN` | every unit `DELIVERED` |
| `FINDING` | at least one `MISSING`/`UNDERSIZE`/`NO-TRAILER`/`BACKGROUND-RECEIPT` |
| `NOT-CHECKED` | no findings but at least one unit unjudgeable, or an empty manifest |
| `DEGRADED` | the manifest itself could not be read |

Exit 0 always, unless `--strict` (then 1 on anything but `CLEAN`). The gate surfaces; it
does not block.

## What `DELIVERED` does NOT mean

`DELIVERED` is **rung 3 of 5** on the L3 ladder — exists, clears the byte floor, carries
its own trailer. All three are self-declared by the unit. It does not prove the content is
correct. Only an independent postcondition probe (rung 5) does. Never restate a
`DELIVERED` count in rung-5 language.

## Prior art on this estate — read this before writing another gate

`~/scratch/codex-auth-research-fanout/completion_predicate.py` (144 lines, with
`test_completion_predicate.py`) is the existing C1 predicate and is **complementary, not
superseded**. It classifies `DONE | RUNNING | ABANDONED | UNKNOWN` by folding **process
liveness** (pid alive, CPU delta, log staleness, husk detection) in with the artifact
AND-gate. `receipt_gate.py` deliberately does **not** do liveness — it answers only "is
the contracted artifact really there". Use both: liveness tells you whether to keep
waiting; the receipt gate tells you whether to believe a digest.

Three differences, all measured 2026-08-08 by executing the prior-art module against
fixtures (probe: `~/.claude/harness-restore-20260806/_foundry_prior_art_probe.py`):

### 1. Substring vs line-equality on the trailer — CONFIRMED false DONE on a fixture

`completion_predicate.py:45` tests `f"UNIT-COMPLETE: {unit_id}" not in tail`. A **substring**
test. Fed an artifact whose tail reads

```
The contract says each artifact must end with UNIT-COMPLETE: u1 as its
last line. This unit did NOT finish and wrote no trailer.
```

it returns `ok=True, reason="and-gate-pass"`. The gate marks a unit DONE that says in
plain text that it did not finish. This is the use-vs-mention class (L8) inside the
completion gate itself.

The same module already contains the correct form —
`extract_unit_complete_from_text` at `:141` anchors with `^UNIT-COMPLETE:\s*(\S+)\s*$` and
correctly returns `None` for that same text. **The module disagrees with itself**; one
function says done, the other says no trailer.

**Correctly scoped (L10):** executable-proven on a fixture. Over the 55 real artifacts the
two forms **agree 55/55 — divergence 0**, so no historical false pass is detected in that
corpus (probe: `_foundry_historical_diff.py`). The weakness is real but **LATENT there**.

The realistic trigger is the interaction with L5: a **write-as-you-go skeleton that echoes
its own contract text into the tail** would pass the substring form while having measured
nothing. The estate mandates writing that skeleton, so the mandate makes the trigger more
likely, not less — *likely* (55-80%), inference from the two measured facts above, not an
observed instance. UNVERIFIED whether any live run has hit it; settling experiment: run
both forms over a corpus of *in-flight* skeletons rather than finished artifacts.

`receipt_gate.py` uses line-equality and ships `substring` as a permanent fixture in its
self-test, so a regression to the substring form fails the control.

### 2. No `NOT-CHECKED` state

`and_gate_artifact` folds an unreadable artifact into `False` with reason
`unreadable-<err>`, and a **path that is a directory** returns `no-artifact` — the same
bucket as a genuinely absent file (measured: both return `ok=False reason=no-artifact`).
`classify_unit` then resolves the unit by process liveness, so "I could not read it"
becomes `ABANDONED` or `RUNNING`. There is a `UNKNOWN` state at `:136` but the
`alive` / `not alive` branches at `:130-134` are exhaustive for a bool, so it is
unreachable. Typed silence has nowhere to go.

### 3. No background-receipt reject

Neither module scans the returned digest for `started in the background` /
`Check /codex:status`. That is the cheapest reject in the whole contract
(`fan-out-contract.md:72`) and catches an entire class outright.

**Not fixed by this lane** — `~/scratch/` is outside the workflow-foundry file scope.
Reported for owner routing.

## Both-states control

```
python ../scripts/receipt_gate.py --self-test
```

Builds throwaway fixtures for every broken shape (missing, undersize, no-trailer,
prose-mention, is-a-directory, background-receipt) plus a good one, asserts the gate FIRES
on each broken state and is SILENT on the good one, and prints both. `CONTROL-OK` means
the verdicts are citable; `CONTROL-BROKEN` (exit 1) means they are not.

Measured 2026-08-08: `CONTROL-OK`, 6/6 broken shapes fire, good state silent.