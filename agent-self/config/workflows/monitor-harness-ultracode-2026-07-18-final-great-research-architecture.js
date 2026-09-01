export const meta = {
  name: 'monitor-harness-ultracode-2026-07-18',
  description: 'Design the best-of unified monitor (esp. codex-monitor visualisation) + harness/skills/rules/MCP/workflow-doctrine improvement queue, grounded in ULTRACODE research and this session',
  phases: [
    { title: 'Ground', detail: 'read ULTRACODE docs, audit all 3 monitor codebases, verify deployment, mine this session' },
    { title: 'Research', detail: 'SOTA TUI/observability, Windows signals, codex+mixed workflow doctrine, native-capability audit' },
    { title: 'Design', detail: 'unified monitor architecture + visualisation spec + harness queue + doctrine' },
    { title: 'Review', detail: '3 adversarial reviewers (feasibility / completeness / scope-alignment)' },
    { title: 'Synthesis', detail: 'one tiered decision queue + implementation plan written to disk' },
  ],
}

// ---------------------------------------------------------------------------
// H6 — per-agent timeout + stall heartbeat. Paste at the top of the workflow.
// Sandbox-safe: uses only injected globals (setTimeout/clearTimeout/log/parallel).
// No Date.now / Math.random / new Date() -> stays workflow_lint clean.
// SCOPE: unblocks the BARRIER. Does NOT kill the agent -- the dropped agent keeps
// running and keeps its concurrency slot until it dies on its own.
// ---------------------------------------------------------------------------
const H6_TIMEOUT_MS = 1800000; // 30 min; blueprint dispatch_timeout_seconds default
const H6_STALL_MS = 90000; // 90 s; B3 falsifier #22

// A typed drop-receipt (design item H3). NEVER return a bare null from a barrier:
// null is produced for at least three different causes -- user skipped the agent,
// the subagent died on a terminal error, and (here) our own timeout -- and
// .filter(Boolean) throws that distinction away, making "12 of 15 returned"
// unauditable.
function h6Receipt(endReason, label, ms, detail) {
  return {
    __h6: true,
    __endReason: endReason, // 'timeout' | 'threw' | 'null'
    label: label,
    ms: ms,
    detail: detail === undefined ? null : detail,
  };
}

function h6IsDrop(r) {
  return !!r && r.__h6 === true;
}
function h6Survivors(results) {
  return results.filter(function (r) {
    return !h6IsDrop(r);
  });
}
function h6Drops(results) {
  return results.filter(h6IsDrop);
}

// Emit one heartbeat line if the unit is still outstanding at H6_STALL_MS.
// Returns a canceller. This is an OBSERVATION ("still waiting"), not a verdict
// that the agent is hung -- the sandbox cannot see orchestrator state.
function h6Heartbeat(label, stallMs) {
  if (typeof setTimeout !== 'function') return function () {};
  const t = setTimeout(function () {
    if (typeof log === 'function') {
      log('H6 heartbeat: still waiting on ' + label + ' after ' + stallMs + 'ms');
    }
  }, stallMs);
  return function () {
    if (typeof clearTimeout === 'function') clearTimeout(t);
  };
}

// Bound ONE thunk. Always resolves -- never rejects, never returns undefined --
// so a barrier over wrapped thunks can no longer be poisoned by one unit.
async function withTimeout(thunk, ms, label, stallMs) {
  const lbl = label === undefined ? 'unit' : label;
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms;
  // Runtime-drift guard: if a future build stops injecting timers, degrade to a
  // plain await instead of dying with a ReferenceError at fan-out time.
  if (typeof setTimeout !== 'function') {
    try {
      return await thunk();
    } catch (err) {
      return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
    }
  }
  const stopBeat = h6Heartbeat(lbl, stallMs === undefined ? H6_STALL_MS : stallMs);
  let timer = null;
  const expiry = new Promise(function (resolve) {
    timer = setTimeout(function () {
      resolve(h6Receipt('timeout', lbl, budgetMs, null));
    }, budgetMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(thunk), expiry]);
  } catch (err) {
    return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
  } finally {
    // ALWAYS clear on the winning path too: an un-cleared timer stays in the
    // runtime's abort set and can hold the workflow open past its last agent.
    if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
    stopBeat();
  }
}

// A SETTLED barrier: same shape as parallel(), but one hung unit costs you that
// unit instead of the phase. Output is index-aligned with `thunks` and every
// slot is either a real result or a typed drop-receipt -- no nulls, no holes.
async function settle(thunks, ms, labels) {
  const nameOf = function (i) {
    return labels && labels[i] !== undefined ? labels[i] : 'unit-' + i;
  };
  const raw = await parallel(
    thunks.map(function (t, i) {
      return function () {
        return withTimeout(t, ms, nameOf(i));
      };
    }),
  );
  return raw.map(function (r, i) {
    // The runtime still yields null for a cause we never saw (a user skip).
    // Type it rather than filtering it away.
    return r === null || r === undefined ? h6Receipt('null', nameOf(i), ms, null) : r;
  });
}

const obj = (properties, required = []) => ({
  type: 'object', additionalProperties: false, required, properties,
})
const WORK_RESULT = obj(
  { digest: { type: 'string', description: 'The prompt-specific report or requested final status message.' } },
  ['digest'],
)
const runAgent = (prompt, options) => agent(prompt, { ...options, schema: WORK_RESULT }).then((result) => (result == null ? null : result.digest))

const OUT = 'C:\\Users\\Prekzursil\\.claude\\monitor-harness-ultracode-2026-07-18'
const TOOLCHAIN = 'C:\\Users\\Prekzursil\\source\\agent-skills-toolchain'
const GEMHUNT = 'C:\\Users\\Prekzursil\\.claude\\gem-hunt-2026-07-12'

