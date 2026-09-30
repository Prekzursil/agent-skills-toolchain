# Research lane: cloud-ai-security
Date: 2026-09-29. Researcher session on the estate VM (Windows Server, Git Bash, `C:\Python314\python.exe`, gh authed as Prekzursil).

Estate context (from the ask): CyberStrike 1.1.16, MCP gateway 127.0.0.1:31100 (43 backends / 17 live), Decepticon (LangGraph), PentAGI staged docker-pending, Ollama qwen3:4b, **NO Docker engine** (GCP, no VT-x). Everything below is scored for Windows-native, no-Docker operation.

## 0. Backend health (verified this session)
- `gh auth status` → logged in as Prekzursil, token present. GitHub API `curl https://api.github.com/octocat` → HTTP 200.
- Exa: `curl -X POST https://api.exa.ai/search` with `$EXA_API_KEY` → works (multiple searches below).
- **Firecrawl: DEAD this session** — `POST https://api.firecrawl.dev/v1/scrape` and `/v1/search` both → `HTTP 401 {"success":false,"error":"Unauthorized: Invalid token"}`. Key present in env but rejected. Worked around with Exa + DDGS + WebFetch/webReader + raw.githubusercontent.
- DDGS (`from ddgs import DDGS`, python) → works.
- arXiv API → reachable, but ATMOcloud/ZeroGuard papers are not on arXiv (empty result sets).
- WebSearch tool → cancelled/unavailable; substituted with the above.

## 1. Named tools from the ask

