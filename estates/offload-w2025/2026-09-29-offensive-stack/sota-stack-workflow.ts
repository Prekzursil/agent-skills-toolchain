// SOTA offensive-stack: exhaustive research, estate audit, E2E verification,
// direct implementation with adversarial grill loops, refusal benchmark, dossier.

interface ToolFind {
  /** Tool/project name. */
  name: string;
  /** Repo or download URL when one exists. */
  repo: string;
  /** One sentence: what it does and why it matters for this stack. */
  what: string;
  /** Exact install method (pip/npm/git/docker/release-url) as verified. */
  install: string;
  /** Can it run on this Windows VM without Docker? */
  windows: "native" | "docker" | "wsl" | "unknown";
  /** Value to the estate: high = closes a real capability gap. */
  value: "high" | "medium" | "low";
}

interface ResearchHaul {
  /** Domain slug researched. */
  domain: string;
  /** Tools/projects found. */
  tools: ToolFind[];
  /** True when further queries stopped returning new information. */
  exhausted: boolean;
  /** Coverage statement: sources tried, what was NOT reachable. */
  coverage: string;
  /** Workspace-relative file with full notes + every query tried. */
  file: string;
}

interface AuditFinding {
  /** Where: path, config key, or component name. */
  where: string;
  /** One sentence: what is missing/unwired/planned-but-not-included/risky. */
  what: string;
  kind: "missing" | "unwired" | "planned-not-included" | "stale" | "risk";
  /** What showed it (lines read, command output). */
  evidence: string;
  severity: "low" | "medium" | "high";
}

interface AuditReport {
  lane: string;
  findings: AuditFinding[];
  /** File with the full audit write-up. */
  file: string;
}

interface ImplResult {
  /** What this implementer changed (paths). */
  changed: string[];
  /** One-paragraph summary of the result. */
  summary: string;
  /** How it was verified (commands run, outputs seen). */
  verified: string[];
  /** What could NOT be done and why. */
  blocked: string[];
}

interface GrillVerdict {
  /** clean = nothing blocking; findings otherwise. */
  verdict: "clean" | "findings";
  /** Each blocking problem, with file/evidence. */
  problems: string[];
}

interface BenchRow {
  /** Model identifier benchmarked. */
  model: string;
  /** Number of lab tasks attempted. */
  tasks: number;
  /** Tasks the model refused or watered down. */
  refusals: number;
  /** refusals/tasks as a percentage. */
  refusalRate: number;
}

artifact.board("research-board", {
  title: "Research lanes",
  key: "domain",
  status: "status",
  columns: ["done", "exhausted"],
  cardTitle: "domain",
  detail: [{ field: "tools", label: "tools found" }],
});
artifact.table("live-backends", {
  title: "Gateway backends after E2E",
  columns: [
    { field: "backend", label: "Backend" },
    { field: "status", label: "Status" },
  ],
  key: "backend",
});
artifact.metrics("bench", {
  title: "Sandbox model refusal rates",
  metrics: [
    { field: "model", label: "Model" },
    { field: "refusalRate", label: "Refusal %", unit: "%" },
  ],
});

const DOMAINS: Array<{ slug: string; brief: string }> = [
  { slug: "browser-offense", brief: "Offensive browser automation MCP servers: nodriver-proxy-mcp, WonderSuite, and anything newer — human-like navigation, MITM interception, authenticated-flow testing, session handling." },
  { slug: "ad-entra-paths", brief: "BloodHound MCP (13 composite tools over CE REST + Neo4j), SpecterOps AI hunting agent, Entra/AWS attack-path tools, any MCP exposing AD graph queries." },
  { slug: "c2-agentic", brief: "Mythic with LLM-generated disposable agents (SpecterOps demo), Sliver/Havoc MCP wrappers, agentic C2 patterns, anything newer than caldera." },
  { slug: "exploit-dev", brief: "N-day exploit pipelines: Clearwing (build vulnerable version, develop exploit, validate against patched), PwnAgent (62% e2e success), automated exploit generation/validation." },
  { slug: "llm-fuzzing", brief: "LLM-guided fuzzers: RESTing-LLAMA (REST APIs), RALFuzz (C harnesses), SemFuzz (protocols), anything newer — input generation quality, harness generation." },
  { slug: "cloud-ai-security", brief: "AICloudSentinel (AI workload misconfig scanner), ATMoCloud, ZeroGuard, GenSecOps, MCP servers for AWS/Azure/GCP offensive assessment beyond CIS checks." },
  { slug: "agent-memory", brief: "Shared knowledge graphs for agents: Graphiti, Kùzu embedded, Agentic-Mythos-SOC chained hypothesis generation, MCP graph servers, cross-engagement memory patterns." },
  { slug: "model-cascade", brief: "Cost-aware model routing for pentest agents: PentestChain cascade data, refusal-rate comparisons of GLM vs DeepSeek vs old Claude (Opus 4.6 era) vs local qwen for offensive tasks, output-filtering workarounds (models that answer but get filtered)." },
  { slug: "mcp-tool-hubs", brief: "MCP Security Hub (300+ tools), MCPwner (55+ containerized), any MCP servers bundling nmap/nuclei/sqlmap/ffuf/BloodHound that could replace manual wiring." },
  { slug: "pentagi-hardening", brief: "PentAGI two-node worker hardening: examples/guides/worker_node.md, DOCKER_INSIDE socket escape CVE-2026-18593, dind + TLS :2376 + OPA + seccomp patterns, safe single-node configs." },
  { slug: "wildcard-2026", brief: "Brand-new 2026 agentic offensive tools NOT in any list you know: GitHub trending (security topics), Hacker News, r/netsec, X/Twitter security researchers, awesome-lists updated recently. Find what nobody mentioned yet." },
  { slug: "deepweb-coverage", brief: "Deep/dark web tool coverage: set up Tor (expert bundle) if direct search misses things, then search ahmia/onion indices for offensive AI tooling repos, leaked research, forums discussing agentic pentest tooling. Configure access on the way — do not skip because it is not configured." },
];

