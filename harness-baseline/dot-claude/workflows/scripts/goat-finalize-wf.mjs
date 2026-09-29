export const meta = {
  name: "goat-finalize",
  description: "Finalize CS+Biomni GOAT stack: model-tier switching both surfaces, access normalization, FULL skills port, MCP wiring, health, e2e verify",
  phases: ["lanes", "grill", "synthesize"],
};

// GOAT Finalization ultracode — 2026-09-22. Owner directive: fully fix + finalize
// CS + Biomni (consistent, healthy), wire all skills/MCPs/SOTA tools for BOTH,
// full resource + tool availability, glm-5.3-flagship <-> 5.3-flash switching on
// BOTH surfaces (+ effort levels), solve the key/access problem, full internet.
// Workflow agents = research/spec/verify (no exec); runbooks return to main session.

const GROUND = `
MEASURED STATE (2026-09-22, all receipts this session - trust over prose):
- Claude Science (CS): WSL daemon 127.0.0.1:8000, v0.1.50. Connector "local:biomni-a1" connected+healthOk, TOOL-CALL-PROVEN (in-CS biomni_status -> "lake=... tools=224"). 56 connectors total.
- Sandbox facts: bwrap --unshare-net; egress ONLY via per-sandbox proxy (3128 http / 1080 socks) gated by an allowlist; ~/.claude-science/config.toml [sandbox] user_read_paths grants /home/prekzursil/miniforge3/envs/biomni_e1 + /home/prekzursil/Biomni. The sandbox NULLS *.env files (--ro-bind /dev/null) so the ONLY env route into a spawn is local-mcp.json's "env" field (daemon store, NOT re-read from file on spawn - API registration or daemon restart is the truth path).
- Network prefs (set this session): builtin-allowlist disabled=["*"], allowed-domains includes api.z.ai+*.z.ai, auto-switch-on-flag enabled=true (auto-approve classifier). Prefs need daemon restart to reach new sandboxes.
- Model plane: CS UI agent -> two-plane GLM router (~/source/agent-skills-toolchain/scripts/claude-science/cs_glm_router.py, :8231, env CS_GLM_MODEL default glm-4.6, started by cs-model glm). OPERON turns ride it fine.
- Biomni: A1 agent, BIOMNI_LLM env (glm-5.3-flash default), key BIOMNI_CUSTOM_API_KEY from ~/Biomni/.env (outside sandbox) or local-mcp.json env (inside). Direct stdio e2e: init ok, task ran with NO 429/NO connection error; answer loop needs >420s window (placeholder returned).
- Keys: prekzursil1993 EXHAUSTED (429, resets 2026-09-26 17:26). realprekzursil HEALTHY (200 on glm-5.3, glm-5.3-flash, glm-4.6 - probed this hour). ACTIVE ZAI_API_KEY (user env) is a THIRD value (sha8 2b98b9a3) - unexplained, investigate. ~/Biomni/.env holds realprekzursil (sha8 5c264c5d).
- Failover machinery (just hardened): ~/.agents/scripts/zai_key_failover.py now calls _propagate_biomni(key) on every apply -> wsl zai_biomni_key_propagate.sh (rewrites .env + local-mcp.json env, kills stale sandbox children, restarts web app). NEVER-ROTATE: selection only.
- Skills SSOT: C:\\Users\\Prekzursil\\.agents\\skills (358 skills) - /deep-research /gem-hunt /grill-me-extensive live here. CS has its OWN Skills system (Settings > Skills; org skills dir ~/.claude-science/orgs/<org>/skills, mounted read-only in sandbox). Biomni accepts know-how docs in its datalake (~ know-how documents loaded into system prompt).
- biomni_hub MCP exposes biomni_inject_mcp (inject estate MCP servers INTO the A1 agent) - live in this session's tool inventory.
- Health: basic-memory needs a netsh portproxy (172.19.16.1:18765->127.0.0.1:18765) that can get wiped; bm-start/bm-stop/bm-health (WSL ~/.local/bin); CS watchdog scheduled task; WSL wedged once tonight (recovered via wsl --shutdown).
HARD RULES: NEVER rotate/regenerate keys (selection only). No live secrets in output - sha8 prefixes. cite file:line or exact probe for every claim. UNVERIFIED must be inline.
`;

