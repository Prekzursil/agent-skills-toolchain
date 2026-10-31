---
title: CODEX-STUB-RETIREMENT-LANE
type: note
permalink: dqverify-repo-20261013/command-center/codex-stub-retirement-lane
---

# CODEX STUB RETIREMENT LANE

**Status:** REVIEWED PLAN — NOT EXECUTED. Nothing in this document has been applied to the
pinned repo. Author changed zero files under `skills/`, `.agents/skills/`, or
`.claude-plugin/`.

**Measured:** 2026-08-09 against `agent-skills-toolchain` @ `53c37c6c` (branch `main`).
**Unit:** `side:codex-stubs`.

---

## 0. Headline

All nine stubs are **ROUTED-BUT-BROKEN**, and they are broken in *two independent ways at once*:
the skill is not resolvable in a live session, **and** the `codex_*` tool each one delegates to
does not exist on any mounted server. Zero are DEAD (all nine are still declared in the plugin
manifest) and zero are LIVE-AND-WORKING.

Two briefed premises did not survive measurement:

| Briefed claim | Verdict | Measurement |
|---|---|---|
| "They are live-deployed" | **REFUTED** | Present only in `REPO/.agents/skills/`. Absent from `~/.agents/skills`, `~/.claude/skills`, and `REPO/skills/`. `Skill(skill="codex-review")` -> `Unknown skill`. |
| "routed from 4 call sites" | **PARTIAL (undercount)** | 5 functional surfaces across 6 physical files, plus ~14 documentation references. |

The single highest-value result in this lane is the **atomicity constraint** in §5, which was
measured, not reasoned: **either half of the change alone turns CI red.**

---

## 1. The nine stubs — exact inventory

All nine live at `C:/Users/Prekzursil/source/ast-integrate/.agents/skills/<name>/SKILL.md`.
Each is a single file of 210-231 bytes whose entire body is one sentence naming a tool.

| # | Stub | Bytes | Delegates to | Tool exists? |
|---|---|---|---|---|
| 1 | `codex-audit` | 225 | `codex_review` | NO |
| 2 | `codex-brainstorm` | 220 | `codex_brainstorm` | NO |
| 3 | `codex-coordinate` | 218 | `codex_coordinate` | NO |
| 4 | `codex-curate` | 231 | `codex_curate` | NO |
| 5 | `codex-discuss` | 210 | `codex_discuss` | NO |
| 6 | `codex-fix` | 218 | `codex_coordinate` | NO |
| 7 | `codex-governance` | 223 | `codex_curate` | NO |
| 8 | `codex-review` | 219 | `codex_review` | NO |
| 9 | `codex-triage` | 210 | `codex_consult` | NO |

Six distinct delegation targets: `codex_review`, `codex_brainstorm`, `codex_coordinate`,
`codex_curate`, `codex_discuss`, `codex_consult`.

**The count "9" is CONFIRMED**, and it is exact in both directions — the repo contains no tenth
per-mode wrapper, and none of the nine is missing.

### Presence matrix (measured, PowerShell `Test-Path`, with detector control)

| Root | 9 stubs present? | Control (`codex-orchestrate`) |
|---|---|---|
| `REPO/.agents/skills` (authoritative) | **9 / 9** | present |
| `REPO/skills` (generated projection) | 0 / 9 | present |
| `~/.agents/skills` (live) | 0 / 9 | present |
| `~/.claude/skills` (live, Claude-visible) | 0 / 9 | absent (genuine) |

The control is what makes the zeros trustworthy: the same probe found `codex-orchestrate` in
three of four roots, so a `.` in the stub columns is a real absence, not a broken matcher.

---

## 2. Every reference, by role

Estate-wide scan: 267,224 files walked across `REPO`, `~/.agents`, `~/.claude`.
Scanner: `~/.claude/harness-restore-20260806/_scan_codex_stub_refs.py` (writes
`_codex_stub_refs.json`); bucketed by `_bucket_codex_refs.py`; focused by `_focus_codex_refs.py`.

**Raw counts are worthless here and must not be quoted.** The nine names produce 6,762-8,930 raw
hits each, almost entirely session transcripts under `~/.claude/projects/` that quote the skill
listing. That is the classic use-vs-mention trap: a transcript that *names* a skill cannot
*route* to it. After excluding mention-only surfaces, salvage clones, `file-history`, scratch
trees and corpora, **84 files** remain, of which the functional ones are below.

### 2A. FUNCTIONAL surfaces — these can break

