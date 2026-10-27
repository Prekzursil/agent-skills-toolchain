---
name: sec-corpora-update
description: Refresh the local security-knowledge corpora under D:\knowledge (PayloadsAllTheThings, GTFOBins, LOLBAS, OWASP WSTG, OWASP CheatSheets, Atomic Red Team) with a shallow git pull each. Idempotent and fail-open per repo - one repo failing never aborts the rest. Use when the secsearch or lolbin-lookup corpora are stale; HackTricks is refreshed by its own htk_update.ps1.
license: Skill MIT. Refreshes third-party corpora retained for personal local reference only. See D:\knowledge\CORPORA.md.
---

# sec-corpora-update — refresh local security corpora

Pulls the latest upstream content for every non-HackTricks corpus that backs the `secsearch` and
`lolbin-lookup` skills. Shallow (`--depth 1`), idempotent, and **fail-open per repo**: each pull runs
in its own try/catch, a failure on one corpus is reported but never aborts the others, and the script
always exits 0.

## Run

```
pwsh D:\knowledge\sec-corpora-update.ps1
```

(The version-controlled source of this script is `skills/sec-corpora-update/scripts/sec-corpora-update.ps1`;
a runnable copy lives at `D:\knowledge\sec-corpora-update.ps1` next to the corpora. Either works —
override the corpora root with `-Root` or `$env:SEC_CORPORA_ROOT`.)

Refreshes: `payloadsallthethings`, `gtfobins`, `lolbas`, `owasp-wstg`, `owasp-cheatsheets`,
`atomic-red-team`. Each line is reported as `OK`, `FAILED`, or `SKIP`.

## Not covered

- **HackTricks** is a sparse, nested checkout (`hacktricks/` + `hacktricks-cloud/`); refresh it with
  its own `htk_update.ps1` (sparse src-only, images excluded), not this script.

See `D:\knowledge\CORPORA.md` for the full corpus catalogue, sizes, and licenses.
