# Research: ad-entra-paths — BloodHound MCP, SpecterOps AI hunting agent, Entra/AWS attack-path tools, AD-graph MCPs

Date: 2026-09-29. Environment context (from ask): Windows Server VM, no Docker engine (GCP no VT-x → no WSL2/nested virt), CyberStrike 1.1.16 + MCP gateway 127.0.0.1:31100 with 43 backends (stdio workers pattern), Ollama qwen3:4b local. Everything below was found via GitHub REST search (`gh api search/repositories`), repo README/release fetches, WebSearch (EN+ZH) and WebFetch (specterops.io) during this session.

## 1. The BloodHound MCP (13 composite tools over CE REST + Neo4j) — IDENTIFIED

**Repo: https://github.com/mwnickerson/bloodhound_mcp** (136★, updated 2026-09-25, GPLv3)
- This is exactly the "13 composite tools" server from the ask. README states: "The server exposes BloodHound CE's REST API and Neo4j graph through a set of **13 composite MCP tools**, **10 reference resources**, and a **system prompt** tuned for offensive security analysis."
- Tools (each with `info_type` selector): `domain_info`, `user_info`, `group_info`, `computer_info`, `ou_info`, `gpo_info`, `graph_analysis`, `adcs_info`, `cypher_query`, `data_quality`, `asset_groups`, `custom_nodes` (OpenGraph CRUD), `file_upload`.
- Resources: `bloodhound://cypher/reference`, `bloodhound://cypher/offensive-queries`, `bloodhound://guides/ad{,-methodology}`, `bloodhound://guides/azure{,-methodology}`, `bloodhound://guides/adcs{,-methodology}`, `bloodhound://opengraph/{guide,examples}`.
- Auth: BloodHound CE token ID+key, HMAC-SHA256-signed requests; startup makes signed read-only `/api/v2/self` call and dies on bad creds. Env: `BLOODHOUND_DOMAIN`, `BLOODHOUND_TOKEN_ID`, `BLOODHOUND_TOKEN_KEY`, optional `BLOODHOUND_PORT/SCHEME/VERIFY_TLS`.
- Install (no clone): `uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp`. Dev: `git clone … && uv sync`. Python 3.11+ + uv → **runs natively on Windows** (pure Python MCP).
- Origin: SpecterOps blog by Matthew Nickerson, 2025-06-04, "Chatting with Your Attack Paths: An MCP for BloodHound" (https://specterops.io/blog/2025/06/04/chatting-with-your-attack-paths-an-mcp-for-bloodhound). Author warns it was built for Claude Desktop → data leaves for Anthropic; use with lab/example data. Video demo: https://youtu.be/eZBT0Iw9CMA
- SpecterOps' own `SpecterOps/skills` repo (685★, LLM-skills marketplace) configures exactly this server in Codex `mcp_servers.bloodhound_mcp` TOML (`uv --directory … run main.py`) — de-facto blessed install.
- **Estate caveat**: needs a reachable BloodHound CE (bhapi REST). BH CE official distribution is Docker-only; bhapi ships as a Linux binary with no Windows release (per official custom-install docs at https://bloodhound.specterops.io/get-started/custom-installation — native Windows requires building the Go bhapi yourself + PostgreSQL + Neo4j, or WSL2, which this VM cannot do without VT-x). So: MCP itself Windows-native; the *backend* is the constraint. Options: bhapi from Go source on Windows, or CE running on any other reachable host.

## 2. BloodHound MCP alternatives (Neo4j-bolt based — no bhapi needed)

**MorDavid/BloodHound-MCP-AI** — https://github.com/MorDavid/BloodHound-MCP-AI (377★, updated 2026-09-26, MIT)
- "First-ever BloodHound AI integration" (Mar 2025 LinkedIn announcement). **75+ specialized tools** derived from BloodHound CE Cypher query library; connects **directly to Neo4j via bolt** (`BLOODHOUND_URI=bolt://localhost:7687`, `BLOODHOUND_USERNAME`, `BLOODHOUND_PASSWORD`).
- Install: `git clone` + `pip install -r requirements.txt`, then MCP config runs `python BloodHound-MCP.py`. Python 3.8+. **Windows-native yes**; works against a Windows-native Neo4j holding BloodHound data (no bhapi/Docker needed).
- Coverage: Kerberoasting/AS-REP, ADCS, NTLM relay vectors, delegation abuse, privesc paths, domain structure, reports. Telegram: t.me/root_sec.

**stevenyu113228/BloodHound-MCP** — https://github.com/stevenyu113228/BloodHound-MCP (160★)
- Also bolt-based. MCP config: `uv run --with mcp[cli],neo4j mcp run server.py` + same three env vars. Custom queries sourced from CompassSecurity/BloodHoundQueries. Windows-native yes (uv + Python).

**art3x/artblood (ArtBlood)** — https://github.com/art3x/artblood (8★, active)
- **Rust analyzer for BloodHound data with an MCP server on board — requires NO Neo4j and NO running BloodHound server.** Imports SharpHound JSON files/dirs/ZIPs into a local indexed cache; search, shortest paths, owned→tier-0, dangerous ACLs, Kerberoastable/AS-REP, AD CS ESC findings, Markdown reports, TUI, Cypher-subset DSL, OpenGraph export, redaction.
- Install: `cargo build --release --workspace` (or `cargo install --path crates/abh-cli`); Windows exe `target\release\abh.exe` noted "not tested" upstream but Rust/MSVC builds natively on Windows. **Best fit for the no-Docker estate**: SharpHound/RustHound JSON → ArtBlood MCP → gateway.

**The-bub/Agent-BloodHound** — https://github.com/The-bub/Agent-BloodHound (0★, FR/EN)
- Claude Code agent + MCP + Python REPL, read-only & audited, queries a BH CE: Kerberoastables, paths to tier-0 (abusable edges only), DCSync, delegations, ACL abuse, blast radius. Requires Docker for its BH CE base → poor fit here; useful pattern reference.

**Thin/0-star same-name repos (observed, not evaluated — dead ends for value)**: NexKosh/BloodhoundMCP, h4wkst3r/bloodhound-mcp-server, sheb1853/bloodhound-mcp-gemini, tac01337/bloodhound-mcp, hHiteshhh/MCP-Bloodhound, iabdullah215/pathhound-mcp, schwarztim/sec-bloodhound-mcp (all 0★, no substantive docs fetched).
**NOT BloodHound (excluded after README check)**: tiluckdave/hound-mcp (npm dependency-vuln scanner using deps.dev+OSV), netwrix/AIHound (AI-app credential scanner), apache/bloodhound (Apache issue tracker), njdaniel/bloodhound (K8s IR agents), BryanDuplantis/concert-bloodhound (concerts).

## 3. SpecterOps AI hunting agent — IDENTIFIED (commercial, not self-hostable)

- **"BloodHound Hunter"** — AI agent interface inside **BloodHound Enterprise**, built on MCP. Announced 2026-07-28 in press release "SpecterOps Extends Attack Path Management Across Hybrid and Agentic AI Workflows" (https://specterops.io/news/specterops-extends-attack-path-management-across-hybrid-and-agentic-ai-workflows). Connects approved AI agents/knowledge sources to BH findings; prioritizes remediation; translates findings for execs. Same release adds **AWS** and **Microsoft Entra Agent ID** platform support (Copilot/AI identities) to the BHE graph (blogs: 2026/07/28 "Introducing Attack Path Management for Entra Agents in BloodHound Enterprise" and "BloodHound Enterprise AWS Attack Path Management"; platform page https://specterops.io/platform/ai-attack-path-management).
- Commercial BHE feature — **no open-source release, nothing to install on this estate**; noted so the estate knows the vendor-anchored reference architecture (MCP + curated attack-path graph).
- Note: "Abbot" name from my initial hypothesis was WRONG — no SpecterOps product named Abbot found; the AI agent is BloodHound Hunter.

## 4. Entra attack-path tooling

- **dafthack/GraphRunner** — https://github.com/dafthack/GraphRunner (1345★). PowerShell post-exploitation for Microsoft Graph/Entra: recon, persistence, pillaging (mail/SharePoint/Teams), OAuth consent-grant flows, CA policy dumps, app registrations. `Import-Module .\GraphRunner.ps1; Get-GraphTokens`. No third-party modules; **"Works with Windows and Linux"**. Windows-native: yes.
- **dirkjanm/ROADtools** — https://github.com/dirkjanm/ROADtools (2725★). ROADrecon et al., Entra/Azure AD enumeration + abuse; `pip install roadrecon`. Windows-native: yes (Python).
- **SpecterOps/AzureHound** — https://github.com/SpecterOps/AzureHound (962★). Azure/Entra data exporter for BloodHound CE. Release v3.1.1 ships **AzureHound_v3.1.1_windows_amd64.zip** → native Windows collector.
- **x0pr4nt3s/graphrunner** — Go M365 post-exploitation framework, "80+ subcommands, single static binary" — native Windows exe, no PowerShell dependencies.
- **OID-See/OID-See** — https://github.com/OID-See/OID-See (38★). Entra third-party/multi-tenant app risk: Graph read-only scanner + browser-only graph viz; v1.1.1 emits **BloodHound OpenGraph** output; MS official permission tiering (levels 1–5); SARIF 2.1. Python 3.10+. Windows-native: yes.
- **mvelazc0/BadZure** — https://github.com/mvelazc0/BadZure (527★, BH Arsenal 2024 & 2026). Deploys deliberately misconfigured Entra tenants + Azure subscriptions with traversable attack paths (atomic templates: ApplicationOwnershipAbuse, ApplicationAdministratorAbuse, CloudAppAdministratorAbuse, ManagedIdentityAbuse, KeyVaultSecretTheft, StorageCertificateTheft, CosmosDBSecretTheft). Install: clone + `pip install -r requirements.txt`; needs `az login` (Global Admin) + Terraform; README explicitly documents Windows venv activation. **Lab generator to exercise the Entra tooling above.**
- **hieuttmmo/entraid-mcp-server** — https://github.com/hieuttmmo/entraid-mcp-server (41★). FastMCP server for Microsoft Graph: users, groups, sign-in logs, MFA status, devices, Conditional Access policies; permission-suggester. Run via `fastmcp dev src/msgraph_mcp_server/server.py`. Windows-native: yes. Closest OSS "MCP exposing Entra graph queries".
- **microsoft MCP Server for Enterprise** (official, preview) — catalog entry in https://github.com/microsoft/mcp (3723★): repo microsoft/EnterpriseMCP, docs https://learn.microsoft.com/graph/mcp-server/overview. **REMOTE MCP at `https://mcp.svc.cloud.microsoft/enterprise`** — natural language → Graph API, read-only enterprise scenarios incl. security posture, privileged access, application risk, access governance, audit telemetry. No local install at all (HTTP MCP) → works from this VM's gateway if it can proxy remote HTTP MCP.
- **Azure/Stormspotter** — https://github.com/Azure/Stormspotter (1721★). Azure/AzureAD graphing for red teams; effectively superseded by AzureHound (lower priority; heavy python+neo4j+PS frontend).
- **cloudbreach/AuthStrike** (20★) — Entra attack-path simulation (device-code, token handling, Graph access). Edge case; noted.
- **O3-Cyber/oidc-code-to-cloud** (12★) — maps attack paths Entra ID ↔ GitHub.
- Also seen (thin): Dfrank77/entra-attack-path-visualizer, loredan1994/entra-relationship-explorer, tomerblum/azath (assumed-breach Azure/Entra analyzer w/ LLM explanations), FortisFortuna-br/pulse-ad (hybrid AD→Entra path analysis over SharpHound+AzureHound), HaakConsulting/Pathrank (impact-ranking layer over BloodHound).

## 5. AWS attack-path tooling

- **nccgroup/PMapper** — https://github.com/nccgroup/PMapper (1582★). Models AWS IAM users/roles as directed graph; privilege-escalation + alternate-path detection; local simulation of AWS authorization ("could launch an EC2 that reads the S3"). `pip install principalmapper` (needs pydot + graphviz, both Windows-available). Windows-native: yes.
- **BishopFox/cloudfox** — https://github.com/BishopFox/cloudfox (2582★). Situational-awareness for cloud pentests; `cloudfox.exe` — release v2.0.5 ships **cloudfox-windows-amd64.zip**. Native Windows: yes. (Companion lab: BishopFox/cloudfoxable, 475★.)
- **RhinoSecurityLabs/pacu** — https://github.com/RhinoSecurityLabs/pacu (5345★). AWS exploitation framework; `pip install pacu`. Python; mostly Windows-OK (some modules assume nix tooling) → windows: native with caveats.
- **awslabs/mcp — official AWS MCP Server** — https://github.com/awslabs/mcp (9743★). Remote managed MCP: `uvx mcp-proxy-for-aws@latest https://aws-mcp.us-east-1.api.aws/mcp` — full AWS API coverage for agents, syntactically validated calls, IAM-scoped, CloudTrail-audited. Lets the estate's agent do IAM/role/trust enumeration that feeds pmapper/cloudfox analysis. Windows-native: yes (uvx). Also in-repo: c7n-mcp, AWS Documentation/Knowledge servers, terraform/cdk IaC servers.

## 6. Other MCPs exposing AD graph queries / AD offensive MCP frameworks

- **neo4j/mcp (official Neo4j MCP Server)** — https://github.com/neo4j/mcp (297★). `pip install neo4j-mcp-server`, `python -m neo4j_mcp_server`. Tools: `get-schema`, `read-cypher` (read-only enforced via EXPLAIN classification), `write-cypher` (disable w/ `NEO4J_MCP_READ_ONLY=true`), `list-gds-procedures`. **Point it at any BloodHound Neo4j (bolt) → generic AD-graph MCP via Cypher.** Windows-native: yes.
- **capture0x/AdStrike** — https://github.com/capture0x/AdStrike (357★). AD attack framework v5.0: 52 attack modules + 4 utilities; **MCP server exposing all 53 tools** to Claude Code/Cursor/Claude Desktop (host LLM is the brain, no API key). Wraps impacket, NetExec, Certipy, Kerbrute, BloodHound, PowerView, Rubeus. Kali/Parrot badge but Python — partial Windows fit.
- **capture0x/AdAgent** — https://github.com/capture0x/AdAgent (9★, new). Autonomous AD kill-chain agent — 59 tools/139 techniques; backends: **Ollama (local, free)**, Claude API, or MCP-server mode where Claude Code drives it. Ships `.mcp.json` for one-approval registration. Estate has Ollama qwen3:4b → direct fit.
- **alpadalar/ActiveDirectoryMCP** — https://github.com/alpadalar/ActiveDirectoryMCP (47★). Python LDAP MCP, 43 tools: users/groups/computers/OUs CRUD + security auditing (privileged groups, inactive users, password policy). Windows-native: yes (Python+LDAP).
- **ruudmens/Koppla** — https://github.com/ruudmens/Koppla (57★). `pip install koppla`; natural-language AD queries/management; Fernet-encrypted config manager (`koppla-config configure`). Windows-native: yes.
- **Evaluris-Solutions/claude-active-directory** (17★) — Claude Code agent harness for AD offensive security (8 skill domains, 13 slash commands, 7 agents, ROE-safe). Skills-shaped, matches estate style.
- **ADScanPro/Claude-AD** — https://github.com/ADScanPro/Claude-AD (207★). **Claude Code plugin**: skills/agents/commands (`/ad-scope`, `/ad-recon`, `/ad-attack-paths`) encoding internal-AD pentest methodology; drives netexec, impacket, certipy, bloodyAD, BloodHound CE; OPSEC/MDI telemetry notes; DORA/NIS2/ENS control mapping. Install: `/plugin marketplace add ADScanPro/Claude-AD` then `/plugin install claude-ad@claude-ad`. Companion engine: **ADScanPro/adscan** (728★) — automated low-priv→DA chain (104 techniques, BloodHound-compatible paths, Linux/macOS/Windows).
- **Yenn503/AdPack** (low stars) — Go, state-aware AD orchestration wrapping nxc/impacket/certipy/BloodHound/TeamsPhisher/GraphRunner/AADInternals/TokenTactics.
- LDAP-specific MCPs: trxo/ldap-mcp (11★), SCKelemen/ldap-mcp (2★), schwarztim/sec-ldapdomaindump-mcp (ldapdomaindump wrapper), markizano/ldap-mcp-server, CData LDAP/AD MCP servers (commercial JDBC). Generic query surfaces, not attack-path aware.
- **Microsoft 365 "agent365" remote MCPs** (microsoft/mcp catalog): Calendar/Mail/Copilot-Chat/Teams/User/Admin-Center at `agent365.svc.cloud.microsoft/agents/tenants/{tid}/servers/...` — Graph data planes, not attack-path tools; Entra-tenant scoped. Adjacent awareness only.
- BloodHound ecosystem analysis (non-MCP, bolt/JSON based): PlumHound (1319★, blue/purple reporting), GoodHound (488★), ImproHound (325★, tiering violations), Max (532★), cypheroth (256★), NetSPI/AD-PathFinder (242★ — SharpHound+OpenGraph attack-path mapping across AD/ADCS/SCCM/MSSQL, `pip install -e .`, Python 3.9+), GoFetch (632★, auto-exercises BH attack plans), bofhound (415★, BOF→BH JSON), ShareHound (313★).
- **Collectors (Windows-native)**: SpecterOps/SharpHound (1354★, C#, native), **g0h4n/RustHound-CE** (597★; release v2.5.14 ships Windows-msvc-x86_64 and Windows-gnu-x86_64 zips — single-exe CE collector, no .NET), RustHound (legacy, 1175★), flashingestor (177★ TUI).
- **SpecterOps collectors feeding OpenGraph attack paths**: MSSQLHound (347★), ConfigManBearPig (SCCM, 150★), JamfHound (137★), GitHound (147★), 1PassHound, SnowHound, SCOMHound — all extend the BH graph into adjacent estate surfaces.
- Misc SpecterOps of note: bloodhound-cli (124★), TierZeroTable (280★), BloodHoundQueryLibrary (207★), Nemesis (1003★ offensive enrichment pipeline), Jailbreaker-CE (107★, chatbot/agent jailbreak evaluation).

## 7. Windows/no-Docker viability summary for THIS estate

| Tool | Needs | Windows native |
|---|---|---|
| mwnickerson/bloodhound_mcp | Python 3.11+uv + reachable BH CE REST (bhapi: Linux-only binary, buildable in Go; or remote host) | MCP yes / backend is the blocker |
| MorDavid/BloodHound-MCP-AI | Python + Neo4j bolt (Neo4j Community runs native on Windows/Java) | yes |
| stevenyu113228/BloodHound-MCP | uv + Neo4j bolt | yes |
| art3x/artblood | Rust toolchain; SharpHound JSON only; no server | yes |
| neo4j/mcp | pip + bolt | yes |
| AdAgent (Ollama mode) | Python + local Ollama (present: qwen3:4b) | yes |
| AdStrike / adscan / Claude-AD / AD-PathFinder | Python / Claude Code plugins | yes (some wrapped tools Kali-first) |
| GraphRunner (dafthack) | PowerShell | yes |
| ROADtools / PMapper / Pacu / OID-See / entraid-mcp | pip (+graphviz for PMapper) | yes |
| cloudfox / AzureHound / RustHound-CE / x0pr4nt3s-graphrunner | prebuilt Windows release zips | yes |
| BadZure | python + az cli + terraform | yes |
| Microsoft Enterprise MCP / AWS MCP Server | remote HTTP MCP endpoints | yes (nothing to install) |
| BloodHound Hunter (SpecterOps) | commercial BHE subscription | not self-hostable |

## 8. Every query issued this session

GitHub `gh api search/repositories` q=:
1. `bloodhound mcp` 2. `entra attack path` 3. `org:SpecterOps` 4. `mcp entra OR azure active directory graph` 5. `GraphRunner entra` 6. `mcp neo4j cypher` 7. `GraphRunner Microsoft Graph` 8. `principalmapper` 9. `cloudfox` 10. `org:neo4j mcp` 11. `pmapper AWS privilege escalation` 12. `mcp aws privilege escalation attack path` 13. `mcp entra OR "microsoft graph" security offensive` 14. `ldap mcp server` 15. `"active directory" mcp` 16. `org:awslabs mcp` 17. `org:microsoft mcp` 18. `sharphound mcp OR kerberos mcp server OR "attack path" mcp azure` 19. `topic:bloodhound` 20. `entra mcp in:name,description` 21. `graphrunner mcp OR "mcp" graphrunner` 22. `principal mapper AWS IAM` 23. `mcp server cyberstrike OR "attack path" mcp in:name`
Direct repo fetches (gh api repos/…): nccgroup/pmappers (404), nccgroup/PMapper, nccgroup/libpacu (404), dirkjanm/ROADtools, Azure/Stormspotter, RhinoSecurityLabs/pacu.
README fetches (gh api repos/X/readme): MorDavid/BloodHound-MCP-AI, mwnickerson/bloodhound_mcp, stevenyu113228/BloodHound-MCP, tiluckdave/hound-mcp, SpecterOps/skills, art3x/artblood, The-bub/Agent-BloodHound, neo4j/mcp, capture0x/AdStrike, capture0x/AdAgent, ruudmens/Koppla, mvelazc0/BadZure, dafthack/GraphRunner, OID-See/OID-See, alpadalar/ActiveDirectoryMCP, nccgroup/PMapper, hieuttmmo/entraid-mcp-server, NetSPI/AD-PathFinder, ADScanPro/Claude-AD, microsoft/mcp (grep graph/entra), awslabs/mcp (grep core/install).
Release fetches: BishopFox/cloudfox (latest → v2.0.5, windows-amd64 asset), g0h4n/RustHound-CE (v2.5.14, Windows msvc/gnu assets), SpecterOps/AzureHound (v3.1.1, windows assets).
WebSearch: `BloodHound MCP server 13 tools BloodHound CE REST API Neo4j` / `SpecterOps Abbot AI attack path agent BloodHound` / `BloodHound CE native install Windows without Docker neo4j bhapi` / `Microsoft Graph MCP server official preview entra developers` / `BloodHound MCP AD域 内网 渗透 AI agent 攻击路径` (ZH).
WebFetch: specterops.io blog 2025/06/04 MCP post; specterops.io press release (BloodHound Hunter / AWS / Entra Agent ID).

## 9. Dead ends / notes
- "Abbot" as a SpecterOps AI agent name: disproven (no such product found).
- tiluckdave/hound-mcp, netwrix/AIHound, apache/bloodhound, concert-bloodhound, njdaniel/bloodhound: name collisions, out of domain.
- Stormspotter: legacy path, superseded by AzureHound.
- BloodHound CE server on this VM: blocked without Docker/WSL2; practical local stack = RustHound-CE (collect) → ArtBlood (MCP analyze) and/or Neo4j-Community-Windows → MorDavid/stevenyu bolt MCPs; mwnickerson 13-tool MCP once a bhapi endpoint exists (build from Go source or remote host).
- CData LDAP/AD MCP servers: commercial JDBC wrappers, excluded.
- Chinese-language sweep (CSDN/ZONE.ci) confirmed the "BloodHound Agent" trend (multi-agent red-team stacks reaching DC in minutes) but surfaced no new tool beyond what GitHub yielded.

---

# SESSION-2 ADDENDUM (2026-09-29, second research context over the same lane)

This context re-ran the lane end-to-end and merged results here. Everything below was
executed/fetched in this context (`gh api`, exa API, WebFetch, curl raw.githubusercontent.com).
Where star/push numbers differ from sections 1–8 above, mine are `pushed_at` (code activity);
the earlier numbers appear to be `updated_at` (metadata touches) — both fetched live, days apart at most.

## A2. Verified again this context (independent confirmation of the core haul)

- mwnickerson/bloodhound_mcp: 136★, pushed_at 2026-08-19, Python, GPL-3.0. README full-read:
  exactly **13 composite tools** (domain/user/group/computer/ou/gpo_info, graph_analysis,
  adcs_info, cypher_query, data_quality, asset_groups, custom_nodes, file_upload) + 10 resources
  + `bloodhound_assistant` prompt. Install line verbatim:
  `uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp`
  (env BLOODHOUND_DOMAIN/TOKEN_ID/TOKEN_KEY; BLOODHOUND_PORT/SCHEME overridable; signed read-only
  /api/v2/self at startup). Repo contents: pyproject.toml, uv.lock, main.py, lib/, tests/, examples/.
  SpecterOps blog 2025-06-04 fetched again: author Matthew Nickerson, SpecterOps — REST-first client
  + CypherClient over Neo4j; repo linked from the post.
- SpecterOps org sweep (`orgs/SpecterOps/repos?sort=pushed`): BloodHound 3446★ (pushed today),
  AzureHound 962★ (2026-09-21), SharpHound 1354★, skills 685★, TierZeroTable 280★,
  BloodHoundQueryLibrary 207★, Nemesis 1003★, pass-the-passkey 227★ — plus NEW 2026 repos below.
- Release assets re-verified: AzureHound v3.1.1 `AzureHound_v3.1.1_windows_amd64.zip`;
  cloudfox v2.0.5 `cloudfox-windows-amd64.zip`; Flangvik/TeamFiltration v3.5.5
  `TeamFiltration-v3.5.5-win-x86_64.zip` (TeamFiltration 1410★, C#, pushed 2026-03-09).
- Install lines README-verified this context: ROADtools `pip install roadrecon` (PyPI);
  PMapper `pip install principalmapper`; GraphRunner `Import-Module .\GraphRunner.ps1` →
  `Get-GraphTokens`; AdStrike `git clone` + `install.sh`/`run.sh` (bash — estate Git Bash OK).
- VM toolchain hard facts (commands run): `uv --version` → **uv 0.12.20 present**;
  `go version` → **go NOT installed**; `cargo --version` → **cargo NOT installed**.
  Consequence: Go tools (BlakHound, stave, perspectivegraph) and Rust ArtBlood cannot be
  built on this VM today without adding toolchains (ArtBlood v1.0.2 release ships only
  `abh.tar.gz`, no .exe).

## B2. NEW findings (not in sections 1–8)

### SpecterOps, September 2026
- **SpecterOps/OpenHound** — 30★, pushed 2026-09-25. The collector *framework* (collect →
  preprocess → convert) behind ConfigManBearPig: build BloodHound OpenGraph datasets for
  File Ingest with raw-data-first reproducibility; extensions install via pip extras;
  sibling collectors openhound-jamf / openhound-okta / openhound-github. Python → Windows-native.
  VALUE high: the dockerless way to extend the BH graph beyond AD.
- **SpecterOps/Blacklight** — 85★, pushed 2026-09-29 (today). Cross-platform (Win/mac/linux)
  endpoint triage + session analysis of AI-agent artifacts (Codex, Claude Code, Cursor,
  Antigravity, Grok). Adjacent lane; VALUE medium.
- **SpecterOps/DAWGS** — 21★, pushed 2026-09-25: openCypher abstraction over Postgres/Neo4j
  (BloodHound v8's backend). VALUE low for estate today.
- Also seen fresh: bloodhound-scim-extension (3★), chow (8★ BH payload validator),
  Oracle (2★, undocumented).

### BloodHound/AD MCP space
- **adithyan-ak/AgentHound** — 442★, pushed 2026-09-29 (today). "BloodHound for AI agent
  infrastructure": recon/credential-looting/exfiltration/poisoning + attack-path analysis
  across MCP, A2A, gateways. Not AD — it maps the estate's OWN MCP-gateway attack surface.
  VALUE medium (defensive crossover for the 43-backend gateway).
- **The-bub/Agent-BloodHound** README full-read: FR/EN read-only Claude agent (MCP + Python
  REPL) over BH CE — kerberoastables, tier-0 paths over abusable edges only, blast radius,
  owned-tracking, `runs/audit.log`. Confirms section 2; 0★, low-medium.
- Schwarztim pair sec-bloodhound-mcp (JS, 9 open issues) + sec-ldapdomaindump-mcp — low.
- iabdullah215/pathhound-mcp — created 2026-07-07, 0★ — low.
- ktol1/RedTeam-Agent (72★, zh; gogo/fscan/httpx/nuclei/impacket over MCP) surfaced again —
  adjacent, already covered by estate fronts; noted.

### Entra lane additions
- **Semperis/EntraGoat** — 986★, PowerShell, pushed 2026-05-06. Deliberately vulnerable Entra
  ID environment with hands-on attack challenges — the training range the section-4 tooling
  (and BadZure) points at. Windows-native. VALUE high (zero-docker lab).
- **Gerenios/AADInternals** — 1699★, PowerShell, pushed 2025-09-30 (canonical Entra/M365
  offense module; synacktiv/AADOutsider-py 64★ is the Python rewrite of its AsOutsider).
  Windows-native. VALUE medium-high.
- **Microsoft MCP Server for Enterprise — provisioning recipe verified from learn.microsoft.com
  (ms.date 2026-05-20)**: endpoint `https://mcp.svc.cloud.microsoft/enterprise`; service-principal
  appId `e8c77dc2-69b3-43f4-bc51-3213c9d915b4`; enable once per tenant with
  `Install-Module Microsoft.Entra.Beta` (≥1.0.13) → `Connect-Entra -Scopes
  'Application.ReadWrite.All','Directory.Read.All','DelegatedPermissionGrant.ReadWrite.All'` →
  `Grant-EntraBetaMCPServerPermission -ApplicationName VisualStudioCode` (or register a custom
  client app + grant `MCP.*` delegated scopes). Read-ONLY (44 MCP.*.Read.All scopes enumerated;
  no write ops). Disable = `PATCH /servicePrincipals(appId='e8c77dc2-…') {"accountEnabled": false}`.
- **NotSoSecure/TokenMesh** — 7★, created 2026-04-17, Python. "Cloud Security Assistant for
  Azure (MCP + LLM)": live identity/role/resource analysis surfacing privilege risks and attack
  paths; Claude-Desktop MCP mode or OpenAI CLI mode. Windows-native. VALUE medium (young).
- **hieuttmmo/entraid-mcp-server** README-verified: FastMCP, modular Graph resources (privileged
  users, sign-in logs, MFA status, groups/apps CRUD). `fastmcp dev src/msgraph_mcp_server/server.py`.
- Tiny/early recorded: Sultan-zd/mcp-entra-secops (read-only Entra incident MCP, glama-listed,
  repo not read), entraadm-mcp on PyPI (`pip install entraadm-mcp`, sign-in/audit triage, ≥3.10),
  Dfrank77/entra-attack-path-visualizer (0★), Assumed-Breach/Azure_Attack_Path_Analyser (1★),
  stasdot/entra-audit-agent (1★, EntraGoat-tested), orelsv/chat-with-your-entra (2★, detects
  4/6 EntraGoat scenarios with GPT-4o).
- Context docs (not tools): Datadog Security Labs 2026-06-18 "Entra Agent ID: Inside a
  cross-tenant agent compromise"; CSA research note 2026-04-28 Entra Agent ID admin-takeover.

### AWS lane additions
- **jusso-dev/BlakHound** — local-first AWS attack graph (identities/policies/workloads/networks
  → SQLite `~/.blakhound/blakhound.db`), CLI **and MCP**, Go-computed deterministic edges with
  policy-statement evidence and honest possible/unknown labeling; standard AWS credential chain.
  README promises prebuilt Windows-amd64 release binaries, but `releases/latest` = 404 (no
  releases yet) → today it's `go install github.com/jusso-dev/BlakHound/cmd/blakhound@latest`
  and go is absent on this VM. VALUE medium-high (exactly the missing AWS attack-path MCP;
  watch for first release).
- **hotnops/apeman** — 264★ AWS attack-path management ("Walking on the Moon"). README:
  requires Docker + docker-compose → **blocked on this no-Docker estate**. VALUE low here.
- **sufield/stave** — 45★, Go, pushed 2026-09-28: offline AWS config verifier proving compound
  attack paths from snapshots, zero credentials. `go install` (go missing). VALUE medium.
- **luiacuaniello/perspectivegraph** — 8★, Go, pushed TODAY 2026-09-29: attack-path engine for
  AWS+K8s correlating scanners into one graph, PR-blocking. VALUE low-medium (watch).
- **DenizParlak/heimdall** — 158★, Python, privesc paths across 10+ AWS services. VALUE medium.
- Recorded small: andrewkrug/iam-recon (4★), SecurityRiskAdvisors/neph (8★),
  DataDog/pathfinding-labs (60★ lab), theanshsonkar/emfirge (4★), gabrielPv/regresso (10★),
  Baneado98/cloud-pathfinder (0★, IaC attack-path MCP + x402 API).
- BloodHound Hunter press coverage re-confirmed via Help Net Security 2026-07-28
  (helpnetsecurity.com/2026/07/28/specterops-bloodhound-hunter/): Hunter = MCP-based AI agent
  interface into BHE findings; same launch added AWS attack-path management (Privilege Zones)
  and Entra Agent ID extension (Copilot-agent indirect privilege paths). Commercial only.

### Graph/Neo4j MCP additions
- **neo4j-contrib/mcp-neo4j** — 979★ (Neo4j Labs; the older/established line vs neo4j/mcp 276★).
  `servers/mcp-neo4j-cypher` runs Cypher against any Neo4j (incl. a BloodHound one); APOC
  required for `get_neo4j_schema` (README-verified). pip/uvx. Windows-native. VALUE medium-high
  as the generic escape hatch paired with BloodHoundQueryLibrary.

## C2. Session-2 query log (complements section 8)

- Bash/env: `gh auth status`; `env | grep -E FIRECRAWL|EXA`; Firecrawl POST /v1/search → **401:
  this shell's FIRECRAWL_API_KEY is the literal placeholder `${FIRECRAWL_API_KEY}` (len 20)**;
  `grep -ri firecrawl ~/.agents/agents.json` → local firecrawl = self-hosted docker stack :3002
  via mcp-proxy :31114, no `fc-` key on disk; probes `:3002/v1/search` → 404 (search needs
  credits), `:31114` → refused; one `:3002/v1/scrape` attempt hung → cancelled, not retried
  (deep-reads via WebFetch + raw.githubusercontent instead).
- exa searches: "MCP server that exposes BloodHound Active Directory attack path queries to
  LLM agents"; "SpecterOps AI agent hunting attack paths BloodHound autonomous"; "Entra ID Azure
  attack path analysis MCP server natural language privilege escalation tool 2026"; "official
  Neo4j MCP server run Cypher queries model context protocol"; (zh) AD攻击路径 MCP BloodHound
  AI agent; (ja) Entra ID Azure 特権昇格 MCP.
- gh search/repositories q=: `bloodhound+mcp`; `attack+path+mcp`; `entra+mcp`; `aws+attack+path`
  (sort=stars); `active+directory+mcp in:name,description`; `GraphRunner`; `AADInternals`;
  `TeamFiltration`; `entragoat OR "entra goat"`; (one `azure attack path` call died with
  PROTOCOL_ERROR — covered by exa instead; one transient 403 rate-limit, then rate_limit showed
  core 5000/5000, search 30/30 and work continued).
- gh orgs/SpecterOps/repos?sort=pushed&per_page=30.
- gh repos/ + readmes (gh api or curl raw): mwnickerson/bloodhound_mcp (full + contents/ +
  default branch), MorDavid (60ln), capture0x/AdStrike, capture0x/AdAgent, tiluckdave/hound-mcp,
  jusso-dev/BlakHound, SpecterOps/{Blacklight,DAWGS,OpenHound,ConfigManBearPig}, The-bub/
  Agent-BloodHound, hotnops/apeman, sufield/stave, NotSoSecure/TokenMesh, Yenn503/AdPack,
  art3x/artblood (+releases), hieuttmmo/entraid-mcp-server, dirkjanm/ROADtools (install),
  nccgroup/PMapper (install), dafthack/GraphRunner (install), neo4j-contrib/mcp-neo4j cypher
  (install).
- gh releases/latest: SpecterOps/AzureHound, BishopFox/cloudfox, jusso-dev/BlakHound (404),
  Flangvik/TeamFiltration, art3x/artblood.
- WebFetch: helpnetsecurity 2026/07/28 specterops-bloodhound-hunter;
  learn.microsoft.com /graph/mcp-server/mcp-server-sample-prompts (full scope list) and
  /graph/mcp-server/get-started (endpoint + provisioning); specterops.io 2025/06/04 MCP post
  (author confirm).
- List walks: punkpeye/awesome-mcp-servers (4,541 lines, downloaded out/research/_awesome_mcp.md;
  grep bloodhound|active?directory|ldap|entra|azure|neo4j|kerberos → only Azure mgmt/FinOps +
  nitin27may/ms-graph-mcp — **no offensive-AD entries**, itself a finding); corca-ai/
  awesome-llm-security grep → no matches; heywoodlh/awesome-offensive-security grep → no matches.
- HN algolia API ("bloodhound MCP", "specterops" stories) → nothing on-domain.
- DDG/ddgs: not needed (exa+gh covered; no lasting rate-limit).

## D2. Session-2 dead ends / corrections
- Wrong-name 404s resolved by search: mnxsyy/GraphRunner → dafthack/GraphRunner;
  dirkjanm/AADInternals → Gerenios/AADInternals; ShaneYoung/TeamFiltration → Flangvik/TeamFiltration;
  cyfinoid/azure-attack-paths → does not exist (404), abandoned.
- tiluckdave/hound-mcp re-confirmed a false friend (deps.dev/OSV package scanner, `npx hound-mcp`).
- Hosted Firecrawl unusable from this shell (placeholder key) — documented workaround attempt
  via the estate's self-hosted stack failed (search endpoint 404s without credits; scrape hung).
- Go/cargo absent on VM → BlakHound, stave, perspectivegraph, ArtBlood are "native-in-principle,
  blocked-today" (add toolchains or wait for release binaries).
