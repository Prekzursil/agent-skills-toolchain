# Research notes — domain `agent-memory`

Lane: shared knowledge graphs for agents (Graphiti, Kùzu embedded + successors, Agentic-Mythos-SOC chained hypothesis generation, MCP graph servers, cross-engagement memory patterns).
Date: 2026-09-29. Box: Windows Server, Git Bash, C:\Python314 (3.14.6), node/npm/git/gh on PATH, NO Docker engine (GCP no VT-x). Estate: CyberStrike 1.1.16, MCP gateway 127.0.0.1:31100 (98 servers in `C:\Users\prekzursil\.agents\agents.json` `mcp.servers`), Decepticon (LangGraph), Ollama qwen3:4b, PentAGI staged docker-pending.

Estate-fit yardstick used throughout: runs natively on Windows without Docker; pip/npm/git-only install; can back shared cross-engagement memory for security agents.

---

## 0. Environment checks run (exact commands + outputs)

- `gh api user -q .login` → `Prekzursil` (gh authed).
- `"C:/Python314/python.exe" -c "...sys.version..."` → `3.14.6 (tags/v3.14.6:c63aec6, Jun 10 2026...) [MSC v.1944 64 bit (AMD64)]`; `EXA_API_KEY True`, `FIRECRAWL_API_KEY True`.
- `"C:/Python314/python.exe" -m pip show ddgs` → `Name: ddgs Version: 9.16.0`.

### Firecrawl lane — BLOCKED, with evidence (worked around)

- `FIRECRAWL_API_KEY` env value is the literal unexpanded string `${FIRECRAWL_API_KEY}` (len 20, prefix `${FIR`) → `POST https://api.firecrawl.dev/v1/search` returns `HTTP 401 {"success":false,"error":"Unauthorized: Invalid token"}`. The placeholder was never expanded by the provisioner.
- `agents.json` `/mcp/servers/firecrawl` block: `"url": "http://127.0.0.1:31114/mcp"`, description "Local firecrawl: mcp-proxy :31114 -> firecrawl-mcp-launch -> self-host docker stack (:3002, no credits). Hosted lane auto-restores after 09-16 by clearing FIRECRAWL_API_URL." — the local firecrawl lane is a Docker-stack design and this box has no Docker.
- Probes: `curl http://127.0.0.1:31114/` → `000` (connection refused — mcp-proxy down). `curl http://127.0.0.1:3002/` → `404 Not Found`, `server: uvicorn` (a Python service, not the Firecrawl API; `/v1/search` and `/v2/search` POST → `Not Found`).
- `POST http://127.0.0.1:31100/mcp` (JSON-RPC, streamable HTTP) → initialize OK (session granted), `tools/list` → exactly `['harness_bridge_status', 'harness_capabilities', 'harness_invoke']` — the gateway /mcp endpoint is the harness bridge, not a firecrawl-exposing aggregator.
- Verdict: firecrawl discovery unusable this run through no fault of the lane; substituted exa + DDG + gh + WebFetch + HN Algolia. (Explain-this-to-owner item: `FIRECRAWL_API_KEY` placeholder never expanded.)

---

## 1. Every query issued

### Exa (neural) — via `out/research/_search_am.py exa "<q>" 10`
1. `Agentic-Mythos-SOC chained hypothesis generation security operations`
2. `MCP server persistent knowledge graph memory for AI agents cross-session`
3. `Kuzu embedded graph database archived community fork successor maintained 2026`
4. `LadybugDB maintained Kuzu fork GitHub repository embedded graph`
5. `DeusData codebase-memory-mcp code intelligence knowledge graph MCP server`
6. `智能体 长期记忆 知识图谱 MCP 本地` (Chinese lane)

### Firecrawl — attempted, blocked (401 invalid placeholder token)
7. `Agentic-Mythos-SOC`
8. `Graphiti Kuzu embedded backend temporal knowledge graph agent memory`

### DDG (keyless) — via `_search_am.py ddg`
9. `MCP server knowledge graph memory agent 2026`

