# Lane: hygiene — Measured anti-patterns and hygiene

**Status: IN PROGRESS — item (a) MEASURED + reclaim pending. Items (b)-(e) UNKNOWN.**
Host: OFFLOAD-W2025 (disposable VM). Profile: `C:/Users/prekzursil`.
Last rewrite: 2026-09-25 ~23:16Z.

Every claim is labelled VERIFIED (exact command + output) or INFERRED, with a confidence band.

---

## (a) Plugin cache temp_git clones — **PREMISE PARTLY REFUTED**

### The refutation (the most important result in this item)

The lane brief says *"Plugin cache is 13 GB with 111 temp_git clones"*, which reads as
*the 111 temp_git clones are the 13 GB*. **They are not.** Measured split of
`~/.claude/plugins/cache`:

| Kind | Dirs | Files | Bytes | GB | % of cache |
|---|---|---|---|---|---|
| `named` (real marketplace clones) | 9 | 404,759 | 11,586,347,194 | 10.791 | **94.5%** |
| `temp_git_*` | 111 | 12,686 | 583,077,022 | 0.543 | 4.75% |
| `temp_subdir_*.clone` | 355 | 2,274 | 96,832,774 | 0.090 | 0.79% |
| **TOTAL cache** | **475** | **419,719** | **12,266,256,990** | **11.424** | 100% |

- **VERIFIED**, confidence 95-99%. Command: `scratchpad/measure_fast.ps1` (DirectoryInfo.EnumerateFiles,
  ReparsePoint-skipping, 5.3 s). Output verbatim:
  `named dirs=9 files=404759 bytes=11586347194 GB=10.791` /
  `temp_git dirs=111 files=12686 bytes=583077022 GB=0.543` /
  `temp_subdir dirs=355 files=2274 bytes=96832774 GB=0.09` /
  `TOTAL_cache bytes=12266256990 GB=11.424`
- **The 13 GB is one directory: `claude-plugins-official` = 11,011.30 MB across 402,620 files.**
  That is a LIVE marketplace clone, referenced by `known_marketplaces.json`. Rule 3 forbids
  touching it, and it is the correct call — it is configuration, not residue.
- **Second refutation:** the brief counted only 111 temp_git dirs. There are **466** residue dirs —
  111 `temp_git_*` plus **355 undocumented `temp_subdir_*.clone`** dirs. The residue problem is
  4x wider in dir count than reported, and ~20x smaller in bytes.

So the honest headline is: **~635 MB / 466 dirs of reclaimable residue, not 13 GB.**

### Proving the residue is genuinely orphaned build residue

Four independent checks, all VERIFIED:

1. **Zero config references.** `temp_git_` and `temp_subdir_` appear **0 times** in
   `settings.json`, `.claude.json` (read-only), `installed_plugins.json`,
   `known_marketplaces.json`, `plugin-catalog-cache.json`, `blocklist.json`,
   `.last_inuse_sweep`. A Grep over `plugins/**/*.json` also returned
   `Found 0 total occurrences across 0 files`. Confidence 95-99%.
2. **All origins are third-party public GitHub repos.** 161 of 466 contain `.git`; every one
   with an origin points at a public upstream marketplace repo — `awslabs/agent-plugins`,
   `astronomer/agents`, `heygen-com/hyperframes`, `semgrep/mcp-marketplace`, `pydantic/skills`,
   `cloudflare/skills`, 47 distinct origins in total. **Not one** is an owner repo. Every byte is
   re-fetchable from a public remote. Confidence 90-95%.
3. **No owner-authored work.** `git rev-list --count HEAD --not --remotes` flagged 9 dirs with
   "1 unpushed commit". Investigated each: **all 9 HEAD commits are authored by upstream
   maintainers** — `kesku@exa.ai`, `viacheslav.tsuvariev@sonarsource.com`,
   `sander.keymeulen@hotmail.com`, `browser-automation-bot@…`, etc. Local git identity is
   `prekzursil1993@gmail.com`; **it authored none of them**. The flag is a shallow-clone artifact:
   the installer leaves HEAD detached at a release commit that is not an ancestor of the
   shallow-fetched `main` tip (e.g. `temp_git_…_gj9vgq`: HEAD `15ffb50` (Aug 20) vs
   `refs/heads/main` `f3d71fb` (Sep 22), `merge-base --is-ancestor` exit 1, `.git/shallow` present).
   Confidence 90-95%.
