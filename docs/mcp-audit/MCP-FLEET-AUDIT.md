---
title: MCP-FLEET-AUDIT
type: note
permalink: dqverify-repo-20261013/docs/mcp-audit/mcp-fleet-audit
---

# MCP Fleet Audit — GROUNDING lane (MCPRESEARCH)

Measured 2026-08-12 on this box, worktree `C:/Users/Prekzursil/source/ast-integrate` @ `ae8205a4`.

COVERAGE: §1 prior art MEASURED (read + executed, not surveyed) · §2 inventory MEASURED
(mcpctl executed) · §3 liveness/capability MEASURED across 4 independent signals · §4 cost
PARTIAL — one server probed end-to-end executably, the rest inherited from `mcpapply/impact.py`
and tagged · §5 duplication MEASURED for the exact-name case, INFERRED for the semantic case
(tagged inline) · §6 resource MEASURED with a passing both-states detector control · §7 security
MEASURED from `mcpctl credentials` name-only output. No production code written. No config
changed. No credential read, printed, or modified.

> **ROUND 1 BUILD LANDED — read [`MCP-CAPABILITY-AND-DISPOSITION.md`](MCP-CAPABILITY-AND-DISPOSITION.md)
> alongside this.** The gap named in §0 is now produced: 21 of 23 mounted servers carry a
> real-call verdict (was 2), per-server context cost is measured — **RESIDENT cost now for
> every one of the 23 mounted rows: 861 tools, 14,132 B**, of which 707 tools / 11,645 B is
> the **16 SAMPLED rows of 23** that also carry a `schema_bytes` figure, so the CONTINGENT
> total (603,233 B, same 16 SAMPLED rows) is still a lower bound — and every mounted row has
> a reversible KEEP/DISABLE/INVESTIGATE disposition with evidence.
>
> > **SUPERSEDED BY MEASUREMENT in round 4, kept rather than deleted.** This read *"per-server
> > context cost is measured for 707 tools over the 16 SAMPLED rows of 23 … a lower bound on
> > the fleet, never a fleet total; the other 7 are HTTP transports with no stdio child to
> > enumerate, and unmeasured is not zero"*. Every word of that was true and correctly scoped
> > — it is **not** retracted. What changed is that its residual got closed: the 7 rows have
> > no *stdio* child, but the client connects to them over HTTP and lists their tools, so
> > round 4 measured them from the client's own deferred-tool listing (154 tools, 2,487 B) and
> > the fleet RESIDENT denominator stopped being unmeasured. The CONTINGENT half is unchanged
> > and still a lower bound, because a deferred-schema client never materialises those
> > schemas. Producer: `command-center/mcp-audit/unsampled_surface.py`. Three claims here are **refined** by that measurement, in this file's favour:
> `cloud-hub = 424` reproduced independently, `chrome-devtools = 29` now has a third
> corroborating method, and the `searxng` ⊂ `search-hub` containment is confirmed by computed
> set arithmetic. One is **narrowed**: `playwright*` share not merely similar names but
> *byte-identical* 24-tool name sets — and are still correctly NOT retirement-eligible.
> Note: this file's `_probe_*.py` scripts were `ruff format`-ed by the build lane to clear the
> repo-wide format gate (9 files, behaviour unchanged and re-executed to prove it), so the
> `sha256:db3ac6964aa3` hook-notice id in `AUDIT-SUMMARY.json` refers to pre-format bytes. It
> did not match the file's digest before the reformat either (`ff01002d…`), so no byte link
> was lost.

---

## 0. Headline for the BUILD lane

**Do not build an MCP audit tool. Five of the six axes already ship in this repo, tested.**
The single genuine gap is a **liveness/capability producer**, and even its primitive already
exists — it just was never wired to the consumer that has four empty sockets waiting for it.

```
tools/mcp/mcp-http-host/mcp_http_host.py :: StdioChild   ── produces ──▶  tool_count, pid, last_error
tools/mcpctl/mcpctl/matrix.py            :: Row          ── consumes ──▶  tool_count, pid, last_error, rss_bytes
                                                                          (currently null in 145/145 rows)
```

Executable proof that the wiring is feasible, run today:

```
$ python smoke_stdio.py C:\Python314\python.exe ...\cloud-hub\hub.py
INIT_SERVERINFO: {"name": "cloud-hub", "version": "0.1.0"}
CHILD_PID: 56976
TOOLS_COUNT: 424
ELAPSED_MS: 1862
```

A real `initialize` + `tools/list` handshake, 1.9 s, returning exactly the fields mcpctl
injects. The build is a **wiring job plus a cache**, not a new tool.

