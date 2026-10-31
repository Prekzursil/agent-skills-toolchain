---
title: dive-Microsoft-MCP-Server-for-Enterprise---Microsoft-Graph
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-microsoft-mcp-server-for-enterprise-microsoft-graph
---

# Deep-dive: Microsoft MCP Server for Enterprise – Microsoft Graph

Candidate lane: **ad-entra-paths**. Candidate "repo" URL: https://learn.microsoft.com/en-us/graph/mcp-server/get-started
Date of dive: 2026-09-29. Dive environment: Windows VM, Git Bash, `gh` authenticated, `EXA_API_KEY` used for REST search.

## 0. TL;DR verdict

**REAL, official, active, and worth adopting — claim substantively accurate with one numeric discrepancy (41 scopes enumerated in current docs, not 44) and one nuance on "nothing to install locally" (the server is remote, but a one-time per-tenant provisioning step is required; it can be done with zero local install via Graph Explorer, or with a PowerShell module).** It is a hosted first-party service (public preview), not an installable package: there is no pip/npm/Docker artifact anywhere. Windows-native: **native** (remote HTTP MCP; any MCP client works; the optional provisioning module is cross-platform PowerShell 7).

## 1. What the candidate URL actually is

The given "repo" is a **Microsoft Learn docs page**, not a GitHub repo. Verified backing artifacts:

| Artifact | Path | Status |
|---|---|---|
| Docs source (mirror of private primary) | `microsoftgraph/microsoft-graph-docs-contrib` @ `main`, `concepts/mcp-server/` | active; pushed 2026-09-29T01:44:07Z |
| Official product repo (docs/issue tracker only, no server code) | `microsoft/EnterpriseMCP` | created 2025-10-29; pushed 2026-06-04; open, not archived |
| Official MCP catalog listing | `microsoft/mcp` README §"Microsoft MCP Server for Enterprise" | 3,723 stars, pushed 2026-09-29 |

Commands run (exact):
- `gh api repos/microsoftgraph/microsoft-graph-docs` → **404** (old docs repo gone/renamed)
- `gh api repos/MicrosoftDocs/microsoft-graph-docs` → **404**
- `gh api repos/microsoftgraph/microsoft-graph-docs-contrib` → `{"full_name":"microsoftgraph/microsoft-graph-docs-contrib","default_branch":"main","stargazers_count":153,"pushed_at":"2026-09-29T01:44:07Z","open_issues_count":502,"license":"CC-BY-4.0","language":"PowerShell","archived":false,"description":"Documentation for the Microsoft Graph REST API"}`
- `gh api repos/microsoft/EnterpriseMCP` → `{"full_name":"microsoft/EnterpriseMCP","created_at":"2025-10-29T22:28:44Z","pushed_at":"2026-06-04T23:33:45Z","stargazers_count":56,"forks_count":15,"open_issues_count":3,"license":"CC-BY-4.0","language":null,"archived":false,"visibility":"public"}`
- `gh api repos/microsoft/mcp` → `{"full_name":"microsoft/mcp","description":"Catalog of official Microsoft MCP (Model Context Protocol) server implementations...","stargazers_count":3723,"pushed_at":"2026-09-29T17:14:39Z"}`

`microsoft/EnterpriseMCP` contents: only `.gitignore, .vscode, LICENSE, README.md, SECURITY.md, assets` — a **docs/tracking repo**. The server itself is closed-source and Microsoft-hosted. This is not a fake or dead repo: it exists purely to host the README and take issues.

## 2. Sources read (downloaded raw copies in this dir)

- `src-get-started.md` (247 lines) ← `.../concepts/mcp-server/get-started.md` (ms.date 05/20/2026)
- `src-overview.md` (86 lines) ← `.../overview.md` (ms.date 11/18/2025)
- `src-mcp-server-sample-prompts.md` (555 lines), `src-use-enterprise-mcp-server-copilot-studio.md` (173), `src-use-enterprise-mcp-server-microsoft-foundry.md` (88)
- `EnterpriseMCP-README.md` (262 lines) ← `microsoft/EnterpriseMCP@main`
- `microsoft-mcp-README.md` ← `microsoft/mcp@main`

Docs activity (commits touching `concepts/mcp-server`): 2026-03 → 2026-07 (e.g. `2026-05-20 Refresh MCP Server permissions (#28921)`, `2026-05-05 Add ServiceHealth to MCP Server scope (#9884) (#28805)`). Command: `gh api "repos/microsoftgraph/microsoft-graph-docs-contrib/commits?path=concepts/mcp-server&per_page=20"`.

## 3. Claim-by-claim verification

