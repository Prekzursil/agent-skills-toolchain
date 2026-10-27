# SKILLS FLEET — GROUNDING LANE ARTIFACT

STATUS: COMPLETE for the grounding mandate.

COVERAGE: MEASURED — §0 budget overrun, §1 harvest, §2 inventory, §3 drift (differ executed, both
axes), §4 overlap (fleet-wide matrix, all 53,628 pairs), §5 prior art, §6a-§6c mechanism.
NOT MEASURED, stated as such inline: which of the 192 diverged file pairs are semantically
substantive vs prose reflow (that is the per-file merge decision, deliberately not made here);
the bodies of the 23 `source-command-*` beyond the one pair the USABILITY lens read; whether the
`ui-audit` broken/fixed variants actually differ at runtime.

---

## 0. KEYSTONE CORRECTION — the brief's central mechanic is REFUTED

The brief states: 328-skill listing costs ~113,654 chars (~28,413 tokens) against the 40,000 that
`skillListingBudgetFraction 0.04` buys on a 1M window — "about 29 percent headroom … do NOT trim
descriptions to save tokens".

**Measured: there is no headroom. The budget is already exhausted and 26 skills are paying for it.**

- 26 of 328 curated skills render as BARE NAMES with no description in THIS session's listing.
  Independently observed in my own system prompt; identical 26/26 to the USABILITY lens's list.
- Their descriptions exist on disk (detector control: 26/26 parsed, none zero-length).
- Full listing measured with a real BPE tokenizer (`o200k_base`): 122,331 chars → **25,034 tokens**
  (4.89 chars/token — the chars/4 proxy the brief used OVER-states tokens, but that is not the
  error that matters). The observed render cut sits at **~22,224 tokens**.
- Overrun ≈ **2,810 tokens** of description that cannot be indexed today.

Consequence: description budget is **zero-sum right now**. Every char added to an early-alphabet
skill silently un-indexes a late-alphabet one. "Enrich descriptions freely" is unsafe until the
fleet is back under budget.

CONFIDENCE almost certain (90-99%) that 26 render bare and that on-disk descriptions exist (two
independent observations). Likely (55-80%) that the shared pool is skills + commands + plugin
skills + built-ins, which is why the cut lands at 22.2k rather than 40k — UNVERIFIED inline: I did
not token-count the command/plugin/built-in sections. Settling experiment: capture the rendered
system prompt (`claude --debug`), token-count each section, and check the four sum to ~40,000.

## 1. HARVEST — five completed lenses (the sixth, OVERLAP, did NOT complete)

File: `command-center/harvest/harvest-wf_18aa91e4-3c1-wf_9cb1a66a-36f.json`, 331,424 B.
Two run-ids. `wf_18aa91e4-3c1` = 5 results, 123,535 chars = the skill audit.
`wf_9cb1a66a-36f` = 21 results = a DIFFERENT wave (ADV-0001..0030 adversarial units).

Split to `command-center/grounding/harvest-split/`. Labels were empty; identified from content:

| idx | agentId | lens |
|---|---|---|
| 00 | a7a3e656b06a714ba | USABILITY |
| 01 | abf96f7d6c87a6701 | QUALITY |
| 02 | a5fa88d4c5d1c2cb8 | SOTA / external research |
| 03 | a22eb383b8e935ce2 | DRIFT |
| 04 | acf06d45c973f20a5 | GAPS |

**The missing sixth lens is OVERLAP** — precisely the lens that would have cleared the merge/retire
candidates. Every merge/retire in this program is therefore UNCLEARED by design.

## 2. FLEET INVENTORY (measured)

- `~/.claude/skills.daily` = 328 skills (dirs with SKILL.md). `~/.agents/skills` = 328.
  Symmetric difference EMPTY both ways (differ: `left_only_skills: []`, `right_only_skills: []`).
- repo `.agents/skills` = 346 skills; 18 exist ONLY in the repo (below).
- `crcp-health` is NOT a skill: no SKILL.md. Three lenses probed it; SOTA's "vault holds 329 real
  skills" is REFUTED by the specific probe (`Test-Path crcp-health/SKILL.md` = False), which wins
  over a directory-name set difference.
- Total description text: 115,426 chars over 328 (my parse, folded blocks handled).

## 3. DRIFT — deterministic differ EXECUTED, output shown