const COMMON = GROUND + `
OUTPUT CONTRACT: markdown only. Every claim tagged [VERIFIED <probe>] / [UNVERIFIED]. End with RUNBOOK section: numbered steps executable by a shell-capable agent (exact commands/paths), each step with a SUCCESS: marker. <=600 words main + runbook. You have NO execution tools - spec/verify-by-reading only; runbooks are for the main session.
`;

const lanes = [
  { id: "model-switch", p: COMMON + `
LANE: model-tier switching on BOTH surfaces.
Deliver: (1) CS router default glm-5.3-flagship plan: exact edit in cs_glm_router.py (GLM_MODEL default), how UI model selector maps (claude-* names -> GLM), effort-level passthrough options z.ai supports (thinking/effort params on glm-5.3 - research from z.ai docs), and how to flip flash/flagship per-session. (2) Biomni bm-model verb spec: a WSL-side toggle (edit BIOMNI_LLM in ~/Biomni/.env + local-mcp.json env + kill children + restart web app - mirror zai_biomni_key_propagate.sh) supporting glm-5.3 | glm-5.3-flash with optional effort env. (3) A per-job override path: how a single CS message can demand flagship vs flash. Note the flash "free-use" lane (coding-plan flash quota) as the default cheap lane.` },
  { id: "access-keys", p: COMMON + `
LANE: access normalization. Deliver: (1) explanation + resolution plan for the THREE key values (prekzursil1993 sha8 2cbe00c7-era, realprekzursil sha8 5c264c5d, active ZAI_API_KEY sha8 2b98b9a3 - check ~/.agents/secrets/zai-coding-plan.env + zai-key-state.json for history). (2) The end-to-end 429-recovery protocol as a runbook: probe -> rotate -> propagate (failover now does biomni automatically) -> daemon restart if needed -> verify with a 1-token call on each model. (3) The single-source-of-truth rule: which file wins where (user env ZAI_API_KEY for Claude Code; .env for biomni web; local-mcp.json for sandbox spawns). Flag any consumer still able to ride an exhausted key.` },
  { id: "skills-port", p: COMMON + `
LANE: FULL skills port to CS + Biomni. Deliver: (1) the CS skills format (read ~/.claude-science/orgs/d505b386-e298-408c-b479-5f1cf6d2fe2e/skills + runtime/0.1.50-release/skills for shipped examples - infer the format: filename/frontmatter/loading). (2) A triage of the 358-skill SSOT (C:\\Users\\Prekzursil\\.agents\\skills) into: PORT (high-value for CS agent: deep-research, gem-hunt, grill-me-extensive, plus research/science/compchem/verification skills), SKIP (harness-internal), DEFER. Cap PORT list at 25. (3) Runbook: copy + transform each PORT skill into the CS org skills dir (verify CS UI Settings>Skills shows them; note daemon reload needs) + drop compact know-how .md versions into the Biomni datalake know-how dir for A1 (find its exact path from ~/Biomni source: know-how documents loader).` },
  { id: "mcp-inject", p: COMMON + `
LANE: MCP wiring both ways. Deliver: (1) runbook for biomni_hub's biomni_inject_mcp to expose estate MCPs (openmm-md, rdkit, schrodinger, qdx-rush, scholarly-access) to the A1 agent - exact tool args + how A1 uses injected servers + how to verify. (2) CS-side: verify the GOAT-relevant connectors among the 56 are enabled (connectors list via /api/mcp-servers/connectors from a logged-in page - spec the check; the main session executes). (3) The basic-memory-in-CS problem: it CANNOT work as an mcp-remote localhost bridge under --unshare-net; spec a stdio-native alternative (a tiny FastMCP stdio wrapper over basic-memory's API, or CS Credentials/netrc route if one exists).` },
  { id: "health-consistency", p: COMMON + `
LANE: always-healthy operation. Deliver: (1) a single 'goat-health' check verb spec (one command checking: CS daemon+wedged, router :8231, biomni web :7860 + MCP :7870, basic-memory :18765 via portproxy, key health 1-token probe, sandbox connector spawn) with SUCCESS/FAILED markers. (2) Startup-order + self-healing map: what starts what (CS watchdog task, bm-start in WSL profile, router via cs-model glm, portproxy persistence), single points of failure, and the WSL-wedge recovery (wsl --shutdown + bm-start + watchdog). (3) RAM guardrails consistent with estate G-99 (reaper cadence, no fleets <8GB free).` },
  { id: "task-verify", p: COMMON + `
LANE: final e2e verification protocol. Deliver a single runbook: (1) long-window biomni_task settle (600s budget, expect a real answer - the 420s run returned the placeholder with NO errors, so egress+key are good). (2) in-CS verification without UI ambiguity: how to read the daemon log for fresh connect receipts + absence of new 'denied api.z.ai' lines + the MCPPool call evidence (the main session must NOT drive the user's live browser tab - spec log-only verification). (3) auto-mode + full-internet regression checks (GET the three prefs endpoints, expect enabled:true / disabled:["*"] / z.ai in domains). (4) The phenibut formula oracle: answer must contain C10H13NO2.` },
];

