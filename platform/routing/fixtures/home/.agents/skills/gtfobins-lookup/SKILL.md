---
name: gtfobins-lookup
description: "Use when looking up authorized Unix living-off-the-land techniques, commands, and paired defensive detections in the local GTFOBins corpus."
license: Skill MIT. Indexed content is GTFOBins (GPL-3.0) - personal local reference only, no redistribution. See D:\knowledge\CORPORA.md.
---

# gtfobins-lookup — Linux GTFOBins/GTFOArgs lookup, abuse vector + detection/hardening

The Linux SUID/sudo/capability shell-escape lookup, the Unix analog to **lolbin-lookup** (which
covers Windows LOLBAS). The query shape is **binary name -> function/technique -> command**, and —
unlike a raw dump — every abuse vector is paired with its **blue-team detection and hardening** so the
output is usable by both an authorized pentester and a defender (know-it-to-detect-it).

Source corpus: **GTFOBins** (`gtfobins.github.io`), cloned offline at
`D:\knowledge\gtfobins\_gtfobins\*` — 478 extensionless YAML entries keyed by binary name. Each lists
*functions* (techniques): `shell`, `command`, `reverse-shell`, `bind-shell`, `file-read`,
`file-write`, `upload`, `download`, `library-load`, `privilege-escalation`, `inherit` — each with a
ready `code:` snippet and the privilege *contexts* it applies in (`unprivileged` / `sudo` / `suid` /
`capabilities`).

## How to look up

```
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 find          # all functions + detect/harden
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 tar -Function sudo     # only sudo-context entries
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 gdb -Function capabilities
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 vim -Quiet    # raw abuse vectors, no blue-team block
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 tar -GtfoArgs # also query GTFOArgs (network, opt-in)
pwsh skills/gtfobins-lookup/scripts/gtfobins-lookup.ps1 -List         # list every entry name

### Parameters
### Manual path (no helper)
### Blue-team framing (why offense is paired with defense)
### When to use which skill
### Refresh
