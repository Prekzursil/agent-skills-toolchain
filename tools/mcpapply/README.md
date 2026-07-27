# mcpapply — the MUTATION sibling of `mcpctl`

`mcpctl` is the **read** core: the five on-disk MCP configuration scopes, their measured
precedence, the object-shaped `deniedMcpServers`, the exact-cwd `projects` row,
credential-name-only redaction, and a health matrix. It is read-only **by
construction** — one of its tests walks the AST of every module in the package and
fails on any write call, any out-of-process call, and any `http` / `socket` / `urllib`
import.

`mcpapply` imports it and owns everything that **changes** something:

| capability | module |
|---|---|
| plan a mutation: current state → desired state → an explicit diff | `plan.py` (pure) |
| apply a plan to the config files, through an injected filesystem port | `apply.py` |
| fail-closed write preconditions (running host, USER-scope human gate) | `guard.py` |
| timestamped sidecar backup + the printed restore command | `backup.py` |
| the stream-json `control_request` channel, behind an injected transport port | `live.py` |
| token / RAM impact preview that never renders "not measured" as `0` | `impact.py` |
| a loopback-only stdlib web GUI (no framework, no CDN, no daemon) | `server.py` + `static/` |
| the CLI | `cli.py` |

Splitting rather than extending is not stylistic: the writer, the process probe and the
GUI would each break the mechanical gate that makes `mcpctl` trustworthy to read from.

---

## Safety contract

This package **mutates the owner's live MCP configuration.** It is treated as
destructive throughout.

1. **DRY RUN IS THE DEFAULT.** `apply_plan(...)` writes only when the caller passes
   `apply=True`; the CLI writes only with `--apply`; the GUI writes only when the
   request body carries a literal `{"confirm": "APPLY"}`. The default parameter value
   *is* the mechanism, so `tests/test_mutations.py` asserts on the **signature** as
   well as on the behaviour — the estate has a recorded case of a suite staying green
   while a default was reverted, because every test passed the value explicitly.
2. **Backup before write**, to `<target>.mcpapply-<UTC stamp>.bak` beside the original,
   with the restore command printed for PowerShell *and* bash.
3. **The curation is load-bearing and is never wiped.** A document is `deepcopy`-ed,
   exactly one key path is mutated, and the copy is re-serialised. The model is never
   rebuilt from a parsed view, so an oauth blob, a project history or a disable list
   this tool has never heard of survives because it is literally the same value object,
   moved. A container of the wrong shape is **reported and skipped**, never coerced.
4. **Fail closed.** A process listing that errors means "a host may be running", not
   "go ahead". `--force` accepts the live-session race; it does **not** touch the
   recorded human gate for USER-scope promotion, which only the operator closing the
   host can satisfy.
5. **Stale-write refusal.** Every running host session rewrites `~/.claude.json`
   continuously. Each target is re-read immediately before the write and the write is
   REFUSED if the bytes moved since the preview.
6. **No credential value can be captured.** Not by filtering — structurally: the only
   `env` representation in the model is `mcpctl.safety.EnvField` (a name plus
   present/absent/reference). Free text additionally goes through `mcpctl.safety.safe`,
   which strips control bytes **then** redacts; reversing that order is a proven
   credential-leak bypass, not a style choice.

---

## The inverse scope map

`mcpctl.scopes.PRECEDENCE` answers "given these scopes, what state wins". Mutation
needs the inverse — "to reach state X, which scope do I write?" — and the two must
never disagree, so the inverse is **derived** from `PRECEDENCE` rather than restated.

* **Disabling needs ONE suppressor.** Any single one wins.
* **Enabling needs ALL of them cleared.** Removing from one while another still lists
  the server is a no-op the operator will read as a failed enable, so `plan_enable`
  emits one edit per suppressing scope and says so.

Which suppressor a plain `disable` writes is a **measured** choice (controlled A/B in a
sandboxed `CLAUDE_CONFIG_DIR`, single variable):

| write target | server process at next start | RAM saved |
|---|---|---|
| `projects[<exact cwd>].disabledMcpServers` | **not spawned** | yes |
| root `disabledMcpServers` | **still spawned** | **no** |

So a disable written to the root list really disables the tool surface but buys no
memory, and `impact.py` reads `plan.SPAWN_PREVENTING` to say so instead of crediting
every disable with a saving.

---

## Budgeting: two axes, never fused

Measured on this box, token cost and memory cost are **anti-correlated**:

| server | tools | tokens | commit |
|---|---:|---:|---:|
| `cloud-hub` | 409 | **77,198** | 17 MB |
| `chrome-devtools` | 29 | — | **331 MB** |

A single blended "cost" score would recommend disabling exactly the wrong server, so
the preview reports two independent deltas.

Other measured facts encoded in `impact.py`:

* Per-server token costs are **exactly additive** (overhead-corrected prediction matched
  measurement with error 0 across two multi-server combinations), so summing deltas
  carries no modelling error.
