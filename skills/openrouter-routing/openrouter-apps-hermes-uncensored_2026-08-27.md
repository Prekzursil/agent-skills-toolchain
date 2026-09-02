# OpenRouter apps ecosystem · the "Hermes" at #1 · uncensored-local update

*Generated: 27.08.2026 | Extends: `openrouter-complete-surface_2026-08-27.md` (apps gap) and `~/.agents/local-models-audit_2026-08-27.md` (uncensored lane) | Providers: firecrawl (live, some cache-hits ~7h old), WebSearch, live OpenRouter `/api/v1/models` + `/endpoints` probes (env key named only, never printed) | Confidence graded per claim.*

## Executive summary (the "Return" answers)

1. **Which Hermes the user saw: (b) an app, not a model.** "Hermes" at/near #1 is **Hermes Agent**, Nous Research's open-source (MIT) self-hosted persistent agent — **#1 on OpenRouter's App & Agent Rankings** in *every* view: Most Popular all-time (44.5–45.6T tokens), Global Ranking today (2.47T, more than #2 Claude Code + #3 Kilo Code combined), and #1 Trending (+42% w/w). No Hermes **model** appears in the models top-10 (today's #1 model is stealth "Ox Alpha"), and it is not a `:nitro` throughput artifact. `[A.corrob x3.2026]`
2. **Why the hype:** launched Feb–Mar 2026, 60k+ GitHub stars within ~2 months; persistent memory + autonomous skill creation (closed learning loop), 40+ tools, 14+ messaging platforms, subagents, cron automations, local SQLite, runs on a $5 VPS; defaults to OpenRouter (433 models used) → one app now ≈ the other ~49 tracked apps combined. `[A.corrob x3.2026]`
3. **Top-3 apps insight:** OpenRouter's traffic is dominated by **autonomous/CLI agents** (Hermes Agent, Claude Code, Kilo Code, Cline, Codex), not chat UIs; roleplay apps (Janitor 34.8B, SillyTavern 12.1B) are now a rounding error. Cursor is #18 at 47B/day.
4. **Adopt/skip:** **Hermes Agent app = SKIP** (second agent runtime + always-on daemon on a RAM-pressured box; estate locks G-26/G-36; duplicates Cursor Max + Codex + sidecar). **Model `nousresearch/hermes-4-70b` = ADOPT** into the allowlist for a *narrow low-refusal research-chat lane only* — $0.13/$0.40 per M (passes the cheap heuristic), 131K ctx, reasoning-capable, **but NO `tools` support on OpenRouter and a single provider (Nebius)** → never for agentic T0/T1, no suffix (suffixes are no-ops with one provider; no `:free` variant exists). `[A.live.2026]`
5. **Uncensored local:** best pull candidate for the privacy/uncensored lane is **`huihui-ai/Huihui-Qwen3-8B-abliterated-v2` Q4_K_M (~5.5 GB)** or the finetuned sibling **Josiefied-Qwen3-8B-abliterated-v1**; **Dolphin 3.0 Llama 3.1 8B Q4_K_M (4.92 GB)** is the safest-fit finetune-style alternative with function calling. Hermes 4 **14B does exist** but violates the ratified no-14B+ rule (Q4 ≈ 8.5–9 GB > 6 GB VRAM). Hub-only now — no downloads performed.

---

## Q1 — The apps ecosystem (the gap in the 100% audit)

### What "top apps" measures

OpenRouter has a **separate App & Agent Rankings page at `openrouter.ai/apps`** (the surface audit only covered `/rankings`, which is models-only). Apps **opt in** to usage tracking via the app-attribution headers (`HTTP-Referer` + `X-Title`) — the same headers our harness already sends — and are ranked by **tokens processed** through OpenRouter, not by users, requests, or revenue. 60 apps are currently tracked; private traffic is excluded before aggregation. Rankings data is CC-BY-4.0. `[A.corrob x2.2026: apps page + rankings methodology]`

