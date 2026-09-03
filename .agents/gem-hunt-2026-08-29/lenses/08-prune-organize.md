# Lens 08 — prune / organize audit of the shared agent harness (29.08.2026)

> **Scope:** verified residual duplication, stale docs, dead/dormant code, latency & rent, missing
> tests, consolidation opportunities. **Read-only pass — nothing was deleted, edited, disabled or
> moved.** Every number below was measured on this box today unless the row says otherwise.
> **Anti-redo:** the 27.08 hunt's lens-7 finds that are already CLOSED (Stop-event rebalance,
> markitdown/meta-tool deny-contradiction, tombstone compression, budget-pacing prose, Cursor hooks
> absence) are **not** re-proposed; each is confirmed closed in the "Already closed" table.

---

## GROUND — what this lens actually measured

| Surface | Measured 29.08.2026 | Anchor given | Note |
|---|---|---|---|
| Skill vault `~/.agents/skills` | **380** `SKILL.md` / **376** top-level dirs | 380 | matches |
| `~/.claude/skills` (materialized) | **380** `SKILL.md` | — | in sync with vault |
| `~/.codex/skills` | **8** `SKILL.md` | — | see F-13 |
| Hook families `~/.claude/hooks` | **71** dirs (excl. `_dispatch`, `_shared`, `_golden`, `_fleet-backups`, caches) | ~40 | anchor understates by ~31 |
| Hook-tree files | **822** files (incl. `.pytest_cache`/`.ruff_cache`) | 469 | anchor is a filtered count |
| `_dispatch/manifest.json` events | 4 (SessionStart 8, Stop 7, PostToolUse 5, PreToolUse 7 checks) | consolidated | confirmed |
| `settings.json` PreToolUse entries | **13** separate command entries | — | see F-11 |
| Append-only state + logs | **~242 MB** (`terminal.jsonl` 147.4 MB + `.agents/logs` 95 MB) | — | see F-01 |

**Dispatcher concurrency, read from source (not assumed):** `_dispatch/dispatch.py:349-372` starts
one daemon thread per check and joins them against a **shared clock started once**
(`start = time.monotonic()`, `remaining = budget - (now - start)`). Each check therefore has an
**absolute deadline of `start + its own timeout`**, and total wall time is bounded by
`max(timeout)`, not by the sum. Current bounds: SessionStart ≤ 30 s (git-hygiene) under a 35 s
ceiling; Stop ≤ 25 s (stub-ledger) under 35 s. **The Stop oversubscription is genuinely fixed.**

---

## Already closed since 27.08 — confirmed, not re-proposed

| 27.08 item | Verification today | Verdict |
|---|---|---|
| Stop-event 144 s/35 s oversubscription | `manifest.json:97-165` — Stop is 7 checks, max timeout 25 s; wire-check + git-hygiene moved to SessionStart (`manifest.json:71-95`) | **CLOSED** |
| markitdown / meta-tool enabled-but-denied | stated closed in the brief; not re-measured this lens | **CLOSED (inherited)** |
| Tombstone compression | `CLAUDE.md` carries a 5-line `multi-ai-mingle` pointer; the full AgentBridge block lives once, in `AGENTS.md` | **CLOSED** |
| "Budget pacing NOT-CHECKED" stale prose | `CLAUDE.md` now states pacing is measurable live via `statusline-command.sh` | **CLOSED** |
| `~/.cursor/hooks.json` ABSENT | now present, 6 hooks across 5 events, `_readme` dated 2026-08-27/28 | **CLOSED** (but see F-01) |
| Cursor-side guard asymmetry | `hooks.json:26-31` `beforeShellExecution` → `shell-guard.ps1`, estate-deny active | **CLOSED** |

---

## FINDINGS

### F-01 — Observe-mode telemetry is unrotated, unredacted, and is now the largest artifact on the harness (242 MB in ~2 days)

**Evidence**
- `~/.agents/state/harness/terminal.jsonl` = **147,414,437 B**, last write 29-Aug 22:14 (today).
- `~/.agents/logs/cursor-afterfileedit.jsonl` = **94,918,180 B**, created 27-Aug 08:38, still growing.
  `.agents/logs` total = **95 MB across 7 files**.
- Producer has no cap and no rotation: `.agents/scripts/cursor-hooks/cursor-hook-log.ps1:31-37` —
  `AppendAllText($logPath, $line + NewLine, $utf8)`, no size check, no roll, no retention.
- Registered at `~/.cursor/hooks.json:51-56` (`afterFileEdit`, timeout 10).
- **The payload embeds verbatim file content.** Tail sample line:
  `{"ts":"2026-08-29T19:04:42.093Z","hook_ms":167,"payload":{…"file_path":"…electronics_engineering_security_proofs.py","edits":[{"old_string":"","new_string":"import importlib"}…`
  Measured over the last 300 lines: **mean 5,002 B/line, max 96,011 B/line**.
