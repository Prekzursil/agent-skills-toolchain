export const meta = {
  name: "goat-complete",
  description: "Close EVERY gap from the full inventory: cheap adoptions, STORM, effort plumbing, skill cherry-picks, ELN/chart, benchmarks, dataset grabs, health hardening - until nothing is missing",
  phases: [
    { title: 'Adopt', detail: 'cheap tool installs verified by main session after' },
    { title: 'Integrate', detail: 'effort levels, UI model map, inject breadth, skill ports' },
    { title: 'Data', detail: 'ChEMBL 37 light grabs + dataset registry' },
    { title: 'Harden', detail: 'watchdogs, dead-MCP triage, reconcile residue' },
    { title: 'Grill', detail: 'adversarial check of every runbook' },
    { title: 'Synthesize', detail: 'one ordered execution queue' },
  ],
};

const GROUND = `
STATE (2026-09-22 21:3x, all verified this session): GOAT stack fully green (goat_health 9/9; biomni_task oracle C10H13NO2; tier switching bm-model+cs-model live; keys converged realprekzursil 2b98b9a3 with auto-propagate failover; auto-approve ON; full internet ON; 94-server registry incl biomcp; deepagents+promptfoo installed; freephdlabor+academic-research-skills cloned to ~/source; skills.sh works).
REMAINING GAP LIST (the mission - close ALL of these; full detail in each lane):
A-cheap: jupyter-mcp-server (datalayer) | QUEST (OSU-NLP) | mcp.science | Medea (mims-harvard) | lifesciences-research (donbr) | chemdraw-mcp + mcp-server-chart (grab-on-use ok) | skill-pack cherry-picks (anthropics/skills, wshobson/agents, VoltAgent) via skills.sh
B-integrate: STORM (stanford-oval) report-writer on GLM | effort/thinking param plumbing through cs-model+bm-model | CS UI model selector -> GLM mapping (x-glm-model header route) | basic-memory stdio wrapper for CS sandbox (G-81) | MCP inject breadth (scholarly-access cluster WSL-native) | freephdlabor+academic-research-skills cherry-pick INTO CS org skills + A1 know-how | SAB first eval run (GLM judge)
C-data: ChEMBL 37 SDF+h5+fingerprints (NOT the 5GB SQLite - owner watch) | UniProt Swiss-Prot | nSIDES/TwoSides | BioGRID -> Biomni lake curated/ with manifest
D-harden: bm-start->health retry loop (race after WSL recycle) | portproxy watchdog (172.19.16.1:18765) | dead-MCP triage (huggingface 401, McpHub 404, dbx-ai, openalex-alt, breach-intel, burp 400) - REPAIR or park-with-reason, never delete | repo reconcile residue (nested_ram_gate.ps1, skills/biomni-local/ untracked) | MLflow-3 run tracking for A1/CS turns | semantic-entropy uncertainty scoring | GRADE certainty grading in research outputs
E-benchmarks: BixBench vs A1 | promptfoo smoke on GLM | Aviary LitQA run
HARD RULES: NEVER rotate keys. No secrets in output (sha8). Workflow agents have NO exec - produce runbooks with exact commands; the MAIN session executes everything and verifies. Commits = main session only. WSL quoting: scripts via Write tool then 'wsl -- bash < file'. Registry edits need credentialNames:[] + validate + sync_shared_state. UNVERIFIED inline. RAM-pressured box: sequential over parallel installs; every >60s op backgrounded.
OUTPUT CONTRACT: markdown; claims [VERIFIED probe]/[UNVERIFIED]; end with RUNBOOK: numbered steps, exact commands, SUCCESS: markers. <=500 words main + runbook.
`;

const COMMON = GROUND + `\nYou have Read/Grep/Glob/WebFetch/WebSearch - NO exec tools.\n`;

