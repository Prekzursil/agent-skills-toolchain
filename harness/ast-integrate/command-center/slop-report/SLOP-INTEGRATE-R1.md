# SLOP lane — INTEGRATE round: wire the class fix in, and prove it is reachable

MEASURED AT: `96362031`, with two sibling commits (`da82f439`, `d8aa0773`) interleaved
between my two. Every number carries its rev, because the round-2 finding of this lane was
that an un-anchored gate number is stale on arrival.

COVERAGE: the integration, its red-proof, its wiring proof and the post-commit gate reading
are all executed and receipted. NOT executed, reasons inline: the two inherited violations in
`platform/lib/` (§4.1), widening the corpus beyond `command-center/` + `docs/` (§4.2), and the
~84 non-ruff steps of `quality.yml` (§4.5).

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died
before measuring anything and no verdict here may be cited.

---

## 1. What was unreachable

Rounds 1 and 2 closed the SLOP lane's DoD and ended `must_fix = EMPTY`. What they did **not**
produce is anything a runner executes. The lane's central finding — *a committed artifact can
name a file that git does not track, so the citation resolves for the author and resolves to
nothing for everyone else* — was fixed **45 times by hand** and **zero times structurally**.

Two independent signals that this was still live:

| signal | measurement |
|---|---|
| no workflow invokes any citation gate | `grep -rn "citation\|dangling\|check_citations\|slop" .github/workflows/` → **0 hits** |
| the nearest existing gate cannot run in CI at all | `command-center/hook-audit/check_citations.py:48` hardcodes `REPO = Path("C:/Users/Prekzursil/source/ast-integrate")`. On a runner that path does not exist. It is referenced only by prose in `docs/hook-audit/ROUND2-CORRECTIONS.md` |

And the class had already recurred. Two committed command-centre reports
(`P12-ADVERSARIAL-REFUTATION.md:45`, `STOPPING-RULE-REDERIVATION.md:212`) publish an
*"Executable proof"* invocation of `platform/lib/_p12_refute_predicate.py` — 18,614 bytes,
present on exactly one disk, `git check-ignore` rc 1 (not even ignored, just never added).
The lane fixed 45 instances in `command-center/`; the 46th was in a directory it never looked
at.

## 2. The integration

**`command-center/slop-report/check_published_commands.py`**, wired as step
`gate-published-commands` in `.github/workflows/no-runtime-junk.yml` (job `no-runtime-junk`,
5th step), running the self-test first and then the gate.

### 2.1 The design decision that matters: count the FIELD, not the document

My first gate design was **refuted by its own first measurement**, and the refutation is why
the shipped scope is narrow.

The obvious gate greps tracked artifacts for an untracked script's *basename*. Executed
(`_i1_dangling_census.out.json`, control: 7 hits on a known-cited name, 0 on a uuid4 name,
distinguishable):

| scope | on disk | tracked | untracked | "dangling" by basename |
|---|---|---|---|---|
| `command-center/_*.py` | 123 | 45 | 78 | **78** |
| `command-center/**/_*.py` | 468 | 310 | 158 | **103** |

Then I read which files were doing the citing: **157 of the citers are this lane's own census
outputs** (`_slop_measure*.out.json`), whose entire job is to ENUMERATE untracked filenames. A
census that lists a file is measuring it, not depending on it. A gate built on that number
would fire on the measurement instead of the defect — the use-vs-mention failure this repo has
already paid for twice.

The field that IS a dependency is a **published runnable command**: `python <path>` in a
tracked document is a promise. A JSON array element `"_foo.py"` cannot match it, so the entire
census noise class disappears **by construction**, not by an exception list.

Re-measured on that field (`_i2_published_cmds.out.json`):

| corpus | files | commands | distinct targets | untracked targets |
|---|---|---|---|---|
| every tracked `.md` | 4,920 | 681 | 244 | 86 |
| `.md` under `command-center/` + `docs/` | 281 | 250 | 134 | **3** |
| all text under those trees | 991 | 699 | 170 | 15 |
| `.py` under `command-center/` | 437 | 65 | 41 | 0 |

Of those 3, two are the real defect and the third pair sits inside
`command-center/grounding/harvest-split/` — verbatim dumps of *other* agent sessions. A
transcript quoting a command another session ran is a record, not this repo publishing an
instruction. That exclusion is declared in the source, counted, and printed by `--report`
(26 files, 20 commands, 3 unresolved) rather than silently dropped.

### 2.2 Two resolution roots

`python scripts/render_docx.py` <!-- published-command-example: scripts/render_docx.py -->
inside `skills/doc/SKILL.md` is citer-relative, not repo-relative. Resolving against
the repo root alone reports **~83 false violations** across the skill packs. A target passes
if it resolves as tracked under **either** root. (That line carries the gate's example marker,
which must sit on the SAME LINE as the command it excuses; §4.4 records why it has to.)

