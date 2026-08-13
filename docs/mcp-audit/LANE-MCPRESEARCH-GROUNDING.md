# LANE MCPRESEARCH — Grounding report (round 2)

Measured 2026-08-13, worktree `C:/Users/Prekzursil/source/ast-integrate`, HEAD `27da3215`.

**This lane already ran.** A prior MCPRESEARCH grounding pass shipped at `ae8205a4`
(`command-center/mcp-audit/AUDIT-SUMMARY.json`, `"lane": "MCPRESEARCH"`), then four
defect-closure rounds and a CI integration landed on top of it. The single most valuable
thing this round can do is stop a build lane rebuilding it — so §1 is the prior-art census
and §2-§7 are only what is NEW or has CHANGED since.

COVERAGE: every claim below carries executed output. **NOT measured:** 7 of 12 cloud-hub
backends; the 7 HTTP-transport rows' tool surfaces; whether `mcp-audit.yml` behaves on a
real GitHub runner; the `mcpctl` precedence question. Each is named with its settling
experiment in §8.

If it still reads this way, the unit died before measuring anything and no verdict here may
be cited. — *it does not; every section quotes a real exit code or a real tool response.*

---

## 1. Prior art — DO NOT REBUILD

Five of six audit axes already ship, tested and CI-wired. Executed at HEAD today:

```
$ python command-center/mcp-audit/ci_gate.py
== mcp-audit CI gate @ 27da321554cf (win32, py 3.14.6) ==
  ok  inventory: 15 planned runs over 14 gates, 18 excluded with reasons
  ... 15/15 gates behaved ...
  ok  disposition.json     byte-identical to the committed blob (29172 B)
  ok  overlap-report.json  byte-identical to the committed blob (3738 B)
SUCCESS:mcp-audit-ci-gate 15/15 gates behaved, 2/2 artifacts byte-identical
EXITCODE=0
```

That is a **third** platform for the portability claim: the lane measured Ubuntu 24.04 /
py3.12 and CI pins py3.11; this run adds win32 / py**3.14.6**.

The pin itself was then run, because a sibling had *just* landed `dfea977d fix(mcp-audit):
commit the 3.11 f-string fix the lane wrote but never landed` — i.e. this lane had already
shipped one py3.11 `SyntaxError`, so "3.11 is probably fine" was not available as an
assumption:

```
$ py -3.11 command-center/mcp-audit/ci_gate.py
SUCCESS:mcp-audit-ci-gate 15/15 gates behaved, 2/2 artifacts byte-identical
EXITCODE=0
```

**Four Python versions across two OSes now agree** (3.11 CI-pinned + 3.12 + 3.14.6, win32 +
Ubuntu 24.04). Residual §8.2 narrows to the runner ENVIRONMENT alone; the interpreter-version
risk is now measured rather than assessed.

| axis | artifact | state |
|---|---|---|
| inventory + scope + precedence | `tools/mcpctl` (100% line+branch, read-only AST gate) | **DONE — reuse** |
| mutation + cost basis | `tools/mcpapply` (dry-run default, `DISABLE_PREFERENCE`) | **DONE — reuse** |
| liveness/capability producer | `command-center/mcp-audit/probe_capability.py` | **BUILT since the last summary** |
| ranked disposition | `rank_disposition.py` → `disposition.json` (23 rows) | **DONE — reuse** |
| duplication | `overlap_report.py` → `overlap-report.json` (set arithmetic) | **DONE — reuse** |
| resource census | `_probe_process_census.py` | **DONE — re-measure only** |
| CI reachability | `.github/workflows/mcp-audit.yml` + `ci_gate.py` | **DONE — 14 gates wired** |

`AUDIT-SUMMARY.json` R7 already says it in the negative: **do not build** a new inventory
tool, scope reader, redaction layer, mutation/GUI layer, a source-static tool counter (tried,
refuted — it read 129 where the truth was 424), or a `claude mcp list` wrapper as a health
source. That list is still correct.

**The one gap the prior lane named is still open:** R1, wiring the producer into `mcpctl`'s
four null fields (`matrix.py:32-35`). The injection seam already exists — `build_rows(...,
liveness: Mapping[str, Liveness])` at `matrix.py:77` reads `live.tool_count / last_error /
pid / rss_bytes`. Nothing produces that mapping. It remains **out of this lane's file scope**
(`docs/mcp-audit/**`, `command-center/mcp-audit/**`).