- Per-edit latency, same 300-line sample: **median 224 ms, mean 289 ms, p90 515 ms, max 1,513 ms**.
  First-ever line records `hook_ms: 6781`.
- `~/.agents/harness/redaction.py` exists and is **not** used by this logger.
- Growth rate ≈ 47 MB/day for `afterfileedit` alone → ~1.4 GB/month unattended.

**Impact** Three distinct costs. (a) Disk/IO on a box whose standing constraint is memory pressure.
(b) The `hooks.json:6` FLIP CRITERIA require analysing these files ("median `hook_ms`",
"count MISSING log entries") — that analysis is due ~03.09 and will have to parse a
100 MB+ JSONL, which is exactly the kind of job that dies on this box, so the flip decision is at
risk of never being made. (c) Every edited file's contents are written in plaintext to a local log
with no redaction pass; `.agents/.gitignore:15` (`logs/`) prevents a repo leak but not a local one.

**Safe validation** `Get-Item` the two paths for size; `Get-Content -Tail 300` and regex `hook_ms`
(this is what produced the numbers above — it does not read the whole file). To prove the
redaction gap, grep one recent line for `new_string` — no read of the full file needed.

**Value × effort** Very High × Low (a size-capped roll in `cursor-hook-log.ps1` + reuse of
`redaction.py`; both are additive, neither removes the evidence stream the flip criteria need).
**Confidence: HIGH** — direct file sizes, direct source read, sampled payloads.

---

### F-02 — Ten dispatcher-compatible hook handlers remain censused as unwired, and the plan docs still call five of them "LIVE+WIRED"

**Evidence**
- `~/.claude/hooks/_dispatch/test_wiring.py:523-540` — `KNOWN_UNREGISTERED_HANDLERS`:
  - PreToolUse: `goal-reinject/reinject`, `compchem-preflight`, `strong-tool-nudge`,
    `contraindication`, `iatrogenics`
  - PostToolUse: `anti-degen/fingerprint`, `memory-guard/scan`, `fresh-verify/trigger`,
    `orphan-commit`, `semantic-router/observe`
- `test_wiring.py:659` states in its own words: *"Ten names remain allowlisted and genuinely absent."*
- Cross-checked against the live manifest: none of the ten appear in
  `manifest.json` `events.PreToolUse.checks` (mcp-liveness/pretool, edit-checkpoints,
  bg-registry/register, memory-spool/spool, dup-guard, monitor-autolaunch,
  codex-monitor-autolaunch) or `events.PostToolUse.checks` (memory-spool/flush_check,
  tool-result-sentinel, claim-guard/ledger-write, stub-ledger/record, edit-validate/record).
- A grep of `~/.claude/settings.json` for all ten names returns **0 matches** — they are on no
  event surface at all.
- **Stale doc:** `~/.claude/OPEN-THREADS.md:55` — *"LIVE+WIRED: B1 hooks · … PB2 verification
  layer"*. `AGENTIC-PERFECTION-PLAN.md:4-5` defines the B1 set as
  *"mcp-liveness, claim-guard, truth-verify, fresh-verify, orphan-commit, anti-degen,
  goal-reinject, edit-checkpoints"*. Measured: **5 of those 8** (truth-verify, fresh-verify,
  orphan-commit, anti-degen, goal-reinject) are wired nowhere.

**Impact** This is the GREEN-not-LIVE defect class the manifest itself documents twice
(`manifest.json:163` dark-surface, `manifest.json:222` edit-validate/record) — a gate that reads as
shipped and fires never. The honest part is that the census is *deliberate* and strict-xfailed, so
the test suite is not lying; the doc is. Two follow-on costs: the always-injected plan docs assert
protection that does not exist, and each of the ten still needs the same individual adjudication
`test_wiring.py:726-727` explicitly says it has **not** performed.

**Safe validation** `pytest ~/.claude/hooks/_dispatch/test_wiring.py -q` — the ten cases report as
`xfailed`, not passed; wiring any one of them turns its case `XPASS(strict)` red, which is the
designed signal. No runtime change needed to confirm.

**Value × effort** High × Medium (ten separate adjudications; several are exit-2 gates that must
**not** enter the inject-only dispatcher — `dispatch.py:53-58`). The **doc correction is High × Trivial**
and should not wait for the wiring work.
**Confidence: HIGH** for the census and the doc contradiction; **MEDIUM** on whether each of the ten
*should* be wired (that is the adjudication the test defers).

---

### F-03 — Two commands document gates and files that do not exist

**Evidence**
- `~/.claude/commands/orchestrate.md:90` — *"`hooks/subagent-lifecycle` Stop hook validates one
  subagent's output shape"*. `subagent-lifecycle` appears in **neither** `settings.json` **nor**
  `manifest.json`; the Stop event's 7 checks are bg-registry/done_marker, heartbeat, honest-signal,
  stub-ledger/report, forge/todo-surfacer, journey-coverage, dark-surface (`manifest.json:97-165`).
