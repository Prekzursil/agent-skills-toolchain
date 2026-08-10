---
name: lolbin-lookup
description: Structured living-off-the-land binary lookup against the local GTFOBins (Unix) and LOLBAS (Windows) corpora under D:\knowledge. Answers "what can binary X do" — name to technique/category to ready command — by parsing GTFOBins YAML entries (file-read, file-write, shell, suid, sudo, ...) and LOLBAS yml Commands (Category, MitreID, Privileges). Use when you have a specific binary (nmap, certutil, tar, msbuild, ...) and want its abuse techniques and exact commands; use secsearch instead for prose/cross-source security lookups.
license: Skill MIT. Indexed content is GTFOBins and LOLBAS (both GPL-3.0) — personal local reference only, no redistribution. See D:\knowledge\CORPORA.md.
---

# lolbin-lookup — GTFOBins + LOLBAS structured quick-lookup

Living-off-the-land lookup for a specific binary, kept separate from the prose `secsearch` because
the query shape is different: **name → technique → command**, not free-text. Two local corpora:

- **GTFOBins** (Unix) — `D:\knowledge\gtfobins\_gtfobins\*` — extensionless YAML entries keyed by
  binary name (e.g. `nmap`, `tar`, `vim`). Each lists *functions* (techniques): `file-read`,
  `file-write`, `shell`, `command`, `suid`, `sudo`, `capabilities`, `library-load`, etc., each with a
  ready `code:` snippet.
- **LOLBAS** (Windows) — `D:\knowledge\lolbas\yml\**\*.yml` — one file per binary/script/library, with a
  `Commands:` list (each a `Command` + `Description` + `Category` (Execute/Download/...) + `MitreID` +
  `Privileges`).

## How to look up

```
pwsh skills/lolbin-lookup/scripts/lolbin-lookup.ps1 nmap            # both corpora
pwsh skills/lolbin-lookup/scripts/lolbin-lookup.ps1 certutil -Source lolbas
pwsh skills/lolbin-lookup/scripts/lolbin-lookup.ps1 tar  -Source gtfobins
pwsh skills/lolbin-lookup/scripts/lolbin-lookup.ps1 -List            # list every entry name
```

Output is a compact summary: for GTFOBins, `[GTFOBins] <name> — techniques: ...` then each technique's
command; for LOLBAS, `[LOLBAS] <name>` then each command tagged with its `Category` / `MitreID` /
`Privileges`. Name matching is case-insensitive substring, so `code` matches `code.exe`, `psh` matches
`PsHostProcess`, etc.

### Manual path (no helper)

### When to use which skill
### Refresh
