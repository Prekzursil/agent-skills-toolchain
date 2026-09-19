
## 3. Agent roles and the separation table

Six roles; a `mode` narrows the task without changing rights; every call is a fresh `agent()`.

| Role | Modes | May write | May never | Votes on | Effort | Reading-list cap |
|---|---|---|---|---|---|---|
| **planner** (R0) | `plan` (incl. REPAIR MODE re-runs, C-19), `api-ledger` | `plan/**`, `AGENTS.md` on `plan/<nonce>` | code, tests, gate files | nothing | high (`api-ledger` medium) | resolved decisions + lens-4 §B-§F + CORRECTED lines + red-team §1-§3 + `plan/preverified.json` (+ its own prior plan and the defect list in REPAIR MODE) |
| **author** | `tests`, `journeys` | new test files under `tests/` on `tests/<id>-<nonce>` (journeys on `task/journeys-<tag>-<nonce>`); existing test files only when listed in `tests_allowed`; xfail/skip only for `xfail_allowed` ids; **persona cards copy the owner fixture verbatim (C-21)** | any non-test file; `system_prompt.py` history (persona card: history-free clone) | nothing | medium | card (verbatim, incl. the finding for fix cards, C-3) + `core` interfaces named in the card + api ledger |
| **builder** | `implement`, `fix` | `files_allowed` + `new_modules` + `required_files` + NEW files under `tests/unit/` on `task/<id>-<nonce>` | any existing test; protected paths outside the card's own manifest (C-21); `plan/**` (except `plan/status/` for the integrator); requirements outside `deps_allowed`; installs; outward actions | nothing (returns evidence) | high | card + decisions + api ledger + files in `files_allowed` |
| **verifier** | `plan`, `preverify`, `catalog`, `index`, `red`, `verify`, `refute`, `review`, `veto`, `evidence` | `.gate/mutants/<id>.json`, `.gate/*-<id>.json` (mode `verify`); `<grill>/evidence/catalog/*.json` (mode `catalog`) | any source/test file; any branch; approving | the ONLY role with a verdict; a `verify:pass` is admissible only when its `gate_digest` equals the builder's | medium; **xhigh** for `veto` and `risk:'security'` | mode-specific (§13 prompts) |
| **integrator** | `setup`, `merge`, `conflict`, `ff`, `revert`, `clean-gate`, **`fixcards` (C-3)** | `integration/<nonce>` (serial, single writer) incl. `plan/status/<id>.json` and **`plan/fixes/*.json` (mode `fixcards` only — the one mutable area of `plan/`)**; venv/tools under `/workspaces/space-build*` (mode `setup` only); bundles | task branches; source edits except conflict hunks | nothing | medium (`conflict` high; `merge`/`ff`/`revert`/`clean-gate`/`fixcards` low) | two cards + hunks (`conflict`); the fix cards verbatim (`fixcards`); nothing else |
| **synthesizer** | `report`, `fix` | `RUN-REPORT-<nonce>.md`, `build-bundles/<nonce>/status.json` | any branch, any code | nothing; its rows are overwritten by the script's table (mode `fix` rewrites the file when they differ) | low | the script-computed table + ledger summary (sorted) |

Separation (who authored what → who may judge it):

