---
title: BUILD-ROUND3-2026-08-14
type: note
permalink: dqverify-repo-20261013/command-center/ssot/build-round3-2026-08-14
---

# LANE SSOT — BUILD round 3 (re-entry after a CONFIRMED defect)

STATUS: **all five milestones measured.** Every claim below names the command that produced it.

If any row still reads `UNKNOWN - not yet measured`, the unit died before measuring it and no
verdict there may be cited. (None does.)

COVERAGE: §1-§6 measured. Not measured and disclosed inline: the destructive cache-side
`worktree remove` experiment (R4), and the *working-tree* content of the two 0-commit no-remote
checkouts (R9).

---

## 0. What this round fixed, and how it found it

The re-entry brief said a verifier confirmed defects; the round-2 audit itself was not on disk
and the prompt carrying it was truncated. Rather than guess, I re-derived the defects from round
2's own DoD table and residual list, and every one of the three below is a case where **the code
was right and the sentence was wider than its evidence** — the estate's measured 7:5 overclaim
ratio, again.

## 1. DoD item 3 was scored PASS over a corpus that cannot see three of the five pointer kinds

The lane's DoD question 3 enumerates the pointer kinds: *"a scheduled task, a hook, a skill, a
PATH entry, a config"*. Round 2 scored it **PASS over 178** on `classify_population.py`, whose
`SCAN_ROOTS`/`SCAN_FILES` are **config files only**. Scheduled Tasks, PATH and the environment
are not in that corpus. The inventory's §3 does answer those three — **at 25 checkouts**, and
that number was carried into a 7×-larger population.

Error direction is the dangerous one: a checkout a scheduled task launches from reads
`inbound_exec = 0` and lands in the retire list. The lane's own grounding names this exact class.

`inbound_surfaces.py`, at 178:

| surface | read | checkouts named | control (real → +synthetic → +fabricated) |
|---|---|---|---|
| Scheduled Tasks | 329 actions (172 with `Execute`) | **0** | 0 → 1 → 0 ✓ |
| PATH (Machine+User) | 87 entries | **0** | 0 → 1 → 0 ✓ |
| Environment (Machine+User) | 388 variables | **0** | 0 → 1 → 0 ✓ |

**The control is the point.** A zero here is worthless unless the same extractor demonstrably
fires when a reference IS present, so each surface is scanned three times — real, real + one
synthetic row naming a real population path, real + a fabricated path. Two hypotheses were named
*before* running: H1 "nothing references a checkout", H2 "the extractor cannot see this surface".
All three surfaces discriminate, so the silence supports H1. Each also has a plausibility floor
and fails closed below it.

Nothing was written to the box: the synthetic row lives in the probe's memory, no task is
created, no variable is set, and env values are matched in memory with only the VARIABLE NAME
recorded — that surface sits next to live credentials.

**Verdict: the conclusion survives, the evidence now covers the claim.** No verdict changes; the
43 retire candidates are corroborated on the three surfaces the scan never covered.

## 2. DoD item 2 was scored PASS with five rows carrying `null` instead of a number

Round 2: *"unique-content measured per clone — **PASS** — unpushed + dirty + staged for all 178;
`null` with a reason for the 5 remote-less, never a false 0"*. Refusing to print a false 0 was
right. Scoring the item PASS was not: `null` is the **absence of a measurement**, and those five
are the highest-risk rows on the board. Round 2 named the settling experiment in its own residual
#2 and did not run it.

Run at **blob** level, because commit-object identity is the wrong instrument — squash-merge keeps
a unique commit SHA forever, so an absent commit says nothing about absent content.

| checkout | commits | tracked blobs | absent by raw SHA | genuinely unique |
|---|---|---|---|---|
| `…/plugin-install-64I3il/…/0.2.0` | 0 | — | — | nothing committed |
| `…/Temp/adv0010/repo` | 2 | 7,323 | 5,518 | **0** |
| `…/Temp/adv0010/repo2` | 2 | 7,323 | 5,518 | **0** |
| `~/source/_advver_M14/chk` | 1 | 5,561 | **0** | **0** |
| `~/source/_advver_M14/scratch` | 0 | — | — | nothing committed |