| # | File | Lines | What it does | Breaks on naive delete? |
|---|---|---|---|---|
| F1 | `REPO/.claude-plugin/marketplace.json` | 82, 83, 85, 86, 88, 89, 91, 95, 98 | Declares all 9 as published skill routes (`./.agents/skills/<name>`) | **YES — CI red** |
| F2 | `REPO/release/platforms/windows/promptbridge-orchestration.toml` | `[skill_mappings.codex-*]` x9 | Maps each stub -> `codex_*` tool + profile | No (inert config) |
| F3 | `REPO/hooks/skill-router/eval.py` | 56-57 | Router **eval fixture**: expects prompt -> `["codex-review"]` | No (assertion goes stale) |
| F4 | `~/.claude/hooks/skill-router/eval.py` | 56-57 | Deployed twin of F3, **byte-identical** (verified by `diff`) | No |
| F5 | `REPO/ci/harness/prebuild_recall/fixture_index.json` | 2191 | `codex-review` as a recall keyword | No |
| F6 | `~/.agents/state/harness/recall-index.json` | 5561, 11657, 13274, 13275, 15627 | Generated keyword index (`built_at` / `vault_hash`) | No — regenerable |

**F1 is the only hard dependency.** F2 is a generated config for a subsystem already deleted
(`integrations/codex/bootstrap.mjs` generated it; the PromptBridge trees were removed 2026-08-09).
F3/F4 are an expectation, not a call. F5/F6 are keyword lists.

So: **5 functional surfaces / 6 physical files.** The briefed "4" is an undercount, not a
fabrication — it is right about the order of magnitude and about F1 being the one that matters.

### 2B. DESCRIPTIVE references — stale prose, no runtime effect

`REPO/.agents/skills/codex-orchestrate/SKILL.md` (L3 description + L60-62 "Replaces") and its
projection `REPO/skills/codex-orchestrate/SKILL.md`; `~/.agents/skills/codex-orchestrate/SKILL.md`
(deployed); `REPO/README.md`; `REPO/docs/plans/2026-03-10-agent-skills-toolchain-design.md`;
`REPO/skills/multi-agent-quickstart/SKILL.md` + `.agents` twin + `REPO/docs/multi-agent-quickstart.md`
+ `REPO/scripts/merges/.agents/skills/multi-agent-quickstart/SKILL.md`;
`REPO/skills/cyberstrike/references/plugin-bridge.md` + `.agents` twin;
`REPO/docs/codex-consult-analysis.md`; `REPO/release/platforms/windows/codex-AGENTS.md`;
`REPO/release/platforms/windows/codex-model-instructions.md`;
`REPO/agent-self/config/docs/WORKSPACE-CURATION.md`;
`REPO/skills/codex-mixed-workflow-doctrine/SKILL.md` + `.agents` twin;
`REPO/docs/claude-toolkit-gap-analysis-2026-05-28.md`;
`~/.agents/skills/multi-agent-quickstart/SKILL.md`.

### 2C. Prior art — this was already recommended once

`~/.claude/harness-mega-audit-2026-07-18/findings/A23.md:24` already recommends pruning exactly
these nine. It was **not** actioned, and `~/.claude/HARNESS-AUDIT-2026-06-21.json:546-548`
records an earlier verdict of `confirmed=FALSE` against a *differently-scoped* prune proposal.
Owner should know a prior audit disputed a neighbouring recommendation before signing this one.

---

## 3. Per-stub verdict

Verdict is identical for all nine; the evidence is per-stub only in the delegation column.

**Verdict: ROUTED-BUT-BROKEN (all 9).** Not DEAD — each is referenced by F1. Not
LIVE-AND-WORKING — neither the skill nor its target resolves.

### Evidence, invocation-level (the exact commands and outputs)

Broken in direction 1 — **the skill does not resolve**:

```
Skill(skill="codex-review")  ->  Unknown skill: codex-review. Did you mean code-review?
Skill(skill="codex-audit")   ->  Unknown skill: codex-audit
```

Detector control for that probe (proves the resolver is not rejecting everything):

```
Skill(skill="codex-consult") ->  Launching skill: codex-consult   [resolved and loaded]
```

Broken in direction 2 — **the delegation target does not exist**:

```
ToolSearch("select:codex_review,codex_brainstorm,codex_curate,
            codex_discuss,codex_coordinate,codex_consult")
  ->  No matching deferred tools found
```

Detector control for *that* probe (proves ToolSearch can resolve a real Codex tool):