4. **The 51 "dirty" trees are installer mechanics, not edits.** Porcelain shows staged deletions
   (`D  .claude-plugin/marketplace.json`, `D  .claude-plugin/plugin.json`, …) — the sparse/partial
   checkout signature. No owner content. Confidence 85-90%.

### A hypothesis I formed and then REFUTED myself

I suspected the residue also inflates **skill-listing pressure**, which would make this a context
win rather than a mere disk win. It does not. Measured:

- 606 of the 2,166 `SKILL.md` files under `plugins/` (**28.0%**) live inside residue dirs.
- 331 distinct skill names appear in residue; **23 of them exist nowhere else on disk**.
- Of those 23, exactly one (`firecrawl`) is in this session's skill listing — and it resolves to
  `~/.claude/skills/firecrawl` **and** `~/.agents/skills/firecrawl`, i.e. the local tree, not the residue.
- The other 22 (`airflow-state-store`, `cloudflare-one`, `fastly-fiddle`, `fiftyone-app-playwright`,
  `mapbox-navigation-patterns`, `output-dev-llm-streaming`, `migrating-dagster-to-airflow`,
  `authoring-go-sdk-tasks`, …) are **absent from the session's skill listing** and exist nowhere
  outside residue.

**Conclusion: the skill loader does not read residue dirs. Reclaiming them buys 0 context tokens.**
VERIFIED, confidence 85-90%. The reclaim is disk-only, and I will not claim otherwise.

### Cross-lane correction for the other lanes (useful side effect)

The ground-truth figure *"2,160 plugin SKILL.md"* is a recursive count under `plugins/`, so it
**includes the 606 never-loaded residue files**. Measured per-subtree:

| Subtree | SKILL.md |
|---|---|
| `plugins/` (recursive, what the ground truth counted) | 2,166 |
| ‣ `plugins/cache` residue (NOT loaded) | 606 |
| ‣ `plugins/cache` named marketplaces | 1,434 |
| ‣ `plugins/marketplaces` | 79 |
| ‣ `plugins/synced` | 34 |
| ‣ `plugins/metaswarm` | 13 |
| ‣ `plugins/data` | 0 |
| `~/.claude/skills` | 468 |
| `~/.agents/skills` | 467 |

**True loadable plugin SKILL.md ≈ 1,560, not 2,160 — the pressure figure is overstated by ~28%.**
Any lane sizing a fix against 2,160 is sizing against a number that includes dead files.
VERIFIED, confidence 85-90%.

### The reclaim tool

`C:/Users/prekzursil/.agents/scripts/reclaim-plugin-cache-residue.ps1` — **dry-run by default**,
`-Apply` to act. Six gates, every one re-asserted immediately before each destructive call:

| Gate | Refuses |
|---|---|
| G1 PATTERN | basename not matching `^temp_(git\|subdir)_\d{13}_[a-z0-9]+(\.clone)?$` |
| G2 PARENT | anything whose parent is not exactly the cache root (no recursion, no nesting) |
| G3 AGE | name-epoch younger than `-MinAgeHours` (default 6) — in-flight guard |
| G4 MTIME | mtime younger than `-MinAgeHours` — second in-flight guard |
| G5 ORIGIN | a `.git` dir with no `origin` (cannot prove re-fetchable) |
| G6 AUTHOR | any commit on HEAD-not-remotes authored by the local `user.email` |

**BOTH-STATES PROOF — VERIFIED.** `-SelfTest` builds a fixture and asserts each classification;
exit 0 only if all 9 cases are correct. Observed output:

