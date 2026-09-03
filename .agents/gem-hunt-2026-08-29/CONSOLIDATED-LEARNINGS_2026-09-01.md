# Consolidated Learnings — everything outside the canonical Databricks packet
**Date:** 01.09.2026 · **Unit:** `consolidated-learnings-2026-09-01` · **Mode:** read-only synthesis (no config/code changes)

## Scope and boundary

**In scope (read for this unit):**
- All 15 lens files, `C:\Users\Prekzursil\source\agent-skills-toolchain\.agents\gem-hunt-2026-08-29\lenses\01..15` (445 KB total, filenames and sizes enumerated on disk this unit).
- Prior baseline: `C:\Users\Prekzursil\source\agent-skills-toolchain\.agents\CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`.
- Behaviour SSOT: `C:\Users\Prekzursil\AGENTS.md`.
- `C:\Users\Prekzursil\.config\fabric\fabric-local-guide_2026-08-29.md`.
- `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\glm53-space\` — `README.md`, `glm53_core.py`, `.coverage-thresholds.json`.
- Databricks packet **root synthesis files only**, for cross-program *method* lessons: `synthesis-acceptance-review.md`, `verification-and-convergence-receipt.md`, `locus-membership-reconciliation.md` under `C:\Users\Prekzursil\Desktop\Codex Useful Prompts\databricks-threat-model_2026-08-29\`.

**Explicitly out of scope:** Databricks `evidence\` and `quarantine\` subtrees (raw evidence), and any Databricks-internal finding that is not a transferable method lesson.

## Verification legend (fail-closed, per AGENTS.md verification doctrine)

| Tag | Meaning |
|---|---|
`disk-verified` | I re-read the artifact or re-ran the measurement **in this unit**. Value quoted is mine.
`lens-claimed` | Asserted in a lens file by an earlier agent; artifact **not** re-read here. Treat as hypothesis, not fact.
`SSOT` | Stated in `AGENTS.md` / `CLAUDE.md`, i.e. binding rule rather than measurement.
`NOT-CHECKED` | In scope conceptually, no evidence gathered. Never folded into a pass.

Nothing below is upgraded from `lens-claimed` to `disk-verified` by agreement between lenses; convergence of two agent write-ups is not corroboration when both drew on the same read.

---

## §0 — Receipts taken in this unit (disk-verified)

These are the only measurements in this document I am willing to call fact.

**R1 — MCP registry now holds 42 servers; Codex coverage still 4.**
`C:\Users\Prekzursil\.agents\agents.json`, parsed this unit. Servers live under `mcp.servers` (an object), **not** a top-level `mcpServers` key. Target tally across all 42: `claude=42`, `codex=4`, `cursor=0`. `AGENTS.md` records "measured 2026-08-20: Claude 40/40, Codex 4/40" — the Claude/Codex ratio holds, the denominator has grown by 2. **Action:** refresh the parenthetical in `AGENTS.md` to `42` at next SSOT edit (not this unit — read-only).

**R2 — `glm53-space` is registered, is tagged `claude-only`, and is nevertheless live in Cursor.**
Registry node: `targets: ["claude"]`, `enabled: true`, `transport: stdio`, command `uv run --locked --directory ...\tools\mcp\glm53-space python mcp_server.py`, `requiredEnv: ["HUGGINGFACE_TOKEN"]`, tags include `approved`, `claude-only`, `hosted-inference`. Independently: `C:\Users\Prekzursil\.cursor\mcp.json` contains 2 `glm53-space` matches, and the `glm53-space` namespace (`glm53_chat`) is present in this Cursor session's own dynamic tool catalogue. Since `targets=cursor` is `0` for all 42 servers, **the `targets` field does not gate Cursor exposure** — the Cursor mirror is derived from the Claude surface, exactly as `AGENTS.md` describes. Consequence: the `claude-only` tag is factually wrong about reach, and any future reasoning that uses `targets` to predict Cursor exposure will be wrong. This is a labelling/precision defect, not a leak.

**R3 — The shell-guard coverage regression is OPEN and reproducing daily.**
`C:\Users\Prekzursil\.agents\logs\guard-tamper.log` (tail, this unit) shows `TRACER MEL-DEFERRAL guard failed to trip on: git push --force origin main | git reset --hard HEAD~3 | git clean -fdx | cat .env` on **28, 29, 30 and 31 August 2026**, most recently `2026-08-31T08:30:02+03:00`. Four consecutive daily tracer runs, four failures, same four contraband strings. The 27.08 line above them (`TRACER OK 5/5 contraband rounds flagged would-deny`) dates the regression precisely: it broke between 27.08 09:19 and 28.08 08:30. The same log also records `APPEARED ...\.cursor\hooks.json` on 28.08 and `DRIFT ...\.agents\agents.json` on 28.08 and 30.08 — consistent with R1's grown denominator.

**R4 — Two harness logs are unbounded and large.**
Measured in `C:\Users\Prekzursil\.agents\logs` and `...\state\harness`: `cursor-afterfileedit.jsonl` = **100,363,036 bytes (~95.7 MiB)**, last written 01.09.2026 00:39 (i.e. still growing this session); `terminal.jsonl` = **147,444,707 bytes (~140.6 MiB)**. Next largest are `cursor-shell-guard.jsonl` (2.54 MB), `estate-deny-guard.jsonl` (1.14 MB), `cursor-mcp-guard.jsonl` (855 KB), `cursor-subagent-lifecycle.jsonl` (462 KB). Two files therefore account for ~98% of harness log bytes. On a box under chronic RAM/disk pressure (digest lines this session: `C: 99% used`, `RAM 3.7–3.9 GB free`) this is the single largest mechanical contributor the harness controls.

**R5 — `cursor-subagent-lifecycle.jsonl` stopped 29.08.**
Last write `29-Aug-26 16:12`, while `cursor-shell-guard.jsonl` and `estate-deny-guard.jsonl` were written minutes ago (01.09 00:42–00:43). The subagent-lifecycle instrument is **not** recording current sessions, including this one. Whether it is unwired or merely idle is `NOT-CHECKED`; either way, subagent-failure metrics computed from it are stale by three days.

**R6 — The GLM adapter has a real coverage SSOT at 80%, not 100%.**
`...\glm53-space\.coverage-thresholds.json`: thresholds 80/80/80/80, `enforcement.command` = `uv run pytest -q --cov=glm53_core --cov=mcp_server --cov=openai_proxy --cov-branch --cov-fail-under=80`, `blockPRCreation` and `blockTaskCompletion` both `true`. Anyone quoting the media-studio 100% pair for this project is quoting the wrong project (the `CLAUDE.md` warning about exactly this).

**R7 — Method receipt against myself: my first registry probe was a false negative.**
My initial probe read `$j.mcpServers` and returned "0 servers, no glm match". The registry uses `mcp.servers`. Had I stopped at one probe I would have written a confident, wrong finding into this document (a fabricated registry-drift defect). The `AGENTS.md` rule "a single probe is not evidence; corroborate load-bearing absences with a second mechanically independent check" earned its place here empirically, in this unit. **Every absence claim in this document that is not double-probed is marked `NOT-CHECKED`, not "absent".**

---

## §1 — Deduplicated status ledger

One row per distinct item, collapsing restatements across the 15 lenses and the 27.08 baseline. "First seen" credits the earliest source; later lenses that re-derived the same thing are not listed separately.

### BUILT — on disk and doing work

| Item | Evidence | Provenance |
|---|---|---|
GLM 5.3 direct-HF adapter (MCP tool + OpenAI-compatible proxy + coverage gate) | `tools\mcp\glm53-space\{README.md,glm53_core.py,.coverage-thresholds.json}` | `disk-verified` (R2, R6) |
MCP registry + three-way merge sync (Codex TOML, Claude JSON, Cursor JSON) | `agents.json` 42 servers; `.cursor\mcp.json`; `AGENTS.md` sync policy | `disk-verified` (R1, R2) |
Guard-tamper daily drift + contraband tracer | `logs\guard-tamper.log` with dated OK/DRIFT/TRACER lines | `disk-verified` (R3) |
Shell/MCP/deny guard logging | `cursor-shell-guard.jsonl`, `cursor-mcp-guard.jsonl`, `estate-deny-guard.jsonl`, all currently written | `disk-verified` (R4) |
Fabric local install with curated dual-identity context (`miky-core.md`, `andrei-core.md`) | `.config\fabric\fabric-local-guide_2026-08-29.md` | `lens-claimed` + guide re-read; per-command behaviour not re-run |
Estate locks (ports 8765/8812/8317, never-rotate, browser 3-way profile choice, private-repo rule) | `AGENTS.md` marker block `estate-locks-2026-08-27` | `SSOT` |
Verification doctrine (`disk-verified` vs `agent-claimed`, budget-abort ≠ green, 60 s grace) | `AGENTS.md` "Verification doctrine" | `SSOT` |
Statusline budget pacing (`5h:N%`, `wk:N%`) | `CLAUDE.md` / `AGENTS.md` AgentBridge block | `SSOT`, `NOT-CHECKED` this unit |

### PLANNED — decided, not on disk

| Item | Source | Note |
|---|---|---|
Unified session analytics archive (SQLite + FTS5, DuckDB mirror, content-free metrics) | lens 05 | Largest single unbuilt item; design settled, nothing materialised |
Attributable-evidence gate / claim-verify hardening as executable check | lenses 02, 11 | Currently doctrine text only |
Denominator registry + additive event contract for metrics | lens 11 | Prerequisite for every metric below it |
Cursor SDK adapter + cloud-agent admission gate (G-68) | lens 04 | Blocked on nothing but effort |
Class-aware lease clocks / budget-by-active-surface-area | lens 14 | Governance layer, no artifact |
Two-axis promotion ladder (reliability × scope maturity) | lens 14 | Governance layer, no artifact |
People Analytics domain router + versioned metric contracts | lens 06 | Gated on legal/privacy work, see §5 |

### STALE — was true, no longer is

| Item | Correction | Provenance |
|---|---|---|
`AGENTS.md` "Claude 40/40, Codex 4/40" | Denominator is now 42; Codex still 4 | `disk-verified` (R1) |
`glm53-space` is "claude-only" | Live in Cursor too; `targets` does not gate Cursor | `disk-verified` (R2) |
Guard tracer "OK 5/5 contraband rounds" (27.08) | Failing on 4 strings every day since 28.08 | `disk-verified` (R3) |
Subagent-lifecycle telemetry reflects current sessions | Last write 29.08 16:12 | `disk-verified` (R5) |
media-studio's `cd app && npx vitest` / 100% pytest pair as a general command | Dead at `~`; per-project SSOT only; GLM project is 80% | `SSOT` + `disk-verified` (R6) |
`~/Cowork/memory.md` as default memory dump | Retired 24.08.2026; archive only | `SSOT` |
AgentBridge budget tools (`get_budget`, `check_budget`) | Plugin disabled; tools do not exist; use statusline | `SSOT` |

### REFUTED — proposed and rejected on evidence

| Item | Why | Provenance |
|---|---|---|
Duplicate/second vector store (Mem0, Graphiti, LynxMCP, "CORE") | basic-memory is sole semantic writer (G-81, G-75/76/83/84) | `SSOT` |
Langfuse or equivalent hosted trace sink | Egress of session content; local archive is the sanctioned shape | `SSOT` + lens 10 |
OpenRouter as Cursor BYOK or Claude `ANTHROPIC_BASE_URL` | Spend-capped CLI/Codex sidecar only | `SSOT` |
Always-on daemons for analytics/memory/DB | On-demand start/stop; nothing binds 8765/8812/8317 but its owner (G-92) | `SSOT` |
Credential rotation of any kind | NEVER-ROTATE, overrides all tooling advice | `SSOT` |
Silent capability removal to buy reliability | Present the tradeoff instead (28.08 hard rule) | `SSOT` |
Cloud memory sync for research/agent memory | `D:\Research` + basic-memory only (G-82) | `SSOT` |
Persistent Cursor-bridge mode / non-local quota bridge | Wrappers stay process-local (G-32); `:8317` local-only, 7-day retire clock (G-23/34) | `SSOT` |
Public visibility for `agent-skills-toolchain` | Contains live browser profiles in plaintext by owner decision; public = credential leak | `SSOT` |
Injecting skill bodies into prompts | Pointers + on-demand Read (G-80/93); subset use is emergency-only with `SUBSET-USED` log | `SSOT` |

### ADOPT — high confidence, do it

Ranked; full cards in §2/§5. `A1` log bounding (R4) · `A2` guard-coverage repair (R3) · `A3` subagent-lifecycle re-wire (R5) · `A4` `glm53-space` label correction + `AGENTS.md` count refresh (R1/R2) · `A5` denominator registry + event contract before any dashboard · `A6` supersession-with-named-successor in memory writes · `A7` artifact-hash (not command-hash) receipts · `A8` Databricks-derived claim-discipline rules folded into the acceptance-review template.

### TRIAL — promising, needs a measured pilot with a kill criterion

`T1` phi-accrual suspicion for stall detection (lens 15) · `T2` Banker's safe-state admission for RAM (lens 15) · `T3` metamorphic MCP contracts for fragile tools (lens 15) · `T4` generational context tenure (lens 15) · `T5` Tall-Man agent identities with confusable rejection (lens 15) · `T6` branchable two-plane checkpoints (lens 03) · `T7` compact codebase map à la Aider (lens 03) · `T8` Deficit Round Robin for hook fairness + value-weighted Age of Information (lens 01) · `T9` anti-windup / bumpless transfer for saturated executors and model handoffs (lens 01) · `T10` difficulty-diversity coreset for eval set selection (lens 02).

### SKIP — considered, not worth it here

Cursor Memories as an automation surface (lens 04 — profile-scoped, opaque, duplicates basic-memory) · `goose mcp` serve and Goose bundled memory (G-12/42/39/44) · Agy with a private `mcp.json` (G-72/95) · DB MCP with no live DB task (G-92) · upstreaming Fabric patterns (G-58, private-only) · `agent worker start` under 8 GB free RAM (G-26) · more than one concurrent `cursor-agent` (G-36) · headless-agent commits (G-68).

---

## §2 — Topic-by-topic learnings

Card format: **Evidence** · **Status** · **Value×Effort** · **Confidence** · **Next action** · **Program**. Programs are `harness` (this estate's agent harness), `Databricks` (the canonical packet), or a named `separate program`.

### §2.1 Cursor native and cloud agents

**L-01 — Cursor SDK is the right adapter seam; hand-rolled orchestration is the thing to retire.**
- Evidence: `lenses\04-cursor-native.md` (re-audited 01.09.2026 00:27, the freshest lens on disk).
- Status: **PLANNED**, `lens-claimed`. No adapter on disk.
- Value×Effort: High × Medium.
- Confidence: Medium — the SDK's existence and shape are lens-claimed; I did not re-read Cursor's SDK surface this unit.
- Next action: before writing any adapter, run a live preflight that enumerates actually-available models and repositories and writes the result to a dated receipt; build against the receipt, not against the docs.
- Program: harness.

**L-02 — Cloud-agent dispatch needs an admission gate, not a policy paragraph.**
- Evidence: `lenses\04-cursor-native.md`; lock G-68 in `AGENTS.md` (`estate-locks` block).
- Status: **PLANNED** (gate), **SSOT** (the rule it enforces: background/headless agents never commit; they report diffs).
- Value×Effort: High × Low-Medium.
- Confidence: High on the rule, Medium on the gate design.
- Next action: express G-68 as a per-project cloud policy capsule checked at dispatch time — admit/deny with a logged reason — so a cloud agent cannot be launched into a repo whose policy forbids it. Pair with a native usage/billed-cost receipt so dispatch cost is attributable per project.
- Program: harness.

**L-03 — Cloud returns are unverified inputs.**
- Evidence: `lenses\04-cursor-native.md` (artifact manifest / download verifier), `lenses\10-security-privacy.md` (cloud return integrity, cloud retention).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × Low.
- Confidence: High — this is structurally the same problem the Databricks acceptance review flagged (self-certification), so the argument transfers even without new measurement.
- Next action: require a manifest (path + size + hash) for every artifact a cloud agent returns, and verify hashes locally before the artifact is allowed to influence a decision. Absent manifest ⇒ `agent-claimed`, never `disk-verified`.
- Program: harness.

**L-04 — Cursor Memories: SKIP, with the reason recorded so it is not re-proposed.**
- Evidence: `lenses\04-cursor-native.md`.
- Status: **SKIP**.
- Value×Effort: Low × Low.
- Confidence: Medium.
- Next action: none. Automation profiles carry the context instead; basic-memory remains the sole semantic store (G-81). Recorded here specifically to stop the fourth rediscovery.
- Program: harness.

**L-05 — Custom subagents are underused relative to their cost.**
- Evidence: `lenses\04-cursor-native.md`; `disk-verified` R5 (lifecycle telemetry stopped 29.08, so current usage is unmeasured).
- Status: **TRIAL**.
- Value×Effort: Medium × Low.
- Confidence: Low — cannot be argued on data while R5 stands.
- Next action: fix R5 first. Deciding subagent policy on three-day-stale telemetry is exactly the false-green pattern this document exists to prevent.
- Program: harness.

### §2.2 GLM direct-HF MCP/proxy and the picker limitation

**L-06 — The adapter deliberately bypasses the public Gradio Space and calls the official HF router.**
- Evidence: `tools\mcp\glm53-space\README.md` and `glm53_core.py` (re-read this unit): `HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"`, `HF_MODEL_ID = "zai-org/GLM-5.3:zai-org"`, `MODEL_ID = "glm-5.3-custom"`, `MAX_PROMPT_CHARS = 500_000`, timeout 120 s, `max_retries=1`.
- Status: **BUILT**, `disk-verified`.
- Value×Effort: already paid.
- Confidence: High.
- Next action: none for the call path. Note the design virtues worth copying into other adapters: a typed error hierarchy (`Glm53ValidationError` vs `Glm53UpstreamError`), upstream detail deliberately **not** surfaced to the caller, text-only content enforcement, injectable `client_factory` for tests, and a token resolver that accepts `HF_INFERENCE_TOKEN` / `HUGGINGFACE_TOKEN` / `HF_TOKEN` in that order.
- Program: harness.

