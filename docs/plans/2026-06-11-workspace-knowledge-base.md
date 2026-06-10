# Optimal Agentic Workspace — Research & Council Knowledge Base

**Date:** 2026-06-10/11 · **Status:** canonical knowledge capture (evidence base for the design doc `2026-06-10-optimal-agentic-workspace-design.md`).
**Provenance:** 4 deep-research pillars + a 50-probe research fan-out (workflow `wf_d3c3408d-c34`, full raw synthesis ~57K tok in its task output) + THREE council streams: external model-council (Claude/Gemini-agy/Qwen; Codex+DeepSeek failed) and a 6-persona self-council (2 Opus: behavior-ux + contrarian; 4 Fable: security/tool-retrieval/ctx-eng/systems-pragmatist).

---

## ★ THE STRATEGIC VERDICT (what to actually do) — convergent across all council streams

> **Prune the menu first (~600 → ~40). That is *most* of the fix, zero infra.** Then keep native Tool Search + basic-memory + add a few hooks. **Defer or CUT** the gateway / vector index / graph-DB / ephemeral-spawn stack until prune + Tool Search is *measured* insufficient. The original 4-layer "platform" was drifting into **"a five-daemon SRE platform to solve a config-hygiene problem"** (Fable systems-pragmatist).

Why prune-first dominates (multi-source):
- Selection accuracy collapses past 30-50 tools → ~13-20% at 200-740 (Anthropic; RAG-MCP 2505.03275). The menu is the cause.
- The ~35K-token/subagent baseline tax (measured this session) is fixed by **shrinking the menu**, NOT by fronting it with a daemon (ephemeral spawn *adds* 5-15s latency and still inherits the menu).
- Live proof: this session carries **3 identical copies** of the same ~17-skill pack (`document-skills`≡`example-skills`≡`claude-api`), ~140 `tooluniverse-*`, ~40 `source-command-*`, binary-ninja mounted 2×, 4 browser stacks. At ~40 tools you don't need MiniLM/FAISS — a grep-able one-page catalog suffices.

---

## A. Corroborated best-practices (highest-confidence, one-line-actionable)

**Lifecycle reframe (adopt as the organizing frame):** organize by **task-lifecycle state machine**, not by mechanism — failure happens per *phase*. **Phase-gated tool visibility** (statewright): destructive tools simply don't exist in a read-only phase (local models 2/10→10/10).

**Discovery/Selection:** `ENABLE_TOOL_SEARCH=auto:5`; keep **≤30 auto-loaded tools**; every description carries a **scope clause** ("use when X / NOT when Y / use Z instead", <12%→97.2% coverage, Trace-Free+ 2602.20426); **two representations per skill** (short routing label seen by agent + full body indexed; 31-44pp drop if body hidden); skill descriptions **single-line** (multi-line YAML truncates to line 1 = ~40% of misfires; optimized 20%→84% activation).

