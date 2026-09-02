# Search + deep-research tooling — gem-hunt decision queue (2026-09-02)

**Status: GRILL IN PROGRESS — discovery + decide, NOT a build.** This doc is the
audit trail for an extensive grill over the 14-lens gem-hunt into better search /
research tools + upgrades for the estate's search stack. Nothing here is adopted
until the owner steers it (one question at a time, below). A grill is not a build.

**Grill modes:** prioritization + scope-change + red-team (dual-use onion lane).

**Grounding (honest):** run from a Cloud Agent VM that CANNOT reach basic-memory
(`127.0.0.1:8765`) or the event-ledger (both on the Windows box). Grounded instead
in `docs/plans/2026-09-02-search-stack-reunion.md` (the built stack) + the in-context
lens reports. This committed doc is the ledger substitute; fold into basic-memory /
`note.py` on the box later.

**Lenses:** 14 dispatched; at time of writing 10 reported, 4 running (self-hosted
backends, research-reliability techniques, academic upgrades, native-capability
audit). Findings from the pending 4 will be folded into the relevant questions as
they land.

**Anti-overfit anchor (gates every adopt):** ride the existing hook/skill/MCP bus;
prefer ENABLE-native > BORROW-technique > new in-process adapter (0 RAM) > new
stdio child > new daemon. No 2nd orchestration runtime, vector-DB daemon, LiteLLM,
LangGraph, or Cursor BYOK. Keyless/low-RAM beats keyed/heavy on a 31.6 GB
commit-starved box.

---

## Candidate inventory (from the lenses; confidence + my recommendation)

### A. Zero-RAM / keyless quick wins (ride the existing bus)
- **SearXNG engine flips (metasearch lens):** turn OFF `google` (keyless Google
  scraping is dead — Whoogle EOL 2026-07-24, searxng#6359; the estate config still
  force-enables it), turn ON the dormant independent indexes `mwmbl` (keyless, live
  200) and `marginalia` (`public` key, rate-limited). +0 MB, +2 uncorrelated
  rankers for RRF. **Rec: DO (T0).** Confidence high.
- **Snippet-carry into RRF (reranking lens):** `FusedResult` carries no snippet
  today, so no reranker can run. Extend `extract_results` to keep
  snippet/description. Pure stdlib, prerequisite for any rerank. **Rec: DO (T0).**
- **Host-diversity cap + near-dup demotion (reranking lens):** ≤2 results/host +
  Jaccard demotion, stdlib, 0 MB. **Rec: DO (T0).**
- **Cloudflare `Accept: text/markdown` (extraction lens):** one request header;
  when a zone supports it, skip extraction entirely. 0 RAM. **Rec: DO (T0).**

### B. New keyless MCPs / adapters (mostly ~0 RAM)
- **Parallel Search MCP (remote, keyless)** `search.parallel.ai/mcp` — independent
  index, 0 local RAM, top-tier in a cited agentic benchmark. **Rec: ADOPT** (probed
  lattice). Confidence high (live probe).
- **grep.app MCP (remote, keyless)** `mcp.grep.app` — cross-repo *code* search, a
  real gap. **Rec: ADOPT.**
- **Wikipedia / Wayback / Hacker News (in-process adapters, keyless, 0 MB):**
  grounding, dead-link recovery, dev-sentiment. **Rec: ADOPT Wikipedia + Wayback;
  HN optional.**
- **`corroborate-mcp` (keyless, Node child):** counts independent origins of a
  claim. Novel but 1★ single-maintainer. **Rec: TRIAL behind a fail-closed flag.**
- **`open-webSearch` MCP (keyless, stdio, 0 MB idle):** independent scraper
  codebase as a SearXNG-parser-breakage fallback (resilience, not new coverage).
  **Rec: ADOPT-lite / defer.**

