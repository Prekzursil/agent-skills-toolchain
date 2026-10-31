---
title: SKILLS2-GROUNDING
type: note
permalink: dqverify-repo-20261013/command-center/grounding/skills2-grounding
---

# LANE SKILLS2 — grounding artifact (write-as-you-go)

STATUS: **MEASURED**, round 3. Every verdict below names the probe that produced it and the
control that proves the probe can fail. Raw stdout for each is committed beside this file.

ROUND-3 RE-ENTRY: **the round-2 verifier's findings never reached this unit** — the handed-down
`PRIOR ROUNDS` JSON is truncated mid-round-1-audit and no round-2 audit report exists on disk
(searched; the verifier's only trace is four of this lane's probe outputs, re-run and left
modified in the working tree). Round 3 therefore could not close a list; it re-derived
independently and found four defects, three of them in this lane's own committed work — a
mis-measured fleet constant, an unexecuted prediction inside a handback, an untested assumption
that would have destroyed live work, and a control anchored to `HEAD` while calling itself
frozen. Corrections are marked **ROUND-3 CORRECTION** inline. Detail: `SKILLS2-ROUND3.md`.
The status of the actual round-2 findings is **NOT-CHECKED**.

ROUND-2 RE-ENTRY: an independent audit returned PARTIAL and a third-pass adversarial verifier
returned `build_is_sound=TRUE, audit_holds=TRUE, must_fix=EMPTY`. Round 2 fixed what was
CONFIRMED. Corrections are marked **ROUND-2 CORRECTION** inline at the sentence they repair,
with the refuted wording **kept, not deleted**, so the dead end is not re-walked. Round-2 detail
and its work-list live in `SKILLS2-ROUND2.md`. Nothing in the four DoD verdicts changed — both
reviewers re-executed all four and passed them; what changed is the scope of three sentences,
one undisclosed regression, and one code defect that is now fixed and proven executably.

COVERAGE — what is NOT measured, stated up front:
- **(round 3)** the round-2 verifier's actual findings: **NOT-CHECKED**, never received.
- **(round 3)** two reported-but-unfixed defects: `bc-drive-plus` silently loses 440 of its 793
  description chars to a ` #` YAML comment, and 7 fleet frontmatters are not valid YAML. Both are
  latent (no repo tool strict-parses `SKILL.md`; the renderer is lenient) and both are owner
  trade-offs, not free fixes — see `SKILLS2-ROUND3.md` §R3-F.
- **(round 2)** why the render budget `B` moves between sessions is UNVERIFIED; only *that* it
  moves is measured, on three samples. Round 3's 4th sample **cannot** help: same orchestrator,
  near-identical preamble, so H-CONST and H-SESSION predict the same result. It is a
  reproducibility and transcription check, not a fourth vote.
- **(round 2)** `dead_button_crawl.mjs` is now a second confirmed two-way-diverged file
  (repo 286 lines / live 367). Its union merge is NOT done and is handed to the owner; only the
  main-guard was repaired.
- **(round 2)** the +6 vault drift round 1 created is disclosed and handed back, NOT closed —
  `~/.agents/skills` is outside this lane's declared write scope.
- The *identity* of the priority/exemption term that lets 2 skills survive the budget is
  **UNVERIFIED** (item 1, §Residual). The budget itself is measured.
- The exact value of the per-description truncation cap is **UNVERIFIED** (item 1, §Second
  mechanism) — observed accidentally, not pinned.
- The vault copy of `workflow-authoring` (a *third* variant) is unanalysed; only repo↔live is.
- No claim is made about whether freeing N budget chars lights up any *specific* dark skill.

---

## Item 1 — the 26 (now 30) bare descriptions: **budget-truncation CONFIRMED, parse-failure REFUTED**

Confidence: **almost certain (90-99%)**.

Premise first: **all 30 bare skills have real, non-empty description text on disk.** This is
a render-path bug, not empty files (`_s2_budget_refit.py` §0, `_s2_render_probe.py` control a).

### H-PARSE is refuted three independent ways

