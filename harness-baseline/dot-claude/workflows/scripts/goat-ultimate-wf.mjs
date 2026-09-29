export const meta = {
  name: "goat-ultimate",
  description: "Internet-wide SOTA sweep: wildcards, deep-research/gem-hunt upgrades, firecrawl+github repos, MCPs, skills - adopt queue for the GOAT stack",
  phases: [
    { title: "Sweep", detail: "7 web lanes, each a different search angle" },
    { title: "Grill", detail: "kill unverifiable candidates" },
    { title: "Rank", detail: "value/effort synthesis" },
  ],
};

const GROUND = `
CONTEXT: The owner's GOAT science stack (2026-09-22, all green): Claude Science WSL daemon + Biomni A1 (224 tools, MCP-injected arxiv/crossref), compchem suite (GROMACS/OpenFF/AmberTools/MDAnalysis/ProLIF/Chemprop/ADMET-AI), agent frameworks (Open Coscientist, OctoTools, PaperQA2, Aviary, SAB), GLM 5.3/flash dual-tier, failover keys, 24-skill port to CS + 8 know-how docs to A1.
ALREADY HAVE (do NOT re-propose): pubmed/openalex/crossref/arxiv/sci-hub/annas/scholarly-access MCPs, firecrawl+exa+tavily+perplexity search hub, rdkit/schrodinger/qdx-rush/openmm chem MCPs, tooluniverse, basic-memory, deep-research + gem-hunt + grill-me-extensive skills.
HARD RULES: no live secrets (sha8 only). Cite URL for every claim. Mark [VERIFIED url] / [UNVERIFIED]. Star-count claims need a date. Prefer MIT/Apache; flag copyleft/licensed.
OUTPUT per lane: markdown table | candidate | what | why-valuable | evidence-url | license | effort (low/med/high). <=10 rows. Then <=80-word summary.
`;

phase('Sweep');
const lanes = [
  { id: "wildcards", p: GROUND + `LANE: wildcard discoveries - brand-new (2025-2026) agentic-science/ai-scientist/bio-agent projects the stack lacks. Search GitHub trending + recent launches: "AI scientist", "autonomous lab agent", "bio-agent 2026", "agent benchmark science".` },
  { id: "deepresearch-upgrade", p: GROUND + `LANE: state-of-the-art deep-research agent implementations - what beats or complements PaperQA2/deep-research skill? Search: open-source deep research agents (STORM, GPT-researcher successors, open deep research 2026 releases), multi-hop RAG with citation grounding, agent-RAG frameworks.` },
  { id: "gemhunt-upgrade", p: GROUND + `LANE: harness-improvement discovery - what makes agent workspaces better? Search: Claude Code/Codex skill marketplaces, MCP server registries/directories 2026, agent-eval frameworks (agent-as-judge successors), prompt/behavior tooling releases.` },
  { id: "github-firecrawl", p: GROUND + `LANE: GitHub repos + Firecrawl-extractable resources for science agents. Search: high-star MCP servers for science/data released 2025-2026, repos with "mcp" + chemistry/biology/papers, awesome-mcp lists, and identify 3-5 repos worth cloning into ~/source.` },
  { id: "mcp-census-2", p: GROUND + `LANE: MCP server census refresh - what new servers appeared since the 2026-09-20 census? Focus: data-analysis (jupyter/pandas), visualization, lab-notebook/electronic-lab, chemical-drawing, workflow-orchestration MCPs.` },
  { id: "skills-sota", p: GROUND + `LANE: other people's skill/prompt libraries - Claude Code skills collections, agent methodology repos (scientific method, reproducibility, literature synthesis, hypothesis testing). What should be ported to the estate SSOT (C:\\Users\\Prekzursil\\.agents\\skills)?` },
  { id: "compute-free", p: GROUND + `LANE: free compute + data grabs - EuroHPC open calls status, new free GPU programs 2026, large open datasets relevant to the phenibut/GABA-B program (ChEMBL 37, GtoPdb updates, BindingDB, Offsides/TwoSides refresh) with direct URLs.` },
];
const results = await parallel(lanes.map(l => () => agent(l.p, { label: `sweep:${l.id}`, phase: 'Sweep' })));

phase('Grill');
const grill = await agent(GROUND + `
GRILL: verify-or-kill every candidate below. A candidate survives ONLY with: a live URL [VERIFIED via fetch], a real license note, and non-duplication vs the ALREADY-HAVE list. Kill vaporware, dead repos (last push >18mo unless canonical), and duplicates. Output: survivors table + killed list (name + reason, one line each).
${lanes.map((l, i) => `\n--- ${l.id} ---\n${JSON.stringify(results[i]).slice(0, 3200)}`).join("\n")}
`, { label: "grill", phase: 'Grill' });

phase('Rank');
const plan = await agent(GROUND + `
RANK the grilled survivors into an adoption queue for the main session. JSON only:
{"adopt_now":[{"name","what","install","why","lane"}],"watchlist":[{"name","why_later"}],"dataset_grabs":[{"name","url","size"}]}
Cap adopt_now at 8 (effort-weighted: pip/clone-able first). dataset_grabs cap 5.
=== GRILLED === ${JSON.stringify(grill).slice(0, 6500)}
`, { label: "rank", phase: 'Rank', schema: {
  type: "object", required: ["adopt_now", "watchlist"],
  properties: {
    adopt_now: { type: "array", items: { type: "object", required: ["name", "what", "install", "why"], properties: { name: { type: "string" }, what: { type: "string" }, install: { type: "string" }, why: { type: "string" }, lane: { type: "string" } } } },
    watchlist: { type: "array", items: { type: "object", required: ["name", "why_later"], properties: { name: { type: "string" }, why_later: { type: "string" } } } },
    dataset_grabs: { type: "array", items: { type: "object", required: ["name", "url"], properties: { name: { type: "string" }, url: { type: "string" }, size: { type: "string" } } } },
  },
} });

({ plan, grill, sweeps: Object.fromEntries(lanes.map((l, i) => [l.id, results[i]])) });
