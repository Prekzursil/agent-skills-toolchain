# CONSOLIDATED GEM DECISIONS — hunt of 27.08.2026

> Gem-hunt (discovery + tiered decision-queue, NOT a build) over the shared agent harness.
> Method: `gem-hunt` skill, 7 steps. 9 lens subagents fanned out after GROUND. Discovery only —
> nothing installed, nothing edited, no secrets touched.
> **Recovery note:** no prior `CONSOLIDATED-GEM-DECISIONS*.md` existed on disk — this file starts
> the 2026-08-27 hunt. Sibling outputs consumed: `openrouter-routing/SKILL.md` (Wave 1 state),
> `openrouter-complete-surface_2026-08-27.md` + `openrouter-free-models_2026-08-27.md` (via skill
> summary), `MAX-EFFORT-PLUGIN-DIAGNOSIS.md`, `MAX-EFFORT-PLUGIN-CLEANUP_2026-08-27.md`.
> **Not yet on disk** (siblings still writing — do not redo, consume when they land):
> `CURSOR-CUSTOMIZE-AUDIT_2026-08-27.md`, `HARNESS-AUDIT_2026-08-27.md`,
> `BASIC-MEMORY-RELIABILITY_2026-08-27.md`.

## GROUND — dedup-set used (measured this hunt)

- Hooks: ~40 families under `~/.claude/hooks`, two dispatch layers (`.agents/harness/dispatcher.py`
  on every event, 2–5s; `~/.claude/hooks/_dispatch/dispatch.py` on 4 events, 15–35s ceilings).
- Skills: **363** `SKILL.md` in `.agents/skills` SSOT; sessions list **538+** entries (materialized
  copies + drive-letter case variants). `skillListingBudgetFraction` = 0.04.
- MCP: `agents.json` 40 servers all `enabled:true` (Claude 40 / Codex 4 / Cursor 6 live + 31 parked).
  Claude denies 5 (markitdown, rdkit, serena, gitlab, meta-tool).
- Claude plugins enabled: codex, hookify, ralph-loop, remember, skill-creator, superpowers,
  claude-reflect, metaswarm, modern-web-guidance.
- Done waves in dedup: OpenRouter Wave 1 sidecar (skill + Codex named provider, free-slug smoke
  PASS, caps = user click); Cursor plugin enable-map 45 all-false incl. cache pins; Max Effort
  diagnosis + binary-search plan (restart pending); prior gems (open-loops, contraindication-registry,
  iatrogenics-gate, ACH, ACE, closed failure→gem→verify→retire loop).
- In-flight (dedup, not re-proposed): basic-memory watchdog, deep-research 42% fix, Cursor
  user-vs-project MCP duplicate scopes, OpenRouter paid bake-off (402-blocked).

## Lens agents (9)

| # | Lens | Finds | Highlight |
|---|------|-------|-----------|
| 1 | cross-domain borrows | 12 | spoliation adverse-inference, alarm stewardship, ANSI Z1.4 |
| 2 | frontier-harness | 10 | verified-resume contract, KV-cache hygiene, rubric verifiers |
| 3 | competitive-teardown | 10 (7 NATIVE) | cloud offload, automations, Bugbot/codex review |
| 4 | native-capability | 12 (all NATIVE) | Codex Windows sandbox+execpolicy, /usage rate_limits |
| 5 | user-domain tools | 15 | Ghidra BSim, Portal Legislativ API, Docling, ADMET-AI v2 |
| 6 | meta self-improvement | 8 | active-cap, birth-certificate template, gem leases |
| 7 | prune/organize | 10+1 | Stop-event 144s/35s oversubscription, skill-family merges |
| 8 | skills/MCPs-in-wild | 9 (0 new MCP) | Trail of Bits skills, K-Dense cherry-pick, LSP plugins |
| 9 | wildcard/gold-gem | 5 | airworthiness trio (MEL + tracer rounds + observational method) |

## Cross-lens convergence (highest-confidence finds)

