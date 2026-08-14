# SLOP — BUILD lane, round 6

Round 5 shipped two commits (`f725baf4`, `9cc80f55`). This round fixes what did not survive
re-derivation, and ships the gate that would have caught it.

**Disclosed first, because it changes how this round should be read: I did not receive round 5's
audit.** The re-entry brief said a verifier confirmed defects last round, but the prior-round
payload was truncated mid-JSON inside round *4*'s audit record, so round 5's findings never
arrived. I checked for them on disk before assuming: no `_AUDIT-SLOP-R3/4/5` artifact exists, and
this lane's auditors return structured output rather than files. **So the defects below were
re-derived independently rather than taken from a list.** Two consequences, stated rather than
discovered later: a defect round 5's auditor found that I did not re-derive is still open and
unknown to me, and where I confirm round 5 was right, that is a second opinion rather than a
repetition.

The first thing I did on entry was read what already landed. `_r5_*` files and a full
`SLOP-BUILD-R5.md` were already on disk and already committed — a round that, on the brief's
numbering, had not happened yet. Re-running it would have overwritten committed evidence.

---

## What this round found

Three items. All three are the same shape this lane has produced in every round: **the code is
right and the sentence is wider than it.** Round 4's audit put it exactly this way, and it held
again.

| # | finding | kind | status |
|---|---|---|---|
| F1 | `SLOP-BUILD-R5.md` DoD-1 row published `d-zero=18` where the committed receipt says **23**. The published parts summed to **300** against the **305** asserted in the same sentence, which also cited `partition_total: true` | wrong number, self-contradicting | **FIXED** in place, original preserved and marked |
| F2 | the same doc said "four of its **six declared inputs**" while its own table said "4 of 12" and the receipt says `n_inputs_resolved: 12`; and "inputs" is not what the extractor measures | overclaim + wrong noun | **FIXED** in place, correctly scoped |
| F3 | my own refuted-wording marker was **inert on live content** — it suppressed nothing, and the preserved wrong number was passing for an unrelated reason | my detector | **CAUGHT AND FIXED** before commit |
| F4 | the gate **indexed its own output as a receipt**, so a document could be confirmed by the gate's previous reading of that same document — a false negative, the dangerous direction | my detector | **CAUGHT AND FIXED** before commit |

### F1 — the number that disagreed with its own receipt

`_r5_reclassify.out.json` records `histogram` `d-zero: 23`, and `row_count` 305 ==
`untracked_total` 305 with `partition_total: true`. The report transcribed `d-zero` as 18. The
row therefore asserted a total partition in the same breath as four parts that sum to 300, and
disagreed with the receipt it cited by name.

**The classifier was correct and the partition really is total.** Only the transcription was
wrong — which is precisely why nothing caught it: every probe, control and exit code was green.

### F2 — "six declared inputs", and what the extractor actually measures

The receipt says 12. The doc's own table two screens earlier says "4 of 12". The prose said six
and printed a six-line block that read as the complete set — a self-contradiction inside one file.

Re-deriving it turned up the deeper problem. `_r5_reclassify.py` resolves inputs with
`FILE_LIT`, a regex over **quoted file literals**. Re-run against that producer it returns **13**,
including the producer's *own output* (`_secfirst_selfaudit.out.json`) and the same catalogue
under two spellings (`WORK-UNIT-CATALOG.json` and `command-center/WORK-UNIT-CATALOG.json`). So the
denominator is a literal count, not an input count, and "declared inputs" overstates the
instrument.

**The K7 verdict itself is sound, and I confirmed it by a different route than round 5 used.**
Round 5 inferred the inputs from a regex; I read the producer. `platform/architecture/_secfirst_selfaudit.py:27-31`
does `json.load` on all four untracked receipts. They are genuine inputs, the file genuinely is
not clone-regenerable, and bucket (c) really is 2 files rather than 3. Correctly scoped: *four of
the file paths this producer names are untracked, and all four are read as inputs at lines 27-31.*

### F3 — my own marker was inert, and the receipt said so

To keep refuted wording without the gate flagging it forever, I added a rule: a claim on a line
carrying the token `REFUTED` is recorded as a preserved refutation, not a violation. Its
both-states control passed on a fixture. The gate went green.