## 2. Zero fleet drift — two independent instruments

The disposition table is 23 rows measured 2026-08-12/13. This session's own mounted namespace
is a mechanically different producer (the client's deferred-tool listing, built from live
config at session start, a different day).

```
$ python command-center/mcp-audit/_g2_drift_probe.py
  ok  differ control fired (sees both an injected name and a withheld one)
  artifact rows (disposition.json) : 23
  session namespace (this session) : 23
  in artifact but NOT mounted here : (none)
  mounted here but NOT in artifact : (none)
  dispositions                     : {'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}
SUCCESS:g2-drift 23/23 names agree across two independent instruments
```

The differ is checked in **both directions** before it is trusted, and against a mangled pair
first — a one-directional read is exactly how a divergence gets scored as agreement.

**Confidence: almost certain (90-99%)** that the disposition table still describes the
mounted fleet.

## 3. NEW — the capability gap is ~60x larger than the audit's worked example

Round 5 correctly narrowed `call_verified` to "the process starts and **advertises** a tool
surface", with `searxng` (4 advertised tools over a dead SearXNG instance) as the
counter-example. **That example understates the problem by two orders of magnitude.**

`cloud-hub` is the largest row in the fleet and is not one server — it is a proxy over 12
backends, each independently able to die while its tools stay listed. This is not inference;
it is what the server says when a dead backend is called:

```
[cloud-hub] backend 'rclone (rclone-mcp over rcd)' is unavailable: initialize failed:
deadline exceeded. Its other tools stay listed; fix the credentials/login for that
backend and restart the session.
```

Five backends probed by real in-session read-only calls, **four distinct failure modes**:

| backend | probe | verdict | evidence |
|---|---|---|---|
| rclone | `core_version` | **DEAD** | backend init: deadline exceeded |
| RunPod | `list-gpu-types` | **DEAD** | backend init: deadline exceeded |
| Modal | `modal_whoami` | **HANG** | no answer in 600 s — the tool timed out, no terminal state at all |
| Databricks | `dbx_current_user` | **AUTH-DEAD** | server answered; `PermissionDenied: Invalid access token` (PAT expired) |
| Biomni | `bm_whoami` | **DEAD** | local broker refused connection (WinError 10061) |

```
$ python command-center/mcp-audit/_g3_backend_liveness.py
  ok  C2 classifier refuses a non-cloud-hub name
  ok  C1 classified 424/424
  databricks   71   AUTH-DEAD | rclone 62 DEAD | runpod 56 DEAD | modal 47 HANG | biomni 31 DEAD
  ok  C3 dead-surface total agrees on two independent sums (267)
  MEASURED-DEAD advertised surface: 267/424 tools (63.0%), ~202,173 B of schema
  SCOPE: 5 of 12 backends were probed. The unprobed ones are NOT claimed live.
```

The C1 unclassified-tail control earned itself immediately: it surfaced 7 RunPod plural
verbs (`list-pods`, `list-tags`, …) the suffix matcher missed, which would have
**under**-reported the dead surface. A bucket percentage with an unclassified tail is fiction.

