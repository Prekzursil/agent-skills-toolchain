# Extensive grill — HF Space `Prekzursil/qwen38-27b-heretic-chat`

- **Started:** 2026-09-19 · **Skill:** `grill-me-extensive` (agent-skills-toolchain) · **Status:** 11 questions walked; waiting for the review workflow + simplification retry, then CONVERGE → plan → implementation workflow
- **Modes:** modification + red-team (the existing design and the way it is being changed) · simplification + scope-change (it grew
  faster than its basics) · better-ideas + modernization (is ZeroGPU + transformers + NF4 the right home) · prioritization (order).
- **Rule:** a grill is not a build. Nothing is implemented, pushed or rolled back until the owner decides it here.
- **Persistence:** this file is the decision queue + audit trail. The contract's "event ledger" / "Basic Memory" are not reachable
  from this Codespace session; Claude's file memory holds a pointer to this folder instead.
- **Evidence:** `evidence/SCOUT_BRIEF.md` (facts F1-F8), `evidence/SCOUT_ADDENDUM.md` (facts A1-A8), `evidence/restart_timeline.txt`.
  Pending inputs: review workflow `wf_f47ecf9e-916` (5 verified dimensions + critic, on snapshot `17dce0c`) and 6 DIVERGE lenses
  (serving platform · agent-backend power user · release engineering/ops · simplification · model & quant · exposure/safety/legal).

## Situation in five lines
1. Production is **down** since ~23:45Z on 2026-09-18: running `f90bb44` (background-thread model load → ZeroGPU CUDA-emulation error).
2. HEAD `f88b120` **cannot import** (`_load_draft`, `_media_from_message`, `_resolve_image_urls` undefined; `images`/`videos` unbound); 1 of 73 tests fails. Last commit known to boot: `17dce0c`.
3. **Another agent is pushing to production every few minutes** with no lint/test gate; 6 earlier commit messages claim code that is not in the diff.
4. Even when up, every preset truncates: lease estimate assumes 22 tok/s vs ~9 claimed; ZeroGPU duration is an up-front quota reservation (PRO 40 min/day ≈ 22k output tokens/day at 9 tok/s).
5. Boot = 4m30s-5m05s (on-the-fly NF4 of 54 GB) racing a ~300 s auto-restart.

## No-decision-needed fix list (obviously right; will be done by whoever holds the pen — not grill questions)
- Define or remove the undefined names at HEAD; make the failing persona-archive test not depend on a file outside the repo.
- `TOK_PER_SEC`/`DURATION_CAP`/preset `gpu_size` must match what commit messages, README and UI text claim (single source of truth).
- `presence_penalty` is accepted everywhere but never reaches `generate()` (pending verification by the review).
- `async def` API route calls blocking generation on the event loop (pending verification).
- Delete dead weight: `hf_transfer` + `HF_HUB_ENABLE_HF_TRANSFER`, `HF_HOME=/data/hf` without storage, `idx.json`, `runlog_tail.txt`, `maintenance/keepalive.log`; README "55 tests".
- `maintenance/update_deps_and_deploy.py`: `bump_within_range` returns None for every spec form (verified) — fix or delete (see G-31).

## Decision queue v0 (35) — will be merged with lens + review output, then pruned by the foundation answers
Legend: ☐ open · ☑ decided · ✂ pruned by an earlier answer

### A. Foundation (asked first; they recolor everything below)
- ☑ **G-1 Single writer.** → DECIDED: lane split, both write (see Resolved decisions; follow-up G-1a).
- ☑ **G-2 Stabilize now?** → DECIDED: leave production down until the pipeline can promote a build.
- ☑ **G-3 Purpose.** → DECIDED: both workbench and agent gateway, equally.
- ☐ **G-4 Ambition envelope.** Money/complexity ceiling for usable speed (PRO quota only · occasional ZeroGPU credits · hourly dedicated GPU · local GPU).

### B. Platform, model, serving
- ☐ **G-5** Stay all-in on ZeroGPU + transformers, or hybrid (ZeroGPU UI + a different API backend), or move.
- ☐ **G-6** Keep the dense 27B as the only tier, or add/switch to a faster sibling (pending model lens).
- ☐ **G-7** How the pre-quantized checkpoint gets made: in-app export inside a GPU lease (current design) vs one-off HF Job / local / notebook.
- ☐ **G-8** Quant target: bnb NF4 prequant vs AWQ / GPTQ / FP8 (pending perf review).

### C. Leases and long outputs
- ☐ **G-9** Long-output strategy: chunked generation with lease chaining vs honest hard caps vs bigger single leases.
- ☐ **G-10** Token ceilings/defaults per preset given what a day of quota buys (slider max is 262144 today).
- ☐ **G-11** `xlarge` policy: never automatic (what the commit said) vs preset-selected (what the code does).
- ☐ **G-12** Rate calibration: measured EMA vs fixed conservative constant.

### D. Scope (simplification)
- ☐ **G-13** Target shape: lean chat · lean API backend · two Spaces · keep everything.
- ☐ **G-14** In-Space tool loop: keep 3 tool families · keep file bench only · move tool execution to the client harness.
- ☑ **G-15** `python_eval` → DECIDED: stays in-container, hardened per the spec in Resolved decisions.
- ☐ **G-16** Vision + video (added 2026-09-18 23:58Z, currently broken): finish now · defer until text path is solid · drop.
- ☐ **G-17** Speculative decoding: keep only if measured ON with logged acceptance · drop the draft model.
- ☐ **G-18** MCP server: narrow purpose-built tool · off · keep exposing `chat`.
- ☑ **G-19** Personas → DECIDED: neutral set, cleaned, improved and extended by Claude (see Resolved decisions).

### E. API
- ☐ **G-20** Contract ambition: strict OpenAI compatibility validated against SDK types vs "good enough for my harness".
- ☐ **G-21** Async job API (submit / poll / resume) for agents: build or not.
- ☐ **G-22** App-level API key on top of Space privacy.

### F. Security and exposure
- ☐ **G-23** Exposure model: private forever (hard-fail risky features if public) vs may go public later.
- ☑ **G-24** Token design → DECIDED with G-15: one narrowly scoped inference token in the app, exports off-Space, pasted token to be revoked by the owner.
- ☐ **G-25** Prompt-injection defaults: web tools default OFF · `http_request` GET-only while the bench holds files · as is.

### G. Process and operations
- ☐ **G-26** Source of truth: GitHub repo + CI deploy · HF Space repo as source · status quo (Windows folder `upload_folder`).
- ☐ **G-27** Staging Space (private duplicate) as mandatory pre-prod, or none.
- ☐ **G-28** Pre-push gate: contents (py_compile · pyflakes/ruff · unit tests · import-smoke with stubs) and where it is enforced.
- ☐ **G-29** Claim-vs-diff discipline for agent commits + post-deploy verification (running sha == pushed sha, canary generation).
- ☐ **G-30** Dev Mode policy: off by default, on only for interactive debugging.
- ☐ **G-31** Keep-alive + dependency updater: delete · move to GitHub Actions cron · fix in place.
- ☐ **G-32** Observability: per-call metrics line (prefill s, tok/s, lease requested vs used, spec acceptance) + quota telemetry; destination.

### H. Tests and docs
- ☐ **G-33** Make `app.py` testable (factory + injected generator), coverage target, CI.
- ☐ **G-34** README: claims audited/generated vs hand-maintained.

### I. Sequencing
- ☐ **G-35** Confirm the critical path: stabilize → gate → lease sizing → boot time → everything else.

