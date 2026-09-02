# BASELINE-SNAPSHOT — Prompt Two Phase 0 freeze

Machine-readable twin: [`BASELINE-SNAPSHOT.json`](BASELINE-SNAPSHOT.json).
This file was written FIRST as a skeleton with every field `UNKNOWN - not yet measured`, then
rewritten as each measurement landed. No field still reads `UNKNOWN`.

- **Captured:** 2026-08-09T14:45Z → 15:35Z (a measurement **window**, not an instant)
- **Host:** DESKTOP-A60S9GP · Python 3.14.6
- **Captured by:** `ground/baseline` subagent

**COVERAGE.** Measured: repo/branches/worktrees, plugin state, live harness tree counts + bytes,
live-vs-repo per-file divergence, hook manifest registrations, python test baseline over 28 of the
60 CI test steps. **NOT measured:** the other 32 CI steps (non-pytest gates, isolated py3.12 venvs,
vendored trees), the node/npm surface, and the *direction of truth* per divergent file.

---

## 0. FREEZE INTEGRITY — read this before citing any working-tree number

**The tree was NOT frozen during this snapshot.**

At the first probe `git status --porcelain | wc -l` returned **0**. Minutes later the same repo
reported `M agent-self/harness/install.py` plus ~20 new untracked paths from concurrent sibling
agents. A test suite measured **`4 failed, 831 passed`** at 15:05Z and **`835 passed`** at 15:12Z
with no action by this unit — a sibling's TDD red phase captured mid-flight.

**Consequence:** only the **committed SHA `53c37c6c`** is a stable rollback anchor. Every
working-tree number below is timestamped and **volatile**. A later phase proving "we changed
something" must diff against the SHA, not against these numbers.
*Confidence: almost-certain (90–99%) — two independent direct observations.*

---

## 1. Detector control (honesty rule 6) — **PASS 3/3**

Enumerator: `command-center/_baseline_probe.py :: enumerate_tree()`.

| Leg | Probe | Result |
|---|---|---|
| known-PRESENT | `enumerate_tree(~/.claude/hooks)` must contain `_dispatch/manifest.json` | **found**, 11,219 B — corroborated by an independent `ls -la` reporting the same size |
| known-ABSENT | `__CONTROL-SHOULD-NOT-EXIST__.md` must appear in none of the 6 trees | **0 hits** |
| BOTH-STATES | same enumerator over a temp dir seeded with that sentinel | **fired** (`sub/deep/__CONTROL-SHOULD-NOT-EXIST__.md`) |

The both-states leg is what makes the middle row meaningful: a detector silent in both states
measures nothing.

**A real detector defect was found and fixed mid-unit.** The first enumerator **crashed** with
`ValueError: path is on mount '\\.\NUL', start on mount 'C:'` — `os.path.relpath()` on a file
literally named `NUL`. Fixed by prefix-stripping the *directory* and reading via the `\\?\`
extended-length prefix. Had that crash been swallowed, every count in this file would have been
`0` and would have read as "the trees are empty".

---

## 2. Repo state

| Field | Value |
|---|---|
| path | `C:/Users/Prekzursil/source/ast-integrate` |
| origin | `https://github.com/Prekzursil/agent-skills-toolchain.git` |
| HEAD | **`53c37c6cfb3e7bd1a48edbe604e1ea06a77b50b1`** (`53c37c6c`) |
| branch | `main` |
| dirty at freeze | **0** (`git status --porcelain \| wc -l`, before this unit wrote anything) |
| worktrees | **6** |

Worktrees (`git worktree list`):

```
C:/Users/Prekzursil/source/agent-skills-toolchain  64340915 [fix/mcp-health-agentmail-fbmessenger]
C:/Users/Prekzursil/source/ast-harness-reconcile   4bcc65ec [chore/enshrine-runtime-config]
C:/Users/Prekzursil/source/ast-integrate           53c37c6c [main]
C:/Users/Prekzursil/source/ast-statusline-capture  24c1be78 [chore/statusline-gotchas-and-goal-short-20260724]
D:/ckwt/cookie-bridge-skill                        efe7d75f [feat/cookie-bridge-skill-20260724]
D:/inc1-wt/ast-increment1                          03e495bb [feat/variant4-increment1-dbx-monitor-20260721]
```