| Claim | Verdict | Evidence |
|---|---|---|
| "Official" | ✅ | Published by Microsoft; endpoint `https://mcp.svc.cloud.microsoft/enterprise` (`src-overview.md:16`); listed in `microsoft/mcp` catalog README:189-195; product repo under `microsoft/` org; docs authors are Microsoft FTEs (`author: FaithOmbongi`). |
| "read-only remote MCP" | ✅ | `src-overview.md:49` "microsoft_graph_get: Runs read-only Microsoft Graph API calls"; `src-overview.md:63` "focuses on ... **read-only** scenarios"; EnterpriseMCP README:56 same. Write ops only "planned for a future release" (README:225). |
| "translating natural language into Graph API over the Entra tenant" | ✅ | `src-overview.md:16`; three tools `microsoft_graph_suggest_queries` (RAG over 500+ real-world Graph query examples), `microsoft_graph_get`, `microsoft_graph_list_properties` (`src-overview.md:44-50`, README:47-52). |
| users/groups | ✅ scopes `MCP.User.Read.All`, `MCP.Group.Read.All`, `MCP.GroupMember.Read.All`, `MCP.GroupSettings.Read.All` (`src-get-started.md:198-201`) |
| apps/SPs | ✅ `MCP.Application.Read.All` (`src-get-started.md:190`); README:62 "Application risk: Which Apps / Service Principals exist, who owns them..." |
| role+PIM assignments | ✅ `MCP.RoleAssignmentSchedule.Read.Directory`, `MCP.RoleEligibilitySchedule.Read.Directory`, `MCP.RoleManagement.Read.All`-style `MCP.RoleManagement.Read.Directory` (`src-get-started.md:219-221`); README:61 "Privileged access: ... PIM status" (needs Entra ID P2 license, `src-overview.md:68`) |
| CA policies | ✅ `MCP.Policy.Read.ConditionalAccess` + `MCP.Policy.Read.All` (`src-get-started.md:215-216`); README:60 |
| risky users/SPs | ✅ `MCP.IdentityRiskyUser.Read.All`, `MCP.IdentityRiskyServicePrincipal.Read.All`, `MCP.IdentityRiskEvent.Read.All` (`src-get-started.md:202-204`) |
| audit logs | ✅ `MCP.AuditLog.Read.All`, `MCP.ProvisioningLog.Read.All` (`src-get-started.md:191,217`); README:65 "audit telemetry" |
| "44 MCP.*.Read.All scopes enumerated" | ⚠️ **inexact** | Command run: `grep -c '^- MCP\.' src-get-started.md` → **41** (lines 188–228). 4 of the 41 don't literally end `.Read.All` (`MCP.LifecycleWorkflows-Workflow.ReadBasic.All`, `MCP.Policy.Read.ConditionalAccess`, `MCP.RoleAssignmentSchedule.Read.Directory`, `MCP.RoleEligibilitySchedule.Read.Directory`) — all read-type. The live servicePrincipal can expose more than the docs list (docs instruct querying `.../oauth2PermissionScopes` and filtering `isEnabled`, `src-get-started.md:172-182`; commit 2026-05-20 "Refresh MCP Server permissions"). 44 vs 41 is a minor stale-count discrepancy, not a fabrication. |
| "nothing to install locally" | ✅ with nuance | The **server** is fully remote (HTTP MCP; no local runtime, no Docker, no package). Nuance: **one-time per-tenant provisioning** is required — either zero-install via Graph Explorer `POST /v1.0/servicePrincipals {"appId":"e8c77dc2-69b3-43f4-bc51-3213c9d915b4"}` (EnterpriseMCP README:16-18) or via PowerShell module (README:118-134). After that, clients just point at the URL. |

## 4. Real install / configuration commands (from sources, not inferred)

1. **One-time tenant provisioning** (Application Administrator or Cloud Application Administrator, `src-get-started.md:28`):
   - PowerShell route (requires **PowerShell 7** + `Microsoft.Entra.Beta` ≥ 1.0.13, README:118):
     `Install-Module Microsoft.Entra.Beta -Force -AllowClobber`
     `Connect-Entra -Scopes 'Application.ReadWrite.All','Directory.Read.All','DelegatedPermissionGrant.ReadWrite.All'`
     `Grant-EntraBetaMCPServerPermission -ApplicationName VisualStudioCode`
   - Zero-install route: Graph Explorer `POST https://graph.microsoft.com/v1.0/servicePrincipals` body `{"appId":"e8c77dc2-69b3-43f4-bc51-3213c9d915b4"}` (README:16-18), then register a client app in Entra and grant `MCP.*` scopes.
2. **VS Code**: one-click install link `https://vscode.dev/redirect/mcp/install?name=Microsoft%20MCP%20Server%20for%20Enterprise&config={...,"type":"http","url":"https://mcp.svc.cloud.microsoft/enterprise"}` (`src-get-started.md:140`, README:148).
3. **Any MCP client**: HTTP server at `https://mcp.svc.cloud.microsoft/enterprise`; OAuth endpoints `https://login.microsoftonline.com/organizations/oauth2/v2.0/{authorize,token}`; scope `api://e8c77dc2-69b3-43f4-bc51-3213c9d915b4/.default` (README Info Table :36-43). GitHub Copilot CLI config in `~/.copilot/mcp-config.json` with `oauthClientId`/`oauthPublicClient` (README:177-186). Claude Desktop / ChatGPT need a custom app registration with their callback redirect URIs (README:22-24).
4. **Disable**: can't be deleted (Microsoft-owned); `PATCH /servicePrincipals(appId='e8c77dc2-...') {"accountEnabled": false}` (`src-get-started.md:232-247`).

