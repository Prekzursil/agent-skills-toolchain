# RELEASE-CHECKLIST

Two different things get "released" here, and conflating them is how a gate reaches enforce
without evidence. They have separate checklists.

```json workflow
{
  "id": "wf.release.validate",
  "description": "Validate command-center gates without spawning.",
  "tools": ["Read"],
  "stop_rule": {"max_stages": 1, "on_error": "halt"},
  "stages": [
    {
      "id": "validate",
      "type": "task",
      "tools": ["Read"],
      "inputs": ["command-center/STATUS.md"],
      "outputs": ["command-center/receipts/TST-0254-validate.json"]
    }
  ]
}
```


## A. Releasing a change to the command center itself

- [ ] `python tools/command-center/validate.py` exits 0.
- [ ] `python tools/command-center/render.py --check` exits 0 (no drift in the derived files).
- [ ] `python -m pytest tools/command-center/tests -q` green, **and** at least one mutated-input
      test proves the check you touched can still go red. A suite that only ever passes is not
      protecting the behaviour.
- [ ] `python -m pytest agent-self/harness/tests/test_register_gate.py -q` green.
- [ ] `ruff check .` and `ruff format --check .` at the CI pin (`ruff==0.15.17`), checked
      against the **LF blob** read through the one helper --
      `python tools/measure-guard/blobread.py <path>`, i.e. `git cat-file -p <rev>:<path>`
      (equivalent recipe: `git show <rev>:<path>`, byte-identical to cat-file) --
      not the CRLF working tree. **Not `git archive`:** on this box it applies export-time
      EOL conversion and hands back the CRLF checkout form, the OPPOSITE of the blob
      (measured 2026-08-15 on `command-center/receipt_validate.py`: archive 8,412 B / 205
      CRLF against cat-file and show both 8,207 B / 0 CRLF, all three identical after LF
      normalisation). Receipt: `command-center/receipts/IMP-0440.json`.
- [ ] Every state change went through `close.py`, so `events/EVENTS.jsonl` has a line for it.
- [ ] No item was deleted. Items leave the open set by acquiring a disposition, never by
      disappearing — REACH-6 fails on a drop, and that failure is the feature.

## B. Promoting the `register_gate` up the ladder

The ladder is `off → shadow → advise`. **There is no `enforce` rung**: the verdict is an
`inject`, so `enforce` would behave identically and offering the rung would only invite a
future session to assume it means something.

| stage | mode | entry condition | exit condition |
|---|---|---|---|
| 0 · build | n/a | — | tests green; the mutation control goes red on demand |
| 1 · **SHADOW** (ships here) | `shadow` — the tier default, no `module-modes.json` key needed | merged | ≥20 distinct `session_hash` values recorded in the shadow sink |
| 2 · review | `shadow` | 20 sessions collected | measured `fires / distinct sessions ≤ 6.0`; **zero** fires on any Stop-family event; zero loop reports |
| 3 · **ADVISE** | add `"register_gate": "advise"` to `module-modes.json` with a `_promoted` block quoting the measured numbers | review passed | — |

**Auto-demote:** >6.0 fires/session over ≥20 sessions ⇒ revert to shadow.

**Promotion honesty clause,** inherited verbatim from `module-modes.json:3`: promotion is on
*frequency, timing and selectivity* only — *"Nothing here is promoted on 'the advice was good';
that was never recorded."* The sink stores no payload, so advice quality is not measurable
today (`UNKNOWNS-REGISTER.md` U-9), and the gate may not be promoted past `advise` until it is.

Pre-promotion evidence to attach, all of it re-measured rather than cited from this PR:

- [ ] fires / distinct sessions from the shadow sink, with the session count.
- [ ] the both-states control re-run: fires on a stale catalog, silent on a clean one.
- [ ] zero records with `event` in `{Stop, StopFailure, SubagentStop}`.

## C. What is explicitly NOT part of any release here

- **No credential is rotated, revoked or regenerated.** `R-B08` is a decision-and-quarantine
  item; rotation is the owner's action (AGENTS.md §9).
- **No live tree is written.** `scripts/sync-from-live.ps1` is not run; `install.py` is used
  only with `--check`.
- **No merge.** This lane is PR-only.

## D. B07 non-inferiority margins (TST-0301)

"Without material regression" (stopping condition 8) is a number, not a phrase. The per-metric
margins live in `command-center/bench/B07-MARGIN-TABLE.json` (schema
`command-center/schema/margin-table.schema.json`), decided at `2026-08-01T00:00:00Z`, BEFORE any
comparison ran. The metrics the gate reads are the `gate: true` rows of
`command-center/bench/METRIC-INVENTORY.json`; `tools/bench/margins.py` refuses a table that does
not cover every one of them.

- A secondary metric is `NON_INFERIOR` when `worse_delta <= margin` (inclusive: exactly at the
  margin resolves `NON_INFERIOR`); beyond it is `MATERIAL_REGRESSION` and the primary win is
  `REFUSE`d by `tools/bench/release_gate.py`.
- Every comparison binds the table's content-address sha256 before scoring. Editing a margin
  afterwards is `POST_HOC_MARGIN_CHANGE`, never a silent re-score; a comparison that started
  before `decided_at` is `POST_HOC_MARGIN_DECISION`.
- [ ] margin table sha256 recorded on the comparison record before the candidate is scored.
