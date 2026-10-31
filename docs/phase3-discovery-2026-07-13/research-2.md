---
title: research-2
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/research-2
---

# SOTA → harness-ready enforcement hooks for doc/cleanup/branch/commit hygiene

Scope: research the state of the art for the four enforcement classes the owner wants, then map each to a **concrete gate that rides the existing `~/.agents/harness` dispatcher** — the same `Module.run(event) -> HookResult` + `stage(gate, tier, event, raw)` shadow-ladder + `GATE_CONTRACTS` anti-zombie registry + fail-open pattern already used by `config_drift`, `injection_quarantine`, `metered_mcp`, etc. Nothing below is a new framework; each is ~1 module method plus a `GATE_CONTRACTS` entry, shipping **SHADOW-first** (observe+log, never blocks, never nags) exactly like every gate landed in `modules.py`.

**Cross-cutting design verdict (confidence: almost certain, 90-95%).** SOTA docs-as-code enforcement uses a **two-layer split**: a *hard* gate at the commit/CI boundary (`drift check` exits 1, pre-commit fails the commit) plus *advisory* surfacing during authoring. The harness's AGENTS.md §6 already mandates this: **block only dangerous; inject for everything else.** So every gate below is `action="inject"` (exit 0 + additionalContext) at the interactive layer, and the *hard* block is deferred to a pre-commit hook / the `Stop` boundary that a promotion to `ENFORCE` can later turn on. This matches the field: the only tools that hard-block are CI gates a human reconciles in a PR ([Fiberplane drift](https://fiberplane.com/blog/drift-documentation-linter/), [zivodoc](https://zivodoc.com/blog/api-documentation-drift-prevention/)), never mid-keystroke.

---

## (a) Doc-reconciliation / knowledge-base hygiene