Instrument: `ci/check_skill_deploy_drift.py` (12,525 B) — **already in the repo**, LF-normalises
before comparing, never consults mtime, refuses to copy, emits `safe_to_deploy` only where one side
is a strict superset. This IS the deterministic differ the DoD asks for. It was never being run.

### 3a. Axis A — live daily vs live vault (this is the briefed "110")
`python ci/check_skill_deploy_drift.py --left ~/.claude/skills.daily --right ~/.agents/skills --json`
exit 1. Output: `command-center/grounding/G-DRIFT-daily-vs-vault.json`.

| | |
|---|---|
| skills both sides | 328 / 328 |
| skill verdicts | IDENTICAL 291 · DIVERGED 33 · LEFT-AHEAD 4 · RIGHT-AHEAD 0 · REORDER-ONLY 0 |
| file verdicts | DIVERGED 61 · LEFT-ONLY-FILE 46 · LEFT-AHEAD 3 |
| **needs_merge** | **110** |
| **safe_to_deploy** | **0** |

`RIGHT-AHEAD = 0` is the load-bearing zero: the vault is a strict superset of the live tree in
ZERO files, so no vault→live copy is provably safe anywhere.

### 3b. Axis B — live daily vs REPO `.agents/skills` (this lane's actual file scope)
`--left ~/.claude/skills.daily --right <repo>/.agents/skills` exit 1.
Output: `command-center/grounding/G-DRIFT-daily-vs-repoagents.json`.

| | |
|---|---|
| skills | live 328 · repo 346 · shared 328 · repo-only 18 |
| skill verdicts | IDENTICAL 225 · **DIVERGED 101** · LEFT-AHEAD 2 · RIGHT-AHEAD 0 |
| file verdicts | LEFT-ONLY-FILE 295 · DIVERGED 192 · RIGHT-ONLY-FILE 93 · LEFT-AHEAD 3 · RIGHT-AHEAD 2 |
| **needs_merge** | **490** |
| safe_to_deploy | 95 |

**The briefed "110 drifted files" is the WRONG axis for this lane.** Against the repo tree the
surface is **490 files / 101 skills**, 4.5x larger. 295 files exist live and not in the repo at all
(noise already excluded by the differ: `.ruff_cache`, `__pycache__`, `node_modules`, `.venv`,
`Zone.Identifier`, `.bak-*`).

### 3c. Repo-only skills (18) — a repo→live deploy RESURRECTS these
`browser-rail, claim-verify-gate, codex-audit, codex-brainstorm, codex-coordinate, codex-curate,
codex-discuss, codex-fix, codex-governance, codex-invoke, codex-mixed-workflow-doctrine,
codex-review, codex-triage, cookie-bridge, cyberstrike, delegated-build-verify, multilingual-search,
stdin-server`

The 9 `codex-*` per-mode wrappers `codex-orchestrate` claims to replace are **already retired from
both live trees**. Three lenses agree independently. The overlap question is CLOSED — the risk is
purely one-directional resurrection, not a live duplication.

### 3d. Named live-ahead / live-only content a redeploy would destroy
- 3 LEFT-AHEAD skills (live strict superset): `gem-hunt`, `re-ensure`, `schrodinger-maestro-driver`.
- `ui-audit/_fix_main_guard.py` is LEFT-ONLY. Per the DRIFT lens this is a live-only fix for a
  junction/symlink main-module check; without it `run_audit.mjs` exits 0 producing NO artifacts —
  a green no-op. All 6 `.mjs` entry points are DIVERGED. UNVERIFIED inline: I did not execute the
  broken and fixed variants. Settling experiment: run each variant and diff the artifact dir.
- `deep-research`: 7 live-only modules+tests (`academic.py`, `calibration.py`, `claims.py` and
  their tests, `test_skill_consistency.py`) plus 11 DIVERGED files.
- `design-system/references/.design-templates/*` — 10 live-only files; a dot-directory the sync
  appears to drop.
- `cv-studio/cv-studio/**` — 12 files, a NESTED DUPLICATE of the skill inside itself. Drop, do not
  merge. This is 11% of the 110 and is pure duplication.

## 4. OVERLAP CANDIDATES — status
- O1 `source-command-*`: **23, not the briefed 22** (USABILITY lens, mechanical). All 23 have a
  live same-named `/command` on disk. Only ONE pair (`promote`) was read body-to-body.
