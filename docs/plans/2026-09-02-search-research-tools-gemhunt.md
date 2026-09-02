# Search + deep-research tooling — gem-hunt decision queue (2026-09-02)

**Status: WAVE 1 BUILT on this branch (2026-09-02) — all six items landed in three
gated commits (`64762079` onion lane + VormWeb default-ON, `7bdd57cc` search-expansion,
`ecfcc9aa` GitHub REST + `read_url`); Waves 2-4 are specified below and wait for their
own branches (G-8 C). Owner follow-ups are listed under "Wave 1 — status".** This doc
is the audit trail for an extensive grill
over the 14-lens gem-hunt into better search / research tools + upgrades for the
estate's search stack, and — per G-8 (A) — the program SSOT: every wave is specified
in the wave map below before it builds. Numbering: the **Decisions log** (G-1…) is
authoritative; the older queue below kept its original numbers and several of its
items were answered in batches (G-3 approved the A+B items per their per-item recs).

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
  `pplx_deep_research`/`pplx_council` + expanded surface;   OWNER-ACTION: refresh the
  Perplexity session cookie in `.agents/local.json` (cloud agent cannot).
- **G-6 — Keyed search APIs: ALL researched lanes.** Build adapters for Brave, Kagi
  (Enrich + Search), Linkup, Marginalia-commercial, Mojeek, You.com, Perplexity
  Search API, and the SERP scrapers (Serper/SerpApi/DataForSEO/ZenSerp/ScrapingBee)
  — all behind a shared keyed-adapter base, DEFAULT-OFF, secrets by env-name only.
  Caveats recorded: SERP scrapers carry the Google-v-SerpApi legal shadow (noted in
  each adapter's description) + add no index SearXNG lacks; large surface → phasing
  decided at the delivery question. Nothing bills until the owner adds a key.
- **G-7 — Dark-web 2nd engine: VormWeb ONLY, default-ON; skip Ahmia MD5 blacklist.**
  Wire VormWeb as a second clearnet `onion index` source (HTML/xpath or HTTP
  scrape of vormweb.de search), DEFAULT-ON, behind the same ask-before-search
  gate + result tagging as the Ahmia lane. Do NOT build the hub-side Ahmia MD5
  blacklist guard. Caveats carried (owner-accepted): (1) operator consent is
  unresolved — cloud agent cannot email VormWeb; ship with the consent gap
  documented in the adapter description + envelope, not silent; (2) filtering is
  VormWeb's self-declared policy only (unverifiable) — no independent hub-side
  CSAM screen. Envelope FORBIDDEN list (no Tor, no .onion fetch) still holds.
- **G-8 — Delivery: A+B+C+D (all four, reconciled).** Owner picked every option;
  read together they are consistent: **(A)** this doc + the reunion decision record
  are the program SSOT — each wave is specified in the wave map below before it
  builds, and the grill's outcome is frozen here rather than in chat. **(B)** the
  build starts now, phased — no further approval round for the program as a whole.
  **(D)** Wave 1 = the A-tier quick wins + VormWeb (default-ON, G-7) on THIS branch
  (`cursor/search-stack-reunion-self-hosted-9cde`); nothing from later waves lands
  here, so this branch stays reviewable. **(C)** Waves 2+ each get their own branch
  spun from this one (or from `main` once it merges); asking for a wave branch IS
  the trigger — scope is already approved, only the manifest gets a per-item veto.
  Cloud-agent constraint: this run stays on its assigned branch, so wave branches
  are opened in later runs (or on explicit instruction in this one).
- **G-9 — Wave 1 manifest: ALL SIX, built by subagents; lens check first.** Owner:
  "everything (subagents for full implementation) but first check for the rest of
  10/14 remaining agents". Check done 2026-09-02 (see "Pending-lens returns"): all four
  had finished; three reports recovered and folded in — none alters a Wave-1 item;
  Lens 1 had stopped without a report and was restarted (resumed) on the owner's
  instruction. Wave 1 then launched as three parallel implementation subagents with
  disjoint file ownership, no commits of their own (the parent gates + commits per
  slice): `bc-ddbc064d-0084-56b3-8af5-44247343b850` = items 1a+2+3
  (`tools/search-expansion/`), `bc-4e8853ae-4128-53a1-b8eb-451d38f2ea1c` = items 1b+5
  (search-hub onion lane, `deploy/`, envelope), `bc-a327747f-31b0-5716-b401-b379cf0e2488`
  = items 4+6 (search-hub adapters: `read_url` v0 + GitHub REST siblings).
- **G-10 — Waves 2-4 now, e2e, on this branch; PRs handled in parallel.** Owner
  (2026-09-02 06:53 UTC): "implement all waves, e2e (everything 100% working and
  wired) with subagents as we did, and while they do that handle the PRs and the ones
  eligible merge to main". Amends G-8 (C): the remaining waves build on THIS branch
  with the same disjoint-ownership subagent model rather than one branch per wave.
  Wiring contract added first (`d6c6fff3`): `tools/mcp/search-hub/lanes.py` registers
  `lane_<name>.py` modules exposing `build(environ)` and fails closed per lane. Nine
  builders launched 07:03 UTC: providers/child MCPs `bc-0d226ced-e4d9-5247-a030-aadc4770b5a5`
  (Parallel, grep.app, corroborate, open-webSearch, LDR, Exa cleanup, environ-aware
  provider list); grounding lane `bc-da5fe256-ecb4-5c8d-9e4e-16439adf5065` (Wikipedia,
  Wayback, HN); repo-health lane `bc-ac8a7fd8-061a-56ee-9af9-bc2b4cfcd19c` (bestofjs v2,
  deps.dev, Scorecard); `read_url` trafilatura ladder + DNS pinning
  `bc-20f2eebe-a9cd-52c2-a74f-74c4d3ffb2e9`; rerank stage + eval
  `bc-caf3d57a-0263-5969-9e9b-0a02e1ee25e4`; deep-research harness reliability set +
  academic route + pplx routing `bc-28fe5bab-7eef-5741-928a-3cdafd6f44a7`; academic
  upgrades (scholarly-access keys/tools, README drift, MCP registrations)
  `bc-ab35b6b5-a647-57d1-b68e-dbd519b8964a`; Vane answer lane + on-demand deploy
  `bc-00254568-1e1f-5c3a-9ca4-14f42d91c515`; keyed search APIs `bc-c94a07ec-46e4-5d05-97cd-ba17ad4bd83f`.
  Then: parent wires each lane into `LANE_MODULES`, adds `--cov=rerank` to the CI gate,
  runs the e2e pass, updates PR #310. PR handling so far: #308 merged to main
  (`acb04057`, all required checks green); #310 (this branch) had one CI failure fixed
  in `5ac13629` (Python 3.11 `HTMLParser._pending` collision); #311/#314 fail the
  pre-#313 full-history gitleaks scan and need `main` merged in (#314 also fails
  `gate-published-commands`); #312 needs `ruff format` on one test file — those three
  are other branches, so their fixes wait for the owner's explicit go-ahead.

