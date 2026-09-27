# Dead-config inventory + per-row recommendations — items (c), (d), (e)

Generated 2026-09-25 by the gem-hunt hygiene lane. **RECOMMEND ONLY.**
Nothing in this file was deleted, disabled or pruned. `~/.claude.json` was read, never written.

---

## (c) Disabled plugins and disabled MCP servers

### C1. "90 disabled plugins" — **REFUTED. There are zero.**

There is no plugin enable/disable state anywhere on this machine:

| Probe | Result |
|---|---|
| `installed_plugins.json` occurrences of `"enabled"` / `"disabled"` / `"active"` / `"state"` | **0 / 0 / 0 / 0** |
| `.claude.json` occurrences of `"enabledPlugins"` / `"disabledPlugins"` / `"enabled":false` | **0 / 0 / 0** |
| projects (45) carrying an `enabledPlugins` map | **0 of 45** |
| plugin entry shape | `{scope, installPath, version, installedAt, lastUpdated, gitCommitSha}` — no flag |

VERIFIED, confidence 90-95%. **100 plugins are installed and all 100 are enabled.** There is no
retained disabled-plugin state to curate, so item (c)'s plugin half has no subject.

**The real, different signal:** `pluginUsage` has **25** rows, so **83 of 100 installed plugins
have no usage record at all** (matching by short name). That is *unused*, not *disabled* — a
different finding with a different remedy, and one this lane may not act on (rule 3).

| Recommendation | Rationale |
|---|---|
| **KEEP all 100 installs. No action.** | Nothing is disabled, so nothing is stale. |
| Separately: the 83 no-usage plugins are the real 13 GB driver — `claude-plugins-official` alone is 11,011 MB / 402,620 files. **Propose** an owner review of which marketplaces to keep subscribed. **Do not prune.** | Plugin curation is load-bearing (rule 3), and `pluginUsage` only records *skill/command invocations*, so a plugin providing only an MCP server would read "unused" while being essential. Absence of a usage row is **not** evidence of uselessness. |

### C2. "131 disabled MCP servers" — count CONFIRMED, implied waste ≈ zero

`.claude.json.disabledMcpServers` = **131** rows (VERIFIED). `mcpServers` = **88**.

131 > 88 looks like mass orphaning. It is not — `disabledMcpServers` spans **three namespaces**,
and only one is keyed by `mcpServers`. My first test compared all 131 against `mcpServers` alone
and reported "77 orphans". **That was a detector bug, not a finding.** Corrected:

| Namespace | Row shape | Total | Resolves | Unresolved |
|---|---|---|---|---|
| local registry | bare name (`docker`, `serena`) | 58 | 54 | **4** |
| plugin-provided | `plugin:<plugin>:<server>` | 38 | 38 | **0** |
| claude.ai connector | `claude.ai <Name>` | 35 | 20 | 15 (unproven) |
| **total** | | **131** | **112** | **19** |

Two successive corrections were needed, both in the same direction (over-reporting):

1. Resolving `plugin:*` rows against `installed_plugins.json` alone gave 19 unresolved. But
   `plugins/data/` holds **66** plugin names installed *inline* (including `local-mcp-bridge`,
   which owns all 19). Against installed **+ inline**, unresolved = **0**.
2. The 15 unresolved `claude.ai` rows were checked against `claudeAiMcpEverConnected` (46 rows).
   That field records connectors **ever connected**, so a connector that exists but was never
   connected is legitimately absent from it. **Absence there does not prove the connector is
   gone** — these 15 are UNPROVEN, not dead. Confidence 60-70%.

**Only 4 rows are defensibly unresolved:** `apify`, `biomni-hub`, `meta-tool`, `schrodinger`.
Even these are weak candidates: `meta-tool` is *also* in `settings.json.deniedMcpServers`, and
`biomni-hub` / `schrodinger` are known estate servers (the Biomni FastMCP server; licensed
Schrödinger compchem) that are plausibly parked on purpose. Precedent:
`.mcp-disabled-defaults.json` lists `cloud-hub`/`social-hub` as parked while both run live.

