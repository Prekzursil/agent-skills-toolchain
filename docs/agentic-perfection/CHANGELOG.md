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
