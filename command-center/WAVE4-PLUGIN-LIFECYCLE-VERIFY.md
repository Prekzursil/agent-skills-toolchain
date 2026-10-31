---
title: WAVE4-PLUGIN-LIFECYCLE-VERIFY
type: note
permalink: dqverify-repo-20261013/command-center/wave4-plugin-lifecycle-verify
---

# WAVE 4 — Independent verification: Phase 5 plugin lifecycle

Unit: `verify/plugin-lifecycle`. Measured first, compared after: the lane's own
`platform/plugin/PHASE5-PLUGIN-REPORT.md` and `PACKAGE-MEASUREMENT.json` were NOT read
before measuring.

STATUS: **COMPLETE — all 5 contracted checks measured.**
COVERAGE: 5 of 5. Marketplace publish/revoke is NOT-CHECKED (different unit — see the
bottom section for the exact reason).

Probes live under `C:/Users/Prekzursil/AppData/Local/Temp/w4plug/` (temp, outside the repo;
nothing in `platform/` was modified). Prefixes used: `w4plug/prefix`, `health_prefix`,
`fail_a`, `fail_b`, `kill_1`, `kill_2`, `empty_prefix`.

| # | Check | Verdict |
|---|---|---|
| 1 | Build the package; byte size + file count | **CONFIRMED** |
| 2 | No .git / credentials / transcripts / caches | **CONFIRMED** |
| 3 | install / update / repair / rollback / uninstall | **CONFIRMED** (2 sub-defects) |
| 4 | Failed install leaves no partial state | **PARTIAL** (clean for in-process failures; hard kill leaves a blocking lock) |
| 5 | Health check + conformance validator can FAIL | **PARTIAL** — conform CONFIRMED 9/9; health has 2 blind spots + a non-gating control |

**Headline:** the package and the conformance validator are genuinely load-bearing and the
five lifecycle verbs all work, including rollback and uninstall. The health check is the
weak member: it verifies **existence, not integrity**, and its own both-states control is
not wired to the exit code. `platform/plugin` is **252/252 green** while every defect
below is live — a green suite is not coverage of these paths.

---

## Check 1 — BUILD (CONFIRMED)

    python platform/plugin/astplugin.py build --repo-root <repo> --out <tmp>/dist
    SUCCESS:build   exit 0

| metric | value |
|---|---|
| archive bytes | **95,093** (0.09 MB) |
| zip entries / files | **45 / 45** (no directory entries) |
| uncompressed payload | **288,265 B** (0.27 MB) |
| builder-counted payload files | 42 (+3 builder-written: plugin.json, INVENTORY, ALLOWLIST) |
| sha256 | `af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04` |

Determinism: built twice into two different output dirs → **identical sha256**. The
committed `platform/plugin/dist/ast-integrate-platform-1.0.0.zip` is **byte-identical**
(same 95,093 bytes, same sha256), so the committed artifact is reproducible from source.
All 45 entries carry one normalised timestamp `1980-01-01 00:00:00`.

The 2 GB failure the spec names is nowhere near: 0.09 MB against the builder's own
4 MB / 200-file budget (`build.py:45-46`).

## Check 2 — FORBIDDEN CONTENT (CONFIRMED)

Scanner: `w4plug/scan_pkg.py`, written from scratch. It deliberately does **not** import
`payload.classify_forbidden` — reusing the lane's own classifier would be the same
detector, not a second signal. It checks path components, filenames, suffixes,
secret-shaped byte patterns, and transcript/git-config content markers.

**Detector control (both-states):** a planted known-bad package containing `.git/config`,
`.env`, `credentials.json`, a PEM key block, a `.jsonl` transcript,
`__pycache__/*.pyc`, `.pytest_cache`, `node_modules`, a `.dll` and a nested `.zip`
produced **20 findings, exit 3**. The scanner's silence on the real package is therefore
meaningful.

**Real package: 0 findings, exit 0.** The archive is exactly: 1 manifest
(`.claude-plugin/plugin.json`), 2 builder-written policy docs (`PLUGIN-INVENTORY.json`,
`PLUGIN-ALLOWLIST.json`), `README.md`, `LICENSE`, 1 `bin/` entrypoint, 1 `commands/`
markdown, 1 `hooks/` script, 19 `lib/astplugin/*.py`, 18 `schema/*.schema.json`. No
`.git`, no cache dir, no `.pyc`, no log, no `.jsonl`, no credential file, no nested
archive, no native binary. Full listing in the JSON companion.

