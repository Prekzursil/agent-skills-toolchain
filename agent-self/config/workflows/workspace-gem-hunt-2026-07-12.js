export const meta = {
  name: 'workspace-gem-hunt-2026-07-12',
  description: 'Extensive multi-lens workspace self-improvement sweep (~40 Fable lenses) -> verified tiered decision-queue for the grill',
  phases: [
    { title: 'Ground', detail: 'build the dedup-set + workspace map + other-sessions eval' },
    { title: 'Fan-out', detail: '~40 distinct Fable lenses: SOTA skills/MCPs/hooks/rules/frontier-harness/cross-domain/agentic-repair/prune/other-sessions/user-domain/AGI/wildcard' },
    { title: 'Synthesize', detail: 'dedup + cross-lens converge + verify load-bearing claims + tiered decision-queue doc' },
  ],
}

const HOME = 'C:/Users/Prekzursil'
const OUT = `${HOME}/.claude/gem-hunt-2026-07-12`

phase('Ground')
const GROUND_SCHEMA = { type:'object', additionalProperties:false, required:['dedupSet','workspaceMap','otherSessions'], properties:{ dedupSet:{type:'string'}, workspaceMap:{type:'string'}, otherSessions:{type:'string'} } }
const ground = await agent(`You are the GROUND phase of a workspace self-improvement gem-hunt. Read the LIVE workspace state and produce a compact dedup-set + map so ~40 downstream lens agents dedup instead of re-proposing what already exists.

Read (use Read/Glob/Grep; PowerShell for shell — Bash is broken):
- Hooks: ${HOME}/.claude/settings.json (the hooks block) + ${HOME}/.claude/hooks/ (list the scripts) + ${HOME}/.agents/harness/modules.py (the MODULE_ORDER + module classes — the shared behavior harness).
- Skills: list ${HOME}/.claude/skills/ (names) + note the vault/curation.
- MCPs: ${HOME}/.mcp.json (server list) + ${HOME}/.mcp.disabled.json if present.
- Memory: ${HOME}/.claude/projects/C--Users-Prekzursil/memory/MEMORY.md (the always-on index) — this lists BUILT gems + the concurrent OTHER-SESSIONS work (codex-fleet-github, multi-ai-mingle, codex-parity, harness-session-scoping-fix).
- Plan/decision docs if present: ${HOME}/.claude/AGENTIC-PERFECTION-PLAN.md, OPEN-THREADS.md, CONSOLIDATED-GEM-DECISIONS*.md, AGENTIC-WORKSPACE-ARCHITECTURE.md.

Produce:
1. dedupSet: the explicit lists — BUILT (hooks/skills/MCPs/harness-modules already present), PLANNED-unbuilt, ABSORBED/REJECTED (rejected components: 2nd orchestration runtime, vector-DB/KG memory, durable-execution engine, trained critic, observability SaaS, guardrail framework — per the anti-overfit meta-anchor). Be concrete (name them).
2. workspaceMap: a compact map of the harness bus (hooks → dispatcher/modules → memory layers → skills → MCPs) so lenses know what bus to ride.
3. otherSessions: what the CONCURRENT sessions built this period (from MEMORY.md + the notes) that this hunt should evaluate for adopt/reconcile (codex-fleet, mingle, harness fixes) + THIS session's learnings worth operationalizing (UI/UX-Figma-first [just added], adversarial-verify-caught-what-CI-missed, the licensing-default-swap pattern, RAM/worktree-OOM, the Workflow args-as-string gotcha).`, { label:'ground', phase:'Ground', schema: GROUND_SCHEMA })

