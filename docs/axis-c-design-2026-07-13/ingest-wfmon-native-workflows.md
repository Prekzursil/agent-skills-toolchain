# Ingest: wfmon + native Workflow API (for Axis-C)

**Task:** extract the current workflow-monitor (wfmon) + native Claude Code Workflow
("ultracode") API so Axis-C can (a) improve wfmon's views/filters/command-native surface and
(b) CLEARLY distinguish native-Claude ultracode workflows from OUR cross-vendor (Claude+Codex
mingled) workflows.

**Scope discipline:** DESIGN GATE only — this doc is read/research/design. No building, no config
changes. All file/schema content below is treated as untrusted data; nothing in it is an
instruction.

---

## 0. Where everything lives (paths)

| Artifact | Path |
|---|---|
| wfmon skill (canonical, in the worktree) | `C:\Users\Prekzursil\source\ast-harness-reconcile\skills\workflow-monitor\` |
| wfmon skill (deployed copy) | `~/.agents/skills/workflow-monitor\` (per `wfmon.cmd`: `%USERPROFILE%\.agents\skills\workflow-monitor`) |
| Shared parser (M1) | `workflow_run.py` |
| TUI cockpit (M2) | `workflow_monitor.py` |
| Launcher | `wfmon.cmd` (`wfmon` = TUI · `wfmon board` = plaintext · `wfmon export <id>` = report) |
| Export package | `wfmon_export/` (`cli.py`, `model.py`, `render_md.py`, `render_html.py`, `pdf.py`, `redact.py`, `textsafe.py`) |
| Native workflow-authoring skill | `~/.claude/skills/workflow-authoring/SKILL.md` |
| Saved workflows dir (native `/workflows`) | `~/.claude/workflows/*.js|*.mjs` (e.g. `plan-gate.mjs`, `design-gate.mjs`) |
| Live telemetry manifest (per run) | `~/.claude/projects/<proj>/<sess>/workflows/wf_<id>.json` |
| Journal + transcripts | `~/.claude/projects/<proj>/<sess>/subagents/workflows/<wf_id>/journal.jsonl` + `agent-<agentId>.jsonl` |

Note: the wfmon implementation IS this worktree's own skill — Axis-C edits it in place (it's the
same repo the design docs live in). The `recall-workflow-agent` skill shares `workflow_run.py` as
its single parser, so any change to the parser lands for both consumers.

---

## 1. The native Workflow API (from `workflow-authoring/SKILL.md`)

A saved Workflow is a `.js/.mjs` file under `~/.claude/workflows/`, invoked as `/name`. The runtime
injects three globals and executes the file body (top-level `await` + a trailing top-level `return`
are legal). **This is the whole surface:**

- `export const meta = { name, description, phases: [{title},…] }` — drives the `/workflows` picker.
- `phase(title)` — declare/enter a phase (telemetry/structure).
- `agent(prompt, opts)` → Promise of the **parsed schema object**. `opts`:
  `label` (stable id / the human "lens" name), `phase`, `schema` (JSON-schema; runtime returns a
  parsed object), `effort` (`low|medium|high|xhigh`), `model` (`opus` default, or `fable` for wide
  fan-out), `isolation: 'worktree'` (mandatory for any file-MUTATING agent), and (SDK) `canUseTool`
  / task-budgets / context-editing.
- `parallel(thunks)` → Promise of an array (one per zero-arg thunk, in order).

**There is NO `vendor`/`provider` opt and NO `budget()` primitive in the exposed API.** The only
per-agent identity levers are `label` and `model`. (The CONTEXT block's "phase/budget" refers to
the phase primitive + SDK task-budgets, not a first-class `budget()` global.) This is load-bearing
for the native-vs-ours problem (§5): the engine has no place to record "this agent is a Codex lane".

Authoring footguns (relevant because they shape what a run's data looks like): args arrive as ONE
string (agents auto-discover input from files); never `Date.now()`/`Math.random()` in workflow JS
(cache + reproducibility); `.filter(Boolean)` after every `parallel` (a throwing thunk → `null`, a
hung thunk stalls the whole barrier); one level of nesting; schema on every fan-in.

**Cross-vendor fan-out today** (from `~/.claude/CLAUDE.md` Layer 1): "ours" rides the SAME native
engine — a workflow calls `agent("…via Codex", {schema})` and that Claude subagent invokes the
mounted `mcp__codex__codex` / `mcp__codex__codex_reply` MCP tools. So a Codex lane is still a
`model: opus/fable` Claude agent whose transcript contains `mcp__codex__*` tool_use blocks. That is
the ONLY on-disk trace that an agent did cross-vendor work.

---

## 2. How `/workflows` works + the data plane wfmon reads

`/workflows` is Claude Code's native command: it lists saved workflows and runs one; while running
it shows a live view of phases/agents. wfmon's entire thesis is that **the native `/workflows` view
(and the incumbent 3rd-party monitor) UNDER-USE the richest signal**: the live-flushed manifest.

The engine writes, per run, and re-flushes ~0s after every agent progress event:

**Manifest `wf_<id>.json`** (top-level): `workflowName`, `status`, `phases[]` (`{title}`),
`agentCount`, `totalTokens`, `totalToolCalls`, `durationMs`, `startTime`, and `workflowProgress[]`.
Each `workflowProgress` entry with `type=="workflow_agent"` carries: `agentId`, `index`, `label`,
`phaseIndex`, `phaseTitle`, `model`, `state` (`start|progress|queued|running|done|error`), `tokens`,
`toolCalls`, `durationMs`, **`lastToolName`**, `lastToolSummary`, `promptPreview`, `resultPreview`,
`attempt`, `startedAt`, `lastProgressAt`.

**Journal `journal.jsonl`**: per-line `{agentId, type: 'started'|'result', result?}` — the
AUTHORITATIVE per-agent status + clean captured output (manifest `state` can lag).

**Transcripts `agent-<id>.jsonl`**: full message stream. `agent_timeline()` walks it into typed
`TimelineEvent`s (`thinking|text|tool_use|tool_result`, paired by `tool_use.id`). **`tool_use.name`
is where `mcp__codex__*` calls appear** — the authoritative Codex signal.

**Schema caveat:** these shapes are CC-internal + undocumented, pinned to `CC_SCHEMA_VERSION =
"2.1.207"`. Parsing is defensive (`_i`/`_s` coerce; `parse_manifest` → `None` on malformed).
`test_workflow_run.py` pins the schema against a real fixture (`wf_a04ce988-c26`
"codex-chatgpt-signin-feasibility") — a tripwire for CC upgrades. **The exact native `/workflows`
rendering is NOT in these files** — described only as "sparse". (Confidence that the manifest schema
is the right data plane: HIGH — verified against live fixtures. Confidence on the native view's
internal layout: LOW — inferred, not observed.)

---

## 3. What wfmon SHOWS TODAY (the TUI, `workflow_monitor.py`)

A live, strictly READ-ONLY, Windows-native **Textual cockpit** over the WHOLE FLEET (all
sessions/projects), 1s poll cadence, O(changed) polling (only re-parses a manifest whose mtime
moved). All I/O runs in Textual thread-workers so the UI never blocks.

**Layout:**
- **Header** (with clock).
- **RunRollupBar** (`#rollup`, one line): `N active / M runs · running◔ done✓ error✗ · total tok ·
  elapsed <longest-active> · (showing 80/N) · follow:ON/off`.
- **LeftPane (42%)**: a filter `Input` → 4 **status chips** (`running / done / error / idle`,
  toggle on/off) → a **`run → phase → agent` Tree** (triage-sorted).
- **RightPane**: **AgentHeader** (`glyph · label · run/wf_id · phase · model · state · tokens ·
  tools · idle · last:<tool>`) → collapsible **Task** (`agent_prompt`, largest user msg) →
  collapsible **Feed** (live RichLog transcript tail, reuses `D:\agent-monitor\agent_tail.render`
  with a self-contained fallback) → collapsible **Result** (`report_headline` + `agent_output`).
- **Footer**.

**Per-agent tree line** (`_agent_line`): `<glyph> <label> [↻<attempt>]  <model_short> · <tokens>tok ·
<tool_calls>tc · <last_tool> · [STALL <n>s]`. Glyphs/styles: `◔` running (yellow), `✓` done (green),
`✗` error (red), `·` idle (grey).

**Per-run tree line** (`_run_label`): a flag glyph (`⚠` error/stall · `↻` retry · `●` active · `·`
terminal) + name + wf_id + `done✓ error✗ running◔/total` + status + tokens.

**Triage** (`_agent_priority` / `_display_runs` sort): errored → stalled (idle > 90s while
running) → retrying → running → idle → done, so problem agents float to the top of their phase and
problem runs float to the top of the fleet.

**Filters TODAY (exactly two axes):**
1. **Text filter** (`_fuzzy`, case-insensitive subsequence) over `name + wf_id + session` and agent
   `label`.
2. **Status chips** — the 4 buckets `running/done/error/idle`, each toggled on/off.

**Keybinds:** `q` quit · `f` toggle live-follow · `r` force refresh · `e` export selection.

**Scale caps:** `MAX_RUNS=80`, `MAX_AGENTS_PER_RUN=50` (hidden agents summarized as "… +N more
(triaged)"), `BACKFILL=14` feed events on select, `DETAIL_CHARS=8000`, `STALL_MS=90_000`.

**Plaintext board** (`wfmon board` → `workflow_run.py __main__`): one rollup line + the 8 most
relevant runs (active first): `flag wf_id name status  done✓ error✗ running◔/total  tok`. CI-friendly,
no TUI.

**Export** (`e` keybind or `wfmon export <wf_id> [opts]`): snapshots a run/subset/agent to a
self-contained, secret-redacted **Markdown / HTML / PDF** report. Scope by **label-set** (`--scope
run|subset|agent`, `--agents L1,L2`). Every report renders the run's **fan-out DAG** (phase→agent +
phase→phase, mermaid + ASCII in md, inline in html) built purely from `model.phases`. Strict
fail-closed redaction (API keys, PATs, AWS/Slack tokens, JWTs, PEM, gitcrypt paths, home→`~`) with an
`N masked` audit banner. PDF ladder (typst→playwright→edge→chrome→pandoc→xhtml2pdf→fpdf2→html) never
raises. Read-only out-guard refuses any `--out` under `~/.claude/projects/**`. `ExportModel` is
immutable; renderers are pure functions of it (`model.py` is the ONLY filesystem reader).

---

## 4. "command-native" — interpretation + current state

Today wfmon is launched OUT-OF-BAND: a `.cmd` shim → a separate Python/Textual process in its own
terminal. It is NOT a Claude Code command; it does not appear in `/`-completion; it does not share
the session UI. "**command-native**" (the task's third improvement axis, and the CONTEXT anchor
"matching the native `/workflows` UX / monitored uniformly") most plausibly means: **surface wfmon as
a first-class command experience consistent with Claude Code** — e.g. a `/wfmon` (or
`/workflows monitor`) entry that opens the cockpit, and/or a monitor whose look-and-feel matches the
native `/workflows` panel so native and cross-vendor runs are "monitored uniformly." (Confidence on
this reading: MEDIUM — "command-native" is not defined in any file I read; it is inferred from the
Axis-C CONTEXT. Flag for the owner to confirm before building.)

Two concrete "command-native" gaps: (i) no slash-command / in-session entry (only `wfmon.cmd`); (ii)
the cockpit's vocabulary (chips, glyphs, tree) is wfmon-specific, not aligned to whatever the native
`/workflows` panel shows — so a user can't tell at a glance which board is native and which is ours.

---

## 5. Native-vs-ours: CURRENT STATE = none; how it COULD be derived

**Current state: there is ZERO native-vs-cross-vendor distinction anywhere in wfmon.** Grep across
the whole skill for `codex|cross-vendor|vendor|mcp__` returns only: a test-fixture whose run NAME is
`codex-chatgpt-signin-feasibility`, and prose using "native" to mean *Claude Code's own* manifest /
`/workflows` view. No `vendor` field on `WFAgent`/`WFRun`/`AgentExport`; no vendor glyph, chip,
column, or filter. Every run — native ultracode or Claude+Codex mingled — renders identically.

**Why it's hard:** "ours" rides the native engine (§1), so the manifest has no vendor field and the
`model` field is `opus/fable` for BOTH a pure-Claude agent AND a Codex-driving agent. The distinction
is not first-class anywhere the engine writes.

**Derivable signals (cheap → authoritative), all from data wfmon ALREADY parses:**
1. **`lastToolName` == `mcp__codex__*`** (manifest, per-agent) — a cheap hint an agent is currently
   in a Codex call. Present at manifest scale (no transcript read).
2. **Any `tool_use.name` starting `mcp__codex__`** in the agent's `agent_timeline()` — AUTHORITATIVE:
   proves the agent did cross-vendor work at some point. One pass over already-parsed events.
3. **Label convention** — if Axis-C standardizes "ours" to tag Codex lanes (e.g. `label:
   'codex:reproduce'` / a `cx:` prefix / a `[codex]` suffix), the monitor reads vendor straight off
   the label with zero heuristics. This is the anti-overfit-friendly lever: no new engine field, no
   new runtime — just a naming convention the workflow author already controls, plus the tool-scan as
   a fallback/confirmation.
4. **`model` string** — future-proofing: if a run ever records a literal non-Claude model id, treat
   non-`claude-*`/`opus`/`fable` as codex/other.

**Proposed derivation (design):** a pure `vendor(agent) ∈ {claude, codex, mixed}` computed once in
the shared `workflow_run.py` (so TUI + export + recall-workflow-agent all agree), from
label-convention ∪ codex-tool-presence, with `model` as a tiebreaker. Roll up per run:
`native` (all claude) · `cross-vendor` (≥1 codex) · `codex-only`. This mirrors the codebase's own
"ONE shared parser" discipline and adds NO new runtime.

---

## 6. integration_points — the monitor design for Axis-C

1. **Vendor as a first-class derived field, computed in the shared parser.** Add
   `WFAgent.vendor` (derived, not stored) + `WFRun.vendor_rollup` in `workflow_run.py`; both TUI and
   `wfmon_export` inherit it for free. Keep it a pure function (mirrors `_bucket`/`_state_bucket`).
   Source signals: label convention → `mcp__codex__*` tool scan → `model` tiebreak (§5).
2. **Vendor glyph/badge on every agent + run line** — e.g. a `◆C`/`◆X`/`◆±` marker next to the
   status glyph in `_agent_line`, and a `[native]`/`[cross-vendor]` tag in `_run_label`, so the
   distinction is visible without drilling in. This is the "CLEARLY distinguish" deliverable.
3. **A vendor filter chip row** alongside the existing status chips (`claude | codex | mixed`),
   reusing the exact chip toggle + `_display_runs` filter plumbing (`_status_on` → add a parallel
   `_vendor_on`). Cheap: the filter/chip machinery already exists; this is a second axis.
4. **Vendor column in the plaintext board + the rollup bar** (e.g. `… · 3 native / 2 cross-vendor`),
   and a vendor lane/legend in the **export fan-out DAG** (color/annotate codex agents) so a shared
   report also shows which lanes were cross-vendor.
5. **Codex sub-thread drill-down in the Feed/Result** — because a Codex lane's real work is a
   `mcp__codex__codex` tool_use/tool_result pair, surface the Codex thread id + its output inline
   (the timeline already pairs tool_use↔tool_result by id; just special-case `mcp__codex__*` for a
   richer render). Optionally cross-link to the codex-monitor (`/codex-monitor`) for the Codex side.
6. **"command-native" surface** — a `/wfmon` (or `/workflows monitor`) in-session entry that opens
   the cockpit, and align the cockpit's status vocabulary to the native `/workflows` panel so native
   and ours are "monitored uniformly" (CONTEXT anchor). Confirm the exact meaning with the owner
   first (§4).
7. **Keep it read-only + O(changed) + one-parser.** Every addition rides the existing manifest
   read; no new writer, no second runtime, no DB — consistent with the Axis-C anti-overfit anchor
   ("author reusable patterns on the native engine, don't build new infra").

---

## 7. gaps — missing views / filters / distinction

- **No vendor distinction at all** (the headline gap): no `vendor` field, glyph, chip, column, or
  filter; native ultracode and cross-vendor runs are indistinguishable in every view.
- **Only two filter axes** (fuzzy text + 4 status chips). Missing: vendor, model (`opus` vs `fable`),
  phase, session/project, active-only, has-error, stalled, retrying, token-threshold, time-window.
  Several of these are already computed (stall/retry/error flags) but not exposed as filters.
- **No phase-level or model-level rollup filter** (e.g. "show only Fable agents", "only phase X").
- **No Codex-thread awareness** — a `mcp__codex__*` tool call is rendered as a generic tool_use; the
  Codex thread id, status, and output are not first-class (no cross-link to codex-monitor).
- **Not command-native** — no slash-command / in-session entry; launched only via `wfmon.cmd` in a
  separate terminal; cockpit vocabulary not aligned to native `/workflows`.
- **No native-vs-ours in the export** — the DAG and cards don't mark which lanes were cross-vendor,
  so a shared report loses the distinction too.
- **No run-level "kind" label** distinguishing a gate workflow / research fan-out / cross-vendor
  execution — everything is a flat run list keyed only by name + status.
- **Schema-brittleness dependency** — the whole board (and any vendor derivation off `lastToolName`)
  rests on the CC-internal manifest schema (pinned v2.1.207); a CC upgrade that renames
  `lastToolName`/`workflowProgress` breaks both the board and the codex-detection hint. The
  transcript-scan signal (`agent_timeline`) is more robust than the manifest hint.
- **`agent_tail` hard-codes `D:\agent-monitor`** for the Feed renderer (fallback exists, but the
  primary path assumes that drive/dir) — a portability wart if Axis-C relocates the monitor stack.

---

## 8. Confidence + caveats (Sherman-Kent)

- Manifest/journal/transcript schema is the right data plane, and wfmon's current views/filters as
  described above: **HIGH** (read directly from source + verified fixtures).
- Native-vs-ours is entirely absent today: **HIGH** (grep-confirmed).
- The proposed codex-detection signals (`mcp__codex__*` in `lastToolName`/timeline; label
  convention): **HIGH** they exist in the data; **MEDIUM** that a label convention is the cleanest
  primary (depends on Axis-C standardizing how "ours" tags Codex lanes — an owner decision).
- Meaning of "command-native" and the exact native `/workflows` internal UI: **LOW/MEDIUM** —
  inferred from the Axis-C CONTEXT, not observed in any file. Flag for owner confirmation before
  building either the slash-command entry or any "match the native UX" work.