Then the receipt printed `preserved_refutations` as an **empty list** — while the document
visibly contained a preserved refutation. A run that reports two things which cannot both be true
is a detector failure, not a finding. Cause: I had wrapped the blockquote so the word `REFUTED`
sat on the line *above* the struck number. The marker matched nothing; the preserved wrong
histogram was passing only because that line happened to carry no total and no receipt reference.

Fixed by putting the marker on the same line as the text it covers. It is now load-bearing and
provably so: that line yields `DISAGREE` with `receipt_mismatch` `{"d-zero": {"doc": 18, "receipt": 23}}`
and is excluded **only** by the marker, while the corrected row stays live-checked. The
suppression path is now exercised by real content, not just by a fixture.

### F4 — the gate was reading its own output as evidence

The receipt glob is `_*.out.json`, and the gate writes `_r6_transcript.out.json`. So on its second
run it indexed **its own output** — a file that records the `key` and `doc_value` of every claim it
has ever seen — and offered those back as receipt evidence. A document could then be confirmed by
the gate's own earlier reading of that same document.

That is a **false negative**, which is the dangerous direction: it makes disagreements disappear
rather than inventing them. Caught because the round-6 report documented the KV syntax literally,
the gate parsed its own documentation as a claim, and the receipt it cited as authority was
itself. Fixed by excluding the probe's own output from the index; `receipts_indexed` drops 83 → 82,
which is the visible tell that the exclusion is real.

Both F3 and F4 are mine, both were found by reading the instrument's output rather than its exit
code, and both were fixed before commit. Recording them because a round that reports only other
people's defects is not measuring itself.

---

## What was shipped: a gate for this defect class

`_r6_transcript.py` — extracts published claims from every `SLOP-*.md` in this directory and
compares each against the committed `_*.out.json` receipts beside it.

* **KV** — a backticked `` `<key>: <value>` `` must match that leaf key in a receipt (the one named
  on the line, when one is named). Written here with angle brackets on purpose: spelled literally,
  the example is itself a claim and the gate flags its own documentation. It did.
* **HISTOGRAM** — a `histogram k=n / k=n …` line must (a) **sum** to the total asserted on the same
  line and (b) match the named receipt's histogram.

**Use-vs-mention is the hard part, and this lane has paid for it three times.** A document that
quotes a superseded value is mentioning it, not asserting it. So a disagreement is a *candidate*,
adjudicated in `_r6_transcript_baseline.json` with a written reason — the same baseline convention
this lane already ships for published commands. Three candidates were adjudicated, each read
before being written down:

| doc | key | why it is not a defect |
|---|---|---|
| `SLOP-BUILD-R2.md` | `quiet_citer_count` | presentation — a count and a verdict in one backtick (`0 / PASS`); the asserted count is 0 and agrees |
| `SLOP-BUILD-R2.md` | `tracked_file_dirty_before` | elision — the value is visibly cut with `…`; the doc's prefix matches the receipt |
| `SLOP-BUILD-R5.md` | `lint_files_n` | a **deliberate quote of a broken reading**, in the sentence that discloses the detector was self-contradicting. Flagging it would penalise the disclosure |

I did not teach the comparator to normalise the first of these away. Accepting any
`/`-separated token would let a wrong number pass whenever a right one sits beside it, and false
negatives are the dangerous direction.

### Controls — all eight, both states

| control | what it proves | reading |
|---|---|---|
| T1 known-broken (×2) | the verbatim pre-fix text must fire on **both** the sum check and the receipt check | fires |
| T2 known-good | the corrected text must be silent | silent |
| T3 uuid4 key | an unknown key reads `UNCHECKABLE`, never a silent agree — so "no violations" cannot mean "looked nothing up" | holds |
| T3 real key / wrong value | a known key with a wrong value must read `DISAGREE` | holds |
| T4 fail closed | zero claims extracted is a shape change, not a pass | holds |
| T5 marker suppresses / T5 marker needed | the **same** text must violate without the marker and stop violating with it | both hold |

T1 and T2 run against fixtures **held in the probe source**, not against the live document. A
control that read the live file would go silent the moment the defect was repaired and could no
longer prove the gate fires at all — the inert-control shape this repo has been bitten by.