**L-07 — The picker limitation is a *presentation* constraint, and the current workaround is a local OpenAI-compatible proxy.**
- Evidence: `README.md` (proxy rationale, `glm-5.3-custom` model id); `openai_proxy.py` present in the project and named in the coverage command (`--cov=openai_proxy`), `disk-verified` via `.coverage-thresholds.json`.
- Status: **BUILT** (proxy exists), with a standing constraint.
- Value×Effort: Medium × already paid.
- Confidence: Medium-High — the file's existence and coverage enrolment are `disk-verified`; I did not exercise the proxy this unit.
- Next action: keep the proxy **process-local and on-demand** (G-32 forbids a persistent Cursor-bridge mode; G-92-style on-demand start/stop applies). Do not promote it to a daemon to make the picker nicer — that trades a labelling annoyance for a banned always-on service.
- Program: harness.

**L-08 — `claude-only` is the wrong label; correct it rather than restrict the tool.**
- Evidence: `disk-verified` R2 — registry `targets: ["claude"]` + tag `claude-only`, yet `.cursor\mcp.json` carries it and `glm53_chat` is in this session's namespace; `targets=cursor` is 0 for all 42 servers.
- Status: **STALE label / ADOPT (A4)**.
- Value×Effort: Medium × Very low.
- Confidence: High — two mechanically independent signals (file contents, live tool catalogue).
- Next action: at the next SSOT edit, retag to reflect actual reach (Claude + Cursor mirror) and add one line to `AGENTS.md`'s MCP sync policy stating explicitly that **`targets` governs Codex/Claude merges while Cursor is mirrored from the Claude surface**, so `targets` is never again read as a Cursor gate. Removing the tool from Cursor would be a silent capability removal — banned; fix the label, keep the capability.
- Program: harness.