### GitHub API searches (`gh api 'search/repositories?q=...'`)
10. `kuzu+graph+fork&sort=updated`
11. `ladybugdb+OR+ladybug-db+OR+ladybug+graph&sort=updated` (noisy)
12. `ladybugdb` (precise)
13. `topic:mcp-server+memory+knowledge+graph&sort=updated`
14. `graphiti+mcp&sort=updated`
15. `ladybug+mcp+OR+kuzu+mcp&sort=updated`
16. `kuzu-mcp+in:name`
17. `engram+memory+agent&sort=stars`

### GitHub repo fetches (`gh api repos/<owner>/<repo>` + READMEs/trees/releases where noted)
pentrestion/Agentic-Mythos-SOC (+readme, +contents/mythos_orchestrator.py, +git/trees), getzep/graphiti (+readme ×2, +contents/mcp_server/README.md), kuzudb/kuzu, Vela-Engineering/kuzu (+readme), predictable-labs/ryugraph, Kineviz/bighorn, siafuDB/siafudb-kuzu, LadybugDB/ladybug (+readme), LadybugDB/mcp-server-ladybug (+readme), renezander030/graphiti-local, DeusData/codebase-memory-mcp (+readme, +releases/latest), caura-ai/caura (+readme ×2), doobidoo/mcp-memory-service (+readme), mem0ai/mem0 (+readme), topoteretes/cognee (+readme), letta-ai/letta, CheMiguel23/MemoryMesh, supermemoryai/supermemory, agentic-mcp-tools/memora → agentic-box/memora (+readme), yucx-go/agent-knowledge, IgorGanapolsky/mcp-memory-gateway (redirected → IgorGanapolsky/ThumbGate, different tool — dropped), basicmachines-co/basic-memory (+readme), GLei16/mythosharness, flaw0-security/mythosharness, mythos-agent/mythos-agent, Gentleman-Programming/engram (+releases/latest), kuzudb/kuzu-mcp-server, Jakedismo/KuzuMem-MCP (via search), modelcontextprotocol/servers.

### PyPI checks (`pip index versions` / `pip download --no-deps -d out/research/wheels`)
`kuzu`, `ladybug`, `graphiti-core`, `kuzu-mcp-server` (absent), `falkordblite`, `graphiti-mcp` (absent), `cognee`; downloads: ladybug, mcp-server-ladybug, graphiti-core, falkordblite, kuzu, cognee.

### npm
`npm view @modelcontextprotocol/server-memory version` → `2026.8.31`; `@ladybugdb/core` → `0.21.0`; `@caura/client` → `1.0.2`.

### HN Algolia
`https://hn.algolia.com/api/v1/search?query=Graphiti%20knowledge%20graph&tags=story` ; `?query=LadybugDB`.

### WebFetch deep reads
https://dev.to/reneza/kuzu-is-deprecated-heres-how-i-run-graphiti-on-one-file-with-ollama-4bfk ; https://vela.partners/blog/kuzudb-ai-agent-memory-graph-database ; https://chatforest.com/guides/best-memory-mcp-servers/ .

### Awesome-list walk
`curl raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md` (1,364,081 chars) → regex-extracted 55 memory/graph-related GitHub entries (list in §5).

---

## 2. The Kùzu collapse and the successor map (core finding)

