# LANE DOCS — BUILD round 6 (re-entry after a CONFIRMED refutation of round 5)

COVERAGE: every row in §2 is backed by a command I executed this round. NOT measured here, and
said so rather than folded into a pass: a real CI run, a fresh-clone run, the full `ci/tests`
sweep, and `validate-all-skills.ps1` over 337 skills. See §6.

> If this document still reads `UNKNOWN - not yet measured`, the unit died before measuring
> anything and no verdict here may be cited.

---

## 0. What round 6 is for

Round 5 (`5d573583`, plus the gate arm carried in `b0e3bf98`) was audited and then adversarially
verified. Both returned `build_is_sound = true`: the doc fix, the gate arm, the CI wiring and the
17-test suite were reproduced independently and **stand**. Nothing in round 5's *code* is being
undone here.

What was CONFIRMED against round 5 is a cluster of **evidence-hygiene** defects — sentences wider
than their evidence, and evidence anchors that do not reproduce. One of them was committed, which
makes it this lane's own defect class shipped inside this lane's own artifact.

This round fixes the SENTENCES, records that the earlier wording was REFUTED rather than deleting
it, and pins both numbers to immutable commits so the class cannot recur in these files.

---

## 1. Starting state (executed, not assumed)

```
HEAD at entry     01febbed 2026-08-14 "docs(hook-audit): stop citing a number that changes
                  every time a sibling commits"        <- a sibling lane, same defect class
branch            main          dirty paths at entry: 284
3 docs suites     42 passed, exit 0     (py -3.11, the interpreter CI uses)
3 sibling suites  49 passed, exit 0
```

---

## 2. The doc-vs-reality table for round 6

Verdict = what I measured. Resolution = fix-doc / fix-code / no-action, with the reason.