| Artifact | Authored by | Judged by | Never judged by |
|---|---|---|---|
| Pre-verification of an UNVERIFIED finding | `verifier mode:'preverify'` (executed probe, mechanically different from the finder's) | planner may only cite the recorded verdict; JS refuses a card citing a REFUTED id | the finder |
| Decision sheet, cards, DAG | planner | `verifier mode:'plan'` (refute-first) + `validateCards()` (throws) + JS (`against_recommendation` marks, REFUTED ids, manifest cards) + owner (C0) — **re-checked in every stage (C-19)** | planner |
| DoD tests | author | `verifier mode:'red'` (`gate.sh --only-tests` at `tests_head`: author-range tamper rules + RED for the expected reason + **digest equality with the author's own run, C-29**) | author, builder |
| Implementation diff | builder | `verifier mode:'verify'`: its own gate run must reproduce the builder's `LEDGER_DIGEST`; mutants; revert-proof (incl. builder-added `tests/unit/*`, C-28); DoD re-runs; `apicheck-extended` (C-18); `diff_stats` required (C-25) | builder (its digest is one half of the equality, never a verdict) |
| Merged tree | integrator | gate on the merged tree (digest returned) + `gate.sh --clean --self-test --journeys` per wave — **skipped only when nothing merged and the last clean gate passed at this head (C-38)** | the builder whose task was merged |
| Review fix cards | `verifier mode:'review'` + `mode:'refute'` (content) → **committed to `plan/fixes/` by the integrator `mode:'fixcards'` (C-3)** | the same inner loop (author → confirm-RED → builder → verifier) on the fix card | the reviewer (never its own fix) |
| Review findings | `verifier mode:'review'` (3 lenses) | `verifier mode:'refute'` (fresh, reproduction mandatory and **non-zero-exit on the defect, C-27**) | the reviewer |
| `satisfied` | JS predicate | `verifier mode:'veto'` (veto with reproduction only; a drop = `veto-unavailable`) | any agent |
| Run report rows | script | JS comparison; `synthesizer mode:'fix'` rewrites the file on mismatch | synthesizer |

Two preamble constants precede every prompt (§13): `PREAMBLE` (F-4; also demands `repo_toplevel` + `git_common_dir` and fixes the dummy-credential convention so fixtures cannot match the secret regex, C-32) and `AUTHORITY` (T-2: no push, no remotes, no repo/Space creation, no secrets, no `*.hf.space`, no HF Jobs, no token lookup, no installs, no foreground servers, no `git log/show` of `system_prompt.py`, no edits under `plan/` — except `plan/status/` for the integrator and `plan/fixes/` for the `fixcards` mode).

---
## 4. Task model

### 4.0 The decision sheet (`plan/decisions.json`) — law; carried here so the owner reads it in the design, written by the planner, refuted by `verifier mode:'plan'`, marks asserted in JS (F-9)

| id | decided (DQ line) | against rec. | build consequence |
|---|---|---|---|
| G-1 (original) | both write, split lanes (85) | **yes** | superseded by the revision below; kept as a row so the sheet is complete |
| G-1 REVISED / work split REVISED | Claude is the single writer, platform AND product (150-153) | — | no hand-off brief; product cards are ordinary cards in the DAG; the other agent's scheduled tasks are still guarded (F-38: `production_space_head` precondition) |
| M-1 | hybrid, hosted first (90) | — | `backends/hosted.py` first (card 03b); worker second; automatic fallback ships OFF (flag) |
| G-3 | **Both, equally** (96) | **yes** | core/UI/API split (cards 02-08); API items first-class (07, 11, 12 stay in R1; Q4 deleted) |
| G-1a / G-26-29 | GitHub SSOT, CI-only production writer, staging + 16-token canary, gate = F821 + tests + import smoke + claim-vs-diff, rollback (100) | — | card 01 gate; card 14 CI/promotion-as-code written + unit-tested, never executed in R1; `build_info.json` written by CI at deploy (the `/healthz` sha source); **a placeholder `build_info.json` with `git_sha: "unknown"` ships in card 03b so `/healthz` is testable and the canary rejects `unknown` (C-34)** |
| G-2 | leave it down until the pipeline (106) | **yes** | no rollback commit; nothing in any run touches production; the first production deploy is R2's promotion |
| M-5 | everything in one release (109) | **yes** | one production promotion; many staging promotions; every card PR-sized and staging-promotable |
| G-15 + G-24 | keep it in-container, hardened, six points (115) | **yes** | cards 09a/09b: (1) env allowlist (2) `prctl(PR_SET_DUMPABLE,0)` (3) rlimits inside a runner + `start_new_session` + `killpg` — **no `preexec_fn`** (4) fresh cwd + output cap (5) **enabled only by an operator secret flag; the UI checkbox and any API/MCP argument cannot enable it; never reachable over MCP or `/v1`** — card 05a DoD line + `tests/test_python_eval_surfaces.py` (protected) + seam H4 (6) no token files; exports off-Space (HF Job); one narrow inference token |
| G-24-clar (needs owner approval) | one fine-grained token = inference-provider scope + read on the private worker Space; two tokens only if HF cannot combine | — | card 08b reads `HF_TOKEN` for both unless `WORKER_TOKEN` is set; C1 `set-staging-secrets` records `token_topology` |
| G-19 | neutral set, cleaned, extended by Claude; no filter-evasion clause; README + tests consistent; no off-repo archive (124) | — | card 13b (history-free clone; owner-generated shingle-hash fixture; absence test protected); card 01 makes the persona-archive test repo-local **and delivers `tools/make_boundary_fixture.py` (C-21)** |
| M-3 / M-4 | curated evidence-gated `models.yaml`; harness admission; no free-text ids (132) | — | card 12 harness; card 13a catalog with provenance + `admission`; gate catalog step |
| M-3-clar (needs owner approval) | pending entries hidden from the selector and `/v1/models`; ≥ 1 `passed` entry before promotion | — | `core/catalog.py.visible()`; `tests/test_catalog_policy.py` (protected); C2 `run-harness` |
| M-2 | one worker Space, one resident model; draft deleted; lease work only in the worker; no automatic `xlarge` (137) | — | cards 08a/08b; `gpu_size` is catalog config; `assistant_model=` is a known-bad idiom |
| G-16-clar (from inference-perf-2/-5/-7 CORRECTED) | vision kept ⇒ **the worker keeps the VLM class (`AutoModelForImageTextToText`)**; `prefill_chunk_size` forbidden while that class is loaded (blocking idiom); `trust_remote_code=True` dropped; **the resident checkpoint must carry `model.visual.*`** | — | R0 catalog agent records `has_visual_tensors`; card 08c (owner decision; export HF Job if neither candidate has them); gate catalog step requires `has_visual_tensors` on local entries |
| Continue-clar (gpu-lease-3 CORRECTED + critic-4) | continuation at **token level**: worker yields a control record `{"__ctl__": {"new_ids", "finish", "prompt_len"}}`; next lease gets `prefix_ids`; `continue_final_message` only for a user Continue on a finished non-thinking turn | — | card 08a (CPU test with a fake generate: seam integrity; greedy equality) + seam H1; `continue_final_message=…reasoning…` is a blocking idiom |
| Kernels-clar (inference-perf-4 CORRECTED) | positive boot probe `importlib.util.find_spec('fla')`/`('causal_conv1d')` printed at boot; `flash-linear-attention` tested on the STAGING worker only; Triton JIT budgeted in the first lease; no `kernels`/`use_kernels` without a build check | — | card 08a (probe line, CPU-testable) + card 08d (staging-required DoD lines → runbook rows) |
| presence-penalty (inference-perf-3 CORRECTED) | LogitsProcessor + CPU test **or** remove the placebo (§15 Q2; default remove) | — | card 08a (`worker/penalty.py` **only when `args.torch_in_venv` — the manifest is derived from the decision, C-14**) or cards 06/07 (remove slider/preset/README sentence; API 400 unless 0) |
| G-13/G-6/G-14/G-16 | maximal, multi-model, expand tools, keep vision/video (164) | — | ship-but-flag decides sequencing (§4.6); video OFF at launch, images ON |
| Owner process | max concurrency; resize before the implementation workflow; keep full reports (158) | — | `args.cap`/`wave_size`; the setup probe asserts `nproc`; full reports under `evidence/`. **V2 adds two owner fields:** `owner_approvals.persona_boundary_fixture_sha256` (the sha the gate pins with `--boundary-sha256`, C-21) and `owner_approvals.accepted_findings` (the ids of confirmed medium/low staging-evidence findings the owner explicitly accepts — recorded data, never inferred, never usable for critical/high; the acceptance policy itself is §15 Q10) |

### 4.1 The card (one PR-sized task) — `plan/cards/<id>.json` on `plan/<nonce>`, merged into `integration/<nonce>` by the setup stage so every worktree can read it; review fix cards live on the mutable `plan/fixes/` and are committed there by the integrator (C-3) (schema §9.1)

| Field | Rule |
|---|---|
| `id` | `<lane>-<nn>[a-d]-<slug>`; sorted order = default priority; review fix cards are `platform-00-rf<round>-<nn>-<slug>` |
| `path` | `plan/cards/<id>.json` for plan cards, `plan/fixes/<id>.json` for review fix cards; every prompt names the path AND carries the card content verbatim (C-3), so a gate never reads a file an agent did not write |
| `step` | 1-14 (lens-4 §D) |
| `decision_ids[]` / `finding_ids[{id, corrected_text}]` | the card quotes ONLY the decided value / the CORRECTED line; **JS throws if a cited finding has no `corrected_text`**; a REFUTED id (from `plan/preverified.json`) may not be cited |
| `files_allowed[]` / `new_modules[]` / `required_files[]` / `deps_allowed[]` | the builder's write set; any hunk outside it, any hunk under `plan/`, any requirement outside `deps_allowed` fails gate step 8. `required_files[]` names files the card must have delivered (its manifest); **`new_modules ∪ required_files` is what `--require` passes to the gate — validated at plan time against the design's `MANIFEST_MIN` (C-14)** |
| `tests_allowed[]` | test files the AUTHOR may create or modify; the builder may only ADD under `tests/unit/` |
| `xfail_allowed[]` | test ids (`file::name`) that may carry xfail/skip — the lens-4 §F known-bads only (`verifier mode:'plan'` refutes anything else); replaces every `Skip-Added:`/`Tests-Removed:` trailer (J1 CG9) |
| `expected_green_tests[]` | test ids that are green on the base tree BY DESIGN — characterisation pins and contract tests (C-13). Confirm-RED requires RED for everything else and GREEN for exactly these, on both the author's and the verifier's execution; the plan verifier refutes any id that is not a lens-4 §F pin or an old-tree contract test |
| `tests_removed_expected` | integer, default 0; the collected floor is `baseline − Σ tests_removed_expected` |
| `est_lines` / `est_minutes` | sizing for the rank order and the scope-expansion check (`changed ≤ 2 × est_lines`); **`est_lines` must fit the size class (S ≤ 120, M ≤ 300) or validation throws (C-13: card 01 is size M because the gate copy + fixtures + skeleton are ≈ 300 lines)** |
| `dod[]` | ≤ 8 lines `{id, command, expect, verification_level}`; every command runnable on CPU under `$VENV`; **no `-k/-x/--deselect/--ignore/--lf` or `|| true`** (JS + gate); `staging-required`/`owner-required` lines are `deferred`, never `pass` (F-37); JS raises the level when the text matches `STAGING_RE` |
| `depends_on[]` | acyclic (JS) |
| `size` | `S` (≤ 120 lines) or `M` (≤ 300); `L` throws at validation |
| `protected_touch` / `bootstrap` | `bootstrap` is false on every card (the profile exists only for the setup red-proof at `base_sha`; JS throws otherwise). **Protected paths are owned, not banned (C-21):** a write-set hit on a protected path is accepted only when the card's own manifest declares it (`MANIFEST_MIN[id]`) or the card carries `protected_touch` (platform-01-gate); anything else fails validation and the gate's scope step |
| `risk` | `none | security | persona | catalog`; `security` → reading list ≤ 6 files, verifier `xhigh`, and a DoD line about surfaces/operator flag (JS); `persona` → history-free clone, G-19 role names only, the FIXTURE COPY STEP; `catalog` → provenance fields mandatory |
| `apis_expected[]` | symbols the gate's apicheck imports from the pinned wheels; unresolved-without-torch symbols are recorded `unresolvable-needs-torch`, never RED (C-16) |
| `owner_precondition` | an `owner_approvals` field that must be non-null before the card may build (`fixture1_path` on 04, `persona_boundary_fixture_path` on 13b, `worker_checkpoint_decision` on 08c) — typed `blocked_on_owner` with the field, the why and the next action (C-22) |

### 4.2 How the 14 steps become 22 cards (the planner's default split; C0 approves) — CORRECTED finding ids inlined; v2 changes marked

| Card | Step | What it builds | deps | risk | Findings carried (CORRECTED text inlined in the card) | Owner precondition |
|---|---|---|---|---|---|---|
| `platform-01-gate` (**M in v2**, bootstrap red-proof at P0 only, protected) | 1 | import at `f88b120`, junk deletion, `.gitattributes`+`.editorconfig` then a `Renormalize-Only: yes` commit, `tests/protected.txt`, `ruff.toml`, `pytest.ini` (excludes `tests/live/`, defines `staging_required`, **deselects the `journey` marker from every default run, C-4**), `tools/gate.sh` (repo copy == pinned bytes), `tests/test_constants_pin.py` **+ the `config.py` skeleton with every §4.6 flag so the pins are green within this card's own gate run (C-13)**, `tests/test_import_contract.py`, `tools/stubs/{torch,transformers,spaces}` (import-only stubs for the worker import smoke), `tests/fixtures/gate/false-claim.patch` + `false-claim-target.txt` (the gate self-test's fixture targets, C-2), `tests/journeys/conftest.py` (the `journey` marker, C-4), `tools/make_boundary_fixture.py` (C-21), persona-archive test made repo-local | — | — | security-tools-6 (`apply_patch` EOL/newline — tracked here, fixed in 09c) | — |
| `platform-02-pins` (M) | 2 | author writes the 10 pins of lens-4 §F (RED via `new_modules` ImportError); builder moves pure functions verbatim into `core/` (`--color-moved` shows moves only, `moves_only` in `diff_stats`) | 01 | — | tool_parse known-bads as `xfail_allowed`; §C items 2, 8 (DoD lines, §4.7) | — |
| `platform-03a-types-fake` (M) | 3 | `core/types` (GenerationRequest, SamplingParams, Message, Event), **`core/engine.py` (C-36: previously delivered by no card)**, `backends/base`, `backends/fake`, FakeEngine, conformance suite skeleton (rows `fake` / `recorded-hosted` skipped-needs-owner, `provenance`), `tools/record_fixture.py --i-accept-cost` | 02 | — | §C items 1, 3, 6, 7, 9 | — |
| `platform-03b-thin-slice` (M) | 3 | `api/app` with `/healthz` reading `build_info.json` (`git_sha`, fallback `git rev-parse`, else `unknown` which the canary rejects), `/v1/chat/completions` relay, `backends/hosted`, one `models.yaml` entry with provenance, placeholder chat via `gr.mount_gradio_app`, **placeholder `build_info.json` (`git_sha: "unknown"`, C-34)**; **its own gate command runs BOTH collections — the default suite and `--journeys` — so card 03b can be green before any journey exists (C-1/C-4)** | 03a | — | openai-api-1/2 (disconnect stops the generator; SSE framing) | — |
| `platform-04-streamparser` (M) | 4 | `core/parsing.StreamParser`, `core/events`, error taxonomy, `reasoning_content` in/out; pins flip; the recorded fixture becomes conformance case #1 | 03b | — | openai-api-3/5/9, chat-loop-ui-4; §C items 4, 5 | **`fixture1_path`** (C-M) |
| `platform-05a-registry` (S) | 5 | tool registry = THE `python_eval` gate; **G-15 (5) verbatim**: operator secret flag only, checkbox/API/MCP cannot enable, absent from `/v1` and MCP toolsets; `tests/test_python_eval_surfaces.py` (protected) | 04 | security | security-tools-8, chat-loop-ui-2; §C item 10 | — |
| `platform-05b-agent-session` (M) | 5 | `core/agent.run_turn` (rounds cap, one rejection round, pairing, prompt-token budget before any backend call, titled notices), `SessionStore` (TTL sweep, explicit keys, per-call bench for API/MCP, never `rmtree` in unload) | 05a | — | chat-loop-ui-1/3/6, gpu-lease-4, security-tools-8 | — |
| `product-06-ui` (M) | 6 | `build_ui(FakeEngine)`: selector (visible catalog entries only), presets, personas dropdown, render, history replay as JSON in the FINAL yield, explicit Continue, grouped settings; `presence_penalty` control per the Q2 decision | 05b | — | chat-loop-ui-1/8/9, critic-2 (`_user_text` both shapes) | — |
| `platform-07-gateway` (M) | 7 | API key opt-in, size/role/range validation before any backend call, threadpool + disconnect watcher, non-blocking semaphore → 429, ledger, `/v1/preflight`, `/status`; `x-ip-token` bound inside the generator body | 03b | — | openai-api-1/2/7/8, gpu-lease-6 | — |
| `platform-08a-worker-pure` (M) | 8 | `worker/encode.py` (encode ladder catching ValueError; `continue_final_message` only for a finished non-thinking user Continue), `worker/lease.py` (estimator rows at measured-or-UNVERIFIED rate, `max_time` = worker entry − measured cold-start margin, **token-level continuation**: control record + `prefix_ids`, stop event → StoppingCriteria, heartbeat, stats record), boot probe line printing `find_spec('fla')`/`('causal_conv1d')`, **`worker/penalty.py` ONLY when `args.torch_in_venv` (C-14)** | 03a | — | gpu-lease-1/3/5/7/8, inference-perf-4/-6, critic-1, critic-4 | — |
| `platform-08b-worker-backend` (M) | 8 | `worker/app.py` (import-time load with **`AutoModelForImageTextToText`**, no `trust_remote_code`, no `prefill_chunk_size`, `@spaces.GPU(size=…)` from the catalog), `backends/worker` (`gradio_client` with the token from env: `WORKER_TOKEN` or `HF_TOKEN`), fallback order OFF, cancel plumbing | 08a, 04 | — | inference-perf-2/-5/-7, gpu-lease-3 (control dict intercepted for BOTH consumers) | — |
| `platform-08c-worker-checkpoint` (S) | 8 | `models.yaml` local entry for the decided candidate (`has_visual_tensors: true` required by the gate), `tools/export_checkpoint.py` (VLM class; runs off-Space as an HF Job; unit-tested against a fake), runbook rows for the bf16-mount fallback until one boot is observed; DoD `staging-required` | 08b, 13a | catalog | inference-perf-2 CORRECTED | **`worker_checkpoint_decision`** |
| `platform-08d-kernels` (S) | 8 | `flash-linear-attention` in the worker requirements behind a flag; Triton JIT budgeted as `overhead` in the estimator's first lease; DoD lines `staging-required` (measured on the staging worker only; never on production) | 08b | — | inference-perf-4 CORRECTED | — |
| `platform-09a-pyeval-env` (S) | 9 | env allowlist, `prctl(PR_SET_DUMPABLE,0)` at startup, canary-secret red-proofs (never prints an environment) | 05a | security | security-tools-1 | — |
| `platform-09b-pyeval-runner` (S) | 9 | `-I runner.py` with `setrlimit` inside the child, `start_new_session`, `killpg`, fresh cwd, output cap; **no `preexec_fn`** (blocking idiom) | 09a | security | security-tools-1 CORRECTED | — |
| `platform-09c-net-guards` (M) | 9 | SSRF opener (resolve once, dial the literal IP, redirect validated before the hop, ports), `regex` timeout, calculator allowlist, archive caps, `apply_patch` ambiguity/offset/EOL/newline, network-origin neutraliser + narrow taint rule | 05a | security | security-tools-3/4/5/6/7/9 | — |
| `product-10-vision` (M) | 10 | OpenAI content parts end-to-end on the fake backend; caps; `vision:false → 400` with zero backend calls; video OFF (flag), images ON | 04, 06 | — | critic-2, chat-loop-ui-9 | — |
| `platform-11-mcp` (S) | 11 | `ask/poll/status/preflight` via `gr.api`; `chat` hidden; listing snapshot = 4 typed tools; exists only if G-18 keeps MCP (§15 Q3) | 05b, 07 | — | chat-loop-ui-7, security-tools-2 | — |
| `platform-12-harness` (M) | 12 | 12-prompt harness, `--backend fake --dry-run` default, zero-call test, `--i-accept-cost` + owner env var, `max_retries=0`, cost ledger, admission schema, evidence JSON per entry | 03b | — | gpu-lease-4 (cost) | — |
| `product-13a-catalog` (S) | 13 | `models.yaml` fill from `evidence/catalog/*.json` (`revision` 40-hex, `provenance{source_url, fetched_at, saved_path}`, `admission: pending|passed|failed`, `has_visual_tensors` on local entries), `core/catalog.py` (`visible()` hides pending — M-3-clar), `tests/test_catalog_policy.py` (protected), `tools/render_readme.py --check`, **`evidence/catalog/README.md` — the R0 catalog raw reads copied into the repo so the gate and CI can read them (C-34)** | 12, 03b | catalog | — | — |
| `product-13b-personas-readme` (M) | 13 | G-19 set (8 roles, role/output contract/tool guidance/quota-aware behaviour), wiring, absence test against the shingle-hash fixture (protected), README rendered from catalog + registry + collected count; **the FIXTURE COPY STEP copies `owner_approvals.persona_boundary_fixture_path` to `tests/fixtures/persona_boundary.json` and its sha256 must equal `persona_boundary_fixture_sha256` (C-21)** | 06, 13a | persona | — | **`persona_boundary_fixture_path`** (C-Q) |
| `platform-14-promotion-ci` (M) | 14 | **`.github/workflows/{gate,deploy-staging,promote,health}.yml`** (OIDC, `permissions:` blocks, SHA-pinned actions, `production` environment; the four filenames the required-files check asserts, C-14/C-34), **CI writes `build_info.json` at deploy**, **`tools/expected.py` — the `EXPECTED.json` contract CI writes from (C-35)**, `tools/promote.py` (sha check incl. `unknown` → fail, `hf spaces wait`, canary pass^3 with last-known-good control, visibility tripwire `private`, log tail on failure, rollback = redeploy known-good), scheduled health job; unit-tested against fakes; never executed | 07, 08b, 12 | — | S/AP-12 canary contract (A1) | — |

22 cards. Critical path: 01 → 02 → 03a → 03b → 04 → 05a → 05b → 06 → 10 (9 deep) with 13b after 06 and 08c after 08b/13a; the owner stop at 04 splits R1 into at least two invocations by design (C-M).

### 4.3 DAG, waves, sizing — all plain JS (§13); recomputed at runtime (C-5)

- `topoOrder(cards)` — dependencies first, ties by id; throws on a cycle or an unknown dependency (F-14, F-47).
- `rankCards(cards)` — A2's longest-path rank in estimated minutes (`est_minutes` or S=20/M=35, +14 per node); `waves()` orders each ready set by `(−rank, id)` (T-8) **and the same key orders integration, C-24** inside **barrier waves** (replay-safe control flow); a wave holds up to `args.wave_size ≤ args.cap` ready cards with pairwise-disjoint write sets; a clash waits (logged); **`readyWave()` is recomputed from the LIVE status map before every wave (C-5): a card whose dependency is parked, blocked on the owner or not yet merged is never scheduled — its dependents can never be built ahead of a failed root.** After the loop, `markDependencyBlocked()` types every still-unstatused card `not_attempted: dependency-blocked:<dep>(<state>)` with the next action (C-22). `waves()` never throws.
- Sizing: `S ≤ 120`, `M ≤ 300` lines, **validated against `est_lines` at plan time (C-13)**; `changed_lines ≤ 2 × est_lines` is a `taskDone()` condition (A2 G8) computed from the gate's `LEDGER_DIFF_STATS` and **fail-closed when the stats are missing (C-25)**; a builder `partial` is not `built` (condition 12) and is re-driven as a fix round.

### 4.4 Worktree → branch → bundle lifecycle (every path absolute; every git command `git -C`)

```
setup     : git -C $R merge --no-ff <plan_sha> into integration/<n> (first commit; plan/** only; once)
author    : git -C $R worktree add $WT/tests-<id>-<n> -b tests/<id>-<n> <integration_head>
            write tests; commit "tests(<id>): …" (trailer Card: <id>); gate.sh --only-tests <paths> --card … --base <head> → expect RED
            git -C $R worktree remove $WT/tests-<id>-<n>            (branch survives in the store)
  persona : git clone --depth 1 --single-branch --branch integration/<n> file://$R $WT/tests-<id>-<n>   (history-free)
            FIXTURE COPY STEP: cp $OA.persona_boundary_fixture_path tests/fixtures/persona_boundary.json (sha256 must equal the pinned value, C-21)
            … commit …; git -C $R fetch $WT/tests-<id>-<n> HEAD:refs/heads/tests/<id>-<n>              (local fetch, never a push)
verifier  : git -C $R worktree add --detach $WT/red-<id>-<n> <tests_head> ; gate.sh --only-tests … ; remove
builder   : git -C $R worktree add $WT/task-<id>-<n> -b task/<id>-<n> tests/<id>-<n>
            implement in commits (Claims: block + Card: trailer); gate.sh --card … --oracle <tests_head> LAST, on the committed clean tree (advisory; returns its LEDGER_DIGEST + steps, C-18); remove
verifier  : git -C $R worktree add --detach $WT/verify-<id>-<n>-<k> <task_head>
            gate.sh --card … --oracle <tests_head> (must reproduce the builder's LEDGER_DIGEST) ; --mutants … --tests … ; --revert-proof <tests_head> --tests <author's + builder-added tests/unit> ; remove
fixer     : git -C $R worktree add $WT/task-<id>-<n>-fix<k> task/<id>-<n>
integrator: in $R on integration/<n>: git merge --no-ff task/<id>-<n>   (record merge_sha for every merge, C-12)
            conflict → git merge --abort → return hunks → integrator mode:'conflict' in $WT/conflict-<id>-<n>
              (created DETACHED — `git worktree add --detach … <head>` — because integration/<n> is checked out in $R, C-30)
            clean  → gate.sh --base <prev_head> --journeys --require … --xfail-allow … ; git cherry == "" ; patch-ids present ;
                     write plan/status/<id>.json {merged, head_sha, merge_sha, gate_digest} + commit ; git bundle create <bundles>/<id>.bundle <prev>..integration/<n> (incremental)
journeys  : author on task/journeys-<tag>-<n> (same helper as every merged branch) → integrator mode:'merge' (gate carries --journeys, C-4)
fixcards  : integrator mode:'fixcards' writes plan/fixes/<fixid>.json verbatim + one commit "plan(fixes): review round <r>" (C-3)
clean-gate: git -C $R worktree add --detach $WT/clean-w<k>-<n> <head> ; BROKEN_SHA=<base> gate.sh --clean --self-test --journeys --lint-base <last clean pass> --require … ; remove
revert    : integrator mode:'revert' on integration/<n>: git revert -m 1 <merge_sha> (+ remove plan/status/<id>.json) ; gate ; return head + digest (checked in JS, C-12)
```

- Branch names carry the run nonce (F-33); a re-drive of the same card in the same run reuses the branch (`status:'reused'` when already green — T-16); every re-drive carries `redrive: <k>` in its prompts (cache miss by construction, J1 D4).
- A worktree is removed by the agent that created it, and only after `git rev-parse <branch>` equals the head it reports; the gate pre-step prunes `index.lock` older than 10 min and kills only listeners whose cwd is the current tree (J1 CG2).
- Bundles are incremental (`<prev>..integration/<n>`, A2 §13) under `/workspaces/space-build-bundles/<nonce>/` (C-17); `bundle_bytes` is reported; > 20 MB is logged with the runbook advice "push from the checkout"; the manifest lands in the grill tree.

### 4.5 Integration order, conflict resolution, integration test

- **Order:** strictly serial, `(−rank, id)` order inside the wave (C-24), one `integrator` call per merge (single writer). A card whose head is already an ancestor returns `already-merged` **with evidence (C-20): the integration head is unchanged, a gate run at that head exited 0 with its digest and the pinned gate sha, and the cherry/patch-id assertions came back empty — anything less is typed `already-merged-unproven` and blocks the card; the head never moves on an `already-merged`.**
- **Conflict:** the integrator never resolves; a fresh `mode:'conflict'` call gets ONLY the hunks and both cards, resolves in its own **detached** worktree (C-30), runs the gate, returns the merge sha; `mode:'ff'` fast-forwards and re-gates. A second conflict → `blocked:integration:conflict`.
- **Lost-hunk check:** `git cherry` empty AND every patch-id present — asserted in JS (`mergeOk`), together with `gate_exit_code === 0`, a 64-hex `gate_digest`, `gate_sha256_observed === args.gate_sha256` and a real `merge_sha` (C-12/C-20).
- **Red after merge (F-34):** the integrator reverts **the recorded `merge_sha`** immediately (`status: reverted`, JS-verified result) → `parked: integration:gate-red-after-merge(reverted)`; a fix card for it comes from the review loop. **"merged + red" is a revert-now case checked against the same merge sha — the target is never "HEAD", which after a journeys merge is the wrong commit (C-12).** A revert that fails for any reason marks the integration branch dirty: no further merges, checkpoint `failed`.
- **Integration test:** `integrator mode:'clean-gate'` after every wave **that merged or merged journeys (C-38: a wave with nothing merged and a last clean gate passing at this exact head is skipped, logged)**: detached pristine checkout of the wave head, `gate.sh --clean --self-test --journeys --lint-base <last clean pass> --require <manifest> --xfail-allow <union>`; **the idiom lint inside it only sees `--lint-base..HEAD` (C-15), so earlier waves' idioms are not re-counted and waiver counts stay per-card.** The clean gate is typed in JS three ways: **`pass`** (exit 0, head matches, digest 64-hex, pinned gate, `self_test.broken_red === true`, `self_test.false_claim_red === 'true'`), **`fail`** (a real RED → `mode:'revert'` of the last merged card **by its merge sha**, whose result is checked: on anything but `merged + exit 0 + digest`, the integration branch is marked dirty, no further merges happen and the checkpoint is `failed` — J2 gap 12), or **`gate-unavailable`** (a dropped agent, a malformed shape, a wrong head, or **exit 0 contradicted by a non-red self-test — any of these is `unavailable`, never a revert, C-11**; `satisfied()` stays false). A journey still `skipped` although its `needs=` card is merged becomes a synthetic blocking finding for the review loop. The clean gate also returns `remotes[]`, the branch count and the toolchain status hash (a mismatch → `HALT`, docs/grills excluded, C-17).

### 4.6 Ship-but-flag (lens-4 §E; A2 §4e) — every flag is a `config.py` constant with a row in `tests/test_constants_pin.py`

| Flag | Default at launch | Pin row (protected test) | Card that owns the constant |
|---|---|---|---|
| automatic hosted→worker fallback | OFF | `FALLBACK_TO_WORKER is False` | 08b |
| server-side tools for `/v1`/MCP | OFF | `SERVER_TOOLS_API is False` | 07 |
| `http_request` POST + third-party reader | OFF | `HTTP_POST_ENABLED is False`, `READER_MODE is False` | 09c |
| video (images ON) | OFF | `VIDEO_ENABLED is False`, `IMAGES_ENABLED is True` | 10 |
| automatic lease chaining (explicit Continue ON) | OFF | `AUTO_CHAIN is False`, `EXPLICIT_CONTINUE is True` | 08a |
| cross-turn `preserve_thinking` | OFF | `PRESERVE_THINKING is False` | 05b |
| `python_eval` | operator secret flag only | `PYTHON_EVAL_ENV_FLAG == 'QWEN_PYEVAL_OPERATOR'` and the surfaces test | 05a |
| `xlarge` | operator config only, never a request field | `GPU_SIZE_FROM_REQUEST is False` | 08b |

Every card's `out_of_scope[]` lists these defaults unless it is the card that owns the constant (A3's enforcement, kept). **Card 01 ships the `config.py` skeleton containing all eight constants (C-13):** the pins test is green inside card 01's own gate run via `expected_green_tests`, and every later card edits its own flag with the pin already in place.