- `gh api repos/kuzudb/kuzu` → `"archived": true, "pushed_at": "2025-10-10T15:34:00Z"`, 4,023 stars. Repo banner: "This repository was archived by the owner on Oct 10, 2025. It is now read-only."
- **PyPI `kuzu` is frozen at 0.11.3** (`pip index versions kuzu` → latest 0.11.3). On this box `pip download --no-deps kuzu` fell back to the sdist and the build failed on a Windows deep path (`FileNotFoundError ... iceberg test ... .snap-...avro.crc`) ⇒ **no cp314 win_amd64 wheel exists for kuzu**; `pip install kuzu` is effectively dead on estate Python.
- Successors/forks verified:
  - **LadybugDB/ladybug** — 1,792 stars, created 2025-10-07 (forked the week of the archive), pushed **2026-09-29** (today), MIT, "The database was formerly known as Kuzu" (README). PyPI `ladybug` 0.21.0, npm `@ladybugdb/core` 0.21.0, Java/Swift/Go/Rust bindings, precompiled C/C++ binaries + CLI in releases, docs at docs.ladybugdb.com, site ladybugdb.com ("DuckDB for graphs — the KuzuDB successor"). HN: "LadybugDB: DuckDB for Graphs" (2026-02-25), "Ladybug Flying Solo" 0.18.0 blog (2026-07-01).
  - **Vela-Engineering/kuzu** — true fork (`"fork": true`), 44 stars, pushed 2026-09-27. Adds **concurrent multi-writer support** (original Kuzu = single writer). README quick-start says `pip install kuzu` — but that installs the frozen 0.11.3 upstream, NOT their fork; they publish no PyPI package I could find ⇒ install = build C++ from source. Vela blog benchmarks (P. Rao kuzudb-study, 100K nodes/2.4M edges): 2nd-degree path 374× faster than Neo4j (0.009s vs 3.22s), filtered path-finding 40.8×, ingestion 53×.
  - **Kineviz/bighorn** — 134 stars, pushed 2026-08-10; Kuzu fork adding server mode + visualization focus.
  - **predictable-labs/ryugraph** — 146 stars, stalled (pushed 2026-01-20).
  - **siafuDB/siafudb-kuzu** — 1 star, v0.11.3 fork relicensed Apache-2.0, pushed 2026-09-11.
  - Landscape article: gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape (2026-05-28) — not deep-read this run (Exa snippet only).
- **Windows-native proof (ran here)**: `pip download --no-deps ladybug` → **`ladybug-0.21.0-cp314-cp314-win_amd64.whl` (5,638,418 bytes)** landed in `out/research/wheels/`. LadybugDB installs natively on this box with one pip command.

## 3. Graphiti (getzep/graphiti) — status on this estate

- `gh api repos/getzep/graphiti` → 31,306 stars, pushed **2026-09-29** (today), not archived, 476 open issues. PyPI `graphiti-core` 0.30.2 (pure-py wheel downloaded here: `graphiti_core-0.30.2-py3-none-any.whl`).
- README backend list: Neo4j 5.26 / FalkorDB 1.1.2 / Amazon Neptune (+OpenSearch) / **Kuzu 0.11.2 (deprecated, "will be removed in a future release — the upstream Kuzu project is no longer maintained. New projects should use Neo4j or FalkorDB. The driver still ships for now but emits a [warning]")**.
- Embedded options on Windows, tested here:
  - `pip install graphiti-core[kuzu]` → broken on estate (kuzu has no cp314 win wheel; driver deprecated anyway).
  - `pip download falkordblite` → **sdist build failure** ("Failed to build 'falkordblite' when getting requirements to build wheel") ⇒ graphiti-core[falkordblite] is not Windows-native either.
  - Server backends (Neo4j/FalkorDB) need Docker ⇒ excluded on this box.
  - **Working native path = the graphiti-local recipe** (renezander030/graphiti-local, 2 stars, pushed 2026-09-25, "local-first temporal knowledge graph"): alias `sys.modules.setdefault("kuzu", ladybug)` so Graphiti's `graphiti_core.driver.kuzu_driver.KuzuDriver` runs on a single Ladybug file (`graph.ladybug`), LLM = Ollama `qwen2.5:7b` + `nomic-embed-text`. Tested by its author on graphiti-core 0.30.1 + LadybugDB 0.19 (Sept 2026). Gotchas (from the dev.to writeup): create full-text indexes manually on first open (`build_indices_and_constraints` is a no-op on the Kuzu driver or hybrid search throws a Binder exception); embedder lock-in (768-dim nomic — dimension mismatch caught by `kg doctor`); only the MCP server reads; writes go through human-approved drain commands; extraction ~34s on a laptop ⇒ batch overnight. **This matches the estate stack (Ollama local, no Docker) almost exactly — estate already runs qwen3:4b.**