| # | claim under test | probe (executed by me this round) | verdict | resolution + reason |
|---|---|---|---|---|
| **R6-1** | round 5's evidence line `mirror HEAD blobs d088884d3bf0 == d088884d3bf0` | `git cat-file -t` fails on `d088884d3bf0` **and** on `d088884d`; a full `--batch-all-objects` census returns **0** objects with that prefix. Detector control: the same census with HEAD's own prefix `01febbed` returns **1**, so the census can find a known-present object | **REFUTED — the anchor resolves to nothing.** The *conclusion* is true: both mirrors are `df9d9d760bba` at HEAD | **fix the sentence.** Report-only — `git grep d088884d` over tracked files returns **NONE**, so no committed file carries it. Corrected in §3.1 of this doc; nothing to edit in the repo. |
| **R6-2** | round 5's evidence line `bare_refs=20 missing=16`, placed in a block describing the state **after** its fix | `docs/_lane_docs_r6_pinned_counts.py` — reads committed blobs at two pinned 40-char SHAs, never touches the working tree: **pre-fix `67137879` -> 20/16**, **post-fix `5d573583` -> 19/15**, HEAD -> 19/15 | **REFUTED as written — 20/16 is the PRE-FIX reading.** The delta of exactly 1 is the line R5-3 fixed | **FIX DOC (2 files).** `docs/_LANE-DOCS-BUILD-R5.md` rows 50 and 180-188, and the comment header of `ci/tests/test_command_doc_promises.py`. Both numbers now carry their commit anchor. |
| **R6-3** | `docs/_LANE-DOCS-BUILD-R5.md` §8.9: "the pre-fix blob pin `3bfb914d` remains valid — `git rev-parse HEAD:commands/sessions.md` still returns it" | `HEAD:commands/sessions.md` -> **`df9d9d76`**, not `3bfb914d`. `3bfb914d` is the blob at the **parent** `67137879`. Control that the reader is not constant: `HEAD:README.md` -> a third, different sha | **REFUTED, and SELF-CONTRADICTING.** Had the stated probe been true the fix would not be at HEAD — the same document also asserts "the fixed line still present at HEAD" | **FIX DOC.** The conclusion survives on a correct probe: parent blob `3bfb914d` contains **0** occurrences of the fixed line vs **1** at HEAD, so the both-states control really is comparing against broken bytes. Re-ran it: `SUCCESS:docs-r5-bothstates broken_state_fires=1 fixed_state_fires=0`. |
| **R6-4** | `docs/_LANE-DOCS-BUILD-R5.md` §4: "would leave **20** equally-referenced siblings behind" | measured three candidate referents; **none is 20**. `hooks/hooks.json` names **23 distinct** `scripts/hooks/*` targets across **51** occurrences (-> **22** siblings excluding `cost-tracker.js`); `~/.claude/scripts/hooks/` holds **27** files (26 siblings); `commands/*.md` names **2** distinct such tokens. Detector control: `scripts/hooks/zzz-not-real` -> **0** matches, so the zero-arm is not a broken matcher | **REFUTED — an unanchored number that reproduces to nothing** | **FIX DOC.** Replaced with the measured **22**, with all three candidate referents recorded inline so the choice is auditable. Not flagged by the audit; found by re-measuring every number in the file rather than only the flagged one. |
| **R6-5** | `docs/_LANE-DOCS-BUILD-R5.md` §8.8: "committed by someone else (`b0e3bf98`, **owner**)" | `git log -60 --format="%an <%ae>" \| Sort-Object -Unique` returns exactly **1** identity — `Andrei Mihai Visalon <54636077+Prekzursil@users.noreply.github.com>` | **UNFALSIFIABLE from git metadata** — no signal separates agent-authored from owner-authored | **FIX DOC.** Rewritten to the falsifiable form: *this lane's own commit action did not produce it*. The attribution is withdrawn, not restated. |
| **R6-6** | the audit's F4: "scope expansion beyond `docs/**` was **undisclosed**" | read the committed artifact: `docs/_LANE-DOCS-BUILD-R5.md` §8 item **5** already says *"Scope widened into `commands/` and `ci/tests/`"* with its precedent and its reason | **HALF-REFUTED.** CONFIRMED for the returned report, which omitted it; REFUTED for the committed artifact, which discloses it | **no doc action.** Carried into this round's report instead (§3.5). Recording only the confirmed half would have been the same overclaim in the opposite direction. |
| **R6-7** | should the pinned-count probe become a CI gate? | `quality.yml`: the docs steps live in job `test-python` (line 283), whose checkout at line 287 has **no `with:` block** -> `fetch-depth` defaults to **1**, a shallow clone. The only `fetch-depth: 0` in the file is line 1631, a **different** job (gitleaks). Separately the probe takes **33.5 s** | **NO — but "structurally unrunnable" is REFUTED; see the round-7 correction. The decision survives, the reason does not** | **no CI wiring.** Two independent grounds. A history-reading gate in a shallow-checkout job fails closed on every run; that is the gate the next lane disables. It stays an on-demand re-derivation. *Correction (round 7): the verdict wording was **REFUTED**. Measured with a two-arm clone control (`docs/_lane_docs_r7_shallow_control.py`): a depth-1 clone fails closed exactly as claimed, and the SAME clone after `fetch --unshallow` returns `SUCCESS:docs-r6-pinned pre_fix=20/16 post_fix=19/15`. So the probe is not structurally unrunnable in CI; it needs `fetch-depth: 0`, a two-line setting that **6 workflows in this repo already carry as a live YAML field — including `quality.yml` itself**, in a different job. The decision not to wire it SURVIVES on a reason round 6 did not give: the probe's inputs are two immutable commits, so its answer is frozen and a gate on it can never go red because reality changed, only because the probe or the checkout broke. The defect that actually recurred is the anchor being stripped off the sentence, and that is checkable in milliseconds with no history at all — which is what round 7 shipped instead.* |

---

## 3. What changed, and the sentence that replaced each refuted one

### 3.1 R6-1 — the anchor that resolves to nothing (report-only)

REFUTED wording: *"mirror HEAD blobs d088884d3bf0 == d088884d3bf0, identical"*.

Correct form: **both mirrors are blob `df9d9d760bbacd4cac3d4141aaa5bba6b318203a` at HEAD**
(`git rev-parse HEAD:commands/sessions.md` and
`git rev-parse HEAD:agent-self/config/commands/sessions.md` return the same object), and the two
working files share SHA256 prefix `e9b4adf360b9`.

The committed artifact never carried the bad hash — `git grep d088884d` over tracked files returns
nothing — so there is no repo edit for this row. It is corrected here because an unreproducible
anchor is the mechanism by which a false claim survives an audit, and deleting it silently would
lose that.

### 3.2 R6-2 — the stale count, in the two files that shipped it

Both carriers now state the number **with its commit anchor** and keep the refuted wording visible:

- `docs/_LANE-DOCS-BUILD-R5.md` row **R5-5** and the `surface` line of its evidence block.
- `ci/tests/test_command_doc_promises.py`, comment header of the round-5 arm.

