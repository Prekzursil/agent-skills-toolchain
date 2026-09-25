# Grill — SOTA coverage workflow (2026-09-20)

Modes: expansion + scope-change + better-ideas + red-team + simplification.
Not a build. One question at a time.

## Scout (already known, not asked)

- Constraint compiler v1 is at `C:\Users\Prekzursil\.agents\prompts\constraint-compiler_2026-09-20.md`.
- Load-bearing findings already in hand: positive polarity > negation; hard vs soft (U-Define); primacy/recency (Purpura MOSAIC); hierarchy system>developer>user>tool is trained but leaky (Wallace 2024, Control Illusion, IH-Challenge, HIPO, NVIDIA 2606.07808); ~5 concurrent constraints not 15; "pass the filter / strip bans" is a detected jailbreak signature.
- Feasibility lens (this session): ~1.25 GB free of 31.6 GB. Estate rule: no multi-agent fleet under 8 GB free. Deep-research skill's own finish line is 3–5 questions and 15–30 sources, and it records 42% success over 90 uses. GitHub search caps and `incomplete_results`. Exa search is top-k (≤100), not a literature index.
- Better-ideas lens recommends: encode axioms, fetch only contradictions. A full scrape collapses context (ACE, arXiv 2510.04618) and never emits a prompt.

## Decision queue

### Framing
- **G-1** What is this program for? (compiler vs survey vs both)
- **G-2** What does "100%" mean if the field is unbounded?

### Scope
- **G-3** Date window and inclusion rule for the corpus
- **G-4** In: instruction hierarchy, polarity, position, hard/soft, agent prompt anatomy. Out: jailbreak ASR leaderboards, marketing prompt lists, pre-2024 CoT notes?
- **G-5** GitHub: repos only, or also code search?

### Effort
- **G-6** Agent budget given RAM (0 children now vs 2 after reap vs full fan-out)
- **G-7** Provider split: Exa=papers, Tavily/Firecrawl=pages, GitHub=repos. No triple-query.

### Safety
- **G-8** Is the deliverable a compiler that preserves authorization, or a filter-evasion rewriter? (explicit call)

### Process
- **G-9** Completeness falsifier: frozen 12-title gold list, missing = incomplete
- **G-10** Where the synthesis file lives and who may edit the compiler

## Resolved

- **G-1 = C (2026-09-20).** Both, survey first. A frozen bibliography blocks the compiler until the survey exists. Owner added: the survey must use live skills and MCP tools (Firecrawl, Exa, Tavily, and the research skills), not model memory alone.
- **Added constraint (not a G-item):** do not launch the crawl until a one-call preflight shows those MCP tools answering. A handshake failure is a stop, not a silent fallback to memory.
- **G-2 = A (2026-09-20).** Open crawl until a provider returns no new titles. Not a frozen cap.
- **G-3 = A (2026-09-20).** No date floor. Maximum recall. Owner accepted that this crawl does not have a natural end from time alone. Topic filter (G-4) is now the only bound.
- **G-4 = A (2026-09-20).** No topic filter. Owner accepted the crawl is not bounded by subject. Provider exhaustion and the later process questions (GitHub shape, agent budget, safety) are the remaining stops.
- **G-5 = A (2026-09-20).** GitHub code search, every matching file. Not repository-only and not README-only. Owner accepted this will not finish on this box if run as a fleet.
- **Preflight cleared (2026-09-20).** Exa, Tavily, Firecrawl (hosted API), and search-hub answer live calls. Standalone paper-search MCP is absent; papers go through Firecrawl and search-hub.