### The leaderboards (scraped 27.08.2026, firecrawl cache ~00:03 UTC; usage data through Aug 25–26)

**Most Popular (all-time tokens):**

| # | App | Tokens | What it is |
| --- | --- | --- | --- |
| 1 | **Hermes Agent** (Nous Research) | **44.5T** | Self-hosted persistent personal agent |
| 2 | Claude Code | 11.8T | Anthropic's CLI coding agent (via BYOK/OR) |
| 3 | Kilo Code | 8.62T | Open-source coding agent (VS Code/JetBrains/CLI) |
| 4 | Cline | 5.86T | Open-source IDE coding agent |

**Global Ranking (today):** 1. Hermes Agent 2.47T · 2. Claude Code 1T · 3. Kilo Code 513B · 4. DeepSeek Harness 511B · 5. Zazen (Freebuff fork) 435B · 6. omp 403B · 7. Cline 343B · 8. pi 329B · 9. ZCode 199B · 10. Codex 191B. Cursor is **#18 at 47B**. `[A.single.2026 live scrape]`

**Trending (fastest growing this week):** Hermes Agent +42% (14.3T), Zazen +742%, DeepSeek Harness >999%, omp +356%, ZCode >999%, Claude Code +64%, pi +86%, Kilo +36%.

Hermes Agent is simultaneously **#1 in Productivity, Coding Agents, Personal Agents, and CLI Agents**, and drove **433 different models** this month — it is a model-agnostic harness, not a one-model app. `[A.single.2026 app detail page]`

### What this reveals about OpenRouter volume