### The 11,036-blob false alarm I nearly shipped

The first probe stopped at raw SHA and printed *"BLOBS absent from canonical: 5518"* for each of
the two `adv0010` rows. Written up unchecked that is **"two checkouts hold 11,036 files that exist
nowhere else"** — a fleet-scale data-loss alarm, with example paths that look entirely plausible
(`hooks/loop-recovery/test_handler.py`). It is an artifact:

    blobs containing CRLF                : 5518 / 5518
    absent raw BUT present LF-normalised : 5518 / 5518
    genuinely absent both ways           :    0

Every one is a line-ending twin of a blob already in the store. Round 1 had **already** burned a
control on this exact shape (its content signal read `positive=False negative=False` because the
tree is CRLF and git stores LF), and it is written down in `windows-shell.md` §8b. It still
nearly shipped a second time — which is the honest lesson: a documented defect class does not
protect you unless the probe is built to fire on it.

**Controls, both states:** the hasher must reproduce a known canonical blob's SHA and must *not*
reproduce it from a deliberately mangled copy of the same bytes; the reader must find a known SHA
and miss a fabricated one. Both discriminate — checked before any number above was believed.

**Not cleared:** the two 0-commit rows, by construction. `_advver_M14/scratch` is where the real
exposure lives — no commits, no remote, thousands of untracked entries in no store anywhere. That
is **uncommitted**, not unpushed, and it is now residual R9 rather than a `null` inside a PASS.

## 3. DoD item 3's "PASS with a named residual" — the residual is closed

`resolve_ref_fields.py` parses each naming file and walks it for keys whose **name** or **value**
resolves to a checkout, so a hit is a field, not a document.

| checkout | live fields | kind |
|---|---|---|
| `~/source/agent-skills-toolchain` | 16 | MCP `command`/`args`, `workspaceRoot`, Codex `local-projects.*.rootPaths[0]`, thread cwd/path |
| `~/Documents/Playground` | **2** | `~/.codex/config.toml` → `projects."…\Playground"` and `desktop.open-in-target-preferences.perPath."…\Playground"` |
| `~/source/ast-harness-reconcile` | 1 | `.codex-global-state.json` → `local-projects.<uuid>.rootPaths[0]` |

Playground's other 4 file-level hits are **backups** of that config — counted, not treated as
live. One file is not field-resolvable (`reconcile-all-branches-prs-imporant.js` is JavaScript);
it names canonical, which is KEEP regardless, so no verdict rests on it. Disclosed, not hidden.

## 4. Two things measured because a number looked wrong

**R10 — is 178 inflated by junction aliases?** Round 1's dedupe and the round-1 audit's
0-collision check were both taken at **170**; round 2 added 8 rows without re-testing. Re-run at
178: **178 realpath groups, 0 collisions**, control passing (a known junction pair collapses, a
known-distinct pair does not). Two rows are spelled through the legacy `Local Settings` junction
and neither has its resolved twin in the population. **178 is not inflated.**

**R4 — the last unclassified row, and a self-contradiction.** The single
`kind-signals-disagree` row has a `.git` that is a **FILE**, and a file cannot contain
`worktrees/*/gitdir` — which reads as a refutation of R4. It is not: there are **two** cache
copies of this repo and they are in different states.

    …/cache/agent-skills-toolchain/agent-skills-toolchain/0.2.0      .git is a DIRECTORY  <- R4
    …/cache/agent-skills-toolchain/plugin-install-64I3il/…/0.2.0     .git is a FILE       <- severed

The severed one points at `<canonical>/.git/worktrees/agent-skills-toolchain`, which does not
exist — hence rc=128 on every git command, hence the disagreeing signals. Both rows are in the
population; neither was mis-enumerated. **The apparent self-contradiction was a two-paths
problem, not a detector failure — but only measurement could establish which.**

