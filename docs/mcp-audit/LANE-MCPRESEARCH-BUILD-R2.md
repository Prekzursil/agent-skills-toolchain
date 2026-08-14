# LANE MCPRESEARCH — BUILD round 2

Executed 2026-08-14. Every number below was produced by running the thing; where something
was not measured it says so inline, next to the claim it qualifies.

## Why this is round 2

The orchestrator labelled this unit "BUILD round 1". A committed BUILD round 1 already
existed (`LANE-MCPRESEARCH-BUILD-R1.md`, landed `a7cafc44` → `ece38dae`), so P1/P2/P4 were
already shipped and redoing them would have been rework. This round starts from R1's own
declared residual instead.

## What shipped

| # | R1 residual | State |
|---|---|---|
| — | 7 of 12 cloud-hub backends UNMEASURED (the named settling experiment) | **CLOSED** — all 7 probed, plus the account layer |
| — | `dead_surface_pct` null for `search-hub` | **PARTLY CLOSED** — all 4 of its backends now measured; byte attribution still null (no tool→backend map) |
| — | `DISPOSITION-TABLE.md` hand-maintained | **CLOSED** — now a generated artifact under the determinism gate |
| P3 | resource regression | **STILL NOT DONE** — mitigation is a config mutation outside this lane's file scope |
| P5 | wire producer into `mcpctl` | **OUT OF FILE SCOPE** (`tools/mcpctl/**`) |
| P6 | Databricks PAT | **OWNER ACTION** — not touched, not read, not printed |

**Dispositions did not move:** DISABLE 1 / INVESTIGATE 2 / KEEP 20, identical to R1.

## The measurements — 11 new backend records, zero unprobed

All read-only, all first-hand in this session. Fired in one parallel batch so that a hang
would cost 600 s once rather than seven times (R1 recorded `modal` consuming a full 600 s
timeout). No probe hung.

| server / backend | tool | verdict | what came back |
|---|---|---|---|
| `cloud-hub` → kaggle | `competitions_list` | dead | backend unavailable: initialize failed **child exited** — a different mode from the deadline-exceeded rows |
| `cloud-hub` → aws | `aws___list_regions` | **not-dispatchable** | `Unknown tool: 'aws___list_regions'` |
| `cloud-hub` → azure | `azmcp_subscription_list` | **not-dispatchable** | `The tool ... was not found`; a second `azmcp_` tool failed identically |
| `cloud-hub` → gcloud | `run_gcloud_command` | live | real Resource Manager read → `lifecycleState=ACTIVE` |
| `cloud-hub` → lightning | `lightning_machine_types` | live | 45 Studio machine types |
| `cloud-hub` → ovh | `ovh_api_catalog` | live | 52-category API catalog |
| `cloud-hub` → compute-unified | `compute_catalog` | live | 45 items, list-equal to `lightning_machine_types` |
| `cloud-hub` → account-layer | `aws_account_current` | live | `ok:true` — and 3 more, below |
| `search-hub` → exa | `web_search_exa` | live | a real result with URL + highlights |
| `search-hub` → tavily | `tavily_search` | **no-credential** | refused locally: no usable Tavily key |
| `search-hub` → firecrawl | `firecrawl_scrape` | **no-credential** | refused locally: no usable Firecrawl key |

`unprobed` is now empty for **both** proxy servers.

### Two verdicts the vocabulary could not express

Both added because a probe produced the shape — not in anticipation. A vocabulary member
with no measured user is dead weight.

- **`not-dispatchable`** — the tool is in the committed surface **and** resolvable in the
  live client namespace, and the server still refuses to dispatch it. **23 tools** (9
  `aws___*`, 14 `azmcp_*`), **515 B of resident context every turn** (~129 tok, rough) for
  capability that cannot run at all. Ruled out both rival explanations: `aws_account_current`
  on the *same server* returned `ok:true` in the same batch (so not "server down"), and two
  *different* `azmcp_` names failed identically (so not a typo).
  > UNVERIFIED, inline: which layer emits the refusal. The two families return different
  > wording (`Unknown tool: 'X'` vs `The tool X was not found`), which hints at different
  > layers, and I did not chase it. *Settling experiment:* capture the server's own
  > `tools/list` and diff it against the client's deferred-tool catalogue.
- **`no-credential`** — refused locally for want of key material; the backend is never
  contacted. Distinct from `auth-dead` (Databricks: a credential *was* presented and
  rejected) because the owner's next action differs — configure vs renew.

## The account layer is not a backend

Every backend used to own its own `*_account_*` family, so **66 working tools** were
attributed to whichever backend they sat beside. Four probes, chosen so the hypothesis
could **fail** — three of the four sit over a backend independently measured non-functional
in this same session:

```
aws_account_current -> ok:true   while every aws___* tool is non-dispatchable
rp_account_current  -> ok:true   while the RunPod backend is dead
kg_account_current  -> ok:true   while the Kaggle backend is dead (child exited)
az_account_current  -> ok:true   while every azmcp_* tool is non-dispatchable
```

