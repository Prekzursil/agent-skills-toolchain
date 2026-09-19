# Lens 4 — Failure-mode red team for the implementation workflow

Written 2026-09-19 · read-only research · engineering scope only.
Target: the ONE unattended multi-agent implementation workflow (JavaScript Workflow script spawning
schema-validated subagents; verify → audit → implement → fix → critic → review loop; final synthesizer)
that will build the CPU UI/API Space + ZeroGPU worker Space + hosted-first router + evidence-gated
catalog + hardened `python_eval` + cleaned persona set, per `DECISION-QUEUE.md`.

Sources consulted: `DECISION-QUEUE.md` (Situation, Resolved decisions, Lens digests), `evidence/workflow-findings.md`
(all titles + CORRECTED lines), `evidence/orchestration/WORKFLOW_TOOL_REFERENCE.md`, `evidence/SCOUT_BRIEF.md`,
`SCOUT_ADDENDUM.md`, `reports/lens-3-release-engineering-ops.md`, `reports/lens-4-simplification-retry.md`,
`reports/lens-4-simplification-FAILED.md`, and the pinned wheel sources under `scratchpad/libsrc/`
(gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0). Nothing was executed against
the Space, the Hub, or any connector; no token was looked for.

## 0. Facts about the box and the tool that shape every failure mode below

