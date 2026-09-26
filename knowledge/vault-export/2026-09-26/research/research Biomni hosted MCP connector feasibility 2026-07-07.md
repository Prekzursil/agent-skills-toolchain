---
title: research Biomni hosted MCP connector feasibility 2026-07-07
type: note
permalink: main/research/research-biomni-hosted-mcp-connector-feasibility-2026-07-07
tags:
- research-report
- high-confidence
- biomni
- phylo
- mcp
- connector
- deep-research
---

# Can we build an UPGRADED MCP connector to HOSTED Biomni Lab? — VERDICT: NO (controls are UI-only, not client-buildable) · 2026-07-07

Confidence: HIGH (primary-source protocol metadata fetched directly). Providers: firecrawl/exa (search-hub), deepwiki, + 2 research subagents (1 no-op'd, redone inline).

## The ask
User wanted to UPGRADE the Biomni connector (OVH/Modal cloud-hub pattern) to expose more tools: attach @@-resources, attach +Skills, set effort (standard/fast/max), read/change settings, richer live polling. Keep it HOSTED (no self-host).

## VERDICT: not buildable client-side
1. The "Biomni Lab connector" = phylo's OWN remote MCP server at **https://mcp.phylo.bio/mcp** ("Biomni Everywhere", live Jun 2026). You CONNECT to it; you don't RUN it → can't add tools (unlike OVH/hlebtkachenko-mcp which was self-run source I vendored+extended).
2. Auth WOULD work for a custom client: OAuth 2.0 via signin.phylo.bio, with Dynamic Client Registration (RFC 7591) + PKCE + **device-code flow** + offline_access refresh. NOT Enterprise-gated for MCP access. (Fetched .well-known/oauth-protected-resource + oauth-authorization-server.) So a cloud-hub HTTP+OAuth backend is technically possible.
3. BUT the server serves a FIXED 10-tool set: list_workspaces, switch_workspace, create_project, list_projects, list_tasks, start_new_task, send_message, wait_for_next_update, upload_file, list_result_files. → workspace/project/task/file/messaging/POLLING only.
4. NO REST API — the advertised OpenAPI spec is an untouched Mintlify "Plant Store" placeholder. Nothing to wrap.
5. effort / +Skills / @-resource-attach / settings = WEB-UI-ONLY, zero documented API (+Skills and "effort" not even in phylo docs). Custom tool/DB integration = Enterprise "by request".
6. No OSS Biomni-hosted connector exists to vendor (GitHub). snap-stanford/Biomni has NO hosted-phylo client (deepwiki) — expose_biomni_server = local agent only; add_mcp = consume external MCPs.

## What IS achievable (the useful part)
- Drive + poll Biomni: ALREADY have it (start_new_task/send_message/wait_for_next_update/list_tasks/list_result_files) — used all session.
- Skills + resources: invoke by NAMING them in the message text (PROVEN: agent logged "Loading gwas-to-function-twas skill"; auto-retrieves GTEx/OpenGWAS). No @@ attach or connector upgrade needed.
- effort + settings: genuinely unreachable via any MCP (UI-only). User sets in web app.

## Options
1. Feature-request to phylo (expose effort/skills/resource-attach/settings as MCP tools) = ONLY true fix.
2. Cloud-hub register mcp.phylo.bio (OAuth device-code backend) = fleet mgmt only (rotation/labels), SAME 10 tools, no new controls.
3. Self-host OSS = full control, ruled out (compute).
RECOMMEND: keep driving via existing connector + name skills/resources in prompts; set effort/privacy in UI; ToolUniverse for direct tools (unlimited); optional feature-request to phylo.

## Security note
phylo docs pages carried hidden-unicode prompt-injection (flagged by research agent, ignored — not acted on).

## Sources (tier A unless noted)
phylo.bio/blog/biomni-everywhere; mcp.phylo.bio/.well-known/oauth-protected-resource + signin.phylo.bio/.well-known/oauth-authorization-server (fetched); docs.biomni.phylo.bio (features/resources, mention-system, memory, pricing-faq, api-reference/openapi.json=stub); phylo.bio/faq; snap-stanford/Biomni (deepwiki); GitHub search (no phylo connector). Relates [[research-biomni-phylo-bio-access-comp-pharm-fit-2026-07-07]].