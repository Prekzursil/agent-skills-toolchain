# MCPRESEARCH round 3 — defect closure ledger

> **PARTIALLY REFUTED BY ROUND 4.** A verifier confirmed that this document's line-endings
> paragraph states a falsehood: the `.md`/`.json` blobs do **not** carry CRLF, and `278` /
> `840` are LINE counts. The refuted text is preserved in place, in a blockquote, with the
> correction beneath it — see *"A control that disagreed — and the round-4 correction"*.
> Everything else here (E1/E2/E3 and the nine gates) survived independent re-execution.
> Full ledger: [`ROUND4-DEFECT-CLOSURE.md`](ROUND4-DEFECT-CLOSURE.md).

Measured 2026-08-13, worktree `C:/Users/Prekzursil/source/ast-integrate`.
Companion to `MCP-CAPABILITY-AND-DISPOSITION.md` §11 and `ROUND2-DEFECT-CLOSURE.md`.
One row per defect, each **reproduced against a pinned commit first**, then fixed, then
red-proofed in both states.

COVERAGE: three defects reproduced BEFORE their fix against the round-2 blob `630bb8af`,
fixed, and each fix proven to fire in the known-broken state. Nine gates re-executed with
their **real** exit codes. One round-3 hypothesis was investigated and **REFUTED** — it is
recorded below rather than dropped. **NOT measured:** the cost of the 7 rows that have no
stdio child (the residual, disclosed inline); the `mcpctl` / `monitorcore` wiring (outside
this lane's file scope); the other ~23 CI steps.

If it still reads this way, the unit died before measuring anything and no verdict here
may be cited. — *it does not; every line below carries executed output.*

## Provenance of this round's defect list — read this first

**The round-2 verifier's report did not reach this lane.** The handoff truncated inside
the *round-1* audit text, so rounds 2's confirmed findings were unavailable to me. Rather
than guess at them, I ran the settling experiment round 2 itself named — *"another
independent verify pass"* — and re-derived a defect list by execution. Everything below is
therefore **my own pass over round 2's output**, not a transcription of a verifier's.

Consequence, stated plainly: if the round-2 verifier confirmed a defect that my pass did
not independently rediscover, **it is still open and this document does not cover it.** The
settling experiment is to re-run the verifier and diff its list against these three. What I
can say is bounded and checkable: the three below were each reproduced against a committed
blob before being fixed.

---

## The three defects

| # | defect | class | status |
|---|---|---|---|
| E1 | 5 rows shipped `call_verified: true` **beside** `last_error: "transport='http': no stdio command"` | self-contradiction in a machine-readable artifact | **CLOSED**, invariant + 5-mutation red-proof |
| E2 | "a row of the shipped table **is** an injectable snapshot" — true for 16 of 23 rows | overclaim, inside the D2 fix itself | **CLOSED**, sentence scoped + `liveness_basis` per row |
| E3 | `dod3` skipped every row without a handshake, so DoD3 reported "per-server context cost measured" while 7 of 23 carried no cost | a control that cannot distinguish the two hypotheses | **CLOSED**, predicate widened + a second control that fires |

All three are **one defect family, and it is the same family as round 1's**: a claim and
the thing it describes drifting apart. Round 1's version was a legend drifting from its
field. Round 3's version is subtler and worth naming — **round 2's two fixes drifted
against each other.** D1 widened the meaning of *verified* to the union (21 rows); D2's
prose, its invariant's scope, and `last_error` all kept the older, narrower meaning (16
rows). Each fix was checked against its own evidence; neither was checked against the
other.

---

## E1 — verified and failed, asserted in the same object

### Reproduced against the round-2 commit, pinned (`_r3_redproof_liveness.py` part A)

The reproduction reads `git show 630bb8af:…disposition.json`, **not** `HEAD` — reading
HEAD would erase the defect the moment the fix lands, which is the self-defeating shape
`_r2_reproduce.py` v1 already shipped once.

```
== PART A: assert_liveness_consistency, BEFORE = 630bb8af ==
  BEFORE verified-and-errored rows (5): ['agent-mail','basic-memory','figma','github','huggingface']
  BEFORE rows with no liveness_basis: 23/23
  BEFORE invariant fires: True
  AFTER  verified-and-errored rows: 0
  AFTER  invariant silent: True
```

It fails closed in **both** directions: if the BEFORE state ever stops exhibiting the
defect, the detector is broken and the run goes red instead of printing a reassuring
SUCCESS.

**Why this is a defect and not a labelling quibble.** `last_error` is one of the four
fields `mcpctl.matrix.Liveness` reads, and the whole point of this producer is that its
rows are injectable into `mcpctl` (and, next, `monitorcore`'s pane — the second consumer
the grounding lane identified). Inject one of those five rows and a downstream reader gets
a server that is simultaneously **verified working** and **carrying a liveness error**,
with every measurement field null. The string itself is not even an error: *"no stdio
command"* is a statement that there is nothing to spawn.

