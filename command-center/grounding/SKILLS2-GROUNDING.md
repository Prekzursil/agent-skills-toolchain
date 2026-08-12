# LANE SKILLS2 — grounding artifact (write-as-you-go)

STATUS: **MEASURED**, round 1. Every verdict below names the probe that produced it and the
control that proves the probe can fail. Raw stdout for each is committed beside this file.

COVERAGE — what is NOT measured, stated up front:
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

- 328 skills, **115,478** description chars total; budget fitted at **~108,144**.
- The fleet is **~7,300 chars OVER**. That is the entire defect.
- **Rewriting the 26 descriptions cannot fix this** — the orchestrator's instruction not to
  is confirmed by measurement, not taken on faith. The levers are (a) fewer curated skills,
  (b) shorter descriptions *somewhere*, or (c) raising the budget if it is configurable.
  Quantified: the 11 over-spec descriptions hold 13,155 chars; capping all 11 at the 1,024
  spec ceiling frees **1,891** chars = 26% of the need. Removing ~28 median-length skills
  (263 chars) frees ~7,364 = the whole need. **Not applied — owner's call.**

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

**Detector-control caveat, disclosed:** the use-vs-mention split in `_s2_vault_gap.py` is
**partially inert** — it found 0 mention-only files, and it mislabels
`ui-audit/_fix_main_guard.py` (the *repair* script, which contains the old pattern as a Python
string literal) as a USE. The six vault files were therefore confirmed individually by
reading their guard lines, not by trusting the classifier. The result does not rest on the
inert half.

**New finding, in scope, NOT fixed:** the repo itself has a **seventh** `ui-audit` entry point
still on the old guard — `.agents/skills/ui-audit/dead_button_crawl.mjs:280`
(`if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {`). So "fixed 6/6
in the repo" is true of the six named files and misses this one. Left for the owner: it is a
one-line change but it must land in `skills/` and `.agents/skills/` together for the
dual-write gate, and this lane had no mandate to touch it.

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

| skill | old | new | Δ | negative case added |
|---|---:|---:|---:|---|
| `transcribe` | 216 | 216 | +0 | → `reframe-transcribe` for word-level timing |
| `tdd-workflow` | 171 | 171 | +0 | → `test-driven-development` for the bare red-green loop |
| `security-review` | 209 | 208 | −1 | → `security-scan` for `.claude` config scanning |
| `screenshot` | 220 | 208 | −12 | → `playwright` / `ui-audit` for web or app UI |
| `e2e-testing` | 133 | 133 | +0 | → `webapp-testing` for driving a live app |
| `python-testing` | 119 | 117 | −2 | → `test-driven-development` for the TDD process |
| `research-ops` | 215 | 208 | −7 | → `deep-research` for the full multi-source pass |

**net −22 chars.** Preconditions enforced and refused-on-failure: skill present in all three
trees; description byte-identical across all three before the edit; `len(new) <= len(old)`;
no `": "` or `"` so it stays a valid plain YAML scalar.

*Detector control:* a deliberately oversized candidate (4,000 chars) is in the table and
**was refused by the length gate** in every run — so "budget-neutral" is a measured property,
not an assertion. Verification after the write: dual-write gate `OK`; deploy-drift reports
**none** of the 7 in `needs_merge` (no new drift); all three trees byte-identical.

Census, re-derived independently (`_s2_appendonly_and_negcase.py` §B, 328 skills): states
WHEN 257 (brief: 261) · states a NEGATIVE case **79** (brief: 69) · says what it RETURNS
**54** (brief: 54 — exact). The negative-case gap is marker-definition width, not a
contradiction; the brief's direction is confirmed.

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