- `~/.claude/commands/harness-audit.md:67` — *"Add prompt/tool preflight security guards in
  `hooks/hooks.json`"*. `~/.claude/hooks/hooks.json` **does not exist**; only
  `hooks.json.bak-schemafix-20260723` (11,832 B) survives. `manifest.json:250` also still names
  `hooks.json` as a registration surface to check.
- `~/.claude/commands/harness-audit.md:17` invokes `node scripts/harness-audit.js <scope>` as a
  **bare relative path**, so it only resolves when cwd happens to be the root that holds it.

**Impact** `orchestrate.md` is the worse of the two: an orchestration command tells the reader a
subagent-output gate is running, which is precisely the failure mode the estate is trying to
instrument. `harness-audit` points at a registration surface that was removed and at a script by a
path that will not resolve from `~`.

**Safe validation** `Test-Path ~/.claude/hooks/hooks.json` → False. Grep `settings.json` +
`manifest.json` for `subagent-lifecycle` → 0 hits.

**Value × effort** Medium-High × Trivial (three doc lines).
**Confidence: HIGH.**

*Sub-note (unresolved):* a count-only probe over `~/.agents`, `~/.claude` and the repo's `scripts/`
found **exactly one** `harness-audit.js` (the 27.08 audit recorded zero), but the follow-up search
to pin its path stalled under memory pressure and was killed. **`NOT-CHECKED`** — do not treat the
27.08 "does not exist anywhere" line as current, and do not treat "it exists" as actionable until
the path is pinned.

---

### F-04 — 62 backup/`.orig` files sit inside the live hook and harness trees; the detector that finds them runs every session and nothing is ever closed

**Evidence** (excluding the designated `backups/`, `deploy-backups/`, `_fleet-backups/` dirs)

- 62 files matching `*.bak*` / `*.orig` / `*-OLD.md` under `~/.agents` + `~/.claude/hooks`.
- Oldest: `~/.agents/scripts/sync_shared_state.ps1.bak-20260401-212229` (01-Apr, ~5 months).
- Doubly-suffixed cruft — a backup of a backup:
  `~/.claude/hooks/calibrated-silence/calibrated_silence.py.bak-floor-20260704.bak-fleet-20260713`,
  `~/.claude/hooks/_dispatch/manifest.json.20260712-193022.bak.bak-fleet-20260713`.
- Four superseded manifests in the dispatcher dir alone (`manifest.json.bak-20260714-012512`,
  `…bak-20260727-100902`, `…bak-q7q8-20260807-161637`, plus the doubled one above).
- Heaviest: `~/.agents/state/harness/recall-index.json.bak-*` — **4 copies, ~5.9 MB**, three of
  them written **today** (05:30, 11:29, 17:28) alongside a live `recall-index.json` of 1,663,091 B.
  The refresh path keeps every backup it has ever made.
- **The detector already exists and already runs.** `~/.claude/hooks/git-hygiene/check.py:12`
  targets *"editor/agent backup cruft (`*.bak-*`, `*.orig`, `*-OLD.md`)"*, `:191-195` lists the
  globs, and it is wired at SessionStart with a 30 s budget (`manifest.json:83-95`), measured
  range **11.8–32.7 s** per its own `timeout_rationale`.

**Impact** This is rent, not just mess. The harness pays **12–33 s of the SessionStart budget**
every session for a scan whose output has produced no cleanup, and `manifest.json:95` concedes that
runs above 30 s lose the check's output entirely. That is the alarm-stewardship problem the 27.08
hunt filed as `PLANNED-UNBUILT #4` (per-hook ISR telemetry) — here it is with a hard number attached.
Secondary risk: `.bak` copies of *hook modules* sit next to the live ones, so a future glob-based
loader or a careless import can execute a stale gate.

**Safe validation** Re-run the same `Get-ChildItem -Include *.orig,*.bak-*,*-OLD.md` with the
backup dirs excluded; compare the list against one SessionStart's git-hygiene injection to confirm
the overlap (that comparison is itself the ISR telemetry starter).

**Value × effort** High × Low for the sweep (move to `~/.agents/trash/`, never delete — house rule),
Medium × Low for adding a retain-N rule to whatever writes `recall-index.json.bak-refresh-*`.
**Confidence: HIGH.**

---

### F-05 — The shared harness's own deploy-integrity record is stale, so it can no longer distinguish an authorized edit from tampering

**Evidence**
- `~/.agents/harness/installed.json:16` records `dispatcher.py` =
  `81079cf230034c6f955785f5ebed6d4dcfa0b3f366a0cb04fb0577e38186532a`.
  **Live SHA-256 = `c772b6d98e3e9a4858bd57343044f44f6727f2e4824ebbb65fba0ed699653558`.**
- `installed.json:19` records `ledger.py` =
  `6aab4d7340824c7f31d43e2f765b1f8d42bfa37ddb49ac647a4ad42f03ea7c6a`.
  **Live SHA-256 = `c477576af9f0865562be36d7012d6748f115ece0e1efac0013d71fd597b5855d`.**
