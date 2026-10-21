# CONSOLIDATED — research fleet output, merged and ranked

Date: 2026-09-29. Merged from 45 fleet files in `out/research/`:

- **Round-1 lanes (12):** browser-offense.md (2 sessions), ad-entra-paths.md (2 sessions), c2-agentic.md, exploit-dev.md, llm-fuzzing.md, cloud-ai-security.md, agent-memory.md, model-cascade.md, mcp-tool-hubs.md (2 passes), pentagi-hardening.md, wildcard-2026.md, deepweb-coverage.md
- **Deep-dives (24):** all `dive-*.md` — ArtBlood, AzureHound, CloakBrowser, CloudFox, EntraGoat, GraphRunner, Microsoft-MCP-Server-for-Enterprise, OpenHound, PMapper, ROADtools, RustHound-CE, Sliver (native MCP), SquidC5, WonderSuite, anything-analyzer, bloodhound_mcp (13 tools), cloakbrowser-mcp, js-reverse-mcp, mitmproxy-mcp, mitre-mcp (Caldera plugin), mythic-ornn, nodriver-proxy-mcp, stealth-browser-mcp, x746b-sliver-mcp
- **Onion lanes (3):** onion-research.md (round 3), onion-forums.md, onion-tools.md
- **Gap/adversarial lanes (4):** gap-chase.md, adv-academic.md, adv-nonenglish.md, adv-social.md
- **Round-2/aux:** deepweb-coverage-round2.md, gcp-windows-docker.md

Where lanes disagreed, the deep-dive evidence wins; where no dive exists, the later/more-verified lane statement wins and the discrepancy is kept in §6.

## 0. Estate constraints (verified on this VM across lanes)

- Windows Server (10.0.26100), **no Docker engine, no VT-x → no WSL2/Hyper-V** (GCP docs: only Linux-KVM nested virt supported; Hyper-V unsupported — `gcp-windows-docker.md`). Docker-era stacks go to a remote Linux worker (`DOCKER_HOST=ssh://…`, provision script exists).
- Python 3.14.6 default (`C:\Python314`) **plus 3.12.10 at `C:\Python312`** — many pins break on 3.14 (kuzu, stealth-browser pydantic 2.11.7, mitmproxy-mcp `<3.14`, nodriver-proxy-mcp `<3.14`, PMapper `collections.Mapping`); use 3.12 venvs or uv.
- Node v24.21.0, uv 0.12.20, git/gh (Prekzursil), Ollama qwen3:4b. **nuclei/ffuf/sqlmap already on PATH; nmap is not; go/cargo absent** (ArtBlood dive added a MinGW toolchain; BlakHound/stave/perspectivegraph remain build-blocked on Go).
- Tor installed and left running: SocksPort 9050 (service) + 9150 (fallback), verified `IsTor:true` in 3 lanes.
- `FIRECRAWL_API_KEY` process env is the literal placeholder `${FIRECRAWL_API_KEY}` — broken in every lane; **the real key lives in the Windows User registry (`fc-213…`, 35 chars) and works** (gap-chase + deepweb found/verified this; other lanes worked around it). Fix at source recommended.
- MCP gateway 127.0.0.1:31100 (`cyberstrike-gateway 1.29.0`): anonymous surface = 3 harness meta-tools; darknet backend = 66 tools (37 keyless-live, map in deepweb-coverage-round2 §5).

## 1. Ranked master table (value descending, Windows-native first)

Install = the real, verified-or-README-anchored command. "✓run" = executed on this VM by a dive/lane; "read" = metadata/README/source-verified only.

### Tier A — HIGH value, Windows-native (no Docker)