**External SOTA names this shape: "zombie servers" — processes that exist but cannot perform
work**, the failure a `/health` 200 cannot see and only a real capability call catches
([MCPcat](https://mcpcat.io/guides/building-health-check-endpoint-mcp-server/),
[Fastio](https://fast.io/resources/implementing-mcp-server-health-checks/)). The lane's
four-signal model (config / host / mounted / real-call) is the right decomposition; this
finding says the fourth signal must be **per-backend** for proxy rows, not per-server.

**Confidence: almost certain (90-99%)** for the five probed backends.
**UNVERIFIED** whether the other 7 (kaggle, ovh, azure, aws, lightning, compute-unified,
gcloud — 157 tools) are live; they are unmeasured, NOT assumed live. *Settling experiment:*
one cheapest read-only call per backend, same shape as above, recorded into a committed JSON
that `rank_disposition.py` READS.

## 4. NEW — the searxng DISABLE holds, but its evidence sentence is too wide

`DISPOSITION-TABLE.md` justifies the only config-mutation recommendation in the fleet with:

> *exact set arithmetic: all 4 tool names are a strict subset of search-hub's surface,
> 0 unique — **nothing becomes unreachable***

The set arithmetic is correct. The clause a reader takes away — *search-hub still covers it* —
is not. Both copies were called this session and returned **byte-identical failure against the
same backend**:

```
mcp__searxng__searxng_instance_info    -> available:false, 127.0.0.1:8890 unreachable
mcp__search-hub__searxng_instance_info -> available:false, 127.0.0.1:8890 unreachable   (identical)
```

Their tool *descriptions* are byte-identical too. This is a C2-class **overclaim, not a wrong
verdict**: DISABLE stays correct — arguably more so. Fix the sentence, keep the disposition.
Suggested scoping: *"0 unique names, so disabling removes no reachable capability — note the
4 duplicated tools are non-functional on **both** sides (shared dead instance at
`127.0.0.1:8890`), so this is deduplication of a dead capability, not a failover."*

Two further rows moved from handshake-only to **capability-verified** at no cost:
`angr` (`list_projects` → `{"count":0}`), `frida-mcp` (`enumerate_devices` → 3 devices).
Also re-confirmed live: `qlty` (0.502.0), `repomix`, `scholarly-access` (real OA resolution).

## 5. NEW — resource axis regressed materially in 24 h, and it survives normalization

`_probe_process_census.py` re-run today. Its own detector control passed (own pid visible,
nonsense token 0 matches, known cloud-hub matched 7).

| metric | 2026-08-12 (audit) | 2026-08-13 (now) | Δ |
|---|---|---|---|
| MCP processes | 238 | **376** | +58% |
| commit | 8.51 GB | **16.03 GB** | +88% |
| redundant processes | 126 | **255** | +102% |
| npx-cli.js copies / commit | 28 / 2.32 GB | **44 / 3.69 GB** | +57% |
| agent sessions | 8 | 9 (5 claude + 4 codex) | +13% |

The prior lane's R6 said to normalise to **copies-per-session** because absolute counts drift.
Doing so does **not** rescue the number — the regression is not explained by session count:

* processes/session **29.8 → 41.8** (+40%)
* commit/session **1.06 GB → 1.78 GB** (+68%)

This matters beyond tidiness: the documented freeze root cause on this box is **commit
exhaustion**, not RAM OOM. 16 GB of MCP commit is the hazard, not a statistic.

**The top RAM consumer is not even a mounted server.** `markitdown-mcp` holds **2,511 MB
across 8 copies** and is absent from all 23 rows of the session namespace. So are `ralph mcp
serve` (5), `excel-mcp-server` (5), `codacy-mcp` (5), `tavily-mcp` (5). This is the executable
corroboration of the audit's `SPAWN_PREVENTING` finding (`mcpapply/plan.py:107`): **a root
`disabledMcpServers` entry does not prevent the spawn.** Any RAM recommendation that writes
there saves zero bytes.

## 6. Cost — rank by the cost the fleet actually pays

`schema_bytes` is the obvious ranking key and it is the **wrong** one for this client. Claude
Code defers MCP schemas once tool descriptions exceed ~10% of the context budget
([MCP.Directory](https://mcp.directory/blog/mcp-context-bloat-fix-2026-tool-search-code-mode-progressive-disclosure)),
and this session is demonstrably in that regime — the injected listing is **names only**.

```
$ python command-center/mcp-audit/_g4_cost_rollup.py
  fleet tools 707 | name bytes 11,645 | schema bytes 603,233   (16 of 23 rows sampled)
  contingent/resident ratio: 51.8x
  cloud-hub  424  6,998 B  60.1%  |  search-hub 68 1,276 B 11.0%  |  paper-search 57 866 B 7.4%
  ok  CONTROL: 12/16 rows change rank between the two cost bases -- load-bearing, not decorative
  RESIDENT ~2,911 tok/turn (rough 4 B/tok); CONTINGENT 150,808 tok if every schema were loaded
```

The control matters: if the two bases ranked identically the distinction would be decorative.
12 of 16 rows move.

**Combine §3 and §6 for the actual headline:** `cloud-hub` is 60.1% of the fleet's every-turn
resident MCP cost, and **63% of that row is advertised over a backend measured non-functional**
— roughly **4,400 B / ~1,100 tokens paid on every single request for tools that cannot run.**

Context for the fleet size: industry consensus in 2026 puts the practical ceiling at **5-7
connected MCP servers** before degradation ([Albato](https://albato.com/blog/publications/embedded-mcp-context-bloat-hallucinations),
[StackOne](https://www.stackone.com/blog/mcp-token-optimization/)). This fleet mounts **23**.
Deferred loading is what makes that survivable — it is a mitigation, not a licence.

## 7. Security — report only, change nothing

Method unchanged from the prior lane: variable NAMES and present/absent only; no value read,
printed, or modified.

* **The Databricks PAT is expired.** `dbx_current_user` returned `PermissionDenied: Invalid
  access token` from the live workspace. **Owner action per AGENTS.md §9 — this lane does not
  rotate, and did not.** A documented non-destructive restore path exists (hub tools
  `db_account_remove` → `db_account_add` → `db_account_switch`; hand-editing `accounts.json`
  clobbers it from stale in-memory state).
* The error body echoed host / account_id / workspace_id and a **server-side-redacted**
  `token=***`. Those identifiers are deliberately not reproduced here.
* **Operational hazard, new:** `modal_whoami` consumed the full **600 s** MCP tool timeout and
  returned no terminal state. A hung backend inside a proxy row blocks the caller for the
  entire timeout — worse than a clean failure, and invisible to any health ping.
* Unchanged and still true: **`claude mcp list` SPAWNS every configured server**, including
  disabled and third-party npx ones. It is not a read-only diagnostic and must not be used as
  a health source.

## 8. Residual — named, with settling experiments

1. **7 of 12 cloud-hub backends unprobed** (157 tools). → one cheap read-only call each.
2. **`mcp-audit.yml` has never run on a real GitHub runner.** Narrowed, not closed: the gate
   is green on CI's exact pin (3.11) plus 3.12 and 3.14.6, on win32 and Ubuntu 24.04, so the
   interpreter-version risk is measured. What remains unmeasured is the runner ENVIRONMENT
   (network egress, clean checkout, Actions-provided git). → first `workflow_dispatch`.
3. **R1 still open:** producer → `mcpctl` four null fields + `monitorcore` pane. Out of scope
   here. The §3b blocker (producer not reproducible off the owner's box) is already removed.
4. **`S4_EXECUTED` is still a hand-typed dict of literals** inside `rank_disposition.py:107` —
   a claim living inside the thing it certifies. This round's calls should land in a committed
   JSON the producer READS, not as more literals.
5. **14 of 23 rows still have no capability-in-use evidence** (was 15/16 before this round's
   angr + frida-mcp + the cloud-hub backend map).
6. **The 5-7 server ceiling is an external consensus figure, not a local measurement.** No
   degradation was measured on this box. Cited as context, not as a finding.

## 9. Detector note — `git show | grep $'\r'` in Git Bash is a false-positive CRLF check

Recorded because round 4 of this lane spent itself on a false CRLF claim, and this round
nearly published a second one. Verifying the new commit, `grep -c $'\r'` over
`git show HEAD:<path>` reported **CR on every file** — including `ci_gate.py`, a blob
`_r4_selfcheck` had *just* certified as 0-CRLF in the same run. Two claims that cannot both
be true is a detector failure, not a finding.

Controlled by reading the same blob byte-wise instead of through a Git Bash pipe:

| path | `git show \| grep -c $'\r'` | `git cat-file -p \| grep -c $'\r'` | python, byte count |
|---|---|---|---|
| `ci_gate.py` | 340 | 340 | **CR=0** |
| `_g2_drift_probe.py` | 128 | — | **CR=0** |
| `LANE-MCPRESEARCH-GROUNDING.md` | 258 | — | **CR=0** |

`git show` and `git cat-file` **agreed with each other and were both wrong** — the MSYS pipe
re-inserts CR, so the grep measures the pipe, not the blob. The repo convention
("`git show`/`git cat-file` return the stored blob, 0 CRLF") is correct *at the byte level*;
it stops being true the moment the output crosses a Git Bash pipe into `grep`. Read blob bytes
in Python (`subprocess` + `.count(b"\r")`), never `git show … | grep`.

---

*Artifacts produced by this round (all read-only probes, no config or credential touched):*
`command-center/mcp-audit/_g2_drift_probe.py`, `_g3_backend_liveness.py`, `_g4_cost_rollup.py`,
refreshed `process-census.json`.
