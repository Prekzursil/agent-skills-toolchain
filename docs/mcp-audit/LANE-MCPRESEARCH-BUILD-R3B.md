# LANE MCPRESEARCH — BUILD round 3B: the second overclaim

**Round 3 shipped at `9ec1eb33` and closed two of the three audit findings.** This is the
same round re-entered, closing the one it never saw.

Round 3's own opening sentence reads *"It CONFIRMED one real defect and one overclaim."*
That is **wrong, and it is corrected here rather than in place**: the audit returned
*"ONE REAL DEFECT (low severity) and TWO OVERCLAIMS"*. The second was truncated out of the
handoff that reached round 3, so round 3 fixed D1 and O1 and stopped. The gap was not a
detector failure — nothing was mis-measured — it was a **transport** failure, and the
lesson is that a round which cannot see the whole finding list will report itself complete.

| # | finding | class | round |
|---|---|---|---|
| D1 | `search-hub` credited with 113 non-exa tools of a 68-tool surface | real defect | 3 — closed |
| O1 | `cloud-hub is 60.1% of every-turn resident MCP cost` | overclaim — per-row denominator | 3 — closed |
| **O2** | **the aggregate feeding O1 was still labelled `fleet`** | **overclaim — same defect one level up** | **3B — closed here** |

---

## The false start, recorded because it is the more useful half

My first candidate for O2 was an **evidence-provenance** defect. The audit's reproduction
block contains a bracketed note that appears in none of its findings:

```
$ python _r4_selfcheck.py 67137879 -> SUCCESS 9/9 blobs 0 CRLF
$ python _r4_selfcheck.py d82b5500 -> SUCCESS 1/1 blobs 0 CRLF   [so 9/9 is NOT a d82b5500 result]
```

I reproduced it exactly — `67137879` → 9/9, `d82b5500` → 1/1, `9ec1eb33` → 8/8 — and was
one step from reporting that round 2 had attributed a receipt to the wrong commit.

**It is not a defect.** `LANE-MCPRESEARCH-BUILD-R2.md:196` heads its evidence block
*"Run at `67137879`"*, and 67137879 is exactly the commit that produces 9/9. The committed
artifact is correct. The mis-attribution existed only in round 2's **ephemeral handoff
summary**, which banners the same receipts under *"Final gate at HEAD `d82b5500`"* — and a
handoff is not a repo artifact.

Recorded rather than deleted, for two reasons. It is the second time in two rounds that the
right answer was already on screen and unread (round 3 called this out about its own O1),
and it is a live warning: **audit findings and repo state can diverge when the audit reads a
summary the repository never contained.**

---

## O2 — a sampled-only aggregate published under a fleet label

### What was wrong

`cost-rank.json` carried its totals in a block named **`fleet`**:

```json
"fleet": { "servers_ranked": 16, "servers_total": 23,
           "tools": 707, "resident_bytes": 11645, "contingent_bytes": 603233 }
```

Every one of those sums covers the **16 sampled rows**, not the 23 mounted servers. Round 3
moved the scope into the per-row field (`resident_share_pct_of_sampled`) and into the
headline, and left the block one level up labelled fleet. `C5` — the guard round 3 built for
exactly this class — stayed green throughout, because **a control on the share cannot see
the scope of the aggregate that feeds it.**

### Measured, not inferred

```
ranked rows in cost-rank.json          : 16
sum(row.tool_count)               707  ==  fleet.tools            707
sum(row.resident_bytes)        11,645  ==  fleet.resident_bytes   11,645
sum(row.contingent_bytes)     603,233  ==  fleet.contingent_bytes 603,233
mounted servers in disposition.json    : 23
rows with NO sampled surface           : 7  [agent-mail, basic-memory, brightdata,
                                             deepwiki, figma, github, huggingface]
```

The aggregate reconciles **exactly** to the 16 ranked rows and to nothing wider. The 7
excluded rows carry `tool_count: null` — *not measured*, never zero — so every figure in
that block is a **lower bound on the fleet**.

### The blast radius, which is why this is not cosmetic

`707` had been copied into prose as a fleet total in **five** places, across documents round
3 never opened:

| site | what it said |
|---|---|
| `MCP-FLEET-AUDIT.md:15` | "per-server context cost is measured for 707 tools in both channels" |
| `MCP-CAPABILITY-AND-DISPOSITION.md:12` | COVERAGE: "§5 context cost MEASURED (707 tools…)" |
| `MCP-CAPABILITY-AND-DISPOSITION.md:256` | the table's **TOTAL** row |
| `MCP-CAPABILITY-AND-DISPOSITION.md:372` | the **DoD ledger**, item 3 — a PASS resting on it |
| `LANE-MCPRESEARCH-BUILD-R3.md:137` | round 3 calling 707 *"the fleet total"* |