phase('Adopt');
const adoptLanes = await parallel([
  () => agent(COMMON + `LANE A1: exact install specs for jupyter-mcp-server, QUEST, mcp.science, Medea, lifesciences-research. For each: the precise uvx/pip/clone command, the env it belongs in (Windows .venvs or WSL conda), a 1-token import/handshake smoke, and - IF it should be a persistent MCP - the full agents.json row (targets/credentialNames/requiredEnv). Read the repos' READMEs via WebFetch for real entrypoints; do not guess flags.`, { label: 'adopt:spec-instant', phase: 'Adopt' }),
  () => agent(COMMON + `LANE A2: STORM integration spec. Read stanford-oval/storm README (WebFetch). Determine: pip install set, how to point its LLM+embeddings at the GLM coding plan (OpenAI-compat base https://api.z.ai/api/coding/paas/v4 + ZAI_API_KEY env; does STORM need an embedding model? if GLM lacks one, spec the fallback - local fastembed or a free embedding API already on the estate). Deliver a 'storm-report <topic>' runbook producing a cited report artifact in D:/Research/projects/<topic>/docs/.`, { label: 'adopt:storm-spec', phase: 'Adopt' }),
  () => agent(COMMON + `LANE A3: skill cherry-pick manifests. Read the cloned repos via Read on C:/Users/Prekzursil/source/freephdlabor and C:/Users/Prekzursil/source/academic-research-skills (dir structures + SKILL.md fronts). Produce: (a) the 10 highest-value skills to port INTO the CS org dir + A1 know-how distillations (phenibut-program-relevant first); (b) a skills.sh shopping list from anthropics/skills + wshobson/agents (WebFetch their dirs) - exact 'npx skills add owner/name' commands, capped at 10, no dupes vs the 358-skill SSOT.`, { label: 'adopt:skill-picks', phase: 'Adopt' }),
]);

phase('Integrate');
const integrateLanes = await parallel([
  () => agent(COMMON + `LANE B1: effort/thinking plumbing. Read ~/source/agent-skills-toolchain/scripts/claude-science/cs_glm_router.py (via Read on C:/Users/Prekzursil/source/...) + WebSearch z.ai docs for glm-5.3 thinking/effort params. Spec: cs-model effort high|max flag + bm-model flag wiring the param into every request; where the router must forward it.`, { label: 'integrate:effort', phase: 'Integrate' }),
  () => agent(COMMON + `LANE B2: CS UI model selector -> GLM tier mapping. Read the web-dist bundle (Read on /home/prekzursil/.claude-science/runtime/0.1.50-release/web-dist/assets/index-ConA6-ks.js is huge - Grep via the main session instead: document the exact grep patterns). Determine how the UI sends model choice (x-glm-model header? body model?) and spec the router change so 'Opus 5' UI selection maps to glm-5.3 flagship and lighter tiers to flash. UNVERIFIED marks where you could not read the bundle yourself.`, { label: 'integrate:ui-model', phase: 'Integrate' }),
  () => agent(COMMON + `LANE B3: basic-memory CS wrapper + inject breadth. Spec (a) a stdio-native FastMCP wrapper around basic-memory :18765 that runs INSIDE the CS sandbox via user_read_paths + local-mcp.json (G-81: basic-memory stays the sole writer; wrapper is read-mostly search/get) - WSL python, httpx to the socat bridge 127.0.0.1:18765... WAIT: sandbox is --unshare-net - the wrapper CANNOT reach the bridge either. Re-derive: the only viable route is the daemon-side env/credential injection or a hub-proxied tool. Spec honestly what IS possible; if nothing is, mark KILLED-ARCHITECTURAL with the evidence. (b) inject breadth: extend ~/Biomni/mcp_inject.yaml with WSL-safe stdio servers only (grep which scholarly-access-adjacent servers have WSL-native entrypoints).`, { label: 'integrate:bmem-inject', phase: 'Integrate' }),
  () => agent(COMMON + `LANE B4: SAB + benchmark protocol. Spec the first SAB eval run: sab-eval env + GLM env vars (ZAI_LITELLM contract), 3-task smoke subset (not all 102), judge on glm-5.3-flash, artifact to D:/Research/tools/. Include the BixBench-vs-A1 comparison protocol (what to install, what to run, cost estimate) and an Aviary LitQA one-shot.`, { label: 'integrate:bench', phase: 'Integrate' }),
]);