// Verified ground truth discovered before this workflow launched. Every agent gets it so nobody
// re-derives it or contradicts it without new evidence.
const FACTS = `
VERIFIED GROUND TRUTH (established by direct inspection immediately before this workflow — treat as
high-confidence; contradict ONLY with fresh evidence you cite):

1. monitorcore IS ALREADY BUILT AND MERGED ON MAIN of ${TOOLCHAIN}:
   - tools/monitorcore/monitorcore/{contract,codex_source,codex_tail,agent_tail,agent_state,discovery,
     export,monitors,pdf,redact,render_html,render_md,report_doc,spawn,textsafe,timeline,watchdog}.py
   - contract.py defines a typed generic MonitorSource[P]/Snapshot[P] Protocol with SourceState
     StrEnum (idle/running/done/error/unreachable/stalled) + a signature-only Alert. Cardinal rule:
     poll() MUST NOT raise; degrade to a stale/unreachable snapshot instead.
   - skills/monitor-launcher/{mon.cmd,agentmon.cmd,monitors.toml} = a generalized 'mon <name>' launcher
     + registry. monitors.toml registers THREE monitors: wfmon (dir workflow-monitor, entry
     workflow_monitor.py, trigger_tool Workflow, autolaunch open), agentmon (dir run-agent-monitor,
     entry agentmon.py, trigger_tool Task, autolaunch remind), codexmon (dir workflow-monitor, entry
     codex_monitor.py, trigger_tool mcp__codex__codex, autolaunch open).
   - Merged via PR-B1 #75 (foundation), PR-B2 #76 (consolidation, retires tools/agent-monitor),
     PR-B3 #92 (codexmon). PR #83 (CodexSource adapter) was CLOSED as superseded by #92.
   - NOTE: 'git merge-base --is-ancestor' reports NO for these branches because they were SQUASH-merged
     (squash-merge false-ahead). The PR state (MERGED) is the truth, not ancestry.

2. THE LEGACY MONITOR IS WHAT /codex-monitor ACTUALLY LAUNCHES — a real gap:
   - C:\\Users\\Prekzursil\\.claude\\commands\\codex-monitor.md invokes
     C:/Users/Prekzursil/.local/opt/mingle/monitor/launch.ps1 (the Jul-12 legacy mingle monitor,
     codex_monitor.py ~29.7KB / ~689 lines), NOT 'mon codexmon' / monitorcore.
   - Today that legacy file was hand-patched to fix a ctx% bug (it used cumulative total_token_usage
     as the context-occupancy numerator instead of last_token_usage). That same fix already existed
     upstream in PR #92 — so the hand-patch duplicated upstream work into a legacy copy. Backup:
     codex_monitor.py.bak-ctxfix-20260718.

3. DEPLOYMENT GAPS (verify and quantify these, do not assume):
   - 'mon' is NOT on PATH (which mon -> not found), so the launcher is unreachable by name.
   - ~/.agents/skills/workflow-monitor/ (deployed 2026-07-18 00:25) contains workflow_monitor.py,
     workflow_run.py, wfmon.cmd — a directory listing did NOT show codex_monitor.py, even though
     monitors.toml registers codexmon with entry codex_monitor.py in that dir. If true, 'mon codexmon'
     is registered-but-undeployed and would fail. VERIFY THIS FIRST.
   - On main, skills/workflow-monitor/codex_monitor.py is only ~714 bytes => it is a thin shim that
     imports monitorcore, not the implementation. Confirm what it actually does.

4. A third monitor lineage exists: D:\\agent-monitor\\ (agent_monitor.py, agent_monitor_ui.py,
   agent_tail.py, watchdog.py) — the Claude-subagent monitor that PR-B2 explicitly RETIRED in favour of
   monitorcore. Treat it as a FEATURE DONOR, not a live target.

5. PRIOR RESEARCH TO REUSE (do not re-derive): ${GEMHUNT}\\ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md
   (49KB, 11 lenses, 117 findings, tiers T0/T1/T2 + self-improvement layer, buildable-vs-needs-Anthropic
   split) and ULTRACODE-HARNESS-SOTA-GRILL-LOG.md (9KB, converged decisions: G-1 Maximal scope, D1
   content-addressed resume cache, D2 soft-sentinel budget exhaustion, D3 HITL checkpoint + branch-aware
   interception, D4 hybrid receipt-typed gates, D5 patterns namespace, G-7 self-improve; plus the
   VERIFIED empirical fact that PreToolUse hooks do NOT reach Workflow subagents).

6. A separate 140-unit pure-Codex mega-audit is RUNNING RIGHT NOW at
   C:\\Users\\Prekzursil\\.claude\\harness-mega-audit-2026-07-18\\ (findings/A01..A10 complete so far).
   Do NOT duplicate its sweep. If you read its findings/ dir, treat them as additional input.

ANTI-OVERFIT ANCHOR (gate every recommendation): minimal architecture is deliberate. A proposal only
counts if it (a) rides the EXISTING bus (monitorcore MonitorSource / monitors.toml / hooks / skills),
and (b) does NOT reintroduce a rejected component (a 2nd orchestration runtime, vector-DB/KG memory,
durable-execution engine, trained critic, observability SaaS, guardrail framework). Prefer "enable a
native feature" and "fold into the existing adapter" over "new daemon / new MCP / new monitor".

ENVIRONMENT: Windows 11, PowerShell 7 primary + Git Bash. Python 3 stdlib-only is strongly preferred
for monitors (no venv). Free RAM on this box is TIGHT (~1GB) — a heavyweight TUI dependency is a real
cost, weigh it.
`

const RUBRIC = `
PER-FINDING RUBRIC (use for every recommendation):
  name / what it is / why THIS user specifically / how to build-or-adopt (concrete: file, function,
  command) / source cited / value x effort (H/M/L each) / novelty-for-us / NATIVE-vs-BUILD tag /
  confidence band (Sherman-Kent: almost-certain 90-99%, likely 55-80%, roughly-even 45-55%,
  unlikely 20-45%) + the evidence tag that justifies the band.
Be adversarially honest. Flag anything you could not verify as UNVERIFIED. Cite file:line or a URL.
`

const WRITE = (name) => `
WRITE YOUR OUTPUT TO DISK as well as returning it. Write the full deliverable to
'${OUT}\\${name}' with the **Write** tool. If a single call is too large, chunk with
Add-Content — never build a multi-KB literal inside a shell command string (Windows
32,767-char limit -> os error 206).
Then return a <=400 word structured summary as your final text
(NOT the whole doc — the doc is on disk).
`

// ---------------------------------------------------------------------------
// PHASE 1 + 2: Ground and Research run together — they are mutually independent.
// A barrier follows because Design genuinely needs ALL of them at once.
// ---------------------------------------------------------------------------
phase('Ground')