1. **Byte-stable skills flipped.** Between observation A (2026-08-12 01:35) and observation B
   (this session) four skills went DESCRIBED → BARE. Three of them —
   `use-image-clipboard`, `using-git-worktrees`, `verification-before-completion` — are
   byte-stable on **two** signals: `size` unchanged (from the 01:35 `G-BARE-DESC.json`
   snapshot, a different probe at a different time) **and** mtime still 2026-07-18 00:25:05.
   Same bytes, different render. `writing-skills` did change today and is excluded as a
   confound. `_s2_bytestable.py`.
   *Control:* the same comparator found 4 genuinely-changed files fleet-wide, so it can see
   change; a "0 changed" reading would have been implausible and voided the probe.
2. **Byte-identical description text renders differently in two namespaces, same session.**
   Five skills have `sha256(description)` **identical** across `skills.daily` and the
   `superpowers` plugin yet render differently: `receiving-code-review`,
   `requesting-code-review`, `test-driven-development` (DESC/BARE) and `writing-plans`,
   `writing-skills` (BARE/DESC). A defect in a file's own bytes cannot do that.
   `_s2_render_probe.py` §2.
3. **Both nominated parse defects fail to correlate.**
   - folded/literal block scalars: **12** fleet-wide, **0** of them bare. The live competing
     hypothesis named in the brief is dead.
   - descriptions over the 1,024-char spec ceiling: **11** fleet-wide, **1** bare
     (`workflow-foundry`) — and **2 of the 4 survivors** are over 1,024
     (`video-watermark-removal` 1154, `workflow-authoring` 1062). Over-length correlates with
     *surviving*, if anything.
   - frontmatter keys: the bare group carries `metadata`/`license`/`origin`, but `origin`
     appears on 59 fleet skills that render fine. Not causal.
     `_s2_render_probe.py` §3.
   - **ROUND-3 ADDITION — YAML *well-formedness*, the sub-hypothesis nobody had tested.**
     The brief named "a frontmatter key the parser rejects"; round 1 tested extra *keys* and
     never tested whether the frontmatter **parses at all**. Measured: **7** fleet skills carry
     frontmatter a strict YAML parser rejects (`ScannerError`, an unquoted plain scalar holding
     `": "`) — `agent-as-judge`, `cv-studio`, `diff-blind-test-synth`, `execution-grounded-bon`,
     `refactor-equivalence`, `rubric-verifier`, `workflow-foundry`. **6 of the 7 render their
     descriptions in full.** If a parse failure suppressed a description, those six would be the
     first to go dark. The seventh (`workflow-foundry`) is bare but sits at rank ≥307 *inside*
     the truncation zone, so it is **confounded** and is evidence for neither side.
     `_s2_r3_yamldiag.py`.

### H-BUDGET is confirmed, and it survives an out-of-sample test

Model: walk the 328 skills in alphabetical (render) order with a cumulative char budget `B`;
if the entry fits, render its description; if not, render the **name only and keep going**
(greedy, not a hard cut — which is why the tail is interleaved rather than a clean suffix).

| test | result |
|---|---|
| fit to observation A (26 bare) | best `B=108,460`, **5** mismatches / 328 |
| **out-of-sample**: hold `B_a`, ask which skills go next | model names 5; **3 of the 4 that actually flipped** are in that set |
| fit to observation B (30 bare) | best `B=108,144`, **2** mismatches / 328 (99.4%) |
| greedy vs hard-cut (independent model) | greedy 5, hard-cut 6 — greedy strictly better |
| monotonicity | `prior_bare ⊂ now_bare`, **0** reversals. A tightening budget can only remove; a parse failure has no such constraint |

**Detector control (the one that matters — rule 3c).** The two hypotheses were stated before
the control ran: *H1 the budget explains the data* → the true set fits far better than
decoys; *H2 the fitter fits anything* → decoys fit as well, and the section-1 fit would be
worthless. Measured:

| observed set handed to the fitter | best mismatches |
|---|---|
| **the true 30** | **2** |
| 200 random 30-subsets | min 27, median 30, max 30 |
| alphabetically first 30 | 30 |
| the 30 longest descriptions | 29 |

The fitter cannot fit an arbitrary 30-set. **DISCRIMINATING.** `_s2_budget_refit.py`.

### Arithmetic, and what it means for the fix

