---
title: toolchain-repo
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/audit/toolchain-repo
---

# Audit — `C:\Users\prekzursil\source\agent-skills-toolchain` (lane: toolchain-repo)

Date: 2026-09-29. All findings below were produced in this session against this checkout.
Every command quoted was run here; every path:line was read here. Anything I did not run is
stated as not run.

## 0. Executive summary

This checkout is a **hollowed, stale shadow of a live remote**. The GitHub remote
(`Prekzursil/agent-skills-toolchain`, PRIVATE, default branch `main`, head `6793d8e2`,
pushed 2026-09-29T16:13:26Z — verified via `gh api repos/Prekzursil/agent-skills-toolchain/commits/main`)
is healthy and 285-entry `command-center/` and a 5,291,659-byte `WORK-UNIT-CATALOG.json` exist
on `main` (verified via `gh api .../contents/command-center?ref=main`). The local tree, by
contrast:

1. has an **empty `.git`** — no history, no index, no refs (`ls -la .git` shows only `.` and `..`);
2. has **20+ top-level trees present as empty directories** (`docs/`, `.github/`, `.quality/`,
   `command-center/`, `hooks/`, `ci/`, `agent-self/`, `.agents/`, `.claude-plugin/`,
   `browser-profiles/`, `agents/`, `commands/`, `guides/`, `harness*/`, `browser-bridge/`, `out/`);
3. still carries all the **narrative documents that describe the missing machinery**
   (README, QUALITY-CHARTER, RECONCILE-*, REPO-TOPOLOGY, golden/), so every "how this works"
   instruction in the local tree now points at absent files.

What survives locally and works: `platform/` (1,303 files — the tournament/defect/council/
marketplace program), `skills/` (375 dirs), `skills-claude-only/` (36), `tools/` (63,770 files
incl. vendored trees), `scripts/` (112), `rules/` (92), `release/`, `userscripts/`, `golden/`,
`reconcile-flags/`, root manifests and probe scripts.

Verification of surviving machinery (run this session):
- `python platform/architecture/_probe_crossvendor_alias_hole.py` → `VERDICT: "REFUTED: the
  gate normalizes vendor identity already"`, `SUCCESS:crossvendor-alias-hole` (D1 fix still green).
- `"C:\Python314\python.exe" -m pytest platform/lib/test_vendor_identity.py -q` → **248 passed**.
- `python platform/lib/vendor_schema_sync.py --check` → `SUCCESS:vendor-schema-sync`.
- `"C:\Python314\python.exe" -m pytest platform/lib/test_schema_resolver.py -q` →
  **14 failed, 19 passed, 4 skipped, 1 error** — the D3 guard suite is red *because its input
  substrate is gone locally*: `FAILED:gen-substrate catalog absent at ...\command-center\WORK-UNIT-CATALOG.json`
  (the generator correctly fails closed; the data is what is missing).
- `python tools/command-center/validate.py` → `FAILED:cc-validate cannot read ...WORK-UNIT-CATALOG.json`,
  real exit code 1.

## 1. The git estate is severed locally

- `ls -la .git` → the directory exists but contains **nothing**; `cat .git/HEAD` →
  `No such file or directory`; any `git` command in the tree → `fatal: not a git repository`.
- Consequence: every procedure the reconcile documents define is unexecutable here —
  `RECONCILE-STATE_2026-09-01.md:24-29` (branch census loop), `RECONCILE-STATE:68-73`
  (green-main ruff/pytest numbers, "re-derivable"), `REPO-TOPOLOGY.md:22-23` (worktree
  checkout rules), the rollback rehearsals of `platform/architecture/TOURNAMENT-VERDICT.md:404-414`
  (all phrased as git reverts). Not run — impossible in this tree; the remote equivalents were
  spot-checked with `gh api` instead.
