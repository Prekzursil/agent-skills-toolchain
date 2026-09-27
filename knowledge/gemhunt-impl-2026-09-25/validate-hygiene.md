# validate-hygiene — adversarial validation of the "hygiene" lane

Status: **COMPLETE**. Validator lane `validate-hygiene`, 2026-09-26.
Every verdict below was reached with an instrument DIFFERENT from the implementer's.
Nothing was deleted, no credential was modified, no process killed, nothing committed.

## Headline

The lane's work is **substantially sound**. All five items exist on disk, the destructive
action reconciles exactly, and both gates pass an independent both-states test I designed.
**Four OVERCLAIMS** found — in every case the code is right and the sentence is wider than
the evidence. **Zero hard-rule violations.** **Zero regressions.**

## Per-item verdicts

| item | verdict | instrument I used (not theirs) |
|---|---|---|
| (a) reclaim residue | **CONFIRMED** (3 scope corrections) | Python `os.walk`/`os.scandir`; production script over MY fixtures |
| (a-bonus) self-refutation | **CONFIRMED** (strengthened) | THIS session's live skill listing as oracle |
| (b) baseline | **CONFIRMED** + 1 OVERCLAIM | `git ls-files --others`; independent Python census |
| (b-defect) CRED/.gitignore | **CONFIRMED** + 1 OVERCLAIM | MY fixture + MY manifest; `git check-ignore -v` |
| (c) dead-config | **CONFIRMED** | full recursive key enumeration; `json.load` |
| (d) superpowers forks | **OVERCLAIM** (facts confirmed) | sha256 over all 14; `skillUsage` telemetry |
| (e) 23 wrappers | **CONFIRMED** + 1 OVERCLAIM | `os.path.getsize`; different 5-skill sample |

### (a) CONFIRMED — the premise refutation holds

- `claude-plugins-official` = **11,011.33 MB / 402,535 files** (they: 11,011.30 MB / 402,620).
  The 13 GB is ONE named marketplace dir, not the clones. Refutation CONFIRMED.
- Cache total now **11,711,992,994 B** vs their claimed post-state 11,711,991,423 (Δ +1,571 =
  live churn). Surviving residue = **49** dirs (37 `temp_git` + 12 `temp_subdir`).
- `hygiene-reclaim-manifest-BEFORE.txt` records **466** distinct residue dir names; exactly
  **49** are still present ⇒ 417 deleted; union = **466**, matching their claim exactly.
- **44 distinct public GitHub owners; 0 owner-owned.** 9 named marketplaces and 100 installed
  plugins intact.

**Both-states, independently proven.** I ran the PRODUCTION main path
(`-CacheRoot <my fixture>`), not their `-SelfTest`, over 12 fixtures of my own design:
`G1-PATTERN 4, G3-AGE 1, G4-MTIME 1, G5-ORIGIN 1, G6-AUTHOR 1` — every gate fired, G6 using
the REAL live `user.email`. `-Apply` deleted the 2 intended dirs; `PRECIOUS-marketplace`
survived. **New case they did not test:** a directory JUNCTION named like residue — the link
was removed and the **target's content survived** (verified `important.txt` intact).

Three scope corrections (not defects):
1. G1 is documented `[a-z0-9]+` but PowerShell `-match` is **case-insensitive**, so
   `temp_git_<epoch>_UPPER99` IS eligible and my fixture's copy was deleted. Enforced
   pattern ≠ documented pattern.