## Resolved decisions (authoritative log — filled as the walk proceeds)
- **G-1 Single writer → DECIDED 2026-09-19: option 4, "both write, split lanes"** (against the recommendation). Owner keeps the
  other agent pushing and wants Claude writing too. Consequence to resolve in **G-1a**: the other agent deploys with
  `HfApi.upload_folder()` of its whole local folder (`deploy_space.py`), which overwrites every file with its local copy — any file
  Claude pushes is silently reverted by its next deploy unless it pulls first or restricts `allow_patterns` to its own lane.
  Until G-1a is decided Claude pushes nothing (grill invariant: no build mid-grill).
- **M-1 Token source → DECIDED 2026-09-19: "Hybrid: hosted first"** (recommended option). The selector routes each model to a
  hosted inference provider when it is live there (main model and DavidAU TURBO are, on featherless-ai); ZeroGPU only serves what
  nobody hosts, and acts as fallback. Accepted trade-offs: pay-per-use/subscription, prompts leave the Space for a third party,
  provider caps on context and tool calling. Follow-ups: **M-1a** billing route (HF Inference Providers routing vs direct provider
  key — pending platform-lens prices) · recolors **M-2** (in-Space serving shrinks to fallback + unhosted models), **G-9..G-12**
  (lease work now matters only for the fallback path), **G-20..G-22** (the provider router already is an OpenAI-compatible API).
- **G-3 Purpose → DECIDED 2026-09-19: "Both, equally"** (against the recommendation): personal multi-model workbench AND backend
  gateway for agent harnesses, same priority. Consequences: API items G-20..G-22 stay first-class; `app.py` must be split into a shared
  core (backends · agent loop · tools) with two thin surfaces (UI, API) so the two do not fight over one 1000-line file; the flat
  "chat only" hosted plan cannot cover the agent side (see lens digest) → feeds M-1a.
- **G-1a Lane protocol → DECIDED 2026-09-19: "GitHub repo, CI-only deploy"** (recommended option). A private GitHub repo becomes
  the source of truth; both agents push branches/PRs; ONE workflow (undefined-name lint + unit tests + claim-vs-diff check → boot on a
  private staging Space + 16-token canary) is the only writer to the production Space, with auto-rollback to the last good sha.
  Accepted trade-offs: ~10+ min per change (batching), no terminal hot-fixes, one-time setup, and **the other agent must stop
  deploying with `upload_folder`**. This also decides G-26 (source of truth = GitHub), G-27 (staging Space = yes), G-28 (gate
  contents + CI enforcement), G-29 (claim check + post-deploy sha/canary verification).
- **G-2 Stabilize → DECIDED 2026-09-19: "Leave it down until the pipeline"** (against the recommendation). No rollback, nobody
  touches production; the first production deploy is the new pipeline's first promotion from staging. Accepted trade-off: the Space
  stays down for hours. Implication: what Release 1 contains (M-5) now decides how long that is.
- **M-5 Release 1 scope → DECIDED 2026-09-19: "Everything in one release"** (against the recommendation). Production receives ONE
  promotion containing: pipeline + gate + staging, core/UI/API split, hybrid backends (hosted first + local ZeroGPU fallback),
  gateway hardening, expanded tool use, vision/video, and the full model catalog. Accepted trade-offs: production stays down the
  longest; the largest possible first load for a new pipeline. **Claude's default (no question needed):** one PRODUCTION release, but
  many STAGING promotions — every PR still merges small and must boot + pass the canary on staging, so "everything" is integrated
  incrementally and only revealed once. Every remaining scope question now defines what "everything" means.
- **G-15 + G-24 Code execution & credentials → DECIDED 2026-09-19: "Keep it in-container, hardened"** (not the recommended
  sandbox). Definition of "hardened" adopted as the build spec: (1) child env = explicit allowlist, never inherited; (2) parent calls
  `prctl(PR_SET_DUMPABLE, 0)` at startup — a same-UID child can otherwise read `/proc/<ppid>/environ` and `/proc/<ppid>/mem`, so
  scrubbing the child's env alone does NOT protect the parent's secrets; (3) rlimits CPU / address space / NPROC / FSIZE,
  `start_new_session=True` and `killpg` on timeout; (4) cwd = fresh temp dir, output capped; (5) enabled only by an operator secret
  flag — the UI checkbox and any API/MCP argument cannot turn it on by themselves; never reachable over MCP or `/v1`; (6) no token
  files on disk; checkpoint exports run off-Space (HF Job) so NO upload token lives in the app; the only credential in the container
  is one narrowly scoped inference token. **Residual risk accepted by the owner:** shared filesystem and open network (no namespaces
  available to block egress), so a flaw in (1)-(2) exposes that inference token. Owner still to do: revoke the token pasted in chat.
- **G-19 Personas → DECIDED 2026-09-19: "Neutral set, cleaned" + owner delegates to Claude: improve the existing personas and add
  specialized ones of Claude's choosing.** Ships WITHOUT the clause about wording prompts to get past other AI systems' filters
  (Claude does not write or tune that). README + tests made consistent; no dependency on an off-repo archive. Claude's delegated
  set (to be written during the build, each with role, output contract, tool-use guidance, quota-aware behaviour): Analyst (default) ·
  Research Analyst (sources, web tools) · Prompt & Agent-spec Architect (cleaned) · Code Engineer (file bench: read-before-edit,
  diffs, tests) · Security Reviewer (authorized scope, defensive findings format, no payloads — the original default's conservative
  rules) · Document & Vision Analyst (PDF/image/table extraction) · Planner/Operator (todo + memory tools, minimal tool rounds) ·
  Custom (always-editable box).
- **M-3 Catalog policy → DECIDED 2026-09-19: "Curated, evidence-gated list"** (recommended option). Checked-in `models.yaml`, one
  entry per slot, each with backend (hosted|local), repo + pinned revision, context, tool/vision flags and admission evidence;
  promotion only after the 12-prompt harness passes (speed, truncation rate, tool-call validity, checkable tasks). Starts from the
  scouts' table and includes the owner's three named models (coder3101's 27B as a local-only candidate). No free-text ids.
  This also answers M-4: coder3101's 27B competes for a local slot on harness results like any other entry.
- **M-2 Local layout → DECIDED 2026-09-19: "One worker Space, one model"** (recommended option). The UI/API Space becomes
  CPU-only (boots in seconds, no `spaces.GPU` in it); a separate private ZeroGPU **worker Space** holds exactly one resident model
  and is reached as one more OpenAI-style backend. Resident model = whichever measures better on the harness between FP8 main
  (`magiccodingman/…-fp8`, self-built copy to keep) and the GPTQ closest-to-base 27B; swapping it is a config PR. Accepted trade-off:
  only one unhosted model selectable at a time. Consequences: the draft model is deleted; lease work (deadline via `max_time`,
  resume, measured rate, no automatic `xlarge`) lives only in the worker; staging needs a staging worker too.
- **Work split → DECIDED 2026-09-19: "Platform vs product"** (recommended option). **Claude owns:** the pipeline (GitHub repo, gate,
  CI, staging, config-as-code, rollback), the core split, both backends (hosted router + ZeroGPU worker), the API gateway and MCP
  surface, tool-call reliability, the hardening spec, the eval harness. **The other agent owns:** UI / interface work, vision + video,
  persona wiring, README and docs, model-worker loading experiments (FP8 / GPTQ) — all through the same gate, as PRs. Accepted
  trade-offs: its PRs wait until the core split lands; the owner relays the hand-off brief to it.
- **Owner instruction 2026-09-19 (process):** do NOT converge until the background review workflow `wf_f47ecf9e-916` has finished;
  keep every subagent's full report, not just digests (saved verbatim under `evidence/reports/`).
- **G-1 / work split REVISED by the owner 2026-09-19 (later message): the other agent will NOT be working. Claude is the single
  writer and handles everything** — platform AND product lanes. G-1a stands (GitHub source of truth, CI as the only production writer,
  staging + canary): it now protects against Claude's own mistakes rather than against a second agent. The hand-off brief for the other
  agent is no longer needed; a stop-notice is still worth sending so it does not resume pushing.
- **Owner instruction 2026-09-19 (execution plan):** after the review workflow and the simplification retry finish → document their
  findings → go over ALL reports → synthesize a full plan → then author an ultracode workflow (Fable 5.1) that implements everything
  end-to-end with a verify → audit → implement → fix → critic → review loop until satisfied, then a final synthesizer. Before authoring
  it, research best-practice / SOTA workflow orchestration and design so the workflow has no weak spots or blind spots.
- **Owner instructions 2026-09-19 (later messages):** (a) run fan-outs at MAX concurrency — the Workflow tool caps at CPUs−2 (= 2 here),
  so lens fan-outs use parallel Agent-tool calls instead, and the owner should resize the Codespace (16-32 cores → cap 14-16) before
  the implementation workflow; (b) after the orchestration research, run a `gem-hunt`-style pass over everything learned and, where
  worthwhile, open a PR in `Prekzursil/agent-skills-toolchain` on GitHub with upgrades to the harness skills; (c) do the external
  research with the `deep-research` skill (Firecrawl/Exa/Tavily harness) — in this session only Exa, Context7, Consensus and HF docs
  are live, so the run routes over those and states the gap.
- **Answered in passing by the owner's expansion mandate (2026-09-19):** G-13 target shape = **maximal, not lean** (✂ simplification
  becomes sequencing) · G-6 = **multi-model selector** · G-14 = **keep and expand tool use** · G-16 = **keep vision/video** ·
  ambition half of G-4 = **"SOTA maximum on all levels"** (budget half still open → M-1).

