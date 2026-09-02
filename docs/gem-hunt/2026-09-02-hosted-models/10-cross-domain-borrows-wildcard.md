# Gem-hunt 2026-09-02 / hosted models / lens 10: cross-domain borrows + wildcard

Lens id: `10-cross-domain-borrows-wildcard`
Branch: `gemhunt/hosted-models-10-cross-domain-borrows-wildcard` (from `main` @ `5fa34fda1`)
Mode: discovery only. No code changed. No PR.

Status legend used below:

- **[FACT]** sourced claim, cited with URL + tier + date checked.
- **[INFER]** my inference from sourced facts; can be wrong.
- **[REC]** recommendation for this estate.
- Tier A = primary/official docs, standards bodies, regulators, peer-reviewed. Tier B = reputable secondary
  (vendor engineering blogs, well-maintained OSS READMEs, trade press). Tier C = forum / single blog / model-training
  memory. **UNVERIFIED** = I could not fetch a live source in this run.

## 0. Constraints honoured (estate locks, cited as constraints)

- OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never `ANTHROPIC_BASE_URL`, never a new
  OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA.
- Ports 8765 / 8812 / 8317 are owned.
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials. Never remove a feature to buy reliability; present tradeoffs instead.

Dedup-set (exists, not re-proposed): `hosted-model-agents` skill (live-capture/2026-09-02), `tools/mcp/glm53-space`
(to be deprecated), `auth2api :8317`, `.agents/agents.json` + `.agents/local.json`, installed runtimes on the Win11 box.

## Estate surfaces the finds must ride (grounding, read this run)

- Prompt SSOT: `.agents/skills/<skill>/SKILL.md` (Fabric/Goose consume it). Any "policy" below is a skill or a data
  file next to one, not a daemon.
- Registry: `.agents/agents.json` `mcp.servers` (42 entries, each with `targets`, e.g. `huggingface` ->
  `https://huggingface.co/mcp?login` targets `claude`; `glm53-space` -> `uv run ... mcp_server.py` targets `claude`;
  `basic-memory` `:8765`, `agent-mail` `:8812` carry `processMatch`). Secrets by name in `.agents/local.json`.
- Health/quarantine state already exists: `.agents/scripts/mcp_fleet_supervisor.py` writes
  `state/mcp-supervisor.json` and `reports/mcp-fleet-status.json` and keeps a **session quarantine**. Every
  "circuit breaker"-like find below should extend that state file, not add a new one.
- Sidecar: `.agents/scripts/openrouter-complete.py` is the T0 OpenRouter completion (prints generation id + usage,
  never logs the secret). CLI/Codex only, per lock.
- Wrappers in `~/.local/bin` (`ai-mode`, `fabric-cursor`, `claude-cursor`, `codex-cursor`, `grok-mode`) are the
  process-local edge where an endpoint is chosen today. A routing table is *data they read*, not a new process.
- Hooks: Claude/Cursor hook scripts under `.agents/scripts/cursor-hooks/` (`shell-guard.ps1`, `cursor-hook-log.ps1`,
  `bm-session-liveness.ps1`) prove the estate already runs pre/post hooks; a "dispatch release" check is one more
  hook body, not a framework.
- Dedup item (1), `hosted-model-agents` (live-capture/2026-09-02), already fixes the three layers (control plane =
  HF Hub MCP; runtime = `/v1`/Gradio/TGI/llama-server/Cursor Max; harness = local executor) and its hard rule 2
  ("an inference URL is not Hub MCP; do not register every GPU URL as MCP"). Everything below is about **which
  runtime to pick and when to switch**, which that skill does not cover. `[FACT]` (read from branch this run).

## 1. Telecom: least-cost routing + quality-based re-ordering + route advance

### Mechanism (sourced)

