# MCP fleet — capability matrix and per-server disposition (BUILD lane, rounds 1-2)

Measured 2026-08-12, re-measured and defect-closed 2026-08-13, on this box, worktree
`C:/Users/Prekzursil/source/ast-integrate`.
Builds on the grounding lane's `MCP-FLEET-AUDIT.md`; this lane produced the thing that
audit identified as the single genuine gap — **a real per-server capability signal** —
and turned it into a ranked, reversible disposition per row.

COVERAGE: §1 prober BUILT + EXECUTED · §2 detector control EXECUTED, 4 states, 4/4
red-proof mutations caught · §3 capability sweep MEASURED for all 23 mounted servers
(16 by stdio handshake) · §4 in-session real calls EXECUTED for 5 HTTP-transport servers
· §5 context cost MEASURED (707 tools, both channels, in bytes — NOT tokens, see the
unit caveat inline) · §6 duplication COMPUTED by exact set arithmetic · §7 disposition
COMPLETE for 23/23 mounted rows · §8 DoD ledger per item · §11 round-2 closure of the 3
defects an independent verifier CONFIRMED, each reproduced before its fix and each fix
red-proofed. **NOT measured:** the 122 non-mounted config rows were deliberately not
spawned; `brightdata` and `deepwiki` have no real call (reasons recorded per row); the R1
wiring into `mcpctl`/`mcpapply` is outside this lane's file scope and was not attempted
(§9); whether a FOURTH defect remains — three were found by a verifier and closed, the
artifact was not re-derived from scratch.

No production code outside `docs/mcp-audit/**` and `command-center/mcp-audit/**` was
written. No config changed. No credential read, printed, or modified.

---

## 0. Headline

**21 of 23 mounted servers carry a real-call verdict, up from 2** — 16 by a stdio
`initialize`+`tools/list` handshake, 5 by a real in-session tool call, and the
machine-readable `call_verified` field now sums to that same 21 (round 1 it summed to 16
while the prose said 21; see §11). The grounding lane proved `claude mcp list` is not a
mount signal; this lane proves the remaining step — that a *mount* is not a *capability*.

> **Round 2 re-measured everything.** The 16 stdio surfaces were re-probed a day later, on
> a differently-loaded box: **16/16 agree with round 1 on both tool COUNT and the exact
> tool NAME set** (`_r2_corroborate.py`, with a control that renames one tool and confirms
> the comparison reports it). Three of the round-1 defects were disclosure defects, not
> measurement defects — the numbers held.

Two detector failures were found and fixed **in this lane's own instruments**, both caught
by a contradiction with a fact already known:

| # | my instrument said | the contradiction | root cause |
|---|---|---|---|
| 1 | `codex`, `chrome-devtools`, all 3 playwright rails = `FileNotFoundError` | `codex` had already returned `PONG` to a real call | Windows `CreateProcess` does not apply PATHEXT, so `Popen(["npx"])` cannot find `npx.CMD`. **5 working servers reported broken.** |
| 2 | red-proof: "the PATHEXT mutation survived" | measuring `run_control()` directly returned red | `not pc.run_control()` negates the `(ok, rows)` **tuple**, and a non-empty tuple is always truthy → always `False` |

A third is a property of the method, not a bug: **a fixed timeout is a detector with a
false-negative rate.** At 45 s, `angr` and `chrome-devtools` reported FAIL; at 150 s both
PASS (91.3 s and 42.3 s). `angr` measured 23 s → timeout → 48 s → 91 s across four runs.
A later FAIL therefore must not overwrite an earlier PASS, and `rank_disposition.py`
encodes exactly that (`best_capability`).

---

## 1. The prober — `command-center/mcp-audit/probe_capability.py`

Per server: spawn → `initialize` → `notifications/initialized` → `tools/list` (paginated,
20 pages max) → measure → reap the **whole process tree** → next.

**It reuses the existing primitive rather than rebuilding it.** `StdioChild` in
`tools/mcp/mcp-http-host/mcp_http_host.py` already speaks this wire and is tested; this
module imports it by path and adds only spec resolution, PATHEXT resolution, tree-reaping,
memory, redaction, the control, and JSON output. **Nothing under `tools/` was modified.**

Three properties worth stating because each is a decision, not an accident:

