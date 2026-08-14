# P2NEXT — BUILD lane, round 3: the deferred anchor hole, closed

COVERAGE: every claim below is measured by an executed probe named beside it. Two things are
NOT measured and say so inline: whether the 42 rail-blocked units would PASS a Codex review,
and whether `codex login` clears agent-identity registration (owner-only credential write).

## 0. Headline: my own brief was stale, and the plan it carried was already built

The grounding I was handed ranks "build the C5 content floor, but close the claim_gate hole
first" as the only genuinely unbuilt rail-independent work. **Both halves were already
committed at `00d0a311`** ("two gates certified reviews they never read -- close both, with
both-states proof"), which shipped the `no-source-probe` rule, the C5 notes floor, 5 new tests
and 7 new self-test cases. Re-deriving it would have rebuilt a delivered, CI-wired result.

The lane brief is stale on its two headline numbers as well, and this remains true this round:

| brief says | committed truth | what the brief's figure actually counted |
|---|---|---|
| 48 self-declared BLOCKED | **52** | round-1 framing; no committed derivation holds 48 |
| 43 of 47 name cross-vendor | **42 of 52** | TAG OCCURRENCES — a receipt with three review tags counted three times |

Both are already marked superseded in `command-center/CROSS-VENDOR-RAIL-STATUS.md`.

## 1. Definition of Done — verified this round, not cited

Re-derived from COMMITTED BLOBS by `rail_count_gate.py`, which fails on disagreement:

```
FRESH DERIVATION: 52 blocked units, 42 rail-blocked, 10 satisfiable now, 10 of those reviewed;
                  catalog carries 2007 units, 449 of them READY
```

| DoD item | State | Evidence |
|---|---|---|
| the blocked set split cross-vendor vs any-independent-reviewer | **PASS** | `VENDOR-SATISFIABILITY.json` @ HEAD: 52 rows, `Counter({'RAIL_BLOCKED': 42, 'SATISFIABLE_NOW': 10})` |
| receipt text quoted per unit | **PASS** | every row carries verbatim `reviewer_requirement` + `blocked_on` |
| satisfiable subset reviewed and receipted | **PASS** | 10 of 10, each `verdict=PASS, independent=true`, notes 1027-2092 chars |
| rail-blocked remainder counted exactly | **PASS** | 42, gate-enforced against the published doc |

No same-vendor review was substituted anywhere a receipt demands cross-vendor. The 42/10 split
is unchanged by this round's work.

## 2. What this round shipped: a timestamp was a valid evidence anchor

`00d0a311` disclosed one hole it deliberately did not fix — claim_gate's evidence-anchor rule
was `https?://\S+|\S+:\d+`, and `\S+:\d+` is satisfied by anything with a colon and a digit.
Its stated reason for deferring: "one behaviour change to a shared skill per round, and that one
has no measured false-negative yet." This round supplies the measurement and closes it.

### The false negative was wider than the disclosed timestamp

`_d1_anchor_corpus.py` section A — the CURRENT rule accepted **9 of 9** non-references:

```
current=PASS  candidate=fire  '2026-08-12T05:15:00'      <- the disclosed case
current=PASS  candidate=fire  '05:15'                     clock time
current=PASS  candidate=fire  'ratio 3:1'                 a ratio
current=PASS  candidate=fire  'v1.2:3'                    a version number
current=PASS  candidate=fire  'measured at 2026-08-12T05:15:00 by the reviewer'
-> current accepts 9/9 non-references; candidate accepts 0/9
```

A CONFIRMED verdict could satisfy its evidence requirement by carrying the time it was written.

### The obvious fix is wrong in the other direction — measured before shipping

The strict shape already in-tree at `rail_count_gate.py:133` requires a file extension. Section
B measured what that costs:

```
-> ext-required would REJECT 3 real anchors: ['Makefile:12', 'Dockerfile:5', 'LICENSE:3']
-> CANDIDATE      would REJECT 0 real anchors: []
```

So the shipped rule tests whether the head names a **path** (contains a separator, or carries an
extension with at least one letter, or is a known extension-less filename), not whether it has a
dot. `C:\...\claim_gate.py:113` is covered explicitly — this estate is Windows.

### Both-states proof at the CLI, one unmodified probe (`_d3_timestamp_anchor.py`)

```
  ok    A real file:line anchor:          old exit 0 (want 0), new exit 0 (want 0)
  ok    B obvious non-evidence (control): old exit 1 (want 1), new exit 1 (want 1)
  ok    C bare timestamp (the defect):    old exit 0 (want 0), new exit 1 (want 1)
```

**B is the load-bearing control.** Without it, C flipping would be indistinguishable from "the
old gate did nothing at all". B fires in BOTH states, so the anchor rule was demonstrably live
while it was silent on C — a real hole, not a dead instrument.

### The fix is mutation-covered, including the old bug re-injected

`test_claim_gate_mutations.py` 6 -> 8 mutations, **8/8 killed**, among them:

```
KILLED   anchor head need not name a file (the pre-fix `\S+:\d+` behaviour)
KILLED   extension need not contain a letter (a version reads as a filename)
```

The first re-injects exactly the behaviour this round removed and requires the suite to go RED.
Tests 35 -> 39; the `no-evidence-anchor` self-test fixture was changed from "I recall seeing it"
to the timestamp, because a fixture that fires under the old AND new rule proves the instrument
runs, not that it discriminates.

## 3. My own probe was wrong first, and its control caught it

`_d1` initially reported "4436 evidence strings, 0 anchored". That shape is self-contradicting,
so `_d2_registry_shape.py` was written to read the registries directly: `evidence` is a **string**
in `command-center/CLAIM-REGISTRY.json` and a **list** in claim_gate's fixtures. Iterating the
string form yields CHARACTERS — the 4436 were 4436 single characters, none of which can contain
`file:line`. Fixed, and section C now reports 24 evidence strings, 3 anchored, **0 newly
rejected** by the shipped rule.

`_d2` deliberately re-implements `git_show` rather than importing `_d1`'s (the dup-guard hook
flagged it): a control that shares its subject's reader inherits the defect it exists to catch.
`_d1`'s first run did carry a reader bug — a cp1252 decode that silently dropped files.

