---
title: LANE-MCPRESEARCH-BUILD-R4
type: note
permalink: dqverify-repo-20261013/docs/mcp-audit/lane-mcpresearch-build-r4
---

# LANE MCPRESEARCH — BUILD round 4: the denominator that was never unmeasurable

Round 4 of at most 4. The re-entry instruction was *"a verifier CONFIRMED defects last round —
fix those."*

**The finding list did not reach me.** My spawn prompt carries the round-**1** audit, and its
`overclaims` field is cut off mid-sentence, at `"The 7 excluded rows are all
session_mounted=True"`. No round-3B verifier artifact exists on disk either
(`git log -- docs/mcp-audit command-center/mcp-audit` ends at `0dc951a7`, a self-correction).

That is the **same transport failure round 3B diagnosed** — *"a round which cannot see the whole
finding list will report itself complete"* — recurring one round later, on the round that
documented it. Round 3B lost the audit's second overclaim to truncation; round 4 lost the whole
list. So this round does not guess at a finding list. It states the gap, then measures.

What it found is better than a guess: **the audit's central residual was still open, and it was
closable.** Round 3 fixed the overclaimed *sentence* and declared the underlying number
permanently unavailable. That availability claim was false.

---

## The finding: a "not available" that was only "not asked for"

`cost_rank.py` shipped this, as a statement of fact about what can be known:

> *"Publishing a fleet-wide figure instead is not available: the 7 rows have no tool names
> anywhere in the repository, so the true fleet denominator is UNMEASURED, not merely
> unpublished."*

**True premise, false conclusion.** "No tool names in the **repository**" is a fact about the
repository, not about what is measurable. The 7 rows are HTTP transports — the stdio sweep
records `transport='http': no stdio command` for every one — so the *sweep* cannot reach them.
The **client connects to them anyway and lists their tools**, and this lane has treated that
listing as a legitimate second instrument since the grounding round: `_g2_drift_probe`'s
`SESSION_NAMESPACE` is exactly that listing, used to corroborate the mounted server set.

The denominator was never unmeasurable. It was unmeasured because the producer asked one
instrument and then generalised from its silence.

### What round 3 got right, and why this is not filed as its defect

Round 3's headline — *"60.1% of the 16 SAMPLED servers … the true fleet share of this row is
strictly lower"* — is **correctly scoped, honest about its residual, and directionally right**.
The measurement came in at **49.5%**, which is strictly lower than 60.1%, exactly as predicted.

It is recorded as **SUPERSEDED BY MEASUREMENT, not REFUTED**, in
`cost-rank.json → superseded_not_refuted`. Filing a correct sentence as a defect teaches the
next round the wrong lesson: it would say *disclose less*, when the disclosure is what made the
residual findable. Only the availability claim in the docstring is marked REFUTED, and it is
kept in place above its correction rather than deleted.

---

## Measured

| | sampled (stdio) | + client-listed | = fleet |
|---|---|---|---|
| servers | 16 | 7 | **23** |
| tools | 707 | 154 | **861** |
| resident bytes | 11,645 | 2,487 | **14,132** |
| contingent bytes | 603,233 | *not measured* | *still a lower bound* |

**`cloud-hub` is 49.5% of the fleet's every-turn resident cost** (6,998 / 14,132), against
**60.1%** of the sampled subset (6,998 / 11,645). Both ship, both labelled, and `C7` fails the
run if the headline stops naming which is which — two unlabelled percentages would be a worse
defect than the one `C5` caught, because a reader could not even tell a choice had been made.

### RESIDENT only, and why that asymmetry is the honest result

Tool **names** are what a deferred-schema client keeps resident, and the client lists them. Tool
**schemas** are precisely what it withholds until selection, so the 7 rows have no honest
contingent figure and `contingent_bytes` stays `null` for every one of them — **null meaning NOT
MEASURED, never zero**. The fleet RESIDENT total is a true total; the fleet CONTINGENT total
remains a lower bound, and `C7` requires that caveat to stay in the key name
(`contingent_bytes_fleet_lower_bound`), not just in prose.