- `REPO-TOPOLOGY.md:45-50` names five sibling checkouts (`ast-integrate`, `ast-harness-reconcile`,
  `ast-statusline-capture`, `D:\ckwt\...`, `D:\inc1-wt\...`). Measured: `ls C:\Users\prekzursil\source`
  → only `Airline-Reservations-System`, `Personal-Finance-Management`, `agent-skills-toolchain`,
  `open-coscientist`, `repos`. **All five are gone**, including `ast-integrate` — the checkout
  `REPO-TOPOLOGY.md:12` declares "the SSOT… edit here". The doc's own "Recommended consolidation —
  NOT yet executed" (`REPO-TOPOLOGY.md:119-128`, "Store B retirement is still open") was evidently
  overtaken by events (store B is gone) without the doc being updated.
- The program spec corpus every platform status doc anchors to is also gone:
  `ls C:\Users\prekzursil\.claude\harness-restore-20260806` → cannot access (0 entries);
  `find ~/.claude -maxdepth 2 -name "_USER-PROMPTS.md"` and `-name "09-WORKFLOW-BLUEPRINT-LIBRARY.md"`
  → no hits. Yet `platform/schema/CONFORMANCE-STATUS.json` (spec_source.file),
  `platform/registry/workflow-candidates-2.json` and `5.METHOD.json`, and every
  `platform/workflows/BP*-STATUS*` doc cite paths inside that directory as their spec.

## 2. Locally empty trees vs. live remote (measured both sides)

`find <dir> -type f | wc -l` per top-level dir (this session):

| files | dir | described locally by | on remote main |
|---|---|---|---|
| 0 | `command-center/` | RECONCILE-STATE:84 (REGISTER.md ledger, 339 lines), TOURNAMENT-VERDICT:30-36 (233 schema shims, catalog) | **285 entries** incl. `WORK-UNIT-CATALOG.json` (5,291,659 B), `ARTIFACT-MANIFEST.json` (gh api) |
| 0 | `.github/` | README:79-96, QUALITY-CHARTER:36-48 (quality.yml, skill-dual-write.yml, dependabot) | 25 workflows incl. `quality.yml`, `skill-dual-write.yml` **plus 23 newer ones** (`autofix-models`, `codex-runner`, `p2-agent-runner`, `decisions`, `no-runtime-junk`, …) |
| 0 | `.quality/` | README:94-96, QUALITY-CHARTER:47-48 (charter.yml, charter_check.sh, opengrep ruleset) | not checked remotely |
| 0 | `docs/` | README links: `docs/SECRETS.md`, `docs/plans/`, `docs/incubating/`, `docs/mcps/`, `docs/workflows/deep-research-literature-workflow.md`, `docs/codex-consult-analysis.md`, `docs/multi-agent-quickstart.md`, `docs/cursor-cli-bridges.md`, `docs/SESSION-RECONCILIATION-2026-06-10.md` — **all dead links locally** | not checked remotely |
| 0 | `hooks/`, `ci/`, `agent-self/`, `.agents/`, `browser-profiles/`, `browser-bridge/`, `agents/`, `commands/`, `guides/`, `harness/`, `harness-audits/`, `harness-sota-2026-07-18-corpus/`, `.claude-plugin/`, `.claude/`, `out/` | README:174 (hooks canonical copy), README:13-14 (plugin marketplace install), RECONCILE-STATE:71-78 (`.agents/tests`, `agent-self/harness` suites), RECONCILE-LOG:55-58 (`ci/harness` deploy tree) | not checked remotely |

Live-estate corroboration (outside the repo): `C:\Users\prekzursil\.claude\hooks` still exists
(`_dispatch`, `semantic-router`, 20+ hook families) and `C:\Users\prekzursil\.agents\harness`
exists (dispatcher.py mtime 2026-09-02, tests/ 27 files) — i.e. the *live* side the repo is
supposed to be the SSOT for is intact; only the repo's copies are gone.

## 3. Findings — planned/designed but never included; half-finished lanes; decisions never applied

### F1 — Tournament migration path G0–G10: partially landed, and the landing is now unverifiable locally
`platform/architecture/TOURNAMENT-VERDICT.md:391-414` defines the winner's migration path and
:430-431 states "NOT-CHECKED: no stage of the migration path was executed… G0-G10 are a design."
Measured now:
- **G1/D3 landed** (fix record `platform/DEFECT-D3-TEST-MUTATES-TREE.md` §C, suite evidence) but
  is **red locally today** through no fault of its own — 14 failures in
  `platform/lib/test_schema_resolver.py`, all rooted in the missing catalog (see §0).