- `installed.json:6-9` claims `deployed_at: 2026-08-19T10:42:02+00:00`,
  `source_commit: 53c37c6c…` — both files have drifted since.
- Same directory holds `dispatcher.py.orig` (22,362 B) and
  `ledger.py.bak-goalshort-20260724-084544` (48,490 B) — the pre-edit copies, unmanaged.

**Impact** `installed.json` is the only artifact that could answer "is the deployed harness the one
we shipped?", and today it answers wrong for at least 2 of its 12 code files. This is the exact
"hash-drift tripwire" the perfection plan asks for at
`AGENTIC-PERFECTION-PLAN.md:72` (*"single-canonical + copy-sync + hash-drift tripwire"*) — the
manifest exists, the comparison does not.

**Safe validation** `Get-FileHash` every path in `installed.json.files` and diff against the
recorded map; read-only, ~12 files, seconds. That loop **is** the missing tripwire.

**Value × effort** High × Low.
**Confidence: HIGH** — two independent hash comparisons.

---

### F-06 — The skill vault is a three-way drift: 19 skills never reached the repo's platform tree, 2 are unversioned entirely, and a `.ruff_cache` lives inside the vault root

**Evidence**

| Tree | Dirs | Missing vs live |
|---|---|---|
| `~/.agents/skills` (SSOT, live) | 376 | — |
| repo `skills/` (platform layout) | 356 | **19 skills + `.ruff_cache`** |
| repo `.agents/skills` (deploy mirror) | 373 | **2 skills + `.ruff_cache`** |

- Missing from repo `skills/`: `c4-architecture`, `claim-verify-gate`, `cli-anything`,
  `clone-website`, `codex-audit`, `codex-brainstorm`, `codex-coordinate`, `codex-curate`,
  `codex-discuss`, `codex-fix`, `codex-governance`, `codex-review`, `codex-triage`, `dr-plan`,
  `hosted-model-agents`, `openrouter-routing`, `qdx-rush`, `qwen-space-tool-api`, `visual-explainer`.
- Missing from **both** repo trees (i.e. exist only on the live box):
  **`hosted-model-agents`, `qwen-space-tool-api`**.
- Direction is one-way: `Compare-Object` finds **0** dirs present in a repo tree but absent live —
  so this is a capture gap, not a divergence in the other direction.
- `git-hygiene/check.py:225` declares the invariant explicitly:
  `repo_skill_trees = ("skills", ".agents/skills", "skills-claude-only")`, and `:758` pairs
  `~/.agents/skills` → `repo/.agents/skills` → `skills` for dual-write comparison.
- `~/.agents/skills/.ruff_cache` exists (`Test-Path` → True): a linter cache inside the vault root,
  which any naive `Get-ChildItem -Directory` enumerator counts as a skill (it did, in this audit).

**Impact** `hosted-model-agents` and `qwen-space-tool-api` are one disk incident from gone —
and `hosted-model-agents` is named in `CLAUDE.md`'s always-injected `hosted-model-agents` block, so
a rule references a skill that exists in no backup. The 19-skill gap in `skills/` means the repo's
platform layout is not a faithful export, which matters the moment anyone installs from it.

**Safe validation** Re-run the three `Compare-Object` passes on directory names only (no content
read). To confirm the two-tree gap: `Test-Path repo/skills/hosted-model-agents` and
`Test-Path repo/.agents/skills/hosted-model-agents` → both False.

**Value × effort** High × Low (a capture commit; the dual-write script already knows the mapping).
**Confidence: HIGH.**

---

### F-07 — `skills-claude-only/` duplicates five skills that also live in the vault, and two of the duplicates have diverged

**Evidence**

| Skill | in `skills-claude-only` | in `.agents/skills` | identical? |
|---|---|---|---|
| `ralph-hats` | 2,826 B | 2,826 B | **yes** |
| `ralph-loop` | 1,967 B | 1,967 B | **yes** |
| `ralph-orchestrator-setup` | 2,107 B | 2,107 B | **yes** |
| `qdx-rush` | 12,128 B | 12,075 B | **no** |
| `microsoft-foundry` | 11,686 B | 25,038 B | **no — 2.1× apart** |

(SHA-256 compared on `SKILL.md`; `microsoft-foundry`, `ralph-hats`, `ralph-loop`,
`ralph-orchestrator-setup` are additionally present in repo `skills/`, i.e. **three** copies.)

**Impact** The three byte-identical pairs are harmless storage duplication. The two divergent pairs
are the dangerous kind: two same-named skills with different bodies in one repo, and nothing
records which is authoritative. `microsoft-foundry` differs by 13 KB — that is not a formatting
drift, that is a different document.

**Safe validation** Hash-compare the five `SKILL.md` pairs (done above). To pick a winner without
editing: compare each repo copy against the **live** `~/.agents/skills/<name>/SKILL.md` — the live
vault is the SSOT by `AGENTS.md` ("Shared skills live in `.agents\skills\`").

