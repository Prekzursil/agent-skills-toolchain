---
name: gtfobins-lookup
description: Use when looking up authorized Unix living-off-the-land techniques, commands,
  and paired defensive detections in the local GTFOBins corpus.
license: Skill MIT. Indexed content is GTFOBins (GPL-3.0) - personal local reference
  only, no redistribution. See D:\knowledge\CORPORA.md.
permalink: dqverify-repo-20261013/skills/gtfobins-lookup/skill
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
```

For each match the tool prints `===== [GTFOBins] <name> — functions: ...`, then each function's
`code:` snippet tagged with its contexts `{sudo,suid,...}`, then a **BLUE TEAM** block: per function its
MITRE ATT&CK ID + `DETECT` + `HARDEN`, plus a per-context block for any privilege-bearing context
(`suid` / `sudo` / `capabilities`) present. `-Function` accepts a function name (`shell`, `file-read`,
...) **or** a privilege context (`sudo`, `suid`, `capabilities`) and filters to functions usable that
way. Name matching is case-insensitive substring (`tar` also matches `setarch`, `start-stop-daemon`).

### Parameters

- `-Function <name|context>` — filter to one function/technique or to a privilege context.
- `-Quiet` — suppress the detection/hardening block (raw abuse vectors only).
- `-GtfoArgs` — also query **GTFOArgs** (argument-injection analog). No local mirror exists, so this is
  an **opt-in network fetch** of `gtfoargs.github.io/api.json`, cached for 7 days under
  `%LOCALAPPDATA%\gtfobins-lookup`. Fails gracefully offline (prints the canonical URL + defense note).
- `-Max <n>` — cap matches (default 10). `-Root <path>` — corpus root (default `$env:SEC_CORPORA_ROOT`
  or `D:\knowledge`).

### Manual path (no helper)

- GTFOBins entry: open `D:\knowledge\gtfobins\_gtfobins\<binary>` directly — the whole entry is short.
- Canonical function -> MITRE map + descriptions: `D:\knowledge\gtfobins\_data\functions.yml`.
- GTFOArgs has no local clone — query `https://gtfoargs.github.io/gtfoargs/<binary>/` in a browser.

## Blue-team framing (why offense is paired with defense)

This skill exists for **defenders as much as testers**. The function -> MITRE -> detect/harden table is
baked into the script (sourced from GTFOBins `functions.yml` + the security-kb `linux-privesc.md`
defenses). Examples it emits: `shell` -> ATT&CK T1059 -> *detect via auditd/EDR execve of /bin/sh whose
parent is this binary from a cron/service context*; `suid` context -> *diff `find / -perm -4000` against
a golden baseline + auditd setuid syscall*; `capabilities` -> *baseline-diff `getcap -r /` + decode
CapEff*. The output is directly actionable as a remediation backlog and as Sigma/auditd/Falco rule seeds.

## When to use which skill

- **gtfobins-lookup (this skill):** a specific **Linux** binary — its SUID/sudo/cap abuse + detection.
- **lolbin-lookup:** the Windows (LOLBAS) + cross-platform (GTFOBins prose) sibling.
- **security-kb-lookup / secsearch:** prose, cross-source technique lookups (offense+defense+ATT&CK).
- For the ATT&CK context behind a technique ID, pivot into `secsearch` against `atomic-red-team`
  (`T####.md`).

## Refresh

`pwsh D:\knowledge\sec-corpora-update.ps1` (or the **sec-corpora-update** skill) refreshes the GTFOBins
clone. The detection/hardening table is static in the script; update it if `functions.yml` gains a
new function type.

> Scope/ethics: for authorized penetration testing, blue-team detection/hardening, CTF, reverse
> engineering, and education only. No target lists, no turnkey attack automation against third parties.