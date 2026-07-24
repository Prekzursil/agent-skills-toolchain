# MCP consolidation — ending per-session process multiplication

Companion plan for `tools/mcp/mcp-http-host/` (PR #159, the shared stdio→HTTP host) and
`tools/mcp/mcp-host-supervisor/` (this PR, the always-on launcher).

**Scope of this document:** the measured live picture, a ranked migration order with
per-server evidence, an honest verdict on aggregator gateways, and the supervisor recipe.
It changes **no live config**. Every flip stays the owner's explicit action.

COVERAGE: §1 live census MEASURED — but the "reclaimable / attributable-to-duplication"
figures (5.92 GB total, 4.81 GB top-18, 2.84 GB Tier A) are a GROSS full-dedup PROJECTION,
not a measured net saving (see the §1 "measured vs projected" note) · §2 ranking MEASURED for
repo-local servers, INFERRED-from-tool-surface for third-party ones (tagged inline) · §3
aggregator evaluation from vendor docs (tagged inline), and §3a records the Q3 transport
decision (mcp-proxy spike PASSED on the box's cmd/c-wrapped servers; footprint UNVERIFIED) ·
§4 launcher BUILT + TESTED.

---

## 1. The live picture (measured 2026-07-24, this box)

Probe: `Get-CimInstance Win32_Process` over the full 1,169-process table, grouped by
**exact normalized command line** — a deterministic algorithm, not judgement. Two processes
with byte-identical command lines are the same server launched twice, by construction.

| Metric | Value |
|---|---|
| Concurrent agent sessions | **13** (5 `claude.exe`, 8 `codex.exe`; plus `grok.exe` seen as an MCP parent) |
| MCP-matching processes | **336** |
| Distinct command lines | 180 |
| Command lines with n > 1 | **58** |
| Redundant processes (Σ n−1) | **156** |
| Commit charge of these processes | **13.24 GB** |
| **Commit attributable to duplication** (GROSS projection — see note) | **5.92 GB** |
| Redundant threads / handles | 757 / 22,404 |
| Box state at probe time | 31.6 GB physical, **1.2 GB free**; commit **76 GB / 175.6 GB** |

**Measured vs projected — the 5.92 GB is a projection, not an observation.** Every per-process
figure and the **13.24 GB** total commit are directly measured (`PrivatePageCount`). The
**5.92 GB "attributable to duplication" is computed**, per command line, as `commit × (n−1)/n`
— the commit that *would* be freed **if** each duplicated server collapsed to one instance
**and** its private commit were fully independent. It is therefore a **GROSS** figure: the
**net** reclaim after a real migration is `5.92 GB − (N × host_commit)`, and `host_commit` is
**UNVERIFIED** — no shared host was running at probe time (§3). No end-to-end before/after
reclaim has been measured. Every "reclaimable" number downstream (4.81 GB top-18 in §1c,
2.84 GB Tier A in §2) inherits this gross-projection scope. Settling test: migrate Tier A per
§3, re-run this census, and compare total commit before/after.

### 1a. Measure COMMIT, not RSS — the metric choice changes the answer 19×

The same census scored by `WorkingSetSize` reports only **0.31 GB** reclaimable. Idle stdio
MCP servers have their working set trimmed to ~0.2-0.3 MB while keeping their full private
commit reserved. Since the measured freeze driver on this box is **commit exhaustion**
(RAM + pagefile), not resident-set OOM, an RSS census understates the real cost by ~19× and
would have made this whole lane look not worth doing. Use `PrivatePageCount`.

### 1b. One logical server ≠ one process — the shim chain multiplies by ~3

Traced parent-child for `frida-mcp` (`Win32_Process` ppid walk):

```
claude.exe ─► frida-mcp.exe ─► python.exe frida-mcp.exe ─► python.exe frida-mcp.exe
 (session)      (venv shim)         (launcher)                  (actual server)
```

**3 OS processes per session for ONE logical MCP server**, across 7 distinct session hosts.
The npx-launched Node servers show the same shape (`cmd.exe /c npx -y repomix --mcp` →
`npx-cli.js` → `repomix.cjs --mcp`). So "156 redundant processes" is a process count, **not**
a count of redundant servers — the redundant *logical server* count is roughly a third of it.
The reclaimable-commit figure is unaffected: it is computed per command line as
`commit × (n−1)/n`, which holds whatever the chain depth.

### 1c. Top offenders, ranked by reclaimable commit

`sess` = distinct session roots — the direct evidence of cross-session multiplication.

| # | server | n | sess | reclaimable | each |
|---|---|---|---|---|---|
| 1 | `markitdown-mcp` | 4 | **1** | 941 MB | 314 MB |
| 2 | `paper-search-mcp` | 12 | 6 | 410 MB | 37 MB |
| 3 | `repomix --mcp` (inner) | 6 | 6 | 386 MB | 77 MB |
| 4 | `npx -y repomix --mcp` (outer) | 6 | 6 | 357 MB | 72 MB |
| 5 | `npx -y @playwright/mcp` (outer) | 5 | 5 | 351 MB | 88 MB |
| 6 | `frida-mcp` | 14 | 6 | 343 MB | 26 MB |
| 7 | **`basic-memory` (already HTTP :8765)** | **2** | 1 | 320 MB | 320 MB |
| 8 | `@playwright/mcp` (inner) | 5 | 5 | 284 MB | 71 MB |
| 9 | **`rdkit-mcp-server` (already streamable-http)** | **2** | 1 | 279 MB | 280 MB |
| 10 | `scholarly-access-mcp` | 10 | 5 | 272 MB | 30 MB |
| 11 | `qlty_mcp_server.mjs` | 7 | 6 | 217 MB | 36 MB |
| 12-18 | searxng ×2, excel ×2, mcp-remote, mcp-graphql, codex | | | 759 MB | |

Top-18 reclaimable: **4.81 GB** of the 5.92 GB total (both GROSS projections — see the §1
"measured vs projected" note).

**Two findings worth acting on independently of any migration:**

* **#1 `markitdown-mcp` — 4 copies inside ONE session, 941 MB.** Cross-session multiplication
  cannot explain this; these look like leaked/orphaned copies. This is the single largest win
  on the board and it needs no protocol change — only reaping. `likely` (55-80%) these are
  orphans rather than a deliberate pool; settling test: `Get-CimInstance Win32_Process` ppid
  walk on the four pids to see whether their parents are alive.
* **#7 and #9 are ALREADY shared-HTTP services running in duplicate.** `basic-memory`
  (`--transport streamable-http --port 8765`) and `rdkit-mcp-server` should each have exactly
  one instance; each has two, costing 599 MB between them. A shared-HTTP endpoint with two
  live copies means one bound the port and the other is a wasted double-launch — exactly the
  failure the supervisor's health-gate ("adopt a healthy endpoint, never double-bind")
  prevents. This is evidence that the shared-HTTP model *needs* a supervisor, not just a host.

---

## 2. Ranked migration plan — what is safe to share, and what is not

**The sharing question is not "is it stateless?" but "does it hold mutable state whose
lifetime is currently per-session?"** Collapsing S processes to 1 makes any such state
global. Tiers are ordered by (reclaimable commit) ÷ (risk).

### Tier A — share now; no cross-session semantics to lose

| server | reclaimable | evidence |
|---|---|---|
| `paper-search-mcp` | 410 MB | pure search/fetch over public corpora; every tool is request→response with no handle |
| `repomix` (both procs) | 743 MB | packs a codebase path per call; the path is an argument, not session state |
| `scholarly-access-mcp` | 272 MB | `tools/scholarly-access-mcp/` — resolve/fetch metadata per DOI; no mutable store |
| `markitdown-mcp` | 941 MB | stateless document→markdown conversion |
| `qlty_mcp_server.mjs` | 217 MB | runs a linter over a path per call |
| `mcp-searxng` | 260 MB | stateless web search |

Tier A total: **≈2.84 GB** — 48% of all reclaimable commit, at the lowest risk. That
2.84 GB is a GROSS projection (net = 2.84 GB − N × host_commit, the UNVERIFIED per-host cost
quantified in §3; see the §1 "measured vs projected" note).

INFERRED-from-tool-surface, not from source, for the third-party members
(`paper-search`, `repomix`, `markitdown`, `searxng`) — **UNVERIFIED** that none holds hidden
per-connection state. Settling test per server: front it with `mcp_http_host.py`, drive
`initialize` + a real tool call from two clients concurrently, and assert `/healthz` reports
`child_spawn_count == 1` with both responses correct.

### Tier B — shareable, but with a DISCLOSED semantic change (the three hubs)

`search-hub`, `cloud-hub`, `social-hub`. PR #159 calls all three `likely` safe. That is right
about `initialize`/`tools/list` (answered from committed caches) but **incomplete**, and the
gap is load-bearing:

* `tools/mcp/search-hub/hub.py:290` constructs `accounts.AccountStore(ACCOUNTS_PATH, …)`
  **once per hub process**, and `_shared/accounts.py:311` loads the JSON store into
  `self._data` at construction — a snapshot taken at startup.
* `hub.py:435 _handle_account` mutates that store on `<prefix>_account_switch` / `_cycle`,
  and `hub.py:445` calls `self.rotator.clear_cooldown(platform, active)`.
* `hub.py:301` keeps `self._children` — lazily spawned backend children — keyed per process.

So **today** each session holds its own account snapshot and its own rotation cooldowns;
a switch in session A does not reach session B's already-running hub. **Shared**, one store
serves everyone: an `az_account_switch` / `ex_account_cycle` in one session immediately
re-routes every other session's next call, and a key exhausted in one session is cooled for
all.

That is arguably *more* correct (one truthful view of which account is active, global
rate-limit accounting) but it **is** a behaviour change, and it breaks any workflow that
relies on two sessions holding different active accounts — the cswap-style multi-account
rotation is exactly such a workflow. `roughly even` (40-60%) that this matters in practice
for the owner's current usage. Settling test: front `search-hub`, then from two HTTP clients
call `ex_account_switch` on one and `ex_account_current` on the other — if the second sees
the first's switch, the semantics changed.

**Recommendation:** migrate the hubs *after* Tier A, one at a time, and only once the owner
confirms no session-local account divergence is wanted. Reclaimable: hubs were not in the
top-18 (they are 3 of the 11 servers in `~/.mcp.json` and were comparatively cheap at probe
time), so there is no urgency to take this risk first.

### Tier C — do NOT share a stdio child; these are strongly stateful

| server | why sharing breaks it |
|---|---|
| `frida-mcp` (343 MB) | `attach_to_process`, `create_interactive_session`, `execute_in_session` — the session handle *is* the state; two agents sharing one child would execute into each other's scripts |
| `@playwright/mcp` (635 MB) | one browser/page/tab per server; two sessions would fight over the same viewport |
| `ida-pro-mcp`, `ghidra-mcp`, `binary-ninja` | bound to the currently-loaded binary/IDB; a second session's `open` silently changes the first's analysis target |
| `angr`, `cheatengine-mcp-bridge` | project / attached-process state |
| `hexstrike-ai` | engagement-scoped state |

For these the correct cure is **not** a shared stdio wrapper. Either (a) leave them
per-session and instead **stop exposing them by default** (they are RE tools; most sessions
never call them — the `mcp-fleet-curation` disable-at-user-scope path), or (b) have them
expose a **native** HTTP mode with real per-session routing. Note `frida-mcp` at 343 MB and
Playwright at 635 MB are large — curation, not sharing, is where their savings come from.

### Tier D — already HTTP; just stop the double-launch

`basic-memory` (:8765) and `rdkit-mcp-server`: 599 MB of pure waste from duplicate instances
of services that are already shared by design. Fix = supervision (§4), not migration.

### Suggested order

1. **Reap the orphans** (markitdown 941 MB + the Tier-D duplicates 599 MB) — **1.54 GB, zero
   protocol risk.** Do this first; it is the best ratio on the board.
2. **Tier A migration**, one server per restart, measuring between each — ≈2.84 GB *gross*
   (net = gross − N × host_commit; §3 settling test).
3. **Curate Tier C** off the default surface — large, and cheaper than any engineering.
4. **Tier B hubs** last, only with the account-semantics decision made explicitly.

---

## 3. Aggregator gateway evaluation — MetaMCP and MCPJungle

Both genuinely solve the topology: clients dial one endpoint, the gateway holds one
connection per downstream, so `S × H` collapses toward `H`. The question is cost on **this**
box and fit with **this** estate's constraints.

### MetaMCP — **REJECT** (`almost certain`, 90-99%)

Its own docs require Docker + PostgreSQL + a Next.js app and state *"an instance of at least
2GB-4GB of memory is required"* (vendor documentation, retrieved 2026-07-24 —
**UNVERIFIED** by local measurement; settling test would be to run it and measure commit,
which is precisely what the box cannot currently afford).

Spending 2-4 GB of resident footprint plus a Docker Desktop runtime to reclaim 5.92 GB of
commit is a poor trade on a box sitting at **1.2 GB free physical**, and Docker on this
machine has its own history (a 49 GB disk reclaim was needed once already). The management
UI and OIDC/RBAC features solve team problems this single-user estate does not have.

### MCPJungle — **REJECT FOR NOW**, revisit if the fleet outgrows the host model (`likely`, 55-80%)

Materially better fit than MetaMCP: a single Go binary (no Docker required), SQLite in dev
mode, and it explicitly supports **stdio** downstreams — so it *could* front this fleet
(vendor docs, retrieved 2026-07-24). Three reasons it still loses here:

1. **It collides with the load-bearing curation.** The gateway exposes tools on one `/mcp`
   endpoint as `<server>__<tool>`. This estate's enabled/disabled MCP curation (~65 exposed,
   ~16 active) is per-server and is explicitly load-bearing — it must not be destroyed. An
   aggregator re-expresses that curation as tool-groups in a *second* registry that must stay
   in sync with `~/.mcp.json`. Two sources of truth for a curation whose whole purpose is
   drift control is a regression.
