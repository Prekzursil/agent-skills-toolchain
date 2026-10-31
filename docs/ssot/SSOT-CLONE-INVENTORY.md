---
title: SSOT-CLONE-INVENTORY
type: note
permalink: dqverify-repo-20261013/docs/ssot/ssot-clone-inventory
---

# SSOT clone inventory — agent-skills-toolchain

**Lane:** SSOT. **Measured:** 2026-08-12 19:40–21:00, extended 2026-08-13 (BUILD round 1: §2b
content check, the §5 retire-criterion correction, R8). **Read-only against every checkout.**
**Nothing was deleted, and nothing may be deleted from this document alone — every RETIRE below
is a recommendation with a named precondition.**

COVERAGE: questions 1–4 measured against a **25-checkout fleet — a population REFUTED twice
since.** Round 1 (2026-08-13) showed the enumerator tested for the repo NAME rather than its
identity; round 2 (2026-08-14) showed the corrected enumerator silently discarded 20 rows whose
identity it could not determine. The measured population is now **178**, and the whole of §1–§4
below is scoped to the 25 it was computed over. §2b content-checks the stranded work in 4 of
those (the other 21 hold no object-unique commits). Every row here is still true of its own
subject; what is refuted is the DENOMINATOR, and one §3 conclusion — see §3a.

Residuals in §7; corrections are marked inline where they occur, with the refuted wording kept
rather than deleted. The full 178 are classified on every DoD axis in
`command-center/ssot/population-classified.json` (`classify_population.py`, three both-states
controls). §6 carries the round-2 summary.

> If it still reads this way, the unit died before measuring anything and no verdict here may be
> cited. (It did not — every row carries a measured value.)

---

## 0. Headline — the count is wrong three times over, and the count is not the problem

| source | claimed | reality |
|---|---|---|
| owner ("nine separate clones") | 9 | subset |
| `REPO-TOPOLOGY.md` (2026-08-09) | "9 local checkouts / 2 stores" | a **different** nine; 2 of its entries no longer exist |
| this lane, first pass (hand-written lists) | 14 / 8 stores | still an undercount |
| exhaustive filesystem sweep (911 git checkouts walked) | 25 checkouts / 18 object stores | **REFUTED — see below** |
| round 1 (2026-08-13), identity by ancestry | 170 | **REFUTED — 20 rows dropped** |
| **round 2 (2026-08-14), ancestry + resolved undecidables** | **178 checkouts / 168 object stores** | measured |

Both prior documents landing on "9" is coincidence, not corroboration. I only got the right number
by refusing to trust either list and walking the filesystem — the first pass gave 14 and I had
labelled that *likely (55–80%) complete*, which was correctly calibrated and still wrong.

