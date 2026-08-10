---
name: firecrawl
description: Web scraping, crawling, structured extraction, site mapping, and change monitoring via the Firecrawl MCP. Use to turn known or discovered URLs into clean markdown or schema-structured JSON, screenshot pages or extract brand identity (colors, fonts, spacing, components), crawl or map entire sites, harvest docs and cookbooks, run competitive or design research, pull structured data with a schema, parse local PDFs and Office files, search the web with operators and domain filters, monitor pages for meaningful changes, search arXiv and GitHub, or drive an autonomous browse agent. Pairs with the Exa MCP (`web_search_exa`) — Exa finds by meaning, Firecrawl fetches, extracts, crawls, and monitors.
metadata:
  origin: custom
---

# Firecrawl

The web-data layer: scrape, crawl, map, structured-extract, search, monitor, and autonomously browse the web via the Firecrawl MCP server (`mcp__firecrawl__firecrawl_*`). Where Exa *finds* pages by meaning, Firecrawl *fetches and structures* them — turning any URL (or a whole site) into clean markdown, schema-typed JSON, screenshots, or brand tokens.

## When to Activate

- Scrape a known page into clean markdown, or pull specific data points as JSON
- Crawl or map a whole site (docs, blog, competitor) for comprehensive coverage
- Harvest documentation/cookbooks (like building this skill) into readable text
- Extract structured data (prices, specs, features, contacts) across many URLs
- Capture screenshots or **brand identity** (colors, fonts, spacing, UI components) for design research
- Search the web with operators/domain filters and get full page content, not just snippets
- Monitor a page or a search for meaningful changes over time
- Find academic papers (arXiv) or GitHub issues/PRs for research
- Parse a local PDF / Word / Excel file into markdown or structured JSON
- User says "scrape", "crawl", "extract from", "map the site", "monitor", or "get the data from this page"

## Firecrawl vs Exa — when to use which

The user has **both**. They are complementary, not redundant:

| Job | Reach for | Why |
|-----|-----------|-----|
| Discover pages by meaning, "find sites like X", semantic recall | **Exa** (`web_search_exa`) | Neural/embedding search; best when you don't know the URL |

### MCP Requirement
### Tool Routing (decision table)
### Core Tools
### firecrawl_scrape
### firecrawl_crawl
### firecrawl_map
### firecrawl_extract
### firecrawl_search
### firecrawl_agent / firecrawl_agent_status
### firecrawl_research_* (paper / GitHub index)
### firecrawl_parse
