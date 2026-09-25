export const meta = {
  name: 'estate-gemhunt-cohesion',
  description: 'Audit the lanes the coherence audit did not touch, hunt SOTA capabilities the estate lacks, verify frontier practice multi-engine, and synthesize one cohesion target architecture',
  phases: [
    { title: 'Lanes', detail: 'audit the uncovered surfaces' },
    { title: 'Gems', detail: 'multi-lens hunt for missing SOTA' },
    { title: 'Research', detail: 'multi-engine frontier verification' },
    { title: 'Synthesis', detail: 'cohesion map + adopt/prune decision queue' }
  ]
}

const KNOWN = [
  'CONTEXT - this estate was just audited (2026-09-25). Do NOT re-derive these; build ON them.',
  'HOST: VM OFFLOAD-W2025 (disposable). HOME desktop-a60s9gp is READ-ONLY reachable via rclone remote homeC: (e.g. rclone lsf "homeC:/Users/Prekzursil/.agents"). Binary at C:/Users/prekzursil/.local/bin/rclone.exe. Ignore host-key NOTICE lines.',
  'PATHS: ~/.claude = real dir, in NO git repo on either host. ~/.agents = junction to C:/suite/payload/Users/Prekzursil/.agents and IS the git repo (github.com/Prekzursil/agent-skills-toolchain, branch live-capture/2026-09-02). ~/source/agent-skills-toolchain = symlink to payload, .git is a HOLLOW STUB tracking nothing.',
  'ALREADY FOUND (do not re-report as new): MCP fleet Claude-VM 88 / HOME 28 / Codex 13 / Cursor 8 / Gemini 0; HOME is a strict SUBSET of VM; VM transport 20http/68stdio(23 npx) vs HOME 22http/6stdio(0 npx); VM has 333 MCP procs / 20.51 GB, ~97% owned by 4 claude.exe sessions (per-session multiplication) while HOME has 109 procs, 0 session-owned, daemon-shaped; VM 1/10 hub endpoints listening vs HOME 11/12 (so the always-on architecture WORKS on home, the VM never inherited it); reap_orphan_mcp.ps1 is blind by construction (cmd/pwsh in $hostRootNames); 4 reapers with 3 safety policies; HOME has 115 tasks / 41 supervision-style / ~80 on Interactive token at PT2M-PT10M = the terminal spam; basic-memory-supervisor.log shows hundreds of relaunches with no root-cause line; bm-watchdog force-kills before relaunch destroying evidence; .agents/.gitignore ignores rules/ on a FALSE premise so the rules corpus is version-controlled NOWHERE; rules are NEVER @-imported by CLAUDE.md and there is no section 12, so authored rules are INERT; mcp_ram_audit.ps1 was fixed today (P1 applied).',
  'STILL UNAPPLIED: P2 reaper scope note, P3 one authoritative reaper, P4 restart ceiling/latch/evidence-capture, P5 un-ignore rules/, P6 real section-12 + loader lint, P7 .claude.json key normalization, P8 process-shape rewrite, P9 SSOT generator + singletonKey.',
  'OWNER CONSTRAINTS: single owner, quality > cost, Opus for substantive subagents, full rigor (no terse mode), no auto-apply without approval, never rotate credentials, private estate so local plaintext is fine but egress is the boundary.'
].join(' ')

const RULES = 'HARD RULES: READ-ONLY. No edits, writes, commits, process kills, task changes or config changes. Never print a credential VALUE. Be concrete and cite evidence (file path + line, or the exact command and its output). Mark anything unverified as UNVERIFIED rather than asserting it. Be concise - short claims, no essays. Return ONLY the schema object.'

const LANE_SCHEMA = {
  type: 'object',
  properties: {
    lane: { type: 'string' },
    inventory: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, evidence: { type: 'string' },
      severity: { type: 'string' }, category: { type: 'string' }
    }, required: ['claim', 'evidence', 'severity'] } },
    cohesion_gaps: { type: 'array', items: { type: 'string' } }
  },
  required: ['lane', 'inventory', 'findings']
}