- Official MCP server: `getzep/graphiti/mcp_server/` (episode management, search tools); install per `mcp_server/README.md`: `git clone https://github.com/getzep/graphiti.git && uv sync && uv run main.py --database-provider neo4j|falkordb...`. No `graphiti-mcp` on PyPI.
- Security: ChatForest comparison (Aug 2026) flags **CVE-2026-32247 Cypher injection in graphiti-core, CVSS 8.1, fixed in v0.28.2** ⇒ estate must pin ≥0.28.2 (0.30.2 current is fine).
- Community forks seen: gyasis/graphiti-mcp (multi-provider LLM build), bradykirk/graphiti (FalkorDB+MCP image), ProxiBlue/pb-graphiti (cross-session Claude Code memory via Graphiti+Neo4j).

## 4. Agentic-Mythos-SOC (named in the ask) — verdict: vaporware

- `gh api repos/pentrestion/Agentic-Mythos-SOC` → 0 stars, 0 forks, created 2026-04-12, pushed 2026-04-13 (one-day repo), Python, "The Multi-Agent Offensive Security & Orchestration Framework - Mythos Preview v2.1".
- Repo tree = exactly 3 files: `README.md`, `llms.txt`, `mythos_orchestrator.py`.
- Read `mythos_orchestrator.py` in full: every "agent" method is `print()` statements; the single substantive comment says "(Simulated execution for repository structure)". "Chained Hypothesis Generation" = a method that prints `[LATENT PLAN: ...]`. No LLM calls, no tool calls, no requirements.txt, no memory persistence of any kind.
- The *real* thing behind the name: Anthropic's "Claude Mythos" red-team methodology (red.anthropic.com, April 2026, per pulseengine/gale HOWTO). Live implementations of the chained-hypothesis pattern with memory: flaw0-security/mythosharness (17★, "long-running, self-evolving vulnerability-discovery harness... self-distills skills", pushed 2026-05-25), GLei16/mythosharness (0★), mythos-agent/mythos-agent (44★, MCP security-scanning agent, pushed 2026-05-23), SomeoneAlt-86/open-mythos (6★), anshug/claude-mythos (six-agent prompt framework). Academic: "Cognitive SOC: Evidence-Backed Narrative Generation for Security Operations with Multi-Agent LLM Architecture" (Oulu, 2026-03, oulurepo.oulu.fi PDF — found, not deep-read).
- **Pattern takeaway for this estate**: chained hypothesis generation needs a persistent hypothesis/finding graph across engagements — none of the Mythos-ecosystem repos ship one; that gap is what Graphiti/Ladybug memory fills.

## 5. MCP graph/memory servers — verified haul

Signals: awesome-mcp-servers full walk (55 memory/graph entries extracted; saved in `_awesome.md`), gh topic search, DDG, Chinese-language search, ChatForest comparative review.

**Tier 1 — install-natively-tomorrow on this box:**
- **LadybugDB/mcp-server-ladybug** (official, 17★, pushed 2026-09-23): one `query` tool = arbitrary Cypher over an embedded Ladybug file; row/char caps (`--max-rows 1024 --max-chars 50000`); `pip install mcp-server-ladybug && mcp-server-ladybug --db-path memory.lbdb`. Wheel proof here: `mcp_server_ladybug-0.1.2-py3-none-any.whl`. This is the smallest possible shared-brain primitive for the estate: agents write findings as graph rows via MCP, others traverse them.
- **Gentleman-Programming/engram** (6,933★, pushed today): agent-agnostic Go binary, SQLite + FTS5, MCP server + HTTP API, session memory for coding agents. Release v2.2.1 (2026-09-25) ships **`engram_2.2.1_windows_amd64.zip`** — verified asset name. Single exe, zero deps.
- **doobidoo/mcp-memory-service** (1,973★, pushed today): `pip install mcp-memory-service`; SQLite default backend (sqlite-vec), REST + MCP + OAuth + CLI + dashboard, autonomous consolidation, LangGraph/CrewAI/AutoGen integration (Decepticon is LangGraph — direct fit), Windows config path documented (`%APPDATA%\Claude\claude_desktop_config.json`).
- **DeusData/codebase-memory-mcp** (45,467★, 3,724 forks, created 2026-02-24, pushed 2026-09-28, MIT, arXiv 2603.27277, SLSA-3, VirusTotal-scanned releases): pure-C static binary indexing codebases (158 langs, tree-sitter) into a persistent SQLite-backed knowledge graph; Cypher-ish structural queries, sub-ms; 8,050 tests. Release v0.11.0 (2026-09-15) ships **`codebase-memory-mcp-windows-amd64.zip`** — verified. Use: cross-engagement code intel over acquired tool sources.
- **modelcontextprotocol/servers → src/memory** (90,673★ repo, active): official reference knowledge-graph memory (entities/relations/observations in JSONL). `npx @modelcontextprotocol/server-memory` (npm `2026.8.31`). Weak (ChatForest 3.5/5: `read_graph` dumps 14k+ tokens, no isolation/temporal) but zero-dependency baseline.

