# RULERESEARCH — grounding lane artifact

STATUS: MEASURED. Lane = RULERESEARCH (grounding). No production code written; no rule edited.

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.
(That sentence is the skeleton sentinel required by the write-as-you-go mandate; it is retained
verbatim. The sections below are measured — see COVERAGE for what is not.)

COVERAGE
- MEASURED: frontmatter classification (3 trees, 88+78+88 files), always-on AND lazy token
  totals, repo-vs-live-vs-agent-self drift, the 8 CI rule-test modules (executed, 167 pass),
  the bootstrap and sync-rules deploy deltas (simulated), 7 contradictions verified against the
  source they describe, and — observed live in-session with a working negative control — that
  user-scope `paths:` rules DO load lazily on a matching touch (§4.1).
- UNMEASURED: Anthropic-tokenizer counts (all totals are cl100k_base estimates, ±10-20%, see §2);
  lazy-injection trigger granularity (§4.1 residual); non-`rules/` instruction surfaces (skills,
  hooks, commands) — other lanes own those.

Probes (re-runnable, read-only, ruff-clean): `docs/rule-audit/_probe_rule_inventory.py`,
`_probe_threeway.py`, `_probe_semantics_disagree.py`, `_probe_alwayson_diff.py`,
`_probe_alwayson_tokens.py`, `_probe_bootstrap_delta.py`, `_probe_lazy_observed.py`.
Raw: `docs/rule-audit/_rule-inventory.json`. Nothing under `rules/`, `agent-self/`, `AGENTS.md`
or `~/.claude/` was written — this lane reports, it does not edit (verified: `git status --short
-- rules/ AGENTS.md agent-self/` returned empty; the live rules tree was opened read-only).

Probe verification status, stated honestly: every probe above was executed at least once and the
numbers in this document are its verbatim output. A final batch re-run of all seven was cut off
by machine contention (sibling lanes), so "all seven reproduce back-to-back" is UNVERIFIED;
individual reproduction is not. `uvx ruff@0.15.17 check docs/rule-audit/` → `All checks passed!`

---

## 1. Inventory: always-on vs lazy (MEASURED)

Rule loading is **first-party Claude Code**, not a harness hook: no file under `hooks/` loads
`~/.claude/rules`, and the live `settings.json` contains no `rules` key (grepped for the token
only; the file holds live credentials and was never read whole).

Measured frontmatter, three trees:

| tree | path | files | no-frontmatter (always-on) | always-on tok | all-rules tok |
|---|---|---|---|---|---|
| repo | `rules/` | 88 | 8 | 17,069 | 62,302 |
| agent-self | `agent-self/config/rules/` | 78 | 4 | 1,201 | 38,008 |
| live | `~/.claude/rules/` | 88 | 8 | **15,141** | 54,426 |

The always-on 8 (identical set in repo and live, all under `common/`): `agents.md`,
`bash-hud-and-terminal-emit.md`, `cross-vendor-dispatch.md`, `fan-out-contract.md`,
`harness-vcs-hygiene.md`, `single-signal-verification.md`, `stale-megapr-reconcile.md`,
`windows-shell.md`.

**Corroboration (two mechanically independent signals).** Signal A: measured frontmatter absence
in `~/.claude/rules/`. Signal B: this agent's own turn-0 system prompt, which lists exactly those
8 rule files by absolute path and no others — 8/8 match, 0 false positives across 88 candidates.

**Discriminating control (rule 3c).** H1 "frontmatter presence gates turn-0 injection" vs H2
"pattern breadth gates it". `common/owner-ops-authorization.md` carries `paths: ["**/*"]` — the
broadest possible glob. Under H2 it would be injected at turn 0. It is **not** in this agent's
context. The observation separates the hypotheses; H1 survives. `rules/README.md` carries the
deliberate never-load sentinel `paths: ["**/*.__never_load__"]`, independent documentary evidence
that the authors hold H1 too.

Confidence: **almost certain (90-99%)** that the 8 no-frontmatter files are the turn-0 set.

## 2. Always-on token cost (MEASURED, with a declared estimator caveat)

**15,141 tokens per turn** from `~/.claude/rules/` alone (cl100k_base). Plus the unconditional
memory files in this agent's prompt: `~/.claude/CLAUDE.md` 2,422 and `~/.claude/AGENTS.md` 2,707
(the former `@AGENTS.md`-imports the latter), and the project `~/CLAUDE.md` 2,780.
Always-on instruction floor = **23,050 tokens** before a single tool call.

