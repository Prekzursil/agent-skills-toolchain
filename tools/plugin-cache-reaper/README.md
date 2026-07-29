# plugin-cache-reaper — sweep abandoned plugin-install staging clones

**This is a MITIGATION, not a fix.** The writer is Claude Code itself, and it ships as a
compiled native binary, so there is no source line of ours to patch. What is fixable —
never letting the husks accumulate unbounded — is what this tool does.

## The leak, measured

`~/.claude/plugins/cache` holds real plugin trees at `cache/<marketplace>/<plugin>/<version>`.
When the CLI materialises a plugin whose marketplace entry declares a **remote** source it
first clones into a staging directory *directly under the cache root*:

| marketplace entry `source.source` | staging directory |
|---|---|
| `git-subdir` (79 of the 276 entries in `claude-plugins-official`) | `temp_subdir_<epoch_ms>_<rand6>.clone` |
| `url` / `git` (142 of those 276) | `temp_git_<epoch_ms>_<rand6>` |

The name is built as `temp_{kind}_{Date.now()}_{rand6}`. The `kind` vocabulary
(`git`, `subdir`, `github`, `npm`, `local`, `unknown`) was recovered from the string pool of
`C:/Users/Prekzursil/.local/bin/claude.exe` (**2.1.220**) at byte offset **109756512**; only
`subdir` and `git` have been observed live. The strings `temp_git_` and `plugins/cache` do
**not** appear in the binary (detector control: `marketplace` → 1568 hits,
`installed_plugins.json` → 18), which is why the writer cannot be quoted as vendor
`file:line` — the JS is compiled, and the name is assembled from those interned fragments.

Three paths were exercised against an isolated `CLAUDE_CONFIG_DIR` sandbox:

| path | staging dir afterwards |
|---|---|
| install succeeds (`claude plugin install 42crunch-api-security-testing@claude-plugins-official`) | **removed** — polling saw it live for ~5 s, then gone |
| clone fails fast (bogus repo URL, `git-subdir` **and** `url`) | **removed** |
| process **killed mid-clone** | **SURVIVES** — leaks, holding a partial `.git` and no worktree |

The survivor's shape matches the live husks exactly: the only child of a leaked
`temp_*` directory is `.git`. There is no on-exit handler and no start-up sweep, so every
interrupted materialisation leaks one staging tree permanently.

Paths that were checked and do **not** leak: `claude plugin marketplace update`, an
idempotent re-`install`, and a fresh session start (`claude -p`, with the version dirs
deliberately wiped first — a session start does not re-materialise them at all).

## Usage

```bash
# dry-run against ~/.claude/plugins/cache (the default root)
python tools/plugin-cache-reaper/reap.py

# actually delete husks older than 2h by BOTH age signals
python tools/plugin-cache-reaper/reap.py --apply

# scan a sandbox / another profile
python tools/plugin-cache-reaper/reap.py --root D:/profile/.claude/plugins/cache --apply
```

Exit is `0` with a `SUCCESS:plugin-cache-reap …` marker, or `2` with
`FAILED:plugin-cache-reap …` (AGENTS.md §4 terminal state). Stdlib only.

Schedule it (daily 03:20, dry-run switch inside the script) with:

```powershell
pwsh -File tools/plugin-cache-reaper/install_reaper_task.ps1            # register
pwsh -File tools/plugin-cache-reaper/install_reaper_task.ps1 -Uninstall # remove
```

The installer is **not** run by CI or by any hook; registering the task is an explicit
owner action.

## Why the safety rules look paranoid

It deletes from a live user directory, so:

* **Name allow-list.** Only `STAGING_RE` matches are candidates. A real cache entry
  (`claude-plugins-official`, `aikido`, `1.2.3`) can never match, and neither can
  `temp_subdir_…​.clone.bak`.
* **Two independent age signals, AND-ed.** The epoch-ms in the *name* and the directory's
  own *mtime* must both clear `--min-age-minutes` (default 120). A single signal is not
  evidence: an in-flight clone has an old-enough name the instant it is created — measured,
  the reaper refused a real husk 0 s after the kill on exactly that ground
  (`rules/common/single-signal-verification.md`).