## Captured new directions (from "Other" answers and lenses)
- **D-1 Three-model selector** (owner, 2026-09-19): main `heretic-org/Qwen3.8-27B-heretic-ara` + the two below.
- **D-2 Expand everything to SOTA** (owner): models, interface, capabilities, tool use, functionality, **loading time / fast Space**.
- **D-3 Curated catalog** (owner): "otherwise find the best heretic model, or add more specialized but SOTA heretic models".
  Selection is on engineering/capability merits only (capability retained vs base, speed / active params, context, tool calling,
  quant + hosted availability, licence, maintenance). Claude does not rank models by refusal behaviour.

### Verified model facts (Hub, read-only, 2026-09-19)
| Repo | What it is | Size | Notes |
|---|---|---|---|
| `heretic-org/Qwen3.8-27B-heretic-ara` (main) | Arbitrary-Rank Ablation of `Qwen/Qwen3.8-27B`, layers 26-56, card KL 0.0535 | 27.36B · 6 shards ≈ 54.7 GB bf16 + `model-auxiliary` 849 MB | Apache-2.0 · 10.0K dl · **live on inference provider featherless-ai** |
| `coder3101/Qwen3.8-27B-heretic-ara` | same method, different run | 27.36B · 2 shards ≈ 54.7 GB | Apache-2.0 · 459 dl · no provider · README within 51 bytes of main's, config differs → near-duplicate until measured |
| `DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU` | multi-stage full fine-tune of the same base | 27.78B · 12 shards ≈ 54.5 GB + `model-mtp-restored` 105 MB | Apache-2.0 · 9.7K dl · **live on featherless-ai** · card claims 1/2-1/10 the reasoning tokens · pre-quantized: `JC1DA/…-INT4-W4A16` (≈19.5 GB, transformers-loadable), `Solstice-AI/…-NVFP4`, GGUF+MTP, EXL3, MLX |

- The id the owner pasted, `DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-Heretic`, does not exist; resolved to the repo above
  (only TURBO safetensors repo by that author). Successors exist: `…TWIN-TURBO…709-L-Uncensored`, `…709-ULTRA-HERETIC-Uncensored`.
- All three share arch `qwen3_5`, the same base, and a chat template of 8952-8953 bytes (tokenizer identity still to verify).
- Physics: three 4-bit 27B models ≈ 55 GB resident — more than ZeroGPU `large`; all share one 40 min/day quota (≈22k output
  tokens/day at ~9 tok/s). ARA variants differ from the base by low-rank deltas on layers 26-56 → a **base + adapters** design is
  plausible for them; the DavidAU model is a full fine-tune and needs its own weights.

### Questions spawned (M-series, asked before the remaining G-items they recolor)
- ☑ **M-1 Where the tokens come from** → DECIDED: hybrid, hosted first, ZeroGPU fallback (see Resolved decisions).
- ☐ **M-1a Billing route** for hosted inference: HF Inference Providers routing (one HF token, HF billing) · direct provider key.
- ☑ **M-2 Multi-model architecture** → DECIDED: CPU-only UI/API Space + one ZeroGPU worker Space with one resident model.
- ☑ **M-3 Catalog policy** → DECIDED: curated, evidence-gated `models.yaml`; harness gate; no free-text ids.
- ☑ **M-4** → answered by M-3: it competes for a local slot on harness results.
- ☑ **M-5** → DECIDED: everything lands in one production release (integrated incrementally on staging).
- ☑ **G-1a Lane protocol** → DECIDED: GitHub source of truth, CI is the only production writer, staging Space promote-only.

## Lens digests (DIVERGE results as they land; sources are inside each lens report)
### Serving platform lens (done 2026-09-19)
- Hosted: Hub API shows `inferenceProviderMapping: featherless-ai = live` for the main model; callable at
  `https://router.huggingface.co/v1` as `heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai`; served in FP8. Featherless lists
  **$1.6 in / $0.15 cached / $12 out per 1M tokens**, tools supported; Developer plan ($50 monthly credit) allows agents + 256K
  context; the $25 flat plan is "human typed interactive chat use only", 32K. PRO's $2/month HF credit covers HF-routed calls.
  UNVERIFIED: tok/s, HF-routed price/context, pass-through of `reasoning_effort` / `preserve_thinking`, sampling knobs lost.
  **Cheapest way to learn all of it: one streamed request through the router with the owner's token (cents).**
- Architecture: all generation already passes one seam, `_gpu_generate()` (`app.py:527`) → add a pluggable OpenAI-compatible
  backend (`BACKEND_URL`); boot drops to seconds on a CPU Space; ZeroGPU can live in a second worker Space (PRO hosts 10).
- Pre-quantized checkpoint: build it as a one-off **HF Job** (`l40sx1` $1.80/h, est. < $1) instead of inside a GPU lease; community
  quants of the main model exist: `JC1DA/Qwen3.8-27B-heretic-ara-INT4-INT8-GPTQ` (22 GB), `cygnal/…-Q4_K_M-MTP-GGUF` (16.8 GB).
- Real engine option: vLLM supports the arch and drives the in-checkpoint **MTP head** (acceptance 0.77-0.90); est. 35 tok/s plain,
  60-70 with MTP on L40S ≈ $7-10 per 1M output tokens. transformers DISCARDS the MTP head (`modeling_qwen3_5.py:807`).
  ZeroGPU overage = ≈ $185 per 1M output tokens at 9 tok/s — never buy it.
- ZeroGPU limits are structural: no `torch.compile`; 48 of 64 GatedDeltaNet layers use the torch fallback unless `fla` /
  `causal_conv1d` are installed (`modeling_qwen3_5.py:199-248`, absent from requirements); each fresh worker re-uploads the 22.3 GB pack.
