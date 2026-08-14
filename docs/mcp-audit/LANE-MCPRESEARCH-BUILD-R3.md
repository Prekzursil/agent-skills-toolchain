# LANE MCPRESEARCH — BUILD round 3

**Re-entry after an independent audit returned PARTIAL on round 2.** It CONFIRMED one real
defect and one overclaim. This round closes both and does not re-litigate what passed.

Both findings landed in the same blind spot: **prose**. Every executable gate in this lane
stayed green through both, because neither number was computed by any producer. A figure
that only ever appears in a sentence has no gate, and this lane had 20-odd gates and no
reader for the one surface where its conclusions are actually published.

| # | audit finding | class | what changed |
|---|---|---|---|
| D1 | `search-hub` credited with more non-exa tools than it advertises in total | real defect — cross-row transposition | number corrected; class now caught by `claim_lint.py` |
| O1 | `cloud-hub is 60.1% of every-turn resident MCP cost` | overclaim — denominator is 16 of 23 rows | scope moved into the field name and the headline; `C5` fails the run if it is dropped |
| D2 | (found while fixing the above) round 1's superseded dead-surface figure carried no marker | documentation drift | supersede note added at the sentence |

---

## D1 — a cloud-hub number inside a search-hub sentence

Round 2 shipped this in its residual, about `search-hub`: *"no tool→backend map exists for
it, so its **113 non-exa tools** cannot be attributed by bytes"*.

*(That restatement is deliberately in plain prose, not backticks, so `claim_lint` attributes
it and prints it as a declared exemption on every run. Quoting it in a code span would have
hidden it from the gate instead — a visible exemption beats an invisible blind spot.)*

`search-hub` advertises **68** tools in total, so 113 cannot be a subset of it under any
reading. Two committed artifacts agree on 68 (`capability-matrix-r2.json`,
`disposition.json`), and `len(tool_names) == tool_count` holds inside the matrix itself.

**Provenance, measured rather than guessed:** `424 − 311 = 113` — the count of *cloud-hub*
tools **not** over a dead backend. The figure crossed a row boundary one paragraph after
`cloud-hub` was last named.

**Corrected figure, derived from the committed artifact:**

```
search-hub committed tool_count = 68   (len(tool_names) = 68)
  exa-shaped   (_exa suffix | ex_ prefix) :  14
  firecrawl_/fc_                          :  32
  tavily_/tv_                             :  11
  searxng_ + web_url_read                 :   4
  UNATTRIBUTABLE by name shape            :   7  ['agent_cancel_run', 'agent_create_run',
      'agent_get_run_output', 'agent_wait_for_run', 'deep_researcher_check',
      'deep_researcher_start', 'search_usage']
  sum                                     :  68
NON-EXA = 68 - 14 = 54
ok  buckets are disjoint and re-sum to the committed tool_count
```

So **54**, not 113. The derivation is controlled two ways — the buckets are asserted
disjoint, and they must re-sum to the committed `tool_count` or the script raises. I did not
take the audit's 54 on trust; this is an independent route to the same number.

**The residual got sharper, not just corrected.** Round 2 said the search-hub map was "not
done blind"; it could not say *why*. Now it can: name shape resolves **61 of 68**, and the
remaining **7** (`agent_*` ×4, `deep_researcher_*` ×2, `search_usage`) are genuinely
ambiguous — each could sit behind more than one backend. That is the concrete blocker, and
it is a better reason not to guess than the vague one it replaces.

**Blast radius: contained, and checked rather than assumed.** The figure drove no
disposition, no artifact byte, and no gate. `claim_lint.py` now scans all 11 lane documents
and finds no second instance.

---

## O1 — a share quoted without its denominator

Shipped in three places: `cost-rank.json`'s headline, `LANE-MCPRESEARCH-BUILD-R1.md`, and —
widest — `LANE-MCPRESEARCH-GROUNDING.md`, as *"60.1% of **the fleet's** every-turn resident
MCP cost"*.