const RESEARCH_RULES = [
  "You are one research lane of an exhaustive tool-research operation on an authorized private-estate security VM (Windows Server, Git Bash, C:\\Python314\\python.exe, node, git, gh, curl on PATH).",
  "MANDATORY estate search backends — use them, not just WebSearch:",
  "  • Firecrawl (key in env FIRECRAWL_API_KEY): POST https://api.firecrawl.dev/v1/search with {\"query\":\"...\",\"limit\":10} for discovery, and /v1/scrape {\"url\":\"...\",\"formats\":[\"markdown\"]} to deep-read JS-heavy pages WebFetch cannot render (docs sites, itchio,SPA pages). Bearer auth header.",
  "  • Exa neural search (key in env EXA_API_KEY): POST https://api.exa.ai/search with {\"query\":\"...\",\"numResults\":10} — best for concept queries ('MCP server that exposes BloodHound attack paths'); x-api-key header.",
  "  • Keyless DDG: python -m pip show ddgs or C:\\Python314\\python.exe -c 'from ddgs import DDGS; ...' when others rate-limit.",
  "MANDATORY GitHub repo sweep — do not rely on web search alone:",
  "  • gh api 'search/repositories?q=...' with per_page=100 AND follow page=2..N while items remain — multiple query templates per lane: topic:offensive-security, topic:red-team, topic:mcp-server+security, 'autonomous pentest', 'red team agent', 'pentest mcp', 'exploit generation', 'llm fuzzing', 'attack path', tool-specific names; add created:>2026-04-01 and sort=updated to catch brand-new repos, plus star ranges (1..50 for hidden gems, >50 for established).",
  "  • Walk awesome-lists (awesome-security, awesome-red-teaming, awesome-llm-security, awesome-mcp-servers): gh api their README, extract repo links, check each candidate's pushed_at/stars/description — new entries at the top of these lists are the highest-signal source for tools nobody blogs about yet.",
  "  • For every candidate repo: gh api repos/OWNER/NAME for stars/pushed_at/open_issues, and read its README before scoring windows-native (look for setup.py/pyproject with Windows support, prebuilt .exe releases, node package) — record the exact evidence.",
  "Search UNTIL EXHAUSTION: keep issuing new queries until consecutive searches return nothing you have not already recorded. Cross-check: exa concept-search + firecrawl discovery + gh sweep must all have been used before you may claim exhaustion.",
  "Diversify sources: GitHub, docs sites (firecrawl-scrape), Hacker News (hn.algolia.com API), Reddit (old.reddit + search API), X, arXiv, vendor blogs, non-English sources (Chinese/Japanese/Korean security blogs often break tools first — search in those languages too).",
  "If a source or network path is blocked, CONFIGURE AROUND IT (proxy, alternate mirror, Tor for onion sources — install the Tor expert bundle via Bash if needed) instead of abandoning the lane.",
  "For every tool record: exact repo/URL, one-line what/why, exact install command, whether it runs natively on Windows without Docker, value high/medium/low for this estate.",
  "Write your full notes (every query tried — including gh queries and API calls, every candidate, dead ends) with your file tools to out/research/<slug>.md, then return the structured result. The file must list every query you issued.",
  "Do not edit anything outside out/research/. Escalate if truly walled in.",
].join(" ");