### 1.1 AICloudSentinel — **real, Windows-native, HIGH**
- Repo: https://github.com/SpecterBreach/AICloudSentinel (1★, pushed 2026-04-25, MIT, Python 3.9+).
- README (read via `gh api repos/.../readme`): "AI Workload Security Scanner for Cloud Infrastructure. Detect misconfigurations in AI/LLM deployments across OCI, AWS, and Azure. Mapped to OWASP LLM Top 10 and OWASP Agentic AI Top 10 (2026)."
- Check matrix from README: AI model storage public access (OCI/AWS/Azure), versioning disabled (poisoning), LLM API key in serverless fn config, agent IAM over-privilege, IMDSv1 on AI/GPU workloads, ML notebook public network, Bedrock/Cognitive Services endpoint without auth, Bedrock invocation logging disabled, Azure AI static keys (no Entra ID), Key Vault soft-delete disabled. Findings mapped to LLM01–LLM10 + ASI01–ASI10.
- AI enrichment: optional `ANTHROPIC_API_KEY`; structured pipeline in `claude_analyzer.py` ("not a chatbot wrapper... Any LLM provider can be substituted").
- **PyPI claim is FALSE today**: README says `pip install aicloudsentinel[all]` but `curl https://pypi.org/pypi/aicloudsentinel/json` → **404** (ran it). Install must be from source.
- pyproject.toml (read via contents API): base dep `openpyxl>=3.1.0`; extras `oci>=2.100.0`, `boto3>=1.34.0`, `azure-identity/azure-mgmt-storage/web/cognitiveservices/machinelearningservices/keyvault`. All pure-Python/wheels → **runs natively on Windows**.
- Install: `git clone https://github.com/SpecterBreach/AICloudSentinel && pip install -e ".[aws,azure]"` (or `[all]`), run `aicloudsentinel scan aws --region ... --output report.xlsx`.
- Value: **HIGH** — it scans the AI/LLM layer (model buckets, agent service accounts, LLM creds), which is exactly the "beyond CIS" gap; the estate's other cloud tooling is compliance-oriented.
- Gaps: no GCP support (estate's own cloud!), 1★/single-author project, README install instructions aspirational re PyPI.

### 1.2 ATMoCloud — **paper only, no code, LOW**
- Resolves to: "ATMOcloud: Automated Threat Modeling for Cloud Architectures Through Cyber Threat Intelligence Enrichment and Structured Validation" — Noam Tarshish, Avishag Shapira, Ido Hersko et al. (Ben-Gurion University, Elovici/Shabtai group), published 2026-07-01, 0 citations (Exa library page + IEEE CSDL: computer.org/csdl/proceedings-article/icws/2026/376900a116).
- `gh api users/noamtarshish/repos` → full repo list read; **no ATMOcloud repo exists**. arXiv queries (`ti:"Automated Threat Modeling for Cloud Architectures"`, `all:Tarshish AND all:threat`) → empty.
- Value: **LOW** — reference/theory (CTI-enriched threat modeling with structured validation); nothing to install.

### 1.3 ZeroGuard — **name collision; two real resolutions**
- (a) **Paper**: "ZeroGuard: A Multi-Agent Zero-Trust Framework for Autonomous IaC Security Remediation" — Harish Apuri, Shikher Goel, Madhan Mohan Reddy Chinthala, Charani Yepuri — SSRN abstract 7068598 (papers.ssrn.com/sol3/papers.cfm?abstract_id=7068598). No arXiv hit, no code repo found. LOW (reference).
- (b) **Package**: `zeroguard-policy` v0.1.0 on PyPI (https://pypi.org/project/zeroguard-policy/, repo NinjaGamerYT12/zeroguard-policy, 1★, pushed 2026-05-16). README (read): "Zero-dependency security engine... protects autonomous AI Agent workflows from infinite logic loops and malicious code execution. Built entirely with the Python Standard Library... sub-millisecond". LoopGuard (SHA-256 fingerprinted circuit breaker after 3 identical tool calls) + ExecutionGuard (deny-by-default AST allowlist, blocks import/os/subprocess/eval/exec). Install: `pip install zeroguard-policy`. Windows: **native** (stdlib only). Value: **MEDIUM** — not cloud, but a fail-closed guard relevant to the estate's 43-backend MCP gateway / agentic loops.
- (c) zeroguard.com — commercial "Modern Threat Hunting Platform" (vendor page seen in Exa results). Not open-source, not installable. Also ~20 unrelated student/hobby "ZeroGuard" repos (email security, IoT anomaly detection, OWASP API scanner Himanshu0523/ZeroGuard-, etc.) — noise, not recorded further.

### 1.4 GenSecOps — **dead academic project, LOW**
- Repo: https://github.com/aatharvauti/GenSecOps (0★, pushed 2024-04-17, Python). README (read): "Leveraging GenAI with DevSecOps (GenSecOps)... Final Year Engineering Academic Project". No stars, no releases, dormant 2.5 years. Nothing usable. Web surface for "GenSecOps" is the generic GenSecOps vendor marketing term, not a tool.

## 2. MCP servers for AWS/Azure/GCP offensive assessment (beyond CIS)

### 2.1 badchars/cloud-audit-mcp — **the lane's exact ask, HIGH**
- https://github.com/badchars/cloud-audit-mcp (24★, TypeScript, MIT, pushed 2026-03-14).
- README (read in full, first 260 lines): "Cloud security audit tools for AI agents — AWS, Azure, GCP misconfiguration detection via MCP. 38 tools, 60+ checks. The agent finds vulns, not you." Comparison table explicitly markets **"Offensive-focused — privilege escalation paths, credential exposure, attack chains"** vs Prowler/ScoutSuite/CloudSploit's compliance scope.
- Tools seen in README examples: `aws_check_s3_public`, `aws_check_s3_objects`, `aws_check_lambda_env`, `aws_check_iam_policies`, `aws_check_ec2_imds`, `cloud_run_all {provider}`, `cloud_audit_summary`, `cloud_audit_report`; sample finding "IAM policy allows privilege escalation via CreatePolicyVersion".
- Install: `git clone https://github.com/badchars/cloud-audit-mcp && cd cloud-audit-mcp && bun install`; run `bun run /path/to/cloud-audit-mcp/src/index.ts`. Auth = existing cloud creds (AWS_PROFILE / az login / gcloud ADC). No Docker.
- Windows: **native via Bun for Windows** (bun 1.1+ supports Windows). Bun not yet verified installed on this VM — install with `powershell -c "irm bun.sh/install.ps1 | iex"` (from bun.sh docs; not run this session).
- Value: **HIGH** — plugs straight into the estate's MCP gateway pattern (stdio), covers all three US clouds, and is agent-first rather than report-first.

### 2.2 cdxiaodong/cain-agent — **HIGH**
- https://github.com/cdxiaodong/cain-agent (961★, Python, pushed 2026-09-29 — same day as this research).
- README (read): "Cain is an AI penetration-testing engineer built for real-world authorized security assessments... ships a cloud penetration module covering AWS / Azure / GCP / 阿里云 / 腾讯云 / 华为云". Deterministic attack pipeline, scope enforced by engineering constraints; 44 test files covering cloud modules; report rendered by pure-Python template.
- Install: `git clone ... && pip install -e .` plus `pip install -e ".[cloud]"` (AWS S3, Huawei OBS, Kubernetes checks). pi backend needs Node.js 20 (`npm ci --prefix toolchain/pi`); claude backend needs the Claude CLI (estate has both).
- Windows: **native Python** (pure-Python core; cloud extras are boto3/OBS SDKs). No Docker required.
- Value: **HIGH** — the only 900★+ AI-pentest agent with a first-class multi-cloud module including Chinese clouds; complements CyberStrike rather than duplicating it.

### 2.3 jowhee327/aws-security-agent — **MEDIUM**
- https://github.com/jowhee327/aws-security-agent (0★, TypeScript, pushed 2026-09-13). "AWS Security scanning MCP Server — works with Kiro, Claude Code, Cursor. Supports AWS China regions."
- README: **`npm install -g aws-security-mcp`** (published npm package), Node ≥18, host "Any of: a developer workstation (macOS / Linux / Windows)...". Glama tool listing shows `scan_iam_privilege_escalation` tool.
- Windows: **native (npm)**. Value: MEDIUM — clean packaging, priv-esc scanning, AWS-only, young project.

### 2.4 ElishaKay/dawshund_mcp — **MEDIUM**
- https://github.com/ElishaKay/dawshund_mcp (0★, pushed 2026-03-30). "MCP server to enumerate AWS IAM data, analyze effective permissions, and visualize access relationships" — MCP wrapper over the dAWShund AWS-IAM-graph project.
- README: Python FastMCP + boto3/neo4j/flask; `setup.sh` installs deps and clones upstream dAWShund; requires AWS CLI on PATH.
- Windows: **native Python**; setup.sh is bash → runs in the estate's Git Bash (neo4j needed for graph store would be a JAR/service — the one non-trivial piece).
- Value: MEDIUM — IAM attack-path graphs (estate mandate example was "MCP server that exposes BloodHound attack paths"; this is the AWS-IAM analogue).

### 2.5 wgpsec/CloudSword — **MEDIUM (scope caveat)**
- https://github.com/wgpsec/cloudsword (624★, Go, Apache-2.0, pushed 2026-02-03). "帮助云租户发现和测试云上风险" — comprehensive cloud-risk testing tool.
- README (read): MCP protocol since v0.0.2, both SSE and STDIO — `./cloudsword sse http://localhost:8080`. Rich per-cloud module tables (list assets, OSS search, ECS ops, RAM create user / attach policy / create login profile / create access key — i.e. real post-exploitation actions).
- Release v0.0.2 (2025-04-01) assets include **cloudsword_v0.0.2_windows_amd64.zip** (+arm64/386, linux, darwin, freebsd) → **native Windows binary**.
- **Caveat verified from README tables: cloud coverage is 阿里云/腾讯云/华为云/百度云 (Chinese clouds) — I found no AWS/Azure/GCP module tables in the README** despite grepping for them. Value: MEDIUM — best-in-class if Chinese-cloud assessments ever enter scope; not a US-cloud answer.

### 2.6 Official/vendor MCP API bridges (generic, agent drives the offense)
- **awslabs/mcp → src/aws-api-mcp-server**: "enables AI assistants to interact with AWS services... through AWS CLI commands" — any AWS API from the agent. README states it is **superseded by the official AWS MCP server** (docs.aws.amazon.com/agent-toolkit, migration guide in repo). Install: `uvx awslabs.aws-api-mcp-server@latest` (uv runs on Windows). Also present: `security-agent-mcp-server` (MCP for the AWS Security Agent service — code scan + **pentest against live applications**; `uvx awslabs.security-agent-mcp-server@latest`) and `well-architected-security-mcp-server`.
- **Azure**: Azure/azure-mcp (1223★, C#) is **archived 2025-08-25**, code moved to **microsoft/mcp → servers/Azure.Mcp.Server** (README states this; verified by fetching the archived README stub).
- **Microsoft Graph / Entra surface**: Softeria/ms-365-mcp-server (1001★, npm, Graph API) — the estate can point an agent at Entra objects/role assignments through it. microsoftgraph/msgraph-mcp → 404 (not public under that name; not found).
- GCP official MCPs are dev-oriented only (GoogleCloudPlatform/cloud-run-mcp 631★, gke-mcp 167★, gemini-cloud-assist-mcp 68★) — no offensive value.
- Value: MEDIUM — no checks of their own; they are the raw API hands for an agent that already knows cloud attack techniques (pairs with hexstrike/decepticon).

### 2.7 Other cloud-security MCPs recorded
- Ta0ing/MCP-SecurityTools (410★, Go, pushed 2025-04-07) — Chinese curated meta-collection of security MCPs: uncover-MCP (FOFA/Shodan), ENScan_GO-MCP (one-click corp intel), VirusTotal-MCP, **cloudsword-MCP**, ZoomEye-MCP (`pip install mcp-server-zoomeye`), AWVS-MCP; Ghidra/IDA/Nmap-MCP "planned". Value: MEDIUM as a discovery index; estate already has nuclei/nmap fronts.
- SiteQ8/CloudMCP-Arsenal (0★, Python 3.9+, SANS Cloud Exchange 2026 demo) — attack MCP server (`cloud_s3_enum`, `cloud_metadata`, `cloud_cert_trans`, `cloud_waf_detect`, `cloud_iam_miscon`, `cloud_playbook`) + defense server. Run: `python3 scripts/mcp-servers/cloud_recon_server.py --port 9090`. Value: LOW-MEDIUM (demo-grade, but a clean offensive-cloud-MCP reference design).
- Jaikumar3/nimbus-mcp (0★, JavaScript) — 45 tools, multi-region, TRA reports, CIS/NIST/PCI-DSS — compliance-leaning. LOW.
- cdxiaodong/cloud_native_mcp (4★, pushed 2025-03-28) — CF-style AK/SK automated attack-utilization MCP for AWS/Azure/Aliyun/Huawei/Tencent/GCP. Author's own README note: "最新版本云鉴已支持，不用我了" (superseded by 云鉴/CloudSword, no longer needed). Value: LOW — superseded, stale.
- Pratikchandrathakur/IAM-Sentinel (1★, Python, pushed 2026-07-25) — "Air-gapped, deterministic AWS/Azure/GCP IAM privilege-escalation scanner — Terraform PR-gate, MCP for Cursor/Claude Code". README: docker-compose primary (`docker compose up -d --build`), BSL 1.1, INSTALL.md claims Mac/Win/Linux/WSL. Value: MEDIUM minus — priv-esc rule engine is on-lane, but docker-compose-first on a no-Docker estate; native Windows path unverified.
- Baneado98/cloud-pathfinder (0★, 2026-06-24) — IaC attack-path auditor (Terraform/CFN/K8s), MCP server + x402 API. "Finds internet-to-crown-jewel chains, not just lint." Value: LOW-MEDIUM, unproven.
- blackrabbit1x0/agentgraph (0★, Go, pushed 2026-09-03) — attack-path analysis for AI agents (agents, MCP tools, identities, secrets, CI/CD, cloud). Install: brew/install.sh/docker(neo4j demo). Value: LOW-MEDIUM, 0★.
- Vivek29112001/cloud-audit-mcp (0★) — clone-ish "MCP-based AI cloud auditing platform". Not inspected further (0★, no differentiator). LOW.

## 3. Classic cloud-offensive corpus (status checked 2026-09-29, Windows-native scoring)

| Tool | Status (gh api repos/…) | Install / Windows | Value |
|---|---|---|---|
| NetSPI/gcpwn | 313★, pushed 2026-09-28 | **PyPI `pip install gcpwn`** (v0.5.25, >=3.11; PyPI JSON verified); `python -m gcpwn`. Release binaries are ubuntu-only but pip route is clean. | **HIGH** — GCP+Workspace pentest → BloodHound OpenGraph; the estate itself runs on GCP. |
| RhinoSecurityLabs/pacu | 5345★, pushed 2026-05-19 | git clone + pip (Python). Windows mostly OK; a few modules assume Linux. | HIGH — the AWS exploitation framework. |
| DataDog/stratus-red-team | 2409★, pushed 2026-09-29 (same-day active) | Go, prebuilt binaries incl. Windows; `stratus list/exploit`. | HIGH — adversary emulation AWS/GCP/Azure, no Docker needed. |
| dirkjanm/ROADtools | 2725★, pushed 2026-08-05 | `pip install roadrecon roadlib roadoidc` (PyPI). dirkjanm tooling is Windows-friendly. | HIGH for Azure/Entra offense. |
| nccgroup/ScoutSuite | 7831★, pushed 2025-09-23 | pip; Python. | MEDIUM — multi-cloud audit but CIS-flavored (the thing we're going beyond). |
| prowler-cloud/prowler | 14896★, pushed 2026-09-29 | `pip install prowler`. | MEDIUM — compliance-first; already the "200-page PDF" cloud-audit-mcp positions against. |
| nccgroup/pmapper | 1582★, pushed 2024-08-02 (stale) | pip. IAM priv-esc graph for AWS. | MEDIUM — right concept (priv-esc paths), unmaintained; dawshund_mcp/gcpwn cover similar ground actively. |
| cyberark/SkyArk | 911★, pushed 2024-12-17 | **PowerShell — Windows-native by design.** Azure/AWS privileged-entity discovery. | MEDIUM. |
| SpecterOps/AzureHound | 962★ | Go binary. Azure data exporter for BloodHound. | MEDIUM-HIGH if estate stands up BloodHound graph analysis (mandate example: "MCP server that exposes BloodHound attack paths"). |
| wyzxxz/aksk_tool | 789★, pushed 2025-02-13 | Multi-cloud AK/SK exploitation (Aliyun/Tencent/Huawei/AWS/UCloud/JD/Baidu/Qiniu/Volcano): ECS command execution, OSS/COS/S3 mgmt, RDS, domains, **add RAM/IAM users**. Language field null in API (script-based). | MEDIUM — strongest AK/SK post-exploitation coverage incl. AWS; Chinese-cloud oriented; stale. |
| libaibaia/cloudSec | 598★, pushed 2024-12-19 | Java jar → runs on Windows with JRE. AK/SK web util tool (CN clouds). | MEDIUM-LOW. |
| gebalamariusz/cloud-audit | 72★, pushed 2026-09-22 | **`pip install cloud-audit`** (PyPI; also pipx/uvx per README). "Fast, opinionated AWS security scanner. Curated checks. Zero noise. Copy-paste fixes." (prhr/cloud-audit is the 1★ origin/fork lineage.) | MEDIUM — clean AWS scanner, agent-friendly output. |
| ankitjha67/orthrus | 11★, pushed 2026-08-22 | `pip install -e .` — README: "Python 3.11+ (developed on 3.14, Windows 11)... lean core dependencies are pure-Python/wheels and install on Windows". 70 scanners, 28 confirmers, cloud CSPM/IAM, bounded LLM agent, **MCP**; docker optional. | HIGH-MEDIUM — explicitly Windows-first with cloud checks + MCP surface. |

Adjacent (AI-agent security, not cloud): **guard0-ai/g0** — 50★, TypeScript, pushed 2026-09-21, npm `@guard0/g0`. "Control layer for AI agents. 1,200+ rules... finds every AI tool, MCP server... MCP supply-chain assessment, rug-pull detection, protect mode (MCP proxy routing + Claude Code hook enforcement)." Windows: native npm. Value for a 43-backend MCP estate: MEDIUM-HIGH.

## 4. Reference intel (not installable)
- **Unit 42 "Zealot"**: "Can AI Attack the Cloud? Lessons From Building an Autonomous Cloud Offensive Multi-Agent System" (origin-unit42.paloaltonetworks.com/autonomous-ai-cloud-attacks/, 2026-04-23). Multi-agent (LangGraph) autonomous cloud attack; chained SSRF → IMDS credential theft → BigQuery exfil on GCP in ~25 min, ~$160 total cost; emphasis on tool permissions as the real security boundary. PoC code not published. Use as doctrine for the estate's own red-team agent design.
- **Yeti-791/Awesome-Offensive-AI-Agentic-Landscape** (315★, pushed 2026-09-10) — curated index of AI-pentest agents/aligned-vs-unaligned models incl. China ecosystem; confirms CyberStrike/PentAGI positioning; no new cloud-MCP tools beyond those above.
- **OFFENSAI** (offensai.com) — commercial agentic red-team/agent network with cloud security testing platform. Commercial, note-only.
- **ZeroGuard SSRN 7068598** + **ATMOcloud (IEEE ICWS 2026)** papers — see §1.

## 5. Every query issued this session
### gh api (GitHub)
1. `search/repositories?q=AICloudSentinel` → 1: SpecterBreach/AICloudSentinel
2. `search/repositories?q=ATMoCloud` → 1: weather webapp (wrong)
3. `search/repositories?q=ZeroGuard` → 38 (noise; real hits resolved later)
4. `search/repositories?q=GenSecOps` → 1: aatharvauti/GenSecOps
5. `repos/SpecterBreach/AICloudSentinel/readme`, `contents/pyproject.toml`, `contents/` — README + deps + tree
6. `repos/aatharvauti/GenSecOps/readme` + repo meta
7. `search/repositories?q=ATMOcloud+OR+threat+modeling+cloud+architecture+agent` → 40 (noise)
8. `search/repositories?q=zeroguard+infrastructure+code` → 0
9. `users/noamtarshish/repos` → 20 repos, no ATMOcloud
10. `search/repositories?q=topic:mcp-server+cloud+security` (39 results, read all)
11. `repos/badchars/cloud-audit-mcp/readme` (full) + meta
12. `search/repositories?q=aws+mcp+pentest` → 2
13. `search/repositories?q=cloud+exploitation+mcp` → 3 (orthrus!)
14. `search/repositories?q=azure+mcp+offensive` → 0
15. `search/repositories?q=gcp+mcp+security+audit` → 7
16. `search/repositories?q=mcp+privilege+escalation` → 16 (IAM-Sentinel)
17. `search/repositories?q=cloud+attack+mcp+created:>2026-04-01` → 13 (CloudMCP-Arsenal, agentgraph, cloud-pathfinder)
18. `search/repositories?q=meteor+cloud+exploitation` → 0; `q=strofer+gcp` → 0 (both gone/renamed)
19. `search/repositories?q=azurehound` → SpecterOps/AzureHound etc.
20. `search/repositories?q=gcp+exploitation+framework` → NetSPI/gcpwn
21. `repos/NetSPI/gcpwn/readme` + `releases` ; `repos/ankitjha67/orthrus/readme`; `repos/SiteQ8/CloudMCP-Arsenal/readme`
22. `repos/awslabs/mcp/contents/src` (35 servers listed) + `contents/src/aws-api-mcp-server/README.md` + `contents/src/security-agent-mcp-server/README.md`
23. `repos/Azure/azure-mcp` + readme (archived → microsoft/mcp)
24. `search/repositories?q=org:GoogleCloudPlatform+mcp` → 10 (dev-only)
25. `search/repositories?q=microsoft+graph+mcp+server` → 227 (Softeria top)
26. `search/repositories?q=org:microsoftsecurityinsights+mcp` → 422 validation error (org not searchable)
27. `search/repositories?q=cloudsword` → wgpsec/cloudsword (624★); `repos/wgpsec/cloudsword` + readme + releases
28. Meta checks: RedSecOps/meteor 404, SD-x/Strofer 404, cyark/workforce 404, BloodHound/AzureHound 404 → corrected to SpecterOps/AzureHound
29. Status batch: ScoutSuite, prowler, pmapper, ROADtools, pacu, stratus-red-team, cyberark/SkyArk
30. `repos/Pratikchandrathakur/IAM-Sentinel/readme` + meta
31. `repos/ElishaKay/dawshund_mcp/readme`; `repos/jowhee327/aws-security-agent/readme`; `repos/gebalamariusz/cloud-audit/readme`; `repos/blackrabbit1x0/agentgraph/readme`
32. `search/repositories?q=topic:red-team+topic:cloud` → 12
33. `search/repositories?q=autonomous+pentest+created:>2026-04-01` → 264 (context: pentestcode 721★, Yeti-791 landscape 315★, etc.)
34. `search/repositories?q=cf+cloud+exploitation` → 4 (cf backups; original teamssix cf not found)
35. `search/repositories?q=awesome-red-teaming` → canonical yeyintminthuhtut/Awesome-Red-Teaming
36. `repos/guard0-ai/g0` + readme
37. `repos/Ta0ing/MCP-SecurityTools/readme`
38. `repos/cdxiaodong/cain-agent/readme`
39. `repos/NinjaGamerYT12/zeroguard-policy/readme`
40. `repos/cdxiaodong/cloud_native_mcp`, `repos/wyzxxz/aksk_tool`, `repos/libaibaia/cloudSec`, `repos/al0ne/cloud-audit` — meta via search results; `repos/kohlersbtuh15/accesskey_tools` → **404** (seen in DDG results as live; already gone/renamed — dead end recorded)

### Exa (`api.exa.ai/search`)
- "ATMoCloud cloud security tool" → ATMOcloud paper landing + AtmosGuard/atmos (DevOps, unrelated)
- "ZeroGuard AI cloud security platform tool 2026" → zeroguard.com, ZeroGuard SSRN paper, guard0.ai/g0, Zero-X
- "MCP server that finds privilege escalation attack paths in AWS IAM" → IAM-Sentinel, gebalamariusz/cloud-audit, nimbus-mcp, dawshund_mcp, jowhee327/aws-security-agent, ekrmcakir/aws-security-mcp, prhr/cloud-audit, badchars/cloud-audit-mcp
- "offensive cloud security agent LLM GCP Azure exploitation beyond CIS" → Unit 42 article, CyberStrike (estate-known), cain-agent, OFFENSAI, skycenter-claude

### Firecrawl
- `/v1/scrape` exa.ai library page → **401 Invalid token**; `/v1/search` "ATMoCloud threat modeling" → **401 Invalid token**. Backend dead this session.

### DDG (ddgs python)
- "ZeroGuard multi-agent zero-trust infrastructure as code remediation arxiv" → SSRN 7068598 + adjacent papers
- "ATMOcloud Tarshish Shapira Elovici github" + "ATMOcloud Ben-Gurion ... code repository" → author profile, IEEE CSDL link, no code
- 云安全 攻击 MCP 服务器 AWS Azure 利用 工具 → cdxiaodong/cloud_native_mcp, Ta0ing/MCP-SecurityTools
- クラウドセキュリティ MCP 攻撃 ツール LLM → defensive articles only (no tools)
- 클라우드 보안 MCP 공격 도구 → defensive articles only
- 云鉴 云安全 AK SK 利用 工具 github → al0ne/cloud-audit, libaibaia/cloudSec, wyzxxz/aksk_tool, kohlersbtuh15/accesskey_tools (repo now 404), ffffffff0x/1earn notes
- "yunjian cloud security tool github AK SK" → same set

### arXiv API
- `ti:"Automated Threat Modeling for Cloud Architectures"`, `all:Tarshish AND all:threat`, `ti:"Zero-Trust Framework for Autonomous" AND all:remediation` → all empty

### Raw README walks
- punkpeye/awesome-mcp-servers (1.36MB) — Cloud Platforms + Security sections fully read: all dev/ops or defensive; **no offensive cloud-assessment MCP listed** → confirms badchars/cloud-audit-mcp and the CN ecosystem tools fill an unlisted gap.
- sbilly/awesome-security — cloud hits all defensive (Falco/CrowdSec/Wazuh/KICS) + offense infra (Axiom, Redcloud).
- yeyintminthuhtut/Awesome-Red-Teaming — cloud content is legacy CloudFront domain-fronting C2 tricks; nothing current.
- Yeti-791/Awesome-Offensive-AI-Agentic-Landscape — read for cloud/cain/pentagi/cyberstrike mentions.
- boldsecurity/awesome-llm-security → fetch failed (14-byte stub, wrong slug); coverage compensated by the lists above.

### HN Algolia
- "cloud MCP security" → Director MCP gateway (14pts), mcp-certify; nothing cloud-offensive.
- "AI agent cloud pentesting" → nothing notable.

## 6. Dead ends / not verified
- Firecrawl 401 (see §0) — the only mandated backend unavailable; all its intended queries were re-run on Exa/DDG/raw GitHub.
- `pip install aicloudsentinel` from PyPI: **does not exist** (404) despite README claim.
- teamssix `cf` original repo: not found (only 64★ backup passwa11/cf-backup, stale 2023-10).
- meteor (RedSecOps) / Strofer (SD-x): repos 404 — tools apparently deleted/renamed; no successor located.
- kohlersbtuh15/accesskey_tools: appears in DDG index but `gh api repos/...` → 404 at research time.
- IAM-Sentinel native-Windows path (INSTALL.md claims Win support): NOT verified — quickstart is docker-compose; estate has no Docker.
- Bun runtime present on this VM: NOT verified (only read bun.sh install docs reference).
- Anything requiring actual cloud creds (running scans): not run — this lane is discovery/scoring only, per ask.

## 7. Exhaustion statement
Final consecutive query batches (`azure mcp offensive` → 0 new; `meteor/strofer` → 0; topic:red-team+cloud → nothing new beyond recorded; awesome-lists → only defensive/legacy entries; JP/KR searches → articles only) returned nothing new. All three usable backends (gh, Exa, DDG) plus raw-list walks were exercised. Exhaustion claimed for: named tools (all four resolved), offensive cloud MCP servers (US + CN ecosystems), and the classic Windows-native cloud-offensive corpus. Not exhausted (out of lane): pure LLM-jailbreak tooling, Kubernetes-only tooling, commercial-only platforms.
