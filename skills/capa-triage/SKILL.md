---
name: capa-triage
description: "Use when identifying capabilities in a PE, ELF, .NET binary, or shellcode with Mandiant capa before deeper authorized analysis."
license: 'capa + capa-rules are Apache-2.0 (Mandiant).'
---

# capa-triage — capability detection for executables (ATT&CK / MBC)

capa answers "what does this binary DO?" WITHOUT running it — it disassembles a PE/ELF/.NET/
shellcode file, matches ~1000 rules, and reports capabilities mapped to MITRE ATT&CK and MBC
(Malware Behavior Catalog). Run it FIRST on an unknown/suspicious binary to see where to aim the
deep RE (IDA / Ghidra / Binary-Ninja / HexStrike), then dig into the addresses it points at.

## Run

```
python C:\Users\Prekzursil\.agents\skills\capa-triage\scripts\capa_triage.py <BINARY> [-j] [-v|-vv]
```
The wrapper defaults the rules + sigs (`~/.capa/rules`, `~/.capa/sigs`); override with the
`CAPA_RULES` / `CAPA_SIGS` env vars. Or call capa directly:
```
python -m capa.main -r C:\Users\Prekzursil\.capa\rules -s C:\Users\Prekzursil\.capa\sigs <BINARY>
```
Flags: `-j` machine-readable JSON · `-v` show rule matches · `-vv` show matched ADDRESSES (jump
straight to them in your disassembler) · `-f sc32`/`sc64` raw shellcode · `-d` debug stack trace.

## What it reports

A table of **Capability → Namespace** (e.g. `parse PE header → load-code/pe`, `terminate process
→ host-interaction/process/terminate`), plus **ATT&CK Tactic/Technique** and **MBC Objective/
Behavior** roll-ups. Namespaces group by behavior (host-interaction, communication, anti-analysis,
crypto, load-code, persistence, …) — a fast map of the binary's surface before you commit hours.

## Setup (already done on this machine, 2026-07-04)

flare-capa 9.4.0 (pip, user site). The pip LIBRARY ships WITHOUT rules/sigs (only the standalone
release binary bundles them), so they were fetched once:
- rules: `git clone --depth 1 https://github.com/mandiant/capa-rules ~/.capa/rules` (1055 rules)
- sigs:  sparse-checkout of `sigs/` from the capa repo → `~/.capa/sigs`

Refresh rules later with `git -C ~/.capa/rules pull`. If capa warns of a rules/version mismatch,
checkout the capa-rules tag matching the installed capa version.

## Acceptance (verified 2026-07-04)

`capa_triage.py C:\Windows\System32\where.exe` → exit 0 and a capability table including
`terminate process (2 matches) → host-interaction/process/terminate` and
`parse PE header (3 matches) → load-code/pe`. A correct run yields the ATT&CK/MBC/Capability table
(or a clean empty table for a capability-free file), NOT the "default embedded rules not found" /
"install the signatures first" errors (those mean the -r/-s paths are missing).

## Notes

- Complements `reverse-engineering-toolkit` / `game-re-binary`: capa says WHAT (behavior), the
  disassemblers say WHERE/HOW. `-vv` gives the addresses — pivot straight to IDA/Ghidra there.
- capa runs the analysis statically (no execution) so it's safe on untrusted samples, but treat
  the sample file itself with the usual malware-handling care.