const GEM_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    gems: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' },
      what_it_is: { type: 'string' },
      do_we_have_it: { type: 'string', description: 'yes | partial | no' },
      value: { type: 'string', description: 'high | medium | low' },
      effort: { type: 'string', description: 'low | medium | high' },
      verdict: { type: 'string', description: 'ADOPT | TRIAL | SKIP | ALREADY-HAVE' },
      why: { type: 'string' }
    }, required: ['name', 'do_we_have_it', 'verdict', 'why'] } },
    lens_summary: { type: 'string' }
  },
  required: ['lens', 'gems', 'lens_summary']
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    deliverable: { type: 'string' },
    analysis: { type: 'string' },
    ranked_actions: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } }
  },
  required: ['deliverable', 'analysis']
}

const LANES = [
  ['hooks-health', 'Audit EVERY hook: ~/.claude/hooks (+ _dispatch/manifest.json), .agents/hooks, and the hooks block in ~/.claude/settings.json. Which actually fire this session, which are dead/superseded, which contradict each other, which exist on only one host. Include the Stop gap-check, goal-reinject, pre-commit secret guard, autopush.'],
  ['commands-health', 'Inventory ~/.claude/commands (75 files) and .agents/commands. Which are live, stale, duplicated, or shadowed by plugin commands? Which have no owner or reference dead paths?'],
  ['agents-health', 'Inventory ~/.claude/agents (20 .md subagent types) + plugin-provided agent types. Which are used, which are dead, which duplicate each other or the built-ins? Check model/tool declarations for drift.'],
  ['workflow-library', 'Audit the saved Workflow library (~/.claude/workflows + any scripts dirs). How many saved, how many ad-hoc run journals, which are reusable vs one-shot? Is there any versioning, naming or quality convention? What would a real workflow library need?'],
  ['monitoring-stack', 'Audit the monitoring stack: monitors.toml, the cockpit/wfmon/agentmon launchers, monitor-autolaunch hook, taskwatch_monitor, agent-monitor. What is live, what is dead, what overlaps? Is there a single pane of glass or N half-built ones?'],
  ['memory-architecture', 'Audit the memory architecture end to end: basic-memory vault (D:/basic-memory, 720 notes) + the native auto-memory (~/.claude/projects/.../memory/MEMORY.md, 20.5KB vs a 24.4KB cap) + the five registers (TASKBOX/OPEN-LOOPS/DIRECTIVES/INVENTORY/RESEARCH-COVERAGE). Where do they overlap, contradict, or silently drop data? Is there one recall path or several?'],
  ['quality-gates', 'Audit code-quality and CI gating on the estate: what linters/scanners/gates exist (semgrep, lizard, gitleaks, trivy, qlty, codacy, deepsource, sonar), which are wired to anything, which are silent-pass. Is any of it actually enforced on this repo?'],
  ['multi-ai-lane', 'Audit the Claude<->Codex multi-AI lane: the codex mcp-server rail, mcp_agent_mail (127.0.0.1:18812), the multi-ai-mingle skill, codex-* skills. What is live vs tombstoned vs aspirational? Does the documented rail match reality?'],
  ['browser-rail', 'Audit the browser automation lane: browser-rail skill, playwright/playwright-cdp/playwright-extension MCPs, claude-in-chrome, chrome-devtools. Three+ overlapping rails - which is canonical, which are dead, what is the routing rule?'],
  ['research-stack', 'Audit the research stack: deep-research, research-ops, multilingual-search, the new RESEARCH-COVERAGE register + rules/common/research-coverage.md, plus search MCPs (exa/firecrawl/tavily/searxng/scrapegraph) and the scholarly stack. Is there ONE routing rule or several competing ones?'],
  ['statusline-tui', 'Audit the operator surface: statusline-command.sh (the two-line HUD), keybindings.json, output-styles, settings.json model/effort/picker config. What is bespoke, what would be lost, what is undocumented?'],
  ['plugin-ecosystem', 'Audit the plugin layer: 100 plugins across 10 marketplaces. Which overlap with estate-authored skills? Which re-expose MCP servers already configured? What is the policy for plugin-vs-estate precedence, and does one exist?'],
  ['skills-quality', 'Sample the skills corpus for QUALITY (not just count): frontmatter correctness, dead references, tombstones, skills that duplicate each other, skills referencing tools/paths that no longer exist. What fraction is rot?'],
  ['docs-contract', 'Audit the always-loaded governance docs (CLAUDE.md, AGENTS.md, AGENTS-RUNTIME.md, ~/AGENTS.md) for internal contradictions, dead references, stale measured claims, and the thin-docs budget (~14.7k always-on tokens). Which sections are provably false today?']
]