phase('Data');
const dataLanes = await parallel([
  () => agent(COMMON + `LANE C1: dataset grab runbook. Exact URLs+sizes from EBI FTP chembl_37 (SDF ~888MB, h5, fingerprints - NOT SQLite), UniProt Swiss-Prot (ftp.uniprot.org), nSIDES, BioGRID. Download into ~/Biomni/data/curated/<name>/ + sha256 manifest (mirror the 2026-09-21 lake-adds pattern). Sequential curl -f --retry, background, RAM-aware. SUCCESS: files non-empty + manifest written.`, { label: 'data:grabs', phase: 'Data' }),
]);

phase('Harden');
const hardenLanes = await parallel([
  () => agent(COMMON + `LANE D1: health hardening. Spec (a) bm-start retry loop: after spawn, poll :7870 up to 30s, one relaunch attempt on fail (edit ~/.local/bin/bm-start); (b) portproxy watchdog: a scheduled-task or goat_health extension checking 172.19.16.1:18765 reachability from WSL and re-adding the netsh rule (needs the exact rule command); (c) MLflow-3 run-tracking spec for biomni_task turns (mlflow server local, log prompt/model/tier/duration/artifact).`, { label: 'harden:health', phase: 'Harden' }),
  () => agent(COMMON + `LANE D2: dead-MCP triage + reconcile. Read C:/Users/Prekzursil/.agents/agents.json rows for huggingface, McpHub, dbx-ai, openalex-alt, breach-intel, burp. For each: the failure signature (this session's connection errors), a repair runbook (re-auth, URL fix, package check), or park-with-reason (never delete). Plus: the reconcile residue - scripts/nested_ram_gate.ps1 + skills/biomni-local/ untracked in agent-skills-toolchain; spec the scoped commit (main session commits).`, { label: 'harden:triage', phase: 'Harden' }),
]);

phase('Grill');
const grilled = await agent(COMMON + `GRILL all lane outputs below: kill wrong paths, quoting traps (Git-Bash vs PowerShell vs WSL), NEVER-ROTATE violations, agents-committing violations, RAM-unsafe parallel installs, registry rows missing credentialNames. Output per-lane SOUND / FIXED <correction> / KILLED <reason> + the riskiest assumption overall.
${JSON.stringify({ adoptLanes, integrateLanes, dataLanes, hardenLanes }).slice(0, 14000)}
`, { label: 'grill', phase: 'Grill' });

phase('Synthesize');
const queue = await agent(COMMON + `SYNTHESIZE into the FINAL execution queue. JSON only:
{"queue":[{"id","what","steps":[...],"risk","phase"}],"owner_decisions":[{"q","rec","why"}],"verify":[...]}
Order: safe cheap adoptions first, then data (background), then integrate, harden, benchmarks last. Cap 14 runbooks. Include EVERY gap - if a gap got KILLED by grill, it goes to owner_decisions with the reason, never silently dropped.
=== GRILLED === ${JSON.stringify(grilled).slice(0, 7000)}
=== RAW === ${JSON.stringify({ adoptLanes, integrateLanes, dataLanes, hardenLanes }).slice(0, 6000)}
`, { label: 'synthesize', phase: 'Synthesize', schema: {
  type: "object", required: ["queue", "owner_decisions", "verify"],
  properties: {
    queue: { type: "array", items: { type: "object", required: ["id", "what", "steps"], properties: { id: { type: "string" }, what: { type: "string" }, steps: { type: "array", items: { type: "string" } }, risk: { type: "string" }, phase: { type: "string" } } } },
    owner_decisions: { type: "array", items: { type: "object", required: ["q", "rec"], properties: { q: { type: "string" }, rec: { type: "string" }, why: { type: "string" } } } },
    verify: { type: "array", items: { type: "string" } },
  },
} });

({ queue, grilled, adoptLanes, integrateLanes, dataLanes, hardenLanes });