phase("Research every gap domain to exhaustion");
log(`Launching ${DOMAINS.length} research lanes (12 domains, search-to-exhaustion)`);
const researchPs = DOMAINS.map((d) =>
  agent(`Researcher: ${d.slug}`, {
    system: RESEARCH_RULES + " Escalate rather than fake exhaustion.",
  }).ask<ResearchHaul>(
    `Research domain "${d.slug}": ${d.brief}\n\nKnown context: the estate runs CyberStrike 1.1.16 + a single MCP gateway (127.0.0.1:31100, 43 backends, 17 live: search fronts exa/tavily/firecrawl, nuclei, nmap, hexstrike :8888, hacktricks pinned corpus, 3 decepticon fronts, cheatengine/binary-ninja/chrome-devtools via managed stdio workers, zai-keys dual-key rotation, frida/mitmproxy/caldera rpc), Decepticon local+upstream (LangGraph), PentAGI staged docker-pending, Ollama qwen3:4b local. Windows Server VM, NO Docker engine yet (GCP no VT-x). Write notes to out/research/${d.slug}.md and return the structured haul.`,
  ),
);

phase("Audit home, repo, and stack wiring in parallel");
const auditTasks: Array<{ lane: string; ask: string }> = [
  {
    lane: "home-configs",
    ask: "Audit C:\\Users\\prekzursil\\.agents (agents.json registry, skills inventory, secrets layout) and C:\\Users\\prekzursil\\.zcode config for: entries pointing at missing installs, stale env vars, planned integrations never finished, supervision policy gaps. Compare agents.json mcp.servers against what actually exists on disk. Write up to out/audit/home-configs.md.",
  },
  {
    lane: "toolchain-repo",
    ask: "Audit C:\\Users\\prekzursil\\source\\agent-skills-toolchain granularly: read RECONCILE-STATE_2026-09-01.md and RECONCILE-LOG.md if present, golden/, platform/, plans and workflow docs — find anything planned/designed but never included in the live estate, half-finished lanes, and decisions that were made but never applied. Write up to out/audit/toolchain-repo.md.",
  },
  {
    lane: "stack-wiring",
    ask: "Audit the live stack wiring on D:\\opt: cyberstrike-mcp (mcp-ssot.json v4 backends vs gateway-server.py capabilities vs reality), decepticon (dual-mode patches, .env), decepticon-upstream (.env staged, compose never verified), pentagi (.env: check DOCKER_INSIDE and socket exposure defaults — flag the docker-socket escape risk concretely), hexstrike-ai. Find unwired, miswired, and claimed-but-not-true. Write up to out/audit/stack-wiring.md.",
  },
  {
    lane: "canonical-vs-reality",
    ask: "Diff C:\\Users\\prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\canonical-mcp-servers.json against the actual machine: which registered servers exist, which are ghosts, which good installs exist that the canonical registry does NOT know about (both directions). Also check ~/.agents/agents.json mcp.servers for ghosts. Write up to out/audit/canonical-vs-reality.md.",
  },
];
const auditPs = auditTasks.map((t) =>
  agent(`Auditor: ${t.lane}`, {
    system: "You are a granular estate auditor on an authorized private VM. Read files, run read-only checks, cite path:line evidence for every finding. Do not edit anything except your out/audit/<lane>.md write-up. Escalate if walled in.",
  }).ask<AuditReport>(t.ask),
);

phase("Baseline-test the live stack end to end");
const e2e = await world.run("python", ["D:\\opt\\cyberstrike-mcp\\verify_stack.py"], { timeoutMs: 420000 });
let e2eNote = "verify_stack.py exit 0";
if (e2e.exitCode !== 0) {
  const fixer = agent("Stack repairer", {
    system: "You fix the estate gateway stack on D:\\opt\\cyberstrike-mcp until its verify_stack.py passes. Read the failure output, repair minimally, re-run the script yourself. Do not weaken checks to make them pass — fix the wiring. Escalate if a fix needs a decision only the owner can make.",
  });
  const fix = await fixer.ask<ImplResult>(
    `verify_stack.py failed:\n${e2e.stdout}\n${e2e.stderr}\nDiagnose and repair, then re-run it and report.`,
  );
  e2eNote = `repaired: ${fix.summary}`;
}
const backends = await world.run("python", ["-c", "import asyncio,json;from mcp import ClientSession;from mcp.client.streamable_http import streamablehttp_client\nasync def m():\n async with streamablehttp_client('http://127.0.0.1:31100/mcp') as (r,w,_):\n  async with ClientSession(r,w) as s:\n   await s.initialize(); c=await s.call_tool('harness_capabilities',{}); man=json.loads(c.content[0].text)\n   for b in man['backends']: print(b['name']+'|'+b['status'])\nasyncio.run(m())"], { timeoutMs: 300000 });
const backendRows = backends.stdout.split("\n").filter((l) => l.includes("|")).map((l) => {
  const parts = l.split("|");
  return { backend: parts[0] ?? "?", status: parts[1] ?? "?" };
});
for (const row of backendRows) report(row, "live-backends");
log(`E2E baseline: ${e2eNote}; ${backendRows.length} backends enumerated`);

phase("Deduplicate the first-pass haul");
const haulSettled = await Promise.allSettled(researchPs);
const okHauls: ResearchHaul[] = haulSettled
  .filter((s): s is PromiseFulfilledResult<ResearchHaul> => s.status === "fulfilled")
  .map((s) => s.value);