### 4.7 lens-4 §C duplication items → DoD lines (J3 gap 4)

| §C item | Collapses into | Card | DoD line (mechanical) |
|---|---|---|---|
| 1 message assembly ×2, persona keys ×2, `red_team` fallback ×3 | `core/prompting.build_messages` | 03a | `test -z "$(git grep -ln 'def build_messages\|def _as_messages\|def normalize_messages' -- '*.py' \| grep -v core/prompting.py)"` |
| 2 content flattening ×3 | `core/prompting.text_of` | 02 | `test "$(git grep -c 'def _flatten_content\|def _user_text\|def text_of' -- '*.py' \| awk -F: '{s+=$2} END {print s}')" = 1` |
| 3 image placeholders ×2 | worker encoder | 03a | `git grep -n '_content_for_template' -- '*.py' \| grep -v worker/encode.py \| wc -l` = 0 |
| 4 parse/validate policy ×3 (is chat-loop-ui-4) | one `StreamParser` | 04 | `git grep -ln '<tool_call>' -- '*.py' \| grep -v core/parsing.py \| grep -v tests/` = empty |
| 5 thinking split ×4 | same parser; `/v1` gains `reasoning_content` | 04 | `git grep -c '</think>' -- '*.py' \| grep -v core/parsing.py` = empty (tests excluded) |
| 6 usage block ×2 | `Finish.usage` | 03a | `git grep -n 'prompt_tokens' -- '*.py' \| grep -v core/types.py \| grep -v api/protocol.py \| grep -v tests/` = empty |
| 7 error-to-content ×3 | `BackendError → Finish(reason)`; UI titled notice; API status | 03a | `git grep -n 'GPU lease ended' -- '*.py'` = empty |
| 8 sampling kwargs in 5 places | `SamplingParams` | 02 | `git grep -n 'repetition_penalty' -- '*.py' \| grep -v core/types.py \| grep -v tests/ \| grep -v worker/` = empty |
| 9 stop normalisation ×3 | one validator | 03a | `git grep -c 'def _normalize_stop\|def normalize_stop' -- '*.py'` sums to 1 |
| 10 tool dispatch ×4, `python_eval` gate ×2 | registry (the single choke point for G-15 (5)) | 05a | `git grep -n 'python_eval' -- '*.py' \| grep -v core/tools/registry.py \| grep -v tests/` = empty |