- **LCR with a prefix routing table.** Carriers keep a "rate deck" (price per destination prefix) and a routing
  table that lists, per prefix, an ordered set of gateways/carriers. OpenSIPS `drouting` is the reference OSS
  implementation; `qrouting` sits on top of it and **re-orders destinations live** from five signalling KPIs:
  **ASR** (answer-seizure ratio), **CCR** (call completion ratio), **PDD** (post-dial delay: INVITE -> first
  180/183), **AST** (average setup time: INVITE -> 200 OK), **ACD** (average call duration). Each KPI has a
  `warn` and a `crit` threshold and a penalty; per-destination scores are recomputed over a `history_span`
  window, and a destination is not judged until `min_samples_*` observations exist. `[FACT]` Tier A (vendor
  docs, corroborated by two OpenSIPS pages), checked 2026-09-02:
  <https://docs.opensips.org/manual/devel/modules/qrouting/> and
  <https://opensips.org/docs/modules/3.2.x/qrouting.html>.
- **Two re-ordering algorithms, deliberately different tradeoffs.** `best-dest-first`: all traffic to the
  top-scored destination, provision the list in expected-quality order because it is blind until samples exist.
  `dynamic-weights`: ratings become weights in a weighted-random balance (ratings 1 and 0.5 -> ~67%/33%), which
  OpenSIPS calls "the superior choice" because it **keeps sampling the poor performers at a low rate**, so recovery
  is detected without a manual reset. `[FACT]` Tier B (vendor blog, 2020, corroborated by the module docs above):
  <https://blog.opensips.org/2020/03/17/quality-based-pstn-routing-in-opensips-3-1-lts-part-2/>.
- **Route advance / carrier failover on SIP `503 Service Unavailable`** with an optional `Retry-After` header;
  a proxy receiving 503 should try alternate destinations rather than surfacing the failure. `[FACT]` Tier A,
  RFC 3261 s21.5.4 (2002, stable): <https://www.rfc-editor.org/rfc/rfc3261#section-21.5.4>. Not re-fetched this
  run (standard text, high confidence).

### Exact analogue for choosing a model endpoint