const GROUND = [
  {
    key: 'ultracode-queue',
    label: 'ground:ultracode-queue',
    prompt: `Read ${GEMHUNT}\\ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md IN FULL (49KB, 117 findings across 11 lenses).

Extract and organise EVERYTHING that bears on: (a) monitoring / observability / live visibility into running agents, (b) workflow orchestration mechanics, (c) Codex or cross-model cooperation, (d) harness self-improvement.

For each relevant finding give: its ID/name as written in the doc, tier (T0/T1/T2), a one-line what, whether it is AUTHOR-BUILDABLE or NEEDS-ANTHROPIC, and its current status if stated. Then flag which findings are ALREADY SATISFIED by monitorcore existing on main (see ground truth), which are still open, and which are now stale.

This is an extraction task — be complete and faithful to the source. Do not invent findings.`,
    out: 'ground/G1-ultracode-queue.md',
  },
  {
    key: 'ultracode-grill',
    label: 'ground:ultracode-grill',
    prompt: `Read ${GEMHUNT}\\ULTRACODE-HARNESS-SOTA-GRILL-LOG.md IN FULL (9KB) plus, if present, the generator script ultracode-harness-sota-wf_*.js under the Claude session workflows/scripts dir (search for it).

Produce the AUTHORITATIVE converged decision log: every decision (G-1, D1-D5, G-7, H1-H3 and any others), what was decided, the reasoning, and any verified empirical facts recorded (notably: PreToolUse hooks do NOT reach Workflow subagents — confirm how that was established).

Then answer precisely: which of those decisions constrain or specify a MONITOR (typed endReason, stall heartbeat, progress ledger, receipt-typed gates, HITL checkpoint/interception)? Quote the exact wording for each.`,
    out: 'ground/G2-ultracode-grill.md',
  },
  {
    key: 'monitorcore-audit',
    label: 'ground:monitorcore-audit',
    prompt: `Audit the monitorcore package on main of ${TOOLCHAIN}. Read every module under tools/monitorcore/monitorcore/ (contract, codex_source, codex_tail, agent_tail, agent_state, discovery, export, monitors, pdf, redact, render_html, render_md, report_doc, spawn, textsafe, timeline, watchdog) plus tools/monitorcore/README.md and its tests.

Deliver: (1) the real architecture — how MonitorSource/Snapshot/ReportDoc compose, how an adapter is registered, how rendering and export work; (2) what codex_source.py / codex_tail.py ACTUALLY capture from Codex (which fields, from ~/.codex rollouts and/or relay streams, and exactly how context-window % is computed — quote the code); (3) what the LIVE view looks like today (render_native) and how rich it is; (4) test coverage and quality gates; (5) an honest gap list: what it does NOT do that a great live cockpit would.

Use 'git show origin/main:<path>' to read files. Quote file:line for load-bearing claims.`,
    out: 'ground/G3-monitorcore-audit.md',
  },
  {
    key: 'legacy-mingle-audit',
    label: 'ground:legacy-mingle',
    prompt: `Audit the LEGACY mingle Codex monitor at C:\\Users\\Prekzursil\\.local\\opt\\mingle\\monitor\\ — read codex_monitor.py (~690 lines) in full, plus launch.ps1 and README.md.

Deliver a precise FEATURE INVENTORY: every thing it displays (per-thread prompt, tool-call/command list, elapsed + idle timers, token usage + ctx%, turn count, status running/idle/done/aborted), how it discovers threads (~/.codex/sessions rollout-*.jsonl AND %TEMP%\\codex-streams\\*.jsonl relay files — explain the merge), its refresh/keyboard model, its rendering approach (ANSI? curses? plain reprint?), and its failure modes.

Then the decisive question: WHAT DOES THIS LEGACY MONITOR HAVE THAT monitorcore's codexmon DOES NOT? Be specific and honest — this list is the feature-donor set for the consolidation. Also note anything the legacy one does BADLY that must not be carried over.

Quote file:line.`,
    out: 'ground/G4-legacy-mingle-audit.md',
  },
  {
    key: 'agentmon-donor',
    label: 'ground:agentmon-donor',
    prompt: `Audit the Claude-subagent monitor lineage as a FEATURE DONOR: D:\\agent-monitor\\ (agent_monitor.py, agent_monitor_ui.py ~21KB, agent_tail.py, watchdog.py, launch.ps1) and on main of ${TOOLCHAIN}: skills/run-agent-monitor/agentmon.py and skills/workflow-monitor/workflow_monitor.py (~34KB) + workflow_run.py.

Deliver: (1) what workflow_monitor.py (the 'whole-fleet ultracode cockpit', PR #71) renders and how — this is the closest thing we have to a native-/workflows-like experience, so describe its layout, its progress tree, its status typing, and its polling model in detail; (2) what agent_monitor_ui.py does better or differently; (3) what watchdog.py's stall/dead-man logic is and how it decides 'stalled'; (4) the donor list: specific UI/UX and mechanism ideas worth porting into a unified codex cockpit.

Quote file:line. Use 'git show origin/main:<path>' for repo files.`,
    out: 'ground/G5-agentmon-donor.md',
  },
  {
    key: 'deployment-verify',
    label: 'ground:deployment-verify',
    prompt: `VERIFY THE DEPLOYMENT STATE — this is a falsification task, report what is actually true.

Check and report each with the exact command output:
1. Does C:\\Users\\Prekzursil\\.agents\\skills\\workflow-monitor\\codex_monitor.py EXIST? If not, 'mon codexmon' is registered-but-undeployed and BROKEN. Confirm or refute.
2. What is in ~/.agents/skills/monitor-launcher/ (mon.cmd, agentmon.cmd, monitors.toml, SKILL.md)? Read mon.cmd — how does it resolve a monitor name to an entry script, and what happens when the entry is missing?
3. Is 'mon' reachable? Check PATH, check for shims in ~/.local/bin, ~/bin, and any PowerShell profile alias/function. How is the user SUPPOSED to invoke it?
4. Compare deployed ~/.agents/skills/workflow-monitor/* against 'git show origin/main:skills/workflow-monitor/*' — is the deployed copy current, and what is missing or stale? (Deployed timestamps are 2026-07-18 00:25.)
5. Read the monitor-autolaunch hook at C:\\Users\\Prekzursil\\.claude\\hooks\\codex-monitor-autolaunch (and any monitor autolaunch hook registered in settings.json). Does it fire? On what tool? Does it point at monitorcore or the legacy mingle monitor?
6. Read C:\\Users\\Prekzursil\\.claude\\commands\\codex-monitor.md and confirm it targets the legacy launcher.
7. What does scripts/sync-skills.ps1 on main do, and would running it fix the gaps you found?

Deliver a numbered GAP LIST, each with: what is broken, the evidence, the exact one-line fix, and the risk of that fix. This list must be immediately actionable.`,
    out: 'ground/G6-deployment-gaps.md',
  },
  {
    key: 'native-ux',
    label: 'ground:native-ux',
    prompt: `The user wants the codex monitor to feel like a NATIVE experience — explicitly: "have native experience to this, shells and signals monitors that you should have live to see them similar to native /workflows".

Study what 'native' means concretely in Claude Code on this machine: the /workflows live progress display (phase groups, per-agent rows, live status), the Monitor tool, TaskList/TaskOutput, background-task notifications, and the /agent-monitor and /compute-monitor commands at C:\\Users\\Prekzursil\\.claude\\commands\\. Read those command files. Also check ~/.claude/settings.json hooks for anything that surfaces live status.

Deliver: (1) a precise description of the native /workflows progress UX — what information architecture makes it feel live and legible (grouping, ordering, state glyphs, in-place update, what it deliberately omits); (2) the specific affordances a Codex cockpit must copy to feel native rather than bolted-on; (3) what CANNOT be replicated (e.g. rendering inside the chat transcript) and the best honest substitute; (4) how 'shells and signals' should surface — live view of spawned shells, child processes, exit signals — and where that data actually comes from on Windows.

Be concrete about the information design, not generic UI advice.`,
    out: 'ground/G7-native-ux.md',
  },
  {
    key: 'session-reflect',
    label: 'ground:session-reflect',
    prompt: `SELF-REFLECT on the current Claude Code session — the user called this session "very important for /self-reflect".

Read the session transcript at C:\\Users\\Prekzursil\\.claude\\projects\\C--Users-Prekzursil\\30bd50d4-5a72-4c19-8fd5-85b6430c7b7d.jsonl. It is large — sample it strategically (head, tail, and grep for error/failure/fix/root cause/wrong/corrected patterns) rather than reading it linearly.

Extract DURABLE, NON-OBVIOUS learnings only. Known highlights to verify and enrich (do not just restate them — find the generalizable rule and the evidence):
- CI gate root causes: ruff pinned 0.15.17 in CI vs 0.15.22 local (different formatting); agents run 'ruff check' but skip 'ruff format --check'; gitleaks-action resolves 8.24.3 so plural [[allowlists]] path waivers do NOT waive historical-commit findings, and mixing singular [allowlist] with plural [[allowlists]] silently falls back to defaults.
- squash-merge false-ahead: squash-merged branches still look unmerged by ancestry.
- 'gh pr checks' fails under a PAT ("Resource not accessible") while 'gh run list/view' works.
- Windows codex fan-out defects: Start-Process needs the native codex.exe (the .ps1 shim fails with "%1 is not a valid Win32 application"); managed policy overrides -s workspace-write so --dangerously-bypass-approvals-and-sandbox was required; -NoNewWindow shares the console so control-break propagates and kills children (-1073741510 / 0xC000013A) => -WindowStyle Hidden + detached; an uncapped agent with no explicit STOP criterion never exits.
- TWO false alarms by the assistant, both from acting on a single unverified signal: (i) reading cumulative total_token_usage as ctx% and concluding "ctx 100%", restarting the run twice on that false signal; (ii) reading stale cached file sizes as "0 KB, agents stuck" when the logs were actually 86-142KB and the processes were burning CPU.
- A count-inference error the USER caught: inferring "22 skills are redundant" from a manifest count (161 > 107) instead of doing a set-comparison; only 1 of 22 was actually present, 21 were net-new.
- Hook false positives blocking legitimate ops (a path guard matching "B:" inside echo text), and one silent abort that skipped a patch the assistant only caught by verifying.

For each learning give: the FACT (canonical, imperative, includes the WHY), type (pattern/gotcha/decision/api_behavior/security/performance/code_quirk), what it applies to, confidence, and WHERE it should live (a rules/*.md file, a skill, CLAUDE.md, or a basic-memory note). Reject the trivial and the PR-specific. Quality over quantity — 10 great learnings beat 40 mediocre ones.

Pay special attention to the meta-pattern: the assistant repeatedly acted on a single unverified signal and had to be corrected. Formulate the sharpest possible durable rule for that.`,
    out: 'ground/G8-session-learnings.md',
  },
  {
    key: 'harness-audit',
    label: 'ground:harness-audit',
    prompt: `Run a HARNESS AUDIT of the live setup. Inventory and assess, with evidence:
- Hooks: C:\\Users\\Prekzursil\\.claude\\hooks\\ and the hooks block of ~/.claude/settings.json, plus the shared harness at C:\\Users\\Prekzursil\\.agents\\harness\\. Which fire, which are dead, which are noisy or produce false positives (a path guard matching "B:" in echo text is a known real case), which block when they should inject (per AGENTS.md section 6: block ONLY dangerous, inject everything else).
- Skills: ~/.claude/skills/ (curated daily set) vs the full vault at ~/.agents/skills/. Count them, find duplicates, dead symlinks, and anything whose description would blow the skills context budget.
- Rules: ~/.claude/rules/common/*.md — are they current, contradictory, or missing a topic that keeps biting (Windows shell footguns, static-analyzer gotchas, agents/orchestration)?
- MCPs: ~/.mcp.json and the restructure artifacts at ~/.claude/mcp-restructure-2026-07-17/ (mcp-fleet.json, APPLY-managed-mcp.md, PREP-STATUS-2026-07-18.md). What is the current fleet size, tiering (daily vs on-demand), and what remains to apply?
- Workflows: what workflow scripts exist under the session workflows/scripts dirs, and what patterns recur?

Deliver a prioritised ISSUE LIST (each: issue, evidence file:line, impact, fix, effort) plus a short "what is genuinely good and should not be touched" section. Be honest about what you could not verify.`,
    out: 'ground/G9-harness-audit.md',
  },
  {
    key: 'codex-doctrine',
    label: 'ground:codex-doctrine',
    prompt: `Establish the DOCTRINE for using Codex properly from Claude, including MIXED Claude+Codex workflows. The user explicitly wants to know "how to use codex workflows properly and mixed workflows".

Ground it in what is actually configured and what actually worked on this machine:
- Read ~/.codex/config.toml (note: it has ~28 [mcp_servers.*] blocks — which is exactly why --ignore-user-config matters for fan-out) and ~/.codex/AGENTS.md if present.
- Read the live launcher that is running RIGHT NOW: C:\\Users\\Prekzursil\\.claude\\harness-mega-audit-2026-07-18\\launch.ps1, plus PLAN.md, a couple of specs/*.md and a couple of findings/*.md there. This is a working, battle-tested pure-codex fan-out — extract the pattern.
- Read the Layer-1 / Layer-2 architecture in C:\\Users\\Prekzursil\\.claude\\CLAUDE.md (codex mcp-server as native MCP vs mcp_agent_mail live peer channel) and the multi-ai-mingle skill if present.
- Check 'codex --help' and 'codex exec --help' for the current real flag surface.

Deliver a practical doctrine document: (1) WHEN to use native mcp__codex__codex vs detached 'codex exec' fan-out vs the mingle peer channel — a decision table with the honest limits of each; (2) the canonical detached fan-out recipe for Windows including every hard-won flag and WHY each is needed (--ignore-user-config, -m, -c model_reasoning_effort, -c web_search, --dangerously-bypass-approvals-and-sandbox, -C, --skip-git-repo-check, --disable multi_agent_v2, -o, prompt via stdin, native codex.exe, -WindowStyle Hidden, RAM-guarded rolling window, resume-by-skipping-existing-outputs); (3) how to write a UNIT SPEC that reliably terminates (explicit STOP/DONE criterion, output contract, read-only discipline) — with a template; (4) mixed-model patterns: which role Claude plays vs Codex, and 2-3 concrete mixed-workflow shapes worth standardising; (5) the failure modes and their signatures.

This should be good enough to become a skill. Quote real evidence.`,
    out: 'ground/G10-codex-doctrine.md',
  },
]