Dirt observed *during* the unit is attributed in the JSON: 1 tracked modification and ~20 untracked
paths from siblings; 7 untracked files written by this unit.

---

## 3. Branches

| Metric | Count |
|---|---|
| local | **57** |
| remote (excl. the `origin` HEAD pseudo-ref) | **96** |
| local merged into `origin/main` | **2** (`harness/upgrade-2026-07-17`, `main`) |
| local NOT merged | 55 |
| remote merged into `origin/main` | **13** |
| remote NOT merged | 83 |

> **Deletion warning.** Ancestry-merged is **not** a delete authorisation on this estate. This repo
> squash-merges, so a fully-landed branch still reports as NOT merged. An unknown subset of those 83
> are actually landed. Use PR-MERGED state or byte-level content comparison before deleting anything.

---

## 4. Plugin / marketplace state

`claude plugin list` → exit 0.

| Status | Count |
|---|---|
| enabled | **9** |
| disabled | **88** |
| **failed to load** | **1** |
| **total** | **98** |

The three buckets reconcile exactly (9+88+1=98). A first two-bucket parse summed to 97; chasing the
residual is what surfaced the third status string — `qodo-skills@claude-plugins-official` v0.6.1 is
**failing to load**, which a two-bucket detector would have silently dropped.

**Enabled:** `claude-reflect` · `codex@openai-codex` · `hookify` · `metaswarm` ·
`modern-web-guidance` · `ralph-loop` · `remember` · `skill-creator` · `superpowers`.

`agentbridge@agentbridge` v0.1.30 (user scope) is **disabled** — an independent re-probe
reconfirming the briefed retirement.

---

## 5. Live harness trees

| Tree | Live path | Live files | Live bytes | Repo files | Repo bytes |
|---|---|---:|---:|---:|---:|
| skills | `~/.agents/skills` | 14,585 | 266,412,606 | 1,721 | 11,183,177 |
| hooks | `~/.claude/hooks` | 314 | 5,529,522 | 293 | 5,251,537 |
| rules | `~/.claude/rules` | 88 | 220,620 | 88 | 255,496 |

Excludes `__pycache__`, `.git`, `.pytest_cache`, `.ruff_cache`, `node_modules`.

---

## 6. Live-vs-repo divergence (nothing was deployed)

Method: sha256 per shared relative path; on mismatch, re-compare after CRLF→LF normalisation to
separate EOL-only drift from real content drift.
`scripts/sync-rules.ps1:67` is a plain `Copy-Item -Force` with **no content transform**, so a rules
content difference is real drift, not a deploy artifact.

| Tree | identical | content-differ | EOL-only | live-only | repo-only |
|---|---:|---:|---:|---:|---:|
| skills | 1,336 | **127** | 125 | 12,997 | 133 |
| hooks | 140 | **49** | 77 | 48 | 27 |
| rules | **5** | **28** | 55 | 0 | 0 |

**skills.** The 12,997 live-only files are dominated by `crypto-ctf` (12,786 files / 344 MB, only
`SKILL.md` in the repo) and `microsoft-foundry` (172) — a deliberately uncommitted payload, not
drift to reconcile. Excluding those two, live-only falls to roughly 39 files.

**rules — the headline.** Only **5 of 88** files are byte-identical, and the drift is
**two-directional**: 25 of the 28 content-differing files are repo-larger, but 3 are live-larger
(`common/owner-ops-authorization.md` +1001 B, `common/performance.md` +178 B, `common/security.md`
+97 B). Neither side is a superset, so a one-directional sync **in either direction would destroy
content**. Extremes: `common/hooks.md` live 849 B vs repo 4,848 B; `common/agents.md` live 317 B vs
repo 2,064 B. Full 28-row table is in the JSON.

> **UNVERIFIED:** which side is authoritative *per file*. Settling experiment:
> `git log -1 --format=%cI -- rules/<path>` against the live file's mtime, per file, plus a content
> read of the 3 live-larger files. Until that runs, no reconcile direction is safe.