```
=== SELF-TEST: GOOD state (each MUST be Eligible) ===
  [PASS] plain old residue, no git                  -> Eligible=True  OK: all gates passed
  [PASS] old .clone subdir                          -> Eligible=True  OK: all gates passed
  [PASS] clone w/ origin, upstream-authored commit  -> Eligible=True  OK: all gates passed
=== SELF-TEST: BROKEN state (each MUST be refused by the named gate) ===
  [PASS] G1 wrong name         -> Eligible=False  G1-PATTERN: name is not a residue staging dir
  [PASS] G1 no epoch           -> Eligible=False  G1-PATTERN: name is not a residue staging dir
  [PASS] G3 too new            -> Eligible=False  G3-AGE: name-epoch age 0.00h < 6h (may be in flight)
  [PASS] G5 git w/o origin     -> Eligible=False  G5-ORIGIN: git dir with no origin - cannot prove re-fetchable
  [PASS] G6 owner-authored     -> Eligible=False  G6-AUTHOR: has local commit(s) authored by prekzursil1993@gmail.com - owner work, never delete
  [PASS] G2 nested one level down -> Eligible=False  G2-PARENT: parent '...\nesting_host' is not the cache root
SUCCESS:reclaim-selftest all gates fire on broken input and pass on good input
EXITCODE=0
```

Note G6 names the **real** owner address, so the guard protects live identity, not a fixture value.

### In-flight safety (4 live claude.exe sessions + this workflow)

- Newest residue dir is **2.2 h** old; **0** are younger than 1 h. Age buckets: `<1h: 0`,
  `1-24h: 130`, `1-7d: 255`, `>7d: 81`; oldest 271.1 h.
- The newest batch (`1790368953xxx`, 20+ dirs in the same second, 8:42:33 PM) is a completed
  marketplace sweep: `installed_plugins.json` mtime is **8:42:37 PM**, i.e. the installer wrote its
  result *after* creating them. INFERRED, confidence 80-90%.
- I still use a **6 h** cutoff, which excludes that batch anyway. Cost of the caution: 45 dirs.

### Dry-run result (VERIFIED, before any removal)

```
cache_root   = C:\Users\prekzursil\.claude\plugins\cache
min_age_hours= 6
owner_email  = prekzursil1993@gmail.com
mode         = DRY-RUN
ELIGIBLE dirs = 417   files = 10853   bytes = 556483895   MB = 530.7
SKIPPED  dirs = 58
  G3-AGE         45      <- too new, in-flight guard
  G1-PATTERN      9      <- the 9 named marketplace dirs, correctly refused
  G5-ORIGIN       4      <- origin-less git dirs, cannot prove re-fetchable
```

Full per-dir manifest with bytes + origin, written **before** removal:
`hygiene-reclaim-manifest-BEFORE.txt` (475 lines).

### Reclaim execution — **DONE, VERIFIED**

```
removed_dirs = 417  failed = 0  freed_bytes = 556483895  freed_MB = 530.7
SUCCESS:reclaim   EXITCODE=0
```

