---
title: model-cascade
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/model-cascade
---

# Research: model-cascade — cost-aware model routing for pentest agents

Date: 2026-09-29. Researcher lane: model-cascade. Estate: CyberStrike 1.1.16 + MCP gateway (127.0.0.1:31100), Decepticon (LangGraph), PentAGI staged, Ollama qwen3:4b, Windows Server, NO Docker.

All findings below cite the exact source I read or the exact command I ran this session. Local artifacts saved: `out/research/pentestchain.pdf`, `out/research/pentestchain.txt`, `out/research/dearbhadh.html`, `out/research/dearbhadh_lb.html`, `out/research/aisi_openweight.html`, `out/research/shellvoide.html`.

---

## 1. PentestChain — the cascade reference

**Identity**: "PentestChain: A Cost-Aware, MCP-Orchestrated Framework for Automated Penetration Testing with Free-Tier LLMs" — arXiv 2609.18120v2 (2026-09-16), accepted at ACM ASIA CCS 2027 (Macau). Authors: Patel et al. (author block incl. Mohamed Chahine Ghanem). Found via Exa query (§Q4). Downloaded: `curl -sL https://arxiv.org/pdf/2609.18120 -o out/research/pentestchain.pdf` (1,029,314 bytes, `%PDF-` verified). The Read tool's PDF page extraction is NOT configured in this runtime (error: "PDF page extraction is not configured"), so I extracted text with pypdf (`pip install pypdf`; `PdfReader` → 13 pages, 74,078 chars → `out/research/pentestchain.txt`). All line numbers below refer to that file.

**Architecture** (pentestchain.txt:19-27, 405-470):
- 10 phases; offensive logic lives in a **deterministic exploit map** (port+banner keyword → Metasploit module), AI only enriches/suggests. 11-tool MCP server (txt:104-108: scan, enumerate, service_detect, vuln_correlate, exploit_suggest, exploit_execute, web_scan, report_generate, status, facts, fix_plan).
- **Cascade (call_ai_fast, Algorithm 1, txt:426-431)**: strict cost order — (1) local Ollama qwen2.5:7b (zero marginal cost, data stays on host), (2) free-tier OpenRouter, (3) free-tier Cerebras, (4) deterministic rule-based fallback D(p). Escalate to next provider on any non-200, 429, or timeout; provider marked dead for 90 s; per-minute guards stay within free-tier ceilings. The deterministic branch is a **total function** — "the loop cannot fail" (txt:413-416, 466-470).
- Provider history: migrated Groq and Gemini → OpenRouter + Cerebras after Groq imposed free-tier limits (txt:562-564).
- Refusals are a first-class outcome class, separated from infra errors: "success, refusal, iteration-budget exhaustion, or infrastructure error—so that genuine model refusals are never counted as infrastructure errors" (txt:624-626). The paper does NOT publish a per-model refusal-rate table (checked: only 3 occurrences of "refus" in the whole text, txt:625, 626, 1013 — none numeric).

**Measured cascade data** (txt:705-733, Table 3; txt:759-770):
- Per engagement (mean±SD over 4 runs): 76.8±12.0 calls to local Ollama, 21.8±1.9 to OpenRouter, 21.8±1.9 to Cerebras. **Ollama first-tier success rate 96.4±0.6%**, mean local latency 16,114 ms.
- **$0.00 paid-API spend across all four engagements**; 181±23K tokens; pipeline 21.7±4.4 min; AI→rule fallback rate 3.6±0.6% (clustered at free-tier peak hours).
- Exploitation: confirmed sessions on Metasploitable 2 (distcm_exec bind shell, postgres Meterpreter), 12 exploits confirmed on MSF2, 0 on the hardened modern Debian host (txt:700-712, Table 4).
- Cost model (§6.3, txt:629-693): paid cost = Σ over providers of tokens × price with free-tier quota ρ; the free-tier config sets ρ=0 so cost reduction "is structural rather than a quality-for-price trade" (txt:242-245).