```
ToolSearch("select:mcp__codex__codex,mcp__codex__codex-reply")
  ->  both returned with full JSONSchema definitions
```

Corroborating third signal: this session's own available-skills inventory lists `codex-consult`,
`codex-databricks-fanout`, `codex:rescue`, `codex:setup`, `codex:codex-cli-runtime`,
`codex:codex-result-handling`, `codex:gpt-5-4-prompting` — and **none of the nine**.

Two mechanically independent probes agree in each direction, each with its own control. This
satisfies the two-signal rule; no verdict here rests on a single reading.

---

## 4. Does the replacement cover them?

The estate reaches Codex via `mcp__codex__codex` / `mcp__codex__codex-reply` (schemas resolved
live, above) and via `~/.claude/agents/codex.md`. The nine stubs were *pure prompt-framing* —
each selected a mode label and a peer count, with no code behind it once the orchestrator server
was deleted.

| Stub | Coverage by the MCP rail | Note |
|---|---|---|
| `codex-audit` | **FULL** | frame "audit for risk/gaps" in the prompt |
| `codex-brainstorm` | **PARTIAL** | idea generation is full; the 2-peer fan-out + synthesis is not a tool feature — reproduce with 2 parallel `mcp__codex__codex` calls |
| `codex-coordinate` | **PARTIAL** | same: role-splitting was server-side; now must be prompt-expressed or fanned out |
| `codex-curate` | **FULL** | selector framing in the prompt |
| `codex-discuss` | **PARTIAL** | same 2-peer caveat as brainstorm |
| `codex-fix` | **FULL** | alias of coordinate; a fix path is one scoped prompt |
| `codex-governance` | **FULL** | alias of curate |
| `codex-review` | **FULL** | critic framing in the prompt |
| `codex-triage` | **FULL** | one scoped classification prompt |

**Six FULL, three PARTIAL.** The three PARTIALs lose only the *automatic* multi-peer fan-out and
synthesis. Since the server implementing that was deleted, the capability is **already lost
today** — retirement does not remove anything that currently works. `codex-orchestrate`,
`codex-invoke` (exec rail) and `multi-agent-quickstart` are the documented successors.

**No capability regression is introduced by this retirement.** Confidence: almost-certain
(90-99%), because the loss already happened when the orchestrator trees were deleted.

---

## 5. What breaks if removed — MEASURED, not predicted

Method: cloned the pinned repo to a scratch path (`--no-hardlinks`), applied each state, ran the
CI gates, then deleted the clone. The pinned repo was never modified.

| State | Delete 9 dirs | Edit `marketplace.json` | `gen_skill_index --check --fail-on-drift` | Diagnostic |
|---|---|---|---|---|
| 0 baseline | no | no | **exit 0** | `dangling 0`, `undeclared 0`, `INDEX DRIFT: no` |
| **A** | **yes** | no | **exit 1** | `dangling (declared, absent): 9`, `INDEX DRIFT: yes` |
| **C** | no | **yes** | **exit 1** | `undeclared (on disk): 9`, `canonical NOT declared: 9` |
| **B** | **yes** | **yes** | **exit 0** | `declared 370 / union 370`, `INDEX DRIFT: no` |

> **THE ATOMICITY CONSTRAINT.** States A and C are both RED. The directory deletion and the
> manifest edit **must land in one commit**. Splitting them across two commits leaves `main`
> red in between, and a PR containing only one half cannot merge.

I predicted, from `ci/gen_skill_index.py`'s "declared-only paths survive generation" docstring,
that State A would pass silently with 9 dangling routes. **That prediction was wrong.** The
measurement refuted it — the gate reports `INDEX DRIFT: yes` and exits 1. Recorded here rather
than quietly corrected, because the wrong version is the intuitive reading of that docstring and
the next person will make the same inference.

### Other gates, measured at State B

| Gate | Result |
|---|---|
| `ci/gen_skill_index.py --check --fail-on-drift` | exit 0 |
| `ci/gen_skills_manifest.py --check` | exit 0 — `skills_tracked=337 rows=337 orphan_rows=0` |
| `ci/check_skill_dual_write.py --base origin/main --head HEAD --strict-parity` | exit 0 — *"OK: changed skill paths match their final-tree counterparts."* |
| `ci/check_skill_context_budget.py` | exit 0 — 5710/8000 trigger chars; catalog 379 -> 370 |
| `pytest ci/tests tools/d001-dual-write/tests -q` | **597 passed, 4 failed, 1 skipped** |