---

## DoD status

| DoD item | verdict | evidence |
|---|---|---|
| 1. every candidate classified into four buckets with evidence | **PASS, inherited from round 5 and not re-measured at this rev** | `_r5_reclassify.out.json` @ `5423de0f`: `row_count: 305` == `untracked_total: 305`, `partition_total: true`, five classifier controls PASS. **Not re-run on purpose** — see the scope note below |
| 2. bucket (b) committed rather than deleted | **PARTIAL — unchanged, and deliberately not re-litigated** | the dangerous subset is empty by construction; the weak-signal remainder is other lanes' in-flight evidence. Round 4's audit independently confirmed that refusing to sweep is correct and that the cost has grown. Round 5 costed it per lane. **In this lane's own scope the gap is zero** — every file under `command-center/slop-report/**` is committed by this round |
| 3. bucket (c) deletions each backed by a shown regenerating command | **PASS** | 0 bucket-(c) files deleted by any round, so no deletion lacks backing; round 5 executed the full cycle on a real candidate with a verified restore. This round deleted nothing |
| 4. frozen-evidence directories untouched | **PASS, re-proven at this lane's start and end** | `_r5_frozen.py` re-run, rc 0, `FROZEN-UNTOUCHED-PROVEN`: 9/9 byte-identical to their HEAD blobs, fail-closed counts 7 + 2, live-detector control firing at 5 lines while both frozen dirs read 0, both-states comparator check |

I reused round 5's frozen prober rather than writing a fourth one. Its receipt is committed, so I
restored it with `git checkout --` after reading it; nothing uncommitted was overwritten.

---

## Scope limits and residuals — stated inline, not folded into a pass

* **The gate compares a rev-pinned published value against a receipt's CURRENT content.** Reports
  here pin numbers to the rev they were measured at; receipts get regenerated. Regenerate a
  receipt and correctly-pinned prose starts reading as a violation. **This is why I did not re-run
  the classifier this round** — doing so would have overwritten round 5's rev-anchored receipts
  and invalidated the very line I had just corrected. Settling experiment: key the comparison on
  the receipt's own `rev` field and compare only same-rev claims.
* **DoD-1 is inherited, not re-measured.** Round 5 measured it at `5423de0f`; the untracked
  population has moved since — **305 at `5423de0f`, 299 here** — and `HEAD` moved four times under
  this lane (`f25b429f` → `f0386cbe` → `6698065f` → `a71a7c0a`) while siblings committed.
  Nothing here claims the partition still holds at this rev. Settling experiment: re-run
  `_r4_buckets.py` at a quiesce point, writing to a fresh snapshot rather than over the pinned
  receipts.
* **The gate's corpus is this lane's own reports** — 9 documents and the receipts beside them. It
  is not a general fact-checker, and it only sees two claim shapes. Free-prose numbers like F2's
  "six declared inputs" are **invisible to it**; that one was found by hand and remains a gap.
* **Baseline granularity is (doc, key), not (doc, line)**, because line numbers move on every
  edit. So baselining a key silences it for that whole document. Acceptable at 38 claims across
  9 documents; if the corpus grows, key the rows by a content hash of the claim.
* **UNVERIFIED, unchanged rounds 2-6:** whether any committed receipt digest-locks carried probe
  bytes. Still the reason no evidence file is reformatted.
* **NOT-CHECKED:** the ~84 non-ruff `quality.yml` steps. Nothing here claims main is green — only
  that these named gates pass at the revs named.
* **Round 5's audit findings are unknown to me** (above). Anything it raised that I did not
  independently re-derive is still open.

## What this round did NOT do

* Did not sweep, format, or commit any file outside `command-center/slop-report/**`.
* Did not delete anything at all.
* Did not re-run `_r5_reclassify.py` or `_r4_buckets.py` (would overwrite pinned receipts).
* Did not touch the three `_r2_`/`_r3_` receipts that were already dirty at lane start.
* Did not re-litigate R0 (`git clean -Xdf` banned), R11 (`skills/` ↔ `.agents/skills/`
  sanctioned), R12 (`_advver_M14` is outside this repo), or the `NUL` writer.