| Recommendation | Rationale |
|---|---|
| **KEEP all 131 rows. Recommend no deletion of any.** | 112 of 131 resolve; 15 are unproven; 4 are plausibly deliberate parks. |
| The whole `disabledMcpServers` array is ~4 KB of JSON. | The cost of retaining it is negligible; the cost of deleting a row that was a deliberate park is a silently re-enabled server. **This is a premise that is true as a count and not worth acting on.** |
| If the owner ever wants it trimmed: start with the 4 named above, one at a time, confirming each is not wanted first. | Never batch-delete curation state. |

`settings.json.deniedMcpServers` (6): `claude-code-mcp`, `markitdown`, `rdkit`, `serena`,
`gitlab`, `meta-tool`. All 6 are deliberate policy denies — `claude-code-mcp` is denied
estate-wide by standing decision. **KEEP all 6.**

---

## (d) superpowers skill forks — premise CONFIRMED (14 of 15 diverged, 0 identical)

Active plugin version is **6.4.1** (`installed_plugins.json` `installPath` →
`…/superpowers/6.4.1`, `gitCommitSha 5bf4e78011075bcfc0dc295f0724994cd123ee71`). The first pass
compared against the `5bf4e7801107` directory; re-run against 6.4.1 to be sure the baseline is
the live one.

All forks are **authored** in `~/.agents/skills/<name>/SKILL.md`, git-tracked, and byte-identical
to the deployed `~/.claude/skills/` copy. Per lane rule 1, any change goes to the authored copy
then through the deploy script — never the deployed copy.

`EstateMarkers` = net count of estate-specific tokens (`prekzursil`, `.agents`, `metaswarm`,
`OPEN-LOOPS`, `basic-memory`, `owner-ops`, `AGENTS-RUNTIME`, `estate`, …) in the local fork minus
the plugin original. A positive number is positive evidence the fork is a deliberate local
adaptation rather than a stale snapshot.

| Skill | local B | plugin B | estate Δ | used? | Verdict | Recommendation |
|---|---:|---:|---:|---|---|---|
| `writing-skills` | 55,785 | 26,623 | **+15** | both | **INTENTIONAL** | **KEEP the fork.** 2.1x larger, heavily estate-adapted. |
| `writing-plans` | 4,348 | 9,092 | +1 | plugin only | **INTENTIONAL (weak)** | **KEEP, but review** — only +1 marker and less than half the size. |
| `brainstorming` | 4,772 | 17,548 | 0 | **both** | **STALE DRIFT** | **Re-sync from 6.4.1.** 3.7x smaller, no estate content, and *both* names are in `skillUsage` — the estate is actively running the thin copy. Highest-value fix here. |
| `executing-plans` | 2,878 | 20,405 | 0 | **never** | **STALE DRIFT** | **Re-sync or retire the fork.** 7.1x smaller; neither name has ever been used, so re-syncing is zero-risk. |
| `subagent-driven-development` | 10,483 | 32,577 | 0 | plugin only | **STALE DRIFT** | **Re-sync from 6.4.1.** 3.1x smaller; only the `superpowers:` name is used, so the fork is shadowing for no benefit. |
| `systematic-debugging` | 13,504 | 9,465 | 0 | plugin only | DIVERGED | Human read. Local is larger — plausibly a real improvement with no estate token. |
| `receiving-code-review` | 8,746 | 6,203 | 0 | — | DIVERGED | Human read; local larger. |
| `verification-before-completion` | 6,925 | 3,646 | 0 | — | DIVERGED | Human read; local 1.9x larger. |
| `dispatching-parallel-agents` | 7,824 | 6,078 | 0 | — | DIVERGED | Human read; local larger. |
| `test-driven-development` | 10,230 | 9,578 | 0 | **never** | DIVERGED | Human read; near-parity. |
| `using-superpowers` | 4,294 | 3,192 | 0 | — | DIVERGED | Human read; local larger. |
| `using-git-worktrees` | 5,849 | 6,813 | 0 | — | DIVERGED | Human read; local slightly smaller. |
| `requesting-code-review` | 2,805 | 2,977 | 0 | — | DIVERGED | Human read; near-parity. |
| `finishing-a-development-branch` | 5,473 | 7,781 | 0 | — | DIVERGED | Human read; local smaller. |
| `diagnosing-superpowers` | — | 6,904 | — | — | PLUGIN-ONLY | **No action** — no local fork exists. Correct state. |