The arithmetic was never wrong. **`6,998 / 11,645 = 60.1%` is exact.** The sentence was
wider than it: `11,645 B` is the sum over the **16 rows with a sampled tool surface**, not
over the 23 mounted servers.

**Why a fleet-wide figure is not simply published instead.** The 7 unranked rows
(`agent-mail`, `basic-memory`, `brightdata`, `deepwiki`, `figma`, `github`, `huggingface`)
carry `tool_count: null` in *both* capability matrices, with
`last_error: transport='http': no stdio command` — the producer enumerates by spawning a
stdio child, and an HTTP transport has none. Their tool names appear **nowhere in the
repository**: grep for a known bare name of each returns no lane artifact. So the fleet
denominator is **unmeasured, not unpublished**, and the honest statement of direction is that
the true fleet share of `cloud-hub` is *strictly lower* than 60.1% by an amount this lane
cannot compute from committed inputs.

The audit offered ~49.5% from a hand-count of its own session's tool listing. **I did not
adopt it.** Not because I doubt the arithmetic — it reconciles — but because it is
transcription from a session namespace, reproducible by no committed input, and dated to a
different day than the artifacts it would be divided into. Fixing a hand-typed number with
another hand-typed number is how D1 happened. It is recorded as an *estimate with its
provenance*, not promoted to a measurement.

**What changed, so the scope travels with the number:**

- the field is renamed `resident_share_pct` → **`resident_share_pct_of_sampled`**;
- the headline states the denominator inline and says what the unsampled rows are;
- `token_basis` gains an entry saying the true fleet share of any row is strictly lower;
- a `refuted` block in `cost-rank.json` keeps the round-2 wording auditable;
- **C5** fails the run closed if the headline loses its scope.

The rename is the load-bearing part. A docstring does not travel with a copied percentage —
and this producer's docstring *already* disclosed "16 of 23 rows" while the overclaim was
being published downstream from it. A field name does travel.

> **The uncomfortable detail.** The grounding lane's own quoted producer output, in the code
> block immediately above the offending sentence, reads `(16 of 23 rows sampled)`. The scope
> was on screen and the sentence dropped it. This was a **recall** failure, not a detector
> failure — the instrument was correct and unread — which is why the fix is a guard in the
> producer rather than a resolution to read more carefully.

---

## The new gate — `claim_lint.py`

Both defects lived in prose, so the guard reads prose. It cannot decide whether a number is
*right* — that is undecidable — so it enforces the weaker mechanical invariant that would
have caught this one:

> **A count attributed to server X can never exceed X's committed `tool_count`.**

Subset claims — *"23 advertised tools"*, *"4 tool names"*, *"157 tools over 7 backends"* —
are all strictly below their server's total and pass untouched. Only an **over**-count fires,
and an over-count is wrong under every reading of its sentence. That asymmetry is why the
measured false-positive rate on the shipped corpus is zero.

Three design decisions, each forced by a measurement rather than chosen up front:

1. **It reads paragraphs, not lines.** The defect's own line — `113 non-exa tools cannot be
   attributed by bytes.` — names no server at all; `search-hub` is two lines above it. A
   line-scoped reader finds **0 of 1** and reports the corpus clean. That version was written
   first and is retained as a control case, because a reader that cannot see the defect it
   was built for is not a weak gate, it is an inert one.
2. **A count with no server *before* it is left unattributed.** The first version fell back
   to the next name downstream, and that fallback produced this file's only false positive:
   `"707 tools"` in `MCP-FLEET-AUDIT.md` — the fleet total — charged to `cloud-hub` because
   cloud-hub happened to be named two sentences later. I removed the fallback rather than
   exempting the symptom; an exemption would have left the same trap armed for every future
   summary paragraph. Unattributed counts are reported, never silently dropped (16 of them).
3. **Fenced blocks are skipped.** Text inside ``` fences is captured command output. It is
   evidence, a program produced it, and editing it to satisfy a linter would be fabrication.