R4's hazard is real and **armed**: 5 registrations, **3 whose `gitdir` names a directory that
exists right now** — `ast-harness-reconcile`, `D:/inc1-wt/ast-increment1`, and
`~/source/ast-integrate` (this worktree). Two are stale. Whether a cache-side `worktree remove`
would delete a real tree remains **UNVERIFIED** — the probe is destructive and was not run, and
declining it is still correct. The standing instruction is unchanged and now has a measured
blast radius, wired into `CLAUDE.md`.

---

## 5. Definition of Done (lane), re-scored

| DoD item | status |
|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS** — 178/178, two agreeing signals; the one disagreeing row is now resolved by a third signal (a `.git` FILE whose gitdir target does not exist = severed worktree), not left as "disagrees" — **REFUTED as written, see below** |
| unique-content measured per clone | **PASS** — 173 by unpushed+dirty+staged, and the 5 `null` rows now measured at blob level: 0 unique committed bytes. Residual R9 (uncommitted content in a 0-commit tree) is disclosed, not folded in |
| inbound-reference measured per clone | **PASS** — config corpus (round 2) **plus** Scheduled Tasks + PATH + env at 178 (round 3), all with both-states controls; all 3 referenced checkouts resolved to exact fields, 1 unparseable file disclosed |
| a one-sentence SSOT rule written | **PASS** — unchanged sentence; gate green (6/6 wires, 16/16 tests) measured after every edit this round |
| nothing deleted | **PASS** — every probe read-only; no checkout, worktree, evidence dir or clone touched; no `worktree` subcommand that mutates state was run |

> **DoD-1 REFUTED as written — round-3 verifier, fixed in round 4. Kept, not deleted.**
> The row above claims **`178/178`, two agreeing signals**. The measurement is **177**:
> `signals_agree` is `true` on 177 rows and `false` on 1. The verifier checked the blob at HEAD,
> at `9a581433` and at `ca4ef63c`, plus the working tree — all four still carried
> `kind_signals_disagree: list[1]` and no resolution field. The code was right; the sentence was
> wider than its evidence, and the resolution existed only in prose while `CLAUDE.md` points
> future agents at the JSON.
>
> **Correctly scoped:** *177 of 178 checkouts are classified by two agreeing primary signals; the
> 178th — the severed cache copy — is classified by a third signal that is validated in both
> states, and both facts are now recorded in `population-classified.json`
> (`kind: "severed-worktree"`, `resolved_by: …`, `signals_agree: false`, plus a `kind_arithmetic`
> block that fails closed when 9 + 168 + 1 stops equalling 178).* So scoped, the item is PASS.
>
> The verifier's other two corrections landed in the same round-4 commit: the `CLAUDE.md`
> arithmetic now closes at 178, and the JSON carries the resolution. Nothing in §1–§4 above is
> withdrawn — the three round-3 findings and every number in them survived the verifier
> (`B4` was CONFIRMED by an independent hasher: 7,645 raw-absent blobs, 7,645 CRLF, 0 absent both
> ways).

## 6. Residuals

1. **R9 — `~/source/_advver_M14/scratch`** is the sharpest exposure: 0 commits, no remote,
   thousands of untracked entries in no store anywhere. It was under active write by other lanes
   while measured, and a uniqueness census of a moving target cannot license any action.
   **Settle:** confirm quiescence (`find … -newermt '10 minutes ago'`), then run the §2c blob
   probe over its working tree.
2. **R4 destructive arm untested.** Whether a cache-side `worktree remove` reaches the 3 armed
   targets is UNVERIFIED by choice. **Settle:** against a throwaway worktree, never a live one.
3. **43 retire candidates identified; nothing retired, nothing deleted.** Prefer moving a
   directory aside over `git worktree remove`, which follows junctions.
4. **One naming file is not field-resolvable** (a `.js` workflow naming canonical). Canonical is
   KEEP, so no verdict rests on it.
5. **Every count is a snapshot.** `main` moved during this round (`8e7ff68c` at start; canonical
   reported 322 behind, up from 198 earlier the same day). Re-run before acting.
6. **Not pushed.** Local `main` is ahead of `origin/main`.