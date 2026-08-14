# SLOP lane — INTEGRATE round 2: the lane's second gate, wired and red-proved

MEASURED ACROSS `46029e92` → `77182bb0`. HEAD moved at least five times under this round
while sibling lanes committed, so every number below carries the rev it was taken at. My
own commit is `2c036164`.

COVERAGE: the wiring, its both-states proof, the behavioural red-proof, the blindness
control and the contested residual are all EXECUTED and receipted. NOT executed, reasons
inline: the ~84 non-ruff `quality.yml` steps (§5), widening the claims corpus beyond
`SLOP-*.md` (§5), and the 179 weak-signal bucket-(b) files that DoD-2 has been partial on
since round 4 (§5).

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died
before measuring anything and no verdict here may be cited.

---

## 1. What was unreachable

Round 7 closed with a one-line residual: *"`_r6_transcript.py` is still not CI-wired. It is
now portable enough to be, which it was not before, but wiring it is a separate change with
its own corpus-cost question."*

I measured the cost question instead of inheriting it. At `46029e92`, running the gate in
its committed mode returned **TRANSCRIPTION-CLEAN over 10 docs and 85 receipts, 42 claims,
all 8 internal controls passing, in 7.5 s, writing nothing.** There was no open cost
question. There was an unwired gate.

That matters because of what the gate checks. This lane's own record, across seven rounds,
is that **every adversarial finding against it was the same shape** — the receipt was right
and the sentence was wider than it. Round 6 found two such lines by hand in a sibling
report. Nothing mechanical was checking any of them, and the one instrument that could was
reachable by nobody.

## 2. The integration

Step **`gate-published-claims`** in `.github/workflows/no-runtime-junk.yml`, job
`no-runtime-junk`, beside the `gate-published-commands` step round 1 wired.

The two are the same rule applied to the two things a committed document can promise:

| step | fails when a committed doc publishes… |
|---|---|
| `gate-published-commands` | a **command** a clone cannot run |
| `gate-published-claims` | a **number** its own committed receipt refutes |

`--committed` is deliberate: it reads docs *and* receipts from HEAD blobs, which is the
question a clone asks. The worktree default answers only "clean on this disk" — the false
negative round 7 measured in both directions on a genuinely divergent key. It writes no
receipt, so the step cannot dirty the tree it is checking.

There is no separate `--self-test`, on purpose: the T1/T5 both-states fixtures live *inside*
the gate, run on every invocation, and gate its exit code. A silent pass is impossible
without them having fired first.

### 2.1 Three defects this round had to fix before the wiring meant anything

**(a) The gate punished the author for checking it.** Reading its CLI surface, I ran
`_r6_transcript.py --help`. It was silently accepted as "no flags", ran the DEFAULT worktree
mode, and **overwrote the tracked receipt `_r6_transcript.out.json`** belonging to round 6.
I had to `git checkout --` it. So the one command an author is told to run before committing
a document dirtied another round's evidence, and a typo'd flag silently answered a different
question than the one asked. Unknown flags now fail closed at rc 2, and `--no-write` gives
the pre-commit worktree check without mutating anything. The default still writes, so the
run meant to refresh the receipt still does.

That flag is not speculative tidying — §3.3 is the check it made possible, and I used it on
this document before committing it.

**(b) The wiring verifier was not clone-valid.** `_i5_ci_wiring_verify.py:36` bound
`ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")`. The instrument whose entire job
is certifying "this gate is reachable from a runner" could only ever measure this laptop.
That is the **third** occurrence of the class in this lane: round 6 shipped it in the
transcript gate, round 7 confirmed and fixed it there, and the verifier standing over both
carried it the whole time. It now resolves from `__file__` via `git rev-parse
--show-toplevel`, the mechanism the CI-wired sibling already used.

**(c) W1–W4 cannot see defect (b), so W5 exists.** A gate binding an absolute root passes
every existing check: the step is wired, the command exits 0, the name matches, the script
is invoked. Only portability separates *runs* from *runs on the runner*. W5 decides it with
`ast` over **assignment targets**, never a regex — about 70 scripts in this directory
contain that literal and most only *mention* it in a docstring, including both gates' own
paragraphs warning against it. Counting the field rather than the document is the
use-vs-mention rule this lane has now paid for four times.

## 3. Proof

### 3.1 The wiring check went red for the real reason, before it went green

This is the executable check that fails if the integration is missing, and I did not have to
simulate the failure — I captured it.