phase('Fan-out')
const DEDUP = (JSON.stringify(ground) || '').slice(0, 7000)
const RUBRIC = `PER-FIND RUBRIC (for each gem): name · what-it-is · why-THIS-user(/domain) · how-to-build-or-adopt · source(CITE a paper/repo/URL) · value×effort(H/M/L each) · novelty-for-us · NATIVE-vs-BUILD tag. ANTI-OVERFIT GATE (reject a find unless it (a) rides the existing hook/skill/MCP/harness bus AND (b) does NOT reintroduce a rejected component [2nd orchestration runtime, vector-DB/KG memory, durable-execution engine, trained critic, observability SaaS, guardrail framework]); prefer "enable a native feature" / "fold into the existing dispatcher" over "new hook file / new MCP". Grade confidence; flag post-cutoff/secondary claims as lower-confidence. Return 5-12 concrete, DEDUPED (vs the dedup-set) finds. Be adversarially honest — a plausible-but-wrong or already-built find is worse than none.`
const CTX = `Workspace = Claude Code (Opus) + a shared Claude/Codex behavior harness (~/.agents/harness: hooks→dispatcher→modules for goal/secret/recall/anti-degen/claim-warning/subagent + the new design-tool-reminder), a curated skill vault, ~49 MCP servers, basic-memory (semantic) + an event-ledger (objective). Owner = power user (RE/security, media/video pro tools [Reframe], drug-discovery, Battle-Cats modding); values exhaustive-parallel ultracode, quality-no-faking, honesty, remember+research-by-default, plug-and-play UX. DEDUP-SET (do NOT re-propose these): ${DEDUP}`
const FS = { type:'object', additionalProperties:false, required:['lens','findings_markdown'], properties:{ lens:{type:'string'}, findings_markdown:{type:'string'} } }
const LENSES = [
  { key:'frontier-reliability', focus:'SOTA agent-RELIABILITY / self-correction / external-verification papers+repos (2025-2026, arXiv+GitHub): green-tested-but-non-functional repair, test-oracle generation, Agent-as-a-Judge, execution-grounded verification, reflexion/self-consistency that actually works. What raises real functional correctness on our TDD+adversarial-verify bus?' },
  { key:'frontier-memory', focus:'SOTA agent-MEMORY architectures (2025-2026): ACE, G-Memory, episodic/procedural/semantic splits, memory distillation, sleep-time compute. What improves our basic-memory + event-ledger WITHOUT reintroducing a vector-DB/KG store (rejected)?' },
  { key:'frontier-orchestration', focus:'SOTA multi-agent ORCHESTRATION (2025-2026): MaAS, GEPA, agent-topology search, verifier-in-the-loop, debate/consensus. What improves our Workflow fan-out + council WITHOUT a 2nd orchestration runtime (rejected)?' },
  { key:'frontier-eval', focus:'SOTA agent EVALUATION / external-signal verification (2025-2026): Agent-as-a-Judge, LLM-as-judge calibration, test-time verification, property-based/metamorphic testing for LLM code. Operationalize as harness hooks / verify agents.' },
  { key:'frontier-testtime', focus:'SOTA test-time compute / reasoning (2025-2026): tree/graph search, self-verification, best-of-N with verifiers, process reward. What is cheaply adoptable in our agent prompts/Workflow?' },
  { key:'frontier-tooluse', focus:'SOTA tool-use / function-calling / computer-use reliability (2025-2026). Patterns that reduce tool-call failure + hallucinated tools (we hit ToolSearch/MCP drift).' },
  { key:'skills-sota-coding', focus:'SOTA / best-voted OSS Claude-Code + Agent SKILLS for CODING/REVIEW (GitHub awesome-lists, Anthropic skills, high-star repos). Which beat our current coding/review skills? Adopt or upgrade.' },
  { key:'skills-sota-research', focus:'SOTA / best-voted RESEARCH + knowledge skills (deep-research variants, citation/verification skills). Upgrades to our deep-research harness?' },
  { key:'skills-sota-design', focus:'SOTA / best-voted DESIGN/UI-UX + Figma skills (this owner just flagged we under-use Figma/Claude-Design). Best design-review/transpose/token/a11y skills to adopt or upgrade — including the official Figma skills + design-review loops.' },
  { key:'skills-sota-security', focus:'SOTA / best-voted RE/SECURITY skills + workflows (the owner does RE). Best disassembly/triage/exploit/malware-analysis skill patterns to adopt.' },
  { key:'skills-sota-general', focus:'SOTA / best-voted GENERAL agent skills (planning, debugging, refactoring, docs, git). Best-of-breed to adopt/upgrade vs our vault.' },
  { key:'skills-anthropic-native', focus:'Anthropic OFFICIAL skills + skill-authoring best practices (2026): what patterns/skills from Anthropic + the skills ecosystem should we adopt or copy into our skill-authoring (skill-create/writing-skills)?' },
  { key:'mcp-sota-general', focus:'High-value OSS MCP servers to ADOPT (2025-2026, awesome-mcp, high-star): general dev/productivity MCPs that beat what we have. Tag NATIVE-vs-BUILD + the RAM/token cost.' },
  { key:'mcp-sota-domain', focus:'High-value DOMAIN MCP servers for the owner (RE, media/video, science/drug-discovery, browser). New ones since our fleet was curated?' },
  { key:'mcp-official', focus:'Official/first-party MCPs (Anthropic, vendors) + the MCP spec evolution (elicitation, sampling, resources) we under-use. ENABLE, not build.' },
  { key:'teardown-editors', focus:'COMPETITIVE teardown: Cursor / Windsurf / Zed / Junie features we lack (composer, rules, background agents, memories). Tag NATIVE-vs-BUILD.' },
  { key:'teardown-agents', focus:'COMPETITIVE teardown: Devin / Cline / OpenHands / Aider / Goose / Amp / Codex-CLI features we lack (planning, verification, sandboxing, multi-file). Tag NATIVE-vs-BUILD.' },
  { key:'native-cc', focus:'NATIVE-CAPABILITY audit: Claude Code features we UNDER-USE (hooks events, output styles, subagent defs, /commands, skills routing, plan mode, background tasks, statusline, MCP resources/prompts). ENABLE, do not build.' },
  { key:'native-sdk', focus:'NATIVE-CAPABILITY audit: Claude Agent SDK + API features we under-use (tool-runner, managed agents, prompt caching, structured outputs, extended thinking, computer-use). What to adopt in our subagent/Workflow layer?' },
  { key:'crossdomain-1', focus:'CROSS-DOMAIN borrows (highest-yield historically): mechanisms from CLINICAL MEDICINE / INTEL TRADECRAFT / EPIDEMIOLOGY (differential diagnosis, ACH, iatrogenics, triage, chain-of-custody) reusable as agent-reliability gems on our bus.' },
  { key:'crossdomain-2', focus:'CROSS-DOMAIN borrows: mechanisms from ECONOMICS/MECHANISM-DESIGN / CONTROL-THEORY / LAW-EVIDENCE / NEUROSCIENCE (incentive-compat, feedback control, evidentiary standards, predictive coding) reusable as agent gems.' },
  { key:'agentic-repair-1', focus:'THE core theme: why AGENTIC REPAIR ships GREEN-TESTED-BUT-NON-FUNCTIONAL software (this session proved adversarial-verify catches what CI cannot — the Export cosmetic-destination honesty gap, contrast composites). SOTA external-signal harness upgrades (real-exec oracles, property tests, screenshot/e2e gates) to make our verify layer catch non-functionality BEFORE merge.' },
  { key:'agentic-repair-2', focus:'Functional-verification patterns for LLM-generated code beyond unit coverage: metamorphic testing, differential testing, mutation testing (we have mutmut/Stryker), invariant mining, real-artifact smoke gates. Which become harness hooks or required CI gates?' },
  { key:'rules-improve', focus:'Improvements to our RULES (~/.claude/rules + AGENTS.md behavior contract): missing/stale rules, better clarify-first / anti-tunnel / honesty / verification-before-completion mechanisms. What rule change measurably improves behavior?' },
  { key:'workflow-improve', focus:'Improvements to our WORKFLOW/orchestration (metaswarm 9-phase, superpowers, the Workflow tool patterns): better gates, decomposition, resume, cost-routing, the Workflow-args-as-string gotcha, cheaper fan-out. Concrete workflow upgrades.' },
  { key:'hooks-new', focus:'NEW HOOK ideas (PreToolUse/PostToolUse/Stop/UserPromptSubmit/SessionStart) that ride our dispatcher bus: reliability nudges, cost guards, auto-verify triggers, drift catchers. Fold into ~/.agents/harness modules, do NOT add standalone hook files if avoidable.' },
  { key:'agi-frontier', focus:'AGI-adjacent / frontier self-improvement: continual/curriculum learning for the harness, self-generated evals, world-model/planning, the closed failure->gem->verify->retire loop, auto-gem-mining, a capability-score. What is the NEXT self-improvement level (meta) that is real + rides our bus?' },
  { key:'prune-1', focus:'PRUNE/leanness (a hunt that only ADDS is a bloat engine): redundant/overlapping HOOKS + SKILLS to retire, per-turn tool/token bloat, latency. Cite the specific redundancy; verify it is truly redundant.' },
  { key:'prune-2', focus:'PRUNE/leanness: redundant/duplicate MCP servers, memory-layer overlap (basic-memory vs event-ledger vs .remember vs MEMORY.md), stale config. Consolidation recs (reversible).' },
  { key:'other-sessions-adopt', focus:'EVALUATE THE OTHER (concurrent) SESSIONS work (codex-fleet-github, multi-ai-mingle, codex-parity-config, harness-session-scoping-fix — see the ground/other-sessions): what is ADOPTABLE into the main harness, what needs RECONCILE (e.g. the mingle port 8810->8812 drift, the lifecycle-guard), what overlaps this session.' },
  { key:'this-session-operationalize', focus:'Operationalize THIS session learnings: the UI/UX-Figma-first reminder (just added — is the regex/coverage right? more triggers?), the licensing-default-swap pattern (a reusable "commercial-permissive-gate" skill/hook?), the adversarial-verify-in-Workflow pattern (a reusable skill?), the args-as-string Workflow gotcha (doc/lint?), RAM/worktree-OOM (a worktree-cap guard?).' },
  { key:'userdomain-re', focus:'USER-DOMAIN gems for RE/SECURITY (the owner does reverse-engineering): new SOTA RE tools/MCPs/skills (decompilers, taint, symbolic exec, LLM-assisted RE) since our RE harness was built.' },
  { key:'userdomain-media', focus:'USER-DOMAIN gems for MEDIA/VIDEO (Reframe + the flagships): SOTA local models/tools for active-speaker/dub/broll/transcript-editing that our flagship research may have missed, + video-editing agent patterns.' },
  { key:'userdomain-science', focus:'USER-DOMAIN gems for DRUG-DISCOVERY / COMPCHEM (the owner runs Schrodinger/compchem): new SOTA tools/MCPs/models + agent patterns for the science stack.' },
  { key:'userdomain-bc', focus:'USER-DOMAIN gems for game-modding / Battle-Cats RE (the owner mods BC): tooling/automation patterns that help the BC/game-RE workflow.' },
  { key:'meta-selfimprove', focus:'META: the auto-gem-mining + closed self-improvement loop (failure-ledger -> gem -> verify -> retire), a capability-score dashboard, auto-eval generation. What META mechanism makes the harness improve ITSELF between sessions (real, on our bus)?' },
  { key:'wildcard-1', focus:'WILDCARD / GOLD-GEM: the genuinely novel cross-field thing NObody would prompt for — a mechanism, tool, or pattern that could be a step-change for this workspace. Be creative; cite; grade honestly.' },
  { key:'wildcard-2', focus:'WILDCARD 2 / plug-and-play UX: the owner values PLUG-AND-PLAY. What gem makes the whole workspace more turnkey / self-healing / zero-config (auto-recovery, self-diagnosis, one-command setup)?' },
  { key:'cost-budget', focus:'COST/BUDGET intelligence: model-routing (the owner wants big fan-outs cheap — Fable/Sonnet/Haiku routing), token-budget pacing, cache exploitation. SOTA cheap-fan-out patterns that keep quality.' },
  { key:'verification-gates', focus:'Pre-completion VERIFICATION gates: this session the Stop hook kept asking for evidence. Best patterns for evidence-before-claim, terminal-state outputs (SUCCESS/FAILED), and auto-running the smallest relevant check — as harness upgrades.' },
]
const findings = (await parallel(LENSES.map(l => () =>
  agent(`You are ONE lens of a big workspace gem-hunt. Your lens: ${l.key}.

FOCUS: ${l.focus}

${CTX}

${RUBRIC}

Use ToolSearch->WebSearch/firecrawl/exa/github + context7 for SOTA (2025-2026); READ the live workspace files where relevant (you may Read ${HOME}/.claude/... and ${HOME}/.agents/harness). Return findings_markdown = a concise markdown list of your 5-12 best DEDUPED finds, each with the full rubric. This lens is BLIND to the others — cover your angle exhaustively.`, { label:`lens:${l.key}`, phase:'Fan-out', schema: FS, model: 'fable' })
))).filter(Boolean)