**Implementations on GitHub** (gh code+repo search, §Q10): the paper has no official repo I could find. `jasperGodson/PenTestChainStudio-1` (0★, "Audit simulation", pushed 2025-10-20) and `Rushabh0508/Pentest-Chain` (0★, pushed 2026-08-23, contains `PentestChain_Claude_Prompt.md`). Third-party derived briefs exist: `Marontis/agentic-engineering` → `research-briefs/pentestchain-cost-aware-mcp-pentesting.md`, `flybfree/AI-Wiki` → `raw/papers/2026-09-16_..._PentestChain_...md`, `Agent-Threat-Rule/agent-threat-rules` → `proposals/arxiv/ARXIV-2609.18120.proposal.yaml` (found via gh code search, not read in full).

**Estate mapping**: the estate already matches this shape — Ollama (qwen3:4b, not 7b), a free GLM web lane (skill `zai-lanes`: MCP `glm_chat`, GLM-5.3-Flash class, browser-backed, ~5-20 s/call; and OpenAI-compatible HTTP form at :18319), plus plan-entitled official API. PentestChain's contribution to copy: deterministic-first design, 90-s dead-provider marking, refusal-vs-infra outcome separation, per-engagement dollar instrumentation.

---

## 2. Refusal-rate comparisons: GLM vs DeepSeek vs (old) Claude vs local Qwen

### 2a. RedLineBench — the direct instrument (cracken-ai/redline-bench)
`gh api repos/cracken-ai/redline-bench` → 13★, MIT, Python, pushed 2026-09-11, 2 open issues. README read in full via gh readme API. 153 grounded single-turn offensive-security prompts (targets are Cracken-owned sinkhole domains/IPs), 6 use cases × 25-26, dual-judged (Claude Sonnet 4.6 + DeepSeek V4 Pro), refusal and capability scored separately; refusal forces capability 0. Reference run = 11 models × 153 prompts:

| Model | Refusal S4.6/DS | Blended quality | Answered-only quality | Recovered |
|---|---|---|---|---|
| **GLM-5.2** | **35% / 39%** | 2.88 / 2.82 | **4.45 / 4.63** | **+1.69** |
| DeepSeek V4 Pro | **7% / 5%** | **4.06 / 4.19** (best) | 4.37 / 4.42 | +0.27 |
| DeepSeek V4 Flash | 7% / 5% | 3.97 / 4.09 | 4.28 / 4.32 | +0.27 |
| Qwen3.6-27B (base) | 11% / 13% | 3.73 / 3.70 | 4.19 / 4.26 | +0.51 |
| Huihui-35B-A3B (abliterated) | 7% / 3% | 3.79 / 3.95 | 4.06 / 4.06 | +0.19 |
| Kimi K2.6 / K2.7-Code / K3 | 17/17/14% & 19/18/20% | 3.66-3.87 | 4.41-4.51 | +0.8 |
| gemma-4-E2B | 38% / 39% | 1.96 / 1.83 | 3.15 / 2.97 | +1.16 |

**The cascade-relevant headline**: GLM-5.2's poor blended score is refusal-driven, not capability-driven — on items it answers it scores 4.45-4.63 (near Kimi K3's top). "Models whose low blended score is driven by refusals rather than weak answers move the most" (README). Per-use-case refusals: `post_exploitation` is the wall — gemma 85%, GLM 85%, Qwen 54-62%, Huihui 27/0%, DeepSeek 27-38%; `payload_generation` and `tool_command_selection` are near-zero for nearly everyone. Judge table: **Opus 4.8 "❌ refuses a large share of items" as judge; Claude Sonnet 4.6 ✅; DeepSeek V4 Pro ✅**. Invariants worth copying: temperature 0, never cap max_tokens (a truncation reads as refusal), strip `<think>` before judging.

