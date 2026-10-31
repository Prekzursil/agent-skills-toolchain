---
name: lolbin-lookup
description: Structured living-off-the-land binary lookup against the local GTFOBins
  (Unix) and LOLBAS (Windows) corpora under D:\knowledge. Answers "what can binary
  X do" - name to technique/category to ready command - by parsing GTFOBins YAML (file-read,
  file-write, shell, suid, sudo) and LOLBAS yml Commands. Use when you have a specific
  binary (nmap, certutil, tar, msbuild) and want its abuse techniques.
license: Skill MIT. Indexed content is GTFOBins and LOLBAS (both GPL-3.0) — personal
  local reference only, no redistribution. See D:\knowledge\CORPORA.md.
permalink: dqverify-repo-20261013/skills/lolbin-lookup/skill
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

- GTFOBins entry: open `D:\knowledge\gtfobins\_gtfobins\<binary>` directly — the whole entry is short.
- LOLBAS entry: the files are named after the binary, e.g. `D:\knowledge\lolbas\yml\OSBinaries\Certutil.yml`.
  Grep them with the Grep tool (path `D:\knowledge\lolbas\yml`, glob `**/*.yml`) when you want full detail.

## When to use which skill

- **lolbin-lookup (this skill):** you already know the binary and want its abuse techniques + exact commands.
- **gtfobins-lookup:** the Unix-only sibling over the same GTFOBins corpus, but every abuse
  vector is paired with its blue-team detection + hardening. Reach for it when the answer must
  also serve a defender; stay here for the faster two-corpora (GTFOBins + LOLBAS) summary.
- **secsearch:** prose/cross-source security lookups (techniques, CVE classes, methodology) over all corpora.
- For ATT&CK context behind a `MitreID`, pivot into `secsearch` against `atomic-red-team` (`T####.md`).

## Refresh

`pwsh D:\knowledge\sec-corpora-update.ps1` (or the **sec-corpora-update** skill) refreshes GTFOBins and LOLBAS.