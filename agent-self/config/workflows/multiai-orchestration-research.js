export const meta = {
  name: 'multiai-orchestration-research',
  description: 'Find the best mature/SOTA tool for SEAMLESS multi-agent collaboration between Claude Code and Codex in one session/workspace (parallel cross-AI fan-out + native-feeling reporting, ultracode-like but cross-vendor). Evaluate the incumbent (AgentBridge), survey alternatives, vaporware-filter + grade, consolidate to a decision. 12 Fable search lenses -> Opus synthesis.',
  phases: [
    { title: 'Search', detail: '12 Fable lenses', model: 'claude-fable-5' },
    { title: 'Synthesize', detail: 'consolidate + decide' },
  ],
}

const GROUND = `
# SHARED GROUNDING — the question + the incumbent + the bar

## The owner's need (verbatim intent)
Find the BEST up-to-date, MATURE, SOTA tool/framework to work with **multiple agents from BOTH Claude Code and Codex (OpenAI), seamlessly, in the SAME session/workspace**. Requirements: **homogeneous + easy to use** ("as easy as talking live with other sessions"); **parallelize agents/subagents from BOTH AIs** (Claude AND Codex, and ideally more); **ultracode-like fan-out** (the owner's Claude "Workflow" tool fans out many parallel subagents) **but with Codex agents mingled with Claude's**, fanning out and **reporting back as natively as within Claude itself**; live cross-session talk. The owner runs Claude Code + Codex CLI locally, both wired to a shared \`~/.agents/harness\` (one Python dispatcher runs BOTH via \`--provider claude|codex\`) + shared \`AGENTS.md\` + a large MCP set.

## The INCUMBENT (installed, being evaluated for replacement): AgentBridge
\`@raysonmeng/agentbridge\` (github \`raysonmeng/agent-bridge\`, site quilin-ai.github.io/agent-bridge, MIT). "Local bridge for bidirectional communication between Claude Code and Codex inside the same working session." Runs a **daemon on 127.0.0.1:4502** (\`agentbridge claude\` in one terminal + \`agentbridge codex\` in another). Claude→Codex via MCP tools (\`reply\`/\`get_messages\`); Codex→Claude is **asymmetric** — Codex has NO send-to-Claude tool; the bridge transparently intercepts Codex's output and pushes it to Claude. **Owner's complaint: it "doesn't work quite seamlessly, and it fails"** — the :4502 daemon is currently DOWN/unreachable; the asymmetry + daemon-fragility make it not-seamless. A prior tool "agentchattr" was also tried (in memory). Decide: FIX AgentBridge, REPLACE it, or BUILD better on the shared harness.

## Your job (your lens below)
Fast, wide, CITED web research. Be an aggressive VAPORWARE FILTER — verify a tool ACTUALLY EXISTS + is MAINTAINED (real repo, recent commits, real users/stars, working demo) vs a README-only/abandoned/hypothetical project; grade confidence high/med/low; flag anything post-training-cutoff or single-source as lower. For EACH real tool you surface give: name + repo/URL, what it does, does it run **Claude Code AND Codex CLI together in one workspace** (or is it API-only / single-vendor?), how parallel/fan-out works, how seamless/easy (the owner's bar), maturity (stars/commits/last-release/2026-active?), and a one-line fit verdict for THIS owner. Prefer concrete tools over abstract advice. Output tight markdown.
`;