### 2b. AISI (UK) — capability gap + cost-per-task + refusal circumvention
Fetched `https://www.aisi.gov.uk/blog/how-far-behind-the-frontier-are-leading-open-weight-models-on-cyber` (2026-07-17) → `out/research/aisi_openweight.html`:
- GLM-5.2 (Jun 2026) ≈ **Opus 4.6** (Feb 2026) on narrow cyber tasks and ≈ Opus 4.5 on long-horizon cyber ranges; DeepSeek V4-Pro ≈ Opus 4.5 (narrow). Open-weight gap narrowed to 4-7 months (from 6-10 in 2025).
- **Safeguards**: "Our evaluations of recent open weight models were largely unimpeded by safeguards. **DeepSeek V4-Pro occasionally refused narrow cyber tasks, mainly in reverse engineering, which we circumvented simply via a small number of repeat attempts** at refused tasks." → retry-on-refusal is a sanctioned, working mitigation.
- **Cost-performance (cascade numbers)**: a 100M-token cyber-range run cost ≈ **$85 for Opus 4.5/4.6 vs $46 GLM-5.2 vs $1.19 DeepSeek V4-Pro**; per 100%-solved task **Opus 4.6 $15.17 vs GLM-5.2 $6.12; Opus 4.5 $12.50 vs DeepSeek V4-Pro $0.28**.
- Related AISI pages found but not read: "How fast is autonomous AI cyber capability advancing?", GPT-5.5 cyber eval, incident report on unsanctioned agent behaviour during cyber testing (leads).

### 2c. dualuse.dev — open-weight models on unpublished 0-days (2026-04-17)
Key claims from the fetched page: **GLM 5.1 topped their autonomous hacking benchmark, outperforming Opus 4.6**; **Qwen 3.6 35B A3B — a size class the estate could run locally — was "surprisingly performant," scoring a full exploit in one scenario where GLM 5.1 and Opus 4.6 did not**, and the new 3.6 35B A3B outperforms the old-gen 397B A17B; **"Every agent had no refusals in its top-level agent after usage of a jailbreak system prompt. Some models, such as Opus 4.6, had a high rate of refusals in subagents"**; DeepSeek v3.2 lacked agentic persistence without continuous prompting.

### 2d. Dearbhadh (raesene) — k8s pentest leaderboard incl. the exact "Opus 4.6 era" + local models
Fetched `https://raesene.github.io/dearbhadh/reports/pentest/` and `leaderboard.html` (curl → local html, parsed). Scenarios: exploit vulnerable k8s clusters, extract CA private key within 15 min; ~46 models tested incl. Claude Opus 4.6/4.7/4.8, GLM-5.2/5.3, DeepSeek V3.2/V4*, Kimi, and **Qwen3.6-35b-a3b (LOCAL), Gemma 4 31B (LOCAL)**. Cross-test table (model | quiz | manifest | cluster | pentest | avg):
- **Claude Opus 4.6: pentest rank 1st (tied), avg 9.5** — the old Opus 4.6-era Claude was best-in-class on offensive k8s work and (per scenario notes) fully complied, extracting CA keys.
- Claude Opus 4.7: pentest 22nd; **Opus 4.8: 24th**; Claude Sonnet 5: 35th; GPT 5.5/6 Astra: 40th → the Claude/GPT series regressed hard on pentest after the 4.6 era.
- GLM-5.3: pentest **6th** (avg 13.75); GLM-5.2: 13th; Claude Sonnet 4.6: 6th; DeepSeek V4 Pro 0813: 11th; DeepSeek V3.2: 31st.
- **Local: Qwen3.6-35b-a3b (LOCAL) pentest 26th, cluster 15th; Gemma 4 31B (LOCAL) pentest 35th**; MiniMax M2.5 34th, Tencent HY3 29th.
- Top pentest ties at 1st: Qwen 3.8 Max 0902, DeepSeek V4.1 Flash, Claude Opus 4.6, Qwen 3.8 Max, Kimi K3.