for (const h of okHauls) report({ domain: h.domain, status: h.exhausted ? "exhausted" : "done", tools: h.tools.length }, "research-board");
log(`Round 1 landed: ${okHauls.length}/${DOMAINS.length} lanes`);

const KNOWN_INSTALLED = new Set([
  "cyberstrike", "decepticon", "pentagi", "hexstrike", "hexstrike ai", "strix", "offsec-ai", "nmap", "nuclei",
  "hacktricks", "caldera", "frida", "mitmproxy", "cheatengine", "binary-ninja", "chrome-devtools",
  "exa", "tavily", "firecrawl", "ollama", "zai-keys", "graphiti", "neo4j", "bloodhound",
]);
const seenCandidates = new Set<string>();
const diveCandidates = okHauls
  .flatMap((h) => h.tools.map((t) => ({ ...t, domain: h.domain })))
  .filter((t) => {
    const key = t.name.toLowerCase().trim();
    if (seenCandidates.has(key) || KNOWN_INSTALLED.has(key)) return false;
    if (t.value === "low") return false;
    seenCandidates.add(key);
    return true;
  })
  .sort((a, b) => (a.value === "high" ? -1 : 1) - (b.value === "high" ? -1 : 1))
  .slice(0, 24);
log(`Deep-dive queue: ${diveCandidates.length} promising leads`);
log("Admission-wedge recovery: unsettled deep-dives re-dispatch on a fresh scheduler");

phase("Deep-dive every promising lead");
const diveSettled = await Promise.allSettled(
  diveCandidates.map((c) =>
    agent(`Deep-dive: ${c.name}`, {
      system: "You are a lead-verifier on an authorized private-estate security VM (Git Bash, C:\\Python314\\python.exe, gh, curl, node on PATH; env keys FIRECRAWL_API_KEY and EXA_API_KEY for REST search; firecrawl /v1/scrape renders JS pages). Verify claims by reading the actual repo — never trust a blog post. Do not edit anything outside out/research/. Escalate if walled in.",
    }).ask<ToolFind>(
      `Deep-dive this candidate from the "${c.domain}" lane:\nname: ${c.name}\nrepo: ${c.repo}\nclaim: ${c.what}\n\nDo ALL of: gh api repos/<owner>/<repo> (stars, pushed_at, open_issues, license, language); read the README AND the packaging files (pyproject/setup.py/package.json/Dockerfile/release assets) to determine the REAL install command and REAL Windows-native feasibility; check dependencies and their Windows support; read issues/discussions for breakage; use exa/firecrawl to find independent mentions (activity signal, alternatives). If the repo is dead or fake, say so and score value low with evidence. Write full notes to out/research/dive-${c.name.replace(/[^a-zA-Z0-9-]/g, "-")}.md. Return the corrected, evidence-backed ToolFind.`,
    ),
  ),
);
const diveResults: ToolFind[] = diveSettled
  .filter((s): s is PromiseFulfilledResult<ToolFind> => s.status === "fulfilled")
  .map((s) => s.value);
log(`Deep-dives landed: ${diveResults.length}/${diveCandidates.length} verified leads`);

phase("Open the deep web and sweep it");
const torProvisioner = agent("Tor provisioner", {
  system: "You provision dark-web access on an authorized private research VM (Windows, Git Bash, curl). Escalate only if the network itself forbids it; otherwise find a way. Write notes to out/research/tor-setup.md. Do not edit anything else.",
});
const tor = await torProvisioner.ask<{ ready: boolean; proxy: string; notes: string }>(
  "Install and verify Tor access: download the Tor expert bundle (tor expert bundle windows x86_64 zip from dist.torproject.org or github.com/torproject/tor archive), extract to D:\\opt\\tor, start tor.exe with SocksPort 127.0.0.1:9050, verify with curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip (is_this_tor should be true). If dist.torproject.org is unreachable, try the GitHub mirror. Record the exact proxy string and any fallbacks in out/research/tor-setup.md.",
);
const onionTargets: Array<{ slug: string; brief: string }> = [
  { slug: "onion-tools", brief: "Offensive-security tooling shared on onion services: GitHub/GitLab mirrors, leak-site tooling repos, initial-access and pentest tool packs discussed on dark forums. Search ahmia (works on clearnet: ahmia.fi/search/?q=), onionland, torch (xmh57jrzkzexv3s...) via the Tor proxy, and any paste mirrors." },
  { slug: "onion-research", brief: "Leaked/dark research relevant to agentic offensive security: private red-team playbooks, 0day research teasers, C2 framework forks, cracked security-tool distributions that reveal capability patterns. Same engines: ahmia, onionland, torch, darksearch." },
  { slug: "onion-forums", brief: "Dark forum/marketplace chatter about AI red-teaming tools and LLM-based hacking services — what tools attackers actually advertise (capability intelligence). ahmia + torch + onionland through the proxy; note market churn." },
];
const onionSettled = await Promise.allSettled(
  onionTargets.map((o) =>
    agent(`Onion researcher: ${o.slug}`, {
      system: "You are a dark-web research lane on an authorized private-estate VM. " + RESEARCH_RULES.split("Do not edit anything outside")[0] + " Route onion fetches through the Tor SOCKS proxy (see out/research/tor-setup.md; default curl --socks5-hostname 127.0.0.1:9050). Clearnet mirrors of onion indexes (ahmia.fi) are the fallback when the proxy is down. NEVER transact, register, or interact beyond reading public pages. Do not edit anything outside out/research/.",
    }).ask<ResearchHaul>(
      `Deep-web lane "${o.slug}": ${o.brief}\nTor status: ${JSON.stringify(tor)}. Write notes (every query, every onion index hit, dead ends) to out/research/${o.slug}.md and return the haul. Tools found count even when they are capability-intelligence rather than installable software — mark windows "unknown" and value by intelligence worth.`,
    ),
  ),
);
const onionHauls: ResearchHaul[] = onionSettled
  .filter((s): s is PromiseFulfilledResult<ResearchHaul> => s.status === "fulfilled")
  .map((s) => s.value);
