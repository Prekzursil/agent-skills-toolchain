# Lens 08 - eval-harness + autoresearch for model endpoints

*Gem-hunt lens (discovery, not a build). Repo: Prekzursil/agent-skills-toolchain. Hunt: 2026-09-02 hosted-models.*
*Status: COMPLETE - all eight sections researched and pushed incrementally (5 commits).*

## 0. Scope, dedup-set and estate locks (constraints this lens designs under)

**Legend used throughout.** Each claim carries `[tier.corroboration.date]`: tier A = primary/official/peer-reviewed, B = reputable secondary (GitHub README, major docs mirror), C = blog/wiki/aggregator; `corrob` = 2+ independent sources agree, `single` = one source, `UNVERIFIED` = recalled or not fetched this run. `FACT` = sourced; `INFER` = my inference from sourced facts; `REC` = recommendation. Today = 2026-09-02.

**What this lens is.** A design for (a) an eval suite that grades *any endpoint registered in the estate* on seven axes and (b) an autoresearch loop that tunes the *routing policy* (which endpoint serves which task class) to maximize a routing score under a spend cap. Discovery only; nothing here is built.

**Dedup - what already exists and is NOT re-proposed (verified on disk this run):**

- `skills/hosted-model-agents/evals.md` on `origin/live-capture/2026-09-02` is a **skill-pressure eval** (5 pressures, "would the agent repeat the 29.08.2026 miss") plus disk checks - it grades agent *behaviour under a prompt*, not an endpoint's tool-call/JSON/latency/cost. `[A.single.2026-09 - read from git]` This lens grades *endpoints*; the two compose (the pressure evals become one task class in Section 2). `INFER`
- `tools/mcp/glm53-space` (one tool `glm53_chat`, mini OpenAI proxy, hardcoded `router.huggingface.co/v1` + `zai-org/GLM-5.3`) - owner has decided to deprecate it in favour of a general integration layer. It is **not on `origin/main`** today (`ls tools/mcp/glm53-space` is empty), but `glm53-space` is still a key in `.agents/agents.json` `mcp.servers` (42 servers). `[A.single.2026-09 - read from disk]` The eval suite below is exactly the acceptance test any replacement integration layer must pass. `INFER`
- `platform/routing/MEASUREMENTS.json` + `hooks/semantic-router/{eval.py,test_eval.py,route.py,success.py,observe.py}` already implement a **retrieval-quality eval** (precision@k / recall@k / gold-hit-rate over a 60-query L1-L4 set, 912-item index) for the *skill/command* router. `[A.single.2026-09 - read from disk]` That is routing of *prompts to skills*; this lens is routing of *tasks to model endpoints*. Its eval shape (gold set, tiers, `failures[]` with qid+query, floor_violations) is the house style to copy, not a duplicate. `INFER`
- `.agents/skills/autoresearch/SKILL.md` already defines the loop contract (commit-before-measure, log-before-revert, revert on any regression, 3-discards-in-a-row review, ~8-variant plateau rule, `.autoresearch/log.tsv` with `variant sha status <axes...> hypothesis`, `.autoresearch/` git-ignored). `[A.single.2026-09 - read from disk]` Section 4 *instantiates* that contract for a routing-policy file; it does not fork the skill.
- `.agents/skills/eval-harness/SKILL.md` defines grader types (code / rule / model / human), pass@k vs pass^k, thresholds (capability pass@3 >= 0.90, regression pass^3 = 1.00), anti-patterns (flaky graders in release gates, ignoring cost/latency drift). `[A.single.2026-09 - read from disk]` Section 2 reuses that vocabulary verbatim.
- `.agents/skills/openrouter-routing/SKILL.md` already has the T0/T1 tiering, "escalate one-way, never mid-tool-call fallback up the tier", and the hard daily+monthly spend-cap checklist. `[A.single.2026-09 - read from disk]`

**Estate locks this lens designs under (hard; cited as constraints from the task brief, not re-litigated):**

1. OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP. => The eval runner may *call* OpenRouter endpoints as one registered endpoint class under the existing cap; it may not become a router in front of Cursor or Claude.
2. No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory. => The eval runner and the autoresearch loop are **plain Python + git + TSV**; no eval SaaS, no proxy layer, no new daemon. (This rules out adopting promptfoo/inspect/DeepEval *as a runtime*; borrowing their *grader ideas* is fine - Section 5.)
3. `auth2api :8317` stays the ONLY Cursor bridge and retires within 7 days of an official Cursor `/v1` GA. => Cursor-quota endpoints (`cursor-*` model ids) are graded through `:8317` like any other OpenAI-compatible endpoint, and the registry entry must carry a `sunset_on: cursor_v1_ga` flag so the loop never "optimizes into" a soon-dead bridge.
4. Ports 8765/8812/8317 are owned. => The runner opens no port; fakes in CI are in-process, not a mock server on a port.
5. `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it). => Grader prompts (model-graded axes) live under a skill folder, not in a Python string.
6. Never rotate credentials; secrets by name only in `.agents/local.json`. => The runner reads secret *names* from the registry and resolves them from env; live runs are opt-in.
7. Never remove a feature to buy reliability - present tradeoffs. => Every routing-policy change the loop proposes is a *tradeoff row* (quality vs cost vs latency), never a "drop endpoint X".
8. Box constraints: Windows 11, 31.6 GB RAM, chronically memory-starved, no GPU assumed. => Local endpoints (ollama, LM Studio `lms`, llama.cpp) are graded on the *same* suite but with a `local` tag; the runner is single-process and streams results to disk so a 12-minute death loses at most one task.

## 1. Prior art - what the field already measures and how (cited)

| Prior art | What it measures / how | What this lens borrows | Grade |
|---|---|---|---|
| **BFCL v4** (Berkeley Function Calling Leaderboard, Gorilla) | Categories *simple / multiple / parallel / parallel-multiple / irrelevance* (+ live variants, multi-turn, format-sensitivity). AST accuracy = parsed call matches gold (function name, every predicted param is real, every gold param value in its acceptable list; `""` in the list marks optional). Parallel = order-independent 1:1 match of all calls. Irrelevance = model must NOT call; relevance = must call. ~2k question-function-answer pairs across Python/Java/JS/REST. | The whole **tool-call fidelity** axis (Section 2.1): AST-style code grader, parallel 1:1 matching, irrelevance-as-refusal. | FACT `[A.corrob.2026]` gorilla.cs.berkeley.edu [S1]; HF dataset overview [S2]; open-source AST-scorer port showing the exact matching rule [S3]; secondary summary [S4] |
| **tau-bench / tau2-bench** (Sierra) | Agent+tools+simulated user; grade by *final database state* vs gold, not by transcript. Introduces **pass^k** = P(all k i.i.d. trials succeed), averaged over tasks; unbiased estimator `E_task[C(c,k)/C(n,k)]`; pass^1 = pass@1 = E[c/n]. GPT-4o < 50% tasks, pass^8 < 25% retail (2024). tau2-bench (2025-06) adds dual-control; leaderboard recommends n >= 4 trials. | **pass^k as the reliability target** for every axis that gates a tier; state-based grading for the tool-loop task class. | FACT `[A.corrob.2024-2025]` arXiv 2406.12045 [S5]; ICLR 2025 paper [S6]; tau2-bench summary [S7-C]; 2026-07 replication with n=8 [S8-C] |
| **HELM** (Stanford CRFM) | Multi-metric by design: 7 metrics (accuracy, calibration, robustness, fairness, bias, toxicity, **efficiency**) x scenarios; all prompts/completions released; living leaderboards (Capabilities, Safety). Open framework with unified model adapters. | The **"never a single number" discipline**: report the vector, derive the scalar (routing score) *from* it, never the reverse. Also: efficiency (latency/cost) is a first-class metric, not an afterthought. | FACT `[A.corrob.2022-2026]` github stanford-crfm/helm [S9]; HELM paper [S10 - 2022, dated]. SEA-HELM (2026-08) adds 8-run averaging + bootstrap CIs + Bradley-Terry Elo [S11-B] |
| **LMArena** (ex-Chatbot Arena) | Crowd pairwise votes -> Bradley-Terry ratings with style control (length/markdown confounders). | Only as a **prior for the initial policy**, never as a grader: arena preference != tool-call fidelity. Pairwise BT is the right aggregator *if* we ever do model-graded pairwise preference between two endpoints on the same task. | FACT `[A.corrob.2024-2026]` open-sourced `arena-rank` (contextual Bradley-Terry, closed-form 95% CIs) [S35]; style-control method [S36] |
| **Artificial Analysis** | API-provider leaderboard over 500+ endpoints: TTFT ("first chunk"; for reasoning models = first reasoning token), output tokens/s (last 80% of chunks for hidden-reasoning models), end-to-end time; **median (P50) over rolling 72h**, default workload **10k input tokens** since 2026-03-02; measured from GCP us-central1-a incl. network. | Definitions for the **latency axis** (TTFT, output speed, E2E) and the honesty that a 1-box home measurement is *our* p50/p95 from *our* network, not theirs. | FACT `[A.single.2026-03]` methodology page [S12]; leaderboard columns [S13]; 2026-08-30 snapshot table [S14-C] |
| **OpenAI Structured Outputs / JSON mode** | `strict: true` + `json_schema` => constrained decoding, 100% schema adherence on the *supported subset*; JSON mode only guarantees valid JSON, not schema. Response carries a separate **`refusal`** field when the model refuses inside a structured call. | The **JSON axis** grades three things separately: valid-JSON rate, schema-valid rate, and *silent fallback* (schema accepted but unsupported => unguided). And: refusal must be detected as a field, not as text. | FACT `[A.corrob.2024-2026]` OpenAI announcement [S15]; current guide [S16]; JSONSchemaBench summaries: OpenAI 100% compliance but low empirical coverage on developer schemas (~29%), Guidance ~96% coverage [S17-C][S18-C] |
| **LLMRouterBench** (ACL Findings 2026 / arXiv 2601.07206) | 33 models x 21 datasets, 1.8B tokens; metrics **PerfGain** (best accuracy over Best-Single), **CostSave** (max cost cut at >= Best-Single accuracy), Pareto frontier + **ParetoDist**. Finding: top routers reach ~+4% PerfGain / ~31.7% CostSave, but several routers **including OpenRouter `openrouter/auto` (-24.7% vs Best-Single)** fail to beat the best single model. | The **routing score** definition and the *null hypothesis the autoresearch loop must beat*: "route everything to the best single endpoint". Any policy that cannot beat Best-Single on our own task set is a discard. | FACT `[A.corrob.2026-01]` arXiv HTML [S19]; ACL PDF [S20]; repo [S21-B] |
| **OpenRouter rankings** | Ranked by `prompt_tokens + completion_tokens` processed through OpenRouter, daily UTC buckets, variants ranked separately, private traffic excluded; the page itself states "these rankings measure adoption, not quality". Data API `/api/v1/datasets/rankings-daily` (top-50/day). | Popularity is a **weak cold-start prior** for candidate ordering only; it never enters the score. Their per-response `usage.cost` and `/generation` metadata ARE the trusted cost source (Section 2.5). | FACT `[A.corrob.2026-09]` rankings page (bucket dated Sep 1 2026) [S40]; Data API docs [S41] |
| **Karpathy `autoresearch`** (2026-03) | One editable file (`train.py`), one metric (`val_bpb`), fixed 5-min budget, loop: edit -> `git commit` -> run -> read metric -> keep (advance branch) or `git reset --hard HEAD~1`; `results.tsv` untracked, columns `commit val_bpb memory_gb status{keep,discard,crash} description`; soft constraint on peak VRAM; simplicity tiebreak (0.001 gain with 20 hacky lines = discard; equal with simpler code = keep); 10-min kill timeout. | Confirms the house `autoresearch` skill's contract is the field's contract; adds three things we adopt: **fixed measurement budget per variant**, **soft-constraint axis** (here: spend), **simplicity tiebreak** written into the policy diff review. | FACT `[A.corrob.2026-03]` program.md at pinned commit [S22]; repo README [S23]; secondary walk-throughs [S24-C][S25-C] |
| **`pass@k` estimator** (Chen et al. 2021, Codex) | Unbiased `1 - C(n-c,k)/C(n,k)` with n > k samples. | Used for the *capability* thresholds; tau-bench's pass^k for *reliability* thresholds. | FACT `[A.single.2021 - dated, canonical]` cited via tau-bench [S5] |

**Gap the prior art leaves for THIS estate (INFER):** every public harness grades *models*; none grades *our registry entries* - an endpoint = (provider, model id, base URL, auth name, bridge such as `:8317`, quota class, sunset flag). Two entries can share a model and differ in every operational axis (Cursor-bridged Claude vs direct Claude; HF Space vs HF Endpoint for the same weights). The unit of evaluation here is therefore the **registry entry**, and the routing policy is a map `task_class -> ordered endpoint list`, which is exactly the object the autoresearch loop edits.

## 2. The endpoint eval suite - seven axes, graders, pass@k / pass^k targets

**Unit under test:** one registry entry `E` = `{name, base_url, model, auth_secret_name, bridge?, quota_class, sunset_on?, local?}`. **Task classes** `T` (the house workloads the routing policy routes): `tool-loop` (multi-step MCP tool use), `extract-json` (T0 grunt: reformat/classify into a schema), `long-doc` (recall over a pasted doc/transcript), `code-edit` (single-file patch), `chat-short` (Q&A), `skill-pressure` (the 5 pressures from `hosted-model-agents/evals.md`, so the dedup-set's eval becomes a task class rather than a separate suite). `REC`

Every axis below reports a **vector** first (HELM discipline [S9]) and is graded by **code where the answer is checkable, by a model only where it is not** (`eval-harness` rule 4). Thresholds use the house vocabulary: `pass@k` (capability, `>= 0.90 at k=3`) and `pass^k` (reliability, tau-bench estimator `E_task[C(c,k)/C(n,k)]` with n >= 4 trials [S5][S6]); the tau-bench finding that pass^8 < 25% while pass^1 ~50% [S6] is the reason no axis may gate on a single trial. `FACT` -> `REC`.

### 2.1 Tool-call fidelity (code grader; BFCL-shaped [S1-S3])

| Sub-check | Grader | Gold | Target |
|---|---|---|---|
| `simple` - one tool, right name, args match | AST-style: name equal; every emitted arg is a declared param; every gold param value in its accepted-value list (`""` = optional) [S3] | 12 house tools sampled from the 42-server registry (basic-memory `write_note`, agent-mail, playwright, github...) with hand-written gold arg sets | pass^3 = 1.00 (gates any tier) |
| `multiple` - pick 1 of N tools | same, penalize extra calls [S2] | N=5..12 tool menus | pass@3 >= 0.95 |
| `parallel` / `parallel-multiple` - several calls in ONE response | order-independent 1:1 match of all calls [S3]; **also record** whether the endpoint emitted them in one turn or serialized them (a latency fact, not a correctness fail) | 20 items | pass@3 >= 0.90; report `parallel_native_rate` separately |
| `irrelevance` - no tool fits, must NOT call | zero calls emitted [S3] | 20 items | false-call rate <= 0.05 |
| `schema-strict` - args must validate against the tool's JSON Schema | `jsonschema` validate on every emitted `arguments` blob (catches stringified JSON, wrong enum, missing required) | derived from tool schemas already in the registry | invalid-arg rate <= 0.02 |
| `bridge-passthrough` - does `:8317` / the HF-Space proxy / Foundry preserve `tool_calls` and `tool_call_id` round-trip? | diff the raw wire JSON before/after the bridge | same items as `simple` | binary per bridge; a bridge that strips tool calls is graded **capability-absent**, not "fails" (lock 7: tradeoff, not removal) |

**Why THIS estate:** the owner's two known outages were exactly bridge-shaped (a Space `/v1` that is inference-only; a `:8317` wrapper set). `INFER` from the dedup-set description. BFCL grades models on their native API; only we can grade *our bridges*. The `glm53-space` replacement must pass `bridge-passthrough` before it is registered. `REC`

### 2.2 JSON mode / structured output (code grader; three separate rates)

Report **(a)** `valid_json_rate` (parses), **(b)** `schema_valid_rate` (`jsonschema` against the requested schema), **(c)** `strict_mode_honoured` = whether the endpoint accepted `response_format: {type: json_schema, strict: true}` at all, and whether the schema we sent is inside the provider's supported subset (OpenAI rejects/falls back on some `anyOf`/`$ref`/`unevaluatedProperties` patterns; JSONSchemaBench reports ~29% empirical coverage on developer-authored schemas for OpenAI strict mode vs 100% compliance on accepted ones) [S15][S16][S17][S18]. **(d)** `refusal_field_rate`: OpenAI returns refusals in a separate `refusal` field inside structured calls [S16]; a bridge that flattens that into `content` breaks every downstream parser - grade it. `FACT` -> `REC`

Gold: 15 house schemas taken from the repo's own manifests (`agents.json` entries, `.autoresearch/log.tsv` rows as JSON, the fan-out schema in `tools/fanout-schema`) so the suite tests schemas we actually emit, per JSONSchemaBench's "benchmark on your own schemas" corrective [S18]. Target: `schema_valid_rate` pass^3 = 1.00 for any endpoint routed for `extract-json`; local llama.cpp/ollama endpoints get the same test with grammar/constrained decoding on and off (two registry entries). `REC`

### 2.3 Long-context recall (code grader; RULER-shaped, our sizes)

Sweep input length {4k, 16k, 32k, 64k, 128k} x needle depth {10%, 50%, 90%} with **multi-key / multi-value needles** (RULER `num_needle_k`, `num_needle_v`), plus one *aggregation* task (count/sum over planted facts), because vanilla single-needle NIAH saturates while multi-hop degrades [S26][S27]. Report the **effective context** = largest length where accuracy stays >= 85% of the endpoint's own 4k score (NoLiMa-style self-relative threshold [S28-C]) - never the advertised window. `FACT` -> `REC`. Haystack = the repo's own docs (contamination-resistant, and the failure mode we care about is "lost my own AGENTS.md rule at 60k"). Target: effective context >= 32k for any endpoint routed for `long-doc`; report the number, do not gate above 32k (memory-starved box, lock 8). `REC`

### 2.4 Latency p50 / p95 (code grader; Artificial Analysis definitions, our network)

Per request record `ttft_ms` (first streamed chunk; for reasoning models the first reasoning token [S12]), `output_tps` (tokens/s after first token; last-80%-of-chunks rule for hidden-reasoning endpoints [S12]), `e2e_ms`. Aggregate **p50 and p95 over a rolling window** (AA uses P50 over 72h and 10k-input default workload [S12]; we add p95 because tail latency is what kills a 30-tool agent loop, a point made independently by practitioner write-ups [S14-C][S29-C]). Fixed workload shapes: `1k-in/200-out`, `10k-in/200-out`, `tool-turn` (2k-in, ~50-out tool call). Minimum n=20 per shape per window before a p95 is trusted (below that, report `insufficient`). `FACT` -> `REC`. **Why THIS estate:** the `:8317` bridge, the HF Space cold start, and Foundry all add hops AA never sees; only a local probe measures *our* p95. `INFER`

### 2.5 Cost per task (code grader; three provenance classes)

`cost_usd_per_task` = sum over the task's calls of (prompt_tokens x in_price + completion_tokens x out_price + reasoning/cached adjustments). Provenance, in order of trust: **(1) provider-reported** - OpenRouter returns a `usage` object with `cost` and `cost_details.upstream_inference_cost`, native tokenizer counts, reasoning and cached tokens, and the `/generation` endpoint returns `native_tokens_*`, `latency`, `generation_time`, `total_cost` by generation id [S30][S31]; **(2) list-price computed** - tokens from the response x a price table in the registry entry (must carry `price_as_of`); **(3) quota-class** - Cursor `:8317` and HF free tiers have no dollar price; record `quota_units` (requests) and mark `cost_usd = null`, never 0 (a null cost cannot be optimized into "free forever"; lock 3's sunset flag rides along). `FACT` -> `REC`

### 2.6 Refusal behaviour (code grader first, model grader second)

Two-sided, XSTest-shaped: a **safe-but-scary** set (should comply) and an **unsafe** set (should refuse) [S32]. Because string-matching refusals produces false positives ("I'm sorry to hear about your hamster" counted as refusal) and GPT-4-judging loses *partial* refusals [S32], grade in two passes: (1) code - the structured `refusal` field / `finish_reason` / tool-call-absence signals; (2) model grader with the house prompt for anything the code pass marks ambiguous, majority-of-3 graders (inspect_ai's multi-model vote pattern [S33]) using *endpoints from a different provider than the one under test*. Known caveat to write into the suite: ~51% of OR-Bench "benign" prompts were judged harmful by humans [S34], so the house safe-set must be **owner-authored from real refused-but-legit work prompts** (RE/security, BC-modding, pharmacology) rather than imported. Targets: over-refusal rate <= 0.05 on the house safe-set; under-refusal <= 0.02 on the unsafe-set; report both, gate neither globally (the right refusal profile depends on task class). `FACT` -> `REC`

### 2.7 Routing score (derived, Section 3) - and the two axes deliberately NOT here

No *general knowledge* (MMLU-style) axis and no *arena preference* axis: the first is a model property already published by HELM/AA [S9][S13], the second measures style-confounded human preference (LMArena controls for length/markdown with contextual Bradley-Terry [S35][S36]) - neither changes with our bridges, so measuring them locally is spend without information. `INFER`

## 3. The routing score - one number per endpoint per task class

**Definition (REC).** For endpoint `E` and task class `T`:

```
quality(E,T)   = weighted pass^3 over the axes T declares load-bearing   (0..1; e.g. tool-loop: 0.5 tool-fidelity + 0.3 schema-strict + 0.2 refusal-safe)
speed(E,T)     = clamp(1 - p95_e2e / p95_budget(T), 0, 1)               (budget per task class, e.g. tool-turn 6 s, long-doc 60 s)
cost(E,T)      = clamp(1 - cost_per_task / cost_budget(T), 0, 1)        (null cost -> use quota_units / quota_budget)
routing_score(E,T) = quality^a * speed^b * cost^c                       (geometric: any axis at 0 zeroes the score - no "cheap but wrong")
```

with per-class exponents `(a,b,c)` stored in the same policy file the loop edits (default `(1, 0.3, 0.3)`), and a **hard floor** `quality >= floor(T)` below which the endpoint is *ineligible* regardless of score (tau-bench: reliability is not a knob to trade [S6]). `REC`

**Policy-level score (what the loop maximizes).** Given policy `P: T -> ordered [E1, E2, ...]` (E2 is the one-way escalation target per `openrouter-routing`'s "escalate one-way, never mid-tool-call fallback up" [disk]):

```
policy_score(P) = sum_T weight(T) * routing_score(P[T][0], T)     subject to  sum_T expected_spend(P[T], T) <= spend_cap
```

and, borrowing LLMRouterBench's yardsticks [S19][S20]: report **PerfGain(P) = quality(P)/quality(BestSingle) - 1** and **CostSave(P) = 1 - cost(P)/cost(BestSingle)**, where BestSingle = the single endpoint that maximizes summed quality under the same cap. A policy with PerfGain < 0 *and* CostSave <= 0 is a discard by construction. `FACT` (metrics) -> `REC` (use as null hypothesis). Noise margin: an improvement counts only if it clears the bootstrap 95% CI of the previous best (SEA-HELM's 8-run + bootstrap pattern [S11]); with n=4 trials per task the CI is wide, so the loop's default is "needs > 1 percentage point *and* CI non-overlap". `REC`

## 4. The autoresearch loop over the registry routing policy

**The object under optimization is ONE file** (Karpathy's "one editable file" rule [S22][S23]): a routing-policy document, proposed as `.agents/routing-policy.json` next to `agents.json` (same closed-schema discipline the AGENTS.md conventions demand; provenance goes to `.provenance/`, never into the manifest). It maps `task_class -> {primary, escalate_to, floors, exponents, spend_share}` and points at registry entries **by name** - it never holds URLs or secrets. The eval runner + registry are read-only to the loop. `REC`

**Metric** = `policy_score(P)` from Section 3, printed by one command (`python tools/endpoint-eval/score_policy.py --policy .agents/routing-policy.json --trials 4 --window 72h`; a proposed command, built in WU-13 of the build wave) <!-- published-command-example: tools/endpoint-eval/score_policy.py -->, which also prints every axis the gate tracks. **Fixed measurement budget per variant** (Karpathy: 5-min wall clock, 10-min kill [S22]): here **spend-bounded, not time-bounded** - each variant may consume at most `cap/40` USD of OpenRouter/HF spend and at most `N` Cursor quota units, then the runner stops sampling and reports `insufficient` for anything below n=4. A variant that hits the budget before finishing is a **CRASH**, not a discard. `REC`

**Loop (the house `autoresearch` skill's contract [disk], instantiated):**

```
0  RESUME CHECK  - if .autoresearch/log.tsv exists: print best-vs-baseline, ask resume/fresh
1  BASELINE      - variant #0 = current policy, no edit; also compute BestSingle under the cap  (both logged)
2  THINK         - one hypothesis, one variable: e.g. "route extract-json to <cheap OR endpoint> instead of cursor-*"
3  COMMIT FIRST  - edit routing-policy.json; git add; git commit -m "autoresearch #N: <hypothesis>"
4  MEASURE       - run score_policy.py; if the chain fails or the spend budget trips -> CRASH
5  COMPARE       - every tracked axis >= baseline (policy_score, per-class quality floors, spend <= cap, p95 <= budget)
                  and policy_score improved by > noise margin (CI non-overlap, Section 3)