---

## Program plan — wave map (G-8; per-item veto at G-9, then build)

Sequencing rule: cheapest + already-decided first; anything needing a key, an LLM,
or a new daemon last. Every wave: tests-first with fakes, `ruff` + search-hub
`pytest` green, commit + push per step, no PR/merge/force-push from the agent,
secrets only by env-name.

### Wave 1 — THIS branch (`cursor/search-stack-reunion-self-hosted-9cde`)
1. **SearXNG engine flips** in `tools/mcp/search-hub/deploy/searxng-min/settings.yml`:
   `google` OFF (keyless Google scraping is dead), `mwmbl` + `marginalia` ON. The
   estate's live SearXNG config is on the Windows box — ship the same diff as a
   documented owner follow-up.
2. **Snippet-carry** into `FusedResult` / `extract_results` (prerequisite for any
   rerank; stdlib).
3. **Host-diversity cap** (≤2 results/host) + Jaccard near-dup demotion in the RRF
   stage (stdlib, 0 MB).
4. **Cloudflare `Accept: text/markdown`** request header on the fetch path; use the
   markdown body when a zone returns it, else fall through unchanged.
5. **VormWeb, DEFAULT-ON** (G-7): second clearnet `onion index` source, as a
   SearXNG `xpath` engine in `settings.yml` (config beats adapter) + `vormweb` added
   to the onion lane's default engine list in `onions.py`. Same ask-before-search
   gate + TOR/DARK-WEB INDEX tagging as Ahmia; `ENABLE_VORMWEB=0` kill switch;
   consent gap + self-declared-filtering caveat written into the tool description
   and `docs/legal/onions-lane-envelope.md`. No Ahmia MD5 blacklist.
   *Probe receipt (2026-09-02, cloud VM):* `GET https://vormweb.de/en/search?q=…`
   → HTTP 200 in ~0.5 s, 41 hits for "privacy"; one `div.query-box` per result with
   `a#urllink` (title + `.onion` href), `li > i` (description), gray `p` (URL), and a
   "Verified" badge on curated entries. Upstream SearXNG ships `ahmia` + `torch`
   only — no `vormweb` engine — so the xpath definition is ours to carry.