const LENSES = [
  { key: 'agentbridge-teardown', prompt: `LENS: **Teardown the INCUMBENT AgentBridge.** Web-research \`raysonmeng/agent-bridge\` (+ quilin-ai.github.io/agent-bridge): how it actually works (the :4502 daemon, the reply/get_messages MCP, the asymmetric Codex-interception), its ARCHITECTURE limits (why it isn't seamless: daemon-fragility, one-Claude-one-Codex pairing, no cross-AI FAN-OUT of many parallel subagents, the asymmetry). Is it actively maintained (recent commits, releases, issues about the failures the owner hits)? Is the owner's failure (daemon :4502 down, not seamless) a config/setup fix or a fundamental design limit? Verdict: fixable-and-keep, or replace?` },
  { key: 'terminal-multiplexers', prompt: `LENS: **Terminal/tmux multi-agent orchestrators.** Survey the 2026 tools that run MANY coding-agent CLIs side by side in one workspace: **Claude Squad**, **tmux-orchestrator**, **uzi**, **Conductor**, **Crystal**, **Sculptor**, **Terragon/terry**, **omnara**. Which run **Claude Code AND Codex together** (mixed vendors, not just multiple Claudes)? git-worktree isolation, parallel sessions, a unified view, seamless switching? Maturity + fit.` },
  { key: 'cross-ai-frameworks', prompt: `LENS: **Cross-vendor agent frameworks.** Microsoft **AutoGen** / **Semantic Kernel** / Agent Framework, **CrewAI**, **LangGraph**, **Google ADK**, **OpenAI Agents SDK / Swarm**, **Anthropic Agent SDK** — can any orchestrate **Claude Code + Codex CLI as agents together** (heterogeneous multi-vendor handoffs + parallel fan-out), or are they API-orchestration only (not the terminal CLIs)? Which best matches "ultracode-like fan-out but cross-AI"? Maturity + fit.` },
  { key: 'a2a-mcp-protocols', prompt: `LENS: **Agent-to-agent standards.** **Google Agent2Agent (A2A) protocol**, **MCP agent-to-agent / MCP sampling / agent-as-an-MCP-server**, **AG-UI**, ACP. Are these mature + adopted in 2026? Do Claude Code / Codex support them (so a Claude agent and a Codex agent talk/hand off natively)? Could a shared A2A/MCP bus give the seamless cross-AI collaboration the owner wants? Grade maturity.` },
  { key: 'multi-cli-boards', prompt: `LENS: **"Kanban/board for multiple AI coding agents" tools.** **Vibe-Kanban** (Bloop), **Conductor**, **Backlog.md**, **container-use** (Dagger), **Claude Squad**, **Async/Devin-style task boards**. Do they dispatch tasks to BOTH Claude Code and Codex agents in parallel from one board + report back? How seamless/easy for a solo power-user? Maturity + fit.` },
  { key: 'native-cross-invocation', prompt: `LENS: **Native cross-invocation paths.** \`openai/codex-plugin-cc\` (lets Claude Code delegate TO Codex — the owner has it) + Codex's native \`spawn_agent\`/subagents + Claude Code Teammates/Task/subagents. How close can the NATIVE tools get to seamless mixing (Claude spawning Codex agents + vice versa) WITHOUT a third-party bridge? Is there a symmetric Codex→Claude path? What's missing for true cross-AI fan-out?` },
  { key: 'worktree-parallel', prompt: `LENS: **Worktree / parallel-session managers for mixed agents.** **Worktrunk (wt)**, **uzi**, **Claude Squad**, **git-worktree** orchestration patterns, **Sculptor**, **Async**. Focus: running N parallel agents (some Claude, some Codex) each in an isolated worktree, coordinated + reported centrally. Which are mature + support mixed vendors? Fit for the owner's fleet/ultracode style.` },
  { key: 'build-on-harness', prompt: `LENS: **BUILD-vs-adopt on the owner's own harness (agent-harness-construction angle).** The owner's \`~/.agents/harness\` ALREADY runs both Claude + Codex (one dispatcher, \`--provider claude|codex\`) + shared AGENTS.md + a big MCP set, and they're building a \`codex-fleet-github\` MCP. Could a THIN layer — a shared event-bus MCP + a "spawn cross-AI subagent" tool + a unified reporting stream — give seamless cross-AI fan-out that's MORE homogeneous than any 3rd-party tool (since it rides their existing bus)? Sketch the minimal design. Weigh build-effort vs adopting a mature tool. Cite any OSS that already does exactly this so we don't reinvent.` },
  { key: 'maturity-shootout', prompt: `LENS: **Maturity + seamlessness shootout.** Across ALL the multi-agent/multi-CLI tools you can find (Claude Squad, uzi, Conductor, Crystal, Vibe-Kanban, AgentBridge, container-use, omnara, Sculptor, etc.), build a RANKED table by: (a) genuinely runs Claude+Codex TOGETHER, (b) parallel fan-out of many agents, (c) seamless/easy for a solo dev, (d) MATURE (stars, 2026-active, real users — vaporware-filter hard). Top 3-5 with the evidence. This is the head-to-head the owner needs.` },
  { key: 'ultracode-for-codex', prompt: `LENS: **"Ultracode fan-out but with Codex agents mingled."** The owner's Claude Workflow tool fans out many parallel subagents natively. What's the closest thing that fans out MIXED Claude+Codex subagents from one orchestrator with native-feeling reporting? Options: a Claude Workflow that spawns Codex via codex-plugin-cc / \`codex exec\` per agent; Codex's \`spawn_agents_on_csv\`; an external orchestrator. Which actually works today + is seamless? Concrete.` },
  { key: 'power-user-2026', prompt: `LENS: **What do 2026 power-users actually use** to run Claude Code + Codex (+ Gemini) together daily? Web-research blogs, HN/Reddit/X threads, "agentmaxxing", "parallel AI agents" writeups, YouTube setups. What's the DE-FACTO winning setup (tool + workflow) for seamless multi-AI coding? Cite the sources + note consensus vs hype.` },
  { key: 'wildcard-goldgem', prompt: `LENS: **Wildcard / gold-gem.** Find the genuinely NOVEL or under-the-radar approach to seamless multi-AI (Claude+Codex) collaboration a sharp power-user would adopt in 2026 that the obvious lenses miss — a new protocol, a clever MCP pattern, a niche-but-brilliant tool, a shared-context trick. One strong, cited find. Vaporware-filter it hard.` },
];