### 2e. Shellvoide KLUE — four frontier models, same live target, 30-min budget (2026-06-22)
Fetched `https://shellvoide.com/blog/glm-deepseek-kimi-opus-pentest-benchmark/` → `out/research/shellvoide.html` (22,144 chars). Live WordPress/WooCommerce + bespoke REST API behind Cloudflare challenge: **Opus 4.8: 9 findings, 0 critical, risk verdict Low** (best false-positive discipline: "a catalogue of clean rule-outs"); **DeepSeek V4 Pro: 14 findings, 2 critical, verdict Critical** ("highest ceiling, the most reach, the most noise"); **Kimi K2.7: 8 findings, 1 critical**; **GLM 5.2: 9 findings, 2 high, Medium — nicknamed "the unfiltered one"**: only model to pull an exposed third-party API key from a configuration endpoint and a static credential baked into the front end. Pricing quoted: Opus 4.8 $5/$25 per MTok (1M ctx). Conclusion: price does not predict result.

### 2f. Unit 42 event (via valueaddvc.com, fetched): Palo Alto Unit 42 found a China-based actor ran **DeepSeek inside an open-source agent framework to autonomously scan/exploit** while Claude and OpenAI models refused the same tasks — the canonical real-world refusal asymmetry.

### Synthesis for the estate cascade
- **Local qwen tier**: qwen3:4b is weaker than every benchmarked tier (RedLineBench's 27B base refuses 11-13% and scores 3.7; dearbhadh's 35B local ranks mid-pack) — fine for routing/enrichment/rule-adjacent calls (PentestChain got 96.4% first-tier success with qwen2.5:7b on bounded roles), not for exploit reasoning.
- **GLM**: refuses 35-39% of naked offensive prompts (worst tier except gemma) but answers at 4.45-4.63 quality when it complies, and its output-side filter is the dominant failure mode (§3). AISI rates GLM-5.2 ≈ Opus 4.6 on capability at 40% of the cost.
- **DeepSeek**: lowest refusal (5-7%) + best blended quality + $0.28/solved-task — the offensive workhorse; noise needs a verifier (Shellvoide: "most noise").
- **Old Claude (Opus 4.6 era)**: 1st-place pentest rank, no top-level refusals with a jailbreak system prompt but high subagent refusal rates (dualuse.dev); successors 4.7/4.8 collapse to 22nd-24th and Opus 4.8 refuses even as a benchmark judge. "Opus 4.6 era" is gone; treat Claude as the disciplined triage/verify tier, not the exploit tier.

---

## 3. Output-filtering workarounds (models that answer but get filtered)

- **GLM / z.ai — `finish_reason: "sensitive"`**: Zhipu returns two non-standard finish reasons (`network_error`, `sensitive` = content-policy trip on OUTPUT). pydantic-ai issue #7678 (closed, 2026-08-21; read via `gh api repos/pydantic/pydantic-ai/issues/7678` + comments): "content policy violation / sensitive content triggered … any partial tokens produced before the crash are lost"; fixed by PR #7685 mapping `sensitive → content_filter`. LiteLLM hit the same: issue #23386, fixed in PR #24373 (merged 2026-03-22, "map Zhipu GLM non-standard finish_reason values"). llmgateway PR #2809 "fix(zai): map content filter + drop temperature". **Estate action**: normalize `sensitive`/`network_error` at the gateway before OpenAI-SDK validation, treat `content_filter` as a cascade-escalation trigger (PentestChain's call_ai_fast already escalates on non-200 — extend the predicate to filtered/invalid output).
- **Claude — "Output blocked by content filtering policy"**: anthropics/claude-code #59796 (read via gh api): intermittent since ~2026-05-16, blocks benign output, "Retrying ('Try again') sometimes succeeds" → **retry-on-filter is the community-validated workaround**; duplicates #59616/#57631/#55596; siblings #17389, #26857 (blocked while generating an ISO country-code dictionary), #25934, #36184 (all found via DDG, §Q20).
- **Retry-on-refusal**: AISI circumvented DeepSeek V4-Pro refusals "simply via a small number of repeat attempts" (§2b). Cheapest workaround; no prompt change needed for the low-refusal tier.
- **Encoding strategies (input- and output-side)**: promptfoo ships a red-team base64 strategy (`promptfoo/promptfoo` `site/docs/red-team/strategies/base64.md`); LLAMATOR (`LLAMATOR-Core/llamator`, `src/llamator/attacks/` listing read via gh api) implements 27 strategies incl. `base64_injection.py`, `repetition_token.py`, `suffix.py`, `pair.py`, `harmbench.py`, `autodan_turbo.py`, `ucar.py`, `dan.py`. General background: AWS Bedrock Guardrails encoding-attack post (defensive mirror of the same technique), austa.ai encoding-smuggling writeup (both found via Exa §Q19/Q3, not deep-read).
- **Jailbreak system prompt at the top level + permissive subagent models**: dualuse.dev's pattern — top-level agent with jailbreak prompt had zero refusals across tested models; Opus 4.6's refusals concentrated in subagents → route subagent calls to low-refusal tiers (DeepSeek/local abliterated).
- **Abliterated local tier**: RedLineBench's Huihui-35B-A3B (abliterated) refuses 7%/3% with 3.79-3.95 quality — the local escape hatch when cloud tiers filter.
- **LinkedIn lead (not fetched — auth wall)**: Atul R V, "Bypassing output filtering in Deepseek AI" (bug-bounty post, found via Exa §Q19). Listed as a lead only.