Per-file, measured (`_probe_alwayson_tokens.py`), live vs repo — note the repo copies are the
ones carrying the §4 corrections, so landing them costs +1,928 tok/turn:

| file | live | repo |
|---|---|---|
| `windows-shell.md` | 4,560 | 5,097 |
| `single-signal-verification.md` | 3,634 | 3,634 |
| `fan-out-contract.md` | 2,632 | 2,773 |
| `bash-hud-and-terminal-emit.md` | 1,951 | 1,966 |
| `cross-vendor-dispatch.md` | 1,126 | 1,652 |
| `stale-megapr-reconcile.md` | 600 | 600 |
| `harness-vcs-hygiene.md` | 566 | 837 |
| `agents.md` | 72 | 510 |
| **total** | **15,141** | **17,069** |

**The realistic cost is not the always-on floor — it is the floor plus the lazy set.** Measured
in this session (§4.1): touching any `.py` file in this repo additionally injects 16 path-scoped
rules worth **8,520 tok**, of which `owner-ops-authorization.md` alone is **2,664** and, being
scoped `paths: ["**/*"]`, is de-facto always-on one turn late. Working total once code is touched:

| layer | tok |
|---|---|
| always-on rules (8) | 15,141 |
| `~/.claude/CLAUDE.md` | 2,422 |
| `~/.claude/AGENTS.md` (imported by the above) | 2,707 |
| `~/CLAUDE.md` (home project instructions) | 2,780 |
| **floor subtotal** | **23,050** |
| lazy rules injected on a `.py` touch (16) | 8,520 |
| repo `CLAUDE.md` | 377 |
| **working total** | **31,947** |

CAVEAT, inline: cl100k_base is OpenAI's tokenizer, not Anthropic's; treat these as ±10-20%
estimates, not receipts. The authoritative instrument is Claude Code's own `/context`, which
prints "Memory files" with a per-file token count; running it would convert this table from
estimate to receipt. It has not been run.

## 3. Drift: three trees, no gate covers the deployed one (MEASURED)

- **repo vs live: 28 of 88 files differ**, including 6 of the 8 always-on rules
  (`single-signal-verification.md` and `stale-megapr-reconcile.md` are byte-identical).
- **repo vs agent-self: 9 differ, 10 absent** — agent-self is missing 7 of the 8 always-on rules.
- **13 files have OPPOSITE load semantics across trees** (`_probe_semantics_disagree.py`).

The direction matters. `rules/` is generally AHEAD (it carries corrections live has never
received). Three files are LIVE-ahead — `owner-ops-authorization.md` (live +1,001 B),
`performance.md` (+234), `security.md` (+169) — i.e. live-authored rule work never reconciled
into git, which `harness-vcs-hygiene.md` itself forbids.

**The gates are all green anyway.** All 8 rule CI modules execute clean: `167 passed in 5.02s`
(`ci/tests/test_rules_{integrity,scope,governance,doc_coherence,doc_contracts,common_contracts,`
`selector_inheritance,hook_examples}.py`). They pass because **every one of them reads `rules/`
and `agent-self/config/rules/` — none reads `~/.claude/rules/`.** The parity gates are also
narrowly scoped and honestly so: `test_agent_self_mirror_is_byte_identical` is parametrized over
`MIRRORED_DOCS`, 5 paths; `test_bundle_mirror_matches_canonical` over `BUNDLE_MIRRORS_PINNED`,
2 paths. Zero of the 9 measured repo↔agent-self divergences fall in those 7 paths. This is a
scope gap, not a broken gate — the docstring says outright that a global invariant "would be a
false invariant".

**Deploy paths, simulated (`_probe_bootstrap_delta.py`), both read-only:**

- `pwsh scripts/sync-rules.ps1` → live always-on 15,141 → **17,069 tok (+1,928)**, 6 always-on
  files rewritten. It is **non-recursive** (`Get-ChildItem $srcRoot -File -Filter *.md`), so the
  10 divergent files outside `rules/common/` — `README.md`, `dart/patterns.md`, `java/testing.md`,
  `perl/patterns.md`, `php/coding-style.md`, `python/security.md`, `rust/hooks.md`,
  `typescript/{coding-style,hooks}.md`, `web/hooks.md` — are unreachable by any tool in the repo.