### 2.3 The baseline is a ratchet, not a mute button

The two inherited violations are **not** carried here — see §4.1 for why that is a decision and
not an omission. `published-commands-baseline.json` holds one row per `(citer, target)` — never
a line number, which drifts on every edit — each recording its owner, why it is open, and the
one-line settling action. **A row that stops violating makes the gate FAIL** and name the row
to delete. A baseline that can only grow is a mute button; one that fails when it is stale is a
ratchet.

## 3. Proof

### 3.1 The gate has teeth — `_i3_integration_redproof.out.json`, 8/8, `INTEGRATION-PROVEN`

Everything below ran in a fresh `git clone -c core.autocrlf=false -c core.eol=lf`, never in
this worktree. EOL pin control: **2,412 tracked `.py`, 0 CRLF**.

| # | control | result |
|---|---|---|
| T1 | clone at HEAD, gate | **rc 0** — wiring it does not red main |
| T2 | same clone + ONE injected NEW violation, committed | **rc 1**, names the target, says NEW |
| T3 | the SAME injection vs the EXISTING gates | see below |
| T4 | a baseline row that no longer violates | **rc 1**, `STALE BASELINE ROW` |
| T5 | a corpus yielding zero commands (throwaway repo) | **rc 1**, `ZERO published commands` |

**T3 is the control that decides whether this was worth wiring.** With the identical injected
defect committed in the clone:

| existing gate | before injection | after injection |
|---|---|---|
| `ruff check .` @0.15.17 | rc 0 | rc 0 |
| `ruff format --check .` @0.15.17 | rc 0 | rc 0 |
| `no-runtime-junk` tracked-junk logic | rc 0 | rc 0 |

**Identical.** The pre-existing CI is blind to it. Without this step the defect ships — which
is exactly how it shipped 45 times, and a 46th.

### 3.2 The wiring is real — `_i5_ci_wiring_verify.out.json`, 5/5, `WIRING-PROVEN`

This is the check that FAILS if the integration is removed, and it does not grep the workflow
for a string. It reads the **committed blob** (`HEAD:.github/workflows/no-runtime-junk.yml`,
not the worktree — a wiring that exists only on this disk is the defect this lane exists to
close), parses the YAML, locates the step, extracts its literal `run:` block, and **executes
it** in a fresh clone.

| # | check | result |
|---|---|---|
| W1 | step exists under `jobs.no-runtime-junk.steps` | `gate-published-commands (no doc may publish a command a clone cannot run)` |
| W2 | both extracted commands execute at rc 0 in a clone at `96362031` | `SUCCESS:published-cmds-selftest`, `SUCCESS:published-cmds` |
| W3 | **both-states control:** same parser against a copy with the step deleted | reports MISSING — wired and unwired are distinguishable |
| W4 | the step invokes the gate, not merely bears its name | true (a step renamed to match while running `echo ok` passes W1+W2 and proves nothing) |
| W4b | the self-test runs first | true |

### 3.3 This round added no gate failure — the lane's own probe, four revs

Measured with `python command-center/slop-report/_r2_gate_now.py --rev <rev>`, the lane's
committed re-runnable replica of `quality.yml:90-93` at the CI pin, **6/6 controls PASS on
every reading** (`C1_eol_pin`, `C2_nested_config`, `C3a/C3b_mangle`, `C4_strict_subset`,
`C5_anchor`):

| rev | | `ruff check` | `ruff format --check` | would-reformat |
|---|---|---|---|---|
| `c488f55b~1` | parent of my commit A | rc 0 | rc 0 | 0 |
| `c488f55b` | **my commit A** | rc 0 | rc 0 | 0 |
| `d8aa0773` | parent of my commit B (sibling) | rc 0 | rc 0 | 0 |
| `96362031` | **my commit B** | rc 0 | rc 0 | 0 |

Two pinned windows, no sibling inside either, zero failures introduced. Scoped deliberately:
this says *these two commits are clean across two pinned windows*, **not** that main is green
today. `bash .quality/charter_check.sh` after the workflow edit: `OK -- 7 gates consistent`.

### 3.4 The shared-file edit, declared

`.github/workflows/no-runtime-junk.yml` is sibling-visible. `git status --porcelain .github/`
was empty immediately before the write. The file is **100% CRLF (121/121)**, so the patch was
applied to bytes with an explicit `\r\n` and asserted: original bytes are an exact prefix,
CRLF 121 → 138 (= +17 lines), no bare-LF introduced, `git diff --numstat` exactly `17 0`.