- **MEL degraded-mode dispatch** — lens 1 #7 AND lens 9 #1 independently.
- **Bühlmann credibility / bonus-malus gate pricing** — lens 1 #10 AND lens 9 #3.
- **Skill lifecycle (cap + prune + curation)** — lens 2 #5, lens 6 #3/#7/#1, lens 7 #7/#8 (triple).
- **Per-hook efficacy telemetry** — lens 1 #4 (alarm stewardship) AND lens 6 #2 (ISR).
- **Verify-subagent-claims-against-disk** — lens 1 #1 (spoliation) AND lens 2 #6 (verified resume).
- **Cloud offload / scheduled automations** — lens 3 #1/#2 AND lens 4 #8.
- **Memory hygiene (decay + recall)** — lens 6 #6 AND lens 9 #4.

## VERIFY — load-bearing claims checked against real config

| Claim | Verdict |
|---|---|
| Stop event oversubscribed: 9 checks, timeouts sum 144s (8+8+25+30+10+25+18+10+10) under a 35s enforced ceiling, sequential collection, tail checks starved | **VERIFIED** — `_dispatch/manifest.json` `events.Stop`; its own `timeout_rationale` documents the starvation trade |
| "5 enabled-but-denied MCP registry entries" (lens 7 #4) | **CORRECTED** — only **markitdown** and **meta-tool** are both in `agents.json` (enabled:true) and Claude-denied; rdkit/serena/gitlab are denied but NOT registered. Prune scope = 2 entries, not 5 |
| PostToolUse spawns 3–4 Python processes per tool call | **PARTIALLY VERIFIED** — 2 always (shared dispatcher `.*` + local dispatch `.*`); compress-output only on Bash/browser matchers, per-edit-check only on edits |
| Skill listing case-duplication (C:\ vs c:\ variants) inflating 363→538+ | **VERIFIED** — this session's own skills block lists both drive-letter casings of `~/.claude/skills` paths |
| AgentBridge tombstone duplicated full-length in CLAUDE.md AND AGENTS.md; multiple "measured 2026-08-08" stale paragraphs | **VERIFIED** — both always-injected rules files carry the full marker-delimited block |
| goal-reinject already exists (so Cline focus-chain = fold, not new hook) | **VERIFIED** — `~/.claude/hooks/goal-reinject/` present |
| Cursor duplicate MCP scopes | **VERIFIED** — this session exposes both `user-basic-memory` and `project-0-Prekzursil-basic-memory` (same for playwright) |
| Claude Code native sandbox on Windows | **NEGATIVE finding** (lens 4) — not available natively on Windows; the Windows sandbox story is Codex's. Do not chase |
| Post-cutoff items (arXiv 26xx, Codex Windows sandbox, Cursor Automations, ToB/K-Dense repos) | **NOT re-verified locally** — graded lower-confidence by lenses; verify official docs at adoption time |

---

## TIER-0 — just-do-it (reversible, verified, next session)

1. **Registry/deny contradiction fix** — set `enabled:false` (or a `denied_by` field the merge
   respects) for **markitdown** and **meta-tool** in `agents.json`; re-run `sync_shared_state.ps1`.
   REC: ADOPT. value M × effort trivial. (Scope corrected by verify: 2 servers, not 5.)
2. **Stop-event rebalance** — demote `git-hygiene` (30s, already self-throttled to 1 scan/15min)
   and `wire-check` (25s) out of the Stop path (SessionStart-only or scheduled task); backup
   manifest first. Restores the starved tail gates (journey-coverage, dark-surface) that the
   manifest says matter most. REC: ADOPT. value H × effort L.
3. **Tombstone/stale-paragraph compression** — AgentBridge block full-length in ONE file, 3-line
   pointer in the other; move "measured 2026-08-08" forensics to basic-memory/guides. These are the
   most expensive tokens in the harness (paid every turn, every agent). REC: ADOPT. value H × effort L.
4. **KV-cache hygiene audit** — 5 rules (byte-stable prefix, append-only, deterministic JSON,
   mask-don't-remove tools, late dynamic content) as a short doc + one-time audit of every
   hook that injects context. Anthropic-docs-backed. REC: ADOPT. value H × effort very L.
5. **Native budget pacing restore** — wire `rate_limits.five_hour/seven_day.used_percentage` from
   statusline stdin JSON into the existing statusline script; use `/usage` attribution to see which
   plugins/MCP burn quota. Directly retires the "budget pacing NOT-CHECKED" hole in the rules.
   REC: ADOPT. value very H × effort L. (Verify exact JSON keys against current docs first.)
6. **Codex execpolicy rules** — `~/.codex/rules/default.rules`: `forbidden` for git writes,
   `allow` for read-only git — turns the AGENTS.md prose ban into enforced policy. REC: ADOPT.
   value H × effort L (experimental-feature caveat).
7. **Rubric-first judging** — adversarial-review/judge prompts gain a phase-1 "explore repo →
   write rubric artifact → then score" step (arXiv:2601.04171, ACL 2026). SKILL.md edit only.
   REC: ADOPT. value H × effort L.

## TOP-GEMS (build/enable wave candidates)

1. **Airworthiness trio** — **MEL registry** (`mel.md`: per-MCP/hook dispatch-with-inoperative
   policy + compensating procedure + rectification clock, read by mcp-liveness) + **tracer-round
   failure-finding** (scheduled synthetic contraband through guards in dry-run; a guard that
   doesn't trip files a MEL deferral) + **observational method** (plan-review gains monitored
   metrics + pre-committed trigger-action responses — the user's own professional epistemology).
   Cross-lens convergence; composes into one doctrine. REC: ADOPT as one wave. value very H ×
   effort M. GOLD.
2. **Cloud offload + scheduled automations** (NATIVE) — Codex Cloud environments per repo +
   `codex cloud exec`; Cursor Cloud Agents for browser-verified work; Codex app Automations /
   Task Scheduler + `codex exec` for nightly chores. Neutralizes the RAM ceiling — the box's #1
   constraint. REC: ADOPT (verify plan-tier gating live). value very H × effort L-M.
3. **Verified-resume + spoliation doctrine** — subagent completion claims are presumed false when
   promised artifacts are absent (adverse inference in tool-result-sentinel/subagent-lifecycle);
   checkpoints gain provenance (`disk-verified` vs `agent-claimed`) + revalidation-before-resume +
   idempotency keys. Targets the #1 documented failure mode. REC: ADOPT. value very H × effort M.
4. **Skill lifecycle system** (triple convergence) — (a) **birth-certificate template** (trigger,
   kill-criterion, rent metric, review date, why-not-NATIVE) enforced on every new gem/skill;
   (b) **bounded active-cap** (~50–80 surfaced skills; vault keeps everything, sync materializes
   the active tier); (c) **gem leases + rent-audit** at T+6 weeks via ledger lookup; (d) family
   merges from lens 7 (13 `source-command-*`, 5 `video-*`, 4 `voice-*`, 3 `grill-*` → 4 umbrellas)
   + archive tier for one-offs; (e) fix case-duplication in the skill enumerator (or list one
   materialized root per client). REC: ADOPT — this is the hunt's own anti-bloat obligation.
   value very H × effort M.
5. **Per-hook ISR telemetry + alarm stewardship** — per-hook compliance signatures over the ledger
   (fired vs acted-on vs token cost); monthly stewardship audit demotes/merges ignored alarms.
   Prerequisite substrate for leases and shadow-testing. REC: ADOPT (start with 5 noisiest hooks).
   value H × effort M.
6. **Codex Windows sandbox** — `windows.sandbox = "elevated"` in `~/.codex/config.toml`; the only
   OS-level isolation available on this box; may retire the git-write-delegation doctrine after
   testing. REC: TRIAL. value very H × effort L. (Post-cutoff feature — verify docs live.)
7. **Cursor hooks parity** — port 2–3 guards (beforeShellExecution guard, afterFileEdit logger,
   stop memory-capture) to `~/.cursor/hooks.json`; repo-level hooks also run in cloud agents.
   Closes the "guards vanish in Cursor" asymmetry. REC: ADOPT. value H × effort L-M.
8. **Eviction landmarks + structured eviction** — precompact hook emits ledger-addressed landmark
   lines for evicted spans; deterministic typed-episode eviction policy instead of blind
   summarization (Scroll arXiv:2608.21690, CWL arXiv:2606.11213). REC: ADOPT-later (one work
   unit on the ledger/precompact hooks). value H × effort M.

## STRONG-TECHNIQUES (doc/skill-text folds, adopt opportunistically)

- **ATC read-back/hear-back** — subagent restates goal/scope/DoD before execution (prompt template only). REC: ADOPT.
- **CCIR registry** — 3–5 per-task "wake the commander" facts; maps onto `[IMPORTANT]/[STATUS]/[FYI]`. REC: ADOPT.
- **Hearsay/provenance grading on agent-mail** — `VERIFIED-DIRECT`/`HEARSAY-n` tags; no irreversible action on hearsay. REC: ADOPT.
- **Cross-model disagreement mining** — `[DISAGREE]` marker + resolution logging feeds claude-reflect corpus + hunt targets. REC: ADOPT.
- **ANSI Z1.4 switching rules** — review depth normal/tightened/reduced from acceptance history. REC: TRIAL.
- **Western Electric brake** — run-rules on bench series before any failure→gem adoption (anti-tamper for the loop itself). REC: ADOPT.
- **Bühlmann/bonus-malus gate pricing** — credibility-weighted verification depth. REC: LATER (needs ISR substrate).
- **Failure-to-rescue bench metric** — score rescue-rate, not error-rate, from ledger. REC: TRIAL.
- **NEWS2 aggregate early-warning** — cross-signal vitals score in the dispatcher; any single red escalates. REC: LATER.
- **Hysteresis/anti-oscillation** — reversal detection over ledger; second flip triggers stop-and-think. REC: LATER.
- **Memory decay + lot-recall** — `confidence/last_verified/expires` frontmatter + recall walk for falsified facts' descendants. REC: TRIAL (coordinate with basic-memory watchdog sibling).
- **EPSS doctrine** — orchestrator never ingests raw subagent transcripts; structured result contracts. REC: ADOPT (doc edit).
- **Focus-chain cadence** — fold plan/todo reinjection every N turns into the existing goal-reinject hook. REC: ADOPT.
- **Experience-compression tiers** — /self-reflect decides note→skill→rule promotion/demotion per learning. REC: ADOPT.
- **Bugbot / `codex review` on PRs** + **/rewind + targeted summarize + /branch doctrine** + **Cursor `/debug`** — native usage doctrine lines in CLAUDE.md. REC: ADOPT.
- **Shadow-mode champion/challenger for hook edits** — REC: LATER (reserve for instruction-injecting hooks).
- **Scheduled hunt on change budget** — monthly, ≤K adoptions, one-in-one-out, trend-gated. REC: ADOPT as the cadence for all of the above.

## TOOLING / user-domain queue

| Item | Domain | REC | Note |
|---|---|---|---|
| Ghidra **BSim** skill | RE | ADOPT | NATIVE (ships in `support/`), file-backed H2; solves game-patch offset loss |
| **Portal Legislativ** SOAP skill | civil-eng | ADOPT | free keyless official API; watchlist + diff; no ro-eli-mcp server |
| **Docling** skill | doc *(row truncated when pass 2 was interrupted — completed in the ADDENDUM tooling table below)* | | |

---
---

# ADDENDUM — recovery pass 3 (27.08.2026, later same day)

> **Why an addendum:** pass 2 wrote everything above and was then cut off mid-row in the TOOLING
> table. Pass 3 (this section) **continues idempotently** — nothing above is rewritten or deleted.
> Its job: (a) fold the five sibling reports that were "not yet on disk" when pass 2 wrote its
> header and have since landed, (b) re-verify the load-bearing TIER-0 claims against real config
> paths, (c) finish the truncated tooling queue, (d) add the sections pass 2 never reached
> (planned-unbuilt, skip list, next wave, steer options).
>
> **Content-scope guard honored:** the offensive-security / reverse-engineering / exploit families in
> the vault (hexstrike*, cyberstrike*, malware*, crypto-ctf, game-re*, frida*, x64dbg, windbg*, angr,
> radare2, ghidra*, ida*, binary-ninja*, cheat-engine*, swfoc-re*, security-bounty*, llm-security,
> gtfobins, lolbin, hacktricks*, secsearch, volatility, qiling, peutils, capa, bindiff, binexport,
> imhex, ret-sync, trail-of-bits-re, dump-to-signature, re-*) were **not opened, not read, and not
> web-searched** this pass. Prune-lens accounting: **RE/security family — ~45 skills, present,
> out of audit scope.** The Ghidra BSim row inherited from pass 2's table is left as written and was
> **not** re-researched. Today's value is in harness / productivity / research / media / docs.

## Sibling outputs folded this pass (consumed, not redone)

| File | What pass 3 took from it |
|---|---|
| `HARNESS-AUDIT_2026-08-27.md` | `harness-audit.js` **does not exist** anywhere under `.agents\scripts` or `source\*\scripts` → the 12-category score is legitimately `NOT-CHECKED`, and "port a deterministic scorer" is a real unbuilt gap. 17 orphan `local.json.*.tmp` already moved to backups. MCP-scope duplication root cause = home-as-workspace, **document-don't-edit** (deleting a pointer kills both scopes). |
| `BASIC-MEMORY-RELIABILITY_2026-08-27.md` | A full supervision stack **already existed since June 2026** (`BasicMemory-HTTP-MCP` 5-min + `BasicMemory-Watchdog` 3-min + vault backup). Pass 3 correction to the standing rule: the health probe is **`GET http://127.0.0.1:8765/mcp` → HTTP 406 = HEALTHY** (not `/health`, which is why sibling probes reported NOT-CHECKED). Watchdog now does a real HTTP probe with a two-strike rule; restarts mirror to `.agents\logs\basic-memory-supervisor.log` (**verified present**). Root cause of the morning red was a **stale Cursor client**, not a dead server. |
| `CURSOR-CUSTOMIZE-AUDIT_2026-08-27.md` + `CURSOR-MARKETPLACE-VISITED_2026-08-27.md` | Visited-set locked (25 Bolt @ rev `edb0999…` + 181 cursor-public). No `~\.cursor\rules\` and no `~\.cursor\commands\` exist → **zero Cursor-side rule drift surface**. Confirms the 5-gem port list from `common` and the full SKIP wall. |
| `local-models-audit_2026-08-27.md` | Ollama = single on-demand runtime (`keep_alive` is the RAM brake); LM Studio manual-only; HF hub-only ($0.10/mo hosted inference is not a lane). **No new always-on daemon** — this now also constrains every gem below: nothing in this hunt may add a resident process. |
| `RECOVERED-THREADS_2026-08-27.md` | Eight cross-session principles that gate the gems: mechanism-only for phenibut, fail-closed gates (a budget-aborted gate is **not** green), never overwrite (`_v2`), no commit without explicit user decision, provenance over assertion, don't invent model tags, one Paper A. **"Fail-closed" is the doctrine the verified-resume gem must inherit.** |
| `openrouter-complete-surface` + `openrouter-free-models` | Sidecar slice is correct and unchanged. Free lane is live (**17 `:free` chat slugs**, 20 zero-price rows; 20 req/min, 1000 req/day on this key since `is_free_tier=false`). Credits **slightly overdrawn** (~319.4 vs ~319.79) → paid T0 402s, free path 200s. Confirms: no OpenRouter MCP, no BYOK, no LiteLLM. |

## VERIFY-2 — pass-2 TIER-0 re-checked against real config paths

Four of the seven TIER-0 items changed status. **Two were already built.** This is the most
important output of pass 3: it prevents a build wave from re-implementing existing capability.

| Pass-2 item | Pass-3 verdict on disk | Corrected action |
|---|---|---|
| #1 Registry/deny contradiction (markitdown, meta-tool) | **CONFIRMED** — `agents.json` L640 `markitdown` and L1031 `meta-tool` both `"enabled": true` with `"targets": ["claude"]`, while Claude denies both. Scope is exactly **2** entries (pass-2's own correction of "5" holds). | Unchanged: ADOPT. |
| #2 Stop-event rebalance | **CONFIRMED** — `~\.claude\hooks\_dispatch\manifest.json` L72–74: `"Stop"` with `"settings_timeout": 35` over a 9-check list whose individual timeouts sum far past it. | Unchanged: ADOPT. |
| #3 Tombstone / stale-paragraph compression | **CONFIRMED + ENLARGED** — the AgentBridge block is still full-length in **both** always-injected rules files, and VERIFY-2 found a second class of stale prose: the budget-pacing paragraphs assert a capability that **is already wired** (next row). | ADOPT, and fold the budget-pacing prose fix into the same edit. |
| #4 KV-cache hygiene audit | Not a config claim (doc + audit). Untouched. | Unchanged: ADOPT. |
| #5 Native budget pacing restore | **ALREADY BUILT — reclassify.** `~\.claude\statusline-command.sh` L44–45 already parses `.rate_limits.five_hour.used_percentage`, `.rate_limits.five_hour.resets_at`, and `.rate_limits.seven_day.used_percentage` from statusline stdin (alongside `context_window.used_percentage` and `cost.total_cost_usd`). The statusline is live in `settings.json` L583–588 (30s refresh). | **DOWNGRADE to a doc fix.** The gap is not wiring — it is that `CLAUDE.md` and `AGENTS.md` still say pacing is "not currently computable / NOT-CHECKED". Delete that prose and point at the statusline fields. Effort: trivial. This is the cheapest correctness win in the hunt. |
| #6 Codex execpolicy rules | **PARTIALLY BUILT — refine.** `~\.codex\rules\default.rules` **exists** (plus `dart/`, `rules/`, `web/` subdirs) and already forbids `git push --force/-f/--force-with-lease`, `git reset --hard`, `git clean -fdx/-xdf`, `diskpart`, `format`, `reg delete`, `bcdedit /delete`, `cipher /w`, and reads of `.env`/`.ssh`/`.aws`. It does **not** cover the routine git-write set that `AGENTS.md` bans in prose (`commit`, `push`, `pull`, `fetch`, `checkout -b`, `branch`, `merge`, `rebase`, `cherry-pick`, `tag`, `stash`). | ADOPT the **delta only** — append the routine git-write prefix rules + an explicit `allow` for read-only git (`status`, `log`, `diff`, `show`, `rev-parse`). Do not rewrite the file. |
| #7 Rubric-first judging | Prompt/SKILL text only. Untouched. | Unchanged: ADOPT. |

### Two pass-2 top-gems, now verified live (both changed)

- **Cursor hooks parity → UPGRADE to top-1 of this pass.** `~\.cursor\hooks.json` is **ABSENT**
  (verified). Official docs (`cursor.com/docs/hooks`) show a far larger surface than pass 2 assumed:
  `sessionStart`/`sessionEnd`, `preToolUse`/`postToolUse`/`postToolUseFailure`,
  **`subagentStart`/`subagentStop`**, `beforeShellExecution`/`afterShellExecution`,
  `beforeMCPExecution`/`afterMCPExecution`, `beforeReadFile`/`afterFileEdit`, `beforeSubmitPrompt`,
  `preCompact`, `stop`, `afterAgentResponse`/`afterAgentThought`. Config is
  `{"version": 1, "hooks": {...}}` at `~\.cursor\hooks.json` (user) or `.cursor\hooks.json`
  (project). **Critical asymmetry:** only `beforeShellExecution` and `beforeMCPExecution` honour a
  `permission` field (`allow`/`ask`/`deny`) — everything else is **observe-only and cannot veto**.
  `failClosed: true` makes a hook failure block instead of fail-open. **Why this is now the top gem:**
  the harness has ~40 Claude hook families and **zero** on the Cursor side, and Cursor is where the
  work is actually happening today — every guard silently evaporates in this very session. Bonus:
  `subagentStart`/`subagentStop` is the first real instrument for the standing
  "subagents appear canceled / cut off mid-work" failure mode.
- **Codex Windows sandbox → correction: already set, but on the weak mode.**
  `~\.codex\config.toml` L990–991 already has `[windows] sandbox = "unelevated"` (with
  `approval_policy = "on-request"`, `sandbox_mode = "workspace-write"` at L6–7). Official docs call
  **`elevated` the recommended value** and `unelevated` the fallback "only if you don't have
  administrator permissions or if elevated setup fails". **But** there is a documented live failure
  mode where elevated setup breaks the helper so badly that even reading `AGENTS.md` fails
  (`helper_unknown_error`), and the community fix is reverting to `unelevated`. → **REC: TRIAL with a
  pre-agreed revert**, not a blind adopt. One-line change, one-line rollback, test with a read of a
  project file before trusting it.

## TOOLING queue — completed (the table pass 2 was cut off inside)

| Item | Domain | Grounding (this pass) | REC |
|---|---|---|---|
| **Docling** | civil-eng doc production | DOCX backend preserves headings/lists/tables incl. merged cells, hyperlinks, comments, headers/footers, and converts Office Math (OMML) **to LaTeX**; XLSX backend maps sheet→page, auto-detects table clusters with a `gap_tolerance` knob, extracts **calculated values, not formulas**. Limits: DrawingML charts need LibreOffice; track-changes and page layout are not preserved. | **ADOPT as an INGEST skill — explicitly NOT a generator.** Sharp correction to pass 2's row: Docling reads documents into `DoclingDocument` and exports md/html/json/DocTags. Miky's output contract (formal `.docx`/`.xlsx` in Romanian) still needs `python-docx`/`openpyxl`. Use Docling for reading norms, standards, and contractor submittals; never for producing the deliverable. |
| **ADMET-AI v2** | pharma / phenibut | v**2.0.1** (2026-02-22) on PyPI; Chemprop **v2** models, RDKit fingerprints **removed** (faster, fewer deps), retrained on TDC PyTDC 1.1.15 + DrugBank v5.1.14, adds PAINS / BRENK / NIH alerts; 2.0.1 specifically moved checkpoints MPS→CPU to fix Linux/CUDA. | **ADOPT** for the phenibut project, with two hard notes: (a) **v2 predictions do not match v1** — any ADMET number already in the phenibut record from v1 is not comparable and must be re-run or labelled with its version; (b) stays inside the **mechanism-only** principle — no dosing/clinical framing. Pin the exact version in every receipt. |
| **tbcml** | BC-modding | The **GitHub repo is ARCHIVED**; canonical home moved to **Codeberg** (`codeberg.org/fieryhenry/tbcml`, active commits to 2026-08-12). PyPI `1.1.0` is stale (2023) → source install is the recommended path. Non-RE surface: apk download/extract, server-file + event-data download, pack decrypt/encrypt, game-data parsing, asset edits, BCU pack import, repack/sign. | **ADOPT as a pointer fix (cheap, prevents a dead end).** The existing `bc-*` / `battlecats-*` skills should point at Codeberg and at a source install, not the archived GitHub + stale PyPI. Scope kept to the data/asset side; the frida/smali/libnative-patching half is RE-family and out of scope this pass. |
| **Portal Legislativ SOAP** | civil-eng | Inherited from pass 2 (free, keyless, official; watchlist + diff pattern). Not re-researched. | ADOPT (unchanged). |
| **Ghidra BSim** | RE | Inherited from pass 2. **Out of audit scope this pass** — not re-verified, not re-researched. | Left as pass 2 wrote it. |
| **remotion** | media pipeline | From the Cursor-public catalog; programmatic video, fits the existing `video-*` / `caption-burn` family. | LATER (on demand). |
| **Academic literature access** | research | **Not a gap — CLOSED.** Institutional access via e-nformation.ro (Anelis Plus) is already provisioned: env credentials, a working cookie jar at `.agents\secrets\enformation-cookies.txt`, and the `institutional-literature-access` skill. | **NO BUILD.** Reuse the existing session material rather than rediscovering access. |
| **`harness-audit-runner`** | harness | `harness-audit.js` confirmed absent everywhere searched → today's scorecard is honestly `NOT-CHECKED`. | ADOPT-later: port/author the scorer into `.agents\scripts\`, wire as a post-sync check in `sync_shared_state.ps1`. |
| **`fly-deploy`** | deploy | Only genuine deploy-target gap (Vercel/Netlify/Cloudflare/Render all covered by vault skills). | LATER, low priority. |
| **`deep-research-triage`** | research | 90 uses / **42% success** — worst popular skill. Hypothesis stands: long multi-hop runs outlive their context/tool budget on a RAM-starved box, so partial runs log as failures. | ADOPT-later: instrument failure modes per run before touching the skill's logic. Do **not** rewrite the skill on a guess. |

## PLANNED-UNBUILT (carried, explicitly not started)

1. Deterministic harness scorer (`harness-audit.js` port) → unblocks numeric audits instead of `NOT-CHECKED`.
2. `deep-research` instrumentation → then a fix, in that order.
3. Eviction landmarks / structured typed-episode eviction on the precompact hook (pass-2 gem 8).
4. Per-hook ISR telemetry substrate → prerequisite for gem leases, Bühlmann gate pricing, and shadow-mode hook testing. Nothing credibility-weighted can be built before this exists.
5. Skill family merges (13 `source-command-*`, 5 `video-*`, 4 `voice-*`, 3 `grill-*` → 4 umbrellas) + archive tier.
6. Port the 5 `common` gems (token-diet, conversation-kickoff, anti-slop, polish-pr, auto-convert-to-markdown) into the vault as vault-owned copies; plugin stays `false`.
7. Paid OpenRouter bake-off — **blocked on credits (402), not on a decision.** Free lane already smoke-PASSed.

## SKIP — anti-overfit wall (restated, with the reason each time)

| Skipped | Why |
|---|---|
| Second orchestrator (orchestrate, compound-engineering, merge-agent-handler, agent-compatibility) | metaswarm **is** the orchestrator; a second one splits the gate story in half. |
| LangGraph / Temporal | Same reason plus a resident-runtime cost this box cannot pay. |
| Vector DB (pinecone, turbopuffer, mem0, paradedb) | basic-memory is the store and is now supervised; a vector layer adds a daemon and a second truth. |
| Sentry #2 | A vault `sentry` skill already exists; duplicate observability earns nothing. |
| Trained critic (coderabbit, tabnine, spottercode, meticulous, subtext-verify) | Adversarial-review gates already exist and are free; a trained critic is an opinion with a subscription. |
| Scrape-MCP dupes (apify, bright-data, browse, browser-use, exa, parallel, tavily, firecrawl-plugin) | The live firecrawl MCP plus vault skills already cover retrieval. |
| OpenRouter MCP / Cursor BYOK / Claude `ANTHROPIC_BASE_URL` / LiteLLM | OpenRouter stays a **spend-capped CLI/Codex sidecar**. Confirmed again by the surface audit. |
| HF hosted inference as a routing lane | $0.10/month free tier is a demo allowance, not a lane; OpenRouter `:free` costs 0 local RAM. |
| LM Studio as a second service / any new always-on daemon | RAM is the binding constraint. One on-demand runtime (Ollama), `keep_alive` as the brake. |
| 14B+ local models on GPU; the 20.55 GB 35B as a routine lane | 6141 MiB VRAM → GPU-full weights ≤ 5117 MiB. The 35B is a deliberate-offline artifact only. |
| Editing `.cursor\mcp.json` to kill the duplicate MCP scopes | Root cause is **home-as-workspace**; the file is read twice. Deleting a pointer removes the server from *both* scopes. The fix is user behavior (open project roots, not `C:\Users\Prekzursil`) or UI toggles — **not** config. |
| All Bolt-internal packs (boltable + 22 team packs) | No Bolt infra, no Jira, no n8n in this estate. |
| ~120 vendor-SaaS Cursor connectors | No accounts, no stack overlap; trivially adoptable later if a project ever demands one. |
| Re-auditing the RE/security skill family | Content scope guard for this hunt. ~45 skills, present, out of scope. |

## Suggested next build wave (ordered, and sized to finish)

**Wave A — the free corrections (one sitting, all reversible, no new processes).**
Registry/deny fix for the 2 servers → Stop-event rebalance (backup the manifest first) → tombstone
compression **including the budget-pacing prose that VERIFY-2 proved is already wired** → execpolicy
git-write delta. Every item is a small edit to a file that already exists, and two of them delete
false claims from the always-injected rules — which is the highest token-per-turn return available.

**Wave B — Cursor hooks parity (the real gem).** Create `~\.cursor\hooks.json` with three hooks:
a `beforeShellExecution` guard (the only place a veto is possible — mirror the destructive-command
set already in `default.rules`, `failClosed: true`), an `afterFileEdit` logger, and
`subagentStart`/`subagentStop` lifecycle logging to finally get evidence on the stalled-subagent
failure mode. Small, self-contained, and it closes the asymmetry that every guard is absent in the
editor the work actually happens in.

**Wave C — verified-resume / fail-closed doctrine.** Inherit the `RECOVERED-THREADS` principle
directly: a subagent completion claim is presumed false when its promised artifact is absent, and a
budget-aborted gate is never green. Checkpoints gain `disk-verified` vs `agent-claimed` provenance.
This hunt is its own proof case — three passes died and the only reason nothing was lost is that the
artifacts were on disk to be re-read.

**Wave D — the airworthiness trio** (MEL registry + tracer-round failure-finding + observational
method), then the skill-lifecycle system. Both need Wave C's substrate and the ISR telemetry to be
worth anything; starting them earlier produces ceremony without measurement.

**Deliberately not in any wave:** Codex `elevated` sandbox stays a **TRIAL** with a scripted revert
to `unelevated`, because a failed elevated setup can break Codex's ability to read files at all —
and Codex is the execution rail.