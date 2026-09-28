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
never raw WebFetch when a live provider fits. Live rails (allowlisted for headless
subagents): **web** firecrawl → perplexity → exa (search-hub) → tavily → web-search-prime;
**academic** scholarly-access → crossref → openalex → pubmed → arxiv (+sci-hub/annas
labeled fallbacks); **repo/code** zread → deepwiki → context7; **extraction** firecrawl
scrape → web-reader. Workflow prompts must state which providers are live/down at launch
(preflight) and require the routing order above. Dead rails as of 2026-09-22: searxng
(key-free corroborator — re-wire when SEARXNG_URL is fixed), huggingface papers (auth 401),
McpHub aggregation (404 — the hub surface is unreachable until the service is restored).
Gap classes accepted knowingly: Google-Scholar scraping (no maintained MCP), OpenAI/Gemini
native deep-research lanes (codex covers code only).

## Escalation discipline
Tool failed twice on the same shape → two-strikes pivot (AGENTS §4b): change transport
(native tool instead of MCP, PowerShell instead of bash), not capability claims. Nested
Claude sessions (`mcp__claude-code-mcp__*`) are NOT a fallback lane — denied estate-wide
except the sandboxed fork (see GRILL-DECISIONS 2026-09-22).