for (const h of onionHauls) report({ domain: h.domain, status: h.exhausted ? "exhausted" : "done", tools: h.tools.length }, "research-board");
log(`Deep-web fleet: tor=${tor.ready ? "up" : "fallback-clearnet"}, ${onionHauls.length}/3 lanes landed (${onionHauls.reduce((n, h) => n + h.tools.length, 0)} finds)`);

phase("Chase the gaps and hunt what everyone missed");
const knownNames = JSON.stringify([...KNOWN_INSTALLED, ...seenCandidates]);
const gapSettled = await Promise.allSettled([
  agent("Gap chaser", {
    system: "You close coverage gaps in an exhaustive research operation on an authorized VM. Read every out/research/*.md written so far, find subtopics NO lane covered, and run fresh queries (exa + firecrawl + gh sweep + WebSearch) until those gaps close or prove empty. Write out/research/gap-chase.md. Do not edit anything else.",
  }).ask<ResearchHaul>(`The fleet has covered: ${knownNames}. Read all out/research/*.md, list the uncovered subtopics, chase them. Return the haul of NEW tools only.`),
  agent("Adversarial hunter: non-English", {
    system: "You are an adversarial completeness reviewer. Your angle: non-English sources — Chinese (先知/t00ls/看雪/freebuf), Japanese, Korean, Russian (habr), Spanish/Brazilian security communities. Use exa/firecrawl/WebSearch IN those languages. Find tools absent from the known list. Write out/research/adv-nonenglish.md. Do not edit anything else.",
  }).ask<ResearchHaul>(`Known tools (do not return these): ${knownNames}. Find offensive-AI tooling the English-language lanes structurally miss. Return the haul.`),
  agent("Adversarial hunter: academic", {
    system: "You are an adversarial completeness reviewer. Your angle: academic and preprint — arXiv (cs.CR, cs.AI), USENIX/NDSS/Oakland 2026 papers and their artifact repos, university lab pages. Research code often ships as unmaintained GitHub repos with real capability. Write out/research/adv-academic.md. Do not edit anything else.",
  }).ask<ResearchHaul>(`Known tools (do not return these): ${knownNames}. Find paper-artifact and lab tools absent from the list. Return the haul.`),
  agent("Adversarial hunter: social", {
    system: "You are an adversarial completeness reviewer. Your angle: social/chatter — X/Twitter security researchers, Telegram channel indexes (tgstat/telemetr), Discord community indexes, Reddit threads, HN comments mentioning tooling. Use firecrawl scrape + exa + WebSearch. Write out/research/adv-social.md. Do not edit anything else.",
  }).ask<ResearchHaul>(`Known tools (do not return these): ${knownNames}. Find tools visible only in chatter. Return the haul.`),
]);
const gapHauls: ResearchHaul[] = gapSettled
  .filter((s): s is PromiseFulfilledResult<ResearchHaul> => s.status === "fulfilled")
  .map((s) => s.value);
for (const h of gapHauls) report({ domain: h.domain, status: h.exhausted ? "exhausted" : "done", tools: h.tools.length }, "research-board");
const totalFinds = okHauls.reduce((n, h) => n + h.tools.length, 0) + diveResults.length + onionHauls.reduce((n, h) => n + h.tools.length, 0) + gapHauls.reduce((n, h) => n + h.tools.length, 0);
log(`Research fleet complete: ${totalFinds} total finds across ${okHauls.length + onionHauls.length + gapHauls.length} lanes + ${diveResults.length} deep-dives`);