`verifier mode:'plan'` refutes a plan in which any §C item lacks a DoD line (prompt rule (g)).

### 4.8 Journeys = held-out seams H1-H7 + J1 (A1 §4.6; A2 gate step 13) — a separate collection (C-4)

| Seam | What the journey exercises | `needs=` card |
|---|---|---|
| J1 | `QWEN_STUB=1` boot serves UI + `/healthz{git_sha}` (from `build_info.json`) in < 10 s on a free port | 03b |
| H7 | error taxonomy: quota / illegal-duration / abort → titled notice in the UI, `{"error":…}` event on `/v1`, partial text kept | 04 |
| H4 | `python_eval` × operator flag × every surface: the UI checkbox alone cannot enable it; unreachable over `/v1` and MCP | 05a |
| H6 | session isolation × TTL sweep × no `rmtree` on unload; two sessions → two benches | 05b |
| H2 | `/v1` × identity: `x-ip-token` bound inside the generator body; 429 on the non-blocking semaphore; stream stops on disconnect | 07 |
| H1 | tool loop × streaming × Continue at **token level**: turn 2 contains turn 1's tool results; `finish_reason: length` → Continue resumes from `prefix_ids` (fake worker) | 08a |
| H3 | MCP `ask → poll → status → preflight` with `chat` hidden; listing = 4 typed tools | 11 |
| H5 | catalog admission × `models.yaml` schema × harness zero-call × pending entries hidden | 13a |