Disclosed detector weakness: the `password-assign` sub-pattern did not fire on the
fixture's JSON-shaped `{"password": "..."}` (the regex expects `key=`/`key:` with no
intervening quote). That entry was caught by filename instead, and 5 other secret
patterns fired, so the control does not rest on it. Settling experiment: add a JSON-key
variant `"key"\s*:\s*"…"` and re-run the control.

## Check 3 — FULL LIFECYCLE (CONFIRMED, with 2 sub-defects)

All five verbs run against `w4plug/prefix`. Real markers and exit codes:

| verb | marker | exit | what it actually did |
|---|---|---|---|
| `install` 1.0.0 | `SUCCESS:install` | 0 | 45 files, 288,265 B into `versions/1.0.0`; deployed `commands/astplugin.md` + `hooks/plugin_health.py` to `live/` |
| `update` → 1.1.0 | `SUCCESS:update` | 0 | `active_version` 1.0.0→1.1.0, `previous_version` 1.0.0, `history` `["1.0.0","1.1.0"]` |
| `repair` | `SUCCESS:repair` | 0 | restored the live file I deleted; **kept** the live file I hand-edited (`kept_live_override`) |
| `rollback` | `SUCCESS:rollback` | 0 | 1.1.0→1.0.0, `rolled_back_from: "1.1.0"`, both version dirs retained, `userdata_untouched: true`, 0 live files removed |
| `uninstall --retain-user-data` | `SUCCESS:uninstall` | 0 | removed both version dirs + the deployed hook; kept the owner-edited live file; `userdata/notes.txt` survived |
| `uninstall --purge-user-data` | `SUCCESS:uninstall` | 0 | `userdata/notes.txt` gone |

Extra properties I probed that nobody asked for but that make the above trustworthy:

* **`--dry-run` is real.** After `repair --dry-run` reported `restored: ["hooks/plugin_health.py"]`,
  the file was **still absent** on disk. Same for `uninstall --dry-run`: both version dirs
  still present afterwards. The dry-run is not a fake.
* **Owner edits survive.** `live/commands/astplugin.md` sha256 was byte-identical before
  and after `repair` (`D44F0C2C…C321`).
* **Rollback past the floor fails closed.** A second `rollback` with no earlier version:
  `FAILED:rollback E_TXN`, **exit 22**, with cause / impact / next-command / hint rendered.
* **Uninstall refuses an implicit data decision.** No `--retain-user-data`/`--purge-user-data`
  → `FAILED:uninstall E_USAGE`, **exit 2**, "Nothing was read and nothing was written."
* **The installed package runs.** I invoked the *installed* entrypoint
  `<prefix>/versions/1.0.0/bin/astplugin.py health-check` (not the source tree) and it
  produced a valid `health-report`. The shipped `bin/` + `lib/astplugin/` layout works.

### D-P5-1 (P2) — after `rollback`, `installed.json.archive_sha256` is stale

`state/installed.json` ends up self-inconsistent: `active_version: "1.0.0"` alongside
`archive_sha256: "aaf7bc56d4efb8a6adf4d4980ee3231c05c713c82f83e2c8c2ef7e599c0e8d05"`,
which is the **1.1.0** archive's hash (the 1.0.0 archive is `af62a883…`).

Cause, `platform/plugin/lifecycle.py:496-503`: rollback builds
`new_state = {**state, "active_version": …, "previous_version": None, "rolled_back_from": …,
"installed_at": …}` and never re-derives `archive_sha256`.

Contained, not currently exploited: `grep -rn archive_sha256 platform/plugin/*.py` shows the
field is only ever **written** (`lifecycle.py:267`, from install at `:312-314` and update at
`:401-403`); no probe or verifier reads it back. So it is a misleading state record rather
than a wrong gate verdict today — but any future integrity check, or an operator reading
`installed.json`, gets the wrong hash for the active version. Fix: record the target
version's archive hash (or drop the field on rollback).

### D-P5-2 (P3) — uninstall under-reports a surviving live file

Second uninstall reported `kept_live_edited: []` while `live/commands/astplugin.md` was
still on disk afterwards. Explanation is defensible — after the first uninstall removed
`deploy-provenance.json`, the reinstall classified that owner-edited file as live-unique and
never recorded it as deployed, so uninstall genuinely does not own it. But the result
document says nothing survived, and a caller reading `kept_live_edited` concludes `live/` is
clean of plugin-named artifacts. Report the untracked-but-plugin-named residue, or say
`unowned_live_paths`.