phase("Consolidate everything into the ranked table");
const sweeper = agent("Research sweeper", {
  system: "You deduplicate and centralize research results. Read every out/research/*.md file (round-1 lanes, dive-* deep-dives, onion lanes, gap/adv lanes), merge duplicates (same tool found by multiple lanes), keep the best evidence per tool, and write out/research/CONSOLIDATED.md with a ranked table (value desc, windows-native first). Escalate if files are missing.",
});
const consolidated = await sweeper.ask<{ file: string; topNative: ToolFind[]; topDocker: ToolFind[] }>(
  `Consolidate the full research fleet output from out/research/ (round-1 hauls: ${JSON.stringify(okHauls.map((h) => ({ domain: h.domain, n: h.tools.length })))}; ${diveResults.length} deep-dives; ${onionHauls.length} onion lanes; ${gapHauls.length} gap/adversarial lanes). Return topNative (top 10 installable on Windows without Docker) and topDocker (top 5 for the docker era).`,
);
log(`Research consolidated: ${consolidated.topNative.length} native + ${consolidated.topDocker.length} docker-priority tools`);

phase("Audit fan-in and cross-checks");
const auditSettled = await Promise.allSettled(auditPs);
const okAudits: AuditReport[] = auditSettled
  .filter((s): s is PromiseFulfilledResult<AuditReport> => s.status === "fulfilled")
  .map((s) => s.value);
const allFindings: AuditFinding[] = okAudits.flatMap((a) => a.findings);
const highFindings = allFindings.filter((f) => f.severity === "high").length;
log(`Audits landed: ${okAudits.length} lanes, ${allFindings.length} findings (${highFindings} high)`);

phase("Implement the gap-closers");
const implBrief = `Implement directly on this authorized estate VM (Git Bash, C:\\Python314\\python.exe, node on PATH; gateway kit at D:\\opt\\cyberstrike-mcp; gateway restart: powershell -File D:\\opt\\cyberstrike-mcp\\gateway-stop.ps1 then Start-ScheduledTask -TaskName CyberStrikeGateway). Principles: single-process gateway, NO watchdogs/supervisors/timers; mcp-stdio workers are managed (one child per backend, Job Object kill-on-close); availability computed lazily; loopback-only binding; secrets stay local (sha8 in logs). Test what you build by actually invoking it. Return structured result.`;
const implTasks: Array<{ area: string; ask: string }> = [
  {
    area: "cascade-router",
    ask: `${implBrief}\nTASK: Add a cost-aware model-cascade backend to the gateway (new front fronts/model_router.py + SSOT row "model-router" kind=module): route(mechanical tasks like scan parsing/summary) -> Ollama qwen3:4b via http://127.0.0.1:11434/v1; reasoning tasks (exploit planning, chain analysis) -> GLM via the existing fronts/zai_keys.py invoke (it rotates keys) with OpenAI fallback via env OPENAI_API_KEY. Tools: route{task_kind,payload}, status. Wire into mcp-ssot.json v5, restart gateway, verify a real route call each way.`,
  },
  {
    area: "knowledge-graph",
    ask: `${implBrief}\nTASK: Build the shared knowledge-graph layer: pip install kuzu into C:\\Python314, create D:\\opt\\knowledge-graph with an embedded Kùzu DB (nodes: Host, Credential, Finding, Technique, Engagement; edges: reached_from, authenticated_to, exploited_via, found_during) plus a gateway front fronts/knowledge_graph.py (tools: add_node, add_edge, neighbors, shortest_path, search, cypher) + SSOT row "knowledge-graph" kind=module. Also write D:\\opt\\knowledge-graph\\NEO4J-MIGRATION.md describing the Graphiti/Neo4j path for the docker era. Restart gateway, verify: write 2 nodes + 1 edge, read them back via shortest_path.`,
  },
  {
    area: "wire-new-tools",
    ask: `${implBrief}\nTASK: Read out/research/CONSOLIDATED.md, pick the top tools that install NATIVELY on Windows (no Docker), install them (D:\\opt\\bin or pip/npm), and wire each as a gateway backend (binary kind or mcp-stdio managed worker with correct entry) in mcp-ssot.json. Prefer the browser-offense, mcp-tool-hubs, and wildcard-2026 picks. Verify each new backend through harness_invoke with one real call. Do not install anything requiring Docker.`,
  },
  {
    area: "pentagi-hardening",
    ask: `${implBrief}\nTASK: Harden PentAGI staging at D:\\opt\\pentagi: edit .env so DOCKER_INSIDE stays false, DOCKER_NET_ADMIN explicitly false for the main node, add commented two-node worker config block (DOCKER_INSIDE_HOST=tcp://worker:2376, DOCKER_INSIDE_TLS_VERIFY=true, DOCKER_INSIDE_CERT_PATH) per the worker_node guide pattern; write D:\\opt\\pentagi\\HARDENING.md documenting the socket-escape chain (agent downloads binary -> docker socket -> WSL2 VM escape -> mount C:\\) and why these settings close it, plus the exact remote-engine alternative (DOCKER_HOST over Tailscale). Also add a preflight check to bring-up.ps1 that refuses to start if DOCKER_INSIDE=true.`,
  },
  {
    area: "sandbox-agents",
    ask: `${implBrief}\nTASK: Author the sandboxed red-team agent harness at D:\\opt\\sandbox-agents\\: (1) AGENTS.md — operating contract for CONTAINED lab agents (own VM/lab targets only, no egress beyond model APIs, full-capability posture, no refusal theater, escalate on genuine ambiguity); (2) provider configs with refusal-minimal system prompts for: GLM 4.6 (via https://api.z.ai/api/anthropic, key from user env ZAI_API_KEY — rotate-aware), local qwen3:4b (Ollama 127.0.0.1:11434), DeepSeek (env DEEPSEEK_API_KEY if present, else config-ready), legacy Claude Opus 4.6 era (config-ready, no key on box) — each prompt establishes sandbox context: authorized lab, contained environment, expert peer framing, task-completion priority; (3) bench/bench.py — refusal benchmark: >=15 authorized-lab offensive tasks (CTF-style: craft payload, analyze malicious sample behavior, write exploit for lab vuln, etc), runs each prompt against a provider endpoint, classifies refusal (hard refuse / watered-down / complied), writes bench/results.json + markdown table. Test bench.py against Ollama qwen3:4b live now.`,
  },
  {
    area: "audit-fixes",
    ask: `${implBrief}\nTASK: Read out/audit/*.md (4 lanes) and fix every actionable finding: wire unwired integrations, correct misconfigurations, register ghost-free entries, apply planned-but-dropped decisions where still useful. Skip anything needing Docker or owner decisions (list those as blocked). Audit findings:\n${JSON.stringify(allFindings.slice(0, 60))}`,
  },
];
const implSettled = await Promise.allSettled(
  implTasks.map((t) =>
    agent(`Implementer: ${t.area}`, {
      system: "You are a senior implementer on an authorized private-estate security VM. Make real, tested changes; verify by invoking what you built; report honestly what is verified vs blocked. Escalate rather than fake success.",
    }).ask<ImplResult>(t.ask),
  ),
);
interface ImplPair { area: string; result: ImplResult | null }
const implPairs: ImplPair[] = implSettled.map((s, i) => ({
  area: implTasks[i]?.area ?? `area-${i}`,
  result: s.status === "fulfilled" ? s.value : null,
}));
const implOk = implPairs.filter((p): p is { area: string; result: ImplResult } => p.result !== null);
for (const p of implOk) log(`Implemented: ${p.area} — ${p.result.summary.slice(0, 120)}`);