The 4 failures are **pre-existing and unrelated**. Control: the identical 4 fail on the
*unmodified* pinned repo @ `53c37c6c` (`4 failed in 7.08s`). All four are Windows-platform
artifacts (invalid-UTF-8 path bytes, the executable mode bit, a PATH-shim race injector) and CI
runs `ubuntu-latest`. **Zero new failures attributable to this change.**

### D-001 has a purpose-built allowance for exactly this deletion

`.agents/skills/` is the **authoritative** root and `skills/` a **generated projection**
(`ci/check_skill_dual_write.py:3-6`) — the reverse of the intuitive layout. These nine are
therefore *canonical-only* skills. An earlier revision of the guard made them **unretirable**:
`--strict-parity` demanded a paired projection deletion that could never exist. That false
positive is fixed and pinned by tests. Live receipt:

```
pytest ci/tests/test_check_skill_dual_write.py -q -k canonical_only
  ->  5 passed, 34 deselected in 3.95s
```

including `test_strict_parity_allows_retiring_a_canonical_only_skill`.

### Live blast radius: none

`scripts/sync-skills.ps1` deploys from **`skills/`**, not `.agents/skills/`. Dry run:

```
pwsh -File scripts/sync-skills.ps1 -WhatIf -Prune
  ->  copies codex-consult, codex-databricks-fanout, codex-fleet-github, codex-invoke,
      codex-mixed-workflow-doctrine, codex-orchestrate, codex-runtime-recovery,
      codex-session-reunion, codex-vscode-host-routing, format-codex-sessions
  ->  prune orphan microsoft-foundry ; prune orphan qdx-rush   (2 orphans, neither a stub)
```

None of the nine appears in the deploy set, because none is in `skills/`. They **cannot** reach a
live tree through the supported path. Deleting them changes nothing a running session can see.

---

## 6. Removal steps, in dependency order

### Step 0 — pre-flight (read-only)

```
git -C <repo> rev-parse --short HEAD                      # expect a known-good base
python ci/gen_skill_index.py --check --fail-on-drift      # expect exit 0, INDEX DRIFT: no
python ci/gen_skills_manifest.py --check                  # expect exit 0
```
Abort if either is already red — you would not be able to attribute a later failure.

### Step 1 — the atomic commit (SAFE TO RETIRE)

Both halves in **one** commit. Order within the commit is irrelevant; separation across commits is
the failure mode (§5).

1a. Delete the nine directories:
```
.agents/skills/codex-audit/        .agents/skills/codex-brainstorm/
.agents/skills/codex-coordinate/   .agents/skills/codex-curate/
.agents/skills/codex-discuss/      .agents/skills/codex-fix/
.agents/skills/codex-governance/   .agents/skills/codex-review/
.agents/skills/codex-triage/
```

1b. Remove the nine entries from `.claude-plugin/marketplace.json` (lines 82, 83, 85, 86, 88, 89,
91, 95, 98 at `53c37c6c` — match by **value**, not line number, since earlier deletions shift
them):
```
"./.agents/skills/codex-audit", "./.agents/skills/codex-brainstorm",
"./.agents/skills/codex-coordinate", "./.agents/skills/codex-curate",
"./.agents/skills/codex-discuss", "./.agents/skills/codex-fix",
"./.agents/skills/codex-governance", "./.agents/skills/codex-review",
"./.agents/skills/codex-triage"
```
Do **not** touch `codex-consult`, `codex-databricks-fanout`, `codex-fleet-github`, `codex-invoke`,
`codex-mixed-workflow-doctrine`, `codex-orchestrate`, `codex-runtime-recovery`,
`codex-session-reunion`, `codex-vscode-host-routing` — those are the nine *real* codex skills and
are adjacent in the same list. **The two groups of nine are easy to confuse; check every value.**

Expected post-state: `declared in marketplace: 370`, `on-disk union: 370`, `INDEX DRIFT: no`.

1c. Verify before pushing:
```
python ci/gen_skill_index.py --check --fail-on-drift                                   # 0
python ci/gen_skills_manifest.py --check                                               # 0
python ci/check_skill_dual_write.py --base origin/main --head HEAD --strict-parity     # 0
```

### Step 2 — de-reference the prose (SAFE, same PR or a follow-up)