The comment header also records *why* the anchored form was chosen over simply updating to 19/15:
a number tied to HEAD moves every time a sibling adds a command doc, so an updated-but-unanchored
number is the same defect with a fresher value. HEAD's 19/15 is reported by the probe and asserted
by nothing.

### 3.3 R6-3 / 3.4 R6-4 / 3.5 R6-5

All three corrected in place in `docs/_LANE-DOCS-BUILD-R5.md`, each as an inline
*Correction (round 6)* that states the refuted wording, the measurement that refuted it, and the
surviving conclusion where there is one. None of the three deletes the original claim.

### 3.5 Scope, stated up front (R6-6)

This round edits **`ci/tests/test_command_doc_promises.py`**, which is outside the lane's declared
file scope of `docs/**`, `README.md`, `AGENTS.md`, `CLAUDE.md`. Stated rather than left implicit,
because that is precisely what the audit faulted in the round-5 report:

- the file is one of the two carriers of the defect being fixed, so fixing only the other one
  would leave the finding half-closed;
- the edit is a **comment block only** — no test, no regex, no assertion changed (17 tests before,
  17 after);
- precedent: round 5's own §8.5, and round 3's §7.6 before it, record this lane owning
  `ci/tests/` for its gate.

`AGENTS.md`, `CLAUDE.md` and `README.md` are **not touched** — verified against the commit surface
in §5.

---

## 4. The probe, and why it is not a gate

`docs/_lane_docs_r6_pinned_counts.py` re-derives both numbers from committed blobs at two
immutable SHAs. It **imports** `extract` / `classify` from `docs/_lane_docs_r5_surface.py` instead
of re-implementing them — a probe that re-implements the thing it checks can only agree with
itself. It reaches the same question the audit reached by mutating the working tree, via a
mechanically different route (blob reads, no tree mutation), so the two are independent signals
rather than one signal run twice.

Three controls, each distinguishing two hypotheses:

| control | H1 | H2 | result |
|---|---|---|---|
| **C1 parity** — is my historical reader measuring the SAME quantity? | reader(HEAD commit) == working-tree probe | they differ | **PASS** (19/15 both) |
| **C2 discrimination** — is the reader blind to the change under test? | pins disagree | pins identical | **PASS** (20/16 vs 19/15) |
| **C3 floor** — did the corpus collapse? | docs > 0 and tokens > 0 | zero-walk reported as clean | **PASS** (72 docs) |

**C1 earned its place immediately.** Its first run **FAILED**: my historical reader said
`missing=16` at the HEAD commit where the working-tree probe says `15`. Cause: the round-5 probe's
`resolves()` is `path in tracked or (REPO/path).exists()`, and `.exists()` is TRUE for a
**directory** — but a directory is never a member of `git ls-tree` output, it exists only as the
prefix of its children. So the token `scripts/` read as missing. Without C1 this probe would have
printed `16` at HEAD and "confirmed" round 5's refuted number by reproducing the right value for
the wrong reason. Fixed by reconstructing directory existence from tracked prefixes
(`resolves_at`), which is the honest historical analogue.

That is **one self-inflicted detector failure this round**, caught by a control rather than by
inspection, and disclosed rather than quietly fixed.

**Why it is not wired into CI** — *rewritten in round 7. The original reasoning is kept below because it was REFUTED, not merely improved.* The probe reads two IMMUTABLE commits, so its verdict is frozen: a CI gate on it cannot detect a new defect, only its own breakage. That is the surviving reason.

REFUTED wording (round 6): *"two independent measurements, not a preference (see R6-7): the hosting job's checkout is shallow, so the pinned commits would not exist; and 33.5 s is not a per-PR gate."* The first is true as a PREMISE and false as the CONCLUSION drawn from it — a depth-1 clone does fail closed (re-measured), but `fetch-depth: 0` is the remedy and 6 workflows here already set it, one of them `quality.yml`. The second was only ever a Windows measurement (re-timed at 27.8 s) and was never taken on a Linux runner. The behavioural gate that *does* run in CI is unchanged and still green.

---

## 5. Evidence (executed; commands and their real output)

Shipped as **`65af5451`** (5 files, +560/-10 — the four corrections plus the pinned probe and
the EOL census) and **`a946b643`** (1 file, +88 — the blob-level check). Both verified ancestors
of HEAD; both committed with explicit pathspecs, so no sibling path was swept in.

