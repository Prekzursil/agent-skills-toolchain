# memory-guard — inbound tool-output injection guard

**Type:** PostToolUse hook  
**Threat model:** OWASP Agent Memory Guard (ASI06) — prompt injection via web/scrape content ingested into context and persisted to the basic-memory vault.

## What it does

Scans the **output** of untrusted web-content MCP tools for prompt-injection payloads **before** that text lands in context (and later in memory).

On detection it emits a single `additionalContext` warning naming the tool and the signal categories found — never blocks.  Clean output = silent exit.

## Scan-list (tools whose output is scanned)

Tool name must contain one of these substrings (case-insensitive):

| Substring | Covers |
|---|---|
| `firecrawl` | firecrawl_scrape, firecrawl_search, firecrawl_crawl, firecrawl_extract, … |
| `exa` | web_search_exa, web_fetch_exa, … |
| `scrapegraph` | smartscraper, markdownify, scrape, searchscraper, … |
| `tavily` | tavily_search, tavily_extract, tavily_crawl, tavily_research, … |
| `claude-in-chrome` | get_page_text, read_page, read_console_messages, … |
| `apify` | any Apify actor output |
| `markitdown` | markitdown__convert_to_markdown |
| `pdf-reader` | pdf-reader__read_pdf |
| `webfetch` | built-in WebFetch |
| `websearch` | built-in WebSearch |
| `repomix__pack_remote` | only remote pack (untrusted); local pack excluded |

## Allowlist (never scanned — silent exit)

These tools legitimately return high-entropy, exploit-shaped, or security-tool output that would produce enormous false-positive noise.  Allowlist takes precedence over the scan-list.

`ghidra`, `ida`, `frida`, `binary-ninja`, `cheatengine`, `hexstrike`, `semgrep`, `sonar`, `codacy`, `deepsource`, `qlty`, `sentry`, `github_cli`, `gh_`, `postgres`

## Injection signals detected

| Signal category | What it matches |
|---|---|
| `imperative-override` | "ignore all previous instructions", "disregard the system", "forget your instructions" |
| `role-spoofing` | "you are now", "new instructions:", `</system>`, `[INST]`, "### System", "developer mode" |
| `agent-directed-command` | "as an AI", "assistant, please send/execute/exfiltrate", "tool_call", "your tools" |
| `data-exfil` | send/post/upload near a URL or email address |
| `injection-marker` | "PROMPT INJECTION", "jailbreak", "DAN", `IMPORTANT: ignore` |
| `hidden-unicode` | zero-width / bidi control chars (U+200B–200F, U+202A–202E, U+2066–2069, U+FEFF) |
| `base64-near-imperative` | large base64 blob within ~120 chars of an imperative verb |

## Design constraints

- **Fail-open:** ALL logic wrapped in try/except; any error → `sys.exit(0)` emitting nothing.
- **Non-nagging:** zero output for clean content.
- **Deterministic:** pure regex + character-range scan.  No LLM calls, no network, no DB.
- **Bounded:** scans only the first 200 KB of output.
- **Windows-safe:** `encoding="utf-8", errors="replace"` on all I/O.

## Registration in settings.json

Add the following block inside `"PostToolUse"` in your `~/.claude/settings.json` (or the project-level `.claude/settings.json`).  The `".*"` matcher means the hook runs for every tool, but internally it exits 0 immediately for anything not in the scan-list, so cost is negligible.

```json
{
  "matcher": ".*",
  "hooks": [
    {
      "type": "command",
      "command": "python \"C:\\Users\\Prekzursil\\.claude\\hooks\\memory-guard\\scan.py\""
    }
  ],
  "description": "Inbound tool-output injection guard (OWASP ASI06) — scans web/scrape MCP outputs for prompt-injection signals before they land in context"
}
```

If you prefer to restrict the matcher to only known-untrusted tools (avoids even the early-exit overhead), use:

```
"matcher": "mcp__firecrawl__|mcp__exa|mcp__scrapegraph|mcp__tavily|mcp__claude-in-chrome|mcp__markitdown|mcp__pdf-reader|WebFetch|WebSearch|mcp__repomix__pack_remote"
```

The broad `".*"` is simpler to maintain and the cost difference is immeasurable (the hook does one string scan and exits in < 1 ms for non-scan-list tools).

## Running tests

```
python C:\Users\Prekzursil\.claude\hooks\memory-guard\test_scan.py
```

11 tests covering: injection warn, clean-silent, allowlist-silent, hidden-unicode warn, fail-open (6 bad inputs), non-scan-list silent, list-of-blocks extraction, dict extraction, role-spoofing, data-exfil.