---

## 1. Prior art — what already exists (all read, several executed)

| Axis | Artifact | State | Verdict |
|---|---|---|---|
| INVENTORY + scope + precedence | `tools/mcpctl/` | 21 modules, 100% line+branch, 17-mutation probe, read-only enforced over the AST | **DONE — reuse** |
| MUTATION (disable/enable) | `tools/mcpapply/` | dry-run default, backup-before-write, `guard.py` fail-closed, loopback GUI | **DONE — reuse** |
| COST (tokens/RAM) | `tools/mcpapply/mcpapply/impact.py` | two anti-correlated axes, `TokenBasis` provenance enum, never renders unmeasured as 0 | **DONE — but constants stale, see §4** |
| RESOURCE census | `docs/mcp-consolidation-plan.md` §1 | 336 procs / 13.24 GB, measured 2026-07-24 | **DONE — re-measured, see §6** |
| RESOURCE cure | `tools/mcp/mcp-http-host/` + `mcp-host-supervisor` | mcp-proxy supervision, shared HTTP, port-scoped reap | **BUILT** |
| SECURITY | `tools/mcpctl/mcpctl/safety.py` | credential **name**-only by construction; strip-controls-then-match ordering pinned by 20/20 mutation rows | **DONE — reuse** |
| Cockpit pane | `tools/monitorcore/monitorcore/mcp_source.py` | mirrors mcpctl's scope table; explicitly leaves liveness `None` | **DONE — the second consumer of the gap** |
| GUI / cross-plane | `tools/mcp-manager/` | 4 planes, resolves to a single `enabled: bool`, no redaction layer | superseded by mcpctl for reads |
| **LIVENESS / CAPABILITY** | — | `tool_count`/`pid`/`rss_bytes`/`last_error` null in **145/145** mcpctl rows | **THE GAP** |

`mcpctl/README.md` already documents why it does not extend `mcp-manager`, and
`mcp_source.py` documents why it cannot import `mcpctl`. Both boundaries are deliberate and
argued; do not re-litigate them.

---

## 2. Inventory — measured

`python -m mcpctl matrix --json` → `command-center/mcp-audit/mcpctl-matrix.json`, 145 rows.

```
total 145 | enabled 16 | disabled 118 | denied 5 | pending-approval 3 | undefined 3
with_conflicts 93 | credential_bearing 8
transport: stdio 58 | http 11 | unknown 76
definition scopes: claude-user 66 · mcp-json 14
verdict scopes:    settings-denied 5 · claude-project-disabled 0 · claude-user-disabled 122
                   · mcpjson-approved 12 · loadout-template 85 [ADVISORY]
precedence: settings-denied > claude-project-disabled > claude-user-disabled > mcpjson-approved
```

Five source files participate: `~/.claude.json` (`mcpServers`, root `disabledMcpServers`,
`projects[<exact cwd>].disabledMcpServers`), `~/.mcp.json`, `~/.claude/settings.local.json`
(`enabledMcpjsonServers`, `enableAllProjectMcpServers`), `~/.claude/settings.json`
(`deniedMcpServers`, **objects not strings**), and `~/.claude/.mcp-disabled-defaults.json`
(advisory template, decides nothing). This is mcpctl's measured model and it held on re-run.

---

## 3. Liveness vs capability — FOUR signals, and they disagree by design

This is the core result. Four mechanically independent probes:

| | signal | what it actually answers |
|---|---|---|
| S1 | mcpctl over the 5 JSON scopes | "what does the config say" |
| S2 | `claude mcp list` | "can a **fresh process** connect right now" |
| S3 | `mcp__*` namespaces injected into this session | "can the model **see** these tools" |
| S4 | a real tool **call** | "does the capability **work**" |

```
S1  145 rows, 16 enabled
S2   64 rows, 53 Connected, 11 failed
S3   23 servers live in-session
```

### 3a. `claude mcp list` is NOT a mount signal — 33 false-positive rows

**33 servers report `✔ Connected` while being absent from the session namespace**: apify,
apktool-mcp, binary-ninja-mcp, biomni-hub, browserstack, cheatengine, codacy, codecov,
cve-mcp, deepscan, deepsource, digitalocean, elevenlabs, excel, figma-rest, firecrawl,
ghidra-mcp, github_cli, hexstrike-ai, ida-pro-mcp, jadx-mcp, mcp-graphql, ocr-suite,
openmm-md, pdf-reader, perplexity, qdx-rush, ralph-orchestrator, schrodinger, scrapegraph,
semgrep, sentry, social-hub.