### C. Reranking + extraction quality
- **ONNX MiniLM cross-encoder rerank (reranking lens):** ~23 MB int8 model via
  FlashRank/fastembed/bare onnxruntime, lazy-loaded, optional stage after RRF over
  top ~30 with snippets. **Rec: ADOPT gated behind a 30-50 query eval** (do not ship
  blind). Confidence high on tooling, medium on lift for SERP snippets.
- **`read_url` extractor MCP over trafilatura/rs-trafilatura (extraction lens):**
  the stack has no readability-pass fetch tool (`web_url_read` doesn't remove
  boilerplate). rs-trafilatura is +6 F1 but needs a Rust/WSL build; plain
  trafilatura is already best-in-class CPU. **Rec: BUILD a small `read_url` over
  trafilatura; rs-trafilatura optional later.**

### D. Repo-discovery (OSSInsight rankings are upstream-dead since ~2025-10)
- **GitHub REST search + `stats/*` (repo lens):** keyless, first-party, fresh
  stars; `created:>…&sort=stars` = the "new & hot" ranking OSSInsight lost.
  **Rec: ADOPT (T0 sibling tools on the OSSInsight adapter).**
- **bestofjs static API v2 + best-of-python CSV + ecosyste.ms + deps.dev/Scorecard
  (repo lens):** keyless, event-independent trend/health signals; deps.dev+Scorecard
  doubles as an adopt-safety gate. **Rec: ADOPT bestofjs v2 + deps.dev; others
  optional.**
- **github.com/trending HTML parse:** guarded, low-volume, ToS-sensitive. **Rec:
  optional.**

### E. Answer engines / deep-research (LLM-dependent → on-demand or OVH)
- **Vane (ex-Perplexica, MIT) as a `search-hub` adapter; local-deep-research
  (`ldr-mcp`, MIT):** keyless *local-LLM* cited-answer path independent of the
  Perplexity cookie. But the LLM is 4-6 GB resident — infeasible on the box.
  **Rec: DEFER to OVH / on-demand; BORROW their techniques now.**
- **Harness technique-borrows (deep-research-frameworks + reranking lenses):**
  budget + "beast mode" forced-finish (Jina), evolving-report state (Tongyi/TTD-DR),
  snippet windows + Wayback fallback (smolagents), STORM perspective sub-questions,
  learnings-recursion (dzhng), think/compression/hard-limit contracts (LangChain
  ODR), academic-SearXNG route (LDR). All zero-RAM prose/stdlib. **Rec: ADOPT the
  budget + evolving-report + academic-route trio first (they attack the measured
  42% partial-run failure).**

### F. Keyed search APIs (cost; only if you want them)
- **Brave Search API** (independent index, $5/1k, $5/mo credit) — the biggest
  index-diversity gain, but keyed + card. **Marginalia** (free non-commercial).
  **Kagi Enrich** ($2/1k small-web). **Linkup** ($20/mo recurring free). **Rec:
  Brave first IF you accept a keyed lane; Marginalia keyless via SearXNG covers most
  of it for free.**

### G. Dark-web second engine (RED-TEAM / legal — explicit owner call)
- **VormWeb** as a 2nd clearnet `onion index` engine + **hub-side Ahmia MD5
  blacklist** (dark-web lens). Envelope-compatible (clearnet, index-only) but needs
  operator consent + a new decision record. **Rec: DEFER; only the Ahmia blacklist
  guard is a clear yes.**

### H. Estate ops (arguably out of search-hub scope)
- **basic-memory embedder → Ollama canary + `ugrep`/`rga` for PDF search (local-RAG
  lens):** basic-memory already IS the local RAG stack; only real gains. **Rec:
  hand to the estate-ops lane, not this branch.**

---

## Decision queue (one at a time; my recommendation on each)

