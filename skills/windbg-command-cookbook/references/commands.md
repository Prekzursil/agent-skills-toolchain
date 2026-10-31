---
title: commands
type: note
permalink: dqverify-repo-20261013/skills/windbg-command-cookbook/references/commands
---

# WinDbg Command Cookbook

## First-pass commands

- `!analyze -v` -> quick crash triage
- `.ecxr` -> switch to exception context when available
- `k`, `kv`, `kn` -> stack views
- `~` and `~* k` -> thread overview and stacks
- `lm` / `lmv m <module>` -> module inventory and details
- `r` -> current register state
- `u <address>` -> disassemble near an address of interest

## What to capture

Always preserve:
- exception code and faulting address
- owning thread ID
- module name + module base
- stack frames around the fault
- any module-relative addresses you plan to inspect in a disassembler

## Handoff targets

- Use `$swfoc-runtime-address-hunting` when the target is SWFOC-specific runtime state.
- Use `$dump-to-signature-workflow` when the dump evidence needs to become a stable signature or comparison artifact.