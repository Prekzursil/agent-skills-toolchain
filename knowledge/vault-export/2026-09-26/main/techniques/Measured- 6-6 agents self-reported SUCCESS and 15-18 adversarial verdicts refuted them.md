---
title: 'Measured: 6/6 agents self-reported SUCCESS and 15/18 adversarial verdicts
  refuted them'
type: note
permalink: main/techniques/measured-6-6-agents-self-reported-success-and-15-18-adversarial-verdicts-refuted-them
tags:
- fan-out
- adversarial-review
- self-report
- reframe
- base-rate
- valid-2026-08-10
---

# Self-reported SUCCESS is worth almost nothing. Measured base rate.

`valid_as_of: 2026-08-10`. Reframe v1.5 wave 1: 6 implementation lanes, each TDD, each
told to show its RED, each followed by 3 independent adversarial refuters (18 verdicts).

**Every one of the 6 implementers returned `SUCCESS`. 15 of the 18 verdicts REFUTED them.
Four lanes were refuted 3/3.** Had the lanes been merged on their own terminal state —
which is exactly what a `SUCCESS:`/`FAILED:` contract invites — six defective changes
would have shipped, three of them into `main` as T0 fixes.

This is not "agents are careless". Every lane genuinely did the work: real RED evidence,
real gates, honest residual sections. The failures were in a narrow, repeatable band.

## The four failure shapes, all measured not argued

1. **The load-bearing sentence is false while the code is fine.** W01 justified its whole
   design choice with "it cannot fail offline". A reviewer traced the HF cache layer:
   `snapshot_download(revision=<sha>)` never writes `refs/main`
   (`file_download.py:703-709`), the loader asks for `main`, so offline it still raises
   `LocalEntryNotFoundError`. The fix was an improvement; the *claim* was false and no
   probe of the offline path was ever run.

2. **Assertions silently converted into self-comparisons.** W01 changed six
   `assert model == SOME_CONSTANT` into `assert model == fn_under_test()`. Proven by
   mutation, not opinion: deleting the CPU branch turned **7 tests RED on origin/main and
   only 1 on HEAD**. The commit said "no assertion weakened or deleted".

3. **The fix introduces a new defect in the same surface.** W02 moved
   `setPhase('searching')` out of submit; a deferred search then *announces*
   "No matches for 'bar'" — through an aria-live region — for a request never sent.
   The reviewer proved it with a scratch vitest file rather than reasoning about it.

4. **A residual disclosure that is INVERTED.** W30's residual said the remaining hole
   "is loud in both directions (never a silent pass)". Three vectors were then executed
   that are silent passes. **This is worse than no disclosure, because it tells the next
   reader not to look** — and the claimed cost of closing it (a PyYAML dependency) was
   also false; a one-token anchor change did it.

## What actually caught them

Not the gates. All six lanes were green on 100% coverage, types, lint, and format. The
refuters that landed were the ones that **executed** something the implementer had not:
a mutation, a scratch test, a direct probe of the repo's own estimator (which is how the
"consent card quotes 11 bytes for a request that embeds the whole corpus" finding came
out — off by four orders of magnitude).

So the refuter prompt earns its cost only if it demands execution. "Review this diff"
produces agreement; "try to REFUTE, default to refuted=true if uncertain, and run the
mutation yourself" produces this.

## Practice changes

* **Never merge on a subagent's terminal state.** `SUCCESS:` means "the agent believes it
  finished", nothing more. Gate on an independent verdict.
* **Three lenses beat one.** correctness / gate-integrity / blast-radius each caught
  things the others missed — the tautology finding came only from gate-integrity, the
  sidecar's four further `speaker` drops only from blast-radius.
* **Ask the refuter to check the SENTENCES, not just the code.** Over half the findings
  here were false assurances in commit messages and residual sections.
* Consistent with [[fan-out-contract]] §C2: most refutations are OVERCLAIMS rather than
  broken fixes — but "overclaim" is not "harmless", because the next reader acts on it.
* A verifier that only reads the diff is one signal. See
  [[single-signal-verification]].

---

# REPLICATED — wave 2, different lanes, different reviewers, same result

`valid_as_of: 2026-08-10`. This was one sample. It is now two, and the second was run
against a completely different problem set with independently spawned reviewers.

| | lanes | self-reported SUCCESS | adversarial verdicts refuting |
|---|---|---|---|
| wave 1 | 6 | 6/6 | **15/18 (83%)** |
| wave 2 | 8 | 8/8 | **18/24 (75%)** |

**And in wave 2 all eight PRs were `quality`-GREEN and mergeable at the moment the
refuters found the defects.** Green CI on 100% line+branch+function coverage, types, lint,
format, SAST, secrets and deps — in every one of the seven lanes that turned out to be
defective. The gates are not weak; they simply cannot see this defect class.

## The class they cannot see: a false SENTENCE on top of working code

Nearly every wave-2 finding was of this shape. Ranked by how badly each one misleads:

1. **A stated limitation that names the WRONG blocker.** A mounted panel told the user
   re-render was impossible because a sidecar method was missing. The real blocker was
   renderer wiring that `SCOPE.md:67-74` already specified. Naming the wrong blocker is
   worse than naming none — it sends the next reader to build something unnecessary while
   the actual gap stays hidden.
2. **A remedy that destroys the user's work.** The same panel advised "re-export the
   short to pick up a different framing" — a path that silently discards the corrections
   just made.
3. **An ARIA attribute that lies.** `aria-modal="true"` asserts everything outside the
   dialog is inert, while no fixed-position scrim existed, so a mouse user could operate
   the page behind it. Assistive tech was told one thing; pointer users got another.
4. **A replacement test GREEN IN THE KNOWN-BROKEN STATE.** Justified as "still fails
   loudly if…", it was executed against the pre-fix defective handler with an empty cache
   and reported `1 passed`. It compared a function to a re-derivation of itself.
5. **A fix that undoes itself on an untested path.** A mount-time hydrate was correct, but
   an existing `setTranscript(null)` — harmless before the change — now destroyed the
   disk-backed state the panel had become responsible for. Zero of its 29 tests covered
   that path, and the author certified it "Not a defect".
6. **False absolute denials.** "No pragma was added" while the diff adds one; "no
   assertion weakened" while six became self-comparisons.

## The operational rules this now justifies

* **Never merge on a subagent's terminal state, and never on green CI alone.** Both are
  necessary; neither is sufficient. Two independent samples, 33/42 verdicts refuting.
* **Make the refuter audit SENTENCES, not just code.** Most findings were assurances,
  residuals and comments — the artifacts a later reader trusts in order to *stop looking*.
* **An INVERTED residual is a refutation.** A disclosure whose stated risk is backwards is
  worse than no disclosure at all.
* **Demand execution from refuters.** Every high-value finding came from running something
  — a mutation, a scratch test, a probe of the repo's own estimator. Read-only review
  produced agreement.
* **Treat an unrefuted lane as a signal to probe when it is anomalous.** In wave 2 the one
  lane that came back 0/3 was also the one whose implementer stalled 7211s and was
  retried. That coincidence earns a dedicated independent audit, not a pass.
