# W-corpus receipt

Measured 2026-09-02. Every section below was rewritten from a measured result; the skeleton
sentence ("the unit died before measuring anything") no longer applies.

COVERAGE: no sections UNKNOWN

## Wave

W-corpus — extend the fail-open `sec-corpora-update` refresher with 10 additional shallow-clone
corpora, keep exit 0, document licenses/provenance, dual-write `.agents/skills/` and `skills/`.

## Scope (files edited)

- `.agents/skills/sec-corpora-update/SKILL.md`
- `.agents/skills/sec-corpora-update/scripts/sec-corpora-update.ps1`
- `.agents/skills/sec-corpora-update/scripts/sec_corpora_update.py` (new)
- `.agents/skills/sec-corpora-update/tests/test_sec_corpora_update.py` (new)
- the same four paths under `skills/sec-corpora-update/` (byte-identical mirror)
- `docs/plans/cyber-receipts/W-corpus.md` (this file)

Nothing outside that list was touched: `agents.json`, other waves' files and `quality.yml` are
unchanged by this wave (verified with `git diff --cached --name-only` before each commit).

## Corpora added (directory names under `$Root`)

MEASURED: `CORPORA` / `$corpora` now hold 16 names; the original 6 are kept first in their
original order, followed by the 10 added:

| Directory | Upstream remote (clone once, by hand) | License |
|-----------|----------------------------------------|---------|
| `seclists` | `https://github.com/danielmiessler/SecLists.git` | MIT |
| `exploitdb` | `https://gitlab.com/exploit-database/exploitdb.git` (official home is GitLab) | GPL-2.0-or-later |
| `attack-stix-data` | `https://github.com/mitre-attack/attack-stix-data.git` | MITRE ATT&CK Terms of Use |
| `misp-galaxy` | `https://github.com/MISP/misp-galaxy.git` | CC0-1.0 / BSD-2-Clause (dual) |
| `misp-warninglists` | `https://github.com/MISP/misp-warninglists.git` | CC0-1.0 / BSD-2-Clause (dual) |
| `signature-base` | `https://github.com/Neo23x0/signature-base.git` | DRL 1.1 (+ per-file YARA `license` meta, some CC BY-NC 4.0) |
| `adversary-emulation-library` | `https://github.com/center-for-threat-informed-defense/adversary_emulation_library.git` | Apache-2.0 (CTID) |
| `control-validation-compass` | `https://github.com/ControlCompass/ControlCompass.github.io.git` | MIT |
| `sysmon-modular` | `https://github.com/olafhartong/sysmon-modular.git` | MIT |
| `loldrivers` | `https://github.com/magicsword-io/LOLDrivers.git` | Apache-2.0 |

Exploit-DB choice: the `exploitdb` git remote (the repo `searchsploit` reads) rather than a
separate searchsploit clone; its official git home is GitLab, which SKILL.md records. The corpus
is retained for offline defensive/`searchsploit` reference only and is never executed here.

**Nothing was cloned in this VM.** The refresher only pulls clones that already exist under the
root; a missing directory or a directory with no `.git` is reported `SKIP`, never fetched. The
end-to-end run below used throwaway local repos under `/tmp`, deleted afterwards.

## Script change

- `sec-corpora-update.ps1`: `$corpora` array extended with the 10 names (multi-line, commented).
  Contract unchanged: `git pull --depth 1 --no-edit` per repo, `try {} catch {}` per repo,
  `$ErrorActionPreference = 'Continue'`, trailing `exit 0`.
- `sec_corpora_update.py` (new): cross-platform Python twin with the identical list and contract —
  per-repo `try/except`, `SKIP` for non-clones, `OK`/`FAILED` by git exit code, always returns 0,
  `--root` / `$SEC_CORPORA_ROOT` override, `GIT_TERMINAL_PROMPT=0`. Added because `pwsh` is
  **absent** in this VM (`command -v pwsh` -> nothing), so the PowerShell script cannot be
  executed or tested here; the twin makes the refresher runnable and testable on POSIX.

## Test

`tests/test_sec_corpora_update.py` — pytest, no network, POSIX `git` shim (a bash script that
exits 1 when the `-C` repo contains a `.fail` marker, else prints `Already up to date.` and exits 0).

MEASURED: **8 passed** per copy, **16 passed** when both copies are collected together with
`--import-mode=importlib` (the mirror shares the basename), `0 failed`, ~0.1 s:

1. `test_existing_corpora_kept_first_in_order` — the original 6 are unchanged and first.
2. `test_all_added_corpora_present_no_dupes` — all 10 present, 16 unique names total.
3. `test_ps1_comment_stripper_ignores_parens_in_comments` — regression for a real bug this suite
   caught mid-wave: the first PS1 parser stopped at the `)` inside the `# Added ... (W-corpus)`
   comment and saw only 6 names (`1 failed, 5 passed` on the first run). The parser is now
   comment-aware and quote-preserving.
4. `test_ps1_and_python_lists_stay_in_sync` — the PowerShell `$corpora` array parsed from the
   `.ps1` equals the Python `CORPORA` tuple (guards the two languages and both dual-write copies).
5. `test_ps1_keeps_fail_open_contract` — static pin of the PS1 contract (`pull --depth 1`,
   `try {`/`} catch {`, `$ErrorActionPreference = 'Continue'`, last line `exit 0`), since pwsh
   cannot run here.
6. `test_default_root_prefers_env` — `$SEC_CORPORA_ROOT` wins, else `D:\knowledge`.
7. `test_fail_open_ok_failed_skip` — fake root: `seclists` (has `.git`) -> `OK`, `exploitdb`
   (`.git` + `.fail`) -> `FAILED`, `gtfobins` (dir, no `.git`) -> `SKIP`, 13 absent -> `SKIP`;
   asserts `ok=1 failed=1 skipped=14`, all 16 corpora reported (one failure did not abort the
   loop), return code 0.
8. `test_fail_open_when_git_binary_missing` — `PATH` set to an empty dir so `git` cannot be
   resolved: `FileNotFoundError` is caught, reported as `FAILED seclists`, `ok=0 failed=1
   skipped=15`, return code 0.

End-to-end with the **real** `git` binary (no shim, no network): a `file://` bare repo and a
`--depth 1` clone of it as `seclists`, `git init` with no remote as `exploitdb`, a bare directory
as `gtfobins`, everything else absent. Output: `OK seclists : Already up to date.`,
`FAILED exploitdb : git branch --set-upstream-to=...`, 14 `SKIP`, summary
`ok=1 failed=1 skipped=14`, **`exit=0`**. Temp tree removed afterwards.

Not measured: the `.ps1` was not executed (no `pwsh`); its behavior is pinned statically (test 5)
and by list parity (test 4) only.

## Licenses / provenance

Documented in `SKILL.md` ("Corpora and licenses" table + provenance notes): upstream remote and
license for each of the 10 added corpora (table above), the GitLab home of Exploit-DB, the
per-file YARA `license` meta caveat for `signature-base`, and the ATT&CK Terms of Use for the two
MITRE-derived corpora. All corpora remain under their upstream licenses; refreshing does not
relicense them. Retained for personal, local, defensive reference only; no exploit is written or
run by this wave.

## Dual-write sync

MEASURED: `diff -r .agents/skills/sec-corpora-update skills/sec-corpora-update` -> no output
(`TREES IDENTICAL`) at commit time. The test docstring was made path-neutral so the two copies are
byte-identical rather than differing only in their own path.

## ruff

MEASURED with ruff 0.15.17 (the pinned gate version), repo `ruff.toml`:

- `ruff check .agents/skills/sec-corpora-update skills/sec-corpora-update` -> `All checks passed!`
- `ruff format --check` on the same paths -> `4 files already formatted`

(Three lines were restructured by hand so `ruff format` is a no-op instead of producing the
`except (\n Exception\n) as exc:` shape.)

## Commit

- **`d7894f64de79f3a186f8c8b8406e33d5c3597543`** — `Add 10 blue/purple/CTI corpora to fail-open
  sec-corpora-update refresher` — path-scoped to `.agents/skills/sec-corpora-update/` and
  `skills/sec-corpora-update/` (8 files, +772/-26); pushed to
  `origin cursor/cyber-suite-full-program` on the first attempt (`a49a2e64..d7894f64`), no race.
- This receipt is committed separately (receipt-only path scope) right after; see `git log` for
  its SHA.

## PARENT MERGE

None. This wave edits only skill files under `sec-corpora-update` and this receipt. No
`agents.json` / parked / provenance / control-plane changes are required, and no new CI step was
added (`quality.yml` is out of this wave's scope); the suite is run manually with
`python3 -m pytest .agents/skills/sec-corpora-update/tests -q`. If the parent wants it gated, the
one-line step is that command (add `--import-mode=importlib` if both copies are collected).