6  DECIDE        - KEEP (advance) | DISCARD (log row FIRST, then git reset --hard HEAD~1) | CRASH (same reset, status=crash)
7  LOG           - append row before any reset
```

**`.autoresearch/log.tsv` semantics (columns are the contract; the file is untracked, `.autoresearch/` git-ignored per the skill):**

| column | meaning | rule |
|---|---|---|
| `variant` | integer, #0 = baseline | monotonic |
| `sha` | short commit of the policy variant | exists even for discards (reflog-recoverable) |
| `status` | `keep` / `discard` / `crash` / `insufficient` | `insufficient` = budget or n<4 stopped the measure; counts as neither keep nor discard and does not advance the plateau counter |
| `policy_score` | 6 decimals | 0.000000 on crash (Karpathy convention [S22]) |
| `spend_usd` | actual spend this variant, provider-reported where available (OpenRouter `usage.cost` [S30]) | must be <= per-variant budget or status=crash |
| `spend_cum_usd` | running total this run | the loop **stops** (not discards) when `spend_cum >= run_cap` |
| `quota_units` | Cursor `:8317` / free-tier requests consumed | tracked as its own soft axis (Karpathy's `peak_vram` analogue [S22]) |
| `perf_gain` / `cost_save` | vs BestSingle (LLMRouterBench yardsticks [S19]) | informational per row; gate only on policy_score + floors |
| `p95_worst_ms` | worst per-class p95 under this policy | must be <= class budget |
| `n_trials` | trials per task actually completed | < 4 => status=insufficient |
| `hypothesis` | one line | free text |

**Guardrails (mandatory; the skill's three plus four that are specific to spend and to endpoints):**

1. *3 discards in a row* -> stop and write a short review before the next variant (skill). 2. *Best unchanged for ~8 variants* -> plateau: invert the assumption (e.g. if "cheaper primary" kept failing floors, try "same primary, cheaper escalation") (skill). 3. *Anchor drift* -> `fresh-context-verify` on the baseline number, do not re-implement (skill).
4. **Spend guard (hard):** per-variant budget and run cap live in the policy file, are read not typed, and the runner refuses to start if `openrouter-routing`'s daily+monthly caps are not set on the key (that skill's checklist [disk]). The loop may not raise a cap. `REC`
5. **Sunset guard:** any registry entry with `sunset_on` set (the `:8317` bridge, lock 3) may be *primary* only if the policy also names a non-sunset `escalate_to`; a variant that routes a class *exclusively* to a sunset entry is an automatic discard. `REC`
6. **Availability guard (Goodhart on quota):** a variant that scores higher only because a rate-limited endpoint returned fewer, faster errors is caught by requiring `n_trials >= 4` per task and treating HTTP 429/5xx as `insufficient`, never as "fast". `REC` (motivated by LLMRouterBench's retry-to-10-then-zero handling for OpenRouter failures [S19])
7. **Simplicity tiebreak (Karpathy [S22]):** equal score with a simpler policy (fewer classes overridden, fewer exponents changed) = KEEP; a +0.001 score bought by a per-class special case = DISCARD. Written into the review step, not automated.
8. **No feature removal (lock 7):** the loop may reorder endpoints per class and change floors/exponents/spend shares; it may not delete a registry entry or a task class. A variant that "improves" by dropping `long-doc` from the weighted sum is a schema violation, caught by the closed policy schema. `REC`

**Termination:** target `policy_score` or max variants or run cap; wrap-up re-runs the metric on the best SHA and reports baseline-vs-best per axis, kept/discarded/crash counts, and the PerfGain/CostSave vs BestSingle. If PerfGain <= 0 and CostSave <= 0 after the run, the honest recommendation is **"route everything to BestSingle"** - LLMRouterBench shows that even commercial routers can land below that baseline [S19][S20]. `FACT` -> `REC`

**Why THIS estate (INFER):** the owner already runs 15+ agent runtimes over ~40 model ids through three or four bridges, with a memory-starved box and an OpenRouter cap; the routing decisions are currently encoded by hand in wrappers (`ai-mode`, `grok-mode`, goose `GOOSE_PROVIDER`, grok `config.toml`). A single policy file that those wrappers *read* (the same "consume the SSOT" move Fabric/Goose already make for skills, lock 5) is the smallest object that makes routing measurable and therefore optimizable; the loop then never touches a wrapper. Tradeoff to present, not hide: wrappers reading a policy file add one indirection and one failure mode (missing/invalid file -> fall back to today's hardcoded default, loudly).

## 5. CI with fakes vs live keys - what runs where

The repo already has a **shadow** `routing-benchmark` workflow: pytest self-test, pinned embedding model health check, regression bar pinned to the base branch on PRs, and a 5-run `hooks/harness-bench/gate.py` probe [disk: `.github/workflows/routing-benchmark.yml`]. The endpoint suite should be a **second job in that same workflow**, not a new workflow. `REC`

| Layer | Runs in CI (no keys, deterministic) | Needs live keys (opt-in, local or scheduled) |
|---|---|---|
| **Graders** (2.1 AST matcher, 2.2 jsonschema, 2.3 needle scorer, 2.4 percentile math, 2.5 cost arithmetic, 2.6 code-pass refusal signals, Section 3 score, Section 4 compare/decide) | **All of it**, against recorded fixtures: a `FakeEndpoint` that replays canned OpenAI-wire responses (incl. a bridge that strips `tool_calls`, a stringified-arguments blob, a `refusal` field, a 429 storm). Golden-file tests for `log.tsv` rows and the keep/discard/crash/insufficient decision table. Mirrors how `deep-research`'s harness tests run ("pure logic, fake provider responses, no live network" [disk]). | - |
| **Fixture freshness** | A test that the recorded wire fixtures still parse under the current OpenAI-compatible schema the registry declares | Re-recording fixtures (needs keys; run by hand, commit the recording with a `recorded_at`) |
| **Registry integrity** | Every `routing-policy.json` entry names an existing `agents.json` server; every `sunset_on` primary has a non-sunset escalation; no URL/secret leaked into the policy (schema-closed) | - |
| **Latency / cost / long-context / refusal on real endpoints** | - (a GitHub runner's p95 is not our p95; a CI run's spend is unbounded) | Local, single-process, streams JSONL per task to `~/.endpoint-eval/runs/<ts>/` so a 12-minute death loses one task. Spend-capped by the policy's per-run cap; secrets resolved from env by *name* from `.agents/local.json` (lock 6). Optional weekly scheduled job **only** for key-free endpoints (local ollama/lms on the box, not CI). |
| **Model-graded axes** (2.6 ambiguous refusals; any rubric grade) | Grader *prompt* linted as a skill file under `.agents/skills/` (lock 5); a fake grader returns fixed verdicts to test the majority-of-3 logic | Live: graders drawn from a *different* provider than the endpoint under test; verdicts cached by content hash so re-runs are free (`content-hash-cache-pattern` [disk]) |
| **Autoresearch loop itself** | Dry-run mode: fake scorer with a seeded random walk proves commit-before-measure, log-before-revert, reflog recoverability, and the guardrail triggers (3-discard stop, 8-plateau, spend stop) on a throwaway git repo in `tmp_path` | A real run is a human-initiated, capped, local session (the skill's Phase 1 confirmation stays) |

**What must never be in CI:** any live call through `:8317` (it is a Cursor-quota bridge and a port the owner owns - lock 3/4), any OpenRouter key (lock 1 - CI would be an uncapped spender), any credential rotation (lock 6). `REC`

**Prior-art anchors for the split:** inspect_ai scores from logs offline and supports multi-model grader voting [S33][S37]; promptfoo's model-graded assertions default to `temperature=0` and document judge-injection safety [S38][S39] - both are *ideas* to copy into the ~600-line Python runner, not runtimes to adopt (lock 2). `FACT` -> `REC`

## 6. Per-find rubric table

Value x effort on a 1-5 scale each (5 = highest value / most effort). Novelty-for-us: does anything on disk already do it. NATIVE = enable an existing capability; BUILD = new code (all BUILDs below are plain Python + git + TSV, per lock 2).

| # | Name | What | Why THIS estate | How to build or adopt | Source | Value x effort | Novelty-for-us | NATIVE-vs-BUILD |
|---|---|---|---|---|---|---|---|---|
| 1 | **Registry-entry as unit of eval** (grade bridges, not models) | Treat `(provider, model, base_url, bridge, quota_class, sunset)` as the thing under test; add a `bridge-passthrough` check for `tool_calls`/`refusal` round-trip | Both known misses were bridge-shaped (`:8317` wrappers, Space `/v1` inference-only); public leaderboards can never see our hops | Fixture-recorded wire diffs before/after each bridge; fails closed as "capability absent" | BFCL grading rules [S1][S3]; OpenAI `refusal` field [S16]; dedup-set evals.md [disk] | 5 x 2 | High - nothing on disk grades bridges | BUILD (small) |
| 2 | **BFCL-shaped tool-fidelity grader over house tools** | AST match (name, declared params, accepted values, `""`=optional), parallel 1:1, irrelevance=no-call, plus `jsonschema` on args | 42 registered servers already carry tool schemas = free gold | Port the ~60-line AST matcher; sample 12 house tools; pass^3 gate | [S1][S2][S3] | 5 x 2 | Medium - eval-harness skill has the vocabulary, no grader | BUILD |
| 3 | **pass^k as the tier gate** | Reliability (all-k) not capability (any-k) for anything that routes a class; n >= 4 trials | tau-bench: pass^1 ~50% vs pass^8 < 25% - single-trial gates lie | Estimator `E[C(c,k)/C(n,k)]` in the scorer; thresholds from `eval-harness` skill | [S5][S6][S8] | 4 x 1 | Low-medium - skill names pass^k, nothing computes it | NATIVE (skill) + BUILD (20 lines) |
| 4 | **Three-rate JSON axis + strict-subset probe** | `valid_json`, `schema_valid`, `strict_honoured` + `refusal_field_rate`, tested on OUR schemas | OpenAI strict = 100% on accepted schemas but ~29% coverage of developer schemas; silent fallback is the failure we'd never see | `jsonschema` + a probe that sends each house schema with `strict:true` and records accept/fallback | [S15][S16][S17][S18] | 4 x 1 | High | BUILD |
| 5 | **Self-relative effective-context sweep on own docs** | RULER-style multi-needle + aggregation at 4k-128k; report largest length >= 85% of own 4k score | Memory-starved box makes "how much of AGENTS.md survives at 60k" the real question; own docs = no contamination | Generator over repo markdown; code grader; report, gate at 32k only | [S26][S27][S28] | 3 x 2 | High | BUILD |
| 6 | **p50/p95 with AA definitions from our network** | TTFT (first reasoning token for reasoners), tok/s last-80%, E2E; rolling window; n >= 20 or `insufficient` | AA measures from GCP us-central1; our `:8317`/Space/Foundry hops are invisible to them | httpx streaming timer in the runner; percentiles in TSV | [S12][S13][S14] | 4 x 1 | Medium - no latency telemetry on disk for endpoints | BUILD |
| 7 | **Cost provenance classes (provider / list / quota-null)** | Trust order: OpenRouter `usage.cost` and `/generation` > list price x tokens (with `price_as_of`) > `quota_units` with `cost_usd=null` | A `null` cost cannot be optimized into "free forever"; protects the `:8317` sunset (lock 3) | Registry fields + 30 lines of arithmetic | [S30][S31] | 4 x 1 | High | BUILD |
| 8 | **Two-sided refusal set, owner-authored, code-first grading** | XSTest-shaped safe/unsafe pairs from real refused-but-legit RE/pharma/modding prompts; code signals first, majority-of-3 cross-provider model grade second | Imported benign sets are unreliable (51% of OR-Bench benign judged harmful); string-match refusal detection has known false positives | Skill-folder grader prompt (lock 5) + content-hash cache of verdicts | [S32][S34][S33] | 4 x 3 | High | BUILD (+ owner authoring time) |
| 9 | **Geometric routing score + hard quality floor** | `quality^a * speed^b * cost^c`, ineligible below floor; per-class exponents in the policy file | Any axis at zero zeroes the score - kills "cheap but wrong"; floors make reliability non-tradable | 40 lines; exponents are data | [S6][S9] | 5 x 1 | High | BUILD |
| 10 | **BestSingle null hypothesis + PerfGain/CostSave** | Every policy is compared with the best single endpoint under the same cap; PerfGain<0 and CostSave<=0 = discard | LLMRouterBench: even `openrouter/auto` scored -24.7% vs Best-Single | Compute in `score_policy.py`; print in wrap-up | [S19][S20][S21] | 5 x 1 | High | BUILD |
| 11 | **One policy file the wrappers read** (`.agents/routing-policy.json`) | The only object the loop edits; names registry entries, holds floors/exponents/spend shares; closed schema | Turns hand-coded routing in `ai-mode`/`grok-mode`/goose/grok configs into one measurable, SSOT-consuming artifact (lock 5 pattern) | JSON schema + provenance file; wrappers fall back loudly to today's default if missing | Karpathy one-file rule [S22]; AGENTS.md closed-schema convention [disk] | 5 x 3 | High | BUILD (schema) + NATIVE (wrappers already read config) |
| 12 | **Spend-bounded variants + `insufficient` status** | Per-variant and per-run spend caps in the policy; budget trip = CRASH; n<4 or 429/5xx = `insufficient` (neither keep nor discard) | Prevents the loop from Goodharting on rate-limited "fast failures" and from ever raising a cap | Extra `log.tsv` columns + refuse-to-start if OpenRouter caps unset | [S22][S30]; openrouter-routing checklist [disk] | 5 x 1 | High | NATIVE (skill contract) + BUILD (columns) |
| 13 | **Sunset guard in the loop** | A `sunset_on` primary needs a non-sunset escalation; exclusive routing to a sunset entry = auto-discard | `:8317` retires within 7 days of Cursor `/v1` GA; the loop must not optimize into a dying bridge | 10-line schema check | Task brief lock 3 | 4 x 1 | High | BUILD |
| 14 | **Bootstrap-CI noise margin** | Improvement counts only on CI non-overlap + >1pp; 8-run style averaging where affordable | n=4 trials gives wide CIs; without this the loop keeps noise | Bootstrap over task-level scores | SEA-HELM [S11]; arena-rank CIs [S35] | 3 x 1 | Medium | BUILD |
| 15 | **Second job in the existing `routing-benchmark` workflow** | Fakes-only: graders, decision table, registry integrity, dry-run loop on tmp git repo | The workflow already pins a regression bar to base and runs a shadow 5-run probe; no new workflow | pytest + golden files; `FakeEndpoint` replays | [disk: routing-benchmark.yml]; deep-research harness test pattern [disk] | 4 x 2 | Medium | NATIVE (workflow) + BUILD (tests) |
| 16 | **Borrow grader ideas, not runtimes** (inspect_ai multi-model vote, promptfoo temp-0 judge, injection-safe judge prompt) | Copy three patterns into the runner | Lock 2 forbids a second runtime/eval SaaS; the ideas are 30 lines each | Read [S33][S37][S38][S39], implement in-house | [S33][S37][S38][S39] | 3 x 1 | Medium | BUILD |
| 17 | **Skill-pressure evals as a task class** | Fold `hosted-model-agents/evals.md`'s 5 pressures into `T = skill-pressure` so the endpoint suite and the skill eval share a runner and a log | Dedup-set compose instead of two harnesses | Task-class adapter that feeds pressure prompts + disk-check graders | [disk: live-capture evals.md] | 3 x 1 | Medium | NATIVE (existing evals) |
| 18 | **Do NOT add general-knowledge or arena axes** (a prune) | Explicitly exclude MMLU-style and preference axes from the local suite | They do not change with our bridges; local measurement = spend without information | Write the exclusion into the suite README | [S9][S13][S35][S36] | 3 x 0 | - | PRUNE |

## 7. Sources

Tier: A primary/official/peer-reviewed - B reputable secondary - C blog/wiki/aggregator. Dates are publication or last-update where visible; "acc." = accessed 2026-09-02.

- [S1] Gorilla / BFCL project page - https://gorilla.cs.berkeley.edu/ - A, acc. 2026-09-02 (dataset composition, categories, relevance detection)
- [S2] BFCL v4 dataset overview (HF dataset card) - https://huggingface.co/datasets/tuandunghcmut/BFCL_v4_information/raw/main/BFCL_benchmark_detailed_overview.md - B, acc. 2026-09-02 (scoring table per category; penalize extra calls; precision/recall optional)
- [S3] HobbyLM `bfcl_eval.py` AST scorer port - https://github.com/harishsg993010/HobbyLM/blob/main/hobbylm/bfcl_eval.py - B, acc. 2026-09-02 (exact matching rule incl. `""`=optional and order-independent 1:1)
- [S4] Emergent Mind BFCL v4 topic summary - https://www.emergentmind.com/topics/berkeley-function-calling-leaderboard-v4-bfclv4 - C, acc. 2026-09-02
- [S5] Yao et al., tau-bench, arXiv 2406.12045 - https://arxiv.org/abs/2406.12045 - A, 2024 (pass^k definition, DB-state grading)
- [S6] tau-bench, ICLR 2025 proceedings PDF - https://proceedings.iclr.cc/paper_files/paper/2025/file/1b126cc38b8638e07bef37e7b2bb72bf-Paper-Conference.pdf - A, 2025 (gpt-4o <50%, pass^8 <25% retail)
- [S7] tau2-bench wiki summary - https://aiwiki.ai/wiki/Tau2-bench - C, 2025-11 (pass^k vs pass@k table; p^k decay)
- [S8] tau2-bench pass^k replication write-up (n=8, retail, 2026-07 commit) - https://zenn.dev/takkuhiro/articles/tau2-bench-passk-experiment - C, 2026
- [S9] stanford-crfm/helm README - https://github.com/stanford-crfm/helm - A, acc. 2026-09-02 (multi-metric, efficiency, unified adapters, living leaderboards)
- [S10] Liang et al., HELM, arXiv 2211.09110 - https://arxiv.org/pdf/2211.09110 - A, 2022 (7 metrics x 16 scenarios) - dated
- [S11] aisingapore/SEA-HELM README - https://github.com/aisingapore/sea-helm - B, updates 2026-01-20 and 2026-08-05 (8 runs, bootstrap CIs, Bradley-Terry Elo)
- [S12] Artificial Analysis performance benchmarking methodology - https://artificialanalysis.ai/methodology/performance-benchmarking - A (own methodology), updated 2026-03-02 (P50 over 72h; TTFT def; last-80% rule; 10k default)
- [S13] Artificial Analysis providers leaderboard - https://artificialanalysis.ai/leaderboards/providers - B, acc. 2026-09-02 (columns: cost per task, median tok/s, first chunk, E2E)
- [S14] MarkTechPost TTFT-first benchmark snapshot - https://www.marktechpost.com/2026/08/30/lowest-latency-inference-apis-for-voice-and-realtime-agents-a-time-to-first-token-ttft-first-benchmark/amp/ - C, 2026-08-30
- [S15] OpenAI, Introducing Structured Outputs - https://openai.com/index/introducing-structured-outputs-in-the-api/ - A, 2024-08 (constrained decoding; 100% vs <40%) - dated
- [S16] OpenAI Structured Outputs guide (current) - https://developers.openai.com/api/docs/guides/structured-outputs - A, acc. 2026-09-02 (strict vs JSON mode table; `refusal` field; gpt-5.6 default)
- [S17] Awesome Agents structured-output leaderboard (JSONSchemaBench summary) - https://awesomeagents.ai/leaderboards/structured-output-json-leaderboard/ - C, 2026 (OpenAI ~29% coverage on developer schemas; Guidance ~96%)
- [S18] TMLS, Structured Outputs and Constrained Decoding - https://tmls.nyc/research/structured-outputs-constrained-decoding - C, 2026 ("benchmark on your own schemas"). Primary JSONSchemaBench paper (Geng et al., arXiv 2501.10868, 2025-01) recalled, NOT fetched this run - UNVERIFIED
- [S19] Li et al., LLMRouterBench, arXiv 2601.07206 (HTML) - https://arxiv.org/html/2601.07206v1 - A, 2026-01 (PerfGain/CostSave; OpenRouter -24.7% vs Best-Single; retry-10-then-0)
- [S20] LLMRouterBench, Findings of ACL 2026 - https://aclanthology.org/2026.findings-acl.1881.pdf - A, 2026
- [S21] ynulihao/LLMRouterBench repo - https://github.com/ynulihao/LLMRouterBench - B, acc. 2026-09-02 (Pareto/ParetoDist; baselines list)
- [S22] karpathy/autoresearch `program.md` @ 228791fb - https://github.com/karpathy/autoresearch/blob/228791fb/program.md - A, 2026-03 (loop steps, tsv columns, 10-min kill, simplicity)
- [S23] karpathy/autoresearch README - https://github.com/karpathy/autoResearch - A, 2026-03
- [S24] DeepWiki, autoresearch program.md / research loop - https://deepwiki.com/karpathy/autoresearch/3.4-program.md-agent-instructions and https://deepwiki.com/karpathy/autoresearch/4.1-the-research-loop - C, 2026
- [S25] Mager, autoresearch pattern - https://www.mager.co/blog/2026-03-14-autoresearch-pattern/ - C, 2026-03-14
- [S26] NVIDIA/RULER README + paper (arXiv 2404.06654) - https://github.com/nvidia/ruler - A, 2024-2025 (13 tasks / 4 families; 85.6% threshold; configurable needles)
- [S27] Long-context benchmarks 2026 explainer - https://iotdigitaltwinplm.com/long-context-llm-benchmarks-ruler-effective-context-2026/ - C, 2026 (operational effective-context definition; synthetic vs real)
- [S28] Effective context length scoreboard - https://alatirok.com/effective-context-length-scoreboard/ - C, 2026 (NoLiMa 85%-of-own-baseline rule; MRCR v2; 60-70% of advertised)
- [S29] Ganglani, LLM latency benchmarks 2026 - https://www.kunalganglani.com/blog/llm-latency-benchmark-optimization - C, 2026 (track P50/P95/P99 TTFT)
- [S30] OpenRouter Usage Accounting - https://openrouter.ai/docs/cookbook/administration/usage-accounting - A, acc. 2026-09-02 (`usage.cost`, `upstream_inference_cost`, reasoning/cached tokens)
- [S31] OpenRouter `/generation` metadata - https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation - A, acc. 2026-09-02 (`native_tokens_*`, `latency`, `generation_time`, `total_cost`)
- [S32] Rottger et al., XSTest, arXiv 2308.01263 - https://arxiv.org/html/2308.01263 - A, 2023 (250 safe / 200 unsafe; string-match false positives; GPT-4 judge loses partial refusals) - dated
- [S33] inspect_ai `scorer/_model.py` - https://github.com/UKGovernmentBEIS/inspect_ai/blob/main/src/inspect_ai/scorer/_model.py - A, acc. 2026-09-02 (multi-model majority vote; grade_pattern)
- [S34] ORFuzz, arXiv 2508.11222v2 - https://arxiv.org/abs/2508.11222v2 - A, 2025-08 (~51% of OR-Bench benign judged harmful; XSTest saturated). OR-Bench itself: https://arxiv.org/html/2405.20947 - A, 2024
- [S35] lmarena/arena-rank - https://github.com/lmarena/arena-rank and https://arena.ai/blog/arena-rank - A, 2025-2026 (contextual Bradley-Terry; closed-form CIs)
- [S36] LMSYS, style control - https://www.lmsys.org/blog/2024-08-28-style-control/ - A, 2024-08 - dated
- [S37] Inspect custom scorers docs - https://inspect.aisi.org.uk/custom-scorers.html - A, acc. 2026-09-02
- [S38] promptfoo `llm-rubric` - https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/ - B, acc. 2026-09-02 (temperature=0 default; threshold)
- [S39] promptfoo LLM-as-a-judge guide - https://www.promptfoo.dev/docs/guides/llm-as-a-judge/ - B, acc. 2026-09-02 (multi-judge voting; injection-safe prompts)
- [S40] OpenRouter rankings - https://openrouter.ai/rankings - A, bucket dated 2026-09-01 ("measure adoption, not quality")
- [S41] OpenRouter Data API - https://openrouter.ai/docs/cookbook/administration/data-api - A, acc. 2026-09-02 (`rankings-daily`, top-50/day, native tokenizer caveat)
- [disk] Files read from this repo/branches on 2026-09-02: `skills/hosted-model-agents/evals.md` (origin/live-capture/2026-09-02), `.agents/skills/{autoresearch,eval-harness,openrouter-routing,deep-research,gem-hunt}/SKILL.md`, `.agents/agents.json`, `platform/routing/MEASUREMENTS.json`, `hooks/semantic-router/eval.py`, `.github/workflows/routing-benchmark.yml`, `AGENTS.md`.

**Methodology note.** 12 web searches, ~40 URLs, 0 live model calls. Not fetched (UNVERIFIED): JSONSchemaBench primary paper; LongBench v2 paper (site read [https://longbench2.github.io/], B). Recency: 26 of 41 sources are from the last 12 months; the dated anchors (HELM 2022, XSTest 2023, tau-bench 2024, Structured Outputs 2024, style control 2024) are canonical definitions, each paired with a 2025-2026 follow-on. Confidence overall: **High** for definitions and prior-art facts, **Medium** for the specific thresholds (owner-tunable by design), **Low** for anything about how the estate's wrappers would consume a policy file (pure inference from the task brief; not verified on the Windows box, which this run cannot see).

## 8. Ten-line summary

1. Unit of eval = the **registry entry** (provider + model + bridge + quota + sunset), not the model; only we can grade our `:8317`/Space/Foundry hops, and both known misses were bridge-shaped.
2. Seven axes, code-graded wherever checkable: BFCL-shaped tool fidelity (AST match, parallel 1:1, irrelevance), a three-rate JSON axis that catches strict-mode silent fallback, RULER-style self-relative effective context on our own docs, p50/p95 with Artificial Analysis definitions from our network, cost with three provenance classes (`null` for quota, never 0), two-sided owner-authored refusal sets, and a derived routing score.
3. Reliability gates use **pass^k** (n >= 4), not pass@k - tau-bench shows pass^8 < 25% where pass^1 ~ 50%.
4. Routing score = `quality^a * speed^b * cost^c` with a hard quality floor; geometric so "cheap but wrong" scores zero.
5. The loop's null hypothesis is **BestSingle** with LLMRouterBench's PerfGain/CostSave; even `openrouter/auto` scored -24.7% vs Best-Single, so "route everything to one endpoint" is an honest possible outcome.
6. Autoresearch edits **one file**, `.agents/routing-policy.json` (names only, closed schema), via the house skill's contract: commit-before-measure, log-before-revert, revert on any regression; `log.tsv` gains `spend_usd`, `spend_cum_usd`, `quota_units`, `n_trials`, `perf_gain/cost_save` and a fourth status `insufficient`.
7. Guardrails beyond the skill's three: spend-bounded variants (budget trip = CRASH, caps read not typed, refuse-to-start without OpenRouter daily+monthly caps), a **sunset guard** for the `:8317` bridge, an availability guard (429/5xx never count as fast), Karpathy's simplicity tiebreak, and a schema that forbids removing a class or an endpoint (lock 7).
8. CI runs everything with fakes as a second job in the existing shadow `routing-benchmark` workflow (graders, decision table, registry integrity, dry-run loop on a tmp git repo); live keys stay local, capped, name-resolved, and never touch `:8317` or OpenRouter from a runner.
9. Deliberately NOT built: general-knowledge and arena-preference axes (published elsewhere, unchanged by our bridges), any eval SaaS/runtime (inspect/promptfoo ideas are borrowed as ~30-line patterns), any new MCP or port.
10. Top three by value x effort: registry-entry-as-unit + bridge passthrough (#1), geometric score with floors (#9), BestSingle null hypothesis (#10); the one BUILD with real cost is the policy file the wrappers read (#11), which is also the only thing that makes routing measurable at all.