## 4. Honest residuals — disclosed, not blocking

- **The corpus control is small.** Section C rests on **3** anchored strings in 2 committed
  ledgers. Section B (10 hand-built anchors) carries the false-positive verdict, not section C.
  Settling experiment: run the shipped rule over a corpus of real EVIDENCE blocks once more
  ledgers exist. [likely 55-80%] that no further false positive exists.
- **`CLAIM-REGISTRY.json` uses `verifier_probe`; claim_gate reads `verify_probe`.** Found while
  measuring, NOT fixed here — it is a schema question for that registry's owner, not an anchor
  question, and claim_gate is not run over it in CI. UNVERIFIED whether this is drift or two
  deliberate schemas.
- **C5's resolvable-anchor half stays ADVISORY.** 0 of 10 receipts carry a resolving anchor;
  enforcing it would turn CI red on every existing receipt and the only fix would be rewriting
  ten reviews this lane did not perform. Unchanged from `00d0a311`.
- **Windows-local green is not CI green.** ~9 of ~25 steps run here.

## 5. The two owner decisions still price together

Unchanged and still the decisive fact: all 10 reviewed units remain blocked on completion
condition 11, which `receipt_schema_gate.py:515-527` hard-rejects while nothing in production
sets `manifest_registration.registered`. **`codex login` buys review capacity for 42 units and
delivers zero of them.** Pricing it alone overstates its value. Neither was attempted: the first
is a credential write (AGENTS.md §9), the second a contract collision.

No READY units were built — all 449 name a cross-vendor reviewer, so building them manufactures
more un-reviewable work behind the same two blockers.