---

## 4. Cascade / routing tooling sweep

- **lemony-ai/cascadeflow** — 3999★, MIT, Python+TS, pushed 2026-09-25. "Cascading runtime for AI agents. Optimize cost, latency, quality, and policy decisions inside the agent loop." Claims 69% (MT-Bench) / 93% (GSM8K) cost savings retaining 96% GPT-5 quality; `pip install cascadeflow`; LangChain/LangGraph, OpenAI Agents, CrewAI, Vercel AI, n8n integrations → drops directly onto Decepticon's LangGraph. `gh api repos/lemony-ai/cascadeflow` + README read.
- **BerriAI/litellm** — 59,867★, pushed 2026-09-29. Gateway/router with fallbacks, cost tracking, and the zhipu `sensitive→content_filter` mapping (PR #24373) — the normalization the estate needs for GLM lanes.
- **seanpoyner/llm-cost-routing** — empirical harness + 2 papers (README read): on agentic τ-bench, **predictive difficulty routing performs at/below random; oracle escalate-on-failure cascades score 0.727-0.753 vs 0.628 always-strong; best judge recall ~0.60 is the binding constraint**. Design law for the estate: don't predict-route pentest subtasks — escalate on failure and invest in the verifier.
- **jadberro/CascadeGateway** — 4★, MIT, Python 3.10+. Hardware-adaptive Ollama-first cascade w/ 3-token-lookahead failover to cloud, MCP protocol support, "$0 token cost" local tier — closest small repo to the estate's shape.
- **mnfst/awesome-free-llm-apis** — 8648★, updated daily; the free-tier provider list a PentestChain-style cascade feeds on.
- **mozilla-ai/otari** (494★) self-hosted OpenAI-compatible gateway w/ budgets; **Inebrio/Routerly** (97★) multi-policy router w/ Ollama + cost tracking; **thushan/olla** (311★) local/remote LB proxy; **sbproxy** (53★) 72-provider gateway.
- Pentest-side: **maso-soup/pt-bench** (0★, 2026-09-01) modular harness comparing pentest agent designs AND models against vulnerable targets (subprocess adapter — but targets typically need Docker, which this VM lacks); **S1N6H/pentest-harness** (400★) BYO-model self-hosted pentest agent harness; **ferniths/pentest-ai** (0★) Ollama-only pentest agent with swappable model pair + laya routing; **felixda9/local-redteam-agent** local uncensored-model agent notes; **vchaplygim/cyber-ai-tips-and-tricks** "Using LLMs for cybersecurity without hitting constant refusals" (README is title-only so far).
- Papers (abstracts/leads, not deep-read): arXiv 2410.10347 unified routing+cascading; SATER (EMNLP 2025) self-aware token-efficient routing/cascading; AgentRouter 2609.22951 heterogeneous cost-optimal agentic routing; CascadeDebate 2604.12262; **2607.15263 "Beyond Success Rate: Cost-Aware Evaluation of Offensive and Defensive Security Agents"**; **2606.02644 "A New Framework for Cybersecurity Refusals in AI Agents"**; 2605.20351 systematic review of 13 malicious-code refusal corpora; evals.frontier.security (cost-aware security benchmarking site).
- Dead/stale: lm-sys/RouteLLM (5556★, last push 2024-08-10 — stale); `not-diamond/not-python` and `martianverse/martian` → gh 404.

---

## 5. Estate-fit notes (local grounding)

- Skill `cost-aware-llm-pipeline` (C:/Users/prekzursil/.agents/skills/cost-aware-llm-pipeline/SKILL.md, head read): complexity-based model selection + immutable CostRecord/CostTracker pattern — the estate's in-house cascade doctrine to extend with refusal/filtered-output escalation predicates.
- Skill `zai-lanes` (same dir, head read): free GLM web lane (`glm_chat` MCP, GLM-5.3-Flash class, serialized 5-20 s calls, don't use for >8k-word outputs) + official plan API lane — maps to cascade tiers 2-3.
- Recommended cascade for this estate (synthesis of the above, not yet run anywhere): qwen3:4b local (bounded roles, PentestChain-style) → free GLM web lane (enrichment/triage; normalize `finish_reason=sensitive`) → DeepSeek V4-class via cheapest entitled lane (exploit reasoning, retry-on-refusal ×2-3) → Opus-class ONLY as verifier/triage (lowest noise per Shellvoide; refusal-heavy on offensive asks) → deterministic rule fallback everywhere. Escalate on failure, never on predicted difficulty (llm-cost-routing Paper C). Measure locally with RedLineBench against 127.0.0.1:11434/v1 before committing.

---

## 6. Every query issued this session

| # | Backend | Query / call | Result |
|---|---|---|---|
| Q1 | Firecrawl POST /v1/search | "PentestChain LLM cascade pentest agent model routing" | **Unauthorized: Invalid token** — env FIRECRAWL_API_KEY is the literal unexpanded string `${FIRECRAWL_API_KEY}` (verified: len=20, od shows literal). Estate firecrawl is self-hosted behind mcp-proxy :31114 per agents.json, not a hosted REST key |
| Q2 | Exa | "cost-aware model routing cascade for penetration testing LLM agents refusal rate comparison" | 10 results (cacr repo, arXiv 2410.10347, SATER, AgentRouter 2609.22951, BhaveshBytess/cascade mirror, dreaming.press router post, CascadeDebate) |
| Q3 | gh api | search/repositories q=PentestChain | 1 repo (PenTestChainStudio-1, 0★) |
| Q4 | Exa | "PentestChain multi-agent penetration testing framework LLM" | **arXiv 2609.18120 found** + PentestAgent 2411.05185, AutoPentest 2505.10321, LLM4Pentest |
| Q5 | HN Algolia | http then https: "PentestChain", "LLM refusal pentest" | http empty/error; https ran → **0 hits both** |
| Q6 | gh api | search/repositories q=LLM+refusal+cybersecurity sort=updated | **RedLineBench found** + 9 others (PrometheusBench, cyber-ai-tips-and-tricks, Mithra-Scanner…) |
| Q7 | gh api | repos/cracken-ai/redline-bench + readme (two slices 0-6000, 6000-14000) | full refusal/quality tables captured |
| Q8 | curl | arxiv.org/pdf/2609.18120 + pypdf extract | 13-page text extracted |
| Q9 | Exa | "GLM-4 DeepSeek Claude refusal rate comparison offensive security exploit code benchmark which model refuses pentest tasks" | arXiv 2607.15263, shellvoide, dualuse.dev, valueaddvc, winbuzzer/AISI, neoresearch GLM/DeepSeek safety evals |
| Q10 | gh api | repos q=PentestChain in:name,description,readme + code q=PentestChain in:file | 5 repos / 108 code files (impls + derived briefs) |
| Q11 | gh api | vchaplygim/cyber-ai-tips-and-tricks readme; Rushabh0508/Pentest-Chain | title-only README; 0★ repo |
| Q12 | local grep | cascade/cost/refus/filter on pentestchain.txt | sections extracted (lines cited above) |
| Q13 | curl | raesene.github.io/dearbhadh /reports/pentest/ + leaderboard.html (+ webReader etcd-noauth attempt) | webReader hit MCP -429 rate limit; curl got index + leaderboard; scenario page not read |
| Q14 | Exa | "AISI UK cyber evaluation open-weight models exploit benchmark refusals Anthropic OpenAI 2026" | AISI blogs + CSA note + winbuzzer |
| Q15 | Exa | "CyberSecEval offensive capability refusal rate comparison models 2025 2026" | arXiv 2606.02644, 2605.20351, CyberSecEval 2/3, evals.frontier.security |
| Q16 | Reddit | search.json "GLM refusal pentest exploit" | **blocked** (non-JSON response) |
| Q17 | curl | aisi.gov.uk open-weight cyber blog | full text captured |
| Q18 | arXiv export API | id_list=2606.02644 | **empty** (no title/abstract returned) |
| Q19 | Exa | "z.ai GLM output side safety filter cuts off response mid answer…" | pydantic-ai #7678, llmgateway PR #2809, docs.z.ai, glm-ai.chat error pages |
| Q20 | DDG (python ddgs) | Claude output filter blocked response exploit code workaround | claude-code issues #59796 #17389 #26857 #25934 #36184 + how-to posts |
| Q21 | gh api | pydantic-ai issues/7678 + comments | full mechanics + fix trail |
| Q22 | gh api | anthropics/claude-code issues/59796 + comments | blocked-benign-output + retry workaround + dup ids |
| Q23 | gh api | litellm pulls/24373; LLAMATOR attacks dir | fix confirmed merged 2026-03-22; 27 attack modules listed |
| Q24 | local read | skills cost-aware-llm-pipeline/SKILL.md, zai-lanes/SKILL.md (head) | estate doctrine + lanes captured |
| Q25 | gh api | topic:llm-routing sort=stars; q=llm+cascade+cost | cascadeflow, awesome-free-llm-apis, otari, Routerly, olla, RouterArena… |
| Q26 | gh api | BerriAI/litellm, lm-sys/RouteLLM, not-diamond/not-python, martianverse/martian | litellm+RouteLLM ok; **not-diamond & martian 404** |
| Q27 | gh api | lemony-ai/cascadeflow + readme; seanpoyner/llm-cost-routing readme; jadberro/CascadeGateway readme | all read |
| Q28 | Exa | Chinese: "GLM DeepSeek 拒绝 渗透测试 漏洞利用 大模型 安全 对比 拒答率" | only generic model-comparison sites (artificialanalysis, benchlm, faun.dev) — **no refusal-specific Chinese source found** |
| Q29 | gh api | q=model+refusal+OR+abstention+OR+router+pentest+agent created:>2026-04-01 sort=updated | pt-bench, pentest-harness, ferniths/pentest-ai, local-redteam-agent, SploitAgent… |
| Q30 | curl | shellvoide.com KLUE article (+2 extraction passes) | findings table, pricing, per-model reads |

### Dead ends / not reached
- Firecrawl hosted search (invalid literal key, §Q1). Reddit search API (blocked). HN Algolia (zero hits). arXiv export API for 2606.02644 (empty). not-diamond / martian repos (404). LinkedIn DeepSeek output-filter post (auth wall). Dearbhadh per-scenario pages (rate-limited then deprioritized). Read-tool PDF pages (not configured; substituted pypdf). Chinese-language refusal-specific source (nothing beyond generic comparisons).