**And 25 was wrong too, for the same reason one level up.** The sweep identified a checkout by
whether the string `agent-skills-toolchain` appeared in its remote URL or store path — a NAME test
standing in for an IDENTITY test (round 1, `enum_defect_proof.py`, 7/7 both-direction assertions).
Replacing it with ancestry gave 170. That figure is **also refuted**: `merge-base --is-ancestor`
returns 0/1/**128**, and round 1 compared `== 0`, folding "the root object is absent from this
store, so the question could not be asked" into "not an ancestor". 20 rows landed there;
105 + 20 = 125 is exactly round 1's published "REJECTED : 125", so the arithmetic closes.
Resolving those 20 on origin + root-markers recovers 8 real checkouts →
**178** (`rc128_redproof.py`, `identity_by_ancestry.py`, `rc128_resolve_probe.py`).

The pattern across all three is one error: **a question the instrument could not answer, recorded
as a confident negative.** The count is still not the problem — §3a is.

**The clone count is not the SSOT defect.** Two things actually matter:

1. **Edit ≠ execute.** `~/source/ast-integrate` holds `main` and is where all editing happens.
   `~/source/agent-skills-toolchain` is permanently detached (git forbids two checkouts of `main`),
   sits **159 commits behind** `origin/main`, and is where **five live MCP servers** load code from.
   Correctly scoped: the drift is **latent, not active** — `git diff 53c37c6c..ae8205a4` over the
   five directories the fleet actually loads returns **0 changed files**. Nothing is broken today.
   The hazard is that the *next* commit under `tools/mcp/**` silently never reaches the running
   fleet. (likely, 55–80% — reasoned from the mechanism, no observed failure.)
2. **Some — not all — of the stranded scratch work is genuinely the only copy.** Four commits are
   object-unique (§2). A content check (§2b, added 2026-08-13) shows object-uniqueness and content-
   uniqueness are different things: the CRCP security fix is byte-identical on `main` and is
   **redundant**, while 5 files across two other locations exist **nowhere on `main`**. The real
   exposure is those 5 files plus one DIVERGED set needing judgement — smaller than "four commits"
   and sharper.

---

## 1. Q1 — worktree vs clone, by measurement

Two mechanically independent signals, agreeing on all 25: (a) `.git` FILE (linked worktree) vs DIR;
(b) `git rev-parse --path-format=absolute --git-common-dir`. A third, `objects/info/alternates`,
was empty everywhere. **25 checkouts, 18 object stores.**

| store | checkouts |
|---|---|
| **A** `~/source/agent-skills-toolchain/.git` | 5 — canonical (detached), `ast-integrate` (main), `ast-harness-reconcile`, `D:/inc1-wt/ast-increment1`, `D:/wt-salvage-probe` |
| **B** `~/source/ast-patch167/.git` | 3 — `ast-patch167`, `_verify_M04_tree`, `_verify_M13` |
| **C** `~/Documents/Playground/.git` | 2 — `Documents/Playground`, `~/.codex/worktrees/8528/Playground` |
| 15 further stores | 1 checkout each (list in `command-center/ssot/all25.json`) |

Store B's `origin/main` is pinned at `07f465f`. **Never measure a baseline there.**

**`~/.claude/codexsrc-work` and `~/.claude/tw-merge-work` are `--local` hardlink clones** whose
`origin` is the canonical *filesystem path*, not GitHub. Verified independently with
`fsutil hardlink list`: `pack-205947e4….pack` is **one inode with three hardlinks** across canonical
and both clones. Two consequences — their disk cost is double-counted, and their "modified today
11:26" mtime is canonical's pack seen through a shared inode, **not activity in them.** I nearly
reported those two as live.

---

## 2. Q2 — unique content (the finding that matters)

Method: per store, `git rev-list --all --reflog` (reflog included, so orphaned/amended work is
caught), `git cat-file --batch-check` against **every one of the other 17 stores**, then intersected
with "not reachable from any tip in `git ls-remote origin`".

**Detector controls, both states:** fabricated SHA → absent; canonical's own HEAD → present; and a
**real commit from an unrelated repo** (`qzp-lean` HEAD `3187b8a2`) → correctly absent. The third is
the load-bearing one: it proves the detector sees genuine absence of a real object.

### Stores holding commits that exist nowhere else and are not on the remote

| store / checkout | count | what it is |
|---|---|---|
| `.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | **2** | `feat(mcp-manager): dead-MCP detector with graded, citable evidence` (2026-07-18, ×2) |
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | **1** | `fix(mcpctl): strip control bytes BEFORE redacting` (2026-07-27) — plus 7 dirty files |
| `source/_wu/CRCP-SEC` | **1** | `fix(crcp): scope the OpenAI bearer to an allowlist of OpenAI hosts` (2026-07-29) — **a security fix** |
| store A (canonical) | **6** | 1 real unpushed commit on `main` (today), 1 orphaned `c165fe3d` (2026-08-10, reflog-only, in no ref), 1 checkpoint, 3 stash/index commits |
| store B (`ast-patch167`) | **3** | `d9ec177`, `be60f18`, `6451b18` — the M04/M13 verify commits |
| `work/agent-skills-toolchain-re` | **3** | 2026-03-31 RE-skills commits, reflog-only orphans |

**Four of these are genuine authored work — two features, a bugfix and a security fix — sitting in
scratch/salvage worktrees with zero inbound references.**

> **REFUTED WORDING, kept so the dead end is not re-walked.** This section originally continued:
> *"That is the fleet's real data-loss exposure."* The commit-OBJECT measurement above is correct
> and stands. The sentence was wider than its evidence: object-uniqueness is not content-
> uniqueness, and under squash-merge a fully-merged change keeps a unique SHA forever
> (`REPO-TOPOLOGY.md` rule 4 — which this document cited and then failed to apply to the scratch
> worktrees). §2b measures the content and supersedes the claim.

**A claim I had to retract mid-lane.** `ast-patch167` HEAD is byte-identical to the remote tip of
`fix/deny-credential-gaps`, which made "store B is fully pushed" look right. `merge-base
--is-ancestor` (control: root→HEAD True, HEAD→root False) shows **0 of its 8 store-unique commits
are ancestors of that tip**. `REPO-TOPOLOGY.md` content-verified the `pr242/244/245/249` lineage as
redundant; it does **not** cover the three verify commits (§7 R2).

**Earlier count corrected.** My first pass reported 13 unpushed commits on store A's `refs/heads/*`.
Against all 18 stores the store-unique figure is 6 — the difference is commits replicated into
`harness-restore/wave3/ast-cc`, `scratch/ast-gp-main` and the plugin cache. Replicated locally is
**not** the same as safe; it only means deleting store A alone would not lose them.

---

## 2b. Content check of the stranded work — added 2026-08-13, BUILD round 1

Method: for every path in each stranded commit, compare the scratch blob against
`origin/main` and classify **bidirectionally** — `ABSENT` / `DIVERGED` (both sides hold unique
lines) / `MAIN_IS_SUPERSET` / `IDENTICAL`. Bidirectional by construction because the one-
directional read ("does scratch have extra lines?") is the measured systematic blind spot:
31 of 47 agent misclassifications were DIVERGED read as safe, and **100% of those errors
pointed at data loss** (`fan-out-contract` §C.D4). Blobs read with `git cat-file -p`, never
`git archive` (CRLF on this box); compared LF-normalised so a pure line-ending delta is not
reported as divergence. Script: `command-center/ssot/content_check.py` → `content-check.json`.

**Detector controls, both states.** Blob reader: a real tree path returns content, a
fabricated path returns `None` (a reader that returned empty for everything would mark every
file ABSENT and manufacture a fleet-wide false alarm). The `IDENTICAL`/`MAIN_IS_SUPERSET`
verdicts — the only ones that could authorise a deletion — were then re-checked by a
**mechanically independent second signal**: git's own SHA-1 blob identity via `git hash-object`
on raw bytes, sharing no code path with the line-set comparison
(`_verify_identical.py` → `verify-identical.json`, control: same-file MATCH, two different real
files DIFFER). **5 of 5 corroborated.**

| location | commit subject | verdict | measured |
|---|---|---|---|
| `source/_wu/CRCP-SEC` | `fix(crcp): scope the OpenAI bearer to an allowlist` | **REDUNDANT** | `auth.py`, `sentinel.py` and **both proving tests byte-identical** on main (12,608 B / 13,487 B / 13,094 B / 10,569 B, sizes equal on both sides); `auth_broker.py` MAIN_IS_SUPERSET (0 scratch-only lines). The 2 DIVERGED files are `quality.yml` (**+689 main-only** — main evolved, scratch is stale) and `__main__.py` (+2/-13). |
| `agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | `feat(mcp-manager): dead-MCP detector` | **UNIQUE — preserve** | `core/health.py`, `mcp_health.py`, `tests/test_health.py` — all three **ABSENT from main** |
| `agent-worktrees-salvage/agent-425276811/ast` | `fix(mcpctl): strip control bytes BEFORE redacting` | **DIVERGED — needs judgement** | all 5 files diverge, incl. `mcpctl/safety.py` (+17 scratch-only / +11 main-only) and 3 test files. Not settled in either direction. |
| `D:/wt-salvage-probe` | *staged index, never committed* | **UNIQUE — preserve, highest urgency** | `ci/tests/test_codex_profiles.py` and `tools/monitorcore/r0_monitor_live_gate.py`, **both ABSENT from main** |

**Consequences.**

1. **The CRCP security fix is not at risk** — it is on `main`, twice-verified. **Almost certain
   (90–99%).** Any plan that reconciles it first is spending effort on a solved problem.
2. **`D:/wt-salvage-probe` is the sharpest hazard in the fleet**, and §4 under-rated it as "needs a
   one-file triage". It holds 2 files that exist nowhere on `main`, in a **staged index** — and a
   staged index is per-worktree and **is destroyed by `git worktree remove`**, unlike the shared
   stash (§5 note). Triage it before any retirement work.
3. **`_b5-toolchain`'s 3 files are genuinely absent** — which independently confirms the
   `tools/mcp-manager/` "42 files on main, 42 in the commit" reading was a **3-for-3 swap, not
   parity**. Equal counts on both sides is the classic collection-level tell, not evidence of
   redundancy. The correct verdict is *superseded parallel implementation*: main solves the same
   capability via `core/claude_adapter.py` + `core/models.py`; whether b5's graded-evidence logic
   holds behaviour main lacks is a judgement call, **UNVERIFIED** — settle by diffing the grading
   logic against main's detector, not by counting files.
4. **The mcpctl fix is the one genuinely open item.** *Correctly scoped:* line-set divergence does
   **not** prove main is missing capability — main may have evolved past the scratch form. It only
   proves the two are not the same text. **UNVERIFIED** whether any scratch-only behaviour is
   absent from main; settle by running the scratch test files against main's `safety.py`.

### Uncommitted work — my first pass under-counted every row

`REPO-TOPOLOGY.md` detector-note 3 says `git status --porcelain` collapses untracked directories and
you must pass `-uall`. **I read that note and then failed to apply it.** Corrected:

| checkout | `-u normal` (wrong) | `-uall` (correct) |
|---|---|---|
| `~/Documents/Playground` | 2 | **111** |
| `~/source/ast-integrate` | 137 | **298** |
| `~/.claude/codexsrc-work` | 52 | **81** |
| `~/source/ast-patch167` | 1 | **8** |
| `.codex/plugins/cache/…/0.2.0` | not measured | **57** + 1 stash |
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | not measured | **7** |

**Fleet total: 567 uncommitted files across 25 checkouts.**

---

## 2c. The five no-remote checkouts, finally measured — added 2026-08-14, BUILD round 3

> **REFUTED, kept not deleted:** round 2 scored the DoD item "unique-content measured per clone"
> as **PASS** while five rows carried `unpushed: null` with the note *"no_remote: unpushed is
> undefined, not 0"*. Declining to report a false 0 was right; scoring the item PASS was not.
> `null` is the **absence of a measurement**, and these five are the highest-risk rows on the
> board — with no remote, no push can have carried anything out of them. Round 2 named the
> settling experiment in its own residual #2 and did not run it. This runs it.

Measured at **blob** level, not commit level, because commit-object identity is the wrong
instrument: `REPO-TOPOLOGY.md` rule 4 and this lane's own round-1 finding both record that
squash-merge keeps a unique commit SHA forever, so an absent commit says nothing about absent
content. What matters for data loss is whether the **bytes** exist elsewhere.

| checkout | commits | tracked blobs | absent by raw SHA | genuinely unique |
|---|---|---|---|---|
| `…/plugins/cache/…/plugin-install-64I3il/…/0.2.0` | 0 | — | — | nothing committed |
| `…/Temp/adv0010/repo` | 2 | 7,323 | 5,518 | **0** |
| `…/Temp/adv0010/repo2` | 2 | 7,323 | 5,518 | **0** |
| `~/source/_advver_M14/chk` | 1 | 5,561 | **0** | **0** |
| `~/source/_advver_M14/scratch` | 0 | — | — | nothing committed |

**The 11,036-blob false alarm, and what caught it.** The first probe stopped at raw SHA and
reported 5,518 blobs absent from the canonical store in each of the two `adv0010` checkouts.
Written up unchecked, that is "two checkouts hold 11,036 files that exist nowhere else" — a
fleet-scale data-loss alarm. It is an artifact. **5,518 of 5,518 contain CRLF, and 5,518 of
5,518 are present in canonical after CRLF→LF normalisation.** Every one is a line-ending twin of
a blob already in the store. Round 1 had already burned a control on this exact shape — its
content signal read `positive=False negative=False` because the tree is CRLF and git stores LF —
and the lesson is in `windows-shell.md` §8b. It still nearly shipped a second time.

**Controls, both states:** the hasher must reproduce a known canonical blob's SHA exactly and
must *not* reproduce it from a deliberately mangled copy of the same bytes; the reader must find
a known SHA and miss a fabricated one. A hasher that cannot tell a mangled copy apart makes every
number in the table meaningless, so it is checked before any of them is believed.

**What is NOT cleared by this.** The two 0-commit rows have nothing committed to compare, so the
blob test is silent about them by construction — and `~/source/_advver_M14/scratch` is precisely
where the exposure lives: no commits, no remote, thousands of untracked entries in no store
anywhere. That is an **uncommitted** exposure, not an unpushed one, and it remains open (§7 R9).

---

## 3. Q3 — inbound references

use-vs-mention applied at the **field** level, not the document level. No line from a
credential-bearing file was ever printed.

### Nothing schedules, PATHs, or env-references any checkout

> **SCOPE CORRECTED 2026-08-14 (round 3) — the conclusion survives, its evidence did not cover
> the population it was quoted for.** Everything in this subsection was measured over **25**
> checkouts. Round 2 then scored the lane's DoD item "inbound-reference measured per clone" as
> PASS over **178**, on the strength of `classify_population.py` — whose corpus is *config files
> only* (`~/.claude/{hooks,skills,commands,workflows,agents,rules,plugins}`, `~/.agents`,
> `~/.codex`, `~/.local/opt`, seven named files). Scheduled Tasks, PATH and the environment are
> not in that corpus, so three of the five pointer kinds the DoD enumerates were carried at the
> 25-row scope into a 7×-larger population. Error direction was the dangerous one: a checkout a
> scheduled task launches from would read `inbound_exec = 0` and land in the retire list.
> Re-measured at 178 in **§3b**, where the answer is still zero — now with evidence that covers
> the claim.

- **Scheduled Tasks: 0 hits across 330 task-actions** (`Execute` / `Arguments` / `WorkingDirectory`).
  **Control, both states:** the same scanner finds `mcp_agent_mail`, `MCPAgentMail` and `Prekzursil`
  in that task set and correctly misses a fabricated string — so the silence is meaningful. This
  **refutes**, for this repo, the briefed premise that a scheduled task is registered against a
  disposable worktree. Scoped: action fields only; a task running a wrapper script that internally
  `cd`s into a checkout is invisible to this probe (§7 R3).
- **PATH (User + Machine): 0. Environment variables: 0.**

### The 8 load-bearing references — every one points at `~/source/agent-skills-toolchain`

| consumer | field | breaks if the path moves |
|---|---|---|
| `~/.mcp.json` | `.mcpServers.{cloud-hub,social-hub,search-hub}.args[0]` | 3 MCP servers |
| `~/.claude.json` | `.mcpServers.qdx-rush.args[2]`, `.mcpServers.scholarly-access.command` | 2 MCP servers |
| `~/.codex/config.toml:201` | `command = …/tools/scholarly-access-mcp/.venv/Scripts/….exe` | Codex MCP |
| `~/.codex/config.toml:475` | `[projects.'…agent-skills-toolchain']` | Codex trust entry |
| `~/.claude/settings.local.json` | `.permissions.allow[30..33]` | 4 permission grants |
| `~/.agents/skills/crcp-health/crcp_health_monitor.cmd:3` | `set "CRP=%USERPROFILE%\source\…\tools\crcp"` | CRCP health monitor |
| `~/.local/opt/mcp-http-host/run_host.ps1:59` | `[string]$Repo = "$HOME\source\agent-skills-toolchain"` | MCP HTTP host default |
| `~/.claude/workflows/reconcile-all-branches-prs-imporant.js:12` | `const TC = 'C:/…/agent-skills-toolchain'` | that workflow |

`~/.codex/config.toml:319`/`:968` additionally register `~/Documents/Playground` as a trusted Codex
project.

**Soft, degrading — the only reference to `ast-integrate`:**
`~/.claude/skills/claude-science-local/cs_monitor.py:52` (and its `.agents` twin) lists
`ast-integrate/scripts/claude-science/cs.ps1` as the **third fallback** in a candidate list and
returns `None` if all three miss.

**Correctly excluded as mentions** — `~/.agents/harness/modules.py:1036` (the path is inside a
*warning-message string*), two `~/.claude/workflows/*.js` prose templates, and ~200
`.codex/plugins/cache/**` archived audit JSON. A naive "executable extension ⇒ dependency" rule
scored **208** hits for canonical; field-level resolution reduces it to **8**.

**Referenced by nothing at all: 23 of 25 checkouts.**

---

## 3a. CORRECTED 2026-08-14 — a third checkout IS referenced, and §4 calls it disposable

> **REFUTED:** "every one of the load-bearing field-level references points at
> `~/source/agent-skills-toolchain`". Kept, not deleted, because the *method* that produced it is
> still the better method — what was wrong is that it was only ever run over 25 of 178 paths.

Re-run over the full 178 (`classify_population.py`, one corpus pass, hits split by whether the
naming file lives INSIDE a checkout of this repo), **three** checkouts are named by live harness
config:

| checkout | harness refs | where |
|---|---|---|
| `~/source/agent-skills-toolchain` | 12 | `.claude.json`, `.codex/.codex-global-state.json`, a `.claude/workflows/*.js`, codex job state |
| `~/Documents/Playground` | 6 | `.codex/config.toml` (+ 3 backups of it) |
| **`~/source/ast-harness-reconcile`** | **1** | `.codex/.codex-global-state.json` → `local-projects.<uuid>.rootPaths[0]` |

The third is the finding. `rootPaths[0]` is a field Codex **reads** to resolve a registered local
project — not prose. **§4 lists `ast-harness-reconcile` as a RETIRE candidate**, and §5's rule says
"no config/task/hook/skill may reference one". So a live tool is registered against a checkout this
document says is disposable — the same shape as the scheduled-task-on-a-scratch-worktree class,
found by widening the population rather than by any new technique.

It is also the second time this exact path has broken a §4 verdict: the `refs/stash` correction
below was likewise a rule that contradicted `ast-harness-reconcile`'s RETIRE listing.

---

## 3b. The three surfaces re-measured at 178 — added 2026-08-14, BUILD round 3

`inbound_surfaces.py`. Windows Scheduled Tasks, PATH (Machine+User) and the environment
(Machine+User), intersected with all 178 checkouts. **All three are silent.**

| surface | read | checkouts named |
|---|---|---|
| Scheduled Tasks | **329 actions** (172 with an `Execute`) | **0** |
| PATH | **87 entries** | **0** |
| Environment | **388 variables** | **0** |

**Why the silence is believable this time.** Each surface is scanned three times: once over the
real data, once over the real data **plus one synthetic row naming a real population path**, and
once plus a fabricated path. The synthetic run must gain exactly one hit and the fabricated run
must gain none — otherwise a zero would be indistinguishable from a reader that cannot see the
surface at all. All three discriminate (`0 → 1 → 0`). Each surface also carries a plausibility
floor and fails closed below it, so "0 tasks" can never be reported as "no task references a
checkout". The synthetic row exists only in the probe's memory: no task is created, no variable
is set, and env values are matched in memory with only the VARIABLE NAME ever recorded, because
this surface sits next to live credentials.

Two hypotheses were named before the probe ran — H1 "nothing references a checkout" and H2 "the
extractor cannot see this surface" — precisely so the control could tell them apart. It does.

**Consequence:** the 43 retire candidates in §5a were computed from a config-only scan, and that
scan is now corroborated on the three surfaces it never covered. No verdict changes.

### 3c. Every reference resolved to its FIELD — no row left to hand-reading

`resolve_ref_fields.py` parses each naming file (TOML/JSON) and walks it for keys whose **name**
or **value** resolves to a checkout, so a hit is a field, not a document. Round 2 left
`Documents/Playground` as "6 hits, not re-resolved"; that residual is now **CLOSED**.

| checkout | live fields | kind |
|---|---|---|
| `~/source/agent-skills-toolchain` | 16 | MCP server `command`/`args`, `workspaceRoot`, Codex `local-projects.*.rootPaths[0]`, thread cwd/path, `remote-projects[0].remotePath` |
| `~/Documents/Playground` | **2** | `~/.codex/config.toml` → `projects."…\Playground"` (trust registration) and `desktop.open-in-target-preferences.perPath."…\Playground"` |
| `~/source/ast-harness-reconcile` | 1 | `~/.codex/.codex-global-state.json` → `local-projects.<uuid>.rootPaths[0]` |

The other 4 of Playground's 6 file-level hits are **backups** of that config (`.agents/backups/*`,
`.codex/backups/*`) — counted, and correctly not treated as live. One naming file is not
field-resolvable: `~/.claude/workflows/reconcile-all-branches-prs-imporant.js` is JavaScript, not
a parseable config; it names canonical, which is KEEP regardless, so no verdict rests on it.

**Control:** the walker is run against a synthetic document containing one table-key hit and one
value hit, and against a fabricated path. It must find exactly 2 of both kinds and 0 — proving it
descends the tree rather than returning empty for every document.

**Detector honesty.** The first version of this scan scored 5 checkouts, and the two extra were
artifacts of the naive rule this document already warns about — `.codex/plugins/cache/**` audit
JSON naming worktree paths, and a plugin-cache copy of this repo whose `tools/crcp/**` test
fixtures name their own directory. Filtering hits whose source file lives inside the population
removed both, and a both-states control confirms the filter does not also remove canonical's real
harness hits (12 kept, 12 reclassified as intra-repo; fabricated path still 0).

UNVERIFIED, inline: the 3 survivors are field-level for canonical and `ast-harness-reconcile`
(both hand-resolved to a JSON key path above) but the `Documents/Playground` hits were **not**
re-resolved key-by-key this round. Settling experiment: resolve each of the 6 to its TOML key in
`.codex/config.toml`, as §3 did for the original 8.

---

## 4. Verdicts

**KEEP (2)** — `~/source/agent-skills-toolchain` (8 load-bearing refs; 2 dirty are `accounts.json`,
the live rotation pool — do not touch) and `~/source/ast-integrate` (holds `main`).

**RECONCILE BEFORE ANYTHING ELSE (8)** — hold unique commits and/or substantial uncommitted work:

**Priority within this list was re-ordered 2026-08-13 by the §2b content check — the original
ordering put a solved problem first.** Correct order of attention: `D:/wt-salvage-probe` (2 files
absent from main, in a destroyable staged index) → `_b5-toolchain` (3 files absent) →
`agent-425276811/ast` (DIVERGED, needs judgement) → everything else. `CRCP-SEC` drops off the
reconcile list entirely.

| checkout | why |
|---|---|
| `.claude/agent-worktrees-salvage/agent-425276811/ast` | 1 unique unpushed bugfix + 7 dirty — §2b: all 5 files **DIVERGED**, needs judgement |
| `.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | 2 unique unpushed feature commits — §2b: 3 files **ABSENT from main**, genuinely the only copy |
| ~~`source/_wu/CRCP-SEC`~~ | **NO LONGER RECONCILE WORK.** §2b measured the fix byte-identical on `main` (both proving tests included), corroborated by an independent hash signal. Reclassify as a RETIRE candidate once its 2 stale DIVERGED files (`quality.yml` is **689 lines behind** main) are confirmed unwanted. |
| `.claude/codexsrc-work` | 81 uncommitted, all under `tools/editor/metaswarm/` |
| `~/Documents/Playground` | 111 uncommitted; separate repo with its own worktree |
| `.codex/plugins/cache/…/0.2.0` | 57 dirty + 1 stash + the §7 R4 hazard |
| `source/ast-patch167` (store B, 3 checkouts) | 3 unique unpushed verify commits + 8 dirty |
| `work/agent-skills-toolchain-re` | 3 reflog-only orphans, frozen since 2026-04-01 |

**RETIRE CANDIDATES — clean, zero unique commits, zero inbound references (11):**
`~/.claude/toolchain-audit` (dead since 2026-07-14) · `~/.claude/tw-merge-work` ·
`D:/sast-depth/agent-skills-toolchain` · `~/source/ast-harness-reconcile` ·
`~/.claude/scratch/ast-gp-main` · `~/.claude/harness-restore-20260806/wave3/ast-cc` ·
`~/source/_cons/C8/tc` · `~/source/_verify/v-l01` · `D:/pr-b3-clone` ·
`~/source/_verify_M04_tree` · `~/source/_verify_M13` · `~/.codex/worktrees/8528/Playground`.
Two more need triage first: `D:/inc1-wt/ast-increment1` (1 untracked) and — **upgraded
2026-08-13 from "nearly clean" to the fleet's highest-urgency item** — `D:/wt-salvage-probe`.
Its **2 staged-but-uncommitted adds** are `ci/tests/test_codex_profiles.py` and
`tools/monitorcore/r0_monitor_live_gate.py`, and §2b measured **both ABSENT from `main`**: this
is real authored content that exists in exactly one place, held in a staged index that
`git worktree remove` destroys. It is **not** a retire candidate until those two files are
committed to a pushed branch or copied out.

---

## 5. Q4 — the SSOT rule

> **The GitHub remote is the SSOT for history; `~/source/ast-integrate` is the only checkout you
> EDIT and `~/source/agent-skills-toolchain` is the only checkout anything EXECUTES from — every
> other checkout is disposable scratch, so no config/task/hook/skill may reference one, and none may
> be retired until its work is on a pushed branch.**

Mechanically checkable corollaries:

1. **Creating:** always `git -C <intended repo> worktree add …`. Bare `git worktree add` resolves
   the repo from cwd and has already landed agents in an unrelated project (`REPO-TOPOLOGY.md` r5).
2. **Retiring:** requires all four — `unique_commit_count == 0`, `git status --porcelain -uall`
   empty, **no worktree-local staged index or stash entry** (see the correction below), zero
   field-level inbound references. Produced by `measure_all25.py` + `scan_inbound_refs.py`.

   > **CORRECTED 2026-08-13 — the original third precondition was `git stash list` empty, which
   > can NEVER pass for a linked worktree and contradicted this document's own retire list.**
   > `refs/stash` is **store-level, not worktree-level**: all **five** store-A checkouts report
   > stash-count 2 and the *identical* `refs/stash` = `d90474213cca...` — canonical,
   > `ast-integrate`, `ast-harness-reconcile`, `D:/inc1-wt/ast-increment1` and
   > `D:/wt-salvage-probe`. So the criterion was simultaneously false for every store-A
   > checkout, including `ast-harness-reconcile`, which §4 lists as a RETIRE candidate. Error
   > direction was SAFE (a false blocker, never a false permission), but the rule was unusable.
   > **The right criterion splits by kind**, because removing a worktree destroys its *index*
   > and not the shared stash:
   > - **independent clone** → `git stash list` empty (the stash is its own).
   > - **linked worktree** → `git diff --cached --quiet` (empty index) **and** no reflog-only
   >   commits unique to that worktree. Measured: `staged` genuinely differs per worktree
   >   (0 / 3 / 0 / 0 / 2 across the five), so the index is the discriminating signal and the
   >   stash is not.
3. **Scratch belongs on a pushed branch or it does not exist.** Four real commits were stranded
   precisely because agent worktrees had no push-before-exit step.

---

## 5a. The full 178, classified — added 2026-08-14, BUILD round 2

§1–§4 are computed over 25 checkouts. This closes that gap over the corrected population.
`classify_population.py` → `population-classified.json`. An algorithm, not a fan-out: every axis
here is file-vs-directory, set membership, or counting, and `fan-out-contract.md` §C4 measured
what happens when that class is handed to LLM judgement (86% accuracy, **100% of the errors
pointing at data loss**).

| axis | measured |
|---|---|
| population | **178**, all 178 still on disk |
| linked worktrees | 9 |
| independent clones (own object store) | 168 |
| severed worktrees (added round 4) | 1 |
| **kind arithmetic** | 9 + 168 + 1 = **178** = on-disk ✓ |
| primary kind signals disagree | 1 — the severed row; resolved by a third signal, still recorded |
| distinct object stores | 168 |
| named by live harness config | **3** (see §3a) |
| holding unpushed commits, dirty or staged files | **132** |
| no remote at all (nothing is in git anywhere else) | 5 |
| clean **and** referenced by nothing **and** has a remote | **43** ← retire candidates |

Controls, all three both-states and all passing: a known linked worktree reads FILE/outside while
a known main checkout reads DIR/inside · the dirty counter reads 315 on a known-dirty tree and 2
on the other · a known-referenced path is found and a fabricated one is not.

**The 132 is the number that matters, not the 178.** It is the fleet's uncommitted-work surface,
and it is 5.3× the entire population this document was originally written about. Nothing here
licenses a deletion: 43 rows meet the retire preconditions, and the recommendation is still to
move a directory aside rather than run `git worktree remove`, which follows junctions and deletes
their targets.

The one `kind-signals-disagree` row is `.codex/plugins/cache/agent-skills-toolchain/
plugin-install-64I3il/agent-skills-toolchain/0.2.0`: its `.git` is a FILE, but every git command
run inside it fails, so `--git-common-dir` returns nothing. That is an independent corroboration
of residual **R4** — the plugin cache holds a copy of canonical's worktree admin dir whose
pointers do not resolve from there. It is also why nothing in this round ran a `worktree`
subcommand anywhere: `git worktree repair` rewrites links **bidirectionally**, so running it from
the cache would repoint the real live worktrees at the cache.

> **REFUTED 2026-08-14 (round 4), kept rather than deleted.** Round 3 wrote that this row "is now
> resolved by a third signal … not left as 'disagrees'", and scored the classification DoD
> **`178/178`, two agreeing signals**. Both sentences were wider than the evidence, and the
> round-3 verifier confirmed it against the blob at HEAD and at two earlier commits: the PROSE was
> resolved, `population-classified.json` was not — it still carried `kind_signals_disagree` with a
> one-element list and no resolution field anywhere, while `CLAUDE.md` points future agents at
> that JSON as the machine-readable SSOT. **Correctly scoped: 177 of 178 rows carry two agreeing
> primary signals; 1 does not, and is resolved by a third.**
>
> Now landed in the artifact, not only the prose. The third signal reads the `.git` FILE's
> `gitdir:` pointer and tests whether that admin dir EXISTS — the row is
> `kind: "severed-worktree"`, `resolved_by: "third-signal:dotgit-file-pointer-target-missing"`,
> `gitdir_target_exists: false`. `signals_agree` stays **false**: the two primary signals really
> did disagree, and deleting that record to make the row look clean would be the same overclaim
> pointing the other way. The file now also carries a `kind_arithmetic` block that fails closed
> when the split stops adding up — the check that would have caught 9 + 168 = 177 against a
> population of 178.
>
> **The negative case is what makes the signal mean anything.** A `.git` FILE alone does not imply
> severance: `~/source/ast-integrate` and `D:/wt-salvage-probe` are LIVE linked worktrees and both
> have one. Measured — severed → `target_exists=False`, both live worktrees → `True`, canonical →
> `.git` is a DIR, fabricated path → missing. A resolver keyed on "`.git` is a FILE" would have
> called all three severed and passed a control while measuring nothing.
> Receipts: `command-center/ssot/apply_severed_resolution.py`, red-proofed 5/5 by
> `command-center/ssot/redproof_severed.py` (healthy→0, floor→3, no-disagreeing-row→1,
> invariant-moved→3, arithmetic-does-not-close→3).

UNVERIFIED, inline: `unpushed_commits` is reported as `null` with the reason `no_remote` for the 5
remote-less checkouts rather than as 0 — with no remote the count is undefined, and reporting 0
there is precisely the false-clean this lane already hit once (`salvage_atrisk.py:24-28`).
Settling experiment: for each of the 5, test each commit's presence in canonical's object store.

---

## 6. Prior art — read this before rebuilding anything

- **`REPO-TOPOLOGY.md`** (repo root) — still the best narrative. Correct and reusable: the
  two-store model, why the main checkout can never hold `main`, the squash-merge/ancestry warning,
  the `git archive` CRLF trap, the `-uall` note, the "identical blob counts prove nothing" note.
  **Stale in three places** this lane corrected: the checkout list (2 gone, 11 unfound), "2 stores"
  (18), and the store-B redundancy claim (3 verify commits uncovered).
- **`command-center/ssot/orchestrator-clone-probe.md`** — the orchestrator's narrow existence probe;
  explicitly defers Q1–Q4 to this lane. Consistent with everything here.
- Do **not** rebuild: worktree tooling already exists at `tools/gitcrypt-worktree/`, and
  `platform/workflows/worktree-isolated-parallel-build.json` already encodes isolated-worktree runs.

---

## 7. Residuals — each with the experiment that settles it

- **R1 — CLOSED.** The exhaustive sweep finished: 911 git checkouts walked under `~` and `D:/`,
  25 belong to this repo. Depth cap 7 and `AppData`/`node_modules` excluded, so a checkout nested
  deeper or inside `AppData` would still be missed (**almost certain (90–99%)** that 25 is complete
  for the scanned scope).
- **R2 — store B's three verify commits are not content-checked.** `REPO-TOPOLOGY.md` verified
  `pr242/244/245/249` byte-for-byte; `d9ec177`, `be60f18`, `6451b18` were not in that table.
  **Settle:** `git -C ast-patch167 diff <sha>^..<sha> --name-only`, then compare each path against
  `git -C ast-integrate cat-file -p origin/main:<path>` — never `git archive` (CRLF on this box).
- **R3 — scheduled-task indirection.** Action fields only. **Settle:** extract each task's
  `Execute`+`Arguments` script path and grep those files' contents.
- **R4 — MEASURED 2026-08-14 (round 3), and the hazard is armed.** `r4_cache_worktree_probe.py`:
  the cache admin dir holds **5 registrations, 3 of them ARMED** — the `gitdir` names a directory
  that exists right now: `~/source/ast-harness-reconcile`, `D:/inc1-wt/ast-increment1`, and
  `~/source/ast-integrate` (this worktree). `ast-statusline-capture` and `D:/ckwt/cookie-bridge-skill`
  are stale, their targets gone. **A contradiction had to be resolved to trust this:** the cache
  row that `classify_population.py` reports as `kind-signals-disagree` has a `.git` that is a
  FILE, and a file cannot contain `worktrees/*/gitdir`. There are **two** cache copies —
  `…/agent-skills-toolchain/agent-skills-toolchain/0.2.0` (`.git` is a DIRECTORY, R4's subject)
  and `…/plugin-install-64I3il/…/0.2.0` (`.git` is a FILE pointing at
  `<canonical>/.git/worktrees/agent-skills-toolchain`, which **does not exist**, so every git
  command there exits 128). Both are in the population; neither was mis-enumerated. The apparent
  self-contradiction was a two-paths problem, not a detector failure — but only measurement could
  establish that. Whether a cache-side `worktree remove` would delete a real tree stays
  **UNVERIFIED**: the probe is destructive and was not run, and declining it is still correct.
  The standing instruction is unchanged and now has a measured blast radius.
- **R4 (original wording, superseded) — the Codex plugin cache holds a COPY of canonical's worktree admin dir.**
  `.codex/plugins/cache/…/0.2.0/.git/worktrees/{ast-integrate,ast-harness-reconcile,ast-increment1,
  ast-statusline-capture,cookie-bridge-skill}/gitdir` point at the **real live directories**. The
  link is one-directional — the real `ast-integrate/.git` points back at canonical, not the cache —
  so the registration is stale. Whether `git -C <cache> worktree remove ast-integrate` would delete
  the real tree is **UNVERIFIED**; the probe is destructive and I did not run it. **Settle:** test
  it against a throwaway worktree, never a live one. Until then, never run a `worktree` subcommand
  from the plugin cache.
- **R5 — `git worktree remove` follows junctions.** Carried from the orchestrator brief (measured
  2026-08-10). Not independently re-verified — destructive by nature. I did measure that **no
  checkout root holds a junction/reparse point at depth 1** (`FILE_ATTRIBUTE_REPARSE_POINT` 0x400),
  so the hazard is not armed at the top level; deeper levels unscanned. **Settle:**
  `fsutil reparsepoint query` over a tree before removal, or move the directory aside instead.
- **R6 — snapshot, not steady state. Every count in this document is a snapshot and several have
  already moved.** `main` took five values across one evening: `ae8205a4` → `9353ed1f` →
  `86dde6c1` → `f5b596e6` (local, 5 ahead of the remote) → `df6377ab` (this document's own
  commit). `ast-integrate` dirty `-uall` went 137 → 298 → 341 → 327. Canonical's "159 behind"
  read 161 within the hour. **Re-run `measure_all25.py` before acting on any number here** — and
  do not treat a changed count as a contradiction of this document.
- **R8 — CLOSED 2026-08-13: this document and its receipts were untracked.** Measured before the
  fix, with working controls (`git ls-files docs/` = 185, `REPO-TOPOLOGY.md` tracked, so the zeros
  were real): `docs/ssot/` 0 of 1 tracked, `command-center/ssot/` 1 of 24. The document defining
  the SSOT rule existed only in one working tree holding 327 dirty entries — one `git clean -fd`
  from unrecoverable, and invisible to the other 24 checkouts. The lane about drift had
  reproduced the `harness-vcs-hygiene` failure it exists to prevent. Fixed by `df6377ab`
  (25 files); postcondition re-measured 1 and 25 tracked. A secret preflight ran first, because
  `inbound-refs.json` came from scanning `~/.claude.json`, `~/.mcp.json` and
  `settings.local.json`: 0 credential-shaped findings over 800,445 chars with a both-states
  control, corroborated by the payload schema storing `{file, line, kind}` — line *numbers*, not
  line content.
- **R7 — disk is only measured for 12 of 25** (3.31 GB, itself an over-count because of the shared
  hardlinked packs). Disk is not the argument here; drift and split-brain are.
- **R9 — OPEN, and it is now the sharpest exposure on the board.** `~/source/_advver_M14/scratch`:
  **0 commits, no remote**, thousands of untracked entries, so nothing in it is in git anywhere.
  §2c clears the *committed* content of the no-remote five and says nothing about this, by
  construction. Round 1 snapshotted 21 live lane artifacts out of it; the remainder is
  unprotected. It was under **active write by other lanes** while being measured, and a
  uniqueness census of a moving target cannot license any action — which is why it was measured
  and left alone, not retired. **Settle:** `find <dir> -newermt '10 minutes ago'` to establish it
  is quiescent, then run the §2c blob probe over its *working tree* rather than a tree-ish.
- **R10 — the population is 178 distinct REAL paths, re-tested at the new size.** Round 1's
  junction dedupe and the round-1 audit's 0-collision check were both taken at 170; round 2 added
  8 rows without re-testing. Re-run at 178 (`noremote_and_alias.py`): **178 realpath groups, 0
  collisions**, with a control proving a known junction pair collapses and a known-distinct pair
  does not. Two rows are spelled through the legacy `Local Settings` junction and neither has its
  resolved twin in the population, so 178 is not inflated by aliasing.

---

## 8. Reproduce — all read-only, in `command-center/ssot/`

| script | answers |
|---|---|
| `sweep_all_checkouts.py` | the authoritative 25/18 enumeration → `full-sweep.json` |
| `measure_all25.py` | Q1 + Q2 for the full fleet, `-uall` → `all25.json` |
| `measure_clones.py` / `measure_unique_depth.py` | first-pass 14-checkout detail + remote decomposition |
| `report_pass3.py` | origin URLs, unpushed decomposition, dirty detail |
| `scan_inbound_refs.py` → `verify_refs.py` | Q3 raw hits, then detector controls + field resolution |
| `storeb_safety.py` | store-B ancestry, with both-states ancestor control |
| `exec_vs_edit.py` | executed-vs-edited drift → `exec-vs-edit.json` |
| `content_check.py` | §2b — stranded work vs `origin/main`, bidirectional → `content-check.json` |
| `_verify_identical.py` | independent hash corroboration of the retire-authorising verdicts → `verify-identical.json` |
| `_secret_preflight.py` | credential-shape preflight with both-states control, run before any commit here |
| `ssot_drift_gate.py` | is the EXECUTED checkout stale against `main`? exit 1 drift / 3 fail-closed |
| `ssot_wiring_check.py` | §9 — is the rule above still REACHABLE and consistent? six wires |
| `_integrate_redproof.py` | the before/after red-proof of §9, rebuilt from `git show HEAD:` |
| `identity_by_ancestry.py` | the identity test; rc 0/1/128 kept apart → `identity-by-ancestry.json` |
| `classify_population.py` | all 178 on every DoD axis → `population-classified.json` |
| `inbound_surfaces.py` | §3b — Scheduled Tasks + PATH + env at 178, synthetic-row controls → `inbound-surfaces.json` |
| `resolve_ref_fields.py` | §3c — every reference resolved to its config KEY, values never emitted → `ref-fields-resolved.json` |
| `noremote_and_alias.py` | §2c + R10 — realpath collisions at 178, and the no-remote blob census → `noremote-alias.json` |
| `noremote_content_truth.py` | §2c — is the absent-blob gap unique content or CRLF? → `noremote-content-truth.json` |
| `r4_cache_worktree_probe.py` | R4 — which cache-held worktree registrations are ARMED → `r4-cache-worktrees.json` |

---

## 9. Where the rule is ENFORCED — added 2026-08-13, INTEGRATE round

Sections 1-8 are a measurement. On their own they were **unreachable**: nothing in the harness
loads `docs/`, and nothing invoked `ssot_drift_gate.py`. This section records the wiring, so a
future agent can find it and a mechanical check keeps it honest.

- **The rule an agent actually reads** is the `<!-- SSOT-WIRE -->` block in the repo-root
  `CLAUDE.md`. That file is git-tracked and auto-injected into any session whose cwd is this
  checkout, with no deploy hop. The blockquote there is **the §5 sentence, verbatim** —
  `ssot_wiring_check.py` code `W2-rule-sentence-drift` fails CI if the two copies ever diverge,
  so §5 remains the single source and the `CLAUDE.md` copy cannot rot silently.
- **`rules/common/` was measured and REJECTED as the home.** `~/.claude/rules` is a plain
  directory, not a junction, and its `harness-vcs-hygiene.md` is 2149 bytes against the repo's
  3142 — **993 bytes stale**. A repo-only rule edit would not have reached a live session. It
  would have looked wired and not been.
- **The gate runs in CI**, via `ci/tests/test_ssot_wiring.py`: collected by the
  `pytest ci/tests` sweep in `.github/workflows/skill-dual-write.yml` and additionally named by
  an explicit `gate-ssot-wiring self-test` step, because that workflow's own comments record
  that the sweep is one refactor away from not containing a given file.
- **Six wires, six paired mutations, plus a synthetic-repo proof** that `ssot_drift_gate.py`
  returns 1 on drift, 0 at parity, 3 fail-closed and 2 on misconfiguration — which is what makes
  a gate aimed at one Windows path verifiable on a Linux runner.

Residual, inline: this is wired for CI and for a session **in this checkout**. It is NOT a hook,
so nothing runs the drift gate at turn-end; and because `CLAUDE.md` is per-checkout, an agent who
opens a stale checkout reads a copy without this block. Both are argued and measured in
`command-center/ssot/INTEGRATE-2026-08-13.md` §5, with the experiment that settles each.