With the workflow edit present in my working tree but **not yet committed**, the verifier
reads the HEAD blob and reports the step missing. Receipt `_i9_prewire_redstate.json`:

| rev | `gate-published-claims:W1_step_is_wired` | verdict | rc |
|---|---|---|---|
| before `2c036164` (edit on disk only) | **false** | FAILED | 1 |
| at `2c036164` (committed) | **true** | WIRING-PROVEN | 0 |

In the *same* red run every check for the already-wired `gate-published-commands` step
passed, so the failure was specific, not a broken instrument. After the commit:
`python command-center/slop-report/_i5_ci_wiring_verify.py` → **WIRING-PROVEN, 14 of 14**,
clone head `2c036164`.

W5's both-states control uses two REAL committed files rather than synthetic strings:
`check_published_commands.py` must come back silent, `_r5_reclassify.py` must come back
firing, and a third arm asserts the silent one *contains* the literal in prose. All three
hold, so a green W5 cannot mean the predicate never fires.

### 3.2 The step actually catches the defect, and existing CI does not

Wiring proves a step runs. It does not prove the step is worth its slot — a step running
`python -c pass` satisfies every check in §3.1. `_i9_claims_redproof.py` asks the harder
question, entirely inside a fresh LF clone, driving **the run block extracted from the
committed workflow blob** rather than a hand-typed command.

`python command-center/slop-report/_i9_claims_redproof.py` → **CLAIMS-GATE-RED-PROVEN**, 8/8:

| # | check | result |
|---|---|---|
| R0 | the gate is present in the clone, or ABORT without filing a reading | pass |
| R1 | baseline: the extracted step is rc 0 on the untouched clone | pass |
| R2 | inject one doc publishing a value the receipt refutes, **commit it**, re-run → rc 1 **and it names the injected doc** | pass |
| R3 | the same injection carrying the CORRECT value leaves it green | pass |
| R4 | every pre-existing gate, on the identical injected clone | **all blind** |
| R5 | the clone-run wrote nothing into the source | pass |

**R4 is the check that decides whether this step earns its place.** Against the identical
injected clone: `gate-published-commands` rc 0, `ruff check .` rc 0, `ruff format --check .`
rc 0, at the CI pin 0.15.17. All green. Without this step the defect ships — which is the
state the repo was in an hour ago. R3 is the half that stops R2 from being meaningless: a
gate that fired on *any* new document would also produce rc 1.

### 3.3 I ran the new gate on this document before committing it

Using the `--no-write` flag added in §2.1(a):
`python command-center/slop-report/_r6_transcript.py --no-write` → rc 0, worktree mode,
11 docs scanned against 10 in committed mode. That difference is itself the discriminator
proving worktree mode really reads the working tree: the extra document is this one, still
untracked at the time.

### 3.4 This round added no lint failure

`ruff check` and `ruff format --check` at the CI pin **0.15.17** — the exact version on this
box — return rc 0 on every script this round touched. Scoped deliberately: that says *these
files are clean at these revs*, **not** that main is green.

## 4. The contested residual, settled

The last adversarial round left one blocking must-fix that rounds 5–7 never closed, and it
was still in the committed bytes when I arrived: **`_r4_buckets.py`'s C5 was an inert
control.** It read `sorted(X) == sorted(<the expression that produced X>)` — f(x) == f(x) —
while sitting in the PASS conjunction as the **only** control over S1, the signal the
classifier calls its strongest. C3 was refuted the same way: it tested set membership
*beside* `sibling_producer` instead of calling it, and was not in PASS at all.

I did not take the refutation on trust. `python command-center/slop-report/_i9_c5_fix.py`
→ **C5-FIX-PROVEN**, 5/5, at `60743c7d`:

| state | shipped C5 | replacement |
|---|---|---|
| real scan | true | **PASS** |
| scan returns nothing | **true** | fails |
| scan fabricates a constant | **true** | fails |

The shipped form is true in all three — confirmed inert, the adversarial round was right.
The replacement is a **mutation pair**: perturb the scan's input and require its output to
move. With nothing tracked the finding set must grow; with every target tracked it must
empty. Neither broken state can satisfy both.

Two things I was careful about:

- **P0 self-control.** A probe reporting false everywhere would look like a successful
  refutation. P0 asserts the comparator produces both booleans on inputs whose answers are
  known independently of the code under test.