> **ROUND-2 CORRECTION — the earlier wording here was REFUTED and is kept, struck, so the
> dead end is not re-walked.** It read: *"328 skills, 115,478 description chars total; budget
> fitted at ~108,144. The fleet is ~7,300 chars OVER. **That is the entire defect.**"* Two
> things were wrong with that sentence (not with the code): it quoted the **pre-edit** fleet
> total while item 4 below claims net −22, and — the substantive error — it presented `B` as a
> **fleet constant** when it is a **per-session** value. The mechanism was right; the number
> was scoped to one session and written as if it were universal.

- Fleet: **328 skills, 115,461 description chars** (measured with the folded-scalar-aware
  parser; `_s2_r2_finalverify.py` V1). The folded-blind parser reports 106,618 — a **−8,843**
  error, the same trap round 1 caught in itself and round 2 reproduced deliberately as a
  control.

  > **ROUND-3 CORRECTION — 115,461 is an OVERCOUNT of what the renderer charges, by 440.**
  > Rounds 1–3 all used one hand-rolled parser. A mechanically independent one (PyYAML 6.0.3)
  > disagrees by 7,253 chars, fully attributed: 7 files it **rejects** outright (6,766) and 4
  > folded-scalar **re-spacings** (487). Which one does the renderer follow? The injected listing
  > — an external signal this lane does not produce — settles it: `bc-drive-plus` renders exactly
  > as far as the strict parse and no further, because a ` #` opens a YAML comment 353 chars in.
  > Loader-faithful fleet total: **115,021**. Every absolute char figure in items 1 and 4 carries
  > a **±440 (0.38%) systematic error**. **The verdict is unchanged** — sensitivity test:
  > re-fitting sample 4 on loader-faithful lengths gives `B=102,600` at *the same* 2 mismatches /
  > 328. `_s2_r3_loaderparse.py`, `_s2_r3_yamldiag.py`, `SKILLS2-ROUND3.md` §R3-B.
- The budget `B` is **session-dependent**. Three independent samples, three different sessions:

  | sample | bare skills | boundary (cumulative desc chars) |
  |---|---:|---:|
  | round-1 build | 30 | fitted `B` = 108,144 |
  | independent audit | 29 | 102,511 – 105,336 |
  | round-2 build (this session) | 30 | 102,511 – 105,239, best fit **103,025** (2 mismatches / 328) |

  Spread **5,633 chars = 21.4 median descriptions**, i.e. the boundary moves by ~13 skills
  between sessions. `_s2_r2_boundary.py`, verdict `H-SESSION`. The two hypotheses were stated
  before the probe ran and predict different tables.
  *Corroboration that both transcriptions are accurate rather than merely similar:* the audit's
  upper bound and mine differ by **97** chars — exactly the length of `writing-skills`, the one
  skill that renders in their session and not in mine.
- **Correctly scoped claim:** *in any single session the fleet overruns the render budget by
  roughly 7,300–13,000 chars; ~7,300 is a one-session **lower bound**, not a fleet constant.*
- **Rewriting the 26 descriptions cannot fix this** — unchanged, and it does not depend on the
  refuted number: every sample puts the boundary far below the fleet total. The levers are
  (a) fewer curated skills, (b) shorter descriptions *somewhere*, (c) raising the budget if it
  is configurable.
  Re-quantified: the 11 over-spec descriptions hold 13,155 chars; capping all 11 at the 1,024
  spec ceiling frees **1,891** chars — that figure reproduces exactly in all three samples, but
  it covers **15–26% of the need depending on the session** (26% only in the round-1 session;
  15–19% in the other two). **Not applied — owner's call.**
- UNVERIFIED: what makes `B` move between sessions. Settling experiment: run the same probe in
  N sessions whose prompt size is deliberately varied and regress `B` on total prompt tokens.

### Residual — the honest gap

Exactly **2** skills survive that the pure-alphabetical model says should drop:
`video-watermark-removal` (1154) and `workflow-authoring` (1062). Both residuals point the
same way (predicted BARE / observed DESC), so there is a **priority or exemption term** the
model does not carry. **UNVERIFIED: what it is.** Both are named in this session's injected
context, which suggests relevance-weighting, but 4 survivors is far too small a sample and
the earlier `_g6_second_root_probe.py` already refuted the obvious "second enumeration"
explanation (3 of the 4 survivors have the same daily+vault copy profile as 23 bare skills).
Settling experiment: add ~2,000 chars of description to a skill early in the alphabet and
check whether the drop boundary moves by the predicted amount and whether these two still
survive.