**Why not `quality.yml`:** `.quality/charter_check.sh` enforces a CLOSED set — every
`gate-<slug>` marker there must map back to a slug in `.quality/charter.yml` and vice versa. A
step there would break the reverse check or require expanding the declared 7-gate charter,
which is a governance decision, not an integration. The repo already keeps a gate outside the
closed set in exactly this file (`gate-no-runtime-junk` is not a charter slug), and the two are
thematic mirrors: that workflow fails when git **tracks** a file it must not; this one fails
when a committed document **promises** a file git does not track.

## 4. Residual — what is NOT done

### 4.1 The two inherited violations are NOT fixed. This is a decision.

`platform/lib/_p12_refute_predicate.py` is textbook bucket (b): 18.6 KB of executable proof,
cited by two committed reports, existing on one disk. Carrying it is what round 1 did 45 times.
**It cannot be carried byte-unchanged:** `ruff check` at the CI pin reports
`F841 Local variable mp is assigned to but never used` at line 107, so committing it as-is
turns `gate-lint-format` RED for every sibling PR. Both SLOP rounds carried evidence
byte-unchanged *on purpose*, because the round-1 provenance-lock detector failed its own
positive control and nobody can yet prove a receipt does not pin those bytes. Editing another
lane's evidence to clear a gate it did not red is the move this lane declined twice and was
vindicated for.

So it is baselined with its owner and its settling action recorded: the owning lane drops the
unused binding at line 107 (behaviour-identical — the call still runs), `git add`s the file,
and deletes both rows; the gate then FAILS until the rows are gone.

*likely (55-80%)* that the one-line change is behaviourally safe — an unused local cannot alter
output — but the digest-lock question is **UNVERIFIED**, unchanged from round 2. Settling
experiment, also unchanged: locate the casualty sha256 manifest, prove the matcher finds a lock
it is pointed straight at, then re-run it against these bytes.

### 4.2 The corpus is 261 of 4,926 tracked `.md`. Quantified, not hand-waved.

`_i7_scope_cost.out.json` pre-runs the widening by **importing the shipped resolver** (a second
implementation would measure my copy of the rule, not the rule):

| corpus | files | commands | unresolved | distinct |
|---|---|---|---|---|
| shipped | 261 | 230 | **2** | 1 |
| harvested transcripts (excluded) | 26 | 20 | 3 | 2 |
| **every tracked `.md`** | 4,926 | 681 | **216** | **61** |

Widening today means either a 216-row baseline or a triage pass. The unresolved targets cluster
by leading segment — `scripts/` 111, `skills/` 43, `platform/` 27 — and by citer tree —
`.agents/` 78, `skills/` 73, `platform/` 34. The `scripts/` cluster is almost certainly a
third path convention in the skill packs that neither of my two roots models; I did not verify
that, so I did not widen. Settling experiment: triage the 61 distinct targets by leading
segment and either add the third root or baseline what remains.

### 4.3 Only `python <path>` is gated

`bash <path>.sh`, `pwsh <path>.ps1`, `node <path>.js` and `python -m <module>` are **not**
covered. `python -m` is deliberately out: a module name is not a path and resolving it needs an
import graph, not a set lookup. The other three are simply unmeasured.

### 4.4 The gate forbade its own documentation. Discipline failed inside one commit.

This file is a tracked `.md` under `command-center/`, so it is **inside the gate's own
corpus**. The first version of this section said the hazard was handled "by discipline — this
document names that path but never in command form", with a declared marker named as the
fallback *"if that discipline ever proves too fragile"*.

**It proved too fragile in the very next command.** Running the gate immediately after
committing this report returned `rc 1`:

```
[NEW] command-center/slop-report/SLOP-INTEGRATE-R1.md:85 -> scripts/render_docx.py
```

Not the literal I was guarding. §2.2 quotes `python scripts/render_docx.py` <!-- published-command-example: scripts/render_docx.py -->
as an *example* of the citer-relative convention; from `skills/doc/SKILL.md` it resolves, from
`command-center/slop-report/` it does not. The gate was right by its own rule and useless in
fact: **it cannot tell an illustration from an instruction.** That is use-vs-mention recursing
a third time in this lane — first the census outputs (§2.1), then the round-1 sentinel, now the
gate's own prose — and the third time it caught me while I was writing the paragraph warning
about it.

Fixed structurally rather than by trying harder. `<!-- published-command-example: <target> -->`
declares one quotation, and the escape is deliberately weak: **it must name the exact target,
on the same line.** It cannot silence a file, a directory or a line, so it suppresses only what
its author looked at and typed out. Two `--self-test` checks hold it to that — a marker naming
the target suppresses, a marker naming a *different* target does not — so it cannot decay into
a mute button. `--report` prints the count of declared examples, so the escape is visible and
auditable rather than invisible.

Cost of the alternative I rejected: rewording one sentence would have made the gate green and
left the trap armed for the next author.

### 4.5 Not established

- **Whether all ~86 `quality.yml` steps pass.** I measured `gate-lint-format` only. Everything
  said here about "the gate" is scoped to ruff.