**The mechanics changed in v2 (C-4).** Card 01 delivers `tests/journeys/conftest.py`, which marks everything under `tests/journeys/` with the `journey` marker; `pytest.ini` (also card 01) deselects that marker from every default run. The default suite therefore NEVER collects a journey: a missing journey cannot be a RED baseline skip, and `needs=` is the only legal skip reason (`pytest.mark.skip(reason="needs=<card-id>")`). `--journeys` runs the collection at **every merge gate and every clean gate** (not only post-wave); the gate counts `skipped_needs[]` by parsing the reasons and reports `skipped_other = max(0, skipped − needs-matches)` — any skip without a `needs=` reason is RED. JS turns a journey whose card IS merged but still skipped into a synthetic blocking finding (§6). The journeys author runs only for a wave in which one of these cards merged (≈ 6-8 times per R1, not per wave). Card 03b's own gate command runs both collections so the thin slice is provably green in both before any journey exists (C-1).

---

## 5. Inner loop per task (exact counters and exit conditions)

```
author → confirm-RED (two-execution digest equality; expected_green_tests exempt both ways, C-13/C-29)
       → builder (gate LAST on the committed clean tree, C-18) → fresh verifier (gate digest must match; DoD re-runs;
       mutants; revert-proof incl. builder-added tests/unit, C-28; apicheck-extended, C-18; diff_stats required, C-25)
       → [fixer ← typed failures (digest-mismatch carries both ledgers' steps, C-18) → verifier]≤2 → taskDone() (JS)
```