phase('Synthesize')
const SYNTH_SCHEMA = { type:'object', additionalProperties:false, required:['docPath','tierCounts','topGems','summary'], properties:{ docPath:{type:'string'}, tierCounts:{type:'string'}, topGems:{ type:'array', items:{ type:'object', additionalProperties:false, required:['name','tier','rec','valueEffort','nativeVsBuild'], properties:{ name:{type:'string'}, tier:{type:'string'}, rec:{type:'string'}, valueEffort:{type:'string'}, nativeVsBuild:{type:'string'} } } }, summary:{type:'string'} } }
const synth = await agent(`Synthesize ${findings.length} lens findings into ONE tiered, DEDUPED, verified decision-queue for the workspace gem-hunt. Steps: (1) DEDUP across lenses; NOTE cross-lens CONVERGENCE (a find surfaced by >=2 independent lenses = highest-confidence). (2) Apply the anti-overfit gate + the dedup-set (drop already-BUILT or rejected-component finds). (3) Roll into TIERS: TIER-0 just-do-it(reversible) · TOP-GEMS · STRONG-TECHNIQUES · TOOLING(skills/MCPs) · RULES/WORKFLOW/HOOKS · PRUNE · PLANNED-unbuilt · SKIP — each item with a per-item REC + value×effort + NATIVE-vs-BUILD + a CITATION. (4) Write the FULL decision-queue markdown to ${OUT}/DECISION-QUEUE.md (create the dir; use Write) — this is the durable audit trail + the input to the grill. Return docPath + tier counts + the top ~12 gems (name/tier/rec/valueEffort/nativeVsBuild) + a 4-sentence summary.

Lens findings (JSON): ${JSON.stringify(findings).slice(0, 240000)}

Owner intent: exhaustive-parallel ultracode · quality-no-faking · honesty · plug-and-play · remember+research. Ride the existing bus; prefer enable-native over new-build; prune too.`, { label:'synthesize', phase:'Synthesize', schema: SYNTH_SCHEMA, model:'opus' })