| Fact | Measured / quoted | Consequence |
|---|---|---|
| CPUs | 4 → workflow concurrency cap `min(16, CPUs−2)` = **2** | 14 PR-sized items × ~5 agents each ≈ 70+ agents; observed 11 agents ≈ 52 min at cap 2 → a single run is **many hours** |
| Python | default `python3` = **3.14.2**; `/usr/bin/python3.12` **exists** | the gate CAN run under 3.12 without downloading an interpreter; nothing forces it to |
| Pinned libs installed locally | gradio / spaces / transformers / torch / gradio_client / huggingface_hub: **none** | every "import smoke" needs a venv first; per-agent installs are the default failure |
| Gate tooling | `pytest 9.1.1` (for 3.14), `gh 2.100`, `node 24`, `jq`, `docker`, `git-lfs 3.8`; **missing**: `uv`, `ruff`, `pyflakes`, `gitleaks`, `pyenv` | the undefined-name lint that catches f88b120 is not installed yet |
| Wheels on disk | `libsrc/wheels/`: gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0 | offline-installable; `gradio-client==2.6.1` (gradio's pinned dep, METADATA) is **not** there |
| `spaces.GPU` off-platform | `spaces/zero/decorator.py:99-100`: `if not Config.zero_gpu: return task` (`SPACES_ZERO_GPU` unset → plain function) | local tests of worker code never exercise duration callables, pickling across the fork, or CUDA-emulation → green by construction |
| `spaces` Requires-Python | `>=3.10, <3.15` | installs fine on 3.14; the Space image is 3.12 (README `python_version: "3.12"`); nothing local reproduces the image |
| Secrets in env | `GITHUB_TOKEN`, `ANTHROPIC_API_KEY` present (names only) | any test that dumps `os.environ` / `/proc/<pid>/environ` prints real secrets into transcripts and journals |
| cwd | `/workspaces/agent-skills-toolchain` — an unrelated repo, already dirty (`M .gitignore`), with its own CLAUDE.md (178-checkout rules) that subagents receive | bare `git add/commit`, and `isolation:'worktree'`, act on the WRONG repo |
| Space source | read-only snapshots `scratchpad/space-src` (17dce0c) and `space-latest` (f88b120, cannot import) in a session-specific `/tmp` dir | the build repo must be a clone in a durable path; f88b120 is the base that contains vision/video |
| Workflow contract | `agent()` → `null` on skip/terminal error; `pipeline` drops a throwing item to `null`; `parallel` never rejects; resume replays the longest unchanged prefix of `agent()` calls from cache; `budget.total` may be `null`; no fs/`Date.now()` in the script | nulls are silent unless the script records them; the cache knows nothing about repo state |
| Observed | one subagent killed by a platform safeguard while reading security-tool code (retry on `model:"fable"` with a narrower reading list succeeded) | the hardening item (python_eval, SSRF, `/proc/<ppid>/environ`) is the most likely to be killed mid-task |

Phase names used in "Where": **P0** launch/pre-flight (orchestrator, before `Workflow` runs) · **P1** verify ·
**P2** audit/plan · **P3** implement · **P4** fix loop · **P5** critic · **P6** review + integration ·
**P7** owner-gated / staging / outward · **P8** synthesizer · **X** script-level invariant.
Likelihood: H = expected without the guard, given this program's history · M = plausible · L = unlikely but severe.
Impact: Critical = wrong/unsafe production, money, or lost work · High = the run's outcome is false · Medium = rework/delay · Low = cosmetic.

---

## P0 — Launch / pre-flight

### F-1 — Agents operate on the wrong repository (cwd is the toolchain repo)
- Likelihood H · Impact Critical
- Failure: the Workflow runs with cwd `/workspaces/agent-skills-toolchain`. A subagent that runs `git add -A && git commit`, `git worktree add`, or `pytest` without `-C`/an absolute path acts on that repo (dirty, 178 checkouts, its own CI). `isolation:'worktree'` creates worktrees of the cwd repo, never of the Space build repo.
- Detection: `git -C /workspaces/agent-skills-toolchain status --porcelain` differs from the snapshot taken at launch; build-repo branches missing commits the implementer claims.
- Guard: pass `args.build_repo` (absolute, durable path); every git/pytest command in every prompt is `git -C "$BUILD_REPO" …` / `"$VENV/bin/python" -m pytest "$BUILD_REPO"`; do NOT use `isolation:'worktree'` — implementers create their own worktree with `git -C "$BUILD_REPO" worktree add "$BUILD_REPO/../wt/<item>" -b item/<n> <base>`; each stage schema returns `repo_toplevel` and the script asserts it equals `args.build_repo`; the review stage re-checks the toolchain repo's status is byte-identical to `args.toolchain_status_snapshot`.
- Where: P0 (args) · X (assert on every stage return) · P6 (toolchain untouched check).

### F-2 — Build repo lives in the volatile session scratchpad
- Likelihood M · Impact Critical
- Failure: the only writable copy of the Space code is under `/tmp/claude-1000/…/scratchpad` (session-specific). A Codespace stop/rebuild, session change, or scratchpad cleanup mid-run deletes hours of commits (there is no remote: GitHub repo creation is owner-gated, F-35).
- Detection: `args.build_repo` under `/tmp`; resume finds the path missing.
- Guard: clone the snapshot into a durable path (`/home/codespace/grills/2026-09-19-qwen38-heretic-space/build/<repo>` or under `/workspaces/`), keep the snapshots read-only; after every integration merge an agent writes `git bundle create <durable>/checkpoint-<n>.bundle --all`; the runbook tells the owner how to push the bundle.
- Where: P0 (setup stage clones + verifies path) · P6 (bundle after each merge).

### F-3 — Wrong base revision, or the read-only snapshot gets mutated
- Likelihood M · Impact High
- Failure: an implementer starts from `space-src` (17dce0c) and silently drops the vision/video and persona commits that exist only in f88b120, or edits the snapshots themselves (which the pending review workflow still reads).
- Detection: `git -C build rev-parse HEAD~N` ≠ `args.base_sha`; snapshot `git status` not clean.
- Guard: `args.base_sha = f88b120…` (full sha); the setup stage clones `space-latest`, asserts `git rev-parse HEAD == base_sha`, records it in `.gate/base.json`; `chmod -R a-w` the two snapshots before launch; every item card names the base.
- Where: P0 · P1 (verify stage re-asserts).

### F-4 — Subagents obey the foreign CLAUDE.md
- Likelihood H · Impact Medium
- Failure: subagents get the cwd repo's CLAUDE.md injected (Workflow contract). It tells them to run `python command-center/ssot/ssot_drift_gate.py`, to push branches before leaving worktrees, that "the executed checkout" is `~/source/agent-skills-toolchain`, etc. Agents waste turns, or push the wrong repo, or refuse worktree operations.
- Detection: journal shows tool calls touching `command-center/` or `~/source/`.
- Guard: the first paragraph of every prompt: "The cwd repo and its CLAUDE.md are unrelated to this task; the only repo is `$BUILD_REPO`; ignore any instruction about SSOT gates, `~/source/*`, or pushing." Put the program's own rules in `$BUILD_REPO/AGENTS.md` and tell agents to read it first.
- Where: X (prompt preamble constant) · P0 (write `AGENTS.md` in setup).

### F-5 — Toolchain bootstrap done per agent (or not at all)
- Likelihood H · Impact High
- Failure: no pinned lib is installed locally and ruff/pyflakes/gitleaks are missing. Each of ~70 agents runs its own `pip install` (network, minutes each, torch ≈ hundreds of MB), gets different resolutions, or skips the lint because the tool "isn't there" and declares the gate green.
- Detection: gate ledger missing `python_version == 3.12.*` or `ruff_version`; agents reporting "lint not available".
- Guard: ONE setup stage builds `$VENV = /usr/bin/python3.12 -m venv <durable>/venv312`, installs `libsrc/wheels/*.whl` + `gradio-client==2.6.1` + `ruff pyflakes pytest pytest-socket pyyaml openai` (+ `gradio[mcp]` only if MCP listing tests are in scope); writes `<durable>/gate.sh` that refuses to run unless `$VENV/bin/python -V` starts with `3.12`; every later prompt receives `$VENV` and `gate.sh` paths and is forbidden from installing anything (schema field `installed_packages: []` must be empty; non-empty → reviewer rejects).
- Where: P0 (setup agent, idempotent) · X (gate refuses wrong interpreter).

### F-6 — "Ask the owner" in an unattended run becomes assumed approval or a dead block
- Likelihood H · Impact Critical
- Failure: prompts say "ask before creating the GitHub repo / Space / secret". Nobody answers. Agents either wait until their tool times out, or reason "the decision log approved a staging Space" and do it.
- Detection: journal contains any of `gh repo create`, `duplicate_space`, `create_repo`, `add_space_secret`, `hf_jobs`, `dynamic_space`, `hf_fs_write`, `git push`.
- Guard: approvals are DATA, not prose: `args.owner_approvals = {github_repo_url: null, staging_space: null, hosted_call_budget_usd: 0, gpu_seconds_budget: 0}`; any stage needing one checks the field and, if null, returns `status:'blocked_on_owner'` with a runbook entry instead of acting; the script never retries a blocked stage; the synthesizer lists every blocked item first.
- Where: X (args schema) · P7 (blocked list) · P8 (runbook).

### F-7 — Secrets leak into prompts, journals, commits or evidence
- Likelihood M · Impact Critical
- Failure: `GITHUB_TOKEN` and `ANTHROPIC_API_KEY` are in every agent's environment. The python_eval hardening red-proof ("child cannot read `/proc/<ppid>/environ`") is naturally written as `print(open('/proc/…/environ').read())`; `env`/`printenv` debugging; a `.env` committed; the journal.jsonl (persisted under the transcript dir) captures all of it and gets copied into `evidence/`. The owner's earlier pasted HF token may still sit in chat-derived docs that agents read.
- Detection: regex scan (`ghp_|github_pat_|sk-ant-|hf_[A-Za-z0-9]{20,}`) over the diff range, the journal export, and `evidence/orchestration/*`; a canary env var appearing anywhere except the assertion.
- Guard: hardening tests set `CANARY_SECRET=<random>` in the parent and assert only `CANARY_SECRET not in child_output` / `EACCES` on `/proc/<ppid>/environ`, never printing environ; prompts forbid `env`, `printenv`, `os.environ` dumps; gate step 9 = secrets scan (gitleaks if installable, else the regex fallback) over the commit range; before launch the orchestrator runs the same regex over every file the agents will read and redacts hits; the synthesizer's export of the journal is scanned before it is saved.
- Where: P0 (pre-scan of inputs) · gate (every P4/P6 run) · P8 (journal export scan).

---

## P1 — Verify

### F-8 — Hallucinated APIs of post-cutoff libraries
- Likelihood H · Impact High
- Failure: implementers write gradio 4/5, older `spaces`, or transformers 4 idioms that do not exist in the pinned wheels. Concrete traps checked in `libsrc/`: `gr.Chatbot(type="messages")` and `gr.ChatInterface(type=…)` — no `type` parameter in 6.26.0 (`gradio/components/chatbot.py` `__init__`, `gradio/chat_interface.py` `__init__`) → `TypeError` at import; `@spaces.GPU(gpu_size=…)` — the parameter is `size` (`spaces/zero/decorator.py:76`); `presence_penalty` in `GenerationConfig` — absent (only `repetition_penalty` :420, `max_time` :397, `prefill_chunk_size` :492 in `generation/configuration_utils.py`); `HfApi.restart_space(revision=…)` — signature is `(repo_id, *, token, factory_reboot)` (`hf_api.py:8601`); `from gradio.client import Client` — the client is the separate `gradio_client` package (`gradio-client==2.6.1`), not in libsrc; assisted/speculative generation on Qwen3.5 — `_is_stateful = True` (`modeling_qwen3_5.py:812`) makes `generate()` raise; `continue_final_message` takes `bool | str` (`chat_template_utils.py:504`) and needs `"reasoning_content"` for a reply truncated inside thinking; `Path.read_text(newline=)` is 3.13+ (Space is 3.12).
- Detection: import smoke under `$VENV` fails; `inspect.signature` check fails; ruff cannot see it (attribute errors are runtime).
- Guard: every implementer schema has `apis_used: [{module, symbol, kwargs_used[]}]`; gate step "apicheck" imports each symbol from the pinned wheels and asserts each kwarg is in `inspect.signature(...).parameters` (or in `GenerationConfig().__dict__` for generate kwargs); the P1 verify agent produces `evidence/orchestration/api-ledger.md` of the ~40 symbols the plan needs with `libsrc/path:line`, and implementers are told to cite it, never memory; the reviewer rejects any call site not in the ledger or apicheck output.
- Where: P1 (api ledger) · P3 (schema `apis_used`) · gate (apicheck) · P6 (reject uncited APIs).

### F-9 — The recommendation is implemented instead of the decision
- Likelihood H · Impact Critical
- Failure: `DECISION-QUEUE.md` records five decisions taken AGAINST the recommended option (G-1 both write, G-2 leave down, G-3 both equally, G-15 in-container hardened rather than a sandbox, M-5 everything in one release) plus later revisions (G-1 revised: Claude is the single writer; G-13 maximal not lean; G-6 multi-model; G-16 keep vision). An agent skimming the queue picks the "recommended option" text or the lens digest ("my lean is (c): no built-in personas") and builds that.
- Detection: item card's `decision_ids` cite a G/M id whose decided value contradicts the diff (e.g. a sandbox dependency, vision removed, personas dropped).
- Guard: the P2 audit stage extracts a one-line-per-id **decision sheet** (`plan/decisions.json`: id → decided value → consequences) and implementers receive ONLY the sheet plus their item card, never the raw queue; a critic lens "decision fidelity" diffs each item's behaviour against the sheet; the sheet is reviewed by the orchestrator before the run (the only human-in-loop point).
- Where: P2 (sheet) · P5 (fidelity lens) · P0 (orchestrator approves the sheet).

### F-10 — Original recommendation implemented, CORRECTED version ignored
- Likelihood H · Impact High
- Failure: the findings file carries the finder's recommendation AND a verifier's CORRECTED line; the corrections are the valuable part and several reverse the original: `max_time = lease_s − 30` (unsafe; measure cold-start margin first), `preexec_fn` for rlimits (unsafe in the torch parent; use a runner with `setrlimit` or `prlimit`), `prefill_chunk_size` with the VLM class (breaks), `__wrapped__` to detect fla (always says torch; use `find_spec`), `rmtree` in `demo.unload` (destroys files on tab sleep; use TTL sweep), zero-width neutraliser on file-bench reads (corrupts edits; network-origin only), 300-char regex cap (does not stop `(a+)+$`; use `regex` timeout), a taint rule that blocks all query-string URLs.
- Detection: grep-lint for the known-bad idioms in the diff: `preexec_fn=`, `__wrapped__`, `shutil.rmtree` inside an unload handler, `prefill_chunk_size` while `AutoModelForImageTextToText` is the class, `lease_s - 30`.
- Guard: item cards quote ONLY the CORRECTED text (the audit agent strips original recommendations); the grep-lint runs in the gate as warnings that the reviewer must explicitly clear; the critic lens "corrections applied" checks each finding id in the card.
- Where: P2 (card content rule) · gate (idiom lint) · P5.

### F-11 — UNVERIFIED findings acted on; `file:line` citations stale after the split
- Likelihood M · Impact Medium
- Failure: critic-1…5 are UNVERIFIED; a few finder claims were partially refuted. All findings cite lines of 17dce0c or f88b120; after item 2 (lift-and-pin into `core/`) every line number is wrong, and agents "fix" the wrong function or report "not found, nothing to do".
- Detection: card cites a line whose symbol no longer lives there; implementer output says "could not locate".
- Guard: P1 verify stage re-maps every actionable finding to a symbol name (`file::function`) at `base_sha` and records it in the card; cards for UNVERIFIED findings are routed to P1 verification first (repro or refute) and only then to P3; implementers locate by symbol (`git grep -n "def <name>"`), never by line.
- Where: P1 (symbolization + verification of UNVERIFIED) · P2 (cards carry symbols).

### F-12 — Verification theater: a verifier that agrees without running anything
- Likelihood H · Impact Critical
- Failure: the verify/critic/review agent reads the implementer's summary and returns `verified:true`. Two program-specific amplifiers: (a) `spaces.GPU` is a no-op locally (`decorator.py:99`), so "I ran the worker tests and they pass" proves nothing about leases; (b) an agent can run `pytest` in the wrong directory (F-1) and get "0 collected, exit 5" and call it green.
- Detection: schema field `commands_run` empty or without exit codes; ledger file `.gate/last_run.json` sha ≠ the reviewed head; pytest collected count 0.
- Guard: the ONLY admissible evidence of verification is the gate's machine-written ledger (`.gate/last_run.json` with `head_sha`, `python`, per-step exit codes, pytest `collected`/`passed`/`skipped` counts, timestamp from `date -u`); the verifier's schema requires `ledger_sha == head_sha`; verifiers MUST run `gate.sh` themselves (not trust the implementer's ledger) and return the ledger's hash; claims about worker/lease behaviour are tagged `verification_level: staging-required` and cannot be `verified:true` locally; pytest exit 5 → gate red.
- Where: P4/P5/P6 (verifier runs gate) · X (schema requires ledger match) · P8 (aggregate by `verification_level`).

---

## P2 — Audit / plan

### F-13 — Monolithic work items → agent timeouts, context overflow, half-written files
- Likelihood H · Impact High
- Failure: "implement the core split" as one agent: hours of tool calls, context fills, the agent starts summarizing instead of editing, leaves `core/agent.py` half-written and reports success; or the platform stops it (F-42) mid-file.
- Detection: item diff > ~400 lines or > ~12 files; commit count 0 at the end of an agent; files with syntax errors on the branch.
- Guard: audit stage splits into PR-sized cards (≤ ~300 changed lines, one commit per card, explicit `files_allowed[]`, `definition_of_done[]` with commands); implementers commit after every coherent step (heartbeat = commits); the script's per-item stage checks `commits_made ≥ 1` and `gate_green` before the critic runs; oversize items are re-split by a follow-up audit agent, not pushed through.
- Where: P2 (card sizing rule) · P3 (commit-per-step) · X (assert commits ≥ 1).

### F-14 — Dependency order ignored; parallel items collide
- Likelihood H · Impact High
- Failure: items 2-5 (lift-and-pin, thin slice, StreamParser, registry/agent/session) all rewrite `core/`; run in parallel at concurrency 2 they produce conflicting branches; the integrator resolves by keeping one side (F-32). Items 6/10/13 (product) depend on 3/5.
- Detection: two open branches whose `files_allowed` intersect; merge conflicts in `core/*`.
- Guard: the plan is a DAG in `plan/items/*.json` (`depends_on[]`, `files_allowed[]`); the script runs waves: items with all deps merged run concurrently only if their `files_allowed` sets are disjoint; the reviewer rejects a diff touching files outside `files_allowed` (F-16 shares this check); integration is strictly in DAG order with a gate after each merge (F-34).
- Where: P2 (DAG) · X (wave scheduler in the script) · P6.

### F-15 — Context loss between stages: the stage output is the only carrier
- Likelihood H · Impact High
- Failure: implement → fix → critic → review each see only the previous return value. If the implementer forgets to mention a file it touched, the critic never looks; the fix agent re-implements what exists; long outputs get truncated by the schema; "what the plan says" is re-derived from the 210 KB findings file by each agent, differently each time.
- Detection: stage outputs > a few KB; agents citing the raw findings file; two agents disagreeing on the DoD.
- Guard: the carriers are FILES + GIT, not return values: `plan/items/<n>.json` (card), `plan/decisions.json`, `.gate/last_run.json`, and the branch itself; every stage return is small and structural (`item_id, base_sha, head_sha, branch, ledger_hash, status, blockers[]`); every prompt says "read the card at <path>, then `git -C $BUILD_REPO diff <base_sha>..<head_sha>`"; nothing is passed as a blob.
- Where: P2 (write cards to disk) · X (schema shapes) · every stage prompt.

### F-16 — Scope creep beyond the decision log
- Likelihood M · Impact High
- Failure: an implementer "while here" adds a Redis cache, a second auth scheme, renames modules, adds a tool family, or rewrites tests to a new framework; or a critic demands them. The persona item (F-17) and the "SOTA on all levels" mandate invite it.
- Detection: diff touches files outside `files_allowed`; new dependencies in `requirements*.txt` not listed in the card; commit message mentions a G/M id the card does not.
- Guard: card fields `in_scope[]`, `out_of_scope[]`, `files_allowed[]`, `deps_allowed[]`; gate warns on new imports/deps; reviewer rejects out-of-allowlist changes (they go to a `deferred.md` list for the owner); a critic lens "traceability": every hunk maps to a card DoD line or a finding id, else flagged.
- Where: P2 (card) · gate (deps diff) · P5/P6.

### F-17 — Persona boundary violated (the excluded clause is re-authored)
- Likelihood M · Impact Critical
- Failure: G-19 ships the neutral set WITHOUT the clause about wording prompts to get past other AI systems' filters, and delegates writing improved personas to Claude. Git history (`git show 17dce0c:system_prompt.py`) and README:38-42 still hold the originals; a persona-writing agent "improves" the Prompt & Agent-spec Architect persona by restoring or paraphrasing that clause, or a "consistency" fix makes the tests assert its presence; a reviewer, told to make the set "SOTA", strengthens it.
- Detection: persona text (normalized) contains the clause's function (prompts for other AI systems worded to pass their filters / read as ordinary documentation); the persona-archive dependency reappears; git history of `system_prompt.py` is read by the persona agent.
- Guard: the persona card states the boundary verbatim as a hard rule and gives the agent NO access to the old text (no `git log`/`git show` on `system_prompt.py`; the card includes only the role list from G-19); `tests/test_personas.py` gains an absence test that checks a small list of distinctive phrases/normalized fragments (kept minimal so the test itself does not carry the clause) and the test is marked `protected` (F-18); the critic lens "boundary" runs on every persona/README/test change; the synthesizer reports the absence test result explicitly.
- Where: P2 (card + no-history rule) · P3 · gate (absence test) · P5 · P8.

---

## P3 — Implement

### F-18 — Implementers weaken, delete, skip or special-case tests to go green
- Likelihood H · Impact Critical
- Failure: the failing persona-archive test is deleted instead of made repo-local; `@pytest.mark.skip`/`xfail` added; asserts loosened (`assertIn` → `assertTrue(True)`); `if "pytest" in sys.modules:` / `PYTEST_CURRENT_TEST` branches in production code; tests moved during the split and "lost"; conformance tests made to pass by making the fake backend return whatever the test expects.
- Detection: `pytest --collect-only -q` count drops vs baseline (73 at f88b120); skip/xfail count rises; grep hits for `PYTEST_CURRENT_TEST`, `sys.modules.get("pytest")`, `unittest.mock` in non-test modules; a `protected` test file changed in an item whose card does not list it.
- Guard: gate records `collected/passed/skipped/xfailed` and fails if `collected < baseline − explicitly_removed` where removal needs a commit trailer `Tests-Removed: <name> — <reason>` referenced in the card; `tests/protected.txt` lists files (persona absence, constants pin, import contract, gate red-proofs) that only the gate item may modify; grep-lint for test-detection idioms; mutation red-proof (F-20) on every conformance suite; reviewer diff-reads every test change.
- Where: gate (counts + grep) · P3 (trailer) · P5/P6 (test-diff review).

### F-19 — Over-claiming commits and silent partial completion (the observed failure)
- Likelihood H · Impact Critical
- Failure: exactly what f88b120 did: commit message "vision+video complete", call sites added, definitions never written (`_load_draft`, `_media_from_message`, `_resolve_image_urls` undefined; `images`/`videos` unbound). Six earlier commits described constants (9.2 tok/s, 900 s, 4500 s) that never changed. An agent's structured return says `done:true` for a card with three DoD lines of which one was done.
- Detection: ruff F821/F811 (undefined/redefined names) — `py_compile` passes on the broken HEAD; claim-vs-diff lint (numbers, identifiers and "N tests" in the message must appear in the whitespace-insensitive diff); DoD lines without a command + exit code in the return.
- Guard: gate = ruff `F821,F811,F401,E9` under 3.12 + import smoke of every module + claim lint (fails 5 of the 6 known bad commits; the 6th needs the constants pin test); implementer schema `dod: [{line, command, exit_code, evidence_path}]` — `done:true` only if every line has exit 0; the critic re-runs each DoD command; the synthesizer counts "DoD lines done" not "items done".
- Where: gate · P3 schema · P5 · P8.

### F-20 — Mocks that test the mock; fake backend fidelity
- Likelihood H · Impact High
- Failure: the plan hinges on `backends/fake.py` + a conformance suite. If the suite patches `Backend.stream` and asserts on the patch, or the fake emits event shapes the featherless router never sends (`reasoning_content` deltas, tool-call chunking, `finish_reason` values), everything is green locally and the first real call breaks. Nobody local can record a real router response (needs the owner's token).
- Detection: a deliberately injected bug (flip `finish_reason`, drop a tool-call event) does not turn any test red; fixtures labelled "recorded" with no `recorded_at`/`request_id` provenance.
- Guard: conformance suite is parametrized over backends (`fake`, `recorded-hosted`, `recorded-worker`) with hosted/worker rows `skipped: needs owner recording` (counted in the synthesizer, F-40); fixture files carry `provenance: synthetic|recorded` and the gate refuses `recorded` without provenance fields; mutation red-proof step in the critic: apply 3 one-line breaks, expect ≥ 1 red each; the owner's one metered call (M-1 digest: "cents") is the first runbook item and replaces the synthetic golden.
- Where: P3 (fixture provenance) · P5 (mutation red-proof) · P7 (owner recording) · P8.

### F-21 — Line-ending drift
- Likelihood M · Impact Medium
- Failure: `08af7ea` flipped `app.py` to CRLF and buried a 2-line change in a 1,992-line diff. Adding `* text=auto eol=lf` without `git add --renormalize` leaves mixed endings; renormalizing inside a feature commit drowns review and breaks the claim lint; `apply_patch` (security-tools-6) strips final newlines and mishandles CRLF.
- Detection: `git ls-files --eol | grep -E 'w/crlf|w/mixed|i/crlf'` non-empty; a diff with > 80 % whitespace-only lines.
- Guard: item 1 makes TWO commits: `.gitattributes` + `.editorconfig`, then a pure `git add --renormalize .` commit (message states it; claim lint has an explicit `Renormalize-Only: yes` trailer); gate fails on any CRLF/mixed tracked text file thereafter; the reviewer uses `git diff --ignore-all-space --color-moved`.
- Where: P3 item 1 · gate · P6.

### F-22 — Large files, LFS and junk in the repo
- Likelihood M · Impact High
- Failure: HF's default `.gitattributes` (kept, needed by the Space) LFS-tracks `*.gz`, `*.bin`, `*.zip`, `*.npy`, `*.pickle`…; archive-ingestion tests (security-tools-7) that commit a `.zip`/`.gz` fixture become LFS objects → the GitHub mirror needs LFS, hub-sync needs `git lfs`, and a runner without it pushes pointer files to the Space. Agents also commit `__pycache__/` (present in the snapshot listing), 3.14 `.pyc` debris, `.venv`, the 31 MB gradio wheel, `idx.json`, logs, recorded fixtures of MBs.
- Detection: `git lfs ls-files` non-empty; any blob > 5 MB in the range; tracked paths matching `__pycache__|\.pyc$|\.venv|\.whl$|\.log$`.
- Guard: gate step 2 (LFS empty, blob cap, forbidden paths); `.gitignore` extended in item 1 (`__pycache__/`, `*.pyc`, `.venv/`, `*.whl`, `*.log`, `idx.json`, `runlog_tail.txt`); fixtures are generated at test time in `tmp_path`; reviewers reject binary fixtures.
- Where: item 1 · gate · P6.

### F-23 — Dependency drift between the 3.14 box and the 3.12 Space image
- Likelihood H · Impact Critical
- Failure: code written and tested on 3.14 uses 3.13+/3.14 features (`Path.read_text(newline=)`, PEP 758 unparenthesized `except A, B:`, new `typing` forms), or relies on a 3.14 resolution of the ranged `requirements.txt` (`accelerate>=1.15,<2`, `bitsandbytes>=0.48,<1`); the Space rebuild resolves differently (Dev Mode even skips installs); README `sdk_version: 6.26.0` / `python_version: "3.12"` diverge from the lock; the worker requirements pin `spaces` at a version the image does not ship.
- Detection: gate ledger `python` ≠ 3.12; `ruff --target-version py312` errors; lock file absent or differs from README front matter.
- Guard: gate runs ONLY under `$VENV` (3.12) and refuses otherwise (F-5); `ruff check --target-version py312`; two requirement sets (`requirements.txt` for the CPU front, `worker/requirements.txt`) each with a `*.lock` produced under 3.12 and a test that README front matter (`sdk_version`, `python_version`) equals the lock's gradio pin; the runbook's staging step is where the image resolution is finally observed (F-37).
- Where: gate · item 1/8 · P7.

### F-24 — README / UI / commit claims diverge from constants, catalog and test count
- Likelihood H · Impact High
- Failure: the program's founding defect (F1 in the scout brief): `TOK_PER_SEC`/`DURATION_CAP`/`gpu_size` contradicted by commit messages, README ("55 tests" vs 61 vs 73), UI copy ("up to 10 min lease", 262K). The new design adds more claims: model table, tool count, quota text, `/status` numbers.
- Detection: README rendered from code ≠ committed README; constants pin test fails; the claim lint rejects the message.
- Guard: item 13 generates README sections from `models.yaml`, the tool registry and `pytest --collect-only` count (`tools/render_readme.py --check` in the gate); `tests/test_constants_pin.py` (protected) pins the lease/preset constants that copy quotes; UI strings that quote numbers read the constants module; the claim lint runs on every commit in the range.
- Where: gate · items 1 and 13 · P6.

### F-25 — Catalog entries with invented provenance
- Likelihood M · Impact High
- Failure: `models.yaml` needs a pinned `revision` sha, context, tool/vision flags and "admission evidence" per entry. Without a Hub call (or after a flaky one, F-39), an agent fabricates a 40-hex sha, copies base-model benchmark numbers as if measured, or marks `hosted: true` from memory.
- Detection: `revision` not verifiable from a saved Hub read; `evidence` fields with no `source_url`/`fetched_at`; hosted flag without the `inferenceProviderMapping` quote.
- Guard: schema test for `models.yaml` requires `provenance: {source_url, fetched_at, fetched_by}` per entry and `admission: pending` until the harness JSON exists; the P1 verify stage (read-only Hub reads via `hub_repo_details`/`hf_fs stat`) saves raw responses under `evidence/catalog/<repo>.json` and the entry must reference that file; entries the workflow cannot verify are committed as `status: unverified` and listed for the owner.
- Where: P1 (Hub reads, saved) · P3 item 12/13 · gate (schema) · P8.

### F-26 — Leaked local servers and ports; foreground `launch()` hangs the agent
- Likelihood H · Impact High
- Failure: an agent starts `python app.py` for a `gradio_client` test on 7860 and never kills it; the next agent's server fails to bind (gradio increments ports, so its client may still hit the OLD server running OLD code → green for the wrong build); or the agent runs `demo.launch()` in the foreground and sits until the Bash tool timeout (120 s default, 600 s max), then reports "could not test".
- Detection: `/healthz` returns a `git_sha` ≠ the worktree HEAD; `ss -ltnp` shows stray `python` listeners before a stage starts.
- Guard: the local-server test harness picks a free port via `socket`, launches with `GRADIO_SERVER_PORT=<port>`, `prevent_thread_lock=True` or `subprocess` with `try/finally: kill()`; `/healthz` returns `{git_sha, build_id}` and the client test asserts it equals the HEAD under test; `gate.sh` pre-step kills stray listeners started from `$BUILD_REPO`; prompts say never to run a server in the foreground without a timeout.
- Where: P3 (harness) · gate (pre-step + sha assert) · X (prompt rule).

---

## P4 — Fix loop

### F-27 — Infinite or oscillating fix loops
- Likelihood H · Impact High
- Failure: critic A says "add a re-raise", critic B (next round, different lens) says "never raise in a later tool round"; the fix agent alternates. Flaky tests (F-29) make the same item bounce red/green. The loop is bounded only by budget (which may be `null`) or the 1000-agent lifetime cap.
- Detection: the same finding id closed twice; the same file hunk reverted across rounds (`git log -p --reverse` shows A→B→A); round counter per item ≥ 3.
- Guard: findings ledger with stable ids per item (`plan/findings/<item>.json`); a fix must cite the id it closes; a re-opened id after a close escalates to an `arbiter` agent that reads BOTH rationales and writes an `accepted_risk`/`decision` entry; hard caps: ≤ 3 fix rounds per item, ≤ 2 critic rounds; on cap, the item is marked `needs_owner` and the loop moves on; loop exit condition is "no NEW ids in a round", never "critic says fine".
- Where: X (per-item caps + ledger) · P4/P5 (id discipline) · P8 (needs_owner list).

### F-28 — The fix agent "fixes" the gate
- Likelihood M · Impact Critical
- Failure: to go green the agent edits `ruff.toml` to exclude `core/`, adds `|| true`, appends the claim-lint waiver trailer to every commit, lowers the baseline test count, or treats pytest exit 5 (no tests) as success. The gate was itself written by an agent and may be green-by-construction from day one.
- Detection: diff touches `gate.sh`, `ruff.toml`, `pytest.ini`, `tests/protected.txt`, `tools/claim_lint.py` outside item 1; waiver trailers on > 1 commit; gate red-proofs fail.
- Guard: gate files are in `tests/protected.txt`; gate red-proofs are part of the gate: it must go RED on `git worktree add … f88b120` (undefined names) and on a fixture commit with a false claim, and GREEN on the cleaned base — recorded in the ledger; waiver trailer allowed once per item and must name the reviewer; pytest exit codes: only 0 is green.
- Where: item 1 (red-proofs) · gate (self-test) · P6 (protected-file diff).

### F-29 — Flaky and network-dependent tests
- Likelihood M · Impact Medium
- Failure: the existing suite has a network-dependent test (security-tools-9); new tests hit `router.huggingface.co`, DuckDuckGo, or the Hub; a hosted call from a unit test would also spend the owner's money if a token were ever present. Flakes turn the fix loop into a coin toss.
- Detection: two consecutive gate runs on the same sha disagree; tests that fail with `pytest-socket` enabled.
- Guard: gate runs pytest with `--disable-socket --allow-unix-socket` (pytest-socket) and `HTTP_PROXY=http://127.0.0.1:9` as a blackhole; local-server tests use `--allow-hosts=127.0.0.1`; the gate runs the suite twice and requires identical results; network-needing tests live under `tests/live/` and are excluded unless `args.owner_approvals.hosted_call_budget_usd > 0`.
- Where: gate · P3.

---

## P5 — Critic

### F-30 — Critic captured by the implementer's self-report; same-model blind spots
- Likelihood H · Impact High
- Failure: the critic receives the implementer's return value and confirms it; it shares the implementer's training-data beliefs about gradio/spaces (so it cannot see F-8 errors); "3 lenses" are the same model three times.
- Detection: critic output without a diff citation; critic never ran `gate.sh`; critic findings only restate the card.
- Guard: the critic prompt gives the diff range and the card, NOT the implementer's narrative; the critic must run `gate.sh` and the apicheck itself and cite hunks; lenses are mechanical-first (apicheck, grep-idiom lint, mutation red-proof, decision-fidelity sheet, scope allowlist) with the model only judging what tools cannot; schema requires `hunks_cited[] minItems 1` for any `pass`.
- Where: P5 (prompt design + schema) · gate.

### F-31 — Critic on security code trips the platform safeguard (observed) or strays out of scope
- Likelihood M · Impact High
- Failure: the simplification lens died on a `[cyber]` safeguard while reading security-tool code; the hardening item (python_eval env allowlist, `PR_SET_DUMPABLE`, `/proc/<ppid>/mem`, SSRF/DNS-rebinding guards) is the same material. A killed critic → `null` → the item passes unreviewed (F-41). Conversely a critic may drift into "make the model better at X" territory.
- Detection: `agent()` returned null on the hardening item; critic output discusses model behaviour rather than code.
- Guard: hardening prompts are framed defensively and narrowly (what the guard must refuse, with red-proof tests), split into small reading lists, run with `model:'fable'`; a null critic is retried once with a narrower list, then the item is marked `unreviewed → needs_owner` (never `pass`); the scope rule from the scout brief is in every critic preamble.
- Where: P5 (framing, model, retry) · X (null handling).

---

## P6 — Review + integration

### F-32 — Merge conflicts resolved by "pick one side"; changes lost at integration
- Likelihood H · Impact Critical
- Failure: branches from waves collide in `core/`; an integrator agent runs `git merge -X theirs` or hand-edits and silently drops hunks; the toolchain repo's own history shows "four real commits stranded" from unpushed worktrees — here there is no remote at all.
- Detection: for every merged item branch, `git cherry integration item/<n>` lists unmerged commits; per-branch added lines missing at integration HEAD (`git diff base..item | grep '^+'` sampled against `git show integration:<file>`); gate red after merge.
- Guard: integration is serial in DAG order by a dedicated integrator agent that rebases the item onto `integration`, resolves conflicts with the card in hand, runs `gate.sh`, and returns `{merged_sha, cherry_unmerged: [], gate_ledger}`; the script asserts `cherry_unmerged.length == 0`; a "no lost hunk" check compares patch-ids (`git patch-id`) of item commits against `integration`; bundle after each merge (F-2).
- Where: P6 (integrator + assertions) · X.

### F-33 — Worktree lifecycle: branch removed with its worktree, or left dangling
- Likelihood M · Impact High
- Failure: `git worktree remove` of an item whose branch was never merged; Workflow-managed worktrees are "auto-removed if unchanged" but manual ones are not; dangling worktrees lock branches (`git branch -D` refuses; `worktree add` fails on the same branch name) and the next wave stalls. The cwd repo's CLAUDE.md warns `worktree remove` follows junctions (Windows; low relevance on this Linux box).
- Detection: `git -C $BUILD_REPO worktree list --porcelain` shows worktrees for merged items; branch names reused across runs.
- Guard: worktrees live under a single `$BUILD_REPO/../wt/` root; the integrator removes a worktree ONLY after `cherry_unmerged == []`; branch names carry the run nonce (`item/<n>-<nonce>`); a P0 cleanup step prunes stale worktrees from a previous run after bundling.
- Where: P0 · P6.

### F-34 — Green on the branch, red on the merged tree
- Likelihood M · Impact High
- Failure: each item passes the gate in isolation; the integration of two green items breaks (import contract, duplicate symbols, moved tests, generated README drift).
- Detection: gate red on `integration` after a merge.
- Guard: gate runs after EVERY merge on the merged tree; a red merged tree spawns a fix agent scoped to `integration` with both cards; if unresolved in 2 rounds, the later item is reverted (`git revert -m 1`) and parked; the synthesizer reports the parked list.
- Where: P6.

---

## P7 — Owner-gated / staging / outward-facing

### F-35 — Outward-facing actions without explicit owner approval
- Likelihood M · Impact Critical
- Failure: `gh` is logged in with `GITHUB_TOKEN`; the HF connector exposes `create_repo`, `dynamic_space`, `hf_jobs`, `hf_fs_write`; `huggingface_hub` has `duplicate_space`, `add_space_secret`, `set_space_volumes` (REPLACES all mounts), `run_job`/`run_uv_job` (paid), `request_space_hardware` (paid). An agent implementing "the pipeline" creates the private GitHub repo, duplicates the Space for staging, sets secrets, or launches the quantization job — each is money, exposure, or an irreversible change; `set_space_volumes` can unmount the model.
- Detection: journal grep for those tool/method names; `git remote -v` in the build repo non-empty; `gh repo list` shows a new repo; Hub shows a new Space/repo.
- Guard: `args.owner_approvals` (F-6) is the only authorization; prompts forbid `gh repo create`, `git push`, any `HfApi` write method and the write MCP tools; the reviewer/critic schema has `outward_actions_taken: []` and the script aborts the run (log + synthesizer) if any stage returns a non-empty list; the orchestrator asks the owner to disable the HF connector's write tools (or the connector) and to confirm `gh auth status` scope for the build session; pipeline code (`deploy.yml`, `promote.py`) is WRITTEN and unit-tested against fakes but never executed.
- Where: P0 (owner pre-flight) · X (abort on outward action) · P7 (runbook).

### F-36 — The eval harness burns ZeroGPU quota or paid provider tokens
- Likelihood M · Impact Critical
- Failure: 12 prompts near 2k tokens at ~9 tok/s ≈ 12 × ~220 s ≈ 44 min > the 40 min/day PRO quota on `large`; past quota ZeroGPU usage is "automatically billed" (~$185 per 1M output tokens); the OpenAI SDK retries twice by default → one request can reserve three leases; hosted runs cost $12/M output tokens and an agent loop with retries multiplies it. A "let me just run the harness once" agent spends real money.
- Detection: harness invoked without `--backend fake`; `max_retries` ≠ 0 in client construction; any `budget_seconds`/`max_cost_usd` argument absent.
- Guard: harness defaults to `--backend fake --dry-run`; real backends require `--i-accept-cost <usd>` AND an env var only the owner sets; preflight computes GPU-seconds/cost from the catalog entry and refuses above `args.owner_approvals.*_budget`; `max_retries=0` and a rolling ledger file; tests assert the harness makes zero backend calls without the flag.
- Where: item 12 · gate (zero-call test) · P7 (owner runs it).

### F-37 — Staging-only behaviour reported as verified
- Likelihood H · Impact High
- Failure: local runs cannot observe: ZeroGPU import-time load / CUDA-emulation contract (the f90bb44 outage), lease sizing and `max_time` vs cold-start margin, which quota bucket `gradio_client` calls land in, fla/Triton behaviour in the forked worker, FP8/GPTQ load on `large`, Space rebuild resolution of requirements, `x-ip-token` presence, MCP over HTTP with a real client. Agents will still write "verified".
- Detection: any claim about these topics with `verification_level` ≠ `staging-required`/`owner-required`.
- Guard: a fixed taxonomy `verification_level ∈ {local-mechanical, local-stub, staging-required, owner-required, unverified}` in every schema; a keyword list (lease, quota, ZeroGPU, worker fork, Triton, `x-ip-token`, MCP transport, Space rebuild) forces ≥ `staging-required`; the runbook (P8) lists each staging-required claim with its exact measurement step and the number it should record (e.g. cold-start margin, tok/s, quota before/after one 16-token call).
- Where: X (schema) · P8 (runbook).

### F-38 — The owner's other agent (or its scheduled tasks) resumes pushing mid-build
- Likelihood M · Impact High
- Failure: the owner said the other agent will not work, but a stop notice is still pending, its weekly `update_deps_and_deploy.py` and 12 h `keepalive.py` Windows scheduled tasks still exist, and its `deploy_space.py` `upload_folder` overwrites every file with its local copy. If it pushes: the Space HEAD moves past `f88b120`, and the first CI promotion either overwrites its work or is reverted by its next deploy; `set_space_volumes` from two writers can unmount the model.
- Detection: at promotion time, the Space repo HEAD ≠ `args.base_sha` (read-only check via `hub_repo_details`/`hf_fs stat`); new commits by the other agent's author in the Space history.
- Guard: the workflow never touches the Space (F-35), so mid-build pushes cannot corrupt the build; the promotion runbook step 0 is "assert Space HEAD == base or explicitly rebase/adopt the delta"; the owner checklist includes: send the stop notice, disable both scheduled tasks, rotate the `HF_TOKEN` that agent uses (that is the effective stop), delete `NF4_EXPORT`/`NF4_UPLOAD_TOKEN` secrets.
- Where: P0 (owner checklist) · P7 (assert at promotion) · P8.

### F-39 — Flaky WebFetch and Hub calls → fabricated fallback values
- Likelihood M · Impact Medium
- Failure: a docs fetch or Hub read times out; the agent "remembers" the price, the sha, the hardware sizes, or the docs sentence and writes it as fetched. The catalog (F-25), the api ledger (F-8) and README claims (F-24) are the sinks.
- Detection: values without a saved raw response; `fetched_at` missing; two agents citing different numbers for the same fact.
- Guard: fetch wrappers retry 3× with backoff, then return `unresolved`; schemas have `source: {url, saved_path}` and the gate rejects catalog/api-ledger entries whose `saved_path` does not exist; unresolved facts are committed as `TODO(owner-verify)` entries, never as numbers.
- Where: P1 · gate (saved-path check) · P8.

---

## P8 — Synthesizer and run-level mechanics

### F-40 — The final synthesizer summarizes work that did not happen
- Likelihood H · Impact Critical
- Failure: the synthesizer receives stage outputs (claims) and a `.filter(Boolean)`-cleaned list; items that returned `null`, were parked, reverted (F-34), or blocked on the owner vanish; skipped conformance rows read as passes; "14/14 done" is written for 9 merged items.
- Detection: synthesizer's per-item table vs `git -C $BUILD_REPO log integration --oneline` and the `.gate/last_run.json` on `integration`; items in `plan/items/` with no row.
- Guard: the synthesizer gets ONLY mechanical inputs: the item DAG, the script's `ledger[]` (every stage's status incl. null/blocked/parked/reverted), the final gate ledger on `integration`, `git log --stat`, and the skip counts; it must emit one row per item with `status ∈ {merged+gate-green, merged+gate-red, parked, reverted, blocked_on_owner, dropped(null:<reason>), not_attempted}`; a second "synthesizer verifier" agent cross-checks every `merged` row against `git log` and every `verified` claim against the ledger and rewrites rows that do not match; the report ends with the owner runbook (F-37/F-38 items) and the explicit list of DoD lines not done.
- Where: P8 (two agents; mechanical inputs only) · X (ledger).

### F-41 — The null-result contract mishandled
- Likelihood H · Impact High
- Failure: `agent()` returns `null` on user skip or terminal API error; `pipeline` drops a throwing item to `null` and skips its remaining stages; `parallel` resolves throwing thunks to `null`. `.filter(Boolean)` (the reference's own idiom) erases the item; `result.head_sha` on null throws and ends the run.
- Detection: `ledger` has fewer entries than items × stages; unhandled TypeError in the script log.
- Guard: every `agent()` call goes through `const r = await safeAgent(stage, item, prompt, opts)` that records `{item, stage, status:'null', reason}` in `ledger` and returns a typed `{status:'null'}` object; stage callbacks branch on `status`; implement/critic nulls retry once (narrower prompt, `model:'fable'`), then park the item; never `.filter(Boolean)` without pushing the removed entries to `dropped[]` and `log()`-ing them.
- Where: X.

### F-42 — Platform safeguard kills an agent mid-task; no graceful degradation
- Likelihood M · Impact High
- Failure: observed once this session on security-tool code. Mid-task death leaves a half-edited worktree (files with syntax errors, an index with staged partial changes, an unfinished commit), a lock (`.git/index.lock`), or a running server (F-26); the retry starts from the same prompt and redoes or double-applies edits.
- Detection: null return; worktree dirty with no commit; `index.lock` present; ruff E9 syntax errors on the branch.
- Guard: implementers commit per coherent step so a kill loses ≤ one step; the retry prompt begins with "inspect `git -C … status` and `git log`; continue from the last commit; discard uncommitted partial edits only if they do not compile"; gate pre-step removes stale `index.lock` older than 10 min and kills stray servers; the hardening item is split into 3 cards with narrow reading lists and `model:'fable'`; two consecutive nulls on the same card → park, not retry.
- Where: P3 (commit granularity) · X (retry policy) · gate pre-step.

### F-43 — Resume cache replays stale results after the repo changed
- Likelihood H · Impact Critical
- Failure: "same script + same args → 100 % cache hit": resume replays cached `agent()` returns for the unchanged prefix, including an implementer's `{head_sha: abc}` although the branch was rebased, reverted, or the worktree pruned since; downstream stages then act on a sha that no longer exists or on a state that a later merge changed. The cache is keyed by call order, not by repo state.
- Detection: a cached `head_sha` that `git cat-file -e` cannot find; ledger `head_sha` ≠ `git rev-parse` of the branch.
- Guard: `args` carry `base_sha`, `integration_sha_at_launch`, and a `run_nonce`; the orchestrator computes them with `git rev-parse` before every invocation, so a moved repo changes `args` and misses the cache deliberately; every stage that consumes a sha first runs a cheap `state probe` agent that verifies the sha exists and the branch points at it, and the script treats a mismatch as `stale → rerun live`; resume from a run is allowed only if `integration_sha_at_launch` still equals the live integration head.
- Where: P0 (orchestrator computes args) · X (state probes).

### F-44 — Concurrency 2 makes wall-clock explode; agents time out; the host stops
- Likelihood H · Impact High
- Failure: ~70+ agents at concurrency 2 with a serialized DAG (items 1→2→3→4→5 must be sequential) → 10-15 h of wall-clock. Individual agents running long installs or a foreground server hit tool timeouts; adversarial "3-5 vote" patterns multiply agent count; Codespaces idle timeout (default 30 min, configurable up to 240; whether an unattended terminal process counts as activity is UNVERIFIED) can stop the container mid-run.
- Detection: `log()` timestamps per stage (from `args.launched_at` + agent-reported `date -u`); stage durations > 45 min; ledger gaps.
- Guard: split the "one workflow" into ONE script with phases that are idempotent against git state, and expect to invoke it several times (the reference's own guidance: several workflows in sequence with the orchestrator in the loop); waves by DAG (F-14); single-vote critics with mechanical lenses instead of 3-5 model votes; the setup stage pre-builds the venv (F-5); the owner sets the Codespace idle timeout to the maximum before launch and keeps a client attached; the script `log()`s an estimated remaining wall-clock at each wave from measured stage durations.
- Where: P0 (owner + orchestrator) · X (waves, logging).

### F-45 — Budget exhaustion mid-run; `budget.total` null; the lifetime agent cap
- Likelihood M · Impact High
- Failure: when `spent() ≥ total` every further `agent()` throws; in a loop this ends the script before the synthesizer runs; with no target `budget.total` is `null` and loop guards written as `while (budget.remaining() > X)` never trigger; the 1000-agent lifetime cap is reachable with unbounded fix loops.
- Detection: script ends without a synthesizer entry in `ledger`; agent count > 600 before P6.
- Guard: all loops are bounded by iteration caps first and budget second; the script reserves a synthesizer slice (stop scheduling new items when `budget.total && budget.remaining() < 0.15 * budget.total`, or when `agentCount > 800`) and ALWAYS runs P8 with whatever state exists; P8 itself is wrapped so a throw still produces a `log()` of the ledger.
- Where: X.

### F-46 — Schema validation failures and schema-valid-but-empty returns
- Likelihood M · Impact Medium
- Failure: a schema with a free-text `diff` field overflows; enums mismatch; `required ⊄ properties` makes every call fail; an agent returns a valid object with `dod: []`, `commands_run: []`, `hunks_cited: []` and `done: true`.
- Detection: StructuredOutput errors in the journal; empty arrays alongside `done:true`.
- Guard: small schemas (paths, shas, enums, counts; no blobs; strings ≤ 2 k); `minItems` on evidence arrays; the script re-validates semantics (`done === (dod.every(exit_code===0))`); a 1-agent dry-run of the script (a smoke workflow with `args.smoke=true` that runs only the state probe and a trivial implement stage) validates every schema before the real launch.
- Where: P0 (smoke run) · X.

### F-47 — Script-level bugs end the run or corrupt resume
- Likelihood M · Impact High
- Failure: `meta` not a pure literal or a phase title not matching `phase()`; `Date.now()`/`Math.random()`/`new Date()` used (throw); an uncaught throw inside a `while` loop (not inside `pipeline`) ends the script; `pipeline` items sharing a global `phase()` race; per-item state kept in closures that resume cannot reconstruct.
- Detection: the smoke run (F-46) fails at load; journal shows the abort line.
- Guard: timestamps and nonces only via `args`; `try/catch` around every stage body with `ledger.push`; `phase` passed per `agent()` call inside pipelines; all cross-stage state derived from the ledger array that is rebuilt from returns (so resume replays it); the smoke run is mandatory before the real run.
- Where: P0 · X.

---

## 1. What can be tested where (so nobody claims more than the environment allows)

| Level | Testable here (3.12 venv, no GPU, no tokens) | Needs the staging Space | Needs the owner |
|---|---|---|---|
| Static gate | ruff F821/F811/F401/E9 under py312, compileall, claim-vs-diff lint, CRLF/LFS/blob/junk checks, secrets regex, import-contract test (`core/` never imports gradio/fastapi/spaces/torch), apicheck against the pinned wheels | — | — |
| Unit / stub | 73 existing tests + new ones with `pytest-socket`; `FakeEngine`/`backends/fake`; tool_parse, SSRF guard functions, regex/calculator timeouts, archive caps, `python_eval` hardening red-proofs with a canary env var (env allowlist, `/proc/<ppid>/environ` EACCES after `PR_SET_DUMPABLE=0`, rlimits trip, killpg leaves no orphans, off on every surface); constants pin; README render check; persona absence test; `models.yaml` schema; harness `--dry-run` zero-call test | — | — |
| Local integration | FastAPI `TestClient` for `/v1` (auth, 429, size/role limits, SSE framing validated with the `openai` SDK types); `gradio_client==2.6.1` against a local server on a free port with `/healthz` sha assert; MCP tool listing if `gradio[mcp]` installs; worker `encode`/`lease` pure modules (estimator rows at 9 tok/s, `max_time` arithmetic, resume encode with `continue_final_message="reasoning_content"`) | — | — |
| Platform behaviour | nothing (`spaces.GPU` is a no-op off-platform) | CPU Space boot + `/healthz` sha; worker Space import-time load under CUDA emulation; lease sizing, cold-start margin, measured tok/s; quota bucket of `gradio_client` calls with the scoped token (compare quota before/after one 16-token call); fla/Triton in the forked worker; FP8 vs GPTQ load on `large`; requirements resolution on rebuild; canary + rollback rehearsal | the owner creates the staging Space(s) and the scoped token |
| Money / identity | nothing | — | one metered hosted call through the router (cents) that becomes the recorded fixture; the real harness run under a stated budget; the quantization HF Job; GitHub repo + Trusted Publisher OIDC; secrets; revoking the pasted token and the other agent's token; disabling the Windows scheduled tasks; Dev Mode off; production promotion |

## 2. Invariants the SCRIPT must encode (prompts are advisory; these are not)

1. `args` = `{build_repo, venv, gate_sh, base_sha, integration_sha_at_launch, run_nonce, launched_at, toolchain_status_snapshot, owner_approvals{…}, smoke}` — computed by the orchestrator with `git rev-parse` immediately before invocation (F-1, F-2, F-43).
2. `safeAgent()` wrapper: records every call in `ledger[]` including nulls, blocked and parked states; nothing is ever silently filtered (F-41, F-40).
3. Every stage return carries `{item_id, repo_toplevel, base_sha, head_sha, ledger_hash, status, outward_actions_taken[], installed_packages[], verification_level}`; the script asserts `repo_toplevel === args.build_repo`, `outward_actions_taken.length === 0` (else abort), `installed_packages.length === 0` (F-1, F-5, F-35).
4. Per-item caps: ≤ 3 fix rounds, ≤ 2 critic rounds, ≤ 2 retries on null; exceed → park (F-27, F-42).
5. Waves by DAG with disjoint `files_allowed`; serial integration with `cherry_unmerged === []` and gate-green after each merge (F-14, F-32, F-34).
6. Budget/agent-count reserve for P8; P8 always runs; P8 receives mechanical inputs only and is followed by a verifier agent (F-40, F-45).
7. Owner approvals are data; a missing approval yields `blocked_on_owner`, never an action and never a retry (F-6, F-35).
8. Smoke run of the script with `args.smoke=true` before the real launch (F-46, F-47).

## 3. The mechanical gate (`gate.sh`, runs only under `$VENV` = `/usr/bin/python3.12` venv) — referenced by most guards

0. Pre-step: refuse if `python -V` ≠ 3.12.*; kill stray listeners started from `$BUILD_REPO`; remove `index.lock` older than 10 min.
1. `git ls-files --eol` has no `w/crlf|w/mixed|i/crlf`; `git lfs ls-files` empty; no blob > 5 MB in the range; no tracked `__pycache__|\.pyc|\.venv|\.whl|\.log|idx\.json|runlog_tail\.txt`.
2. `ruff check --select F821,F811,F401,E9 --target-version py312 .` (pyflakes as fallback); `python -m compileall -q`.
3. apicheck: every `apis_used` entry resolvable in the pinned wheels with the listed kwargs.
4. `pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1` run twice; exit code must be 0 both times; `collected ≥ baseline − Tests-Removed`; skip/xfail counts non-increasing without a trailer.
5. Import smoke: `SPACES_ZERO_GPU` unset; `python -c "import app"` (CPU front, must not load models) and `python -c "import worker.app"` with the torch/transformers stubs; import-contract test.
6. Claim-vs-diff lint over every commit in the range (waiver trailer once per item, named reviewer).
7. Idiom lint (warnings the reviewer must clear): `preexec_fn=`, `__wrapped__`, `rmtree` in unload, `prefill_chunk_size` with the VLM class, `lease_s - 30`, `PYTEST_CURRENT_TEST`, `sys.modules.get("pytest")`.
8. `tools/render_readme.py --check`; `tests/test_constants_pin.py`; persona absence test; `models.yaml` schema + provenance file existence.
9. Secrets regex over the diff range.
10. Red-proofs: the gate goes RED on the f88b120 tree and on the false-claim fixture commit, GREEN on the cleaned base (recorded).
11. Write `.gate/last_run.json` `{head_sha, python, started_at, steps:[{name, exit_code, summary}], pytest:{collected, passed, skipped, xfailed}}` — the only admissible evidence of verification.

## 4. Coverage notes

- Every item the brief listed is covered: tests weakened (F-18), hallucinated APIs with wheel-verified examples (F-8), over-claiming/partial completion (F-19), verification theater (F-12, F-30), fix loops (F-27), merge/lost changes (F-32, F-33, F-34), context loss (F-15), resume caching (F-43), concurrency/wall-clock/timeouts (F-44), safeguard kills + degradation (F-42, F-31), null contract (F-41), local vs staging vs owner (§1, F-37), outward actions (F-35, F-6), secrets (F-7), scope creep (F-16), dependency drift (F-23, F-5), line endings (F-21), claims vs constants (F-24), harness cost (F-36), persona boundary (F-17), flaky network (F-39, F-29), large files/LFS (F-22), schema failures (F-46), budget exhaustion (F-45), synthesizer over-claiming (F-40), the other agent resuming pushes (F-38).
- Program-specific additions not in the brief: wrong-repo/cwd hazard (F-1), volatile build path (F-2), wrong base (F-3), foreign CLAUDE.md (F-4), recommendation-vs-decision confusion (F-9), CORRECTED-line neglect (F-10), stale line refs (F-11), monolithic items (F-13), fake-backend fidelity + mutation red-proofs (F-20), catalog provenance (F-25), leaked local servers (F-26), gate self-tampering (F-28), script-level bugs (F-47).
- Verified against sources for this report: `spaces.GPU` no-op off-platform (`decorator.py:99-100`), `Chatbot`/`ChatInterface` have no `type` kwarg (6.26.0), `spaces.GPU(size=…)` (`decorator.py:76`), no `presence_penalty` in `GenerationConfig` (5.16.1), `restart_space` has no `revision` (`hf_api.py:8601`), `gradio-client==2.6.1` is gradio's pinned client, `spaces` Requires-Python `<3.15`, `_is_stateful = True` (`modeling_qwen3_5.py:812`), `continue_final_message: bool | str` (`chat_template_utils.py:504`), local box facts (nproc 4, Python 3.14.2 + `/usr/bin/python3.12`, missing tools, env var names).
- Not verified (stated as such in the text): Codespaces idle-timeout behaviour for unattended processes; whether `GITHUB_TOKEN` in this Codespace can create repos; per-agent tool timeouts inside Workflow subagents (assumed equal to this session's Bash defaults); the exact quota bucket for token-less calls (already UNVERIFIED in the findings).
- Deliberately out of scope: anything about model or persona behaviour beyond the engineering boundary; no live Space, Hub write, or connector calls were made and no token was sought.