- O2 codex-orchestrate's nine: CLOSED — already gone from both live trees (§3c).
- O3 humanizer / agentic-humanizer / slop-check: UNKNOWN - not yet measured
- O4 four `*-deploy`: the USABILITY lens calls these the fleet's **counter-example done right** —
  each names the other three. NOT a merge candidate; a template to copy.
- O5 hexstrike trio: UNKNOWN - not yet measured
- O6 security-lookup cluster: UNKNOWN - not yet measured
- O7 two-tier-verify / verification-before-completion / mutation-check: UNKNOWN - not yet measured
- Fleet-wide: **0 exact-duplicate descriptions** among the 328 (detector controlled against a
  known duplicate). No consolidation case in this fleet can be built from description similarity.

## 5. PRIOR ART IN-REPO (the build lane must NOT rebuild these)

| path | what it already does |
|---|---|
| `ci/check_skill_deploy_drift.py` | the deterministic two-directional differ. LF-normalised, mtime-blind, refuses to copy. Executed above. |
| `ci/check_skill_context_budget.py` | description/trigger budget checker with a `CONTROL_SKILL` fixture and `DEFAULT_MAX_TRIGGER_CHARS` |
| `ci/check_skill_dual_write.py` | repo `skills/` ↔ repo `.agents/skills` parity, wired in `skill-dual-write.yml` |
| `ci/gen_skill_index.py`, `ci/gen_skills_manifest.py`, `ci/skill_surface_census.py` | index/manifest/census generators |
| `scripts/sync-skills.ps1` | repo `skills/` → `~/.agents/skills` (full replace per skill) |
| `scripts/sync-from-live.ps1` | `~/.agents/skills` → repo `.agents/skills` |
| `scripts/validate-all-skills.ps1`, `scripts/test-live-skill-helpers.py` | validators |
| `docs/audit-design-2026-07-13/A4-skills-dup-matrix.{md,json}` | **a skills duplicate matrix already exists** |
| `docs/audit-design-2026-07-13/C-skills-reconcile.{md,json}` | a prior skills reconcile pass |
| `tools/harness-drift/harness_drift.py` | harness-wide drift |
| `tools/detector-self-test/` | both-states detector control; 36 tests green, wired NOWHERE |
| `tools/measure-guard/{suitefloor,blobread,refcheck,jsonparse,wudeps}.py` | CI-wired, zero agent-facing surface |

**Architectural hole confirmed by grep:** no script in `scripts/` or `ci/` WRITES to
`skills.daily`. The only tree Claude Code reads is hand-deployed. That is the root cause of all
drift and it regenerates after every fix until a sync path exists.

## 6a. THE 26 BARE DESCRIPTIONS — five hypotheses refuted, mechanism narrowed

| hypothesis | verdict | control |
|---|---|---|
| YAML folded/multiline description | REFUTED | 0/26 folded; all 12 genuinely folded skills render fully |
| duplicate description de-dup | REFUTED | 0 exact duplicates fleet-wide; matcher proven on a known dup |
| positional contiguity / simple suffix cut | REFUTED | 8 later skills keep descriptions |
| frontmatter key-set (extra `metadata`/`license`/`origin`) | REFUTED (mine) | 13 of the 26 bare have ONLY name+description |
| second root / plugin membership | REFUTED (mine) | `writing-plans` has 11 copies and is BARE; 4 survivors have 2 copies |
| **greedy budget fill in alphabetical order** | **BEST FIT** (mine) | reproduces 323/328; beats hard-cut control 5 vs 6 mismatches |

Greedy model: walk alphabetically; if `used + cost <= B` render the description and charge it,
else render name-only and KEEP GOING. Only greedy can produce the observed INTERLEAVING
(`ui-drive` 946 chars bare, the very next skill `ui-ux-pro-max` 353 chars described).
Best fit `B ≈ 108,408` desc+name chars. Residual 5, all "predicted BARE, observed DESC":
`using-git-worktrees, verification-before-completion, video-watermark-removal, workflow-authoring,
writing-skills` — consistent with a small pinning/priority layer on top. UNVERIFIED inline: the
pinning rule is unidentified. Settling experiment: capture the rendered prompt across two sessions
with different recent-skill history and see whether the 5 change.

