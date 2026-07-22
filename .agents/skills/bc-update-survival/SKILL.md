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
- `so_sha256 = 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`,
  `so_size 12 666 808`, build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`.
- **Real seed signature** — `getGlobal()` fingerprint: `48 8D 05 ?? ?? ?? ?? C3`
  (`lea rax,[rip+disp]; ret`; the 4 `disp` bytes are wildcarded because they
  point at a data pointer table that moves on relink). This is the exemplar the
  whole approach is built on and is covered by the module selftest.

## The offset table (single source of truth)
A JSON file keyed by function name; each entry carries the pinned `rva` **and**
its AOB `sig`. Save it under whichever consumer owns it (e.g.
`tools/offsets/en-15.4.1.json`). Schema:

```json
{
  "so": "libnative-lib.so",
  "version": "15.4.1",
  "sha256": "9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676",
  "offsets": {
    "getGlobal":  { "rva": "0x65D900", "sig": "48 8D 05 ?? ?? ?? ?? C3", "note": "getGlobal() -> MyApplication*" },
    "getScene":   { "rva": "0x668910", "sig": "",                        "note": "author me from the pinned .so" },
    "touchDispatch": { "rva": "0x668C70", "sig": "", "note": "vtable[+0x40]" }
  }
}
```
`sig: ""` means "not signatured yet" — author it once from the pinned `.so`
(below); thereafter every future update ports automatically by pattern.

## aob_resolver.py — author & resolve signatures
```
# Author a bullet-proof cross-version sig by byte-diffing the SAME function in
# two versions (needs the addr in both, e.g. from a ghidriff match). Wildcards
# EXACTLY the bytes that differ -> matches both by construction. No disassembler.
python aob_resolver.py author-diff old.so new.so 0x668910 0x669120 --name getScene

# Author a single-version sig at an RVA (capstone if importable, else a
# conservative rel32/RIP-disp32 heuristic; extends until unique).
python aob_resolver.py author libnative-lib.so 0x668910 --name getScene

# Resolve one signature (or a whole table) against a .so -> RVA(s).
python aob_resolver.py resolve new.so "48 8D 05 ?? ?? ?? ?? C3"
python aob_resolver.py resolve new.so --table tools/offsets/en-15.4.1.json

# List every match (uniqueness check).
python aob_resolver.py scan libnative-lib.so "48 8D 05 ?? ?? ?? ?? C3"

# Emit a Frida agent that Memory.scan's the live module for a table's sigs.
python aob_resolver.py gen-agent tools/offsets/en-15.4.1.json --module libnative-lib.so
```
Resolution status is `ok` (one match), `missing` (zero → relinked away / bad
sig), or `ambiguous` (>1 → sig not specific enough; re-author longer).

## Live resolution (Frida `search_memory`)
For a running BC on rooted BlueStacks (frida-server up; see `bc-drive`):
```
python aob_resolver.py live jp.co.ponos.battlecatsen tools/offsets/en-15.4.1.json
```
This attaches, injects the generated agent, and returns each function's live
runtime address **and** its `rva` (addr − module base). Runtime-resolving by AOB
means you never hardcode a base+RVA again — the search survives the relink at
runtime, the same way the offline scan does on disk. (Read-only scan; no per-
frame hook — obeys the bc-drive hot-path rule.)

## ghidriff_port.py — auto-port the whole table across an update
```
# PRIMARY, no Ghidra: re-scan the new .so for each entry's sig, write new RVAs.
python ghidriff_port.py port-aob tools/offsets/en-15.4.1.json new.so \
    --out tools/offsets/en-15.5.0.json
#   entries lacking a sig are auto-authored from --old-so first:
python ghidriff_port.py port-aob table.json new.so --old-so old.so --out new.json