- **The receipt was NOT regenerated.** `_r4_buckets.out.json` belongs to rounds 4 and 5 and
  sibling documents publish numbers from it — including to the gate I wired this round.
  Regenerating it to prove my own fix would have moved those numbers. So the edited
  classifier was executed **end to end in a fresh clone**, where its receipt costs nothing,
  and the source receipt was verified byte-and-mtime identical afterwards. The clone's
  receipt carries the new control keys, which is what proves the edited file actually ran.

## 5. Residual — what is NOT done

- **DoD-2 remains PARTIAL and I made no progress on it.** 179 weak-signal bucket-(b) files
  are still uncommitted. Unchanged settling experiment: each owning lane commits its own, or
  a per-lane gate requires it at close. Not swept, not silently passed.
- **The claims corpus is `SLOP-*.md` in one directory.** Every other report in
  `command-center/` publishes numbers against receipts and none of them is checked. Settling
  experiment: run the extractor over a wider corpus with the shipped resolver imported (not
  reimplemented), count unresolved rows, and either widen or baseline what remains — the
  same method round 1 used for the commands gate, which found the cost was 216 rows.
- **The claim FORM is narrower than the corpus, and my own report proves it.** The extractor
  recognises a backticked `key: value` pair and a `histogram` line. Running it over my
  working tree scanned 11 documents against 10 committed — the extra one being this file —
  and the claim count did **not move**: 42 both times. So this document, which publishes
  numbers in almost every section, contributed **zero** checkable claims, and the gate that
  just passed it verified nothing about it. That is not a hypothetical: it is the reading I
  got, and I only noticed because the two counts sat next to each other. A report can evade
  this gate by writing a number in a table cell instead of in backticks, with no intent to
  evade at all. Settling experiment: extract table-cell and prose numerics that sit adjacent
  to a named receipt, measure the false-positive rate on the existing 10 documents, and
  widen only if it is near zero — the same evidence bar the commands gate cleared before it
  narrowed its own corpus.
- **The gate is rev-blind**, unchanged from round 7. It compares today's receipt against a
  claim anchored to an older rev, so re-running a producer can redden a sibling's correct
  sentence. That is why I refused to regenerate `_r4_buckets.out.json` in §4, and it is now
  a live CI risk rather than a local one. Settling experiment: require a claim to carry its
  rev and compare against the receipt *at that rev*.
- **~70 lane scripts still bind an absolute root.** W5 only covers scripts a CI step
  invokes, which today is two. That is a ratchet on the next wiring, not a repair of the
  population. Mass-fixing them would regenerate dozens of tracked receipts and redden
  sibling documents under the very gate wired here.
- **`command-center/hook-audit/check_citations.py` is portable and still invoked by no
  workflow** — unchanged since round 1 reported it.
- **UNVERIFIED, unchanged rounds 2–7:** whether any committed receipt digest-locks probe
  bytes. Still the reason no evidence file is reformatted.
- **NOT-CHECKED:** the ~84 non-ruff `quality.yml` steps. Nothing here claims main is green.
- **Nothing is pushed.**

## 6. My own failures this round, recorded rather than dropped

1. **I reproduced the lane's own defect within minutes of arriving.** Running the gate with
   an unrecognised flag overwrote a tracked receipt belonging to round 6. I caught it only
   because I ran `git status` afterwards out of habit. The fix in §2.1(a) exists because I
   walked into it, not because I foresaw it.
2. **My first R5 control was an equality test against a moving value.** It compared the full
   repo porcelain before against after and came back false. I nearly recorded that as
   evidence the clone-run had written into the source — the round-7 defect — which would
   have been a fabricated finding. It cannot distinguish that from a sibling touching the
   shared tree. Diagnosed instead of assumed (`_i9_r5_diag.out.json`): in a 12-second window
   with HEAD stationary, the only line that moved was another lane's file under
   `command-center/mcp-audit/`, while the gate's own output was identical **to the
   nanosecond**. H1 refuted, H2 confirmed. Replaced with an invariant scoped to what a
   clone-run could actually touch; the wide reading is kept in the receipt, labelled
   refuted, alongside the foreign churn that explains it.
3. **A field in my own probe came back null and I nearly published around it.** The clone
   reader asked the classifier's receipt for a `counts` key that does not exist under that
   name. The check it gates reads `controls` and genuinely found the new keys, so the
   verdict stands — but the null sat in the output and I only noticed on the second read.
   Disclosed rather than trimmed out of the receipt.
4. **The dup-guard hook caught me redefining a helper** that already exists in
   `_r5_bucket_c.py`. I kept the local copy deliberately: importing that module executes its
   module-level hardcoded root, which is the exact defect this round is removing. Recording
   the trade rather than pretending the hook did not fire.