**L-09 — This project's coverage gate is 80%, blocking, and the command is project-local.**
- Evidence: `disk-verified` R6.
- Status: **BUILT**.
- Value×Effort: already paid.
- Confidence: High.
- Next action: run `uv run pytest -q --cov=glm53_core --cov=mcp_server --cov=openai_proxy --cov-branch --cov-fail-under=80` from the project directory before any PR touching the adapter. Not run this unit (read-only) ⇒ current pass/fail is `NOT-CHECKED`.
- Program: harness.

### §2.3 Fabric configuration

**L-10 — Fabric is configured locally with curated, identity-separated context files.**
- Evidence: `.config\fabric\fabric-local-guide_2026-08-29.md` (re-read): version/binary/config root, default vendor+model, pattern and strategy counts, verified commands, and the two curated context files `miky-core.md` / `andrei-core.md`.
- Status: **BUILT**, guide `disk-verified` as a document; the behaviours it records are `lens-claimed` (I re-ran no Fabric command).
- Value×Effort: Medium × already paid.
- Confidence: Medium-High.
- Next action: treat the guide as the Fabric entry point and keep the two context files as the *only* identity surface. Fabric is a **consumer** of `.agents\skills`, never a second prompt SSOT (G-79), and its patterns stay private (G-58).
- Program: harness.