The last one is the tell. **Round 3 re-asserted the fleet framing three sections after
fixing the share** — in the same document, describing the very linter it had just built.
That is not carelessness; it is what happens when the guard is attached to the narrow
symptom instead of the class.

### What changed

- `cost_rank.py`: the block is renamed **`fleet` → `sampled_aggregate`**, every summed value
  key gains a **`_sampled`** suffix, and the block carries an explicit `scope` string. The
  key name is the carrier because *a bare number gets copied into prose and its footnote
  does not* — the same argument round 3 made for the per-row rename, applied one level up.
- **C6** fails the run closed if the block is ever renamed back to `fleet` or a summed key
  loses its suffix.
- `refuted.round_3_wording` records the shipped JSON verbatim, with the measurement that
  refuted it. Nothing was deleted.
- The five prose sites now state `16 SAMPLED rows of 23`; §5 and the DoD ledger carry the
  supersede note and the settling experiment inline.
- **The DoD item moves from `PASS` to `PASS, scope disclosed`.** The measurement was always
  over the sampled subset; only the sentence changes.

### New gate — `scope_lint.py`

> **A paragraph quoting a sampled-only aggregate must also carry its scope.**

`claim_lint` cannot catch this, and not by oversight: it bounds a count against the server
it is attributed to, and **an aggregate is attributed to no server**. Its own notes record
`707` as the corpus's single false positive under the attribution rule it then removed. The
class needed its own reader.