* **No child stderr is ever captured.** `StdioChild` spawns with `stderr=DEVNULL`, so a
  server dying about a missing API key cannot leak it into an artifact. The cost is
  diagnostic: `last_error` is *our* exception (timeout / EOF / spawn failure), never the
  server's message. Env values additionally pass a redactor that replaces any
  environment value of length ≥ 8 with `<redacted:NAME>`.
* **Tree reap, not `terminate()`.** `StdioChild.terminate()` signals only the direct
  child; half the fleet launches as `cmd /c npx …`, so terminating `cmd.exe` orphans the
  node process. A naive sweep would *add* to the process duplication the audit measures.
  `reap_tree()` runs `taskkill /T /F` on the recorded pid while it is provably still ours.
* **This is NOT a read-only operation and the target list is an explicit allowlist.**
  The grounding lane's operational warning — `claude mcp list` spawns all 145 configured
  entries including 33 disabled ones — is the failure mode this deliberately avoids: 23
  named servers, each killed immediately.

`commit_bytes` / `working_set_bytes` are the **direct child only**. A hub that lazily
spawns backends (cloud-hub → rclone rcd; search-hub → per-provider children) charges most
of its RAM elsewhere, so these are a **floor, never a total**. That is why this lane's
`chrome-devtools` figure is 6.9 MB while `docs/mcp-consolidation-plan.md` records 331 MB:
different scopes, both correct, neither interchangeable.

## 2. Detector control — both states, and red-proofed

`python probe_capability.py --control` runs four states and **fails the whole run closed**
if any misbehaves:

```
control GOOD     -> call_verified=True  tools=1    passed=True   # committed fixture, EXACTLY 1 tool
control MISSING  -> call_verified=False tools=None passed=True   # nonexistent binary
control NOT-MCP  -> call_verified=False tools=None passed=True   # real process, speaks no MCP
control SHIM     -> call_verified=True  tools=1    passed=True   # same fixture behind a bare .cmd on PATH
```

`NOT-MCP` is what makes this a control rather than theatre: without it, a prober that
merely checked `Popen` succeeded would pass GOOD and MISSING and be indistinguishable
from one that performs a handshake. Requiring the **exact** count (not `>0`) closes the
other direction — an invented surface could not land on 1. `SHIM` is a regression control
for detector failure #1.

`python redproof_control.py` then proves the control **can** go red — three stubbed
mutations plus one real-code mutation (`RESOLVE_SHIMS = False`, i.e. reverting the PATHEXT
fix):

```
baseline control: GREEN (unmutated)
mutation good-broken        -> control red? True
mutation good-wrong-count   -> control red? True
mutation bad-reported-ok    -> control red? True
mutation no-pathext-resolve -> control red? True
SUCCESS:redproof-control 4/4 mutations caught
```

### 2b. The repo gates were verified against the COMMITTED BLOBS, with controls

Working-tree green is not blob green is not CI green, so both gates were re-run over
`git show <commit>:<path>` output with `ruff.toml` from HEAD mirrored into place (a bare
temp dir would make ruff fall back to its own defaults and answer a different question):

```
extracted 12 blobs from b9dce830; CRLF bytes in blobs: 0
blob ruff check        rc=0  ['All checks passed!']
blob ruff format-check rc=0  ['12 files already formatted']
MANGLED control fires: True (rc=1)          <- a mis-formatted copy MUST be flagged
SUCCESS:blob-gate blobs pass both ruff gates, control fired, 0 CRLF
```

Secrets, with a control that is itself committed (because `gitleaks git` reads **history**,
so an uncommitted control proves nothing — the recorded failure on this estate):

```
control (committed synthetic secret in a throwaway repo) fires: True (rc=1)
real scan over b9dce830: rc=0, 1 commit scanned, no leaks found
SUCCESS:secrets-gate
```

**The mangled control failed twice more before it was trustworthy, both times because the
mangle depended on the file's CONTENT.** v1 hardcoded `probe_capability.py`, which crashed
on the second commit that does not contain it. v2 globbed for any `.py` but mangled by
replacing `import argparse` — a silent no-op on a file without it, so the control reported
"did not fire" when nothing had been mangled. v3 **appends** `x  =  1`, which is
content-independent, always mis-formatted, and always syntactically valid (prepending breaks
`from __future__` and makes ruff exit **2 = error**, which is non-zero and would let a broken
control masquerade as a firing one — so the check now demands **exactly** rc=1).

