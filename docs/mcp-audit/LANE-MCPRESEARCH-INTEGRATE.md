# LANE MCPRESEARCH — INTEGRATE (final stage)

Measured 2026-08-14 in `C:/Users/Prekzursil/source/ast-integrate`. Companion to
`INTEGRATION.md` (which wired the lane's gates into CI) and to the four
`ROUND{1,2,3,4}-DEFECT-CLOSURE` ledgers.

`INTEGRATION.md` made the lane's **gates** reachable. This round makes the lane's
**measurement** reachable, closes the two contested items the adversarial round left open,
and records one it could not have known about because I committed it myself.

COVERAGE: every claim below carries an executed exit code. **NOT measured:** the ~21
`quality.yml` steps other than the two lint halves; behaviour on a real GitHub runner; the
7 HTTP rows' *contingent* cost (structurally unmeasurable — §5); `dead_surface_pct` for
non-`cloud-hub` rows. Each is in §6 with its settling experiment.

If it still reads this way, the unit died before measuring anything and no verdict here
may be cited. — *it does not; every section quotes a real exit code.*

---

## 1. The gap: a measurement that reached no consumer

Round 4's headline finding was that the fleet denominator had never been unmeasurable,
only unasked. It measured the 7 HTTP-transport rows the stdio sweep cannot spawn — the
ones with no child process to sample — and wrote them to `unsampled-surface.json`.

**Nothing joined the number back.** `disposition.json` still carried seven nulls, and
`docs/mcp-audit/DISPOSITION-TABLE.md` — the only artifact in this lane a human reads —
still printed `--` in all seven `tools` cells. The DoD ledger still reported
`cost-measured=16/23`. Round 4 named the fix as its own **first residual** and did not run
it:

> *Settling experiment: join `unsampled-surface.json` into `rank_disposition` and re-run
> the determinism set; the ledger counter should then read 23/23 for resident and keep
> 16/23 for contingent.*

That is the same shape as the hole `INTEGRATION.md` opened with — *"a gate nobody invokes
is indistinguishable from one that does not exist"* — one level down, in the lane's own
output. A measurement no consumer reads is indistinguishable from one never taken.

## 2. What is wired

| | |
|---|---|
| `rank_disposition.py` | READS `unsampled-surface.json` and joins `resident_tool_count` / `resident_bytes` / `resident_basis` / `resident_instrument` onto every mounted row. New invariant `assert_resident_completeness()`. |
| `render_table.py` | Renders the resident columns, marks a client-listed cell `*`, and states the resident-vs-contingent asymmetry in the footer. New `G5` both-states invariant. |
| `_r2_dod_check.py` | `DoD3` gains a second limb requiring a resident cost on every mounted row. Summary splits into `resident-measured` and `contingent-measured`. |
| `_i5_resident_join.py` | **NEW.** The end-to-end proof, in `CI_PLAN`. §4. |

**The join is a READ, never a recomputation.** `unsampled_surface.py` owns those numbers
and `cost_rank.py` already sums them; a third module deriving them independently is how two
artifacts start disagreeing. `assert_resident_completeness()` requires each joined value to
equal its source exactly, so a drift between the two files fails the run instead of
shipping.

**RESIDENT is a separate field set, not a widening of `tool_count`.** `tool_count` and
`name_bytes` are what `liveness_basis` describes — the stdio child — and an HTTP row has
none. Writing a client-listed count into `tool_count` would leave a row asserting a
measurement beside a basis saying `not-measured:`: the round-2 *"verified and failed in one
object"* defect, reappearing in a new column. The instrument travels with the number, in a
machine-readable enum (`stdio` / `client-listing`) rather than a prose prefix, because a
renderer keyed on prose silently stops marking the day the sentence is improved.

## 3. The DoD counter moved exactly as round 4 predicted

```
$ python command-center/mcp-audit/_r2_dod_check.py WORKTREE
  summary: call_verified=21/23  resident-measured=23/23  contingent-measured=16/23
           stdio-sampled=16/23  dispositions={'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}
SUCCESS:dod-check 4/4 DoD items PASS, 9/9 negative controls fired
```

Negative controls went **7 → 9**. `render_table`'s invariants went **6 → 8**.
No disposition moved: `DISABLE 1 / INVESTIGATE 2 / KEEP 20`, before and after. A wiring
change that moved a verdict would be a different change, and this one did not.

### The control that carries the weight

`unjoin-with-a-good-reason` reproduces the **exact state the artifact shipped in before
this round**: resident cost null on a client-listed row, beside the entirely truthful
basis those rows already carried about the stdio child.

That is why DoD3's new limb accepts **no stated reason**, unlike its first limb. A
reason-accepting predicate cannot fail in the state it exists to detect — the reverted rows
would carry an honest `not-measured: transport='http'…` and read as a correctly-disclosed
residual. Which is precisely how a measurement sat unreached for a whole round while every
check agreed the artifact was fine. The asymmetry between the two limbs is the finding.

## 4. Red-proof: the check fails without the integration

`_i5_resident_join.py` compares **two committed blobs** — `PRE` is pinned to `f6a1f91b`,
the last commit before the join — so "it used to be broken" is a blob anyone can fetch
rather than a sentence in a report.

```
$ python command-center/mcp-audit/_i5_resident_join.py
  source: unsampled-surface.json carries 7 client-listed rows
  ok  P1 fires on f6a1f91b (23 mounted rows with no resident cost), silent now
  ok  P2 a 1-byte drift from unsampled-surface.json fires (brightdata)
  ok  P3 an inert join fires on its own, with every other limb satisfied (16 rows)
  ok  P4 table cost cells: 7 unmeasured at f6a1f91b -> 0 now, 7 row(s) marked `*`
SUCCESS:i5-resident-join
```

The same red state is visible through the shipped ledger, which is the cheaper
demonstration:

```
$ python command-center/mcp-audit/_r2_dod_check.py f6a1f91b   # the pre-join artifact
  DoD3 FAIL  per-server RESIDENT cost measured on every mounted row; …
  summary: … resident-measured=0/23  contingent-measured=16/23 …
FAILED:dod-check ['DoD3']                                        rc=1
```

**Why four probes and not one.** P1 alone would pass for a producer that *invented* the
numbers — invented numbers are still non-null — so P2 perturbs a joined value by exactly 1
and requires the invariant to notice it disagrees with its source. P3 exists because the
empty-join limb cannot be isolated in the real artifact (with zero rows joined, the 7 HTTP
rows have no resident cost and the presence limb fires first), so it runs against a
synthetic all-stdio row set where presence and integrity both pass and an inert join is the
only thing left to detect: a guard that only ever fires alongside another guard has not
been shown to work. P4 exists because the invariant is about `disposition.json` while the
deliverable is a markdown file, and a reader is served by neither if the renderer drops the
join on the floor.

### Two detector failures in this probe, caught by its own fail-closed checks

Both were **self-contradicting output**, which this repo classifies as a detector failure
rather than a finding, and both are recorded rather than quietly fixed:

1. **P1 printed `fires … (0 mounted rows with no resident cost)` beside a verdict that it
   fired.** The counter matched `"mounted with no RESIDENT cost"` — `dod3`'s wording, not
   the invariant's. On the pre-join blob the rows carry no `resident_basis` *at all*, so a
   different limb fires with different wording. Fixed by counting complaint **lines**
   (which limb objected is not the question the probe asks), and the mismatch is now itself
   a hard failure rather than a cosmetic zero.
2. **P4 reported `23 row(s) marked *` when only 7 rows are client-listed.** The test was
   `"* |" in line`, and every row satisfies it because the disposition cell is bolded —
   `**KEEP**` ends in `* |`. It counted the document, not the field: the exact
   use-vs-mention shape this repo keeps paying for, in the probe written to guard against
   sloppiness. Fixed by reading column 7, and the count is now cross-checked against the
   number of client-listed rows in `disposition.json`, so mark and data disagreeing is a
   failure.

## 5. What did NOT get joined, and why that is the result

**CONTINGENT cost (`schema B`) stays null for the 7 rows.** Tool *names* are what a
deferred-schema client keeps resident and the client lists them; tool *schemas* are exactly
what it withholds until selection. There is no honest figure to carry, so `--` stays, and
DoD3's new limb deliberately does not require one — demanding it would force a fabrication.

So the artifact now says two different things about two different quantities, and both are
true: **resident measured on 23 of 23 rows; contingent measured on 16 of 23**, with the
fleet contingent total still a lower bound. Round 4 shipped a residual explaining that
`cost-measured=16/23` was not a contradiction of its own 23-row fleet total; it was one
counter standing for two quantities. A single counter could only ever be right about one of
them, so there are now two.

## 6. Contested items carried in from the adversarial round

The lane ended contested (`audit_holds: true`, `build_is_sound: false`). Both `must_fix`
items are resolved; one was already closed before I arrived and I verified it rather than
assuming.

| item | state |
|---|---|
| **MUST-FIX 2** — `113 non-exa tools` of a 68-tool surface | **Already closed in round 3.** Verified at `LANE-MCPRESEARCH-BUILD-R2.md:231`: the refuted wording is preserved in a blockquote with the corrected figure (54 of 68) and the transposition traced. `claim_lint.py` now refuses any prose count exceeding the surface it is attributed to. I re-read it rather than trusting the round-3 report. |
| **MUST-FIX 1 (a)** — `ruff check` alone quoted as `== the CI pin` | **Fixed** at `LANE-MCPRESEARCH-BUILD-R2.md:210`. The pinned job runs two steps and only one was run; the comment was true of the ruff *version* and false of the ruff *gate*. Refutation recorded in place, not deleted. |
| **MUST-FIX 1 (b)** — the CI-runner residual scoped to "the runner environment" | **Fixed** at the same file's residual list. The residual was not the environment; it was the un-run half of the pinned gate, and that half was RED on the exact blobs the sentence certified. Narrowing an unverified claim to the part you *cannot* measure hides the part you can. |
| **MUST-FIX 1 (c)** — run `ruff format --check` before committing | **Done, and it caught me.** §7. |

## 7. The refuted defect reproduced itself on my own files

Running only the half of the gate I was in the middle of writing a correction about would
have been an unusually pure repeat, so both halves were run at the pinned version:

```
$ uvx ruff@0.15.17 check command-center/mcp-audit/          ->  All checks passed!   rc=0
$ uvx ruff@0.15.17 format --check command-center/mcp-audit/ docs/mcp-audit/
Would reformat: command-center\mcp-audit\_i5_resident_join.py
Would reformat: command-center\mcp-audit\rank_disposition.py
2 files would be reformatted, 42 files already formatted                            rc=1
```

`ruff check` was green in exactly that state. Formatted, then re-ran both:
`All checks passed!` / `44 files already formatted`, rc=0 and rc=0.

This is the second time in this lane that the format half went red while the check half
stayed green, on a different round and different files. The recurrence is the point: the
first occurrence was written up as a one-off, and the correction ("state which half was
run") is a documentation fix that does not stop it happening. **What stops it is running
both halves, which is now the last step before every commit in this lane.**

## 8. Evidence

Gate at the integration commit, on the interpreter `mcp-audit.yml` pins:

```
$ py -3.11 command-center/mcp-audit/ci_gate.py
  ok  inventory: 28 planned runs over 23 gates, 21 excluded with reasons
  ok  rc=0 (want 0)  i5_resident_join (join reachable, both-states)
                     SUCCESS:i5-resident-join …
  ok  rc=0 (want 0)  render_table (G1-G5 both-states)
                     SUCCESS:render-table self-test 8/8 invariants behaved
  ok  rc=0 (want 0)  dod_check @ rev
                     SUCCESS:dod-check 4/4 DoD items PASS, 9/9 negative controls fired
  ok  rc=1 (want 1)  dod_check @ 630bb8af (must FAIL)   FAILED:dod-check ['DoD3']
  -- producer determinism --
  ok  disposition.json / overlap-report.json / unsampled-surface.json /
      cost-rank.json / DISPOSITION-TABLE.md   all byte-identical to their committed blobs
SUCCESS:mcp-audit-ci-gate 28/28 gates behaved, 5/5 artifacts byte-identical
```

Measured **at** the commit, not before it: the determinism job compares regenerated bytes
against the *committed* blob, so a pre-commit reading exercises the fail-closed branch
instead of the result. Pre-commit the gate reported exactly three problems — `dod_check @
rev` plus the two artifacts not yet committed — and nothing else, which is the expected
shape and is recorded here so a reader can tell it from a real failure.

`cost-rank.json` and `unsampled-surface.json` stayed **byte-identical throughout**, so the
join did not disturb the round-4 cost figures — the numbers were joined, not recomputed.

## 9. Residual — inline, none of it blocks

- **The 7 rows' CONTINGENT cost remains unmeasured and structurally so.** §5.
  *Settling experiment:* an eager-schema client, or an HTTP `tools/list` against each
  endpoint with credentials this lane does not read (AGENTS.md §9).
- **Instrument independence is still not established.** The joined numbers and the audit's
  hand count are two *transcriptions of the same client listing*, so a systematic error in
  the client would survive both. Round 4 said this and the join does not improve it: it
  makes the number reachable, not more independent. *Settling experiment:* the same HTTP
  `tools/list` above.
- **`dead_surface_pct` is still null for every non-`cloud-hub` row**, `search-hub`
  included. Null means NOT ATTRIBUTED, never zero. Round 2 measured why it was not built
  blind: name shape resolves only 61 of `search-hub`'s 68, leaving 7 genuinely
  unattributable. Unchanged, and deliberately so.
- **P3, the resource regression, is still untouched** and still outside this lane's file
  scope (`docs/mcp-audit/**`, `command-center/mcp-audit/**`) — the mitigation is a config
  mutation via `mcpapply`. *Likely (55-80%)* that it is the most operationally urgent open
  item; that rests on the documented commit-exhaustion mechanism, not on a freeze observed
  here. It has now survived five rounds as "out of scope", which is itself the finding:
  **it needs assigning to a lane that owns config, not restating.**
- **The R1 target — wiring this producer into `tools/mcpctl`'s four null fields and
  `monitorcore`'s pane — is still not done**, same scope reason. `INTEGRATION.md` §3b
  removed the blocker (the producer reproduces off the owner's box) and this round removes
  the second one: every mounted row now carries a resident cost, so a consumer joining on
  it no longer has to special-case seven nulls.
- **CI-runner behaviour remains UNVERIFIED**, and now honestly scoped: green on 3.11 (the
  pin) locally, and **both** halves of the pinned lint job are green. What is untested is
  the runner itself. *Settling experiment:* the first `workflow_dispatch` after merge.
- **`_i5_resident_join.py` pins `PRE` to a commit hash.** If that commit is ever
  unreachable — a shallow clone, a rewritten history — the probe fails closed rather than
  silently skipping. That is the correct direction, but it does mean the gate depends on
  `fetch-depth: 0`, which `mcp-audit.yml` already sets for four other gates.
- **A report-only `POTENTIAL-CREDENTIAL` artifact notice fired**, id `sha256:14c745ad1f24`
  — the same id rounds 1 and 4 recorded. No credential was read, printed, rotated or
  edited. No agent action clears it; surfaced for the owner.

## 10. Confidence

**Almost certain (90-99%)** — that the join is wired end to end and that the check fails
without it. Two committed blobs compared, the invariant fires on one and is silent on the
other, its integrity and empty-join limbs each fire in isolation, and the rendered table
went from 7 unmeasured cost rows to 0 with 7 rows marked. The gate is byte-identical across
its determinism set at the commit.

**Almost certain (90-99%)** — that `ruff format --check` was red on this round's files
before I formatted them, and green after. Executed at the pinned version, both states, rc
recorded each way.

**Likely (55-80%)** — that the workflow passes first time on a real runner. Unchanged from
round 4, and unchanged *because* nothing this round could test it.

**Uncertain (20-55%)** — that no further "measured but unreached" gap remains in this lane.
This round found one that four previous rounds had named and left; a self-review is not the
settling experiment, an independent pass is.

**Self-check.** The number that moved in the flattering direction is `cost-measured 16/23`
becoming `resident-measured 23/23`, which makes the lane's DoD look completed. So that is
the one given the reason-refusing control (`unjoin-with-a-good-reason`), a join-integrity
limb that rejects invented values, and a counter *split in two* rather than widened — the
contingent half deliberately stays at 16/23 and is printed beside it, because a single
counter reading 23/23 would have been the overclaim.