### Second mechanism, observed accidentally

While item 4's writer bug (below) briefly set seven descriptions to 4,000 `x` characters, the
re-injected listing rendered them **truncated with a trailing `…`**. That is a *per-description
cap*, and it is a **different** mechanism from the 30 bare skills, which show no text and no
ellipsis — they are omitted wholesale. `workflow-foundry` (1,750 chars) is omitted rather than
truncated, which is consistent with the two mechanisms being separate.
**UNVERIFIED: the cap's value.** Settling experiment: set one skill's description to 1,000 /
1,500 / 2,000 chars in turn and read the ellipsis position.

---

## Item 2 — the vault orphan: dry-run plan read, and **the plan does NOT close the defect**

Confidence: **almost certain**. Command, verbatim:

```
python scripts/deploy-skills-daily.py --target C:/Users/Prekzursil/.agents/skills
```

Exit 0, nothing written (`DRY-RUN-OK:deploy-skills-daily copied=0 needs_merge=397`).
Full output: `S2-VAULT-DRYRUN.out.txt`. `sync-skills.ps1 -Prune` was **not** run.

The plan, repo `.agents/skills` → `~/.agents/skills`:

| | |
|---|---|
| per-skill summary | IDENTICAL 226 · LEFT-AHEAD 1 · RIGHT-AHEAD 5 · **DIVERGED 96** (=328) |
| safe to deploy | **133 files** across 14 skills |
| refused by P2 | 0 |
| needs a human merge (never touched) | **397 files** |
| repo-only skills not resurrected | 18 |

**The headline: the plan offers 12 `ui-audit` files and ZERO of the 6 that carry the defect.**

The vault's live silent-no-op is 6 entry points still on the old lexical main-guard —
`axe_scan.mjs`, `capture.mjs`, `critique.mjs`, `layout_lint.mjs`, `run_audit.mjs`,
`visual_diff.mjs`. Every one is `in-plan=NO` (refused as DIVERGED) while its repo counterpart
is fixed. So `--apply` against the vault would copy 133 files and leave the no-op **6/6
intact**. The 12 offered `ui-audit` files are all unrelated to it. `_s2_vault_gap.py`.

This is the shape the ground floor warns about: a plan that *looks* like it covers `ui-audit`
by file count, whose intersection with the actual defect is empty. Closing the vault no-op
needs a targeted merge of those six files, not the deploy hop.

> **ROUND-3 CORRECTION — "a targeted merge of those six files" was an UNTESTED assumption, and
> it is destructive for one of them.** The sentence assumes the six are one-way behind the repo.
> Nobody measured the direction — even though round 2 measured exactly that for the *seventh*
> file and found the opposite of what two earlier reports assumed. Measured now
> (`_s2_r3_vault.py`, reconstruction checked in both directions, differ validated against the
> known-two-way `dead_button_crawl.mjs`): five of the six —`axe_scan`, `capture`, `layout_lint`,
> `run_audit`, `visual_diff` — have **11 repo-only lines and exactly 1 vault-only line, and that
> line is the old guard the repo deliberately replaced**, so a copy destroys nothing.
> **`critique.mjs` is different: 281 repo-only against 19 vault-only, 18 of them substantive** —
> a Claude-facing critique-input/rubric path that exists only in the vault. It is a **third**
> two-way-diverged file after `workflow-authoring` and `dead_button_crawl.mjs`, and copying it
> would delete live work.
> **Correctly scoped claim:** *five of the six close with a scoped copy; `critique.mjs` needs a
> union merge and is handed to the owner with the other two.*
> Note on method: set arithmetic alone calls all six "two-way", because a one-line **replacement**
> leaves one unique line on each side. The question that matters is *would a copy destroy work*,
> so the vault-only lines are classified rather than counted.

**Detector-control caveat, disclosed:** the use-vs-mention split in `_s2_vault_gap.py` is
**partially inert** — it found 0 mention-only files, and it mislabels
`ui-audit/_fix_main_guard.py` (the *repair* script, which contains the old pattern as a Python
string literal) as a USE. The six vault files were therefore confirmed individually by
reading their guard lines, not by trusting the classifier. The result does not rest on the
inert half.