**My first secrets control was INERT and I nearly recorded it as diligence.** An
`AKIA` + 16-identical-chars synthetic fires under **neither** the repo `.gitleaks.toml`
**nor** gitleaks' own defaults — measured as a 2×2 over {default, repo} × {low, high
entropy}. The clean verdict on the real commit was therefore meaningless until the control
was replaced with a token shape measured to fire under both configs. The synthetic is
generated from a fixed seed rather than written as a literal, so the verifier does not trip
the gate it verifies.

## 3. Capability sweep — 23 mounted servers

`python probe_capability.py --mounted --timeout 150`, control passed, exit 0,
`verified=16/23`:

| PASS (stdio handshake) | tools | ms | | FAIL | reason |
|---|---|---|---|---|---|
| cloud-hub | 424 | 1,806 | | agent-mail | HTTP transport — nothing to spawn |
| search-hub | 68 | 1,075 | | basic-memory | HTTP transport |
| paper-search | 57 | 15,195 | | brightdata | HTTP transport |
| chrome-devtools | 29 | 42,345 | | deepwiki | HTTP transport |
| playwright | 24 | 37,325 | | figma | HTTP transport |
| playwright-cdp | 24 | 29,409 | | github | HTTP transport |
| playwright-extension | 24 | 19,207 | | huggingface | HTTP transport |
| angr | 14 | 91,343 | | | |
| frida-mcp | 13 | 6,767 | | | |
| repomix | 8 | 19,328 | | | |
| scholarly-access | 8 | 7,326 | | | |
| qlty | 5 | 3,370 | | | |
| codex | 2 | 15,165 | | | |
| context7 | 2 | 39,044 | | | |
| searxng | 4 | 22,404 | | | |
| claude-code-mcp | 1 | 54,938 | | | |

Every FAIL is a *transport* limitation, not a broken server: an HTTP-mounted server has no
stdio command to spawn. Those are covered by §4 instead.

**Corroborations (independent methods agreeing, which raises confidence in both):**

* `cloud-hub = 424 tools` — measured here by `tools/list`, and by the grounding lane's
  separate `smoke_stdio.py` run earlier the same day. Both 424 against `impact.py`'s
  inherited `409`: **the constant is stale by +15 tools (+3.7%) in ~16 days.**
* `chrome-devtools = 29 tools` — now agreed by **three** mechanically different methods:
  this handshake, the session-namespace count, and `impact.py`'s constant.
* The 23-name mounted set reproduced exactly across two independent sessions.

**The grounding lane's "tools advertised, server down" shape is confirmed and refined.**
`brightdata`, `playwright-cdp`, `playwright-extension` are all mounted while
`claude mcp list` reports them FAILED. For the two playwright rails a real handshake now
returns 24 tools each, so the *host check* is the wrong signal, not the server.
`brightdata` remains genuinely unverified (§7).

## 4. In-session real calls (S4) — the HTTP transports

A stdio handshake cannot reach an HTTP-mounted server, so capability was verified by
executing a real read-only tool call from the auditing session:

| server | tool called | result |
|---|---|---|
| `agent-mail` | `health_check` | `status=ok` |
| `basic-memory` | `list_memory_projects` | 2 projects, default `main` |
| `figma` | `whoami` | handle + Full seat returned (email withheld from this artifact) |
| `github` | `get_me` | authenticated login returned |
| `huggingface` | `hf_whoami` | `status=anonymous` — server answered, so capability is live |

Declined deliberately, with the reason recorded per row in `disposition.json`:
`brightdata` (metered third-party API — a real call bills the owner), `deepwiki`
(third-party network AI service), `claude-code-mcp` (a call spawns a nested Claude).