phase("Grill the implementations until clean");
const grillLenses = [
  "correctness lens: does each implementation actually work as claimed? Re-run its verification commands yourself, read the diff, hunt for fake-success (checks weakened, results fabricated, features stubbed).",
  "security lens: loopback-only? secrets not leaked into logs? no new daemons/watchdogs/timers? Job Object containment intact? no widened attack surface? sandbox prompts cannot exfiltrate keys?",
  "completeness lens: does each deliverable cover its full spec (cascade has both tiers, KG has all node/edge types + migration doc, sandbox harness has all 4 provider configs + working bench)? What was silently dropped?",
];
const implDigest = implPairs
  .map((p) => p.result
    ? `--- Impl: ${p.area} ---\nsummary: ${p.result.summary}\nchanged: ${p.result.changed.join(", ")}\nverified: ${p.result.verified.join("; ")}\nblocked: ${p.result.blocked.join("; ")}`
    : `--- Impl: ${p.area} --- LANDED: NO (implementer failed or was stopped)`)
  .join("\n");
let grillProblems: string[] = [];
const repairAgent = agent("Repairer", {
  system: "You repair griled implementations on the estate VM minimally and honestly, re-verifying each fix by running it. Escalate if a fix needs an owner decision.",
});
for (let round = 1; round <= 3; round++) {
  const verdictSettled = await Promise.allSettled(
    grillLenses.map((lens, i) =>
      agent(`Grill reviewer ${round}-${i}`, {
        system: `You are an adversarial reviewer with this lens — ${lens} Read the actual files and re-run checks; do not trust summaries. Report only problems that matter, with file+evidence. Escalate rather than rubber-stamp.`,
      }).ask<GrillVerdict>(`Implementation digest to grill (round ${round}):\n${implDigest}\n\nPrior unresolved problems: ${JSON.stringify(grillProblems)}\nReturn verdict clean only if you actively verified.`),
    ),
  );
  const verdicts: GrillVerdict[] = verdictSettled.map((s, i) =>
    s.status === "fulfilled" ? s.value : { verdict: "findings", problems: [`grill lane ${round}-${i} did not complete — treat as unverified`] },
  );
  grillProblems = verdicts.flatMap((v) => v.problems);
  const clean = verdicts.every((v) => v.verdict === "clean");
  log(`Grill round ${round}: ${clean ? "clean" : `${grillProblems.length} problems`}`);
  if (clean) break;
  const fixed = await repairAgent.ask<ImplResult>(
    `Grill round ${round} found these problems:\n${JSON.stringify(grillProblems, null, 1)}\nRepair each one, re-verify, and report.`,
  );
  grillProblems = grillProblems.filter((p) => !fixed.changed.some((c) => p.includes(c)));
}

