export const meta = {
  name: "goat-parked-e2e",
  description: "Execute all parked GOAT items e2e: MCP-inject spec+execute, PDSP retry, SAB eval env, connectors verify, repo reconcile, daemon-store gate",
  phases: [
    { title: "Scout", detail: "signatures, URLs, drift - read-only discovery" },
    { title: "Grill", detail: "adversarial check of runbooks" },
    { title: "Execute", detail: "main-session runbook queue" },
  ],
};

const GROUND = `
MEASURED STATE (2026-09-22 20:2x, fresh):
- CS daemon healthy (:8000), GLM router :8231 (default glm-5.3/light flash), biomni web :7860 + MCP :7870 (tools=224, llm=glm-5.3-flash), basic-memory :18765 chain OK. goat_health = GOAT:HEALTHY 9/9. WSL was just recycled (free RAM 4.2GB) - the CS watchdog task + bm-start relaunch services; verify before depending.
- Keys converged: all stores on realprekzursil sha8 2b98b9a3 (200 on all 3 models); prekzursil1993 exhausted until 2026-09-26 17:26; failover propagates into .env+local-mcp.json automatically (prefers registry value).
- biomni_task works end-to-end (oracle: phenibut formula C10H13NO2 through the MCP tool; go() returns (history, solution) tuple - wrapper now reads it).
- PARKED ITEMS (this workflow's scope):
  1. MCP-inject into A1: biomni_hub MCP exposes biomni_inject_mcp - signature UNKNOWN (grep D:/opt or the hub source; the MCP hub at D:\\agent-monitor or McpHub). Estate servers registered Windows-side in C:\\Users\\Prekzursil\\.agents\\agents.json mcp.servers (93) but A1 runs in WSL bwrap sandbox - Windows exes cannot spawn there; candidates must be WSL-native or the hub proxies them.
  2. PDSP Ki DB dataset: https://pdspdb.unc.edu/pdspWeb/ unreachable twice from this box (2026-09-21); needs URL discovery (search the web for the direct export path) or browser-session retry.
  3. SAB eval env: ~/ScienceAgentBench (WSL), env sab has litellm 1.53.x + openai>=1.75 (httpx proxies-kwarg conflict when litellm tries 1.53-era); README wants a pip-tools eval env; needs era-matched pin set (litellm 1.53.x era wanted openai<1.55 + httpx<0.28) built in a NEW env (sab-eval), sab env left as-is.
  4. Connectors verify: CS /api/mcp-servers/connectors (authenticated: logged-in page + x-operon-csrf cookie header; from a CS page context fetch) - verify GOAT set present+connected among 56 (bioRxiv, ChEMBL, PubMed, biomni-a1, open-coscientist-lit-review...). Do NOT drive the user's browser tab; the daemon API needs a logged-in session - alternative: verify via local-mcp.json + agents.json on disk where possible and mark API checks as needing a page.
  5. Repo reconcile: live edits to commit (branch cursor/p2-loop-to-green-0db0 in C:\\Users\\Prekzursil\\source\\agent-skills-toolchain): skills/claude-science-local SKILL.md ALREADY committed (7855434cc). UNCOMMITTED live-side: scripts/claude-science/cs_glm_router.py (glm-5.3 default), ~/.agents/scripts/goat_health.ps1 + zai_key_failover.py propagate patch + zai_biomni_key_propagate.sh + bm-model (WSL ~/.local/bin - these live OUTSIDE the repo; decide: copy into repo scripts/ or document). Also WSL ~/Biomni patches (a1.py key-mask, biomni_mcp_server.py go()-fix, biomni_mcp_stdio.py, bm-start) - upstream repo is github snap-stanford/Biomni; local patches need a patches/ dir or notes. sync-from-live with -Drift FIRST (bare -Report json WRITES).
  6. Daemon-store both-states gate (RB-01): the daemon caches connector env at registration/load; prove the store vs file divergence settled (current: .env and local-mcp.json both 2b98b9a3, spawns verified receiving it via /proc/<pid>/environ).
HARD RULES: NEVER rotate keys. No live secrets in output - sha8 only. Commits: the MAIN session (interactive) may commit; workflow agents NEVER commit. Cite file:line or exact probe. UNVERIFIED inline.
`;

const COMMON = GROUND + `
OUTPUT: markdown. Claims tagged [VERIFIED <probe>]/[UNVERIFIED]. End with RUNBOOK: numbered steps for a shell-capable main-session agent (exact commands, Write-tool script files for quoting-heavy WSL bits), each with SUCCESS: markers. <=500 words + runbook. You have Read/Grep/Glob and web tools but NO exec.
`;

