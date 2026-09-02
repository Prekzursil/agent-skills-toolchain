---
name: jina-reader
description: >
  Zero-RAM, server-less way to fetch a single web page as clean, LLM-ready markdown via a one-line
  HTTP GET to Jina Reader (r.jina.ai plus the target URL) — no MCP, no resident process. Use as the
  cheapest first hop for a simple or mostly-static page (article, doc, blog, README, changelog) when
  you just need its readable text and do not need crawling, JS rendering, screenshots, or schema
  extraction. Escalate to the Firecrawl MCP for JS-heavy or dynamic pages, crawling, or structured
  extraction; use the exa MCP web_fetch for batch URL reads. NEVER hardcode the Jina API key.
---

# Jina Reader (zero-RAM page fetch)

Fetch one URL as clean markdown with a single HTTP GET — no MCP server, no subprocess, no RAM
footprint. This is the leanest fetch in the stack; reach for it before waking a heavier tool.

## When to use

- A **simple / mostly-static** page: article, blog post, docs page, README, changelog, release notes.
- You need the **readable text/markdown**, not screenshots, brand extraction, crawling, or a schema.
- You want to avoid spawning a resident MCP process (RAM-conscious sessions).

Prefer a heavier tool when: the page is JS-heavy / renders client-side, you need to **crawl** or
**map** a site, you need **structured/schema extraction** or **screenshots** (use `firecrawl`), or
you want to **batch** many URLs in one call (use the `exa` MCP `web_fetch_exa`).

## How (HTTP GET — pick your client)

Prefix the target URL with `https://r.jina.ai/`:

```bash
# Bash / curl
curl -sS "https://r.jina.ai/https://example.com/some/article"
```

You can also use the `WebFetch` tool against `https://r.jina.ai/<TARGET_URL>` — same idea, no shell.

### Optional headers

- `Authorization: Bearer $JINA_API_KEY` — higher rate limits + the free 10M-token allowance. Read the
  key from the environment; **never hardcode or print it**. Skip the header entirely for anonymous use.
- `X-Return-Format: markdown` (default) — also `text`, `html`.
- `X-Target-Selector: <css>` / `X-Remove-Selector: <css>` — keep/drop parts of the DOM.
- `X-With-Links-Summary: true` — append a consolidated list of the page's links.

### Authenticated (key from env — never inline the literal)
### Fallback chain
### Guardrails