2. `Measure-Dir` traverses a junction for ACCOUNTING (it counted my target's 16 B) though
   `Remove-Item` does not follow it, so `freed_bytes` can be inflated when a junction is
   present. Their exact before/after match (556,483,895) is itself evidence none was.
3. G6 is structurally **fail-open**: `if ($OwnerEmail)`. With no global `user.email` the
   owner-authorship gate is silently skipped. Not triggered here (email IS set). INFERRED.

### (a-bonus) CONFIRMED and strengthened

My oracle is stronger than theirs: the 49 residue dirs STILL on disk hold exactly **277
SKILL.md** with **19 skill names existing nowhere else**. In THIS session — started AFTER the
reclaim — **none of the 19 appear in the skill listing**, while the positive control
`firecrawl` does. A true both-states test on live data: the loader provably ignores residue,
so the reclaim bought 0 context tokens, exactly as they said.
Cross-lane correction CONFIRMED: plugins/ **1,838** SKILL.md − 277 residue = **1,561
loadable** (they claimed ~1,560).

### (b) CONFIRMED, one OVERCLAIM

- 452 files / **6,895,804 B** — exact. `git ls-files --others --exclude-standard` = **454**
  visible, `--ignored` = **0** ⇒ nothing silently dropped (their gate's purpose holds).
- `~/.claude` = **14.225 GB / 423,102 files**; composition plugins **77.0%** / projects 18.9%
  / fp-recovery 3.5% — exact. hooks **898 vs 10**, agents **29 vs DOES-NOT-EXIST**, commands
  **75 vs 6** — all exact. Strict `*.bak` = **4**, so the "235" refutation is exact.

**OVERCLAIM:** "210 backup-shaped" and "123 plugin-installer churn" did NOT reproduce — my
independent classifier gives **104** and **17**. Both rest on an unstated "backup-shaped"
predicate. The load-bearing authored-config cluster DOES reproduce (85 vs their 83).
Separately, `baseline-manifest.txt` still carries stale pre-correction numbers in its header
("461 files / 9.18 MB / 0.063%", "71 of them, 1.77 MB") against the final 452 / 6.58 MB /
0.045% and 83 / 1.97 MB.

### (b-defect) CONFIRMED — both gates independently proven

With MY fixture and MY manifest (`hooks/**`, **zero** denies):
- CRED gate blocked all 6 planted stores (`cred_blocked = 6`: `.credentials.json`,
  `keystore.jks`, `api.keystore`, `.env.local`, `oauth_config.json`, bare `id_ed25519`)
  while COPYING `deny-credential-reads/{deny.py,README.md}` ⇒ the regression fix is real.
- IGNORE gate **FIRED** (`stage = IGNORE`, exit 1) against a fixture `.gitignore` lacking the
  negation, naming exactly the 2 `deny-credential-reads` paths — the live failure they
  describe, reproduced in a controlled fixture.

**OVERCLAIM: "Net change in ignore coverage for credential STORES = zero."** True for the
store-name patterns tested, not unconditionally. Their fixture used `id_rsa.key` (caught by
`*.key`); a **bare `id_rsa` / `id_ed25519` / `.netrc` / `authorized_keys` matches NO pattern
in `~/.agents/.gitignore`**, so inside that one re-included directory such a file would now
be git-visible where the directory-level `*credential*` previously hid it. Mitigated (not
eliminated) by the manifest's `!**/id_rsa`, `!**/id_ed25519`, `!**/.netrc` denies and
`CRED_ALWAYS_RX`, which I verified blocks a bare `id_ed25519`. The directory holds only 4
`.py` files, so exposure today is nil.

**Blind spot I proved:** the CRED gate is name+extension based — `secrets.yaml`, `token.txt`,
`.npmrc`, `creds.toml` are NOT blocked. The real 452 contains only 3 such shapes and all are
legitimate detector SOURCE (`test_secrets.py`, `pretool-secrets.ps1`, `prompt-secrets.ps1`),
so "0 stores" holds in substance. It is a name verdict, not a content scan — as they disclosed.

### (c) CONFIRMED

`installed_plugins.json`: 0 occurrences of enabled/disabled/enabledPlugins/disabledPlugins/
active/state; ALL distinct keys = {plugins, scope, installPath, version, installedAt,
lastUpdated, gitCommitSha} + 100 name keys ⇒ **"90 disabled plugins" REFUTED**. 100 installed,
`pluginUsage` = 25 rows. `.claude.json` (read-only): `disabledMcpServers` = **131**,
`skillUsage` = **92**, `projects` = **45**, **0 of 45** carry `enabledPlugins`, top-level
`enabledPlugins` ABSENT, `claudeAiMcpEverConnected` = 46. `settings.json deniedMcpServers` =
exactly the 6 named rows. Extra datum: **36 of 45** projects DO carry a project-scoped
`disabledMcpServers`, consistent with their three-namespace correction.

### (d) OVERCLAIM — facts exact, resolution framing wrong

Byte/SHA facts all EXACT, and I extended byte-identity of authored↔deployed to **all 14**
(they spot-checked 4): 15 plugin skills at 6.4.1, 14 with a local counterpart, **0
byte-identical**; brainstorming 17,548/4,772; executing-plans 20,405/2,878;
subagent-driven-development 32,577/10,483; writing-skills 26,623/55,785; writing-plans
9,092/4,348.

**But "a local fork wins resolution" ⇒ "a CAPABILITY REGRESSION" is refuted.** Both names
coexist as separately-addressable skills — this session's listing shows `brainstorming` AND
`superpowers:brainstorming`. Nothing is shadowed. The telemetry they cite points the OTHER
way: `superpowers:brainstorming` usageCount=**6** vs bare `brainstorming` usageCount=**1**
(and older); `superpowers:subagent-driven-development` usageCount=3, last used 2026-09-25,
while bare `subagent-driven-development` has **no row at all**. The estate predominantly runs
the FULL plugin copy. Their sub-claims (executing-plans never used by either name; only the
`superpowers:` name used for subagent-driven-development) are CONFIRMED.

### (e) CONFIRMED, one OVERCLAIM

23 authored + 23 deployed, **23/23** paired with a command. Delta range **179..521 B** and
total **101,699 B** — EXACT, as are aside 6,269/5,946, prime 6,848/6,427, save-session
10,081/9,631. (My first pass understated these because Python text-mode `read()` collapses
CRLF; I retracted it and re-measured with `os.path.getsize`.) `skillUsage` 92 rows, **0**
matching `source-command-*` — exact.

**OVERCLAIM: "all 23 wrappers duplicate their command 100% verbatim."** Across all 23 on
non-blank lines only **2 of 23** reach 100%; the rest are 89.3-99.6%
(`source-command-projects` 25/28, `promote` 27/30, `skill-health` 36/39). Every non-matching
line is the command's own YAML frontmatter (`name:`, `description:`, `command: true`), which
the SKILL.md rewrites. Their sample reported different denominators (`projects 12/12` vs my
25/28), so the "100%" came from a filtered line set stated as unfiltered. The conclusion —
these are wrappers — is unaffected.

## Hard-rule violations found: NONE

1. **Rule 1** no rules touched; `~/.claude/rules/common` and `~/.agents/rules/common` have
   identical mtimes for the 4 newest files, all ≤22:20, before the lane's 23:09+ work.
2. **Rule 2** no `.claude.json` write; sole reference is a comment at reclaim L41.
3. **Rule 3** 417 plugin-CACHE STAGING dirs deleted — NOT one of the protected classes:
   9 marketplaces / 100 plugins / 468+467 skills intact, 0 owner-owned origins, no branch
   deleted, and the live-listing oracle proves the loader never read the deleted class.
4. **Rule 4** no credential read-modify-write, no rotation, no value printed. They edited a
   `.gitignore` PATTERN (metadata) and flagged it themselves.
5. **Rule 5** no `Stop-Process`/`taskkill` in either script.
6. **Rule 6** not committed — all 5 paths are `M`/`??`. Commits `e04ffabc4`/`2c0ac7e55`
   predate the lane and belong to other work.
7. **Rule 7** satisfied, and independently re-proven by me for both gates.
8. **Rule 8** scripts created via the Write tool. (I tripped the command-scanner footgun
   twice myself; they did not.)
9. **Rule 9** artifact exists, 497 lines, all five items — **but line 3 is STALE and FALSE**:
   "Status: IN PROGRESS — item (a) MEASURED + reclaim pending. Items (b)-(e) UNKNOWN."
   Safe-direction untruth (understates completion), but it IS an untruthful line on disk.
10. **Rule 10** every item names what it retires or says explicitly that it retires nothing.
11. **Rule 11** every item carries VERIFIED/INFERRED plus a confidence band.

## Regressions found: NONE

- `settings.json` still parses: **27,825 B**, 36 top-level keys, `deniedMcpServers` intact,
  `ENABLE_TOOL_SEARCH = "true"`, `skillListingBudgetFraction = 0.04`.
  (Note: ground truth said 27,209 B — it grew by 616 B via another lane, not this one.)
- `~/.agents/scripts/lint-rules-loading.ps1` → **"PASS: every authored rule is cited AND
  deployed"**, exit 0.
- 0 ignored-but-present files under `harness-baseline`.
- Marketplaces, installed plugins and both skill trees unchanged.

## Recommended follow-ups (for the orchestrator, not done by me)

1. Fix `hygiene.md` line 3 — it contradicts its own body.
2. Re-scope the four overclaimed sentences ((b) "210/123", (b-defect) "net change = zero",
   (d) "wins resolution / capability regression", (e) "100% verbatim").
3. Refresh the stale header numbers in `baseline-manifest.txt`.
4. Consider `-cmatch` for G1 and an explicit `$OwnerEmail`-required assertion for G6.
5. `~/.agents/.gitignore` has no pattern for bare `id_rsa`/`id_ed25519`/`.netrc` — a
   pre-existing gap, independent of this lane. Owner's call.
