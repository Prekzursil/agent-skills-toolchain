# LANE MCPRESEARCH — BUILD round 1

Executed 2026-08-13. Every number below was produced by running the thing, and every command
is reproducible from the repo root. Where something was not measured it says so.

## What shipped

| # | Plan item | State | Where |
|---|---|---|---|
| P1 | 4th signal per-BACKEND, read from committed data | **DONE** | `s4-evidence.json`, `s4_evidence.py`, `backend_map.py`, `rank_disposition.py` |
| P2 | Cost ranked by RESIDENT + dead-surface-adjusted column | **DONE (lane-scoped)** | `cost_rank.py`, `cost-rank.json` |
| P4 | Scope the searxng DISABLE sentence (C2 overclaim) | **DONE** | `rank_disposition.decide()`, regenerated `DISPOSITION-TABLE.md` |
| P3 | Resource regression | **NOT DONE this round** — reporting only, see Residual |
| P5 | Wire producer into `mcpctl` | **OUT OF FILE SCOPE** — `tools/mcpctl/**` is not this lane's |
| P6 | Databricks PAT | **OWNER ACTION** — not touched, not read, not printed |

**No disposition moved.** DISABLE 1 / INVESTIGATE 2 / KEEP 20, identical to the pre-build
table. This round changed what the rows can *say*, not what they *decide*.

## P1 — the fourth signal is now data, and it is per-backend

`rank_disposition.S4_EXECUTED` was a dict literal inside the producer: a claim living
inside the thing that certifies it, undated, unattributed, and structurally unable to say
*which backend* of a proxy answered. It is now `s4-evidence.json` — 17 records, each
carrying tool, verdict, result, backing resource, date, and author.

**The loader fails closed.** A missing or malformed file raises; it never degrades to "no
S4 evidence". That direction is the one that actually bites — an absent source is zero
signals, not one, and the measured version of that bug is a gate whose missing
`source_probe` normalised to empty strings and therefore certified corroboration for claims
that declared no measurement at all.

**The validator caught its own author.** First run against the file I had just written:

```
FAILED:s4-evidence ... invalid:
  agent-mail/- result is empty or too short to be evidence ('status=ok')
  qlty/-      result is empty or too short to be evidence ('PASS')
```

Both were migrated verbatim from the old dict. `"PASS"` is not evidence. Fixed the
sentences to state what the recorded measurement does and does not support, rather than
lowering the threshold.

**New first-hand measurements** (real read-only in-session calls, this session):

| server / backend | tool | verdict | what came back |
|---|---|---|---|
| `angr` | `list_projects` | live | `{"count":0,"projects":[]}` — proves tool execution, **not** that a binary can be analysed |
| `frida-mcp` | `enumerate_devices` | live | 3 devices (local, socket, barebone) |
| `searxng` | `searxng_instance_info` | degraded | tool executed, `available=false` |
| `searxng` → instance | same | dead | `127.0.0.1:8890` unreachable |
| `search-hub` → instance | same | dead | **byte-identical** response, same instance |
| `cloud-hub` → `rclone` | `core_version` | dead | backend init deadline exceeded — **corroborates** the round-2 record on a different day |

`modal` was deliberately **not** re-probed: its verdict is `hang` (600 s timeout, no
terminal state) and a re-probe costs the full timeout without being able to improve on it.

**The byte-identity claim is checked, not asserted.** `validate()` fails closed if a
record's prose says `BYTE-IDENTICAL` and no other record carries the same captured bytes.
Two of the mutation controls exercise exactly that.

## P2 — cost ranked by what is actually paid, with the dead slice netted out

`cost_rank.py` → `cost-rank.json`, ranked by **resident** bytes (tool names, paid every
turn under a deferred-schema client) with **contingent** (schema bytes) kept visible.

```
fleet: 16/23 rows ranked (7 not measured), 707 tools
RESIDENT 11,645 B (~2,911 tok/turn, rough) | CONTINGENT 603,233 B | 51.8x
```

Those totals were computed independently here and **match the grounding lane's exactly**
(707 / 11,645 / 603,233 / 51.8x / 12-of-16 rank movement) — two readers, same artifact,
same answer.

**Headline:** cloud-hub is **60.1%** of every-turn resident MCP cost, and **4,172 B of that
(59.6% of the row, ~1,043 tokens on EVERY request)** buys tools whose backend was measured
non-functional.

That 4,172 B is **exact, not pro-rated**. `name_bytes` is defined upstream as
`sum(len(n) for n in tool_names)`, so per-tool attribution reconciles against the committed
field, and **C3 fails the run closed unless the buckets re-sum to the number that shipped**.

> CORRECTION, inline: the grounding lane's "~1,100 tokens" was a pro-rated estimate from the
> 63.0% tool-count share. Measured by bytes the share is **59.6%** and the figure is
> **~1,043 tokens**. Dead-backend tool names are marginally shorter than average. The
> grounding claim was right in magnitude and slightly wide; this supersedes it.

## P4 — the searxng sentence, scoped from data

Was: *"0 unique — nothing becomes unreachable."* The set arithmetic was correct and the
sentence was wider than it: it implies search-hub still **serves** the capability.

Now generated by `shared_dead_resource()`, which returns `None` for any pair without a
jointly-measured dead resource and lets the plain wording ship:

> …0 unique -- so disabling removes no REACHABLE capability. The duplicated tools are
> non-functional on BOTH sides: each was measured against the same unreachable
> `http://127.0.0.1:8890`, so this is deduplication of a DEAD capability, not a failover to
> a live one.

