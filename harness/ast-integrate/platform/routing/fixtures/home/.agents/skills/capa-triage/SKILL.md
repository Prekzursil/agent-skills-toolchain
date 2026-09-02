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
python C:\Users\agentuser\.agents\skills\capa-triage\scripts\capa_triage.py <BINARY> [-j] [-v|-vv]
```
The wrapper defaults the rules + sigs (`~/.capa/rules`, `~/.capa/sigs`); override with the
`CAPA_RULES` / `CAPA_SIGS` env vars. Or call capa directly:
```
python -m capa.main -r C:\Users\agentuser\.capa\rules -s C:\Users\agentuser\.capa\sigs <BINARY>
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

### Acceptance (verified 2026-07-04)
### Notes