**Tier 2 — real, minor friction on this estate:**
- **renezander030/graphiti-local** (2★): the Graphiti-on-Ladybug+Ollama recipe (§3). POSIX shell commands; estate has Git Bash; needs `uv`. Untested here — flagged.
- **agentic-box/memora** (729★, pushed 2026-09-28): `pip install memora-mcp`; SQLite (+optional S3/R2/D1 sync) structured storage, semantic retrieval, graph relations, `memory_digest(topic)` with source IDs, Mermaid graph viz, `memora-server --graph-port 8765`. Cross-session digest pattern is exactly "cross-engagement memory".
- **basicmachines-co/basic-memory** (4,063★, pushed today): markdown-first local knowledge memory; `claude mcp add basic-memory -- uvx --prerelease=allow basic-memory mcp`; human-readable/git-diffable memory (good for engagement reports), local FastEmbed hybrid search.
- **CheMiguel23/MemoryMesh** (353★, TypeScript, pushed 2026-03-01): schema-driven KG memory (JSON schemas constrain nodes) — strong for structured security entities (host/vuln/cred); `npx`; slightly stale.
- **topoteretes/cognee** (31,219★, pushed today): pip-native core (`cognee-1.6.1-py3-none-any.whl` downloaded here); "Docker is needed for its MCP service" per README — MCP lane needs custom wiring on no-Docker box; default graph engine not confirmed this run (README grep for kuzu/networkx returned nothing).
- **caura-ai/caura** (542★, pushed today, Apache-2.0; ex-MemClaw): governed shared fleet memory — trust tiers, scoped memory, cross-agent outcome propagation, MCP at `/mcp` (Streamable HTTP) built into server. Self-host = `docker compose up` (Postgres+pgvector+Redis+API); README does document "Manual deployment without Docker" (multi-service; not verified). Clients: `pip install caura-client` (1.0.2 on npm too). Conceptually the best "shared governed memory" match; infra-heaviest.
- **mem0ai/mem0** (66,314★, pushed 2026-09-25): SDK memory layer; graph memory wants Neo4j; standalone MCP repo archived Mar 2026 (MCP now cloud-hosted); SDK v2.0.2 fixes GHSA-5gv3-2fv6-jvhx (SQL/Cypher injection). Private-estate fit: weak for MCP lane, fine as SDK.
- **supermemoryai/supermemory** (31,015★, TS, pushed today): memory+context engine "can be run fully locally" — monorepo, stack weight unverified for Windows-native here.