### Release engineering / ops lens (done 2026-09-19)
- 23 pushes in 2h35m; 12 of 22 gaps shorter than one boot. `py_compile` PASSES on the broken HEAD; an undefined-name lint
  (ruff F821 / pyflakes) finds exactly the three missing functions. A claim-vs-diff lint fails 5 of the 6 over-claiming commits.
- `08af7ea` flipped `app.py` to CRLF (1,992-line diff hiding a 2-line change) → `* text=auto eol=lf`. The pushing box appears to
  run Python 3.14; ZeroGPU supports 3.12 / 3.10 only. The failing test needs `_personas_archive/`, which `deploy_space.py` excludes.
- `upload_folder` never deletes (junk stays tracked); `restart_space` has no revision arg → rollback = a new commit;
  `set_space_volumes` REPLACES all mounts → two agents each adding one can unmount the model.
- Recommended operating model: private GitHub repo = source of truth; agents push branches/PRs; CI (Trusted Publisher OIDC, no
  stored token) is the ONLY writer to production; a private **staging Space** must boot + pass a 16-token canary before promote;
  auto-rollback to last known-good sha on hard signals; Space config as code (`space.yaml` + drift check); Dev Mode off in prod;
  retire the laptop keep-alive and the dead updater in favour of a scheduled CI health/telemetry check.
- Biggest unknown: who issues the ~300 s restarts — pause the other agent 15 min and watch whether they stop.
### Exposure / safety / legal lens (done 2026-09-19)
- `python_eval` child inherits the app environment (`web_tools.py:440-445`, no `env=`; reproduced) → `HF_TOKEN` + `NF4_UPLOAD_TOKEN`
  are reachable by model-authored code with raw sockets. The served models are public and ungated → **serving needs no token at all**.
- Risky features are caller-selected, not operator-gated: `python_eval` is a plain argument of `chat`, `mcp_server=True` publishes
  `chat`, `/v1` has no app-level auth. PRO's "protected" visibility keeps source private but **the running app is publicly reachable
  via its embed URL** (docs quote in the lens report). Recommended: fail-closed guard (secret flags) + boot tripwire on visibility.
- `trust_remote_code=True` at five call sites with no `revision=` pin (inert today, standing opt-in); `requirements.txt` partly
  unpinned; `keepalive.py` sends the same `HF_TOKEN` variable the deploy script uses to the Space every 12 h (inferred).
- NF4 export makes the owner the uploader of derivative weights: Apache-2.0 §4 needs a LICENSE copy + change notice; export writes
  neither. HF content policy has no private carve-out and does not name refusal-removed models.
- Personas: the swap changed vocabulary, not position — README still advertises the originals, git history holds them verbatim,
  and one clause of the "neutral" set keeps the original function (prompts for other AI systems worded to read as ordinary
  documentation). Which set ships is the owner's explicit call (G-19); Claude will not write or strengthen that clause.
### Agent-backend power-user lens (done 2026-09-19)
- **Speculative decoding is dead code:** `_is_stateful = True` (`modeling_qwen3_5.py:812`) makes `generate()` raise for assisted
  decoding (`generation/utils.py:1578-1583`); the app's fallback silently decodes plainly while the UI prints "spec-decode: on".
  The 2B draft model only costs boot time and VRAM. (Decides G-17 by evidence: drop it.)
- **`/v1` probably spends the wrong quota bucket:** the custom FastAPI route never sets `spaces`' request context, so leases carry
  `token=None`; Gradio docs call such requests "unauthenticated" (≈2 min/day tier vs 40 for PRO). Server-side bucket for a private
  PRO Space UNVERIFIED — measure with one short call and the billing meter.
- Lease end as a checkpoint: `max_time` stopping criterion (`stopping_criteria.py:93-115`) + `finish_reason:"length"` + stateless
  resume via `continue_final_message` (works inside reasoning content; `chat_template_utils.py:544-605`).
- Cost guard: past quota, ZeroGPU usage is "automatically billed" ($1/10 min ≈ $185 per 1M output tokens at 9 tok/s); the OpenAI
  SDK retries twice by default → one request can reserve three leases; Blackwell `large` reserves 1.5x requested seconds.
  → `/v1/preflight`, per-request `budget_seconds`, rolling 24 h ledger with a hard cap, truthful `/status`.
- MCP: replace the 21-parameter `chat` tool with typed `ask` / `poll` / `status` / `preflight`; hide `chat` (`api_visibility`).
- Tool-call reliability bugs reproduced in `tool_parse.py`: JSON-looking string params become dicts; enum violations and unknown
  args pass validation; truncated calls leak markup into `content`; a literal `</parameter>` truncates the value; JSON-mode failure
  appends prose to `content`; `/v1` neither returns nor accepts `reasoning_content`.
### Model & quantization lens (done 2026-09-19)
- **Prebuilt block-FP8 of the exact main checkpoint exists:** `magiccodingman/Qwen3.8-27B-heretic-ara-fp8` @ `ae4c4a3` (30.9 GB),
  transformers-native `FineGrainedFP8Config`, Triton kernel pulled from the Hub (`kernels-community/finegrained-fp8`, nothing to
  compile). A public ZeroGPU peer Space uses this path and budgets 0.045 s/token (≈22 tok/s) + ~21 s fixed cost per call. Trap
  reproduced: 65 skip-list `...mlp.gate` entries prefix-match `gate_proj` (`quantizers_utils.py:39`) → filter before loading.
  Removes the 4m14s quantize-at-boot; higher fidelity than NF4; pack grows ~18 → ~30 GB per cold lease. Decode gain UNVERIFIED.
- ~9 tok/s is not a hardware limit (dense 27B does 46 tok/s at Q8_0 in llama.cpp on the full card): decode runs pure-torch
  delta-rule code unless Hub kernels load (`modeling_qwen3_5.py:509-522`) and the `kernels` package is not installed.
  Cheapest test: one 128-token greedy lease with per-phase timing, NF4 vs FP8.
- Fast tier: Qwen3.8 has no small MoE; newest A3B is `Qwen/Qwen3.6-35B-A3B` (8 of 256 experts active). Verified derivatives:
  `trohrbaugh/Qwen3.6-35B-A3B-heretic-v2`, `llmfan46/…-Native-MTP-Preserved`, `protoLabsAI/Qwen3.6-35B-A3B-uncensored-heretic-FP8`
  (36.6 GB). bitsandbytes cannot quantize the fused 3-D expert parameters → **only FP8 fits `large`**. llama.cpp shows 4.2x A3B vs
  dense 27B; est. 2-3x in this stack. Quality cost per official cards: SWE-bench Pro 49.5 (A3B) vs 61.7 (3.8-27B).
- Draft model: never ran (see power-user lens); costs 18 s boot + ~4.5 GB of each cold-lease pack → delete. MTP head ships in
  `model-auxiliary.safetensors` (15 `mtp.*` tensors) but transformers drops it; llama.cpp MTP: 45.8 → 79.4 tok/s.
- Hard thinking budget: `reasoning_effort` is only a system-prompt sentence (`medium` adds nothing); add a LogitsProcessor that forces
  `</think>` after N thinking tokens, per preset, thinking off for tool rounds.
- 12-prompt backend-agnostic eval harness (TTFT, tok/s, length-truncation rate, think share, GPU-seconds, tool validity) so every
  model/quant swap is decided on measurements; keep each run near 2k tokens.