- **G-1 — Ambition tier** (foundation).
- **G-2 — Anti-overfit strictness** (foundation).
- **G-3 — SearXNG engine flips (kill dead Google, enable mwmbl/marginalia)?**
- **G-4 — Snippet-carry + host-cap + Cloudflare-markdown T0 bundle?**
- **G-5 — Parallel + grep.app remote keyless MCPs?**
- **G-6 — Wikipedia / Wayback / HN in-process adapters (which)?**
- **G-7 — ONNX reranker stage (gated behind eval) yes/no?**
- **G-8 — `read_url` readability extractor (trafilatura; rs-trafilatura later)?**
- **G-9 — Repo-discovery fix: GitHub REST search + bestofjs v2 + deps.dev?**
- **G-10 — Harness technique-borrows: which of the trio (budget / evolving-report /
  academic-route) + others?**
- **G-11 — Keyed search APIs (Brave? Marginalia? none)?**
- **G-12 — Answer engines (Vane/LDR): defer-to-OVH vs on-demand-local vs skip?**
- **G-13 — Dark-web 2nd engine (VormWeb) + Ahmia MD5 blacklist guard?** (red-team)
- **G-14 — corroborate-mcp + open-webSearch resilience lanes?**
- **G-15 — Estate-ops items (basic-memory→Ollama, ugrep) — in scope or hand off?**
- **G-16 — Delivery: how should the chosen items ship (this branch vs new branch;
  build now vs decision-record only)?**
- (Pending-lens questions will be inserted: academic upgrades, native-capability
  ENABLE list, self-hosted-backend re-eval, and any research-reliability additions.)

---

## Decisions log (filled as answered)

- **G-1 — Ambition tier: A+B+C (full program).** Owner wants all three tiers
  pursued, sequenced (A first, then B, then C behind per-item gates). Consequence:
  the grill now scopes the whole program; C items (local-LLM answer engines, keyed
  APIs, dark-web 2nd engine, OVH) are IN, each gated on its own question.
- **G-2 — Posture: Balanced + Loose.** Balanced defaults (keyless/in-process/remote
  freely on-box; OVH/on-demand for heavy) BUT on-box residency for heavy/LLM tools
  is PERMITTED when the owner opts in, mitigated by on-demand spawn + eviction
  (`OLLAMA_KEEP_ALIVE=0`). Keyed APIs allowed with a hard spend cap + secrets by
  env-name only. Our own code still avoids LangGraph/LiteLLM/vector-DB/2nd
  orchestrator; a vendored tool MAY use them internally (even on-box).   Accepted
  risk: a resident local model pressures the 1.2-1.8 GB-free box; opt-in per item.
- **G-3 — Grill shape: Focus.** A+B are approved-to-build per the doc's per-item
  recommendations (owner may veto any before build); remaining questions target the
  C-tier gates, delivery, and the 4 pending-lens picks. Cloud agent cannot poll
  running subagents; their questions get injected on completion.
- **G-4 — OVH: defer + build endpoint-agnostic.** Heavy adapters take their base URL
  from an env var (like `TRAILSEARCH_URL`): on-box on-demand now, one-line repoint to
  OVH later, no rework. OVH standup = documented owner follow-up (cloud agent cannot
  provision it).
- **G-5 — Answer engines: build BOTH fully now (on-demand) + expand Perplexity.**
  Vane as a `search-hub` adapter (`selfhosted_answer`, `VANE_URL`, flag OFF by
  default → 0 RAM idle, usable once an LLM is pointed at it); LDR MCP registered but
  ON-DEMAND (resident is 8-16 GB — "enabled" = wired/callable, a GPU/OVH item, not
  always-on); borrow both technique-sets (LDR academic-SearXNG route + cheap→escalate
  gating; Vane provider-dir pattern). SPAWNED DIRECTION (G-5b): make
  `pplx_deep_research` work + expand — buildable: deeper harness routing to
  `pplx_deep_research`/`pplx_council` + expanded surface; OWNER-ACTION: refresh the
  Perplexity session cookie in `.agents/local.json` (cloud agent cannot).