**New finding, in scope — FIXED IN ROUND 2, and the round-1 framing of it was wrong twice.**
The repo had a **seventh** `ui-audit` entry point on the old guard —
`dead_button_crawl.mjs:280` in both repo trees. Round 1 called it "a one-line change"; the
audit went further and called the repair "a copy-back, not new authorship, because the LIVE
trees already carry `__isMain`". **Both sentences are REFUTED by the diff** (`_s2_r2_deadbutton.py`,
reconstruction control passed in both directions): repo 286 lines vs live 367, two-directional,
**8 significant repo-only lines against 56 significant live-only lines**. Live is not the same
file plus a guard fix — it replaced the simple `__uiAuditMut` mutation *counter* with a
signature-based noise-attribution engine (`__uiAuditSigs`, `onPageError`, `noisiest`,
`attributed`, `throwing`). A whole-file copy-back would have imported 56 unreviewed lines. This
file is a second `workflow-authoring`: genuinely two-way diverged, permanently refused by the
deploy hop, and it needs a union-merge decision, **which is still open and handed to the owner.**

What round 2 *did* fix is the guard alone, in both repo trees, using the repo's own
`_fix_main_guard.py` — no live content imported. Proven executably, both states, same inode:

| state | canonical path | via a junction |
|---|---|---|
| before | exit 1, 157 chars of output — `main()` ran | **exit 0, 0 chars — `main()` never ran** |
| after | exit 1, 157 chars | exit 1, 157 chars — `main()` ran |

The canonical leg is the discriminating control: had it also been silent the probe would be
broken and the script says so instead of returning a verdict. `_s2_r2_guard_exec.ps1`.

**A premise this probe had to correct in itself first:** the initial version used a Windows 8.3
short path (`PREKZU~1`) as the "lexically different" spelling and reported `GUARD IS FIXED`
while the guard was broken. Measured with `_s2_r2_guardvals.mjs`: Node keeps the short form on
**both** sides, so `resolve()` matches and that spelling never triggers the bug. A junction —
which is exactly how `~/.claude/skills` → `skills.daily` is set up, and the mechanism the repair
tool's own docstring describes — gives `LEXICAL match: false`, `REALPATH match: true`. The
control was rebuilt on the measured mechanism, not the assumed one.

**And the first repair did not repair — the fix tool commits the defect class it exists to
fix.** Running `_fix_main_guard.py` unmodified produced a file that *looked* patched
(`__isMain` present, old guard gone, `node --check` clean, 11/1 diff in both trees) and the
both-states probe still reported `GUARD IS BROKEN`. Root cause:

```python
out = text.replace(OLD, NEW)
if needs_import(out):            # <-- called on the PATCHED text
```

`needs_import` is `"realpathSync" not in text.split(OLD)[0]`. After the replace, `OLD` is gone,
so `split(OLD)` returns the whole document — and `NEW` itself contains the token `realpathSync`.
The check therefore always answered *"already imported"* and **the import was never inserted**.
The patched guard then raised `ReferenceError`, which its own `catch` swallowed, falling back to
precisely the broken lexical compare. A silent no-op inside the tool written to fix silent
no-ops, invisible to every static check because the file parses and the fallback is by design.
Fixed at the call site (`needs_import(text)`) plus a hard post-condition that fails loudly if a
file references `realpathSync` without importing it, in both repo trees. The `.mjs` files were
then rewound to their HEAD bytes and re-patched **by the corrected tool**, so what is on disk is
the tool's output rather than a hand edit (`_s2_r2_reapply_guard.py`; rewind via `git show`
bytes, never `git checkout`, which would have applied EOL conversion and turned a 12-line change
into a whole-file CRLF diff — verified `crlf=0` on all four written files).

Only the executable both-states probe caught this. Every cheaper signal — the diff, the
syntax check, the presence of `__isMain`, the tool's own exit 0 — said the repair had landed.

---

## Item 3 — `workflow-authoring` union merge: **proposal written, nothing merged**

Confidence: **almost certain** on the measurements; the merge itself is a decision, not a fact.