Publishing one and not the other is the result, not an omission.

### Independence, stated narrowly

The audit reached 154 tools / 2,487 B by hand and rated it only **LIKELY**, for two stated
reasons: the count was hand-transcribed, and its session ran days after the audited sweep, so
the fleet might have drifted.

Both are now settled, and only those two:

- **Drift** — `_g2_drift_probe` reports **23/23** server names agreeing across two instruments,
  differ control fired first in both directions.
- **Transcription** — my transcription agrees with the audit's on **all 7 servers, on both
  tools and bytes**, re-checked on every run by `C_audit_corroborates` rather than asserted once.

This is **transcription independence, not instrument independence.** Both transcriptions read
the same client listing, so a systematic error in the *client* would survive both. That rules
out the error mode the audit actually flagged and rules out nothing else. *Settling experiment:*
an HTTP `tools/list` against each of the 7 endpoints, which needs credentials this lane does not
read (AGENTS.md §9).

---

## Already closed in earlier rounds — not re-litigated

| id | finding | class | closed |
|---|---|---|---|
| D1 | `search-hub` credited with a non-exa tool count transposed from cloud-hub's row | real defect | round 3 |
| O1 | `cloud-hub is 60.1% of every-turn resident MCP cost` | overclaim — denominator was 16 of 23 rows | round 3 |
| O2 | the aggregate feeding O1 was still labelled `fleet` | overclaim — same defect one level up | round 3B |

> **On D1's wording, declared rather than done quietly.** `claim_lint` fired on my first draft
> of that row, which restated the refuted figure verbatim — the guard working exactly as
> intended on a brand-new file. Three exemptions already exist for that number. I **rephrased
> instead of adding a fourth**, and say so here rather than letting a silent reword look like
> the gate was always green: round 3B's rule is that *quietly* slipping past a working guard is
> the failure, and the row does not need to re-assert the count to name the defect. The figure
> and its full derivation stay in `LANE-MCPRESEARCH-BUILD-R3.md`, which is exempted precisely
> so one document keeps the receipt.

---

## Evidence

Measured **at** commit `3e54214a`, not before it — the determinism job compares regenerated
bytes against the *committed* blob, so a pre-commit reading measures the fail-closed branch
instead of the result:

```
== mcp-audit CI gate @ 3e54214a (win32, py 3.11.9) ==     # 3.11 == the mcp-audit.yml pin
  ok  inventory: 27 planned runs over 22 gates, 21 excluded with reasons
  ok  rc=0 (want 0)  unsampled_surface (fleet-denominator rows)
  ok  rc=0 (want 0)  unsampled_surface (both-states)  SUCCESS:unsampled-surface self-test
                                                      8/8 controls behaved
  ok  rc=0 (want 0)  cost_rank (invariants)           SUCCESS:cost-rank FLEET
        resident=14,132B over all 23 mounted rows (16 by stdio + 7 from the client
        listing); of that, 11,645B is the 16 SAMPLED rows this table ranks. Contingent
        603,233B stays a LOWER BOUND
  ok  rc=0 (want 0)  cost_rank (C5+C6+C7 both-states) SUCCESS:cost-rank self-test 13/13
  ok  rc=0 (want 0)  claim_lint   SUCCESS:claim-lint 36 attributed counts over 13 docs,
                                  0 exceed their server, 3 declared exemption(s)
  ok  rc=0 (want 0)  scope_lint   SUCCESS:scope-lint 35 aggregate quotation(s), 0 unscoped,
                                  1 declared exemption
  ok  rc=1 (want 1)  dod_check @ 630bb8af (must FAIL) FAILED:dod-check ['DoD3']
  ... 19 further gates, all rc as planned ...
  -- producer determinism --
  ok  unsampled-surface.json byte-identical to the committed blob (5407 B)
  ok  cost-rank.json         byte-identical to the committed blob (16100 B)
SUCCESS:mcp-audit-ci-gate 27/27 gates behaved, 5/5 artifacts byte-identical to their producers
```

