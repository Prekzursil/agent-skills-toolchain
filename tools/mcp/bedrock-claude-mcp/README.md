# bedrock-claude-mcp

Minimal stdio MCP server exposing **Amazon Bedrock Claude** as chat tools, for
runtimes that cannot talk to AWS directly (ZCode, Claude, any MCP client).

- `claude_chat` — Claude Sonnet (`BEDROCK_CLAUDE_MODEL`, default EU Sonnet 4.5 ID)
- `claude_haiku` — Claude Haiku fast/cheap tier
- `bedrock_models` — list Anthropic models available in the region

Auth: the operator's **AWS SSO credential chain** (`AWS_PROFILE`, default
`bolt-datascience`, region `eu-central-1`). No secrets are stored — the server
shells to `aws bedrock-runtime converse`, so a live SSO session is required
(`aws sso login --profile bolt-datascience`).

Wire into the harness via `.agents/agents.json` (registry entry `bedrock-claude`);
`sync_shared_state.ps1` renders it into ZCode and Claude.

Note: Bedrock bills per token to the AWS account owner. For zero-cost Claude on
this estate use the Claude Max subscription (`claude -p`) instead.
