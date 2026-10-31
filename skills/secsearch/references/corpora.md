---
title: corpora
type: note
permalink: dqverify-repo-20261013/skills/secsearch/references/corpora
---

# secsearch corpora reference

Catalogue of what `secsearch` indexes. Authoritative manifest + licenses: `D:\knowledge\CORPORA.md`.

| Corpus | Path under D:\knowledge | Best for | Glob |
|---|---|---|---|
| HackTricks | `hacktricks\**\src\**\*.md` | pentest, AD, cloud, web, mobile, forensics, OS internals | `**/*.md` |
| PayloadsAllTheThings | `payloadsallthethings\**\*.md` | per-vuln-class payloads + methodology (SQLi, XSS, SSRF, AD) | `**/*.md` |
| OWASP WSTG | `owasp-wstg\**\*.md` | web app test cases (WSTG-IDNT-*, WSTG-SESS-*, ...) | `**/*.md` |
| OWASP CheatSheets | `owasp-cheatsheets\**\*.md` | defensive AppSec guidance / secure-coding | `**/*.md` |
| Atomic Red Team | `atomic-red-team\**\*.md` (+ `*.yaml`) | ATT&CK technique docs `T####.md` + executable atomics | `**/*.md` |
| GTFOBins | `gtfobins\_gtfobins\*` (extensionless YAML) | Unix living-off-the-land — use **lolbin-lookup** | `**/*` |
| LOLBAS | `lolbas\yml\**\*.yml` | Windows living-off-the-land — use **lolbin-lookup** | `**/*.yml` |

Notes:
- Provenance = first path segment after `knowledge` (`…\<corpus>\…`).
- GTFOBins entries have **no file extension**, so the default `**/*.md` glob skips them on
  purpose — query them through the structured `lolbin-lookup` skill instead.
- Atomic Red Team also ships per-technique `*.yaml` atomics; fold them in with
  `-Glob "**/*.{md,yaml}"` if you want the executable test commands.