Summary: **2 INTENTIONAL · 3 STALE DRIFT · 9 DIVERGED · 1 PLUGIN-ONLY.** Zero identical.

**The actionable core is the 3 STALE DRIFT rows.** A local fork wins over the plugin original in
resolution, so the estate is running `brainstorming` at 4,772 B while a 17,548 B current version
sits unused. That is a *capability* regression, not just duplication — and it is the one finding
in this item worth acting on. Byte-size is a proxy, so a human should confirm before re-syncing;
I did not re-sync anything (rule 3, and rule 1 would route it through `~/.agents/skills`).

---

## (e) 23 `source-command-*` skill duplicates — premise CONFIRMED, cleanest case in the lane

23 skills named `source-command-<X>` exist in **both** `~/.agents/skills` (authored, all 23
git-tracked) and `~/.claude/skills` (deployed). **Every one of the 23 has a paired
`~/.claude/commands/<X>.md`.**

They are wrappers, not adaptations. Verified by body comparison on a 4-skill sample:

| wrapper | command lines found verbatim inside the SKILL.md |
|---|---|
| `source-command-rules-distill` | **100%** (3/3) |
| `source-command-projects` | **100%** (12/12) |
| `source-command-promote` | **100%** (15/15) |
| `source-command-prime` | **100%** (114/114) |

Each SKILL.md is its command's text plus YAML frontmatter — consistently 179-521 bytes larger
than the command file, which is exactly the frontmatter. No wrapper adds content.

**Usage evidence is decisive: `skillUsage` has 92 rows and NOT ONE matches `source-command-*`.
All 23 have never been invoked**, while the underlying commands (`/prime`, `/aside`, `/plan`,
`/self-reflect`, …) are the real entry points and remain fully available.

Cost, stated honestly:

| Measure | Value |
|---|---|
| wrapper `SKILL.md` bodies | 101,699 bytes |
| **always-on listing cost (frontmatter only)** | **3,447 bytes ≈ 862 tokens** |
| duplicate rows in the skill listing | 23 |

The 101,699 bytes are *not* an always-on cost — a body loads on invocation. The real cost is
**~862 tokens of permanent listing overhead plus 23 confusable entries that duplicate existing
commands and have never been used.**

| Recommendation | Rationale |
|---|---|
| **RETIRE all 23 wrapper skills** (the commands stay). Highest confidence in this lane: 85-90%. | Zero usage across 92 usage rows; 100% verbatim duplication; the command is the real entry point. |
| Do it at the **authored** copy `~/.agents/skills/source-command-*`, then re-deploy — never by deleting the deployed copy (rule 1). Record it as RETIRED in `INVENTORY.md` so `estate-inventory` does not flag 23 UNEXPLAINED disappearances. | Rule 1 + the measured 2026-09-24 lesson that 13 skills vanished with zero git record. |
| **NOT DONE by me** — rule 3 forbids this lane deleting any skill. Recommendation only. | — |

**Honest caveat:** "never invoked" is measured from `skillUsage`, a single field. It is one
signal. If `skillUsage` only records *model-invoked* skills, a human typing a wrapper name would
not appear. The 100% verbatim-duplication finding is the independent second signal, and it does
not depend on usage telemetry at all.