**`would_fit` distinguishes the two failure shapes.** A number that fits *another* server
named nearby is a cross-row transposition (D1: it reports `fits ['cloud-hub']`). A number
that fits none of them is a different **scope** entirely — a fleet or aggregate total (the O1
shape). That diagnostic fell out of the measurement; I did not design it in.

**Two declared use-vs-mention exemptions**, both printed on every run. Round 2's report and
this one must *quote* the refuted figure in order to record that it was refuted — the
contract says fix the sentence and record the refutation, never delete the wrong number so
the problem disappears. Rephrasing to slip past the matcher would leave the same text on the
page while the gate reported clean, so the exemptions are declared, keyed narrowly to
`(document, count, server)`, and a stale one fails the run.

---

## Detector controls — what proves each guard fires when broken

| control | mutation | observed |
|---|---|---|
| `claim_lint` on the **real** defect text | the verbatim round-2 paragraph, not an invented fixture | fires; attributes to `search-hub`; names `cloud-hub` in `would_fit` |
| `claim_lint` on the corrected text | 54 of 68 | silent |
| `claim_lint` line-scope control | the defect's own line, alone | attributes to nobody — the measured reason it reads paragraphs |
| `claim_lint` fleet-total control | a fleet count preceding every server name | not attributed, and counted as unattributed |
| `claim_lint` subset control | 23 tools of cloud-hub's 424 | silent |
| `claim_lint` fenced-receipt control | `999 tools` inside a fence | not linted |
| `claim_lint` exemption narrowness | same figure, different document | **not** exempted |
| `claim_lint` empty roster | roster stripped | cannot silently certify |
| `claim_lint` zero-extraction | — | fails closed: 0 claims over 11 docs is a broken matcher, not a clean corpus |
| `claim_lint` stale exemption | an `ALLOW` key matching nothing | fails the run |
| `cost_rank` **C5** | `HEADLINE_TMPL` replaced with the **verbatim refuted round-2 wording** | fires |
| `cost_rank` C5 revert | mutation reverted | green again — so the fire was caused by the mutation, not a sticky failure |
| `cost_rank` rename | any row still carrying the bare `resident_share_pct` | absent |

Two of these earned themselves rather than being written for completeness:

- The **line-scope** control is the `manifest["events"][ev]` shape from this repo's own
  ledger — a probe that passes while measuring the wrong collection. Mine would have printed
  a clean corpus while the defect it was built for sat in that corpus.
- **C5's required tokens are structural phrases** (`"16 SAMPLED"`, `"of 23 rows"`), not the
  bare digits `16` and `23`. Bare digits can appear inside an unrelated byte count and let
  the check pass for the wrong reason.

## Gate output

Run on **Python 3.11**, the version `mcp-audit.yml` pins, with `ruff 0.15.17`, the version
CI pins:

```
== mcp-audit CI gate (win32, py 3.11.9) ==
  ok  inventory: 23 planned runs over 20 gates, 21 excluded with reasons
  ok  rc=0 (want 0)  cost_rank (invariants)      SUCCESS:cost-rank resident=11,645B contingent=603,233B over 16 ranked rows
  ok  rc=0 (want 0)  cost_rank (C5 both-states)  SUCCESS:cost-rank self-test 4/4 controls behaved
  ok  rc=0 (want 0)  claim_lint (prose counts)   SUCCESS:claim-lint 34 attributed counts over 11 docs, 0 exceed their server, 2 declared use-vs-mention exemption(s)
  ok  rc=0 (want 0)  claim_lint (both-states)    SUCCESS:claim-lint self-test 15/15 controls behaved
  ok  rc=1 (want 1)  dod_check @ 630bb8af (must FAIL)   FAILED:dod-check ['DoD3']
  ... 18 further gates, all rc as planned ...
  -- producer determinism --
  ok  disposition.json / overlap-report.json / DISPOSITION-TABLE.md byte-identical to the committed blob
```