Deliverable: **`command-center/S2-WORKFLOW-AUTHORING-UNION-MERGE.md`**.

Measured (`_s2_wa_union.py`, reconstruction control passed both directions): repo 587 lines,
live 354, common 300, **live-only 54, repo-only 287** → genuinely two-directional → `DIVERGED`
→ permanently outside `safe_to_deploy`. It cannot close by waiting.

The substance is one hard conflict, not 341 lines of noise:

- **repo §7** says every fan-in schema MUST set `additionalProperties: false`.
- **live §7** says **do NOT**, and backs it with a dated, id-bearing incident
  (`wf_950ea2e9-e82`, 2026-07-23): `additionalProperties: false` + 6 `required` fields turned
  a `{"raw": …}` double-encode into 5 unrecoverable retries and discarded 57 minutes of a
  10-lens wave.

Deploying the repo copy as-is **deletes that incident report and reinstalls the instruction
that caused it.** Conversely the repo holds 2026-08-12 corrections re-derived from the
installed runtime binary (eight injected globals, not three; `args` verbatim, not one string)
plus five whole sections the live tree lacks. Both sides are load-bearing. The proposal takes
repo as base, grafts the live §7 + checklist + one surviving §2 sentence, and hands the
description choice to the owner with its budget cost priced (live 1,062 chars vs repo 389).

---

## Item 4 — negative-case clauses: **7 applied, budget-neutral, net −22 chars**

Confidence: **almost certain** (verified by post-write re-read *and* by the harness's own
re-injected skill listing, which is an external signal I do not control).

The brief said adding "do NOT use for X, use Y" **costs nothing**. Item 1 refutes that: the
fleet is ~7,300 chars over the render budget, so every added char pushes roughly its own
length of tail description into darkness. **Corrected constraint applied here:
`len(new) <= len(old)` per skill.** This is the C2 pattern — the code was fine, the sentence
was wider than its evidence.

Second constraint, proven executably: **the deploy hop is APPEND-ONLY.** `classify_pair`
compares unique-line SETS, so MODIFYING the description line puts the old text in `left_only`
and the new in `right_only` → `DIVERGED` → refused forever. Measured on real fixtures through
the real classifier: append → `RIGHT-AHEAD`, modify → `DIVERGED`, **and the two verdicts
differ**, so the probe is not inert (`S2-NEGCASE.out.txt` §A). Consequence: a description
edit authored only in the repo can never reach the loaded tree. So each edit was applied to
**all three trees at once**, which also leaves them IDENTICAL and creates no new drift.

| skill | baseline | round 1 | round 2 | Δ vs baseline | negative case added |
|---|---:|---:|---:|---:|---|
| `transcribe` | 216 | 216 | **214** | −2 | → `reframe-transcribe` for word-level timing |
| `tdd-workflow` | 171 | 171 | 171 | +0 | → `test-driven-development` for the bare red-green loop |
| `security-review` | 209 | 208 | 208 | −1 | → `security-scan` for `.claude` config scanning |
| `screenshot` | 220 | 208 | **216** | −4 | → `playwright` / `ui-audit` for web or app UI |
| `e2e-testing` | 133 | 133 | 133 | +0 | → `webapp-testing` for driving a live app |
| `python-testing` | 119 | 117 | 117 | −2 | → `test-driven-development` for the TDD process |
| `research-ops` | 215 | 208 | **207** | −8 | → `deep-research` for the full multi-source pass |

**Round 1: net −22. Round 2: net −17 vs the same pre-round-1 baseline** (+5 against round 1,
spent restoring lost recall words and a positive `Use when` opener). The ceiling was re-anchored
in round 2 from `len(new) <= len(round-1)` to `len(new) <= len(pre-round-1 baseline)`, so the
lane's cumulative effect on the render budget stays ≤ 0 measured from where it found the fleet.
Preconditions enforced and refused-on-failure: skill present in all three trees; description
byte-identical across all three before the edit; the length ceiling; no `": "` or `"` so it
stays a valid YAML scalar; **round 2 adds** a positive-WHEN gate and the lexical-recall gate.
All three round-2 rows were refused on first run until every word loss was declared.