| Counter | Value | Exhaustion → typed result |
|---|---|---|
| `MAX_AUTHOR` | 2 author calls (second re-driven WITH the red verdict, C-26) | `blocked:'tests-not-red'` |
| `MAX_BUILD` | 3 builder calls = 1 `implement` + ≤ 2 `fix` | `blocked:'fix-exhausted'` |
| two-strikes | failure fingerprint after a fix equals the previous one — **the fingerprint is never empty (C-18), so a vacuous verifier cannot disable two-strikes** | `blocked:'no-progress'` |
| oscillation | fingerprint sequence A→B→A | `blocked:'oscillation'` |
| `MAX_NULL_RETRY` | 1 per call slot (`attempt: 2` + `NARROW`) | `blocked:'agent-null:<role>'` |
| starvation | budget guard, agent slice or HALT cut the chain short — **typed `starved` → `not_attempted` (retryable on resume, C-8), never parked** | `not_attempted:'starved:<why>'` |
| secret in a return | any secret-shaped string in `failures[]`, `output_tail`, `notes`, `red_excerpt`, excerpts (redacted in JS before anything reads it) | `blocked:'secret-shaped-output'` (never fixer-fed) |
| budget / halt | `budget.remaining() ≤ RESERVE`, agent slice, `HALT` (outward action, toolchain mutated, remote added, budget throw) — **the synthesizer is exempt (C-7)** | `{status:'null', reason:'budget'|'halt'}` → `not_attempted` |