6. **GitHub REST search siblings** on the OSSInsight adapter (`created:>…&sort=stars`
   = the "new & hot" ranking OSSInsight lost). Keyless, in-process, T0.

#### Wave 1 — status (2026-09-02): BUILT, gated, pushed

| # | Item | Landed in | Gate evidence |
|---|------|-----------|---------------|
| 1a | Flips rendered into the owner's managed block (`searxng_config.py`, `--probe` extended) | `7bdd57cc` | 191 tests, 100% line+branch, mutation 53/53 + 24/24 + 8/8 |
| 1b | Flips mirrored in `deploy/searxng-min/settings.yml` + text-level guard test | `64762079` | `tests/test_deploy_settings.py` (11) |
| 2 | `FusedResult.snippet` carried through RRF (500-char cap, best-rank provider) | `7bdd57cc` | `test_rank_fusion.py` snippet block |
| 3 | `diversify()` opt-in: <=2/host + Jaccard > 0.8 demotion, re-order only; multilingual-search snippet opted in | `7bdd57cc` + wrap-up | boundary tests (0.8 kept, > 0.8 demoted) |
| 4 | `read_url` v0: Cloudflare `Accept: text/markdown` negotiation, stdlib fallback labelled `quality: low`, `.onion`/private-address refusal | `ecfcc9aa` | `tests/test_read_url.py` (47 cases) |
| 5 | VormWeb DEFAULT-ON as SearXNG `xpath` engine, `ENABLE_VORMWEB=0`, same gate + tagging, envelope caveats | `64762079` | `tests/test_onions.py` (+15) |
| 6 | `GitHubSearchAdapter` (5 tools, default ON, rate-limit relay, token by env-name) | `ecfcc9aa` | `tests/test_github_search.py` (59 cases) |

search-hub suite 99 -> 233 passing; search-expansion 105 -> 191 at 100% coverage; ruff
0.15.17 clean on both. Concurrency note for the record: the three builders shared one
working tree with disjoint file ownership and no commits of their own; each slice was
gated against the others' in-progress files excluded, then committed alone.

**Owner follow-ups (cannot be done from the cloud VM):**
1. Restart the estate SearXNG (engine stanzas load only on restart), then run one
   `engines=vormweb` query and tick the envelope sign-off checkbox.
2. `python tools/search-expansion/searxng_regional.py --dry-run` -> `--apply` -> `--probe`
   on the box; expect `marginalia` to 429 truthfully until a personal key replaces
   `public` (untracked overlay, never committed).
3. Optional live probes: `read_url` against a Cloudflare doc page (expect
   `extractor: cloudflare-markdown`), `search_usage {"provider":"github","probe":true}`.
4. Not built by design (G-7): no hub-side Ahmia MD5 blacklist. Not verified from here:
   a live SearXNG loading the VormWeb xpath stanza; live GitHub rate-limit headers.

### Wave 2 — new branch: keyless adapters + extraction + harness trio
- Parallel Search MCP + grep.app MCP (remote, keyless; probed lattice).
- Wikipedia + Wayback in-process adapters (HN optional).
- `read_url` readability tool over trafilatura (rs-trafilatura optional later).
- ONNX MiniLM rerank stage, gated behind a 30-50 query eval; ships only if it lifts.
- bestofjs v2 + deps.dev/Scorecard repo-health adapters.
- Harness borrows: budget/"beast mode" forced finish, evolving-report state,
  academic-SearXNG route (the trio); the rest as prose in the deep-research skill.
- corroborate-mcp TRIAL behind a fail-closed flag; open-webSearch adopt-lite.

