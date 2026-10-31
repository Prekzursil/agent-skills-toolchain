# Agentic-Perfection — CHANGELOG

Durable, revisit-able record of the *agentic-perfection / proactive-partner*
program: the work that makes the agent reliable, proactive, human-like, and
AGI-adjacent by putting discipline in the **harness** (hooks / files / a second
agent the tired mid-task self can't override), not in the model's good intentions.

- **Canonical code:** [`../../hooks/`](../../hooks/) (synced to `~/.claude/hooks`
  via [`../../scripts/sync-hooks.ps1`](../../scripts/sync-hooks.ps1)) and
  [`../../scripts/agentic-perfection/`](../../scripts/agentic-perfection/).
- **Plan & vision (verbatim):** [`AGENTIC-PERFECTION-PLAN.md`](AGENTIC-PERFECTION-PLAN.md),
  [`PROACTIVE-PARTNER-PROGRAM.md`](PROACTIVE-PARTNER-PROGRAM.md),
  [`OPEN-THREADS.md`](OPEN-THREADS.md) (point-in-time backlog snapshot).
- **Design law:** MAST failure taxonomy (arXiv 2503.13657) + the self-calibration
  LAW (Huang ICLR'24 — intrinsic same-context self-correction fails; every check
  needs an external signal). Keep total active hooks ~6 via per-event consolidation;
  flat-file / SQLite ledgers only (no graph-memory — it blew the latency budget).

---

## 2026-06-30 — Design-review skill suite + DESIGN-EVAL ui-audit upgrade versioned

The **design-SOTA research** thread (the TCR *transpose → critique → revert* design-review
loop) landed as runnable skills in `skills/`, plus its research deliverables under
`docs/design/`: five new skills, one upgraded skill, four docs. All six skills pass
`quick_validate.py`; the pure-Node suites pass (design-tokens 12, critique-panel 19,
design-review-loop 14).

### Added — the TCR design-review skill suite (`skills/`)

- **`design-review-loop`** — the orchestrator: the 8-gate TCR workflow (G0 PRIME → G1 AUDIT →
  G2 TRANSPOSE → G3 CRITIQUE → G4 DIRECT → G5 ITERATE → G6 RECONCILE → G7 VERIFY → loop),
  driving the *transpose-then-discuss-then-revert* motion with a first-class revert-gate (every
  apply-back is a reversible commit, reverted if it regresses a tracked axis or touches logic).
- **`critique-panel`** — the G3 CRITIQUE gate: a four named-persona panel (user-advocate /
  systems-consistency / a11y / brand-aesthetic) that reasons over ui-audit's Track-A numbers +
  the screenshot, runs the NN/g *I Like / I Wish / What If* ritual, scores the nine DESIGN-EVAL
  v1 dimensions 0-4 with critical-error overrides, and synthesizes a deduped, severity-ranked
  findings list with a weighted composite (a TRIAGE accelerator, not an oracle).
- **`transpose-to-figma`** — the G2 TRANSPOSE gate: the *altitude selector* for the
  code-to-Figma edge (story.to.design / the Figma MCP `generate_figma_design` / html.to.design)
  and what survives the lossy round-trip (DTCG tokens + Code-Connected components) vs what is
  lost (state, routing, data, logic).
- **`design-tokens-pipeline`** — the G5/G6 token spine: the W3C-DTCG round-trip surface
  (extract tokens from code → validate → diff with an inverse revert patch), transformable via
  Style Dictionary + sd-transforms.
- **`firecrawl`** — the web-data layer (scrape / crawl / map / structured-extract / search /
  monitor / browse-agent via the Firecrawl MCP); the *fetch-and-structure* companion to
  exa-search's *find-by-meaning*, feeding brand-identity extraction into the design loop.

### Changed — `ui-audit` upgraded to the two-track DESIGN-EVAL engine

After the deterministic **Track-A** audit (a11y, contrast, spacing, tap targets, dead buttons,
affordance/focus-visible, motion, visual regression), `ui-audit` now adds **Track-B**: Claude
reasons over the pre-computed numbers + the screenshot on the **DESIGN-EVAL v1** rubric — nine
dimensions scored 0-4, a critical-error override that forces a zero and caps the verdict, a
weighted composite (color-contrast weighted highest), and a one-dimension-per-call reliability
protocol — against Refactoring-UI / Material / HIG / Nielsen / WCAG. New files: `critique.mjs`,
`critique_schema.mjs`, `critique.schema.json`, `critique_rubric.md`, `uiclip_score.py` (opt-in
numeric prior), plus fixtures/tests.

### Fixed — `design-tokens-pipeline` validator test now asserts all five DTCG rules

The bundled `tests/tokens.test.mjs` asserted only 2 of the 5 validators the SKILL.md claims.
Extended it to assert **all five** by rule id (missing-type, bad-alias, alias-cycle,
raw-hex-in-code, reserved-misuse) — the validator already fired for all five; the assertions
were the gap. `npm test` green (12/12).

### Added — design research deliverables (`docs/design/`)

`DESIGN-WORKFLOW.md` (the 8-gate loop + per-gate method), `FIGMA-SETUP.md` (the Figma/Variables
round-trip surface), `DESIGN-SKILLS-AND-EVAL.md` (the skill map + DESIGN-EVAL rubric), and
`DESIGN-SKILLS-BUILT.md` (what shipped). Manifest: 5 rows added + the `ui-audit` row updated
(`skills/SKILLS-MANIFEST.md`).

---

## 2026-06-30 — Calibrated-silence over-suppression SAFETY fix + Binary Ninja GUI bring-up

Two corrections to hooks landed in the prior `2026-06-29` waves. The first is a **safety
bug**: the calibrated-silence (CS) dedup gate was allowed to silence *brand-new* harm /
advisory findings, so a long, noisy session whose CS ledger was stuffed with ignored rows
could gag a real, first-time safety warning. The fix makes CS what it was meant to be — a
**dedup of exact repeats**, never a gag on a distinct alert. The second wires **Binary
Ninja** into the RE-backend autolaunch data model as a GUI-only (off-the-auto-path) backend.

### Fixed — calibrated-silence may no longer suppress a DISTINCT harm/advisory finding

- **`hooks/contraindication/check.py`** — a contraindication is a tool-combo HARM warning
  (DDI-style). The hook now partitions matches into **distinct vs. repeat** per session
  (sha1-keyed per-session seen-map under `~/.claude/contraindication/`, TTL-cleared, env-
  overridable via `CONTRAINDICATION_SEEN_DIR` / `CONTRAINDICATION_SEEN_TTL_HOURS`). At least
  one **new** matched id in a call → **bypass CS, always surface**. Only an exact repeat
  (every matched id already surfaced this session) is handed to the CS gate for dedup.
  A stuffed ledger can no longer silence a first-time harm warning.
- **`hooks/iatrogenics/gate.py`** — a high-severity advisory (model-initiated live-state
  mutation: CheatEngine memory write, Frida code injection) now **bypasses CS on its
  DISTINCT first occurrence** (`cs_bypass = is_high_sev and count == 0`); a repeat
  (`count > 0`) stays CS-gated for dedup. Reuses the existing `_IRREVERSIBLE_TOOL_RE`
  classification so command-triggered (non-tool) findings keep their unchanged first-use
  grace.

### Fixed — deterministic, hermetic CS state in the three test suites (test-isolation)

- **`hooks/contraindication/test_check.py`**, **`hooks/iatrogenics/test_gate.py`**,
  **`hooks/recall-inject/test_recall_inject.py`** — added per-test isolation so the suites
  no longer read or write the **live production CS ledger** (the source of flaky
  pass/fail). Each test gets a fresh per-test seen-dir + an empty per-test CS ledger
  (`CALSIL_LEDGER_PATH` / monkeypatched `calibrated_silence.LEDGER_PATH`), and CS-gate tests
  force CS active (`CALIBRATED_SILENCE=""`) against their *own* stuffed/fresh ledger. The
  old "CS suppresses everything" tests were replaced with the correct two-case contract:
  **distinct-bypasses-CS** + **exact-repeat-is-CS-deduped**. Suites: contraindication
  **32 passed**, iatrogenics **31 passed**, recall-inject **39 passed**.

### Changed — `hooks/re-autolaunch/`: Binary Ninja GUI bring-up, off the auto-path

- **`backends.json`** — the `binary-ninja-mcp` (`bn`) entry is now `launchable: true` with a
  new **`auto_launch: false`** flag: explicit `re-ensure bn` / `re_launch.py bn` may open
  the BN GUI (the in-GUI "MCP Max" plugin auto-starts `:9009` on file-open, zero clicks),
  but the **PreToolUse hook never auto-pops the heavy GUI** on a stray tool call (the user
  has an OOM history — RAM-conscious by default). IDA / Ghidra omit `auto_launch` and so
  keep their existing auto-launch behavior.
- **`autolaunch.py`** — `decide()` now treats *launchable-but-`auto_launch:false`* the same
  as unlaunchable in the auto path (returns `manual` + the `manual_hint`); `auto_launch`
  **defaults to `True`** so IDA/Ghidra are unchanged. `cmd_ensure(..., "all")` **skips**
  `auto_launch:false` backends (prints a `SKIP:` line pointing at the explicit
  `re-ensure <tool>`), while an explicit single-target `re-ensure bn` still launches.
- **`test_autolaunch.py`** — new cases pin the contract: BN spec is `launchable:true` /
  `auto_launch:false` → `decide` returns `manual`; `auto_launch:true` and the
  *omitted-field default* both → `launch`; IDA/Ghidra omit the field; `ensure all` skips the
  GUI backend yet an explicit target launches it. Custom runner: **ALL PASS**.

> **Tracked elsewhere (NOT in this repo):** the orphaned-MCP reaper section added to
> `~/scripts/ram-keeper.ps1` and the Binary Ninja re-harness adapter
> `~/.local/opt/re-harness/adapters/bn.py` live outside the toolchain tree and should be
> versioned in whatever repo tracks those trees.

---

## 2026-06-29 — App-driver / audit skillset + RE-backend autolaunch + userscope-sync

Delivers the program's queued **"app-driving drive-and-verify"** thread (see Status):
deterministic skills that *drive a running app and verify it* (a web/Electron app and a
live game), plus two infra hooks that make on-demand RE backends and the MCP user-scope
config "just work". All new skills pass `quick_validate.py` (no angle brackets in the
`description`, allowed frontmatter keys only) — the as-built frontmatter was corrected on
the way in (stripped a non-standard `origin:` key; de-angle-bracketed the ui-audit /
bc-drive descriptions).

### Added — skills (`skills/`)

- **`skills/ui-audit/` (v2 hardened + orchestrator)** — drives a running web or Electron
  app and emits a deterministic, terminal-state UI/UX + functional audit. Audit modules:
  `capture.mjs` (deterministic screenshots), `layout_lint.mjs` (spacing / tap-target /
  overlap / contrast), `dead_button_crawl.mjs` (wired-vs-dead control crawl),
  `axe_scan.mjs` (accessibility), `visual_diff.mjs` (visual regression) — composed by
  `run_audit.mjs` (the orchestrator). READ-ONLY: it drives and inspects, never edits app
  source. Emits `SUCCESS:ui-audit-[id]` / `FAILED:ui-audit-[id] [reason]` terminal-state
  markers plus an annotated findings JSON for downstream Track-B VLM design critique.
  Ships `tests/` (7 suites) + `fixtures/` (static / SPA / component HTML); `node_modules/`
  and `package-lock.json` are NOT versioned (repo `.gitignore` policy — run `npm install`).
- **`skills/bc-drive/`** — deterministic on-demand driver for a LIVE Battle Cats
  (`jp.co.ponos.battlecatsen`, EN 15.4.1) on rooted BlueStacks. `bc_agent.js` reads engine
  state (scene / metrics) via **crash-safe one-shot Frida `NativeFunction` calls** —
  explicitly NO per-frame `Interceptor` (the render-thread hook that crashes on scene
  transitions); `bc_drive.py` actuates with OS-level `adb shell input tap` in device px and
  resolves the device-to-drawable coordinate space. BC is a custom PONOS C++/GLES engine
  (not cocos2d-x). Drive-and-verify applied to a native game.
- **`skills/re-ensure/`** — explicit, on-demand bring-up of the RE MCP backends so
  `mcp__ida-pro-mcp` / `mcp__ghidra-mcp` / `mcp__binary-ninja-mcp` calls just work. Shares
  the `re-autolaunch` engine (`autolaunch.py ensure <ida|ghidra|bn|all>`): cold-starts ONLY
  the requested backend (RAM-conscious), prefers an already-running GUI IDA on `:13337`
  (never duplicates), and reports honestly that Binary Ninja (Personal license) cannot run
  headless.
- **`skills/gem-hunt/`** — manifest row backfilled (the skill shipped in `b2f3cd8` but was
  missing from `SKILLS-MANIFEST.md`).

### Added — hooks (`hooks/`)

- **`hooks/re-autolaunch/` (`autolaunch.py` + `backends.json` + `test_autolaunch.py`)** —
  the automatic PreToolUse companion to `re-ensure`, matching
  `mcp__(ida-pro|ghidra|binary-ninja)-mcp__.*`. The RE MCPs are **bridge proxies** whose
  calls forward to a plugin/server inside a GUI/headless app; if that backend is down the
  call just fails. The hook probes the backend port(s) and: UP (incl. the live GUI IDA on
  `:13337`) → fast silent no-op; DOWN + launchable → cold-starts ONLY that backend via the
  re-harness (`re_launch.py`, DETACHED so the hook never blocks) and returns an actionable
  retry; DOWN + unlaunchable (Binary Ninja Personal) → emits the manual step. Backends are
  declared in `backends.json` (data-driven; a new backend is a JSON entry, no code change).
  RAM-conscious (on-demand only, single-backend, idempotent, refuses below
  `min_free_ram_mb`) and FAIL-OPEN (any error exits 0, never blocks the call).
- **`hooks/mcp-userscope-sync/` (`heal.py` + `promote-mcp-userscope.ps1`)** — MCP
  user-scope drift fix. The PRIMARY cure is `promote-mcp-userscope.ps1`, which promotes the
  canonical MCP set into **user** scope so it loads in every normal session (not silently
  shadowed by project-scope writes — the reappearing-server failure mode). `heal.py` is the
  SessionStart belt-and-suspenders backstop: (1) plants the canonical `~/.mcp.json` at an
  *orphan* tree root (CREATE-ONLY; never overwrites, skips `mcp-funnel`/ralph and
  plugins/node_modules paths), and (2) re-syncs the `~/.agents/skills` mirror (a copy, not
  a junction, so it goes stale). FAIL-OPEN and ralph-safe (ralph's `--setting-sources
  project,local` excludes user scope, so it never runs there). Runtime state
  (`.last-skills-heal`) is NOT versioned.

### Not a skill (noted for traceability, not versioned here)

- **529-overload gateway** — the `ANTHROPIC_BASE_URL` multi-provider gateway that survives
  transient Anthropic-side 529 overloads lives under **`D:\tools`** (host infra, not a repo
  skill/hook).

### Not versioned (by design)

`node_modules/` (ui-audit), the `bc_demo_before.png` / `bc_demo_after.png` before/after
captures, `__pycache__` / `.ruff_cache`, runtime state, and the `~/.claude/settings.json`
hook wiring (personal — it binds these hooks to events).

---

## 2026-06-29 — Wave 0 (lifecycle hooks) + Wave 1 (security / reasoning gems)

This session extends the hook set with two new waves. A **fresh-context Opus
adversarial review** (no session context, to prevent confirmation bias) caught
real bugs the green unit tests had missed — all fixed before versioning.

### Added — Wave 0: native lifecycle hooks

- **`hooks/session-end/end.py`** (`Stop` event) — ledger checkpoint on session
  end: writes a durable snapshot of the current event ledger so the next
  SessionStart replay always has a clean tail. Fail-open; no side-effects.
- **`hooks/notify-idle/notify.py`** (`Stop` event) — local alert (Windows toast /
  terminal bell) when the session ends while the user has been idle for >N minutes.
  Fixes the "Claude finished but nobody was watching" silent-completion case.

**Model-routing lesson (not versioned):** `fallbackModel` in `hooks.json` lets
lifecycle hooks route to a lighter model (e.g. `claude-haiku-3-5`) to avoid
burning Sonnet/Opus quota on bookkeeping. The same field on a `SubagentStart`
hook can route specialized background agents to a cost-appropriate model —
keeping the harness cheap per-turn without manual model selection.

### Added — Wave 1: security / reasoning gems (7 hooks)

- **`hooks/contraindication/` (`check.py` + `contraindications.json`)** —
  *Contraindication registry.* PreToolUse gate: checks tool arguments against a
  JSON registry of known dangerous patterns before execution. Exits 2 (block) on
  a hit; logs to the ledger. Registry is plain JSON — new rules require no code
  changes.
- **`hooks/iatrogenics/gate.py`** — *Iatrogenics gate.* PreToolUse classifier that
  scores whether the proposed call would likely worsen the situation (reversibility,
  blast radius, diagnostic confidence, whether it was requested, whether an
  alternative exists). Injects a structured warning above threshold. Fail-open;
  threshold tunable in the hook header.
- **`hooks/per-edit-check/check.py`** — *Per-edit diagnostic loop.* PostToolUse on
  Edit/Write: runs a fast per-language syntax/lint pass (`py_compile`, `tsc
  --noEmit`, etc.) immediately after each modification so the next turn sees
  breakage immediately, not at the next test run. Closes the tight-feedback-loop
  gap that causes edit avalanches.
- **`hooks/file-scope/` (`check.py` + `set_scope.py` + `_common.py`)** —
  *File-scope enforcement.* `set_scope.py` records a declared scope at session
  start; `check.py` (PreToolUse on Edit/Write/Bash) blocks any modification
  outside that scope and injects *"OUT OF SCOPE — declared files: …"*.
- **`hooks/loop-recovery/` (`handler.py` + `verdict.py`)** — *Progress ledger +
  stuck escalation.* Tracks milestone timestamps and per-turn action fingerprints;
  if consecutive turns produce the same action hash without advancing a milestone,
  fires the escalation path: injects a STUCK verdict with the full ledger state
  and instructs the agent to surface the blockage instead of spinning. Directly
  addresses the parallel-agent hung-barrier deadlock pattern.
- **`hooks/subagent-lifecycle/` (`start.py` + `stop.py` + `_common.py`)** —
  *Subagent lifecycle.* `start.py` (SubagentStart): injects the parent session's
  goal verbatim into every spawned subagent so drift/forgetting is structurally
  impossible. `stop.py` (SubagentStop): anti-degen guardrail — verifies the
  transcript ends with a terminal-state output (`SUCCESS:<id>` / `FAILED:<id>`)
  and injects a warning on ambiguous completion (prevents silent no-op subagents).
- **`hooks/recall-inject/` (`inject.py` + `build_index.py`)** — *Recall-first
  injection.* SessionStart hook: embeds the resumed goal / first user message
  against a local basic-memory vector index and injects the top-k relevant notes
  BEFORE the model sees any other context. Forces memory-pull proactively without
  relying on the model's willingness to call `build_context`.
  `build_index.py` maintains the index (state dir `index/` is not versioned).

### Bugs caught by fresh-context adversarial review — all fixed, 279 tests green

Unit tests were green before the review, yet three real bugs were found:

- **C1 (Critical — `subagent-lifecycle/stop.py`)** — the anti-degen check read a
  field named `output` from the transcript event structure, which does not exist;
  the correct field is `transcript_path`. The check silently skipped every
  transcript, making it a no-op. Fixed: field name corrected; test updated to
  assert the check fires on a real transcript path.
- **H1 (High — `file-scope/check.py`)** — path comparison was case-sensitive on
  Windows (`str.__eq__`), so `C:\Foo\bar.py` would pass when the scope declared
  `c:\foo\bar.py`. Fixed: both sides normalized via `Path.resolve().lower()`.
- **M1–M6 (Medium / noise / correctness)** — two wrong default values in `_common.py`
  helpers; one off-by-one in `verdict.py`'s retry counter; two test fixtures with
  incorrect expected exit codes; one missing `except OSError` guard in `inject.py`.
  All fixed.

### Not versioned (by design)

`~/.claude/settings.json` event-wiring (hook registrations, matchers,
`fallbackModel` entries) is personal configuration and is NOT versioned here.
The hook source is versioned; the wiring that binds it to Claude Code events
lives only in the personal settings file.

---

## 2026-06-29 — Phase 1 + 2 landed (consolidate → top gems)

### Added — Dispatcher (consolidation)

- **`hooks/_dispatch/` (`dispatch.py` + `manifest.json`)** — a per-event dispatcher.
  Reads stdin once, runs each manifest check whose `matcher` matches in its own
  in-process thread with a per-check timeout, fail-open, and aggregates every
  check's `additionalContext` into ONE `hookSpecificOutput`. Consolidated
  **Stop 5→1** and **SessionStart 3→1** (54/54 behavioural-equivalence verified),
  reclaiming per-turn latency under the ~6-hook ceiling. Adding a future check is a
  one-line manifest edit (this seeds Discipline-Forge). Pre-existing B1/legacy hooks
  stay separate by design.

### Added — Durability spine (between-turns/agents, Tier 1 keystones)

- **`hooks/bg-registry/`** — background-work registry + restart reconciler.
  Write-ahead NDJSON per `Task`/longrun spawn `{id,kind,cmd,pid,artifact,scope,ts,status}`;
  SessionStart reconciler checks pid-liveness + artifact and injects
  *"ORPHANED BG WORK: agent-X died, artifact incomplete — resume/discard?"*.
  *Trigger:* PreToolUse(`Task`) register · Stop done-marker · SessionStart reconcile.
  Fixes the restart-killed-agent silent loss.
- **`hooks/memory-spool/`** — memory write-ahead spool + continuity self-check.
  Distinct from mcp-liveness (which heals the *server*): a note you were writing
  during an outage is gone. Spools every intended `write_note` to a local file
  FIRST; SessionStart read-back-verifies the flush to basic-memory and
  re-flushes/alerts if not. *Trigger:* PreToolUse + PostToolUse on
  `write_note`/`edit_note` · SessionStart. The true fix for the 4h silent-memory-loss.
- **`hooks/wire-check/`** — reachability gate (anti-slop keystone). Stop hook builds
  a static reference graph over the session diff and flags any session-added
  symbol/component/route/handler referenced 0× (dead button / built-but-not-wired)
  and `*_v2/_new/_copy` with no live v1. Enforces the perfect-work bar mechanically.
- **`hooks/_shared/projid.py` (+ `projid_migrate.py`)** — per-project identity
  resolver. Keys every ledger by a **canonical project root** instead of drifting
  cwd (the "5-Reframe-shard" bug); migrator moves legacy cwd-keyed state.

### Added — Verification / anti-slop / boundary (Tier 2)

- **`hooks/tool-result-sentinel/`** — PostToolUse(*) classifier: every result →
  SUCCESS / FAILED / AMBIGUOUS (exit code + MCP error-envelope + empty-on-expected);
  injects *"TOOL X returned FAILURE — do not treat as success."* The generic
  tool-boundary guard.
- **`hooks/honest-signal/`** — Stop hook: the verbalized confidence band
  (VERIFIED / INFERRED / GUESSED) must match whether a verifying tool actually ran.
  Kills "I'm unsure" → then act certain.
- **`hooks/stub-ledger/`** — tracks every placeholder/stub/TODO introduced
  (PostToolUse record on Edit/Write) and reports unresolved ones at Stop.
- **`hooks/dup-guard/`** — PreToolUse(Write) search-before-build: warns when a new
  file duplicates an existing capability.

### Added — Wildcard gems (cross-domain borrows the field hasn't absorbed)

- **`hooks/open-loops/`** — *Zeigarnik / GTD prospective memory.* Trigger-action
  notes `{condition,action,status}` fired on **detection**, not request
  (SessionStart `resurface.py`; `add.py`; `trigger_match.py`). Bullseye on the
  forgotten-thread stress.
- **`hooks/ulysses/`** — *Ulysses self-binding / behavioral contracts.* `arm.py`
  records a contract; `enforce.py` is an exit-2 PreToolUse tripwire that blocks a
  declared-dangerous op (e.g. a live-game write). Makes the other gems stick.
- **`hooks/tms/`** — *Doyle-1979 Truth Maintenance System auto-retraction.* A SQLite
  justification graph behind every load-bearing RE value (offset/address/pid/version);
  retract a premise → cascade-flip every downstream finding to OUT, and
  `stale_anchor.py` (PreToolUse) BLOCKS a tool call resting on a retracted/changed-hash
  premise (*"0x… rests on the pre-rebase IDA base, retracted — re-derive"*). Structural
  fix for the wrong-but-consistent anchor (the costliest recurring RE failure).
  Conventions in `tms/CONVENTIONS.md`.
- **`hooks/calibrated-silence/`** — *Signal Detection Theory / clinical
  alarm-fatigue.* Proactivity = an adaptive SDT operating-point: logs each
  interjection `{context,type,user-reaction}` (`log_reaction.py`) and slides the
  threshold by rolling hit-rate + a fatigue proxy (correction-rate, terseness,
  caveman-mode, time-of-day). **Dissolves proactive-vs-don't-fatigue-me** and is the
  precondition that makes every other proactive feature sustainable; now governs all
  proactive consumers.
- **Discipline-Forge (capstone, #12 — the moat)** — lives as the **skill**
  `skills/forge-discipline/` (not a hook). `/forge-discipline "<pattern>"` takes any
  named pattern (a gem here, or tomorrow's arXiv paper) and emits the hook +
  memory-schema + tripwire + skill that installs it, then runs a **chaos/GameDay
  self-test proving the tripwire/halt actually FIRES** before declaring it installed.
  Generalizes instinct→skill evolution (forges BEHAVIORS; distinct from tool-forge,
  which forges TOOLS). Reframes the program from "find every gem" to "consume any gem
  in a day" = antifragile. *Dogfood-proven:* it forged the two disciplines below.

### Added — Forged disciplines (dogfood output, chaos-tested)

- **`hooks/no-force-push/`** — PreToolUse tripwire blocking `git push --force` to
  protected branches. Ships `spec.json`, `fixtures.json`, `chaos_no_force_push.py`
  (GameDay), `tripwire.py`, `hook.py`, `INSTALL.md`, `SKILL.md`, and a PASSED
  `SELFTEST-RESULT.txt`.
- **`hooks/todo-surfacer/`** — Stop hook surfacing unresolved TODOs introduced in the
  session. Ships the same forge bundle (`spec.json`, `fixtures.json`,
  `chaos_todo_surfacer.py`, `hook.py`, `INSTALL.md`, PASSED `SELFTEST-RESULT.txt`).

### Added — Anticipatory layer ("while you were away")

- **`hooks/background-digest/reader.py`** — SessionStart reads the digest produced by
  the scheduled watchers, surfaces it, then archives + truncates it.
- **`scripts/agentic-perfection/world-watch.ps1` + `world-watch.yaml`** — a daily
  Scheduled Task (`World-Watch`) that fingerprints each curated watcher and appends a
  digest line ONLY when the fingerprint changes (first observation records a baseline
  silently; each watcher fail-opens independently). Watcher types: `gh_commit`,
  `gh_release`, `adb_package_version`, `http_etag`, `file_hash` — external signals only
  (a Scheduled Task can't reach in-session MCP). Curated watchers include the Battle
  Cats app version (a bump invalidates committed RE offsets → HGT risk) and upstream
  repos whose pulls clobber local patches (HexStrike, BCSFE, tbcml, insta-mcp).
  `test-world-watch.ps1` is the regression test.
- **`scripts/agentic-perfection/resource-guard.ps1`** — cgroup-style fleet
  memory-governor + OOM-avoidance (Gem 5): parks the fattest non-essential MCP via
  `.mcp.disabled.json` under RAM pressure. LOG-and-act-only; never kills a healthy
  essential.

### Added — Per-project self-model

- **`hooks/capability-catalog/project_card.py`** (+ test) — SessionStart injects a
  per-project card ("how I fail THIS user" / resume state) after the global
  capability catalog, keyed by the canonical project root. Never writes during inject
  and never raises into the hook. Only `project_card.py` + its test are versioned;
  the pre-existing `inject.py`/`catalog.json` remain live-only by design.

### Fixed — Infra / health

- **basic-memory race root-caused + launcher HARDENED** —
  `scripts/agentic-perfection/bm-http-server.ps1` is the shared streamable-HTTP
  launcher (ONE process for all Claude/Codex sessions → single FastEmbed load, no
  per-session hang, no 4× RAM). Fixes the `[Errno 10048]` port-flapping from racing
  launch paths via a held-open **lockfile mutex** guarding only the start+bind
  critical section (releasing it once bound, so a hung launcher can never deadlock
  future restarts), a port-in-use idempotent skip, and a kill-stale + socket-release
  step so exactly one instance binds.
- **`scripts/agentic-perfection/bm-watchdog.ps1`** — keep-alive watchdog: every few
  minutes, if `:8765` isn't serving, relaunch via the hardened launcher (LOG +
  restart only; never touches a live server; fully fail-open). Closes the gap where
  the daemon died between uses and stayed down until the next memory call.
- **`hooks/mcp-liveness/`** — self-heal + alert when basic-memory is down
  (`restart-basic-memory.ps1`, `critical.json`). The original 4h-memory-loss fix.
- **`hooks/heartbeat/`** — health-heartbeat banner; accuracy fixed to a **live
  socket-probe** (no more stale mem:UP/DOWN reporting).

### Earlier waves (context — shipped before this entry)

- **B1 keystone hooks:** mcp-liveness, capability-catalog, edit-checkpoints (+
  `/rollback`), truth-verify, persist-nudge — cover the famous in-context failure
  modes. (`edit-checkpoints`, `truth-verify`, `persist-nudge` are versioned here.)
- **PP1 semantic router** (the live `[auto-router]` line) — `hooks/semantic-router/`:
  embeds skills/MCP/agents/commands into a local index (`index/meta.json` +
  `vecs.f32`, generated; rebuild via `build_index.py`) and routes a prompt to the
  best capability.

---

## Status

**Phase 1 + 2 COMPLETE + independently verified.** Remainder durably queued in
`OPEN-THREADS.md` and `AGENTIC-PERFECTION-PLAN.md`: PreToolUse-dispatcher
consolidation (ulysses + tms co-fire today) · the rest of the round-2 *reasoning*
spine (file-centric world-model state ledger, hold-your-ground dissent, code-mode
default, capability-gap tool-forge, variant-archive self-improvement, Brier ledger) ·
USER.md / dreaming + adopt-llmcouncil · app-driving drive-and-verify · basic-memory
periodic deep-diagnosis (self-heals for now).

### Versioned here vs left in place

- **Versioned:** the hook set above (`hooks/`), the four program scripts + sync
  (`scripts/agentic-perfection/` + `scripts/sync-hooks.ps1`), and the plan/program/
  open-threads docs.
- **Left in place (by design):** `~/.claude/settings.json` wiring (personal, not
  versioned — the manifest documents the consolidation); the pre-existing
  `capability-catalog/inject.py` + `catalog.json`; the `forge-discipline` *skill*
  (belongs to the `skills/` surface, synced via `sync-skills.ps1`); runtime state
  (logs, `*.state.json`, the live digest file) which is regenerated, not source.