**Overhead (token≠RAM — keep separate):** tokens degrade *cognition*, RAM only constrains the *machine*. Native Tool Search defers MCP schemas (~85% token cut; Opus 4.5 79.5%→88.1%) **but does NOT defer HTTP/SSE-transport MCP tools** (CC #40314 closed not-planned → route HTTP MCPs through a stdio aggregator or ~120K tokens load upfront). Compact early at **70%** (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`; summarizer deadlocks ~48% at high fill). **AGENTS.md** as cross-tool config (`@AGENTS.md` import; Codex+Antigravity+Claude read it). Lazy-RAM *is* possible w/o Docker (lazy-mcp 5-min reaper, MCPJungle stateless) — but Docker is OUT on Windows (Resource Saver can't reclaim WSL2 RAM).

**Memory/Continuity:** echo-chamber fix = post-compaction **`/clear` + reload ONLY the structured checkpoint** (never merge auto-summary). **Hooks (not the agent) write memory** — agent = annotator. JIT/pull (identifiers in context, content via tools); CLAUDE.md <300 lines; "assume interruption". Write schema: distilled beliefs w/ `confidence/source/verified_by/learned_date` + **causal provenance** (−24.6% retrieval without it); prefer **failure-derived heuristics**; dedup-then-compress; **cull stale** (topically-coherent-but-irrelevant is a *worse* distractor than noise → vindicates [[harness-trim]]).

**Behavior (hooks WIRING TABLE, not prose):** clarification **EVPI-gated, NOT always-on** (always-ask → 93% rubber-stamping); **front-load** goal-clarification into first 1-2 actions (hard phase transition at ~10%, worthless after); proactive suggestions only at **task boundaries**, never mid-task; **generator-critic pass** before surfacing output (sycophancy is in weights). Make `clarify_requirements` a **tool the model elects to call**, not a blocking gate (a gate that refuses to start *is* delirium by another name).

**Hooks/Enforcement:** hooks are the **only** enforcement layer (CLAUDE.md is advisory); `exit 2` is the only blocking code; Stop = `{"decision":"block"}`+exit0, **honor `stop_hook_active`**; **risk-tiered** not binary (force-push only if SHA matches recent commit); **terminal-state tool outputs** (`SUCCESS:/FAILED:`+id) = 7× reduction (14→2) *before* any detector; **goal re-injection every N turns** (PreToolUse write-op preamble, counters drift); **result-aware fingerprint** `(tool, args_hash, output_hash)` not input-hash (health-check MCPs have identical args by design → plain debounce false-positives).

---

## B. Holes / corrections the councils surfaced (de-risking)

- **Security (the crown-jewel hole):** an unauthenticated localhost HTTP gateway = a **credential-aggregating confused deputy** (cf. CVE-2025-49596 MCP-Inspector localhost RCE) fronting code-exec MCPs (`ida py_eval`, `playwright browser_run_code_unsafe`, frida) at full user privilege. Loopback ≠ auth boundary (DNS-rebinding, malicious npx postinstall). Ralph loops run `--dangerously-skip-permissions` + `--setting-sources project,local` → **user-scope hooks are bypassed**; phase-gated *visibility* ≠ authorization. **Fix:** authenticated **per-identity capability broker** (named-pipe ACL or random-port+bearer+Origin check), vend short-lived per-server scoped tokens, **default-DENY** for mutating/code-exec classes enforced server-side. **Memory poisoning:** durable failure-store + self-improving index re-injected every session = one indirect injection becomes a persistent backdoor (MINJA); confidence/provenance are model-self-reported = **forgeable**; embeddings are invertible; secrets pasted in chat get indexed. **Fix:** quarantine tool/web-derived memory in a **data-only namespace** (quoted, non-actionable); **HMAC-sign** checkpoints written by the trusted hook; gitleaks/regex redaction on every write.
- **Retrieval (if we even build an index):** MiniLM-only dense is the weakest config (2021, 256-token truncation → "full body" = first ~200 words; **can't model negation** → "NOT when Y" scope clauses pull *excluded* queries *closer*, NevIR). TWO routers (native BM25 + dense find_capability) = meta-selection problem. **Fixes:** ONE entry point, **hybrid BM25 + modern small embedder, RRF-fused**, + a **cross-encoder reranker** (bge-reranker) top-50→5 (one component fixes negation + near-dups + register gap); **doc2query/ToolDreamer** (index task-phrased synthetic queries, not capability prose); move NOT/use-Z into structured metadata as **post-retrieval filters**; **canonicalize duplicates** at index build (cluster >0.9 cosine + alias map + MMR); dedupe FIRST, learner LAST (cluster-level bandit w/ verified-outcome attribution); **eval harness** (mine transcripts for task→tool pairs, freeze ~200 as recall@5 gate); content-hash incremental reindex (skills are copied not symlinked → drift).
- **Memory ("swaps the auto-summary echo-chamber for a *self-summary* one"):** nobody writes the "continuous" checkpoint + nothing verifies it on reload; agent self-report decays in exactly the long sessions that compact; monotonic+HEAD stamp is decoration (nothing diffs it). **Fix:** **PostToolUse hook** harvests the objective ledger (cmd/exit/files/HEAD/test-counts); agent writes only rare decision records; SessionStart/reload **diffs the stamp vs live `git rev-parse HEAD` + dirty-hash and surfaces drift BEFORE the agent reads**. Failure-notes ROT (your own scholarly-access note already needed a "don't trust it" amendment; Corn-718 "DISPUTED" forever) → failure entries carry **falsifiable preconditions (version/env/error-sig) + TTL**, labeled "hypothesis — cheap re-test before trusting", contradicting success **auto-tombstones** via supersedes-link. **FalkorDB/Graphiti contradicts your own context-rot audit** ([[toolkit-gap-analysis-2026-05]]: root cause = *too many* memory layers) → **CUT it**; basic-memory only; if ever justified, derive a graph as a *rebuildable read-index*, never a 2nd writable store. Also: 52 auto-memory files (~4.9K tok MEMORY.md) load every turn — itself violates the JIT principle (candidate for H6 memory-consolidation, already deferred in [[harness-trim]]).
- **Systems (over-engineering):** 5+ always-on daemons + graph DB + index + TUI is unmaintainable for one user; **SPOF inversion** (gateway-in-critical-path: one wedged daemon kills ALL tools; stdio clients hold dead pipes across proxy restart); 10+ hooks × 200-600ms PowerShell spawn/tool-call = a tax often exceeding the MCP call; config truth splits 5 ways (.claude.json/.mcp.json/gateway-registry/index/TUI-state) — you've already been burned wiping curated `disabledMcpServers`. **Simplify:** prune → static menu + per-project `.mcp.json` profiles + native Tool Search; keep reaper only if orphans persist post-prune.

---

## C. Novel / ceiling-raising ideas (evaluated)

1. **Warm JIT capability-gateway** (`find_capability` over tools+skills + `spawn_scoped_workspace`) — all external-council models converged here; "the 4 layers are one diagonal: hooks emit signal → memory stores it (incl. failures) → retrieval consumes it → next selection improves." **BUT** the Fable council heavily qualifies it: at ~40 tools it's unnecessary; ephemeral spawn adds latency + still inherits the menu; needs auth + hybrid retrieval + dedup to not be worse than nothing. → **Treat as a LATER, measured option, not the centerpiece.**
2. **Lifecycle state machine + phase-gated tool visibility** — structurally robust anti-degeneration; strong keep.
3. **Hooks-as-memory-ledger + HEAD-validated reload** — the highest-value *new* mechanism (kills the echo-chamber at the source). Strong keep.
4. **Terminal-state tool outputs + result-aware fingerprint** — cheap, high-ROI, zero-infra. Strong keep.

---

## D. "Insist & explore" — what to pursue deeper vs drop

**INSIST / explore deeper (high value, under-developed):**
- **Hooks-write-memory + HEAD-validated reload** — the echo-chamber root fix; needs a concrete hook design + checkpoint schema. (Explore: build it.)
- **The prune itself** — exact dedup/disable list, the "prune by *workflow* not frequency" caveat, + a one-week firing-frequency measurement to seed it. (Explore: do it.)
- **Failure-memory with TTL + falsifiable preconditions + auto-tombstone** — fixes the rotting-notes problem we can SEE in the vault. (Explore: design the schema.)
- **EVPI-gated clarification as an elected tool** (not a blocking gate) — directly serves the user's "inquisitive but not delirious" goal. (Explore: prototype.)
- **AGENTS.md cross-tool config** — one config Claude+Codex+Antigravity read = the cleanest cross-AI win. (Explore.)

**HOLD / measure-before-building (don't insist yet):**
- Vector index / hybrid+reranker retrieval — only if prune+ToolSearch proves insufficient (build the recall@5 eval first).
- Capability-gateway / ephemeral scoped sub-agents — measured option after prune.
- Shared HTTP hot-core — only with the authenticated broker; lower-leverage (RAM not cognition).

**DROP:**
- FalkorDB/Graphiti (3rd memory layer — contradicts the user's own context-rot root cause).
- Docker MCP Gateway (Resource Saver can't reclaim WSL2 RAM on Windows).
- Always-on clarification gate / always-ask (→ rubber-stamping).
- MiniLM-only dense retrieval; scope-clauses-as-indexed-text (negation-blind).

---

## E. Key citations
Discovery: RAG-MCP 2505.03275 · MCP-Zero 2506.01056 · Trace-Free+ 2602.20426 · ToolRet · ToolScope 2510.20036 · Anthropic Tool Search (platform.claude.com/.../tool-search) · skill-activation deep-dive. Memory: Anthropic effective-context-engineering + multi-agent-research-system · CoALA · Mem0/Letta/Zep · claudefa.st context-recovery-hook. Anti-degen: dev.to/aws reasoning-loops · SpecRA (OpenReview xVO4BqmzVD) · Ralph. Hooks: code.claude.com/docs/en/hooks · severity1/prompt-improver · nizos/tdd-guard · boucle.sh. Security: CVE-2025-49596 · MINJA · NevIR · OWASP MCP Top 10. SOTA: AGENTS.md · shyamverma shared-mcp-proxy · lazy-mcp/MCPJungle · Docker Resource-Saver docs.