```
pinned counts    SUCCESS:docs-r6-pinned controls=C1,C2,C3-ok
                 pre_fix=20/16 post_fix=19/15 head_moving=19/15
C1 first run     FAILED:docs-r6-pinned controls=C1-parity   (16 vs 15 -- the caught defect)
fabricated hash  git cat-file -t d088884d3bf0  -> fatal: Not a valid object name
                 --batch-all-objects | rg "^d088884d"  -> 0
                 CONTROL rg "^01febbed" (HEAD's own prefix) -> 1   (census works)
                 git grep d088884d -- .  -> NONE in tracked files
mirror (real)    HEAD:commands/sessions.md == HEAD:agent-self/config/commands/sessions.md
                 == df9d9d760bbacd4cac3d4141aaa5bba6b318203a
blob pin         67137879:commands/sessions.md -> 3bfb914d   (NOT HEAD, as R5 claimed)
                 5d573583:commands/sessions.md -> df9d9d76
                 CONTROL HEAD:README.md -> f5e7fc02   (reader is not constant)
                 fixed-line occurrences: HEAD=1  parent=0
authorship       git log -60 --format="%an <%ae>" | Sort-Object -Unique -> 1 identity
siblings (R6-4)  hooks/hooks.json: 51 occurrences, 23 distinct scripts/hooks/* targets
                 ~/.claude/scripts/hooks: 27 files ; commands/*.md: 2 distinct
                 CONTROL scripts/hooks/zzz-not-real -> 0 matches
gate suite       py -3.11 -m pytest ci/tests/test_command_doc_promises.py -q -> 17 passed, exit 0
                 (17 before this round's comment edit, 17 after -- no assertion touched)
3 docs suites    42 passed, exit 0     (py -3.11)
3 sibling suites 49 passed, exit 0     test_deploy_doc_consistency, test_rules_doc_coherence,
                                       test_rules_doc_contracts
R5 both-states   SUCCESS:docs-r5-bothstates broken_state_fires=1 fixed_state_fires=0 blob=3bfb914d
EOL census       all 4 touched files LF, CRLF=0, loneCR=0, MIXED=none, before AND after
ruff 0.15.17     check "All checks passed!" exit 0 ; format --check "2 files already formatted"
                 exit 0  -- exit codes captured BEFORE any pipe
CI job facts     quality.yml:283 test-python / ubuntu-latest / python 3.11 ;
                 checkout at :287 has no `with:` -> fetch-depth defaults to 1 (SHALLOW) ;
                 only fetch-depth: 0 in the file is :1631, the gitleaks job
probe timing     33,535 ms
```

---

## 6. Residual, disclosed inline rather than in a footnote

1. **No real CI run, and this lane does not push.** Everything above is local, on the CI
   interpreter (3.11.9) and against committed blobs. Settling experiment: push and read the
   `gate-tests-coverage (python packages)` job.
2. **No fresh-clone run.** Partly mitigated: every number in §2 that could be is derived from
   committed blobs rather than the working tree, so it is clone-independent by construction. The
   `.exists()`-dependent working-tree baseline is not.
3. **Full `ci/tests` sweep NOT-CHECKED.** Prior rounds measured 4 Windows-only failures at parent
   `96362031` that reproduce with an empty tree and are not this lane's. I ran the 6 suites that
   touch what I changed.
4. **R5-1 half 2 remains UNVERIFIED [likely 55-80%]** — a fresh `claude plugin install` wiring 3
   dead plugin-root targets. Unchanged from round 5, still tagged inline there with its settling
   experiment, still routed to hook-audit, still not gated red.
5. **`skill-dual-write.yml` still has no `push:` trigger** — carried from INTEGRATE §6.1, not
   mine.
6. **The pinned probe is on-demand only** — for the frozen-input reason in §4, not for the
   shallow-checkout reason round 6 gave, which round 7 REFUTED. Nor is "the docs steps
   moving" the precondition: adding `fetch-depth: 0` to the hosting job would be, and that
   is a deliberate cost (full history on the repo's largest job) bought for a frozen answer.
7. **One self-inflicted detector failure this round** (§4, the `.exists()`-vs-`ls-tree` directory
   asymmetry). Caught by C1, disclosed, fixed. Also a Windows-only `UnicodeDecodeError` from
   `subprocess(text=True)` decoding as cp1252 — CI's UTF-8 default would have hidden it; the fix
   is an explicit `encoding="utf-8"`.
8. **R6-4's `22` is the best-supported of three candidate referents, not a recovered original
   intent.** The round-5 author's meaning cannot be recovered from the text. All three measured
   candidates are recorded inline in the corrected sentence so a reader can disagree with the
   choice without re-measuring.