const results = await parallel(lanes.map(l => () => agent(l.p, { name: `lane:${l.id}` })));

const grill = await agent(COMMON + `
GRILL: adversarially review these lane outputs (below). Kill or correct anything unverified, wrong-pathed (e.g. edits to files the daemon does not read), or violating NEVER-ROTATE/no-secrets rules. Output: per-lane verdict (SOUND / FIXED-HERE <correction> / KILLED <reason>) + the single riskiest unvalidated assumption overall.
=== LANE OUTPUTS ===
${lanes.map((l, i) => `\n--- ${l.id} ---\n${JSON.stringify(results[i]).slice(0, 3500)}`).join("\n")}
`, { name: "grill" });

const plan = await agent(COMMON + `
SYNTHESIZE: merge grilled lane outputs into ONE execution plan for the main session. Output JSON only:
{"runbooks": [{"id": "...", "what": "...", "steps": ["..."], "risk": "low|med|high"}], "owner_decisions": [{"q": "...", "rec": "...", "why": "..."}], "verify": ["..."]}
Order runbooks by dependency (keys/models first, then skills port, then injection, then health). Cap 12 runbooks. Include the biomni 5.3-flagship toggle and the FULL skills port as first-class items.
=== GRILLED ===
${JSON.stringify(grill).slice(0, 6000)}
=== RAW LANE RESULTS ===
${lanes.map((l, i) => `\n--- ${l.id} ---\n${JSON.stringify(results[i]).slice(0, 2500)}`).join("\n")}
`, { name: "synthesize", schema: {
  type: "object", required: ["runbooks", "owner_decisions", "verify"],
  properties: {
    runbooks: { type: "array", items: { type: "object", required: ["id", "what", "steps"], properties: { id: { type: "string" }, what: { type: "string" }, steps: { type: "array", items: { type: "string" } }, risk: { type: "string" } } } },
    owner_decisions: { type: "array", items: { type: "object", required: ["q", "rec"], properties: { q: { type: "string" }, rec: { type: "string" }, why: { type: "string" } } } },
    verify: { type: "array", items: { type: "string" } },
  },
} });

const final = { plan, grill, lanes: Object.fromEntries(lanes.map((l, i) => [l.id, results[i]])) };
final;