*Detector control:* a deliberately oversized candidate (4,000 chars) is in the table and
**was refused by the length gate** in every run — so "budget-neutral" is a measured property,
not an assertion. Verification after the write: dual-write gate `OK`; all three trees
byte-identical.

> **ROUND-2 CORRECTION — "no new drift created" was REFUTED, and the refuted wording is kept
> here rather than deleted.** It was true of the `skills.daily` deploy target and **false for
> the `~/.agents/skills` vault**: 6 of the 7 edited skills were byte-IDENTICAL to the vault
> before the edit and DIFFER after, moving `needs_merge` 397 → 403 (`IDENTICAL` 226 → 220,
> `DIVERGED` 96 → 102 — the arithmetic matches to the file). Because a description MODIFY
> classifies `DIVERGED` — this lane's own executable proof — those 6 are now permanently
> refused by the deploy hop, i.e. the item-4 edit added 6 files to the very orphan pile item 2
> exists to diagnose.
> **Correctly scoped claim:** *no new drift against `skills.daily`; +6 newly-diverged files
> against the vault.* The vault is outside this lane's declared write scope, so the remedy is
> this sentence plus a **handback**, never a write. Settling experiment (owner): copy the
> description lines into `~/.agents/skills` and re-run the dry-run — `needs_merge` must return
> to 397. Round 2 re-ran the dry-run and it still reads **403**, so round 2 added none of its
> own (its 3 edits and the guard fix all touch files that were already `DIVERGED`).
>
> **ROUND-3: that settling experiment has now been RUN, and the prediction holds.** A prediction
> inside a handback is a claim, not a receipt. `_s2_r3_vault.py` executed it through the real
> `deploy-skills-daily.plan()` classifier on a temp COPY of the seven skill directories — the
> real `~/.agents/skills` was never written, and the guard census re-confirms it (6 vault files
> still on the old lexical guard, unchanged). State A: `DIVERGED 7`, all seven `SKILL.md`
> refused. State B, after the *minimal* action the handback specifies (replace the description
> line, not the file): `IDENTICAL 6 / DIVERGED 1`, **6 reconciled** — i.e. 403 → 397 exactly as
> predicted. Six of the seven differ from the vault by **exactly one line**.
> Controls: the two states give different verdicts (identical counts would make the probe inert),
> and `tdd-workflow` — 4 differing lines, already `DIVERGED` before round 1, therefore *not* part
> of the +6 — is a built-in negative control that must NOT reconcile, and did not. My first
> version copied whole files, reported the self-contradicting *"7 of 6 reconciled"*, and killed
> that control; recorded rather than deleted.

Census, re-derived independently (`_s2_appendonly_and_negcase.py` §B, 328 skills): states
WHEN 257 (brief: 261) · states a NEGATIVE case **79** (brief: 69) · says what it RETURNS
**54** (brief: 54 — exact). The negative-case gap is marker-definition width, not a
contradiction; the brief's direction is confirmed.

> **ROUND-2 CORRECTION — the WHEN census moved 257 → 256 and round 1 did not disclose it.**
> Worse than an omission: the count was right **by accident** and the attribution was wrong in
> both directions. The round-1 regex `\b(use when|when the user|triggers?|use this)\b` matches
> `"Do NOT use when …"` — a NEGATIVE clause — as a positive statement of when to use a skill.
> Measured with a detector that strips negative clauses first (`_s2_r2_census.py`, control
> anchored to the frozen round-1 blob so it keeps discriminating after its own fix):
>
> | | round-1 detector | negative-aware detector |
> |---|---|---|
> | skill it says lost a WHEN | `research-ops` | `transcribe` |
> | verdict | **mis-attributed** — `research-ops` only changed marker wording (`Use when the user wants` → `Use for`) and still states when to use itself | **the real regression** — `transcribe` lost its only positive opener; the sole surviving `use when` sits inside `Do NOT use when` |
>
> Both detectors report a net of −1, which is why the regression was invisible: the total was
> correct while naming the wrong skill and masking the right one. **Round 2 repaired
> `transcribe`**; the census is now `PRE 268 → R1 267 → R2 268`, **net +0 vs pre-round-1**, and
> **0** skills lost a WHEN. Disclosed limitation: the negative-aware detector accepts
> `use for` / `use to` as positive markers, which is why `research-ops` passes it; under a
> stricter marker set it would fail too, and round 2 restored its `Use when` opener anyway.