**Finding — a health check that misreports its own listener.** `agent-mail`'s
`health_check` returns `http_port: 8811`. Two mechanically independent probes disagree:
`curl http://127.0.0.1:8811/api/health` returns **nothing**, while
`curl http://127.0.0.1:8812/api/health` returns `{"status":"ok", …}`. So the `http_port`
field does **not** identify the live HTTP listener; 8812 (the port `~/CLAUDE.md` documents)
is the one actually serving. Confidence in *the field disagreeing with the live listener*:
**almost certain (90-99%)** — two independent probes, zero counter-examples.
**UNVERIFIED — whether this is a stale field or a second instance** configured for 8811
that never binds. *Settling experiment:* compare the MCP-mounted server's pid against the
pid owning 8812 (`Get-NetTCPConnection -LocalPort 8812`); same pid ⇒ stale field, different
pid ⇒ two instances. Not acted on: this is a doc/tool surface outside this lane's scope.

## 5. Context cost — measured, in bytes

Both channels measured from the same `tools/list` payloads. `name_bytes` = the
names-only surface (this session's **deferred** regime); `schema_bytes` = the full tool
declaration as the server sends it, `name + description + inputSchema`, the **eager**
regime. Schemas were measured and deliberately **not stored**.

| server | tools | name B | schema B | share of eager | commit MB (direct child) |
|---|---|---|---|---|---|
| **cloud-hub** | 424 | 6,998 | **321,053** | **53.2%** | 16.3 |
| search-hub | 68 | 1,276 | 105,831 | 17.5% | 19.2 |
| paper-search | 57 | 866 | 43,457 | 7.2% | 1.0 |
| chrome-devtools | 29 | 378 | 21,971 | 3.6% | 6.9 |
| playwright | 24 | 410 | 18,441 | 3.1% | 6.7 |
| playwright-cdp | 24 | 410 | 18,441 | 3.1% | 6.9 |
| playwright-extension | 24 | 410 | 18,441 | 3.1% | 6.9 |
| repomix | 8 | 154 | 18,150 | 3.0% | 6.7 |
| angr | 14 | 189 | 8,196 | 1.4% | 0.9 |
| frida-mcp | 13 | 211 | 6,091 | 1.0% | 0.9 |
| searxng | 4 | 77 | 5,640 | 0.9% | 6.9 |
| context7 | 2 | 28 | 4,867 | 0.8% | 6.7 |
| scholarly-access | 8 | 144 | 4,707 | 0.8% | 0.9 |
| qlty | 5 | 67 | 3,013 | 0.5% | **69.3** |
| claude-code-mcp | 1 | 11 | 2,594 | 0.4% | 6.6 |
| codex | 2 | 16 | 2,340 | 0.4% | 6.5 |
| **TOTAL** | **707** | **11,645** | **603,233** | | |

* **`cloud-hub` alone is 53.2% of the eager surface and 60% of the deferred one.** It is
  the only row where a cost decision has leverage; the bottom eight rows together are 5%.
* **Cost rank ≠ RAM rank.** `qlty` is 0.5% of the tool surface and the heaviest resident
  child measured (69.3 MB); `paper-search` is 7.2% of the surface at 1.0 MB. `impact.py`
  is right to keep the two axes anti-correlated and unblended — this data reproduces that.
* **UNIT CAVEAT, inline:** the byte ratio here is **51.8x** (603,233 / 11,645). Do **not**
  quote that as the deferred-vs-eager *token* factor; `impact.py`'s ~14x is tokens with a
  different denominator (it charges `TOOL_BLOCK_OVERHEAD_TOKENS = 496` once per request,
  and its deferred figure is evidently more than bare names). The two are consistent where
  comparable — 321,053 B / 77,198 tokens ≈ 4.2 B/token is ordinary for JSON — but they are
  **not the same measurement**. *Settling experiment:* run one tokenizer over both channels
  of the same captured payload and report a token ratio; until then this table is bytes.

## 6. Duplication — computed, not judged

`overlap_report.py` does exact set arithmetic over the measured tool-name surfaces. An
exact question deserves an algorithm: this is set membership, so it is computed. 16
surfaces, 4 overlapping pairs, and only ONE is retirement-eligible.

| pair | shared | a-only | b-only | relation | eligible |
|---|---|---|---|---|---|
| `search-hub` × `searxng` | 4 | 64 | **0** | b ⊂ a | **`searxng`** |
| `playwright` × `playwright-cdp` | 24 | 0 | 0 | **identical** | none — INVESTIGATE |
| `playwright` × `playwright-extension` | 24 | 0 | 0 | **identical** | none — INVESTIGATE |
| `playwright-cdp` × `playwright-extension` | 24 | 0 | 0 | **identical** | none — INVESTIGATE |

**The three playwright rails have byte-identical tool-NAME sets — 24/24, zero unique on
either side — and are still NOT retirement-eligible.** Eligibility requires *strict*
containment, which identical sets are not: you must keep at least one, and choosing which
needs behavioural knowledge the names cannot carry. They target different browser contexts
(own browser / CDP attach / logged-in extension profile), and the memory note "browser
rail DEAD (Chrome-136 default-profile CDP break)" is why the variants exist at all. The
estate base rate is decisive here: 34 of 57 skill pairs *looked* like duplicates and zero
shared meaningful content. **Name identity is a necessary condition for retirement, never
a sufficient one** — that rule is encoded in `overlap_report.py`, not left to prose.

`searxng` ⊂ `search-hub` (4/4 contained, 0 unique) confirms the grounding lane's claim, now
by computed set arithmetic over two real `tools/list` surfaces rather than inference.

## 7. Disposition — 23/23 rows, reversible only

Full table with per-row evidence: **`docs/mcp-audit/DISPOSITION-TABLE.md`** (generated);
machine-readable: `command-center/mcp-audit/disposition.json`.

```
DISABLE 1   INVESTIGATE 2   KEEP 20
```

The four signals are emitted as four columns and **never collapsed into one boolean** —
collapsing is the measured error that over-counts the live fleet 2.3x.

**`REMOVE` is not a representable outcome.** `assert_reversible()` fails the run closed if
any disposition is not one of KEEP / DISABLE / INVESTIGATE, so every recommendation is
undone by re-enabling one JSON key.

* **DISABLE — `searxng` (1 row).** Evidence: all 4 tool names are a strict subset of
  `search-hub`'s 68, 0 unique, both surfaces measured. Nothing becomes unreachable.
  **Route it through `mcpapply`'s `DISABLE_PREFERENCE` (project-scoped), not root
  `disabledMcpServers`** — per `mcpapply/plan.py` `SPAWN_PREVENTING`, a root disable hides
  the tools but does **not** prevent the spawn, so it saves zero RAM. Executing this is a
  config mutation and therefore outside this lane's file scope (§9).
* **INVESTIGATE — `brightdata`** (mounted, host says FAILED, no real call: metered API) and
  **`deepwiki`** (config enabled, host Connected, mounted, no real call: third-party
  network). Both are honest gaps with the reason recorded, not silent passes.
* **KEEP — 20 rows**, each with either a handshake tool count or a named real call.

Worth flagging to the owner: **6 KEEP rows are `config_state != enabled`** — `chrome-devtools`,
`angr`, `context7`, `claude-code-mcp`, `searxng` (disabled) and `playwright-cdp`,
`playwright-extension` (pending-approval) — yet all are mounted and all pass a real
handshake. This is the same disagreement the grounding lane scoped as **uncertain (20-55%)**
between "the precedence model is wrong" and "17 days of config drift". This lane adds
capability evidence but **not** a resolution, and does not act on it.

## 8. Definition-of-Done ledger

**This ledger is executable.** `_r2_dod_check.py` re-derives all four verdicts from
`git show <rev>:command-center/mcp-audit/disposition.json` — the bytes that shipped, not
the working tree, because a working-tree check passes on an uncommitted edit no reviewer
will ever see. Each item also carries a **negative control**: the predicate is re-run
against a copy of the rows broken in exactly the way that item is meant to catch, and the
run fails unless the control fires. Without that, a predicate with a typo'd field name
would report PASS on all 23 rows by finding nothing to object to.

```
== DoD ledger, executed against 630bb8af:command-center/mcp-audit/disposition.json (23 rows) ==
  DoD1 PASS  inventory: scope + source file per row       negative control fires: True
  DoD2 PASS  liveness vs capability by a real call        negative control fires: True
  DoD3 PASS  per-server context cost measured             negative control fires: True
  DoD4 PASS  reversible recommendations with evidence     negative control fires: True
  summary: call_verified=21/23  dispositions={'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}
SUCCESS:dod-check 4/4 DoD items PASS, 4/4 negative controls fired
```

| DoD item | state | evidence |
|---|---|---|
| every mounted server inventoried with its **scope and source file** | **PASS** | 23/23 rows in `disposition.json` carry `definition_scope`, `source_file` (absolute), `config_basis`, `transport`. The 122 non-mounted config rows keep their scope/basis in `mcpctl-matrix.json`; they were deliberately not spawned. |
| **liveness distinguished from capability by a real call** | **PASS** | 21/23 verified: 16 by stdio `initialize`+`tools/list`, 5 by a real in-session tool call. 2 declined with the reason recorded. The four signals stay in four columns, and S4's two methods stay in three fields (`call_verified` = union, `handshake_verified` / `s4_executed` = the halves, `call_method` = which answered). Round 1 passed this item with a field that contradicted its own legend (§11 D1); the artifact now fails closed on that shape. |
| **per-server context cost measured** | **PASS** | §5: 707 tools, `name_bytes` + `schema_bytes` per server from the same payloads, ranked, with the bytes-vs-tokens caveat inline. Not inherited from any constant. |
| **recommendations reversible (disable, not remove) with evidence per row** | **PASS** | `assert_reversible()` makes REMOVE unrepresentable; every row carries an `evidence` sentence naming its measurement; the one DISABLE names the reversal mechanism and the scope that actually prevents a spawn. |

## 9. Explicitly NOT done in round 1

* **R1's real target — wiring the producer into `tools/mcpctl`'s four null fields and
  `tools/monitorcore`'s pane — was not attempted.** Both live outside this lane's declared
  file scope (`docs/mcp-audit/**`, `command-center/mcp-audit/**`). `probe_capability.py` is
  built as an *injectable* producer precisely so that wiring is a small diff later, and it
  lives outside the `mcpctl` package so its read-only AST gate is untouched.
  **Orchestrator decision needed.**

  > **REFUTED in round 1, corrected in round 2.** This bullet used to read "it emits
  > `tool_count` / `pid` / `commit_bytes` / `last_error`, the exact four fields
  > `mcpctl.matrix.Row` leaves null". It emitted **three** of the four by name:
  > `mcpctl`'s fourth is `rss_bytes` and the producer published the same number as
  > `working_set_bytes`, so an injection would have silently dropped memory. Fixed in
  > `process_memory()` — Windows has no RSS counter and `WorkingSetSize` is its documented
  > analogue (the mapping psutil uses for `rss` on nt), so the VALUE was right and only
  > the NAME was missing; both names are now emitted so the provenance survives the alias.
  > The claim is no longer prose: `_r2_redproof_invariants.py` part B constructs
  > `mcpctl.matrix.Liveness` from the producer's own row keys and requires all four to be
  > non-null on every row it checks, with a control that deletes `rss_bytes` and
  > confirms it goes red.
  >
  > > **REFUTED in round 3 — the wording, not the number.** This paragraph used to end
  > > "non-null on **every verified row (16/16)**". Round 2's *other* fix had just
  > > redefined `call_verified` to the **union** — 21 rows — so "every verified row" read
  > > as a claim about 21 rows while part B only ever examines the **16 stdio-handshake**
  > > rows (the only ones with a child process to sample); the other 5 verified rows
  > > cannot pass it and are not looked at. 16 is the right count for the right set and
  > > the check was never wrong; the *word* was borrowed from the sibling fix, which is
  > > the same legend-drifts-from-field failure D1 was. Scope is now stated in
  > > `_inject()`'s docstring and printed as `stdio-handshake rows` at run time. Two
  > > fixes landing in one round can drift against **each other** — round 2 checked each
  > > against its own evidence and neither against the other.
* **Executing the `searxng` disable** is a config mutation — out of scope, and it must go
  through `mcpapply` dry-run → backup → apply.
* **The 122 non-mounted rows** were not spawn-probed. Deliberate: spawning every configured
  entry is the anti-pattern this lane exists to avoid.
* **`impact.py`'s stale constants** were not edited (outside scope), but the drift is now
  measured twice: `cloud-hub` 409 → 424.

## 10. Artifacts

| path | contents |
|---|---|
| `command-center/mcp-audit/probe_capability.py` | the prober + 4-state fail-closed control |
| `command-center/mcp-audit/redproof_control.py` | 4/4 mutation red-proof of that control |
| `command-center/mcp-audit/overlap_report.py` | exact tool-surface set arithmetic |
| `command-center/mcp-audit/rank_disposition.py` | 4-signal join + disposition + reversibility invariant |
| `command-center/mcp-audit/_verify_blob_gate.py` | re-runs pinned ruff over the committed BLOBS + a mangled control |
| `command-center/mcp-audit/_verify_secrets_gate.py` | real gitleaks over the commit + a committed positive control |
| `command-center/mcp-audit/_diag_popen_cmd.py` | the measurement that settled detector failure #1 (PATHEXT) |
| `command-center/mcp-audit/_diag_mutation.py` | the measurement that settled detector failure #2 (tuple truthiness) |
| `command-center/mcp-audit/capability-matrix.json` | 23 rows, 150 s budget, control block included |
| `command-center/mcp-audit/capability-matrix-r2.json` | round-2 re-sweep; the rows that carry `rss_bytes` |
| `command-center/mcp-audit/capability-slowrows.json` | `angr` + `chrome-devtools` re-probe that refuted the 45 s FAILs |
| `command-center/mcp-audit/overlap-report.json` | 16 surfaces, 4 pairs, 1 eligible |
| `command-center/mcp-audit/disposition.json` | the ranked table, machine-readable |
| `docs/mcp-audit/DISPOSITION-TABLE.md` | the ranked table, rendered |
| `command-center/mcp-audit/_r2_reproduce.py` | reproduces D1 + D2 **before** the fix |
| `command-center/mcp-audit/_r2_redproof_invariants.py` | both-states red-proof of both round-2 fixes |
| `command-center/mcp-audit/_r2_corroborate.py` | round-1 vs round-2 sweep, count **and** name sets, with a control |
| `command-center/mcp-audit/_r2_ruff_census.py` + `ruff-census.json` | the D3 disclosure as a scoped, timestamped measurement |
| `command-center/mcp-audit/_r2_dod_check.py` | the §8 DoD ledger, executed against the COMMITTED blob, 4 negative controls |
| `docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md` | the round-2 ledger: one row per confirmed defect |

Reproduce, in order:

```
python command-center/mcp-audit/probe_capability.py --control
python command-center/mcp-audit/redproof_control.py
python command-center/mcp-audit/probe_capability.py --mounted --timeout 150 \
    -o command-center/mcp-audit/capability-matrix.json
python command-center/mcp-audit/overlap_report.py \
    command-center/mcp-audit/capability-matrix.json \
    command-center/mcp-audit/capability-slowrows.json \
    -o command-center/mcp-audit/overlap-report.json
python command-center/mcp-audit/rank_disposition.py \
    -o command-center/mcp-audit/disposition.json \
    --md docs/mcp-audit/DISPOSITION-TABLE.md
python command-center/mcp-audit/_r2_redproof_invariants.py
python command-center/mcp-audit/_r2_corroborate.py
python command-center/mcp-audit/_r2_ruff_census.py
```

## 11. Round-2 defect closure — what a verifier refuted, and what changed

An independent verifier re-ran every DoD item in round 1 and returned **PARTIAL**: all four
DoD items PASS when executed, but three defects survived. None was a wrong measurement.
All three were the estate's dominant failure shape — **a sentence wider than its evidence**.
Full ledger with the pre-fix reproduction: `docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md`.

| # | what round 1 shipped | verdict | what changed |
|---|---|---|---|
| D1 | `disposition.json` documented `call_verified` as "handshake **or** a real in-session tool call" while computing it from the handshake alone — 5 rows sat at `false` beside their own non-null `s4_executed`, and the prose said 21 while the field summed to 16 | **CONFIRMED** — a self-contradiction inside the machine-readable artifact | `call_verified` is now the union; `handshake_verified` / `s4_executed` keep the halves visible; `call_method` names which probe answered; `assert_signal_consistency()` aborts the run on any row that disagrees with its own evidence, **and** on a legend that stops advertising both methods |
| D2 | "emits **exactly the four fields** `mcpctl.matrix.Row` leaves null" | **CONFIRMED overclaim** — three of four by name; `rss_bytes` was published as `working_set_bytes` | producer emits `rss_bytes` (the value was already correct — see §9); the claim is now executed, not asserted |
| D3 | "the repo-wide ruff format gate is RED with 60 files … zero are mine" | **CONFIRMED disclosure-accuracy defect** — the verifier measured 51 for the same claim | see below |

**D3 in full, because the correction is the interesting part.** Neither 60 nor 51 was
wrong. Four readings of the same repo-wide count, all correct at their timestamps:

| reading | count |
|---|---|
| round-1 build | 60 |
| round-1 verifier | 51 |
| round-2 open | 46 |
| round-2 close (`ruff-census.json`) | 27 |

A dozen sibling lanes commit into this worktree while the audit runs, so the absolute
repo-wide count is a **moving target and not a reportable fact** — quoting it without a
timestamp manufactures a disagreement between two honest observers. The stable claim is
the scoped one, so `_r2_ruff_census.py` reports **in-scope vs out-of-scope by owner**, with
a UTC stamp, and its exit code is driven by the in-scope count alone: **0 offenders under
`docs/mcp-audit/` + `command-center/mcp-audit/`** at 2026-08-13T03:33:57Z. Failing this
lane on a sibling's file would repeat the original error — a number whose scope does not
match the claim.

**What did NOT change: the verdicts.** DISABLE 1 / INVESTIGATE 2 / KEEP 20 is byte-identical
before and after, and the round-2 re-sweep agrees with round 1 on 16/16 tool counts and name
sets. Confidence that the three fixes are complete: **almost certain (90-99%)** — each was
reproduced before the fix, and each fix has a control observed to fire in the known-broken
state. Confidence that no FOURTH defect is hiding in the same artifact: **uncertain
(20-55%)** — I closed the three the verifier found; I did not re-derive the artifact from
scratch, and the settling experiment is another independent verify pass, not another
self-review.

## 12. Round-3 defect closure — round 2's two fixes drifted against each other

That settling experiment was run. Full ledger, with the pre-fix reproduction pinned to the
round-2 commit `630bb8af`: [`ROUND3-DEFECT-CLOSURE.md`](ROUND3-DEFECT-CLOSURE.md).

> **Provenance, stated up front:** the round-2 verifier's report did not reach the build
> lane — the handoff truncated inside the *round-1* audit text. The three below were
> re-derived by an independent execution pass, not transcribed from a verifier. If round 2's
> verifier confirmed something this pass did not rediscover, **it is still open.**

| # | what round 2 shipped | verdict | what changed |
|---|---|---|---|
| E1 | 5 rows carried `call_verified: true` beside `last_error: "transport='http': no stdio command"` — widening `call_verified` to the union (D1) left `last_error` at its old meaning | **CONFIRMED** — a self-contradiction in the machine-readable artifact, in one of the four fields `mcpctl.matrix.Liveness` reads | `liveness_basis` on every row; the categorical case moved to `probe_note`; `assert_liveness_consistency()` aborts on 4 shapes, red-proofed by 5 mutations incl. the literal round-2 row |
| E2 | "a row of the shipped table **is** an injectable snapshot", and part B reported "every **verified** row (16/16)" after *verified* had been redefined to mean 21 | **CONFIRMED overclaim** — true for 16 of 23 rows; the other 7 inject as four nulls | both sentences scoped in place (refuted wording kept, not deleted); `_inject()` prints its scope as `stdio-handshake rows`; residual disclosed inline with its settling experiment |
| E3 | `dod3` skipped every row without a handshake, so "per-server context cost measured" PASSED while 7 of 23 rows carried no cost — and its one control could only exercise the covered branch | **CONFIRMED** — a control that cannot distinguish the two hypotheses | predicate widened to every row (a null is legal only beside a stated reason); a second control `strip-reason-from-unmeasured-row` fires; the ledger is now red on `630bb8af` and green on HEAD |

All three are one family, and it is round 1's family: **a claim drifting from the thing it
describes.** The new variant is that round 2 landed two fixes in one round and checked each
against its own evidence, never against the other. Verdicts unchanged again: DISABLE 1 /
INVESTIGATE 2 / KEEP 20.

One hypothesis was **REFUTED** and is recorded rather than dropped: the round-1 and round-2
sweeps are byte-identical on every cost field (707 tools / 11,645 name B / 603,233 schema B
on both), so no doc figure was stale.