- **G3/D1 landed and still green** — probe + 248 tests pass (see §0).
- **G4/D2 landed** — `platform/lib/wfdsl/authz_census.py` and `test_work_unit_authorization.py`
  exist on disk (listed this session; not executed — see §5).
- **G0 ("commit the untracked substrate") was never done** — it was D4, "an absent commit"
  (`TOURNAMENT-VERDICT.md:67`); locally it can no longer be done at all (no git).
- **G2 (the `or ""` wall_cap coercion in `dispatch.py`) is unverifiable**: `grep -n 'or ""' platform/coordination/dispatch.py` →
  no hits, but the G2 target per the verdict's M4 was the *live hook* dispatcher
  `hooks/_dispatch/dispatch.py` — and `hooks/` is empty locally. Not run further.
- The panel's own evidence instruments are gone: `TOURNAMENT-VERDICT.md:15-16` names
  `_judge_verify.py`, `_judge_verify2.py`, `_judge_refutation.py` as its probes;
  `ls platform/architecture | grep judge` → nothing. Only `_probe_crossvendor_alias_hole.py` survives.

### F2 — The `17-DECISION-LOG.md` is unbacked filler posing as owner rulings
Measured: 153 `## DL-` headers; 158 `padding-NNNN` HTML comments
(`grep -c "^## DL-"` = 153, `grep -c "padding-"` = 158). Of these, DL-0101..DL-0250 are 150
byte-identical "Owner ruling NNN: keep workflow catalog entry WF-NNNN as the published path"
stanzas all dated 2026-07-15; DL-0158..DL-0174 carry **empty bodies** (header + dates only).
`grep -rln "WF-0250\|workflow catalog" --include=*.md --include=*.json --include=*.yml .`
→ the **only** hit is `17-DECISION-LOG.md` itself: no workflow catalog with `WF-NNNN` ids exists
anywhere in the repo (the real registries use `WFC-00xx`/skill ids —
`platform/registry/workflow-candidates-4.json`). 150 "owner rulings" cite an artifact that
does not exist. Treat this file as fabricated/synthetic, not as a decision record.

### F3 — `golden/AGENTS.md` no longer mirrors the live contract, and its own rule is broken
`golden/SHA256.txt` records `sha256 52D96A3C…`, `source C:\Users\Prekzursil\AGENTS.md`,
`date 2026-09-23`, `bytes 37172`, `rule do-not-edit-this-copy`. Measured:
- `golden/AGENTS.md` = 37,172 B, sha256 `52d96a3c111e…` (matches its own record — self-consistent);
- live `C:\Users\prekzursil\AGENTS.md` = **1,132 B**, different hash (mtime 2026-09-24 17:36 —
  replaced *after* the snapshot).
`golden/AGENTS.md:4` mandates that every runtime load rules from the live file "(or a 10-line
pointer file that only includes that)". The live file is now a 20-line "VM working contract"
that does **not** include or point to the golden contract — so the estate locks, memory contract,
MCP sync policy and the whole owner-identity block in the golden file are loaded by nothing on
this box. The golden snapshot is the only surviving copy of that contract.

### F4 — Harness-lineage reunion output: live half landed, repo half deleted
`reconcile-flags/harness-lineage-reunion-2026-09-02.md` (header note) says the reunion ported
the live fixes into `agent-self/harness` (834→926 tests) and refreshed `.agents/harness`.
Measured: **both trees are empty locally** (`agent-self/` 0 files, `.agents/` 0 files), while the
live `C:\Users\prekzursil\.agents\harness` exists. So the repo half of the reunion — the
"maintained source" the doc says CI runs — exists only on the remote now.

### F5 — Cursor provider adapter: fully scoped, never built (deliberate, but still open)
`reconcile-flags/cursor-provider-followup-2026-09-02.md:4-6` — "nothing about Cursor was built
here", Cursor sessions get "none of the lifecycle enforcement". Verified still true on the live
tree: `grep -n SUPPORTED_PROVIDERS C:\Users\prekzursil\.agents\harness\adapters.py` →
`{"claude", "codex", "grok"}`; `grep -i cursor` in that file → no hits.