**27/27**, up from round 3B's 25/25 — the two new runs are `unsampled_surface`'s, and a fifth
artifact joins the determinism set. `EXIT=0` read directly, not through a pipe (`$?` after a
`| tail` reports *tail's* status, which is how a red gate reads green). Repeated on **3.12**
and **3.14.6**: identical line, exit 0, artifacts byte-identical on all three — so the result
is not one runtime's dict ordering or float formatting. `ci_gate --self-test` 8/8.

**Line endings and lint, measured on the stored blob rather than the working tree.**
`_r4_selfcheck` reports **8/8 blobs 0 CRLF** at the commit, positive control firing. `ruff`
0.15.17 (the CI pin) run against blobs extracted with `git show` into a temp tree **carrying a
copy of the repo's `ruff.toml`** — without the config ruff falls back to its own defaults and
manufactures a false red — gives `check` clean and `format --check` "3 files already
formatted", with a deliberately mangled file proving both directions fire. `git` printed *"LF
will be replaced by CRLF"* on commit; that describes the working copy, not the blob.

New this round, in isolation:

```
SUCCESS:unsampled-surface 7 unsampled row(s), 154 tools, 2,487 resident B
        (RESIDENT only -- contingent stays unmeasured for every row here)
SUCCESS:g2-drift 23/23 names agree across two independent instruments
SUCCESS:blob-ruff clean on the blob=True, control fired=True
```

### Detector controls — both states, on real mutations

| control | mutation | observed |
|---|---|---|
| `unsampled_surface` **V1** | drop a server from the surface | **fires** — a fleet total cannot be completed short |
| `unsampled_surface` V2 | add a server that is already sampled | fires — no double count |
| `unsampled_surface` V3 | an `mcp__`-prefixed name | fires — would inflate `name_bytes` |
| `unsampled_surface` V4 | a duplicated name | fires |
| `unsampled_surface` V5 | an empty server surface | fires |
| `unsampled_surface` **C_basis** | perturb a **committed** `name_bytes` by 1 | **fires** |
| `unsampled_surface` C_audit | a surface drifting from the audit's hand count | fires |
| `cost_rank` **C7a** | `FLEET_SUFFIX` emptied → bare `tools` key | **fires** |
| `cost_rank` C7b | lower-bound caveat removed from the contingent key | fires |
| `cost_rank` **C7c** | upstream producer returns a **stale, short** surface | **fires** |
| `cost_rank` C7 revert | all constants restored | green again — the fire was the mutation |

**`C_basis` is the control that can distinguish the two hypotheses**, and it is the one worth
explaining. The question is *"are the new rows commensurable with the old ones?"* — do I count
bytes the way the sweep counted them? A check that read my own surface back would pass under
both hypotheses and prove only that the file parses; that is the inert shape this repo has
measured four times. So the control recomputes `name_bytes` for all **16 SAMPLED rows** with my
function and requires an exact match against their committed values. It reconciles 16/16, and
perturbing one committed value by a single byte turns it red.

**`C7c` is the mutation that matters most.** V1 guards the surface against the matrix, but the
branch that actually publishes a fleet total lives in `cost_rank`. Mutating this module's own
constants cannot reach it — only replacing the upstream producer with one that returns a short
surface does, which is the realistic failure (a stale transcription after a fleet change). It
fires.

**One control I deliberately did not claim.** `V1` compares my surface against the *committed*
matrix's unsampled set. If the real fleet gains an HTTP server, both sides stay unchanged and V1
stays green while the transcription is stale. It fails closed against **schema drift**, not
against **world drift**; the drift probe is what covers the latter, and only on the day it runs.
Disclosed rather than counted as coverage.

---

## Residual — inline, none of it blocks

- **The DoD ledger still prints `cost-measured=16/23`, and that is not a contradiction —
  but it reads like one, so it is stated here rather than left for a reader to trip over.**
  `_r2_dod_check` counts rows in **`disposition.json`** carrying a cost field, and those come
  from the stdio handshake sweep, which still reaches 16. The round-4 measurement lives in
  `unsampled-surface.json` and `cost-rank.json`, which I did not back-port into
  `disposition.json`. So both numbers are true of the artifact each reads: **16/23 rows carry
  a sweep-derived cost; 23/23 rows have a measured RESIDENT cost across the two producers.**
  I deliberately did not widen `disposition.json` late in the round — it feeds `render_table`
  and the committed `DISPOSITION-TABLE.md`, and a ripple through the determinism set at this
  point buys less than it risks. *Settling experiment:* join `unsampled-surface.json` into
  `rank_disposition` and re-run the determinism set; the ledger counter should then read
  23/23 for resident and keep 16/23 for contingent.
- **CONTINGENT fleet total is still a lower bound**, and structurally so: a deferred-schema
  client never materialises schemas for the 7 client-listed rows. *Settling experiment:* an
  eager-schema client, or an HTTP `tools/list` with credentials this lane does not read.
- **Instrument independence is not established** — see above. Transcription error is ruled out;
  a systematic client-side under-report is not.
- **`V1` cannot see world drift**, only schema drift. Named above.
- **`dead_surface_pct` remains null for every non-cloud-hub row**, search-hub included: all 4 of
  its backends are measured, but no tool→backend map exists to attribute its bytes. Null means
  NOT ATTRIBUTED, never zero. Unchanged from round 2, deliberately not built blind.
- **P3, the resource regression, is still untouched** and still outside this lane's file scope
  (`docs/mcp-audit/**`, `command-center/mcp-audit/**`); the mitigation is a config mutation via
  `mcpapply`. *Likely (55-80%)* that it is the most operationally urgent open item — it rests on
  the documented commit-exhaustion mechanism, not on a freeze observed here.
- **CI-runner behaviour remains UNVERIFIED**, narrowed to the runner environment.
  *Settling experiment:* the first `workflow_dispatch` after merge.
- **The round-4 finding list never arrived.** If the round-3B verifier confirmed a defect that is
  not the one closed here, it is still open and this report cannot say otherwise. *Settling
  experiment:* recover the verifier's untruncated output and diff it against this section.
- **A report-only `POTENTIAL-CREDENTIAL` artifact notice fired**, id `sha256:14c745ad1f24` — the
  same id round 1 recorded. No credential was read, printed, rotated or edited; no agent action
  clears the notice. Surfaced for the owner.

## Confidence

**Almost certain (90-99%)** — that the fleet resident denominator is 14,132 B over 861 tools and
`cloud-hub` is 49.5% of it. The arithmetic reconciles exactly to its parts inside the producer
(`C7`), the byte basis reproduces 16/16 committed values (`C_basis`), the two server sets are
proven to partition all 23 mounted rows, and two independent transcriptions agree on every
server. The gate is byte-identical across three interpreters, so the result is not one runtime's
formatting.

**Almost certain (90-99%)** — that the docstring's availability claim was false. `_g2_drift_probe`
has been reading the very listing it said did not exist, since before that sentence was written.

**Likely (55-80%)** — that P3 is the most operationally urgent open item. Mechanism-based, not
observed here.

**UNVERIFIED, inline** — whether the round-3B verifier's confirmed defect is the one closed here.
Its output never reached this round and no artifact of it exists in the repo. What is *not*
uncertain is that the residual closed here was named, in writing, by both the audit and round 3B.

**Self-check.** The finding I shipped is one the audit *had already pointed at* — it computed
49.5% itself and round 3 declined to publish it as unreproducible. I did not discover a new
defect; I reproduced a number someone else had measured and made it fail closed. The honest
framing is that round 3's "not available" was the overclaim, not round 3's headline — and I only
noticed because the docstring stated its impossibility as a fact, which is the kind of sentence
worth testing. The one number that moved in the flattering direction — `cloud-hub` looking
*smaller*, 60.1% → 49.5% — is the one whose denominator I reconciled twice and gave its own
partition control, because a correction that makes the fleet look better is the one nobody
audits.