Independent before/after measurement (not the script's own arithmetic):

| Metric | BEFORE | AFTER | Delta |
|---|---|---|---|
| cache bytes | 12,268,475,318 | 11,711,991,423 | **−556,483,895 (−530.7 MB)** |
| cache files | 419,887 | 409,034 | −10,853 |
| cache top-level dirs | 475 | 58 | −417 |
| C: free bytes | 3,600,281,600 | 4,176,691,200 | **+576,409,600 (+549.7 MB)** |
| C: free GB | 3.353 | 3.890 | +0.537 |

The script's predicted freed bytes and the independently measured delta agree **exactly**
(556,483,895). C: free rose slightly more (576 MB) than the file-byte total — cluster slack from
10,853 small files. Note C: had only **3.35 GB free**, so this was a 16% increase in free space.

**Integrity checks after the reclaim — all VERIFIED:**

- All 9 named marketplace dirs intact. `claude-plugins-official` still 1,320 `SKILL.md`,
  `anthropic-agent-skills` 60, `metaswarm-marketplace` 14; named-marketplace total still **1,434**
  (unchanged from the pre-reclaim measurement).
- Local skill trees untouched: `~/.claude/skills` = 468, `~/.agents/skills` = 467 (both unchanged).
- Config files byte-identical and mtime-unchanged: `installed_plugins.json` 38,185 B @ 8:42:37 PM,
  `known_marketplaces.json` 2,947 B, `plugin-catalog-cache.json` 406,641 B, `blocklist.json` 414 B.
- `~/.claude.json` was **never written by me** (rule 2). Its mtime does advance on its own —
  the 4 live sessions write it continuously — so mtime is not a valid integrity signal for that file;
  I only ever read it.
- **SKILL.md accounting reconciles exactly:** residue held 606 before; the 49 deliberately skipped
  dirs still hold 277; 606 − 277 = **329**, and the `plugins/` recursive total fell 2,166 → 1,837 =
  **329**. No file outside the removal set was touched.
- The 49 preserved dirs are exactly the ones the gates refused: 45 too-new (`1790368953xxx` batch)
  and the 4 origin-less (`…_43t01d`, `…_ag05s3`, `…_9m93km`, `…_o0en6v`).

**What is now unrecoverable:** the 417 removed staging directories are gone from disk with no
recycle-bin copy. Every one was a shallow/partial clone of a **public third-party** GitHub
marketplace repo (47 distinct origins, all listed in `hygiene-reclaim-manifest-BEFORE.txt`) and
contained **zero** commits authored by `prekzursil1993@gmail.com`. Recovery path if ever needed:
re-clone from the origin recorded per-dir in that manifest, or simply let the plugin installer
re-stage on next marketplace refresh. **No owner-authored content was destroyed.** The residual
exposure is the manifest itself: keep `hygiene-reclaim-manifest-BEFORE.txt` — it is the only
surviving record of which upstream each staging dir came from.

**Residual, honestly stated:** 49 residue dirs (~105 MB, 277 never-loaded SKILL.md) remain by
design. A second run after the 45 age out (≥6 h from 8:42 PM) reclaims those; the 4 origin-less
dirs should stay until someone eyeballs them (they are ~78 files total, negligible).

---

## (b) `~/.claude` in no git repo, ".235 .bak files" — **DONE; count REFUTED**

### Measured

| Field | Value |
|---|---|
| `~/.claude` is a git repo? | **NO — VERIFIED.** `git -C ~/.claude rev-parse --is-inside-work-tree` -> `fatal: not a git repository` |
| `~/.agents` is a git repo? | **YES — VERIFIED.** origin `https://github.com/Prekzursil/agent-skills-toolchain.git`, branch `live-capture/2026-09-02` |
| `~/.claude` total size | **14,558.9 MB = 14.218 GB**, 422,680 files — VERIFIED, matches the "~14 GB" premise |

Composition (VERIFIED, confidence 95-99%):

| Subtree | Files | MB | Share |
|---|---:|---:|---:|
| `plugins/` | 411,571 | 11,212.6 | 77.0% |
| `projects/` (transcripts) | 4,538 | 2,751.3 | 18.9% |
| `fp-recovery-backup-20260925/` | 766 | 513.9 | 3.5% |
| `skills/` | 3,273 | 26.9 | 0.18% |
| root loose files | 39 | 20.8 | 0.14% |
| `hooks/` | 898 | 13.9 | 0.10% |
| `file-history/` | 1,013 | 13.5 | 0.09% |
| everything else (22 dirs) | ~580 | ~5.9 | 0.04% |

### "235 .bak files" — REFUTED, and the honest number is better evidence

| Pattern | Count |
|---|---|
| strictly `*.bak` | **4** |
| all backup-shaped (`.bak .bak-* .backup .old .orig .tmp.* .pre-* .corrupt-* .save`) | **210** |
| ‣ of which **authored-config** (the real symptom) | **83**, 1,974,984 B |
| ‣ of which plugin-installer churn (`plugins/**`, mostly `.in_use/*.tmp.*`) | 123 |
| ‣ of which transcripts / fp-recovery | 4 |

VERIFIED, confidence 90-95%. Full list: `hygiene-bak-inventory.txt` (233 lines). **Nothing deleted.**

The 83 authored-config ones prove the anti-pattern precisely — they cluster on the most-edited
authored files: **5** shadow copies of `settings.json`, **3** of `AGENTS-RUNTIME.md`, **3** of
`hooks/_dispatch/manifest.json`, **3** of `skills/owner-ops-authorization/SKILL.md`, 2 each of
four hook sources. That is hand-rolled version control on exactly the files that need history.

### The design: authored set is 0.045% of the tree

| Measure | Value |
|---|---|
| authored-and-irreplaceable | **452 files / 6,895,804 B (6.58 MB)** |
| as a share of `~/.claude` | **0.045%** |
| regenerable/noise excluded by the manifest | 345,867 files |

**The biggest gap found:** `~/.claude/hooks` has **898** files and only **10** have any
counterpart in `~/.agents/hooks`. `~/.claude/agents` has **29** files and
**`~/.agents/agents` does not exist at all**. `~/.claude/commands` 75 vs 6. `settings.json`
(27,825 B live) is untracked — only a dated snapshot at `backups/policy-2026-09-24/settings.json`.
**`hooks/recall-gate` — built, tested, both-states-proven — was version-controlled nowhere.**

### Deliverables

| Artifact | What it is |
|---|---|
| `~/.agents/harness-baseline/baseline-manifest.txt` | the `.gitignore`-shaped manifest: deny rules first, includes second, every exclusion justified inline |
| `~/.agents/scripts/backup-claude-baseline.ps1` | the working script, `-DryRun` / `-SelfTest` / apply |
| `~/.agents/harness-baseline/dot-claude/` | **452 files copied, 6.58 MB** |
| `~/.agents/harness-baseline/README.md` | the bootstrap recipe (fresh-machine restore, step by step) |

### Result — VERIFIED

```
selected      = 452 files, 6895804 bytes (6.58 MB)
denied        = 345867 (manifest ! rules)
cred_blocked  = 0 (CRED gate, selection pass)
copied        = 452
stage         = DONE
message       = copied and verified git-visible
SUCCESS:baseline DONE   APPLY_EXIT=0
```

Independent verification (not the script's own check): `git add --dry-run -- harness-baseline`
reports **454** paths and **454** files exist on disk under `harness-baseline` — the 452 copied
files plus `baseline-manifest.txt` and `README.md`. **Equal counts means zero silently dropped**,
which is the property that matters; the absolute number moves as the two hand-written docs are
added (it read 453/453 before `README.md` was written). Credential sweep of the destination:
**0** stores. Spot-checked present:
`settings.json` 27,825 B, `CLAUDE.md` 10,404 B, `AGENTS-RUNTIME.md` 21,962 B,
`hooks/recall-gate/gate.py` 14,527 B, `tree_index.py` 9,924 B, `test_recall_gate.py` 10,305 B,
`hooks/_dispatch/manifest.json` 14,369 B.

### BOTH-STATES PROOF — 17 assertions, VERIFIED

`-SelfTest` builds a fixture repo whose `.gitignore` mimics the real one. All pass:

| # | Case | Must | Got |
|---|---|---|---|
| 1 | clean manifest | copy + verify | `Ok=True Stage=DONE copied=2` |
| 2 | manifest asks for `.credentials.json` | never lands on disk | `credential_file_on_disk=False credBlocked=1` |
| 3 | a `*.bak-*` slips in | FAIL as git-invisible | `Stage=IGNORE ignored_count=1` |
| 4 | destination under `backups/` | FAIL | `Stage=IGNORE ignored_count=2` |
| 5 | destination outside the repo | FAIL | `Stage=DEST` |
| 6 | 12-case credential regression | source in / stores out | 12/12 |

### Two defects the gates caught on live data — the reason the gates exist

**1. `IGNORE` fired on `hooks/recall-gate/state/*` (3 files).** `state/` is ignored by
`~/.agents/.gitignore`, so those would have been copied and then silently dropped by git — a
backup that looks done and is not. They are regenerable hook state; the manifest now denies
`**/state/**`. A gate failing loudly beat a backup passing quietly.

**2. My own `CRED` gate silently dropped 4 authored source files.** The first version matched the
bare substring `credential`, which excluded
`hooks/deny-credential-reads/{deny.py,test_deny.py,test_denylist_coverage.py,test_guard_scope.py}`
— **the source of the hook that guards credential reads** — because its *directory name* contains
the word. A baseline that omits its own security guard is worse than no baseline. Fixed: the
heuristic is now anchored to the file name and exempts source/doc extensions, with a dedicated
regression case (self-test 6).

Fixing that exposed a **pre-existing defect in `~/.agents/.gitignore`**: its `*credential*`
pattern also matches the *directory*, so git excluded the tree and never descended — meaning that
hook's source **could never have been version-controlled in this repo**. I added a narrow
re-include, and only after verifying the files are secret-free.

**Security-adjacent change, flagged deliberately (rule 4 / §9).** I edited a credential pattern in
`.gitignore`. Justification and evidence:

- Scanned all 4 files for real secrets: **0 high-entropy mixed-charset tokens ≥28 chars**
  (deny.py 218 L, test_deny.py 160 L, test_denylist_coverage.py 408 L, test_guard_scope.py 160 L).
  The only credential-ish strings are **2 short detection prefixes** (`sk-`, `Bearer`) used as
  match patterns. No value was printed.
- The negation is scoped to that one directory and to `*.py` / `*.md` only. Proven both ways:
  `deny.py`, `test_deny.py`, `README.md` → TRACKABLE; `credentials.json`, `token.json`,
  `server.pem`, `id_rsa.key`, `.credentials.json` (root and nested) → still IGNORED. 9/9 correct.
- **No credential pattern was weakened.** `.credentials.json` remains ignored everywhere, and the
  script's CRED gate blocks it before a copy is attempted.
- This is a genuine safeguard *repair*, not a relaxation — but it is the owner's call to keep, so
  it is called out here rather than buried.

---

## (c) Dead config rows — **"90 disabled plugins" REFUTED; 131 MCP rows real but not worth acting on**

Full per-row detail: **`hygiene-dead-rows-inventory.md`**. Summary:

- **Disabled plugins: there are ZERO.** No enable/disable state exists anywhere —
  `installed_plugins.json` has **0** occurrences of `"enabled"`/`"disabled"`/`"active"`/`"state"`;
  `.claude.json` has **0** of `"enabledPlugins"`/`"disabledPlugins"`/`"enabled":false`; **0 of 45**
  projects carry an `enabledPlugins` map. 100 plugins installed, all enabled. Item (c)'s plugin
  half has no subject. VERIFIED, confidence 90-95%.
  - The different real signal: **83 of 100 installed plugins have no `pluginUsage` record.**
    That is *unused*, not *disabled* — and absence of a usage row is not evidence of uselessness
    (a plugin providing only an MCP server would read "unused"). **Recommend owner review, no prune.**
- **Disabled MCP servers: 131 rows CONFIRMED**, but **112 of 131 resolve**. I had to correct my own
  detector **twice**, both times over-reporting:
  1. "77 orphans" came from comparing all three namespaces against `mcpServers` alone.
  2. The 19 `plugin:local-mcp-bridge:*` rows resolve once `plugins/data/`'s **66 inline** plugin
     names are in the index — unresolved went 19 → **0**.
  3. The 15 unresolved `claude.ai` rows are checked against `claudeAiMcpEverConnected`, which
     records *ever connected* — absence there does **not** prove the connector is gone. UNPROVEN.

  | Namespace | Total | Resolves | Unresolved |
  |---|---:|---:|---:|
  | local registry (bare name) | 58 | 54 | **4** |
  | plugin-provided (`plugin:X:Y`) | 38 | 38 | **0** |
  | claude.ai connector | 35 | 20 | 15 (unproven) |

  **Recommendation: KEEP all 131.** Only `apify`, `biomni-hub`, `meta-tool`, `schrodinger` are
  defensibly unresolved, and even those are plausibly deliberate parks (precedent:
  `.mcp-disabled-defaults.json` lists `cloud-hub`/`social-hub` as parked while both run live). The
  array is ~4 KB; the cost of a wrong deletion is a silently re-enabled server. **A premise that is
  true as a count and not worth acting on.**

## (d) superpowers forks — **premise CONFIRMED (14 of 15 diverged, 0 identical)**

Compared against the **active** version 6.4.1 (`installPath` → `…/superpowers/6.4.1`). My first
pass used the `5bf4e7801107` directory; re-run to be sure the baseline was live.

**2 INTENTIONAL · 3 STALE DRIFT · 9 DIVERGED · 1 PLUGIN-ONLY.**

The actionable core is the **3 STALE DRIFT** rows, which are a *capability regression*, not mere
duplication — a local fork wins resolution, so the estate runs the thin copy:

| Skill | local | plugin 6.4.1 | ratio | usage |
|---|---:|---:|---:|---|
| `brainstorming` | 4,772 | 17,548 | **3.7x smaller** | both names used — actively running the thin copy |
| `executing-plans` | 2,878 | 20,405 | **7.1x smaller** | never used — re-sync is zero-risk |
| `subagent-driven-development` | 10,483 | 32,577 | **3.1x smaller** | only `superpowers:` used |

Keep the fork for `writing-skills` (55,785 B, **+15** estate markers — clearly deliberate).
**Nothing re-synced by me** (rule 3); and rule 1 routes any fix through `~/.agents/skills`, where
all forks are authored and git-tracked byte-identically to the deployed copies.

## (e) 23 `source-command-*` duplicates — **CONFIRMED, cleanest case in the lane**

- All 23 have a paired `~/.claude/commands/<X>.md`.
- **100% of command body lines appear verbatim inside the SKILL.md** on a 4-skill sample
  (3/3, 12/12, 15/15, 114/114). Each SKILL.md is its command plus frontmatter, 179-521 B larger.
- **`skillUsage` has 92 rows and not one matches `source-command-*` — all 23 have never been
  invoked**, while `/prime`, `/aside`, `/plan`, `/self-reflect` remain fully available.
- Cost, honestly: bodies total 101,699 B but those load on invocation. The always-on cost is
  **3,447 B of frontmatter ≈ 862 tokens** plus 23 confusable listing entries.
- **Recommendation: RETIRE all 23** (commands stay), at the authored copy then re-deploy, recorded
  as RETIRED in `INVENTORY.md`. Confidence 85-90%. **Not done — rule 3.**

---

## Net-negative ledger (rule 10)

| ADD | RETIRES |
|---|---|
| `scripts/reclaim-plugin-cache-residue.ps1` | **Nothing — no retirement, justified.** There is no residue sweeper today. `plugins/.last_inuse_sweep` (2026-09-25T00:54:32Z) shows Claude Code runs an *in-use* sweep, but it demonstrably does not remove these dirs — the oldest is 271 h (11 days) old and survived it. Manual, dry-run-default, **not a hook**: zero per-turn cost. |
| `scripts/backup-claude-baseline.ps1` + `harness-baseline/` | **RETIRES the 83 authored-config backup files** as a version-control mechanism (they are listed, not deleted — the owner removes them once real history exists). Also **retires** the need for `~/.agents/backups/policy-2026-09-24/{settings.json,AGENTS-RUNTIME.md,home-AGENTS.md}` as an ad-hoc snapshot, since those three files are now in a tracked, refreshable baseline. Manual script, **not a hook**: zero per-turn cost. |
| narrow `.gitignore` negation (3 lines) | **RETIRES a silent hole**: `*credential*` made the credential-guard hook's source permanently unversionable. Net change in ignore coverage for credential *stores*: **zero** (proven 9/9). |
| 3 knowledge artifacts under `knowledge/gemhunt-impl-2026-09-25/` | Nothing. They are evidence, and two of them (`hygiene-reclaim-manifest-BEFORE.txt`, `hygiene-bak-inventory.txt`) are the **only** surviving record of what was removed and what was listed. |
| **Net disk:** −530.7 MB reclaimed vs +6.58 MB baseline copy = **−524.1 MB** | The lane is net-negative on bytes as well as on mechanisms. |

## Files changed

Created:
- `C:/Users/prekzursil/.agents/scripts/reclaim-plugin-cache-residue.ps1`
- `C:/Users/prekzursil/.agents/scripts/backup-claude-baseline.ps1`
- `C:/Users/prekzursil/.agents/harness-baseline/baseline-manifest.txt`
- `C:/Users/prekzursil/.agents/harness-baseline/README.md`
- `C:/Users/prekzursil/.agents/harness-baseline/dot-claude/` (452 files, 6.58 MB)
- `C:/Users/prekzursil/.agents/knowledge/gemhunt-impl-2026-09-25/hygiene.md` (this file)
- `C:/Users/prekzursil/.agents/knowledge/gemhunt-impl-2026-09-25/hygiene-reclaim-manifest-BEFORE.txt`
- `C:/Users/prekzursil/.agents/knowledge/gemhunt-impl-2026-09-25/hygiene-bak-inventory.txt`
- `C:/Users/prekzursil/.agents/knowledge/gemhunt-impl-2026-09-25/hygiene-dead-rows-inventory.md`

Modified:
- `C:/Users/prekzursil/.agents/.gitignore` (3-line narrow negation + comment; security-adjacent, see (b))

Deleted (item (a) reclaim, all gated and manifested):
- 417 residue dirs under `~/.claude/plugins/cache`, 10,853 files, 556,483,895 B

**Nothing committed** — rule 6; the orchestrator commits. All changes are unstaged in
`~/.agents` (branch `live-capture/2026-09-02`).

**Commit scope — do NOT `git add -A`.** `git status` in `~/.agents` shows 18 changed paths and
only 5 are mine. A blanket add would sweep in other lanes' and other sessions' work. Mine are
exactly:

```
 M .gitignore
?? harness-baseline/
?? knowledge/gemhunt-impl-2026-09-25/          (shared with other lanes - add only hygiene* files)
?? scripts/backup-claude-baseline.ps1
?? scripts/reclaim-plugin-cache-residue.ps1
```

Pre-existing and **not** mine: `CLAUDE.md`, `browser-profiles/chrome-agent/**`,
`skills-index.md.bak`, `.copilot-for-azure-skills-manifest.json`, `AGENTS.md.pre-vm-blunt`,
`scripts/{cache_lens.py,lint-frontmatter-keys.py,skill_listing_audit.py,stable_prefix_lint.py,supervise.ps1,supervise.selftest.ps1,supervise.selftest/}`.
The `knowledge/gemhunt-impl-2026-09-25/` directory is shared — other lanes' artifacts
(`context-prefix.md`, `native-features.md`, `supervision.md`, `wire-inert.md`, `validate-*.md`)
live there too. My four files are `hygiene.md`, `hygiene-bak-inventory.txt`,
`hygiene-dead-rows-inventory.md`, `hygiene-reclaim-manifest-BEFORE.txt`.

Not touched: `~/.claude.json` (read-only), `installed_plugins.json`, `known_marketplaces.json`,
any MCP server, plugin, skill or remote branch, any credential.

## Risks

1. **The 6 h age gate is a heuristic, not a lock.** Windows has no cheap open-handle check without
   `handle.exe`. Mitigated by the G3+G4 double age gate and a gate re-assert immediately before
   each delete — but a clone started 6 h ago and still running would not be protected. No evidence
   of one: the newest residue was 2.2 h old and its batch's `installed_plugins.json` write had
   already completed.
2. **The reclaim is irreversible.** No recycle bin. Acceptable only because every eligible dir was
   proven re-fetchable from a public remote and free of owner-authored commits. **Keep
   `hygiene-reclaim-manifest-BEFORE.txt`** — it is the only record of which upstream each came from.
3. **`.gitignore` is a security-adjacent edit.** Evidenced above, narrow, and proven not to weaken
   credential-store coverage — but the owner should confirm they want it.
4. **The baseline is a snapshot, not a hook.** It goes stale the moment `settings.json` changes and
   nothing reminds anyone. Deliberate (rule 10: no per-turn cost), but it means the anti-pattern
   returns unless the script is re-run. A Stop-hook nudge would fix it and would need its own
   both-states proof — out of scope here, and I did not add one.
5. **Byte-size is a weak proxy for the (d) verdicts.** The 9 DIVERGED rows genuinely need a human
   read; I did not claim otherwise, and I re-synced nothing.
6. **`skillUsage` is one signal** for the (e) "never invoked" claim. The independent second signal
   is the 100% verbatim duplication, which does not depend on telemetry.
7. **49 residue dirs remain by design** (~105 MB): 45 too-new, 4 origin-less. A later run reclaims
   the 45 once they age past 6 h; the 4 should stay until someone eyeballs them.