const RESEARCH = [
  {
    key: 'tui-sota',
    label: 'research:tui-sota',
    prompt: `Research the STATE OF THE ART in terminal dashboards / TUIs for live multi-agent monitoring, current as of 2026.

Cover: Python TUI options (Textual, rich.live, blessed, urwid, plain ANSI) with an honest trade-off table including startup cost, dependency weight, Windows Terminal compatibility, and whether they work stdlib-only; the visual grammar that makes live dashboards legible (sparklines, status glyphs, in-place diff rendering, sticky headers, progress trees, log tailing panes, flicker-free repaint); and concrete exemplars worth stealing from (k9s, lazygit, btop, ctop, gh dash, htop, Textual showcase apps) — for each, name the SPECIFIC interaction or layout idea worth porting to an agent cockpit.

Constraint to respect: this box is Windows 11 with ~1GB free RAM, and the existing monitors are Python-3-stdlib-only with no venv. A heavyweight dependency is a real cost — say clearly whether Textual is worth it here or whether a well-built ANSI renderer wins, and justify with evidence.

Cite sources with URLs. ${RUBRIC}`,
    out: 'research/R1-tui-sota.md',
  },
  {
    key: 'observability-sota',
    label: 'research:observability',
    prompt: `Research SOTA in AGENT OBSERVABILITY (2025-2026): OpenTelemetry GenAI semantic conventions, Langfuse, AgentOps, Braintrust, LangSmith, W&B Weave, Arize Phoenix, and any newer entrants.

For each: what data model do they use for an agent run (spans? events? typed lifecycle states?), what do they surface that a hand-rolled monitor typically misses, and what is their stall/failure taxonomy.

CRITICAL FRAMING: the anti-overfit anchor forbids adopting an observability SaaS or a heavyweight framework. So the deliverable is NOT "adopt X" — it is: which CONCEPTS and DATA-MODEL choices should a local stdlib monitor borrow? Specifically evaluate: a typed run/turn/tool-call event schema, terminal-state taxonomy (the existing SourceState is idle/running/done/error/unreachable/stalled — is that the right set?), token/cost accounting semantics (notably last-turn vs cumulative context occupancy, a bug this project just hit), stall and dead-man detection, and trace/replay for post-hoc review.

Cite URLs. Flag anything post-cutoff or secondary-source as lower confidence. ${RUBRIC}`,
    out: 'research/R2-observability-sota.md',
  },
  {
    key: 'windows-signals',
    label: 'research:windows-signals',
    prompt: `Research how to correctly OBSERVE AND SUPERVISE child processes on Windows from Python/PowerShell — the "shells and signals" half of what the user asked for.

Cover concretely: enumerating a process tree (WMI/CIM Win32_Process ParentProcessId, psutil vs stdlib alternatives), reading per-process CPU time and working set without a heavy dependency, detecting a process that is alive-but-idle vs alive-and-working (the exact technique that resolved a false 'stuck agent' alarm in this project was sampling CPU delta over ~20s — validate and improve that), Job Objects for reliable tree kill, console control events (CTRL_BREAK/CTRL_C) and precisely why -NoNewWindow causes control-break to propagate to children (exit code -1073741510 / 0xC000013A) while -WindowStyle Hidden with a detached process does not, CREATE_NEW_PROCESS_GROUP / DETACHED_PROCESS creation flags, and how to reliably tail a file being written by another process on Windows (sharing modes, buffering).

Deliver an implementable recipe section with real code snippets, stdlib-first, and a clear statement of what genuinely requires psutil. Cite docs. ${RUBRIC}`,
    out: 'research/R3-windows-signals.md',
  },
  {
    key: 'codex-cli-current',
    label: 'research:codex-cli',
    prompt: `Research the CURRENT OpenAI Codex CLI surface (2026) with emphasis on what a monitor can consume and what an orchestrator can drive.

Cover: the 'codex exec --json' event stream — what event types exist and what fields each carries (this is the single most important input for a monitor, so be exhaustive and precise); the rollout files under ~/.codex/sessions/**/rollout-*.jsonl — their schema, what token-usage fields they carry (total_token_usage vs last_token_usage semantics), and how a thread's model/context-window is recorded; 'codex mcp-server' mode and the tool surface it exposes (codex / codex-reply, threadId semantics); resume/continue semantics; sandbox and approval policy flags and how a managed/enterprise policy can override them; and anything new in recent releases relevant to fan-out or observability.

Prefer primary sources: the openai/codex GitHub repo, its docs and CHANGELOG, and the local install at C:\\Users\\Prekzursil\\AppData\\Roaming\\npm\\node_modules\\@openai\\codex (read its files and any bundled schema — local ground truth beats a blog post). Also run 'codex --help' and 'codex exec --help'.

Where local install and web docs disagree, say so explicitly and trust the local install. ${RUBRIC}`,
    out: 'research/R4-codex-cli.md',
  },
  {
    key: 'native-capability',
    label: 'research:native-capability',
    prompt: `NATIVE-CAPABILITY AUDIT — the highest-yield lens historically. What does Claude Code (and the Claude Agent SDK) NATIVELY support, as of 2026, that this workspace under-uses? The point is to ENABLE rather than BUILD.

Focus on the user's stated needs: live visibility into running work, monitoring, hooks, background tasks, workflows/orchestration, subagent management, task tracking, scheduling, notifications, and anything that surfaces status to the user.

Investigate systematically: read C:\\Users\\Prekzursil\\.claude\\settings.json and the installed plugins/commands; check the documented hook events and their payloads; check background-task and notification mechanisms; check what the Workflow tool exposes for progress reporting (phase grouping, labels, logging) and what it does NOT; and confirm the known limitation that PreToolUse hooks do not reach Workflow subagents (state how you verified it).

Deliver: a table of NATIVE-BUT-UNUSED capabilities (what it is, how to enable it, what it would replace, effort), and separately a short list of things that genuinely CANNOT be done natively and therefore justify building. Be rigorous about the boundary — a wrong "must build" here causes real waste. Cite official docs with URLs. ${RUBRIC}`,
    out: 'research/R5-native-capability.md',
  },
  {
    key: 'crossdomain',
    label: 'research:crossdomain',
    prompt: `CROSS-DOMAIN BORROW lens (historically the highest-yield lens in this program). Find mechanisms from fields OUTSIDE software agent tooling that would materially improve a live multi-agent cockpit and the harness around it.

Mine deliberately from: mission control / flight operations (telemetry hierarchies, go-no-go polling, caution-and-warning systems, the discipline of a single authoritative status board), ICU / clinical monitoring (alarm fatigue research and how it is countered, early-warning scores, trend-over-value display, escalation ladders), air traffic control (attention management, conflict detection, strip-based state), SRE and incident command (SLOs, error budgets, dead-man switches, the ICS command structure), industrial process control and SCADA (alarm rationalisation standards such as EEMUA 191 / ISA 18.2 — highly relevant to which agent events deserve an alert), and intelligence tradecraft (structured analytic techniques for status assessment under uncertainty).

For each borrow: the mechanism, the field it comes from, the concrete translation to this monitor or harness, and why THIS user (running 100+ parallel Codex agents on a RAM-tight Windows box, prone to acting on single unverified signals) specifically benefits.

Alarm rationalisation deserves special attention: this project just had two false-alarm incidents caused by a single unverified signal. What does the alarm-management literature prescribe? Cite it. ${RUBRIC}`,
    out: 'research/R6-crossdomain.md',
  },
  {
    key: 'mixed-orchestration',
    label: 'research:mixed-orchestration',
    prompt: `Research SOTA in MULTI-MODEL / CROSS-VENDOR agent orchestration (2025-2026) — running Claude and Codex (and potentially Gemini/Antigravity) cooperatively on one task.

Cover: published patterns and results for cross-model review, debate, and ensembling (does cross-vendor adversarial review actually beat same-model review? find evidence, and be honest if the evidence is weak); orchestrator-worker vs peer-to-peer topologies; how frontier harnesses (Cursor, Devin, OpenHands, Aider, Goose, Amp, Windsurf, Zed, Cline, Junie) handle multi-model routing and what they surface to the user about it; task-to-model routing heuristics grounded in each model's actual strengths; context/state handoff between vendors without a shared memory substrate; and cost/quota pacing across two independent subscriptions.

Then apply it here: this machine has a Claude Max subscription and a ChatGPT subscription (independent quotas), Codex mounted as a native MCP, a local peer-mail channel, and a proven detached codex-exec fan-out. Recommend 3-5 concrete mixed-workflow SHAPES worth standardising, each with the topology, which model does what and why, the handoff mechanism, and the failure mode to watch.

Respect AGENTS.md section 5: never pass a subagent's raw output as the next agent's prefix context — always a structured summary with the goal re-anchored. Cite sources. ${RUBRIC}`,
    out: 'research/R7-mixed-orchestration.md',
  },
  {
    key: 'wildcard',
    label: 'research:wildcard',
    prompt: `WILDCARD / GOLD-GEM lens. Your job is to find the genuinely novel, non-obvious thing that no other lens in this sweep will surface — the find that makes the user say "I would never have asked for that."

Context: the user runs a Windows workspace orchestrating 100+ parallel Codex agents plus Claude subagents and Workflows, with a hook-based harness, a skills vault, an event ledger, and semantic memory. Their standing intent is exhaustive parallel exploration, plug-and-play UX, quality over cost, honesty, and self-improving tooling. Their recurring failure mode is acting on a single unverified signal and tunnel-visioning on a detail.

Range widely. Consider: what a self-improving harness looks like when the monitor's own data feeds back into routing decisions; what becomes possible if agent runs are treated as a queryable dataset rather than logs; what an 'attention economy' design for a human supervising 100 agents implies (what should NEVER reach the human, and what must always interrupt); whether the cockpit should be predictive rather than reportive (ETA, anomaly, projected quota exhaustion); what a genuinely good post-mortem/replay experience would be; and any mechanism that would have PREVENTED this session's two false alarms structurally rather than by exhortation.

Be specific and buildable, not visionary hand-waving. 5-8 finds maximum, each held to a high bar. Cite anything real. ${RUBRIC}`,
    out: 'research/R8-wildcard.md',
  },
]