* **One non-recursive scan.** The husks contain deep `.git` trees that blow `MAX_PATH`; a
  recursive glob over this directory is the documented ENAMETOOLONG trap (see
  `tools/glob-argv-guard`). A `Get-ChildItem -Recurse` over the live cache returned a false
  `0 bytes` for exactly that reason during this investigation.
* **Long-path + read-only safe delete.** `\\?\` prefixing plus a chmod retry, because git
  marks pack files read-only. Measured: the smoke run deleted a real husk of 29 files, 3 of
  them read-only. `shutil.rmtree` is deliberately not used — its `onerror` callback is gone
  in Python 3.14 and its `onexc` replacement does not exist in the 3.11 the CI lane pins.
* **Root shape assertion.** `--root` must end in `plugins/cache`, so a typo cannot turn this
  into a generic deleter.
* **Dry-run default.**

## Tests

```
pytest --cov=reap --cov-branch --cov-report=term-missing --cov-fail-under=100   # 45 passed, 100%
python test_reap_mutations.py                                                  # 5/5 killed
```

The mutation probe is the both-states check applied to the suite: it reverts the AND-gate to
an `or`, drops the regex end-anchor, removes the is-a-directory check, no-ops the root
validation, and makes dry-run delete anyway — the suite must go RED for each. The first run
found a real hole (the decoy file in the discovery test had a fresh mtime, so the
is-a-directory check was never the thing excluding it); the fixture was backdated and the
mutation now dies.

## End-to-end smoke (real husk, not a fixture)

Killed a live `claude plugin install` mid-clone, then:

```
AFTER temp_*: 1 :: temp_subdir_1785342959924_jdvey2.clone
  contents: .git
=== dry-run, default 120-minute window ===
SUCCESS:plugin-cache-reap would reap 0 staging dirs (0 bytes) ...
=== dry-run, 1-minute window (name still fresh -> still refused) ===
SUCCESS:plugin-cache-reap would reap 0 staging dirs (0 bytes) ...
husk=temp_subdir_1785342959924_jdvey2.clone files=29 readonly=3
=== after backdating BOTH signals by 3h, --apply ===
SUCCESS:plugin-cache-reap reaped 1 staging dirs (28795 bytes) ... by_kind={'subdir': 1}
remaining temp_*: 0
real cache entries still present: claude-plugins-official
```

## Known-unknowns

* **UNVERIFIED — what drives the volume.** 1680 husks accumulated over 2026-07-23..29
  (`temp_subdir_*` 1623, `temp_git_*` 55) in bursts (601 on 07-24, 759 on 07-26). Process
  kills reproduce the leak one husk at a time; nothing measured here explains hundreds per
  day. The cache also held version dirs for *hundreds of plugins that are not installed*,
  which points at the interactive `/plugin` browse UI materialising previews — untested,
  because it cannot be driven headlessly. Settling experiment: record `temp_*` names (they
  carry epoch-ms) before and after a `/plugin` browse session and check whether the ms
  values cluster within seconds, which would mean one interrupted run leaks many husks at
  once rather than one.
* **UNVERIFIED — the clone-timeout abort path.** The CLI prints
  `Cloning repository (timeout: 120s)`. A fast clone failure cleans up, but a *timeout*
  abort was not exercised. Settling experiment: point a `git-subdir` entry at a repo behind
  a throttled proxy so the clone exceeds 120 s, then check the cache.
* **NOT corroborated — the "~333 MB/day" figure.** No byte total for the accumulated husks
  was ever measured here; the one attempt returned a false `0` (see the ENAMETOOLONG note
  above) and the husks were deleted by a concurrent actor before a long-path-aware walk
  could run. The single real byte measurement in this document is one husk = 28,795 bytes
  for a small plugin repo. Settling experiment: run `reap.py` (dry-run, it tallies bytes
  long-path-safely) after a fresh week of accumulation.