### Fixed

`liveness_view()` splits the prober's `last_error` into two fields that cannot be confused:

* `last_error` — a stdio handshake that was **attempted and failed**.
* `probe_note` — the categorical *"there is no child to sample"* case.
* `liveness_basis` — on **every** row: either `stdio child sampled at handshake time`, or
  `not-measured: <reason>`.

### Made unrepresentable, not merely corrected

`assert_liveness_consistency()` aborts the run on four shapes: a verified row carrying a
`last_error`; a row with no basis at all; a basis claiming a measurement while
`pid`/`rss_bytes`/`tool_count` are null; and a `not-measured:` with no reason. A fifth
mutation covers the inverse — a full snapshot mislabelled `not-measured:` — because without
it the string would be a free pass on any row.

```
== PART B: one mutation per clause ==
  baseline (a well-formed measured row) -> silent  OK
  mutation verified-and-errored       -> invariant fired  OK
  mutation no-liveness-basis          -> invariant fired  OK
  mutation claims-measured-but-null   -> invariant fired  OK
  mutation reasonless-not-measured    -> invariant fired  OK
  mutation measured-but-labelled-not  -> invariant fired  OK
```

`verified-and-errored` is the **literal round-2 row shape**. The invariant fires on it.

Dispositions unchanged: `DISABLE 1 / INVESTIGATE 2 / KEEP 20`. This was a disclosure fix
and it must not have moved a verdict — it did not.

---

## E2 — "a row of the shipped table IS an injectable snapshot"

Measured over `630bb8af`: true for the **16** handshake-verified rows, false for the other
**7**, whose `pid`, `rss_bytes`, `tool_count`, `name_bytes` and `schema_bytes` are all
null. An injection built from one of those rows carries four nulls — *exactly* the
"unmeasured renders as nothing" hole that `mcpctl.matrix.Liveness` documents itself as
guarding against, and exactly the hole D2 was written to close. The fix's own sentence
reintroduced the defect class one level up.

The same drift shows up a third time, in the wording of D2's evidence: round 2 reported
part B as *"all four non-null on every verified row (16/16)"*. By then the artifact's own
legend defined *verified* as the union — **21** rows. Part B only ever examines the 16
stdio-handshake rows; the other five cannot pass it and are never looked at. **16 is the
right count for the right set** and the check was never wrong — the *word* was borrowed
from the sibling fix.

**Fixed by scoping the sentences and giving the machine the distinction.** Both refuted
wordings are recorded in place (`ROUND2-DEFECT-CLOSURE.md` §D2 and
`MCP-CAPABILITY-AND-DISPOSITION.md` §9) rather than deleted, `_inject()`'s scope is stated
in its docstring and printed at run time as `stdio-handshake rows`, and `liveness_basis`
now tells a reader per row whether an injection is meaningful.

**Residual, disclosed not closed (uncertain, 20-55% that it is worth building):** those 7
rows still have **no cost measurement**. Settling experiment: an HTTP
`initialize`+`tools/list` against each endpoint, or a dump of the client-side tool
registry. Neither is a stdio spawn, so neither is reachable from this producer as built —
which is why the honest move was to make the gap loud rather than to quietly widen a
filter.

---

## E3 — the DoD3 control could not distinguish its two hypotheses

Round 2's `dod3` opened with `if not r.get("handshake_verified"): continue`. Its negative
control blanked `rss_bytes` on a **measured** row — so it only ever exercised the branch
that was already covered. A silently-unmeasured row could not make it fire, because such
rows were skipped before the predicate ran. The control passed, and passing meant only
that the predicate executed.

### The discriminating comparison (`_r3_redproof_liveness.py` part C)

The round-2 predicate is re-implemented **verbatim** in the red-proof, so this is a
measurement and not a recollection:

```
== PART C: does the widened DoD3 see what the round-2 DoD3 could not? ==
  round-2 rows with a null cost field: 7/23 ['brightdata','deepwiki','agent-mail']...
  round-2 predicate on those rows -> 0 problems (PASS = blind)
  round-3 predicate on those rows -> 7 problems
  round-3 predicate on the CURRENT rows -> 0 problems
```

### And the ledger itself is now a both-states check

`_r2_dod_check.py` reads the committed blob, so it can be pointed at either state. It must
be **red on the round-2 blob** for its green on the current one to mean anything:

```
  ok  rc=0 (want 0)  dod_check @ current                SUCCESS:dod-check 4/4 DoD items PASS, 5/5 negative controls fired
  ok  rc=1 (want 1)  dod_check @ 630bb8af (must FAIL)   FAILED:dod-check ['DoD3']
```