const groundResults = h6Survivors(await settle(
  GROUND.map((u) => () =>
    runAgent(`${FACTS}\n\n=== YOUR TASK (${u.key}) ===\n${u.prompt}\n\n${RUBRIC}\n${WRITE(u.out.replace('/', '\\\\'))}`,
      { label: u.label, phase: 'Ground' })
      .then((text) => ({ key: u.key, out: u.out, text }))
  ).concat(
    RESEARCH.map((u) => () =>
      runAgent(`${FACTS}\n\n=== YOUR TASK (${u.key}) ===\n${u.prompt}\n${WRITE(u.out.replace('/', '\\\\'))}`,
        { label: u.label, phase: 'Research' })
        .then((text) => ({ key: u.key, out: u.out, text }))
    )
  )
, H6_TIMEOUT_MS))

const ok = groundResults.filter(Boolean)
log(`Ground+Research complete: ${ok.length}/${GROUND.length + RESEARCH.length} returned`)

// A compact, structured digest of every upstream agent — per AGENTS.md section 5 we hand off
// structured summaries, never raw output as a prefix.
const digest = ok.map((r) => `----- [${r.key}] (full doc on disk: ${OUT}\\${r.out}) -----\n${r.text}`).join('\n\n')

// ---------------------------------------------------------------------------
phase('Design')