**Value × effort** Medium-High × Low (3 dedupes + 2 reconciliations).
**Confidence: HIGH.**

---

### F-08 — The `.agents` root-doc version-control gap that commit `fbc70f22` closed on 27.08 reopened within two days; 91% of the root corpus by bytes is now unversioned

**Evidence**
- Repo HEAD = `fbc70f22` (27-Aug) — *"chore(sync): capture .agents root audit docs into SSOT
  (close root-doc version-control gap)"*.
- Live `~/.agents/*.md`: **54 files, 2,628 KB**. Repo `.agents/*.md`: **16 files, 239 KB**.
  → **38 files / ~2,389 KB (91% by bytes) uncaptured.**
- The 38 include every 28–29.08 artifact: 11 `COUNCIL-*_2026-08-28`, 12 `PERPLEXITY-*_2026-08-29`
  (the blueprint alone is 671 KB), `DARIA-REMOTE-AI-UX-SPEC_2026-08-29`,
  `LONG-HORIZON-*`, `RESEARCH-*`, `AUTOMATION-SUITE-DECISIONS_2026-08-29`, plus two **standing
  contracts**: `memory-contract.md` and `memory-map.md`, both of which `AGENTS.md` cites as SSOT
  ("follow `C:\Users\Prekzursil\.agents\memory-contract.md` (SSOT — do not fork a second copy)").
- Organization half: `~/.agents/docs/` exists but contains only `incidents/` and `plans/`, while 54
  `.md` sit loose at the root, ~1.4 MB of which is a single `PERPLEXITY-*` research series.

**Impact** A one-shot capture cannot hold a corpus that grows ~19 docs/2 days. Two contracts the
always-injected rules point at (`memory-contract.md`, `memory-map.md`) have **no** version history.
Root sprawl also makes the `git-hygiene` scan and every future audit more expensive than it needs
to be.

**Safe validation** `Compare-Object` on the two `.md` name sets (done); `Test-Path` the repo copies
of `memory-contract.md` / `memory-map.md` → both False.

**Value × effort** High × Low for the capture; Medium × Low for filing the `PERPLEXITY-*` series
under a dated subfolder. The durable fix is Medium × Medium: make capture a step in
`sync_shared_state.ps1` rather than a remembered chore — which is also what would give
`git-hygiene`'s existing finding somewhere to land (see F-04).
**Confidence: HIGH.**

---

### F-09 — The skill-family merge backlog is not just unbuilt, it regressed: `source-command-*` grew 13 → 23 since 27.08

**Evidence** (top-level dirs in `~/.agents/skills`, grouped by first token)

| Family | 27.08 (lens 7) | **29.08 measured** | Δ |
|---|---|---|---|
| `source-command-*` | 13 | **23** | **+10** |
| `codex-*` | not flagged | **18** | — |
| `security-*` | — | 7 | — |
| `design-*` | — | 6 | — |
| `video-*` | 5 | **5** | 0 |
| `voice-*` | 4 | **4** | 0 |
| `grill-*` | 3 | **3** | 0 |

`CONSOLIDATED-GEM-DECISIONS_2026-08-27.md:259` carries this as `PLANNED-UNBUILT #5`
(*"13 `source-command-*`, 5 `video-*`, 4 `voice-*`, 3 `grill-*` → 4 umbrellas"*). The three small
families are unchanged; the one flagged as largest nearly doubled.

**Impact** `source-command-*` is 6% of the vault and, by name, is imported slash-commands
re-expressed as skills — a family that grows by import rather than by design is the clearest
candidate for an umbrella + archive tier. `codex-*` at **18** is now the second-largest family and
was never flagged; it should be sized before, not after, an umbrella is designed.

**Safe validation** The grouping command above is read-only. Before any merge, check each family
member's inbound references (`Grep` for the skill name across `~/.agents/skills` and
`~/.claude/commands`) — a skill referenced by a command is not a free merge.

**Value × effort** Medium-High × Medium. **Recommend sequencing behind F-06**: do not merge
families while 19 skills are missing from the repo tree, or the merge will be performed against an
incomplete export.
**Confidence: HIGH** on the counts, **MEDIUM** on merge-ability (contents not read this pass).

---

### F-10 — `codex-monitor-autolaunch` is registered on two surfaces at once with complementary matchers

**Evidence**
- `manifest.json:293-301` — `PreToolUse` check `codex-monitor-autolaunch` →
  `codex-monitor-autolaunch/check.py`, matcher `Bash|PowerShell`, timeout 6, `side_effect: launch`.
- `settings.json:310-314` — a **standalone** `PreToolUse` entry running the **same script**,
  matcher `mcp__codex__codex`.
- The matchers are disjoint, so there is no double-fire; but the same hook now has two owners and
  two timeout regimes.
- Adjacent overlap: `manifest.json:283-291` runs `monitor-autolaunch/check.py` on
  `Task|Workflow|mcp__codex__codex` — so an `mcp__codex__codex` call fires *both* a dispatcher
  launch-check and a standalone launch-check in separate processes.