| Telecom | Model routing in this estate |
|---|---|
| Prefix (destination class) | **Task class**: `edit-code`, `agentic-tools`, `long-context-read`, `cheap-classify`, `vision`, `red-team-report` |
| Gateway / carrier | Endpoint: `cursor-*` via `auth2api :8317` (Cursor quota), OpenRouter model id (**CLI/Codex only**), HF Space or Endpoint `/v1`, local `ollama` / `lms` / llama-server |
| Rate deck | Price per 1M tokens (OpenRouter `/models` exposes it; HF Endpoint per-hour; Cursor = quota units) |
| ASR | Completion success ratio: HTTP 200 with non-empty `choices[0]` |
| CCR | **Tool-call well-formedness ratio**: `tool_calls` parse + schema-validate (the estate's harness rule 3 already validates them locally) |
| PDD | Time-to-first-token |
| AST | Time-to-first-`tool_call` (agentic) or time-to-final (non-streaming) |
| ACD | Output tokens per completion; a sudden ACD drop = truncation / silent context cut |
| `503` + `Retry-After` | HTTP 429/503/529 from the provider; `Retry-After` honoured; **route-advance to the next destination for the same prefix** |
| `min_samples` | Do not demote an endpoint on one failure; demote after N |
| `history_span` | Sliding window so a bad hour does not blacklist a provider for a week |

`[INFER]` The two KPIs the software lenses usually skip are **CCR** (format validity, not just HTTP success) and
**ACD** (output-length collapse as a silent-degradation signal). Both are free to compute from responses the wrappers
already have in hand.

### How it rides the existing bus (no new runtime)

- `routes.json` (per task class: ordered destinations, thresholds, penalties, `min_samples`, `history_span`) lives in
  `.agents/` next to `agents.json` so it is under the same SSOT/sync (`sync_shared_state.ps1`). The wrappers in
  `~/.local/bin` and the wrapper that replaces `tools/mcp/glm53-space/openai_proxy.py` **read** it. `[REC]`
- Stats are appended to `.agents/state/` in the same shape `mcp_fleet_supervisor.py` already uses for session
  quarantine; the supervisor's existing `--report` becomes the place a demoted endpoint shows up. `[REC]`
- Route-advance on 429/503/529 is a loop in the wrapper (the `openrouter-complete.py` request function already
  returns `(status, body)` and could try the next destination). No LiteLLM: the table is ~50 lines of JSON and the
  loop is ~30 lines. `[REC]`
- Lock compliance: OpenRouter destinations may only appear in CLI/Codex-side task classes; `cursor-*` destinations
  only via `:8317`. The table makes the lock **inspectable** (a validator like `validate_mcp_control_plane.py` can
  fail closed if an OpenRouter id appears in a Cursor-targeted class). `[REC]`

### Tradeoff (never remove a feature to buy reliability)

`dynamic-weights` buys recovery detection by spending a few percent of traffic on the worse endpoint (cost of
information). `best-dest-first` is cheaper and deterministic but needs a manual "un-quarantine". Offer both as a
per-class flag; default `best-dest-first` for quota-metered Cursor classes (every sample costs quota), `dynamic-weights`
for local/HF classes where samples are cheap. `[REC]`

## 2. Finance: smart order routing + best execution + "regular and rigorous review"

### Mechanism (sourced)

- **FINRA Rule 5310 (Best Execution and Interpositioning).** A member must "use reasonable diligence to ascertain
  the best market" so the resulting price is "as favorable as possible under prevailing market conditions". A firm
  that routes on an automated, non-discretionary basis must run **"regular and rigorous reviews"** of execution
  quality, **at least quarterly**, on a **security-by-security, type-of-order basis**, and must either **modify its
  routing arrangements or justify why it is not modifying them**. Review factors: price improvement, likelihood of
  execution, speed, size, transaction costs, customer needs. A member **cannot transfer its best-execution
  obligation to another person**. `[FACT]` Tier A, checked 2026-09-02:
  <https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310>. Corroborated by Regulatory Notice 15-46
  (<https://www.finra.org/rules-guidance/notices/15-46>) and the 2026 FINRA oversight report, which adds that the
  review should consider "competing markets to which a firm does not send order flow":
  <https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report/best-execution>.
- **"Interpositioning"**: 5310 forbids inserting a third party between the member and the best market when doing so
  worsens the customer's outcome. `[FACT]` Tier A, same rule page.
- **MiFID II Article 27** (EU): "all sufficient steps" for the best possible result, weighing **price, costs, speed,
  likelihood of execution and settlement, size, nature of the order**; a **written execution policy** per instrument
  class, reviewed **at least annually** and on material change. `[FACT]` Tier B (industry regulatory guide,
  checked 2026-09-02):
  <https://www.quodfinancial.com/best-execution-in-institutional-trading-regulatory-requirements-and-the-role-of-technology/>.
  Primary text: Directive 2014/65/EU Art. 27, <https://eur-lex.europa.eu/eli/dir/2014/65/oj> (Tier A, not
  re-fetched this run). The former RTS 28 "top five venues" report was being wound down in the 2024 MiFID review;
  treat the *disclosure* piece as **UNVERIFIED** this run.
- **Smart order routers** are the automation of the duty: a SOR "assess[es] trading venues for the best priced
  quotation and liquidity prior to routing" and is a permissible algorithm precisely because it serves best
  execution. `[FACT]` Tier A (SEC release 34-99488, Feb 2024):
  <https://public-inspection.federalregister.gov/2024-02858.pdf>.

### Exact analogue for choosing a model endpoint

| Finance | Model routing in this estate |
|---|---|
| Security x order type | Task class x invocation shape (interactive vs background, streaming vs batch) |
| Price improvement | Quality above the class baseline at equal or lower cost (from the estate's own evals) |
| Likelihood of execution | Non-refusal, non-timeout, non-truncation ratio |
| Speed | TTFT + total latency |
| Size | Max context / max output the endpoint reliably handles |
| Transaction costs | `$` per 1M tokens **plus Cursor quota units** (quota is a cost, not free) |
| Customer needs | Explicit owner pins ("this class must stay on Claude"), security scope (no third-party exploit playbooks on a Space, per `profiles.md`) |
| Regular and rigorous review | A **scheduled review skill** that compares current routes against alternatives, **including endpoints not currently used**, and writes "changed" or "kept, because ..." |
| Cannot transfer the duty | Using OpenRouter's own provider routing or Cursor's model choice does **not** discharge the estate's review; log the *actual* provider/model used (OpenRouter returns `provider` in the response body) |
| Interpositioning | Do not add a hop (second bridge, LiteLLM, extra proxy) that adds cost/latency without benefit. This is the finance-language justification of the `auth2api`-only and no-LiteLLM locks |

`[INFER]` Best execution is a *multi-factor* duty; a cheapest-token router would fail a 5310 review. That is the
argument, in a regulator's words, against pure LCR.

### How it rides the existing bus

- `review-routing` is a **skill** (prompt in `.agents/skills/`) any runtime can run monthly; input = the stats file
  from s1; output = `.agents/reports/routing-review-<date>.md` with a "modified / justified-not-modified" line per
  task class (the 5310 wording). `[REC]`
- "Competing markets you do not send flow to" = a tiny **shadow-eval** line item: once a month, run the estate's
  existing eval set (dedup item (1) `evals.md` already exists) against one non-routed endpoint. Cost bounded by the
  OpenRouter spend cap for CLI classes and by zero for local models. `[REC]`
- The routing table from s1 gains one column: `justification` (free text, dated). That is the "written execution
  policy". `[REC]`

### Tradeoff

Quarterly is FINRA's floor and many firms review monthly (Notice 15-46). For this estate the cost of a review is one
eval run per class; the cost of *not* reviewing is that `cursor-*` quota keeps going to a model that a cheaper local
one now matches. Keep the cadence a parameter. `[REC]`

## 3. Pharmacy: formulary, generic substitution (AB-rating), therapeutic interchange, step therapy

### Mechanism (sourced)

- **FDA Orange Book therapeutic-equivalence (TE) codes.** A-rated products (AB, AA, AN, AO, AP, AT) are
  therapeutically equivalent and may be substituted at the pharmacy counter without going back to the prescriber;
  B-rated products (BC, BD, ..., BX) are **not** and need prescriber authorisation. **AB is relative to a reference
  product**: a generic rated AB1 substitutes only for the AB1 reference, not for an AB2 one. Bioequivalence is shown
  with the 80-125% confidence-interval criterion. `[FACT]` Tier B (three secondary sources agree; primary is the
  FDA Orange Book preface), checked 2026-09-02:
  <https://www.assyro.com/blog/therapeutic-equivalence-guide>,
  <https://medcraveonline.com/MOJBB/fdarsquos-orange-book-and-ab-ratings-of-pharmaceutical-drug-products-a-guide-to-community-pharmacist.html>,
  <https://www.elsevier.support/ckpharma/answer/what-are-orange-book-therapeutic-equivalence-ratings-in-the-drug-product-information>.
  Primary: <https://www.fda.gov/drugs/development-approval-process-drugs/orange-book-preface> (Tier A, not
  re-fetched this run).
- **ASHP formulary-system guideline.** *Generic substitution* of FDA-bioequivalent products "does not require review
  or approval by the P&T committee". *Therapeutic interchange* is "the authorized exchange of therapeutic
  alternatives in accordance with previously established and approved written guidelines, policies, or protocols" for
  products **with different chemical structures** expected to give the same outcome; the pharmacist may swap
  "without having to contact the prescriber", the protocol should be built into the EHR, and **a process must exist
  for the prescriber to opt out**. `[FACT]` Tier A (professional-society guideline, draft text checked
  2026-09-02):
  <https://www.ashp.org/-/media/assets/policy-guidelines/docs/draft-guidelines/draft-pharmacy-therapeutics-committee-and-formulary-system.pdf>.
- **Utilisation management**: *step therapy* (formulary product first; escalate on documented failure), *prior
  authorisation* (decision within 14 days, 24 h expedited), and **non-formulary exceptions** granted when the patient
  has "tried and failed" formulary products or is "previously stable on" a medication (continuity). `[FACT]` Tier B
  (industry best-practice checklist, 2019, checked 2026-09-02):
  <https://www.nationalforum.org/wp-content/uploads/2019/06/PT-Committee-Best-Practices-Checklist-June-19-v2.pdf>.

### Exact analogue for choosing a model endpoint

| Pharmacy | Model routing in this estate |
|---|---|
| Formulary with tiers | Allowed endpoints per task class in tiers: T1 local (`ollama`/`lms`/llama-server), T2 HF Endpoint or OpenRouter (CLI/Codex only), T3 Cursor quota via `:8317` |
| Generic substitution (A-rated) | **Same checkpoint, different provider** (an open-weights model on HF vs OpenRouter vs local) - swappable by the wrapper without asking |
| B-rated "same ingredient, different dosage form" | **Same weights, different quantisation/serving stack** (Q4 GGUF vs bf16 vLLM). Not automatically equivalent; treat as B until the estate's evals say otherwise |
| AB1 vs AB2 | Equivalence is **per task class**: a local model may be AB for `cheap-classify` and B for `agentic-tools` |
| Therapeutic interchange (different molecule) | **Different model family** for the same class (Claude -> GPT -> Qwen) under a *written* protocol in the skill, with an owner **opt-out pin** |
| Step therapy | Try T1/T2 first, escalate to T3 on documented failure (the `openrouter-routing` T0/T1 idea, made a class-level rule) |
| Prior authorisation | Human-in-the-loop before a **background** job may burn T3 quota; time-boxed |
| "Tried and failed" / "stable on" exception | **Grandfathering**: a workflow stable on a model is not force-switched by a formulary update. This is "never remove a feature to buy reliability" in P&T language |
| 80-125% bioequivalence margin | An explicit **equivalence margin on the estate's own eval scores** (dedup item (1) `evals.md`) before an endpoint is rated substitutable |

`[INFER]` The non-obvious borrow is the **AB1/AB2 relativity**: interchangeability is a property of the (class,
reference) pair, not of the model. Most "model router" designs rate models globally.

### How it rides the existing bus

- The `routes.json` from s1 gets an `equivalence` field per (class, endpoint): `A` (auto-swap), `B` (owner must
  approve), `NR` (no alternative exists). Derived from `evals.md` runs; written by a skill, read by wrappers. `[REC]`
- Interchange protocols are prose in the skill (the SSOT), e.g. "for `red-team-report`, interchange Claude ->
  local Qwen is A only when tool-call CCR >= 0.97 over 50 samples". `[REC]`
- Prior-authorisation gate = one check in the existing hook path (`cursor-hooks/`) or wrapper: `invocation=background
  and tier=T3 and no --authorized flag -> refuse with the PA message`. `[REC]`
- Grandfathering = `pinned_until` (date) on a class row; the s2 review job may not touch pinned rows. `[REC]`

### Tradeoff

A strict formulary cuts cost but loses off-formulary capability. Keep a **non-formulary request log** (owner asks, gets
it, the request is recorded) instead of a hard block; the log is the input to the next P&T (= s2 review). `[REC]`

## 4. Aviation: MEL deferral categories, dispatch release, dispatch reliability

### Mechanism (sourced)

- **14 CFR 121.628 (inoperable instruments and equipment).** An airline may fly with inoperative equipment only if
  an approved **Minimum Equipment List** exists, the crew has "direct access at all times prior to flight" to it,
  **records identify the inoperative items**, and operations respect the MEL's conditions and limitations. Some items
  may **never** be deferred: those "essential for safe operations under all operating conditions", those an
  airworthiness directive requires, and those required for specific operations. `[FACT]` Tier A (eCFR via LII,
  checked 2026-09-02): <https://www.law.cornell.edu/cfr/text/14/121.628>.
- **Repair (rectification) categories.** Category A: interval stated in the MEL item itself; B: 3 consecutive
  calendar days; C: 10 days; D: 120 days (day of discovery excluded). `[FACT]` Tier A (FAA MMEL Policy Letter
  PL-25 rev 21, checked 2026-09-02): <https://www.wildingair.com/wp-content/uploads/forms/pl-025%20rev%2021.pdf>;
  corroborated by <https://www.aviationhunt.com/mmel-vs-mel-definitive-guide/> (Tier B), which also notes the
  MEL column "Number required for dispatch" and the **"AR - as required by operating rule"** flag: whether an item
  may be inoperative depends on the *route* (ETOPS, RVSM, night, overwater), and that operating under an MEL "constitutes
  a degradation of certified system redundancy" bounded by time limits derived from safety analysis.
- **Dispatch reliability** (industry KPI) = share of scheduled departures that leave without a technical delay
  beyond a threshold (commonly 15 min) or cancellation. `[FACT]` Tier C / **UNVERIFIED URL** this run (standard
  industry definition; the search surfaced it but no single citable page was retained).

### Exact analogue for choosing a model endpoint

| Aviation | Model routing in this estate |
|---|---|
| Aircraft | Endpoint (a `cursor-*` id via `:8317`, an HF Endpoint, a local server) |
| MEL item | A **capability**: `tool_calls`, `json_mode`, `vision`, `>=128k context`, `streaming`, `system-prompt adherence`, `stop sequences` |
| Never-deferrable items | For `agentic-tools`: `tool_calls` well-formedness. For `long-context-read`: no silent truncation. If inoperative, the endpoint is **grounded for that class** |
| Repair category A/B/C/D | How long an endpoint may keep serving a class with that capability degraded before it must be fixed or swapped: e.g. `streaming` broken = D (cosmetic, 120 d); `json_mode` flaky = C (10 d); tool-call CCR below `warn` = B (3 d); context truncation = A ("before next flight") |
| "AR - as required by operating rule" | Requirements depend on the **mission**: an unattended background run (no human "alternate airport" nearby; the ETOPS case) needs more operative capabilities than an interactive session where the owner can intervene |
| Dispatch release | A **pre-flight hook**: MEL status of the chosen endpoint, fuel (quota headroom), a named alternate (fallback endpoint), weather (provider status). Go / no-go with a reason |
| Records of inoperative items | `state/mcp-supervisor.json` already records quarantine; add `deferred: [{capability, category, expires}]` |
| Dispatch reliability | **% of agent runs that start within N s without a provider-caused delay/cancel**, per endpoint. One number; the s2 review reads it |

`[INFER]` The MEL is the industry's formal answer to "never remove a feature to buy reliability": you *fly* with the
broken item, **deferred, placarded, time-boxed**, instead of grounding the fleet or pretending it works. Software
circuit breakers have the "open/closed" states but no repair clock; the repair categories are the missing piece.

### How it rides the existing bus

- MEL table (capability -> category, per class) is prose + a small JSON block in the routing skill. `[REC]`
- Dispatch release is a hook body in `.agents/scripts/cursor-hooks/` (the estate already runs `shell-guard.ps1`
  and `bm-session-liveness.ps1` there) or the first step of `ai-mode` / `*-cursor` wrappers. It reads two files and
  prints one line. `[REC]`
- Expiry of a deferred item is checked by the same `mcp_fleet_supervisor.py --report` run that already exists. `[REC]`

### Tradeoff

Discipline cost: someone (a skill) has to record the deferral and the clock. Benefit: no silent degradation for weeks,
and no over-reaction to a one-off. `[REC]`

## 5. Power grid: security-constrained unit commitment, reserves sized to the worst single contingency

### Mechanism (sourced)

- **SCUC + economic dispatch.** PJM's day-ahead market "clears ... using least-cost security constrained resource
  commitment and dispatch that simultaneously optimizes energy and reserves"; a *dispatch run* decides what runs and a
  separate *pricing run* sets locational prices. Demand-side "Curtailment Service Providers" bid demand *reductions*
  into the same optimisation. `[FACT]` Tier A (PJM Manual 11 v136, 2025-10-01, checked 2026-09-02):
  <https://www.pjm.com/-/media/DotCom/documents/manuals/archive/m11/m11v136-energy-and-ancillary-services-market-operations-10-01-2025.pdf>.
- **Resource constraints** in SCUC: capacity limits, **ramp-rate limits, minimum run time, minimum down time**,
  startup / no-load / incremental costs; system constraints: power balance, reserve requirement, transmission under
  the NERC **N-1** standard. Large ISOs solve it as MILP (PJM since 2004). `[FACT]` Tier A (DOE/OSTI review,
  checked 2026-09-02): <https://www.osti.gov/servlets/purl/1899996>.
- **Soft constraints with penalty prices.** PJM's transmission-constraint penalty is $30,000/MWh in the day-ahead
  dispatch run and $2,000/MWh in the pricing run; reserve shortage is priced on a two-step **Operating Reserve Demand
  Curve** ($850/MWh for the Largest-Single-Contingency step, $300/MWh for an extra 190 MW buffer). `[FACT]` Tier B
  (academic working paper citing PJM 2025, checked 2026-09-02):
  <https://www.fawolak.org/pdf/market_clearing_penalty_parameters.pdf>.
- **NERC BAL-002-3**: carry enough **contingency reserve to recover within 15 minutes** from a sudden loss up to the
  **Most Severe Single Contingency (MSSC)**; 90-minute restoration period; PJM implements it as 10-minute *primary
  reserve* (synchronised + non-synchronised) sized to the largest contingency plus a buffer. `[FACT]` Tier A/B
  (PJM Manual 12 and the Independent Market Monitor's 2021 report, checked 2026-09-02):
  <https://www.pjm.com/-/media/DotCom/documents/manuals/m12.pdf>,
  <https://www.monitoringanalytics.com/reports/PJM_State_of_the_Market/2021/2021q2-som-pjm-sec10.pdf>.

### Exact analogue for choosing a model endpoint

| Grid | Model routing in this estate |
|---|---|
| Unit commitment (what is *on*) vs dispatch (how much each gets) | **Two decisions, two cadences**: daily "which local model is loaded in RAM / which HF Endpoint is warm / is `auth2api` up" vs per-request "which committed endpoint gets this call" |
| Startup cost, min run time, min down time | On a 31.6 GB, memory-starved box a local model load *is* a startup cost; **do not thrash** `ollama`/`lms` load-unload; commit one local model per day-part and leave it |
| Ramp-rate limit | Concurrency ramp per provider (rate limits and 429s) |
| Transmission constraint (N-1) | RAM ceiling: at most one heavy local runtime + one `cursor-agent` (the existing G-36 rule) |
| MSSC | **Loss of the Cursor path (`:8317` / quota exhausted)** is the largest single contingency for this estate |
| 15-minute contingency reserve sized to MSSC | Always keep one endpoint that can take the Cursor classes' load **within minutes without human action**: a warm local server or a CLI-side OpenRouter route with spend headroom, sized to the interactive classes only |
| ORDC (reserve value rises as headroom shrinks) | **Quota headroom curve**: as Cursor quota headroom drops, background classes are priced out first |
| Curtailment Service Providers | Background jobs (`background-digest`, monitors) **declare themselves curtailable** and are shed first |
| Penalty price vs hard constraint | Estate locks stay **hard** (like N-1); softer preferences (prefer local for `cheap-classify`) get a **penalty weight** so the router degrades rather than fails |

`[INFER]` The grid's key discipline is that the reserve is *sized to a named contingency*, not to a vague "have a
fallback". Naming the MSSC (Cursor path loss) makes the reserve requirement computable: how many interactive requests
per hour must the reserve absorb, and for how long (90-minute restoration).

### How it rides the existing bus

- Daily commitment = a 10-line `state/commitment-<date>.json` written by a skill run at session start (which local
  model, which endpoint warm). Wrappers read it to avoid loading a second local model. `[REC]`
- Reserve check = one line in the s4 dispatch-release hook: "is the MSSC reserve endpoint healthy and within
  headroom?". `[REC]`
- Curtailment = a `priority` field on invocations (the same field the wildcard's water-rights borrow uses); the
  wrapper refuses T3 for low priority when headroom < threshold. `[REC]`

### Tradeoff

Reserves cost money or RAM (a warm HF Endpoint bills per hour; a loaded local model holds RAM). Make the reserve level
an explicit knob with the outage cost stated next to it, per the owner's "present tradeoffs" rule. `[REC]`

## 6. Wildcard: the find the other lenses would miss

_(pending)_

## 7. Rubric table

_(pending)_

## 8. Ten-line summary

_(pending)_