const GEMS = [
  ['claude-code-native', 'Which NATIVE Claude Code capabilities is this estate NOT using or under-using? Check current docs for: output styles, compact instructions, plugins, skills frontmatter features, hooks events, checkpointing/rewind, background tasks, subagent model/effort control, /context, sandboxing, MCP scope. Name what exists that they do not use.'],
  ['verification-sota', 'What is SOTA for VERIFYING agent output (beyond what this estate has)? Consider execution-grounded selection, adversarial verification, mutation testing, fail-first/red-proof, property-based checks, self-consistency, LLM-as-judge calibration. The estate already has claim-verify-gate, mutation-check, execution-grounded-bon, two-tier-verify, agent-as-judge - find what is MISSING or mis-wired.'],
  ['eval-harness', 'Does this estate have real EVALS? Hunt for benchmark/eval infrastructure (eval-harness skill, harness-bench, regression suites for the harness itself). What would a proper agent-harness eval look like and what is missing to run one? Without evals, how would they know a harness change helped?'],
  ['context-engineering', 'SOTA context engineering beyond what they have: progressive disclosure, retrieval over listing, tool-result offloading, sub-agent isolation, prompt caching discipline, memory tools, compaction steering. They already have ToolSearch, skill-budget 0.04, a semantic router, hubs. What is the next tier?'],
  ['orchestration-sota', 'SOTA multi-agent orchestration patterns they lack: DAG/dependency orchestration, blackboard/shared-state, debate/consensus, tournament selection, speculative execution, resumability, cost-aware routing, failure escalation. They have Workflow fan-out, pipeline, parallel, worktree isolation. What is missing?'],
  ['observability', 'SOTA agent observability they lack: tracing (OpenTelemetry for agents), per-run cost attribution, token accounting, replay/debugging, drift detection dashboards, structured event ledgers. They have an event-ledger, statusline quota, monitors. What is the gap?'],
  ['config-as-code', 'SOTA for managing agent config across machines: dotfile managers (chezmoi/stow), declarative config generation, drift detection, secret templating, reproducible bootstrap. Their config is hand-edited and unsynced. What should they adopt?'],
  ['knowledge-management', 'SOTA for agent knowledge/memory beyond a markdown vault: graph memory, temporal knowledge, retrieval evaluation, automatic distillation, contradiction detection. They run basic-memory (semantic markdown vault) and explicitly BANNED Mem0/Graphiti/LynxMCP/CORE. Respect that ban - find what is compatible with their choice.'],
  ['security-posture', 'What defensive/security engineering does the estate lack for ITS OWN harness: supply-chain checks on skills/plugins/MCP servers, untrusted-repo config auto-load protection, secret scanning in the loop, permission-mode discipline, audit trails. They have estate-deny-guard, pre-commit secret guard, owner-ops doctrine.'],
  ['reliability-patterns', 'Reliability patterns the estate lacks: health checks with backoff, circuit breakers, idempotent restarts, graceful degradation, crash-loop detection, evidence capture before restart. Their supervisors force-kill and never latch. What is the correct pattern set?'],
  ['developer-experience', 'What would make this estate NICER to operate day to day? Bootstrap/reproducibility, onboarding a new machine, one-command doctor, discoverability of 400+ skills, naming conventions, a real index. Judge the actual friction from the evidence.'],
  ['anti-patterns', 'ADVERSARIAL lens: what is this estate doing that frontier practice says NOT to do? Over-automation, watchdog zoos, config sprawl, 400+ skills with unclear routing, duplicated tooling, hand-edited generated files, unversioned deployed trees. Rank the anti-patterns by damage.']
]

const RESEARCH = [
  ['r-frontier-harness', 'What do the most advanced publicly-documented Claude Code / coding-agent setups do in 2026 that a single-owner estate could adopt? Focus on harness architecture, not vendor marketing.'],
  ['r-agent-evals', 'What is current best practice for EVALUATING an agent harness itself (not the model)? Benchmarks, regression suites, A/B on harness changes, measuring whether a skill/hook helped.'],
  ['r-context-frontier', 'What is the 2026 frontier in context engineering for long-running coding agents beyond compaction and tool-search? Cite primary sources.'],
  ['r-multiagent-reliability', 'What does current research/practice say about reliability in multi-agent systems: failure handling, partial results, verification, cost control, when fan-out HURTS?'],
  ['r-config-drift', 'State of the art for configuration drift detection and reconciliation across machines, applicable to agent/dotfile config.'],
  ['r-supervision', 'Correct supervision patterns for long-lived local services (health checks, backoff, crash-loop detection, latching, evidence capture) - what should replace a naive restart watchdog?'],
  ['r-skill-scaling', 'How do teams manage LARGE skill/tool libraries (hundreds) without dilution? Routing, progressive disclosure, retrieval, naming, deprecation.'],
  ['r-mcp-frontier', 'Current frontier for MCP at scale: gateways, registries, dynamic discovery, OAuth/scopes, server lifecycle management. What is standardizing?']
]