const DESIGNS = [
  {
    key: 'monitor-design',
    label: 'design:monitor',
    prompt: `You are designing THE HEADLINE DELIVERABLE: a unified, best-of agent cockpit whose flagship view is a dramatically better Codex monitor.

The user's words: "for me the /codex-monitor with much better visualisation than what it is now so yeah this is most important" and "have native experience to this, shells and signals monitors that you should have live to see them similar to native /workflows".

Design constraints that are NOT negotiable:
- It must ride the EXISTING monitorcore MonitorSource/Snapshot contract and the monitors.toml registry. Do NOT propose a fourth parallel monitor lineage — the whole point of PR-B1/B2/B3 was consolidation.
- Python 3 stdlib-only unless you make an explicit, justified case for one dependency.
- Windows 11, PowerShell 7, ~1GB free RAM.
- poll() must never raise; degrade to a stale/unreachable snapshot.
- Redaction-safe output (monitorcore has redact.py — use it).

Deliver a concrete DESIGN DOCUMENT:
1. Target architecture — how the legacy mingle feature set folds into codexmon behind MonitorSource; what changes in codex_source.py / codex_tail.py; what the shared renderer gains. Name real files and functions.
2. THE VISUALISATION SPEC — this is the centrepiece and must be genuinely detailed. Give the actual screen layout as ASCII mockups (at least a main board and one drill-down), the information hierarchy, the state glyph vocabulary, colour semantics, what updates in place vs scrolls, the refresh model, keyboard interactions, and how it degrades on a narrow terminal. Make it feel like native /workflows: phase grouping, live per-agent rows, terminal-state typing. Show, do not describe.
3. Shells and signals — how live child-process/shell state (alive/idle/working/stalled/died + exit signal) is captured on Windows and surfaced, using the CPU-delta technique validated in the research.
4. Alarm design — apply the alarm-rationalisation findings so this cockpit structurally prevents the two false-alarm incidents (single-signal ctx% misread; stale-file-size 'stuck agent' misread). Specify which signals require corroboration before they are allowed to display as a failure state.
5. The ULTRACODE decisions that apply (typed endReason, stall heartbeat, progress ledger, receipt-typed gates) — how each lands in this design.
6. Work-unit decomposition: ordered WUs, each with scope, files touched, test strategy, and acceptance criteria. Respect the repo's 100% coverage gate.
7. Explicit NON-goals and what you deliberately rejected, with reasons.

Base everything on the upstream findings below — especially the deployment gaps (fix those first, they are cheap and unblock everything) and the legacy feature-donor list.`,
    out: 'design/D1-monitor-design.md',
  },
  {
    key: 'harness-queue',
    label: 'design:harness-queue',
    prompt: `Produce the HARNESS IMPROVEMENT DECISION QUEUE covering the user's ask: "improve harness knowledge, skills, rules, mcps, workflows in general".

Synthesise across the upstream findings: the harness audit, the session self-reflect learnings, the ULTRACODE queue's still-open items, the native-capability audit, the cross-domain borrows, and the wildcard finds.

Deliver a TIERED decision queue:
- TIER 0 — just-do-it: reversible, cheap, high-confidence (deployment fixes, a stale command pointer, a missing rule, a wrong doc). Each must be a one-or-two-line concrete action.
- TIER 1 — high-value builds worth a wave.
- TIER 2 — worthwhile but deferrable.
- SKIP — things that surfaced but should NOT be done, with the reason (this section is mandatory; a queue that only adds is a bloat engine).

Cover these dimensions explicitly: hooks (false positives, block-vs-inject discipline), skills (what to add/retire/fix, and specifically which NEW skills this session's learnings justify — e.g. a codex fan-out skill), rules (what durable rule files need creating or amending), MCPs (the pending managed-mcp apply and fleet tiering), workflows (patterns worth standardising), knowledge/memory (what must be written to basic-memory and what belongs in the event ledger), and docs.

For every item: value x effort, confidence band, NATIVE-vs-BUILD, and dependencies on other items. Apply the anti-overfit anchor ruthlessly — call out anything that would reintroduce a rejected component.

Dedup hard against what already exists. Note cross-source convergence explicitly: an item surfaced independently by two or more upstream agents is the highest-confidence class and should be marked as such.`,
    out: 'design/D2-harness-queue.md',
  },
  {
    key: 'doctrine-doc',
    label: 'design:doctrine',
    prompt: `Write the CODEX + MIXED-WORKFLOW DOCTRINE as a finished, usable document — good enough to become a skill in the vault.

The user asked to know "how to use codex workflows properly and mixed workflows". Build on the upstream codex-doctrine grounding and the mixed-orchestration research.

Required sections:
1. Decision table — native mcp__codex__codex vs detached 'codex exec' fan-out vs the mingle peer channel vs a Claude Workflow: when each is correct, and the honest limits of each.
2. The canonical Windows detached fan-out recipe — a complete, copy-pasteable launcher with every hard-won flag explained (why each one exists, and what breaks without it). Include the RAM-guarded rolling window, resume-by-skipping-existing-outputs, and the detachment requirements.
3. The UNIT SPEC template — how to write a task spec that reliably TERMINATES and produces a parseable artifact: explicit STOP/DONE criterion, output contract, read-only discipline on the subject, no tool-call cap. Include a filled example.
4. Mixed-model workflow shapes — 3-5 standard topologies with a diagram, role assignment, handoff format (structured summary per AGENTS.md section 5, never raw output), and the failure mode to watch.
5. Failure catalogue — every known failure with its exact signature and fix (the .ps1-shim Win32 error, managed-policy sandbox override, control-break child kill, the no-exit-criterion stall, RAM starvation, and the observability traps: cumulative-vs-last token usage, stale file-size reads).
6. Verification discipline — how to tell a fan-out is genuinely healthy, requiring TWO independent signals before declaring a failure state.

Write it as documentation for a competent engineer who has not seen this session. Concrete commands, real paths, no hand-waving.`,
    out: 'design/D3-codex-doctrine.md',
  },
]

