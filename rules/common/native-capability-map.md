---
paths:
- '**/*'
permalink: dqverify-repo-20261013/rules/common/native-capability-map
---

# Native Capability Map (always-on)

Every session — main loop, workflow subagent, nested context — starts with the native
toolset (Bash/PowerShell, Read/Write/Edit, Grep/Glob, ToolSearch, Skill, Task/Agent,
WebFetch/WebSearch) plus the full MCP registry via ToolSearch. **Never conclude "I don't
have tool X" from a failed call or an error message** — failures are transport/permission
events, not absence. Prove absence with ToolSearch + the tool catalog before claiming it.
Measured 2026-09-22 (wf_c8e4c79c-1c8): an agent that reported "NO native Bash/Read/Write
tools" had successfully called all of them earlier in its own transcript; its failures
were a nested-spawn argv limit (ENAMETOOLONG), a 600s MCP timeout, and browser-tool
errors — none of which remove tools.

## File-ownership vs tool-ownership
Unit prompts that say "you own only `<path>`" restrict WHICH FILES you may write, never
WHICH TOOLS you have. Do not infer tool absence from scope restrictions.

## Images
- On the GLM/z.ai chat plane, image content blocks may not be passed through to the
  model — an attached image can arrive unrendered. That is a transport limitation, not
  a policy refusal; SAY SO explicitly, then use the MCP image lanes:
  `mcp__zai-mcp-server__analyze_image` / `extract_text_from_screenshot`,
  `mcp__ocr-suite__*` (batch/compare), `mcp__pdf_reader__*` for documents.
- Never end an image-dependent task with "can't read it" without having tried a lane.

## Browser
- Native rails: `mcp__playwright__*` (extension/CDP variants), `mcp__chrome-devtools__*`,
  `mcp__playwright-cdp__*`, skills `browser-rail` (logged-in multi-step work),
  `playwright-interactive` (debug loops), `ui-drive` (drive a running app). A rail that
  errors ("No page found") is a dead page-handle — retry with a fresh navigate/snapshot,
  don't declare the capability missing.

## Desktop / OS
- `screenshot` skill (full/window/region), UIA automation, `mcp__zai-mcp-server__*`
  screenshot-analysis. OS-level ops via PowerShell/Bash per `windows-shell.md`.

## Search / deep research (SOTA routing)
Any search or research task routes through the `deep-research` skill's routing table —
never raw WebFetch when a live provider fits. **LIVE SET (verified 2026-09-29, post-consolidation):
web = web-search-prime (z.ai) / web-reader (z.ai) / native WebSearch-WebFetch / firecrawl (:31114, recovered) /
firecrawl self-host :3002 (raw API) / exa (plugin enabled, mount unverified). Long tail lives behind
McpHub (74 registered servers incl. tavily, search-hub, scholarly-access, the RE lane) — reachable via
mcp__McpHub__execute when the hub daemon is healthy.** Dead rails as of 2026-09-29: tavily + search-hub
MCP (McpHub rail, disabled ×35/×41), searxng MCP (container up, front unverified), huggingface papers
(auth 401). Workflow prompts must state which providers are live/down at launch (preflight) and require
the routing order above. Registry + preflight output are SSOT; this table is intent, not inventory.
Gap classes accepted knowingly: Google-Scholar scraping (no maintained MCP), OpenAI/Gemini
native deep-research lanes (codex covers code only).

## Escalation discipline
Tool failed twice on the same shape → two-strikes pivot (AGENTS §4b): change transport
(native tool instead of MCP, PowerShell instead of bash), not capability claims. Nested
Claude sessions (`mcp__claude-code-mcp__*`) are NOT a fallback lane — denied estate-wide
except the sandboxed fork (see GRILL-DECISIONS 2026-09-22).