**Impact** Small latency cost (one extra Python spawn per Codex call) and a real maintenance
hazard: a future matcher edit on one surface silently changes coverage without touching the other.
`test_wiring.py:840` (`test_prepost_manifest_scripts_have_no_standalone_duplicates`) exists to
catch exactly this shape — worth confirming why this pair passes it (likely because the matchers
differ), because that is the loophole.

**Safe validation** Widen the manifest matcher to `Bash|PowerShell|mcp__codex__codex` in a scratch
copy and run `pytest test_wiring.py -q`; the standalone-duplicate test will then tell you directly
whether it considers the settings.json entry redundant.

**Value × effort** Medium × Low.
**Confidence: HIGH** on the double registration; **MEDIUM** on whether folding is safe (the
standalone entry may exist because the dispatcher is inject-only and this check has a `launch`
side effect that wants its own process).

---

### F-11 — A single `Bash` tool call still spawns ~13 Python processes, against a documented ~6-hook ceiling

**Evidence** — entries in `settings.json` whose matcher admits `Bash`:

| Phase | Entries | Lines |
|---|---|---|
| PreToolUse | **9** — harness dispatcher, `no-force-push`, `estate-deny-guard`, `test-tamper-guard`, `cmd-rewrite/inject-nopager`, `ulysses/enforce`, `loop-recovery/handler`, `deny-credential-reads`, `_dispatch/dispatch.py` | 178, 189, 200, 211, 222, 233, 277, 288, 299 |
| PostToolUse | **4** — harness dispatcher, `cmd-rewrite/compress-output`, `_dispatch/dispatch.py`, `selection-events/emitter` | 349, 360, 386, 406 |

`settings.json` declares **13 PreToolUse entries total** (178–310). Two full dispatch layers run on
most events: `~/.agents/harness/dispatcher.py` (15 event registrations) **and**
`~/.claude/hooks/_dispatch/dispatch.py` (4 events).
`AGENTIC-PERFECTION-PLAN.md:11-13` sets the rule this violates: *"stay under the ~6-active-hook
latency ceiling — CONSOLIDATE checks … never one always-on hook per check."*
`OPEN-THREADS.md:57` files it as `CONSOLIDATION-DEBT (do FIRST)`.

**Honest constraint — most of these cannot be folded.** `test_wiring.py:167-209`
(`REQUIRED_STANDALONE_HANDLERS`) documents that 8 of the 9 PreToolUse Bash-matching hooks use an
exit-2 / `updatedInput` / permission contract *"which the current inject-only dispatcher cannot
preserve"*, and `dispatch.py:53-58` confirms the dispatcher cannot honour exit 2. So the real
consolidation surface here is **not** the guard set.

**The two tractable items:**
1. `selection-events/emitter.py` is registered on **both** `UserPromptSubmit` (`:169`) and
   `PostToolUse` `.*` (`:410`) — an always-on emitter on every single tool result.
2. The two dispatch layers are never merged; the shared-harness dispatcher runs on 15 events
   including several (`TaskCreated`, `TaskCompleted`, `TeammateIdle`, `ConfigChange`,
   `PermissionRequest`, `PermissionDenied`, `PostCompact`, `SubagentStart`) that no `_dispatch`
   manifest event covers.

**Impact** On a box where "simple PowerShell commands can take minutes", 13 interpreter starts per
Bash call is the single largest fixed per-turn tax in the harness — and unlike F-01 it cannot be
fixed by a retention policy.

**Safe validation** Measure before proposing anything: time 20 trivial `Bash` calls with
`HOOK_DISPATCH=off` vs default (`dispatch.py:152` honours the env opt-out, fail-open), and read
`hook_ms` from `.agents/logs/cursor-shell-guard.jsonl` for the Cursor-side equivalent. **Do not**
fold a guard to buy latency — the house rule forbids trading capability for speed; present the
measured cost and let the owner choose.

**Value × effort** High value × High effort, and **partially blocked by design**. Recommend it stay
a *measurement* item this wave, not a build item.
**Confidence: HIGH** on the counts, **HIGH** on the standalone constraint (source-cited),
**LOW** on any latency estimate — not measured this pass.

---

### F-12 — Store B (a fully redundant second git object store, 3 checkouts) is still on disk 20 days after being verified redundant

**Evidence**
- `REPO-TOPOLOGY.md:55-97` (measured 09.08): `~/source/ast-patch167/.git` is a **separate full
  clone** — 724 commits, 128 refs, 3 checkouts — whose `origin/main` is pinned 39+ commits stale,
  and whose 25 unique commits were content-verified to hold **zero** files absent from main.
  Conclusion as written: *"store B is fully redundant. Retiring it loses nothing."*
- `REPO-TOPOLOGY.md:120-128` files retirement as *"NOT yet executed"*.
- Measured today: `ast-patch167` **exists**, `_verify_M04_tree` **exists**, `_verify_M13` **exists**.
- Live footgun documented at `REPO-TOPOLOGY.md:108-110`: *"Never measure a baseline in store B."*