# Cross-check via ghidriff (Ghidra BinDiff-style function matching).
#   1) produce the diff (LONG — Ghidra analysis, minutes; wrap with longrun):
python ghidriff_port.py diff old.so new.so --out ghidriff-out
#   2) port the table from ghidriff's matched pairs (pure logic):
python ghidriff_port.py port-ghidriff table.json ghidriff-out/*.ghidriff.json \
    --ghidra-base 0x100000 --out new.json
```
`--ghidra-base` subtracts Ghidra's load base so emitted RVAs stay file-relative
(BC base 0x0 usually loads at Ghidra `0x100000`). The **AOB path is base-
independent** (it scans the raw file) — prefer it; use ghidriff to cross-check
and to bulk-author sigs for functions you have not pinned yet.

## Update-triage workflow (per version bump)
```
# One command: extract the .so from each APK (or pass .so directly),
# sha-compare, and — if the native code changed — port the table via AOB
# (and cross-check with ghidriff if --ghidriff).
python ghidriff_port.py triage bc-15.4.1.apk bc-15.5.0.apk \
    --table tools/offsets/en-15.4.1.json --out tools/offsets/en-15.5.0.json
```
`triage` pulls `lib/x86_64/libnative-lib.so` out of the APK (an APK is a zip — no
apktool needed for the native lib), sha256-compares, and only ports when the
`.so` actually changed (`native code UNCHANGED` → your pinned offsets are still
valid, zero work). Full per-bump checklist:

1. **Grab both builds** — old (pinned) APK + new APK.
2. **Native diff** (this tool) — `triage` → if unchanged, done; else it ports
   the offset table by AOB and (optionally) cross-checks with ghidriff.
3. **Verify moved offsets** — any `missing`/`ambiguous` entry needs a re-authored
   sig (open old+new in `ida-multi-mcp` → `similar_functions` re-finds the moved
   function name-independently → `author-diff` a fresh cross-version sig).
4. **Resource / DAT diff** (out-of-band for offsets, in-scope for behavior) —
   `apktool d bc-15.5.0.apk` on both, then diff `res/`, `assets/`, smali, and the
   `AndroidManifest` `clientVersion`; decrypt/compare event `DAT` packs with the
   BC pack tooling (see `battlecats-event-unlock` for the schedule-band format).
5. **Bump the pinned table** — save the ported table as `en-<newver>.json`, set
   its `version` + `sha256`, and point `bc-drive` / `battlecats-event-unlock` at
   it. Record the old version in the table `changelog` (don't delete it).

## SHADOW drift gate (council C5 — never blocks, never nags)
A safety net that catches "you are about to act on stale offsets":
```
python aob_resolver.py verify tools/offsets/en-15.4.1.json /path/to/live/libnative-lib.so
```
It re-resolves every pinned sig in the given `.so` and compares to the pinned
RVA. Drift (a moved/missing/ambiguous function, or a changed `so_sha256`) is
**observed and logged only** — appended to a bounded, auto-rotating sink
(`~/.Codex/logs/bc-update-survival-drift.log`, cap 256 KB + one rotation;
override with `$BC_DRIFT_SINK`). It **always exits 0**, prints advisory `advice`,
and never blocks or fails a caller. This is the shadow-first, reversible path the
council mandated for new gates: the loud "offsets stale — re-port before trusting
RVAs" is a suggestion, not an interrupt. The companion always-on module
`bc_offset_guard` (E.2, folded into the harness) is the graduation target; this
skill's gate stays project-scoped and observe-only.

## Requirements / optional deps
- **AOB offline path + porting + triage:** pure Python, **no third-party deps**.
- `frida` (installed, 17.x) — only for the `live` backend + a running device.
- `capstone` (optional) — sharpens single-version `author`; the byte heuristic is
  the fallback and matches the real getGlobal sig.
- `pyelftools` (optional, installed) — sharpens `--elf-sections` for a general
  ELF; unnecessary for BC (imagebase 0 → RVA == offset).
- `ghidriff` (installed, 1.0.0) + `GHIDRA_INSTALL_DIR` — only for `diff` /
  `port-ghidriff`; missing toolchain degrades gracefully to the AOB path.

## Verify it works
Both modules ship a real offline selftest (no device needed):
```
python aob_resolver.py selftest     # 27 checks incl. the relink-survival proof
python ghidriff_port.py selftest    # 21 checks incl. AOB + ghidriff + APK triage
```
The keystone check builds two synthetic `.so`s where a function is relinked to a
new offset, authors a signature on v1, and proves it re-locates the function at
its new address in v2 — the whole reason the toolpack exists.

## Safety & honest limits
- **Read-only / additive.** Scans files and (read-only) live memory; never writes
  the game, never patches, never spends currency. The drift gate never blocks.
- **AOB is only as good as the sig.** A too-short sig → `ambiguous`; over-
  wildcarding → `ambiguous`; under-wildcarding a reloc byte → breaks on relink.
  `author-diff` (byte-diff of two known versions) is bullet-proof; the single-
  version heuristic is best-effort (prefer capstone, and always verify uniqueness
  with `scan`).
- **ghidriff addresses carry Ghidra's image base** — use `--ghidra-base`. The AOB
  path avoids this entirely.
- **Not a decompiler / not a save editor / not a UI driver.** Pair with:
  `game-re-binary`, `ida-multi-mcp` (BCSD re-find), `ghidra-mcp`, `frida` (RE);
  `bc-drive` (live canvas driving); `battlecats-event-unlock` (event offsets);
  `bcsfe-save-roundtrip` (saves).

## Evidence
MASTER-DECISION-QUEUE §E.2 (V×E H×M, BUILD, verified): "AOB wildcard-signature
resolver (retire hardcoded RVAs; survive relink via `frida search_memory`) ·
ghidriff (one-command cross-version `.so` diff → auto-port the offset table) · BC
update-triage skill (decode+diff APK/DAT/.so per version bump)." Shadow-gate
discipline per COUNCIL-VERDICT §C5. BC ground truth from `battlecats-event-unlock`
+ `bc-drive` (both EN 15.4.1, x86_64, imagebase 0).