const SYNTH = [
  ['s-cohesion-map', 'Produce THE cohesion map: every place the estate contradicts itself across VM/REPO/HOME and across tools. Group by root cause, not by symptom. Name the 5 root causes that explain the most incoherence.'],
  ['s-target-architecture', 'Define ONE target architecture for the estate covering: config SSOT + generation, MCP lifecycle, skills/rules author-deploy-sync, supervision policy, memory/registers, and observability. It must be achievable by a single owner and must say what to DELETE, not only what to add.'],
  ['s-decision-queue', 'Produce a RANKED adopt/prune decision queue from all gems and lanes: each row = item, verdict (ADOPT/TRIAL/SKIP/DELETE), value, effort, and the ONE sentence that justifies it. Rank by (value / effort) with cohesion impact as the tiebreak. Be ruthless: most things should be SKIP or DELETE.'],
  ['s-sequencing', 'Given P2-P9 plus everything newly found, produce the correct ORDER of operations. What must happen first because other things depend on it? Where would acting early destroy information or capability? Include the explicit rule that hub liveness precedes any Tier-1 collapse.'],
  ['s-critic', 'ADVERSARIAL completeness critic: what did this entire sweep still MISS? Which lanes were audited thinly? Which claims rest on one measurement? What would a fresh auditor say we are still fooling ourselves about?']
]

phase('Lanes')
log('Auditing ' + LANES.length + ' uncovered lanes...')
const lanes = (await parallel(LANES.map(([k, p]) => () =>
  agent(KNOWN + '\n\n' + RULES + '\n\nLANE [' + k + ']: ' + p, { label: k, phase: 'Lanes', schema: LANE_SCHEMA })
))).filter(Boolean)
log('Lanes: ' + lanes.length + '/' + LANES.length)

phase('Gems')
const gems = (await parallel(GEMS.map(([k, p]) => () =>
  agent(KNOWN + '\n\n' + RULES + '\n\nGEM-HUNT LENS [' + k + ']: ' + p + '\n\nBe concrete about what THIS estate has vs lacks - check the filesystem before claiming something is missing. Verdict ALREADY-HAVE is a valid and useful answer.',
    { label: k, phase: 'Gems', schema: GEM_SCHEMA })
))).filter(Boolean)
log('Gems: ' + gems.length + '/' + GEMS.length)

phase('Research')
const research = (await parallel(RESEARCH.map(([k, q]) => () =>
  agent(RULES + '\n\nRESEARCH [' + k + ']: ' + q + '\n\nPer the estate web-search discipline use AT LEAST TWO independent engines (firecrawl, exa, tavily, searxng, context7) and reconcile them; name the engines and cite sources. Then state precisely how it applies to this estate:\n' + KNOWN,
    { label: k, phase: 'Research', schema: GEM_SCHEMA })
))).filter(Boolean)
log('Research: ' + research.length + '/' + RESEARCH.length)

const brief = JSON.stringify({
  lanes: lanes.map(l => ({ lane: l.lane, summary: l.inventory, findings: (l.findings || []).map(f => f.claim), gaps: l.cohesion_gaps || [] })),
  gems: gems.concat(research).map(g => ({ lens: g.lens, summary: g.lens_summary, gems: (g.gems || []).map(x => ({ n: x.name, have: x.do_we_have_it, v: x.verdict, why: x.why })) }))
}).slice(0, 120000)

phase('Synthesis')
const synth = (await parallel(SYNTH.map(([k, p]) => () =>
  agent(KNOWN + '\n\n' + RULES + '\n\nSYNTHESIS [' + k + ']: ' + p + '\n\nBase it strictly on this sweep brief:\n' + brief,
    { label: k, phase: 'Synthesis', schema: SYNTH_SCHEMA })
))).filter(Boolean)

return { lanes: lanes.length, gems: gems.length, research: research.length, synth, lane_results: lanes, gem_results: gems.concat(research) }