1. **author** (`mode:'tests'`) → `{tests_head, test_paths[], red_excerpt, gate_digest, mutants_suggested[]}`; exit: `commits_made ≥ 1` (or `reused`) and a 40-hex `tests_head`. Persona cards run the FIXTURE COPY STEP (C-21) and commit the fixture with the tests.
2. **confirm-RED** (`verifier mode:'red'`): `gate.sh --only-tests <paths> --card … --base <head>` at `tests_head`: the **author-range tamper rules** (no pre-existing test M/D outside `tests_allowed`; no assertion-count drop in a modified pre-existing test; no skip/xfail marker outside `xfail_allowed`) and RED for the expected reason (rc 1 or 2, collected > 0, passed == 0 **except exactly the card's `expected_green_tests`, which must be green — an extra green new test is RED and a listed-but-not-green one is RED, on BOTH executions (C-13)**; rc 5 and rc 0 are not red). `pass` requires `red.sha === tests_head` **and `red.gate_digest === author.gate_digest` — confirm-RED is a two-execution equality too (C-29)**.
3. **builder** (`mode:'implement'`): implements, commits per step with a `Claims:` block, runs every DoD command, **then runs the gate LAST, at the final commit, on a clean tree (C-18)** and returns `gate_digest` + `gate_profile` + `gate_steps[]` (the mismatch diagnosis) + `dod[]` (one row per card DoD id) + `apis_used[]` (each with a `ledger_ref`).
4. **verifier** (`mode:'verify'`): runs the same gate command itself in a detached worktree (`gate_digest`, `gate_sha256_observed`, `idiom_hits`, **`diff_stats` — required, its absence fails the card (C-25)**, `apicheck_unresolvable[]`), re-runs every DoD command (`dod_reruns[]`), reads the diff (`hunks_cited`), writes and runs 3 mutants (`--mutants … --tests …`), runs `--revert-proof <tests_head> --tests <author's tests + builder-added tests/unit/*>` (C-28), **and separately runs the apicheck with the builder's `apis_used[]` appended, recorded as `checks[]: apicheck-extended` — a run with its own ledger that never perturbs the digest equality (C-18)** — clearing idiom warnings by idiom.
5. **`taskDone()`** = `okSemantics(c, t, b, v)` — twelve booleans, logged per card, all required:
   1. `v.verdict === 'pass' ∧ v.gate_exit_code === 0`
   2. `v.ledger_head_sha === b.head_sha ∧ v.sha === b.head_sha` (40-hex)
   3. **`v.gate_digest === b.gate_digest`** (64-hex) — two independent executions agree (A1 G1; F-12)
   4. `v.gate_sha256_observed === args.gate_sha256` and profile `full` on both sides — the bootstrap profile is never a card profile (CG1; A2 G9)
   5. `hunks_cited ≥ 1 ∧ checks[] contains a gate.sh run` (A2 `semantic()`)
   6. `mutants.written ≥ 1 ∧ killed === written` (F-20)
   7. `revert_proof.observed === 'red'` (negative control)
   8. `b.dod.length === c.dod.length` and every local-level DoD id exits 0 in **both** `b.dod` and `v.dod_reruns` (A1 ok[6]; `expected_green_tests` are covered by condition 1's rule set, not by a per-id exemption here)
   9. `warnings_cleared.length ≥ idiom_hits` (F-10 in code)
   10. `diff_stats` present **(fail-closed without it, C-25)** `∧ insertions + deletions ≤ 2 × est_lines` (scope expansion)
   11. neither return had a secret-shaped string redacted (CG3)
   12. `commits_made ≥ 1 ∧ status ≠ 'partial'` ∧ every `apis_used[]` carries a `ledger_ref` (F-8)
   DoD lines at `staging-required`/`owner-required` are `deferred`, never done (F-37).
6. **fixer** (`builder mode:'fix'`) receives ONLY typed failures (`failures[]`, failed checks, failed DoD re-runs, mutants, revert-proof, the verifier's strongest disagreement, all capped and redacted) and the card. **A digest mismatch (condition 3) additionally carries `digest_mismatch`: both ledgers' step lists, the steps only in the builder's, the steps only in the verifier's, and the hint "re-run the gate LAST on the committed tree" (C-18).**

Fingerprint = sorted failing test ids + first error lines with shas, digits and paths normalised **+ the failed condition ids + the digest-mismatch step diff (C-18)**, computed in JS; it can never be the empty string, so two-strikes always has teeth.

---

## 6. Outer loop per wave and for the whole tree

### 6.1 Per wave (mechanical; no LLM review per wave)

```
readyWave() recomputed from the live status map (C-5) →  pipeline(wave, buildTask)
  →  serial integrate in (−rank, id) order (merge → gate on the merged tree with --journeys (C-4) → cherry/patch-id
     → status commit (with merge_sha, C-12) → incremental bundle)
  →  [journeys author when a seam card merged → integrate]
  →  integrator mode:'clean-gate' (--clean --self-test --journeys) typed pass|fail|gate-unavailable (C-11)
     — skipped when nothing merged and the last clean gate passed at this head (C-38)
fail → checked revert of the last merged card BY ITS MERGE SHA (revert failure ⇒ integration dirty ⇒ no further merges);
gate-unavailable → no revert, not satisfied
```

### 6.2 Whole tree (after the last wave; also the body of R2/R3 on their evidence)

```
round = 0; dry = 0; seen = Set(prior seen_keys); probesUsed = Set()
gate the loop itself before spending a lens (C-5, C-10, C-33):
  smoke mode                        → skip the review loop entirely ('smoke-skip-review')
  tree incomplete (C-5)             → stop 'tree-incomplete' — any card not merged and not a parked LEAF,
                                      incl. every dependent of a parked card; no lens is ever spent on such a tree
  last clean gate ≠ pass at head    → run ONE clean gate first; fail/unavailable → stop, no lenses (C-10)
while (true):
  stop if satisfied() ∧ vetoes==0 ∧ round>0        → 'satisfied'
  stop if HALT                                      → 'halt:<why>'
  stop if round ≥ MAX_ROUNDS (3)                    → 'max-rounds'
  stop if dry ≥ 2                                   → 'dry'
  stop if budget/agent slice cannot fund the round  → 'budget-or-agent-cap'
  round++
  findings  = parallel(3 lenses) + synthetic findings (journeys skipped after merge; staging evidence)   // barrier: dedup needs all
  levels raised in JS (STAGING_RE); fresh = dedup(findings, seen); probesUsed ∪= lenses' probes_used
  confirmed = pipeline(fresh, verifier mode:'refute') → holds ONLY with a reproduction that exits non-zero on the
              defect (a "holds" without one is ignored and logged, C-27)
  staging/owner-level confirmed findings → blocked_on_owner rows (never a fix card) — EXCEPT ids the owner listed in
              owner_approvals.accepted_findings at medium/low severity, which are recorded deferred (C-6 policy, §15 Q10);
              a confirmed critical/high one at stage/promote → stop 'blocked-on-owner:staging-evidence' (C-6)
  local confirmed findings + vetoes → fix cards → integrator mode:'fixcards' commits plan/fixes/ (C-3)
              → buildAndIntegrate (waves, clean gates); fixcards unavailable → not_attempted, never silent
  vetoes    = satisfied() ? verifier mode:'veto' (xhigh; last-round mandate = DoD inversion with probesUsed) : []
              a dropped veto judge → stop 'veto-unavailable' (fail closed)
  dry = (fresh.length==0 ∧ vetoes.length==0) ? dry+1 : 0
```

`satisfied()` (JS): `¬HALT ∧ ¬INTEG_DIRTY ∧ lastClean.verdict==='pass' ∧ lastClean.head_sha===head ∧ openBlocking===0 ∧ unreviewed===0 ∧ tree-complete ∧ ownerCritical===0` (C-5/C-6). **R2/R3 (J2 A3-4):** `lastClean` is seeded from `args.last_clean_gate` **only when its `head_sha` equals the live integration head AND its digest is 64-hex — otherwise it is `gate-unavailable: no prior pass at this head` and the pre-check re-runs one clean gate (C-10)**; findings that need a code fix run through the same loop and refresh `lastClean` via the fix wave's clean gate; `promote-production` is emitted only from `status:'ready'`, and `ready` is false while any row is `blocked_on_owner`, `not_attempted`, or a confirmed critical/high owner finding stands (C-6).

Budget reserve: `RESERVE = args.reserve_tokens ?? 120000`; a budget-ceiling throw from `agent()` sets `HALT='budget-exhausted'` and every later `budgetOk()` is false without further calls (J2 gap 8); **the synthesizer is exempt from the HALT branch and from the reserve guard — the reserve is what pays for it, so it always runs (C-7/F-45).**