**Junk file found:** `~/.agents/skills/workflow-monitor/NUL` — 409 B, mtime 2026-07-26 08:47, a
Windows reserved device name as a real file, live-only. Found via the enumerator crash and confirmed
independently with `ls -la '//?/…/workflow-monitor/'`.

---

## 7. Hook dispatch manifest

`~/.claude/hooks/_dispatch/manifest.json` — 11,219 B, `version: 1`.

**Registration count: 25.**

| Event | Count | Registrations |
|---|---:|---|
| SessionStart | 6 | bg-registry/reconcile, memory-spool/replay, memory-spool/flush_check, heartbeat, open-loops/resurface, background-digest/reader |
| Stop | 9 | bg-registry/done_marker, heartbeat, wire-check, git-hygiene, honest-signal, stub-ledger/report, forge/todo-surfacer, journey-coverage, dark-surface |
| PostToolUse | 5 | memory-spool/flush_check, tool-result-sentinel, claim-guard/ledger-write, stub-ledger/record, edit-validate/record |
| PreToolUse | 5 | bg-registry/register, memory-spool/spool, dup-guard, monitor-autolaunch, codex-monitor-autolaunch |

A first pass reported **4** — it counted the top-level `events` keys instead of the per-event
`checks` lists. Recorded because an unreconciled 4-vs-25 is exactly the number that gets cited as
authoritative. Note this is the **live** manifest, and it is one of the 49 content-differing hooks
files vs the repo copy.

---

## 8. Test baseline

Runner: `command-center/_baseline_tests.py` · 512.4 s · 28 suites attempted.

> **Disclosed deviation from CI.** CI runs each suite with the venv `pytest` **console script**
> after `pip install -e`. This runner used `python -m pytest` and performed **no installs**
> (installing would mutate the shared interpreter). `-m pytest` prepends CWD to `sys.path`, so it is
> a **broken detector for packaging/import-path regressions** — it measures test outcomes only, not
> CI's packaging gate.
>
> `quality.yml`'s `test-python` job declares **60** steps; **28** ran here. The other 32 are
> non-pytest gates, isolated py3.12 venvs, or need editable installs. Those are **NOT-CHECKED**,
> not passing.

**Tally:** 21 PASS · 4 FAIL · 3 NOT-CHECKED.
**Aggregate (verbatim):** `passed: 5326, failed: 8, error: 4, skipped: 2, deselected: 1`.

Largest green suites (verbatim): `monitorcore: 1147 passed` · `agentspec: 582 passed, 1 deselected` ·
`taskwatch_monitor: 407 passed` · `mcp-manager: 335 passed` · `cloud-hub: 325 passed` ·
`codex-dbx-fanout: 234 passed` · `mcpctl: 191 passed`.

### The 8 failures, triaged — none survives as a real regression on `53c37c6c`

**(a) `command-center` — `3 failed, 45 passed`. Windows CRLF artifact. REFUTED as a regression.**

```
REACH-6 -: register snapshot sha256 1a404a91d819 != recorded 8b3e44cc3813
FAILED:cc-validate violations=1
```

Proof, at blob level (mechanically independent of the validator):

| Source | bytes | CRLF | sha256 |
|---|---:|---:|---|
| `git cat-file -p HEAD:command-center/sources/REGISTER.md` | 56,931 | 0 | `8b3e44cc3813…` |
| recorded `provenance.register_sha256` | 56,931 | — | `8b3e44cc3813…` ✅ **exact match** |
| working-tree copy | 57,235 | 304 | `1a404a91d819…` |

`57,235 − 56,931 = 304 = ` the CRLF count — the delta is pure EOL expansion. `core.autocrlf=true`
and `.gitattributes` carries no `*.md eol=lf` rule (`git check-attr text eol` → both `unspecified`),
so every `.md` checks out CRLF on Windows, while `tools/command-center/validate.py:217` hashes the
**working-tree** bytes.