`claude mcp list` **spawns and health-checks every configured entry, ignoring the disable
lists**. So the lane's briefed starting point — *"55 connected of 67"* — measures reachability,
not mounting. Using it as a fleet-health number over-counts the live fleet by ~2.3x
(53 vs 23). Confidence: **almost certain (90-99%)**, n=33 with zero counter-examples.

### 3b. The lane's worked example is REFUTED

> Briefed: *"the codex entry reports CONNECTED while a real call FAILS at OpenAI
> agent-identity registration -- proof that a health check is not a capability check."*

Executed today via `mcp__codex__codex`, sandbox `read-only`:

```
{"threadId":"019ff6e7-e9a5-7730-8182-93147c2cb441","content":"PONG"}
```

**Codex works.** S1=enabled, S2=Connected, S3=LIVE, S4=**PASS**. The briefed fact is stale or
was wrong. Per the fan-out contract's re-probe rule this used a *mechanically different*
measurement (an actual tool call, not a re-read of the health line). Confidence: **almost
certain (90-99%)** that basic Codex capability is live right now. *Residual, disclosed:* a
single successful call cannot prove the failure never occurred nor that every invocation
shape works. **Settling experiment:** re-run with the exact failing shape (MCP tools active +
typed `--output-schema`, the codex issue #15451 landmine recorded in `workflow-authoring` §9).

**The gap the example was reaching for is real — it just points the other way.** Better
evidence, measured: `brightdata`, `playwright-cdp`, `playwright-extension` are all **LIVE in
the session namespace** (the model can see and call their tools) while `claude mcp list`
reports them **FAILED**. Tools advertised, server down. That is the true liveness≠capability
shape on this box, and it is the one an audit must catch.

### 3c. mcpctl's config resolution misses 8 live servers

`S3 LIVE but S1 != enabled`:

| server | S1 state | basis |
|---|---|---|
| angr | disabled | claude-user-disabled |
| chrome-devtools | disabled | claude-user-disabled |
| claude-code-mcp | disabled | claude-user-disabled |
| context7 | disabled | claude-user-disabled |
| searxng | disabled | claude-user-disabled |
| brightdata | pending-approval | mcp-json |
| playwright-cdp | pending-approval | mcp-json |
| playwright-extension | pending-approval | mcp-json |

`mcpctl/README.md` discloses **`angr` as "the sole exception in 46 root-disabled defined
servers."** Measured today: **5 root-disabled servers are live, not 1**, plus 3
pending-approval servers are live. The README's own `UNVERIFIED` tag on the angr mechanism was
correct to be there; the exception class is simply wider than one row.

Honest scoping — this is **not** a refutation of mcpctl's precedence table, and I am not
claiming it is. My S3 probe is the *same kind* of probe the README used (session tool
namespaces), 17 days later, so config drift is a live alternative explanation.
**UNVERIFIED — whether these 8 are a genuine exception class or ordinary config drift is not
established.** Settling experiment: re-run `mcpctl matrix` and the namespace census
back-to-back after a session restart, and diff the root `disabledMcpServers` list against its
2026-07-26 state via `git log -p` on any captured copy. Confidence in *the disagreement
existing today*: **almost certain**. Confidence in *"the precedence model is wrong"*:
**uncertain (20-55%)** — do not act on it yet.

Reverse direction: `fiddler` is S1=enabled but S2=FAILED and absent from S3 — a configured
server whose backing app (Fiddler) is not running. Only 1 such row.

---

## 4. Cost — already measured, and the constants have DRIFTED

`mcpapply/impact.py` is the prior art and it is unusually rigorous: two **anti-correlated**
axes kept separate (a blended score "would recommend disabling exactly the wrong server"), a
`TokenBasis` provenance enum (`EXACT` / `SCHEMA_BYTES` / `TOOL_COUNT` / `NOT_MEASURED`) whose
aggregate carries the **weakest** contributing basis, and `TOOL_BLOCK_OVERHEAD_TOKENS = 496`
charged once per request rather than per server.

Its measured facts, inherited from the 2026-07-27 scout run and **tagged as inherited in the
source itself**:

| server | tools | eager tokens | deferred tokens | commit |
|---|---|---|---|---|
| cloud-hub | 409 | 77,198 | 5,370 | 17 MB |
| chrome-devtools | 29 | — | — | 331 MB |

**Deferred loading changes the arithmetic ~14x** (77,198 → 5,370). This session is in the
**deferred** regime — the tool list injected here is names-only and schemas arrive via
`ToolSearch` — so eager-regime numbers must not be quoted as this session's cost.

Two corroborations and one drift, measured today:

* **chrome-devtools = 29 tools** — my independent namespace count matches `impact.py` exactly.
  Two mechanically different methods agreeing raises confidence in both.
* **cloud-hub = 424 tools** (executable `tools/list`, above) **vs 409 inherited** — **+15 tools,
  +3.7% drift in ~16 days.** The inherited constant is stale. This is precisely why the
  producer must be a *live probe with a cache*, not a hardcoded table.
* **A source-static tool counter is a DETECTOR FAILURE — discarded, recorded here so nobody
  rebuilds it.** I wrote one (`_probe_tool_cost.py`); its both-states control passed on a
  synthetic 2-tool fixture, and it still reported cloud-hub=129, search-hub=1, social-hub=0
  against real values of 424 / ~50 / ~30. cloud-hub and search-hub **proxy their backends'
  tools at runtime**, so nothing static can count them. The control proved the regex could
  count decorators; the hypothesis was "this counts the tool surface". *A control that cannot
  distinguish the two hypotheses is not a control.* Only `tools/list` is authoritative.

---

## 5. Duplication

**Exact-name collision, MEASURED (strongest evidence class).** `searxng` and `search-hub` are
both live and expose an **identical 4/4 tool-name set**: `searxng_web_search`,
`searxng_instance_info`, `searxng_search_suggestions`, `web_url_read`. The standalone server is
wholly contained in the hub. Confidence: **almost certain**.

**Semantic overlap, INFERRED from tool surfaces — not byte-compared.** Three browser rails live
simultaneously (`playwright`, `playwright-cdp`, `playwright-extension`, ~24 near-identical
`browser_*` tools each) plus `chrome-devtools` (29 tools, and the heaviest RAM row on the box at
331 MB). Search backends overlap across `search-hub` (exa+firecrawl+tavily+searxng), standalone
`searxng`, `brightdata`, and disabled `firecrawl`/`perplexity`/`tavily`.

**Destructive-action default applies and it has teeth here.** The measured base rate on this
estate is that 34 of 57 skill pairs *looked* like duplicates and **zero** shared meaningful
content. The three playwright variants are a textbook trap: they share tool *names* but target
different browser contexts — `playwright` launches its own browser, `playwright-cdp` attaches to
an existing CDP endpoint, `playwright-extension` drives a logged-in profile via the extension.
The memory note *"browser rail DEAD (Chrome-136 default-profile CDP break)"* is exactly why the
variants exist. **Read both surfaces before proposing any retirement, and prefer DISABLE.**

---

## 6. Resource — re-measured, control passed

`Get-CimInstance Win32_Process` over the full 947-process table, grouped by exact normalized
command line. Both-states detector control: own PID visible ✔, nonsense token 0 matches ✔,
known-present `cloud-hub` matched 4 ✔.

| metric | today (2026-08-12) | plan §1 (2026-07-24) |
|---|---|---|
| agent sessions | **8** (4 claude, 4 codex) | 13 |
| MCP processes | **238** | 336 |
| distinct command lines | **112** | 180 |
| command lines n>1 | **58** | 58 |
| redundant processes (Σ n−1) | **126** | 156 |
| commit of MCP procs | **8.51 GB** | 13.24 GB |
| gross dedup projection | **4.38 GB** *(PROJECTION, not a measured saving)* | 5.92 GB |
| `npx-cli.js` copies | **28** / 2.32 GB | (lane brief: 76 / ~5.5 GB) |

**The per-session multiplier is the durable fact; the absolute counts are not.** Top duplicates:
scholarly-access n=10, paper-search n=8, frida-mcp n=8, and a long tail at **n=4 — exactly the
4 concurrent `claude.exe` sessions**. The lane's briefed "76 copies of npx-cli.js / ~5.5 GB" and
today's 28 / 2.32 GB are both correct at their measurement times; quoting either as a constant is
the error. Report `copies-per-session`, never `copies`.

**Why 238 processes with only 16 "enabled": root `disabledMcpServers` does not prevent the
spawn.** `mcpapply/plan.py:107` encodes this from a controlled A/B — `SPAWN_PREVENTING` is
`{SETTINGS_DENIED, CLAUDE_PROJECT_DISABLED}` and root `CLAUDE_USER_DISABLED` is **deliberately
absent**. A disable written to the root list hides the tools but still pays the RAM. This is the
single most actionable fact in the audit and it is already encoded, tested, and unused.

---

## 7. Security

From `mcpctl credentials` (variable **names** and present/absent/reference only — mcpctl's
`safety.env_fields` is the sole route by which an `env` block enters the data model, and it never
carries a value). **22 rows carry env fields; 8 are classed credential-bearing. No value was read,
printed, or modified anywhere in this audit.**

Credential-bearing servers that are **live**: `cloud-hub` (8 vars — GCP/Kaggle/Lightning/Modal/
RunPod) and `search-hub` (6 vars — Exa/Firecrawl/Tavily ×2 each). Credential-bearing and
**disabled/denied**: codacy, codecov, context7, deepsource, digitalocean, figma-rest, firecrawl,
github_cli, gitlab (denied), scrapegraph, sentry, social-hub, sonarqube, browserstack, biomni-hub.

Structural notes, not new findings — all three already argued in `mcpctl/README.md`:
an MCP server is RCE by design; third-party npx servers (`context7`, `repomix`, `searxng`,
`chrome-devtools`, `pdf-reader`, `excel`) execute fetched-at-install code; `deepwiki`, `figma`,
`github`, `basic-memory`, `agent-mail` are HTTP transports. Two are loopback-only and safe by
binding (`basic-memory` :8765, `agent-mail` :8812). **Per §9 no credential is rotated, revoked, or
modified — that is the owner's lifecycle to run.**

One thing to flag rather than fix: `claude mcp list` **spawns every configured server**, including
33 that are disabled and several third-party. Running it is not a read-only operation.

---

## 8. Ranked plan for the BUILD lane

**R1 — Wire the liveness producer into mcpctl's four empty fields. (highest value, smallest diff)**
`StdioChild` in `tools/mcp/mcp-http-host/mcp_http_host.py` already performs `initialize` +
`tools/list` and returns tool count + PID; `smoke_stdio.py` is the working driver. Proven today at
**1.9 s/server**. Add: an on-disk cache keyed by `(command, args, mtime)` so a full sweep is paid
once; `rss_bytes` joined from `Win32_Process` by the returned PID; `last_error` carrying the
handshake failure verbatim through `mcpctl.safety.safe`. Respect mcpctl's read-only AST gate —
the producer must live **outside** the `mcpctl` package (in `mcpapply`, which already spawns) and
be *injected*, exactly as its docstring specifies.

**R2 — Make the four-signal disagreement a first-class output, not a footnote.** Every row should
carry `config_state / host_reachable / session_mounted / call_verified` as four columns that are
never collapsed into one boolean. §3a proves collapsing them over-counts the fleet 2.3x. mcpctl's
`Resolution.basis`/`conflicts`/`inferred` design already refuses to collapse config scopes; extend
the same discipline one level up.

**R3 — Replace `impact.py`'s inherited constants with cached live probes.** Keep the `TokenBasis`
enum and the two-axis split — both are correct and hard-won. Only the *values* are stale
(cloud-hub 409→424 in 16 days). Wire R1's cache in as the `EXACT` basis source.

**R4 — Act on `SPAWN_PREVENTING`, which is already built and unused.** Any RAM recommendation that
writes to root `disabledMcpServers` saves **zero** memory. Route disables through
`mcpapply`'s `DISABLE_PREFERENCE` (project-disabled first). This is the highest-RAM-per-line-of-
code change available and it needs no new code at all.

**R5 — Retire exactly one thing, the only one with exact-name evidence:** standalone `searxng`
(4/4 tools contained in `search-hub`). **DISABLE, not remove**, via `mcpapply` dry-run → backup →
apply. Leave the three playwright variants and `chrome-devtools` alone pending a real surface diff
(§5).

**R6 — Report `copies-per-session`, never `copies`.** Every absolute process count in the existing
docs is already stale by ~30% because session count changed. Normalise the metric.

**R7 — Do NOT build:** a new inventory tool, a new scope reader, a new redaction layer, a new
mutation/GUI layer, a source-static tool counter (§4 — measured detector failure), or a
`claude mcp list` wrapper as a health source (§3a).

---

## 9. Artifacts

| path | contents |
|---|---|
| `command-center/mcp-audit/mcpctl-matrix.json` | 145-row inventory, mcpctl envelope |
| `command-center/mcp-audit/claude-mcp-list.txt` | raw S2 host health output |
| `command-center/mcp-audit/process-census.json` | S6 census + detector-control block |
| `command-center/mcp-audit/_probe_three_signals.py` | the S1×S2×S3 cross-tab |
| `command-center/mcp-audit/_probe_process_census.py` | census with both-states control |
| `command-center/mcp-audit/_probe_matrix.py` | matrix decomposition |
| `command-center/mcp-audit/_probe_tool_cost.py` | **the discarded detector** — kept as a negative result (§4) |