### F6 — `mcp-cursor-merge` reconciliation: landed on a branch; local evidence gone
`reconcile-flags/mcp-cursor-merge-lineage-2026-09-02.md:41-56` records the reunited
`merge_generated_cursor_mcp.py` on branch `cursor/generated-cursor-mcp-reconciliation-ae2a`
(82 tests green in `.agents/tests`). The live script carries the reunion markers
(`grep -c "ApprovalEvidenceError\|attach_all_safe\|CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS"` on the
live file → 27 hits), but the repo's `.agents/scripts` copy is gone with the empty `.agents/`,
so the in-repo CI step that doc describes cannot run locally.

### F7 — `JOBMON`/`taskwatch_monitor`: package and skill landed; the commands-file artifact did not
`JOBMON_DESIGN_GRILL.md:41` (converged spec, grill COMPLETE 2026-07-11) lists artifacts incl.
`~/.claude/commands/taskwatch_monitor.md`. Measured: `tools/taskwatch_monitor/` exists in the
repo, `skills/run-taskwatch_monitor/` exists, the live skill exists
(`C:\Users\prekzursil\.agents\skills\run-taskwatch_monitor`), but
`ls C:\Users\prekzursil\.claude\commands | grep -i taskwatch` → **no match** (75 command files).
The `/taskwatch_monitor` command surface of the spec was never created (or was removed).

### F8 — RECONCILE-STATE §6b open items: mixed fates, one contradiction
- 6b.3 "Intake #288's questions into `REGISTER.md`" — **unresolvable locally**: both `docs/`
  (the merged queue) and `command-center/sources/REGISTER.md` are gone. Not verified remotely.