**Impact** Any agent that resolves a repo from cwd (the failure mode recorded at
`REPO-TOPOLOGY.md:115-118` — five agents pointed at the wrong repository on 08.08) can still land
in a 39-commit-stale baseline. That is the cost, more than the disk.

**Safe validation** Before anything: `git -C ~/source/ast-patch167 status --porcelain -uall` to
triage the 1 uncommitted file `REPO-TOPOLOGY.md:97-100` flags as **UNVERIFIED**, and diff it
against `origin/main:<path>`. Retirement is owner-invoked and out of scope for this lens.

**Value × effort** Medium × Low-Medium. **Confidence: MEDIUM** — existence measured today,
redundancy inherited from the 09.08 measurement and **not** re-derived this pass.

---

### F-13 — Test coverage gaps: 18 of 71 hook families have no tests, and three of those are live-wired

**Evidence** — `test_*.py` present per hook family (recursive):

- **With tests: 53 families** (`event-ledger` 5, `stub-ledger` 5, `git-hygiene` 4,
  `per-edit-check` 4, `wire-check` 4, `cmd-rewrite` 3, `deny-credential-reads` 3, `memory-spool` 3,
  `open-loops` 3, `semantic-router` 3, …).
- **Without tests: 18** — `beads`, `compchem-preflight`, `compute-confidence-gate`, `figma-mirror`,
  `fresh-verify`, `harness-trim`, `local-tui-reminder`, `mcp-canonical-sync`, `mcp-defaults`,
  `mcp-userscope-sync`, `orphan-commit`, `precompact-basicmemory`, `profile-capture`,
  `sonar-secrets`, `stopfailure-notify`, `strong-tool-nudge`, `tool-preflight`,
  `workflow-monitor-autolaunch`.
- **Of those 18, three are wired and running today:**
  `local-tui-reminder` (`settings.json:142`, SessionStart),
  `profile-capture` (`settings.json:547`, Stop),
  `stopfailure-notify` (`settings.json:107`, Notification).
- Several of the untested-and-unwired ones are **not** dead code — they are on-demand CLI utilities
  invoked from skills/scripts, e.g. `mcp-userscope-sync/promote-mcp-userscope.ps1`
  (`.agents/scripts/apply-mcp-health-fixes.ps1:81`,
  `.agents/skills/workflow-authoring/templates/governed-run-orchestrator.md:1980-1986`) and
  `mcp-defaults/enforce-mcp-defaults.py` (same template, `:1990`). Treating "unregistered" as
  "dead" would be wrong here.

**Impact** Two separate things. (a) The three live-wired untested hooks run on every session/turn
with no regression net — `profile-capture` on Stop is the one that would fail most silently.
(b) The `hooks/` tree conflates **event-registered hooks** with **on-demand CLI tools**, which is
why "is this hook wired?" cannot be answered by directory listing alone; that ambiguity is the
same one that let `edit-validate/record` and `edit-checkpoints` sit unwired for months
(`manifest.json:222`, `:250`).

**Safe validation** For (a): write one characterization test per hook that feeds a canned stdin
payload and asserts exit 0 + JSON shape — the pattern already used by the 53 tested families.
For (b): no code change — a `KIND:` line (`event-hook` vs `cli-tool`) in each family's header
would make the census answerable, and `test_wiring.py`'s census already proves the pattern works.

**Value × effort** Medium-High × Low for the three live hooks; Medium × Low for the KIND labelling.
**Confidence: HIGH** on the counts and the three wirings; **MEDIUM** on the dead-vs-CLI split
(established for 6 families by grep, not for all 18).

---

### F-14 — Small stale-accuracy items (low value, listed for completeness, no action urged)

| # | Item | Evidence | Verdict |
|---|---|---|---|
| a | `manifest.json:8` `rebalance_note` justifies the Stop rebalance by *"timeouts summing 144s"* under a 35 s ceiling. Under the shipped dispatcher the sum is **not** the binding constraint — `dispatch.py:349-372` gives every check an absolute `start + timeout` deadline, so wall time is bounded by `max(timeout)`. The neighbouring `git-hygiene.timeout_rationale` (`manifest.json:95`) states this correctly. | source read | The rebalance was still right (tail checks *were* starved by elapsed-clock exhaustion); only the stated arithmetic is loose. **Fix the sentence, not the config.** |
| b | `~/.claude/AGENTIC-PERFECTION-PLAN.md` (13,952 B) and repo `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md` (14,341 B) differ. | `Compare-Object` → **4 lines**, all repo-only: a `See also:` pointer to `AGENTIC-REPAIR-RELIABILITY.md`. | Genuine two-copy divergence but trivial in size. `OPEN-THREADS.md` is **byte-identical** across both. Low priority; the substantive staleness in these docs is F-02. |
| c | `~/.codex/skills` holds **8** `SKILL.md` vs 380 in the vault. | measured | `AGENTS.md` ("Profile ownership") says `~/.codex/skills` is *"Codex-owned for built-ins, plugins, and Codex-local-only skills"*, which makes 8 expected — **but** the same file's "Universal harness share (HARD)" says every runtime must load from `.agents\skills`. Worth confirming Codex actually reaches the vault via its `AGENTS.md` pointer. **Confidence: LOW — intent not established; flagged as a question, not a defect.** |
| d | `.claude/plugins/cache/claude-plugins-official/data-engineering/0.1.0/skills/*` — 10 skill dirs enumerate in the parent listing but fail to open (`os error 3`). | ripgrep traversal errors | Consistent with the long-path/ENAMETOOLONG class `git-hygiene/check.py:25` already tracks. **Confidence: LOW — not independently corroborated. Observation only.** |