- **`command-center/hook-audit/check_citations.py`: half of this claim went stale while I
  wrote it, and re-checking is the only reason I know.** §1 cited it as hardcoding
  `REPO = Path("C:/…")`, measured at `f1ce459e`. Sibling commit `6f30510a` then made it
  portable — it now derives its root from `git rev-parse --show-toplevel`. Correctly scoped at
  `6f30510a`: **it is portable now, and still invoked by no workflow** (`grep -rn
  "check_citations" .github/workflows/` → 0 hits). The reachability half stands; the
  portability half does not, and the round-1 wording is kept above rather than deleted. This is
  the lane's own D1 shape — a point-in-time reading published as a standing fact — and I only
  avoided shipping it by re-running the probe at the commit I was publishing into.
- **Nothing is pushed.** `origin/main` is behind by this lane's commits plus the siblings'.
- The round-2 verifier's F1–F4 (an audit citing a residual that is not in the repo; a
  six-probe-scoped "6 receipts" that is 14 at full scope; a vacuous-control shape in the
  auditor's DoD-4; a stale restatement of the blast-radius number) are **unchanged** — all were
  non-blocking and none was a defect in the builder's code.

## 4.6 Final verification, re-executed after the last commit

Every proof below was re-run against the FINAL state, not quoted from the earlier run, because
the gate itself changed in `f3a1410c`/`f1c57145` and a receipt measured before a fix is a
receipt for different code.

| probe | rev | verdict |
|---|---|---|
| `check_published_commands.py` | HEAD | **rc 0** — 236 commands / 269 docs / 2 example-marked / 0 NEW / 0 stale |
| `_i5_ci_wiring_verify` | `268b5747` | **WIRING-PROVEN** 5/5 |
| `_i3_integration_redproof` | `268b5747` | **INTEGRATION-PROVEN** 8/8 |
| `_i8_final_integrity` | `6f30510a` | **INTEGRITY-OK** 5/5 |
| `_r2_gate_now` | `f1014b19~1`, `f1c57145`, HEAD | rc 0 / rc 0 / 0 would-reformat, 6/6 controls each |
| `.quality/charter_check.sh` | HEAD | `OK -- 7 gates consistent` |

`_i8_final_integrity.out.json`: all five of this round's commits are ancestors of HEAD;
**0 foreign paths and 0 deletions** in any of them (files 2/1/19/3/2, every path either
`.github/workflows/no-runtime-junk.yml` or `command-center/slop-report/`); frozen evidence
**UNTOUCHED** — `casualty/probes` 7 files and `p2-wave/probes` 25 files, each with 0 commits
touching, 0 tracked diff and 0 dirty lines since `c488f55b~1`, under a hasher proven
non-constant (stable re-hash equal, mutated differs) and a count floor > 0, because silence
about a nonexistent pathspec is indistinguishable from silence about an untouched one.

Scope, stated because the round-1 version of this sentence is what got refuted: this says
*these commits are clean at these revs*. It does **not** say main is green today. The tree
moved at least eight times while this round ran.

## 5. My own failures this round, recorded rather than dropped

1. **My first gate design was refuted by my own first measurement.** I set out to gate
   "committed artifact names an untracked file", ran the census, and got 103–158 violations —
   157 of whose citers were this lane's own census outputs. Had I shipped it, the gate would
   have fired on the measurement, not the defect. Caught only by reading the citer list instead
   of the count.
2. **My first red-proof run filed a reading against an instrument that was not there.** `_i3`
   cloned the repo and ran the gate — but the gate was still untracked, so the clone did not
   contain it, python exited 2, and T1 recorded a number. It crashed later for an unrelated
   reason, which is the only reason I looked. Fixed with a loud precondition: a missing
   instrument must abort, never produce a datum. This is the same shape as the lane's round-1
   defect, arrived at independently.
3. **I nearly wired the gate into `quality.yml`.** It is the obvious home and the repo's own
   most recent precedent (`f087a6f6 feat(casualty): wire the recovered lane into CI, with the
   proof it can go red`). Reading `.quality/charter_check.sh` first showed the reverse check
   would have failed the build on my own step name.
4. **I shipped the gate red, then broke it again fixing it.** §4.4 is the full account: the
   marker landed on line 86 while the command sat on line 85 (markdown wrapping), and the
   paragraph documenting that occurrence reproduced the literal a second time unmarked. Four
   instances of one class in one lane. **Knowing about the trap did not help once** — the fix
   each time came from running the instrument and reading `example-marked 0`, a number I had
   printed and skimmed past on the first pass.
5. **My §4.5 residual went stale between writing it and committing it**, and only a re-check
   caught it: a sibling made the hook-audit gate portable while I was describing it as
   hardwired. Corrected in place, old wording kept.