Update the `Replaces` list at `.agents/skills/codex-orchestrate/SKILL.md:60-62` **and its
projection** `skills/codex-orchestrate/SKILL.md` (D-001: canonical and projection must move
together or `--strict-parity` fires). Then the §2B files. Prefer "these nine per-mode wrappers
were retired 2026-08-XX; use the MCP rail" over silent deletion — the names appear in three prior
audits and a bare disappearance will be re-litigated.

### Step 3 — `promptbridge-orchestration.toml` (NEEDS OWNER SIGN-OFF)

`release/platforms/windows/promptbridge-orchestration.toml` carries nine `[skill_mappings.codex-*]`
blocks plus six `[profiles.*]` blocks for the deleted PromptBridge subsystem. Its header says
*"Generated and managed by integrations/codex/bootstrap.mjs"* — a generator that no longer exists.
Options: (a) delete the whole file as dead release config; (b) strip only the nine
`[skill_mappings]`; (c) leave it. **Not decidable from the code** — it ships in `release/` and the
owner may have downstream consumers. Recommend (a), confidence: likely (55-80%). Do not fold this
into Step 1: it is a different blast radius (release artifact vs plugin manifest).

### Step 4 — `hooks/skill-router/eval.py:56-57` (NEEDS OWNER SIGN-OFF)

The router eval asserts that *"ask codex to give a second opinion and review this implementation
plan before I build it"* should select `["codex-review"]`. After retirement that expectation names
a skill that does not exist. Retarget to `codex-orchestrate` (or `codex-invoke`) rather than
deleting the case — deleting it removes routing coverage for a real user phrasing. The deployed
twin `~/.claude/hooks/skill-router/eval.py` is byte-identical and must move with it, or the
deployed-hook-twin-parity gate will diverge. **Confirm the intended replacement target with the
owner** — I did not measure what the router *should* select, only that its current answer will
become invalid.

### Step 5 — regenerate the recall index (SAFE, deferred)

`~/.agents/state/harness/recall-index.json` holds five stale keyword occurrences. It is generated
(`schema_version` / `built_at` / `vault_hash`) and self-heals on the next rebuild. No action.

---

## 7. Rollback

Single-commit revert. There is no state outside git: no live deployment, no generated cache, no
database row.

```
git revert --no-edit <commit-sha>          # preferred: preserves history
python ci/gen_skill_index.py --check --fail-on-drift    # expect exit 0 -> back to 379
```

Post-revert expected: `declared in marketplace: 379`, `on-disk union: 379`, `INDEX DRIFT: no`.

If Step 2 (prose) shipped in the same PR, revert restores it too — harmless. If Steps 3/4 shipped
separately, revert them separately; they have no ordering dependency on Step 1.

**Do NOT roll back with `git checkout <sha> -- .agents/skills/codex-*`**: that restores the
directories while leaving `marketplace.json` pruned, which is State C — **red**.

---

## 8. The regression test

**`python ci/gen_skill_index.py --check --fail-on-drift`** is the guard, and it is already wired
into CI as the `gate-skill-surface-manifest` step of `.github/workflows/skill-dual-write.yml:71-72`
(a `pull_request` gate on `main`). No new test needs to be written.

It satisfies the both-states requirement — it was observed to FIRE in both broken directions, not
merely to be silent in the good one:

| State | Result | This proves |
|---|---|---|
| A: dirs gone, manifest stale | **exit 1**, `dangling: 9` | catches a half-done retirement |
| C: manifest pruned, dirs remain | **exit 1**, `undeclared: 9` | catches the reverse half |
| B: both | exit 0 | does not false-positive on the correct change |
| 0: neither | exit 0 | does not false-positive on the status quo |

A gate silent in both states measures nothing; this one is red in both failure directions and
green in both consistent ones. That is the strongest evidence in this lane.

Secondary guards, already wired: `gate-skills-manifest-inventory`
(`ci/gen_skills_manifest.py --check`) for the human inventory, and the `D-001` strict-parity gate
for canonical/projection symmetry.

---

## 9. Safe-to-retire vs needs sign-off

| Item | Classification |
|---|---|
| Delete the 9 dirs + prune 9 `marketplace.json` entries (Step 1, atomic) | **SAFE TO RETIRE** — measured CI-clean, zero live blast radius, no capability regression |
| De-reference the prose (Step 2) | **SAFE** — cosmetic; keep canonical+projection in step |
| `promptbridge-orchestration.toml` (Step 3) | **OWNER SIGN-OFF** — release artifact, unknown consumers |
| `hooks/skill-router/eval.py` expectation (Step 4) | **OWNER SIGN-OFF** — needs a chosen replacement target |
| Recall index (Step 5) | **SAFE** — regenerates itself |

