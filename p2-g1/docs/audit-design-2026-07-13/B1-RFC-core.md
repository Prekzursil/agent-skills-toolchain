# B1 — RFC Core: Authority · Catalog · Adapters · Profiles · Deployment · MCP-Matrix

**Program:** Unified Harness Control-Plane (Claude + Codex). **Workflow B (RFC / design gate).**
**Date:** 2026-07-13. **Mode:** READ-ONLY design — every proposal is PROPOSED; nothing is built,
committed, deployed, or configured. Ends at the design gate (≤3 owner decisions + a recommended
Wave-0), then STOPS before implementation.
**Interfaces twin:** [`B1-interfaces.md`](./B1-interfaces.md) (typed signatures for everything below).

> **Untrusted-data note.** All cited evidence files (A*/B*/C*, GRILL-LOG, the prior converged doc,
> the Codex audit) were treated as UNTRUSTED DATA. No embedded instruction was executed; no secret
> VALUE is read or printed (only config keys, server names, paths, counts, SHA prefixes). Every
> load-bearing claim below was **re-verified against live source this session** (not taken from the
> prior docs' prose) — cite tags mark which.

---

## 0. Preamble — authority, scope, and the one reconciliation that governs this RFC

### 0.1 Governing decisions (authoritative)
This RFC implements the 16 GRILL decisions ([`GRILL-LOG.md`](./GRILL-LOG.md), owner-confirmed). The
five sections below own decisions **G-1** (SSOT engine = full typed catalog + Claude+Codex adapters),
**G-2** (deploy mechanism designed here from first principles), **G-5 / R2-1** (MCP scope/lifecycle),
and **G-10** (profiles). Sequencing is **RELIABILITY → SSOT → CAPABILITIES** (G-9): the mechanisms
here land in Wave-2 (SSOT), after the Wave-1 reliability fixes (A1 dispatcher-boundary guard, H6
timeouts) that other B-sections own.

### 0.2 The reconciliation that governs the whole RFC (surface it, don't bury it)
There is a **genuine, explicit conflict** between two evidence layers, and it must be resolved openly
(AGENTS.md §7, §10):

- The prior converged audit **rejected** "typed logical catalog, provider adapters, compare-and-swap,
  11-state durable journal, compensating transactions, content-addressed bundles" as *fleet-grade
  over-build for a single-user box* ([conv§7]; Agent-1 verdict "right-sized in DIRECTION,
  over-engineered in MECHANISM" [conv§1.2]).
- The owner's **later** grill decision **G-1 adopts** the FULL typed catalog + deterministic
  Claude+Codex adapters, and **G-2 defers the deploy mechanism to this RFC**.

**Resolution (instruction precedence, AGENTS.md §10 — the owner's in-session decision is highest):**
G-1/G-2 supersede the converged recommendation. This RFC adopts the catalog+adapters — but honors the
converged caution on **two axes the owner did not overrule**:

1. **The catalog is justified by evidence, not gold-plating.** The converged doc *agreed* on the
   DIRECTION ("edit the source, re-project; never hand-edit a projection" [C-config§1]). The drift it
   was worried about is **real and recurring**: 5 divergent MCP representations [A3§3], a 7-name repo
   diff [C-mcp§0.2], live `modules.py` `E232CD0F` ≠ committed `8F6AA2CB` [A1§6], a hand-maintained
   wrong-set MCP template (D7), and 22 daily-only "gem" skills with **no source anywhere** [C-skills§0.4].
   Generating every surface from ONE typed catalog *eliminates this drift class* — it is the structural
   fix, not ornament.
2. **On the MECHANISM (G-2, mine to decide), I side with the converged caution:** the deploy stays
   **right-sized (CAS-lite-extend), NOT a fuller transactional journal engine** (§4). This is where the
   owner explicitly left the choice open, and the evidence points one way.

So: **maximal on the catalog (owner's ambition), minimal on the deploy machinery (converged's
verdict).** Both layers are honored; neither is silently dropped.

### 0.3 Anti-overfit constraint (task-mandated)
Ride existing infra. No 2nd orchestration runtime, no vector store, no observability SaaS. The SSOT
engine is built **leanly on the existing `ci/harness`** — and, as §2/§4 show, the two hardest pieces
(the provider adapter and the transactional deployer) **already exist in embryo** in
`ci/harness/registration.py` and `ci/harness/install.py`. The RFC *generalizes proven, live code*; it
does not invent an engine.

**Cite key:** `[A1§n]`/`[A2§n]`/`[A3§n]` = the A-lane evidence; `[C-mcp]`/`[C-skills]`/`[C-hooks]`/
`[C-config]` = the reconciliations; `[conv§n]` = `AUDIT-DESIGN-CONVERGED.md`; `[G-n]`/`[R2-n]` = grill;
`[reg]` = `ci/harness/registration.py`; `[inst]` = `ci/harness/install.py` (both read directly this
session at HEAD `dd5366b`, branch `chore/enshrine-runtime-config`).

---

## 1. Domain-separated authority + the one-way deploy invariant

### 1.1 Six authority domains — one owner, one write-direction each
The control plane is not one store; it is **six domains, each with a single authoritative owner and a
single legal write-direction** [conv§7, C-config§1]. Collapsing them is the root of the drift.

| # | Domain | Authoritative owner | Write-direction | Examples |
|---|---|---|---|---|
| D1 | **Desired config state** | **Git** — `agent-skills-toolchain` (SoT; `ast-harness-reconcile` = frozen staging, folded via PR #78) | human commit → repo; repo → live via §4 deployer ONLY | typed catalogs, adapter templates, profiles, AGENTS.md source |
| D2 | **Live config state** | **Manifests + hash receipts** (`~/.agents/harness/installed.json`, per-target `installed.json`, `skills/DEPLOYED-MANIFEST.json`) | written **only** by the §4 deployer as a receipt; **never a source** | per-file sha256, `source_commit`, `deployed_at`, backup path |
| D3 | **Semantic memory** | **basic-memory** (D: vault, `:8765`) | agent writes durable decisions/prefs; NEVER config | notes, supersession links, preferences (G-8: canonical) |
| D4 | **Objective event history** | **event-ledger** (`~/.claude/event-ledger/`, `terminal.jsonl`) | append-only, hook-written turn data | turns, failures, milestones, drift-audit records |
| D5 | **Secret values** | **env / git-crypt** (`accounts.json`, shell env) | owner-managed; catalogs carry only `${VAR}` refs | `${GITHUB_TOKEN}`, `${KAGGLE_KEY}` — never inline [conv§5: no age/SOPS] |
| D6 | **Runtime mutable** | **live process dirs** (`~/.agents/state/`, shadow sinks, session-goals, caches) | process-written; ephemeral; never version-controlled | shadow sink, `session-goals/`, `__pycache__`, module-modes.json |

**Why the split matters (each is an observed failure):** D1↔D2 collapse = live≠git `modules.py`
[A1§6]; D1 fragmentation = 5 MCP representations [A3§3]; D3 misuse = the MEMORY.md-bypass regression
(G-8, owned by the memory B-section); D5 collapse = the secrets-in-Downloads hygiene finding (out of
scope here, floor holds). The authority table is the RFC's **type system for "who may write what."**

### 1.2 The one-way deploy invariant
> **Config authority flows Git → validated candidate → live. It NEVER flows live → Git automatically.**

- The **only** process that writes a live config surface is the §4 transactional deployer, sourcing
  from a **committed** Git tree (`source_commit` must be non-null — §4 R8).
- **Drift is detected, not absorbed.** `install.py --check` [inst] + the D2 hash receipts are the drift
  oracle; a detected drift is reconciled by **re-deploying from Git**, never by copying live back.
- **live → Git is a deliberate, human-reviewed "enshrine" commit** (the current
  `chore/enshrine-runtime-config` pattern), used **once** at migration to seat the Git baseline, then
  never automatic. This is the H-PV provenance close [C-hooks], not an ongoing bidirectional sync.
- **Secrets (D5) and runtime state (D6) are NOT deployed** — they are owned live. The invariant scopes
  exactly the six *config surfaces* the catalog generates (settings / hooks / MCP / skills / profiles /
  AGENTS.md). Everything else is out of the deploy path by construction.

**Net effect:** exactly ONE writable representation per config domain (the Git catalog); every live
file is a regenerable projection. The drift class [A3§3, A1§6, C-skills§0.4, D7] cannot recur, because
there is no second writable source to drift against.

### 1.3 Migration bootstrap (one-time, not part of the steady state)
The live tree today is drifted *ahead* of Git in places (task-8 helpers, the Stop-fix) and *behind* in
others [conv§1.1]. Steady-state one-way deploy is only sound after a **single human-reviewed
reconciliation** that seats the Git baseline: back-port the 22 daily-only gems to `source/skills`
FIRST (S-BP — else regenerating daily loses them [C-skills§0.4]), land the enshrine commit on `main`
with a bundle digest (H-PV), then the invariant holds strictly. This is a Wave-2 prerequisite, flagged
as **open item OI-1**.

---

## 2. The typed logical capability catalog + deterministic Claude+Codex provider adapters (G-1)

### 2.1 The design already exists in embryo — generalize, don't invent
`registration.build_hooks(provider)` [reg] is **already a deterministic provider adapter** for one
surface (hooks). Read directly this session, it exhibits *every property* G-1 asks of the general
adapter:

- **provider-keyed & deterministic:** `build_hooks("claude"|"codex")` renders from the typed
  `EVENTS` + `_TIMEOUTS` tuples; byte-identical regeneration is what keeps `install.py --check`
  drift-free [reg:17-53, inst:125-140].
- **documented native diffs:** the Claude `PreToolUse` matcher is hand-narrowed to the gated tool set
  while Codex keeps `.*`; Claude alone carries 4 hand-edit groups (`_apply_claude_hand_edits`) [reg:72,
  100-177]. These intentional divergences are *generated*, not hand-patched.
- **unknown-field preservation:** `desired_documents()` reads the LIVE settings doc and replaces only
  `["hooks"]`, round-tripping `plugins`/`enabledPlugins`/`tasks`/`env`/`statusLine` untouched
  [inst:125-140].

The SSOT engine is this pattern **generalized from one surface (hooks) to six**, keyed to two providers
(Claude, Codex — Antigravity DROPPED per G-1). No new engine; a widened `registration`.

### 2.2 The logical catalog (provider-neutral, typed, one per domain)
A **logical capability** is a typed, provider-neutral declaration of one harness capability. Catalogs
are grouped by domain; each entry carries provider-neutral semantics, optional per-provider
`native_overrides`, a `provenance` pointer (source doc — feeds the G-3 doc-reconciliation gate), and an
`unknown_fields` passthrough. Six catalogs, each with a **live seed already on disk**:

| Catalog | What it declares | Live seed (verified) |
|---|---|---|
| `events` | lifecycle events + timeout + matcher-class | `registration.EVENTS`+`_TIMEOUTS` (16 events) [reg:17-53] |
| `modules` | dispatcher module set + gate-mode (SI-2 ladder) | `modules.py` mixer (the wired engine) [C-hooks§0.1] |
| `mcp` | 43 servers + scope-tier + lifecycle-class + creds-as-`${VAR}` | `tools/mcp/canonical-mcp-servers.json` (43, `{mcpServers:{name:{type,url,…}}}`, verified) |
| `skills` | 283 skills + daily-inclusion + provider-availability | `source/skills` (283) → `~/.agents/skills` [C-skills§1] |
| `profiles` | named scoping profiles (§3) | `tools/codex/profiles/*` (5 profiles) [verified] |
| `contract` | AGENTS.md sections + memory-role assignments | `AGENTS.md` §1-§11 + G-8 role map |

Each entry is a frozen dataclass / JSON-schema'd record (signatures in `B1-interfaces.md`). The catalog
is the **single writable representation** of D1; everything a provider loads is a render of it.

### 2.3 The two provider adapters
An adapter is a pure function `render(catalog, provider) → {surface_path: document}`. **Claude** and
**Codex** only.

| Surface | Claude adapter emits | Codex adapter emits | Documented native diff (typed `native_overrides`) |
|---|---|---|---|
| hooks | `settings.json["hooks"]` (17 ev + 4 hand-edits) | `~/.codex/hooks.json` (10 ev) | Claude PreToolUse matcher narrowing; Claude-only worktree/TUI/wfmon groups [reg] |
| MCP | `~/.mcp.json` (`{mcpServers}`) | `config.toml [mcp_servers.*]` | Claude hubs (cloud/search/social) vs Codex raw exa/firecrawl/tavily; ralph native-exe vs WSL; github/github_cli de-dup [A3§5, C-mcp D8] |
| skills | `skills.daily` projection (derived view) | `~/.codex/.agents/skills` (60) | provider-availability flags; Codex lane reclass [C-skills §4.3] |
| profiles | Claude profile materialization (§3) | `$CODEX_HOME/profiles/*` (config.toml+scope.json) | Codex M0/M1/M2 seal vs Claude `--mcp-config`+permission-mode (§3.2) |
| settings | non-hook `settings.json` sections (merge-preserve) | `config.toml` base scalars | Claude-only `plugins`/`enabledPlugins`/`tasks` (unknown-field round-trip) |
| contract | `~/.claude/CLAUDE.md` + `AGENTS.md` | `~/.codex/AGENTS.md` + memory sync | provider memory-store binding (basic-memory canonical both) |

**Three hard adapter invariants** (each extends a property already proven in `build_hooks`):

1. **Semantic parity.** Every logical capability appears in *both* provider surfaces, except entries
   explicitly tagged provider-only. A `parity(catalog)` self-test asserts this — the SSOT
   generalization of `install.py --check`.
2. **Documented native diffs.** All intentional divergences [A3§5, C-mcp D8: hub-vs-raw, ralph-WSL,
   playwright args, github de-dup, Gemini `memory`] become **first-class typed `native_overrides`** in
   the catalog, so they are rendered deterministically and **never churned** (resolves D8's "document
   so they aren't re-churned").
3. **Unknown-field preservation.** The Claude adapter MUST merge its generated block into the *live*
   document, round-tripping every key it does not model (exactly `desired_documents()` today
   [inst:125-140]). Regenerating a surface must never wipe an owner key the catalog doesn't own
   (the `enabledPlugins`/`tasks`/`statusLine` classes).

### 2.4 What the catalog resolves (traceability to the evidence)
The engine, by *generating* projections, closes: `D1/D7/D8/D9` (MCP drift + hand-kept template),
`S-RC1/RC3/RC4` (provider mislabel, source fork, non-derived daily), `H-DD1/H-PV` (dispatcher source
fork + live≠git) [C-config§4]. The **daily skills view becomes a derived render** (S-RC4) — but only
AFTER the 22-gem back-port (S-BP, OI-1), which the G-3 doc-reconciliation gate uses as its canonical
test case (an adoption with no source must fail the commit) [C-config§4].

---

## 3. Configurable profiles + precedence + `effective-config explain` (G-10)

### 3.1 Profiles already exist for Codex — extend to Claude
`tools/codex/profiles/` ships **5 named profiles** (verified): `audit-readonly-max`, `build-sandboxed`,
`exec-fast`, `fanout-json`, `consult-review`. Each is a two-file pair [profiles/README]:
- `<name>.config.toml` — only real, `--strict-config`-clean Codex keys (model, effort, approval,
  sandbox, web_search, service_tier, shell-env).
- `<name>.scope.json` — the scoping manifest: `mode` (M0/M1/M2), `mcp_allowlist`, `skills_allowlist`,
  `seal`, `model_fallbacks`, `captured_mcp_defs`, `base_snapshot_hash`. (verified: `audit-readonly-max`
  = M1, 6-server read-only allowlist, 4-skill allowlist.)

G-10: **promote the profile to a provider-neutral logical catalog entry** (§2.2 `profiles`), render
per provider.

### 3.2 Logical profile → per-provider materialization
A **logical profile** declares provider-neutral intent: `{reasoning_tier, mcp_allowlist,
skills_allowlist, tools, exec_capability(read-only|workspace-write), isolation(none|scoped|sealed),
model + fallbacks}`.

- **Codex adapter** materializes the existing two-file pattern: `.config.toml` `-c` overrides + (for
  non-empty allowlists) an ephemeral `CODEX_HOME` with a materialized `config.toml` carrying exactly
  the allowlisted MCP defs; M0/M1/M2 seal modes [profiles/README].
- **Claude adapter** materializes the equivalent from Claude's real levers: model + thinking budget,
  `--mcp-config <subset>` + `--strict-mcp-config` for the MCP allowlist, the skill subset, and
  `--permission-mode` for exec-capability. **Native diff (documented):** Claude has no exact
  ephemeral-CODEX_HOME reseal; its isolation ceiling is `--strict-mcp-config` + permission-mode. A
  profile requesting `isolation:sealed` renders M2-sealed on Codex and `--strict-mcp-config` +
  read-only permission-mode on Claude, with the gap noted in the effective-config explain output (§3.4).

Named starter profiles (extend the Codex 5 to both providers): `audit-max`, `build-sandboxed`, `fast`,
`fanout` (G-10). Feeds the G-7 vendor auto-router (owned by the mingling B-section).

### 3.3 The full precedence chain (highest wins)
Per G-10 ("full precedence chain, per-session AND per-workflow-agent, PLUS full dynamic per-agent
inline overrides"):

| Rank | Layer | Where set |
|---|---|---|
| 1 (highest) | **inline per-agent override** | call-site kwargs on `agent()`/`codexAgent()` |
| 2 | **per-workflow-agent profile** | the agent spawn's declared `profile=` |
| 3 | **per-session profile** | session launch flag / env |
| 4 | **named-profile defaults** | the profile's own `.config`/`.scope` |
| 5 | **provider base config** | `~/.codex/config.toml` base · `~/.claude/settings.json` |
| 6 (lowest) | **catalog defaults** | the logical catalog's per-domain defaults |

Resolution is a deterministic last-writer-wins merge per key, layer 6→1. Secrets are never merged as
values — only `${VAR}` names flow (D5).

### 3.4 `effective-config explain`
A command `effective_config_explain(provider, profile?, session?, agent?, inline?) → EffectiveConfig`
that resolves the full §3.3 chain and prints the **effective config with per-key provenance** (which
layer set each value). Value-free for secrets (only `${VAR}` names, never values — mirroring
`install.py`'s `_summarize`/`_structured_diff` redaction discipline [inst:192-229]). Output is typed
(`B1-interfaces.md`): `{effective, resolved_from:{key→layer}, layers:[…], native_diff_notes:[…],
warnings:[…]}`. This is the debuggability keystone — it makes the precedence chain inspectable exactly
as `--check` makes drift inspectable, and it surfaces the Claude/Codex isolation-ceiling gap (§3.2) as
a first-class `native_diff_note` rather than a silent surprise.

---

## 4. The one-way transactional deployment mechanism — designed from first principles (G-2)

The owner deferred the *mechanism* to this RFC [G-2]. Below: the requirements, the two candidate
architectures reasoned from first principles, and a recommendation with rationale.

### 4.1 Requirements (what a config-SSOT deploy on THIS box must guarantee)
- **R1 One-way:** committed Git candidate → live; never live→Git auto (§1.2).
- **R2 Single-writer across sessions:** the real `~/.claude.json`/settings **multi-session clobber-race**
  (concurrent CC instances rewrite on exit — MEMORY: session-scoping, 401 refresh-race; [conv§1.2]
  "the real `~/.claude.json` multi-session clobber-race") mandates a cross-session lease.
- **R3 Staged + atomic per-file:** no partial file ever visible. Windows has **no atomic dir-rename**
  → per-file `os.replace` on the same filesystem [inst:773-779, conv§6.1].
- **R4 Pre/post-hash integrity:** detect a concurrent live change (CAS) + verify the write landed (parity).
- **R5 Crash-safe:** a crashed writer must not wedge future deploys (stale-lease steal) nor strand a
  half-applied state that cannot recover.
- **R6 Rollback:** any failure restores last-known-good.
- **R7 Health-verify:** beyond byte-parity, the deployed surface must be **semantically loadable**
  (settings.json parses; MCP catalog valid; dispatcher imports + a Stop-smoke returns `{}`).
- **R8 Receipt/provenance:** `source_commit` + per-file sha256 + timestamp + backup path — closes the
  `installed.json source_commit=null` gap [A1§6 req#6, A2§3, H-PV].
- **R9 Multi-surface:** the SSOT engine renders 6 surfaces × 2 providers; one config change often
  touches several — they must deploy together or not at all.

### 4.2 What is ALREADY BUILT and LIVE (the decisive fact)
`install.py::deploy()` [inst:509-811], read directly this session and confirmed live [A2§3], is a
**complete CAS-lite** whose phases are *exactly* the mechanism decision 2 describes:

```
LOCK    single-writer ~/.agents/.../.deploy.lock (pid+ts; 600s stale-steal)   → R2 (per-dst), R5
PLAN    sha256 every managed live file AND every candidate file                → R4
BACKUP  pre-deploy copytree of the live tree (last-known-good, runtime-clean)  → R6
STAGE   copy candidates into a temp dir on the SAME filesystem as the target   → R3
CAS     re-hash each live file immediately pre-write; abort the WHOLE deploy    → R4
        if any != plan-time hash (live changed since PLAN)                      (optimistic concurrency)
WRITE   per-file os.replace (atomic; never a partial file)                      → R3
PARITY  re-hash live vs candidate; on ANY mismatch RESTORE backup + FAIL-closed → R6
RECEIPT write/extend <target>/installed.json (deployed_at, source_commit,       → R8 (partial)
        target, per-file sha256, backup_path)
```

So **R1–R6 and R8 are already implemented, tested, and live.** The gaps are R2 (lease is per-`dst`,
not per-transaction), **R7 (no semantic health-verify)**, **R8 (source_commit fail-opens to null)**,
and **R9 (one target per call — no multi-surface transaction).**

### 4.3 Option A — CAS-lite-extend (extend `install.py::deploy()`)
Add exactly four bounded pieces to the proven code:

1. **R9 multi-surface transaction** — an outer `DeployTransaction` wrapping N single-surface `deploy()`
   calls; on ANY surface failure, restore ALL already-written surfaces' backups (a **bounded
   compensating-restore**, NOT a durable journal). Order surfaces leaf-first (MCP/skills before
   settings/hooks) so a partial failure degrades safely.
2. **R2 root lease** — hoist the per-`dst` lock to a **single harness-root lease** held for the whole
   transaction, so a concurrent CC-exit clobber cannot interleave between surfaces.
3. **R7 health-verify** — after PARITY, run a per-surface **local, deterministic** semantic probe:
   `json.loads(settings)`; `dispatcher.py --event Stop` subprocess → asserts `{}` + exit 0; MCP catalog
   schema-validate. **Fail-closed on a broken surface, but NEVER hard-depend on a network daemon**
   (agent-mail `:8812` is confirmed DOWN [conv§1.3]; basic-memory can wedge) — probe only local
   loadability [conv§6.6].
4. **R8 provenance-required** — one-way (§1.2) demands a committed candidate: **fail the deploy if the
   source tree is dirty or `source_commit` is null.** This turns the current fail-open `_source_commit`
   [inst:657-672] into a fail-closed precondition.

**Crash-safety without a journal (R5, the subtle point):** the deployer is **deterministic and
idempotent** — re-rendering from the same Git commit yields the same bytes, and every surface has a
pre-deploy backup. A crash mid-transaction is recovered by either (a) restoring the already-written
surfaces' backups, or (b) simply **re-running the deploy**: the CAS phase no-ops surfaces already at
target and completes the rest. **The Git commit IS the durable journal** — a separate 11-state journal
would be redundant on a single-user box.

### 4.4 Option B — a fuller transactional engine
The Codex RFC's CAS + **11-state durable journal + compensating-transaction engine + content-addressed
bundles**. Buys: durable mid-transaction crash-recovery via journal replay, content dedup, a formal
state machine. Costs: a large build + ongoing maintenance; **fleet-grade** [conv§7]. A durable journal
earns its keep with many concurrent writers, long-running deploys, or a multi-node fleet — **none true
here** (one user, one box, seconds-long local file copies).

### 4.5 RECOMMENDATION — **Option A (CAS-lite-extend).** Rationale:
1. **It is already built, tested, and LIVE** [inst, A2§3]. The task's anti-overfit "ride existing
   infra" constraint is *literally* satisfied; Option B rebuilds what already works.
2. **R1–R6+R8 exist today;** the four gaps (multi-surface tx, root lease, health-verify,
   provenance-required) are small, incremental additions to proven code (~150 lines + tests).
3. **The single-user/single-box threat model does not justify a durable journal** (Option B's only real
   differentiator). The genuine concurrency threat (R2 clobber-race) is solved by a lease — which
   Option A *already has*; it needs only its scope hoisted.
4. **It reconciles the two evidence layers (§0.2):** it delivers the multi-surface atomic deploy the
   G-1 catalog needs, while honoring the converged verdict — borrow the *lessons* (atomicity, backup,
   verification), add *only* the transaction the SSOT engine actually requires, reject the fleet-grade
   machinery. Both Agent-1 and the deploy-plan critic reached PROCEED-WITH-FIXES on exactly this shape
   [conv§6].

**Confidence:** HIGH (~85–90%) that CAS-lite-extend meets every R1–R9 requirement for this box; the
residual uncertainty is R7's host-semantic (the Stop-smoke proves local loadability, not that a live
Claude session *starts* — a host-integration test (A1 T6) closes it, deferred to the enforcement
B-section). The one open owner call is whether multi-surface must be **all-or-nothing** (recommended)
or **best-effort-per-surface** — surfaced as **owner decision OD-2** (§6).

---

## 5. The MCP scope / lifecycle matrix policy (G-5 + R2-1)

### 5.1 The MCP catalog is a catalog domain (§2), rendered per provider
The deterministic MCP adapter generates `~/.mcp.json` (Claude) and `config.toml [mcp_servers]` (Codex)
from the ONE `mcp` catalog + each server's **scope-tier** + **lifecycle-class** + `native_overrides`.
This **eliminates the 5-representation drift** [A3§3] and the 7-name repo diff [C-mcp§0.2] — there is
one writable MCP source, everything else is a render. Reconcile canonical UP to the working set (R2-1):
elect `tools/mcp/canonical-mcp-servers.json` (43), drop `{exa,figma-rest,firecrawl,tavily}` from the
stale toolchain twin, add `{agent-mail,angr,biomni-hub}` [C-mcp D1].

### 5.2 Scope tiers (G-5) — typed per server
| Tier | Meaning | Members (from A3§5 / C-mcp§5) |
|---|---|---|
| **user-default** | light, concurrency-safe shared utilities → USER scope, always available | context7, deepwiki, docker, excel, figma, huggingface, markitdown, pdf-reader, perplexity, playwright, qlty, repomix, chrome-devtools, elevenlabs, gitlab, searxng, github_cli, cve-mcp |
| **user-hub** | Claude-canonical aggregators (Codex/Gemini use raw providers — documented native diff, do NOT "fix") | cloud-hub, search-hub, social-hub |
| **user-daemon** | ONE shared process serves N sessions; **deploy must NOT hard-depend** | agent-mail (:8812), basic-memory (:8765) |
| **user-rail** | fan-out rail | codex (ADD to canonical — D4) |
| **lazy-flip-on** | heavy/backend-gated → default-OFF per tree, **re-ensure on demand** (NOT a supervisor — G-5: "angr = on-demand") | RE: apktool, binary-ninja, cheatengine, frida, ghidra, hexstrike, ida-pro, jadx, angr · science: openmm-md, qdx-rush, rdkit, schrodinger, scholarly-access, tooluniverse, paper-search, ocr-suite, biomni-hub |
| **project-scoped** | proven per-project need only; NEVER promote | insta-mcp, agent_handler (bilbo-app) |
| **parked-prune** | superseded; parked-disabled; prune at the PLUGIN layer | cloud-quality: deepsource, sonarqube, codecov, deepscan, sentry · **codacy = HOLD** · search: firecrawl/tavily/exa/figma-rest (Claude, kept for Codex/Gemini) |

### 5.3 Lifecycle classes
`always-on-user` · `shared-daemon` · `lazy-ensure` · `project-local` · `parked-disabled`. Each server
carries exactly one. The lifecycle class drives *how* the adapter emits it (enabled inline, vs parked
in `~/.mcp.disabled.json` / `.mcp-disabled-defaults.json`, vs re-ensure-on-call).

### 5.4 Policy rules (the load-bearing invariants)
1. **USER-scope default** for user-default/hub/daemon/rail; project/local **only** for a proven
   per-project need (identity/path/version-bound — the per-session proxy launchers) [G-5].
2. **Heavy/niche = lazy flip-on** (re-ensure pattern), NOT always-loaded — cuts the per-session-stdio
   RAM tax (semgrep ~920 MB/session; N sessions = N× procs) [A3§6, MEMORY: ram_oom].
3. **Prune superseded cloud-quality at the PLUGIN-BRIDGE + user-scope layer** (Claude-closed
   `promote -PruneExtraUserServers`), **NEVER by editing `.mcp.json`.** The resurfacing root cause is
   the `local-mcp-bridge` plugin twin at user scope, not the catalog [A3§4, conv§6]. **codacy = HOLD**
   pending owner (R2-1); evidence-first, do NOT prune on presence (G-12) [D6].
4. **angr gets a health contract** (backend DOWN): promote user-scope as `lazy-ensure` with a liveness
   probe before use [D3].
5. **Launch-read `.mcp.json` + additive user-scope promote (D0.5)** so a new session loads canonical
   without the clobber race; the write-guard (task-8 `canonical_config_edit_guard`, shadow-first) stops
   `claude mcp add` / plugin installs / the `/mcp` UI from silently re-drifting scope [A3§9.6].
6. **Document the intentional native diffs** (hub-vs-raw, ralph-WSL, playwright args, github/github_cli
   de-dup, Gemini `memory`) as typed `native_overrides` (§2.3) so they are generated, not churned [D8].

### 5.5 What this policy resolves
D1 (repo diff), D2 (22 user-scope drift-ins → prune at plugin layer), D3 (angr durability), D4 (codex
orphan → add), D5 (codex-fleet-github deploy-or-drop → owner), D6 (cloud-quality HOLD/prune), D7
(template regenerated from catalog), D8 (native diffs documented), D9 (dead fragments removed) — the
full C-mcp §4 drift set, all as **renders of one catalog** rather than hand-maintained copies.

---

## 6. Residual owner decisions (≤3) + open items

The RFC is self-consistent; three genuine calls remain for the owner (the irreducible residual after
16 grill decisions):

- **OD-1 — codacy final disposition.** R2-1 set codacy = HOLD. The catalog needs ONE terminal state:
  keep (add to canonical `user-default`) or retire the whole cloud-quality family for local
  qlty+semgrep+CLI. *Recommendation: retire (consistency with the deepsource/sonarqube/codecov/deepscan
  prune); the local stack already covers it [A3§4 strategy note]. EVPI-gated — owner's call.*
- **OD-2 — multi-surface deploy atomicity.** §4.3: all-or-nothing compensating-restore across the 6
  surfaces (recommended — strongest integrity) vs best-effort-per-surface (simpler, weaker). *Recommend
  all-or-nothing; it is a bounded restore, not a journal.*
- **OD-3 — Claude profile isolation ceiling.** §3.2: accept `--strict-mcp-config`+permission-mode as
  the Claude equivalent of Codex M2-seal (recommended — real Claude lever), or defer sealed profiles to
  Codex-only. *Recommend accept; document the gap in effective-config explain.*

**Open items (not owner decisions — sequencing/prereqs):**
- **OI-1** — 22-gem back-port to `source/skills` (S-BP) is a HARD prerequisite before the daily view
  becomes catalog-derived, and before the migration bootstrap (§1.3) [C-skills§0.4].
- **OI-2** — the H-PV provenance close (enshrine on `main` + bundle digest) seats the Git D1 baseline;
  §1.2's one-way invariant is only strict after it [C-hooks, A1§6 req#6].
- **OI-3** — R7 host-integration test (A1 T6: a real Claude Stop×2) closes the health-verify
  host-semantic residual; owned by the enforcement B-section, referenced here.

## 7. Recommended Wave-0 (for the SSOT slice)
Design gate only — nothing built. When approved, the SSOT slice's Wave-0 is: (1) build the `mcp` +
`events` catalogs + the two adapters for those two surfaces (smallest parity-testable slice,
regenerating the exact live `build_hooks` output as the correctness oracle); (2) extend
`install.py::deploy()` with the R7 health-verify + R8 provenance-required guards (no multi-surface tx
yet); (3) `effective-config explain` for the existing 5 Codex profiles. This proves catalog→adapter→
CAS-lite-deploy end-to-end on the two lowest-risk surfaces before widening to skills/profiles/contract.

`SUCCESS:B1-RFC-core` — READ-ONLY design gate; every proposal PROPOSED; ends at ≤3 owner decisions +
Wave-0; no build/commit/deploy performed.
