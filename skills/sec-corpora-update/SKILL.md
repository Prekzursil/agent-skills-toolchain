---
name: sec-corpora-update
description: Refresh the local security-knowledge corpora under D:\knowledge (PayloadsAllTheThings, GTFOBins, LOLBAS, OWASP WSTG, OWASP CheatSheets, Atomic Red Team, plus SecLists, Exploit-DB, MITRE ATT&CK STIX, MISP galaxy/warninglists, signature-base, CTID adversary-emulation-library, Control Validation Compass, sysmon-modular, LOLDrivers) with a shallow git pull each. Idempotent and fail-open per repo - one repo failing never aborts the rest, and the script always exits 0. Use when the secsearch or lolbin-lookup corpora are stale; HackTricks is refreshed by its own htk_update.ps1.
license: Skill MIT. Refreshes third-party corpora retained for personal local reference only; each corpus keeps its own upstream license (see "Corpora and licenses" below and D:\knowledge\CORPORA.md).
---

# sec-corpora-update - refresh local security corpora

Pulls the latest upstream content for every non-HackTricks corpus that backs the `secsearch`,
`lolbin-lookup`, and the blue / purple / CTI lookups. Shallow (`--depth 1`), idempotent, and
**fail-open per repo**: each pull runs in its own try/catch, a failure on one corpus is reported
but never aborts the others, and the script always exits 0.

## Run

PowerShell (canonical Windows runner):

```
pwsh D:\knowledge\sec-corpora-update.ps1
```

Cross-platform Python twin (same corpus list, same fail-open contract, same `exit 0`):

```
python3 scripts/sec_corpora_update.py --root D:\knowledge
```

(The version-controlled source of the PowerShell script is
`skills/sec-corpora-update/scripts/sec-corpora-update.ps1`; a runnable copy lives at
`D:\knowledge\sec-corpora-update.ps1` next to the corpora. Either script works - override the
corpora root with `-Root` / `--root` or `$env:SEC_CORPORA_ROOT`.)

Each line is reported as `OK`, `FAILED`, or `SKIP`. This refresher only pulls clones that already
exist under the root - a directory with no `.git` is reported `SKIP`, never cloned. Clone each
corpus once (into the directory name in the table below) before the first refresh; the multi-GB
clones are deliberately not performed by this script.

Refreshes (directory names under `$Root`):
`payloadsallthethings`, `gtfobins`, `lolbas`, `owasp-wstg`, `owasp-cheatsheets`,
`atomic-red-team`, `seclists`, `exploitdb`, `attack-stix-data`, `misp-galaxy`,
`misp-warninglists`, `signature-base`, `adversary-emulation-library`,
`control-validation-compass`, `sysmon-modular`, `loldrivers`.

## Corpora and licenses

The six original corpora (`payloadsallthethings`, `gtfobins`, `lolbas`, `owasp-wstg`,
`owasp-cheatsheets`, `atomic-red-team`) are unchanged; their sizes and licenses are catalogued in
`D:\knowledge\CORPORA.md`. The ten added 2026-09-02 (W-corpus, blue / purple / CTI) with their
official upstream and license:

| Directory | Upstream remote (clone once) | License |
|-----------|------------------------------|---------|
| `seclists` | `https://github.com/danielmiessler/SecLists.git` | MIT |
| `exploitdb` | `https://gitlab.com/exploit-database/exploitdb.git` (**GitLab**, not GitHub) | GPL-2.0-or-later (Exploit-DB / SearchSploit) |
| `attack-stix-data` | `https://github.com/mitre-attack/attack-stix-data.git` | MITRE ATT&CK Terms of Use (© The MITRE Corporation) |
| `misp-galaxy` | `https://github.com/MISP/misp-galaxy.git` | CC0-1.0 or BSD-2-Clause (dual) |
| `misp-warninglists` | `https://github.com/MISP/misp-warninglists.git` | CC0-1.0 or BSD-2-Clause (dual) |
| `signature-base` | `https://github.com/Neo23x0/signature-base.git` | Detection Rule License (DRL) 1.1; some YARA files carry a per-file `license` meta (e.g. CC BY-NC 4.0) |
| `adversary-emulation-library` | `https://github.com/center-for-threat-informed-defense/adversary_emulation_library.git` | Apache-2.0 (CTID / MITRE; uses ATT&CK) |
| `control-validation-compass` | `https://github.com/ControlCompass/ControlCompass.github.io.git` | MIT |
| `sysmon-modular` | `https://github.com/olafhartong/sysmon-modular.git` | MIT |
| `loldrivers` | `https://github.com/magicsword-io/LOLDrivers.git` | Apache-2.0 |

Provenance notes:

- **Exploit-DB** carries exploit proof-of-concept code that this skill keeps only for
  defensive/`searchsploit` offline reference - it is **never executed**, and no exploit authoring
  or running happens here (owner-ops H2 + Cursor cyber hard rule). Its official git home is GitLab.
- **signature-base** is DRL 1.1 overall, but an individual YARA file may declare a stricter
  `license` in its `meta` (CC BY-NC 4.0 on some rules) - honor the per-file meta.
- **attack-stix-data** and **adversary-emulation-library** use MITRE ATT&CK(R) under the
  [ATT&CK Terms of Use](https://attack.mitre.org/resources/terms-of-use/).

All corpora are retained for personal, local, defensive reference only. Refreshing them here does
not relicense them; the upstream license above governs each.

## Not covered

- **HackTricks** is a sparse, nested checkout (`hacktricks/` + `hacktricks-cloud/`); refresh it with
  its own `htk_update.ps1` (sparse src-only, images excluded), not this script.

See `D:\knowledge\CORPORA.md` for the full corpus catalogue, sizes, and licenses.

## Tests

`tests/test_sec_corpora_update.py` (pytest, no network, 8 tests) runs the Python twin against a
fake `$Root` of fake git repos and missing directories - via a POSIX `git` shim, so nothing is
fetched - and asserts the fail-open contract: `OK` / `FAILED` / `SKIP` reporting and counts, all
16 corpora still visited after one fails, and `exit 0` even when a pull fails or the `git` binary
is absent. It also parses the PowerShell `$corpora` array (comment-aware) and asserts it equals the
Python `CORPORA` list, and pins the PowerShell contract statically (`pull --depth 1`, per-repo
`try {} catch {}`, `$ErrorActionPreference = 'Continue'`, trailing `exit 0`) because `pwsh` is not
available in cloud CI:

```
python3 -m pytest .agents/skills/sec-corpora-update/tests -q
```

The `skills/sec-corpora-update/` mirror is byte-identical; add `--import-mode=importlib` if you
collect both copies in one pytest invocation.