2. **Tool-budget risk.** Flattening many servers behind one endpoint pushes toward the
   per-turn tool/token bloat the `mcp-fleet-curation` skill exists to fight. Tool groups
   mitigate it, but only by rebuilding the curation (see 1).
3. **It does not help Tier C.** A gateway holding one shared connection to `frida-mcp` has
   exactly the same cross-session state-bleed problem as `mcp_http_host.py` — the aggregator
   buys nothing on the hardest servers.

**Recommendation: `mcp-http-host` (PR #159) + this supervisor.** It preserves 1:1 server
identity, so the existing per-server curation keeps working unchanged; it is stdlib-only
(no Node, no Go, no Docker, no database); and it is additive and reversible per server.
**Update — §3a: the Q3 spike now favours *adopting* `mcp-proxy` for the stdio→HTTP transport
rather than hand-rolling `mcp_http_host.py`; the supervisor half of this recommendation is
unchanged.**

**The honest cost of that recommendation:** it needs **one host process per shared server**
(N hosts) where an aggregator needs one process total. At 6 Tier-A servers that is 6
supervisor-managed `http.server` processes. Their own footprint is **UNVERIFIED** — PR #159's
host was not running at probe time, so its per-process commit was never measured. Settling
test: start the 6 Tier-A hosts, re-run the §1 census, and compare total commit before/after;
the migration is only worth it if `6 × host_commit` is far below the 2.84 GB reclaimed.
`likely` (55-80%) it is, since the host is a stdlib `http.server` with one subprocess pipe
and no framework imports — but that is an inference from reading `mcp_http_host.py`, not a
measurement, and it must be checked before Tier A is called done.

### 3a. Transport update (Q3 decision) — adopt `mcp-proxy`, don't hand-roll the bridge

The recommendation above hand-rolls the stdio→HTTP transport as `mcp_http_host.py` (PR #159).
The **Q3 spike supersedes that transport choice.** A `mcp-proxy` (sparfenyuk/mcp-proxy) spike
run on this box **works on the `cmd /c`-wrapped stdio servers** — the
`cmd.exe /c npx -y … --mcp` launch shape §1b traces, which is exactly the case the hand-rolled
host was built to cover.

* **Prefer adopting `mcp-proxy` for the stdio→HTTP transport over maintaining a hand-rolled
  bridge.** It gives the *same* property this section values in `mcp-http-host` — **1:1 server
  identity, so the load-bearing per-server curation (~65 exposed / ~16 active) keeps working**
  (one proxy per server, not a flattening aggregator like MetaMCP / MCPJungle) — but as a
  maintained community package, not estate-local code the owner must own and debug (the
  UTF-8-BOM and wedge-recycle bugs this PR had to find by hand are the standing cost of
  hand-rolling).
* **What does NOT change.** This is a *transport* swap only. The §4 supervisor
  (ownership-scoped reaping, AND-gate wedge detection, adopt-don't-double-bind health gate,
  opt-in manifest) is transport-agnostic and stays the deliverable — it can front `mcp-proxy`
  processes exactly as it fronts `mcp_http_host.py`. **Tier C (§2) stays unshareable
  regardless**: `mcp-proxy` multiplexing one stdio child has the identical cross-session
  state-bleed as an aggregator or the host — transport choice does not change a server's
  protocol-level statefulness.
* **Honest scope of the spike.** It proved a `mcp-proxy` bridge **functional** on a
  cmd/c-wrapped server; `mcp-proxy`'s own per-process **footprint is UNVERIFIED** and feeds the
  *same* `N × host_commit` net-reclaim question as §1 and the honest-cost note above (settling
  test: run the Tier-A servers under `mcp-proxy` and re-census). It is also not yet checked that
  `mcp-proxy` serves `initialize` / `tools/list` from a cache the way the curation relies on.
  Net: adopting `mcp-proxy` over a hand-rolled bridge is the better call — `likely` (55-80%) —
  pending that footprint measurement and cache check.

---

## 4. Always-on launcher — `tools/mcp/mcp-host-supervisor/`

Mirrors `MCPAgentMailSupervisor` (named mutex, health gate, backoff, rotating log, logon
Scheduled Task) and adds the two capabilities that supervisor **measurably lacks** — a grep
of `agentmail_supervisor.ps1` for `orphan|reap|TotalProcessorTime|wedge` returns nothing.

### 4a. CPU-progress wedge detection (AND-gate)

The agent-mail supervisor's own comment records the failure: a 90 s startup grace *"killed
near-ready children 2-60s before they bound → a non-converging crash loop"*, fixed by raising
the grace to 240 s. Raising a timeout treats the symptom. The cause is **recycling on a single
signal**. `fleet.py:wedge_verdict` requires three agreeing signals before authorising a kill:

| verdict | condition | action |
|---|---|---|
| `HEALTHY` | health probe answered | — |
| `STARTING` | inside the startup grace | never kill |
| `DEGRADED` | unhealthy, streak < 3, **or no previous sample** | wait |
| `BUSY` | unhealthy + streak exceeded, but **CPU or `requests_served` still advancing** | wait — it is working |
| `WEDGED` | unhealthy **AND** CPU flat **AND** requests flat | recycle |

`BUSY` is the case a single-signal supervisor gets wrong. One reading is never enough:
with no previous sample the verdict is `DEGRADED`, never `WEDGED`.

### 4b. Ownership-scoped orphan reaping

A machine-wide pattern reap once killed sibling sessions' MCP children. `fleet.py:find_orphans`
kills a process only when it matches the host signature **and** is either parented by this
supervisor but untracked (our leftover), or its parent is gone (a true orphan). A process
whose parent is a *different live process* belongs to someone else and always survives. An
empty signature raises `ValueError` rather than matching every process on the box.

### 4c. Safety posture

* `fleet.example.json` ships with **every server `"enabled": false`** — installing the task is
  inert until the owner opts a server in.
* `fleet.py validate` rejects ports **8765** (basic-memory) and **8812** (agent-mail), and any
  non-loopback bind.
* A healthy endpoint is **adopted**, never double-bound — the fix for the §1c Tier-D finding.
* `-DryRun` reports every start/kill without performing it; `install_task.ps1 -Uninstall`
  removes the task and backs up any prior registration.
* Registration into `~/.mcp.json` stays apply-when-closed via
  `../mcp-http-host/apply_registration.py`. This lane changes no live config.

### 4d. Install

```powershell
cd tools/mcp/mcp-host-supervisor
Copy-Item fleet.example.json fleet.json     # then set "enabled": true on ONE server
C:/Python314/python.exe fleet.py validate --manifest fleet.json
./mcp_host_supervisor.ps1 -Manifest fleet.json -Once -DryRun    # rehearse
./install_task.ps1                                              # logon task
Start-ScheduledTask -TaskName MCPHostSupervisor
```

**Dependency:** the supervisor launches `../mcp-http-host/mcp_http_host.py`, which lands with
**PR #159**. Until that merges the supervisor validates, plans, reaps and dry-runs correctly,
but cannot start a real host.

---

## 5. Evidence

* Live census + commit analysis: `Get-CimInstance Win32_Process` over 1,169 processes,
  grouped by exact command line (2026-07-24).
* `tools/mcp/search-hub/hub.py:290,301,435,445` — per-process account store, lazy children,
  account mutation, rotation cooldown.
* `tools/mcp/_shared/accounts.py:311,314-326` — `_data` snapshot at construction, `_persist`
  write-back.
* `~/.local/opt/mcp_agent_mail/supervisor/agentmail_supervisor.ps1:57-63` — the measured
  90 s→240 s grace fix and `MaxHealthFailStreak`; no orphan/CPU logic present.
* `tools/mcp/mcp-http-host/README.md` (PR #159) — shared-child invariant and its own caveats.
* MetaMCP / MCPJungle: vendor documentation retrieved 2026-07-24 (tagged UNVERIFIED inline).
* `mcp-proxy` (sparfenyuk/mcp-proxy): Q3 spike on this box — stdio→HTTP bridge verified
  **functional** against a `cmd /c`-wrapped `npx … --mcp` server; per-process footprint
  UNVERIFIED (see §3a).
