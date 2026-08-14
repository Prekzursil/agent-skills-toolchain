# SKILL-FLEET SOTA PLAN

**Lane:** PLAN (synthesis of OVERLAP + DRIFT + QUALITY lenses, plus this lane's own re-probes)
**Date:** 2026-08-14
**Status:** proposal only. Nothing on disk was changed by this lane. No skill touched, no commit made.
**Trees referenced throughout:**

| tag | path | role |
|---|---|---|
| LIVE | `C:\Users\Prekzursil\.claude\skills.daily` (symlink target of `~/.claude/skills`) | the only tree Claude Code reads |
| VAULT | `C:\Users\Prekzursil\.agents\skills` | Codex-side deploy target |
| REPO | `C:\Users\Prekzursil\source\ast-integrate\.agents\skills` | designated source of truth |
| PLUGIN | `C:\Users\Prekzursil\.claude\plugins\cache\claude-plugins-official\superpowers\6.3.0\skills` | installed superpowers 6.3.0 |

---

## 0. HEADLINE — and where the program's framing was wrong

**The consolidation premise did not survive contact with evidence. Zero destructive actions passed
verification (0 SURVIVED / 2 REFUTED). Section 4 of this plan is therefore empty by measurement, not by
caution.** The value in this program is entirely in *fix* and *upgrade*, and the fleet is smaller-in-index
than the brief assumed only because the previous consolidation already happened.

Four things the orchestrator/lenses got wrong that would have caused real damage or wasted work.
I re-probed each myself.

**W1. `writing-skills` is NOT live-only, and is NOT "one accidental delete away from unrecoverable loss."**
The refuted-overlap lens's corrected-recommendation #3 asserts it is absent from the repo and must be
urgently reconciled into git. Measured false:

```
Get-FileHash <LIVE>\writing-skills\SKILL.md   -> 2809E46D646A6F136C591A7657128DE919A88B5C67486F4F24A79EC138EFAA2E
Get-FileHash <REPO>\writing-skills\SKILL.md   -> 2809E46D646A6F136C591A7657128DE919A88B5C67486F4F24A79EC138EFAA2E
git ls-files --error-unmatch .agents/skills/writing-skills/SKILL.md -> tracked
```
LIVE and REPO are **byte-identical (SHA256 equal) and git-tracked**. Sizes: LIVE 49,717 / REPO 49,717 /
VAULT 23,120 / PLUGIN 26,360. Only **VAULT** is stale. The urgency framing is wrong and the proposed
DO-NOW is a no-op. *Almost certain (90-99%)* — hash equality plus `ls-files` are two independent checks.
The real (much smaller) finding is that VAULT is 26.6 KB behind, which is a vault-rebuild item (§5.5).

**W2. A case-insensitive corruption detector manufactures a false LIVE hit — and the entire direction
decision rests on "LIVE is clean."** The corruption signature is a **case change** (`codex` -> `Codex`).
PowerShell `Select-String` is case-INSENSITIVE by default. My first sweep returned LIVE=1, VAULT=20,
REPO=10. The single LIVE hit was `design-studio-session/SKILL.md:49` matching `by:codex` — the *correct*
lowercase form — against my `by:Codex` pattern. Re-run with `-CaseSensitive` and a both-states control
(the detector must still fire on the known-bad `REPO\ida-multi-mcp\SKILL.md` line, and does — count 1):

```
-CaseSensitive totals over 7 markers:  LIVE=0   VAULT=18   REPO=6
```
The DRIFT lens reported 0/19/9 over its 6-marker set. **Direction is identical and robust; magnitude is
detector-dependent.** Anyone executing §1.2 MUST re-measure with a case-sensitive detector at execution
time. A case-insensitive one would have put a phantom marker in LIVE and broken the premise the whole
reconcile direction depends on. *Almost certain (90-99%)* on the direction; *uncertain (20-55%)* on any
exact count until the marker set is frozen.

**W3. The grounding pack's fleet arithmetic does not reproduce, in two places.** It states "328 of 328"
curated skills; `(Get-ChildItem <LIVE> -Directory).Count` returns **329**. It states 110 differing files
and "21 of the first 40 shared skills already differed"; the DRIFT lane measured 135 files across 74
skills and only 8-of-first-40. Those two briefed numbers are also mutually inconsistent (52.5% of skills
differing cannot be covered by 110 files at ~1.8 files/skill). Per the single-signal rule, the source
probe was never declared, so it is zero signals, not one. **Do not carry 110 or 21/40 into any
execution.** *Almost certain (90-99%)* that the briefed pair is unreproducible.

**W4. The refuted MERGE proposal (`two-tier-verify` + `smallest-check-ladder`) named the right defect and
the wrong remedy.** The missing-cross-reference half is real and I confirmed it bidirectionally
(`two-tier-verify` mentions `smallest-check-ladder` 0 times; the reverse is also 0). But the two skills
hold asymmetric unique capability. The fix is two lines of routing text (§1.7), not a merge.

---

## 1. DO NOW — no risk, no owner decision required

Every item is a text edit with a one-line revert. Ordered by value/risk. **Edit the REPO copy and deploy
via `scripts/deploy-skills-daily.py`; do not hand-edit the deployed tree** (harness-vcs-hygiene; and
`writing-skills` documents the deploy tool as the last hop). Exception: §1.2, whose whole point is that
LIVE currently holds the *correct* bytes.

### 1.1 Un-invert the three corrupted Red-Flag rows in `verification-before-completion` — HIGHEST VALUE

**File:** `<REPO>/.agents/skills/verification-before-completion/SKILL.md` lines **68, 70, 72**
(LIVE carries the same corruption; VAULT/REPO sizes match LIVE).

An ASCII transliteration turned `≠` into `=` and **inverted the meaning of a skill that sits on the
"am I done?" path**. Measured, with the plugin as control:

| line | curated (LIVE/REPO) — WRONG | plugin 6.3.0 line — CORRECT |
|---|---|---|
| 68 | `\| "I'm confident" \| Confidence = evidence \|` | 66: `Confidence ≠ evidence` |
| 70 | `\| "Linter passed" \| Linter = compiler \|` | 68: `Linter ≠ compiler` |
| 72 | `\| "I'm tired" \| Exhaustion = excuse \|` | 70: `Exhaustion ≠ excuse` |

**Edit:** restore `≠` in those three cells. **Rollback:** revert three characters.
**Why first:** it is the only defect in the fleet that actively teaches the opposite of its own thesis,
and it does so on the completion-claim path that gates every other skill's "done".
*Almost certain (90-99%)* — read both files, plugin acts as the correct-state control.

### 1.2 Repair the vendor-name substitution corruption in VAULT and REPO (LIVE -> REPO/VAULT)

A blind `Claude`->`Codex` find-and-replace produced degenerate strings that no human wrote. LIVE escaped
it. Anchor, verified from the git object store rather than the filesystem:

```
LIVE   ida-multi-mcp/SKILL.md:74  Register as an MCP server (Claude Code / Codex / Cursor):
VAULT  ida-multi-mcp/SKILL.md:74  Register as an MCP server (Codex / Codex / Cursor):
REPO   ida-multi-mcp/SKILL.md:74  Register as an MCP server (Codex / Codex / Cursor):
```

**Direction is provable and one-way:** `Claude Code`->`Codex` destroys information, so the coherent
three-distinct-tool LIVE string is the pre-image. You cannot recover `Claude Code` from `Codex`.
**Therefore LIVE wins here regardless of dates** — and dates point the wrong way on exactly these files
(REPO commit 2026-07-21 vs LIVE mtime 2026-07-12), so a "newer wins" rule would propagate the corruption
in the 8 cases where it matters most.

**Targets (8):** `design-studio-session`, `execution-grounded-bon`, `ida-multi-mcp`, `pdf-reader`,
`compchem-validators`, `re-triage-preflight`, `agent-as-judge`, `workflow-authoring`.
**Highest-severity two:** `design-studio-session` and `execution-grounded-bon` are the two skills whose
entire thesis is cross-vendor independence; `Claude + Codex` collapsed to `Codex + Codex` inverts the
documented safety property into same-vendor agreement — the exact correlated-blind-spot failure they
exist to prevent. `design-studio-session`'s corruption is in its **description**, i.e. always-loaded.

**Pre-flight (mandatory, per W2):** re-run the marker sweep **case-sensitively**, with a both-states
control asserting the detector still fires on `REPO\ida-multi-mcp\SKILL.md`. My case-sensitive baseline:
LIVE=0, VAULT=18, REPO=6.
**Rollback:** `git revert` the single scoped commit; VAULT is a deploy target and is re-derivable.
*Almost certain (90-99%)* on direction (three independent signals: filesystem, git blob, and this
session's own loaded description text for `design-studio-session`).

### 1.3 Replace the `gh pr create` heredoc with `--body-file` in `finishing-a-development-branch`

**File:** `.../finishing-a-development-branch/SKILL.md:96`
```
gh pr create --title "<title>" --body "$(cat <<'EOF'
```
This is the exact shape `rules/common/windows-shell.md` §10 records as killing 6+ consecutive Bash calls
in one session: the Bash tool wraps the command in single quotes, so any apostrophe in a PR body
(`the repo's own CI`, `don't`) closes the quote early and the call dies with
`unexpected EOF while looking for matching '` before a byte runs. A PR body is prose; apostrophes are
near-certain. A body containing literal `@'`/`'@` cannot be written this way at all (§9).

**Blast radius:** the project `CLAUDE.md` mandates this skill before *every* branch finish, and six
superpowers plugin-cache versions carry the same block.

**Fleet-wide measurement that makes this bigger than one skill:**
```
Select-String -Path <LIVE>\*\SKILL.md -Pattern 'body-file'   ->  0
```
**Zero of 329 curated skills know the fix.** So this edit is also the seed of a pattern (see §2.5).
**Edit:** `gh pr create --title "<title>" --body-file <path>` with a one-line note that the body is
written with the Write tool first. **Rollback:** restore the heredoc.
*Almost certain (90-99%)* that the text is present and the documented failure applies.
UNVERIFIED: I did not execute a `gh pr create` to reproduce the failure in this session — the failure is
cited from the ledger-proven rule, not re-measured. Settling experiment: run `gh pr create` through the
Bash tool with a body containing an apostrophe and confirm the `unexpected EOF` error.

### 1.4 Repoint the 5 stale `design-review-loop` referrers BEFORE the tombstone expires

`design-review-loop`'s own description opens *"MOVED — renamed to design-studio. This is a redirect
tombstone…"* and costs ~663 chars of always-loaded index. Five live skills name it **inside their
frontmatter description** — verified by reading only the first 12 lines of each SKILL.md:

`critique-panel` (3 hits) · `design-studio` (3) · `design-studio-session` (3) ·
`design-tokens-pipeline` (2) · `ui-drive` (3)

**Ordering is load-bearing:** retiring the tombstone first breaks the very redirect it exists to provide.
Repoint all five to `design-studio`, *then* the tombstone may expire on the owner's schedule (§5.4).
**Rollback:** the five edits are pure string substitutions.
*Almost certain (90-99%)* — exact grep with per-file counts plus a frontmatter-scoped re-check.

### 1.5 Trim the dead "Replaces the per-mode wrappers…" clause from `codex-orchestrate`

Its description ends by naming nine skills that no longer exist. Verified with a positive control:

```
codex-audit .. codex-triage   -> Test-Path False  (9 of 9)
CONTROL codex-orchestrate     -> True
CONTROL codex-consult         -> True
```
This is ~130 chars of permanently-resident index naming nine non-existent skills. **Trim only the
trailing `Replaces …` sentence.** The rest of the description is doing real intent-to-tool routing and
must not be touched. **Rollback:** restore one sentence.
*Almost certain (90-99%)* that the names are dead; *uncertain (20-55%)* that the token saving matters —
the reason to do it is index correctness, not budget.

### 1.6 Restore the dangling `code-reviewer.md` template in curated `requesting-code-review`

```
SKILL.md:105  See template at: requesting-code-review/code-reviewer.md
curated has code-reviewer.md? False
plugin  has code-reviewer.md? True
```
Five references to `code-reviewer` across the body; the local template is absent. Copy it from
`<PLUGIN>/requesting-code-review/code-reviewer.md`. Note the *agent* (`superpowers:code-reviewer`) comes
from the plugin and is fine — only the local file reference dangles. **Rollback:** delete the copied file.
*Almost certain (90-99%)* — direct `Test-Path` on both trees.

### 1.7 Add the missing reverse cross-references (5 one-line description edits)

Pure additive routing text; no body changes, no merges. Confirmed asymmetries:

| skill to edit | add pointer to | why |
|---|---|---|
| `two-tier-verify` | `smallest-check-ladder` | **0 refs in BOTH directions** — the only overlapping pair in the fleet with routing in neither. This is the correct remedy for the REFUTED merge (W4). |
| `smallest-check-ladder` | `two-tier-verify` | as above |
| `hacktricks` | `secsearch` | `secsearch` names it; not vice versa |
| `lolbin-lookup` | `gtfobins-lookup` | `gtfobins-lookup` names it; not vice versa |
| `deep-research` | `research-ops` | `research-ops` names it; not vice versa |

For the first pair, state the split explicitly so a merge is never re-proposed: `two-tier-verify` owns the
commit-boundary OUTER gate, scoped-bisect attribution, and the "three ways a green OUTER loop still lies"
section; `smallest-check-ladder` owns the L0-L3 tiering, mandatory `longrun` wrapping above 60s, the L3
packaged-artifact tier, and diff-scoped coverage.
**Rollback:** remove the added clauses. *Almost certain (90-99%)* on the asymmetries (exact grep);
*uncertain (20-55%)* that they cause real mis-routing today.

### 1.8 Vault hygiene: 3,585 `__pycache__` files and a reserved-device `NUL` file

`C:\Users\Prekzursil\.agents\skills\workflow-monitor\NUL` is a Windows reserved device name (the classic
artifact of a Git-Bash `> NUL` redirect). It crashed a lens's enumeration with
`ValueError: path is on mount '\\.\NUL'` and exists in VAULT only. Separately, 3,585 of the 3,604
VAULT-only files are `__pycache__` (crypto-ctf alone contributes 3,509), and two `.pyc` files are being
diffed as if they were content.
**Removal syntax:** `Remove-Item -LiteralPath '\\?\C:\Users\Prekzursil\.agents\skills\workflow-monitor\NUL'`.
**Rollback:** `__pycache__` is regenerated automatically by Python; the `NUL` file is pure garbage.
Flagged as owner-executed because it is a delete, but no capability is at risk.
*Almost certain (90-99%)* — direct enumeration plus a reproducible exception.

---

## 2. UPGRADE — encode the measured lessons into existing skills

**I probed each target before proposing an edit, so nothing here duplicates text that already exists.**
Skills that already carry their lesson and must NOT be edited are listed at the end of this section.

### 2.1 `dispatching-parallel-agents` <- L6 (write-as-you-go). HIGHEST VALUE IN THIS SECTION

```
Select-String dispatching-parallel-agents/SKILL.md -Pattern 'write-as-you-go|as you go|skeleton' -> 0
fleet-wide  'write-as-you-go'  -> 4 skills of 329     (CONTROL: 'parallel' -> 143)
```
This is the highest-traffic fan-out skill in the fleet and it says nothing about durability. The measured
cost: one review unit ran **70 minutes, produced 691 KB of transcript, and wrote nothing** —
unrecoverable. A relaunched unit under a write-as-you-go mandate produced a truthful artifact in 3 minutes.
**Exact edit — add a `## Durability mandate` section for any unit expected to run >10 min:**
1. Write the artifact IMMEDIATELY as a skeleton with every claim enumerated and marked
   `UNKNOWN - not yet measured`, plus a COVERAGE line naming which sections are unmeasured.
2. REWRITE it at each milestone.
3. Whatever is on disk must ALWAYS be truthful. A partial file with honest UNKNOWNs is a SUCCESS; a
   perfect file that is never written is a total loss.
Include verbatim: *"If it still reads this way, the unit died before measuring anything and no verdict
here may be cited."*
*Almost certain (90-99%)* the gap is real (grep with a live control).

### 2.2 `verification-before-completion` <- L1 (working-tree green != clone green)

```
Select-String verification-before-completion/SKILL.md -Pattern 'clone|fresh clone' -> 0
```
Measured: a fresh clone of the same commit had **31 collection errors** while the working tree reported
**3,910 passed**. The skill that owns the "done" claim has no clone-green row.
**Exact edit — one row in the existing evidence table:**
`| Tests pass | Suite run from a FRESH CLONE of the commit, exit 0 | Working-tree green |`
Pair it with the Windows CRLF corollary (L5): a local formatter green is not CI green — verify against the
**stored blob** via `git ls-files -s` + `git cat-file -p`, never `git archive` or `git show <rev>:<path>`,
both of which return CRLF worktree bytes on this box.
Do this **after** §1.1, so the row lands in a file whose Red Flags already read correctly.

### 2.3 `systematic-debugging` <- L3 (detector controls / both-states)

```
Select-String systematic-debugging/SKILL.md -Pattern 'both-states|known-broken|control' -> 0
```
Eight-plus detector failures in one program, and this session produced a ninth (W2).
**Exact edit — add a `## Control your detector` step before the hypothesis loop:**
- Before a probe's silence counts as evidence, run it against the **known-broken** state and confirm it
  FIRES there. A probe silent in both states measures nothing.
- A control that cannot distinguish the two hypotheses is not a control — state both hypotheses first and
  ask what a PASS looks like under each.
- Two named traps, both with real anchors: `grep -c pat || echo 0` emits a **doubled zero** (`grep -c`
  prints `0` *and* exits 1, so the fallback also fires); and **a case-insensitive matcher cannot detect a
  case-change signature** — `Select-String` defaults to case-insensitive and produced a phantom hit in
  this very program (W2).
*Almost certain (90-99%)* the gap is real.

### 2.4 `receiving-code-review` <- L11 (overclaims outnumber real defects ~5:3)

```
Select-String receiving-code-review/SKILL.md -Pattern 'overclaim|wider than the evidence' -> 0
```
Measured across three lanes and four adversarial reviews: **5 of 8 refuted claims were overclaims, not
broken fixes** — the code was right and the *sentence* was wider than the evidence. This program
reproduced the ratio exactly (W1 is an overclaim; §1.2 is a real defect).
**Exact edit — add `## When a finding is an overclaim`:**
- On a REFUTED overclaim, fix the SENTENCE, not the code: state the scope actually measured, disclose the
  residual INLINE, name the settling experiment. A correctly-scoped claim is CONFIRMED.
- A residual gap that is honestly scoped and disclosed is NOT a refuted item and must NOT block.
- Record that the earlier wording was REFUTED; do not silently delete it.
- Reviewers: an overclaim is a REFUTED verdict **even when the underlying code is fine**.
This also makes the "round N until green" stopping rule tractable rather than unbounded.

### 2.5 `finishing-a-development-branch` <- L8, second half (make §1.3 a stated rule)

Beyond the line-96 fix, add a one-line rule so the pattern generalises: *"Never inline apostrophe-bearing
prose into a shell command. Write it with the Write tool, then pass the path — `gh pr create --body-file`,
`git commit -F <file>`, `python <script.py>`. Not `-m "…"`, not `<<'EOF'`, not `python -c '…'`."*
Justified fleet-wide by the measured `body-file` count of **0 across 329 skills**.

### 2.6 `writing-skills` <- W2 + §3.1 (the vendor-substitution trap)

`writing-skills` is already this estate's skill-fleet operating manual (49,717 B, LIVE == REPO, and it
already documents the four-tree model, the deploy last-hop, the listing-budget mechanics, and two YAML
render traps with measured anchors). Add **one** trap to that existing list: a blind vendor find-and-replace
across the trees produced `Codex / Codex / Cursor`, `Codex + Codex`, `Codex-reflect` and `~/.Codex/…`; the
substitution is information-destroying and therefore one-way, so LIVE is always the pre-image; and any
detector for it must be **case-sensitive**. Cross-reference the new gate from §3.1.
*Likely (55-80%)* that this is the right home rather than a standalone skill — it is where every other
render trap already lives, and adding a 329th skill for one trap is worse than a paragraph in the manual.

### Do NOT edit these — the lesson is already encoded (measured)

| skill | lesson | measured |
|---|---|---|
| `two-tier-verify` | L1 clone-green | 8 hits for `clone` |
| `workflow-authoring` | L10 parallel()/no per-agent timeout | 5 hits for `per-work-unit\|deadlock\|timeout` |
| `mutation-check` | L3 both-states | 3 hits |
| `workflow-monitor` | L9 mtime cannot prove liveness | `SKILL.md:20` explicitly states status comes from the authoritative journal `result`/`started` events, *"not mtime guessing"* |

---

## 3. ADD — new artifacts worth authoring

Only two. I deliberately reject a third that has an existing home (§6.8).

### 3.1 `ci/check_skill_vendor_substitution.py` — a CI gate, not a skill

**Gap is measured, with a control:**
```
Select-String <REPO>\ci\*.py -Pattern 'Codex / Codex|vendor.*substitut|Claude Code / Codex'  -> 0
CONTROL     <REPO>\ci\*.py -Pattern 'skill'                                                 -> 340
```
Five skill gates already exist (`check_skill_context_budget`, `check_skill_deploy_drift`,
`check_skill_description_ratchet`, `check_skill_dual_write`, `check_skill_render_traps`) and **none catches
the corruption class that a previous reconcile actually shipped**. The root cause is documented: the
substitution entered the repo through commit `9513a3bc` (2026-07-21), a commit whose message claims to
land live-authored files, adding `+Register as an MCP server (Codex / Codex / Cursor):` as new content.

**Spec (all four are non-negotiable, each traceable to a measured failure):**
1. **Case-SENSITIVE** matching. A case-insensitive gate cannot see a case-change signature (W2).
2. **Both-states self-test.** The gate must assert it FIRES on a synthetic corrupted fixture, and exit
   non-zero if the fixture passes. A gate that is silent in both states measures nothing.
3. **Fail-closed on implausible counts.** Print `scanned N files across M skills` and exit non-zero at
   zero — a shape change must be loud, not report parity.
4. **It must EXECUTE, not read a claim.** L2: a verifier once returned CONFIRMED for a file asserting
   999,999 passing tests and for three files of 2,000 `x` characters.

**Marker seed set (extend, do not shrink):** `Codex / Codex` · `Codex + Codex` · `by:Codex` ·
`` `Codex` | `codex` `` · `Codex-reflect` · `current Codex model` · `.Codex/` · `Codex Workflow`.
**Rollback:** delete one file; it is additive and gates nothing that exists today.
*Almost certain (90-99%)* that the gap is real.

### 3.2 `skill-tree-reconcile` — a new skill, because no home exists

**Trigger phrases:** "sync my skills", "reconcile the skill trees", "deploy skills to live", "which tree
wins", "live vs vault vs repo", "sync-from-live", "my skills drifted".

**Why it must exist:** the tooling exists (`scripts/sync-from-live.ps1`, `scripts/deploy-skills-daily.py`,
`scripts/sync-skills.ps1`, `scripts/validate-all-skills.ps1`) but the *direction discipline* does not, and
the last reconcile that ran without it **introduced** the §1.2 corruption. The measured facts a reconciler
must not re-derive wrong:

- **There is no safe bulk direction.** Of 99 substantive LIVE-vs-VAULT text pairs: **95 DIVERGED, 4
  LIVE-supersets, 0 VAULT-supersets.** A one-directional sync destroys work in either direction.
  *Honest scope limit, stated inline:* 41 of the 95 are small-delta (<=3 lines/side) and many are a single
  modified line, which the classifier must call DIVERGED by construction. "DIVERGED" means "not a clean
  superset", **not** "95 files of two-sided authored work". The heavyweight set is the ~20 files with >10
  unique lines on both sides.
- **mtime and commit-date are broken direction signals here.** 136 of 337 LIVE SKILL.md share one
  bulk-copy mtime; "repo commit newer" holds for 86 of 95 differing SKILL.md **including all 8 corrupted
  files**; and `gem-hunt` / `re-ensure` are LIVE-supersets while mtime says VAULT is newer.
- **Per-class direction rule** (this is the executable core of the skill):

| class | direction | note |
|---|---|---|
| the 8 vendor-corrupted skills | **LIVE -> REPO/VAULT, ignore dates** | information-destroying substitution is one-way |
| skills where LIVE has a negative-case clause VAULT lacks (34) | **LIVE -> REPO/VAULT** | this is the active anti-overlap work |
| 4 strict LIVE supersets + ~75 orphaned live-only files | **LIVE -> REPO** | |
| CRLF-only differences (34 of 135) | either; **exclude from effort** | 25% of the surface, zero content risk |
| ~20 heavyweight DIVERGED files | **no automatic direction; per-file union merge only** | both sides hold unique lines |
| VAULT as a whole | **rebuild from REPO after the above; never a merge source** | VAULT carries the most corruption (18) and the fewest disambiguation clauses |

- **Never let a mass-vendored tree ride along.** `crypto-ctf` is 12,816 files live vs **2** tracked, is
  **not** gitignored (`git check-ignore` returns nothing) and is **not** staged. A naive sync-from-live
  sweeps ~12,800 files into one commit and buries the 8 real fixes.
- **CRLF discipline:** verify against the stored blob (`git ls-files -s` + `git cat-file -p`); `git archive`
  and `git show <rev>:<path>` return CRLF worktree bytes on this box.
- **Cross-reference** `writing-skills` (the four-tree model) rather than restating it.

*Likely (55-80%)* that a standalone skill is right rather than a `writing-skills` section — it is
operational-procedure content with distinct triggers, and `writing-skills` is already 49.7 KB.
UNVERIFIED: whether `sync-from-live.ps1` can express per-class direction at all; I did not read it.
Settling experiment: `scripts/sync-from-live.ps1 -Report json` and check for a per-path include/exclude
mechanism before writing the skill's procedure section.

---

## 4. CONSOLIDATE — **EMPTY BY MEASUREMENT**

**Nothing survived verification. 0 SURVIVED / 2 REFUTED.** There is no consolidation to execute and no
rollback to write, because no merge or retirement is recommended.

This is the program's most important negative result, so state it plainly rather than softening it:

- **REFUTED — retire 14 bare curated superpowers copies.** The duplication is real (9 of 14 descriptions
  byte-identical to the plugin's) but the bodies are **0 of 14 identical**, and 7 of 14 curated SKILL.md
  are *larger* after CRLF normalisation. `executing-plans` curated implements batched execution with human
  review checkpoints (`batch` x8); the plugin contains the string `batch` **zero** times. Retiring it
  silently deletes the checkpoint between batches. `subagent-driven-development` curated documents a
  two-stage spec-then-quality review (plugin: a different single-reviewer architecture); I confirmed
  LIVE=VAULT=REPO=10,483 B vs PLUGIN=32,339 B — different documents, not stale copies. The
  `docs/plans/YYYY-MM-DD-<topic>-design.md` convention appears in curated `brainstorming` and
  `writing-plans` and in **zero** plugin markdown anywhere.
- **REFUTED — merge `two-tier-verify` + `smallest-check-ladder`.** Asymmetric unique capability on both
  sides. Correct remedy is the two cross-references in §1.7.

**The consolidation already happened, at the deploy layer, before this program started.** The 9 codex-*
wrappers `codex-orchestrate` claims to replace are absent from LIVE (9/9, positive control passed) and
absent from VAULT; they remain tracked in REPO with a 2026-03-23 commit date. Nineteen REPO skills are
undeployed in total. Nothing to do; nothing at risk.

---

## 5. OWNER DECISIONS

### 5.1 The 23 `source-command-*` skills — repair in place, relocate, or leave?

**Measured, not inferred:**
- 23 of 23 have a same-named live command at `~/.claude/commands/<base>.md` (0 missing). Body similarity
  after frontmatter strip: 22 of 23 score 0.906-0.994 (control pair scores 0.0218).
- The Claude->Codex rewrite corrupted their paths. `~/.Codex/skills/continuous-learning-v2/scripts/
  instinct-cli.py` -> `Test-Path False`. The `.claude` twin -> `True`. The `.agents` twin -> `True`.
  Fleet-wide there are **44** `.Codex/` references (control: 191 `.claude/`).
- **This lane resolves the lens's open question:** `~/.codex/skills` contains exactly **two** entries,
  `.system` and `skill-stocktake` — **neither is a `source-command-*`**. So they are not being delivered
  to Codex's own skills directory.

**Read:** on the Claude side they are redundant (the working original is the slash command, already
loaded); on the Codex side they are both undelivered and path-broken. An agent that auto-picks the skill
instead of the command runs a command against a file that does not exist.
**Options:** (a) repair the `~/.Codex/` -> `~/.claude/` substitution in place (non-destructive, reversible,
smallest step); (b) relocate them out of the Claude-curated tree into a Codex delivery tree; (c) leave.
**Recommendation: (a) now, and decide (b) separately.** I am explicitly **not** recommending deletion —
the mandate defaults to KEEP and I did not establish that Codex has no other path to this tree.
UNVERIFIED: whether Codex reads `~/.claude/skills.daily` via a `CODEX_HOME`/config route. Settling
experiment: read `~/.codex/config.toml` for a skills path.

### 5.2 The `skillOverrides` name-only lever — untested on this box

`~/.claude/settings.json` contains `skillListingBudgetFraction` but **does not contain `skillOverrides`**
(measured). So the cheapest index-reclaim lever has never been exercised here.
`writing-skills` states that plugin skills are NOT affected by it — which, if true, **inverts the retire
argument**: keeping the 14 bare copies is a *precondition* for tuning them at all, and retiring them would
convert 14 tunable index entries into 14 untunable ones.
**Owner experiment before relying on it:** set `name-only` on one bare skill and one plugin skill, restart,
compare the `/context` Skills row before and after. *Uncertain (20-55%)* until run.

### 5.3 `crypto-ctf`: vendored-but-uncommitted, or orphaned work?

12,816 files live, 2 tracked, no ignore rule, nothing staged. Only the owner knows whether this tree is
reproducible from upstream. Until answered, any reconcile must exclude it explicitly (§3.2).

### 5.4 When may the `design-review-loop` tombstone expire?

After §1.4 lands, not before. It costs ~663 always-loaded chars. Owner's call on timing.

### 5.5 VAULT's role: deploy target or peer?

This plan treats VAULT as a **derived deploy target to be rebuilt from REPO**, never a merge source —
it carries the most corruption (18 markers), is the stalest tree (newest SKILL.md cluster 2026-07-19 vs
LIVE files touched 2026-08-14), diverges from REPO *more* than LIVE does, and is 26.6 KB behind on
`writing-skills` alone. Confirm before executing §3.2. *Likely (55-80%)* this is right; it is a judgement
call, not a measurement.

### 5.6 Adopt the plugin's richer companion assets additively?

Zero-capability-cost option: copy in `brainstorming/visual-companion.md`,
`test-driven-development/writing-good-tests.md`, `using-superpowers/references/*-tools.md`,
`systematic-debugging/root-cause-tracing.md` and `find-polluter.sh` **without** removing curated bodies.
Captures 6.3.0's genuine gains with no deletion.

---

## 6. EXPLICITLY NOT DOING — and why

1. **Not retiring the 14 bare curated superpowers copies.** REFUTED. Bodies 0-of-14 identical; 7-of-14
   larger; behavioural divergence (batched execution with review checkpoints; two-stage review) that
   exists in no other copy. Retiring destroys capability. (§4)
2. **Not merging `two-tier-verify` and `smallest-check-ladder`.** REFUTED. Asymmetric unique capability.
   Cross-references instead (§1.7).
3. **Not deleting the 9 `codex-*` wrappers from the repo.** Already undeployed everywhere; deployment
   state was compared, **content was not**. A retire decision requires reading all 9 bodies against
   `codex-orchestrate`. Keep in history.
4. **Not deleting the `design-review-loop` tombstone yet.** Retiring before §1.4 breaks the redirect it
   exists to provide.
5. **Not deleting the 23 `source-command-*` skills.** Default-to-KEEP; the Codex delivery question is
   unresolved (§5.1).
6. **Not flagging `learned` as an orphan.** It is the only skill in the fleet with
   `disable-model-invocation: true` + `user-invocable: false`, and its body says the marker exists
   precisely so inventory tools recognise the folder as intentional. Deleting it orphans `/learn` output
   *and* guarantees the next audit re-flags it.
7. **Not bulk-syncing in either direction, and not using mtime or commit-date to pick one.** 95 of 99
   substantive pairs DIVERGED; 0 VAULT-supersets; date-based direction points the wrong way on all 8
   corrupted files.
8. **Not authoring a `detector-control` skill.** The discipline already lives in
   `rules/common/single-signal-verification.md`, which is **always-on** (no `paths:` frontmatter). A new
   skill would be a lazily-loaded, weaker copy of an always-loaded rule. The right move is §2.3 — put the
   *operational* form into `systematic-debugging`, and leave the rule as the canonical statement.
9. **Not "reconciling `writing-skills` into git."** Already there and byte-identical (W1). Only the VAULT
   copy is stale, which §3.2/§5.5 handles as a rebuild.
10. **Not touching the four families the brief flagged as duplicates** — `*-deploy`, `hexstrike-*`,
    `humanizer/*`, `playwright/*`, `voice-*`, `video-*`, `secsearch/*`. High description similarity is a
    shared *template*, and 83 of 328 descriptions already carry explicit negative routing
    ("NOT for X, use Y"). Payload inventory refutes the `*-deploy` case outright: `cloudflare-deploy`
    carries ~300 reference files, `render-deploy` 20 refs + 6 blueprint templates, `vercel-deploy` a
    9,178 B `deploy.sh`. Merging collapses a working auto-pick router for zero real saving, since only the
    ~85-token description is resident. *Likely (55-80%)* — KEEP-by-default under the mandate, since bodies
    were not read.
11. **Not editing `two-tier-verify`, `workflow-authoring`, `mutation-check`, or `workflow-monitor` with
    their "missing" lessons.** Measured: each already carries it (§2, closing table).
12. **Not carrying the briefed "110 files / 21-of-40 / 328-of-328" figures into execution.** Unreproducible
    and internally inconsistent (W3). Re-measure at execution time.

---

## 7. Execution order and the one gate that matters

```
§1.1 -> §1.2 (with the case-SENSITIVE pre-flight) -> §1.3-§1.8
     -> §2.2 (lands cleanly only after §1.1)
     -> §2.1, §2.3, §2.4, §2.5, §2.6
     -> §3.1 (gate; must self-test both-states before it is trusted)
     -> §3.2 (skill; must read sync-from-live.ps1 first)
     -> §5 owner decisions
```

**The one gate:** before *any* write in §1.2, re-run the marker sweep **case-sensitively** with a
both-states control proving the detector fires on the known-bad
`<REPO>\ida-multi-mcp\SKILL.md:74`. If that control does not fire, stop — the instrument is broken and
every count in §1.2 is unreadable. This program has already produced one phantom finding from exactly that
mistake (W2), and the previous reconcile shipped the corruption this plan exists to remove.

**Everything in §1 and §2 is a text edit with a one-line revert. §3 is purely additive. §4 is empty. There
is no irreversible step anywhere in this plan.**

---

## 6. EXECUTION CORRECTIONS — measured while applying this plan (2026-08-14)

Recorded here rather than by editing the items above, so the original claim and its refutation
both stay visible.

### 1.1 APPLIED and verified — commit `e4c00b2c`

Confirmed before editing: the three cells were inverted in **five paths resolving to four
distinct files** (both repo trees, the vault, and `~/.claude/skills.daily`; `~/.claude/skills`
resolved to the same file and was correctly not rewritten twice). Two independent signals — the
table's own pattern (5 of 8 rows refute their excuse; the 3 that do not are exactly the `=`
rows) and **six** upstream plugin versions all carrying the correct form. 12 cells repaired,
idempotent on re-run.

### 1.3 APPLIED — commit `cf023def`

The item was marked UNVERIFIED; settled here. The heredoc shape was present at `:96`,
`body-file` occurred **0 times** in the file, and the `--body-file` path round-trips a
two-apostrophe body cleanly. After the edit a naive grep still reports the heredoc — at line
102, `in_code_fence=False`, inside backticks in the prose explaining why not to use it. A
mention, not a use, confirmed with a fence-aware reader.

**Footnote worth keeping.** Appending this very section failed on the first attempt with
`unexpected EOF while looking for matching '` — the identical defect, hit minutes after fixing
it, because the prose above contains apostrophes and it was being appended via a shell heredoc.
The fix is the one now written into the skill: author the payload with the Write tool and pass a
path. A rule you have just written is not a rule you have internalised.

### 1.5 REFUTED — the nine wrappers are NOT dead, and the real defect is different

> The item states: *"Its description ends by naming nine skills that no longer exist …
> `codex-audit .. codex-triage -> Test-Path False (9 of 9)`"*.

**Measured across four roots, all nine are ALIVE** — present in `.agents/skills`, the repo's
canonical skill root. `Test-Path False` was true of the *live curated tree* and was generalised
to "no longer exist". The clause is not dangling; it points at skills that exist in SSOT but are
not deployed.

**The genuine defect in that same sentence is one the item did not notice.** The clause names
**ten** skills, and `codex-consult` is among them — while `codex-consult` is present in **all
four** roots and is live. The item used `codex-consult -> True` as its *control* without
observing that the control subject sits inside the list being called dead. So the description
claims to replace a skill that is alive and curated.

**Recommended instead of the proposed trim:** remove `codex-consult` from the replaced-list only,
and leave the other nine — they name real, SSOT-present skills. Not applied here: the remaining
nine raise a prior question (§6.1) that should be answered first.

### 6.1 NEW — 15 skills are asymmetric between the two repo trees, and the gate cannot see it

Found while refuting 1.5. `.agents/skills` holds **346** skills, `skills/` holds **337**:

| direction | n | skills |
|---|---:|---|
| `.agents/skills` only | **12** | `claim-verify-gate`, the 9 `codex-*` wrappers, `microsoft-foundry`, `qdx-rush` |
| `skills/` only | **3** | `harness-module-authoring`, `patent-fto-search`, `social-corpus-extraction` |

`ci/check_skill_dual_write.py` enforces **final-tree strict parity on CHANGED paths only**, so a
skill never touched in the compared range is invisible to it. That is correct for its stated job
— catching drift a change introduces — and it means the gate is not, and never was, an inventory
check. Reading a green from it as "the two trees agree" is a scope error.

This matters beyond tidiness: **`claim-verify-gate` is executed by `quality.yml`** from
`.agents/skills` and has no projection counterpart. And `microsoft-foundry` / `qdx-rush` are the
two skills recorded elsewhere on this estate as being deleted by `sync-skills.ps1 -Prune`, so the
asymmetry is a live hazard rather than a cosmetic one.

**Not repaired here.** Which direction wins is a real per-skill decision — the 3 projection-only
skills may be deliberate, and copying 12 skills into the projection changes what a consumer of
that tree sees. Owner call. **Cheap durable fix regardless of that decision:** extend the gate
with an inventory arm that fails when the two roots disagree on the SET of skills, independent
of whether anything changed in the range.
