# recall-gate — prior-art gate over the local harness tree

**STATUS: BUILT, TESTED, BOTH-STATES PROVEN — and WIRED TO NOTHING.**
Wiring requires an edit to `~/.claude/settings.json`, which is outside the `recall`
lane's declared file scope. Until an owner performs step 1 below this hook never runs.
Shipping green-but-inert is the exact defect class this program exists to close, so it is
recorded here rather than quietly left as "done".

## What it does

On `UserPromptSubmit`, when the prompt is about to **assert absence** ("there is no…",
"from scratch", "nothing exists", "missing", "novel") or **propose a build**, it extracts
artifact nouns and checks them against an index of the local harness tree, then injects a
short `PRIOR ART` digest naming files that already exist.

## Why it is not a duplicate of what already ships

The harness already runs `bounded_recall` (`~/.agents/harness/modules.py:1984`, live on
`UserPromptSubmit` via the harness dispatcher). It works — an end-to-end probe surfaced the
right note in 0.68 s. But it indexes the **basic-memory vault only**. Measured against the
live `~/.agents/state/harness/recall-index.json` (597 notes, built 2026-08-07):

| root | notes in vault index |
|---|---|
| `.claude/hooks` | **0** |
| `.agents/harness` | **0** |
| `.claude/rules` | **0** |

Of the seven wrong claims recorded on 2026-08-07, the majority named a **tree artifact**
present on disk and absent from that index. This gate serves that half and deliberately does
not re-search the vault (`test_does_not_index_the_vault` enforces it).

## Typed silence

Every run resolves to exactly one state, appended to `state/recall-gate-<YYYYMMDD>.jsonl`:

| state | meaning | injects? |
|---|---|---|
| `FINDING` | prior art found | yes |
| `CLEAN` | searched, nothing found (or no build/absence intent) | no |
| `NOT-CHECKED` | index unavailable or time budget blown — **not** a pass | no |
| `RAISED` | an exception was swallowed (fail-open) | no |
| `DEGRADED` | reserved: partial index | no |

A `CLEAN` never manufactures a digest; a run that cannot prove it executed reports
`NOT-CHECKED`, never silence.

## Budget

The four DISARMED Stop checks parse the whole transcript, so cost is O(session length) with no
deadline. This gate is O(index) behind a content-hash cache with a monotonic deadline checked
between phases and inside the match loop.

Measured: scan surface 331 files / 3.5 MB; cold index build **0.279 s**; hot path **~10 ms**;
full hook end-to-end **0.148 s** against a `RECALL_GATE_BUDGET_SEC` default of 2.5 s, inside
the 8 s `UserPromptSubmit` wall it would share with three other hooks.

## Wiring (OWNER ACTION — not performed by the `recall` lane)

1. Add to `~/.claude/settings.json` under `hooks.UserPromptSubmit`, alongside the existing
   `semantic-router` and `selection-events` entries:

   ```json
   { "type": "command",
     "timeout": 10,
     "command": "python \"C:/Users/Prekzursil/.claude/hooks/recall-gate/gate.py\"" }
   ```

   Back up `settings.json` first. The hook exits 0 unconditionally, so a failure cannot block
   a prompt; the worst case is silence.

2. Verify with the both-states probe (it must be silent BEFORE and fire AFTER):

   ```
   python ~/.claude/harness-restore-20260806/_recall_bothstates.py
   ```

3. Reconcile into version control — live-only harness work is drift
   (`rules/common/harness-vcs-hygiene.md`). Copy this directory to
   `~/source/agent-skills-toolchain/hooks/recall-gate/` and commit. Do **not** run
   `scripts/sync-from-live.ps1` (a bare `-Report json` writes).

## Tests

```
python ~/.claude/hooks/recall-gate/test_recall_gate.py     # 9/9, no pytest needed
python ~/.claude/hooks/recall-gate/tree_index.py --rebuild # rebuild the index
```

Each capability test is paired with the state in which it must FIRE and the state in which it
must be SILENT, including a detector control that forces the index unavailable and asserts
`NOT-CHECKED` rather than a false `CLEAN`.

## Opt-out

`RECALL_GATE=off`, or `touch ~/.claude/hooks/recall-gate/.disabled`.

## Known limits

- **UNVERIFIED: precision against real prompt traffic.** Tuning used a handful of
  hand-written prompts plus one measured false hit ('length' matching three unrelated test
  files, fixed by requiring single-word nouns to match a stem exactly). The settling
  experiment is to replay a day of real `UserPromptSubmit` payloads through
  `gate.run()` and count FINDING/CLEAN, which nothing has done yet.
- Only three roots are indexed (`hooks`, `harness`, `rules`). Skills and commands are not.
- It fires on the **user's** prompt only. The agent's own mid-turn absence assertions — which
  is how several of the 2026-08-07 wrong claims were actually stated — do not pass through
  `UserPromptSubmit`. Closing that needs a different, more dangerous surface; see the design
  sketch in `~/.claude/harness-restore-20260806/31-LANE-recall.md`.