* The 496-token tool block is charged **once per request**, and is credited only when a
  plan removes the last tool-bearing server.
* The cheap proxies are bad — tokens-per-tool spans 12.5×, bytes-per-token 2.2× — so a
  proxy number always carries its `TokenBasis` and can never pass as a measurement.
* Deferred tool loading changes the arithmetic by ~14×, so the regime is an explicit
  input and is printed with the number.
* Memory is reclaimed at the **next** session start, never "freed now".
* **An unmeasured cost renders `-` / `null`, never `0`.** Any aggregate over an
  incomplete set is marked a LOWER BOUND and names what it could not account for.

---

## Live control — what is proven, and what is not

The transport is the stream-json `control_request` channel. Two corrections to the
folklore are encoded in `live.AFFORDANCES` and enforced by the mutation probe:

* `mcp_toggle` is **not "any scope"**. Project scope (`.mcp.json`) is a recorded CLEAN
  NEGATIVE — connected before the disable, connected after. Dynamic is proven twice,
  user scope once (sandbox only, marked provisional). An unrecorded pair defaults to
  UNPROVEN, i.e. the UI does not offer it.
* `mcp_toggle` is a **persistent config write**, not an in-memory flip: it edits
  `~/.claude.json → projects[<the control session's cwd>].disabledMcpServers`. So the
  live lane mutates the same file the config lane does, it cannot be previewed through
  the control channel (issuing it *is* the write), and the write lands under the
  **control session's** cwd — which is why `SubprocessTransport` takes an explicit
  `cwd` rather than inheriting the caller's.

Also encoded: the payload is **double** nested (`msg["response"]["response"]`; the
un-guarded read produced a confident false negative), `response` is absent entirely on
reconnect/toggle, `mcp_set_servers` REPLACES the dynamic set, a partial failure is a
*success* frame with a populated `errors` map, and frames arrive interleaved and
possibly out of order — so the reader is a demultiplexer keyed on `request_id`.

**UNVERIFIED on the installed build.** The evidence campaign was build-verified on
Claude Code **2.1.214**; the installed binary has since moved to **2.1.220**. The wire
contract re-verifies statically (the zod schemas extracted from the installed binary
are byte-identical), but no behavioural cell was re-measured on 220 by this work unit
and none is claimed. The settling experiment is one deliberate run of
`pytest -m live` against a real session — default-deselected precisely because it
spawns a host, costs a 104–275 s cold boot, and persists a write.

---

## The web GUI

`python -m mcpapply gui` — stdlib `http.server` plus hand-written HTML/JS/CSS. No
framework, no CDN, no npm, no build step, **no network request off the loopback**, and
**zero resident cost when closed**: there is no daemon, no service and no scheduled
task.

* Binds `127.0.0.1` on an ephemeral port and **refuses** any other bind address.
* Rejects non-loopback `Host` headers — the loopback bind alone does not stop DNS
  rebinding.
* Requires a fresh per-run bearer token on **every** API route, reads included: the
  inventory names credential-bearing servers.
* Server-renders the matrix (works with JavaScript disabled) with everything passed
  through `safe()` then `html.escape(..., quote=True)`; the static JS assigns
  `textContent` only, and a test asserts that mechanically over the shipped asset —
  after stripping comments, because the asset documents the very sinks it bans.

---

## Usage

```bash
# preview (writes nothing, sends no control frame)
python -m mcpapply disable cloud-hub --project "C:/Users/me/proj"

# commit that exact diff
python -m mcpapply disable cloud-hub --project "C:/Users/me/proj" --apply

# with measured costs, so the impact preview shows numbers instead of '-'
python -m mcpapply disable cloud-hub --costs costs.json --tool-search "$ENABLE_TOOL_SEARCH"

# the GUI
python -m mcpapply gui
```

Verbs: `enable` · `disable` · `add` · `remove` · `edit` · `reconnect` · `gui`.
Every one is dry-run until `--apply`.

---

## Gates

```bash
pip install -e ../mcpctl && pip install -e ".[dev]"
pytest -m "not live" --cov=mcpapply --cov-branch --cov-report=term-missing --cov-fail-under=100
basedpyright mcpapply
ruff check . && ruff format --check .
```

Measured 2026-07-27: **223 passed, 1 deselected, 100.00 % line+branch, 0 basedpyright
findings, ruff clean, gitleaks clean, the repo SAST ruleset clean, ZERO
`# pragma: no cover` in package source.**

`tests/test_mutations.py` reverts 24 load-bearing decisions one at a time and requires
each to be caught, with a control test proving every check is green unmutated —
coverage alone does not prove behaviour.

Reproduce the coverage gate with the venv's `pytest` **console script**, never
`python -m pytest`: the `-m` form prepends the CWD to `sys.path` and passes in both
states, so it cannot detect a missing editable install.