---

## Consolidated queue (value × effort, highest return first)

| # | Item | Value | Effort | Conf | Note |
|---|---|---|---|---|---|
| F-01 | Cap + rotate + redact the observe logs (242 MB) | Very High | Low | High | Keep the stream — the flip criteria need it |
| F-05 | Re-hash `installed.json` = the missing drift tripwire | High | Low | High | 12 files, read-only loop |
| F-02b | Correct `OPEN-THREADS.md:55` "LIVE+WIRED" | High | Trivial | High | Do not wait on the wiring work |
| F-03 | Fix 3 doc lines claiming absent gates/files | Med-High | Trivial | High | `orchestrate.md:90` first |
| F-06 | Capture the 2 unversioned skills + close the 19-skill repo gap | High | Low | High | `hosted-model-agents` is cited by an injected rule |
| F-08 | Capture 38 root docs; make capture a sync step | High | Low→Med | High | `memory-contract.md` has no history |
| F-04 | Sweep 62 backups to `trash/`; retain-N on `recall-index.json.bak-*` | High | Low | High | Closes an alarm that fires every session |
| F-07 | Dedupe 3 identical + reconcile 2 divergent skill copies | Med-High | Low | High | `microsoft-foundry` differs by 13 KB |
| F-13a | Characterization tests for the 3 live untested hooks | Med-High | Low | High | `profile-capture` fails most silently |
| F-02a | Adjudicate the 10 censused handlers, one at a time | High | Medium | Med | Several are exit-2 gates → must stay standalone |
| F-09 | Size then umbrella `source-command-*` (23) + `codex-*` (18) | Med-High | Medium | Med | Sequence **after** F-06 |
| F-10 | Resolve the split registration of `codex-monitor-autolaunch` | Medium | Low | Med | Let `test_wiring.py:840` arbitrate |
| F-13b | Label each hook family `event-hook` vs `cli-tool` | Medium | Low | Med | Makes "is it wired?" answerable |
| F-12 | Triage store B's 1 uncommitted file (retirement = owner call) | Medium | Low-Med | Med | Baseline footgun, not disk |
| F-11 | **Measure** the per-Bash 13-process tax; do not fold guards | High | High | High/Low | Blocked by design; measurement only this wave |
| F-14 | Four small accuracy fixes | Low | Trivial | Mixed | Opportunistic |

## Explicitly NOT proposed (anti-overfit)

- Re-litigating the Stop rebalance, the deny-contradiction fix, tombstone compression, the
  budget-pacing prose, or Cursor-hooks parity — **all confirmed closed above.**
- Deleting any of the 62 backups outright — house rule is move-to-trash, never permanent delete.
- Disabling `afterFileEdit`, `git-hygiene`, or any guard to buy latency — that trades capability
  for speed, which the standing rules forbid; F-01 and F-11 are framed as retention + measurement
  precisely for that reason.
- Retiring store B in this pass — it touches a tree a running program may be using, and the
  1 uncommitted file is still `UNVERIFIED` per `REPO-TOPOLOGY.md:97`.
- Re-auditing the RE/security skill family (~45 skills) — content-scope guard, unchanged from 27.08.
- Any claim about `deep-research`'s 42% success rate, ISR telemetry, or gem leases — those are
  27.08 `PLANNED-UNBUILT` items with no new evidence today.

## Method / limits

Read-only. Nothing deleted, edited, disabled, moved, or rotated. Every count came from a direct
`Get-ChildItem` / `Get-FileHash` / `Compare-Object` on this box today, or from a source read with a
line cite. Searches were scoped to single subdirectories and run sequentially per the standing
memory-pressure rule. Three known gaps, stated rather than papered over: (1) the exact path of the
single `harness-audit.js` is **NOT-CHECKED** — the follow-up recursive search stalled and was
killed; (2) the dead-vs-CLI status of 12 of the 18 untested hook families is **NOT-CHECKED** —
corroborated by grep for only 6; (3) no latency was measured for the per-Bash process fan-out
(F-11) — the process **count** is exact, any timing claim would not be.

UNIT-COMPLETE: lens-08