**L-11 — Fabric context compliance is measurable and currently unmeasured.**
- Evidence: `lenses\11-metrics-evals.md` lists "Fabric context compliance" in the metric catalogue; no instrument on disk.
- Status: **PLANNED**.
- Value×Effort: Medium × Low.
- Confidence: Medium.
- Next action: once the event contract exists (A5), emit one event per Fabric invocation recording which context file was loaded. Until then the honest report is `NOT-CHECKED`, not "compliant".
- Program: harness.

**L-12 — Fabric's shared-harness limitation is real and should not be papered over.**
- Evidence: `fabric-local-guide_2026-08-29.md` ("shared harness limitations" section); `AGENTS.md` universal-harness-share rule.
- Status: **BUILT constraint**.
- Value×Effort: n/a (constraint).
- Confidence: Medium.
- Next action: when Fabric cannot see a skill the other runtimes can, resolve it by pointer/cherry-pick from the vault — never by forking a diverged copy into Fabric's own tree (that violates the one-SSOT rule and is how skill vault drift starts, see L-24).
- Program: harness.

### §2.4 Unified session analytics / AgentsView

**L-13 — The archive design is settled and is the highest-value unbuilt item in the estate.**
- Evidence: `lenses\05-session-intelligence.md`: local SQLite + FTS5 archive, DuckDB mirror for analytics, content-free metric layer, `ccusage` for cost reconciliation, `txcript` for transcript format/continuation handling.
- Status: **PLANNED**, `lens-claimed`. Nothing on disk.
- Value×Effort: High × Medium-High.
- Confidence: Medium-High on value, Medium on effort.
- Next action: build in the order the data boundary demands — (1) ingest to local SQLite from the JSONL transcripts already on disk, (2) FTS5 index, (3) content-free metric views, (4) DuckDB mirror only when a query actually needs it. **On-demand only, no daemon.** Reconcile cost against `ccusage` rather than inventing a cost model.
- Program: separate program — *Session Intelligence* (shares the event contract with harness metrics, but its storage, privacy surface and lifecycle are distinct).

**L-14 — Four data boundaries must be fixed *before* the first row is written.**
- Evidence: `lenses\05-session-intelligence.md` (canonical evidence / local storage / egress / learning), reinforced by `lenses\10-security-privacy.md`.
- Status: **PLANNED** (design), **SSOT** (the egress ban).
- Value×Effort: High × Low.
- Confidence: High.
- Next action: write the boundary contract as a short header in the schema file: raw transcripts are canonical evidence and stay local; analytics views are content-free; **no egress** (no Langfuse, no hosted trace sink, no cloud memory sync — G-82); "learning" outputs go to basic-memory via `write_note`, never a parallel store.
- Program: separate program — *Session Intelligence*.

**L-15 — The session catalogue is itself a privacy index.**
- Evidence: `lenses\10-security-privacy.md` ("session catalog as privacy index", cross-project/person linkage).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × Low.
- Confidence: Medium-High — the argument is structural.
- Next action: even a content-free catalogue links projects, identities and times; treat the catalogue's own access as sensitive, and keep Andrei/Marius rows separable at the schema level from day one (see L-27) rather than retrofitting a filter later.
- Program: separate program — *Session Intelligence*.