> **ROUND-2 CORRECTION — "Do NOT shorten descriptions" was an explicit instruction and round 1
> deviated from it.** Round 1 framed this as the brief being refuted on cost; the brief was
> *also* protecting the lexical recall surface, and that part was not refuted. Resolving the
> two reviewers who disagreed on the count (audit said 5 of 7 shorter, verifier said 4): from
> the raw deltas the **verifier is right — 4 of 7** were shorter after round 1
> (`security-review` −1, `screenshot` −12, `python-testing` −2, `research-ops` −7).
> Round 2 replaces the char-length proxy with a **mechanical lexical-recall gate**: every
> content word in the pre-round-1 baseline must survive in the new description **or in the
> skill name**, and any remaining loss must be declared per skill or the row is refused. It
> refused all three round-2 rows on first run until each loss was enumerated. Under it, all
> seven skills this lane touched now pass with **zero undeclared losses**, and the lane's
> cumulative length delta is **−17 chars vs the pre-round-1 baseline** (`_s2_r2_finalverify.py`
> V3/V4). Restored: `speech` and `speakers` (transcribe), `system` (screenshot), and a positive
> `Use when` opener on both `transcribe` and `research-ops`.
> One refinement of the audit's own finding: with a substring-aware matcher only **`speech`**
> was a true loss — `speakers` remained reachable inside `known-speaker hints`. Both are
> restored regardless. Newly declared loss, disclosed inline: `transcribe` no longer says
> `known-speaker hints` (216 chars cannot hold the opener, `diarization`, and that phrase at
> once); `speakers` and `diarization` both survive.

### Self-inflicted defect, its blast radius, and the revert

The first `--apply` **corrupted 21 files** (7 skills × 3 trees): the writer loop unpacked
`rows` without the new *text*, so the identifier `new` still held the last value of the
earlier loop — the 4,000-char control string — and every description was replaced with 4,000
`x`. The length gate was working correctly; the bug was downstream of it, in the writer.

- **Caught by** the script's own POST-WRITE RE-READ, which compares what is on disk against
  what was intended: `7/7 MISMATCH`, `FAILED:s2-negcase`. A run that reported success without
  that check would have shipped the corruption silently.
- **Blast radius traced and closed** (`_s2_restore_negcase.py`): 14 git-tracked files (clean
  at HEAD before the write) plus 7 untracked `skills.daily` files. All 21 restored from
  `git show HEAD:.agents/skills/<n>/SKILL.md`, which is also the correct value for
  `skills.daily` because the applier's P2 precondition had already proven the description was
  byte-identical across the three trees. Three controls: corruption signature present in **0**
  files fleet-wide · **0** mismatches vs HEAD · `git status` on both skill trees **CLEAN**.
  Independently confirmed by the harness re-injecting the skill listing with the original
  seven descriptions.
- Writer fixed (text now travels in the row, plus a length assertion), re-applied, verified.

---

## Prior art found in repo (read before measuring — recall, not detection)

`command-center/grounding/` already held a dead SKILLS2 round: `_s2_render_probe.py`,
`_s2_bytestable.py`, `_s2_vault_guard_exec.ps1` were all written and **never run to disk**
(the grounding artifact was still a bare skeleton; only `S2-RENDER-PROBE.json` existed, and
its Discriminator-2 table — the single most decisive result — lives only in stdout, which was
never captured). Round 1 ran all three and committed their output. That is the C1 total-loss
pattern: the analysis existed and was unrecoverable because nothing was written as it went.

Also reused rather than rebuilt: `_g5_bare_desc_probe.py`, `_g6_second_root_probe.py`
(refutes the second-enumeration hypothesis), `_g7_greedy_budget_solve.py` (the in-sample fit
this lane extended out-of-sample), `G-BARE-DESC.json` (the 01:35 snapshot that made the
byte-stability control possible).

## External SOTA

Not consulted; not needed. Every question in this lane was answerable by an exact algorithm
over local files, which per the fan-out contract §C4 is exactly the case where an algorithm
beats judgement. Confirmed here: the decisive results all came from a differ, a set
intersection, and a budget solver with a decoy control.