**Decision consequence: do NOT rewrite those 26 descriptions.** Five content-shaped hypotheses are
refuted; the text on disk is not the defect. Six of the 26 are among the best-written in the fleet
(`ui-drive`, `ui-invariant-walk`, `vercel-deploy`, `video-convert`, `webapp-testing`,
`workflow-foundry` all carry both a trigger and a negative case). Rewriting them changes nothing
while the budget stays full.

## 6b. EXTERNAL SOTA
Covered in depth by the SOTA lens (9 URLs fetched). Key: Anthropic's spec allows only SIX
frontmatter fields for packaging/upload; **66 of 328 skills carry non-spec keys** (`origin` 59,
`tools` 5, `version` 2) and hard-fail `package_skill.py`; 7 descriptions exceed the 1,024-char spec
max; `tools:` is not a Claude Code field at all (the real ones are `allowed-tools` /
`disallowed-tools`) so 5 skills carry an inert declaration. Fix is lossless: move `origin`/`version`
under the spec-legal `metadata:` map.

## 6c. MECHANISM RESOLVED — externally confirmed, and my own model partly REVISED

Fetched `https://claudefa.st/blog/guide/mechanics/skill-listing-budget` plus a web search over
`anthropics/claude-code` issues #56710 · #56966 · #57599 · #57941 · #60560 · #64606 (search
snippets only for the issues — NOT fetched; github.com fetch was blocked by domain policy).

Documented mechanism:
1. `skillListingMaxDescChars` (default **1536**) shortens any over-long description FIRST.
2. Total listing is checked against `skillListingBudgetFraction` × context window.
3. If exceeded, descriptions are dropped by **recency and frequency of invocation** —
   "Most-invoked survives. Least-invoked gets cut." Startup emits
   **"Skill listing will be truncated / N descriptions dropped…"**.