phase('Scout');
const lanes = [
  { id: "mcp-inject", p: COMMON + `
LANE: find biomni_inject_mcp. Locate the biomni_hub MCP server source (search D:\\ for biomni_hub / the FastMCP server exposing it; also C:\\Users\\Prekzursil\\source). Read the tool signature + how injected servers reach the A1 agent (hub-side spawn? config write?). Deliver the exact call shape + which estate servers are WSL-safe (basic-memory needs a stdio wrapper under G-81; scholarly-access is a Windows exe - likely NOT injectable; openmm/rdkit may exist WSL-side).` },
  { id: "pdsp", p: COMMON + `
LANE: PDSP Ki DB export URL discovery. Web-search for the NIDA/UNC PDSP Ki database bulk download (pdspdb.unc.edu pdspWeb; possible mirrors: pdsp.unc.edu, data on nigms or figshare). Find a direct CSV/TSV export URL and its license note. Deliver the curl command + expected size + a mirror fallback if the main site stays down.` },
  { id: "sab-env", p: COMMON + `
LANE: SAB eval-env pin set. Read ~/ScienceAgentBench README + requirements (via Read on \\\\wsl$ or D: mirrors if readable; else reconstruct from the known 2026-09-21 notes: repo OSU-NLP-Group/ScienceAgentBench, litellm==1.52.8 yanked). Web-check litellm 1.53.x dependency metadata for the era-correct openai/httpx pins. Deliver the exact mamba create + pip install command set for a NEW sab-eval env with pins that satisfy both litellm<1.54 and httpx<0.28, plus the GLM env vars (ZAI_LITELLM contract: base https://api.z.ai/api/coding/paas/v4, key from ZAI_API_KEY env, model glm-5.3-flash) and a 1-token smoke.` },
  { id: "verify", p: COMMON + `
LANE: connectors + daemon-store verification protocol. Deliver: (a) which of the 56 CS connectors can be verified WITHOUT a browser (local-mcp.json for locals; orgs DB via sqlite for others - read-only URI) and the exact sqlite query; (b) the API-check script for a logged-in page (JS fetch with x-operon-csrf - the main session runs it in an isolated CS tab, NOT the user's); (c) the RB-01 both-states design: how to prove spawn-env == file (the /proc/<pid>/environ read pattern, sha8-only).` },
  { id: "reconcile", p: COMMON + `
LANE: repo-reconcile plan. Read C:\\Users\\Prekzursil\\source\\agent-skills-toolchain state: git status/branch (Read .git/HEAD), list which live-side files have repo homes (cs_glm_router.py YES under scripts/claude-science/; goat_health.ps1 + zai_key_failover.py + propagate scripts live in ~/.agents/scripts - the repo mirror location? search repo for existing copies). For WSL ~/Biomni patches: propose a biomni-local/patches/ dir in the repo (or D:\\Research\\tools\\biomni-local receipts - check what exists). Deliver: ordered commit list (main session commits), sync-from-live -Drift command first, and what deliberately stays out-of-repo.` },
];
const results = await parallel(lanes.map(l => () => agent(l.p, { label: `scout:${l.id}`, phase: 'Scout' })));

phase('Grill');
const grill = await agent(COMMON + `
GRILL the five scout outputs below. Kill/correct: wrong paths, anything violating NEVER-ROTATE/no-secrets, commands that would mangle quoting (Git-Bash vs PowerShell vs WSL - scripts must go via Write-tool files), commits from agents. Output per-lane: SOUND / FIXED <correction> / KILLED <reason>, then the single riskiest assumption.
${lanes.map((l, i) => `\n--- ${l.id} ---\n${JSON.stringify(results[i]).slice(0, 3000)}`).join("\n")}
`, { label: "grill", phase: 'Grill' });

phase('Execute');
const queue = await agent(COMMON + `
SYNTHESIZE the grilled outputs into the main-session execution queue. JSON only:
{"queue":[{"id","what","steps":[...],"risk"}], "owner_notes":[...], "verify":[...]}
Order: quick wins first (verify, pdsp), then sab-env (long pip), then mcp-inject (needs live calls), reconcile last (commits). <=10 items.
=== GRILLED === ${JSON.stringify(grill).slice(0, 5000)}
=== RAW === ${lanes.map((l, i) => `\n--${l.id}--\n${JSON.stringify(results[i]).slice(0, 2000)}`).join("\n")}
`, { label: "synthesize", phase: 'Execute', schema: {
  type: "object", required: ["queue", "verify"],
  properties: {
    queue: { type: "array", items: { type: "object", required: ["id", "what", "steps"], properties: { id: { type: "string" }, what: { type: "string" }, steps: { type: "array", items: { type: "string" } }, risk: { type: "string" } } } },
    owner_notes: { type: "array", items: { type: "string" } },
    verify: { type: "array", items: { type: "string" } },
  },
} });

const out = { queue, grill, lanes: Object.fromEntries(lanes.map((l, i) => [l.id, results[i]])) };
out;