const designs = h6Survivors(await settle(
  DESIGNS.map((u) => () =>
    runAgent(`${FACTS}\n\n=== YOUR TASK (${u.key}) ===\n${u.prompt}\n\n=== UPSTREAM FINDINGS (structured summaries; full docs are on disk at ${OUT}) ===\n${digest}\n\n${RUBRIC}\n${WRITE(u.out.replace('/', '\\\\'))}`,
      { label: u.label, phase: 'Design' })
      .then((text) => ({ key: u.key, out: u.out, text }))
  )
, H6_TIMEOUT_MS))

const okDesigns = designs.filter(Boolean)
log(`Design complete: ${okDesigns.length}/${DESIGNS.length}`)

const designDigest = okDesigns.map((d) => `----- [${d.key}] (full doc: ${OUT}\\${d.out}) -----\n${d.text}`).join('\n\n')

// ---------------------------------------------------------------------------
// Adversarial review — the project's mandated plan-review gate (3 reviewers, all must pass).
phase('Review')

const LENSES = [
  {
    key: 'feasibility',
    prompt: `FEASIBILITY reviewer. Attack the designs on: does this actually work on THIS machine (Windows 11, PowerShell 7, ~1GB free RAM, Python 3 stdlib preference, an existing monitorcore contract with a 100% coverage gate)? Are the named files, functions and APIs real — spot-check the load-bearing ones against the repo and refute any that do not exist. Is the effort estimate honest? Is any step blocked by something the design did not notice (git-crypt in worktrees, the ruff 0.15.17 CI pin, the gitleaks 8.24.3 behaviour, hook guards that block writes to certain paths)? Does the work-unit decomposition actually sequence correctly?`,
  },
  {
    key: 'completeness',
    prompt: `COMPLETENESS reviewer. Attack the designs on omission. Did they address EVERY part of what the user asked for: self-reflect learnings captured durably, harness knowledge, skills, rules, MCPs, workflows in general, codex workflows and mixed workflows, native live experience for shells and signals, and — the headline — a materially better codex-monitor visualisation? Is the visualisation spec concrete enough to build from (real mockups, real state vocabulary, real interactions) or is it still hand-waving? Are the ULTRACODE converged decisions actually applied or just name-checked? What did every upstream agent collectively MISS?`,
  },
  {
    key: 'scope',
    prompt: `SCOPE AND ALIGNMENT reviewer. Attack the designs on overreach and drift. Apply the anti-overfit anchor hard: does anything reintroduce a rejected component (a second orchestration runtime, vector-DB/KG memory, durable-execution engine, trained critic, observability SaaS, guardrail framework)? Is anything being BUILT that a native capability already provides? Is anything being rebuilt that monitorcore already does — the single biggest risk here, given the assistant nearly rebuilt a monitor that already existed and already had the ctx% fix? Is the TIER-0 list genuinely reversible and cheap? Is the SKIP list honest and non-empty? Is the whole thing right-sized, or has it inflated into a program the user did not ask for?`,
  },
]