### SOTA findings
- **Code↔doc binding + AST-fingerprint staleness is the frontier technique.** Fiberplane's `drift` binds a markdown spec to `code_path#Symbol@<git-sha>` via YAML frontmatter; on check it does `git show <baseline>:<file>`, parses both with tree-sitter, and compares a **normalized AST hash (node kinds + token text, no whitespace/positions)** so reformatting doesn't false-positive. `drift check` exits 1 in CI; the author must re-run `drift link` to re-stamp the sha — an explicit "I acknowledged the code moved" gesture ([Fiberplane blog](https://fiberplane.com/blog/drift-documentation-linter/), [github.com/fiberplane/drift](https://github.com/fiberplane/drift)). Confidence: high (95%) — I read the mechanism directly.
- **"Docs change goes through nothing" is the named root cause.** Code gets review+CI+merge gates; docs get none. The fix everyone converges on: *make doc accuracy a merge requirement, auto-open a fix PR when drift is detected* ([Just Understanding Data](https://understandingdata.com/posts/doc-drift-detection-ci/), [zivodoc](https://zivodoc.com/blog/api-documentation-drift-prevention/)).
- **ADR "superseded" discipline = the update-don't-rewrite pattern.** ADRs are immutable append-only; a new decision gets status `superseded` stamped on the old one **with a link to the superseder** — `adr-tools` automates exactly this state transition ([npryce/adr-tools](https://github.com/npryce/adr-tools), [Fowler](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html), [MADR](https://adr.github.io/madr/)). This is the industry-standard shape of the owner's own AGENTS.md §8 rule (`superseded_by:` on old, `valid_as_of:` on new). Confidence: high (90%).
- **Freshness metadata + scoring.** SOTA KB governance mandates `last_verified` / `updated_at` / `owner` on every doc as *prerequisites, not optimizations*; freshness measured on 4 axes (content age, embedding lag, stale-retrieval rate, coverage drift); production thresholds alert <85%, warn users <70%; critical docs re-reviewed ≤3 months ([Atlan freshness scoring](https://atlan.com/know/llm-knowledge-base-freshness-scoring/), [Atlan staleness](https://atlan.com/know/llm-knowledge-base-staleness/), [knowledge-base.software governance](https://knowledge-base.software/guides/knowledge-base-governance-framework/), [dosu.dev score-in-CI](https://dosu.dev/blog/score-documentation-freshness-in-ci)). Confidence: high (90%).
- **Duplicate/scattered detection is content-similarity, not filename.** Near-dup detection uses semantic/token similarity (revised/reformatted copies), and "scattered docs" is a costed antipattern; Vale + markdownlint + a link-checker are the standard authoring linters ([matrixflows](https://www.matrixflows.com/blog/knowledge-debt-scattered-documentation-cost), [Vale via GitLab](https://docs.gitlab.com/development/documentation/testing/vale/), [Fern link checker](https://buildwithfern.com/post/docs-linting-guide)). Confidence: medium-high (80%).

### Harness gate design

**Gate `doc_drift` (PostToolUse on write tools; TIER_HEURISTIC; SHADOW).** Direct analog of the existing `_config_drift` method in `SecretGuardModule` — swap the settings-hash comparison for the Fiberplane binding model. Maintain a repo-local `.harness/doc-anchors.json` (`{doc_path: [{"code": "src/x.py#Sym", "sha": "<git-sha>"}]}`). On a `mutation` event whose `path` matches a bound `code`, compute a normalized-AST hash (reuse the existing `_stripped_signature` volatility-stripping as a cheap language-agnostic stand-in for tree-sitter; upgrade to tree-sitter later) of the symbol at `sha` vs now; if it changed **and** the bound doc had no `mutation` event this session (query the ledger, which already records `kind="mutation"` with `path`) → `stage("doc_drift", TIER_HEURISTIC, event, inject("DOC DRIFT: <doc> is bound to <code> which changed this turn and was not updated. Update the doc or re-stamp the anchor."))`. Fail-open when the anchor file / git is absent.

**Gate `kb_supersede` (PostToolUse on `write_note` / MEMORY.md / `.beads` doc edits; TIER_HEURISTIC; SHADOW).** Enforces AGENTS.md §8 temporal-validity mechanically. On a new basic-memory note or MEMORY.md bullet, use the **existing `recall_index.py`** to find the top-k most-similar existing notes; if similarity > τ and the new note lacks a `superseded_by:`/`valid_as_of:` link → inject "Near-duplicate of <permalink> (sim=X). Per AGENTS.md §8, add `superseded_by:` to the old note and `valid_as_of:` to this one, or fold into the existing note (update-don't-rewrite)." This is the ADR-supersede + near-dup-similarity SOTA collapsed into one advisory.

**Rule `single-source-docs` (a rules/ markdown rule, backed by a `scattered_doc` inject).** Declare canonical doc roots (`docs/`, `.beads/`, the basic-memory vault, `rules/`). A `scattered_doc` check (PostToolUse on `Write` of `*.md`) that fires when a new markdown file lands **outside** those roots and outside the scratchpad → inject "single-source: put this under <canonical root> or the vault, not a random dir." Pairs with the cleanup gate in (b).

---

## (b) Cleanup-enforcement (no stale artifacts in random dirs)

### SOTA findings
- **`git status --porcelain` / untracked-file detection is the primitive.** pre-commit itself has long-standing tension around hooks that *generate* untracked files; the accepted pattern is to **detect newly-created untracked files and fail** (`pre-commit` issue [#2789](https://github.com/pre-commit/pre-commit/issues/2789)), while genuinely transient files go to gitignore/stash ([#708](https://github.com/pre-commit/pre-commit/issues/708), [#1981](https://github.com/pre-commit/pre-commit/issues/1981)). Confidence: high (90%).
- **Agentic SessionEnd cleanup is the emerging idiom.** Claude Code `SessionEnd` hooks are explicitly used to "remove temp files and stale logs"; the general principle — "the value shifts from writing code to *enforcing the constraints code must satisfy*, mechanically" — is exactly the leftover-artifact case ([Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide), [claudefa.st 12 lifecycle events](https://claudefa.st/blog/tools/hooks/hooks-guide), [Leading EDJE shifting-left](https://blog.leadingedje.com/post/claudeagenthooks.html)). Confidence: high (90%).

### Harness gate design

**Gate `artifact_hygiene` (Stop hook; TIER_HEURISTIC; SHADOW→ADVISE).** At `Stop`, the harness already has every `mutation` event with its `path` for this session in the ledger. Compute the set of paths this session created that are (a) still untracked per `git status --porcelain`, (b) not matched by `.gitignore`, and (c) not under the scratchpad root — those are the "left in a random dir" artifacts. If non-empty → inject "N stray artifacts created this session and neither committed, ignored, nor in scratchpad: <list>. Move to the scratchpad dir, gitignore, or commit." Never deletes (that would be a §6/§9 irreversible op — advise only). This *reuses the mutation ledger you already write*, so it's near-free and precise (no full-tree scan). Fail-open if git is absent.

**Optional `SessionEnd` companion** for genuinely transient scratch: a config'd sweep of the *scratchpad* dir only (never the repo), matching the SOTA SessionEnd cleanup idiom — but keep it advisory/opt-in given the §9 New-Item/`rm -rf` footguns in `rules/common/windows-shell.md`.

---

## (c) Stale-branch reconciliation

### SOTA findings
- **Merged-branch detection = `git merge-base --is-ancestor` (handles squash/rebase merges), not `git branch --merged`.** This is the correctness point every good tool makes ([onamfc/branch-clean](https://github.com/onamfc/branch-clean)). Confidence: high (90%).
- **Stale = no commit in N months (GitHub's own default = 3 months); age via last-commit date.** ([cleanup-stale-branch action](https://github.com/sichoi42/cleanup-stale-branch), [HackerNoon GH Actions](https://hackernoon.com/clean-stale-branches-with-github-actions), [GitScrum branch automation](https://docs.gitscrum.com/en/best-practices/automating-branch-management)). Confidence: high (90%).
- **Prefer auto-delete-on-merge + scheduled review over ad-hoc.** GitHub's "Automatically delete head branches" + a scheduled Action is the recommended reconciliation loop; protect protected branches ([GitScrum](https://docs.gitscrum.com/en/best-practices/automating-branch-management), [Railsware](https://railsware.com/blog/git-clean-up-in-local-and-remote-branches/)). Confidence: high (85%).

### Harness gate design

**Gate `stale_branch` (SessionStart on `startup`/recovery, dedup'd; TIER_ADVISORY; ADVISE — advisory tier default per `DEFAULT_MODE_BY_TIER`).** Advisory-tier because it's read-only reconciliation, not a per-turn risk. On session start in a git repo: (1) list local branches; (2) those where `git merge-base --is-ancestor <branch> main` succeeds → *merged, prunable*; (3) those with last-commit age > `HARNESS_STALE_BRANCH_DAYS` (default 90, GitHub's number) → *stale*. If either set is non-empty, inject a **one-time** reconcile reminder (dedup via a per-repo seen-file like `budget_pacing` does): "M merged + K stale local branches — reconcile: `git branch -d <merged>`; review stale: <list>." Never deletes (a `git branch -D` is §9-gated). This is the same "surface, human decides" posture; the *actual* deletion stays a human/`Automatically delete head branches` job. Fail-open outside git.

---

## (d) Change-must-be-documented-and-committed gate

### SOTA findings
- **Stop-hook "gate commit until green" is the canonical agentic pattern.** Stop hooks fire when the agent says "done"; the documented use is to *not let "all done" stand while the build is broken or work is uncommitted* ([ksred hooks guide](https://www.ksred.com/claude-code-hooks-a-complete-guide-to-automating-your-ai-coding-workflow/), [Blake Crosley deterministic layer](https://blakecrosley.com/blog/claude-code-hooks-explained), [hidekazu-konishi complete guide](https://hidekazu-konishi.com/entry/claude_code_hooks_complete_guide.html)). Confidence: high (90%).
- **"Docs updated as part of every code review" is the #1 recommended anti-rot control** — treat the doc update as a required part of the change, not a follow-up ([TheCodeForge doc-rot](https://thecodeforge.io/cs-fundamentals/documentation-best-practices/), [Stew DevOps doc-rot](https://www.stew.so/blog/documentation-rot-devops), [Glitter](https://www.glitter.io/blog/process-documentation/why-documentation-gets-outdated)). Confidence: high (85%).

### Harness gate design

**Gate `uncommitted_change` (Stop hook; TIER_HEURISTIC; SHADOW→ADVISE).** At `Stop`: if the session recorded ≥1 `mutation` event to tracked code files **and** `git status --porcelain` is non-empty **and** no `git commit` tool_result appears in this turn's ledger → inject "You made N edits this session; the working tree has uncommitted changes and no commit ran. Commit them (or state why deferring)." Deliberately `inject`, never `block` (AGENTS.md §6 — committing/not is the owner's call; the harness surfaces, doesn't force). Promotable to ADVISE after burn-in; a true hard gate belongs in pre-commit, not the interactive Stop.

**Gate `doc_required` (Stop hook, co-located; TIER_ADVISORY; SHADOW).** When the last assistant message asserts completion of a feature/fix (a WEP-style "done/shipped/implemented" + a code `mutation` this session) but **no** doc/changelog/ADR/basic-memory `mutation` occurred → inject "Change looks complete but no docs/changelog/ADR/memory-note was updated (SOTA anti-rot: docs are part of the change, not a follow-up). Update the relevant doc or record the decision." Fold this signal into the existing `claim_warning` module rather than a new module — it's the same "completion-claim needs a receipt" shape already there.

---

## Wiring checklist (all four, uniform)

1. **Add one method per gate** to the closest existing module (`doc_drift`/`scattered_doc`→`SecretGuardModule` alongside `_config_drift`; `kb_supersede`/`stale_branch`→`LedgerModule`; `uncommitted_change`/`doc_required`→`LedgerModule`/`ClaimWarning`), each wrapped in `try/except → HookResult.success()` (fail-open per §6).
2. **Route every verdict through `stage(name, tier, event, raw)`** so they ship at the tier default (HEURISTIC→SHADOW, ADVISORY→ADVISE) and can only reach ENFORCE via `module-modes.json`/`HARNESS_GATE_MODE__<gate>` after burn-in.
3. **Register a `GATE_CONTRACTS[<gate>]`** entry (metric/owner/deadline/fire_rate) so the anti-zombie fitness scorer can sunset a gate that never fires or never helps — mandatory for every new gate in this file.
4. **Reuse existing state**: the `mutation` ledger (paths written this session), `recall_index.py` (similarity), `_stripped_signature`/`_digest` (cheap fingerprints), `read_json`/`atomic_write_json` + per-repo seen-files (one-time dedup, like `budget_pacing`), and `redact_text` on anything surfaced. No new stores.
5. **Keep the hard gate out-of-band**: mirror `doc_drift` + `uncommitted_change` as a repo `pre-commit` hook (exit 1) for the *commit boundary*, where SOTA hard-blocks live and a human reconciles — the interactive hooks stay inject-only.

**Net confidence that this design is both SOTA-aligned and drop-in for the harness: almost certain (90%)** — the four gates are near-isomorphic to gates already shipping in `modules.py`, and each SOTA mechanism (AST-fingerprint binding, `merge-base --is-ancestor`, `status --porcelain` untracked-set, ADR-supersede metadata, Stop-hook commit gate) maps cleanly onto the dispatcher's `event → HookResult` surface with no framework additions. Main residual risk (medium, 60%): the `doc_drift` AST hash is only as good as tree-sitter coverage — the `_stripped_signature` stand-in will over-fire on some languages until upgraded, which is precisely why it must ship SHADOW and prove precision before ADVISE.