The figures are **read from `cost-rank.json` at run time, never hardcoded**, so the lint
tracks the producer instead of drifting from it. Fenced blocks are excluded through
`claim_lint.paragraphs` — imported, never re-implemented, because two spellings of the same
split is how a control ends up measuring the speller (this lane paid for that once already
in `render_table`'s G1).

---

## Detector controls — both states

| control | mutation | observed |
|---|---|---|
| `cost_rank` **C6a** | `AGG_KEY` set back to the verbatim `"fleet"` | **fires** |
| `cost_rank` **C6b** | `AGG_SUFFIX` emptied, so summed keys go bare | **fires** |
| `cost_rank` C6 revert | both constants restored | green again — the fire was the mutation |
| `scope_lint` C1 | the **verbatim** `MCP-FLEET-AUDIT.md` sentence | flagged unscoped |
| `scope_lint` C2 | the corrected sentence | silent |
| `scope_lint` **C3** | `\| scholarly-access \| 8 \| 144 \| 4,707 \|` | **not** matched as `707` |
| `scope_lint` C4 | a real bare `707` | matched |
| `scope_lint` C5 | `707` inside a ``` fence | not linted |
| `scope_lint` C6 | an empty corpus | extracts 0 **and** fails closed |
| `scope_lint` C7 | `cost-rank.json` absent / block renamed | fails closed |
| `scope_lint` stale exemption | an `ALLOW` key matching nothing | fails the run |

**C3 earned itself.** The first matcher was `"707" in para` and it reported a site in
`DISPOSITION-TABLE.md` that does not exist — it was matching `4,707`, scholarly-access's
schema bytes. A substring of a larger number is not that number. The controls I had written
at that point (scope-token present / absent / fail-closed) all passed, because **none of
them could distinguish a real occurrence from a substring** — they measured the scope test,
never the extraction. The bounded matcher and C3 exist because of that miss, and the count
it corrected was **19 → 18**.

**The C6 mutations are applied to the module constants the producer builds its keys from,
not to a predicate in isolation.** A predicate can be correct while nothing calls it; C5 was
correct and called throughout the defect it could not see.

---

## Gate output

Run on **Python 3.11**, the version `mcp-audit.yml` pins, **at the commit** rather than
before it — the determinism job compares regenerated bytes against the *committed* blob, so
a pre-commit reading measures the fail-closed branch and not the result:

```
== mcp-audit CI gate @ 5684eac39d38 (win32, py 3.11.9) ==
  ok  inventory: 25 planned runs over 21 gates, 21 excluded with reasons
  ok  rc=0 (want 0)  cost_rank (invariants)      SUCCESS:cost-rank resident=11,645B contingent=603,233B
                                                 over 16 SAMPLED rows of 23 (a lower bound on the
                                                 fleet, never a fleet total)
  ok  rc=0 (want 0)  cost_rank (C5+C6)           SUCCESS:cost-rank self-test 8/8 controls behaved
  ok  rc=0 (want 0)  scope_lint (prose)          SUCCESS:scope-lint 28 aggregate quotation(s) over the
                                                 lane's docs, 0 unscoped, 1 declared exemption
  ok  rc=0 (want 0)  scope_lint (both-states)    SUCCESS:scope-lint self-test 9/9 controls behaved
  ok  rc=0 (want 0)  claim_lint (prose counts)   SUCCESS:claim-lint 35 attributed counts over 12 docs,
                                                 0 exceed their server, 3 declared exemption(s)
  ok  rc=0 (want 0)  claim_lint (both-states)    SUCCESS:claim-lint self-test 15/15 controls behaved
  ok  rc=1 (want 1)  dod_check @ 630bb8af (must FAIL)   FAILED:dod-check ['DoD3']
  ... 18 further gates, all rc as planned ...
  -- producer determinism --
  ok  cost-rank.json         byte-identical to the committed blob (12859 B)
SUCCESS:mcp-audit-ci-gate 25/25 gates behaved, 4/4 artifacts byte-identical to their producers
```

**25/25**, up from round 3's 23/23 — the two new runs are `scope_lint`'s. Repeated on
**3.12** and **3.14.6**: same line, artifacts byte-identical on all three, so the result is
not one runtime's dict ordering. `ci_gate --self-test` 8/8. `ruff check` clean and
`ruff format --check` reports 42 files already formatted, both at the CI-pinned **0.15.17**.

**Line endings.** `_r4_selfcheck` reports **11/11 blobs 0 CRLF** at the commit — all eleven
changed files, read from the stored bytes, which is what CI checks out. `git` printed
*"LF will be replaced by CRLF"* on commit; those describe the working copy, not the blob.
Deliberately not measured through a Git Bash pipe: that has already manufactured one false
CRLF finding in this lane.

## Residual — inline, none of it blocks

- **`scope_lint` bounds, it does not certify.** A paragraph carrying a scope token is not
  thereby correct; only the unscoped direction is decidable. It also only knows the three
  aggregate figures in `cost-rank.json` — a different aggregate published elsewhere is
  invisible to it. *Settling experiment:* extend `figures()` to every committed aggregate.
- **The true fleet-wide totals remain UNMEASURED** — unchanged from round 3, and now stated
  for the tool count and both byte channels as well as the share. Direction is known: the
  fleet figures are strictly **higher** than 707 / 11,645 / 603,233, and every published
  share of them is strictly **lower**. *Settling experiment:* an HTTP `tools/list` probe
  needing no stdio child, for the 7 unsampled rows.
- **One exemption is declared and printed on every run** — `LANE-MCPRESEARCH-BUILD-R3B.md`
  (this file) must quote the refuted framing to record it. Keyed to `(document, figure)`;
  a stale entry fails the run. Round 3's exemption was **removed**, not carried: its
  paragraph was corrected instead. An exemption is the last resort.
- **P3, the resource regression, is still untouched** and still out of this lane's file
  scope (the mitigation is a config mutation via `mcpapply`). *Likely (55-80%)* that it is
  the most operationally urgent open item — it rests on the documented commit-exhaustion
  mechanism, not on a freeze observed here.
- **CI-runner behaviour remains UNVERIFIED**, narrowed to the runner environment.
  *Settling experiment:* the first `workflow_dispatch` after merge.

## Confidence

**Almost certain (90-99%)** — that the aggregate was sampled-only: it reconciles exactly to
the sum over the 16 ranked rows and 7 of 23 disposition rows carry `tool_count: null`, both
computed from committed artifacts by a reader that does not import the producer. That C6 and
`scope_lint` fire when broken: each was observed red on a mutation of the real constant or
the verbatim shipped sentence, then green again on revert.

**Almost certain (90-99%)** — that the r4-selfcheck provenance concern is **not** a defect in
the repository: `LANE-MCPRESEARCH-BUILD-R2.md:196` names `67137879`, and that commit
reproduces 9/9.

**Likely (55-80%)** — that no further instance of this class survives in the lane's prose.
`scope_lint` clears all 12 documents, but it only knows three figures; a differently-derived
aggregate would not be seen.

**UNVERIFIED, inline** — that O2 as reconstructed here is the *same* finding the audit
recorded. Its second overclaim was **truncated out of the handoff** and I never saw its
text. What is not uncertain is that this is a real, independently reproduced overclaim of
the exact class the audit named. *Settling experiment:* recover the audit's untruncated
`overclaims` field and diff it against this section.

**Self-check.** The finding I was most confident in on arrival — the 9/9 provenance defect —
was the one that did not survive contact with the file, and it took one `Read` to refute. I
went looking for the audit's second finding and instead measured my way to a defect the
audit may never have named. Both are recorded, because a round that reports only its
successful hypothesis is the shape this lane keeps catching.