## Check 4 — FAILED INSTALL LEAVES NO PARTIAL STATE (PARTIAL)

Three injections, each into a fresh prefix, each snapshotting the whole prefix tree
(relpath → sha256) before and after. The assertion is **positive** — exactly which markers
must not exist — not "nothing blocking".

**A. Corrupt archive** (good 95,093-byte zip truncated to 47,546):
`FAILED:install E_CONFORM`, **exit 51**, "not a readable archive … (File is not a zip file)".
Post-state: `installed_json_exists: false`, `version_dirs: []`, `staging_entries: []`,
`live_files: []`, no lock. **Clean.**

**B. Failure AFTER the journal opened — the one that actually tests inverse replay.**
I pre-created `live/commands/astplugin.md` as a **directory**, so the deploy write fails
only after stage → verify → activate → record_installed have all applied.
`FAILED:install E_IO`, **exit 90**. Post-state: `version_dirs: []` and
`installed_json_exists: false` — the activated version directory and the recorded state were
**both** rolled back. `staging_entries: []`. The only live file is my own decoy obstruction.
**Clean, and this is the real proof.**

**C. Hard kill mid-transaction.** My first attempt killed at a fixed 0.12 s and died during
interpreter startup — zero writes, so it proved nothing; I discarded it and re-ran
deterministically, polling the journal until the target step was recorded and then killing.
Two variants (kill after the `stage` step, kill after the `activate` step) both landed
inside the open transaction (`record_observed_before_kill: true`).

Result: no orphaned version dir and no `installed.json` in either case, but an orphaned
`state/staging/<txn>` plus an unclosed transaction — expected, since a hard kill cannot run
an except-handler. The **next** operation's preflight ran crash recovery and the journal
gained a `recovered` event with staging cleaned. Retry then installed fine.

### D-P5-3 (P2) — a hard-killed install wedges the prefix for up to 1 hour

The killed process leaves `state/prefix.lock` (containing `install pid=<dead pid>`), and the
immediate retry is refused: `FAILED:install E_LOCK`, **exit 21**,
"prefix is locked by another lifecycle operation (66s old)".

`PrefixLock.__init__` (`platform/plugin/journal.py:99`) sets `stale_after: float = 3600.0`, and
`__enter__` (`:110-126`) raises `E_LOCK` whenever `age < stale_after`. So an unattended retry
— a CI installer, a scheduled update, a retry loop — is blocked for a **full hour** after
any crash.

Both directions measured, so this is not a one-sided reading:
* back-dating the lock's mtime by 2 h → `SUCCESS:install`, exit 0. The staleness-takeover
  branch does work; it simply needs an hour to arm.
* `health-check --prefix <p> --clear-stale-lock` removes the lock, after which
  `install` → `SUCCESS:install`, exit 0. A documented escape hatch exists.