**Residual real defect (CONFIRMED):** REACH-6 is unrunnable on *any* Windows checkout with default
autocrlf. CI stays green because Linux checks out LF. Fix: add `*.md eol=lf` to `.gitattributes`, or
normalise CRLF before hashing in `validate.py`.

**(b) `agent-self-harness` — `4 failed, 831 passed` → `835 passed`. REFUTED: sibling-induced.**
A concurrent agent modified `agent-self/harness/install.py` and added
`agent-self/harness/tests/test_deploy_command_center.py` while the runner executed. Same 835-test
total; 4 flipped red→green with no action by this unit.

**(c) `ci-tests-all` — `1 failed, 557 passed, 1 skipped`. POSIX-only test. REFUTED as a regression.**
`test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct` dies in fixture setup:
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0` at `os.fsdecode(b"\xff")`.
Linux surrogate-escapes those bytes; this Windows interpreter rejects them. Expected green on
ubuntu-latest — *confidence: likely (55–80%), not executed on Linux by this unit.*

**(d) `hooks-regression` — first run was my own mis-invocation. PARTIAL.**
`no tests ran … INTERNALERROR> SystemExit: 0` because I omitted CI's
`--ignore=hooks/memory-guard/test_scan.py --ignore=hooks/cmd-rewrite` (memory-guard exits at module
level). Re-run with CI's exact flags: **`1 failed, 1229 passed, 8 skipped, 10 xfailed in 297.51s`**.
The one residual — `hooks/iatrogenics/test_gate.py::TestCounterMechanics::test_counter_auto_clears_after_ttl`
(`assert not fired(out)` / `assert not True`) — **passed 3/3 when re-run in isolation**, so it is an
order- or load-dependent flake, not a deterministic failure. *Settling experiment: run the full
`hooks/` suite 5× with the CI ignores and record the failure rate; if it recurs, bisect with
`-p no:randomly` and by running the immediately-preceding test in the same process to find the state
leak.*

### NOT-CHECKED (3)

`mcpapply` (exit 4), `agentrail` (exit 4), `crcp` (exit 2, 4 collection errors) — all
`ModuleNotFoundError` / conftest import failures requiring `pip install -e`. CI's own comments
document that the bare-install form produces exactly this state.

### Headline

**5,326 tests pass. Zero of the 8 counted failures survive triage as a real regression on
`53c37c6c`.** The residual is one order/load-dependent flake plus one genuine Windows-portability
defect in the command-center REACH-6 gate.

---

## 9. Rollback

**Primary anchor:** `git -C C:/Users/Prekzursil/source/ast-integrate reset --hard 53c37c6cfb3e7bd1a48edbe604e1ea06a77b50b1`

> **Do not run that while sibling agents are active** — it would destroy their uncommitted work (a
> tracked modification and ~20 untracked files were live during this snapshot). Prefer a per-agent
> `git stash`, or branch-and-revert.

**Safer:** `git diff 53c37c6c --stat`, then revert only the paths your phase touched.

**The live harness trees are NOT covered.** `~/.agents/skills`, `~/.claude/hooks` and
`~/.claude/rules` are not under version control, and this snapshot records only counts, sizes and
per-file divergence — **not contents**. There is no rollback for a live-tree edit from this artifact.
To create one, copy the three trees to a dated backup directory before any deploy.

**Reproduce:** `python command-center/_baseline_probe.py` · `python command-center/_baseline_tests.py`

---

## 10. Artifacts written by this unit

| Path | What |
|---|---|
| `command-center/BASELINE-SNAPSHOT.json` | machine-readable snapshot |
| `command-center/BASELINE-SNAPSHOT.md` | this file |
| `command-center/_baseline_probe.py` | enumerator + detector control, re-runnable |
| `command-center/_baseline_probe_out.json` | full per-file divergence lists (1.38 MB) |
| `command-center/_baseline_tests.py` | test-baseline runner, re-runnable |
| `command-center/_baseline_tests_out.json` | per-suite verbatim tails |
| `command-center/_baseline_tests_console.log` | runner console output |

Nothing was staged or committed; nothing was deployed; no credential was read, printed or modified.