They now share a `cloud-hub-account-layer` bucket. This moves the headline in the
**flattering** direction (less surface counted dead), which is exactly why it needed
measurement rather than an argument — and why it got its own control.

## The corrected number, reconciled rather than replaced

> **CORRECTION, inline:** R1 shipped `267/424 (63.0%)` dead surface and `4,172 B / 59.6% /
> ~1,043 tok`. Both are **SUPERSEDED**, not deleted — they were correct for the five
> backends known then. The new figures are `311/424 (73.3%)` and `5,125 B / 73.2% /
> ~1,281 tok`.

The move is fully decomposable, so it can be audited rather than trusted:

```
267  R1, five dead backends (with their account families folded in)
-30  account-layer tools measured WORKING over those five backends
----
237
+51  kaggle          (newly measured dead)
 +9  aws             (not-dispatchable)
+14  azure           (not-dispatchable)
----
311  = 73.3% of 424      bytes: 5,125 B = 73.2% of the cloud-hub row
```

Per-backend, all 424 tools classified, nothing unclassified:

| backend | tools | name B | verdict |
|---|---:|---:|---|
| cloud-hub-account-layer | 66 | 1,073 | live |
| databricks | 65 | 1,033 | auth-dead |
| rclone | 56 | 789 | dead |
| kaggle | 51 | 923 | dead |
| runpod | 50 | 721 | dead |
| modal | 41 | 761 | hang |
| ovh | 27 | 447 | live |
| biomni | 25 | 383 | dead |
| azure | 14 | 328 | not-dispatchable |
| compute-unified | 10 | 132 | live |
| aws | 9 | 187 | not-dispatchable |
| lightning | 9 | 203 | live |
| gcloud | 1 | 18 | live |
| **TOTAL** | **424** | **6,998** | 0 unclassified |

**search-hub keeps its KEEP and loses most of its capability.** Three of its four backends
are non-functional — searxng (dead instance), tavily and firecrawl (no credential). Only
exa answered a real query. The disposition is unchanged and correct; the *evidence sentence*
now says so, which it could not before.

## OVH is recorded `live` deliberately

Its first probe failed (`ovh_services` → OVH `404 Client::NotFound`), but `ovh_api_catalog`
returns 52 categories. Marking the backend dead on one tool would have counted ~30 working
tools as dead surface — an over-report in the other direction. The failing tool is instead
recorded structurally in a new `known_tool_defects` field, with its own validation rules,
rather than buried in prose where it would rot.

> UNVERIFIED, inline: whether that catalog is fetched or served from a local static list.
> What *is* established is that `ovh_services` reached something answering in OVH's own
> error envelope. *Settling experiment:* a tool that must transit the network, compared on
> latency and error shape.

## DISPOSITION-TABLE.md is now generated

It was hand-transcribed from a machine-generated JSON, and it had drifted exactly the way
that arrangement always drifts: the committed table still read `267/424 (63.0%)` and
`7 further backend(s) UNMEASURED` — a residual this round closes. `render_table.py` derives
every figure from `disposition.json`, **counts** the footer totals instead of typing them
(R1 shipped a hardcoded `2/2 artifacts` while a third was being added), and `ci_gate`
compares the regenerated bytes against the committed blob. The determinism job now carries
a full repo-relative path, so a produced artifact no longer has to sit beside its producer.

## Detector controls — every new guard seen RED

| Control | Fires on the broken state? | Silent on the good state? |
|---|---|---|
| `backend_map` C4 account-layer completeness | **fired** (see below) | yes |
| `backend_map` C4a detector fixture | 3 shim names matched, 4 look-alikes refused | yes |
| `s4_evidence` — 15 validation rules + missing-file | **15/15 fired** | yes |
| `s4_evidence` LIVE-width assertion | 1 verdict means working, 6 mean not | yes |
| `render_table` G1 dropped row | **fired** | yes |
| `render_table` G2 pipe / newline in a cell | **2/2 fired** | yes |
| `render_table` G3 footer counts follow rows | recount tracks a flipped verdict | yes |
| `render_table` G4 zero rows | **fired** | yes |
| `_b1_redproof_backend` A + B | 7/7 mutations, both `backend_view` guards | yes |

**C4 is the control that earns its keep**, and it had to be built carefully to be worth
anything. C1/C2/C3 *cannot* see an incomplete relocation: the stragglers stay classified,
disjoint, and summing to 424 — they are merely attributed to a dead backend. So C4 needed a
detector **independent of the family table**; asking `ACCOUNT_FAMILIES` which names belong
to the account layer would be the mutant grading itself, both sides shrinking together, and
the control could never fire. That is the inert-control shape this repo has already measured
on `manifest["events"][ev]`. The isolating mutation drops `rc_account_` only — those names
still match rclone's `rc_`, so **C1 and C3 stay green while six working tools are attributed
to a dead backend**, and only C4 goes red.

## Three detector failures, two of them mine