**Tier 3 — recorded, low fit / stalled / frozen:**
- kuzudb/kuzu-mcp-server (42★, **pushed 2025-10-10** — frozen at the archive; official Kuzu MCP; dead-end on py3.14).
- Jakedismo/KuzuMem-MCP (24★, TS memory bank on Kuzu, pushed 2026-02-14).
- jkear/kuzu-memory-graph-mcp, SankarPatnaik/kuzu-knowledge-graph-mcp, NovaAI-innovation/qdrant-kuzu-mcp (0★ each; qdrant+kuzu graph-RAG, pushed 2026-09-26).
- Vela-Engineering/kuzu (§2): valuable multi-writer fork, but no PyPI artifact ⇒ build-from-source only on Windows.
- Kineviz/bighorn, predictable-labs/ryugraph, siafuDB/siafudb-kuzu (§2).
- STiFLeR7/memex (12★, bitemporal codebase KG MCP), mironmax/claudecode-plugins (6★, KG for Claude Code/Codex), 1999AZZAR/project-mcp (3★), EtanHey/brainlayer (9★, SQLite KG + 13-tool MCP), Michael-Obele/sepia (5★, remote KG memory for coding agents), Luqueee/kivgraph (21★, cross-repo semantic code intel on persistent graph), brianmeyer/mollygraph (1★, Ladybug + GLiNER2 extraction local-first graph memory — tiny but exactly the estate pattern), yucx-go/agent-knowledge (3★, CN/EN, zero-vector-dependency long-term memory, PyPI), LAIguapi/layered-memory-mcp (4-layer memory, PyPI, trilingual README), remnic (211★, scoped user-aware memory), tribal-memory/tribal, omega-memory, shaneholloman/mcp-knowledge-graph (server-memory fork with `--memory-path`; listed on Tencent Cloud MCP marketplace 1.2K uses).
- IgorGanapolsky/mcp-memory-gateway → repo now redirects to ThumbGate (pre-action checks; unrelated) — dead end for the gateway-memory idea.

## 6. Cross-engagement memory patterns (what the sources converge on)

- Vela Partners blog (production, quant agents): graph memory = persistent validated patterns with confidence scores; cross-session context reload; social learning across agents; "the graph is the audit log and the active knowledge base at once". Multi-agent writes ⇒ they forked Kuzu for concurrent multi-writer (single-writer Kuzu/Ladybug = one read-write process + read-only readers; the dev.to recipe relies on exactly that model: MCP server owns the single read-write open).
- graphiti-local: writes are never agent-direct — agents propose, human-approved "drain" applies; only the MCP server reads. Temporal KG with bi-temporal validity windows (Graphiti's core feature; ChatForest 4/5).
- Caura: governance first — trust tiers, scoped access tokens, cross-agent outcome propagation; memory as fleet infrastructure.
- memora: `memory_digest(topic)` — retrieval-shaped memory API (digest of memories+TODOs+edges+source IDs) rather than raw graph dumps.
- Engram/mcp-memory-service/basic-memory: single-binary/single-service local memory, agent-agnostic transport (MCP+HTTP/REST) so any harness (CyberStrike, Decepticon, Claude Code) can share one store.
- Estate mapping (my synthesis): MCP gateway already aggregates backends — the cheapest shared-brain increment is mcp-server-ladybug (Cypher over one .lbdb file) or engram (exe) behind the existing gateway; the richest is graphiti-local (temporal KG + Ollama) with the single-writer constraint respected (one drain process); codebase-memory-mcp indexes acquired tooling sources; MemoryMesh-style schemas would structure host/vuln/credential nodes.

## 7. Not done / gaps stated honestly

- Firecrawl discovery never executed (blocked, §0) — every "firecrawl-scrape JS-heavy page" step was substituted with WebFetch/Exa.
- graphiti-local NOT actually run on this box (recipe cited from author's Sept-2026 writeup; `uv` availability untested).
- cognee default graph engine not confirmed; gdotv landscape article and Oulu "Cognitive SOC" PDF found but not deep-read (time-boxed).
- Caura "manual deployment without Docker" not verified step-by-step.
- Vela kuzu fork not built (C++ toolchain path not exercised).

## Artifacts

- Wheels proving native Windows py3.14 support: `out/research/wheels/` (ladybug cp314 win_amd64 5.6MB; mcp_server_ladybug 0.1.2; graphiti_core 0.30.2; cognee 1.6.1).
- Helpers: `out/research/_search_am.py` (exa/fc/ddg), `out/research/_gw_mcp.py` (gateway JSON-RPC probe), `out/research/_awesome.md` (awesome-mcp-servers dump).