DoD3 now has **two** controls, one per branch: `drop-rss-on-measured-row` and
`strip-reason-from-unmeasured-row`. Both fire.

---

## A round-3 hypothesis that was REFUTED

Recorded because a pass that reports only confirmations is selecting for the answer it
wanted. My highest-prior hypothesis on opening was: *round 2 regenerated `disposition.json`
from a fresh sweep (`capability-matrix-r2.json`) while the narrative kept round-1 cost
figures, so the docs and the shipped JSON now disagree.* `_r3_hunt.py` measured it:

```
  verified      r1=      16  r2=      16
  tools         r1=     707  r2=     707
  name_bytes    r1=   11645  r2=   11645
  schema_bytes  r1=  603233  r2=  603233
  per-row schema_bytes drift r1 -> r2:  (none)
  rows whose schema_bytes match r1: 16/16      rows whose schema_bytes match r2: 16/16
```

The two sweeps are byte-identical on every cost field, so the docs' `707` / `11,645` /
`603,233` / `51.8x` / `53.2%` are correct against either matrix. **REFUTED**, and the
re-derivation strengthens round 2's corroboration claim rather than weakening it.

---

## One defect in my OWN round-3 instrument, caught and fixed

Consistent with rounds 1 and 2, where self-inflicted detector failures outnumbered the
real ones.

| my instrument said | the contradiction | root cause |
|---|---|---|
| `dod_check @ 630bb8af` printed `FAILED:dod-check ['DoD3']` and, two lines below, `cost-measured=23/23` | a summary asserting full coverage directly beneath the verdict that says coverage is missing | the counter read `not basis.startswith("not-measured:")`, and on a **pre-round-3 blob no row has the field at all**, so absence scored as measured. A self-contradicting output is a detector failure, not a finding. Absence now counts as unmeasured; the same blob reports `cost-measured=0/23`. |

And one shell-level trap worth writing down, because it invalidated my first reading of
three gates: `python gate.py | tail -6; echo $?` reports **`tail`'s** exit status, not the
gate's — a red gate reads as green. `_r3_gate_sweep.py` exists so every number in the next
section is a captured `returncode`.

### A control that disagreed — and the round-4 correction (this section was REFUTED)

> **REFUTED in round 4. The two paragraphs below are preserved verbatim because they are
> the evidence, and deleting a wrong sentence is how a lane loses the ability to see its
> own failure mode. Read the correction that follows them; do not cite them.**
>
> Checking line endings on this round's blobs I used round 2's `README.md | 328 CRLF` row
> as the positive control. It measured **0**. One reading short of writing up "round 2's
> CRLF table is wrong", which would have been false. A second, mechanically identical
> control on a different file settled it: `AGENTS.md` reads **112**, *exactly* round 2's
> number, so the detector fires and agrees. `git log -- README.md` names the cause —
> sibling commit `7aa86f16` rewrote that file to LF between the two rounds. A single
> control that has itself changed is not evidence about the instrument.
>
> Line endings on this round's blobs, for the record: every `.py` blob is **0 CRLF** (blob
> gate, both commits), while the `.md`/`.json` blobs carry CRLF
> (`ROUND3-DEFECT-CLOSURE.md` 278, `disposition.json` 840) — the repo-wide pre-existing
> condition round 2 documented.

**What was actually true.** The first reading was CORRECT and the second control talked me
out of it. `AGENTS.md` has **112 LF lines and 0 CRLF**; `README.md` has **328 LF lines and
0 CRLF**. Comparing a line count against a line count and calling the agreement a fired
detector is precisely the control-that-cannot-distinguish shape this lane had already
committed twice — the third instance, and the only one that shipped a false statement of
fact. `278` and `840` are the exact LINE counts of those two blobs. The `7aa86f16`
attribution is also wrong: that commit is *"docs: repair a decapitated README section"*
(+7/-3 on README.md), not an EOL rewrite, and README.md is `i/lf` on both sides of it.

**Scoped replacement.** `README.md` and `AGENTS.md` are CRLF in the WORKING TREE (`w/crlf`)
but LF in the committed blob (`i/lf`). Every blob this lane committed — `.py`, `.md` and
`.json` alike — is **0 CRLF**, which is what CI reads. `.gitattributes` pins only `*.sh`
and `*.ps1`, so the worktree is unnormalised, but no committed byte is affected. There is
therefore **no `.md`/`.json` CRLF condition to fix**, in this lane or repo-wide.

Measured by `_r4_eol_probe.py`, whose PART A is the control round 3 never ran: a
purpose-built repo with a genuinely-CRLF blob, read back through the identical
`git show` call, returns `(3 CRLF, 3 LF)`. Without that, a reading of 0 could equally have
meant "`git show` normalises" — and that ambiguity is what produced the false sentence.
Second instrument, mechanically independent: `git ls-files --eol` reports **0 of this
lane's 40 indexed paths** as `i/crlf`, with its own control (127 of 135 `*.ps1` read
`w/crlf`, so the parser can see `crlf` when it is there).

