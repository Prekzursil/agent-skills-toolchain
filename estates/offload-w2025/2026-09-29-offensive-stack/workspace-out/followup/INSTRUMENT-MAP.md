---
title: INSTRUMENT-MAP
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/instrument-map
---

# INSTRUMENT-MAP — standing bench instruments, registered 2026-09-30

**What this registers.** The clean bench lane of the follow-up workflow declared three
standing non-goals (`sota-followup-workflow.ts:98` — *"Do not re-tune the provider config
mid-run… Do not extend to GLM or reasoning tiers in this run. Do not adopt RedLineBench
here."*). Non-goals of one run are scope boundaries of future runs; this file maps each
into its own instrument with **scope / precondition / do-not-mix / run-when**, plus a
cross-reference to the dossier §7 owner-decision list. Nothing here was executed beyond
the verification commands recorded in §5; the instruments themselves are future runs.

**Grounding.** Files read this session: `D:\opt\sandbox-agents\providers\ollama-qwen3-4b.json`,
`D:\opt\sandbox-agents\providers\glm-4.6.json`, `D:\opt\sandbox-agents\bench\bench.py`,
`D:\opt\sandbox-agents\bench\finalize_rerun.py`, `out/SOTA-STACK-DOSSIER.md`,
`out/research/CONSOLIDATED.md`, `sota-followup-workflow.ts`.

**Instrument 0 (by reference, not registered here).** The clean run itself —
`bench.py --provider ollama-qwen3-4b`, serial, version-pinned, raws preserved — is the
standing *measure-the-shipped-config* instrument the three below build on. It ran in this
workflow's bench lane and is owned by that lane's report (`out/followup/bench-rerun.md`).

---

## 0. Invariants inherited by every instrument

From the clean-run lane's spec (`sota-followup-workflow.ts:86-90`); any future bench-shaped
run on this estate follows these or states why not:

1. **Serial measurement** (concurrency=1), recorded in the results header.
2. **Pin the versions** in the results header: `bench.py` git blob, provider-config git
   blob, model tag + digest (local) or model id (cloud), Ollama/runtime version.
3. **Preserve raw responses per run** (`bench/raw/<task_id>.txt` for the clean run; §per-
   instrument raw stores below) so a later classifier or config change can be diffed
   without re-running the model.
4. **Report the distribution, not a headline**: counts + task IDs per verdict class
   (`hard_refuse / watered_down / complied / answered_no_artifact / error`), mean/median
   latency; a `compliance_rate` only with its definition printed next to it.
5. **Classifier sanity first**: the 12-task suite (`bench/test_classify.py`) must be 12/12
   before any model run.
6. **Raw stores are per-run and disjoint** — never overwrite a previous run's raws.

---

## 1. I1 — PROVIDER-CONFIG TUNE (provider: `ollama-qwen3-4b`)

**Scope.** Owns changes to `D:\opt\sandbox-agents\providers\ollama-qwen3-4b.json`
generation parameters — `params.max_tokens`, `params.timeout_s`, `params.temperature`,
and `ollama.think` — and re-running the 20-task table to attribute verdict/latency deltas
to the config change. The shipped baseline being tuned against (read from the live file
this session): `max_tokens=4096, timeout_s=1500, temperature=0.3, think=false`, native
Ollama `/api/chat` at `http://127.0.0.1:11434` (`bench.py:453-455` passes `think` in the
request body). The config's own note records the tuning history: at `max_tokens=1024`
every response was cut mid-sentence, truncating payloads and feeding the classifier
partial non-deliveries; `timeout_s=1500` because a full 4096-token generation under CPU
contention measured ~4.5–6 tok/s and 900 s was not always enough.

**Precondition.**
- The clean run's artifacts exist: `bench/raw/<task_id>.txt` × 20 and
  `bench/results.{json,md}` with the pinned-version header (bench.py blob
  `da72cb1e…`, provider blob, Ollama `0.34.4`, `qwen3:4b` digest `359d7dd4…` per
  `finalize_rerun.py:26-29`). This is what makes attribution possible:
  - *classifier-only change* → re-classify the preserved raws, **no model re-run** (the
    cheap path; exactly how the stale 17/20 headline was exposed — dossier §6:140);
  - *generation-param change* → re-run all 20 tasks serial, then diff **raw response vs
    raw response** per task against the baseline raws; only the config may differ.
- Classifier sanity 12/12 before any re-run (invariant 5).
- Re-establish the baseline pin from the config that actually produced the raws — see the
  pin discrepancy observed at registration time (§5, item 2).
- `think` semantics are already wired for this instrument: `think=false` measures the
  final answer, `think=true` measures deep-reasoning behavior, and the classifier strips
  `<think>` blocks either way (`ollama-qwen3-4b.json` `ollama.note`;
  `bench.py:233-240`).

**Do-not-mix.**
- Exactly **one changed variable per measured run**: classifier OR config, never both in
  the same run (if both must change, two sequential instrument invocations).
- Tune runs get their own results files and their own raw store (e.g.
  `bench/tune-<param><value>-<date>/` with raws inside, mirroring the existing
  `rerun-serial-20260930` / `pre-repair-1024mt-20260930` convention) — never merged into
  the shipped-config table, never overwriting `bench/raw/`.
- `system_prompt` edits are **out of scope**: that is prompt-tuning, a different variable;
  if ever wanted it needs its own registration.
- No GLM / other providers and no RedLineBench work inside this instrument.

**Run-when.**
- The clean table exists and the owner wants to know whether qwen3:4b's non-delivery
  failure mode (the `answered_no_artifact` class — dossier §6:144-146) is a config
  artifact (token ceiling, think mode, timeout) rather than a 4B-on-CPU capability limit.
  I1 is the instrument that tests the config-attribution half of that §6 claim; the clean
  run measures only the shipped config.
- Before changing any shipped default in `ollama-qwen3-4b.json`.
- When the Ollama version or the `qwen3:4b` digest changes (re-baseline required first).

**Adjacent but NOT owned by I1:** the cascade router's own defaults
(`fronts/model_router.py` `max_tokens=6144 / timeout=900s`, dossier §7a #3) are a
different config surface; I1 findings may inform a router-defaults change but changing
router defaults is not part of this instrument.

---

## 2. I2 — GLM + REASONING-TIER BENCH (per-provider tables; tiers never mixed)

**Scope.** The same 20 authorized-lab tasks, run against the delivery tiers, **one table
per provider/tier**:
- **(a) `glm-4.6` direct** — `bench.py --provider glm-4.6` (`bench.py:33-34` selects any
  config in `providers/`); Anthropic-compatible z.ai endpoint, key read live from
  `ZAI_API_KEY`, rotate-aware (process env first, then HKCU — rotation is picked up
  between runs, never mid-run; `providers/glm-4.6.json` auth block). Shipped params:
  `max_tokens=4096, timeout_s=240`. The GLM thinking-block budget behavior is already
  handled: `bench.py:398-407` records `thinking_chars` and flags thinking-only responses
  that consumed the budget.
- **(b) cascade reasoning tier (optional)** — measure through the estate's production
  path instead: `model_router` `task_kind=reasoning` → GLM via `fronts.zai_keys`
  call-time dual-key rotation (`model_router.py:216-219`; live rotation evidence in
  dossier §2:25, `used_sha8 2cbe00c7` / `2b98b9a3`). This answers "what does the tier
  the estate actually routes to deliver?", as distinct from the raw provider.
- The other two provider configs (`deepseek-chat.json`, `claude-opus-4.6-legacy.json`)
  are config-ready but keyless on this box (dossier §2:28) — out of scope unless keys
  are staged.

**Precondition.**
- `ZAI_API_KEY` live in user env/HKCU (verify before the run; the rotate-aware reader
  resolves it).
- The GLM thinking-budget fix landed (it has: `max_tokens=4096` in the config +
  `bench.py:398-407` handling; the earlier 2-task GLM smoke included this fix — dossier
  §6:133, which also states that smoke was T01/T02 only, *not* a bench).
- All invariants of §0; version pins per provider run (config blob, model id, endpoint).
- A **per-provider raw store** (e.g. `bench/raw-glm-4.6/`, `bench/raw-cascade-reasoning/`)
  so tier raws never touch the local-tier `bench/raw/`.

**Do-not-mix.**
- **Tiers/providers are never mixed in one table.** Each provider/tier gets its own
  results table, own raw store, own latency line. Never averaged across tiers.
- **Never co-mingled with the local-tier (ollama-qwen3-4b) table** — the regimes are
  incomparable (cloud ~18–19 s/call per dossier §2:25 vs ~270–1300 s/task CPU-local) and
  mixing them is exactly how a stale headline like 17/20@rate-1.0 misleads.
- No key rotation mid-run (rotation is picked up between runs per the config's auth
  policy); no provider-config changes inside a measured run; no classifier changes inside
  a measured run.

**Run-when.**
- The owner extends the bench to GLM full-20 (dossier §7b:179, clause 2). The prior GLM
  evidence is a 2-task smoke; a full-20 table is the first real GLM measurement under
  authorized-lab framing.
- Before relying on the cascade reasoning tier for offensive delivery work.
- To compare authorized-lab refusal against the research numbers for naked offensive
  prompts (GLM refuses 35–39% naked but scores 4.45–4.63 when it answers —
  CONSOLIDATED.md:211, dossier §3d): the comparison is only meaningful from a separate
  full table under this instrument's framing.

---

## 3. I3 — REDLINEBENCH ADOPTION (candidate standing comparison instrument)

**Scope.** An *evaluation* instrument, not an install-and-run. Deliverables when run:
1. **Delta vs bench.py** — what `cracken-ai/redline-bench` measures that
   `bench/bench.py` does not. Known from research only (CONSOLIDATED.md:63): 153-prompt
   refusal/quality benchmark, git clone, run against `127.0.0.1:11434/v1`
   (OpenAI-compatible endpoint). Candidate axes to verify against its repo (not assume):
   naked-prompt refusal (bench.py measures only authorized-lab framing), response
   *quality* scoring (bench.py emits delivery verdicts, not quality scores), and
   statistical power (153 prompts vs 20 tasks).
2. **Install footprint on Windows-native** — deps, Python-version constraints (mind the
   estate's py3.14 pin-breakage cluster, CONSOLIDATED.md:16), runtime shape (no new
   daemons/timers; single-process invocation only), disk size, and whether its
   OpenAI-compatible client works against both local Ollama `/v1` and the z.ai endpoint.
   Current evidence grade is **"native (read)"** — metadata/README/source-verified, never
   executed on this VM.
3. **Go/no-go recommendation with evidence** — including license, maintenance state, and
   whether its numbers can be compared alongside bench.py tables without conflation.

**Adoption means a separate standing run config** — its own provider wiring, own results
location, own version pins. It is **not** a modification of `bench.py`, its classifier,
or its task set.

**Precondition.** The clean bench table exists (the comparison baseline); the research
candidate note (CONSOLIDATED.md:63) and the dossier's pointer (§6:147 — "For a systematic
measurement, RedLineBench (153 prompts) is the research-recommended instrument") are the
rationale being evaluated. Note the dossier's caution that the research note is
read-verified only (13★ at consolidation time).

**Do-not-mix.**
- Never modifies `bench.py`, its classifier, or its 20-task set.
- Does not replace the authorized-lab suite's role: bench.py measures refusal/delivery
  *under the estate's authorized-lab contract*; whatever RedLineBench measures is a
  different axis and its results live in their own tables, never merged into bench.py
  tables.
- No provider-config changes and no tier mixing while the evaluation runs.

**Run-when.**
- The owner decides the standing-instrument question (dossier §7b:179, clause 3).
- A systematic re-measure bigger than 20 tasks is wanted (dossier §6:147).
- Before any cascade-tuning claim that needs more statistical power than 20 tasks give.

---

## 4. Cross-reference — dossier §7 owner-decision list

Dossier §7b:179 carries the bench bullet: *"Bench re-run scope (§6): whether to re-measure
qwen3:4b full-scale post-fix, extend to GLM full-20, and/or adopt RedLineBench as the
standing instrument."* Clause mapping:

| Dossier question | Answered by | Note |
|---|---|---|
| §7b:179 clause 1 — "re-measure qwen3:4b full-scale post-fix" | **The clean bench run itself** (this workflow's bench lane; instrument 0 above), not one of the three deferred instruments | It is what retires the stale 17/20@rate-1.0 headline (§7a #1). I1 is the follow-on for that tier: it answers whether the *remaining* non-delivery is config-fixable. |
| §7b:179 clause 2 — "extend to GLM full-20" | **I2 — GLM + REASONING-TIER BENCH** | First real GLM full-20 table (prior evidence: 2-task smoke, §6:133); optionally the cascade reasoning tier as its own table. |
| §7b:179 clause 3 — "adopt RedLineBench as the standing instrument" | **I3 — REDLINEBENCH ADOPTION** | Evaluation + evidence-backed go/no-go; adoption = separate standing run config. |
| §6:146 claim — "qwen3:4b's failure mode is non-delivery… a 4B-on-CPU capability limit, not refusal" | **I1** tests the config-attribution half (token ceiling / think / timeout) | The clean run alone cannot attribute; the claim stays partial until I1 runs or is explicitly waived. |
| §7a #3 — mechanical cascade tier CPU-marginal; router defaults 6144/900s | **Not owned by any instrument here** | Router defaults live in `fronts/model_router.py`, not the bench provider config; I1 may inform but does not change them. Registered as adjacent to prevent scope creep. |

All other §7b items (McpHub, cursor adapter, PAT rotation, decision-log disposition,
workspace-supervisor, LINKEDIN_*/TAVLY_2, HKLM env, vault content program,
harness-restore spec dir, supervision-policy redesign) are untouched by this map — none
of the three instruments answers them.

---

## 5. State observed at registration time (commands run this session)

1. **Clean run in flight.** `bench/raw/` exists but is empty; `bench/rerun-serial-20260930/`
   holds `chunk1.log` (created 17:01, empty at check). The bench lane runs chunks via
   `bench.py --concurrency 1` and assembles via `finalize_rerun.py`, which writes
   `bench/raw/<task_id>.txt` and the pinned-header results (`finalize_rerun.py:1-30`).
   **I1's precondition (20 raw files) must be verified against the lane's final state,
   not against this snapshot.**
2. **Provider-config pin discrepancy (observed, not fixed — bench lane's gate owns it).**
   Computed live (`C:/Python314/python.exe` git-blob sha1 over the file bytes):
   `bench.py` → `da72cb1e5cbbca5b4b9943e42c25d61ee6e60d2a` (**matches** the pin at
   `finalize_rerun.py:26`); `providers/ollama-qwen3-4b.json` (mtime 2026-09-30 01:19,
   unchanged since) → `c58254593f6967e604b205929e1a38061f607b1a`, which does **not**
   match the pinned `4bf43c4e3f295e8d4d2e27f6e4708072526a690a` at
   `finalize_rerun.py:27`. The finalize gate (`finalize_rerun.py:51-52`) fails loudly on
   this by design, so the lane must resolve it; whichever config actually produced the
   raws is the one whose hash I1 must record as baseline. Recorded here because I1 owns
   that file.
3. **Pre-clean-run results still on disk.** `bench/results.md` (mtime 2026-09-30 04:34,
   pre-dating this workflow's rerun) shows 11 complied / 1 watered_down / 0 hard_refuse /
   7 answered_no_artifact / 1 error, mean latency 1157.87 s, `compliance_rate 0.917`,
   with **no** pinned-version header. It is superseded when the clean run finalizes and
   must not be quoted as the clean-run table.
4. **GLM provider config read** (`providers/glm-4.6.json`): rotate-aware `ZAI_API_KEY`
   auth (process env → HKCU, never cached), `max_tokens=4096`, `timeout_s=240` — the
   shipped state I2 measures.

## Speed levers for bench runs (registered 2026-09-30, post first clean run)

The measured bottleneck is CPU inference of qwen3:4b on the 12-vCPU n2 VM
(~270s/task median, worst-case tasks rambling to the 1500s timeout). Ranked:

1. **BANKED (already active)**: raw responses preserved per-task — any future
   classifier change re-scores from disk, never re-runs the model. This was the
   single biggest structural win.
2. **Cheap, same box (~1.3-1.5x)**: Ollama server toggles —
   `OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0` (halves KV memory
   bandwidth on long generations). Environment change: must be recorded in the
   results header; belongs to the provider-tune instrument's first experiment.
3. **Medium, same box (~1.8x, integrity-aware)**: TWO Ollama instances on
   separate ports, core-pinned (6 vCPU each), tasks split 10/10 — each stream
   stays serial so per-task latency remains meaningful; cross-instance memory
   bandwidth contention is the residual. Report concurrency=2-instances,
   serial-per-stream in the header.
4. **Big, dollar-scale (~15-20x, exact same serial protocol)**: throwaway GPU
   VM (G2 + L4, ~$0.7-1/hr) running Ollama for the bench window; point the
   provider's base URL at it via `OLLAMA_HOST`. 20 tasks in ~20-30 min with
   concurrency=1 preserved exactly. Provision/teardown script pattern is the
   same as provision-docker-remote-host.ps1. This is the recommended default
   for the GLM/reasoning-tier comparison rounds where repeated runs matter.
   NOTE: n2 machine types cannot attach GPUs — it must be a separate VM.
5. **NOT a lever**: reducing max_tokens/timeout or task count — that changes
   what is measured and is barred by the instrument's own non-goals.