4. Reported bug (#57941): the fraction is computed against a fixed ~200K baseline, not the
   model's real window — so on a 1M model the effective budget is ~5x smaller than expected.

I am REVISING my greedy-alphabetical model because of this new evidence. It got the CAUSE right
(budget exhaustion → drop, not per-file breakage) and the ORDERING wrong. The reconciled model
that fits all my measurements: most skills have ZERO invocations and tie, ties break
alphabetically, so **the drop set is the alphabetically-last NEVER-INVOKED skills** — which is
exactly the observed u–z cluster — while the 8 tail survivors are the ones with real invocation
history (`using-git-worktrees`, `verification-before-completion`, `writing-skills`,
`workflow-authoring`, `video-watermark-removal` are estate staples). Confidence: likely (55-80%);
this reconciles a fetched third-party description with my partition, it is not a code read.
SETTLING EXPERIMENT (both-states): invoke `volatility-3` or `yeet` once, restart, and check
whether its description now renders while a different never-invoked skill drops out.

Estate settings measured (single-field greps, no wholesale read of settings.json):
- `skillListingBudgetFraction: 0.04` in BOTH `~/.claude/settings.json` and the repo SSOT
  `agent-self/config/settings.json` — consistent, already 4x the 0.01 default.
- `skillListingMaxDescChars` is **NOT SET** anywhere → default 1536 → exactly ONE skill is
  shortened, `workflow-foundry` (1,750 chars, loses 214).
- 210 of 328 descriptions exceed 200 chars; 95 exceed 400; 27,996 chars sit above a 400-char cap.

**The COLD-START DEATH SPIRAL (this is the real damage):** a never-invoked skill is the FIRST to
lose its description → it can no longer be auto-picked → it is never invoked → it stays dark,
permanently. The tail is not merely unlucky, it is self-reinforcing, and it gets worse with every
skill added. This is the strongest argument in the whole lane for de-curation over enrichment.

## 7. RANKED PLAN

**R1. Restore the description index — frees MORE budget than the overrun and writes NO new text.**
- R1a. De-curate the 23 `source-command-*` from `~/.claude/skills.daily`; KEEP the vault copy and
  KEEP every `/command`. Frees 2,870 chars ≈ 587 tokens. Reversible, zero capability loss.
- R1b. Deploy the description cap ALREADY COMMITTED in the repo (75 skills, −17,244 chars ≈
  3,526 tokens; commits #167 / #176). The description LINE deploys independently of the diverged
  bodies. Move the removed prose into the BODY, do not delete it — bodies are ~free.
- R1a+R1b ≈ **4,113 tokens freed vs a ~2,810-token overrun** → back under budget with headroom.
- R1c. READ THE STARTUP WARNING before and after. It states the dropped count directly. This is a
  both-states proof and the estate has never read its own instrument.
- R1d. Set `skillListingMaxDescChars` explicitly rather than inheriting 1536.

**R2. MERGE / RETIRE NOTHING. Verdict now measured, not merely cautious.**
Fleet-wide body-similarity sweep over all 53,628 pairs: only **7 exceed J≥0.40**, max **0.560**
(control: self-pair 1.000, unrelated 0.04-0.08). Every briefed cluster is far below threshold —
humanizer 0.267 · hexstrike 0.291 · seclookup 0.323 · deploy 0.279 · verify **0.217 with
containment ≈ 0.000** · playwright 0.165 · design 0.226. There is no near-duplicate cluster in
this fleet, the OVERLAP lens never ran, and adversarial clearance never ran. Default KEEP.

**R3. Reconcile live→repo BEFORE any redeploy, on the 490-file axis (not the briefed 110).**
Priority: `ui-audit` (`_fix_main_guard.py` + 6 diverged `.mjs`; a redeploy reverts a green-no-op
fix) → `deep-research` (7 live-only modules+tests, 11 diverged) →
`design-system/references/.design-templates/*` (10 live-only) → `transpose-to-figma` (3 live-only)
→ the 3 LEFT-AHEAD skills `gem-hunt`, `re-ensure`, `schrodinger-maestro-driver` (strict superset,
mechanically safe live→repo). DROP `cv-studio/cv-studio/**` (12 files, nested self-duplicate) —
drop, do not merge.

**R4. Close the architectural hole.** No script in `scripts/` or `ci/` writes to `skills.daily`;
the only tree Claude Code reads is hand-deployed. Add the sync path and wire
`ci/check_skill_deploy_drift.py` as a LOCAL pre-deploy gate — it cannot run in GitHub CI because
the live trees do not exist on a runner.

**R5. Spec compliance (lossless).** 66 skills carry non-spec frontmatter keys (`origin` 59,
`tools` 5, `version` 2) that HARD-FAIL `package_skill.py` / claude.ai upload. Move them under the
spec-legal `metadata:` map. Convert `tools:` per skill deliberately — renaming it to
`allowed-tools` silently PRE-APPROVES Write/Edit/Bash on audit skills, the opposite of intent.

**R6. Encode the measured lessons into BODIES (nearly free).**
`workflow-authoring/templates/governed-run-orchestrator.md:1142-1146` git-archive → `git cat-file
-p` (leave :2173, a legitimate packaging use) · `two-tier-verify` clean-checkout + blob-verify
lines · `rubric-verifier` coverage-is-not-sufficient · `devtu/modes/fix-tool/QUICK-REFERENCE.md:285`
`grep -c` doubled-zero.

**R7. Route the dark instruments by NAMING them in existing bodies, not new skills.**
`tools/detector-self-test/` (36 tests green, wired in 0 CI / 0 hooks / 0 skills) and
`tools/measure-guard/*` (CI-wired, zero agent-facing surface). A new skill costs description
budget — the scarce resource — so name them inside `two-tier-verify` / `smallest-check-ladder` /
`mutation-check` instead.

## 8. RISKS

- **The 26-bare set is USAGE-DEPENDENT and NOT stable across sessions.** Any before/after
  measurement must control for invocation history or it measures noise.
- Cold-start death spiral (§6c) — adding skills makes the rarely-used tail darker.
- Deploying the description cap trades trigger vocabulary for index budget. Mitigate by moving the
  text into the body, never deleting it.
- A repo→live deploy RESURRECTS 18 repo-only skills including the 9 retired `codex-*` wrappers.
- `scripts/sync-skills.ps1 -Prune` without `-IncludeClaudeOnly` is a live destruction path for
  `microsoft-foundry` and `qdx-rush`.
- `RIGHT-AHEAD = 0` on both axes: no vault→live or repo→live file copy is provably safe anywhere.
- I revised my own greedy-alphabetical model on new evidence (§6c). Recorded, not deleted.