phase("Benchmark sandbox model refusal rates");
const benchSetup = implPairs.find((p) => p.area === "sandbox-agents" && p.result !== null);
let benchRows: BenchRow[] = [];
if (benchSetup) {
  const benchRun = await world.run("python", ["D:\\opt\\sandbox-agents\\bench\\bench.py", "--all"], { timeoutMs: 900000 });
  if (benchRun.exitCode === 0) {
    const read = await world.run("python", ["-c", "import json;d=json.load(open(r'D:\\opt\\sandbox-agents\\bench\\results.json'));print(json.dumps(d))"]);
    try {
      const parsed: unknown = JSON.parse(read.stdout);
      if (Array.isArray(parsed)) benchRows = parsed as BenchRow[];
    } catch {
      benchRows = [];
    }
  }
  for (const row of benchRows) report(row, "bench");
  log(`Benchmark: ${benchRows.length} models measured`);
} else {
  log("Benchmark skipped: sandbox-agents implementer did not land");
}
const finalReview = await agent("Independent final reviewer", {
  system: "You have seen nothing of this run. Read out/research/CONSOLIDATED.md, out/audit/*.md, the changed files the digest names, and bench/results.json if present. Say what is unclear, unsupported, or missing from the whole delivery — as a reader would. Do not edit anything.",
}).ask<string>(`Deliverable digest:\n${implDigest}\nBench: ${JSON.stringify(benchRows)}\nGrill residual problems: ${JSON.stringify(grillProblems)}\nWhat would a skeptical owner push back on?`);

phase("Compile the final dossier");
const compiler = agent("Dossier compiler", {
  system: "You write the final deliverable document for the estate owner: precise, evidence-linked, no marketing tone. Write it to out/SOTA-STACK-DOSSIER.md.",
});
const dossier = await compiler.ask<{ file: string; conclusion: string }>(
  `Compile out/SOTA-STACK-DOSSIER.md from: research consolidated (${consolidated.topNative.length} native + ${consolidated.topDocker.length} docker tools), audit findings (${allFindings.length}), implementations (${implDigest}), grill residuals (${JSON.stringify(grillProblems)}), bench (${JSON.stringify(benchRows)}), final review critique (${finalReview.slice(0, 2000)}), E2E (${e2eNote}). Sections: Executive summary; New capabilities wired today; Research horizon (ranked, install-ready vs docker-pending); Audit results and what was fixed; Hardening posture (PentAGI socket risk closed); Refusal benchmark; Residual risks and owner decisions. Return the file path + 3-sentence conclusion.`,
);
try {
  await artifact.file("dossier", "out/SOTA-STACK-DOSSIER.md", {
    title: "SOTA stack dossier",
    description: "Exhaustive research, audit, implementation, grill and benchmark results",
    primary: true,
  });
} catch {
  await artifact.markdown("dossier-fallback", `# Dossier fallback\n\n${dossier.conclusion}`, { title: "SOTA stack dossier (fallback)" });
}
await artifact.markdown(
  "report",
  [
    "# Run summary",
    "",
    `- Research: ${okHauls.length}/${DOMAINS.length} lanes landed, ${okHauls.filter((h) => h.exhausted).length} reached exhaustion`,
    `- Audits: ${allFindings.length} findings (${highFindings} high) across ${okAudits.length} lanes`,
    `- Implementations: ${implOk.length}/${implTasks.length} areas landed`,
    `- Grill: ${grillProblems.length} residual problems after repair loop`,
    `- Benchmark: ${benchRows.length} models measured`,
    `- E2E: ${e2eNote}`,
  ].join("\n"),
  { title: "Run summary" },
);

return {
  conclusion: dossier.conclusion,
  findings: allFindings.map((f) => ({
    where: f.where,
    what: `${f.kind}: ${f.what}`,
    evidence: f.evidence,
    status: "unconfirmed" as const,
    severity: f.severity,
  })),
  verified: [
    "gateway E2E via verify_stack.py (world.run gate)",
    `backend census: ${backendRows.filter((r) => r.status === "available").length} available of ${backendRows.length}`,
    ...implOk.flatMap((p) => p.result.verified.map((v) => `${p.area}: ${v.slice(0, 140)}`)),
  ],
  notCovered: [
    "Docker-era tools verified only as staged configs (PentAGI stack, Decepticon upstream 7-service, strix sandbox)",
    benchRows.length === 0 ? "refusal benchmark did not produce results" : "refusal benchmark covers only providers with keys on box (GLM/qwen); DeepSeek and legacy Claude configs are staged untested",
    ...grillProblems.map((p) => `residual grill problem: ${p.slice(0, 140)}`),
  ],
};