Assessment: **fail-closed, not data-losing**, and the error text does name the cause ("a
previous run died holding the lock"). The defect is availability, and the 3600 s default is
unreasonably long for a lock whose holder PID can be checked for liveness. Fix: probe
whether the recorded PID is alive before honouring the lock, and/or cut the default to
minutes. Verdict PARTIAL rather than CONFIRMED because "no partial state" holds for version
content but not for this blocking lock file.

## Check 5 — CAN THE GATES FAIL? (PARTIAL)

### Conformance validator — CONFIRMED load-bearing

Controls first: the good package → `SUCCESS:conform` exit 0, and an **identical repack**
(same entries, rebuilt zip) → exit 0, which isolates repacking itself as harmless. Then 9
mutants:

| mutant | exit | rejected |
|---|---|---|
| drop `.claude-plugin/plugin.json` | 51 | yes |
| manifest missing `license` | 51 | yes |
| manifest `version: "not-a-semver"` | 51 | yes |
| tampered `lib/astplugin/cli.py` (inventory hash mismatch) | 51 | yes |
| missing entrypoint `bin/astplugin.py` | 51 | yes |
| drop `PLUGIN-INVENTORY.json` | 51 | yes |
| extra `.git/config` | 51 | yes |
| extra `.env` with a PLACEHOLDER token | 51 | yes |
| extra unlisted `random/unlisted.txt` | 51 | yes |

**9 of 9 rejected, 0 survivors.** This is not a no-op gate: it catches content tampering,
manifest schema violations, missing declared files, and unlisted/forbidden additions.

### Health check — PARTIAL: it fails, but it verifies existence rather than integrity

Controls: a good installed prefix → `SUCCESS:health-check` exit 0 with 8/8 PASS. A
completely empty prefix → **exit 50**, failing `prefix-layout`, and it honestly marks the 4
inapplicable probes `SKIP` (reported as `passed: 3, skipped: 4, failed: 1`) rather than
folding SKIP into PASS. Not fail-open.

Six independent tampers of my own (not the lane's `break_()` functions), restoring between
each — **4 detected, 2 missed**, and all six restored to exit 0:

| tamper | health-check | detected |
|---|---|---|
| truncate `versions/1.0.0/.claude-plugin/plugin.json` | 50 | yes |
| `installed.json active_version` → absent `9.9.9` | 50 | yes |
| delete `live/hooks/plugin_health.py` | 50 | yes |
| plant a cache entry whose bytes do not hash to its key | 50 | yes |
| **delete `versions/1.0.0/lib/astplugin/cache.py`** | **0** | **NO** |
| **overwrite `live/hooks/plugin_health.py` with junk** | **0** | **NO** |

### D-P5-4 (P2) — `installed-state` cannot see a mutilated installed runtime

`_probe_installed_state` (`platform/plugin/health.py`) checks only `vroot.exists()` and
`(vroot / MANIFEST_RELPATH).exists()`, then returns PASS
`"active version 1.0.0 is present and manifested"`. Deleting any of the 19 installed runtime
modules leaves `ok: true`, exit 0 — and `doctor` also exits 0, so the remediation surface
says nothing either.

The data to catch this is sitting in the same directory, unread:
`versions/1.0.0/PLUGIN-INVENTORY.json` carries `sha256` + `size` for all 45 files. Failure
scenario: a partially-extracted or half-deleted install reports healthy, and the first
symptom the owner sees is an `ImportError` from the hook or CLI at use time.

### D-P5-5 (P2) — `deployed-files-intact` means "present", not "intact"

Its own body is `missing = [rel for rel in prov.records if not (live / rel).exists()]`.
Meanwhile `state/deploy-provenance.json` records `content_sha256` per deployed file —
never compared. Measured asymmetry: **deleting** `live/hooks/plugin_health.py` → exit 50,
but **replacing its contents** with `# tampered\n` → exit 0.

This is the security-relevant one: `hooks/plugin_health.py` is a script projected into live
config to be executed. Silent post-deploy content substitution of an executed hook is
invisible to both `health-check` and `doctor`. `live-no-divergence` does not cover it either
— a changed live file classifies as a legitimate owner override, and without the provenance
hash "owner edited it" and "something else rewrote it" are indistinguishable. Fix is one
comparison: hash the live file against `content_sha256` and report `modified-since-deploy` as
its own state.

### D-P5-6 (P2) — `health-check --controls` cannot fail on an INVALID control

The control harness itself is good and honest: 6 of 8 probes carry a `break_()` and are
proven VALID by a real three-state test (`healthy=PASS`, `broken=FAIL`, `restored=PASS`), and
the 2 without one are reported `NOT-CHECKED` with reason `"no break_() is declared for this
probe"` — it does **not** claim a false 8/8.

But the verdict is not wired to the outcome. `HealthReport.ok` is `not self.failed`
(`health.py:358-359`), reading only live probe results; `cli.py:315` returns
`EXIT_OK if report.ok else 50`. Controls are attached to the document and ignored by the gate.

Proven executably (`w4plug/prove_controls_not_gating.py`), not inferred from reading code: I
replaced one probe's `break_()` with a no-op, i.e. simulated exactly the thing the control
exists to catch — a probe that cannot detect its own invariant.

| | baseline | one control sabotaged |
|---|---|---|
| `control_valid` | 6 | 5 |
| `control_invalid` | 0 | **1** (`cache-integrity`, reason `healthy=PASS broken=PASS restored=PASS`) |
| `control_not_checked` | 2 | 2 |
| exit code | 0 | **0** |
| stdout marker | `SUCCESS:health-check` | **`SUCCESS:health-check`** |

The harness detected the sabotage perfectly and the command's terminal state was
byte-identical to healthy. Per `cli.py`'s own docstring the marker/exit code *is* the
supported contract ("so a caller (or a harness) can parse the outcome without reading
prose"), so a harness cannot see this. `not_checked > 0` is likewise invisible to the exit
code. Fix: fail non-zero when `invalid > 0` (and choose deliberately whether
`not_checked > 0` warns or fails).

### D-P5-7 (P3) — `cache-integrity` repairs on read, so its FAIL is not reproducible

`_probe_cache_integrity` calls `Cache(...).verify()`, which **quarantines** offending
entries. Measured on one planted bad entry, with nothing repaired by me between runs:

    health-check run 1 -> FAILED:health-check exit=50   (entry moved to state/cache/quarantine/)
    health-check run 2 -> SUCCESS:health-check exit=0

A diagnostic that mutates state means "run it twice to corroborate" is impossible for this
probe, and a monitor polling `health-check` sees one red then permanent green. Mitigated, so
P3 not P2: the evidence is preserved — the entry plus a `.reason.json` land in
`state/cache/quarantine/`. Still worth splitting into a read-only probe plus an explicit
`cache --verify` repair (which already exists as its own verb).

### D-P5-8 (P2) — the SHIPPED README overclaims the control coverage

`platform/plugin/build.py:197`, which becomes **README.md line 27 inside the built
package** (verified by reading it back out of the zip), states:

    * every health probe ships a both-states control proving it fails when its invariant breaks;

The tool's own control summary contradicts it: `not_checked: 2`, with reason
`"no break_() is declared for this probe"` for `no-open-transactions` and `interpreters`.
So **6 of 8**, not every.

This is the overclaim pattern, not a broken fix: the control harness is well built and
honest — it reports its own gap rather than inventing a verdict. The *sentence* is wider
than the evidence, and it ships to end users. `PHASE5-PLUGIN-REPORT.md` does not disclose
the two uncontrolled probes either (`grep -niE "break_|no break|2 probes"` → no match).
Correctly-scoped version: "6 of 8 health probes ship a both-states control; the other 2
are reported NOT-CHECKED because no `break_()` is declared."

### The suite is green over all of this

`python -m pytest plugin -q` → **252 passed** in 56 s, while D-P5-1 and D-P5-4 through
D-P5-7 are all live. None of the 252 tests catches the two health blind spots — proven by
my tampers going undetected against a green suite. This is the mutation-testing lesson in
its usual shape: green ≠ that behaviour is protected.

---

## Comparison with the lane's own report (read only AFTER measuring)

Every package NUMBER the lane published reproduces exactly, independently:

| claim in `PACKAGE-MEASUREMENT.json` | my independent measurement | agree |
|---|---|---|
| `archive_bytes: 95093` | 95,093 | yes |
| `member_count: 45` | 45 | yes |
| uncompressed 288,265 | 288,265 | yes |
| `archive_sha256: af62a883…3067b04` | `af62a883…3067b04` | yes |
| all 10 `absence_checks: true` | 0 findings from an unrelated scanner | yes |
| `credential_scan blocking: 0` over 45 members | 0 secret-shaped hits over 45 members | yes |

The lane also ran a detector control before claiming its zeros
(`detector_control_valid: true`), which is why those zeros were worth reproducing rather
than distrusting. `PHASE5-PLUGIN-REPORT.md:280`'s health claim ("8 probes; exits 50 on
failure; `doctor` maps each failure to its exact command") is accurate as written and does
not overclaim integrity.

So the lane's build-and-package work is honest and holds up. What it did **not** do is
adversarially tamper with an *installed* prefix or with *deployed* files — which is exactly
where D-P5-4 and D-P5-5 live — and it shipped one sentence wider than its evidence
(D-P5-8).

## NOT-CHECKED

* **Marketplace** `publish → install → verify signature+SBOM → REVOKE → refuse`
  (`platform/marketplace/`, 93 files). Out of this unit — my brief's five numbered checks
  are all plugin-scoped. It remains unverified as the pinned ground truth states, and needs
  its own unit; I did not touch it, so I can offer no verdict.
* **Real `~/.claude` deployment.** Every run used `--live` under a temp prefix. The
  projection into a real live config directory is untested here by choice (it would mutate
  the operator's harness).
* **Cross-platform.** Windows 11 / CPython 3.14.6 only. The manifest declares
  `platforms: windows/macos/linux` and `shells: pwsh/bash/zsh/cmd`; I exercised one
  combination.
* **Concurrency.** I proved a stale lock blocks a retry, but did not run two genuinely
  simultaneous lifecycle operations to test the lock under real contention.

## Note surfaced, not acted on

The harness emitted a POTENTIAL-CREDENTIAL notice (`sha256:ad70f44c9def`) against my own
known-bad **fixture generator**, which contains only PLACEHOLDER values assembled at runtime
and lives in a temp dir outside the repo. No credential was read, printed, modified or
rotated (AGENTS.md §9).