### Wave 3 — new branch: answer engines (on-demand, endpoint-agnostic; G-4/G-5)
- Vane adapter (`selfhosted_answer`, `VANE_URL`, OFF by default → 0 RAM idle).
- LDR MCP registered on-demand (`LDR_URL`); residency is a GPU/OVH item.
- `pplx_deep_research` / `pplx_council` routing + surface expansion (G-5b).
  OWNER-ACTION: refresh the Perplexity cookie in `.agents/local.json`.

### Wave 4 — new branch: keyed search APIs (DEFAULT-OFF, env-name secrets; G-6)
- Shared keyed-adapter base + spend cap.
- Brave first; then Kagi (Enrich + Search), Linkup, Mojeek, You.com, Perplexity
  Search API, Marginalia-commercial; SERP scrapers last (legal shadow in each
  description).

### Not a wave — hand-offs / owner actions
- OVH standup (G-4): owner follow-up; adapters are already endpoint-agnostic.
- Estate-ops items (basic-memory → Ollama canary, ugrep/rga PDF search): estate-ops
  lane, not this program (confirm at G-10).
- Pending lenses (academic upgrades, native-capability ENABLE list, self-hosted
  backend re-eval, research-reliability): folded into Wave 2/3 scope when they land.

---

## Pending-lens returns (recovered 2026-09-02)

All four "pending" lenses had in fact finished; their completion notifications never
reached this run. Three reports were recovered verbatim from the subagent transcripts
and archived, body unedited, under `gemhunt-lenses/`:

- [Lens 12](gemhunt-lenses/lens-12-research-reliability-techniques.md) - research
  reliability techniques (agent bc-68ba5a88-fc1f-5081-b011-77d6864d4a5f).
- [Lens 13](gemhunt-lenses/lens-13-academic-search-upgrades.md) - academic search
  upgrades (agent bc-1c26835a-bf96-5c49-afdf-541a37602cf9).
- [Lens 14](gemhunt-lenses/lens-14-native-capability-monitoring-audit.md) -
  native-capability + monitoring audit (agent bc-148e974b-f9f3-5b2d-b578-09f8bc6cfd47).