---

## 10. Adjacent defect found while scoping — NOT part of this lane

Reported because it is strictly worse than the nine stubs and was invisible until a stub probe
tripped over it.

**The live `codex-consult` is a pre-tombstone copy that actively misdirects.** The repo version was
retired to a redirect tombstone on 2026-08-09; the live copies were never updated. Four-way hash
comparison of `SKILL.md`:

| Location | sha256 (first 16) | Bytes | Contains `RETIRED`? |
|---|---|---|---|
| `REPO/skills/codex-consult` | `75a652e143487326` | 2116 | **yes (2)** |
| `REPO/.agents/skills/codex-consult` | `75a652e143487326` | 2116 | **yes (2)** |
| `~/.agents/skills/codex-consult` | `1c3b4dafc3be044c` | 3068 | **no** |
| `~/.claude/skills/codex-consult` | `1126163e4a34062f` | 3279 | **no** |

Three distinct versions. Unlike the nine stubs, this one **is** live, **is** Claude-visible, and
**does** load: `Skill(skill="codex-consult")` returned the old body, which instructs the agent to
call `codex_local_consult` / `codex_local_curate` / `codex_local_review` with
`codex_orchestrator_*` fallback — none of which exist — and to "check `CODEX_HOME`, the
PromptBridge MCP registration, and the codex-orchestrator MCP", a debugging path into deleted
trees. Severity: this wastes a real session, whereas the nine stubs are unreachable and waste
nothing.

`~/.agents/skills/codex-orchestrate/SKILL.md` has the same shape (deployed; carries a DEPRECATED
banner but still tables six non-existent `codex_*` tools). It is not in `~/.claude/skills`, so it
is not Claude-visible in this session.

Suggested fix (**owner sign-off — it writes to live trees, which is outside this unit's scope**):
`pwsh -File scripts/sync-skills.ps1 -Prune` after a `-WhatIf` review. The script's own header
already calls for exactly this: *"Worth a -Prune pass after the 2026-08-09 Codex-lane"*
consolidation. The dry run shows it would overwrite live `codex-consult` with the repo tombstone
and prune only two unrelated orphans (`microsoft-foundry`, `qdx-rush`).

---

## 11. Residual / not checked

- **UNVERIFIED [likely, 55-80%]** — that CI on `ubuntu-latest` is green at State B. I measured the
  gates on Windows; the 4 known failures are Windows-only and CI runs Linux, but I did not push a
  branch. *Settling experiment:* open the Step-1 PR and read the `skill-dual-write` workflow
  result. Cheap, and it is the natural first step of execution anyway.
- **UNVERIFIED [likely, 55-80%]** — that no consumer outside the three scanned roots references a
  stub. The scan covered `REPO`, `~/.agents`, `~/.claude` (267,224 files); other repos under
  `~/source` were **not** scanned. *Settling experiment:* run `_scan_codex_stub_refs.py` with
  `ROOTS` extended to `~/source`.
- **NOT-CHECKED** — whether `release/platforms/windows/promptbridge-orchestration.toml` has any
  downstream consumer. Nothing in this repo reads it; a packaged release might. This is precisely
  why Step 3 is owner-gated.
- **NOT-CHECKED** — the correct replacement target for the `skill-router` eval expectation. I
  verified the current answer becomes invalid; I did not measure what the router *should* return.

---

## 12. Reproduction

Scripts written for this lane (kept — they follow the existing `_`-prefixed probe convention in
that directory):

- `~/.claude/harness-restore-20260806/_scan_codex_stub_refs.py` — estate scan; has a built-in
  detector control that exits 2 if the control token returns zero hits
- `~/.claude/harness-restore-20260806/_bucket_codex_refs.py` — role bucketing (use-vs-mention filter)
- `~/.claude/harness-restore-20260806/_topfiles_codex_refs.py` — distinct-file collapse
- `~/.claude/harness-restore-20260806/_focus_codex_refs.py` — REPO+LIVE focus
- outputs: `_codex_stub_refs.json`, `_codex_stub_routed.json`, `_codex_stub_files.json`,
  `_codex_stub_focus.json`

The State A/B/C experiment used a scratch clone at
`C:/Users/Prekzursil/AppData/Local/Temp/ast-stub-probe`, since deleted. To re-run: clone the repo
`--no-hardlinks`, apply each state, run the gates, delete the clone. Do not run it in the pinned
working tree — parallel agents share one git index.