const reviews = h6Survivors(await settle(
  LENSES.map((l) => () =>
    runAgent(`${FACTS}\n\nYou are an ADVERSARIAL REVIEWER in a mandatory plan-review gate. Your default posture is skeptical: it is far more useful to find a real flaw than to approve. Do NOT be agreeable.\n\n=== YOUR LENS ===\n${l.prompt}\n\n=== THE DESIGNS UNDER REVIEW (full docs on disk at ${OUT}\\design\\) ===\n${designDigest}\n\nVerify load-bearing claims against the real repo and filesystem — read files, run commands. An unverified objection is worth little; a verified one is worth a lot.\n\nDeliver: a VERDICT (PASS / PASS-WITH-CHANGES / FAIL), then a numbered list of findings, each with: severity (blocking / major / minor), the claim, the EVIDENCE you gathered (file:line or command output), and the specific required change. End with the single most important thing the designs got wrong.`,
      { label: `review:${l.key}`, phase: 'Review' })
      .then((text) => ({ key: l.key, text }))
  )
, H6_TIMEOUT_MS))

const okReviews = reviews.filter(Boolean)
log(`Review complete: ${okReviews.length}/${LENSES.length}`)

// ---------------------------------------------------------------------------
phase('Synthesis')

const reviewDigest = okReviews.map((r) => `----- REVIEW [${r.key}] -----\n${r.text}`).join('\n\n')

const final = await runAgent(
  `${FACTS}\n\nYou are the SYNTHESISER. Produce the single authoritative deliverable for this whole sweep.\n\n` +
  `=== DESIGNS ===\n${designDigest}\n\n=== ADVERSARIAL REVIEWS (apply every blocking and major finding) ===\n${reviewDigest}\n\n` +
  `Write ONE consolidated document: a MASTER DECISION QUEUE + IMPLEMENTATION PLAN.\n\n` +
  `Structure it as:\n` +
  `1. BOTTOM LINE — 10 lines maximum. What is actually true about the current monitor situation (including the correction that monitorcore already exists and /codex-monitor points at the legacy one), and what the recommended course of action is.\n` +
  `2. TIER 0 — do-now, reversible, cheap. Each item: the exact command or edit, the expected result, the rollback. These should be executable in under an hour total.\n` +
  `3. THE MONITOR BUILD — the reconciled design after review, with the visualisation spec (keep the ASCII mockups — they are the point), work-unit decomposition, and acceptance criteria per WU.\n` +
  `4. HARNESS QUEUE — tiered, deduped, with cross-source convergence marked.\n` +
  `5. DOCTRINE — the codex + mixed-workflow doctrine, condensed to its actionable core with a pointer to the full doc on disk.\n` +
  `6. SELF-REFLECT CAPTURE — the durable learnings from this session, each with its destination (which rules file, which skill, which memory note), written in final form and ready to paste.\n` +
  `7. SKIP LIST — what surfaced but should not be done, with reasons.\n` +
  `8. OPEN QUESTIONS — anything genuinely requiring an owner decision, phrased as a concrete choice with your recommendation. Keep this short; decide what you can.\n\n` +
  `Rules: every review finding marked blocking or major must be visibly resolved (say how). Mark cross-source convergence — an item independently surfaced by two or more agents is the highest-confidence class. Attach a confidence band to forward-looking claims. Be honest about what remains unverified. Do not pad; density over length.\n` +
  WRITE('MASTER-QUEUE.md'),
  { label: 'synthesise:master', phase: 'Synthesis' }
)

return {
  ground: ok.length,
  designs: okDesigns.length,
  reviews: okReviews.map((r) => r.key),
  outputDir: OUT,
  master: final ? final.slice(0, 6000) : null,
}