- Killed with evidence: NVFP4 in transformers (needs sm100+ at load; ZeroGPU emulates 9.0), AWQ/GPTQ (gptqmodel wheels unverified,
  no fused-expert support), DFlash drafts, `xlarge` for speed.
### Catalog scouts (2 of 3 done 2026-09-19; card-reported numbers, nothing was run)
Evidence-ranked, engineering merits only. "hosted" = Hub lists a live inference provider (featherless-ai) on 2026-09-19.
| Slot | Repo | Evidence | 4-bit build | Hosted |
|---|---|---|---|---|
| default 27B (current) | `heretic-org/Qwen3.8-27B-heretic-ara` | KL 0.0535; no benchmark on the checkpoint | `JC1DA/Qwen3.8-27B-heretic-ara-W4A16` 19.55 GB; FP8 `magiccodingman/…-fp8` 30.9 GB | yes |
| 27B, closest to base | `llmfan46/Qwen3.8-27B-Ultra-Uncensored-Heretic-Native-MTP-Preserved` | KL 0.0244; MMLU 83.42→82.82; MTP + vision kept; ships a rewritten 28.9 KB chat template (needs render-diff vs stock) | first-party GPTQ-Int4 19.56 GB | no |
| 27B, reasoning-efficient | `nerkyor/Qwen3.8-27B-EfficientThink-…-DFlash2` | same-harness vs base: GPQA-D 82.83→86.36, LCB-100 69→74, MMLU-500 90.2→88.4; reasoning tokens −6.6/−9.4/+2.9 %; no KL; no root config (needs `subfolder=`) | AWQ-W4A16 20.77 GB (vLLM-validated only) | no |
| 27B, owner-named | `DavidAU/…TURBO…-735-882-…-NM-DAU` | gains are 0-shot instruct scores on MLX mxfp8 (ARC-C 0.735 vs 0.591); token-reduction claim unmeasured; configs ship `use_cache:false` (must override) | `JC1DA/…-INT4-W4A16` 19.55 GB | yes |
| 27B, owner-named | `coder3101/Qwen3.8-27B-heretic-ara` | KL 0.0349 (better than main, worse than llmfan46); no MTP tensors; single 49.8 GB shard | none found | no |
| fast MoE | `llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved` | KL 0.0015; MMLU 83.71→83.39; 3B active of 35B (≤9x est., upper bound); vision, tools, 262K | first-party GPTQ-Int4 22.34 GB | **yes** |
| fast MoE, vision | `coder3101/gemma-4-26B-A4B-it-heretic` | KL 0.0499; 3.8B active; base card MMLU-Pro 82.6 | AWQ 17.19 GB (vLLM only) | **yes** |
| fast, text-only | `p-e-w/gpt-oss-20b-heretic-ara-v3` | KL 0.0554; native MXFP4 13.76 GB — lowest integration risk for a local MoE | repo itself | no |
| tiny | `heretic-org/Qwen3-4B-Instruct-2507-heretic` | KL 0.0741; 8 GB bf16 | none needed | **yes** |
| other family 31B | `llmfan46/gemma-4-31B-it-uncensored-heretic` | KL 0.0541; MMLU 86.50→85.90 | GPTQ-Int4 19.20 GB (QAT sibling) | **yes** |
- Duplicates/rejects with reasons are in the scout reports (e.g. `trohrbaugh/Qwen3.8-27B-heretic-ara` = byte-identical twin of main;
  TWIN-TURBO ULTRA is weaker than its siblings on its own card; NVFP4/GGUF-only repos are not transformers-loadable).
- bitsandbytes cannot quantize fused MoE experts → local MoE needs FP8/GPTQ/MXFP4, all UNVERIFIED on ZeroGPU. Hosted needs none.
- ZeroGPU docs now state `large` = half an RTX Pro 6000 Blackwell (48 GB), `xlarge` = 96 GB at 2x quota.
- **Third scout (coding · vision · tool-use/long-context), done 2026-09-19:** on card evidence the coding and vision slots are
  best filled by the model already listed — base Qwen3.8-27B reports SWE-bench Pro 61.7 vs 49.5 for Qwen3.6-35B-A3B and 51.2 for Muse
  Glimmer, and OmniDocBench 91.1. Only the tool-use/speed slot gains something new: `llmfan46/Qwen3.6-35B-A3B-…-MTP-Preserved`
  (hosted; ≈20 KB KV/token → ≈5.4 GB at 262K, derived). Extra hosted candidates: `llmfan46/gemma-4-31B-it-uncensored-heretic`
  (different vision encoder; MMMU Pro 76.9 on base card), `coder3101/Qwen3-VL-32B-Thinking-heretic-v2`,
  `llmfan46/Qwythos-9B-…-1M-uncensored-heretic` (1M context via static YaRN, only smoke-tested at ~137k),
  `llmfan46/gemma-4-12B-coder-…-heretic`. Caveats: every capability number quoted describes the unmodified BASE model (cards report
  only KL + MMLU/PIQA after processing); no finalist has a bitsandbytes build; GPTQ / auto-round / compressed-tensors kernels are
  unverified on ZeroGPU; one NVFP4 repo's "coding table" is the base card copied number for number.

## Evidence index (everything is saved in full; digests above are summaries only)
- `evidence/reports/lens-1…6-*.md`, `evidence/reports/scout-1…3-*.md` — verbatim final reports of every background subagent
  (lens 4 "simplification" was killed by a platform safeguard on its first run; retried 2026-09-19 on Fable 5.1, reframed under the
  decisions — result to be saved as `evidence/reports/lens-4-simplification-retry.md`).
- `evidence/workflow-findings.md` — all findings of review workflow `wf_f47ecf9e-916` with verifier verdicts, proofs and CORRECTED
  claims/fixes; `evidence/workflow-journal-snapshot.jsonl` — raw journal. **Re-export both when the workflow completes**
  (pending at last snapshot: verify:openai-api, verify:security-tools, critic).
- `evidence/feature-inventory.md` — lines per file + `app.py` top-level map at `f88b120` (5,276 lines total; `app.py` 1,158).
- `evidence/SCOUT_BRIEF.md`, `SCOUT_ADDENDUM.md`, `restart_timeline.txt`, `git_log_stat.txt`, `unittest_output.txt`.

