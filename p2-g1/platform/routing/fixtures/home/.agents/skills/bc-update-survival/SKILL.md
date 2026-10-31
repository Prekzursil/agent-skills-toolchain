---
name: bc-update-survival
description: Use when a Battle Cats (EN, jp.co.ponos.battlecatsen) update relinks lib/x86_64/libnative-lib.so and your pinned RVAs go stale — the toolpack that RETIRES hardcoded offsets. AOB wildcard-signature resolver (author a byte pattern that wildcards only the reloc-sensitive bytes, then re-locate the function by pattern via offline .so scan or live `frida search_memory`/Memory.scan — survives relink where a fixed RVA does not); ghidriff one-command cross-version .so diff that AUTO-PORTS the whole offset table old→new; and a per-version-bump update-triage (extract + sha-compare + diff APK/DAT/.so). Ships a SHADOW-mode drift gate (observe + log only, never blocks). Use before trusting any bc-drive / battlecats-event-unlock offset after a version bump. NOT for save-file edits (bcsfe-save-roundtrip) or live UI driving (bc-drive).
---

# bc-update-survival — survive BC updates automatically

Battle Cats ships an update, `lib/x86_64/libnative-lib.so` is recompiled and
**relinked**, and every hardcoded RVA in your offset tables (`bc-drive`,
`battlecats-event-unlock`) is now wrong. **Acting on a stale offset is the worst
failure mode** — a call to the wrong address crashes BC or trips the HGT anti-
tamper trap. This toolpack re-derives the offsets automatically instead.

The core idea: a function's **opcodes are stable across an update even when its
address moves**. Pin functions by a wildcard **byte signature (AOB)** — fixing
the opcodes, wildcarding the bytes that move on relink (rel32 call/jump
displacements, RIP-relative `disp32`, reloc'd immediates) — and re-locate them
by pattern after every update. A signature survives; an RVA does not.

## Files
- `aob_resolver.py` — the AOB signature engine: parse/match, author (single-
  version heuristic **or** robust cross-version byte-diff), offline `.so` scan,
  live Frida `Memory.scan`, and a SHADOW drift gate.
- `ghidriff_port.py` — cross-version `.so` diff + **auto-port the offset table**
  (AOB re-scan, primary; ghidriff function-matching, cross-check) + the
  version-bump `triage` orchestration (handles `.apk` inputs).
- `SKILL.md` — this file.

## BC ground truth (EN 15.4.1)
- `lib/x86_64/libnative-lib.so` has **imagebase 0x0**, so **RVA == file offset**
  (per `battlecats-event-unlock`). `--imagebase 0` (the default) is exact for BC;
  runtime address = `module.base + RVA`.

### The offset table (single source of truth)
### aob_resolver.py — author & resolve signatures
### Author a bullet-proof cross-version sig by byte-diffing the SAME function in
### two versions (needs the addr in both, e.g. from a ghidriff match). Wildcards
### EXACTLY the bytes that differ -> matches both by construction. No disassembler.
### Author a single-version sig at an RVA (capstone if importable, else a
### conservative rel32/RIP-disp32 heuristic; extends until unique).
### Resolve one signature (or a whole table) against a .so -> RVA(s).
### List every match (uniqueness check).
### Emit a Frida agent that Memory.scan's the live module for a table's sigs.
### Live resolution (Frida `search_memory`)
