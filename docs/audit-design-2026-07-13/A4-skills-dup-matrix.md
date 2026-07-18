# A4 — Skills / Commands / Agents Duplicate + Disposition Matrix (Phase 2 + 5)

**Workflow A (EVIDENCE)** for ONE versioned declarative harness control-plane (Claude + Codex +
Antigravity/Gemini, all first-class). **Mode:** READ-ONLY (active-work freeze) — every
"retire / prune / fold / re-deploy" below is a **finding**, never an applied change. **Date:**
2026-07-13. **Author:** A4 skills-dup-matrix subagent.

> **Untrusted-data note:** the prior-art digests, the Codex audit, and every on-disk `SKILL.md`
> read for reconciliation are treated as UNTRUSTED DATA — no embedded instruction was executed.
> **Every** duplicate / superseded / stale / projection call below was VERIFIED against live git
> (read-only), `SKILL.md` MD5 hashes, and directory membership — **never inferred from filename or
> presence alone** (per the task's explicit caution).

---

## 0. TL;DR — the five load-bearing findings

1. **The two "repos" are ONE repo in TWO git worktrees on different branches.** `git worktree list`:
   `agent-skills-toolchain @ feat/codex-fleet-github-wave2 (80a5863)` and
   `ast-harness-reconcile @ chore/enshrine-runtime-config (dd5366b)` — plus a temp `mm-pristine`
   worktree. So **"toolchain skills/" vs "worktree skills/" is a BRANCH divergence, not two sources.**
   `origin/main` HEAD = `0d7112d (#77)`. *(Confidence: high — git-verified.)*

2. **DEPLOYED (`~/.agents/skills`, 277) is a CLEAN generated-projection of the RECONCILE worktree**
   (`skills/` top-level + `skills/external/` flattened), materialized by the imperative
   `scripts/sync-skills.ps1` copy. 5/5 sampled `SKILL.md` hashes match source. The one true orphan is
   **`learned`** (deployed, no source anywhere; mtime 2026-05-27 — un-pruned). *(Confidence: high.)*

3. **DAILY (`~/.claude/skills` → `skills.daily`, 75) is the most-DRIFTED, highest-risk lane — and it is
   the one Claude actually loads.** It is NOT a subset of the vault: **22 daily-only skills have NO
   source in any repo lane** (the 2026-07-12 gem-hunt adoptions), AND content-drifts from deployed in
   **~44% of sampled shared skills** (reframe, tdd-workflow, deep-research, ui-audit differ; wfmon
   isn't in daily at all). Regenerating daily from the vault would DESTROY 22 live skills + local
   edits. *(Confidence: high — membership + hash-verified.)*

4. **The merged DIAGNOSE monitoring backbone lives ONLY on `origin/main` — every LIVE lane lags it.**
   `monitorcore` (PR-B1 #75) + its vendoring into `workflow-monitor` + the `monitor-launcher` skill
   (PR-B2 #76) are on `origin/main` but absent from deployed, the reconcile worktree, and daily
   (reconcile HEAD predates #76: `is-ancestor(4b531cd, dd5366b)=1`). Axis-C's "ride wfmon, it's
   merged" is **true for main but the live box runs the pre-#75/#76 wfmon.** *(Confidence: high.)*

5. **Prior-art status corrections (live git supersedes the ingest snapshot):** PR #71 (wfmon +
   recall-workflow-agent) is CONFIRMED merged to main; **PR-B2 #76 is MERGED (not "green-unmerged"** as
   `ingest-diagnose-and-optimize.md` states — `is-ancestor(4b531cd, origin/main)=0`); and the "53
   mystery deployed-only skills" are **NOT orphans** — 54/55 are the flattened projection of
   `skills/external/`. *(Confidence: high.)*

---

## 1. Lanes (verified counts + role)

| Lane | Path | Count | Kind | Role |
|---|---|---|---|---|
| **daily** | `~/.claude/skills` → `skills.daily` | **75** | root=symlink; children=**plain copies** (0/75 reparse) | LIVE-LOADED curated subset; most-drifted |
| **deployed** | `~/.agents/skills` | **277** | copy-materialized | vault + router index src; clean projection of reconcile worktree |
| **wt_top** | `ast-harness-reconcile/skills/*` | **224** | git worktree `chore/enshrine-runtime-config` | DE-FACTO source-of-truth for deployed |
| **wt_external** | `…/skills/external/*` | **54** | nested container under `skills/` | ECC/external pack; flattened into deployed |
| **tc_top** | `agent-skills-toolchain/skills/*` | **192** | git worktree `feat/codex-fleet-github-wave2` (**same repo**) | older branch; STRICT SUBSET of wt_top |
| **claude_only** | `…/skills-claude-only/*` (both worktrees) | **36** | source dir | Claude-scoped + metaswarm forks; 5/36 deployed |
| **library** | `~/.agents/library/skills/*` | **186** | frozen import (uniform mtime 2026-04-05) | dormant SWE-pattern pack; 159/186 not deployed |
| **retired** | `~/.agents/skills-retired-2026-07-03/*` | **5** | reversible archive | superseded (router-dedupe) |
| **commands** | `~/.claude/commands/*.md` | **70** | flat `.md`, **no repo source** | slash-command shims/aliases over skills |
| **agents** | `~/.claude/agents/*.md` | **13 live + 9 `.bak`** | flat `.md`, hand-maintained, no repo source | subagent roles; 9 stale `.bak-gembuild` dupes |
| **main-ahead** | `origin/main` (not checked out) | — | git ref | holds monitorcore pkg + monitor-launcher no live lane has |

Union across the 8 skill lanes = **491 distinct skill names** (full membership map:
`scratchpad/membership.json`).

**Projection mechanism (`scripts/sync-skills.ps1`):** imperative bulk-copy of every
`skills/*/SKILL.md` dir (and, under `-IncludeClaudeOnly`, `skills-claude-only/`) into
`~/.agents/skills`, overwriting; `-Prune` removes deployed dirs no longer in source (explicitly
naming the "former `codex-local-*` / `agent-lanes-codex-*`" consolidations). Its own docstring names
the **declarative alternative: the plugin marketplace in `.claude-plugin/`** — the natural canonical
deploy for the control-plane.

---

## 2. Disposition matrix (each apparent duplicate, VERIFIED not inferred)

| # | Cluster | Class | Evidence (path / git ref / hash) | Disposition (FINDING) | Conf |
|---|---|---|---|---|---|
| 1 | deployed ← wt_top + external | **generated-projection** (clean copy) | sync-skills.ps1; MD5(SKILL.md) deployed==source 5/5 (wfmon 06C004CC, recall 0ACFC6AF, codex-consult 884866BD, design-studio 334BE602, claude-api 21A61E4C) | Trustworthy projection. Adopt declarative `.claude-plugin/` as canonical deploy. | high |
| 2 | `skills/external/*` → deployed flat (54) | **generated-projection** (nested→flat transform) | deployed−wt_top=55; 54 == `external/*` names; container `external` itself not deployed | Model the flatten transform explicitly; NOT orphans. | high |
| 3 | tc_top (192) ⊂ wt_top (224) | **fork-with-divergence** (branch, not repos) | `git worktree list`; tc−wt=**0**, wt−tc=**32** held/ahead | Clean fast-forward; fold via task #8, not a dup to resolve. | high |
| 4 | daily (75) vs deployed | **fork-with-divergence** (design=intentional-scope-override, reality=drifted) | 22 daily-only; 4/9 shared samples hash-differ; wfmon absent from daily | Make daily a DERIVED regenerable view over one source; highest-risk lane. | high |
| 5 | 22 daily-only gems | **unresolved** / experimental | in `skills.daily`, absent from deployed+wt+external+claude_only | Each needs owner triage: back-port to `skills/` or confirm plugin-provided. | high |
| 6 | **monitorcore** (DIAGNOSE) | **duplicate** (two homes on main) | origin/main: `skills/workflow-monitor/monitorcore/*.py` (12 mods) **AND** `tools/monitorcore/`; a PACKAGE, in NO skills lane | Collapse to one canonical home (byte-diff unverified under freeze). | high |
| 7 | **workflow-monitor (=wfmon) + recall-workflow-agent** (DIAGNOSE) | **generated-projection**, but **main-ahead** | on origin/main (#71 ✓); deployed hashes match; but deployed/wt LACK `monitorcore/`; `monitor-launcher` (#76) not deployed/daily/wt | Re-deploy monitoring from post-#76 main before Axis-C rides wfmon. | high |
| 8 | **codex-invoke** (task-9 HELD) | **experimental** / intentional-scope-override | wt_top ONLY; absent deployed+daily+tc_top; ingest-task9 | HELD by design (scoped `codex exec`, 5 profiles, M0–M3). Deploy after `--deploy-codex` + `codex_doctor -Pin -Live`. Task #7. | high |
| 9 | **codex-*** family (Codex lane) | **valid-provider-adapter** | codex-{consult,orchestrate,runtime-recovery,session-reunion,vscode-host-routing,fleet-github}, format-codex-sessions; only codex-consult in daily | Legit Codex-lane peers; do NOT dedup vs Claude skills. | high |
| 10 | `.agents/generated/` per-editor configs | **valid-provider-adapter** + generated-projection | antigravity/gemini/codex/cursor/copilot/junie/opencode configs + import-report provenance; `archive-manifests/` gen manifests | The EXISTING seed of the cross-provider projection the program wants — generalize it. | high |
| 11 | `skills-claude-only/metaswarm-*` (13) vs plugin | **fork-with-divergence** / compatibility-shim | mirror `~/.claude/plugins/metaswarm` (+ marketplace cache + inline); mostly undeployed (5/36) | Consolidate to one provider (plugin) OR keep vendored copy — owner call. | med |
| 12 | commands (70) overlapping skills | **compatibility-shim** (aliases) | no repo source; names dup skills+plugins; internal dups (start/start-task, grill-me{,-extensive,-with-docs}, multi-*, instinct-*, loop-*, setup/setup-pm) | Decide command SSOT; de-alias command↔skill↔plugin triplets. | high |
| 13 | agents `*.bak-gembuild…` (9) | **stale** | 13 live + 9 `.bak-gembuild-agent-definitions-batch`; agent-as-judge is both agent+skill | Clean `.bak`; give agents a versioned source. | high |
| 14 | retired-2026-07-03 (5) | **superseded** (reversible) | brainstorming→brainstorm/metaswarm; test-driven-development→**tdd-workflow**(live); verification-before-completion→verification-loop; handoff→metaswarm:handoff; ralph-orchestrator-setup→orchestration-patterns | Correctly retired w/ live successors; keep archived. | high |
| 15 | **learned** (deployed, no source) | **stale** (orphan) | deployed−wt_top−external={learned}; mtime 2026-05-27; has SKILL.md | Prune (or confirm intentional) — finding, not applied. | high |
| 16 | `~/.agents/library/skills` (186) | **stale** / experimental | uniform mtime 2026-04-05; 27/186 overlap deployed; 159 dormant (android/api/django/golang/cpp packs) | Separate frozen import; promote-select / archive / drop — owner scope call. | high |
| 17 | off-box clones (D:\gem-wave-b, D:\pr-b-clone, C:\tmp\ds-*, mm-pristine) | **stale** / duplicate | `git worktree list` (mm-pristine) + A0 census Cat-3 | Out of live-lane scope; A0/D0.5 retire. | med |

**Every taxonomy class is instantiated:** exact-duplicate (#6 candidate + clean daily/deployed
content matches) · generated-projection (#1,#2,#7,#10) · valid-provider-adapter (#9,#10) ·
intentional-scope-override (daily-by-design, claude_only, #8) · fork-with-divergence (#3,#4,#11) ·
compatibility-shim (#11,#12, sync-vs-marketplace) · experimental (#5,#8, library) · superseded
(#14, #7-status) · stale (#13,#15,#16,#17) · unresolved (#5, monitorcore-canonical, command/agents SSOT).

---

## 3. The DIAGNOSE monitoring skills (explicit fold-in)

- **`workflow-monitor` (wfmon)** and **`recall-workflow-agent`** — top-level skills, share one parser
  `workflow_run.py`. **On origin/main (#71 ✓)**; deployed as a clean projection (hash-matched). BUT the
  **deployed/reconcile copies are the PRE-#75/#76 version** — they lack the `monitorcore/` subpackage.
- **`monitorcore`** — NOT a skill; a Python **package** at `skills/workflow-monitor/monitorcore/*.py`
  (12 modules: contract, discovery, export, monitors, pdf, redact, render_html, render_md, report_doc,
  agent_state, agent_tail, `__init__`) on origin/main, **duplicated** at `tools/monitorcore/`
  (tests/fixtures). Canonical home = **unresolved**.
- **`monitor-launcher`** — a separate skill (`skills/monitor-launcher/mon.cmd` + `monitors.toml`, PR-B2
  #76) on origin/main; **NOT deployed, NOT in daily, NOT in the reconcile worktree**.
- **Net:** the monitoring backbone is merged on main but **absent from every live lane.** Re-deploy
  from post-#76 main is a prerequisite before the control-plane "rides wfmon."

## 4. task-9 `codex-invoke` + the codex-* lane

- **`codex-invoke`** is present in the reconcile worktree `skills/` ONLY — absent from deployed, daily,
  and the toolchain branch (one of only 2 skills in `wt_top − deployed`, the other being the `external`
  container). This exactly matches its documented **HELD** status: the scoped `codex exec` primitive
  (5 profiles, M0–M3 MCP/skills scoping, `SUCCESS:`/`FAILED:` contract, `codex-doctor` trust gate). It
  is the keystone cross-vendor lane — the `codexAgent()` sibling of the native `agent()` — and deploys
  only after the deploy/pin prerequisite. **Class: experimental (held-by-design).** Task #7.
- The **codex-*** family (codex-consult/orchestrate/runtime-recovery/session-reunion/vscode-host-routing/
  fleet-github + format-codex-sessions) are **valid provider-adapters** for the first-class Codex lane —
  NOT duplicates of Claude skills. Only `codex-consult` is surfaced in the daily lane.

---

## 5. Confidence (Sherman-Kent) & receipts

- Lane counts, membership, branch topology, PR-merge status: **high (95-99%)** — git + fs verified.
- Projection integrity (deployed ← source): **high** — 5/5 hashes match.
- Daily drift (membership + content): **high** — 22 daily-only + 4/9 hash-differ measured.
- metaswarm fork intent + off-box clones: **medium (60-75%)** — provenance inferred.
- monitorcore canonical home + 22 daily-only source-of-truth: **unresolved** (open questions).

**Receipts:** `git worktree list` (toolchain 80a5863 / reconcile dd5366b / mm-pristine detached);
`origin/main` HEAD `0d7112d (#77)`; `ls-tree origin/main:skills` ⊇ {workflow-monitor,
recall-workflow-agent}; `merge-base --is-ancestor` {4b531cd #76, 9fd4245 #75} → 0 (merged);
projection hashes §2 row 1; daily-drift set §0.3; membership `scratchpad/membership.json` (491×8);
cross-read `ingest-task9-codex-invoke.md`, `ingest-wfmon-native-workflows.md`,
`ingest-diagnose-and-optimize.md`; sibling `A0-wholedrive-census.md` (off-box clones).

`SUCCESS:A4-skills-dup-matrix` — READ-ONLY, freeze respected (no build / commit / config / process /
deploy change; all dispositions are findings).