- `pwsh agent-self/bootstrap.ps1` (`:44`, `Copy-Item config\* $ClaudeHome -Recurse -Force`) →
  **silently PROMOTES 3 rules from lazy to always-on**: `git-workflow.md` (+157 tok),
  `hooks.md` (+349), `security.md` (+185), because the agent-self copies lack the `paths:`
  frontmatter their live counterparts carry. Always-on count 8 → 11. It also *downgrades*
  `agents.md` content. This is the inverse-intuition frontmatter trap firing in the promote
  direction, unpoliced, as a side effect of a bootstrap.

## 4. Contradictions (each verified against the source it describes)

### 4.1 `single-signal-verification.md:28` — CONFIRMED in both clauses (settled in-session)
The always-on rule states: *"the 8 files with NO frontmatter are exactly the 8 injected at turn 0;
the 12 WITH `paths:` load lazily on a matching touch."*
- First clause: **CONFIRMED** (§1).
- Second clause: **CONFIRMED by direct observation.** Mid-audit, after this lane wrote and edited
  `.py` files under `docs/rule-audit/`, Claude Code 2.1.228 injected 16 path-scoped user-level
  rules as a first-party system-reminder: 11 from `~/.claude/rules/common/` and all 5 of
  `~/.claude/rules/python/`, total **8,520 tok** (`_probe_lazy_observed.py`).
- **Negative control fired correctly (both-states).** Exactly one `common/` lazy rule did *not*
  arrive: `common/hooks.md`, whose globs are `['**/hooks/**', '**/settings*.json', '**/.claude/**']`
  — none of which match `docs/rule-audit/*.py`. Every one of the 16 that *did* arrive carries
  `**/*.py` or `**/*`. 16/16 matching injected, 1/1 non-matching withheld: the selector is
  genuinely evaluated per-glob, not "load everything after the first touch".