---

## Every gate, re-executed, with its real exit code

`python _r3_gate_sweep.py --rev bfec0543` → `SUCCESS:gate-sweep 9/9 gates behaved, exit
codes captured`, exit 0. Receipt: `command-center/mcp-audit/_r3_gate_sweep.out.txt`.

The `--rev` matters: it points the DoD ledger at the **committed blob** of this round's
commit rather than the working tree, so the green below is about bytes a reviewer can
fetch. A `WORKTREE` run prints `[WORKTREE pre-flight, NOT a shipped verdict]` in its own
marker precisely so a pre-flight can never be quoted as this line.

| gate | rc | want | marker |
|---|---|---|---|
| `probe_capability --control` | 0 | 0 | `SUCCESS:probe-capability control-only` |
| `redproof_control` | 0 | 0 | `SUCCESS:redproof-control 4/4 mutations caught` |
| `overlap_report` | 0 | 0 | `SUCCESS:overlap-report pairs=4 surfaces=16` |
| `_r2_reproduce` | 0 | 0 | `SUCCESS:r2-reproduce both defects present in the round-1 blob, absent now` |
| `_r2_redproof_invariants` | 0 | 0 | `SUCCESS:r2-redproof 4/4 A-mutations caught, B injection complete and its control fired` |
| `_r2_corroborate` | 0 | 0 | `SUCCESS:r2-corroborate 16/16 agree on count AND names` |
| `_r3_redproof_liveness` | 0 | 0 | `SUCCESS:r3-redproof A ok, B 5/5 mutations caught, C the widened predicate sees the gap the old one skipped` |
| `_r2_dod_check` @ `bfec0543` (this commit) | 0 | 0 | `SUCCESS:dod-check 4/4 DoD items PASS, 5/5 negative controls fired` |
| `_r2_dod_check` @ `630bb8af` (round 2) | 1 | **1** | `FAILED:dod-check ['DoD3']` |

Repo gates over this commit's blobs, both with their controls: `_verify_blob_gate.py
bfec0543` → 6 blobs, **0 CRLF**, `ruff check` rc=0, `ruff format --check` rc=0, MANGLED
control fires rc=1 → `SUCCESS:blob-gate`. `_verify_secrets_gate.py bfec0543` → committed
synthetic-secret control fires rc=1, real scan `no leaks found` →
`SUCCESS:secrets-gate`. Commit scope: 13 files, **0 out of scope**.

Ruff, pinned `0.15.17`: five of this lane's files were reformatted to clear the repo gate.
Behaviour preserved by **re-execution, not assumption** — `disposition.json` and
`DISPOSITION-TABLE.md` regenerate byte-identical afterwards (`diff -q` → IDENTICAL). Census
after: `in_scope=0`, repo-wide 39 **at that instant** (a moving target — see §D3 of round
2; nine sibling-lane readings this program have ranged 27-60).

## Confidence

* **Almost certain (90-99%)** — each of E1/E2/E3 was reproduced against a pinned commit
  before its fix; each fix has a control observed to fire in the known-broken state; the
  round-2 predicate's blindness is measured by re-implementing it verbatim rather than
  recalling it; the 9 gate exit codes are captured `returncode`s; the reformat is
  behaviour-preserving by byte-comparison of regenerated artifacts.
* **Likely (55-80%)** — that E1 is the same defect an independent round-2 verifier would
  have named first. It is the highest-severity shape (a machine-readable
  self-contradiction), it is the same class as round 1's headline, and it is trivially
  reproducible — but see the provenance note: I did not read their report.
* **Uncertain (20-55%)** — that no FOURTH defect remains. Three rounds have each found
  three, which is not obviously a converging series. A self-review is not the settling
  experiment; another independent verify pass is.
* **UNVERIFIED, named with its experiment** — whether the 7 unmeasured rows would yield a
  tool surface over HTTP (`initialize`+`tools/list` against each endpoint); whether
  `agent-mail`'s `health_check` port field (8811 vs the live 8812) is a stale constant or a
  second instance (compare pids); whether the three playwright rails differ BEHAVIOURALLY
  (name identity is measured, behaviour is not — which is why they are INVESTIGATE).
* **Unchanged from earlier rounds, still open** — the `mcpctl` precedence question, the
  bytes-vs-tokens reconciliation with `impact.py`, and the `searxng` disable (a config
  mutation, recommended only). ~~the `.md`/`.json` CRLF condition~~ — **struck in round 4:
  there is no such condition; every committed blob is 0 CRLF. See the correction above.**
* **Explicitly NOT claimed** — that CI is green. Two gates were verified over the committed
  blobs; the other ~23 steps were not run.