| # | Tool | Repo | Install | Windows | Evidence |
|---|---|---|---|---|---|
| 1 | js-reverse-mcp | zhizhuodemao/js-reverse-mcp (2853★, active) | `npx js-reverse-mcp` (Node≥20.19, system Chrome) | native ✓run | Dive: full MCP handshake, 24 tools, headed Chrome launched on VM; breakpoints/XHR-breakpoints/Set-Cookie tracing, persistent-login profile, own Patchright fork; 106/114 tests pass (8 are Windows-only test-env failures) |
| 2 | CloudFox | BishopFox/cloudfox (2583★, MIT, pushed 2026-08-20) | release `cloudfox-windows-amd64.zip` (v2.0.5) | native ✓run | Dive: sha1-verified exe executed on VM; 34 AWS / ~60 GCP commands, IAM privesc (iam-simulator/pmapper/cape/foxmapper); gotcha: region-hang fix (#134) only on main until next tag |
| 3 | ROADtools | dirkjanm/ROADtools (2725★, MIT) | `pip install roadrecon roadtx` | native ✓run | Dive: install + CLI smoke + offline dump→GUI→API e2e on py3.14; roadtx 1.22.1 PRT/passkey/Windows-Hello flows; Selenium flows need Firefox+geckodriver |
| 4 | Sliver (native MCP) | BishopFox/sliver (11,929★, v1.7.7 2026-09-03) | release `sliver-server_windows-amd64.exe` + `sliver-client_windows-amd64.exe` | native (read) | Dive: `client/mcp/*` in v1.7.7 tree; stdio (`sliver-client mcp`) + token-authed HTTP/SSE (`mcp start --transport http`, default 127.0.0.1:8080); 11 fs/session tools; agentic-loop doc real; one MCP issue (#2294) fixed upstream |
| 5 | RustHound-CE | g0h4n/RustHound-CE (598★, MIT, v2.5.14) | release `rusthound-ce-Windows-msvc-x86_64.zip` | native ✓run | Dive: exe run on VM, PE-import-verified pure native (no .NET/OpenSSL); 84.3% SharpHound attribute coverage; emits BH-CE JSON → feeds ArtBlood |
| 6 | ArtBlood | art3x/artblood (8★, GPL-3.0) | `cargo build --workspace` (MinGW path proven on this VM) | native ✓run | Dive: built (1m23s), **176/176 tests**, live ingest→kerberoast/ASREP/ACL/tier-0-paths→8-tool MCP handshake; offline BH analysis, no Neo4j/server/Docker. Risks: one-commit repo, Linux-only release ELF, Windows TUI degrades to REPL |
| 7 | stealth-browser-mcp | vibheksoni/stealth-browser-mcp (2162★, MIT, pushed 2026-09-25) | git clone + venv + `pip install -r requirements.txt` (**Python ≤3.13 — 3.14 pins break**) | native ✓run | Dive: 98 tools verified 3 ways incl. live `tools/list`; browser spawn→navigate→close on VM; dynamic Python network hooks (exec by design); anti-bot claims self-reported |
| 8 | cloakbrowser-mcp | swimmwatch/cloakbrowser-mcp (66★, MIT; engine CloakHQ/CloakBrowser 31,790★) | `npx -y cloakbrowser-mcp@latest` | native ✓run | Dive: doctor + full stdio session, real page navigation, auto-downloaded stealth Chromium 146 (537MB); humanize flags, GeoIP-proxy match, managed CDP. Free engine = Chromium 146/58 patches; newest (152/87) license-gated |
| 9 | mitmproxy-mcp | snapspecter/mitmproxy-mcp (123★, MIT, pushed 2026-09-28) | `uv tool install --python C:/Python312/python.exe mitmproxy-mcp`; for 0.7.2 security fixes: `uv tool install git+https://github.com/snapspecter/mitmproxy-mcp` | native ✓run | Dive: install + `--help` verified on py3.12; session variables (CSRF capture→replay), interception rules, curl-cffi chrome120 stealth replay, OpenAPI export — all in source. PyPI (0.6.1) lags 2 security releases |
| 10 | GraphRunner | dafthack/GraphRunner (1345★, MIT) | `git clone` + `Import-Module .\GraphRunner.ps1` | native ✓run | Dive: 0 parse errors on Windows PowerShell 5.1 + pwsh 7; recon/CAPS-dump/OAuth-consent-abuse/M365 pillaging; zero deps in core. Pushed 2026-04-09 |
| 11 | AzureHound | SpecterOps/AzureHound (962★, GPL-3.0, v3.1.1) | release `AzureHound_v3.1.1_windows_amd64.zip` | native ✓run | Dive: exe run on VM incl. Windows-service mode; Entra (az-ad) + ARM (az-rm) → BloodHound JSON. Caveat: no dockerless consumer yet for its output (BH CE itself is Docker-gated; ArtBlood ingests SharpHound JSON) |
| 12 | bloodhound_mcp (13 tools) | mwnickerson/bloodhound_mcp (136★, GPL-3.0, SpecterOps-blogged) | `uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp` | native ✓run | Dive: exact 13 tools + 10 resources verified in code; uvx install+launch proven on VM (died only on dummy-creds preflight, as designed). Blocker: needs reachable BloodHound CE REST (bhapi = Linux binary/Docker or remote host) |
| 13 | mitre/mcp (Caldera AI plugin) | mitre/mcp (40★, Apache-2.0, pushed 2026-09-03) | clone into existing Caldera `plugins/mcp` + `pip install -r requirements.txt` + `python -m spacy download en_core_web_lg` + enable in `conf/local.yml`; **pin a commit** | native (read) | Dive: all deps have win wheels; spawns via `sys.executable`; DSPy ReAct ability-authoring + op planning + STIX RAG; loads in-process into the estate's Caldera. Not live-run; bus factor 1; no releases |
| 14 | SquidC5 | SquidSec/SquidC5 (57★, MIT, v0.1.319) | release `squidc5-windows-x64.exe` / `sc5-windows-x64.exe` (sha256-verified) or `pip install -e .` (py≥3.11) | native ✓run | Dive: venv boot + release-exe boot + API probes on VM; 369/373 tests pass (4 Windows artifacts); INKO AI operator, scoped MCP **off by default**, Ollama-opt-in, Go beacon factory, OAST, audit hash-chain. Alpha, bus factor 1 |
| 15 | OpenHound | SpecterOps/OpenHound (30★, Apache-2.0, v0.4.1) | `uv tool install "openhound[all]"` (py≥3.13) | native ✓run | Dive: pip install + CLI dispatch verified on VM py3.14; collect→preprocess→convert OpenGraph for BH file ingest; jamf/okta/github extras; base of ConfigManBearPig |
| 16 | EntraGoat | Semperis/EntraGoat (986★, MIT) | `git clone` + `Install-Module Microsoft.Graph` + `.\Start-EntraGoat.ps1` | native (read) | Dive: WPF GUI, PS 5.1+, zero-Docker; 6 attack scenarios w/ setup/cleanup/solutions; needs free Entra trial tenant (GA). Open issue #15 breaks Scenario-4 CLI solution path |
| 17 | mythic_ornn (prompt mode) | n0qword/mythic_ornn (54★, **no license file**) | `git clone` → point any coding agent at `template/AGENT.md` | native ✓run-shaped | Dive: prompt mode = zero-install (docs-grounded Mythic dev with AST-validated build mode); build mode requires Mythic→Docker; only open implementation of the SpecterOps "disposable tooling" idea (post shipped no code) |
| 18 | anything-analyzer | Mouseww/anything-analyzer (3721★, Apache-2.0) | release `Anything-Analyzer-Setup-3.6.62.exe` | native (read) | Dive: source-verified CDP browser + MITM :8888 + crypto.subtle/CryptoJS/SM2-3-4 JS hooks + 30-tool MCP server (binds 0.0.0.0 — set 127.0.0.1); installer not executed here; anti-bot fragile (#18), single maintainer |
| 19 | FuzzingLabs/mcp-security-hub (cherry-pick) | FuzzingLabs/mcp-security-hub (796★) | `git clone` + per-server `pip install -r <server>/requirements.txt` + run `server.py` as stdio worker | native (read) | mcp-tool-hubs ×2: source-verified `cmd=[...]` exec of host binaries; nuclei/ffuf/sqlmap already on this VM; pick sqlmap-mcp/ffuf-mcp/bloodhound-mcp(wraps MorDavid)/hashcat/searchsploit/whatweb/masscan/gitleaks; nmap not on PATH |
| 20 | darknet-mcp-server | badchars/darknet-mcp-server (464★, npm v0.1.1) | `npx darknet-mcp-server` (TOR_SOCKS_PORT=9050) | native (read) | deepweb ×2 + onion lanes: 66 tools (HIBP, ThreatFox, ransomware trackers, onion fetch/search, stealer logs, blockchain); estate Tor already running; gateway darknet backend exposes the same surface keyless |
| 21 | engram | Gentleman-Programming/engram (6,933★) | release `engram_2.2.1_windows_amd64.zip` (verified asset) | native (read) | agent-memory: single-exe SQLite+FTS5 shared agent memory, MCP + HTTP API |
| 22 | mcp-server-ladybug | LadybugDB/mcp-server-ladybug (17★; LadybugDB 1,792★ = maintained Kùzu successor) | `pip install mcp-server-ladybug` (**cp314 win wheel downloaded & verified on this VM**) | native ✓run (wheel) | agent-memory: Cypher over one embedded .lbdb file — smallest shared-brain primitive; kuzu itself is dead (no cp314 wheel, archived 2025-10-10) |
| 23 | garak | NVIDIA/garak (9,386★) | `python -m pip install -U garak` | native (read) | gap-chase + adv-academic: canonical LLM vulnerability scanner |
| 24 | PyRIT | microsoft/PyRIT → Azure/PyRIT (4,558★) | `pip install pyrit` (per docs; README install not grep-verified) | native (read) | gap-chase + adv-academic: generative-AI red-team automation |
| 25 | deepteam | confident-ai/deepteam (2,975★) | `pip install -U deepteam` (ships an MCP server) | native (read) | gap-chase: red-team LLMs/agents from Cursor/Claude Code |
| 26 | mcpsec | manthanghasadiya/mcpsec (26★, PyPI 2.4.0) | `pip install mcpsec` | native (read) | llm-fuzzing: MCP-protocol fuzzer (state violations, SSRF/LFI) — direct fit for the 43-backend gateway |
| 27 | Anthropic-Cybersecurity-Skills | mukul975/Anthropic-Cybersecurity-Skills (33,573★) | `npx skills add mukul975/Anthropic-Cybersecurity-Skills` | native (read) | gap-chase: 818 skills / 34 domains / 6 framework mappings |
| 28 | Microsoft MCP Server for Enterprise | microsoft/EnterpriseMCP + learn.microsoft.com/graph/mcp-server (remote) | one-time tenant provisioning (`Install-Module Microsoft.Entra.Beta` → `Grant-EntraBetaMCPServerPermission`), then point any client at `https://mcp.svc.cloud.microsoft/enterprise` | native (nothing to install) | Dive: official, read-only, 41 `MCP.*` scopes (docs say 44 — drift), NL→Graph; preview, global cloud only, 100 rpm |
| 29 | gcpwn | NetSPI/gcpwn (313★, PyPI 0.5.25) | `pip install gcpwn` | native (read) | cloud-ai-security: GCP+Workspace pentest → OpenGraph; estate itself runs on GCP |
| 30 | stratus-red-team | DataDog/stratus-red-team (2409★, pushed 2026-09-29) | Go release binaries incl. Windows | native (read) | cloud-ai-security: adversary emulation AWS/GCP/Azure, no Docker |
| 31 | T3MP3ST | elder-plinius/T3MP3ST (6,277★, AGPL) | `npm install && npm run server` → 127.0.0.1:3333/ui | native (read) | c2-agentic + wildcard: multi-agent offensive meta-harness over existing coding agents or offline models; "Works on Windows (PowerShell)" README L156; 90.1% XBOW pass@1 self-verified |
| 32 | cascadeflow | lemony-ai/cascadeflow (3,999★) | `pip install cascadeflow` | native (read) | model-cascade: cascading runtime (cost/latency/quality) with LangGraph integration → Decepticon |
| 33 | cain-agent | cdxiaodong/cain-agent (961★, pushed 2026-09-29) | `pip install -e ".[cloud]"` | native (read) | cloud-ai-security + wildcard: AI pentest engineer with AWS/Azure/GCP/CN-cloud module |
| 34 | RedLineBench | cracken-ai/redline-bench (13★) | git clone; run against 127.0.0.1:11434/v1 | native (read) | model-cascade: 153-prompt refusal/quality benchmark — the instrument for tuning the estate cascade (GLM refuses 35-39% but scores 4.45-4.63 when it answers; DeepSeek 5-7% refusal, $0.28/solved-task) |

### Tier B — MEDIUM value, Windows-native

| Tool | Repo | Install | Windows | Notes |
|---|---|---|---|---|
| nodriver-proxy-mcp | BobongKu/nodriver-proxy-mcp (3★) | `uv pip install nodriver-proxy-mcp` (py 3.10–3.13; plain pip fails: zstandard backtrack) | native ✓run | Dive: all 39 tools + proxy/browser/dual-session/code-mode smoked on VM — **but dead upstream since 2026-04-10, no LICENSE, no community**. Adopt = own it |
| x746b/sliver-mcp | x746b/sliver-mcp (5★) | clone + `uv pip install -e .` **+ `uv pip install "mcp<2"` (fresh install currently broken)** | native ✓run (import) | Dive: 74 tools exact, BOF/coff-loader port verified in code; dormant since 2026-04-23; complements Sliver's fs-only native MCP |
| PMapper | nccgroup/PMapper (1582★) | `pip install principalmapper` **+ 1-line `collections.abc` patch (≥3.10 broken out of the box; 32/32 tests pass after)** | native ✓run (patched) | Dive: dormant since 2022, AGPL, 33% privesc coverage, perf ceiling — pair with a maintained scanner |
| WonderSuite | sfr-development/WonderSuite-Ai-Bug-Bounty (51★) | v0.3.35 `.msi`/`-setup.exe` (release assets verified) | native (read) | Dive: every headline feature real in code (93 MCP tools on :3100, JA3/JA4+H2 impersonation, isTrusted input, OAST, storage_full) — **dormant since 2026-06-11, site down, zero community** |
| anything else browser | veilbrowser (npm, Bézier humanization), bladebro (`npm i -g bladebro && bladebro mcp`, 283★), spectral (`pip install spectral-mcp`, 118★), hackbrowser-mcp (dual-role IDOR, Bun), browser-session-mcp (Rust, Linux/macOS binaries only) | npm/pip/clone | native (read) | browser-offense ×2: session-handling specialists; none dive-verified |
| mitre MCP alternatives | cowboy-samurai/caldera-mcp (PyPI, remote REST) | `pip install caldera-mcp` | native (read) | dive-mitre: attaches remotely without touching the Caldera tree |
| pentest-mcp | DMontgomery40/pentest-mcp (146★) | `npm install -g pentest-mcp` | native (read) | mcp-tool-hubs: nmap+ffuf+nuclei+hashcat+hydra in one Node server + reporting |
| blitzstrike | shinthink/blitzstrike (488★, pushed 2026-09-29) | `npx -y blitzstrike doctor && npx -y blitzstrike install` | native (read) | mcp-tool-hubs ×2 + wildcard: methodology layer (BLITZ/EAGLE-EYE/STRIKE) + 130-tool catalog + `ensure_tool` |
| sqlmap-skynet | drcrypterdotru/sqlmap-skynet (98★) | clone; FastMCP CLI "best for Windows" | native (read) | mcp-tool-hubs: autonomous sqlmap orchestration; sqlmap.exe present |
| Arkana | JameZUK/Arkana (238★) | clone + pip | native (untested) | mcp-tool-hubs pass-2: 308 MCP tools for binary analysis (angr, emulation, debugging) — complements binary-ninja/cheatengine workers |
| RedTeam-Agent | ktol1/RedTeam-Agent (72★) | `python scripts/install_tools.py` (Windows 10/11 documented) | native (read) | c2-agentic + wildcard: Windows-native AD chain installer (SharpHound→BH→impacket→nxc) |
| AADInternals | Gerenios/AADInternals (1,699★) | PowerShell module | native (read) | ad-entra-s2: canonical Entra/M365 offense module |
| TeamFiltration | Flangvik/TeamFiltration (1,410★, v3.5.5) | release `TeamFiltration-v3.5.5-win-x86_64.zip` | native (read) | ad-entra-s2: Entra user-enumeration/spray/exfil |
| entraid-mcp-server / roadrecon_mcp_server | hieuttmmo (41★) / atomicchonk (52★) | clone + `fastmcp dev …` / pip | native (read) | ad-entra ×2 + gap-chase: Graph read MCP; ROADrecon-data analysis MCP |
| BadZure / OID-See | mvelazc0 (527★) / OID-See (38★) | pip (+terraform+az for BadZure) | native (read) | ad-entra: misconfigured-tenant lab generator; Graph-risk scanner w/ OpenGraph output |
| AICloudSentinel | SpecterBreach/AICloudSentinel (1★) | `pip install -e ".[aws,azure]"` from source (**PyPI claim is false — 404**) | native (read) | cloud-ai-security: AI/LLM-layer cloud misconfig scanner (OWASP LLM/Agentic mapped); no GCP support |
| orthrus | ankitjha67/orthrus (11★) | `pip install -e .` (developed on py3.14/Win11) | native (read) | cloud-ai-security: 70 scanners + bounded LLM agent + MCP, docker optional |
| cloudsword | wgpsec/cloudsword (624★) | release `cloudsword_v0.0.2_windows_amd64.zip`; MCP sse/stdio since v0.0.2 | native (read) | cloud-ai-security: CN-cloud AK/SK exploitation only (no AWS/Azure/GCP modules) |
| pacu | RhinoSecurityLabs/pacu (5345★) | pip | native w/ caveats | cloud-ai-security: AWS exploitation framework; some modules assume nix |
| AWS/Azure official MCPs | awslabs/mcp (9743★, `uvx mcp-proxy-for-aws@latest …`), microsoft/mcp → Azure.Mcp.Server | uvx | native (read) | cloud-ai-security: raw API hands for agents; Azure/azure-mcp archived→microsoft/mcp |
| zeroguard-policy | NinjaGamerYT12/zeroguard-policy (PyPI 0.1.0) | `pip install zeroguard-policy` | native (read) | cloud-ai-security: stdlib LoopGuard/ExecutionGuard for agentic loops |
| AICryptoProxy | hzhsec/AICryptoProxy (51★) | clone + pip (py3.12+) | native (read) | adv-nonenglish: auto-reverses frontend-encrypted traffic → emits mitmproxy encrypt/decrypt scripts |
| ProcMon-MCP | 0xhackerfren/ProcMon-MCP (82★, PyPI) | `pip install procmon-mcp` (admin) | native (read) | adv-nonenglish: Windows internals visibility for agents (ETW, drivers, minifilters) |
| jadx-ai-mcp / apktool-mcp-server | zinja-coder (2,842★ / 661★) | uv pip install httpx fastmcp + plugin | native (read) | gap-chase: mobile RE MCPs |
| radare2-mcp / Reversecore_MCP / GhidrAssistMCP | radareorg (312★, renamed from r2mcp) / sjkim1127 (205★) / symgraph (756★) | clone/build, pip, Ghidra extension | native (read) | gap-chase: RE/malware MCP cluster |
| cve-mcp / mcp-shodan / osint-mcp-server | badchars (29★) / w0h1v (173★) / badchars (57★) | `npx cve-mcp` / `npx -y @burtthecoder/mcp-shodan` / `npx osint-mcp-server` | native (read) | gap-chase: CVE-intel (NVD/EPSS/KEV/OSV) + surface recon |
| wifi-security-mcp-server | badchars (6★) | `npx wifi-security-mcp-server` | native (read) | gap-chase: full-spectrum wireless lane (young; radio tooling needs adapters) |
| IndusFuzz | TaoYaTou/IndusFuzz (v1.8.5) | clone + venv + pip (Windows-first, DPAPI key storage) | native (read) | llm-fuzzing: industrial-protocol fuzzing agent, Ollama-local w/ deterministic fallback |
| RALFuzz | Go-ther/RALFuzz (0★) | clone + pip **+ clang/LLVM (absent on VM)** | native-cond (read) | llm-fuzzing: C fuzz-harness generation, explicit Windows LLVM path |
| mcp-server-fuzzer | mcp-runtime (46★) | clone + pip | native (read) | llm-fuzzing: generic MCP json-rpc fuzzer |
| memora / basic-memory / graphiti-local | agentic-box (729★) / basicmachines-co (4,063★) / renezander030 (2★) | `pip install memora-mcp` / `uvx basic-memory mcp` / recipe (Ladybug+Ollama, untested) | native (read) | agent-memory: cross-engagement memory tier-2; graphiti-core 0.30.2 wheel verified (pin ≥0.28.2: CVE-2026-32247 Cypher injection) |
| litellm | BerriAI/litellm (59,867★) | pip | native (read) | model-cascade: gateway w/ Zhipu `sensitive→content_filter` normalization (PR #24373) |
| VulnClaw / Agentic-Bug-Hunter / ptai / PentesterFlow | Netw0rkNoob (3,462★) / awarexone (5,205★) / 0xSteph (1,708★) / PentesterFlow (1,382★) | `pip install vulnclaw` / `uv tool install agentic-bug-hunter` / `pipx install ptai` / install.ps1 + exe | native (read) | wildcard: 2026 agentic pentest harnesses; several with Ollama providers |
| reverse-skill / Claude-Red / hack-skills / open-reverselab | zhaoxuya520 (38,705★) / SnailSploit (7,096★) / yaklang (2,333★) / LING71671 (1,190★) | git clone into skills dirs | native (read) | wildcard: 2026 skill packs (reverse-skill has Windows CI per README) |
| Shannon | KeygraphHQ/shannon (48,486★) | unverified (found via HN) | unknown | adv-social: biggest single find of the social sweep; "AI pentester … executes real exploits"; install + claims NOT verified |
| PentestAgent (GH05TCREW) | GH05TCREW/pentestagent (3,073★) | clone | native (read) | adv-social: black-box agent framework + HexStrike integration |
| robin | apurvsinghgautam/robin (7,379★) | clone + pip | native (read) | adv-social: AI dark-web OSINT |
| Numasec | FrancescoStabile/numasec (800★, npm) | `npm i -g numasec` | native (read) | adv-social: "Claude Code for security" ReAct agent over nmap/nuclei/sqlmap/ffuf |
| ARTEX / AiScan-N / XuanMu / Oktos / WolfShell / SecSkills / AboutSecurity / FofaMap / Scan-Spring-GO | Autumn-27 (1,290★) / SecNN (541★) / guaidao2 (125★) / 1y0n (179★) / 0x7556 (276★) / DaoYiSec (1,093★) / wgpsec (1,767★) / asaotomo (733★) / sspsec (308★) | per-README (mostly clone/native; ARTEX = Go+Next.js) | native/unknown (read) | adv-nonenglish: the Chinese-lane haul (Baidu-challenge champion ARTEX; MCP-supporting C2 Oktos; AI webshell WolfShell; wgpsec agent-executable methodology KB) |
| OWASP Noir / DarkBERT / CAI | owasp-noir/noir (1,439★) / s2w-ai (HF, gated) / aliasrobotics/cai (9,839★, archived 2026-08-22) | clone / HF gated / pip-docker | native-unknown / n/a / archived | adv-nonenglish: KR/ES lanes |
| PentestGPT | GreyDGL/PentestGPT (15,648★) | pip | native (read) | gap-chase + adv-social: alive, agentic pipeline v1.0.0 (2025-12-24) |
| hackingBuddyGPT | ipa-lab (1,248★) | `pip install hackingbuddyGPT` | native (read) | adv-academic + c2-agentic: LLM pentest agent (Linux-lab oriented) |
| eval frameworks | inspect_ai (2,883★), agentdojo (877★, pip), Cybench (334★, docker), CyberGym (917★, docker), NYU_CTF_Bench, BountyBench, BoxPwnr (458★), exploitbench (412★), cve-bench (291★) | pip or docker | mixed | adv-academic + exploit-dev: capability evaluation side |
| cracking/RE classics surfaced | angr (9,118★), AFL++ (6,777★), syzkaller, Fuzzilli, LLM4Decompile (7,060★), ReSym (CCS'24) | pip/cargo/build | mostly wsl/docker | adv-academic: research corpus the fleet lacked |
| fissure | Stefan0x03/fissure (1★) | fork + GitHub Actions workflows | native (runs on GHA) | exploit-dev: CVE triage → fuzz repro, zero local Docker |
| ai-vuln-harness | daedalus (5★, PyPI) | `pip install "ai-vuln-harness[search]"` | native-leaning | exploit-dev: 15-stage pipeline, container optional |
| jaegis-RAVERSE | usemanusai (7★) | `pip install jaegis-raverse-mcp-server` | native (untested) | exploit-dev: binary-patching MCP (35 tools) |
| gophish-mcp / beelzebub / redink | dan1t0 (21★) / beelzebub-labs (2,186★) / AnshumanAtrey (0★) | pip / Go binary / clone | native (read) | gap-chase: phishing-infra, deception, report-gen lanes |

### Tier C — Docker era (blocked on this VM; stage for a remote Linux worker)

| Tool | Repo | Install | Windows | Notes |
|---|---|---|---|---|
| PentAGI | vxcontrol/pentagi (25,108★, MIT; staged on estate) | docker compose (main branch only — see hardening) | docker | pentagi-hardening: CVE-2026-14784 (socket escape) + CVE-2026-18593 (foreign-binary RCE→Windows host via `/run/desktop/mnt/host/`); fixes only on `main` (`DOCKER_INSIDE=false` default); two-node TLS+OPA+seccomp worker guide = the deploy pattern; official installer exists but needs a Linux engine |
| Clearwing | Lazarus-AI/clearwing (1,073★, MIT, pushed 2026-09-24) | `git clone` + `uv sync --all-extras`; `clearwing mcp` for stdio MCP | docker (sandbox) | exploit-dev: the literal N-day pipeline named in the ask; controller installs natively, but SourceHunt/N-day sandbox has **no local-process backend** (docker/dind/kubernetes only); model-agnostic (Ollama OK) |
| Mythic (+ sage / echidna / Mythic-MCP / ornn-build-mode) | its-a-feature/Mythic (4,797★) | `mythic-cli install github …` | docker | c2-agentic: MythicAgents/sage (LangGraph AI operator, Ollama provider), 0xrdi/echidna, nbaertsch/Mythic-MCP (~150 tools), mythic_ornn build mode |
| RedAmon | samugit83/redamon (2,807★, MIT, v6.21.0, pushed 2026-09-29) | docker compose (webapp+postgres+neo4j+kali-sandbox+socket-proxy) | docker | adv-nonenglish: recon→exploit→post-ex autonomous, attack graph, auto-fix PRs, OpenVAS optional |
| MCPwner | nedlir/MCPwner (55★) | `docker compose up -d --build` | docker | mcp-tool-hubs ×2: deepest hub (CodeQL+semgrep+joern, DAST suite, PoC-script sandbox w/ oracles, findings ledger); "Windows (with WSL2)" prereq |
| bolt | cyberstrikeus/bolt (64★) | `docker run ghcr.io/cyberstrikeus/bolt` (license shows NOASSERTION — resolve first) | docker | mcp-tool-hubs ×2: estate vendor's own 33-tool hub; in-family upgrade |
| PromptFuzz / PromeFuzz / oss-fuzz-gen | FuzzAnything (346★) / pvz122 (61★) / google (1,441★) | docker | docker | llm-fuzzing: harness-generation state of the art (33 valid bugs; CCS'25 artifact; Google production) |
| CyberGym / CyberGym-E2E | sunblaze-ucb (917★ / 78★) | docker | docker | adv-academic: real-world CVE agent benchmark incl. PoC+patch lifecycle |
| apeman | hotnops/apeman (264★) | docker compose | docker | ad-entra-s2: AWS attack-path management MCP (the piece BlakHound would replace natively) |
| cybergym-adjacent eval fleet | cve-genie (93★), cve-env (27★), anypoc (34★), patchproof-repro (PyPI, sandbox), BoxPwnr (458★), auto-pen-bench (102★), VulnBot (197★), CHAP | docker | docker | exploit-dev + adv-academic: repro/benchmark infra |
| xalgorix | xalgorix/xalgorix (1,143★) | Docker (Linux badge) | docker | adv-nonenglish + wildcard: verifier re-exploits every finding |
| ARL-Next / redcell / docker-stealthy-auto-browse / BrowseForge / the-box-mcp | owl234 (447★) / martian56 (323★) / psyb0t (86★) / nczz (54★) / horizonfps | docker / wsl | docker/wsl | wildcard + browser-offense: asset platform, Kali red-team, anti-detect farm, MITM+OOB+evidence vault (WSL2-gated) |
| sandbox hardening kit | opa-docker-authz (106★), Tecnativa/docker-socket-proxy (2,804★), nestybox/sysbox (3,885★), google/gvisor (19,455★), docker-bench-security (9,699★) | Linux daemon plugins/runtimes | docker-host | pentagi-hardening: deploy on the future worker node; authz.rego fail-closed + seccomp (S_IFBLK mknod denied) + never mount a socket |

### Tier D — recorded, low value / watch / not installable

Watch-list (native-in-principle, blocked on missing toolchains): **BlakHound** (jusso-dev, AWS attack graph + MCP, no releases yet, needs Go), **stave**/**perspectivegraph** (Go), **open-re** (Rust, no releases), **browser_oxide** (Rust), **phaedra** (`cargo install phaedra`, Rust), **Vela-Engineering/kuzu** fork (C++, no PyPI), **AgentHound** (Go, 442★ — attacks AI-agent infra; defensive crossover for the gateway).
Papers/anchors with no code: **PwnAgent** (62.12% e2e, Springer 2026 — no release), **PentestChain** (arXiv 2609.18120, ASIA CCS'27 — cascade design source), **ATMOcloud**, **ZeroGuard** (SSRN), **RESTing-LLAMA** (no artifact), **SemFuzz** (only Bluetooth variant BSFuzz public), **StepStone** (Oakland'26, no repo), **Unit 42 "Zealot"** (doctrine).
Name-collision traps recorded: `MCPwner` (Docker fleet) ≠ `mcpwn` (redlightconsole, Go, unreleased) ≠ `D0rs4n/mcpwn`; `sliver-mcp` on PyPI = different project (hi-unc1e); `hound-mcp` = deps.dev scanner, NOT BloodHound; `tiluckdave/hound-mcp` same; ArgusRed (Cosine) possibly ≠ "argus (ai-agent red-team)"; estate "CyberStrike 1.1.16" maps to `cyberstrikeus/CyberStrike` per mcp-tool-hubs (releases verified), while `Ed1s0nZ/CyberStrikeAI` (7,096★) is a same-name separate project flagged by adv-nonenglish — **both claims exist in the fleet; not reconciled here**.
Dead/vaporware: **Agentic-Mythos-SOC** (0★ one-day repo, all print-statements — the real pattern is Anthropic's Claude-Mythos methodology; live impls = mythosharness repos), **AICloudSentinel PyPI package** (404), **v0idravl/sliver-mcp** (gone), **Kuzu** (archived; no cp314 wheel), **Havoc** (archived 2025-12-18; only MCP wrapper also archived).

## 2. Duplicate-merge map (lanes → single entry)

| Tool | Found by | Kept evidence |
|---|---|---|
| bloodhound_mcp (mwnickerson) | ad-entra ×2, mcp-tool-hubs ×2, c2-agentic | dive-…bloodhound-mcp (13/10 counts in code; uvx run on VM) |
| MorDavid/BloodHound-MCP-AI | ad-entra ×2, mcp-tool-hubs ×2 | ad-entra (377★, Neo4j-bolt, native w/ Windows Neo4j; stale 2025-06) |
| CloudFox | ad-entra, cloud-ai-security | dive-CloudFox (exe executed, sha1-verified) |
| AzureHound | ad-entra ×2, cloud-ai-security | dive-AzureHound (exe executed, service mode) |
| ROADtools | ad-entra ×2, cloud-ai-security | dive-ROADtools (e2e on py3.14) |
| GraphRunner | ad-entra ×2 | dive-GraphRunner (PS5.1 import); mnxsyy/GraphRunner 404 correction kept |
| PMapper | ad-entra, cloud-ai-security | dive-PMapper (≥3.10 breakage + 1-line fix proven) |
| RustHound-CE | ad-entra ×2 | dive-RustHound-CE (exe run) |
| ArtBlood | ad-entra ×2 | dive-ArtBlood (built + 176 tests + MCP handshake) |
| EntraGoat | ad-entra-s2 | dive-EntraGoat |
| OpenHound | ad-entra-s2 | dive-OpenHound (install run) |
| Sliver native MCP | c2-agentic | dive-Sliver (v1.7.7 tree verified) |
| x746b/sliver-mcp | c2-agentic | dive-x746b (74 tools; mcp<2 pin fix) |
| mythic_ornn | c2-agentic | dive-mythic-ornn (no-license, no-Docker prompt mode) |
| mitre/mcp | c2-agentic | dive-mitre (in-process install correction; not remote bolt-on) |
| SquidC5 | c2-agentic | dive-SquidC5 (boot + release exe + tests on VM) |
| T3MP3ST | c2-agentic, wildcard-2026 | c2-agentic (README Windows line quoted) |
| nodriver-proxy-mcp | browser-offense ×2 | dive (runtime smoke; resolves the 2026-09-09-vs-2026-04-10 pushed_at discrepancy in favor of 2026-04-10) |
| WonderSuite | browser-offense ×2, mcp-tool-hubs | dive (93 tools, not 90; dormant-since-June correction) |
| CloakBrowser / cloakbrowser-mcp | browser-offense ×2 | dives (freemium reality: free=146/58 patches; wrapper live-run) |
| js-reverse-mcp | browser-offense | dive (live run; Google chrome-devtools-mcp fork provenance) |
| stealth-browser-mcp | browser-offense | dive (98 tools live; py≤3.13) |
| mitmproxy-mcp | browser-offense | dive (py3.12 install run; PyPI lag warning) |
| anything-analyzer | browser-offense | dive (source-verified; not executed) |
| FuzzingLabs/mcp-security-hub | mcp-tool-hubs ×2 | second-pass source verification (exec pattern + bloodhound wrapper exists) |
| MCPwner / bolt | mcp-tool-hubs ×2 | second pass (Docker hard requirement; license caveat) |
| blitzstrike | mcp-tool-hubs ×2, wildcard-2026 | mcp-tool-hubs |
| cain-agent | cloud-ai-security, wildcard-2026 | cloud-ai-security |
| AgentHound | ad-entra-s2, c2-agentic, wildcard-2026 | ad-entra-s2 (442★, pushed 2026-09-29) |
| PyRIT / garak / deepteam | gap-chase, adv-academic | gap-chase (install lines) + adv-academic (star counts) |
| PentestGPT | gap-chase, adv-social | adv-social (15,648★, alive) |
| hackingBuddyGPT | c2-agentic, adv-academic, adv-social | adv-academic |
| darknet-mcp-server | deepweb ×2, onion-tools, onion-forums | deepweb-coverage (464★, 66 tools, npx) |
| dhunter | c2-agentic, wildcard-2026, adv-nonenglish | adv-nonenglish (SRC acceptance gate) |
| Shannon | adv-social only | adv-social (unverified install — flagged) |

## 3. topNative — top 10 installable on Windows without Docker

1. **js-reverse-mcp** — `npx js-reverse-mcp`. The only estate tool giving an agent a real Chrome DevTools debugging loop (breakpoints, call-frame eval, XHR breakpoints, Set-Cookie/HttpOnly provenance) over headed persistent-login Chrome with protocol-level stealth. Live-verified on this VM; 2,853★, active.
2. **CloudFox** — release `cloudfox-windows-amd64.zip` (v2.0.5), exe sha1-verified and run on this VM. Multi-cloud situational awareness + IAM privesc (AWS 34 cmds, GCP ~60, thin Azure). Use ≥1.17.0; note region-hang fix is on main only.
3. **ROADtools** — `pip install roadrecon roadtx`. The canonical Entra enumeration + token/PRT/passkey abuse baseline; full offline pipeline proven on py3.14 here. Unit42 tracks nation-state abuse of it — it works.
4. **Sliver (native MCP)** — v1.7.7 Windows exes; `sliver-client mcp` (stdio) or `mcp start --transport http` (token-authed 127.0.0.1:8080) plugs a 11.9k★ C2 straight into the estate gateway; agentic-loop work is in-tree. Experimental label upstream; fs/session tool surface (pair with x746b/sliver-mcp + `mcp<2` pin for exec/armory/BOFs).
5. **RustHound-CE** — release zip, exe run on this VM. Single-exe AD→BloodHound-CE JSON collector, no .NET, MIT, actively released (v2.5.14, 2026-09-17).
6. **ArtBlood** — `cargo build --workspace` (MinGW path proven on this VM; 176/176 tests). Offline BloodHound analyzer + 8-tool MCP: SharpHound JSON → indexed cache → shortest paths/tier-0/Kerberoast/ASREP/ACL/ESC — **no Neo4j, no server, no Docker**. Single-commit repo; pin it. With #5 this closes the dockerless AD attack-path stack (RustHound-CE → ArtBlood MCP → gateway).
7. **stealth-browser-mcp** — clone + py3.12 venv. 98-tool nodriver stealth browser MCP with AI-written network hooks; live-verified on this VM; biggest community in the lane (2,162★).
8. **cloakbrowser-mcp** — `npx -y cloakbrowser-mcp@latest`. Live-verified navigation through the CloakBrowser stealth Chromium with humanized input, GeoIP proxy matching, managed CDP; drop-in Playwright-MCP tool surface. Free engine = Chromium 146 (paid key for newest/152+ and >1 session).
9. **mitmproxy-mcp** — `uv tool install --python C:/Python312/python.exe mitmproxy-mcp` (git main for the 0.7.2 security fixes). Turns the estate's existing mitmproxy into agent tools: session variables (CSRF capture→replay), interception rules, curl-cffi stealth replay, OpenAPI reconstruction.
10. **GraphRunner** — `Import-Module .\GraphRunner.ps1`. Zero-dependency PowerShell M365/Entra post-exploitation (recon, CAPS dumps, OAuth consent abuse, mail/Teams/SharePoint pillaging); import-verified on PS 5.1 here.

(Dropped from the top 10 on completeness grounds: AzureHound — verified run but its graph consumer is Docker-gated today; bloodhound_mcp — native but backend-blocked; SquidC5/OpenHound/EntraGoat/mitre-mcp/anything-analyzer — strong but alpha/lab/static-verified; all remain Tier A in §1.)

## 4. topDocker — top 5 for the docker era (remote Linux worker)

1. **PentAGI** — `vxcontrol/pentagi` (25,108★), already staged. Deploy **main branch** with the two-node worker pattern (host Docker TLS :2376 + hardened dind TLS :3376 + fail-closed OPA authz + S_IFBLK-blocking seccomp, `examples/guides/worker_node.md`); never mount a socket, never run ≤v2.1.0 (CVE-2026-14784 + CVE-2026-18593 chain to the Windows host via Docker Desktop mounts).
2. **Clearwing** — `Lazarus-AI/clearwing` (1,073★, MIT). The N-day pipeline from the ask (build vulnerable version → exploit → validate vs patched) + `clearwing mcp` stdio server; sandbox is Docker-only by design (no local-process backend).
3. **Mythic** — `its-a-feature/Mythic` (4,797★) as the platform that unlocks the whole agentic-Mythic cluster: MythicAgents/sage (in-C2 AI operator, Ollama provider), 0xrdi/echidna, nbaertsch/Mythic-MCP (~150 tools), mythic_ornn build mode.
4. **RedAmon** — `samugit83/redamon` (2,807★, active). Autonomous recon→exploit→post-ex with a neo4j attack graph, docker-socket-filtering broker, and auto-fix pull requests.
5. **MCPwner** — `nedlir/MCPwner` (55★). The deepest single security hub found: 55+ containerized tools incl. CodeQL/joern SAST, full DAST suite, PoC-script sandbox with deterministic oracles, and a findings ledger.

(Runners-up kept in §1 Tier C: bolt — in-family vendor hub, resolve NOASSERTION license first; PromptFuzz/PromeFuzz for harness generation; CyberGym/CyberGym-E2E for evaluation; apeman for AWS attack-path MCP.)

## 5. Non-tool findings the estate should keep

- **Darkweb intelligence** (deepweb ×2 + 3 onion lanes): the onion-side offensive-AI landscape is closed-source subscription services, not repos (FraudGPT $89.99/mo-variant tiers, WormGPT $189–249/mo, Luciferus $35–75/mo on Exploit, ~19k WormGPT accounts leaked 2026-07-15); PikaSim = MCP server for agentic SMS-verification bypass (the clearest "AI-agent crime stack" item); cracked-tool trade now on escrow markets (cracked CS 4.12 at $2,500, Pandorum C2/Cracked categories, Dead Drop forum); engine map collapsed to **Ahmia (token trick, scriptable) + Onionland (live+scriptable, round-3 reversal) + Torch-onion (SPA, unusable) + onion.live**; Dread live via https-on-onion; DarkSearch rotated addresses; forum availability map in deepweb-coverage-round2 §2G; stale-index lag is systematic — verify every address.
- **Model-cascade numbers** (model-cascade): GLM-5.2 refuses 35–39% of naked offensive prompts but scores 4.45–4.63 when it answers; DeepSeek V4-Pro 5–7% refusal at $0.28/solved-task; local qwen tier fine for bounded roles (PentestChain: 96.4% first-tier success, $0.00 paid spend); normalize Zhipu `finish_reason:"sensitive"` at the gateway; retry-on-refusal is AISI-sanctioned; escalate-on-failure beats predictive routing (llm-cost-routing).
- **Gateway hygiene** (gap-chase + AgentHound + mcpsec + g0): the 43-backend MCP gateway is itself attack surface — mcpsec (pip), AgentHound (Go, watch), guard0-ai/g0 (npm `@guard0/g0`, 1,200+ rules, rug-pull detection), mukul975 skill-scanner (cisco-ai-defense, 2,565★), Sliver MCP CVE-2026-34227 as the cautionary tale.
- **Infra fix-ups found by the fleet**: FIRECRAWL_API_KEY placeholder (fix from User registry value); Python 3.14 pin breakage cluster (use `C:\Python312` venvs); Docker-CLI-present/engine-down state + WSL features rolled back same-day (boot-loop risk contained — gcp-windows-docker.md); nested virtualization is documented-unsupported (GCP), remote-SSH Docker host is the sanctioned path.

## 6. Discrepancies kept (not silently merged)

- nodriver-proxy-mcp pushed_at: 2026-09-09 (browser-offense s1) vs 2026-04-10 (s2 repos call + dive) — dive wins.
- WonderSuite tool count: 85/90/91 (README drifts) vs **93** extracted from `mcp/mod.rs` (dive wins).
- Microsoft Enterprise MCP scopes: "44 MCP.*.Read.All" vs **41** counted in current docs (dive wins).
- ROADtools stars 2725 (claim) = exact; RustHound-CE 597 vs 598 — immaterial drift.
- mitre/mcp "bolts onto caldera rpc remotely" — corrected: in-process plugin, must clone into the Caldera tree and restart (dive wins).
- cyberstrikeus/CyberStrike license: AGPL-3.0 (pass 1) vs NOASSERTION via API (pass 2) — unresolved.
- anything-analyzer license: README says MIT, actual LICENSE file is Apache-2.0 (dive).
- mythic_ornn described as "the open-source implementation of the SpecterOps demo" — corrected: independent implementation of the idea; the post shipped no code (dive).
- Sliver default MCP bind 127.0.0.1:8080, not 31100 — gateway proxying is config, not code (dive).
- x746b/sliver-mcp README claims MIT; no LICENSE file exists (dive).

## 7. What was NOT done / honest gaps

- No tool in this consolidation was newly installed by the consolidator; all ✓run claims are inherited from the dives/lanes that ran them (each cites its commands in its own file).
- Shannon (48k★) install/claims unverified; X/Twitter and Discord surfaces unreachable fleet-wide; Reddit direct 403 (PullPush archive used); t00ls/先知/看雪 post bodies login-gated; Reddit/LinkedIn auth-walled leads unresolved; several Go/Rust tools blocked on missing toolchains; Sliver/SquidC5/artblood MCP sessions not exercised against live implants/targets; PyRIT README install line not grep-verified.