**L-16 — Secret scanning belongs on the ingest path.**
- Evidence: `lenses\05-session-intelligence.md` (AgentsView, Gitleaks, Presidio) and `lenses\10-security-privacy.md` (raw transcript handling).
- Status: **TRIAL** (tool choice), **ADOPT** (the requirement).
- Value×Effort: High × Medium.
- Confidence: Medium.
- Next action: scan on ingest and record *findings as pointers*, not copies. If a secret is found: report blast radius, **do not rotate** (NEVER-ROTATE is absolute and overrides every scanner's own remediation advice).
- Program: separate program — *Session Intelligence*.

### §2.5 People Analytics — blockers and the safe architecture

**L-17 — People Analytics is blocked on legal/privacy grounds, not technical ones.**
- Evidence: `lenses\06-people-analytics.md` (34 KB, the largest lens after memory): GDPR and AI Act exposure, small-group suppression, surveillance framing, aggregate re-identification.
- Status: **PLANNED-BLOCKED**, `lens-claimed`.
- Value×Effort: High × High.
- Confidence: Medium-High that the blockers are real; Low that they can be cleared by an agent unilaterally.
- Next action: do **not** start with a pipeline. Start with a written purpose limitation and a legal basis per metric; anything without both stays unbuilt. The blocker is a decision the owner must make, and an agent building ahead of it is building a surveillance tool by accident.
- Program: separate program — *People Analytics* (explicitly **not** harness, explicitly **not** Databricks).

**L-18 — The safe architecture is: domain router → versioned metric contracts → policy gates → least-privilege read.**
- Evidence: `lenses\06-people-analytics.md`.
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × High.
- Confidence: Medium.
- Next action: if and when L-17 clears, implement in that order and never let a query reach the warehouse except through a versioned contract. Metric families named in the lens: headcount, terminations, attendance, performance, compensation, open positions — compensation and performance are the two that most need small-group suppression and the tightest legal basis.
- Program: separate program — *People Analytics*.

**L-19 — Small-group suppression must be enforced by the contract, not by report authors.**
- Evidence: `lenses\06-people-analytics.md`; `lenses\10-security-privacy.md` (aggregate report re-identification).
- Status: **PLANNED**.
- Value×Effort: High × Low (relative to the rest).
- Confidence: High — re-identification via small cells is a well-established failure, not a speculative one.
- Next action: put the threshold in the metric contract so a suppressed cell cannot be returned by construction, and add a test that asserts a small cell is suppressed. Author discipline is not a control.
- Program: separate program — *People Analytics*.

**L-20 — Looker access must be least-privilege and separate from the agent's own identity.**
- Evidence: `lenses\06-people-analytics.md`.
- Status: **PLANNED**.
- Value×Effort: Medium × Medium.
- Confidence: Medium.
- Next action: scope credentials per metric family; never reuse a broad analyst credential for agent queries. And per NEVER-ROTATE: if an existing credential is over-scoped, the fix is a new narrowly-scoped grant, not rotating the old one.
- Program: separate program — *People Analytics*.

### §2.6 Memory, provenance, and Andrei/Marius separation

**L-21 — The read path needs poison and supersession filters, and supersession must name its successor.**
- Evidence: `lenses\09-memory-provenance.md` (47 KB, largest lens): digest read-path poison/supersession filters, "naming successors in supersession"; `AGENTS.md` memory contract (`superseded_by`, never silent delete); the session digest is marked **UNTRUSTED** by `CLAUDE.md`/`AGENTS.md`.
- Status: **ADOPT (A6)**, partly `SSOT` already.
- Value×Effort: High × Low.
- Confidence: High.
- Next action: whenever a note is superseded, write `superseded_by` **with the successor's identifier** in the same operation. A `superseded_by` with no named successor deletes knowledge while looking like provenance — it removes the old answer and supplies no new one, which is the memory-layer form of silent capability removal.
- Program: harness.

**L-22 — Hash the artifact, not the command.**
- Evidence: `lenses\09-memory-provenance.md` ("artifact hashing vs command hashing"); Databricks `synthesis-acceptance-review.md` (disk-receipt omissions among its blocking defects).
- Status: **ADOPT (A7)**.
- Value×Effort: High × Low.
- Confidence: High — independently supported by the Databricks review's failure mode and by R7 in this unit.
- Next action: a receipt that records the command that was run proves an intention; a receipt that records the resulting file's path, size and hash proves an outcome. Require the latter for every completion claim. `disk-verified` vs `agent-claimed` is exactly this distinction and is already doctrine — the gap is mechanical enforcement, not policy.
- Program: harness (method also owed back to Databricks, see §4).

**L-23 — Taint must propagate: `derived_from` and `taint_dependents`.**
- Evidence: `lenses\09-memory-provenance.md`.
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × Medium.
- Confidence: Medium.
- Next action: when a note is found wrong, marking it superseded is insufficient if downstream notes were derived from it. Record `derived_from` at write time so that a later correction can enumerate dependents and mark them for re-check. Without this, one corrected fact leaves a fan-out of confidently-wrong descendants — which is precisely how R7's class of error would have persisted.
- Program: harness.

**L-24 — Failed `write_note` calls must spool, not vanish.**
- Evidence: `lenses\09-memory-provenance.md` (failed-write spooling); this session's health line reports `spool:0unflushed`, i.e. the spool concept is live in the health surface.
- Status: **PARTLY BUILT**, `lens-claimed` (I did not locate the spool implementation this unit).
- Value×Effort: Medium-High × Low.
- Confidence: Medium.
- Next action: confirm the spool path exists and is drained; if the health counter can only ever read 0 because nothing writes to it, that is a false-green indicator. Verify by inspection, not by trusting the counter — `NOT-CHECKED` until then.
- Program: harness.

**L-25 — Corrections and directives deserve higher importance than ordinary facts, and Romanian corrections must be captured.**
- Evidence: `lenses\09-memory-provenance.md` (importance model for corrections/directives; Romanian corrections in `claude-reflect`).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × Medium.
- Confidence: Medium.
- Next action: weight owner corrections above agent-generated facts in retrieval, and ensure the correction capture path is language-agnostic — a correction given in Romanian is the same signal as one given in English, and dropping it silently trains the wrong behaviour. Ties to the `correction capture` metric in lens 11.
- Program: harness.

**L-26 — Session analytics must be able to reach memory, but only through basic-memory.**
- Evidence: `lenses\09-memory-provenance.md` ("session analytics reaching memory"); G-81.
- Status: **PLANNED**.
- Value×Effort: Medium × Low.
- Confidence: High on the constraint.
- Next action: the archive (L-13) may *write durable conclusions* via basic-memory `write_note`; it may not become a second semantic store, and no second tool may write the vault. A read-only-over-the-vault tool is permissible; anything else must not run.
- Program: separate program — *Session Intelligence*, constrained by harness SSOT.

**L-27 — Andrei/Marius separation is an identity boundary that currently depends on discipline.**
- Evidence: `lenses\09-memory-provenance.md` (identity separation); `lenses\13-user-domain-identity.md` (propagation across Cursor, Fabric, Zotero, Anki, Windows); `fabric-local-guide_2026-08-29.md` (`miky-core.md` / `andrei-core.md` as the two curated contexts, `disk-verified` as documented).
- Status: **PARTLY BUILT** — Fabric has explicit dual contexts; cross-tool propagation is **PLANNED**.
- Value×Effort: High × Medium.
- Confidence: Medium.
- Next action: make profile/domain attribution a **field**, not a convention: stamp every session, note and analytics row with the acting identity, and keep Zotero profile-separated. Two identities sharing one memory surface is a privacy failure that is invisible until it is embarrassing. The archive schema (L-13) is the cheapest place to get this right, because it is not built yet.
- Program: separate program — *Identity & User Domain* (spans harness, Session Intelligence, and personal tooling).

### §2.7 Harness latency, logging, and guard regressions

**L-28 — Two logs hold ~98% of harness log bytes and neither is bounded.** `[ADOPT A1 — top priority]`
- Evidence: `disk-verified` R4 — `cursor-afterfileedit.jsonl` 100,363,036 B (still growing at 00:39 today); `terminal.jsonl` 147,444,707 B; next largest 2.54 MB.
- Status: **OPEN REGRESSION**, `disk-verified`.
- Value×Effort: High × **Very low**.
- Confidence: High — direct measurement, two files, one command.
- Next action: bound both with rotation + a retention cap (size-based, e.g. rotate at 16 MB keeping N generations), and confirm the writer reopens correctly after rotation. This is the cheapest large win available: ~236 MB reclaimed on a volume the resource-guard reports at **99% used**, and it removes a growing per-write cost on a box with 3.7–3.9 GB free RAM. Do **not** solve it by switching the instrument off — that is silent capability removal; rotate and retain.
- Program: harness.

**L-29 — The shell guard has been failing on four contraband strings every day since 28.08.** `[ADOPT A2 — top priority]`
- Evidence: `disk-verified` R3 — `guard-tamper.log`, `TRACER MEL-DEFERRAL` on 28/29/30/31 August, last `2026-08-31T08:30:02`; preceded by `TRACER OK 5/5` on 27.08 09:19.
- Status: **OPEN REGRESSION**, `disk-verified`.
- Value×Effort: **Very high** × Low-Medium.
- Confidence: High — four independent daily runs agree.
- Next action: this is a *security* regression with a known break window (27.08 09:19 → 28.08 08:30) and a known symptom set (`git push --force origin main`, `git reset --hard HEAD~3`, `git clean -fdx`, `cat .env`). Two `DRIFT` events land inside that window — `.codex\rules\default.rules` and `.agents\agents.json` both changed on 28.08 08:15, fifteen minutes before the first failing tracer. Start there. Until it trips again, treat the shell guard as **not** protecting against force-push, hard-reset, clean, or `.env` read, and rely on the explicit `AGENTS.md` prohibitions instead. A guard that logs its own failure and is left running is the definition of a visible degraded mode (L-40) — the failure is that nobody acted on it for four days.
- Program: harness.

**L-30 — Subagent-lifecycle telemetry has been dark since 29.08 16:12.** `[ADOPT A3]`
- Evidence: `disk-verified` R5 — last write 29.08 16:12 while sibling guard logs wrote at 00:42–00:43 today.
- Status: **OPEN REGRESSION**, `disk-verified`.
- Value×Effort: High × Low.
- Confidence: High on the fact; the cause (unwired vs idle) is `NOT-CHECKED`.
- Next action: determine whether the handler is registered and firing. This blocks L-05 and every subagent metric in lens 11, and it interacts badly with the known local pathology that subagents "frequently appear canceled, cut off mid-work, or stalled" — the one instrument that would characterise that is the one that is dark.
- Program: harness.

**L-31 — Cursor hooks double-fire, and observe-mode telemetry has size/redaction/latency defects.**
- Evidence: `lenses\12-harness-optimizer.md` (double-fire, unbounded log, stale flip-gate blocker, MCP validator deny collision, scorer not seeing regressions); `lenses\08-prune-organize.md` (observe-mode logging size/redaction/latency, double hook registration, unwired handlers).
- Status: **OPEN**, `lens-claimed` — except the unbounded-log component, which I upgraded to `disk-verified` as L-28.
- Value×Effort: High × Medium.
- Confidence: Medium — the lenses converge, but convergence between two lenses is not corroboration (see legend). The one component I re-measured turned out to be real and *larger* than described, which raises my prior on the rest without proving it.
- Next action: re-measure double-registration directly (count handler registrations per event) before fixing. The `scorer not seeing regressions` item is the most alarming if true, because it is the mechanism by which L-29 could go four days unactioned.
- Program: harness.

**L-32 — Per-Bash-call Python process count is a latency tax.**
- Evidence: `lenses\08-prune-organize.md` (high Python process count per Bash call); corroborated circumstantially by this unit's own shell timings (2.8–10.1 s for trivial PowerShell probes).
- Status: **OPEN**, `lens-claimed`.
- Value×Effort: Medium-High × Medium.
- Confidence: Medium.
- Next action: count hook interpreter launches per shell call and consolidate where multiple hooks each pay full interpreter startup. On a RAM-starved box this is both latency and memory pressure. Deficit Round Robin (T8) is the principled fairness answer once the count is known.
- Program: harness.

**L-33 — Housekeeping backlog: stale docs, backups in live trees, deploy-integrity drift, duplicate and unmerged skills.**
- Evidence: `lenses\08-prune-organize.md`.
- Status: **OPEN**, `lens-claimed`.
- Value×Effort: Medium × Low each, and they are independent — good candidates to clear opportunistically.
- Confidence: Medium.
- Next action: handle in one pass, respecting the rules that bite here: never permanently delete (move to the project's trash); `.claude\skills` and `.codex\skills` are **materialised sync targets** — only sync writes there (G-97/98); skill dedup must not diverge the vault (G-79); and `.agents` keeps its harness-at-root layout locally regardless of the repo's platform layout.
- Program: harness.

### §2.8 Frontier, cross-domain, and wildcard gems

These are the idea-import lenses (01, 02, 03, 15). None is on disk; all are `lens-claimed`. I have grouped them by what they would actually change, because the failure mode with imported techniques is adopting the vocabulary without the mechanism.

**L-34 — Cross-domain safety mechanisms that map onto real, already-observed harness failures.**
- Evidence: `lenses\01-cross-domain.md` (13 findings, tiered 0/1/2).
- Status: **ADOPT** for the two below, **TRIAL** for the rest (T8, T9).
- The two worth adopting as *doctrine text* now, at near-zero effort:
  - **STPA framing for unsafe control actions.** Ask, per control action, what unsafe variant exists. Applied to L-29 it names the exact gap: the guard's unsafe control action is "permit a contraband command" and there was no independent detection of that state — except there was (the tracer), and it was unread. That is the finding.
  - **Separate source quality from claim credibility.** A high-quality lens can carry a low-credibility claim. This document's legend is that principle mechanised, and R7 is the case that justifies it.
  - Also cheap and directly useful: **Key Assumptions Check** (which of this plan's assumptions, if false, changes the conclusion?) and **Safety-II positive-adaptation mining** (record what went *right* under stress, not only failures — currently the estate logs only failures, so every adaptation that worked is invisible).
- Value×Effort: High × Very low (doctrine) / Medium × Medium (T8, T9 mechanisms).
- Confidence: Medium-High for the framings, Medium for the control-theory imports (anti-windup for saturated executors, bumpless transfer for model/agent handoffs) — those need a real saturation event to tune against.
- Next action: fold the four framings into the acceptance-review / claim-verify template (A8) as questions, not prose. Leave T8/T9 in TRIAL with a named trigger.
- Program: harness.

**L-35 — Frontier-harness items: adopt the two that are measurement, trial the rest.**
- Evidence: `lenses\02-frontier-harness.md` (10 findings, ADOPT/TRIAL/BORROW/ENABLE).
- Status: mixed.
- The measurement-shaped ones (**ADOPT**): attributable-evidence gates (HarnessLens shape) and failure attribution over traces (TraceElephant shape). Both are versions of A7 — they only work if there is an event contract (A5) and an archive (L-13) underneath, which is why L-13 outranks them.
- The capability-shaped ones (**TRIAL**): boundary-local compaction evaluation (TRACE), environment-memory evaluation (LongMemEval-V2 shape), cascade drills (OrchestraBench shape), difficulty-diversity coreset for eval sets (T10), per-agent prompt-cache TTL, native hook telemetry.
- The one with a hard dependency: **session constraint sidecars (COMPINT)** — attractive, but a sidecar must not become an always-on daemon; scope it to session lifetime or drop it.
- Value×Effort: High × Medium-High collectively.
- Confidence: Medium.
- Next action: do not start any of these before A5. An eval harness without a denominator registry produces numbers that cannot be compared across weeks.
- Program: harness.

**L-36 — Competitive teardown: three concrete borrowings.**
- Evidence: `lenses\03-competitive-teardown.md`.
- Status: **TRIAL** (T6, T7) + **ADOPT** (the two below).
- **ADOPT — explicit execution-environment contract** (OpenHands Workspace shape): state, per task, what environment the work runs in. This estate has repeatedly been burned by the opposite — the media-studio coverage command pinned into `CLAUDE.md` and dead at `~` is the canonical example, and R6 is the corrected form.
- **ADOPT — executable runtime discovery** (`grok inspect --json` shape) and **`roll-call` connectivity tests** (Kilo Code shape): ask the runtime what it has rather than asserting it from memory. R1/R2 in this unit are exactly this, done by hand; the lesson is that it should be a command.
- **TRIAL** — branchable two-plane checkpoints (T6), compact codebase map (T7), native asynchronous hooks, ACP registry/UI.
- Value×Effort: High × Low for the two ADOPTs.
- Confidence: Medium-High — I validated the discovery pattern's value empirically this unit (R7 was caught by it).
- Next action: write a `roll-call` that enumerates MCP servers, their reachability, and their actual per-runtime exposure — and have it print the `targets`-vs-Cursor-mirror distinction from L-08 so that trap is closed by tooling rather than by a note.
- Program: harness.

**L-37 — Wildcard gems: five mechanisms, all TRIAL, two with unusually clean fits.**
- Evidence: `lenses\15-wildcard.md`.
- Status: **TRIAL** (T1–T5).
- The two clean fits:
  - **Phi-accrual suspicion for stall detection (T1)** — the estate's documented pathology is subagents that "appear canceled, cut off mid-work, or stalled", compounded by transcript-flush lag. A binary timeout is exactly the wrong instrument for that (it fires on lag); an accrual suspicion level is the right shape, and it composes with the doctrine's 60-second grace window instead of fighting it.
  - **Banker's safe-state admission for RAM (T2)** — the estate already has a hard admission rule of this type (G-26: no `agent worker start` below 8 GB free) and a resource-guard that only *proposes*. Generalising the rule into safe-state admission is a small step from a control that already exists.
  - The other three: metamorphic MCP contracts for fragile tools (T3), generational context tenure (T4), Tall-Man confusable-rejection for agent identities (T5 — cheap and relevant given Andrei/Marius, L-27).
- Value×Effort: T1 High × Medium · T2 High × Low-Medium · T3–T5 Medium × Low-Medium.
- Confidence: Medium.
- Next action: T2 first — it is the smallest change to an existing control and it targets the measured constraint (3.7 GB free). Each trial needs a pre-registered kill criterion (L-39).
- Program: harness.

### §2.9 Governance and metrics

**L-38 — A denominator registry and an additive event contract are the gate on everything measurable.** `[ADOPT A5]`
- Evidence: `lenses\11-metrics-evals.md` (denominator registry; additive event contract with common + event-specific fields; then a 14-item metric catalogue).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: **Very high** × Low-Medium.
- Confidence: High — it is a precondition, and preconditions are the cheapest thing to be right about.
- Next action: define the common event envelope (timestamp, session, identity/profile per L-27, project, event type, provenance tag) plus a registry that names, for each metric, *what its denominator is*. Additive-only: new fields may be added, existing fields never repurposed. The catalogue that then becomes computable: verified completion, false-green rate, goal fidelity, tool terminal coverage, retry burden, failure-to-rescue, hook opportunity/latency, cloud dispatch acceptance, Fabric context compliance, People Analytics workflow quality, evidence coverage, correction capture, cost/latency, memory promotion.
- Program: harness (contract shared with *Session Intelligence*).

**L-39 — Governance: pre-registered, isolated, reversible experiments with named kill criteria.**
- Evidence: `lenses\14-governance.md` (smallest lens, 15.8 KB, and the densest in binding shape).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: High × Low.
- Confidence: Medium-High.
- Next action: every TRIAL in §1 gets, before it starts: a hypothesis, a metric, a kill criterion, and a reversal path. This is the mechanism that stops the estate accumulating half-adopted techniques — which, judging by the PLANNED list, is the actual failure mode in play.
- Program: harness.

**L-40 — Fail-open controls must be visibly degraded, and reviewer independence must be attested.**
- Evidence: `lenses\14-governance.md` (visible degraded mode for fail-open controls; reviewer independence via lineage attestation; disagreement resolved by discriminator; two-axis promotion; consumer-safe deprecation/quarantine; reflexive SLO for the improvement system).
- Status: **PLANNED**, with one component now proven necessary by measurement.
- Value×Effort: High × Low.
- Confidence: High for the degraded-mode component specifically — **L-29 is the proof**: the guard failed open, logged it honestly four times, and nothing surfaced it. Visibility that only reaches a log file is not visibility.
- Next action: any control that can fail open must raise its degraded state into the session surface (the same place the health/digest lines already appear), not merely into a log. Concretely: `guard-tamper.log` containing a `MEL-DEFERRAL` line within the last 24 h should appear in the session health line.
- Program: harness.

**L-41 — Anti-Goodhart controls and a reflexive SLO for the improvement system itself.**
- Evidence: `lenses\11-metrics-evals.md` (anti-Goodhart, subjective evaluation protocol, continuous/weekly/release programmes, acceptance thresholds); `lenses\14-governance.md` (reflexive SLO, budget by active surface area, class-aware lease clocks and rent).
- Status: **PLANNED**, `lens-claimed`.
- Value×Effort: Medium-High × Medium.
- Confidence: Medium.
- Next action: pair every gate metric with a countervailing one (e.g. verified-completion rate against retry burden and cost) so that gaming one is visible in the other. And hold the improvement system to its own SLO: if the gem-hunt produces 40 PLANNED items and 0 built in a fortnight, that is a measured failure of the improvement system, not a backlog.
- Program: harness.

### §2.10 Repeated subagent failure modes, and the corrections

These are the patterns that recur across lenses, the Databricks acceptance review, and this unit's own conduct. I am including my own errors because a failure-mode list that exempts the author is decoration.

**L-42 — Self-certification: an agent declaring its own gate passed.**
- Evidence: Databricks `synthesis-acceptance-review.md` lists self-certification among its **BLOCK**-level defects; `verification-and-convergence-receipt.md` marks its *own* root-artifact row `agent-claimed` and marks convergence `NOT CLAIMED` — the honest form.
- Correction: the orchestrator validates independently; a subagent's "done" is an input, not a verdict. `CLAUDE.md` already states this ("NEVER self-certify"); the Databricks packet is the case study in what happens when the verification layer is authored by the party being verified.
- Program: applies to Databricks **and** harness. This is the single most transferable Databricks lesson.

**L-43 — Command receipts substituted for artifact receipts.**
- Evidence: Databricks `synthesis-acceptance-review.md` (disk-receipt omissions); `lenses\09-memory-provenance.md` (artifact vs command hashing).
- Correction: A7. Exit 0 is not completion; the artifact on disk is completion. `AGENTS.md`: "Completion is an AND-gate: artifact exists on disk (not just exit 0)."
- Program: harness + Databricks.

**L-44 — Single-probe absence claims.**
- Evidence: **this unit, R7** — one probe against the wrong JSON key produced a clean, plausible, entirely false "not registered" finding.
- Correction: corroborate every load-bearing absence with a mechanically independent second check; if you cannot, write `NOT-CHECKED`. Note the asymmetry: presence claims survive a single probe, absence claims do not.
- Program: harness (and every program).

**L-45 — Convergence between agents mistaken for corroboration.**
- Evidence: Databricks `verification-and-convergence-receipt.md` explicitly declining to claim convergence; multiple gem-hunt lenses independently re-deriving the same items from the same underlying reads (the reason §1 exists).
- Correction: two agents agreeing is one piece of evidence if they read the same source. Corroboration requires mechanical independence, not a second opinion.
- Program: harness + Databricks.

**L-46 — Set-semantics and count-reconciliation errors in synthesis.**
- Evidence: Databricks `synthesis-acceptance-review.md` (set semantics among blocking defects); `locus-membership-reconciliation.md` (the corrected form — explicit disjointness and residual-observation accounting).
- Correction: when a synthesis claims "N items across M groups", state whether groups are disjoint and account for residuals explicitly. `locus-membership-reconciliation.md` is a good template and is worth reusing outside Databricks.
- Program: harness + Databricks.

**L-47 — Stale authority: citing a superseded gate, doc, or command as current.**
- Evidence: Databricks `synthesis-acceptance-review.md` (superseded authorities, self-releasing gates, stale red-team phase gates); this unit's STALE table (7 rows, 4 of them `disk-verified` corrections).
- Correction: date every authority you cite and re-read it if the date is older than the last known change to its subject. Self-releasing gates — a gate that clears itself on a timer or on the author's assertion — should be treated as no gate at all.
- Program: harness + Databricks.

**L-48 — Status-header understatement: a document whose headline is milder than its own contents.**
- Evidence: Databricks `synthesis-acceptance-review.md` lists exactly this as a defect.
- Correction: the header must be at least as severe as the worst finding in the body. Applied here: this document's headline finding is **an open security-guard regression, four days unactioned** (L-29), and §3 leads with it.
- Program: harness + Databricks.

**L-49 — Scope drift and out-of-scope edits by subagents.**
- Evidence: `CLAUDE.md` subagent discipline ("STAY within declared file scope"); recurring across lens write-ups.
- Correction: declare the file scope up front and treat a write outside it as a failure even if the write was good. This unit's declared scope was one output file; nothing else was written.
- Program: harness.

**L-50 — Work lost to apparent cancellation, then restarted from zero.**
- Evidence: `AGENTS.md` learned workspace facts — subagents on this box "frequently appear canceled, cut off mid-work, or stalled", compounded by RAM pressure and transcript-flush lag; `disk-verified` R5 shows the instrument that would characterise this is dark.
- Correction: re-verify on-disk/git state before assuming loss, and make work resumable and idempotent — which is why this document was written incrementally through a sentinel rather than in one final write. T1 (phi-accrual) is the principled detector; the 60-second grace window is the interim rule.
- Program: harness.

---

## §3 — Ranked next actions

Ordered by (disk-verified evidence) × (value ÷ effort). The first three are the only items in this document justified by measurement I took myself; everything below them rests on lens claims and should be treated as a hypothesis queue.

| # | Action | Basis | Value×Effort | Program |
|---|---|---|---|---|
**1** | **Repair the shell-guard contraband coverage.** Failing daily on `git push --force origin main`, `git reset --hard HEAD~3`, `git clean -fdx`, `cat .env` since 28.08. Break window 27.08 09:19 → 28.08 08:30; two `DRIFT` events (`.codex\rules\default.rules`, `.agents\agents.json`) sit inside it at 28.08 08:15. | `disk-verified` R3 / L-29 | Very high × Low-Med | harness
**2** | **Bound `cursor-afterfileedit.jsonl` (95.7 MiB, growing) and `terminal.jsonl` (140.6 MiB).** Rotate with a retention cap; verify writer reopen. ~236 MB on a volume at 99%. Rotate — do not disable. | `disk-verified` R4 / L-28 | High × Very low | harness
**3** | **Surface degraded controls into the session health line.** A `MEL-DEFERRAL` in the last 24 h should appear where the digest/health lines already appear. This is the control that would have caught #1 on day one. | `disk-verified` R3 + L-40 | High × Low | harness
**4** | **Re-wire subagent-lifecycle telemetry** (dark since 29.08 16:12); blocks L-05 and every subagent metric. | `disk-verified` R5 / L-30 | High × Low | harness
**5** | **Correct the `glm53-space` label and the `AGENTS.md` server count**, and add the one-line rule that `targets` gates Codex/Claude while Cursor mirrors the Claude surface. | `disk-verified` R1, R2 / L-08 | Med × Very low | harness
**6** | **Define the denominator registry + additive event contract.** Precondition for L-13, L-35, L-38, L-41. Nothing measurable should start before it. | `lens-claimed` / L-38 | Very high × Low-Med | harness
**7** | **Build the session archive** (SQLite → FTS5 → content-free views → DuckDB on demand), with the four data boundaries and identity attribution in the schema from row one. | `lens-claimed` / L-13–L-16, L-27 | High × Med-High | *Session Intelligence*
**8** | **Adopt supersession-with-named-successor and artifact-hash receipts** in the memory write path. | `lens-claimed` / L-21, L-22 | High × Low | harness
**9** | **Fold the claim-discipline rules into the acceptance-review template** as questions: STPA unsafe-control-action, Key Assumptions Check, source-quality ≠ claim-credibility, single-probe-absence, convergence ≠ corroboration, header-severity floor. | Databricks review + R7 / L-42–L-48 | High × Very low | harness (owed back to Databricks)
**10** | **Write a `roll-call`** that enumerates MCP servers, reachability, and true per-runtime exposure. | L-36 | Med-High × Low | harness
**11** | **Pre-register the trials.** T2 (Banker's safe-state admission) first, then T1 (phi-accrual stalls); each with a kill criterion. | L-37, L-39 | High × Low-Med | harness
**12** | **People Analytics: obtain the purpose limitation and per-metric legal basis** before any pipeline work. Blocked on an owner decision, not on effort. | L-17–L-20 | High × High | *People Analytics*

## §4 — Program assignment

| Program | Items | Character |
|---|---|---|
**harness** | L-01–L-12, L-21–L-25, L-28–L-50 | Everything with a control, a guard, a log, a receipt, or a rule. All three disk-verified regressions live here.
**Session Intelligence** (separate) | L-13–L-16, L-26 | Own storage, own privacy surface, own lifecycle. Shares the event contract (L-38) with harness and writes durable conclusions only through basic-memory.
**People Analytics** (separate) | L-17–L-20 | Blocked on legal basis. Deliberately not harness and not Databricks; the surveillance risk is categorically different from anything else here.
**Identity & User Domain** (separate) | L-27, and the identity field in L-13/L-38 | Spans harness, Session Intelligence and personal tooling (Zotero, Anki, Fabric contexts, Windows profiles).
**Databricks** | Method lessons only: L-42–L-48 | Nothing Databricks-internal was imported. The traffic is one-way and methodological: its acceptance review is the best failure-mode catalogue in the estate, and L-42/L-43 flow back to it as corrections.

## §5 — Ban compliance

Checked against the prohibitions in the request and the `estate-locks-2026-08-27` block. Nothing in §3 or §2 recommends:
- **Duplicate/second vector stores** — basic-memory remains the sole semantic writer (L-26 states the constraint explicitly; Mem0/Graphiti/LynxMCP/CORE are in REFUTED).
- **Langfuse or any hosted trace sink** — the archive is local-only, no egress (L-14).
- **OpenRouter MCP or BYOK** — not proposed anywhere; the GLM path is HF's official router via a process-local adapter (L-06, L-07).
- **Always-on daemons** — L-07 keeps the proxy process-local, L-13 specifies on-demand, L-35 puts an explicit lifetime bound on the COMPINT sidecar idea.
- **Credential rotation** — L-16 and L-20 both state the non-rotation form of the remediation explicitly.
- **Silent capability removal** — L-08 (fix the label, keep the tool), L-28 (rotate, don't disable), L-21 (unnamed supersession is memory-layer capability removal).

Also observed: no config or code was changed; the only file written is this one. Ports 8765/8812/8317 untouched. No git operations. No credentials read or printed — R2 shows the registry's `env` as the `${HUGGINGFACE_TOKEN}` placeholder, which is what is on disk.

## §6 — Residual unknowns (`NOT-CHECKED`, not "clear")

1. Cause of the guard-coverage regression (L-29) — the two 28.08 `DRIFT` events are a lead, not a diagnosis.
2. Whether the subagent-lifecycle handler is unwired or merely idle (L-30).
3. Whether the failed-`write_note` spool has a live write path, or whether `spool:0unflushed` can only ever read 0 (L-24).
4. Current pass/fail of the GLM coverage gate — the command and thresholds are `disk-verified`, the run was not performed (L-09).
5. Cursor hook double-registration count (L-31) — lens-claimed, deliberately not upgraded.
6. Statusline budget parsing (`5h:N%`, `wk:N%`) — asserted in SSOT, unverified this unit.
7. Fabric per-command behaviour — the guide was re-read as a document; no Fabric command was run (L-10).
8. Everything in §2.8 — no imported technique was measured against this estate. They are candidates, not findings.
9. Nine unresolved ledger failure loops flagged in this session's health line, including two WU-B items, remain open and were not addressed here.

---

**Document provenance:** 8 disk-verified receipts (R1–R7 plus the lens-file enumeration), taken 01.09.2026 between 00:29 and 00:45 EEST. Everything else is tagged `lens-claimed`, `SSOT` or `NOT-CHECKED`. One receipt (R7) records an error I made and corrected inside this unit; it is left in deliberately, because a synthesis whose author reports no errors is reporting on its own confidence rather than on the estate.

UNIT-COMPLETE: consolidated-learnings-2026-09-01