phase('Search');
log(`Fanning out ${LENSES.length} Fable search lenses on seamless Claude+Codex multi-agent tooling...`);
const findings = await parallel(
  LENSES.map((l) => () =>
    agent(GROUND + '\n\n---\n\n' + l.prompt, { label: `search:${l.key}`, phase: 'Search', model: 'fable' })
  )
);

phase('Synthesize');
const bundle = LENSES.map((l, i) => `## LENS: ${l.key}\n\n${findings[i] || '(no output — agent died)'}`).join('\n\n---\n\n');
const SYNTH = `
You are the SYNTHESIS agent (deep). Above are ${LENSES.length} Fable search lenses on the best tool for SEAMLESS multi-agent Claude-Code + Codex collaboration in one workspace (the owner's ultracode-but-cross-AI ask). The incumbent AgentBridge is fragile/asymmetric/not-seamless. Consolidate into a decision the owner will STEER (this is discovery+decide, NOT a build).

Produce authoritative markdown:
1. **Headline verdict** (4-6 sentences): the single best path — FIX AgentBridge, ADOPT a specific mature tool (name it), or BUILD a thin layer on the owner's dual-provider harness. Why.
2. **Vaporware-filtered maturity table**: the real, maintained, 2026-active tools that actually run Claude+Codex together, ranked by (runs-both / parallel-fan-out / seamless-easy / mature), each with repo + stars + a confidence grade. Kill the vaporware explicitly.
3. **Cross-lens convergence** (what ≥2 lenses agreed on = highest confidence).
4. **Tiered decision queue**: TIER-0 just-do-it · the recommended primary path · strong alternatives · build-vs-adopt call · DROP (incl. AgentBridge if it's a dead end, with the reason).
5. **Honest tradeoffs**: seamlessness vs power vs maintenance; what "as native as within Claude" realistically costs.
6. **A recommended decision + 4-6 steering questions** for the owner (each with your recommended default), to feed a follow-up grill-me-extensive.
Be decisive, cite the lens per claim, and converge — do not survey-dump.`;

const synthesis = await agent(GROUND + '\n\n=== SEARCH FINDINGS ===\n\n' + bundle + '\n\n=== END ===\n\n' + SYNTH, {
  label: 'synthesize:multiai-decision',
  phase: 'Synthesize',
});

return { synthesis, lensCount: LENSES.length, ok: findings.filter(Boolean).length };