## Review workflow digest (27 of 45 findings verified at snapshot; code at `17dce0c`)
Confirmed, high:
- **chat-loop-ui-1** Gradio strips the custom `bench_turn` metadata key → tool calls/results NEVER reach the next turn. Fix: carry the
  transcript in message text, only in the FINAL yield (`status='done'`), parse defensively (results may contain ``` fences), cap the
  replayed transcript, keep assistant tool_calls + tool results paired and BEFORE the final answer.
- **gpu-lease-1** lease estimator assumes 22 tok/s. Verifier: `max_time = lease_s - 30` is NOT safe — `MaxTimeCriteria` counts from
  `generate()` start while the lease clock starts at `schedule()` and covers worker fork + the 22.3 GB transfer on a cold worker →
  deadline from worker function entry minus a MEASURED cold-start margin; `max_time` cannot bound prefill; do not rely on the 1.5x
  Blackwell reservation factor; measure tok/s before seeding 9.2.
- **gpu-lease-2 / inference-perf-1** speculative decoding never runs (stateful model → `generate()` raises; app swallows and retries plain).
- **inference-perf-2** (partially) boot re-quantizes 54 GB every start. Verifier: quantize OFFLINE, never inside a lease; bnb NF4 offline
  needs a CUDA GPU or a bnb CPU build; **decide text-only vs VLM class BEFORE exporting** (a checkpoint saved from the causal-LM class
  has no visual tensors) → owner kept vision ⇒ VLM class; keep the bf16 mount as fallback until one boot on the new mount is observed.
Confirmed/partially, medium:
- **chat-loop-ui-2** `request=gr.Request()` is never injected → one global bench/state for every tab, API and MCP call. Fix:
  `request: gr.Request = None`; TTL sweep (evict benches idle > 1-2 h) — do NOT rmtree in `demo.unload` (fires on tab sleep / network
  blips and would destroy files mid-task); per-call throwaway bench for API/MCP callers.
- **chat-loop-ui-3** broad `except` hides ZeroGPU quota / illegal-duration errors. Fix: re-raise only when `rounds == 1 and not acc`;
  strip HTML from `HTMLError` messages; never append the notice to `acc`; set `interrupted` and skip tool execution that round.
- **chat-loop-ui-4** reply truncated inside `<think>` is re-rendered as the visible answer and saved into history.
- **chat-loop-ui-6** tool loop dead-ends silently at the round cap; rejected calls show "…"; no context budget while every round re-prefills.
- **chat-loop-ui-8** Continue needs its OWN encode path (`add_generation_prompt=False`; the fallback loop catches only TypeError while
  the clash raises ValueError); for a reply truncated inside thinking use `continue_final_message="reasoning_content"`; size the
  Continue lease from the remaining budget.
- **gpu-lease-3** lease chaining: take new ids from `generate()`'s RETURN value (the streamer yields text only); intercept the control
  dict in `_gpu_generate` for BOTH consumers (`"".join(...)` in `openai_protocol.py:613` would crash on a dict); id-equality test is
  valid for greedy only; size each chunk lease with measured cold-start overhead.
- **gpu-lease-4** up to 8 leases per turn, each reserving the full `max_new_tokens` budget.
- **gpu-lease-5** Stop releases the lease but never stops `model.generate`. Fix: StoppingCriteria + bounded `join`, plus a heartbeat
  (`yield ''` every ~15 s on `queue.Empty`) so the worker reaches its `stop_event` check; cannot interrupt prefill.
- **gpu-lease-6** `/v1` leases carry `token=None` and bypass the Gradio queue. Fix: set `LocalContext.request` INSIDE the generator body
  before `yield from _gpu_generate` (StreamingResponse runs each `next()` in a copied context); non-blocking semaphore → 429;
  `await run_in_threadpool(...)` for non-stream; FIRST log whether `x-ip-token` is present at all.
- **gpu-lease-8 / inference-perf-6** nothing measures decode or prefill rate → per-call stats record + EMA-calibrated estimate.
- **inference-perf-3** `presence_penalty` is a no-op (never in `gen_kw`; transformers 5.16.1 has no such option).
- **inference-perf-4** 48 of 64 GatedDeltaNet layers use the pure-PyTorch fallback. Verifier: check with
  `importlib.util.find_spec('fla')` / `('causal_conv1d')` (NOT `__wrapped__`); fla is imported in the GPU-less main process then
  inherited by the forked worker — device detection cached at import may be wrong; test on a duplicate Space, budget Triton JIT in the
  first lease; do not add `kernels` without checking a build exists for the image's torch/CUDA.
- **inference-perf-5** advertised 262K does not fit `large` as coded (KV 64 KiB/token = 16 GiB at 262K). Verifier: `prefill_chunk_size`
  BREAKS with the VLM class (position ids sliced on the wrong axis) → only with the text-only class, or not at all; first lower the
  slider ceiling, count prompt tokens before taking a lease, reject over-budget requests in the main process.
Low: gpu-lease-7 (`streamer.thread` does not exist → AttributeError after 180 s silence), gpu-lease-9 (retry loop can replay the
prompt), chat-loop-ui-5/7/9, inference-perf-7/8/9 — see the findings file. Note from the verifier: `fermicalva/…-MTP-FP8` is
compressed-tensors on a DIFFERENT ablation, not finegrained-fp8 of these weights — check provenance of any third-party quant.
Pending verification (finder claims only, do not act on them yet): openai-api-1…9, security-tools-1…9.
### Simplification lens — RETRY (Fable 5.1, done 2026-09-19; full report `evidence/reports/lens-4-simplification-retry.md`)
- Dead weight under the decided architecture: **≈2,270 lines deleted outright** (≈690 code/scripts + 1,586 committed junk; 32 % of the
  tree) + ≈210 lines relocated to the worker: draft model + spec-decode (never ran), in-app NF4 export + upload thread (→ HF Job),
  bnb quantize-at-load + flash-attn chain + `_generate_kwargs` retry ladder (→ one `from_pretrained` of a prebuilt checkpoint),
  import-time load / mount probing / lazy-boot remnants (→ `worker/app.py`), `api_generate` 17-kwarg pass-through (→
  `GenerationRequest`), `gpu_size` as a caller knob (→ catalog property), monkey-patched API mount (→ own FastAPI app +
  `gr.mount_gradio_app`), token-counter hook (usage arrives in the backend `Finish` event), `maintenance/` + `deploy_space.py` (→ CI),
  `idx.json` / `runlog_tail.txt` / `keepalive.log`, 7 of 9 requirements lines in the CPU front. `app.py` 1,158 → ≈20-line composition root.
- Module layout: `app.py` (composition root, nothing at import) · `core/types.py` (GenerationRequest, SamplingParams, Message =
  OpenAI content parts, Event = TextDelta | ReasoningDelta | ToolCall | ToolResult | Finish{reason, usage, timings, error}) ·
  `core/catalog.py` · `core/prompting.py` · `core/parsing.py` (tool_parse + incremental StreamParser) · `core/agent.py` (run_turn) ·
  `core/session.py` (SessionStore, TTL, explicit keys) · `core/engine.py` · `core/tools/` (registry = THE python_eval gate; file_bench,
  web, knowledge, state) · `backends/{base,hosted,worker,fake}.py` (Backend.stream(req) → Iterator[Event], health(), BackendError) ·
  `ui/build.py` (build_ui factory) · `api/{app,protocol,mcp}.py` · `worker/{app,encode,lease}.py` (the only file with import side
  effects is `worker/app.py`). Rule: surfaces → core → backends/tools; core never imports gradio/fastapi/spaces/torch — enforced by an
  import-contract test in the gate.
- The seam: `_gpu_generate(gpu_size, **kw)` is the right place at the wrong altitude (raw-markup str iterator, no finish reason/usage/
  error/cancel) → raise it to `Backend.stream(GenerationRequest) → Events`; parsing and media conversion move below it.
- Duplication to collapse (10 items): message assembly ×2, content flattening ×3, image placeholders ×2, parse/validate policy ×3
  (this divergence IS chat-loop-ui-4), thinking split ×4, usage block ×2, error-to-content ×3, 17 sampling kwargs spelled in 5 places
  (how `images`/`videos` went unbound at HEAD), stop normalisation ×3, tool dispatch ×4.
- Thinnest slice = what the canary needs (CPU Space, `/healthz` with git sha, `/v1/chat/completions` → HostedBackend → router, one
  `models.yaml` entry, placeholder chat via `gr.mount_gradio_app`); its first request doubles as the provider measurement and becomes
  fixture #1. 14 PR-sized steps with proofs (see report §D).
- Ship-but-flag (default OFF at launch): automatic hosted→worker fallback · server-side tools for `/v1`/MCP · `http_request` POST +
  third-party reader mode · video (images on) · automatic lease chaining (explicit Continue on) · cross-turn `preserve_thinking`.
- Characterisation tests BEFORE moving code: 10 pins (§F) incl. `_as_messages`, `chat()` with a scripted generator, `_render`,
  `_estimate` table, gen-kwargs, encode ladder, the 19 positional inputs kept in sync by hand, golden `/v1` transcripts, tool_parse xfails.
- Biggest risk: the seam gets shaped by whichever backend is built first → guard: spend the cents first — ONE metered streamed request
  through the router with a tool and thinking on, recorded as fixture #1, decides whether the provider returns structured
  `tool_calls`/`reasoning_content` or raw markup, i.e. where the parser lives; it becomes the first case of the conformance suite every
  backend (fake, hosted, worker) must pass.

## Orchestration research index (deep-think before authoring the implementation workflow; all in `evidence/orchestration/`)
| File | What | Size |
|---|---|---|
| `WORKFLOW_TOOL_REFERENCE.md` | Workflow tool contract + empirical notes from this session | reference |
| `research-1-doctrine.md` | owner's skills doctrine: 30 principles D-1..D-30, 17 anti-patterns, 9 conflict resolutions, **20 candidate skill upgrades** (input to the gem-hunt PR) | 325 lines |
| `research-2-tool-native.md` | Workflow-tool-native architecture: 25 principles T-1..T-25, 12 anti-patterns, full JS skeletons, FIFO scheduling data (cap-14 projection ≈ 26 min vs 52.5 min for the review run) | 689 lines |
| `research-3-external-sota.md` | external SOTA via web search: 25 principles S-1..S-25, 14 anti-patterns, 55 sources | — |
| `research-3-external-sota-DEEP.md` | external SOTA via the `deep-research` skill harness (Exa/Consensus/Context7/HF docs; Firecrawl/Tavily unavailable here): 22 principles, 12 anti-patterns, 88 graded sources | 92 KB |
| `research-4-red-team.md` | 47 failure modes F-1..F-47 with detection / guard / where; testability table; `gate.sh` spec; 8 script-level invariants | — |
| `DESIGN_BRIEF.md` | shared brief for the judge panel: inputs, non-negotiables, the 15 required sections | 42 lines |
| `design-A1-reliability-first.md`, `design-A2-throughput-first.md`, `design-A3-minimal-scaffold.md` | three independent designs (in progress) → judged → synthesized → critiqued → `design-v2-final.md` | pending |
- Security note from research-2: the review workflow's trigger message (the owner's first message, which contained a pasted
  credential) was relayed verbatim to its 11 subagents and is present in their local transcripts under `~/.claude/projects/`.
  Nothing was pushed; the credential must be revoked (already advised). Rule adopted for every later run: **the launch message of a
  workflow must never contain a secret** (T-2 / S-21).
- Cross-lens convergence worth noting (highest confidence): test author ≠ implementer with an oracle lock (D-6/D-15, T-6, S-4/S-5,
  DEEP S-3/S-5, F-18); refute-first with mandatory reproduction and default-refuted schema (D-16, S-11, DEEP S-8, F-12); deterministic
  gates decide, LLM judges only veto (D-24, S-17, DEEP S-9); bounded loops with typed `blocked` and dry counters (D-23, T-4/T-5,
  S-16, DEEP S-14, F-27); claims reconciled against the diff (D-17, S-20, DEEP S-20, F-19); owner checkpoints between runs for every
  outward action (D-28, T-1, S-19, DEEP S-19, F-35); replay-safe pure-function prompts pinned to a SHA (T-13/T-14, S-18, DEEP S-17/S-18, F-43).

## Design panel outcome (2026-09-19; files in `evidence/orchestration/`)
| Design | Angle | Agents (est.) | Wall-clock cap 2 / cap 14 | J1 red-team | J2 tool-contract | J3 program-fit |
|---|---|---|---|---|---|---|
| `design-A3-minimal-scaffold.md` | fewest mechanisms that still cover 102 rows; 6 roles | ≈240 | 18-20 h / 14-16 h | **4.20** | **4.15** | **4.40** |
| `design-A2-throughput-first.md` | admission scheduler, verifier ‖ refuter, cap-aware knobs | ≈325 | 16-18 h / ≈6.5 h | 3.95 | 3.45 | 3.70 |
| `design-A1-reliability-first.md` | maximal verification, 12-condition reducer | ≈740 | ≈41 h / ≈22 h | 2.90 | 2.80 | 3.40 |
- Unanimous winner: **A3**, as the base for `design-v1.md` (synthesizer) → `design-v1-critique.md` (blind-spot critic) → `design-v2-final.md`.
- Every judge reproduced blocking defects in every design (they executed the JS and traced the gates), e.g. A1's build loop throws on
  wave 2; A2's ledger-hash equality is unsatisfiable and a bare `null` aborts the run; A3's `repo_toplevel` exact match nulls every
  card, its journeys branch is never merged, and a null clean-gate reverts a good merge. All are on the synthesizer's work list.
- Grafts converged on by ≥2 judges: A1's timestamp-free gate digest with implementer-vs-verifier equality; A1's oracle reset diffed
  against the oracle + tamper scan; A1's revert-proof / negative control + mandatory mutants; A1's pre-verifier for UNVERIFIED findings;
  A2's gate self-test + integrity hash pinned in args + scan of the gate's own logs; A2's `semantic()` JS re-validation and
  `STAGING_RE` forcing; A2's critical-path ordering inside barrier waves; A2's R0 grounding trio; fail-closed judging.
- Gaps none of the three handled (now on the work list): timeout ↔ resume replay divergence; queue wait vs timers at cap 2; the
  external `gate.sh` copy unpinned; structured returns not secret-scanned before entering prompts; persona history reachable via
  `git show`; outward-action detection by self-report only; `/healthz` git-sha source inside a Space; one-scoped-token decision vs
  two backends; `presence_penalty` fate; fixture #1 as a merge precondition; `admission: pending` catalog policy; VLM-class export job.

## Session state note (2026-09-19 ~06:02Z, after restart)
- The weekly model limit killed the v2 reviser mid-run; session restarted (now on glm-5.3 max effort; claude.ai MCP connectors
  disconnected). The reviser's transcript survived in full and has been resumed; it was told its scratch (assembled v2 script, gate,
  drive, schema checks — and the critic's drive) was lost with the volatile scratchpad and must be recreated under
  `scratch/revise-v2/` in this folder, which the auto-sync loop now versions.
- Auto-sync loop restarted after the restart (`save-to-repo.sh`); PR #336 stays current.
- Also lost with the scratchpad (to recreate during build setup, as the design already specifies): the pinned gradio/spaces/
  transformers wheels under `libsrc/`, the Space clones (`space-src` @17dce0c, `space-latest` @f88b120), and the local test venv.
  Re-clone/re-download to a durable path before the build runs; the Space HEAD must be re-checked before anything is planned
  against it (it was changing minute to minute on 2026-09-18/19).

## design-v2-final.md produced (2026-09-19; final verification critic running)
- 2,516 lines · 385 KB · all 38 critic gaps resolved (Appendix B maps every C-id) · 158 coverage rows (136 v1 rows kept + 22 v2
  mechanism rows) · 22 cards, six roles, four stage runs (plan/build/stage/promote) + R0 grounding.
- Mechanical checks green: `bash -n` gate; 13/13 heredocs + 3/3 one-liners compile; schema walk 34 nodes clean; `node --check`
  both assembled forms; gate control-path dry run 22/22 (self-pin exit 66, typed RED ledger, identical LEDGER_DIGEST across two
  executions, conditional import-app, wheel-SOURCE apicheck with unresolvable-not-RED, journeys `needs=` counting, claim-lint
  fixture agreement, `--lint-base` scoping).
- Regression drive: 37 scenarios, **98/98 assertions** (critic's 21 adapted + 16 new blocking-gap variants); drive itself caught and
  fixed three real script bugs (protected-ownership contradiction; synthesizer blocked after HALT; not-ready promote advancing
  next_args.stage to done). Artifacts under `scratch/revise-v2/`.
- Estimates: ≈ 310-325 agents total (R0 11 + repair ≤2, R1 ≈ 275, R2 ≈ 25-30, R3 ≈ 8), ≤ 110 per invocation at cap 2;
  wall-clock cap 2 ≈ 25-27 h in 4-6 resumable invocations, cap 14 ≈ 18-20 h in 2-3. Timings remain extrapolations.
- Open owner questions (§15): Q1 resize · Q2 torch wheel in the gate venv · Q3 keep MCP · Q4 token topology · Q5 prompt-injection
  defaults · Q6 python patch level · Q7 worker checkpoint (VLM-class export job if neither candidate carries visual tensors) ·
  Q8 R2/R3 budgets · Q9 two recorded clarifications · Q10 policy for confirmed medium/low staging findings.
- A fresh-context FINAL VERIFICATION CRITIC is now auditing v2 (closure audit C-1..C-38, independent mechanical extraction
  document-vs-artifacts, its own adversarial drive of the NEW v2 mechanisms, loop/termination, authorability, cost realism) →
  `design-v2-critique.md`. Only a `ready` verdict (or a closed gap list) unblocks writing the PLAN and the implementation
  workflow script.
- **Final-critic verdict on v2 (2026-09-19): `revise`, narrowly** — 0 blocking · 3 major · 9 minor; closure audit **38/38** (34 clean,
  4 with an attached V-gap: C-23→V-1, C-4→V-2, C-19→V-3, C-2→V-4); document byte-identical to the reviser's artifacts; the critic's
  own drive 50/51 (the one failure = V-3, real) and its independent gate execution 10/10. Majors: V-1 receipt phrases still null the
  card in `assertCommon` (drive-proven) vs the log-only claim; V-2 journeys conftest specified by name only — the critic validated
  the correct path-scoped hook after two naive dead ends; V-3 plan-needs-repair emits `next_args.stage='build'` with empty defects
  (owner loops). All three sub-ten-line fixes; **reviser resumed to patch in place (v2.1) + extend the drive; with these applied the
  critic calls v2 ready to be the build standard.**

## DESIGN CLOSED — v2.1 is the build standard (2026-09-19)
- v2.1 patch applied in place by the reviser after the final critic: V-1..V-11 all fixed, 0 declined; drive **107/107 across 41
  scenarios**; dry run **22/22**; mechanical checks green; document byte-identical to artifacts; deviations declared (Appendix D;
  8-vs-9 minor tally note). sha256 `7742a9c8…`, 2,563 lines, 169 coverage rows.
- Coordinator spot-check confirmed the three majors by direct inspection: receipt match is log-only and the return stands;
  the pinned journeys conftest carries `import pathlib`/`import pytest`; S40 asserts plan-needs-repair routes `next_args.stage`
  back to `plan`. The mid-task stall was recovered by resume (transcript intact).
- **`PLAN.md` written** (launch view): owner prerequisites, local setup, R0→R3 sequence with checkpoints, the ten questions with
  defaults, exit criteria, gem-hunt parallel track. Next concrete steps: owner answers §6 (or "all defaults") + §3 prerequisites
  (token revocation, other-agent stop, resize, GitHub repo approval, fixture #1) → local setup → author the implementation
  Workflow script from design-v2 §13 → R0.

## LAUNCH (2026-09-19, owner: "run it now with subagents since you have no cap")
- Read as: proceed immediately, **ten defaults accepted** (vetoes still possible by number), executed through parallel Agent-tool
  subagents instead of the Workflow tool's CPU cap. Still owner-only (unchanged): GitHub repo creation, fixture #1 metered call,
   plan-hash approval, promotion.
- Setup receipts (build root `/home/codespace/build/qwen38-space`): gate copied + sha pinned `c96ef05c…`; gate venv Python 3.12.3
  (apt python3.12-venv; pytest 9.1.1 + pytest-socket; ruff 0.14.5; packaging); wheels extracted gradio 6.26.0 / spaces 0.51.3 /
  transformers 5.16.1 / huggingface-hub (179 MB); Space cloned — **upstream HEAD still f88b120, 0 commits after** (other agent
  stopped; matches the design precondition), base pinned at f88b120; remote URL cleaned of credentials.
- ⚠ The pasted HF token is STILL VALID (clone succeeded) — revocation remains outstanding.
- R0 grounding fan-out launched: findings symbolizer (with executed reproduction of critic-1..5) · API ledger from wheel source ·
  catalog provenance (public anonymous Hub reads only — claude.ai connectors are disconnected in this session).
- R0 grounding: **symbolizer done** (50/50 mapped; 32 re-anchored + 9 already-f88b120 + 9 wheel-only; repros 5/5 matched).
  Sharpenings absorbed into the plan: 5 undefined names over 9 sites at f88b120 (card 01 red-proof widened); the template
  hard-closes `</think>` + rstrip drops seam whitespace ⇒ `continue_final_message="reasoning_content"` is actively harmful,
  token-level seam only; the 1.5x lease factor is runtime-UNVERIFIED (silent H200 fallback = 1.0) ⇒ estimator must log it.
  `plan/decisions.json` drafted (21 rows incl. the accepted defaults). API-ledger + catalog-provenance still running.
- R0 grounding: **catalog provenance done** — 21 repos checked, all exist, pins recorded (40-hex); 9 provider-live (featherless;
  the mapping needs `expand[]=inferenceProviderMapping` — a default API read falsely shows none); 7/14 bases + 7 sidecars with
  verified 4-bit/FP8 builds; contradictions vs scouts recorded (coder3101 = 2 shards 54.71 GB not 49.8; "the JC1DA quant" is TWO
  repos — W4A16 auto-round 19.56 GB vs INT4-INT8-GPTQ 23.19 GB which declares NO LICENCE and is excluded; llmfan46 GPTQ keeps
  vision+MTP at weight level — 333 visual + 15 mtp — but ships no preprocessor_config; nerkyor AWQ folder internally inconsistent
  compressed-tensors vs NVFP4). **Resident-worker pin proposed: magiccodingman FP8 @ ae4c4a3… — 30.87 GB, 333 visual + 22 mtp
  tensors, preprocessor AND video_preprocessor present ⇒ satisfies the vision clarification; no VLM-class export job needed if it
  loads.** models.yaml proposal: 9 hosted + 1 local (pending admission) + 5 parked. API-ledger still running.
- R0 grounding: **API ledger done** — 39 verified / 6 known_bad (red-proofed both directions) / 1 unresolvable → FIXED by extracting
  the gradio_client 2.6.1 wheel (gradio's exact pin) into libsrc. Card-relevant: **BROKE** `prefill_chunk_size` on the VLM class
  (generic loop slices dim 0 = modality axis of the (3,b,s) mrope ids; per-chunk grid token-count checks unsatisfiable) — VLM worker
  must not set it, staging-gated at best; **CONFIRMED** X-IP-Token attribution (MCP forwards headers → caller bills; custom routes
  need `LocalContext.request.set(gr.Request(fastapi_request))` before the first yield); **BROKE** `spaces.GPU(gpu_size=…)` silently
  swallowed by `**kwargs: Unpack[EmptyKwargs]` — size only via the decorator's `size=` param; plus duration_factor 1.5 on Blackwell
  and >42 GiB models auto-flipping to xlarge. All three grounding agents complete; card drafting begins.