All **23** planned runs matched their expected exit code, including the both-states run that
must FAIL. `ruff check` clean; `ruff format --check` reports 41 files already formatted.
Every changed file is **0 CRLF**, verified by a byte-wise read rather than a shell pipe —
this lane has already been bitten once by a Git Bash pipe re-inserting CR and manufacturing
a false CRLF reading.

The determinism job for `cost-rank.json` **failed before the commit** and that is the guard
working: it compares the regenerated bytes against the *committed* blob, and the regenerated
artifact had not been committed yet. It is green in the same run once the commit lands, which
is the receipt quoted in the handoff.

## Residual — inline, and none of it blocks

- **`claim_lint` bounds, it does not certify.** A count that *fits* its server is not thereby
  verified — only over-counts are decidable this way. It also cannot check the 7 unsampled
  servers at all (no committed surface to compare against) and leaves 19 counts unattributed
  because no server is named before them. Both numbers are printed on every run so the blind
  spot is visible rather than implied. *Settling experiment for the unsampled 7:* an HTTP
  `tools/list` probe that does not need a stdio child.
- **The true fleet-wide resident share is still UNMEASURED.** Direction is known (strictly
  below 60.1%); magnitude is not. The audit's ~49.5% is recorded as an estimate with its
  provenance, not adopted. *Settling experiment:* enumerate the 7 HTTP rows over their own
  transport and commit the names, at which point the denominator becomes computable and
  `resident_share_pct_of_sampled` can gain a genuine fleet sibling.
- **`dead_surface_pct` is still null for `search-hub`**, and now for a measured reason: name
  shape resolves 61 of 68, and 7 names are genuinely ambiguous. Null means *not attributed*,
  never zero.
- **P3, the resource regression, remains untouched and out of this lane's file scope.** The
  mitigation is a config mutation via `mcpapply`. *Confidence it matters: likely (55-80%)* —
  it rests on the documented commit-exhaustion mechanism, not on a freeze observed here.
- **CI-runner behaviour remains UNVERIFIED**, narrowed to the runner *environment*: green
  locally on the pinned interpreter and the pinned ruff. *Settling experiment:* the first
  `workflow_dispatch` after merge.
- **A `POTENTIAL-CREDENTIAL` artifact notice fired**, id `sha256:14c745ad1f24` — the same id
  rounds 1 and 2 recorded, report-only. Surfaced for the owner. No credential was read,
  printed, rotated or edited (AGENTS.md §9).

## Confidence

**Almost certain (90-99%)** — that `search-hub` is 68 and the corrected non-exa figure is 54:
two committed artifacts agree, the matrix is internally consistent
(`len(tool_names) == tool_count`), and the split re-sums with a disjointness assertion.
That `6,998 / 11,645 = 60.1%` is arithmetically exact and its denominator is 16 rows: read
directly from the artifact the producer writes. That both guards fire when broken: each was
observed red on the *verbatim* defect it exists to catch, then green again on revert.

**Likely (55-80%)** — that no third instance of either class survives in the lane's prose.
`claim_lint` clears all 11 documents, but it can only see over-counts that follow a server
name outside a code span; an under-count that is simply wrong is invisible to it.

**UNVERIFIED, inline** — CI-runner environment (settles on first dispatch); the true
fleet-wide denominator (settles by enumerating the 7 HTTP rows).

**Self-check.** The one thing I might be criticised for *not* doing is publishing the ~49.5%
fleet figure the audit computed. I decided against it deliberately: it is a hand-count of a
session namespace, from a different day than the artifacts it would divide into, reproducible
from no committed input. Fixing a hand-typed number with another hand-typed number is exactly
how D1 happened, and a second unsourced figure would have been a *new* overclaim wearing the
correction's clothes. The direction of the error is stated instead, which is what the evidence
supports.