There is **no** pip/npm/Dockerfile/release asset — verified by listing `microsoft/EnterpriseMCP` contents (docs-only) and `microsoft/mcp/servers/` (contains only `Azure.Mcp.Server`, `Fabric.Mcp.Server`, `Template.Mcp.Server` — the Enterprise server is NOT in the open catalog code, only referenced in its README).

## 5. Windows-native feasibility

**Native.** The server runs at Microsoft. Local footprint is only:
- an MCP client: VS Code (native Windows), GitHub Copilot CLI, or remote connectors (Claude/ChatGPT — no local install at all);
- optional provisioning tooling: PowerShell 7 + `Microsoft.Entra.Beta` (cross-platform .NET module from Microsoft; official, on PowerShell Gallery — feed responded live on 2026-09-29; exact newest version **not determined** — my parse of the gallery OData feed returned unrelated entries, so reported as not run rather than guessed), or zero-install Graph Explorer.
No dependency chain with Windows problems. Known gotcha: if the Microsoft.Graph PS SDK modules conflict, run `Uninstall-Graph -All` (README:138-143); VS Code MSAL broker error fixed by `"microsoft-authentication.implementation": "msal-no-broker"` (README:3,150).

## 6. Issues / breakage check (commands run)

- `gh api "search/issues?q=repo:microsoftgraph/microsoft-graph-docs-contrib+'MCP Server'+is:issue"` → **0** doc-feedback issues.
- `gh api "repos/microsoft/EnterpriseMCP/issues?state=all"` → 20 issues total; 3 open, all mild: #22 "Queries allowed to all users" (2026-08-12, permission-granularity ask), #21 "When will write operations be supported?" (2026-06-28), #20 "mcp" (vague, 2026-06-08). Closed user-facing ones: #15 "Unable to authenticate?" (2026-03), #14 "not permitted to execute queries related to owned objects" (2026-03, scope behavior). **No breakage pattern, no death signals.**
- Microsoft Q&A thread (found via Exa, fetched): "Unable to find MCP Enterprise resource (e8c77dc2-69b3-43f4-bc51-3213c9d915b4)" (2026-04-24) — one Global Admin hit `AADSTS650057: Invalid resource`; 2 answers, **no accepted answer**; a moderator claimed tenant gating is needed while docs describe self-service provisioning — unconfirmed community noise, not a documented outage.
- Documented constraints (not bugs): PREVIEW (overview:20-24); delegated-only, **app-only not supported** (get-started:172); Global cloud only — no Gov L4/L5, no China (overview:26-30); 100 calls/min/user + Graph throttling (overview:69); DCR not supported (README:74); M365 APIs will be covered by Agent 365 instead (README:224).

## 7. Independent mentions & alternatives (Exa, commands run)

`curl -X POST https://api.exa.ai/search` (queries above) returned, among others:
- Hands-on reviews: office365itpros.com "Testing the MCP Server for Enterprise" (2025-12-11); blog.icewolf.ch preview writeup (2026-01-07); entra.news / Entra.Chat podcast (2025-11-29) interviewing Microsoft Entra AI Innovations' Luca Spolidoro — hackathon origin, patented three-tool design, write-ops roadmap, Security Copilot comparison. (Fetched page; technical detail lives in the audio.)
- Registries/aggregators listing `io.github.microsoft/EnterpriseMCP`: mcppedia.org, typingmind.com, vibehackers.io, mcptoplist.com.
- **Alternative in the same lane**: **Lokka** (Merill Fernando, Microsoft MVP) — open-source local Microsoft Graph MCP server, read+write; plus `hieuttmmo/entraid-mcp-server`. The Microsoft server's differentiators: zero install, RAG-driven query generation, IT-admin-controlled `MCP.*` scope grants, single audited appId.

## 8. Scoring

- **Real/active**: yes — docs commits through 2026-07, product repo pushes through 2026-06, fresh issue filed 2026-08, catalog pushed 2026-09-29, podcast/blogs through 2026-04.
- **Value: high** — first-party, zero-local-install, delegated, read-only, fully-audited (single appId `e8c77dc2-69b3-43f4-bc51-3213c9d915b4` in Graph activity logs) natural-language gateway over Entra. Directly serves the ad-entra-paths lane.
- **Caveats**: public preview; read-only; Global cloud only; no app-only (blocks unattended CI); 100 req/min/user; small scope-count drift in the claim (41 vs 44).
- Repo to cite for the estate: https://github.com/microsoft/EnterpriseMCP (product) + https://learn.microsoft.com/graph/mcp-server/overview (docs).