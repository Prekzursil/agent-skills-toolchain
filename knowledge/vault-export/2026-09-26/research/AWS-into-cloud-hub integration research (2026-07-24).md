---
title: AWS-into-cloud-hub integration research (2026-07-24)
type: research
permalink: main/research/aws-into-cloud-hub-integration-research-2026-07-24
tags:
- aws
- cloud-hub
- mcp
- sso
- integration
- research
- '2026-07-24'
---

3-lane Opus/max research (wf_8c31870b). cloud-hub source = `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\cloud-hub\` (hub.py, launched by ~/.mcp.json via C:\Python314\python.exe).

## Observations
- [decision] RECOMMENDED MCP = awslabs.aws-api-mcp-server (official awslabs/mcp, 9.5k-star, daily-maintained, Apache-2.0). #mcp — `call_aws` runs ANY aws CLI command = full AWS surface ("most features"). boto3 default cred chain -> SSO just works + auto-refreshes STS per call_aws. Built-in guardrails READ_OPERATIONS_ONLY / REQUIRE_MUTATION_CONSENT. Install `uvx awslabs.aws-api-mcp-server@latest` (cmd /c shim on Windows). CAVEAT: MIGRATION.md marks it "superseded" by a managed remote AWS MCP (mcp-proxy-for-aws, preview) -> EOL-watch. RUNNER-UP = BUILD a boto3 FastMCP wrapper (aws-mcp/server.py mirroring databricks-mcp/server.py:1-119) -> aws_*-namespaced (auto ConfirmGate on aws_*_delete), offline enum, no deprecated dep, ~120 LOC + TDD/100%/review. boto3 CONFIRMED present under C:\Python314.
- [decision] AUTH = IAM Identity Center SSO, 4 Bolt accounts sharing ONE sso-session (bolt-sso), NO long-lived secrets. #auth — ~/.aws is greenfield (empty). `aws configure sso` x4 reusing the session; `aws sso login --sso-session bolt-sso` unlocks all 4. boto3 reads ~/.aws/sso/cache, auto-refresh (SSO token 8h default; STS ~1h auto-renew). Accounts (from owner screenshots): Root 737418964414, Maps-Team-Test 414388475997, DataScience 287845475429, Data-Engineering 451613234044; SSO region eu-central-1; portal 71582c.awsapps.com; role ENGGeo<acct>.
- [decision] ROTATOR = FREE via cloud-hub's AccountPolicy(platform=aws, mode=env). #rotator — Declaring it on the AWS BackendSpec SYNTHESIZES aws_account_list/current/add/remove/switch/cycle in-hub (evidence: _shared/accounts.py ACCOUNT_OPS:62; hub.py:275-289 respawns child on switch). ZERO account code. Structural analog = OVH (backends.py:218; accounts.json "ovh":21). AWS env bundle = AWS_PROFILE + AWS_DEFAULT_REGION (SECRET-FREE with SSO). Files: backends.py default_backends() (add BackendSpec), accounts.json (add "aws" block).
- [gotcha] SECURITY finding (pre-existing, not AWS): the databricks/bolt-ds account in cloud-hub/accounts.json stores a LITERAL PAT. #security — accounts.json is git-crypt-committed. Do NOT repeat literal secrets for AWS (SSO = secret-free by construction). Flag to owner: consider ${ENV}-ref'ing the databricks PAT.
- [reference] Integration = config-only adopt route: aws configure sso x4 -> register BackendSpec -> add accounts.json aws block -> ~/.mcp.json env passthrough (AWS_PROFILE/AWS_DEFAULT_REGION + optional READ_OPERATIONS_ONLY) -> `python hub.py --refresh aws` (cache + both-states probe) -> restart. UNVERIFIED: uvx can fetch the pkg on this box; it enumerates tools/list WITHOUT creds (if not -> switch to BUILD wrapper); aws CLI present for call_aws.

## Relations
- relates_to [[social-hub lazy MCP multiplexer (built)]]
- relates_to [[Databricks auth restore 2026-07-24]]