Code was right; the sentence was wider than its evidence. **The verdict does not move.**
A side effect worth naming: `search-hub` now also discloses that one of its own
sub-capabilities is dead — a fact the old per-server field could not represent.

## Detector controls — every new guard, seen RED

| Control | Broken state fires? | Good state silent? |
|---|---|---|
| `s4_evidence` — 11 validation rules + missing-file branch | **12/12 fired** | yes |
| `backend_map` C1 completeness | fired on an injected unownable name | 424/424 classify |
| `backend_map` C2 negative fixture | 3 non-backend names refused | — |
| `backend_map` C3 partition | disjoint, sums to 424 | — |
| `assert_backend_consistency` — 7 mutations | **7/7 fired** | yes |
| `backend_view` B1 unclassified tail | fired | yes |
| `backend_view` B2 double-sum disagreement | fired | yes |
| `assert_signal_consistency` — 5 mutations | **5/5 fired** | yes |
| `cost_rank` C1/C2/C3/C4 | C1 12/16 rows move; C3 reconciles exactly | yes |

**B2 is the control that earns its keep.** Mutating `classify` alone could not prove the
double-sum works — *both* sums would use the mutant and agree, which is precisely the inert
control this repo measured on `manifest["events"][ev]` (four probes agreeing, all wrong).
So the mutation drives `bucket` and `classify` **apart**, which is the real defect shape.

**A new branch got a new fixture.** `call_method` can now report both methods
(`stdio-handshake+in-session-tool-call`), and the mutation
`both-methods-labelled-handshake-only` **is the previously shipped behaviour** — so a
survivor there would prove the fix cosmetic.

## Two defects found by running the gate

1. **`ci_gate.blob()` crashed instead of failing.** Adding a producer before committing its
   artifact produced a raw `CalledProcessError` traceback. Now a reported problem: *"the
   producer runs but the artifact does not exist at `<rev>` — commit it, or its determinism
   is unverifiable."*
2. **The success line hardcoded `2/2 artifacts`** while a third was being added. Now
   counted. A hardcoded total in a success message is the same drift class as a legend that
   stops matching its field.

## Evidence

Run at `a7cafc44`, on three interpreters including the one CI pins (`mcp-audit.yml`
→ `python-version: "3.11"`). Not optional diligence: a sibling had to land `dfea977d` to
fix a 3.11 `SyntaxError` this lane shipped, so "probably fine" was unavailable.

```
$ py -3.11 command-center/mcp-audit/ci_gate.py      # == the CI pin
SUCCESS:mcp-audit-ci-gate 19/19 gates behaved, 3/3 artifacts byte-identical to their producers
$ py -3.12 command-center/mcp-audit/ci_gate.py
SUCCESS:mcp-audit-ci-gate 19/19 gates behaved, 3/3 artifacts byte-identical to their producers
$ python command-center/mcp-audit/ci_gate.py        # 3.14.6
SUCCESS:mcp-audit-ci-gate 19/19 gates behaved, 3/3 artifacts byte-identical to their producers

$ python command-center/mcp-audit/ci_gate.py --self-test
SUCCESS:mcp-audit-ci-gate self-test 8/8 checks behaved

$ ruff check command-center/mcp-audit/        # ruff 0.15.17 == the CI pin
All checks passed!
```

The three artifacts are byte-identical to their committed blobs on **all three**
interpreters — dict ordering and float formatting are stable, not accidentally matching
one runtime. `r4_selfcheck` independently reports **12/12 blobs 0 CRLF** for this commit.

All lane files are **0 CRLF, pure LF** (byte-checked), and local ruff is the exact CI pin,
so the working-tree green is not the CRLF false-green that windows-shell §8b warns about.

## Residual — inline, and none of it blocks

- **P3 (resource regression) NOT DONE.** 16.03 GB MCP commit, +88% in 24 h, is the most
  operationally urgent item in the plan and it is untouched: the mitigation is a config
  mutation via `mcpapply`, outside this lane's file scope. *Confidence it matters: likely
  (55-80%)* — it rests on the documented commit-exhaustion freeze mechanism, not on a
  freeze observed this session.
- **7 of 12 cloud-hub backends UNMEASURED.** Recorded as `unprobed` in the evidence file
  with the settling experiment named. A 5/5 dead base rate among the probed does **not**
  license an inference — probe selection was not random. *Not claimed.*
- **`dead_surface_pct` is null for every non-`cloud-hub` row**, including `search-hub`.
  Null means **not attributed**, never zero: no tool→backend map exists for those servers.
- **CI-runner behaviour still UNVERIFIED.** Green locally on py 3.14.6 at the CI-pinned
  ruff. *Settling experiment:* the first `workflow_dispatch` after merge.
- **Sibling sessions are committing to `main` concurrently** — HEAD moved ~6 commits
  (`4ef63930` → `dcdf45ea`) mid-round. All commits here use `git commit -F <msg> -- <paths>`,
  so no sibling file was swept.
- **A `POTENTIAL-CREDENTIAL` artifact notice fired**, id `sha256:14c745ad1f24`, report-only.
  Surfaced for the owner; no credential was read, printed, rotated, or edited (AGENTS.md §9).

*Confidence in the shipped work: almost certain (90-99%)* — every claim above is backed by
an executed command with its real output, and every new guard was observed firing on a
known-broken input before its silence was accepted as clean.