- 6b.4 harness-lineage decisions — decision 1 resolved (reunion, F4), decision 2 not built (F5).
- 6b.5 retire the 2026-07 lanes — executed by the owner per
  `reconcile-flags/branch-retirement-nonjuly-2026-09-02.md:10-12` ("the owner ran the July delete
  script… 74 branches gone… all 74 `archive/2026-07/*` tags intact"). Locally the tags are
  unreachable (no git); they exist only on the remote.
- 6b.6 "Rotate the personal access token" (`RECONCILE-STATE:173-175`) — no evidence it was done,
  and it **contradicts the standing NEVER-ROTATE lock** (`golden/AGENTS.md:251`, owner ruling
  28.08.2026, and the live VM contract's "Do not rotate credentials"). A reconcile doc written
  2026-09-01 recommending rotation three days after the lock is a decision that was never
  applied *and* never should be, as-applied.

### F9 — Stranded authored work on archived branches
`reconcile-flags/branch-retirement-nonjuly-2026-09-02.md:34-40`: the
`wip/harness-workspace-supervisor-20260826` branch holds **6,435 lines of authored, unshipped
code and tests** ("the only content in the set that is a coherent capability `main` does not
have", its own commit message says "Not for merge to main until reviewed/tested"; no PR), plus
792 lines of parked forensic scripts on `fix/deny-credential-gaps`. These are
planned-but-never-included lanes whose only remaining handle is the remote archive tags
(`archive/2026-09/*`) — locally unreachable since `.git` is empty.

### F10 — README/charter vs reality
- `README.md:13-14` Quick Start (`claude plugin marketplace add … --sparse .claude-plugin …`)
  is broken locally: `.claude-plugin/` has 0 files.
- `README.md:38` says `tools/web/` is "0 — Empty since the 2026-08-09 ChatGPT-web retirement";
  measured: `tools/web/agentify-desktop/` exists containing **only `node_modules`** — a retirement
  husk that contradicts both the "0" claim and the "five trees deleted" narrative at
  `README.md:131-133`.
- `QUALITY-CHARTER.md:36-37` ("**One CI workflow.** All gates run inside the single `quality`
  workflow") vs remote reality: 25 workflows on main (verified `gh api …/actions/workflows`),
  including runner/noise/probe workflows the charter never mentions. The charter is stale
  against the remote it claims to govern.
- Skills counts drift: `ls -d skills/*/ | wc -l` → **375** vs README's 372;
  `skills-claude-only` → **36** vs README's 35.
- `.gitleaks.toml:236-260` still carries the `browser-profiles/` path waiver for a tree that no
  longer exists locally (it does on the remote — harmless there, dead config here).

### F11 — Environment notes that gate any re-verification
- `python` on PATH is **3.12.10 without pytest/jsonschema** (`python -m pytest --version` →
  No module named pytest; `import jsonschema` fails), while `C:\Python314\python.exe` (the one
  `AGENTS.md` names) has both. Any doc instructing bare `python -m pytest` (e.g.
  `platform/schema/CONFORMANCE-STATUS.json` commands block) fails on this box.
- Repo-root junk: `a.yml` (0 bytes), `mitm_mcp_traffic.db` (24,576 B, 2026-09-19) — plus a second
  copy inside `zai-lanes/`. Tracked-vs-untracked status unverifiable (no git).
- Repo `CLAUDE.md` is the pre-amendment VM contract ("Do not print secret values",
  `CLAUDE.md:12`) while live `AGENTS.md:12-15` carries the newer PRIVATE-ESTATE PLAINTEXT
  amendment (24.09.2026) — the two "same" files have diverged; `CLAUDE.md.pre-vm-blunt` (root)
  preserves the older long contract.

## 4. What is intact and healthy in this tree (for contrast)

- `platform/` program artifacts: 9 architecture candidates + TOURNAMENT-VERDICT, D1/D3 defect
  records, council presets (60+) and protocols (48), plugin/routing/marketplace/coordination
  lanes with their MEASURED status files, 108 workflow-blueprint JSONs + per-slice STATUS docs,
  forged/ REJECTED + fused experiments, VENDOR-REGISTRY + generated enum sync (green, §0).
- `reconcile-flags/` — the full adjudication trail (import-2026-08-28, harness-lineage +
  reunion, mcp-cursor-merge, branch retirements July + non-July) — the best-preserved
  decision record in the tree.
- `skills/` + `skills/DEPLOYED-MANIFEST.json` (105 entries) + `SKILLS-MANIFEST.md`,
  `scripts/` (incl. the non-destructive `sync-hooks.ps1` — verified copy-only by read; its
  canonical `hooks/` source is gone, so it is now a no-op that can no longer *restore* live
  hooks), `rules/` (15 dirs), `tools/` incl. `scholarly-access-mcp` and `taskwatch_monitor`.

## 5. Checks not run (and why)

- Full `python -m pytest platform -q` — not run (targeted files above suffice for the audit;
  the tree is also missing its catalog input, so a full run measures the gutting, not the code).
- `.agents/tests`, `agent-self/harness/tests`, `pytest .agents/harness/tests` from
  RECONCILE-STATE §3 — impossible: both trees are locally empty.
- ruff / gitleaks / osv-scanner gates — tooling not invoked (audit is read-only; gates' config
  trees `.quality/`, `.github/` are locally absent anyway).
- Remote PR/branch-level reconciliation (e.g. whether `cursor/generated-cursor-mcp-reconciliation-ae2a`
  merged) — only repo/workflow/content-level `gh api` reads were made; not exhaustively enumerated.

## 6. Recommended owner actions (priority order)

1. Treat this checkout as **non-authoritative**: the remote is the SSOT (REPO-TOPOLOGY's own
   rule, `REPO-TOPOLOGY.md:12`). Either re-clone to a fresh worktree or retire this path;
   do not run repo→live sync scripts from it in its hollowed state.
2. Re-run the D3/schema-resolver suites in a checkout that has `command-center/` (remote main)
   before citing any platform green/red number from this tree.
3. Decide the fate of `17-DECISION-LOG.md` (F2) — 150 unbacked "owner rulings" should not be
   quotable as decisions.
4. Re-point or re-authorize `golden/AGENTS.md` (F3): the live file no longer includes it, and
   the golden copy is now the only surviving instance of the estate contract.
5. The genuinely open designed-not-built lanes worth an owner decision: Cursor provider adapter
   (F5), workspace-supervisor salvage (F9), taskwatch command artifact (F7).