const VERIFY_SCHEMA = { type:'object', additionalProperties:false, required:['notes','refuted','confirmed'], properties:{ notes:{type:'string'}, refuted:{type:'array',items:{type:'string'}}, confirmed:{type:'array',items:{type:'string'}} } }
const verify = await agent(`ADVERSARIALLY VERIFY the top gems before the owner acts. For each of the top ~12 gems, check the load-bearing FACTUAL claims against reality: (a) is it ALREADY BUILT in the workspace (read ${HOME}/.claude/hooks, settings.json, skills, ~/.mcp.json, ~/.agents/harness/modules.py)? (b) does the cited paper/repo actually exist + say what's claimed (spot-check the highest-stakes 3-4 via WebSearch/github)? (c) does it violate the anti-overfit gate (reintroduce a rejected component)? Report notes + which gems you REFUTED (already-built / vaporware / overfit) + which you CONFIRMED. Default skeptical — a prune audit once called a router-referenced file "safe to delete".

Top gems (JSON): ${JSON.stringify(synth.topGems || [])}`, { label:'verify', phase:'Synthesize', schema: VERIFY_SCHEMA, model:'opus' })

log(`Gem-hunt: ${findings.length} lenses -> ${synth.tierCounts}; verify confirmed ${(verify.confirmed||[]).length}, refuted ${(verify.refuted||[]).length}`)
return { decisionDoc: synth.docPath, tierCounts: synth.tierCounts, topGems: synth.topGems, summary: synth.summary, verify: { refuted: verify.refuted, confirmed: verify.confirmed, notes: verify.notes }, lensesRun: findings.length }