1. **C4's first detector was wrong and its own fixture caught it.** It began as the
   substring `_account_` and immediately claimed three stragglers —
   `azmcp_cosmos_account_list`, `azmcp_storage_account_list`, `ovh_account_info` — which are
   backend tools *about* cloud accounts. Textbook use-vs-mention: the word is in the name
   without the name being one. Tightened to name shape plus the shim's fixed six-verb op
   set, and given a negative fixture (C4a) so the next loosening cannot land silently.
2. **`render_table` G1 counted rows two different ways** and the two disagreed by one, so
   the dropped-row control reported `0` and went red on a correct renderer. Two spellings of
   the same count is how a control ends up measuring the speller; both now call one helper.
3. **A PostToolUse sentinel reported a successful exa search as an infra failure**, matching
   the word `Timeout` in the *result content* — a page about MCP ping timeouts. The call
   plainly succeeded (title, URL, highlights). A self-contradicting output is a detector
   failure, not a finding, so I recorded it and did not act on it. **Not fixed — the hook is
   outside this lane's file scope.** Surfaced here for whoever owns it.

## Evidence

Run at `67137879`, on three interpreters including the one CI pins
(`mcp-audit.yml` → `python-version: "3.11"`):

```
$ py -3.11 command-center/mcp-audit/ci_gate.py      # == the CI pin
SUCCESS:mcp-audit-ci-gate 20/20 gates behaved, 4/4 artifacts byte-identical to their producers
$ py -3.12 command-center/mcp-audit/ci_gate.py
SUCCESS:mcp-audit-ci-gate 20/20 gates behaved, 4/4 artifacts byte-identical to their producers
$ python command-center/mcp-audit/ci_gate.py        # 3.14.6
SUCCESS:mcp-audit-ci-gate 20/20 gates behaved, 4/4 artifacts byte-identical to their producers

$ python command-center/mcp-audit/ci_gate.py --self-test
SUCCESS:mcp-audit-ci-gate self-test 8/8 checks behaved

$ python -m ruff check command-center/mcp-audit/    # ruff 0.15.17 == the CI pin
All checks passed!
```

`r4_selfcheck` independently reports **9/9 blobs 0 CRLF** at this commit (it was 4/4 before;
it picked up the new files). `git` printed *"LF will be replaced by CRLF"* working-copy
warnings on commit — those describe the working tree, not the blob, and the determinism
check settles it from the other direction: the producers write LF and their output is
byte-identical to `git show`'s blob bytes on all three interpreters.

## Residual — inline, and none of it blocks

- **P3 (resource regression) still NOT DONE.** 16.03 GB MCP commit, +88% in 24 h, remains
  the most operationally urgent item in the plan and is untouched: the mitigation is a
  config mutation via `mcpapply`, outside this lane's file scope. *Confidence it matters:
  likely (55-80%)* — it rests on the documented commit-exhaustion mechanism, not on a freeze
  observed this session.
- **`dead_surface_pct` is still null for every non-`cloud-hub` row**, `search-hub` included.
  Its four backends are now all *measured*, but no tool→backend map exists for it, so its
  **54** non-exa tools — of a committed surface of **68** — cannot be attributed by bytes.
  Null means **not attributed**, never zero.
  > **REFUTED, corrected in round 3.** This sentence shipped reading *113 non-exa tools*.
  > `search-hub` advertises 68 in total, so 113 could not be a subset of it under any
  > reading. The figure is `424 − 311`: the count of **cloud-hub** tools *not* over a dead
  > backend, transposed one paragraph across a row boundary. Nothing computed from it —
  > every gate stayed green — because it lived only in prose. The refutation is recorded
  > rather than deleted, and the class now has an executable guard: `claim_lint.py` refuses
  > any prose count that exceeds the surface it is attributed to.
  *Settling experiment:* extend `backend_map` with a search-hub table. Measured this round,
  and the reason it is still not done blind: name shape resolves only 61 of the 68 —
  `_exa`/`ex_` 14, `firecrawl_`/`fc_` 32, `tavily_`/`tv_` 11, `searxng_`+`web_url_read` 4 —
  leaving **7 genuinely unattributable** (`agent_*` ×4, `deep_researcher_*` ×2,
  `search_usage`), each of which could belong to more than one backend.
- **The two `not-dispatchable` families are reported, not diagnosed.** I did not determine
  whether the tools are missing server-side, shadowed, or mis-registered. The audit fact —
  23 advertised tools that cannot run and still cost context — stands either way.
- **CI-runner behaviour still UNVERIFIED.** Green locally on three interpreters at the
  CI-pinned ruff; the residual is the runner *environment*. *Settling experiment:* the first
  `workflow_dispatch` after merge.
- **A `POTENTIAL-CREDENTIAL` artifact notice fired**, id `sha256:14c745ad1f24`, report-only —
  the same id R1 recorded. Surfaced for the owner; no credential was read, printed, rotated
  or edited (AGENTS.md §9).
- **The Databricks PAT is still expired** (`auth-dead`, unchanged from R1). Owner action.

*Confidence in the shipped work: almost certain (90-99%)* — every claim above is backed by
an executed command with its real output, every new guard was observed firing on a
known-broken input before its silence was accepted, and the one number that moved in the
flattering direction is decomposed line-by-line above so it can be checked rather than
believed.