- **I am revising a conclusion I had drafted the other way, because of new evidence.** On the
  strength of three upstream reports — [#16853](https://github.com/anthropics/claude-code/issues/16853)
  (**still OPEN**, 20 reactions, "this never worked", v2.1.1),
  [#21858](https://github.com/anthropics/claude-code/issues/21858) (v2.1.25, Windows) and
  [#22170](https://github.com/anthropics/claude-code/issues/22170) (v2.1.27), which say
  `paths:` rules at `~/.claude/rules/` never load — I had this at "uncertain (20-55%) that the
  rule's clause is wrong". **It does not reproduce on 2.1.228.** Note both closed issues were
  closed *by their own reporters* with `closed_by_pull_requests.total_count = 0`, so the
  literature gave no fix signal either way; only the direct measurement settled it. Lesson for
  this audit: stale upstream issues nearly produced a false "the rules are all dead" alarm.
  Confidence the clause is CORRECT as written: **almost certain (90-99%)**.
- Residual, disclosed inline: "the 12" is common-only; there are **80** `paths:`-scoped rules
  tree-wide. That is a scoping imprecision in the sentence, not an error, and does not block.
- Residual, UNVERIFIED: the exact trigger granularity (first matching touch vs. batched vs.
  re-injected per turn) was not measured — the injection was observed once. Settling experiment:
  `/context` before and after a single `Read` of one `.py` file in a fresh session.

### 4.2 `harness-vcs-hygiene.md` — the deployed copy teaches a data-loss command (CONFIRMED)
Live (always-on, in this agent's context right now) says run `sync-from-live.ps1` "`-Report json`
to see drift". Measured at `scripts/sync-from-live.ps1:477`:
`$writeAllowed = (-not $WhatIf -and -not $Drift)` — `$Report` is absent from that expression, so
bare `-Report json` selects mode `sync` and `Copy-Item -Force` overwrites repo files with live
bytes. The **repo** copy already carries the correction ("`-Report` selects the OUTPUT FORMAT, not
read-only mode. Bare `-Report json` WRITES") and `test_rule_does_not_advertise_bare_report_as_`
`inspection` gates it — but only in `rules/`. The wrong text is what ships. Severity: this lane's
own spawn prompt had to hard-ban `sync-from-live.ps1` outright, which is the workaround for a rule
that is wrong in the only copy anyone reads.

### 4.3 `cross-vendor-dispatch.md §1` vs `AGENTS.md §4a` — live rule-vs-rule collision (CONFIRMED)
Both are in this agent's turn-0 context simultaneously. `AGENTS.md §4a`: any op >60s, *expressly
including "long Codex generations" and "multi-agent dispatch"*, MUST run under `longrun` with
`run_in_background`/`Monitor`, "never a blocking foreground call". Live
`cross-vendor-dispatch.md §1`: "NEVER `--background`, `&`, `nohup`, `spawn(detached)`, or
`run_in_background` for a dispatch whose result a barrier is waiting on." The same live rule's §7
then says such a dispatch "must … run under `longrun` (AGENTS.md §4a)" — so §1 contradicts §7 of
its own document as well. The repo copy fixes exactly this: it retitles §1 "MUST be JOINED" and
opens with an explicit "Reconciliation with AGENTS.md §4a — read this first." Again: fixed in
`rules/`, absent from live.

### 4.4 `agent-self/config/AGENTS.md` reverses the §9 credential non-negotiable (CONFIRMED)
The repo's versioned copy of the behavior contract is missing the entire live §9 opening bullet
("**NEVER remove, rotate, revoke, regenerate, unset or otherwise MODIFY any API key or token**"),
and its §9b ends *"→ rotate, don't just delete"* where live says *"per §9 you do not rotate it
yourself … leave the rotation to the owner."* The repo copy therefore **instructs the opposite of
the standing owner instruction** on the one rule that is never overridable. `agent-self/bootstrap.ps1:44`
force-copies `config/*` over `~/.claude`, so this is a deploy source, not an inert snapshot.
Nothing gates AGENTS.md parity (the mirror gates cover 5 + 2 unrelated paths). Blast radius:
one `pwsh agent-self/bootstrap.ps1` on any machine.

### 4.5 `scripts/sync-rules.ps1` docstring is refuted by the current tree (CONFIRMED)
Its `.DESCRIPTION` claims "the live rules dir is a SUPERSET of this repo's rules/common (it also
holds rules this repo does not version -- windows-shell.md, static-analyzer.md, coding-style.md,
...)". Measured: all three named files **are** versioned in `rules/common/`, and the repo↔live
name sets are identical (only-in-repo 0, only-in-live 0). The premise the non-destructive design
rests on no longer holds.

### 4.6 `commands/context-budget.md` delegates to a skill that does not exist (CONFIRMED)
`:24` — "Run the **context-budget** skill (`skills/context-budget/SKILL.md`) … The skill handles
all scanning logic, token estimation, issue detection, and report formatting." Probed 5 roots:
`skills/`, `.agents/skills/`, `skills-claude-only/`, `~/.claude/skills/`, `~/.agents/skills/` —
**ABSENT in all five**; a tree-wide `find` returns only the three command-file copies. The command
is invocable (it is in this agent's command list) and is a no-op shell. Meanwhile
`ci/tests/test_rules_doc_contracts.py:222` gates its 200K-denominator prose — a green gate on the
documentation of an unimplemented feature. Consequence for this audit: **there is no working
prior-art tool for always-on token accounting.**

### 4.7 `rules/README.md` structure block is stale (CONFIRMED, low severity)
It lists `common/` as 8 files; there are 20. Seven of the eight always-on rules are absent from
the diagram. Note the README correctly documents `paths:` semantics at `:127-131` — an earlier
draft of this report claimed it did not; that was my error, corrected on re-read.

## 5. Prior art in this repo — do NOT rebuild

| asset | what it already does | gap |
|---|---|---|
| `ci/tests/test_rules_*.py` (8 modules, ~1,990 lines, 167 tests, green) | executable rule contracts incl. both-states controls, detector controls, use-vs-mention fence-stripping, selector inheritance | reads `rules/` + `agent-self/` only; **never reads `~/.claude/rules/`** |
| `test_agent_self_mirror_is_byte_identical` / `test_bundle_mirror_matches_canonical` | repo↔agent-self byte parity | 7 pinned paths; 9 divergences all outside them |
| `scripts/sync-rules.ps1` | repo→live for `rules/common/*.md` | non-recursive; cannot reach 10 divergent language-dir files; stale premise (§4.5) |
| `agent-self/bootstrap.ps1` | full config→`~/.claude` deploy | force-copy, no prune, silently flips load semantics (§3) |
| `scripts/sync-from-live.ps1` | live→repo reconcile | `-Report json` writes (§4.2); banned by this lane's prompt |
| `commands/rules-distill.md`, `platform/workflows/rules-distill-sweep.json` | distil skills→rules | authoring, not auditing |
| `commands/context-budget.md` | *intended* token accounting | implementation absent (§4.6) |
| `hooks/git-hygiene/check.py` | Stop-hook live-vs-repo harness drift nudge | advisory, throttled 15 min; did not surface these 28 |

## 6. External SOTA

- Claude Code memory model — rules without `paths:` load at launch at CLAUDE.md priority; rules
  with `paths:` are conditional. `/context` and `/memory` are the first-party instruments that
  list loaded memory files with token counts.
  https://code.claude.com/docs/en/memory
- User-scope `paths:` defect cluster (fetched via GitHub API, not recalled) —
  **does NOT reproduce on 2.1.228, see §4.1; retained so the next reader does not re-alarm**:
  https://github.com/anthropics/claude-code/issues/16853 (OPEN, v2.1.1),
  https://github.com/anthropics/claude-code/issues/21858 (self-closed, stale, v2.1.25),
  https://github.com/anthropics/claude-code/issues/22170 (self-closed, duplicate, v2.1.27).
- Community write-ups corroborating the load model and the user-scope workaround (project-level
  rules, or symlink user→project): https://konadu.dev/how-claude-code-loads-claude-rules

## 7. Ranked plan (for the build lane)

1. **Fix `agent-self/config/AGENTS.md` §9/§9b (§4.4).** Highest severity: a security
   non-negotiable is *inverted* in a live deploy source, and `bootstrap.ps1:44` force-copies it
   over `~/.claude`. Restore the live §9 "NEVER … rotate … any API key or token" bullet and the
   "leave the rotation to the owner" §9b wording. Then add an AGENTS.md parity gate — nothing
   currently covers it. Propose-only from this lane (AGENTS.md is propose-not-rewrite scope).
2. **Deploy the corrected `rules/common` to live**: `pwsh scripts/sync-rules.ps1 -WhatIf`, read
   the list, then the real run. This is what lands §4.2 (the `-Report json` data-loss text) and
   §4.3 (the §1-vs-§4a dispatch contradiction) where agents actually read them. Costs +1,928
   tok/turn — worth it. Do **NOT** use `sync-from-live.ps1` (that is the tool §4.2 is about).
3. **Extend the CI gates to the deployed surface.** One test comparing `rules/common/*.md` to
   `~/.claude/rules/common/*.md`, `pytest.skip` when `~/.claude` is absent (CI has none). This is
   the single missing gate that let 28 files drift while 167 tests stayed green. Give it a
   both-states control: a synthetic divergence must make it fail.
4. **Add a load-semantics gate**: no rule may change frontmatter-presence relative to its sibling
   trees without an explicit allowlist entry. Catches the bootstrap promote-by-accident (§3) —
   the trap that silently turns 3 lazy rules always-on.
5. **Run `/context` once and paste the Memory-files block in.** Converts §2 from cl100k estimate
   to first-party receipt and settles the §4.1 granularity residual. Cheap; no longer a blocker
   now that §4.1 is settled by direct observation.
6. **Make `sync-rules.ps1` recursive** (or document that language dirs have no bridge at all) and
   correct its refuted superset docstring (§4.5). 10 divergent files are currently unreachable.
7. **Reconcile the 3 live-ahead files** into git (`owner-ops-authorization.md`, `performance.md`,
   `security.md`). Read BOTH sides first — live holds content the repo has never seen; this is a
   merge, not an overwrite.
8. **Either implement `skills/context-budget/` or retire the command** (§4.6). If (5) shows
   `/context` is sufficient, retiring is cheaper than building.
9. **Refresh `rules/README.md`'s structure diagram** (§4.7). Cosmetic; do last.

Explicitly NOT recommended: (a) re-scoping any rule's frontmatter on the strength of the upstream
issue cluster — it does not reproduce here (§4.1); (b) treating the 167 green tests as coverage of
the deployed tree; (c) any consolidation of the three rule trees before step 3 exists, since
without a gate the merge cannot be shown not to have lost content.