Lens 1 (self-hosted search backends, agent bc-1c484032-11cf-5a6e-8c82-a2e6c19cd3a0) had
stopped after ~21 min / 84 tool calls without a final report; it was resumed on the
owner's instruction and delivered at 05:33 UTC — archived as
[Lens 1](gemhunt-lenses/lens-01-self-hosted-search-backends.md), digest below. The
digests keep each lens's own evidence
(numbers, IDs and licenses are the lens's, not re-verified here); the wave-map table is
the proposal, still subject to the per-item veto at G-9.

### Lens 12 - research reliability techniques

Verdict: BORROW-technique; all twelve items are stdlib, 0 RAM. Dedup against
`deep-research/references/research_harness/`: routing, cache, RRF, grading, claim
audit, renderer exist; missing: per-run state on disk, budget object, partial status,
`contradicted` verdict, volatility-aware TTL, dependency order, loop guard. Ranked by
lift on the measured 42% partial-run failure x diff size; build 2 -> 3 -> 1, then
5 + 4, then 6, 9, 8, then 7, 10-12.

1. Run ledger + resume-from-checkpoint: `checkpoint.py`, append-only JSONL keyed by
   plan hash, fail closed on corrupt lines (FS-Researcher arXiv:2602.01566, ACL 2026;
   Anthropic multi-agent research write-up; ReSum arXiv:2509.13313).
2. Terminal-state taxonomy: `Report.status` + `open_subquestions`; always render a
   partial report with an "Unanswered sub-questions" section; count `partial:*` apart
   from `failed` (Context Rot arXiv:2606.29718, 2026 preprint; Deep Research Bench
   arXiv:2506.06287).
3. Budget tracker, regimes explore <60% / converge 60-85% / finalize >85% (render
   `partial:budget`). BATS arXiv:2511.17006, s1 arXiv:2501.19393; BAGEN (2026):
   early stop saves 28-64% tokens on failing runs at a 1.6-4.2 pp success cost.
4. Keep the last 3 tool outputs raw, digest older (~32k-token trigger; ReSum
   +4.5-8.2%). 5. Loop guard on `query_hash` (token-Jaccard >= 0.8), ~20 lines.
6. Sufficiency gate per sub-question (>= 2 sources graded >= B, corroboration >= 1)
   + one bounded follow-up (CRAG; Sufficient Context +2-10%).
7. Report-as-state (WebResearcher, TTD-DR) = the trio's "evolving report" as loop
   state. 8. Sub-question DAG + effort classes fact/compare/deep = 3/8/15 calls
   (`graphlib`). 9. `contradicted` verdict + "Disputed" callout (Astute RAG).
   10. Hedge filter before best-of-2 (+2.6-4.9%, 2026 preprint). 11. CoVe-style
   bounded re-check of numeric/date claims. 12. Volatility axis on `ttl_for`
   (FreshLLMs).

Demoted: HyDE, step-back, Self-RAG tokens (rubric only), sub-agent context isolation
(a fresh context per sub-question is the RAM failure mode), value-tree / debate / SFT
variants. Caveat: several headline numbers are 2026 preprints; the practices are
2024-25, production-backed.

### Lens 13 - academic search upgrades

Keyless-first; no Sci-Hub anywhere. Dedup: `scholarly-access` already wraps Crossref,
OpenAlex, Unpaywall, Europe PMC, arXiv, S2, CORE, DOAJ, PubMed, Zenodo;
`paper-search-mcp` (57 tools, KEEP) searches the same sources. Gap-fillers:

- F4 OpenAlex via `cyanheads/openalex-mcp-server` (Apache-2.0, budget-aware; hosted
  `https://openalex.caseyjhand.com/mcp` or `npx`). OpenAlex now REQUIRES a free key
  ($1/day budget = ~10k list/filter + 1k search + 100 PDF/XML downloads;
  `search.semantic` $0.01/call). `scholarly-access` still runs anonymous via
  `mailto`: threading `OPENALEX_API_KEY` is "the single cheapest upgrade". ADOPT.
- F5 Semantic Scholar via the first-party Ai2 Asta MCP
  (`https://asta-tools.allen.ai/mcp/v1`, `x-api-key`): 225M+ papers, snippet search
  over 12M+ full texts; keyed 1 req/s; keys pruned after ~60 idle days (the recorded
  403). Data ODC-BY-1.0. ADOPT.
- F3 `blazickjp/arxiv-mcp-server` (Apache-2.0, 3.1k stars, active): keyless, 19
  tools incl. bounded LaTeX section reads; arXiv ToU 1 req / 3 s, one connection.
  ADOPT.
- F1 OpenCitations REST (keyless, CC0, 180 req/min): third independent citation leg
  + self-citation flags for `citation-mapping`; REST helper (no MCP exists). ADOPT.
- F2 Europe PMC `fullTextXML` + Annotations API (keyless, ~1-2 req/s): extend the
  existing client; skip the two zero-star MCPs. ADOPT-lite.
- F6 PaperQA2 (`Future-House/paper-qa`, Apache-2.0, 9.1k stars): the only mature
  cited multi-PDF QA; needs LLM tokens + an embedding provider, uses LiteLLM inside
  (allowed for a vendored tool under G-2); run as a CLI/skill step over
  institutional/OA PDFs. ADOPT-conditional.
- F7 CORE v3: config-only (`CORE_API_KEY`, 150 req / 15 min); SKIP as a tool.

Skips: Unpaywall (subsumed by OpenAlex `best_oa_location`), Crossref (already
primary), PapersWithCode (dead July 2025), JackKuo666 PubMed/bioRxiv MCPs (stale),
`oksure/openalex-research-mcp` (superseded), "ancatmara" (404).
Hygiene: `tools/scholarly-access-mcp/README.md` still advertises Sci-Hub/LibGen though
the code is clean - fix it; treat every `paper-search-mcp` download tool
(`download_with_fallback(use_scihub=True)`) as off-limits, search/metadata only.
Order: F4 -> F5 -> F3 -> F1 + F2 -> F6 trial -> F7 only if needed.

### Lens 14 - native-capability + monitoring audit

Thesis: the hub already EXPOSES far more than the harness CALLS - Exa via `mcp.exa.ai`
(14 tools), `firecrawl-mcp` (27 tools incl. 8 `firecrawl_monitor_*` and 5
`firecrawl_research_*`), `mcp-searxng` (`searxng_instance_info`). Confirms
cross-provider RRF already exists at `tools/search-expansion/rank_fusion.py`.

ENABLE now (H x L unless noted):
1. Firecrawl Monitors: standing web/page/site queries on a Firecrawl-hosted scheduler
   + AI judge; min 5-min cadence, 30-day retention (max 365), 1-50 targets,
   email/Slack/webhook. Cost: web monitor 2 credits per 10 results per check + 1 per
   judged result; scrape 1 credit/URL/check; `estimatedCreditsPerMonth` returned.
2. SearXNG keyless academic lane: `searxng_web_search(categories="science")` or
   `engines="arxiv,google scholar,pubmed,semantic scholar,openalex,crossref"`; verify
   with `searxng_instance_info`, enable any disabled ones via the managed block in
   `tools/search-expansion/searxng_config.py`; several science engines ignore
   `time_range`.
3. Exa `web_search_advanced_exa`: `maxAgeHours` (livecrawl deprecated), `category`
   (research paper / news / github / pdf), `enableSummary` + `summaryQuery`,
   `subpages`, `additionalQueries`, date filters; MCP `type` is only
   auto|fast|instant.
4. Firecrawl `formats:[{type:"json",schema}]` / `firecrawl_extract`;
   `firecrawl_search` `sources:[{type:"news"}]` + `tbs:"qdr:w"`;
   `firecrawl_search_feedback` refunds 1 credit per search.
5. Firecrawl `research_search_papers` (k <= 500), `inspect_paper`
   (arxiv/pmid/pmcid/doi), `related_papers`, `read_paper`; pricing/coverage
   unverified. M/H x L.
6. Tavily `search_depth=advanced`, `time_range`, `include_raw_content`,
   `exact_match` per call; `topic=news|finance` only via `DEFAULT_PARAMETERS` on a
   second ProviderSpec (MCP enum is `general` only). M x L.
7. Firecrawl `changeTracking` format (git-diff/json, `tag`) on re-scrapes. M x L.
8. Exa `agent_create_run` (`outputSchema`, `effort`, `input.exclusion` +
   `previousRunId` = daemon-free standing query); `deep_researcher_*` is deprecated
   yet still listed in the hub's `_EXA_TOOLS`. ENABLE selectively; credits scale with
   effort.
9. SearXNG `format=rss` (add `rss` to `search.formats`); RSSHub SKIP.

DEFER/SKIP: Exa Websets monitors (NEW MCP + REST; webhooks need a daemon; cron at
most daily); changedetection.io (NEW DAEMON, 180-280 MB core, ~2 GB with Chrome);
Kagi has no monitoring product (Search $12/1k, Extract $4/1k pages; official MCP =
Search + Extract); neither has Tavily.

### Lens 1 - self-hosted search backends (resumed; landed 05:33 UTC)

Bottom line: **nothing found beats TrailSearch for the Tavily slot** (only candidate
with native `/tavily/*` + clean license + trafilatura/crawl4ai-grade extraction) — keep
it `native`. 31 backends scored on (clean license) x (low RAM) x (Tavily/Firecrawl
shape); RAM marked "measured" was run by the lens on Linux.

- **trafilatura-scrape** (github.com/DaRacci/trafilatura_scrape, MIT, `LICENSE` in tree;
  ~30 KB Python, stdlib HTTP server + requests + trafilatura + pypdf): Firecrawl v2 +
  v1 shape (`/v2/scrape|batch/scrape|map|parse|search`, `/v1/scrape|search`), search =
  thin proxy to our SearXNG via `SEARXNG_URL`. **Measured 60 MB idle, 98 MB after 4
  scrapes**; pure-Python wheels = native Windows, no Docker. Caveats: 0 stars, single
  author, not on PyPI (README claim false — install from git), two bugs seen (handler
  thread dies with no HTTP response when SearXNG is unreachable; title mojibake). Verdict
  ADOPT after a 1-day trial as the **fastCRW (AGPL) replacement** in the emulated
  Firecrawl tier.
- **WebSearchFree** (github.com/drmikecrypto/WebSearchFree, MIT): 1 MB static binary,
  native `.exe`; Tavily-shaped unprefixed `/search` + `/extract` (no `/tavily/*`);
  **measured 9.7 MB idle, 18.7 MB after use**, 687 ms search. Extract is plain text;
  6 commits old; Brave scraper already 429ing. Verdict TRIAL as an ultra-low-RAM
  standby search lane (extract labelled `emulated`).
- **Markdown Crawler / microcrawl** (MIT core, Rust axum, Firecrawl v2 + streamable
  MCP, SPA-shell-gated Lightpanda JS tier = AGPL, Linux-only): best-shaped design,
  2 commits / 0 releases. DEFER, watch-list.
- **AginxBrowser** (Apache-2.0, V8 + own renderer, no Chromium, Firecrawl `/v1/scrape`,
  ~227 MB under load self-reported, 73 MiB image, **no Windows asset**): the only
  sub-300 MB JS renderer found. TRIAL off-box (OVH/WSL2) as the missing JS tier.
- **fastCRW correction:** v0.33.0 (2026-09-02) ships native `win32-x64` zips for
  `crw`/`crw-server`/`crw-mcp` with sigstore-signed `SHA256SUMS` (README stale); its own
  `COMPATIBILITY.md` rates Tavily parity "adapter required" (no `/tavily/*`, no
  `search_depth`, single-URL extract). Keep as secondary fallback; fix the branch's
  "Docker-only" note.
- SKIP (license/weight/redundancy): webclaw (AGPL, `/v1/search` needs Serper key),
  Searcharvester (AGPL, stale), Draco (no LICENSE file), GroktoCrawl (vector DB),
  fire_ctrl/ScrapeForge/agents-api/Angler (multi-container), tavily-hikari (keyed),
  Lightpanda (AGPL, Linux-only -> OVH). BORROW only: AgentSearch, MetaSearchMCP, Argo,
  Kindly, Scrapyard, TadMSTR/searxng-mcp.
- Techniques worth borrowing (all 0 RAM): TadMSTR per-domain capability DB (30-day
  per-tier success, skip tiers <30% over >=10 attempts) = per-domain, time-decayed
  `probed`; `llms-full.txt` + JSON-LD/`__NEXT_DATA__` fast paths; Scrapyard
  `pipeline_steps` provenance + daily canary; Argo per-engine circuit breaker + negative
  cache; AgentSearch escalation ladder + prompt-injection scrub (LLM01) + paywall
  detection; Searcharvester extract size presets + pagination; UnSearch signed citation
  envelope (sha256 + fetched-at + engine + lattice label); Scrapling TLS impersonation.

### Wave-map impact

Anchor applied: ENABLE-native > BORROW-technique > in-process adapter (0 RAM) > stdio
child > daemon; monitoring/estate-ops items go to the "Not a wave" hand-off list. Bold
marks anything that touches a Wave-1 item or says an existing feature only needs
ENABLING.

| Recommendation | Lens | Wave | Changes a Wave-1 item? |
|---|---|---|---|
| Terminal-state taxonomy + always-emit partial report (find 2) | 12 | 2 | no; joins the Wave-2 harness trio, which becomes a reliability set built 2, 3, 1 first |
| Budget tracker + regimes (find 3) | 12 | 2 | no; this IS the trio's budget / "beast mode" item, now with regime thresholds |
| Run ledger + resume-from-checkpoint (find 1) | 12 | 2 | no; new Wave-2 item |
| Loop guard on `query_hash` (5) + keep-latest-3 compaction (4) | 12 | 2 | no |
| Sufficiency gate (6), `contradicted` verdict (9), sub-question DAG + effort classes (8) | 12 | 2, second tranche | no |
| Report-as-state (7) = the trio's evolving report; hedge filter (10), CoVe re-check (11), volatility TTL (12) | 12 | 2 as skill prose; code once `partial:*` is measured | no |
| HyDE, Self-RAG tokens, sub-agent isolation, value-tree / debate / SFT folding | 12 | skip (step-back = one prompt line) | no |
| Thread `OPENALEX_API_KEY` (+ `CORE_API_KEY`) into `scholarly-access` | 13 | 2, config; OWNER-ACTION: create the free keys | no. **ENABLE, not build**: the existing client only lacks the key |
| `cyanheads/openalex-mcp-server` (hosted or npx; free key; budget-aware) | 13 | 2 | no |
| Ai2 Asta MCP for S2 (fresh key; retire the 403ing direct key) | 13 | 2; OWNER-ACTION: key | no |
| `arxiv-mcp-server` (keyless uvx stdio child) | 13 | 2 | no |
| OpenCitations + Europe PMC fullTextXML/annotations REST helpers in the skills | 13 | 2 (in-process, 0 RAM) | no |
| PaperQA2 trial over institutional/OA PDFs (LLM + embeddings) | 13 | 3 (on-demand, endpoint-agnostic per G-4) | no |
| Fix `scholarly-access` README Sci-Hub/LibGen drift; record `paper-search-mcp` downloads as off-limits | 13 | 2, first commit (docs-only; can land any time) | no |
| Unpaywall, Crossref, PapersWithCode, JackKuo666 MCPs, oksure, ancatmara, CORE as a tool | 13 | skip | no |
| SearXNG `categories=science` academic lane | 14 | 2 | **no by default. ENABLE, not build**: the Wave-2 "academic-SearXNG route" is param routing. `searxng-min/settings.yml` inherits upstream engines via `use_default_settings`; only if `searxng_instance_info` shows a science engine disabled does item 1 gain an additive `disabled: false` line for it |
| Firecrawl `research_*` academic tools (second lane for RRF) | 14 | 2 | no. **ENABLE** (existing key; probe pricing first) |
| Exa advanced-search knobs; Firecrawl JSON/extract + `sources:news`/`tbs`; Tavily depth/time_range/raw + `DEFAULT_PARAMETERS` news spec | 14 | 2, router/adapter params + skill prose | no. **ENABLE** |
| Exa `agent_create_run`; drop deprecated `deep_researcher_*` from `_EXA_TOOLS` | 14 | 3 (with the deep-research routing work) | no |
| Firecrawl Monitors (standing queries, email delivery, credits) | 14 | hand-off: monitoring lane; ENABLE via config/prose, no code | no |
| Firecrawl `changeTracking`; SearXNG `format=rss` (+ `rss` in `search.formats`); RSSHub | 14 | hand-off: monitoring lane; RSSHub skip | no; `rss` is a one-line addition to the item-1 file but need not ride Wave 1 |
| Exa Websets monitors + webhooks | 14 | defer/skip (NEW MCP + REST; webhooks need a daemon) | no |
| changedetection.io | 14 | skip (NEW DAEMON, 180-280 MB + ~2 GB Chrome) | no |
| Kagi for monitoring | 14 | skip; the Kagi search lane stays in Wave 4 with these prices noted | no |
| Cross-provider RRF exists at `tools/search-expansion/rank_fusion.py` | 14 | - | **confirms, does not change**: Wave-1 items 2-3 extend that file; do not add a second fusion path |
| Keep TrailSearch as the `native` Tavily-shaped backend | 1 | - | no; confirms the built stack |
| trafilatura-scrape trial as the fastCRW (AGPL) replacement in the emulated Firecrawl tier (`deploy/` run script + endpoint-agnostic `*_URL`, wrap with hub timeout for the dead-handler bug) | 1 | 2 | no |
| WebSearchFree as ultra-low-RAM standby search (unprefixed `/search`+`/extract`; extract labelled `emulated`) | 1 | 2 (optional) | no |
| AginxBrowser JS-render tier (Docker/WSL2 or OVH; `probed`, behind trafilatura) | 1 | 3 (on-demand, G-4 endpoint-agnostic) | no |
| Markdown Crawler / microcrawl | 1 | watch-list (OSSInsight/GitHub REST) | no |
| fastCRW: record native Windows x64 build + "adapter required" Tavily parity in the reunion decision record | 1 | 1 (docs-only, parent edits `docs/plans/2026-09-02-search-stack-reunion.md` at Wave-1 wrap-up) | no |
| Per-domain capability DB, `llms-full.txt` + JSON-LD fast paths, `pipeline_steps` provenance, engine circuit breaker, injection scrub, extract size presets, signed citation envelope | 1 | 2 (harness/adapter borrows, 0 RAM; injection scrub first) | no |
| webclaw, Searcharvester, Draco, GroktoCrawl, fire_ctrl, ScrapeForge, agents-api, Angler, tavily-hikari, Lightpanda on-box | 1 | skip | no |

Net effect on Wave 1: none of the six items is removed or altered by any of the four
recovered lenses. One conditional, additive touch to item 1 (science engines, only if
the probe shows them disabled), one confirmation for items 2-3 (extend the existing
`rank_fusion.py`), and one docs-only correction (fastCRW ships Windows binaries) for
the reunion decision record at wrap-up. Everything else lands in Wave 2/3 or the
hand-off list.