- **Volume = agents, not chat.** The top 10 is almost entirely autonomous/CLI agents. A crypto-press analysis measured Hermes Agent at **1.5T tokens in one early-August week — nearly matching the other 49 tracked apps combined** (all-time 33.1T then; 45.6T now per the app page). `[B.corrob x2.2026: cryptobriefing + live app page]`
- **The old intuition "OpenRouter volume = SillyTavern/roleplay" is dead:** Janitor AI (34.8B) and SillyTavern (12.1B) are three orders of magnitude below the top agent.
- **LiteLLM does not appear** in the top-20 app ranking at all (it's a proxy, mostly untracked/private); Cline/Roo/Kilo confirm the IDE-agent cohort the surface audit already assessed.
- Nous Research gets **vertical integration**: their agent drives OR volume while their Hermes models serve other developers — one reason the brand is suddenly everywhere. `[B.single.2026]`

### Adopt gate (anti-overfit) — verdict per top app

| App | Verdict | Reason |
| --- | --- | --- |
| Hermes Agent | **SKIP** | A second persistent agent runtime (daemon + gateway + own memory/skills in SQLite) duplicates Cursor Max + Codex + agent-mail + basic-memory; RAM-pressured box; estate locks (one cursor-agent at a time, no worker start <8 GB free, basic-memory sole memory writer). Its **agentskills.io open skill standard** is the one idea worth *watching* — our `.agents\skills` SSOT is conceptually compatible. |
| Claude Code / Codex via OR | **SKIP** (unchanged) | Rebills Max / already native — surface audit verdicts stand. |
| Kilo / Cline / Roo | **SKIP** (unchanged) | Fourth IDE / RAM. |
| DeepSeek Harness, omp, pi, ZCode, Zazen | **SKIP** | More CLI coding agents; nothing they add that Cursor+Codex lack. Trending spikes are adoption curves, not capability signals. |

---

## Q2 — Which "Hermes", and the explainer

### Disambiguation (the three hypotheses, tested)

| Hypothesis | Test | Result |
| --- | --- | --- |
| (a) Nous **Hermes model** trending on model rankings | `/rankings` top-10 scrape | **No** — no Hermes model in top 10 (top: Ox Alpha, DeepSeek V4 Flash, MiMo-V2.5, Hy3…) |
| (b) An **app named Hermes** on apps ranking | `/apps` scrape | **YES — Hermes Agent, #1 in Most Popular, Today, and Trending** |
| (c) `:nitro`-style fast-provider variant | live `/models` probe | **No** — no `hermes*:nitro` slug exists; only 4 Hermes slugs total |

"Fast on top 1" fits (b): the app is both #1 *and* the top trending line (+42% on an already-#1 base). `[A.corrob x2.2026]`

### Who is Nous Research; what is Hermes Agent

Nous Research is a respected open-source AI lab known for the **Hermes model series** ("open, steerable, capable of the full range of human expression… aligned to your values"), the RefusalBench benchmark, and decentralized-training work (Psyche network). **Hermes Agent** (MIT, released Feb 2026 per the project site/Tencent writeup; OpenRouter shows "active since Mar 2026") is their self-hosted agent: persistent memory across sessions, **autonomous skill creation with self-improvement during use**, FTS5 session search, 40+ tools (web search, browser automation, vision), Telegram/Discord/Slack/WhatsApp/Signal/CLI gateways, cron automations, subagents, 7 terminal backends (local → Modal/Daytona serverless), local SQLite, no telemetry. Provider-agnostic but **OpenRouter is the default rail** — hence the token tsunami. 60k+ GitHub stars within ~2 months of launch. `[A/B.corrob x3.2026: github repo + hermes-agent.org + Tencent techpedia + cryptobriefing]`

### The Hermes model family (for the allowlist decision)

**Hermes 4** (released 26.08.2025, tech report + HF cards): hybrid-mode reasoning models — answer directly by default, toggleable `<think>` deliberation — in **three sizes: 14B (Qwen3-14B base, "small and dense for local inference"), 70B and 405B (Llama-3.1 bases)**. Trained for in-turn function calling (`<tool_call>` XML, parsers built into vLLM/SGLang), schema-valid JSON + repair, and **steerability/low refusals: SOTA on Nous's RefusalBench (166 prompts over 32 commonly-refused categories, judged by Sonnet 4; three harm categories keep inverted reward, i.e. the model is still *supposed* to refuse minor-harm/trafficking/self-harm-instruction prompts). Hermes 4 (Reasoning) scores 57.1 vs GPT-4o 17.67.** Newer: **Hermes-4.3-Seed-36B** (03.12.2025) ≈ Hermes-4-70B quality at half the size, trained on the Psyche network — not on OpenRouter. `[A.corrob x3.2026: tech report PDF + HF cards + releases page]`

**Live on OpenRouter (verified 27.08.2026 via `GET /api/v1/models` + `/endpoints`, 417 models total):**

| Slug | $/M in / out | Ctx | Reasoning | `tools` | Providers |
| --- | --- | --- | --- | --- | --- |
| `nousresearch/hermes-4-70b` | **0.13 / 0.40** | 131K | yes | **NO** | Nebius only |
| `nousresearch/hermes-4-405b` | 1.00 / 3.00 | 131K | yes | **NO** | Nebius only |
| `nousresearch/hermes-3-llama-3.1-70b` | 0.70 / 0.70 | 131K | no | no | legacy |
| `nousresearch/hermes-3-llama-3.1-405b` | 1.00 / 1.00 | 131K | no | no | legacy |

No `hermes-4-14b`, no `:free`, no `:nitro` variants exist on OR. The model was *trained* for tool calling, but the hosted endpoint does not expose the `tools` parameter — you'd have to hand-roll `<tool_call>` XML parsing. `[A.live.2026]`

### Why the growth (hype decomposition)

1. **The agent, not the models, is the growth engine** — Hermes Agent's token volume is what put "Hermes" at #1; its default-OpenRouter wiring converts every self-hoster into OR traffic.
2. **Steerability/low-refusal brand**: RefusalBench SOTA + "aligned to you" positioning made Hermes the name people reach for when hosted frontier models over-refuse.
3. **Genuinely open**: MIT agent + open weights + open technical report + cheap hosting (70B at $0.13/$0.40 undercuts most 70Bs).
4. **Self-improvement narrative** ("gets smarter every day", skill marketplace) is catnip in 2026's agent discourse. `[B.corrob x2.2026]`

### Verdict — Hermes in OUR harness

- **`nousresearch/hermes-4-70b` → ADOPT (narrow lane).** Add to the allowlist as the **hosted low-refusal/steerable research-chat lane** the local-models audit identified — exactly the pharma/harm-reduction-literature queries (phenibut project) hosted default lanes over-refuse. Price passes the T0 cheap heuristic (≤$0.15/$0.60); 131K ctx; reasoning toggle available.
  - **Constraints:** chat/extraction/synthesis ONLY — **no OpenRouter-side `tools`** and a **single provider** (Nebius) means no `:floor`/`:nitro` benefit, no fallback diversity, and no agentic use. Do not route T0 grunt-with-tools or T1 tool work here. Paid → still blocked until the credit top-up (account overdrawn per surface audit).
  - **Suffix recommendation: none** (bare slug). `:free` doesn't exist; suffixes are no-ops with one provider.
  - Escalate to `hermes-4-405b` only for correctness-critical steerable work, per T0→T1 escalation rules.
- **Hermes Agent app → SKIP** (see Q1 gate). **Hermes-4-14B local → SKIP** (violates ratified no-14B+ rule: Q4_K_M ≈ 8.5–9 GB > 6 GB VRAM).

---

## Q3 — Uncensored local models, state of the art ≤7–9B (update to the local-models audit)

**Ethics/safety framing (unchanged from the audit):** this lane exists for *legitimate research the hosted lanes over-refuse* — pharmacology/harm-reduction literature work (phenibut project), security research on the estate's own assets — not for wrongdoing. Note that even Nous's own RefusalBench *keeps refusals rewarded* for minor-harm/trafficking/self-harm-instruction categories; the recommendation set below stays lawful and the local lane stays estate-local.

### What "abliterated" means, and the quality cost

**Abliteration** = directional ablation of the "refusal direction": Arditi et al. (NeurIPS 2024) showed refusal in 13 open chat models (1.3B–72B) is mediated by a **single direction in activation space**; ablating it disables refusal, adding it induces refusal on harmless prompts. Applied as **weight orthogonalization**, it permanently edits a copy of the weights — no finetuning run needed. `[A.corrob x3.2026: NeurIPS paper + two mech-interp secondaries]`

**Quality cost:** real but shrinking. Side effects reported include shifts in confidence/disposition and occasional coherence/format regressions; the measurable proxy is KL divergence from the original on harmless prompts. The 2026 **Heretic** tool (`heretic-llm` on PyPI, AGPL, by p-e-w) automates abliteration with Optuna and reached **3/100 refusals at KL 0.16** on Gemma-3-12B vs **0.45–1.04 for manual abliterations** at the same refusal rate — i.e. modern automated abliteration costs ~6× less behavioral drift than the classic huihui/mlabonne manual method. Finetuned-uncensored models (Dolphin, Josiefied) take a different route: retraining on uncensored data, which can *add* capability but changes the model more broadly. `[B.corrob x2.2026]`

### Candidate table (hub only — NO downloads performed; probe `real=1` before any pull)

| Model | Size / base | VRAM @ Q4_K_M | Fit on 6 GB? | Method / license | Trusted GGUF source | vs hosted alternative |
| --- | --- | --- | --- | --- | --- | --- |
| **Huihui-Qwen3-8B-abliterated-v2** (huihui-ai) | 8.2B / Qwen3-8B | ~5.5 GB (+ KV; keep ctx short) | **Yes, tight** | Abliteration / Apache-2.0 | `huihui-ai` HF repos | Beats hosted on privacy; hosted `hermes-4-70b` beats it on quality |
| **Josiefied-Qwen3-8B-abliterated-v1** (Goekdeniz-Gülmez) | 8.2B / Qwen3-8B | ~5.4 GB | **Yes, tight** | Abliteration **+ finetune** (claims ≥ base on benchmarks, tool use kept) / Apache-2.0 | `Goekdeniz-Guelmez` HF; ollama `goekdenizguelmez/JOSIEFIED-Qwen3:8b-q4_k_m`; `Mungert`/`DuoNeural` GGUF mirrors | Same |
| **Dolphin 3.0 Llama 3.1 8B** (cognitivecomputations / Eric Hartford) | 8B / Llama-3.1-8B | **4.92 GB** (Q4_0: 4.66 GB) | **Yes — safest fit** (same class as proven qwen2.5:7b @ 4.7 GB) | Uncensored **finetune** (system-prompt steerable, function calling, ChatML) / Llama-3.1 community license | official `dphn`/`cognitivecomputations` GGUF + `bartowski` | Its 24B "Venice" sibling is ON OpenRouter at $0.20/$0.90 (no tools) — use that hosted when privacy not required |
| **Hermes 3 Llama 3.1 8B** (Nous) | 8B / Llama-3.1-8B | ~4.9 GB | Yes | Neutral-alignment finetune (lower refusals, function calling, NOT fully uncensored) / Llama-3.1 license | official `NousResearch` GGUF + bartowski | `hermes-4-70b` hosted is the strictly better Hermes when RAM=0 is fine |
| Hermes 4 **14B** (Nous) | 14B / Qwen3-14B | ~8.5–9 GB | **NO — excluded** (no-14B+ rule) | Official small Hermes 4; GGUF by LM Studio | — | Use `hermes-4-70b` hosted instead |
| Heretic-made builds (e.g. `p-e-w/*-heretic`) | varies | varies | 12B example: no | Automated abliteration (lowest KL); tool itself AGPL | `p-e-w` HF | Watch this space — a Heretic'd Qwen3-8B would likely be the best-in-class abliterated 8B |
| qwen2.5:7b (incumbent) | 7B | 4.7 GB (installed) | Yes — proven | Stock (censored) | already local | Keep as the general local T0; it is NOT the uncensored lane |
| WORMGPT-13 (estate) | — (already pulled) | — | installed | Offensive/uncensored, owner-ops only | already local | Unchanged; named only |

**VRAM reality check:** the audit's envelope (~5117 MiB GPU-full weights + ~1 GB KV) means **8B Q4_K_M is the ceiling, and Qwen3-8B builds (~5.4–5.5 GB) are tighter than Llama-8B builds (~4.9 GB)** — run them with reduced context (the 41K-ctx-full figure is 11.3 GB, far over budget) or accept partial CPU offload. Dolphin 3.0 8B is the only candidate with the same comfort margin as the proven qwen2.5:7b. `[B.corrob x2.2026: llmrun VRAM tables + HF file sizes]`

**Trusted GGUF sources (hub-only rule):** official model-org repos first (`dphn`/`cognitivecomputations`, `NousResearch`, `huihui-ai`, `Goekdeniz-Guelmez`), then the two high-reputation quantizers **`bartowski`** and **`mradermacher`**; `Mungert`, `DuoNeural` are newer/smaller uploaders — prefer originals over mirrors. TheBloke is stale (inactive since 2024). Never invent tags; probe before pull.

### Local vs OpenRouter low-refusal hosted (the RAM=0 comparison)

| Axis | Local abliterated 8B | Hosted `hermes-4-70b` ($0.13/$0.40) / `dolphin-mistral-24b-venice-edition` ($0.20/$0.90) |
| --- | --- | --- |
| Privacy | **Fully offline** — the only choice for phenibut IP, institutional data, estate work | Prompts hit Nebius/venice via OR; fine for public-literature queries only |
| Quality | 8B ceiling; abliteration adds small KL drift | 70B/24B — **much smarter**; Hermes 4 has reasoning mode |
| Refusals | ~0 (abliterated) | Low (RefusalBench SOTA / Venice uncensored) but **not zero** — provider ToS still applies |
| Cost | $0 + VRAM/RAM load while resident | ~$0.0002–0.003 per typical query; RAM=0; **blocked until credit top-up** |
| Rule of thumb | Privacy required OR truly zero-refusal needed | Privacy NOT required and quality matters — **default to hosted Hermes 4 70B** |

**Verdict:** the local uncensored lane stays (ratified), and gets **one upgrade candidate: Huihui-Qwen3-8B-abliterated-v2 (or Josiefied v1) Q4_K_M** as the modern abliterated option next to the existing estate model — pull only when a concrete task needs it, per the no-speculative-downloads discipline. For everything where privacy is not required, **`hermes-4-70b` via the sidecar is the better answer than any local 8B.**

---

## Changes to existing docs (PROPOSED ONLY — A-D wave worker owns skill edits)

1. **`openrouter-routing/SKILL.md`** — add allowlist entry: `nousresearch/hermes-4-70b`, lane = "low-refusal research chat (no tools, single provider Nebius, no suffix)"; forbid it for tool-calling T0/T1; note 405B as escalation.
2. **`openrouter-complete-surface_2026-08-27.md`** — §5 correction: "Hermes" in the works-with row is now **the #1 app on a dedicated `/apps` leaderboard** (44.5T tokens; separate from `/rankings`); apps-attribution headers we already send are what feeds it.
3. **`~/.agents/local-models-audit_2026-08-27.md`** — append: uncensored candidates table (this report §Q3), abliteration/Heretic explainer pointer, and the "hosted hermes-4-70b when privacy not required" rule.
4. **`AGENTS.md` T0/T1/T2 bullet** — no change needed (lane addition lives in the skill, not the contract).
5. Optional watch-items: agentskills.io skill standard (Hermes Agent) vs our `.agents\skills` SSOT; a future Heretic'd Qwen3-8B; Hermes-4.3-Seed-36B if it ever lands on OR at 70B-class pricing.

---

## Methodology

**Sub-questions:** (1) apps-ranking mechanics + leaderboard state (2) Hermes disambiguation (app vs model vs variant) (3) Hermes Agent/Nous background + hype drivers (4) live Hermes slugs/pricing/params (5) abliteration technique + cost (6) ≤9B uncensored candidates + VRAM fit + sources (7) local-vs-hosted comparison (8) adopt/skip gates vs anti-overfit rules.

**Providers routed:** firecrawl scrape (rankings, apps, app-detail — all 200, cache-hits from ~00:03–00:09 UTC same day; usage data through Aug 25–26), WebSearch (5 queries, corroboration), live OpenRouter API via two Python probes in this folder (`_tmp_hermes_probe.py`, `_tmp_hermes_endpoints.py` — 417 models confirmed, matching the sibling audit), Hermes 4 tech-report PDF full-text (grep for RefusalBench). Context7/Exa/Tavily not needed; no Playwright; no installs, no MCP changes, no downloads. `OPENROUTER_API_KEY` named only; probes work unauthenticated for `/models`.

**basic-memory:** both MCP namespaces returned "Not connected"/error at write time — optional vault note **NOT-CHECKED** (this file is the durable record; re-attempt when the MCP is healthy).

**Cross-ref:** every load-bearing claim carries ≥2 independent sources of {live scrape, live API, official repo/HF/docs, tech report, third-party press/analysis} except single-scrape leaderboard numbers, marked `[A.single]`. Known conflict resolved: "Hermes 4 has no 14B" (one search synthesis) was **wrong** — official Nous releases page + HF card confirm 14B exists; the correct claim is "no 14B **on OpenRouter**".

**Confidence:** High on Q1/Q2 identification and live pricing (live scrape + live API + 2 independent press/docs). Medium on VRAM figures (estimator site + HF file sizes; not measured on this box) and on Josiefied benchmark claims (author self-reported). Low/watch on anything about future Hermes releases.

## Sources

1. [OpenRouter App & Agent Rankings](https://openrouter.ai/apps) — tier A — firecrawl live scrape (27.08.2026)
2. [OpenRouter Model Rankings + methodology](https://openrouter.ai/rankings) — tier A — firecrawl (27.08.2026)
3. [Hermes Agent app detail](https://openrouter.ai/apps/hermes-agent) — tier A — firecrawl (45.6T, #1, since Mar 2026, 433 models)
4. Live `GET /api/v1/models` + `GET /api/v1/models/{slug}/endpoints` — tier A — this machine, 27.08.2026 (417 models; 4 Hermes slugs; Nebius-only; no `tools`)
5. [NousResearch/hermes-agent GitHub](https://github.com/nousresearch/hermes-agent) — tier A — websearch
6. [hermes-agent.org](https://hermes-agent.org/) — tier B — websearch (MIT, Feb 2026, self-hosted)
7. [Tencent Cloud techpedia: What Is Hermes Agent](https://www.tencentcloud.com/techpedia/143930) — tier B — websearch (60k stars, 14+ platforms, MIT)
8. [CryptoBriefing: Hermes Agent 1.5T tokens ≈ 49 apps combined](https://cryptobriefing.com/hermes-agent-1-5-trillion-tokens-openrouter/) — tier B — websearch
9. [Hermes 4 Technical Report (PDF)](https://nousresearch.com/wp-content/uploads/2025/08/Hermes_4_Technical_Report.pdf) — tier A — full text (RefusalBench 57.1 vs GPT-4o 17.67; 166 prompts/32 categories; inverted-reward categories)
10. [NousResearch/Hermes-4-405B HF card](https://huggingface.co/NousResearch/Hermes-4-405B) + [Hermes-4-14B](https://huggingface.co/NousResearch/Hermes-4-14B) — tier A — websearch (sizes, tool-call format, steerability)
11. [Nous Research releases page](https://nousresearch.com/releases/) — tier A — websearch (14B/70B/405B 26.08.25; Hermes-4.3-Seed-36B 03.12.25)
12. [Arditi et al., "Refusal in Language Models Is Mediated by a Single Direction", NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/f545448535dfde4f9786555403ab7c49-Paper-Conference.pdf) — tier A — full text
13. [Heretic vs abliterated benchmarks 2026](https://aithinkerlab.com/heretic-ai-abliteration-benchmarks-2026/) — tier B — full text (KL 0.16 vs 0.45–1.04)
14. [llmbase.ai: obliterated models explained](https://llmbase.ai/guides/obliterated-models-explained/) — tier B
15. [llmrun VRAM tables: huihui Qwen3-8B-abliterated v1/v2](https://llmrun.dev/model/huihui-ai-huihui-qwen3-8b-abliterated-v2) — tier B (Q4_K_M 5.4–5.5 GB)
16. [Josiefied-Qwen3-8B-abliterated-v1 HF](https://huggingface.co/Goekdeniz-Guelmez/Josiefied-Qwen3-8B-abliterated-v1) — tier B — author card
17. [dphn/Dolphin3.0-Llama3.1-8B-GGUF HF](https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B-GGUF) + [RunThisModel entry](https://runthismodel.com/models/dolphin-3.0-llama-3.1-8b) — tier A/B (Q4_K_M 4.92 GB, llama3.1 license)
18. [NousResearch/Hermes-3-Llama-3.1-8B HF](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B) — tier A
19. Prior harness docs: `openrouter-complete-surface_2026-08-27.md`, `~/.agents/local-models-audit_2026-08-27.md` — tier A — this machine
